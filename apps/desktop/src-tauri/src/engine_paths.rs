use std::path::{Path, PathBuf};

/// Contract: `docs/requirements/runtime-root.md` (must match `engine.research.runtime.resolve_runtime_root`).
pub fn resolve_runtime_root() -> Result<PathBuf, String> {
    if let Ok(override_root) = std::env::var("ALPHALOOP_RUNTIME_ROOT") {
        return Ok(PathBuf::from(override_root));
    }
    let base = user_runtime_base()?;
    Ok(base.join("alphaloop"))
}

pub fn owner_file_path() -> Result<PathBuf, String> {
    resolve_runtime_root().map(|root| root.join("owner.json"))
}

pub fn clear_owner_file() -> Result<(), String> {
    let path = owner_file_path()?;
    clear_owner_file_at(&path)
}

pub fn clear_owner_file_logged() {
    if let Err(error) = clear_owner_file() {
        eprintln!("alphaloop: failed to clear owner.json: {error}");
    }
}

pub fn clear_owner_file_at(path: &Path) -> Result<(), String> {
    if path.exists() {
        std::fs::remove_file(path).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn user_runtime_base() -> Result<PathBuf, String> {
    #[cfg(target_os = "linux")]
    {
        return linux_user_runtime_base();
    }
    #[cfg(not(target_os = "linux"))]
    {
        return dirs::runtime_dir().ok_or_else(|| {
            "could not resolve platform runtime directory (set ALPHALOOP_RUNTIME_ROOT)".into()
        });
    }
}

#[cfg(target_os = "linux")]
fn linux_user_runtime_base() -> Result<PathBuf, String> {
    if let Ok(xdg) = std::env::var("XDG_RUNTIME_DIR") {
        let path = PathBuf::from(xdg);
        if runtime_dir_usable(&path) {
            return Ok(path);
        }
        eprintln!(
            "alphaloop: XDG_RUNTIME_DIR is set but not usable as a runtime dir ({}); trying fallbacks",
            path.display()
        );
    } else {
        eprintln!("alphaloop: XDG_RUNTIME_DIR is not set; using platformdirs-compatible runtime fallback");
    }
    let uid = current_uid();
    let run_user = PathBuf::from(format!("/run/user/{}", uid));
    if runtime_dir_usable(&run_user) {
        return Ok(run_user);
    }
    let temp = std::env::temp_dir().join(format!("runtime-{}", uid));
    std::fs::create_dir_all(&temp).map_err(|error| {
        format!(
            "could not create runtime fallback directory {}: {error} (set ALPHALOOP_RUNTIME_ROOT)",
            temp.display()
        )
    })?;
    Ok(temp)
}

#[cfg(target_os = "linux")]
fn current_uid() -> u32 {
    unsafe { libc::getuid() }
}

#[cfg(target_os = "linux")]
fn runtime_dir_usable(path: &Path) -> bool {
    use std::os::unix::fs::MetadataExt;
    match std::fs::symlink_metadata(path) {
        Ok(meta) => {
            if meta.file_type().is_symlink() || !meta.is_dir() {
                return false;
            }
            let mode = meta.mode() & 0o777;
            meta.uid() == current_uid() && mode == 0o700
        }
        Err(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::{Mutex, MutexGuard};

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn with_env_lock<F: FnOnce()>(run: F) {
        let _guard = ENV_LOCK.lock().expect("env lock");
        run();
    }

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

    #[test]
    fn resolve_runtime_root_honours_override() {
        with_env_lock(|| {
            std::env::set_var("ALPHALOOP_RUNTIME_ROOT", "/tmp/alphaloop-contract-override");
            std::env::remove_var("XDG_RUNTIME_DIR");
            let root = resolve_runtime_root().expect("root");
            assert_eq!(root, PathBuf::from("/tmp/alphaloop-contract-override"));
            std::env::remove_var("ALPHALOOP_RUNTIME_ROOT");
        });
    }

    #[test]
    fn resolve_runtime_root_uses_xdg_when_set() {
        with_env_lock(|| {
            std::env::remove_var("ALPHALOOP_RUNTIME_ROOT");
            let uid = current_uid();
            let xdg = std::env::temp_dir().join(format!("alphaloop-xdg-test-{}", uid));
            let _ = fs::remove_dir_all(&xdg);
            fs::create_dir_all(&xdg).expect("mkdir");
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                fs::set_permissions(&xdg, fs::Permissions::from_mode(0o700)).expect("mode");
            }
            std::env::set_var("XDG_RUNTIME_DIR", xdg.to_string_lossy().as_ref());
            let root = resolve_runtime_root().expect("root");
            assert_eq!(root, xdg.join("alphaloop"));
            std::env::remove_var("XDG_RUNTIME_DIR");
            let _ = fs::remove_dir_all(&xdg);
        });
    }

    #[test]
    fn resolve_runtime_root_falls_back_without_xdg() {
        with_env_lock(|| {
            std::env::remove_var("ALPHALOOP_RUNTIME_ROOT");
            std::env::remove_var("XDG_RUNTIME_DIR");
            let uid = current_uid();
            let root = resolve_runtime_root().expect("root");
            let expected = std::env::temp_dir()
                .join(format!("runtime-{}", uid))
                .join("alphaloop");
            assert_eq!(root, expected);
        });
    }
}
