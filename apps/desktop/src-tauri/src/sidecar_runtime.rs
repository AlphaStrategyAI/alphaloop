use std::sync::Mutex;

use crate::sidecar_policy::{RestartPolicy, SidecarUiPhase, SidecarUiState};

pub struct SidecarRuntime {
    pub policy: RestartPolicy,
    pub ui: Mutex<SidecarUiState>,
}

impl Default for SidecarRuntime {
    fn default() -> Self {
        let policy = RestartPolicy::default();
        Self {
            policy,
            ui: Mutex::new(SidecarUiState::running(&policy)),
        }
    }
}

impl SidecarRuntime {
    pub fn record_crash(&self, detail: &str) -> bool {
        let mut ui = self.ui.lock().expect("sidecar ui lock poisoned");
        ui.record_crash(&self.policy, detail);
        !matches!(ui.phase, SidecarUiPhase::Stopped)
    }

    pub fn mark_running(&self) {
        let mut ui = self.ui.lock().expect("sidecar ui lock poisoned");
        ui.mark_running();
    }

    pub fn prepare_user_restart(&self) {
        let mut ui = self.ui.lock().expect("sidecar ui lock poisoned");
        ui.user_restart();
    }
}
