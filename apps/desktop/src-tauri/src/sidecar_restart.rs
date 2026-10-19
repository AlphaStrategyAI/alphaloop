use std::sync::Arc;
use std::thread;
use std::time::Duration;

use tauri::AppHandle;

use crate::commands::EngineConnection;
use crate::engine_paths;
use crate::secrets::SecretVault;
use crate::sidecar::EngineSupervisor;
use crate::sidecar_runtime::SidecarRuntime;
use crate::start_desktop_sidecar;

pub enum SidecarFailureOutcome {
    Stopped,
    Retry(Duration),
}

/// Record a crash / failed start and decide whether to retry or stop.
pub fn after_sidecar_failure(runtime: &SidecarRuntime, detail: &str) -> SidecarFailureOutcome {
    if !runtime.record_crash(detail) {
        return SidecarFailureOutcome::Stopped;
    }
    let attempt = runtime.ui.lock().expect("sidecar ui lock poisoned").restart_count;
    SidecarFailureOutcome::Retry(runtime.policy.backoff_delay(attempt))
}

pub fn on_sidecar_stopped(connection: &EngineConnection) {
    engine_paths::clear_owner_file_logged();
    connection.clear();
}

pub fn schedule_sidecar_recovery(
    app: AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
    runtime: Arc<SidecarRuntime>,
    vault: Arc<SecretVault>,
    detail: String,
) {
    match after_sidecar_failure(runtime.as_ref(), &detail) {
        SidecarFailureOutcome::Stopped => on_sidecar_stopped(&connection),
        SidecarFailureOutcome::Retry(delay) => {
            thread::spawn(move || {
                thread::sleep(delay);
                let _ = supervisor.quit();
                match start_desktop_sidecar(
                    app.clone(),
                    supervisor.clone(),
                    connection.clone(),
                    runtime.clone(),
                    vault.clone(),
                ) {
                    Ok(()) => {}
                    Err(error) => {
                        eprintln!(
                            "alphaloop sidecar restart failed: {}",
                            vault.redact(&error)
                        );
                        schedule_sidecar_recovery(
                            app,
                            supervisor,
                            connection,
                            runtime,
                            vault,
                            error,
                        );
                    }
                }
            });
        }
    }
}

/// Synchronous driver for unit tests (no thread sleep).
#[cfg(test)]
pub fn drive_recovery_sync(
    runtime: &SidecarRuntime,
    mut spawner: impl FnMut() -> Result<(), String>,
    mut detail: String,
    max_steps: usize,
) -> usize {
    for step in 1..=max_steps {
        match after_sidecar_failure(runtime, &detail) {
            SidecarFailureOutcome::Stopped => return step,
            SidecarFailureOutcome::Retry(_delay) => match spawner() {
                Ok(()) => {
                    runtime.mark_running();
                    return step;
                }
                Err(error) => detail = error,
            },
        }
    }
    panic!("drive_recovery_sync exceeded {max_steps} steps");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sidecar_policy::{RestartPolicy, SidecarUiPhase, SidecarUiState};
    use std::sync::Mutex;

    fn test_runtime(policy: RestartPolicy) -> SidecarRuntime {
        SidecarRuntime {
            policy,
            ui: Mutex::new(SidecarUiState::running(&policy)),
        }
    }

    #[test]
    fn handshake_failure_retries_with_backoff_until_stopped() {
        let policy = RestartPolicy {
            max_restarts: 3,
            base_delay_ms: 1,
            max_delay_ms: 1,
        };
        let runtime = test_runtime(policy);
        let mut attempts = 0;
        let steps = drive_recovery_sync(
            &runtime,
            || {
                attempts += 1;
                Err("engine exited before handshake".into())
            },
            "process exited".into(),
            10,
        );
        assert!(steps >= 3);
        assert_eq!(attempts, 2);
        assert_eq!(
            runtime.ui.lock().expect("lock").phase,
            SidecarUiPhase::Stopped
        );
    }

    #[test]
    fn startup_failures_share_counter_with_post_ready_crashes() {
        let policy = RestartPolicy {
            max_restarts: 4,
            base_delay_ms: 1,
            max_delay_ms: 1,
        };
        let runtime = test_runtime(policy);
        let mut attempts = 0;
        drive_recovery_sync(
            &runtime,
            || {
                attempts += 1;
                if attempts < 2 {
                    Err("engine exited before handshake".into())
                } else {
                    Ok(())
                }
            },
            "process exited".into(),
            10,
        );
        assert_eq!(runtime.ui.lock().expect("lock").phase, SidecarUiPhase::Running);
        assert_eq!(runtime.ui.lock().expect("lock").restart_count, 2);
        drive_recovery_sync(
            &runtime,
            || Err("process exited".into()),
            "process exited".into(),
            10,
        );
        assert_eq!(runtime.ui.lock().expect("lock").restart_count, 4);
        assert_eq!(
            runtime.ui.lock().expect("lock").phase,
            SidecarUiPhase::Stopped
        );
    }

    #[test]
    fn successful_restart_keeps_restart_count_per_policy() {
        let policy = RestartPolicy::default();
        let runtime = test_runtime(policy);
        drive_recovery_sync(
            &runtime,
            || Ok(()),
            "process exited".into(),
            5,
        );
        assert_eq!(runtime.ui.lock().expect("lock").restart_count, 1);
        assert_eq!(
            runtime.ui.lock().expect("lock").phase,
            SidecarUiPhase::Running
        );
    }
}
