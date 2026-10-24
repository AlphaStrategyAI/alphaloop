//! Secret vault. Plaintext stays in memory or the OS keyring, never in a clear file.
//!
//! Spike (2026-10-19): depend on `keyring-core` 1.0.1 with no features (the `sample`
//! feature is a non-secure file store). Platform stores, not the `keyring` 4.x
//! all-in-one crate:
//! - macOS: `apple-native-keyring-store` 1.0.2, feature `keychain` (login keychain).
//! - Windows: `windows-native-keyring-store` 1.1.0, default features off (`search` pulls regex).
//! - Linux: `zbus-secret-service-keyring-store` 1.0.1, feature `crypto-rust`
//!   (sync Secret Service client; no Tokio feature, calls run off the UI thread).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use aes_gcm::aead::rand_core::RngCore;
use aes_gcm::aead::{Aead, AeadCore, KeyInit, OsRng};
use aes_gcm::{Aes256Gcm, Nonce};
use argon2::Argon2;
use keyring_core::CredentialStore;
use keyring_core::Error as KeyringError;
use serde::Serialize;

const SERVICE: &str = "alphaloop";
const MAGIC: &[u8] = b"ALPHALOOPVAULT1\0";
const REDACTED: &str = "«redacted»";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum VaultMode {
    Keyring,
    Memory,
    Passphrase,
    NeedsChoice,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VaultStatus {
    pub backend: String,
    pub locked: bool,
}

pub struct SecretVault {
    platform: Option<Arc<CredentialStore>>,
    mode: Mutex<VaultMode>,
    memory: Mutex<BTreeMap<String, String>>,
    passphrase: Mutex<Option<String>>,
    directory: PathBuf,
}

impl SecretVault {
    pub fn open_default() -> Self {
        let directory = default_directory();
        let vault_file_exists = vault_path(&directory).is_file();
        // Test-only. Unset, the platform keyring is still preferred.
        let force_passphrase =
            std::env::var("ALPHALOOP_SECRETS_BACKEND").ok().as_deref() == Some("passphrase");
        if force_passphrase {
            return Self::new(
                None,
                resolve_startup_mode(true, false, vault_file_exists),
                directory,
            );
        }
        match open_platform_store() {
            Ok(store) => Self::new(
                Some(store),
                resolve_startup_mode(false, true, vault_file_exists),
                directory,
            ),
            Err(_) => Self::new(
                None,
                resolve_startup_mode(false, false, vault_file_exists),
                directory,
            ),
        }
    }

    fn new(platform: Option<Arc<CredentialStore>>, mode: VaultMode, directory: PathBuf) -> Self {
        Self {
            platform,
            mode: Mutex::new(mode),
            memory: Mutex::new(BTreeMap::new()),
            passphrase: Mutex::new(None),
            directory,
        }
    }

    pub fn status(&self) -> VaultStatus {
        let mode = *self.mode.lock().expect("vault mode");
        // Locked means an encrypted file is on disk and this process has not
        // unlocked it. Choosing passphrase storage before any file exists is
        // not a lock.
        let locked = mode == VaultMode::Passphrase
            && vault_path(&self.directory).is_file()
            && self.passphrase.lock().expect("passphrase").is_none();
        let backend = match mode {
            VaultMode::Keyring => "keyring",
            VaultMode::Memory => "memory",
            VaultMode::Passphrase => "passphrase",
            VaultMode::NeedsChoice => "needs_choice",
        };
        VaultStatus {
            backend: backend.to_string(),
            locked,
        }
    }

    pub fn choose_fallback(&self, choice: &str) -> Result<(), String> {
        let mut mode = self.mode.lock().expect("vault mode");
        if *mode != VaultMode::NeedsChoice {
            return Err("系统钥匙串可用，不必改用降级存放。".into());
        }
        *mode = match choice {
            "memory" => VaultMode::Memory,
            "passphrase" => VaultMode::Passphrase,
            _ => return Err("请选择仅本次会话或口令加密文件。".into()),
        };
        Ok(())
    }

    pub fn set(&self, id: &str, secret: &str, passphrase: Option<&str>) -> Result<(), String> {
        validate_id(id)?;
        if secret.is_empty() {
            return Err("密钥不能为空。".into());
        }
        let mode = *self.mode.lock().expect("vault mode");
        match mode {
            VaultMode::NeedsChoice => Err("这台电脑没有系统钥匙串。请先选择仅本次会话或口令加密文件。".into()),
            VaultMode::Memory => {
                self.memory.lock().expect("memory").insert(id.to_string(), secret.to_string());
                Ok(())
            }
            VaultMode::Passphrase => self.set_passphrase(id, secret, passphrase),
            VaultMode::Keyring => self.set_keyring(id, secret),
        }
    }

    pub fn delete(&self, id: &str) -> Result<(), String> {
        validate_id(id)?;
        let mode = *self.mode.lock().expect("vault mode");
        match mode {
            VaultMode::NeedsChoice => Ok(()),
            VaultMode::Memory => {
                self.memory.lock().expect("memory").remove(id);
                Ok(())
            }
            VaultMode::Passphrase => {
                self.unlock_existing(None)?;
                self.memory.lock().expect("memory").remove(id);
                self.write_encrypted()?;
                Ok(())
            }
            VaultMode::Keyring => {
                if let Some(store) = &self.platform {
                    let entry = store
                        .build(SERVICE, id, None)
                        .map_err(|error| public_keyring_error(&error))?;
                    match entry.delete_credential() {
                        Ok(()) | Err(KeyringError::NoEntry) => {}
                        Err(error) => return Err(public_keyring_error(&error)),
                    }
                }
                self.remove_index_id(id)?;
                Ok(())
            }
        }
    }

    pub fn is_set(&self, id: &str) -> Result<bool, String> {
        validate_id(id)?;
        let mode = *self.mode.lock().expect("vault mode");
        match mode {
            VaultMode::NeedsChoice => Ok(false),
            VaultMode::Memory => Ok(self.memory.lock().expect("memory").contains_key(id)),
            VaultMode::Passphrase => {
                if self.passphrase.lock().expect("passphrase").is_none() {
                    return Ok(false);
                }
                Ok(self.memory.lock().expect("memory").contains_key(id))
            }
            VaultMode::Keyring => self.keyring_is_set(id),
        }
    }

    pub fn unlock(&self, passphrase: &str) -> Result<(), String> {
        if *self.mode.lock().expect("vault mode") != VaultMode::Passphrase {
            return Ok(());
        }
        self.unlock_existing(Some(passphrase))
    }

    pub fn export_map(&self) -> BTreeMap<String, String> {
        let mode = *self.mode.lock().expect("vault mode");
        match mode {
            VaultMode::Memory | VaultMode::Passphrase => self.memory.lock().expect("memory").clone(),
            VaultMode::Keyring => {
                let mut map = BTreeMap::new();
                for id in self.read_index() {
                    if let Ok(Some(secret)) = self.keyring_get(&id) {
                        map.insert(id, secret);
                    }
                }
                map
            }
            VaultMode::NeedsChoice => BTreeMap::new(),
        }
    }

    pub fn redact(&self, text: &str) -> String {
        let secrets: Vec<String> = self.export_map().into_values().filter(|value| value.len() >= 8).collect();
        redact_text(text, &secrets)
    }
}

impl SecretVault {
    fn set_keyring(&self, id: &str, secret: &str) -> Result<(), String> {
        let store = self.platform.as_ref().ok_or("系统钥匙串不可用。")?;
        let entry = store
            .build(SERVICE, id, None)
            .map_err(|error| public_keyring_error(&error))?;
        entry
            .set_password(secret)
            .map_err(|error| public_keyring_error(&error))?;
        self.add_index_id(id)
    }

    fn keyring_is_set(&self, id: &str) -> Result<bool, String> {
        Ok(self.keyring_get(id)?.is_some())
    }

    fn keyring_get(&self, id: &str) -> Result<Option<String>, String> {
        let Some(store) = &self.platform else {
            return Ok(None);
        };
        let entry = store
            .build(SERVICE, id, None)
            .map_err(|error| public_keyring_error(&error))?;
        match entry.get_password() {
            Ok(secret) => Ok(Some(secret)),
            Err(KeyringError::NoEntry) => Ok(None),
            Err(error) => Err(public_keyring_error(&error)),
        }
    }

    fn set_passphrase(&self, id: &str, secret: &str, passphrase: Option<&str>) -> Result<(), String> {
        self.unlock_existing(passphrase)?;
        self.memory.lock().expect("memory").insert(id.to_string(), secret.to_string());
        self.write_encrypted()
    }

    fn unlock_existing(&self, passphrase: Option<&str>) -> Result<(), String> {
        if let Some(phrase) = passphrase {
            if phrase.is_empty() {
                return Err("请输入口令。".into());
            }
            *self.passphrase.lock().expect("passphrase") = Some(phrase.to_string());
        }
        let phrase = self
            .passphrase
            .lock()
            .expect("passphrase")
            .clone()
            .ok_or("请输入口令。")?;
        let path = vault_path(&self.directory);
        if !path.is_file() {
            self.memory.lock().expect("memory").clear();
            return Ok(());
        }
        let bytes = fs::read(&path).map_err(|_| "读不到加密的密钥文件。".to_string())?;
        let map = decrypt_vault(&bytes, &phrase).map_err(|_| "口令不正确。".to_string())?;
        *self.memory.lock().expect("memory") = map;
        Ok(())
    }

    fn write_encrypted(&self) -> Result<(), String> {
        let phrase = self
            .passphrase
            .lock()
            .expect("passphrase")
            .clone()
            .ok_or("请输入口令。")?;
        let map = self.memory.lock().expect("memory").clone();
        let bytes = encrypt_vault(&map, &phrase).map_err(|_| "无法加密密钥文件。".to_string())?;
        fs::create_dir_all(&self.directory).map_err(|_| "无法建立密钥目录。".to_string())?;
        let path = vault_path(&self.directory);
        write_private(&path, &bytes)?;
        for secret in map.values() {
            if secret.len() >= 8 && bytes.windows(secret.len()).any(|window| window == secret.as_bytes()) {
                let _ = fs::remove_file(&path);
                return Err("加密结果仍含明文，已删除文件。".into());
            }
        }
        Ok(())
    }

    fn index_path(&self) -> PathBuf {
        self.directory.join("secret-index.json")
    }

    fn read_index(&self) -> Vec<String> {
        let Ok(text) = fs::read_to_string(self.index_path()) else {
            return Vec::new();
        };
        serde_json::from_str(&text).unwrap_or_default()
    }

    fn add_index_id(&self, id: &str) -> Result<(), String> {
        let mut ids = self.read_index();
        if !ids.iter().any(|item| item == id) {
            ids.push(id.to_string());
            ids.sort();
        }
        self.write_index(&ids)
    }

    fn remove_index_id(&self, id: &str) -> Result<(), String> {
        let ids: Vec<String> = self.read_index().into_iter().filter(|item| item != id).collect();
        self.write_index(&ids)
    }

    fn write_index(&self, ids: &[String]) -> Result<(), String> {
        fs::create_dir_all(&self.directory).map_err(|_| "无法建立密钥目录。".to_string())?;
        let text = serde_json::to_string(ids).map_err(|_| "无法记录密钥别名。".to_string())?;
        write_private(&self.index_path(), text.as_bytes())
    }
}

fn write_private(path: &Path, bytes: &[u8]) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;
        let mut file = fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .mode(0o600)
            .open(path)
            .map_err(|_| "无法写入密钥文件。".to_string())?;
        file.write_all(bytes).map_err(|_| "无法写入密钥文件。".to_string())?;
        return Ok(());
    }
    #[cfg(not(unix))]
    {
        fs::write(path, bytes).map_err(|_| "无法写入密钥文件。".to_string())
    }
}

