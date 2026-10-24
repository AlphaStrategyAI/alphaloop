mod commands;
mod engine_paths;
mod secrets;
mod ui_language;
mod sidecar;
mod sidecar_policy;
mod sidecar_restart;
mod sidecar_runtime;

pub use sidecar::{
    BindingSnapshot, EngineOwner, EngineSupervisor, ManagedChild, OwnerRecord, SidecarError,
};
pub use sidecar_policy::{RestartPolicy, SidecarUiPhase, SidecarUiState};

use std::{
    io::{BufRead, BufReader},
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    thread,
};

use serde::Deserialize;
use tauri::{Manager, RunEvent, WindowEvent};

use commands::EngineConnection;
use secrets::SecretVault;
use sidecar::SharedChild;
use sidecar_runtime::SidecarRuntime;

#[derive(Deserialize)]
struct Handshake {
    protocol_version: u16,
    status: String,
    owner: EngineOwner,
    pid: u32,
    endpoint: String,
    auth_token: String,
}

/// Hide the console. A windowed parent that spawns a `console=True` PyInstaller
/// exe otherwise allocates a console, and the bootloader rebinds stdout away
/// from the pipe. The parent then sees EOF and reports "exited before handshake"
/// with empty stderr.
#[cfg_attr(not(windows), allow(dead_code))]
const WINDOWS_CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn engine_command(executable: &std::path::Path) -> Command {
    let mut command = Command::new(executable);
    if let Some(directory) = executable.parent() {
        // PyInstaller onedir resolves `_internal` next to the executable. Native
        // extensions still search the process working directory, which for a
        // double-clicked app is not the bundle folder.
        command.current_dir(directory);
    }
    command
        .args(["--owner", "desktop"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(WINDOWS_CREATE_NO_WINDOW);
    }
    command
}

fn describe_handshake_failure(executable: &std::path::Path, status: &str, stderr: &str) -> String {
    let stderr = stderr.trim();
    let stderr = if stderr.is_empty() { "(empty)" } else { stderr };
    let stderr: String = stderr.chars().take(4000).collect();
    format!(
        "engine exited before handshake (exe {}, status {status}, stderr {stderr})",
        executable.display()
    )
}

pub fn start_desktop_sidecar(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
    runtime: Arc<SidecarRuntime>,
    vault: Arc<SecretVault>,
) -> Result<(), String> {
    let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
    let executable = resource_dir
        .join("engine")
        .join("alphaloop-engine")
        .join(if cfg!(windows) {
            "alphaloop-engine.exe"
        } else {
            "alphaloop-engine"
        });
    let mut child = engine_command(&executable)
        .spawn()
        .map_err(|error| format!("failed to spawn {}: {error}", executable.display()))?;
    let stderr = child.stderr.take().ok_or("engine stderr was not piped")?;
    let stderr_vault = vault.clone();
    let stderr_text = Arc::new(Mutex::new(String::new()));
    let stderr_for_thread = stderr_text.clone();
    let stderr_thread = thread::spawn(move || {
        let mut reader = BufReader::new(stderr);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    let redacted = stderr_vault.redact(line.trim_end());
                    let message = format!("alphaloop-engine stderr: {redacted}");
                    eprintln!("{message}");
                    append_desktop_log(&message);
                    if let Ok(mut buffer) = stderr_for_thread.lock() {
                        buffer.push_str(&redacted);
                        buffer.push('\n');
                    }
                }
                Err(error) => {
                    append_desktop_log(&format!("alphaloop-engine stderr read failed: {error}"));
                    break;
                }
            }
        }
    });
    let stdout = child.stdout.take().ok_or("engine stdout was not piped")?;
    let mut lines = BufReader::new(stdout).lines();
    let first = match lines.next() {
        Some(Ok(line)) => line,
        Some(Err(error)) => {
            let _ = child.kill();
            let _ = child.wait();
            let _ = stderr_thread.join();
            return Err(format!("engine stdout read failed: {error}"));
        }
        None => {
            let status = match child.try_wait() {
                Ok(Some(status)) => status.to_string(),
                Ok(None) => {
                    let _ = child.kill();
                    match child.wait() {
                        Ok(status) => format!("killed after stdout closed ({status})"),
                        Err(error) => format!("killed after stdout closed (wait error {error})"),
                    }
                }
                Err(error) => format!("wait error {error}"),
            };
            let _ = stderr_thread.join();
            let stderr = stderr_text
                .lock()
                .map(|text| text.clone())
                .unwrap_or_else(|poisoned| poisoned.into_inner().clone());
            return Err(describe_handshake_failure(&executable, &status, &stderr));
        }
    };
    let handshake: Handshake = match serde_json::from_str(&first) {
        Ok(handshake) => handshake,
        Err(error) => {
            child.kill().map_err(|kill_error| kill_error.to_string())?;
            return Err(error.to_string());
        }
    };
    if handshake.protocol_version != 1 {
        child.kill().map_err(|error| error.to_string())?;
        return Err("engine protocol version mismatch".into());
    }
    let owner = OwnerRecord {
        protocol_version: handshake.protocol_version,
        owner: handshake.owner,
        pid: handshake.pid,
        endpoint: handshake.endpoint.clone(),
        auth_token: handshake.auth_token.clone(),
    };
    connection.set(handshake.endpoint, handshake.auth_token)?;
    append_desktop_log(&format!(
        "alphaloop-engine handshake status={} pid={}",
        handshake.status, handshake.pid
    ));
    let on_exit = {
        let app_handle = app.clone();
        let supervisor = supervisor.clone();
        let connection = connection.clone();
        let runtime = runtime.clone();
        let vault = vault.clone();
        move || {
            schedule_sidecar_restart(
                app_handle,
                supervisor,
                connection,
                runtime,
                vault.clone(),
                "process exited",
            )
        }
    };
    match handshake.status.as_str() {
        "ready" => supervisor.adopt_owned(Box::new(SharedChild::spawn(child, on_exit)), owner)?,
        "already_running" => {
            if owner.owner != EngineOwner::Cli {
                child.kill().map_err(|error| error.to_string())?;
                return Err("another desktop instance already owns the engine".into());
            }
            supervisor.attach(owner)?;
            child.wait().map_err(|error| error.to_string())?;
        }
        _ => {
            child.kill().map_err(|error| error.to_string())?;
            return Err("unknown engine handshake status".into());
        }
    }
    thread::spawn(move || {
        for line in lines.map_while(Result::ok) {
            let message = format!("alphaloop-engine: {line}");
            eprintln!("{message}");
            append_desktop_log(&message);
        }
    });
    runtime.mark_running();
    tauri::async_runtime::block_on(commands::push_installed_secrets(&connection, &vault));
    Ok(())
}

