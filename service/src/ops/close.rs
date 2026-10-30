//! `stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination
//! DIR]` (INTERFACE 5.8). Close is available in every state and is one
//! algorithm: repeating it resumes from the recorded state.
//!
//! 1. A damaged log gets nothing published, so never `closed`.
//! 2. An existing `closed` is returned as recorded; options are not evaluated.
//! 3. Options are checked against the records as they stand, before anything
//!    is published.
//! 4. `close_requested` is published once, recording the first call's
//!    options. From that log position authoring ends.
//! 5. Before launch, close waits for an intake, reconciles, and records the
//!    end. No answer, seal or confirmation is created.
//! 6. After launch: stop (wait for a held run to observe the request), lock
//!    and reconcile, seal (an existing seal stands; otherwise close seals the
//!    selection current at its request with manager attribution), deliver
//!    or present a verified delivery, and complete only on a confirmation or
//!    on a delivery that verified before close was first requested.
//!
//! Close never removes anything: not at a destination, not in the archive
//! and not in the preparation folder. A seal alone never counts as stopped
//! execution, and a copy existing now never turns a repeat into confirmation.

use super::{accepted_settings, headline, seal_j};
use crate::answer::{self, PrepareError, Preparer, SealError, Sealer};
use crate::archive::{self, Audit, Fail};
use crate::bodies::{
    CloseFlags, CloseRequested, Closed, ClosedAfterLaunch, ClosedDelivery, ClosedSeal,
    DeliveryEnded, NoticeReport, RunEnded, Surrendered,
};
use crate::delivery::{self, AttemptView, By, Destination, Request};
use crate::json::J;
use crate::log::{self, LogState, PubErr};
use crate::reply::{Cause, Next, Outcome, Reply};
use crate::util;
use std::cell::{Cell, RefCell};
use std::time::{Duration, Instant};

const OP: &str = "close";
/// How long close waits for an intake that holds the lock (Appendix B).
const INTAKE_WAIT: Duration = Duration::from_secs(10);
/// How long close waits for a run to observe `close_requested` and exit.
pub const RUN_WAIT: Duration = Duration::from_secs(30);
/// How often close looks at the lock while it waits.
const POLL: Duration = Duration::from_millis(50);

type Effects = Vec<(&'static str, &'static str)>;

fn eff(
    run: &'static str,
    seal: &'static str,
    delivery: &'static str,
    closure: &'static str,
) -> Effects {
    vec![
        ("run", run),
        ("seal", seal),
        ("delivery", delivery),
        ("closure", closure),
    ]
}

fn eff_before(closure: &'static str) -> Effects {
    eff("not_started", "none", "none", closure)
}

fn eff_unknown(closure: &'static str) -> Effects {
    eff("unknown", "unknown", "unknown", closure)
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
    let ctx = Ctx::default();
    let mut reply = close(&audit, flags, &ctx);
    ctx.account(&audit, &mut reply);
    audit.diagnose(
        &mut reply,
        J::obj().with("reference", audit.reference.as_str()),
    );
    reply
}

/// The archive directories whose new entries close attributes to itself:
/// a preparation of the answer and a seal manifest.
const CREATED_DIRS: [&str; 2] = ["prepared", "seal"];

/// What one close invocation did that a failed or refused reply must
/// account for: whether it published `close_requested` (1.4) and which
/// locations it created and kept (1.3).
#[derive(Default)]
struct Ctx {
    /// This invocation published `close_requested`.
    requested: Cell<bool>,
    /// The entries of `CREATED_DIRS` when this close took the active lock.
    /// Under the lock no run or other close adds to them, so an entry there
    /// afterwards was created by this invocation.
    before: RefCell<Option<[Vec<String>; 2]>>,
    /// The delivery plans and packages this invocation created.
    delivered: RefCell<Vec<String>>,
}

fn entries(audit: &Audit, dir: &str) -> Vec<String> {
    audit
        .dir
        .open_dir(dir)
        .and_then(|d| d.names())
        .unwrap_or_default()
}

impl Ctx {
    /// Note the entries that exist when close takes the active lock.
    fn snapshot(&self, audit: &Audit) {
        *self.before.borrow_mut() = Some(CREATED_DIRS.map(|d| entries(audit, d)));
    }

    /// Every location this invocation created, as absolute paths.
    fn created(&self, audit: &Audit) -> Vec<String> {
        let mut out = Vec::new();
        if let Some(before) = &*self.before.borrow() {
            for (dir, had) in CREATED_DIRS.iter().zip(before) {
                for n in entries(audit, dir) {
                    if !had.contains(&n) {
                        out.push(audit.abs(&format!("{dir}/{n}")));
                    }
                }
            }
        }
        out.extend(self.delivered.borrow().iter().cloned());
        out
    }

    /// Account for this invocation in a failed or refused reply: closure is
    /// `requested` when it published `close_requested` and failed, wherever
    /// the failure happened (an `unknown` closure stays unknown), and
    /// `retained` lists every location it created, ahead of the diagnostic
    /// that `diagnose` adds.
    fn account(&self, audit: &Audit, reply: &mut Reply) {
        if reply.outcome == Outcome::Completed {
            return;
        }
        if reply.outcome == Outcome::Failed
            && self.requested.get()
            && reply.effect("closure") != Some("unknown")
        {
            reply.set_effect("closure", "requested");
        }
        for p in self.created(audit) {
            if !reply.retained.contains(&p) {
                reply.retained.push(p);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Facts and presentation shared by the paths.

/// The `effects.delivery` value of an attempt's recorded outcome. A
/// `name_taken` attempt is a failed placement of the package; an attempt
/// without a recorded outcome is unknown.
pub(crate) fn delivery_value(outcome: Option<&str>) -> &'static str {
    match outcome {
        Some("verified") => "verified",
        Some("verified_with_losses") => "verified_with_losses",
        Some("partial") => "partial",
        Some("failed") | Some("name_taken") => "failed",
        _ => "unknown",
    }
}

/// The presented attempt's outcome, else the newest attempt's, else none.
fn delivery_eff(state: &LogState, presented: Option<u64>) -> &'static str {
    let ds = state.deliveries();
    let d = presented
        .and_then(|a| ds.iter().find(|d| d.attempt == a))
        .or(ds.last());
    match d {
        None => "none",
        Some(d) => delivery_value(d.outcome()),
    }
}

fn seal_fact(state: &LogState) -> &'static str {
    if state.seal().is_some() {
        "existing"
    } else {
        "none"
    }
}

/// Whether a run still holds the audit: a placement without `run_ended`
/// and the lock held. A free lock with such a placement means its process
/// is gone, so no placement is live (1.4).
fn run_fact(audit: &Audit, state: &LogState) -> &'static str {
    if !state.launched() {
        return "not_started";
    }
    if state.open_placement().is_none() {
        return "ended";
    }
    match audit.lock_held() {
        Ok(true) => "still_held",
        Ok(false) => "ended",
        Err(_) => "unknown",
    }
}

