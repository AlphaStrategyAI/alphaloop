mod commands;
mod engine_paths;
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
    sync::Arc,
    thread,
};

use serde::Deserialize;
use tauri::{Manager, RunEvent, WindowEvent};

use commands::EngineConnection;
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

pub fn start_desktop_sidecar(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
    runtime: Arc<SidecarRuntime>,
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
    let mut child = Command::new(executable)
        .args(["--owner", "desktop"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| error.to_string())?;
    let stderr = child.stderr.take().ok_or("engine stderr was not piped")?;
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            eprintln!("alphaloop-engine stderr: {line}");
        }
    });
    let stdout = child.stdout.take().ok_or("engine stdout was not piped")?;
    let mut lines = BufReader::new(stdout).lines();
    let first = lines
        .next()
        .ok_or("engine exited before handshake")?
        .map_err(|error| error.to_string())?;
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
    let on_exit = {
        let app_handle = app.clone();
        let supervisor = supervisor.clone();
        let connection = connection.clone();
        let runtime = runtime.clone();
        move || schedule_sidecar_restart(app_handle, supervisor, connection, runtime, "process exited")
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
            eprintln!("alphaloop-engine: {line}");
        }
    });
    runtime.mark_running();
    Ok(())
}

fn schedule_sidecar_restart(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
    runtime: Arc<SidecarRuntime>,
    detail: &'static str,
) {
    sidecar_restart::schedule_sidecar_recovery(
        app,
        supervisor,
        connection,
        runtime,
        detail.to_string(),
    );
}

pub fn run() {
    let supervisor = Arc::new(EngineSupervisor::default());
    let connection = EngineConnection::default();
    let runtime = Arc::new(SidecarRuntime::default());
    let setup_supervisor = supervisor.clone();
    let setup_connection = connection.clone();
    let setup_runtime = runtime.clone();
    let window_supervisor = supervisor.clone();
    let exit_supervisor = supervisor.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .manage(supervisor.clone())
        .manage(connection)
        .manage(runtime.clone())
        .invoke_handler(tauri::generate_handler![
            commands::fetch_view,
            commands::create_draft,
            commands::confirm_run,
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
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let sidecar = setup_supervisor.clone();
            let engine_connection = setup_connection.clone();
            let sidecar_runtime = setup_runtime.clone();
            if let Err(error) = start_desktop_sidecar(
                handle.clone(),
                sidecar.clone(),
                engine_connection.clone(),
                sidecar_runtime.clone(),
            ) {
                eprintln!("alphaloop sidecar startup failed: {error}");
                sidecar_restart::schedule_sidecar_recovery(
                    handle,
                    sidecar,
                    engine_connection,
                    sidecar_runtime,
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
