use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RestartPolicy {
    pub max_restarts: u32,
    pub base_delay_ms: u64,
    pub max_delay_ms: u64,
}

impl Default for RestartPolicy {
    fn default() -> Self {
        Self {
            max_restarts: 5,
            base_delay_ms: 500,
            max_delay_ms: 30_000,
        }
    }
}

impl RestartPolicy {
    pub fn backoff_delay(&self, restart_attempt: u32) -> Duration {
        if restart_attempt == 0 {
            return Duration::from_millis(self.base_delay_ms);
        }
        let exp = restart_attempt.min(10);
        let scaled = self.base_delay_ms.saturating_mul(1u64 << exp.min(6));
        Duration::from_millis(scaled.min(self.max_delay_ms))
    }

    pub fn cap_exceeded(&self, restart_count: u32) -> bool {
        restart_count >= self.max_restarts
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SidecarUiPhase {
    Running,
    Restarting,
    Stopped,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SidecarUiState {
    pub phase: SidecarUiPhase,
    pub restart_count: u32,
    pub max_restarts: u32,
    pub message: String,
}

impl SidecarUiState {
    pub fn running(policy: &RestartPolicy) -> Self {
        Self {
            phase: SidecarUiPhase::Running,
            restart_count: 0,
            max_restarts: policy.max_restarts,
            message: String::new(),
        }
    }

    pub fn record_crash(&mut self, policy: &RestartPolicy, detail: &str) {
        self.restart_count += 1;
        if policy.cap_exceeded(self.restart_count) {
            self.phase = SidecarUiPhase::Stopped;
            self.message = format!("引擎已停止：{}", detail);
            return;
        }
        self.phase = SidecarUiPhase::Restarting;
        self.message = format!("引擎异常退出，正在重启（{}/{}）", self.restart_count, policy.max_restarts);
    }

    pub fn mark_running(&mut self) {
        self.phase = SidecarUiPhase::Running;
        self.message.clear();
    }

    pub fn user_restart(&mut self) {
        self.restart_count = 0;
        self.phase = SidecarUiPhase::Restarting;
        self.message = "正在重启引擎…".into();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backoff_grows_and_caps() {
        let policy = RestartPolicy::default();
        let d1 = policy.backoff_delay(1);
        let d2 = policy.backoff_delay(2);
        assert!(d2 >= d1);
        assert!(policy.backoff_delay(20).as_millis() <= policy.max_delay_ms as u128);
    }

    #[test]
    fn cap_marks_stopped() {
        let policy = RestartPolicy {
            max_restarts: 2,
            base_delay_ms: 10,
            max_delay_ms: 100,
        };
        let mut state = SidecarUiState::running(&policy);
        state.record_crash(&policy, "sqlite");
        assert_eq!(state.phase, SidecarUiPhase::Restarting);
        state.record_crash(&policy, "sqlite");
        assert_eq!(state.phase, SidecarUiPhase::Stopped);
        assert!(state.message.contains("引擎已停止"));
    }

    #[test]
    fn user_restart_resets_counter() {
        let policy = RestartPolicy::default();
        let mut state = SidecarUiState::running(&policy);
        state.restart_count = 3;
        state.user_restart();
        assert_eq!(state.restart_count, 0);
        assert_eq!(state.phase, SidecarUiPhase::Restarting);
    }
}
