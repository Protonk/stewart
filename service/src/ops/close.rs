//! `stewart close REF [...]` for references that never launched (INTERFACE
//! 5.8 steps 1–4). Close is one algorithm; repeating it resumes from the
//! recorded state. Before launch it creates no answer, seal or confirmation:
//! it records the end of the reference, accounting for any incomplete intake.
//! The after-launch steps (stop, seal, deliver, confirm, surrender) belong to
//! the run and delivery steps of the build and are not reachable here.

use super::headline;
use crate::archive::{self, Audit, Fail};
use crate::json::{self, J};
use crate::log::{self, Body, PubErr};
use crate::reply::{Cause, Next, Reply};
use crate::util;
use std::time::{Duration, Instant};

const OP: &str = "close";
/// How long close waits for an intake that holds the lock (Appendix B).
const INTAKE_WAIT: Duration = Duration::from_secs(10);

fn eff(closure: &'static str) -> Vec<(&'static str, &'static str)> {
    vec![
        ("run", "not_started"),
        ("seal", "none"),
        ("delivery", "none"),
        ("closure", closure),
    ]
}

fn eff_unknown(closure: &'static str) -> Vec<(&'static str, &'static str)> {
    vec![
        ("run", "unknown"),
        ("seal", "unknown"),
        ("delivery", "unknown"),
        ("closure", closure),
    ]
}

pub struct Flags {
    pub confirm: Option<String>,
    pub surrender: Vec<String>,
    pub destination: Option<String>,
}

pub fn run(reference: &str, flags: &Flags) -> Reply {
    let mut audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, eff_unknown("unknown")),
    };
    if let Err(f) = audit.require_mutation() {
        return f.into_reply(OP, eff_unknown("unknown"));
    }
    let mut reply = close(&audit, flags);
    audit.diagnose(
        &mut reply,
        J::obj().with("reference", audit.reference.as_str()),
    );
    reply
}

fn closed_reply(rec: &log::LogRec, already: bool, state: &log::LogState) -> Reply {
    let (before, accepted) = match rec.body {
        Body::Closed {
            before_launch,
            accepted,
        } => (before_launch, accepted),
        _ => (true, false),
    };
    let data = J::obj()
        .with("closure", "complete")
        .with("already_closed", already)
        .with("before_launch", before)
        .with("accepted", accepted)
        .with("closed_at", rec.at.as_str())
        .with("headline", headline(state).to_j());
    // A closed audit owes nothing further, so no next call is offered; the
    // receipt stays readable through the status reply's receipt line.
    Reply::completed(OP, eff("complete"), data)
}

fn unfinished(
    audit: &Audit,
    reason: &'static str,
    closure: &'static str,
    extra: J,
    state: &log::LogState,
) -> Reply {
    let mut data = J::obj()
        .with("closure", "unfinished")
        .with("unfinished_reason", reason)
        .with("headline", headline(state).to_j());
    if let J::Obj(m) = extra {
        if let J::Obj(d) = &mut data {
            d.extend(m);
        }
    }
    let mut r = Reply::completed(OP, eff(closure), data);
    r.next.push(Next::new(
        audit.argv(&["close", &audit.reference]),
        "Continue the close; it resumes from the recorded state.",
    ));
    r.next.push(Next::new(
        audit.argv(&["status", &audit.reference]),
        "See the evidence for where the close stands.",
    ));
    r
}