/// The recorded facts, for a refusal that published nothing.
fn facts_eff(audit: &Audit, state: &LogState) -> Effects {
    eff(
        run_fact(audit, state),
        seal_fact(state),
        delivery_eff(state, None),
        if state.close_requested().is_some() {
            "unfinished"
        } else {
            "none"
        },
    )
}

/// `runs` of the close reply: `{count, held, last_ending}`.
fn runs_j(state: &LogState, held: bool) -> J {
    let placements = state.placements();
    J::obj()
        .with("count", placements.len() as u64)
        .with("held", held)
        .with(
            "last_ending",
            placements
                .last()
                .and_then(|p| p.ended.map(|(_, e)| e.ending.as_str())),
        )
}

/// The presented attempt, else the newest attempt, as the run reply shows it.
fn delivery_j(audit: &Audit, state: &LogState, presented: Option<u64>) -> J {
    let ds = state.deliveries();
    let d = presented
        .and_then(|a| ds.iter().find(|d| d.attempt == a))
        .or(ds.last());
    match d {
        Some(d) => delivery::view_of(audit, d).to_j(),
        None => J::Null,
    }
}

/// The confirmation call for an attempt awaiting it: `close --confirm
/// TOKEN`, with `--surrender LOSS` for each of its losses and an
/// explanation naming what each surrender gives up.
pub fn confirm_next(audit: &Audit, token: &str, v: &AttemptView) -> Next {
    let mut args: Vec<&str> = vec!["close", &audit.reference, "--confirm", token];
    for l in &v.losses {
        if let Some(id) = &l.loss {
            args.push("--surrender");
            args.push(id);
        }
    }
    let at = v.location.as_deref().unwrap_or("its destination");
    let mut why = format!("Confirm that this delivered copy at {at} is where you want the return.");
    if !v.losses.is_empty() {
        let given: Vec<String> = v
            .losses
            .iter()
            .map(|l| {
                let what = if l.recorded.role == "entry" {
                    format!("entry {}", l.recorded.member)
                } else {
                    format!("{} ({})", l.recorded.member, l.recorded.role)
                };
                format!(
                    "{} gives up {what}, {} at {}",
                    l.loss.as_deref().unwrap_or(""),
                    l.recorded.failure,
                    l.recorded.stage
                )
            })
            .collect();
        why.push_str(&format!(
            " Each --surrender names an undertaking you give up: {}. The losses stay recorded, and this is not a complete delivery.",
            given.join("; ")
        ));
    }
    Next::new(audit.argv(&args), why)
}

/// Continuing an owed delivery or an interrupted close: `close`, whose
/// explanation offers `--destination DIR` after an incomplete attempt.
pub fn continue_next(audit: &Audit, state: &LogState) -> Next {
    let replaceable = state.seal().is_some()
        && state.newest_verified().is_none()
        && state.deliveries().iter().any(|d| d.incomplete());
    let why = if replaceable {
        "Continue delivering the sealed answer: close makes a fresh attempt at the last destination. If that destination cannot be used, close REF --destination DIR delivers to an existing directory you choose instead."
    } else if state.seal().is_some() {
        "Continue the close: it delivers the sealed answer, or presents a delivery that verified."
    } else {
        "Continue the close; it resumes from the recorded state."
    };
    Next::new(audit.argv(&["close", &audit.reference]), why)
}

fn status_next(audit: &Audit, why: &str) -> Next {
    Next::new(audit.argv(&["status", &audit.reference]), why)
}

fn close_next(audit: &Audit, why: &str) -> Next {
    Next::new(audit.argv(&["close", &audit.reference]), why)
}

// ---------------------------------------------------------------------------
// The algorithm.

fn close(audit: &Audit, flags: &Flags, ctx: &Ctx) -> Reply {
    let state = log::read(audit);
    // Step 1: a damaged log gets nothing published, so never `closed`.
    if state.damaged() {
        return damaged_reply(audit, &state);
    }
    // Step 2: already closed. Options are not evaluated.
    if let Some(c) = state.closed() {
        return closed_reply(audit, &state, c, true, "existing");
    }
    if !state.launched() {
        return before_launch(audit, flags, &state, ctx);
    }
    after_launch(audit, flags, state, ctx)
}

fn damaged_reply(audit: &Audit, state: &LogState) -> Reply {
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
            .with("headline", headline(audit, state).to_j()),
    );
    r.retained.push(audit.abs("log"));
    r.next.push(status_next(
        audit,
        "Status reports what the readable records establish; Stewart never repairs the log.",
    ));
    r
}

/// The reply for a `closed` record, this call's or an earlier one's.
fn closed_reply(
    audit: &Audit,
    state: &LogState,
    rec: &log::LogRec,
    already: bool,
    seal_effect: &'static str,
) -> Reply {
    let body = rec.closed_body();
    let mut data = J::obj()
        .with("closure", "complete")
        .with("already_closed", already)
        .with("before_launch", body.is_none_or(|b| b.before_launch()))
        .with("accepted", body.is_some_and(|b| b.accepted))
        .with("closed_at", rec.at.as_str())
        .with("headline", headline(audit, state).to_j());
    // A closed audit owes nothing further, so no next call is offered; the
    // receipt stays readable through the status reply's receipt line.
    let Some((b, a)) = body.and_then(|b| b.after.as_ref().map(|a| (b, a))) else {
        return Reply::completed(OP, eff_before("complete"), data);
    };
    let (seal, _) = seal_j(audit, state);
    data.push("outcome", b.outcome.as_str());
    data.push("runs", runs_j(state, false));
    data.push("seal", seal);
    data.push(
        "delivery",
        delivery_j(audit, state, Some(a.delivery.attempt)),
    );
    data.push("placement", a.placement.as_str());
    data.push(
        "surrendered",
        J::Arr(a.surrendered.iter().map(|s| s.to_j()).collect()),
    );
    Reply::completed(
        OP,
        eff(
            "ended",
            seal_effect,
            delivery_value(Some(a.delivery.outcome.as_str())),
            "complete",
        ),
        data,
    )
}

