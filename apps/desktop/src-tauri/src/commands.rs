use std::sync::{Arc, Mutex};
use std::time::Duration;

use reqwest::Client;
use serde_json::{json, Value};
use tauri::{AppHandle, State};

use crate::engine_paths;
use crate::secrets::SecretVault;
use crate::sidecar::EngineSupervisor;
use crate::sidecar_runtime::SidecarRuntime;
use crate::start_desktop_sidecar;
use crate::ui_language::{self, UiLanguageSnapshot};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_opener::OpenerExt;

#[derive(Clone)]
struct Connection {
    endpoint: String,
    auth_token: String,
}

type Redactor = Arc<dyn Fn(&str) -> String + Send + Sync>;

#[derive(Clone)]
pub struct EngineConnection {
    connection: Arc<Mutex<Option<Connection>>>,
    locale: Arc<Mutex<Option<String>>>,
    redactor: Redactor,
}

impl Default for EngineConnection {
    fn default() -> Self {
        Self {
            connection: Arc::new(Mutex::new(None)),
            locale: Arc::new(Mutex::new(None)),
            redactor: Arc::new(|text| text.to_string()),
        }
    }
}

impl EngineConnection {
    pub fn set(&self, endpoint: String, auth_token: String) -> Result<(), String> {
        let mut connection = self
            .connection
            .lock()
            .map_err(|_| "engine connection lock poisoned")?;
        *connection = Some(Connection {
            endpoint,
            auth_token,
        });
        Ok(())
    }

    pub fn with_redactor(redactor: Redactor) -> Self {
        Self {
            connection: Arc::new(Mutex::new(None)),
            locale: Arc::new(Mutex::new(None)),
            redactor,
        }
    }

    pub fn clear(&self) {
        if let Ok(mut connection) = self.connection.lock() {
            *connection = None;
        }
    }

    #[cfg(test)]
    fn is_configured(&self) -> bool {
        self.connection
            .lock()
            .map(|guard| guard.is_some())
            .unwrap_or(false)
    }

    pub fn set_locale(&self, locale: &str) -> Result<(), String> {
        if locale != "zh" && locale != "en" {
            return Err("locale must be the resolved language zh or en".into());
        }
        let mut slot = self
            .locale
            .lock()
            .map_err(|_| "engine locale lock poisoned")?;
        *slot = Some(locale.to_string());
        Ok(())
    }

    fn inject_locale(&self, mut request: Value) -> Value {
        let locale = self
            .locale
            .lock()
            .ok()
            .and_then(|guard| guard.clone());
        if let Some(locale) = locale {
            if let Some(object) = request.as_object_mut() {
                object.entry("locale").or_insert(json!(locale));
            }
        }
        request
    }

    async fn post(&self, request: Value) -> Result<Value, String> {
        let request = self.inject_locale(request);
        let connection = self
            .connection
            .lock()
            .map_err(|_| "engine connection lock poisoned")?
            .clone()
            .ok_or("engine is not ready")?;
        let redact = self.redactor.clone();
        let response = Client::builder()
            .timeout(Duration::from_secs(command_timeout_secs_from_env()))
            .build()
            .map_err(|error| redact(&error.to_string()))?
            .post(format!("{}/commands", connection.endpoint))
            .bearer_auth(connection.auth_token)
            .json(&request)
            .send()
            .await
            .map_err(|error| {
                if error.is_timeout() {
                    let envelope = json!({
                        "error": "行情请求在壳层等待时超时，引擎还没返回。请稍后重试。（MARKET_DATA_TIMEOUT）",
                        "code": "MARKET_DATA_SHELL_TIMEOUT",
                        "params": {},
                        "detail": null,
                    });
                    redact(&envelope.to_string())
                } else {
                    redact(&error.to_string())
                }
            })?;
        let status = response.status();
        let body = response
            .text()
            .await
            .map_err(|error| redact(&error.to_string()))?;
        if !status.is_success() {
            return Err(redact(&parse_engine_error_body(&body)));
        }
        serde_json::from_str(&body).map_err(|error| redact(&error.to_string()))
    }
}

/// Desktop wait for one engine command. Must stay above the Python load
/// deadline in `shell_command_timeout_seconds` (40 batches × seconds-per-batch,
/// or the explicit timeout, plus 120s).
fn command_timeout_secs(explicit: Option<u64>, sec_per_batch: u64) -> u64 {
    const MARGIN_SECS: u64 = 120;
    const BATCHES: u64 = 40;
    match explicit {
        Some(value) => value.saturating_add(MARGIN_SECS),
        None => sec_per_batch.saturating_mul(BATCHES).saturating_add(MARGIN_SECS),
    }
}