fn close(audit: &Audit, flags: &Flags) -> Reply {
    let state = log::read(audit);
    // Step 1: a damaged log gets nothing published, so never `closed`.
    if state.damaged() {
        let closure = if state.close_requested().is_some() {
            "unfinished"
        } else {
            "unknown"
        };
        let mut r = Reply::completed(
            OP,
            eff_unknown(closure),
            J::obj()
                .with("closure", "unfinished")
                .with("unfinished_reason", "log_damaged")
                .with("bad_records", state.bad_j())
                .with("headline", headline(&state).to_j()),
        );
        r.retained.push(audit.abs("log"));
        r.next.push(Next::new(
            audit.argv(&["status", &audit.reference]),
            "Status reports what the readable records establish; Stewart never repairs the log.",
        ));
        return r;
    }
    // Step 2: already closed.
    if let Some(c) = state.closed() {
        return closed_reply(c, true, &state);
    }
    if state.launched() {
        // Not reachable in this build: no run can start, so no run_started exists.
        return Fail::failed(
            "record_failed",
            "This audit was launched; closing a launched audit is not supported by this build.",
        )
        .into_reply(OP, eff_unknown("unknown"));
    }
    // The after-launch flags have nothing to act on before launch.
    if flags.destination.is_some() {
        return Fail::refused(
            "destination_not_replaceable",
            "--destination replaces only a destination whose delivery attempt was partial or failed; this reference never launched, so nothing is owed for delivery.",
        )
        .next(Next::new(audit.argv(&["close", &audit.reference]), "Close without --destination."))
        .into_reply(OP, eff(if state.close_requested().is_some() { "unfinished" } else { "none" }));
    }
    if flags.confirm.is_some() || !flags.surrender.is_empty() {
        return Fail::refused(
            "confirmation_mismatch",
            "This reference never launched, so it has no delivery to confirm and no loss to surrender; close before launch needs neither.",
        )
        .next(Next::new(audit.argv(&["close", &audit.reference]), "Close without --confirm or --surrender."))
        .into_reply(OP, eff(if state.close_requested().is_some() { "unfinished" } else { "none" }));
    }
    // Step 3: record the request. From here no intake may be accepted.
    if state.close_requested().is_none() {
        let flags_j = J::obj()
            .with("confirm", flags.confirm.clone())
            .with("surrender", json::strs(&flags.surrender))
            .with("destination", flags.destination.clone());
        let p = log::publish(audit, "close_requested", |st| {
            if st.close_requested().is_some() {
                // Another close recorded it first; that request stands.
                return Err(Fail::refused("already_requested", ""));
            }
            Ok(J::obj()
                .with("flags", flags_j.clone())
                .with("observations", archive::observations()))
        });
        match p {
            Ok(_) | Err(PubErr::Refused(_)) => {}
            Err(PubErr::Damaged(st)) => {
                return unfinished(
                    audit,
                    "log_damaged",
                    "unknown",
                    J::obj().with("bad_records", st.bad_j()),
                    &st,
                );
            }
            Err(PubErr::NotPublished(c)) => {
                return Fail::failed(
                    "record_failed",
                    format!(
                        "The close request could not be recorded ({}: {}); nothing changed.",
                        c.operation, c.error
                    ),
                )
                .cause(c)
                .next(Next::new(
                    audit.argv(&["close", &audit.reference]),
                    "Close again once the archive is writable.",
                ))
                .into_reply(OP, eff("none"));
            }
            Err(PubErr::Uncertain { cause, .. }) => {
                return Fail::failed(
                    "record_failed",
                    "The close request was linked, but Stewart could not confirm it is durable.",
                )
                .cause(cause)
                .next(Next::new(
                    audit.argv(&["status", &audit.reference]),
                    "Status reports whether close was requested.",
                ))
                .next(Next::new(
                    audit.argv(&["close", &audit.reference]),
                    "Repeating close resumes from the recorded state.",
                ))
                .into_reply(OP, eff_unknown("unknown"));
            }
        }
    }
    // Step 4: before launch. Wait for an intake holding the lock to end.
    let start = Instant::now();
    let mut announced = false;
    let lock = loop {
        match audit.try_lock() {
            Ok(Some(f)) => break f,
            Ok(None) => {
                if start.elapsed() >= INTAKE_WAIT {
                    let st = log::read(audit);
                    let open = st.open_intake();
                    let reason = if open.is_some() {
                        "intake_still_running"
                    } else {
                        "close_in_progress"
                    };
                    let extra = J::obj().with("intake", open);
                    return unfinished(audit, reason, "unfinished", extra, &st);
                }
                if !announced {
                    eprintln!(
                        "stewart close: waiting up to 10 s for the process holding the active lock to finish"
                    );
                    announced = true;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => {
                return Fail::failed(
                    "record_failed",
                    format!(
                        "The active lock cannot be tested or taken: {}.",
                        util::describe(&e)
                    ),
                )
                .cause(Cause::io("lock active.lock", &e).at(audit.abs(archive::LOCK_FILE)))
                .next(Next::new(
                    audit.argv(&["close", &audit.reference]),
                    "Close again; it resumes from the recorded state.",
                ))
                .into_reply(OP, eff("unfinished"));
            }
        }
    };
    // Reconcile under the free lock: an intake planned without an outcome
    // belongs to a process that is gone.
    let st = log::read(audit);
    if let Some(gone) = st.open_intake() {
        let r = log::publish(audit, "intake_ended", |s| {
            if !s
                .intakes()
                .iter()
                .any(|i| i.attempt == gone && i.ended.is_none())
            {
                return Err(Fail::refused("already_ended", ""));
            }
            Ok(J::obj()
                .with("attempt", gone)
                .with("outcome", "process_gone")
                .with("recorded_by", "close")
                .with("message", "The intake's process ended without recording an outcome; reconciled by close under a free lock.")
                .with("cause", J::Null)
                .with("changes", J::Null))
        });
        if let Err(e) = r {
            if !matches!(e, PubErr::Refused(_)) {
                drop(lock);
                return Fail::failed(
                    "record_failed",
                    format!(
                        "Intake {gone} could not be reconciled ({}); close is unfinished.",
                        e.describe()
                    ),
                )
                .next(Next::new(
                    audit.argv(&["close", &audit.reference]),
                    "Close again; it resumes from the recorded state.",
                ))
                .into_reply(OP, eff("unfinished"));
            }
        }
    }
    if let Err(e) = crate::fault!("close.before_closed_link") {
        return Fail::failed(
            "record_failed",
            format!(
                "The closing record could not be published ({}); close is unfinished.",
                util::errno_name(&e)
            ),
        )
        .cause(Cause::io("publish closed", &e))
        .next(Next::new(
            audit.argv(&["close", &audit.reference]),
            "Close again; it resumes from the recorded state.",
        ))
        .into_reply(OP, eff("unfinished"));
    }
    let p = log::publish(audit, "closed", |s| {
        if s.close_requested().is_none() {
            return Err(Fail::failed("record_failed", "close_requested is missing"));
        }
        if s.closed().is_some() {
            return Err(Fail::refused("already_closed", ""));
        }
        if s.launched() {
            return Err(Fail::failed("record_failed", "a run started"));
        }
        if let Some(open) = s.open_intake() {
            return Err(Fail::failed(
                "record_failed",
                format!("intake {open} has no outcome"),
            ));
        }
        let accepted = s.accepted().is_some();
        Ok(J::obj()
            .with("before_launch", true)
            .with("accepted", accepted)
            .with(
                "outcome",
                if accepted {
                    "closed_after_acceptance_before_launch"
                } else {
                    "closed_without_acceptance"
                },
            ))
    });
    drop(lock);
    match p {
        Ok(_) | Err(PubErr::Refused(_)) => {
            let st = log::read(audit);
            match st.closed() {
                Some(c) => closed_reply(c, false, &st),
                None => unfinished(audit, "close_in_progress", "unknown", J::obj(), &st),
            }
        }
        Err(PubErr::Damaged(st)) => unfinished(
            audit,
            "log_damaged",
            "unfinished",
            J::obj().with("bad_records", st.bad_j()),
            &st,
        ),
        Err(PubErr::NotPublished(c)) => Fail::failed(
            "record_failed",
            format!(
                "The closing record could not be published ({}: {}); close is unfinished.",
                c.operation, c.error
            ),
        )
        .cause(c)
        .next(Next::new(
            audit.argv(&["close", &audit.reference]),
            "Close again; it resumes from the recorded state.",
        ))
        .into_reply(OP, eff("unfinished")),
        Err(PubErr::Uncertain { cause, .. }) => Fail::failed(
            "record_failed",
            "The closing record was linked, but Stewart could not confirm it is durable.",
        )
        .cause(cause)
        .next(Next::new(
            audit.argv(&["status", &audit.reference]),
            "Status reports whether the reference is closed.",
        ))
        .next(Next::new(
            audit.argv(&["close", &audit.reference]),
            "Repeating close returns the recorded outcome.",
        ))
        .into_reply(OP, eff_unknown("unknown")),
    }
}
