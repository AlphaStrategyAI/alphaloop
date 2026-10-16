use std::path::{Path, PathBuf};

/// Matches `RuntimePaths.default()` in `engine/research/runtime.py` (platformdirs user_runtime_path).
pub fn runtime_root() -> Option<PathBuf> {
    if let Ok(override_root) = std::env::var("ALPHALOOP_RUNTIME_ROOT") {
        return Some(PathBuf::from(override_root));
    }
    dirs::runtime_dir().map(|dir| dir.join("alphaloop"))
}

pub fn owner_file_path() -> Option<PathBuf> {
    runtime_root().map(|root| root.join("owner.json"))
}

pub fn clear_owner_file() -> Result<(), String> {
    match owner_file_path() {
        Some(path) => clear_owner_file_at(&path),
        None => Ok(()),
    }
}

pub fn clear_owner_file_at(path: &Path) -> Result<(), String> {
    if path.exists() {
        std::fs::remove_file(path).map_err(|error| error.to_string())?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn clear_owner_file_at_removes_existing_file() {
        let dir = std::env::temp_dir().join("alphaloop-owner-test");
        fs::create_dir_all(&dir).expect("mkdir");
        let owner = dir.join("owner.json");
        fs::write(&owner, r#"{"owner":"desktop","pid":1}"#).expect("write");
        clear_owner_file_at(&owner).expect("clear");
        assert!(!owner.exists());
        let _ = fs::remove_dir_all(&dir);
    }
}
