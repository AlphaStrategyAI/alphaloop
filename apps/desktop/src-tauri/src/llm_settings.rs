//! Non-secret LLM settings. The API key stays in the secret vault (`llm-api-key`).

use std::path::Path;

use serde::Serialize;
use serde_json::{json, Value};

use crate::ui_language::settings_file;

pub const BASE_URL_KEY: &str = "llmBaseUrl";
pub const MODEL_KEY: &str = "llmModel";
pub const PRIVACY_KEY: &str = "llmPrivacyAcknowledged";
pub const SECRET_ID: &str = "llm-api-key";

const SECRET_FILE_KEYS: &[&str] = &["llmApiKey", "apiKey", "api_key", "ALPHALOOP_LLM_API_KEY"];

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LlmSettingsSnapshot {
    pub base_url: String,
    pub model: String,
    pub privacy_acknowledged: bool,
    pub local: bool,
}

fn http_host(url: &str) -> Option<String> {
    let text = url.trim();
    let rest = text
        .strip_prefix("https://")
        .or_else(|| text.strip_prefix("http://"))?;
    if rest.contains('@') || rest.contains('?') || rest.contains('#') {
        return None;
    }
    let authority = rest.split('/').next().unwrap_or("");
    if authority.is_empty() {
        return None;
    }
    let host = if let Some(inner) = authority.strip_prefix('[') {
        inner.split(']').next().unwrap_or("").to_string()
    } else {
        authority.split(':').next().unwrap_or("").to_string()
    };
    if host.is_empty() {
        None
    } else {
        Some(host.to_lowercase())
    }
}

pub fn is_loopback_base_url(url: &str) -> bool {
    let Some(host) = http_host(url) else {
        return false;
    };
    if host == "localhost" || host == "::1" {
        return true;
    }
    let parts: Vec<&str> = host.split('.').collect();
    if parts.len() != 4 {
        return false;
    }
    let mut numbers = Vec::with_capacity(4);
    for part in parts {
        let Ok(number) = part.parse::<u32>() else {
            return false;
        };
        if number > 255 {
            return false;
        }
        numbers.push(number);
    }
    numbers[0] == 127
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

pub fn read_llm_settings(path: &Path) -> LlmSettingsSnapshot {
    let map = read_object(path);
    let base_url = map
        .get(BASE_URL_KEY)
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    let model = map
        .get(MODEL_KEY)
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_string();
    let privacy_acknowledged = map.get(PRIVACY_KEY).and_then(Value::as_bool).unwrap_or(false);
    let local = is_loopback_base_url(&base_url);
    LlmSettingsSnapshot {
        base_url,
        model,
        privacy_acknowledged,
        local,
    }
}

fn validate(base_url: &str, model: &str) -> Result<(String, String), String> {
    let base_url = base_url.trim();
    let model = model.trim();
    if base_url.is_empty() || base_url.len() > 500 || http_host(base_url).is_none() {
        return Err("base url must be an http(s) address without a secret or a query".into());
    }
    if model.is_empty() || model.len() > 200 || model.contains('\n') || model.contains('\r') {
        return Err("model name is required".into());
    }
    Ok((base_url.to_string(), model.to_string()))
}

pub fn write_llm_settings(
    path: &Path,
    base_url: &str,
    model: &str,
    privacy_acknowledged: bool,
) -> Result<LlmSettingsSnapshot, String> {
    let (base_url, model) = validate(base_url, model)?;
    let mut map = read_object(path);
    for key in SECRET_FILE_KEYS {
        map.remove(*key);
    }
    map.insert(BASE_URL_KEY.to_string(), json!(base_url));
    map.insert(MODEL_KEY.to_string(), json!(model));
    map.insert(PRIVACY_KEY.to_string(), json!(privacy_acknowledged));
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
    }
    let temporary = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&Value::Object(map)).map_err(|error| error.to_string())?;
    std::fs::write(&temporary, body + "\n").map_err(|error| error.to_string())?;
    std::fs::rename(&temporary, path).map_err(|error| error.to_string())?;
    Ok(read_llm_settings(path))
}

pub fn current_snapshot() -> LlmSettingsSnapshot {
    read_llm_settings(&settings_file())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_keeps_other_keys_and_drops_a_secret_field() {
        let path = std::env::temp_dir().join(format!("alphaloop-llm-settings-{}.json", std::process::id()));
        std::fs::write(
            &path,
            r#"{"uiLanguage":"en","dataSources":{"kept":true},"llmApiKey":"sk-secret"}"#,
        )
        .unwrap();
        let saved = write_llm_settings(&path, "http://127.0.0.1:11434/v1", "local-model", true).unwrap();
        assert!(saved.local);
        assert_eq!(saved.base_url, "http://127.0.0.1:11434/v1");
        assert_eq!(saved.model, "local-model");
        assert!(saved.privacy_acknowledged);
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains("\"uiLanguage\": \"en\"") || text.contains("\"uiLanguage\":\"en\""));
        assert!(text.contains("kept"));
        assert!(!text.contains("sk-secret"));
        assert!(!text.contains("llmApiKey"));
        assert_eq!(SECRET_ID, "llm-api-key");
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn rejects_a_url_that_embeds_a_secret() {
        let path = std::env::temp_dir().join(format!("alphaloop-llm-reject-{}.json", std::process::id()));
        let error = write_llm_settings(&path, "https://user:sk-secret@example.com/v1", "m", true);
        assert!(error.is_err());
        assert!(!path.is_file() || !std::fs::read_to_string(&path).unwrap_or_default().contains("sk-secret"));
        let _ = std::fs::remove_file(&path);
    }
}