fn append_desktop_log(line: &str) {
    let path = crate::ui_language::data_root().join("desktop.log");
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let mut file = match std::fs::OpenOptions::new().create(true).append(true).open(&path) {
        Ok(file) => file,
        Err(_) => return,
    };
    use std::io::Write;
    let _ = writeln!(file, "{line}");
}

fn schedule_sidecar_restart(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
    runtime: Arc<SidecarRuntime>,
    vault: Arc<SecretVault>,
    detail: &'static str,
) {
    sidecar_restart::schedule_sidecar_recovery(
        app,
        supervisor,
        connection,
        runtime,
        vault,
        detail.to_string(),
    );
}

#[cfg(windows)]
fn detach_inherited_console() {
    // msedgedriver is a console process. WebView2 keeps that console as a
    // visible ConsoleWindowClass window. A double-clicked app has none;
    // detaching is a no-op in that case.
    #[link(name = "kernel32")]
    extern "system" {
        fn FreeConsole() -> i32;
    }
    unsafe {
        FreeConsole();
    }
}

pub fn run() {
    #[cfg(windows)]
    detach_inherited_console();

    let supervisor = Arc::new(EngineSupervisor::default());
    let vault = Arc::new(SecretVault::open_default());
    let connection = EngineConnection::with_redactor({
        let vault = vault.clone();
        Arc::new(move |text| vault.redact(text))
    });
    let runtime = Arc::new(SidecarRuntime::default());
    let setup_supervisor = supervisor.clone();
    let setup_connection = connection.clone();
    let setup_runtime = runtime.clone();
    let setup_vault = vault.clone();
    let window_supervisor = supervisor.clone();
    let exit_supervisor = supervisor.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .manage(supervisor.clone())
        .manage(connection)
        .manage(runtime.clone())
        .manage(vault.clone())
        .invoke_handler(tauri::generate_handler![
            commands::fetch_view,
            commands::market_data_progress,
            commands::create_draft,
            commands::confirm_run,
            commands::set_research_symbol,
            commands::answer_symbol_ask,
            commands::use_hinted_symbol,
            commands::revert_symbol_ask,
            commands::remove_market_side,
            commands::dismiss_mismatched_symbol,
            commands::choose_default_market,
            commands::unlock_brief,
            commands::send_dialogue,
            commands::pause_research,
            commands::resume_research,
            commands::confirm_modification,
            commands::continue_iterate,
            commands::extend_research,
            commands::delete_research,
            commands::resolve_confirm,
            commands::export_artifact,
            commands::reveal_export_in_folder,
            commands::reverify,
            commands::revise_method,
            commands::create_method,
            commands::engine_sidecar_state,
            commands::restart_engine_sidecar,
            commands::get_ui_language,
            commands::set_ui_language,
            commands::read_system_locale,
            commands::set_engine_locale,
            commands::secret_store_status,
            commands::secret_choose_fallback,
            commands::secret_set,
            commands::secret_delete,
            commands::secret_is_set,
            commands::secret_unlock,
            commands::secret_failure_preview,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let sidecar = setup_supervisor.clone();
            let engine_connection = setup_connection.clone();
            let sidecar_runtime = setup_runtime.clone();
            let sidecar_vault = setup_vault.clone();
            if let Err(error) = start_desktop_sidecar(
                handle.clone(),
                sidecar.clone(),
                engine_connection.clone(),
                sidecar_runtime.clone(),
                sidecar_vault.clone(),
            ) {
                let message = format!(
                    "alphaloop sidecar startup failed: {}",
                    sidecar_vault.redact(&error)
                );
                eprintln!("{message}");
                append_desktop_log(&message);
                sidecar_restart::schedule_sidecar_recovery(
                    handle,
                    sidecar,
                    engine_connection,
                    sidecar_runtime,
                    sidecar_vault,
                    error,
                );
            }
            Ok(())
        })
        .on_window_event(move |window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let count = window.app_handle().webview_windows().len();
                if let Err(error) = window_supervisor.window_close_requested(count) {
                    eprintln!("alphaloop sidecar close failed: {error}");
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build alphaloop desktop");
    app.run(move |_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. }) {
            if let Err(error) = exit_supervisor.quit() {
                eprintln!("alphaloop sidecar quit failed: {error}");
            }
        }
    });
}

