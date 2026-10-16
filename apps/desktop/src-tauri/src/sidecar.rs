use std::process::Child;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum EngineOwner {
    Desktop,
    Cli,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub struct OwnerRecord {
    pub protocol_version: u16,
    pub owner: EngineOwner,
    pub pid: u32,
    pub endpoint: String,
    pub auth_token: String,
}

pub trait ManagedChild: Send {
    fn pid(&self) -> u32;
    fn kill(self: Box<Self>) -> Result<(), String>;
}

pub struct SharedChild {
    pub(crate) child: Arc<Mutex<Option<Child>>>,
}

impl SharedChild {
    pub fn spawn(child: Child, on_exit: impl FnOnce() + Send + 'static) -> Self {
        let shared = Arc::new(Mutex::new(Some(child)));
        let waiter = Arc::clone(&shared);
        thread::spawn(move || {
            // Child::wait() closes stdin first; engine exits on stdin EOF — keep it open.
            let stdin_keepalive = {
                let mut guard = waiter.lock().expect("child lock poisoned");
                guard.as_mut().and_then(|process| process.stdin.take())
            };
            loop {
                let finished = {
                    let mut guard = waiter.lock().expect("child lock poisoned");
                    match guard.as_mut() {
                        None => true,
                        Some(process) => match process.try_wait() {
                            Ok(Some(_status)) => {
                                guard.take();
                                true
                            }
                            Ok(None) => false,
                            Err(_) => {
                                guard.take();
                                true
                            }
                        },
                    }
                };
                if finished {
                    break;
                }
                thread::sleep(Duration::from_millis(100));
            }
            drop(stdin_keepalive);
            on_exit();
        });
        Self { child: shared }
    }

    fn with_child<R>(&self, f: impl FnOnce(&mut Child) -> R) -> Option<R> {
        let mut guard = self.child.lock().expect("child lock poisoned");
        guard.as_mut().map(f)
    }
}

impl ManagedChild for SharedChild {
    fn pid(&self) -> u32 {
        self.with_child(|process| process.id()).unwrap_or(0)
    }

    fn kill(self: Box<Self>) -> Result<(), String> {
        let mut guard = self.child.lock().map_err(|_| "child lock poisoned")?;
        if let Some(mut process) = guard.take() {
            process.kill().map_err(|error| error.to_string())?;
            process.wait().map_err(|error| error.to_string())?;
        }
        Ok(())
    }
}

enum Binding {
    Stopped,
    Owned {
        child: Box<dyn ManagedChild>,
        owner: OwnerRecord,
    },
    Attached(OwnerRecord),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BindingSnapshot {
    Stopped,
    Owned(OwnerRecord),
    Attached(OwnerRecord),
}

impl BindingSnapshot {
    pub fn owner(&self) -> Option<EngineOwner> {
        match self {
            Self::Stopped => None,
            Self::Owned(record) | Self::Attached(record) => Some(record.owner),
        }
    }
}

pub type SidecarError = String;

pub struct EngineSupervisor {
    binding: Mutex<Binding>,
}

impl Default for EngineSupervisor {
    fn default() -> Self {
        Self {
            binding: Mutex::new(Binding::Stopped),
        }
    }
}

impl EngineSupervisor {
    pub fn adopt_owned(
        &self,
        child: Box<dyn ManagedChild>,
        owner: OwnerRecord,
    ) -> Result<(), SidecarError> {
        if owner.owner != EngineOwner::Desktop || child.pid() != owner.pid {
            return Err("owned child does not match desktop handshake".into());
        }
        let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
        if !matches!(*binding, Binding::Stopped) {
            return Err("engine supervisor already bound".into());
        }
        *binding = Binding::Owned { child, owner };
        Ok(())
    }

    pub fn attach(&self, owner: OwnerRecord) -> Result<(), SidecarError> {
        let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
        if !matches!(*binding, Binding::Stopped) {
            return Err("engine supervisor already bound".into());
        }
        *binding = Binding::Attached(owner);
        Ok(())
    }

    pub fn snapshot(&self) -> BindingSnapshot {
        let binding = self.binding.lock().expect("supervisor lock poisoned");
        match &*binding {
            Binding::Stopped => BindingSnapshot::Stopped,
            Binding::Owned { owner, .. } => BindingSnapshot::Owned(owner.clone()),
            Binding::Attached(owner) => BindingSnapshot::Attached(owner.clone()),
        }
    }

    pub fn window_close_requested(&self, native_window_count: usize) -> Result<bool, SidecarError> {
        if native_window_count == 1 {
            self.close_last_window()
        } else {
            Ok(false)
        }
    }

    pub fn close_last_window(&self) -> Result<bool, SidecarError> {
        self.shutdown_owned()
    }

    pub fn quit(&self) -> Result<bool, SidecarError> {
        self.shutdown_owned()
    }

    fn shutdown_owned(&self) -> Result<bool, SidecarError> {
        let prior = {
            let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
            std::mem::replace(&mut *binding, Binding::Stopped)
        };
        match prior {
            Binding::Owned { child, .. } => {
                child.kill()?;
                Ok(true)
            }
            Binding::Attached(owner) => {
                let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
                *binding = Binding::Attached(owner);
                Ok(false)
            }
            Binding::Stopped => Ok(false),
        }
    }
}

#[cfg(test)]
mod shared_child_tests {
    use super::*;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::time::{Duration, Instant};

    fn spawn_sleep_child(seconds: u32) -> Child {
        Command::new("sleep")
            .arg(seconds.to_string())
            .stdin(Stdio::piped())
            .spawn()
            .expect("spawn sleep")
    }

    fn spawn_exits_when_stdin_closes() -> Child {
        Command::new("sh")
            .arg("-c")
            .arg("read -r _ || exit 0; exec sleep 300")
            .stdin(Stdio::piped())
            .spawn()
            .expect("spawn sh")
    }

    fn process_alive(pid: u32) -> bool {
        Command::new("kill")
            .arg("-0")
            .arg(pid.to_string())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    }

    #[test]
    fn child_stays_alive_while_stdin_held_open() {
        let child = spawn_exits_when_stdin_closes();
        let _guard = SharedChild::spawn(child, || {});
        thread::sleep(Duration::from_millis(400));
        let pid = _guard.pid();
        assert_ne!(pid, 0);
        assert!(process_alive(pid), "child should not exit when stdin is held");
    }

    #[test]
    fn pid_and_kill_do_not_deadlock_while_child_running() {
        let child = spawn_sleep_child(30);
        let shared = SharedChild::spawn(child, || {});
        let pid = shared.pid();
        assert_ne!(pid, 0);
        let done = Arc::new(AtomicBool::new(false));
        let done_flag = Arc::clone(&done);
        let poller = thread::spawn({
            let shared = SharedChild {
                child: Arc::clone(&shared.child),
            };
            move || {
                let deadline = Instant::now() + Duration::from_secs(2);
                while Instant::now() < deadline {
                    let _ = shared.pid();
                    thread::sleep(Duration::from_millis(20));
                }
                done_flag.store(true, Ordering::SeqCst);
            }
        });
        thread::sleep(Duration::from_millis(50));
        Box::new(SharedChild {
            child: Arc::clone(&shared.child),
        })
            .kill()
            .expect("kill");
        poller.join().expect("poller join");
        assert!(done.load(Ordering::SeqCst));
    }

    #[test]
    fn external_kill_invokes_on_exit() {
        let child = spawn_sleep_child(60);
        let fired = Arc::new(AtomicBool::new(false));
        let shared = SharedChild::spawn(child, {
            let fired = Arc::clone(&fired);
            move || fired.store(true, Ordering::SeqCst)
        });
        let pid = shared.pid();
        assert!(Command::new("kill")
            .arg(pid.to_string())
            .status()
            .expect("kill status")
            .success());
        let deadline = Instant::now() + Duration::from_secs(3);
        while Instant::now() < deadline {
            if fired.load(Ordering::SeqCst) {
                return;
            }
            thread::sleep(Duration::from_millis(50));
        }
        panic!("on_exit was not invoked after external kill");
    }
}