fn vault_path(directory: &Path) -> PathBuf {
    directory.join("secret-vault.bin")
}

fn resolve_startup_mode(
    force_passphrase: bool,
    platform_available: bool,
    vault_file_exists: bool,
) -> VaultMode {
    if force_passphrase || !platform_available {
        return if vault_file_exists {
            VaultMode::Passphrase
        } else {
            VaultMode::NeedsChoice
        };
    }
    VaultMode::Keyring
}

fn vault_directory_from(data_root_override: Option<&str>, platform_data_dir: Option<&Path>) -> PathBuf {
    if let Some(value) = data_root_override.map(str::trim).filter(|value| !value.is_empty()) {
        return PathBuf::from(value);
    }
    platform_data_dir
        .unwrap_or_else(|| Path::new("."))
        .join("alphaloop")
}

fn default_directory() -> PathBuf {
    // When a test sets ALPHALOOP_DATA_ROOT, keep the passphrase file with the
    // research data. Unset, the vault stays in the platform data dir.
    let override_root = std::env::var("ALPHALOOP_DATA_ROOT").ok();
    vault_directory_from(override_root.as_deref(), dirs::data_dir().as_deref())
}

fn open_platform_store() -> Result<Arc<CredentialStore>, String> {
    #[cfg(target_os = "linux")]
    {
        let store = zbus_secret_service_keyring_store::Store::new().map_err(|error| error.to_string())?;
        return Ok(store);
    }
    #[cfg(target_os = "macos")]
    {
        let store = apple_native_keyring_store::keychain::Store::new().map_err(|error| error.to_string())?;
        return Ok(store);
    }
    #[cfg(target_os = "windows")]
    {
        let store = windows_native_keyring_store::Store::new().map_err(|error| error.to_string())?;
        return Ok(store);
    }
    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        Err("no platform keyring".into())
    }
}