#[cfg(test)]
mod engine_spawn_tests {
    use super::{describe_handshake_failure, engine_command, WINDOWS_CREATE_NO_WINDOW};
    use std::path::Path;

    #[test]
    fn windows_spawn_hides_the_console() {
        assert_eq!(WINDOWS_CREATE_NO_WINDOW, 0x0800_0000);
    }

    #[test]
    fn engine_starts_in_its_bundle_directory() {
        let executable = Path::new("/opt/alphaloop/engine/alphaloop-engine/alphaloop-engine");
        let command = engine_command(executable);
        assert_eq!(
            command.get_current_dir(),
            Some(Path::new("/opt/alphaloop/engine/alphaloop-engine"))
        );
    }

    #[test]
    fn handshake_failure_records_status_and_stderr() {
        let message = describe_handshake_failure(
            Path::new("alphaloop-engine.exe"),
            "exit code: 0xc0000135",
            "Failed to load Python DLL",
        );
        assert!(message.contains("exited before handshake"));
        assert!(message.contains("exit code: 0xc0000135"));
        assert!(message.contains("Failed to load Python DLL"));
        assert!(message.contains("alphaloop-engine.exe"));
    }

    #[test]
    fn handshake_failure_marks_empty_stderr() {
        let message = describe_handshake_failure(Path::new("alphaloop-engine.exe"), "exit code: 1", "");
        assert!(message.contains("stderr (empty)"));
    }
}