fn command_timeout_secs_from_env() -> u64 {
    let explicit = std::env::var("ALPHALOOP_MARKET_DATA_TIMEOUT_SEC")
        .ok()
        .and_then(|value| value.parse::<f64>().ok())
        .map(|value| value.ceil() as u64);
    let per_batch = std::env::var("ALPHALOOP_MARKET_DATA_SEC_PER_BATCH")
        .ok()
        .and_then(|value| value.parse::<f64>().ok())
        .map(|value| value.ceil() as u64)
        .unwrap_or(60);
    command_timeout_secs(explicit, per_batch)
}

fn parse_engine_error_body(body: &str) -> String {
    if let Ok(payload) = serde_json::from_str::<Value>(body) {
        if payload.get("code").and_then(|value| value.as_str()).is_some() {
            return body.to_string();
        }
        if let Some(message) = payload.get("error").and_then(|value| value.as_str()) {
            return message.to_string();
        }
    }
    body.to_string()
}

fn notification_title(kind: &str) -> Option<&'static str> {
    match kind {
        "awaiting_confirm" => Some("有研究在等你确认"),
        "completed" => Some("研究已完成"),
        "ended" => Some("研究已结束"),
        _ => None,
    }
}

fn notify_kinds(payload: &serde_json::Value) -> Vec<&str> {
    if let Some(items) = payload.get("notifies").and_then(|value| value.as_array()) {
        return items.iter().filter_map(|item| item.as_str()).collect();
    }
    payload
        .get("notify")
        .and_then(|value| value.as_str())
        .into_iter()
        .collect()
}

fn maybe_notify(app: &tauri::AppHandle, payload: &serde_json::Value) {
    for kind in notify_kinds(payload) {
        if let Some(title) = notification_title(kind) {
            let _ = app.notification().builder().title(title).show();
        }
    }
}

async fn mutate(
    app: &AppHandle,
    connection: &EngineConnection,
    request: Value,
) -> Result<Value, String> {
    let payload = connection.post(request).await?;
    maybe_notify(app, &payload);
    Ok(payload)
}

#[tauri::command]
pub async fn fetch_view(
    route: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<Value, String> {
    mutate(
        &app,
        &connection,
        json!({"type": "fetch_view", "route": route}),
    )
    .await
}

#[tauri::command]
pub async fn market_data_progress(
    connection: State<'_, EngineConnection>,
) -> Result<Value, String> {
    connection
        .post(json!({"type": "market_data_progress"}))
        .await
}

#[tauri::command]
pub async fn create_draft(connection: State<'_, EngineConnection>) -> Result<String, String> {
    let result = connection.post(json!({"type": "create_draft"})).await?;
    result["research_id"]
        .as_str()
        .map(str::to_owned)
        .ok_or("create_draft response omitted research_id".into())
}

#[tauri::command]
pub async fn confirm_run(
    research_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "confirm_run", "research_id": research_id}),
    )
    .await
    .map(|_| ())
}


#[tauri::command]
pub async fn unlock_brief(
    research_id: String,
    slot: Option<String>,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    let mut request = json!({"type": "unlock_brief", "research_id": research_id});
    if let Some(slot) = slot {
        request["slot"] = json!(slot);
    }
    mutate(
        &app,
        &connection,
        request,
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn send_dialogue(
    research_id: String,
    message: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "send_dialogue", "research_id": research_id, "message": message}),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn pause_research(
    research_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "pause", "research_id": research_id}),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn resume_research(
    research_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "resume", "research_id": research_id}),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn confirm_modification(
    research_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "confirm_modification", "research_id": research_id}),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn continue_iterate(
    research_id: String,
    user_confirmed: bool,
    high_suspicion_acknowledged: Option<bool>,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    let mut body = json!({
        "type": "continue_iterate",
        "research_id": research_id,
        "user_confirmed": user_confirmed
    });
    if let Some(value) = high_suspicion_acknowledged {
        body["high_suspicion_acknowledged"] = json!(value);
    }
    mutate(&app, &connection, body).await.map(|_| ())
}

#[tauri::command]
pub async fn extend_research(
    research_id: String,
    hours: f64,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({
            "type": "extend_research",
            "research_id": research_id,
            "hours": hours
        }),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn delete_research(
    research_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "delete_research", "research_id": research_id}),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn resolve_confirm(
    research_id: String,
    decision: String,
    who_pays: Option<String>,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    let mut body = json!({
        "type": "resolve_confirm",
        "research_id": research_id,
        "decision": decision
    });
    if let Some(value) = who_pays.filter(|item| !item.is_empty()) {
        body["who_pays"] = json!(value);
    }
    mutate(&app, &connection, body).await.map(|_| ())
}

