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

    #[test]
    fn durable_close_precondition_wins_over_stopped_or_cancelled_publication() {
        for close_wins in [false, true] {
            for cancel in [false, true] {
                let (path, audit) = log::tests::scratch_audit();
                let gate = Gate::new(Instant::now() + Duration::from_secs(60));
                gate.within(|| {
                    log::publish(&audit, "reference", |_| Ok(log::tests::reference_body()))
                })
                .ok()
                .expect("firing control publishes through the same gate");
                let call = gate.call();
                let mut checks = 0;
                let result = call.within(|| {
                    log::publish(&audit, "entry", |state| {
                        checks += 1;
                        if let Some(close) = state.close_requested() {
                            return Err(Fail::refused("authoring_ended", "Close won publication.")
                                .data(
                                    crate::json::J::obj()
                                        .with("ended_by", "close")
                                        .with("close_requested_at", close.at.as_str())
                                        .with("seal", state.seal_observation_j()),
                                ));
                        }
                        if close_wins {
                            // The independent manager thread has no runtime gate.
                            // Its record wins after this mutation checked state.
                            std::thread::scope(|scope| {
                                scope
                                    .spawn(|| {
                                        log::publish(&audit, "close_requested", |_| {
                                            Ok(log::tests::close_body())
                                        })
                                    })
                                    .join()
                                    .unwrap()
                                    .ok()
                                    .expect("close wins the staged candidate's slot");
                            });
                        }
                        if cancel {
                            call.cancel();
                        } else {
                            gate.stop();
                        }
                        Ok(crate::json::J::obj())
                    })
                });
                let Err(PubErr::Refused(refusal)) = result else {
                    panic!("publication must refuse")
                };
                assert_eq!(
                    refusal.reason,
                    if close_wins {
                        "authoring_ended"
                    } else {
                        "placement_stopped"
                    }
                );
                assert_eq!(checks, if close_wins { 2 } else { 1 });
                let state = log::read(&audit);
                assert_eq!(state.recs.len(), if close_wins { 2 } else { 1 });
                assert!(!state.damaged());
                assert!(state.seal().is_none());
                if close_wins {
                    let data = refusal.data.unwrap();
                    assert_eq!(
                        data.get("ended_by"),
                        Some(&crate::json::J::Str("close".into()))
                    );
                    assert_eq!(
                        data.get("close_requested_at"),
                        Some(&crate::json::J::Str(
                            state.close_requested().unwrap().at.clone()
                        ))
                    );
                    assert_eq!(data.get("seal"), Some(&state.seal_observation_j()));
                }
                std::fs::remove_dir_all(path).unwrap();
            }
        }
    }
}
