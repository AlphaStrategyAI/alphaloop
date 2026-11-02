//! Dialogue-driven research switch. Default off. The write gate is a sidecar file.

use std::path::Path;

use serde::Serialize;
use serde_json::{json, Value};

use crate::ui_language::{data_root, settings_file};

pub const ENABLED_KEY: &str = "dialogueDrivenResearchEnabled";
pub const GATE_FILE_NAME: &str = "dialogue-write-gate.json";

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DialogueRolloutSnapshot {
    pub enabled: bool,
    pub gate_closed: bool,
    pub gate_reason: String,
    pub gate_detail: String,
}

fn read_object(path: &Path) -> serde_json::Map<String, Value> {
    let Ok(text) = std::fs::read_to_string(path) else {
        return serde_json::Map::new();
    };
    match serde_json::from_str::<Value>(&text) {
        Ok(Value::Object(map)) => map,
        _ => serde_json::Map::new(),
    }
}

fn gate_file(root: &Path) -> std::path::PathBuf {
    root.join(GATE_FILE_NAME)
}

fn read_gate(root: &Path) -> (bool, String, String) {
    let map = read_object(&gate_file(root));
    let closed = map.get("closed").and_then(Value::as_bool).unwrap_or(false);
    let reason = map
        .get("reason")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let detail = map
        .get("detail")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    (closed, reason, detail)
}

pub fn read_dialogue_rollout(settings: &Path, root: &Path) -> DialogueRolloutSnapshot {
    let enabled = read_object(settings)
        .get(ENABLED_KEY)
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let (gate_closed, gate_reason, gate_detail) = read_gate(root);
    DialogueRolloutSnapshot {
        enabled,
        gate_closed,
        gate_reason,
        gate_detail,
    }
}

pub fn write_dialogue_enabled(settings: &Path, enabled: bool) -> Result<DialogueRolloutSnapshot, String> {
    let mut map = read_object(settings);
    map.insert(ENABLED_KEY.to_string(), json!(enabled));
    if let Some(parent) = settings.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
    }
    let temporary = settings.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&Value::Object(map)).map_err(|error| error.to_string())?;
    std::fs::write(&temporary, body + "\n").map_err(|error| error.to_string())?;
    std::fs::rename(&temporary, settings).map_err(|error| error.to_string())?;
    let root = settings.parent().unwrap_or(settings);
    Ok(read_dialogue_rollout(settings, root))
}

pub fn current_snapshot() -> DialogueRolloutSnapshot {
    read_dialogue_rollout(&settings_file(), &data_root())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_key_stays_off_and_other_keys_survive() {
        let dir = std::env::temp_dir().join(format!("alphaloop-dialogue-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let settings = dir.join("settings.json");
        std::fs::write(&settings, r#"{"uiLanguage":"en"}"#).unwrap();
        let loaded = read_dialogue_rollout(&settings, &dir);
        assert!(!loaded.enabled);
        assert!(!loaded.gate_closed);
        let saved = write_dialogue_enabled(&settings, true).unwrap();
        assert!(saved.enabled);
        let text = std::fs::read_to_string(&settings).unwrap();
        assert!(text.contains("uiLanguage"));
        assert!(text.contains("dialogueDrivenResearchEnabled"));
        std::fs::write(
            dir.join(GATE_FILE_NAME),
            r#"{"closed":true,"reason":"duplicate_m","detail":"window"}"#,
        )
        .unwrap();
        let gated = read_dialogue_rollout(&settings, &dir);
        assert!(gated.gate_closed);
        assert_eq!(gated.gate_reason, "duplicate_m");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
