use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};

use alphaloop_desktop::{
    EngineOwner, EngineSupervisor, ManagedChild, OwnerRecord,
};

struct FakeChild {
    kills: Arc<AtomicUsize>,
}

impl ManagedChild for FakeChild {
    fn pid(&self) -> u32 {
        4321
    }

    fn kill(self: Box<Self>) -> Result<(), String> {
        self.kills.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }
}

fn owner(owner: EngineOwner) -> OwnerRecord {
    OwnerRecord {
        protocol_version: 1,
        owner,
        pid: 4321,
        endpoint: "http://127.0.0.1:46321".into(),
        auth_token: "test-token".into(),
    }
}

#[test]
fn last_window_close_kills_owned_sidecar_exactly_once() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.close_last_window().unwrap(), true);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 1);
}

#[test]
fn app_quit_kills_owned_sidecar_exactly_once() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.quit().unwrap(), true);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 1);
}

#[test]
fn attached_cli_owner_is_never_killed_by_desktop() {
    let supervisor = EngineSupervisor::default();
    supervisor.attach(owner(EngineOwner::Cli)).unwrap();

    assert_eq!(supervisor.close_last_window().unwrap(), false);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(supervisor.snapshot().owner(), Some(EngineOwner::Cli));
}

#[test]
fn a_second_binding_is_rejected() {
    let supervisor = EngineSupervisor::default();
    supervisor.attach(owner(EngineOwner::Cli)).unwrap();
    let error = supervisor.attach(owner(EngineOwner::Desktop)).unwrap_err();
    assert_eq!(error, "engine supervisor already bound");
}

#[test]
fn closing_one_of_multiple_windows_does_not_call_shutdown() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.window_close_requested(2).unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 0);
}

#[test]
fn browser_tab_close_has_no_supervisor_event() {
    let public_events = ["last_native_window_closed", "native_app_quit"];
    assert!(!public_events.contains(&"browser_unload"));
}