fn public_keyring_error(error: &KeyringError) -> String {
    match error {
        KeyringError::NoEntry => "密钥未设置。".into(),
        KeyringError::NoStorageAccess(_) => "系统钥匙串锁住了，或这台电脑没有 Secret Service。".into(),
        _ => "系统钥匙串拒绝了这次操作。".into(),
    }
}

fn validate_id(id: &str) -> Result<(), String> {
    if id.is_empty() || id.len() > 128 {
        return Err("密钥别名无效。".into());
    }
    if !id
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'))
    {
        return Err("密钥别名无效。".into());
    }
    Ok(())
}

fn encrypt_vault(map: &BTreeMap<String, String>, passphrase: &str) -> Result<Vec<u8>, String> {
    let mut salt = [0u8; 16];
    OsRng.fill_bytes(&mut salt);
    let key = derive_key(passphrase, &salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key).map_err(|_| "无法加密密钥文件。".to_string())?;
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
    let plaintext = serde_json::to_vec(map).map_err(|_| "无法加密密钥文件。".to_string())?;
    let ciphertext = cipher
        .encrypt(Nonce::from_slice(nonce.as_slice()), plaintext.as_ref())
        .map_err(|_| "无法加密密钥文件。".to_string())?;
    let mut out = Vec::with_capacity(MAGIC.len() + salt.len() + nonce.len() + ciphertext.len());
    out.extend_from_slice(MAGIC);
    out.extend_from_slice(&salt);
    out.extend_from_slice(nonce.as_slice());
    out.extend_from_slice(&ciphertext);
    Ok(out)
}

