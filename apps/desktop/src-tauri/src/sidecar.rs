use std::process::Child;
use std::sync::{Arc, Mutex};
use std::thread;

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
    child: Arc<Mutex<Option<Child>>>,
}

impl SharedChild {
    pub fn spawn(child: Child, on_exit: impl FnOnce() + Send + 'static) -> Self {
        let shared = Arc::new(Mutex::new(Some(child)));
        let waiter = shared.clone();
        thread::spawn(move || {
            let mut slot = waiter.lock().expect("child lock poisoned");
            if let Some(mut process) = slot.take() {
                let _ = process.wait();
            }
            on_exit();
        });
        Self { child: shared }
    }
}

impl ManagedChild for SharedChild {
    fn pid(&self) -> u32 {
        self.child
            .lock()
            .expect("child lock poisoned")
            .as_ref()
            .map(|process| process.id())
            .unwrap_or(0)
    }

    fn kill(self: Box<Self>) -> Result<(), String> {
        let mut slot = self.child.lock().map_err(|_| "child lock poisoned")?;
        if let Some(mut process) = slot.take() {
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
