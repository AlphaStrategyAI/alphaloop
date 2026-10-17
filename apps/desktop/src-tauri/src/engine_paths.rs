use std::path::{Path, PathBuf};

/// Contract: `docs/requirements/paths-contract.md` runtime section (must match `resolve_runtime_root`).
pub fn resolve_runtime_root() -> Result<PathBuf, String> {
    resolve_runtime_root_with(&RuntimeRootContext::production())
}

pub fn resolve_runtime_root_with(ctx: &RuntimeRootContext) -> Result<PathBuf, String> {
    if let Some(override_root) = (ctx.getenv)("ALPHALOOP_RUNTIME_ROOT") {
        return Ok(PathBuf::from(override_root));
    }
    let base = linux_user_runtime_base_with(ctx)?;
    Ok(base.join("alphaloop"))
}

pub struct RuntimeRootContext {
    pub getenv: Box<dyn Fn(&str) -> Option<String>>,
    pub uid: u32,
    pub temp_dir: PathBuf,
    pub runtime_dir_usable: Box<dyn Fn(&Path, u32) -> bool>,
}

impl RuntimeRootContext {
    pub fn production() -> Self {
        Self {
            getenv: Box::new(|key| std::env::var(key).ok()),
            uid: current_uid(),
            temp_dir: std::env::temp_dir(),
            runtime_dir_usable: Box::new(production_runtime_dir_usable),
        }
    }
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

#[cfg(target_os = "linux")]
fn linux_user_runtime_base_with(ctx: &RuntimeRootContext) -> Result<PathBuf, String> {
    if let Some(xdg) = (ctx.getenv)("XDG_RUNTIME_DIR") {
        let path = PathBuf::from(xdg);
        if (ctx.runtime_dir_usable)(&path, ctx.uid) {
            return Ok(path);
        }
        eprintln!(
            "alphaloop: XDG_RUNTIME_DIR is set but not usable as a runtime dir ({}); trying fallbacks",
            path.display()
        );
    } else {
        eprintln!("alphaloop: XDG_RUNTIME_DIR is not set; using platformdirs-compatible runtime fallback");
    }
    let run_user = PathBuf::from(format!("/run/user/{}", ctx.uid));
    if (ctx.runtime_dir_usable)(&run_user, ctx.uid) {
        return Ok(run_user);
    }
    let temp = ctx.temp_dir.join(format!("runtime-{}", ctx.uid));
    std::fs::create_dir_all(&temp).map_err(|error| {
        format!(
            "could not create runtime fallback directory {}: {error} (set ALPHALOOP_RUNTIME_ROOT)",
            temp.display()
        )
    })?;
    Ok(temp)
}

#[cfg(not(target_os = "linux"))]
fn linux_user_runtime_base_with(_ctx: &RuntimeRootContext) -> Result<PathBuf, String> {
    dirs::runtime_dir().ok_or_else(|| {
        "could not resolve platform runtime directory (set ALPHALOOP_RUNTIME_ROOT)".into()
    })
}

#[cfg(target_os = "linux")]
fn current_uid() -> u32 {
    unsafe { libc::getuid() }
}

#[cfg(not(target_os = "linux"))]
fn current_uid() -> u32 {
    0
}

#[cfg(target_os = "linux")]
fn production_runtime_dir_usable(path: &Path, uid: u32) -> bool {
    use std::os::unix::fs::MetadataExt;
    match std::fs::symlink_metadata(path) {
        Ok(meta) => {
            if meta.file_type().is_symlink() || !meta.is_dir() {
                return false;
            }
            let mode = meta.mode() & 0o777;
            meta.uid() == uid && mode == 0o700
        }
        Err(_) => false,
    }
}

/// Non-Linux production builds do not probe `/run/user` or XDG tmpfs semantics; `linux_user_runtime_base_with`
/// uses `dirs::runtime_dir()` instead. This probe exists so `RuntimeRootContext::production()` compiles on
/// macOS/Windows and returns a sensible answer if callers reuse the hook.
#[cfg(not(target_os = "linux"))]
fn production_runtime_dir_usable(path: &Path, _uid: u32) -> bool {
    let Ok(meta) = std::fs::symlink_metadata(path) else {
        return false;
    };
    if meta.file_type().is_symlink() || !meta.is_dir() {
        return false;
    }
    let probe = path.join(".alphaloop-runtime-writable-probe");
    match std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&probe)
    {
        Ok(_) => {
            let _ = std::fs::remove_file(&probe);
            true
        }
        Err(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use std::collections::HashMap;
    use std::fs;
    use std::sync::{Mutex, MutexGuard};

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn env_lock_guard() -> MutexGuard<'static, ()> {
        ENV_LOCK.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    struct EnvRestore {
        saved: Vec<(String, Option<String>)>,
    }

    impl EnvRestore {
        fn capture_and_apply(env: &HashMap<String, String>) -> Self {
            let keys = ["ALPHALOOP_RUNTIME_ROOT", "XDG_RUNTIME_DIR"];
            let mut saved = Vec::new();
            for key in keys {
                let previous = std::env::var(key).ok();
                saved.push((key.to_string(), previous));
            }
            std::env::remove_var("ALPHALOOP_RUNTIME_ROOT");
            std::env::remove_var("XDG_RUNTIME_DIR");
            for (key, value) in env {
                std::env::set_var(key, value);
            }
            Self { saved }
        }
    }

    impl Drop for EnvRestore {
        fn drop(&mut self) {
            for (key, value) in &self.saved {
                match value {
                    Some(v) => std::env::set_var(key, v),
                    None => std::env::remove_var(key),
                }
            }
        }
    }

    #[derive(Debug, Deserialize)]
    struct RuntimeRootCase {
        id: String,
        env: HashMap<String, String>,
        uid: u32,
        temp_dir: String,
        xdg_runtime_dir: Option<String>,
        xdg_usable: bool,
        run_user_usable: bool,
        expected_root: String,
    }

    fn fixture_cases() -> Vec<RuntimeRootCase> {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tests/fixtures/runtime_root_cases.json");
        let raw = fs::read_to_string(&path).expect("fixture json");
        serde_json::from_str(&raw).expect("parse fixture")
    }

    fn context_for_case(case: &RuntimeRootCase) -> RuntimeRootContext {
        let env = case.env.clone();
        let xdg_for_env = case.xdg_runtime_dir.clone();
        let xdg_for_probe = case.xdg_runtime_dir.clone();
        let xdg_usable = case.xdg_usable;
        let run_user_usable = case.run_user_usable;
        let uid = case.uid;
        RuntimeRootContext {
            getenv: Box::new(move |key| {
                if key == "ALPHALOOP_RUNTIME_ROOT" {
                    return env.get("ALPHALOOP_RUNTIME_ROOT").cloned();
                }
                if key == "XDG_RUNTIME_DIR" {
                    return xdg_for_env.clone();
                }
                env.get(key).cloned()
            }),
            uid: case.uid,
            temp_dir: PathBuf::from(&case.temp_dir),
            runtime_dir_usable: Box::new(move |path, probe_uid| {
                if probe_uid != uid {
                    return false;
                }
                if xdg_for_probe.as_deref() == path.to_str() {
                    return xdg_usable;
                }
                let run_user = format!("/run/user/{}", uid);
                if path == Path::new(&run_user) {
                    return run_user_usable;
                }
                false
            }),
        }
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
    fn shared_fixture_table_runtime_root() {
        let _lock = env_lock_guard();
        for case in fixture_cases() {
            let _restore = EnvRestore::capture_and_apply(&case.env);
            let ctx = context_for_case(&case);
            let root = resolve_runtime_root_with(&ctx).expect(&case.id);
            assert_eq!(
                root,
                PathBuf::from(&case.expected_root),
                "case {}",
                case.id
            );
        }
    }
}