fn decrypt_vault(bytes: &[u8], passphrase: &str) -> Result<BTreeMap<String, String>, String> {
    if bytes.len() < MAGIC.len() + 16 + 12 || &bytes[..MAGIC.len()] != MAGIC {
        return Err("密钥文件格式不对。".into());
    }
    let salt = &bytes[MAGIC.len()..MAGIC.len() + 16];
    let nonce = &bytes[MAGIC.len() + 16..MAGIC.len() + 16 + 12];
    let ciphertext = &bytes[MAGIC.len() + 16 + 12..];
    let key = derive_key(passphrase, salt)?;
    let cipher = Aes256Gcm::new_from_slice(&key).map_err(|_| "口令不正确。".to_string())?;
    let plaintext = cipher
        .decrypt(Nonce::from_slice(nonce), ciphertext)
        .map_err(|_| "口令不正确。".to_string())?;
    serde_json::from_slice(&plaintext).map_err(|_| "口令不正确。".to_string())
}

fn derive_key(passphrase: &str, salt: &[u8]) -> Result<[u8; 32], String> {
    let mut key = [0u8; 32];
    Argon2::default()
        .hash_password_into(passphrase.as_bytes(), salt, &mut key)
        .map_err(|_| "无法从口令派生密钥。".to_string())?;
    Ok(key)
}

pub fn redact_text(text: &str, secrets: &[String]) -> String {
    let mut out = text.to_string();
    let mut ordered: Vec<&str> = secrets.iter().map(String::as_str).filter(|item| item.len() >= 8).collect();
    ordered.sort_by_key(|item| std::cmp::Reverse(item.len()));
    for secret in ordered {
        out = out.replace(secret, REDACTED);
    }
    redact_urls(&out)
}

fn redact_urls(text: &str) -> String {
    let mut out = String::new();
    let bytes = text.as_bytes();
    let mut index = 0;
    while index < bytes.len() {
        if let Some(start) = find_url(text, index) {
            out.push_str(&text[index..start]);
            let end = url_end(text, start);
            out.push_str(&redact_one_url(&text[start..end]));
            index = end;
        } else {
            out.push_str(&text[index..]);
            break;
        }
    }
    out
}