/// Publish `close_requested`, recording this call's options. `Ok(true)`
/// when this call published it (noted in `ctx`), `Ok(false)` when another
/// close did first.
fn request_close(audit: &Audit, flags: &Flags, ctx: &Ctx) -> Result<bool, Reply> {
    let body = CloseRequested {
        flags: CloseFlags {
            confirm: flags.confirm.clone(),
            surrender: flags.surrender.clone(),
            destination: flags.destination.clone(),
        },
    };
    let p = log::publish(audit, "close_requested", |st| {
        if st.close_requested().is_some() {
            // Another close recorded it first; that request stands.
            return Err(Fail::refused("already_requested", ""));
        }
        Ok(body.to_j())
    });
    match p {
        Ok(_) => {
            ctx.requested.set(true);
            Ok(true)
        }
        Err(PubErr::Refused(_)) => Ok(false),
        Err(PubErr::Damaged(st)) => Err(damaged_reply(audit, &st)),
        Err(PubErr::NotPublished(c)) => Err(Fail::failed(
            "record_failed",
            format!(
                "The close request could not be recorded ({}: {}); nothing changed.",
                c.operation, c.error
            ),
        )
        .cause(c)
        .next(close_next(
            audit,
            "Close again once the archive is writable.",
        ))
        .into_reply(OP, facts_eff(audit, &log::read(audit)))),
        Err(PubErr::Uncertain { cause, .. }) => Err(Fail::failed(
            "record_failed",
            "The close request was linked, but Stewart could not confirm it is durable.",
        )
        .cause(cause)
        .next(status_next(
            audit,
            "Status reports whether close was requested.",
        ))
        .next(close_next(
            audit,
            "Repeating close resumes from the recorded state.",
        ))
        .into_reply(OP, eff_unknown("unknown"))),
    }
}

/// Map a failed publication of a reconciliation or closing record.
fn publication_failure(audit: &Audit, what: &str, e: PubErr, effects: Effects) -> Reply {
    if let PubErr::Damaged(st) = &e {
        return damaged_reply(audit, st);
    }
    let mut f = Fail::failed(
        "record_failed",
        format!(
            "{what} could not be recorded ({}); close is unfinished.",
            e.describe()
        ),
    )
    .next(close_next(
        audit,
        "Close again; it resumes from the recorded state.",
    ))
    .next(status_next(audit, "See what was recorded."));
    match e {
        PubErr::NotPublished(c) | PubErr::Uncertain { cause: c, .. } => f = f.cause(c),
        PubErr::Refused(r) => f = f.cause(Cause::new(format!("publish {what}"), r.message)),
        PubErr::Damaged(_) => {}
    }
    f.into_reply(OP, effects)
}

// ---------------------------------------------------------------------------
// Before launch.

fn before_launch(audit: &Audit, flags: &Flags, state: &LogState, ctx: &Ctx) -> Reply {
    // Nothing is owed for delivery, so the after-launch options have
    // nothing to act on.
    let closure_now = if state.close_requested().is_some() {
        "unfinished"
    } else {
        "none"
    };
    if flags.destination.is_some() {
        return Fail::refused(
            "destination_not_replaceable",
            "--destination replaces only a destination whose delivery attempt was partial or failed; this reference never launched, so nothing is owed for delivery.",
        )
        .next(close_next(audit, "Close without --destination."))
        .into_reply(OP, eff_before(closure_now));
    }
    if flags.confirm.is_some() || !flags.surrender.is_empty() {
        return Fail::refused(
            "confirmation_mismatch",
            "This reference never launched, so it has no delivery to confirm and no loss to surrender; close before launch needs neither.",
        )
        .next(close_next(audit, "Close without --confirm or --surrender."))
        .into_reply(OP, eff_before(closure_now));
    }
    // Step 4: record the request. From here no intake may be accepted.
    if state.close_requested().is_none() {
        if let Err(r) = request_close(audit, flags, ctx) {
            return r;
        }
        let _ = crate::fault!("close.after_requested");
        // A run that started before the request was published makes this a
        // close after launch.
        let st = log::read(audit);
        if st.damaged() {
            return damaged_reply(audit, &st);
        }
        if st.launched() {
            return after_launch(audit, flags, st, ctx);
        }
    }
    // Step 5: wait for an intake holding the lock to end.
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
                    return unfinished_before(audit, reason, J::obj().with("intake", open), &st);
                }
                if !announced {
                    eprintln!(
                        "stewart close: waiting up to 10 s for the process holding the active lock to finish"
                    );
                    announced = true;
                }
                std::thread::sleep(POLL);
            }
            Err(e) => return lock_failure(audit, &e, eff_before("unfinished")),
        }
    };
    // Reconcile under the free lock: an intake planned without an outcome
    // belongs to a process that is gone.
    if let Err(r) = reconcile(audit, eff_before("unfinished")) {
        return r;
    }
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("empty_return_before_launch") {
        sabotage_empty_return(audit);
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
        .next(close_next(
            audit,
            "Close again; it resumes from the recorded state.",
        ))
        .into_reply(OP, eff_before("unfinished"));
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
        Ok(Closed::before(s.accepted().is_some()).to_j())
    });
    drop(lock);
    match p {
        Ok(_) | Err(PubErr::Refused(_)) => {
            let _ = crate::fault!("close.after_closed_link");
            let st = log::read(audit);
            match st.closed() {
                Some(c) => closed_reply(audit, &st, c, false, "none"),
                None => unfinished_before(
                    audit,
                    "close_in_progress",
                    J::obj().with("intake", J::Null),
                    &st,
                ),
            }
        }
        Err(PubErr::Uncertain { cause, .. }) => Fail::failed(
            "record_failed",
            "The closing record was linked, but Stewart could not confirm it is durable.",
        )
        .cause(cause)
        .next(status_next(
            audit,
            "Status reports whether the reference is closed.",
        ))
        .next(close_next(
            audit,
            "Repeating close returns the recorded outcome.",
        ))
        .into_reply(OP, eff_unknown("unknown")),
        Err(e) => publication_failure(audit, "The closing record", e, eff_before("unfinished")),
    }
}

