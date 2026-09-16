use std::sync::{Arc, Mutex};

use reqwest::Client;
use serde_json::{json, Value};
use tauri::{AppHandle, State};
use tauri_plugin_notification::NotificationExt;

#[derive(Clone)]
struct Connection {
    endpoint: String,
    auth_token: String,
}

#[derive(Clone, Default)]
pub struct EngineConnection {
    connection: Arc<Mutex<Option<Connection>>>,
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

    async fn post(&self, request: Value) -> Result<Value, String> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| "engine connection lock poisoned")?
            .clone()
            .ok_or("engine is not ready")?;
        Client::new()
            .post(format!("{}/commands", connection.endpoint))
            .bearer_auth(connection.auth_token)
            .json(&request)
            .send()
            .await
            .map_err(|error| error.to_string())?
            .error_for_status()
            .map_err(|error| error.to_string())?
            .json()
            .await
            .map_err(|error| error.to_string())
    }
}

fn notification_title(kind: &str) -> Option<&'static str> {
    match kind {
        "awaiting_confirm" => Some("有研究在等你确认"),
        "completed" => Some("研究已完成"),
        "ended" => Some("研究已结束"),
        _ => None,
    }
}

fn maybe_notify(app: &tauri::AppHandle, payload: &serde_json::Value) {
    let Some(kind) = payload.get("notify").and_then(|value| value.as_str()) else {
        return;
    };
    let Some(title) = notification_title(kind) else {
        return;
    };
    let _ = app.notification().builder().title(title).show();
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
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({
            "type": "resolve_confirm",
            "research_id": research_id,
            "decision": decision
        }),
    )
    .await
    .map(|_| ())
}

#[tauri::command]
pub async fn export_artifact(
    research_id: String,
    kind: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    mutate(
        &app,
        &connection,
        json!({"type": "export_artifact", "research_id": research_id, "kind": kind}),
    )
    .await
    .map(|_| ())
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
            "body": definition
        }))
        .await
        .map(|_| ())
}

#[cfg(test)]
mod tests {
    use super::notification_title;

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
}
