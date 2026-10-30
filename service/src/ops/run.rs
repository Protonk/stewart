//! `stewart run REF` (INTERFACE 5.7, section 6): place the auditor into the
//! arrangement in the foreground and exit when the placement ends.
//!
//! This build has no run adapter. `run` resolves the reference and checks
//! the writer as every mutation does, then fails without recording anything:
//! it publishes no `run_started`, so the audit's state is unchanged and
//! nothing needs reconciling.

use crate::archive::{Audit, Fail};
use crate::json::J;
use crate::log;
use crate::reply::{Next, Reply};

const OP: &str = "run";

/// How often the run's watcher checks whether the log's next record is a
/// `close_requested` (6.8).
pub const WATCH_INTERVAL: std::time::Duration = std::time::Duration::from_millis(250);

/// Effects of a run that started nothing: the recorded facts as they stand.
fn eff(state: Option<&log::LogState>) -> Vec<(&'static str, &'static str)> {
    let (run, seal) = match state {
        Some(s) if !s.damaged() => (
            if !s.launched() {
                "not_started"
            } else if s.open_placement().is_none() {
                "ended"
            } else {
                "unknown"
            },
            if s.seal().is_some() {
                "existing"
            } else {
                "none"
            },
        ),
        _ => ("unknown", "unknown"),
    };
    vec![
        ("run", run),
        ("answer", "unchanged"),
        ("seal", seal),
        ("delivery", "none"),
    ]
}

pub fn run(reference: &str) -> Reply {
    let mut audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, eff(None)),
    };
    if let Err(f) = audit.require_mutation() {
        return f.into_reply(OP, eff(None));
    }
    let state = log::read(&audit);
    let mut reply = Fail::failed(
        "not_implemented",
        "This build of Stewart has no run adapter, so it cannot place the auditor; nothing was started or recorded.",
    )
    .next(Next::new(
        audit.argv(&["status", &audit.reference]),
        "See where the audit stands.",
    ))
    .next(Next::new(
        audit.argv(&["close", &audit.reference]),
        "End the commission without running it.",
    ))
    .into_reply(OP, eff(Some(&state)));
    audit.diagnose(
        &mut reply,
        J::obj().with("reference", audit.reference.as_str()),
    );
    reply
}