fn unfinished_before(audit: &Audit, reason: &'static str, extra: J, state: &LogState) -> Reply {
    let mut data = J::obj()
        .with("closure", "unfinished")
        .with("unfinished_reason", reason)
        .with("headline", headline(audit, state).to_j());
    if let (J::Obj(m), J::Obj(d)) = (extra, &mut data) {
        d.extend(m);
    }
    let mut r = Reply::completed(OP, eff_before("unfinished"), data);
    r.next.push(close_next(
        audit,
        "Continue the close; it resumes from the recorded state.",
    ));
    r.next.push(status_next(
        audit,
        "See the evidence for where the close stands.",
    ));
    r
}

fn lock_failure(audit: &Audit, e: &std::io::Error, effects: Effects) -> Reply {
    Fail::failed(
        "record_failed",
        format!(
            "The active lock cannot be tested or taken: {}.",
            util::describe(e)
        ),
    )
    .cause(Cause::io("lock active.lock", e).at(audit.abs(archive::LOCK_FILE)))
    .next(close_next(
        audit,
        "Close again; it resumes from the recorded state.",
    ))
    .into_reply(OP, effects)
}

// ---------------------------------------------------------------------------
// Reconciliation under a free lock: the end of work whose process is gone.

/// The `run_ended` of a placement whose process is gone (6.4, 6.7): usage
/// accounted from its run directory, its notices with what their requests
/// show, and the seal published during it. A run directory that was never
/// created (a crash right after `run_started`) accounts nothing.
pub fn gone_run_ended(audit: &Audit, state: &LogState, p: &log::Placement, by: By) -> RunEnded {
    let account = crate::runs::account(audit, p.run);
    let missing_dir = crate::runs::open(audit, p.run)
        .err()
        .is_some_and(|e| e.raw_os_error() == Some(libc::ENOENT));
    let notices = state
        .notices()
        .iter()
        .filter(|(_, n)| n.run == p.run)
        .map(|(rec, n)| NoticeReport {
            kind: n.kind.clone(),
            record: rec.name(),
            sent: match &account {
                Ok(a) => a.notice_sent(n.request),
                Err(_) if missing_dir => "not_sent",
                Err(_) => "unknown",
            }
            .to_string(),
        })
        .collect();
    let seal = state
        .seal()
        .filter(|(rec, _)| rec.n > p.started.n)
        .map(|(rec, _)| rec.name());
    let (usage, requests, attempts, note) = match &account {
        Ok(a) => (a.usage, a.requests, a.attempts, String::new()),
        Err(why) => (
            Default::default(),
            0,
            0,
            format!(" Its run directory could not be accounted ({why})."),
        ),
    };
    RunEnded {
        run: p.run,
        ending: "interrupted".to_string(),
        cause: Some("process_gone".to_string()),
        recorded_by: by.name().to_string(),
        provider: None,
        requests,
        attempts,
        usage,
        notices,
        seal,
        message: format!(
            "Placement {}'s process ended without recording its ending; reconciled by {} under a free lock.{note}",
            p.run,
            by.name()
        ),
    }
}

