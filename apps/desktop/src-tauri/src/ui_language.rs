//! Interface-language preference. Lives in the data-directory settings file,
//! not the research library and not the keychain.

use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::{json, Value};

pub const APP_DATA_DIR_NAME: &str = "ai.alphastrategy.alphaloop";
pub const SETTINGS_FILE_NAME: &str = "settings.json";
pub const SETTINGS_KEY: &str = "uiLanguage";

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UiLanguageSnapshot {
    pub preference: String,
    pub system_locale: Option<String>,
    pub resolved: String,
}

pub fn language_from_system_locale(tag: Option<&str>) -> &'static str {
    let Some(tag) = tag else {
        return "en";
    };
    let text = tag.trim();
    if text.is_empty() {
        return "en";
    }
    let primary = text.split('.').next().unwrap_or("");
    let primary = primary.split('@').next().unwrap_or("");
    let lang = primary
        .split(['_', '-'])
        .next()
        .unwrap_or("")
        .to_lowercase();
    if lang == "zh" {
        "zh"
    } else {
        "en"
    }
}

pub fn resolve_ui_language(preference: Option<&str>, system_locale: Option<&str>) -> &'static str {
    match preference {
        Some("zh") => "zh",
        Some("en") => "en",
        _ => language_from_system_locale(system_locale),
    }
}

pub fn data_root_from(override_root: Option<&str>, platform_data_dir: Option<&Path>) -> PathBuf {
    if let Some(value) = override_root.map(str::trim).filter(|value| !value.is_empty()) {
        return PathBuf::from(value);
    }
    platform_data_dir
        .unwrap_or_else(|| Path::new("."))
        .join(APP_DATA_DIR_NAME)
}

pub fn data_root() -> PathBuf {
    let override_root = std::env::var("ALPHALOOP_DATA_ROOT").ok();
    data_root_from(override_root.as_deref(), dirs::data_dir().as_deref())
}

pub fn settings_file() -> PathBuf {
    data_root().join(SETTINGS_FILE_NAME)
}

pub fn read_ui_language_preference(path: &Path) -> String {
    let Ok(text) = std::fs::read_to_string(path) else {
        return "system".to_string();
    };
    let Ok(value) = serde_json::from_str::<Value>(&text) else {
        return "system".to_string();
    };
    match value.get(SETTINGS_KEY).and_then(Value::as_str) {
        Some(preference @ ("system" | "zh" | "en")) => preference.to_string(),
        _ => "system".to_string(),
    }
}

pub fn write_ui_language_preference(path: &Path, preference: &str) -> Result<(), String> {
    if preference != "system" && preference != "zh" && preference != "en" {
        return Err("uiLanguage must be system, zh, or en".into());
    }
    let mut current = match std::fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
    {
        Some(Value::Object(map)) => Value::Object(map),
        _ => json!({}),
    };
    if let Some(object) = current.as_object_mut() {
        object.insert(SETTINGS_KEY.to_string(), json!(preference));
    }
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
    }
    let temporary = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&current).map_err(|error| error.to_string())?;
    std::fs::write(&temporary, body + "\n").map_err(|error| error.to_string())?;
    std::fs::rename(&temporary, path).map_err(|error| error.to_string())?;
    Ok(())
}

pub fn read_system_locale_tag() -> Option<String> {
    sys_locale::get_locale().filter(|value| !value.trim().is_empty())
}

pub fn current_snapshot() -> UiLanguageSnapshot {
    let preference = read_ui_language_preference(&settings_file());
    let system_locale = read_system_locale_tag();
    let resolved = resolve_ui_language(Some(preference.as_str()), system_locale.as_deref());
    UiLanguageSnapshot {
        preference,
        system_locale,
        resolved: resolved.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;

    #[derive(Deserialize)]
    struct LocaleCases {
        #[serde(rename = "systemTags")]
        system_tags: Vec<TagCase>,
        resolution: Vec<ResolutionCase>,
    }

    #[derive(Deserialize)]
    struct TagCase {
        id: String,
        tag: Option<String>,
        language: String,
    }

    #[derive(Deserialize)]
    struct ResolutionCase {
        id: String,
        preference: Option<String>,
        system: Option<String>,
        resolved: String,
    }

    fn fixture() -> LocaleCases {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tests/fixtures/ui_language_cases.json");
        let text = std::fs::read_to_string(path).expect("ui language fixture");
        serde_json::from_str(&text).expect("ui language fixture json")
    }

    #[test]
    fn shared_fixture_matches_resolver() {
        let cases = fixture();
        for case in cases.system_tags {
            assert_eq!(
                language_from_system_locale(case.tag.as_deref()),
                case.language,
                "{}",
                case.id
            );
        }
        for case in cases.resolution {
            assert_eq!(
                resolve_ui_language(case.preference.as_deref(), case.system.as_deref()),
                case.resolved,
                "{}",
                case.id
            );
        }
    }

    #[test]
    fn preference_file_is_legacy_neutral_and_keeps_other_keys() {
        let root = std::env::temp_dir().join(format!(
            "alphaloop-ui-language-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join(SETTINGS_FILE_NAME);
        assert_eq!(read_ui_language_preference(&path), "system");

        std::fs::write(&path, r#"{"dataSources":{"kept":true},"uiLanguage":"en"}"#).unwrap();
        assert_eq!(read_ui_language_preference(&path), "en");
        write_ui_language_preference(&path, "zh").unwrap();
        let saved: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(saved["uiLanguage"], "zh");
        assert_eq!(saved["dataSources"]["kept"], true);

        std::fs::write(&path, r#"{"uiLanguage":"fr","other":1}"#).unwrap();
        assert_eq!(read_ui_language_preference(&path), "system");
        std::fs::write(&path, "{not json").unwrap();
        assert_eq!(read_ui_language_preference(&path), "system");
        write_ui_language_preference(&path, "en").unwrap();
        let saved: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(saved["uiLanguage"], "en");
        assert!(write_ui_language_preference(&path, "fr").is_err());
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn data_root_honors_override_without_touching_process_env() {
        let root = data_root_from(Some("/tmp/alphaloop-data-contract"), None);
        assert_eq!(root, PathBuf::from("/tmp/alphaloop-data-contract"));
        let fallback = data_root_from(Some("  "), Some(Path::new("/data")));
        assert_eq!(
            fallback,
            PathBuf::from("/data").join(APP_DATA_DIR_NAME)
        );
    }
}