#[tauri::command]
pub async fn export_artifact(
    research_id: String,
    kind: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<String, String> {
    let payload = mutate(
        &app,
        &connection,
        json!({"type": "export_artifact", "research_id": research_id, "kind": kind}),
    )
    .await?;
    payload["path"]
        .as_str()
        .map(str::to_owned)
        .ok_or("export_artifact response omitted path".into())
}

#[tauri::command]
pub fn reveal_export_in_folder(path: String, app: AppHandle) -> Result<(), String> {
    if app.opener().reveal_item_in_dir(&path).is_ok() {
        return Ok(());
    }
    let parent = std::path::Path::new(&path)
        .parent()
        .ok_or_else(|| "无法打开文件夹：路径无效".to_string())?;
    app.opener()
        .open_path(parent.to_string_lossy().to_string(), None::<&str>)
        .map_err(|error| format!("无法打开文件夹：{}", error))
}

#[tauri::command]
pub async fn reverify(
    research_id: String,
    round_id: String,
    method_id: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({
            "type": "reverify",
            "research_id": research_id,
            "round_id": round_id,
            "method_id": method_id
        }),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn revise_method(
    method_id: String,
    definition: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "revise_method",
            "method_id": method_id,
            "definition": definition
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn create_method(
    name: String,
    definition: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "create_method",
            "method_id": format!("user.{name}"),
            "name": name,
            "description": definition,
            "body": definition,
            "source": "deposited"
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub fn engine_sidecar_state(runtime: State<'_, Arc<SidecarRuntime>>) -> Result<Value, String> {
    let ui = runtime.ui.lock().map_err(|_| "sidecar ui lock poisoned")?;
    let phase = match ui.phase {
        crate::sidecar_policy::SidecarUiPhase::Running => "running",
        crate::sidecar_policy::SidecarUiPhase::Restarting => "restarting",
        crate::sidecar_policy::SidecarUiPhase::Stopped => "stopped",
    };
    Ok(json!({
        "phase": phase,
        "restartCount": ui.restart_count,
        "maxRestarts": ui.max_restarts,
        "message": ui.message,
    }))
}

#[tauri::command]
pub fn get_ui_language() -> UiLanguageSnapshot {
    ui_language::current_snapshot()
}

#[tauri::command]
pub fn set_ui_language(
    preference: String,
    connection: State<'_, EngineConnection>,
) -> Result<UiLanguageSnapshot, String> {
    ui_language::write_ui_language_preference(&ui_language::settings_file(), &preference)?;
    let snapshot = ui_language::current_snapshot();
    connection.set_locale(&snapshot.resolved)?;
    Ok(snapshot)
}

#[tauri::command]
pub fn read_system_locale() -> Option<String> {
    ui_language::read_system_locale_tag()
}

#[tauri::command]
pub fn set_engine_locale(
    locale: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection.set_locale(&locale)
}

#[tauri::command]
pub fn restart_engine_sidecar(
    app: AppHandle,
    runtime: State<'_, Arc<SidecarRuntime>>,
    supervisor: State<'_, Arc<EngineSupervisor>>,
    connection: State<'_, EngineConnection>,
    vault: State<'_, Arc<SecretVault>>,
) -> Result<(), String> {
    runtime.prepare_user_restart();
    supervisor.quit()?;
    engine_paths::clear_owner_file()?;
    connection.clear();
    start_desktop_sidecar(
        app,
        supervisor.inner().clone(),
        connection.inner().clone(),
        runtime.inner().clone(),
        (*vault).clone(),
    )
}

pub async fn push_installed_secrets(connection: &EngineConnection, vault: &SecretVault) {
    let secrets = vault.export_map();
    let result = connection
        .post(json!({"type": "install_secrets", "secrets": secrets}))
        .await;
    if let Err(error) = result {
        eprintln!("{}", vault.redact(&error));
    }
}

#[tauri::command]
pub async fn secret_store_status(vault: State<'_, Arc<SecretVault>>) -> Result<Value, String> {
    Ok(serde_json::to_value(vault.status()).map_err(|error| vault.redact(&error.to_string()))?)
}

#[tauri::command]
pub fn secret_choose_fallback(choice: String, vault: State<'_, Arc<SecretVault>>) -> Result<(), String> {
    vault.choose_fallback(&choice)
}

#[tauri::command]
pub async fn secret_set(
    id: String,
    value: String,
    passphrase: Option<String>,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
    vault: State<'_, Arc<SecretVault>>,
) -> Result<(), String> {
    let _ = app;
    vault.set(&id, &value, passphrase.as_deref())?;
    push_installed_secrets(&connection, &vault).await;
    Ok(())
}

#[tauri::command]
pub async fn secret_delete(
    id: String,
    connection: State<'_, EngineConnection>,
    vault: State<'_, Arc<SecretVault>>,
) -> Result<(), String> {
    vault.delete(&id)?;
    push_installed_secrets(&connection, &vault).await;
    Ok(())
}

#[tauri::command]
pub fn secret_is_set(id: String, vault: State<'_, Arc<SecretVault>>) -> Result<bool, String> {
    vault.is_set(&id)
}

#[tauri::command]
pub async fn secret_unlock(
    passphrase: String,
    connection: State<'_, EngineConnection>,
    vault: State<'_, Arc<SecretVault>>,
) -> Result<(), String> {
    vault.unlock(&passphrase)?;
    push_installed_secrets(&connection, &vault).await;
    Ok(())
}

#[tauri::command]
pub async fn secret_failure_preview(
    id: String,
    connection: State<'_, EngineConnection>,
    vault: State<'_, Arc<SecretVault>>,
) -> Result<String, String> {
    let payload = connection
        .post(json!({"type": "secret_failure_preview", "secret_id": id}))
        .await
        .map_err(|error| vault.redact(&error))?;
    let message = payload
        .get("message")
        .and_then(|value| value.as_str())
        .unwrap_or("失败说明不可用。");
    Ok(vault.redact(message))
}

#[cfg(test)]
mod tests {
    use super::{
        EngineConnection, command_timeout_secs, notification_title, notify_kinds,
        parse_engine_error_body,
    };
    use serde_json::json;

    #[test]
    fn notify_titles_cover_only_awaiting_and_terminal_states() {
        assert_eq!(
            notification_title("awaiting_confirm"),
            Some("有研究在等你确认")
        );
        assert_eq!(notification_title("completed"), Some("研究已完成"));
        assert_eq!(notification_title("ended"), Some("研究已结束"));
        assert_eq!(notification_title("paused"), None);
        assert_eq!(notification_title("running"), None);
        assert_eq!(notification_title("draft"), None);
    }

    #[test]
    fn engine_connection_clear_drops_stored_endpoint() {
        let conn = EngineConnection::default();
        conn.set("http://127.0.0.1:9".into(), "token".into())
            .expect("set");
        assert!(conn.is_configured());
        conn.clear();
        assert!(!conn.is_configured());
    }

    #[test]
    fn command_timeout_stays_above_the_v2_fetch_budget() {
        assert_eq!(command_timeout_secs(None, 60), 60 * 40 + 120);
        assert!(command_timeout_secs(None, 60) > 38 * 60);
        assert!(command_timeout_secs(None, 60) > 13 * 60);
        assert_eq!(command_timeout_secs(Some(120), 60), 240);
        assert!(command_timeout_secs(Some(120), 60) > 120);
    }

    #[test]
    fn parse_engine_error_body_keeps_the_envelope_when_a_code_is_present() {
        let body = r#"{"error":"请先暂停","code":"RUNNING_CANNOT_MODIFY","params":{},"detail":null}"#;
        assert_eq!(parse_engine_error_body(body), body);
    }

    #[test]
    fn parse_engine_error_body_uses_json_error_field_without_a_code() {
        let body = r#"{"error":"请先暂停"}"#;
        assert_eq!(parse_engine_error_body(body), "请先暂停");
    }

    #[test]
    fn inject_locale_adds_the_resolved_language_to_every_request() {
        let connection = EngineConnection::default();
        let untouched = connection.inject_locale(json!({"type": "create_draft"}));
        assert!(untouched.get("locale").is_none());
        connection.set_locale("zh").expect("zh");
        let body = connection.inject_locale(json!({"type": "fetch_view", "route": "#/research"}));
        assert_eq!(body["locale"], "zh");
        assert!(connection.set_locale("zh-CN").is_err());
        assert!(connection.set_locale("system").is_err());
    }

    #[test]
    fn notify_kinds_drains_every_pending_event() {
        let payload = serde_json::json!({
            "notify": "awaiting_confirm",
            "notifies": ["awaiting_confirm", "completed"]
        });
        assert_eq!(
            notify_kinds(&payload),
            vec!["awaiting_confirm", "completed"]
        );
    }
}