/// Record the end of every intake, placement and delivery attempt whose
/// process is gone. The caller holds the active lock.
fn reconcile(audit: &Audit, effects: Effects) -> Result<(), Reply> {
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
        match r {
            Ok(_) | Err(PubErr::Refused(_)) => {}
            Err(e) => {
                return Err(publication_failure(
                    audit,
                    &format!("The end of intake {gone}"),
                    e,
                    effects,
                ));
            }
        }
    }
    let st = log::read(audit);
    if let Some(p) = st.open_placement() {
        let ended = gone_run_ended(audit, &st, &p, By::Close);
        let run = p.run;
        let r = log::publish(audit, "run_ended", |s| {
            if s.open_placement().is_none_or(|o| o.run != run) {
                return Err(Fail::refused("already_ended", ""));
            }
            Ok(ended.to_j())
        });
        match r {
            Ok(_) | Err(PubErr::Refused(_)) => {}
            Err(e) => {
                return Err(publication_failure(
                    audit,
                    &format!("The end of run {run}"),
                    e,
                    effects,
                ));
            }
        }
    }
    let st = log::read(audit);
    let open: Vec<u64> = st
        .deliveries()
        .iter()
        .filter(|d| d.ended.is_none())
        .map(|d| d.attempt)
        .collect();
    let manifest_sha256 = st
        .seal()
        .map(|(_, s)| s.manifest_sha256.clone())
        .unwrap_or_default();
    for attempt in open {
        // What the gone process wrote is not established, so membership of
        // this attempt's result is unknown and no package is claimed.
        let ended = DeliveryEnded {
            attempt,
            outcome: "failed".to_string(),
            recorded_by: "close".to_string(),
            cause: Some(Cause::new("deliver", "process_gone")),
            manifest_sha256: manifest_sha256.clone(),
            package: None,
            members: None,
            losses: None,
        };
        let r = log::publish(audit, "delivery_ended", |s| {
            match s.deliveries().iter().find(|d| d.attempt == attempt) {
                Some(d) if d.ended.is_none() => Ok(ended.to_j()),
                _ => Err(Fail::refused("already_ended", "")),
            }
        });
        match r {
            Ok(_) | Err(PubErr::Refused(_)) => {}
            Err(e) => {
                return Err(publication_failure(
                    audit,
                    &format!("The end of delivery attempt {attempt}"),
                    e,
                    effects,
                ));
            }
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// After launch.

/// An accepted `--confirm`: the attempt it names, its token and the losses
/// surrendered with it.
struct Confirmed {
    attempt: u64,
    token: String,
    surrendered: Vec<Surrendered>,
}

/// Step 3 after launch: check the options against the records as they
/// stand. A refusal publishes nothing.
fn check_options(
    audit: &Audit,
    state: &LogState,
    flags: &Flags,
) -> Result<Option<Confirmed>, Reply> {
    let refuse = |f: Fail| Err(f.into_reply(OP, facts_eff(audit, state)));
    let newest = state.newest_verified();
    let mut confirmed = None;
    if let Some(token) = &flags.confirm {
        let want = newest
            .as_ref()
            .and_then(|d| delivery::confirmation(audit, state, d.attempt));
        let Some(d) = newest
            .as_ref()
            .filter(|_| want.as_deref() == Some(token.as_str()))
        else {
            let mut f = Fail::refused(
                "confirmation_mismatch",
                if newest.is_none() {
                    format!("{token} confirms nothing: no delivery of this audit has verified. A confirmation names the newest verified delivery, so it can only follow one.")
                } else {
                    format!("{token} is not the confirmation of this audit's newest verified delivery, so it cannot confirm its placement.")
                },
            )
            .next(close_next(
                audit,
                "Close without --confirm; it presents the delivery and its confirmation token.",
            ));
            f = f.next(status_next(
                audit,
                "Status shows an outstanding confirmation token.",
            ));
            return refuse(f);
        };
        let v = delivery::view_of(audit, d);
        let ids = v.loss_ids();
        if let Some(bad) = flags.surrender.iter().find(|s| !ids.contains(s)) {
            let mut f = Fail::refused(
                "handle_invalid",
                format!("{bad} is not a loss ID of the confirmed delivery; a surrender names exactly one of its recorded losses."),
            )
            .data(J::obj().with("loss", bad.as_str()))
            .next(close_next(audit, "Close without the confirmation; it presents the delivery, its token and its loss IDs."));
            if !ids.is_empty() {
                f = f.next(confirm_next(audit, token, &v));
            }
            return refuse(f);
        }
        let missing: Vec<&String> = ids
            .iter()
            .filter(|i| !flags.surrender.contains(i))
            .collect();
        if !missing.is_empty() {
            let names: Vec<&str> = missing.iter().map(|s| s.as_str()).collect();
            return refuse(
                Fail::refused(
                    "surrender_required",
                    format!(
                        "The confirmed delivery has losses the call did not name: {}. Confirming its placement does not give them up; name each one you surrender with --surrender.",
                        names.join(", ")
                    ),
                )
                .data(J::obj().with("losses", v.losses_j()))
                .next(close_next(audit, "Close without the confirmation; it presents the delivery again."))
                .next(confirm_next(audit, token, &v)),
            );
        }
        confirmed = Some(Confirmed {
            attempt: d.attempt,
            token: token.clone(),
            surrendered: v
                .losses
                .iter()
                .map(|l| Surrendered {
                    loss: l.loss.clone().unwrap_or_default(),
                    member: l.recorded.member.clone(),
                    role: l.recorded.role.clone(),
                    failure: l.recorded.failure.clone(),
                    stage: l.recorded.stage.clone(),
                })
                .collect(),
        });
    } else if !flags.surrender.is_empty() {
        return refuse(
            Fail::refused(
                "confirmation_mismatch",
                "--surrender is given only with --confirm: a loss is surrendered as part of confirming the delivery that has it.",
            )
            .next(close_next(audit, "Close without --surrender.")),
        );
    }
    if let Some(dir) = &flags.destination {
        if newest.is_some() {
            return refuse(
                Fail::refused(
                    "delivery_already_verified",
                    "A delivery of this audit has verified, so close completes no further copy; close is not a copy service.",
                )
                .next(close_next(audit, "Close without --destination; it presents the verified delivery.")),
            );
        }
        let incomplete =
            state.seal().is_some() && state.deliveries().iter().any(|d| d.incomplete());
        if !incomplete {
            return refuse(
                Fail::refused(
                    "destination_not_replaceable",
                    if state.seal().is_none() {
                        "No answer is sealed yet, so no delivery is owed; --destination replaces only the destination of a delivery that could not complete."
                    } else {
                        "No delivery attempt of the seal is incomplete, so there is no destination to replace; --destination serves only a delivery that could not complete."
                    },
                )
                .next(close_next(audit, "Close without --destination; it delivers to the commissioned destination.")),
            );
        }
        let usable =
            crate::ids::check_absolute(dir).is_ok() && crate::fsx::Dir::open_follow(dir).is_ok();
        if !usable {
            return refuse(
                Fail::refused(
                    "destination_invalid",
                    format!("--destination {dir:?} is not an existing absolute directory; give the absolute path of a directory that exists."),
                )
                .data(J::obj().with("destination", dir.as_str()))
                .next(close_next(audit, "Close without --destination; it retries the last destination.")),
            );
        }
    }
    Ok(confirmed)
}

/// What the stop step found.
enum Stop {
    /// No run holds the lock.
    Free,
    /// A placement without `run_ended` still holds the lock after the wait.
    RunHeld,
    /// Every placement has its ending and the lock is held: another close.
    CloseHeld,
    /// The lock could not be tested.
    Unknown(std::io::Error),
    /// The `seal_as_stopped` sabotage control: a seal taken as stopped
    /// execution while a run holds the lock.
    #[cfg(feature = "sabotage")]
    SealedAsStopped,
}

/// Step 6, stop: wait up to 30 s for a held run to observe
/// `close_requested` and exit. Only the lock, tested without taking it, is
/// evidence of a live holder; elapsed time never is.
///
/// A run publishes `run_ended` and then releases the lock as it exits, so
/// for a moment the lock is held while every placement has its ending. Once
/// close is waiting for a run (`run_open`: a placement had no ending when
/// this close read the log), that moment is the run exiting, and close
/// keeps waiting for the release instead of taking the holder for another
/// close. A held lock with every placement ended, when close waited for no
/// run, is another close.
fn stop(audit: &Audit, run_open: bool) -> Stop {
    let start = Instant::now();
    let mut announced = false;
    let mut waiting_for_run = run_open;
    loop {
        match audit.lock_held() {
            Ok(false) => return Stop::Free,
            Err(e) => return Stop::Unknown(e),
            Ok(true) => {
                let st = log::read(audit);
                let open = st.open_placement().is_some();
                if !open && !waiting_for_run {
                    return Stop::CloseHeld;
                }
                waiting_for_run = true;
                #[cfg(feature = "sabotage")]
                if crate::sabotage!("seal_as_stopped") && st.seal().is_some() {
                    return Stop::SealedAsStopped;
                }
                if start.elapsed() >= RUN_WAIT {
                    // Still held: by the run that has not stopped, or, once
                    // every placement has its ending, by whatever holds it now.
                    return if open { Stop::RunHeld } else { Stop::CloseHeld };
                }
                if !announced {
                    eprintln!(
                        "stewart close: waiting up to 30 s for the run holding the audit to observe the close request and stop"
                    );
                    announced = true;
                }
                std::thread::sleep(POLL);
            }
        }
    }
}

/// An unfinished close after launch.
fn unfinished_after(
    audit: &Audit,
    state: &LogState,
    reason: &'static str,
    effects: Effects,
    presented: Option<u64>,
) -> Reply {
    let held = reason == "run_still_held";
    let holder = if held {
        state
            .open_placement()
            .map(|p| p.start.observations.to_j())
            .unwrap_or(J::Null)
    } else {
        J::Null
    };
    let confirmation = if reason == "awaiting_confirmation" {
        presented.and_then(|a| delivery::confirmation(audit, state, a))
    } else {
        None
    };
    let (seal, _) = seal_j(audit, state);
    let data = J::obj()
        .with("closure", "unfinished")
        .with("unfinished_reason", reason)
        .with("headline", headline(audit, state).to_j())
        .with("runs", runs_j(state, held))
        .with("seal", seal)
        .with("delivery", delivery_j(audit, state, presented))
        .with("confirmation", confirmation.as_deref())
        .with("holder", holder);
    let mut r = Reply::completed(OP, effects, data);
    match reason {
        "awaiting_confirmation" => {
            let v = presented.and_then(|a| delivery::view(audit, state, a));
            if let (Some(token), Some(v)) = (&confirmation, &v) {
                r.next.push(confirm_next(audit, token, v));
            }
            r.next.push(status_next(
                audit,
                "Status keeps showing the delivery and its token until you confirm.",
            ));
        }
        "delivery_incomplete" => r.next.push(continue_next(audit, state)),
        _ => {
            r.next.push(close_next(
                audit,
                "Continue the close; it resumes from the recorded state.",
            ));
            r.next.push(status_next(
                audit,
                "See the evidence for where the close stands.",
            ));
        }
    }
    r
}

fn after_launch(audit: &Audit, flags: &Flags, state: LogState, ctx: &Ctx) -> Reply {
    // Step 3: options, against the records as they stand.
    let confirmed = match check_options(audit, &state, flags) {
        Ok(c) => c,
        Err(r) => return r,
    };
    // Step 4: the request.
    let requested_now = if state.close_requested().is_none() {
        match request_close(audit, flags, ctx) {
            Ok(b) => b,
            Err(r) => return r,
        }
    } else {
        false
    };
    if requested_now {
        let _ = crate::fault!("close.after_requested");
    }
    // The closure a failed reply states from here on. When this invocation
    // published the request, `Ctx::account` reports `requested` instead,
    // wherever the failure happened (1.4).
    let closure_failed = "unfinished";

    // Stop. Whether a placement was open is read from the records as they
    // stood before the request, so a run that ends meanwhile is still one
    // close waits for.
    match stop(audit, state.open_placement().is_some()) {
        Stop::Free => {}
        Stop::RunHeld => {
            let st = log::read(audit);
            return unfinished_after(
                audit,
                &st,
                "run_still_held",
                eff(
                    "still_held",
                    seal_fact(&st),
                    delivery_eff(&st, None),
                    "unfinished",
                ),
                None,
            );
        }
        Stop::CloseHeld => {
            let st = log::read(audit);
            return unfinished_after(
                audit,
                &st,
                "close_in_progress",
                eff(
                    "ended",
                    seal_fact(&st),
                    delivery_eff(&st, None),
                    "unfinished",
                ),
                None,
            );
        }
        #[cfg(feature = "sabotage")]
        Stop::SealedAsStopped => {
            let st = log::read(audit);
            return unfinished_after(
                audit,
                &st,
                "close_in_progress",
                eff(
                    "ended",
                    seal_fact(&st),
                    delivery_eff(&st, None),
                    "unfinished",
                ),
                None,
            );
        }
        Stop::Unknown(e) => {
            return lock_failure(
                audit,
                &e,
                eff("unknown", "unknown", "unknown", closure_failed),
            );
        }
    }

    // Lock, then reconcile under it.
    let lock = match audit.try_lock() {
        Ok(Some(f)) => f,
        Ok(None) => {
            let st = log::read(audit);
            return unfinished_after(
                audit,
                &st,
                "close_in_progress",
                eff(
                    "ended",
                    seal_fact(&st),
                    delivery_eff(&st, None),
                    "unfinished",
                ),
                None,
            );
        }
        Err(e) => {
            return lock_failure(
                audit,
                &e,
                eff("unknown", "unknown", "unknown", closure_failed),
            );
        }
    };
    // From here this close is the only writer: what appears in `prepared/`
    // and `seal/` is its own, for a failed reply's `retained`.
    ctx.snapshot(audit);
    let st = log::read(audit);
    if let Err(r) = reconcile(
        audit,
        eff("unknown", seal_fact(&st), "unknown", closure_failed),
    ) {
        return r;
    }

    // Seal.
    let st = log::read(audit);
    if st.damaged() {
        return damaged_reply(audit, &st);
    }
    let sealed_now = match ensure_seal(audit, &st, closure_failed) {
        Ok(b) => b,
        Err(r) => return r,
    };
    if sealed_now {
        let _ = crate::fault!("close.after_seal");
    }
    let seal_effect = if sealed_now { "recorded" } else { "existing" };

    // Deliver, or present an existing verified delivery.
    let st = log::read(audit);
    let mut made: Vec<u64> = Vec::new();
    let deliver = |request: Request, made: &mut Vec<u64>| -> Result<(), Reply> {
        let d = delivery::deliver(audit, &log::read(audit), &request);
        made.extend(d.attempts.iter().map(|a| a.attempt));
        ctx.delivered.borrow_mut().extend(d.created);
        if let Some(cause) = d.stopped {
            return Err(Fail::failed(
                "record_failed",
                format!(
                    "A delivery record could not be written ({}: {}); the delivery's outcome is not established.",
                    cause.operation, cause.error
                ),
            )
            .cause(cause)
            .next(status_next(audit, "Status reports which delivery records exist."))
            .next(close_next(audit, "Close again; it resumes from the recorded state."))
            .into_reply(OP, eff("ended", seal_effect, "unknown", closure_failed)));
        }
        Ok(())
    };
    let presented: Option<u64> = if let Some(c) = &confirmed {
        Some(c.attempt)
    } else if let Some(v) = st.newest_verified() {
        if delivery::delivery_losses_now_verify(audit, &st, v.attempt) {
            // The archive can now supply what this attempt lost at delivery:
            // a new attempt to its destination replaces it.
            let request = Request {
                by: By::Close,
                destination: Destination::of(v.plan),
                retries_losses_of: Some(v.attempt),
                stop: None,
            };
            if let Err(r) = deliver(request, &mut made) {
                return r;
            }
        }
        log::read(audit).newest_verified().map(|d| d.attempt)
    } else {
        let destination = match &flags.destination {
            Some(p) => Destination::replacement(p.clone()),
            None => match st.deliveries().last() {
                Some(d) => Destination::of(d.plan),
                None => match accepted_settings(&st) {
                    Some(s) => Destination::commissioned(s.destination),
                    None => {
                        return Fail::failed(
                            "record_failed",
                            "The commissioned destination cannot be read from the accepted preparation, so close cannot deliver.",
                        )
                        .next(status_next(audit, "Status reports what the records establish."))
                        .into_reply(OP, eff("ended", seal_effect, "none", closure_failed));
                    }
                },
            },
        };
        // Close has no stop input: it is not a placement, and a close that
        // is killed mid-delivery is reconciled by the next close.
        let request = Request {
            by: By::Close,
            destination,
            retries_losses_of: None,
            stop: None,
        };
        if let Err(r) = deliver(request, &mut made) {
            return r;
        }
        log::read(audit).newest_verified().map(|d| d.attempt)
    };
    let st = log::read(audit);
    let Some(presented) = presented else {
        // No attempt verified: the delivery continues through close, or
        // close --destination after an incomplete attempt.
        drop(lock);
        return unfinished_after(
            audit,
            &st,
            "delivery_incomplete",
            eff("ended", seal_effect, delivery_eff(&st, None), "unfinished"),
            None,
        );
    };

    // Complete.
    let ds = st.deliveries();
    let Some(pd) = ds.iter().find(|d| d.attempt == presented) else {
        drop(lock);
        return unfinished_after(
            audit,
            &st,
            "delivery_incomplete",
            eff("ended", seal_effect, "unknown", "unfinished"),
            None,
        );
    };
    let cr_n = st.close_requested().map_or(0, |c| c.n);
    let before_request = pd
        .ended
        .is_some_and(|(rec, e)| e.outcome == "verified" && rec.n < cr_n);
    let placement: Option<(&'static str, Option<String>, Vec<Surrendered>)> = match &confirmed {
        Some(c) => {
            let still = st.newest_verified().is_some_and(|d| d.attempt == c.attempt)
                && delivery::confirmation(audit, &st, c.attempt).as_deref()
                    == Some(c.token.as_str());
            still.then(|| ("confirmed", Some(c.token.clone()), c.surrendered.clone()))
        }
        None if before_request => Some(("delivered_before_close", None, Vec::new())),
        None if crate::sabotage!("skip_confirmation") && made.contains(&presented) => {
            // Sabotage control: a delivery close made is taken as confirmed.
            Some(("delivered_before_close", None, Vec::new()))
        }
        None => None,
    };
    let delivery_effect = delivery_value(pd.outcome());
    let Some((placement, confirmation, surrendered)) = placement else {
        drop(lock);
        return unfinished_after(
            audit,
            &st,
            "awaiting_confirmation",
            eff("ended", seal_effect, delivery_effect, "unfinished"),
            Some(presented),
        );
    };
    if let Err(e) = crate::fault!("close.before_closed_link") {
        return Fail::failed(
            "record_failed",
            format!(
                "The closing record could not be published ({}); close is unfinished.",
                util::errno_name(&e)
            ),
        )
        .cause(Cause::io("publish closed", &e))
        .next(close_next(
            audit,
            "Close again; it resumes from the recorded state.",
        ))
        .into_reply(
            OP,
            eff("ended", seal_effect, delivery_effect, closure_failed),
        );
    }
    let p = log::publish(audit, "closed", |s| {
        let refuse = |why: &str| Err(Fail::refused("record_failed", why.to_string()));
        if s.close_requested().is_none() {
            return refuse("close_requested is missing");
        }
        if s.closed().is_some() {
            return Err(Fail::refused("already_closed", ""));
        }
        if s.open_placement().is_some() {
            return refuse("a placement has no recorded ending");
        }
        let Some((seal_rec, seal)) = s.seal() else {
            return refuse("no seal is recorded");
        };
        let Some(d) = s.newest_verified().filter(|d| d.attempt == presented) else {
            return refuse("the presented delivery is no longer the newest verified one");
        };
        let (ended_rec, ended) = d.ended.expect("verified");
        Ok(Closed::after(ClosedAfterLaunch {
            seal: ClosedSeal {
                record: seal_rec.name(),
                actor: seal.actor,
                manifest_sha256: seal.manifest_sha256.clone(),
            },
            delivery: ClosedDelivery {
                attempt: d.attempt,
                record: ended_rec.name(),
                outcome: ended.outcome.clone(),
                package: ended.package.clone().unwrap_or_default(),
            },
            placement: placement.to_string(),
            confirmation: confirmation.clone(),
            surrendered: surrendered.clone(),
            runs: s.placements().len() as u64,
        })
        .to_j())
    });
    drop(lock);
    match p {
        Ok(_) | Err(PubErr::Refused(_)) => {
            let _ = crate::fault!("close.after_closed_link");
            let st = log::read(audit);
            match st.closed() {
                Some(c) => closed_reply(audit, &st, c, false, seal_effect),
                None => unfinished_after(
                    audit,
                    &st,
                    "awaiting_confirmation",
                    eff("ended", seal_effect, delivery_effect, "unfinished"),
                    Some(presented),
                ),
            }
        }
        Err(PubErr::Uncertain { cause, .. }) => Fail::failed(
            "record_failed",
            "The closing record was linked, but Stewart could not confirm it is durable.",
        )
        .cause(cause)
        .next(status_next(
            audit,
            "Status reports whether the audit is closed.",
        ))
        .next(close_next(
            audit,
            "Repeating close returns the recorded outcome.",
        ))
        .into_reply(OP, eff("ended", seal_effect, delivery_effect, "unknown")),
        Err(e) => publication_failure(
            audit,
            "The closing record",
            e,
            eff("ended", seal_effect, delivery_effect, closure_failed),
        ),
    }
}

/// The seal step: keep an existing seal, whoever made it; otherwise prepare
/// the selection current at `close_requested` and seal it with manager
/// attribution (8.1). `Ok(true)` when this call published the seal.
fn ensure_seal(
    audit: &Audit,
    state: &LogState,
    closure_failed: &'static str,
) -> Result<bool, Reply> {
    if state.seal().is_some() {
        return Ok(false);
    }
    let fail = |reason: &'static str, message: String, cause: Option<Cause>, seal: &'static str| {
        let mut f = Fail::failed(reason, message)
            .next(status_next(
                audit,
                "Status reports whether a seal was recorded.",
            ))
            .next(close_next(
                audit,
                "Close again; it resumes from the recorded state and never seals twice.",
            ));
        if let Some(c) = cause {
            f = f.cause(c);
        }
        Err(f.into_reply(OP, eff("ended", seal, "none", closure_failed)))
    };
    let Some(family) = accepted_settings(state).and_then(|s| crate::forms::family(&s.family))
    else {
        return fail(
            "record_failed",
            "The accepted commission's question family cannot be read, so close cannot prepare the answer for sealing.".to_string(),
            None,
            "none",
        );
    };
    let Some(cr) = state.close_requested() else {
        return fail(
            "record_failed",
            "No close request is recorded, so there is no selection to seal.".to_string(),
            None,
            "none",
        );
    };
    let prepared = match answer::prepare(audit, family, state, cr.n, Preparer::Manager) {
        Ok(p) => p,
        Err(PrepareError::WriteFailed(c)) => {
            return fail(
                "record_failed",
                format!(
                    "The answer could not be prepared for sealing ({}: {}); nothing was sealed.",
                    c.operation, c.error
                ),
                Some(c),
                "none",
            );
        }
        Err(PrepareError::Damaged(entries)) => {
            let names: Vec<String> = entries
                .iter()
                .map(|e| format!("{} ({})", e.id, e.failure))
                .collect();
            return fail(
                "record_failed",
                format!(
                    "Preparing the answer for a manager seal refused damaged entries ({}); nothing was sealed.",
                    names.join(", ")
                ),
                None,
                "none",
            );
        }
    };
    match answer::seal(audit, &family.versioned_id(), &prepared, Sealer::Manager) {
        Ok(s) => Ok(!s.existing),
        // Another seal took the slot first; it stands, whoever made it.
        Err(SealError::AuthoringEnded { seal: Some(_), .. }) => Ok(false),
        Err(SealError::LogDamaged) => Err(damaged_reply(audit, &log::read(audit))),
        Err(SealError::Uncertain(c)) => fail(
            "record_failed",
            format!(
                "The seal was linked, but Stewart could not confirm it is durable ({}: {}).",
                c.operation, c.error
            ),
            Some(c),
            "unknown",
        ),
        Err(SealError::NotPublished(c)) => fail(
            "record_failed",
            format!(
                "The seal could not be recorded ({}: {}); nothing was sealed.",
                c.operation, c.error
            ),
            Some(c),
            "none",
        ),
        Err(SealError::Damaged(why)) => fail(
            "record_failed",
            format!(
                "The prepared answer failed re-verification at sealing ({why}); nothing was sealed."
            ),
            None,
            "none",
        ),
        Err(SealError::Stale { revision_now }) => fail(
            "record_failed",
            format!(
                "The selection changed while close sealed it (revision {revision_now}); nothing was sealed."
            ),
            None,
            "none",
        ),
        Err(SealError::AuthoringEnded { by, record, .. }) => fail(
            "record_failed",
            format!(
                "Sealing found authoring ended by {} ({record}) without a seal; nothing was sealed.",
                by.name()
            ),
            None,
            "none",
        ),
    }
}

/// The `empty_return_before_launch` sabotage control: before launch, seal
/// an empty selection as manager and deliver it. The product creates no
/// answer before launch.
#[cfg(feature = "sabotage")]
fn sabotage_empty_return(audit: &Audit) {
    use crate::bodies::{Actor, SealRec};
    use crate::returns::{Manifest, Member};
    let st = log::read(audit);
    let Some(settings) = accepted_settings(&st) else {
        return;
    };
    let family = crate::forms::family(&settings.family)
        .map(|f| f.versioned_id())
        .unwrap_or_default();
    let answer = b"{\"schema\":\"stewart.answer/1\",\"revision\":0,\"entries\":[]}\n".to_vec();
    let rendering = b"No answer entries recorded.\n".to_vec();
    let Ok((n, dir)) = crate::names::claim_prepared(audit) else {
        return;
    };
    let (Ok(a_sha), Ok(r_sha)) = (
        crate::names::write_prepared_file(audit, &dir, n, "answer.json", &answer),
        crate::names::write_prepared_file(audit, &dir, n, "answer.md", &rendering),
    ) else {
        return;
    };
    let manifest = Manifest {
        audit: audit.id.clone(),
        store: audit.archive.store.clone(),
        family,
        renderer: crate::forms::RENDERER_ID.to_string(),
        writer: audit
            .exe
            .as_ref()
            .map(|e| e.sha256.clone())
            .unwrap_or_default(),
        actor: Actor::Manager,
        sealed_at: util::now_utc(),
        revision: 0,
        members: vec![
            Member {
                name: "answer.json".into(),
                role: "answer".into(),
                size: answer.len() as u64,
                sha256: a_sha.clone(),
            },
            Member {
                name: "answer.md".into(),
                role: "rendering".into(),
                size: rendering.len() as u64,
                sha256: r_sha.clone(),
            },
        ],
        unproduced: vec![],
    };
    let bytes = manifest.bytes();
    let Ok((_, name)) = crate::names::write_manifest(audit, &bytes) else {
        return;
    };
    let seal = SealRec {
        actor: Actor::Manager,
        prepared: n,
        answer_sha256: a_sha,
        rendering_sha256: Some(r_sha),
        revision: 0,
        manifest: name,
        manifest_sha256: util::sha256_hex(&bytes),
        invocation: None,
    };
    if log::publish(audit, "seal", |_| Ok(seal.to_j())).is_err() {
        return;
    }
    let request = Request {
        by: By::Close,
        destination: Destination::commissioned(settings.destination),
        retries_losses_of: None,
        stop: None,
    };
    let _ = delivery::deliver(audit, &log::read(audit), &request);
}

#[cfg(test)]
mod tests {
    #[test]
    fn delivery_values_stay_in_the_effect_set() {
        for o in [
            "verified",
            "verified_with_losses",
            "partial",
            "failed",
            "name_taken",
        ] {
            let v = super::delivery_value(Some(o));
            assert!(
                crate::reply::EFFECT_VALUES
                    .iter()
                    .any(|(k, vs)| *k == "delivery" && vs.contains(&v)),
                "{o} -> {v}"
            );
        }
        assert_eq!(super::delivery_value(None), "unknown");
    }
}