fn find_url(text: &str, from: usize) -> Option<usize> {
    let rest = &text[from..];
    let http = rest.find("http://").map(|pos| from + pos);
    let https = rest.find("https://").map(|pos| from + pos);
    match (http, https) {
        (Some(a), Some(b)) => Some(a.min(b)),
        (Some(a), None) => Some(a),
        (None, Some(b)) => Some(b),
        (None, None) => None,
    }
}

fn url_end(text: &str, start: usize) -> usize {
    text[start..]
        .find(|ch: char| ch.is_whitespace() || matches!(ch, '<' | '>' | '"' | '\''))
        .map(|pos| start + pos)
        .unwrap_or(text.len())
}

fn redact_one_url(raw: &str) -> String {
    let mut end = raw.len();
    let mut tail = String::new();
    while end > 0 && matches!(raw.as_bytes()[end - 1], b'.' | b',' | b')' | b';') {
        tail.insert(0, raw.as_bytes()[end - 1] as char);
        end -= 1;
    }
    let raw = &raw[..end];
    let Some(scheme_end) = raw.find("://") else {
        return format!("{REDACTED}{tail}");
    };
    let scheme = &raw[..scheme_end];
    let rest = &raw[scheme_end + 3..];
    let (authority, path_and_query) = match rest.find(['/', '?', '#']) {
        Some(pos) => (&rest[..pos], &rest[pos..]),
        None => (rest, ""),
    };
    let host = authority.rsplit('@').next().unwrap_or(authority);
    let path = path_and_query.split(['?', '#']).next().unwrap_or("");
    let mut cleaned = String::new();
    for segment in path.split('/') {
        if !cleaned.is_empty() || path.starts_with('/') {
            if !cleaned.ends_with('/') {
                cleaned.push('/');
            }
        }
        if segment.is_empty() {
            continue;
        }
        if looks_like_token(segment) {
            cleaned.push_str(REDACTED);
        } else {
            cleaned.push_str(segment);
        }
    }
    if path.starts_with('/') && !cleaned.starts_with('/') {
        cleaned.insert(0, '/');
    }
    format!("{scheme}://{host}{cleaned}{tail}")
}

