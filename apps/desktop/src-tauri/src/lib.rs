mod commands;
mod sidecar;

pub use sidecar::{
    BindingSnapshot, EngineOwner, EngineSupervisor, ManagedChild, OwnerRecord, SidecarError,
};

use std::{
    io::{BufRead, BufReader},
    process::{Child, Command, Stdio},
    sync::Arc,
    thread,
};

use serde::Deserialize;
use tauri::{Manager, RunEvent, WindowEvent};

use commands::EngineConnection;
use commands::NotificationTracker;

struct TauriChild(Child);

impl ManagedChild for TauriChild {
    fn pid(&self) -> u32 {
        self.0.id()
    }

    fn kill(mut self: Box<Self>) -> Result<(), String> {
        self.0.kill().map_err(|error| error.to_string())?;
        self.0.wait().map_err(|error| error.to_string())?;
        Ok(())
    }
}

#[derive(Deserialize)]
struct Handshake {
    protocol_version: u16,
    status: String,
    owner: EngineOwner,
    pid: u32,
    endpoint: String,
    auth_token: String,
}

fn start_desktop_sidecar(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
) -> Result<(), String> {
    let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
    let executable = resource_dir
        .join("engine")
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
    match handshake.status.as_str() {
        "ready" => supervisor.adopt_owned(Box::new(TauriChild(child)), owner)?,
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
        for line in lines {
            if let Ok(line) = line {
                eprintln!("alphaloop-engine: {line}");
            }
        }
    });
    Ok(())
}

pub fn run() {
    let supervisor = Arc::new(EngineSupervisor::default());
    let connection = EngineConnection::default();
    let setup_supervisor = supervisor.clone();
    let setup_connection = connection.clone();
    let window_supervisor = supervisor.clone();
    let exit_supervisor = supervisor.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .manage(supervisor.clone())
        .manage(connection)
        .manage(NotificationTracker::default())
        .invoke_handler(tauri::generate_handler![
            commands::fetch_view,
            commands::create_draft,
            commands::confirm_run,
            commands::send_dialogue,
            commands::pause_research,
            commands::resume_research,
            commands::confirm_modification,
            commands::extend_research,
            commands::delete_research,
            commands::resolve_confirm,
            commands::export_artifact,
            commands::reverify,
            commands::revise_method,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let sidecar = setup_supervisor.clone();
            let engine_connection = setup_connection.clone();
            if let Err(error) = start_desktop_sidecar(handle, sidecar, engine_connection) {
                eprintln!("alphaloop sidecar startup failed: {error}");
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
