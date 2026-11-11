//! A placement/call gate is checked again at the log's link operation. The
//! lock orders a cancellation or stop against publication, including a handler
//! that was already executing. Candidate payloads can remain unreferenced.
use crate::archive::Fail;
use std::cell::RefCell;
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::Instant;

#[derive(Clone)]
pub struct Gate {
    stopped: Arc<Mutex<bool>>,
    cancelled: Arc<Mutex<bool>>,
    deadline: Instant,
}
thread_local! { static CURRENT: RefCell<Option<Gate>> = const { RefCell::new(None) }; }
pub fn current() -> Option<Gate> {
    CURRENT.with(|g| g.borrow().clone())
}
pub struct Permit<'a> {
    _stop: MutexGuard<'a, bool>,
    _cancel: MutexGuard<'a, bool>,
}
impl Gate {
    pub fn new(deadline: Instant) -> Self {
        Self {
            stopped: Arc::new(Mutex::new(false)),
            cancelled: Arc::new(Mutex::new(false)),
            deadline,
        }
    }
    pub fn call(&self) -> Self {
        Self {
            cancelled: Arc::new(Mutex::new(false)),
            ..self.clone()
        }
    }
    pub fn stop(&self) {
        *self.stopped.lock().unwrap_or_else(|e| e.into_inner()) = true;
    }
    pub fn cancel(&self) {
        *self.cancelled.lock().unwrap_or_else(|e| e.into_inner()) = true;
    }
    pub fn permit(&self) -> Result<Permit<'_>, Fail> {
        let stop = self.stopped.lock().unwrap_or_else(|e| e.into_inner());
        let cancel = self.cancelled.lock().unwrap_or_else(|e| e.into_inner());
        if *stop || *cancel || Instant::now() >= self.deadline {
            return Err(Fail::refused(
                "placement_stopped",
                "This placement or call stopped before publication; no authoring record was linked.",
            ));
        }
        Ok(Permit {
            _stop: stop,
            _cancel: cancel,
        })
    }
    pub fn within<T>(&self, f: impl FnOnce() -> T) -> T {
        struct Reset(Option<Gate>);
        impl Drop for Reset {
            fn drop(&mut self) {
                CURRENT.with(|g| *g.borrow_mut() = self.0.take());
            }
        }
        let _reset = Reset(CURRENT.with(|g| g.replace(Some(self.clone()))));
        f()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::log::{self, PubErr};
    use std::time::Duration;

    #[test]
    fn publication_control_late_stop_and_fresh_invariance() {
        let (path, audit) = log::tests::scratch_audit();
        let live = Gate::new(Instant::now() + Duration::from_secs(60));
        // A positive publication through the actual log path establishes that
        // the archive and body builder can publish, before changing only stop.
        assert!(
            live.within(|| log::publish(&audit, "reference", |_| Ok(log::tests::reference_body())))
                .is_ok()
        );
        let count = audit.sub("log").unwrap().names().unwrap().len();
        let call = live.call();
        let result = call.within(|| {
            log::publish(&audit, "close_requested", |_| {
                // The handler already ran and built a body. Cancellation wins
                // before linking; the stage file is an independent witness.
                call.cancel();
                Ok(log::tests::close_body())
            })
        });
        assert!(matches!(result, Err(PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert_eq!(audit.sub("log").unwrap().names().unwrap().len(), count);
        assert!(audit.sub("stage").unwrap().names().unwrap().len() >= 2);
        assert!(
            live.call().permit().is_ok(),
            "a cancelled call does not cancel its next sibling"
        );
        assert!(
            live.call()
                .within(|| log::publish(
                    &audit,
                    "close_requested",
                    |_| Ok(log::tests::close_body())
                ))
                .is_ok()
        );
        assert_eq!(audit.sub("log").unwrap().names().unwrap().len(), count + 1);
        live.stop();
        assert!(live.call().permit().is_err());
        let fresh = Gate::new(Instant::now() + Duration::from_secs(60));
        assert!(fresh.permit().is_ok());
        std::fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn deadline_is_checked_at_publication_permission() {
        let gate = Gate::new(Instant::now() - Duration::from_millis(1));
        assert!(gate.permit().is_err());
        assert!(current().is_none());
        gate.within(|| assert!(current().unwrap().permit().is_err()));
        assert!(current().is_none());
    }
}
