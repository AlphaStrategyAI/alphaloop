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

#[derive(Default)]
pub struct NotificationTracker {
    last_event: Mutex<Option<String>>,
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

#[tauri::command]
pub async fn fetch_view(
    route: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
    tracker: State<'_, NotificationTracker>,
) -> Result<Value, String> {
    let view = connection
        .post(json!({"type": "fetch_view", "route": route}))
        .await?;
    let kind = view["kind"].as_str().unwrap_or_default();
    let status = view["status"].as_str().unwrap_or_default();
    let body = match (kind, status) {
        ("awaiting_confirm", _) => Some("研究需要你确认"),
        ("completed", "completed") => Some("研究已完成"),
        ("completed", "ended") => Some("研究已结束"),
        _ => None,
    };
    if let Some(body) = body {
        let event_id = format!(
            "{}:{}",
            view["researchId"].as_str().unwrap_or_default(),
            status
        );
        let mut last = tracker
            .last_event
            .lock()
            .map_err(|_| "notification tracker lock poisoned")?;
        if last.as_deref() != Some(&event_id) {
            app.notification()
                .builder()
                .title("alphaloop")
                .body(body)
                .show()
                .map_err(|error| error.to_string())?;
            *last = Some(event_id);
        }
    }
    Ok(view)
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
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "confirm_run", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn send_dialogue(
    research_id: String,
    message: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "send_dialogue", "research_id": research_id, "message": message}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn pause_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "pause", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn resume_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "resume", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn confirm_modification(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "confirm_modification", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn extend_research(
    research_id: String,
    hours: f64,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "extend_research",
            "research_id": research_id,
            "hours": hours
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn delete_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "delete_research", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn resolve_confirm(
    research_id: String,
    decision: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "resolve_confirm",
            "research_id": research_id,
            "decision": decision
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn export_artifact(
    research_id: String,
    kind: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "export_artifact", "research_id": research_id, "kind": kind}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn reverify(
    research_id: String,
    round_id: String,
    method_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "reverify",
            "research_id": research_id,
            "round_id": round_id,
            "method_id": method_id
        }))
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
