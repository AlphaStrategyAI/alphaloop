use alphaloop_desktop::{RestartPolicy, SidecarUiPhase, SidecarUiState};

#[test]
fn restart_cap_marks_stopped_message() {
    let policy = RestartPolicy {
        max_restarts: 2,
        base_delay_ms: 1,
        max_delay_ms: 10,
    };
    let mut state = SidecarUiState::running(&policy);
    state.record_crash(&policy, "sqlite");
    state.record_crash(&policy, "sqlite");
    assert_eq!(state.phase, SidecarUiPhase::Stopped);
    assert!(state.message.contains("引擎已停止"));
}