fn looks_like_token(segment: &str) -> bool {
    if segment.len() == 36 && segment.as_bytes().get(8) == Some(&b'-') {
        return false;
    }
    let lower = segment.to_ascii_lowercase();
    if lower.starts_with("sk")
        || lower.starts_with("ghp_")
        || lower.starts_with("github_pat")
        || lower.starts_with("akia")
        || lower.starts_with("ya29")
    {
        return segment.len() >= 12;
    }
    segment.len() >= 32 && segment.chars().all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' || ch == '+' || ch == '/')
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::{Path, PathBuf};

    struct TempDir {
        path: std::path::PathBuf,
    }

    impl TempDir {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "alphaloop-vault-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .expect("clock")
                    .as_nanos()
            ));
            std::fs::create_dir_all(&path).unwrap();
            Self { path }
        }

        fn path(&self) -> &std::path::Path {
            &self.path
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }

    fn temp_vault(mode: VaultMode) -> (TempDir, SecretVault) {
        let dir = TempDir::new();
        let vault = SecretVault::new(None, mode, dir.path().to_path_buf());
        (dir, vault)
    }

    #[test]
    fn redacts_userinfo_query_and_known_secret() {
        let secret = "alphaloop-test-secret-9f3a".to_string();
        let raw = format!("https://user:{secret}@example.invalid/v1/{secret}?api_key={secret}");
        let cleaned = redact_text(&raw, &[secret.clone()]);
        assert!(!cleaned.contains(&secret));
        assert!(!cleaned.contains("api_key"));
        assert!(!cleaned.contains("user:"));
        assert!(cleaned.contains("example.invalid"));
    }

    #[test]
    fn needs_choice_does_not_write_a_file() {
        let (dir, vault) = temp_vault(VaultMode::NeedsChoice);
        let err = vault.set("vendor-demo", "alphaloop-test-secret-9f3a", None).unwrap_err();
        assert!(err.contains("没有系统钥匙串"));
        assert!(!vault_path(dir.path()).exists());
        assert!(dir.path().read_dir().unwrap().next().is_none());
    }

    #[test]
    fn memory_mode_keeps_secret_out_of_files() {
        let (dir, vault) = temp_vault(VaultMode::Memory);
        vault.set("vendor-demo", "alphaloop-test-secret-9f3a", None).unwrap();
        assert!(vault.is_set("vendor-demo").unwrap());
        assert!(!vault_path(dir.path()).exists());
        vault.delete("vendor-demo").unwrap();
        assert!(!vault.is_set("vendor-demo").unwrap());
    }

    #[test]
    #[ignore = "requires an unlocked Secret Service (dbus-run-session + gnome-keyring)"]
    fn keyring_secret_service_roundtrip() {
        let vault = SecretVault::open_default();
        if vault.status().backend != "keyring" {
            assert!(
                std::env::var("ALPHALOOP_REQUIRE_KEYRING").ok().as_deref() != Some("1"),
                "Secret Service was required but the vault fell back"
            );
            return;
        }
        let secret = "alphaloop-test-secret-9f3a";
        vault.set("ci-probe", secret, None).unwrap();
        assert!(vault.is_set("ci-probe").unwrap());
        assert_eq!(vault.export_map().get("ci-probe").map(String::as_str), Some(secret));
        vault.delete("ci-probe").unwrap();
        assert!(!vault.is_set("ci-probe").unwrap());
    }

    #[test]
    fn passphrase_flag_skips_the_platform_store_until_a_file_exists() {
        assert_eq!(
            resolve_startup_mode(false, true, false),
            VaultMode::Keyring
        );
        assert_eq!(
            resolve_startup_mode(true, true, false),
            VaultMode::NeedsChoice
        );
        assert_eq!(
            resolve_startup_mode(true, true, true),
            VaultMode::Passphrase
        );
        assert_eq!(
            resolve_startup_mode(false, false, false),
            VaultMode::NeedsChoice
        );
    }

    #[test]
    fn data_root_override_relocates_the_vault_directory() {
        let overridden = vault_directory_from(Some("/tmp/alphaloop-e2e"), Some(Path::new("/platform")));
        assert_eq!(overridden, PathBuf::from("/tmp/alphaloop-e2e"));
        let fallback = vault_directory_from(None, Some(Path::new("/platform")));
        assert_eq!(fallback, PathBuf::from("/platform/alphaloop"));
        let blank = vault_directory_from(Some("  "), Some(Path::new("/platform")));
        assert_eq!(blank, PathBuf::from("/platform/alphaloop"));
    }

    #[test]
    fn choosing_passphrase_without_a_file_is_not_locked() {
        let (dir, vault) = temp_vault(VaultMode::NeedsChoice);
        vault.choose_fallback("passphrase").unwrap();
        let status = vault.status();
        assert_eq!(status.backend, "passphrase");
        assert!(
            !status.locked,
            "a missing passphrase file must not claim the vault is locked"
        );
        assert!(!vault_path(dir.path()).is_file());
        assert!(vault.set("vendor-demo", "alphaloop-test-secret-9f3a", Some("correct horse")).is_ok());
        assert!(!vault.status().locked);
        assert!(vault_path(dir.path()).is_file());

        let (dir2, locked) = temp_vault(VaultMode::Passphrase);
        fs::copy(vault_path(dir.path()), vault_path(dir2.path())).unwrap();
        assert!(locked.status().locked);
        locked.unlock("correct horse").unwrap();
        assert!(!locked.status().locked);
    }

    #[test]
    fn passphrase_file_is_not_plaintext() {
        let (dir, vault) = temp_vault(VaultMode::Passphrase);
        let secret = "alphaloop-test-secret-9f3a";
        vault.set("vendor-demo", secret, Some("correct horse")).unwrap();
        let bytes = fs::read(vault_path(dir.path())).unwrap();
        assert!(!bytes.windows(secret.len()).any(|window| window == secret.as_bytes()));
        assert!(vault.is_set("vendor-demo").unwrap());
        let (dir2, locked) = temp_vault(VaultMode::Passphrase);
        fs::copy(vault_path(dir.path()), vault_path(dir2.path())).unwrap();
        assert!(!locked.is_set("vendor-demo").unwrap());
        locked.unlock("correct horse").unwrap();
        assert!(locked.is_set("vendor-demo").unwrap());
        assert_eq!(locked.export_map().get("vendor-demo").map(String::as_str), Some(secret));
    }
}
