//! A placement's publication gate (INTERFACE 6.8; the development runtime's
//! contract). A stop closes it: a stop signal on either runtime, and on the
//! development runtime also the owner's own stop. A call's cancellation closes
//! that call's gate, and a development runtime placement's deadline closes its
//! gate too. A call's mutation passes the gate to the log's link operation
//! (`log::publish_under`), and the permit holds the gate's locks across the
//! link and its directory sync. So a stop is ordered against publication,
//! including a handler that was already executing, and waits for a link that
//! has begun. Candidate payloads and stage files can remain unreferenced. A
//! placement owner's own records are never published under a gate.
//!
//! The development runtime also checks the gate when a call starts. The
//! Messages adapter gates only publications, so reads continue until the
//! placement ends.
use crate::archive::Fail;
use crate::log::{self, PublicationGate};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::Instant;

#[derive(Clone)]
pub struct Gate {
    stopped: Arc<Mutex<bool>>,
    cancelled: Arc<Mutex<bool>>,
    deadline: Option<Instant>,
}
pub struct Permit<'a> {
    _stop: MutexGuard<'a, bool>,
    _cancel: MutexGuard<'a, bool>,
}
impl Gate {
    /// A development runtime placement's gate, which its deadline closes too.
    pub fn new(deadline: Instant) -> Self {
        Self::closing_at(Some(deadline))
    }
    /// A Messages placement's gate, which only a stop closes.
    pub fn without_deadline() -> Self {
        Self::closing_at(None)
    }
    fn closing_at(deadline: Option<Instant>) -> Self {
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
        if *stop || *cancel || self.deadline.is_some_and(|d| Instant::now() >= d) {
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
}

impl PublicationGate for Gate {
    fn permit(&self) -> Result<log::Permit<'_>, Fail> {
        Gate::permit(self).map(|p| Box::new(p) as log::Permit<'_>)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::archive::Audit;
    use crate::log::PubErr;
    use std::sync::mpsc;
    use std::time::Duration;

    #[test]
    fn publication_control_late_stop_and_fresh_invariance() {
        let (path, audit) = log::tests::scratch_audit();
        let live = Gate::new(Instant::now() + Duration::from_secs(60));
        // A positive publication through the actual log path establishes that
        // the archive and body builder can publish, before changing only stop.
        assert!(
            log::publish_under(&audit, "reference", Some(&live), |_| Ok(
                log::tests::reference_body()
            ))
            .is_ok()
        );
        let count = audit.sub("log").unwrap().names().unwrap().len();
        let call = live.call();
        let result = log::publish_under(&audit, "close_requested", Some(&call), |_| {
            // The handler already ran and built a body. Cancellation wins
            // before linking; the stage file is an independent witness.
            call.cancel();
            Ok(log::tests::close_body())
        });
        assert!(matches!(result, Err(PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert_eq!(audit.sub("log").unwrap().names().unwrap().len(), count);
        assert!(audit.sub("stage").unwrap().names().unwrap().len() >= 2);
        assert!(
            live.call().permit().is_ok(),
            "a cancelled call does not cancel its next sibling"
        );
        assert!(
            log::publish_under(&audit, "close_requested", Some(&live.call()), |_| Ok(
                log::tests::close_body()
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
        let (path, audit) = log::tests::scratch_audit();
        // Without a deadline only a stop closes the gate.
        let messages = Gate::without_deadline();
        assert!(messages.permit().is_ok());
        messages.stop();
        assert_eq!(messages.permit().err().unwrap().reason, "placement_stopped");
        let gate = Gate::new(Instant::now() - Duration::from_millis(1));
        assert!(gate.permit().is_err());
        let late = log::publish_under(&audit, "reference", Some(&gate), |_| {
            Ok(log::tests::reference_body())
        });
        assert!(matches!(late, Err(PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert!(log::read(&audit).recs.is_empty());
        // The same record links when published without a gate, as a
        // placement owner's own records are.
        assert!(log::publish(&audit, "reference", |_| Ok(log::tests::reference_body())).is_ok());
        assert_eq!(log::read(&audit).recs.len(), 1);
        std::fs::remove_dir_all(path).unwrap();
    }

    /// The refusal a mutation's precondition gives once close is recorded.
    fn close_refusal(state: &log::LogState) -> Option<Fail> {
        let close = state.close_requested()?;
        Some(
            Fail::refused("authoring_ended", "Close won publication.").data(
                crate::json::J::obj()
                    .with("ended_by", "close")
                    .with("close_requested_at", close.at.as_str())
                    .with("seal", state.seal_observation_j()),
            ),
        )
    }

    #[test]
    fn durable_close_precondition_wins_over_stopped_or_cancelled_publication() {
        for close_wins in [false, true] {
            for cancel in [false, true] {
                let (path, audit) = log::tests::scratch_audit();
                let gate = Gate::new(Instant::now() + Duration::from_secs(60));
                log::publish_under(&audit, "reference", Some(&gate), |_| {
                    Ok(log::tests::reference_body())
                })
                .ok()
                .expect("firing control publishes through the same gate");
                let call = gate.call();
                let mut checks = 0;
                let result = log::publish_under(&audit, "entry", Some(&call), |state| {
                    checks += 1;
                    if let Some(refusal) = close_refusal(state) {
                        return Err(refusal);
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

    /// A gate that closed before the publication began does not hide a close
    /// that is already durable: the precondition runs first and refuses
    /// `authoring_ended`, and nothing is staged for the link.
    #[test]
    fn a_close_recorded_before_publication_outranks_a_closed_gate() {
        for cancel in [false, true] {
            let (path, audit) = log::tests::scratch_audit();
            let gate = Gate::new(Instant::now() + Duration::from_secs(60));
            log::publish_under(&audit, "reference", Some(&gate), |_| {
                Ok(log::tests::reference_body())
            })
            .ok()
            .expect("firing control publishes through the same gate");
            log::publish(&audit, "close_requested", |_| Ok(log::tests::close_body()))
                .ok()
                .expect("the manager's close is not gated");
            let stages = audit.sub("stage").unwrap().names().unwrap().len();
            let call = gate.call();
            if cancel {
                call.cancel();
            } else {
                gate.stop();
            }
            let mut checks = 0;
            let result = log::publish_under(&audit, "entry", Some(&call), |state| {
                checks += 1;
                match close_refusal(state) {
                    Some(refusal) => Err(refusal),
                    None => Ok(crate::json::J::obj()),
                }
            });
            let Err(PubErr::Refused(refusal)) = result else {
                panic!("publication must refuse")
            };
            assert_eq!(refusal.reason, "authoring_ended", "cancel: {cancel}");
            assert_eq!(checks, 1);
            assert_eq!(log::read(&audit).recs.len(), 2);
            assert_eq!(audit.sub("stage").unwrap().names().unwrap().len(), stages);
            std::fs::remove_dir_all(path).unwrap();
        }
    }

    /// A stop issued after a publication's permit and before its link waits
    /// for the link and the directory sync: the record links, and only then
    /// does the stop take effect. The interposed gate takes the real permit,
    /// has another thread issue the stop, and notes on release whether the
    /// record was already linked.
    #[test]
    fn a_stop_issued_after_the_permit_waits_for_the_link() {
        struct Interposed<'a> {
            gate: &'a Gate,
            audit: &'a Audit,
            issue: mpsc::Sender<()>,
            issuing: mpsc::Receiver<()>,
            at_release: &'a Mutex<Option<usize>>,
        }
        struct Release<'a> {
            _held: Permit<'a>,
            audit: &'a Audit,
            at_release: &'a Mutex<Option<usize>>,
        }
        impl Drop for Release<'_> {
            fn drop(&mut self) {
                // Runs before the held permit is released.
                *self.at_release.lock().unwrap() = Some(log::read(self.audit).recs.len());
            }
        }
        impl PublicationGate for Interposed<'_> {
            fn permit(&self) -> Result<log::Permit<'_>, Fail> {
                let held = self.gate.permit()?;
                self.issue.send(()).unwrap();
                self.issuing.recv().unwrap();
                // Let the stopper reach the gate's lock before the link.
                std::thread::sleep(Duration::from_millis(50));
                Ok(Box::new(Release {
                    _held: held,
                    audit: self.audit,
                    at_release: self.at_release,
                }))
            }
        }
        let (path, audit) = log::tests::scratch_audit();
        let gate = Gate::new(Instant::now() + Duration::from_secs(60));
        log::publish_under(&audit, "reference", Some(&gate), |_| {
            Ok(log::tests::reference_body())
        })
        .ok()
        .expect("firing control publishes through the same gate");
        let count = log::read(&audit).recs.len();
        let at_release = Mutex::new(None);
        let (issue, issue_rx) = mpsc::channel();
        let (issuing_tx, issuing) = mpsc::channel();
        let (linked, after_stop) = std::thread::scope(|scope| {
            let stopper = scope.spawn({
                let (gate, audit) = (&gate, &audit);
                move || {
                    issue_rx.recv().unwrap();
                    issuing_tx.send(()).unwrap();
                    gate.stop();
                    log::read(audit).recs.len()
                }
            });
            let interposed = Interposed {
                gate: &gate,
                audit: &audit,
                issue,
                issuing,
                at_release: &at_release,
            };
            let linked = log::publish_under(&audit, "close_requested", Some(&interposed), |_| {
                Ok(log::tests::close_body())
            })
            .is_ok();
            (linked, stopper.join().unwrap())
        });
        assert!(linked, "a publication holding its permit links");
        assert_eq!(
            *at_release.lock().unwrap(),
            Some(count + 1),
            "the permit is held until the record is linked"
        );
        assert_eq!(after_stop, count + 1, "the stop took effect after the link");
        assert_eq!(gate.permit().err().unwrap().reason, "placement_stopped");
        let later = log::publish_under(&audit, "close_requested", Some(&gate), |_| {
            Ok(log::tests::close_body())
        });
        assert!(matches!(later, Err(PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert_eq!(log::read(&audit).recs.len(), count + 1);
        std::fs::remove_dir_all(path).unwrap();
    }
}
