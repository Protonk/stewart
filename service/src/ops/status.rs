//! `stewart status REF` and `stewart status --archive ROOT` (INTERFACE 5.6).
//!
//! Status is read-only: it never launches, repairs, seals, copies or closes
//! anything, and it writes nothing. Liveness comes only from the active lock
//! (tested without being taken), never from elapsed time. A fact that cannot
//! be established is `unknown`, with a diagnostic naming the record and the
//! cause; a damaged record is never read as absent. The condition is the
//! first of the interface's list that applies, so a later, weaker fact never
//! hides an earlier one.

use super::{answer_j, headline, seal_j};
use crate::archive::{self, Audit, Fail};
use crate::delivery;
use crate::ids;
use crate::json::{self, J};
use crate::log::{self, Body, LogState};
use crate::reply::{Next, Reply};
use crate::util;

const OP: &str = "status";

fn ev(fact: impl Into<String>, evidence: impl Into<String>) -> J {
    J::obj()
        .with("fact", fact.into())
        .with("evidence", evidence.into())
}

/// The active lock, observed without taking it (4.6).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lock {
    Held,
    Free,
    /// The lock could not be tested; nothing about liveness is established.
    Unknown,
}

/// Observe the lock; the second value is the diagnostic when it cannot be
/// tested.
pub fn observe_lock(audit: &Audit) -> (Lock, Option<J>) {
    match audit.lock_held() {
        Ok(true) => (Lock::Held, None),
        Ok(false) => (Lock::Free, None),
        Err(e) => (
            Lock::Unknown,
            Some(J::obj().with("record", archive::LOCK_FILE).with(
                "cause",
                format!("the active lock cannot be tested: {}", util::describe(&e)),
            )),
        ),
    }
}

/// How close would report an unfinished close now (5.6, 5.8): with the lock
/// held, what holds it; with it free, a confirmation awaited or a delivery
/// incomplete. `None` means the last close stopped before recording more,
/// and repeating close continues it.
pub fn unfinished_reason(audit: &Audit, state: &LogState, lock: Lock) -> Option<&'static str> {
    if state.damaged() {
        return Some("log_damaged");
    }
    match lock {
        Lock::Held => Some(if state.open_intake().is_some() {
            "intake_still_running"
        } else if state.open_placement().is_some() {
            "run_still_held"
        } else {
            "close_in_progress"
        }),
        Lock::Free => {
            if delivery::outstanding(audit, state).is_some() {
                Some("awaiting_confirmation")
            } else if state.seal().is_some() && state.newest_verified().is_none() {
                Some("delivery_incomplete")
            } else {
                None
            }
        }
        Lock::Unknown => None,
    }
}

pub struct View {
    pub condition: &'static str,
    pub summary: String,
    pub evidence: Vec<J>,
    pub next: Vec<Next>,
    pub headline: J,
    pub diagnostics: Vec<J>,
    pub lock: Lock,
}

/// Establish the condition, its evidence and the next calls from the log
/// and the lock.
pub fn view(audit: &Audit, state: &LogState) -> View {
    let mut evidence = Vec::new();
    let mut diagnostics: Vec<J> = Vec::new();
    let r = audit.reference.as_str();
    let (lock, lock_diag) = observe_lock(audit);
    diagnostics.extend(lock_diag);
    for b in &state.damage {
        diagnostics.push(
            J::obj()
                .with("record", b.name.as_str())
                .with("cause", b.problem.as_str()),
        );
    }
    for s in log::unlinked_stage(audit, state) {
        diagnostics.push(J::obj().with("record", s).with(
            "cause",
            "interrupted_publication: a staged record that no log name holds; it is not a record",
        ));
    }
    for s in unlinked_run_stage(audit) {
        diagnostics.push(J::obj().with("record", s).with(
            "cause",
            "interrupted_publication: a staged run record that no run record shares; it is not a record",
        ));
    }
    for c in unpublished_candidates(audit, state) {
        diagnostics.push(J::obj().with("record", c).with(
            "cause",
            "unpublished_candidate: no log record names it; it is not a record",
        ));
    }
    for d in recorded_diagnostics(audit) {
        diagnostics.push(d);
    }
    let hl = headline(audit, state);
    let accepted = state.accepted();
    let latest_prep = state.latest_prepared();
    let latest_handle = latest_prep.map(|p| match &p.body {
        Body::Prepared { prep, .. } => ids::handle(
            &audit.archive.store,
            &audit.id,
            "mp",
            &format!("mp{prep}"),
            &[&p.sha256],
        ),
        _ => String::new(),
    });
    let n = |args: &[&str], why: &str| Next::new(audit.argv(args), why);
    let mut next = Vec::new();
    let open_place = state.open_placement();
    let latest = state.latest_placement();
    let lock_evidence = |evidence: &mut Vec<J>| match lock {
        Lock::Held => evidence.push(ev("a process holds the active lock", "lock held")),
        Lock::Free => evidence.push(ev("no process holds the active lock", "lock free")),
        Lock::Unknown => evidence.push(ev(
            "whether a process holds the active lock is unknown",
            "the lock could not be tested",
        )),
    };

    let (condition, summary): (&'static str, String) = if state.damaged() {
        let readable = state.recs.len();
        match accepted {
            None => {
                evidence.push(ev(
                    "acceptance cannot be established",
                    format!("log damaged at {}; no accepted record among the {readable} readable records before the damage", state.damage[0].name),
                ));
                next.push(n(
                    &["status", r],
                    "Status again after you restore your storage; Stewart never repairs the log.",
                ));
                next.push(Next::new(
                    vec![
                        audit.writer().to_string(),
                        "new".into(),
                        audit.refile.folder.clone(),
                        "--archive".into(),
                        audit.archive.path.clone(),
                    ],
                    "Start a new reference for a new commission.",
                ));
                (
                    "acceptance_uncertain",
                    format!(
                        "The audit log is damaged ({}); whether a commission was accepted cannot be established.",
                        state.bad_names()
                    ),
                )
            }
            Some(a) => {
                evidence.push(ev(
                    "commission accepted",
                    format!("accepted record log/{}.json", a.n),
                ));
                evidence.push(ev(
                    "later facts cannot be established",
                    format!("log damaged at {}", state.damage[0].name),
                ));
                next.push(n(&["receipt", r], "Read the accepted commission."));
                next.push(n(
                    &["status", r],
                    "Status again after you restore your storage; Stewart never repairs the log.",
                ));
                (
                    "log_damaged",
                    format!(
                        "A commission was accepted, but the audit log is damaged after it ({}); later facts are unknown.",
                        state.bad_names()
                    ),
                )
            }
        }
    } else if let Some(c) = state.closed() {
        let body = c.closed_body();
        evidence.push(ev("closed", format!("closed record log/{}.json", c.n)));
        match body.and_then(|b| b.after.as_ref()) {
            Some(a) => {
                evidence.push(ev(
                    format!("sealed by the {}", a.seal.actor.name()),
                    format!("seal {}", a.seal.record),
                ));
                evidence.push(ev(
                    format!("delivery {} {}", a.delivery.attempt, a.delivery.outcome),
                    format!("delivery_ended {}", a.delivery.record),
                ));
                let placement = if a.placement == "confirmed" {
                    "you confirmed its placement"
                } else {
                    "it was delivered before close was first requested, so the ordinary close settled its placement"
                };
                let summary = if a.surrendered.is_empty() {
                    format!(
                        "Closed after launch. The return was delivered to {}, and {placement}.",
                        a.delivery.package
                    )
                } else {
                    let given: Vec<String> = a
                        .surrendered
                        .iter()
                        .map(|s| format!("{} ({} at {})", s.member, s.failure, s.stage))
                        .collect();
                    format!(
                        "Closed after launch with surrendered losses: {}. The verified members were delivered to {}; this closure is not a complete delivery.",
                        given.join(", "),
                        a.delivery.package
                    )
                };
                ("closed", summary)
            }
            None => (
                "closed_before_launch",
                if body.is_some_and(|b| b.accepted) {
                    "Closed before any auditor launch. The accepted commission stays in the archive; no answer was created.".to_string()
                } else {
                    "Closed before any commission was accepted. No answer was created.".to_string()
                },
            ),
        }
    } else if let Some(cr) = state.close_requested() {
        evidence.push(ev(
            "close requested",
            format!("close_requested record log/{}.json without closed", cr.n),
        ));
        lock_evidence(&mut evidence);
        let reason = unfinished_reason(audit, state, lock);
        if reason == Some("awaiting_confirmation") {
            let (attempt, token) = delivery::outstanding(audit, state).expect("outstanding");
            let v = delivery::view(audit, state, attempt).expect("planned");
            if let Some(d) = state.deliveries().iter().find(|d| d.attempt == attempt) {
                if let Some((rec, e)) = d.ended {
                    evidence.push(ev(
                        format!("delivery {attempt} {}", e.outcome),
                        format!("delivery_ended log/{}.json", rec.n),
                    ));
                }
            }
            next.push(super::close::confirm_next(audit, &token, &v));
            next.push(n(
                &["status", r],
                "Status keeps showing the delivery and its token until you confirm.",
            ));
            let losses = if v.losses.is_empty() {
                String::new()
            } else {
                format!(
                    " It has losses, each of which confirmation must surrender by name: {}.",
                    v.loss_ids().join(", ")
                )
            };
            (
                "awaiting_confirmation",
                format!(
                    "Close was requested, and delivery {attempt} verified at {}. Close waits for your confirmation with {token}.{losses}",
                    v.location.as_deref().unwrap_or("its destination")
                ),
            )
        } else {
            let detail = match reason {
                Some("intake_still_running") => "an intake still holds the active lock".to_string(),
                Some("run_still_held") => {
                    "a run still holds the active lock and has not recorded its ending".to_string()
                }
                Some("close_in_progress") => "another close holds the active lock".to_string(),
                Some("delivery_incomplete") => {
                    "the answer is sealed and no delivery attempt has verified".to_string()
                }
                _ => "the last close stopped before recording more".to_string(),
            };
            if reason == Some("delivery_incomplete") || reason.is_none() {
                next.push(super::close::continue_next(audit, state));
            } else {
                next.push(n(
                    &["close", r],
                    "Continue the close; it resumes from the recorded state.",
                ));
            }
            next.push(n(
                &["status", r],
                "See the evidence for where the close stands.",
            ));
            (
                "close_unfinished",
                format!(
                    "Close was requested but has not finished: {detail}. Repeat close to continue it."
                ),
            )
        }
    } else if let Some(p) = open_place.as_ref().filter(|_| lock != Lock::Free) {
        evidence.push(ev(
            format!("placement {} has no recorded ending", p.run),
            format!("run_started log/{}.json without run_ended", p.started.n),
        ));
        lock_evidence(&mut evidence);
        next.push(n(&["status", r], "See whether the run has ended."));
        next.push(n(
            &["close", r],
            "End authoring; close waits for the run to stop, then seals and delivers.",
        ));
        (
            "run_active",
            if lock == Lock::Held {
                format!("Run {} is active: it holds the audit now.", p.run)
            } else {
                format!(
                    "Run {} has no recorded ending, and whether it still holds the audit cannot be tested; it is not known to have stopped.",
                    p.run
                )
            },
        )
    } else if accepted.is_none()
        && (lock == Lock::Held || (lock == Lock::Unknown && state.open_intake().is_some()))
    {
        if let Some(a) = state.open_intake() {
            evidence.push(ev(
                format!("intake {a} in progress"),
                "intake_planned without outcome; lock held",
            ));
        } else {
            evidence.push(ev("a process holds the active lock", "lock held"));
        }
        next.push(n(&["status", r], "See whether the intake ended."));
        next.push(n(
            &["close", r],
            "End this reference; close waits for the intake to finish.",
        ));
        (
            "intake_in_progress",
            "A commission is capturing the selection now.".to_string(),
        )
    } else if let Some((srec, seal)) = state.seal() {
        evidence.push(ev(
            format!("sealed by the {}", seal.actor.name()),
            format!("seal log/{}.json", srec.n),
        ));
        match state.newest_verified() {
            Some(d) => {
                let (rec, e) = d.ended.expect("verified");
                evidence.push(ev(
                    format!("delivery {} {}", d.attempt, e.outcome),
                    format!("delivery_ended log/{}.json", rec.n),
                ));
                let why = if e.outcome == "verified" {
                    "Close the audit. An ordinary close confirms where the delivered copy is."
                } else {
                    "Close the audit. This delivery has losses, so close asks you to confirm it and to surrender each loss by name."
                };
                next.push(n(&["close", r], why));
                (
                    "delivered_open",
                    format!(
                        "The answer is sealed by the {}, and delivery {} {} at {}. The audit is open.",
                        seal.actor.name(),
                        d.attempt,
                        if e.outcome == "verified" {
                            "verified".to_string()
                        } else {
                            "verified with losses".to_string()
                        },
                        e.package.as_deref().unwrap_or("its destination")
                    ),
                )
            }
            None => {
                if let Some(d) = state.deliveries().last() {
                    match d.ended {
                        Some((rec, e)) => evidence.push(ev(
                            format!("delivery {} {}", d.attempt, e.outcome),
                            format!("delivery_ended log/{}.json", rec.n),
                        )),
                        None => evidence.push(ev(
                            format!("delivery {} has no recorded outcome", d.attempt),
                            format!(
                                "delivery_planned log/{}.json without delivery_ended",
                                d.planned.n
                            ),
                        )),
                    }
                } else {
                    evidence.push(ev("no delivery attempt", "no delivery_planned record"));
                }
                next.push(super::close::continue_next(audit, state));
                (
                    "sealed_undelivered",
                    format!(
                        "The answer is sealed by the {}; no delivery has verified. Close continues delivering that same sealed answer without another investigation.",
                        seal.actor.name()
                    ),
                )
            }
        }
    } else if let Some(p) = latest
        .as_ref()
        .filter(|p| p.ended.is_some_and(|(_, e)| e.ending != "interrupted"))
    {
        let (rec, e) = p.ended.expect("ended");
        evidence.push(ev(
            format!("run {} ended {}", p.run, e.ending),
            format!("run_ended log/{}.json", rec.n),
        ));
        evidence.push(ev("no seal", "no seal record"));
        next.push(n(
            &["close", r],
            "Close seals the recorded selection with manager attribution and delivers it; it does not infer an auditor conclusion.",
        ));
        match e.ending.as_str() {
            "damaged" => (
                "damaged",
                format!(
                    "Run {} ended because recorded answer bytes were found damaged; the answer is not submitted.",
                    p.run
                ),
            ),
            "limit_reached" => (
                "limit_reached",
                format!(
                    "Run {} ended at the audit's limits without a submission.",
                    p.run
                ),
            ),
            "ended_unsubmitted" => (
                "ended_unsubmitted",
                format!(
                    "Run {} ended without a submission; the auditor did not seal its answer.",
                    p.run
                ),
            ),
            // `sealed` has a seal and `stopped_by_close` a close request,
            // both handled above.
            other => (
                "interrupted",
                format!("Run {} ended {other}; the answer is not submitted.", p.run),
            ),
        }
    } else if let Some(p) = latest.as_ref() {
        match p.ended {
            Some((rec, e)) => evidence.push(ev(
                format!(
                    "run {} interrupted ({})",
                    p.run,
                    e.cause.as_deref().unwrap_or("no cause recorded")
                ),
                format!("run_ended log/{}.json", rec.n),
            )),
            None => evidence.push(ev(
                format!("run {} ended without recording its ending", p.run),
                "run_started without run_ended; lock free",
            )),
        }
        next.push(n(
            &["run", r],
            "Continue the audit in a new placement under the same cumulative limits.",
        ));
        next.push(n(
            &["close", r],
            "End authoring and seal the recorded selection with manager attribution.",
        ));
        (
            "interrupted",
            format!(
                "Run {} was interrupted; the answer is not submitted. Run continues it, or close ends authoring.",
                p.run
            ),
        )
    } else if let Some(a) = accepted {
        evidence.push(ev(
            "commission accepted",
            format!("accepted record log/{}.json", a.n),
        ));
        evidence.push(ev("no run started", "no run_started record"));
        next.push(n(
            &["run", r],
            "Start the audit; the receipt lists what run needs.",
        ));
        next.push(n(
            &["close", r],
            "End the commission without an auditor return.",
        ));
        (
            "not_started",
            "The commission is accepted and has not been run.".to_string(),
        )
    } else if let Some(last) = state
        .intakes()
        .last()
        .filter(|i| i.outcome() != Some("accepted"))
    {
        match last.outcome() {
            Some(o) => evidence.push(ev(
                format!("intake {} ended without acceptance", last.attempt),
                format!(
                    "intake_ended {o} (log/{}.json)",
                    last.ended.map(|e| e.n).unwrap_or(0)
                ),
            )),
            None => evidence.push(ev(
                format!("intake {} ended without acceptance", last.attempt),
                "intake_planned without outcome; lock free",
            )),
        }
        next.push(n(
            &["prepare", r],
            "Prepare the current folder for a fresh handle.",
        ));
        if let Some(h) = &latest_handle {
            next.push(n(
                &["commission", r, h, "--i-am-finished"],
                "Commission the latest preparation (it is refused if the folder changed since).",
            ));
        }
        next.push(n(
            &["close", r],
            "End this reference without commissioning.",
        ));
        (
            "intake_failed",
            format!(
                "Intake {} ended without acceptance; no commission is accepted.",
                last.attempt
            ),
        )
    } else {
        evidence.push(ev(
            "no commission accepted",
            format!(
                "log readable through log/{}.json; no accepted record",
                state.recs.len()
            ),
        ));
        if let Some(p) = latest_prep {
            evidence.push(ev(
                format!(
                    "latest preparation {}",
                    latest_handle.clone().unwrap_or_default()
                ),
                format!("prepared record log/{}.json", p.n),
            ));
        }
        next.push(n(
            &["prepare", r],
            "Prepare the folder once you have finished editing it.",
        ));
        if let Some(h) = &latest_handle {
            next.push(n(
                &["commission", r, h, "--i-am-finished"],
                "Accept exactly the latest prepared selection.",
            ));
        }
        next.push(n(
            &["close", r],
            "End this reference without commissioning.",
        ));
        ("preparing", "No commission is accepted yet.".to_string())
    };
    View {
        condition,
        summary,
        evidence,
        next,
        headline: hl.to_j(),
        diagnostics,
        lock,
    }
}

/// Stage files of every run directory that no run record shares.
fn unlinked_run_stage(audit: &Audit) -> Vec<String> {
    let Ok(runs) = audit.dir.open_dir("runs") else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for n in runs.names().unwrap_or_default() {
        if let Ok(d) = runs.open_dir(&n) {
            for s in crate::runs::unlinked_stage(&d) {
                out.push(format!("runs/{n}/{s}"));
            }
        }
    }
    out
}

/// Files no log record names: manager preparations, intake receipts, seal
/// manifests, delivery plans and payload files (4.3). An auditor's
/// preparation of the answer is an inspection candidate by design and is not
/// reported.
fn unpublished_candidates(audit: &Audit, state: &LogState) -> Vec<String> {
    let mut out = Vec::new();
    if let Ok(prep) = audit.dir.open_dir("prep") {
        if let Ok(names) = prep.names() {
            for n in names {
                let named = n
                    .parse::<u64>()
                    .ok()
                    .is_some_and(|k| state.prepared(k).is_some());
                if !named {
                    out.push(format!("prep/{n}"));
                }
            }
        }
    }
    if let Ok(intake) = audit.dir.open_dir("intake") {
        if let Ok(names) = intake.names() {
            for n in names {
                let has_receipt = intake
                    .open_dir(&n)
                    .and_then(|d| d.exists("receipt.json"))
                    .unwrap_or(false);
                let named = state.recs.iter().any(|r| matches!(&r.body, Body::Accepted { receipt, .. } if *receipt == format!("intake/{n}/receipt.json")));
                if has_receipt && !named {
                    out.push(format!("intake/{n}/receipt.json"));
                }
            }
        }
    }
    let listed = |dir: &str| -> Vec<String> {
        audit
            .dir
            .open_dir(dir)
            .and_then(|d| d.names())
            .unwrap_or_default()
    };
    let manifests: Vec<String> = state
        .seal()
        .map(|(_, s)| s.manifest.clone())
        .into_iter()
        .collect();
    for n in listed("seal") {
        let rel = format!("seal/{n}");
        if !manifests.contains(&rel) {
            out.push(rel);
        }
    }
    let plans: Vec<String> = state.deliveries().iter().map(|d| d.plan.plan()).collect();
    for n in listed("delivery") {
        let rel = format!("delivery/{n}");
        if !plans.contains(&rel) {
            out.push(rel);
        }
    }
    let payloads: Vec<&str> = state
        .entries()
        .filter_map(|(_, e)| e.created.as_ref().map(|v| v.payload.file.as_str()))
        .collect();
    for n in listed("payload") {
        let rel = format!("payload/{n}");
        if !payloads.contains(&rel.as_str()) {
            out.push(rel);
        }
    }
    out
}

/// Diagnostics recorded by earlier invocations (`diag/`).
fn recorded_diagnostics(audit: &Audit) -> Vec<J> {
    let mut out = Vec::new();
    let Ok(diag) = audit.dir.open_dir("diag") else {
        return out;
    };
    let Ok(mut names) = diag.names() else {
        return out;
    };
    names.sort_by_key(|n| {
        n.strip_suffix(".json")
            .and_then(|x| x.parse::<u64>().ok())
            .unwrap_or(u64::MAX)
    });
    for n in names {
        let rel = format!("diag/{n}");
        match diag
            .read_regular(&n, archive::RECORD_LIMIT)
            .map_err(|e| e.describe())
            .and_then(|(b, _)| archive::decode_record(&b))
        {
            Ok(rec) => {
                let b = rec.body();
                out.push(
                    J::obj()
                        .with("record", rel)
                        .with("at", rec.at.as_str())
                        .with("operation", b.str("operation").unwrap_or(""))
                        .with("reason", b.str_or_null("reason").ok().flatten())
                        .with("message", b.str_or_null("message").ok().flatten()),
                );
            }
            Err(e) => out.push(
                J::obj()
                    .with("record", rel)
                    .with("cause", format!("the diagnostic cannot be read: {e}")),
            ),
        }
    }
    out
}

/// `runs`: the count, whether a placement holds the lock now, that
/// placement's observations while it does, and the latest placement.
fn runs_j(state: &LogState, lock: Lock) -> J {
    let placements = state.placements();
    let open = state.open_placement();
    let held = match (lock, &open) {
        (Lock::Held, Some(_)) => J::Bool(true),
        (Lock::Unknown, Some(_)) => J::Str("unknown".into()),
        _ => J::Bool(false),
    };
    let holder = match (lock, &open) {
        (Lock::Held, Some(p)) => p.start.observations.to_j(),
        _ => J::Null,
    };
    let last = match placements.last() {
        None => J::Null,
        Some(p) => {
            let e = p.ended;
            J::obj()
                .with("number", p.run)
                .with("started_at", p.started.at.as_str())
                .with("ending", e.map(|(_, e)| e.ending.as_str()))
                .with("cause", e.and_then(|(_, e)| e.cause.as_deref()))
                .with("ended_at", e.map(|(r, _)| r.at.as_str()))
                .with("recorded_by", e.map(|(_, e)| e.recorded_by.as_str()))
        }
    };
    J::obj()
        .with("count", placements.len() as u64)
        .with("held", held)
        .with("holder", holder)
        .with("last", last)
}

/// `deliveries`: every attempt in order, with its plan, outcome, members,
/// losses (with loss IDs, only for `verified_with_losses`) and its token
/// while it is outstanding.
pub fn deliveries_j(audit: &Audit, state: &LogState) -> J {
    let outstanding = delivery::outstanding(audit, state);
    J::Arr(
        state
            .deliveries()
            .iter()
            .map(|d| {
                let v = delivery::view_of(audit, d);
                let token = outstanding
                    .as_ref()
                    .filter(|(a, _)| *a == d.attempt)
                    .map(|(_, t)| t.as_str());
                J::obj()
                    .with("attempt", d.attempt)
                    .with("by", d.plan.by.as_str())
                    .with("destination", d.plan.destination.as_str())
                    .with("destination_source", d.plan.destination_source.as_str())
                    .with("package", d.plan.package.as_str())
                    .with("replaces", d.plan.replaces)
                    .with("outcome", v.outcome.as_deref())
                    .with(
                        "cause",
                        v.cause.as_ref().map(|c| c.to_j()).unwrap_or(J::Null),
                    )
                    .with("verified_members", json::strs(&v.verified_members))
                    .with("unverified_members", v.unverified_j())
                    .with("losses", v.losses_j())
                    .with("confirmation", token)
            })
            .collect(),
    )
}

/// `closure`: null without `close_requested`; otherwise the same keys in
/// every state, each null while it does not apply, or `unknown` where a
/// damaged log hides it.
fn closure_j(audit: &Audit, state: &LogState, lock: Lock) -> J {
    let keys = |requested_at: J,
                before_launch: J,
                accepted: J,
                unfinished_reason: J,
                closed_at: J,
                outcome: J,
                placement: J,
                surrendered: J| {
        J::obj()
            .with("requested_at", requested_at)
            .with("before_launch", before_launch)
            .with("accepted", accepted)
            .with("unfinished_reason", unfinished_reason)
            .with("closed_at", closed_at)
            .with("outcome", outcome)
            .with("placement", placement)
            .with("surrendered", surrendered)
    };
    let unknown = || J::Str("unknown".into());
    let Some(cr) = state.close_requested() else {
        if state.damaged() {
            // A close request may lie beyond the damage; it is not absent.
            return keys(
                unknown(),
                unknown(),
                if state.accepted().is_some() {
                    J::Bool(true)
                } else {
                    unknown()
                },
                J::Str("log_damaged".into()),
                unknown(),
                unknown(),
                unknown(),
                unknown(),
            );
        }
        return J::Null;
    };
    let before_launch = !state.placements().iter().any(|p| p.started.n < cr.n);
    let accepted = J::Bool(state.accepted().is_some());
    match state.closed().and_then(|c| c.closed_body().map(|b| (c, b))) {
        Some((c, b)) => {
            let (placement, surrendered) = match &b.after {
                Some(a) => (
                    J::Str(a.placement.clone()),
                    J::Arr(a.surrendered.iter().map(|s| s.to_j()).collect()),
                ),
                None => (J::Null, J::Null),
            };
            keys(
                J::Str(cr.at.clone()),
                J::Bool(before_launch),
                accepted,
                J::Null,
                J::Str(c.at.clone()),
                J::Str(b.outcome.clone()),
                placement,
                surrendered,
            )
        }
        None => {
            // On a damaged log a `closed` record may lie beyond the damage;
            // its facts are unknown rather than absent.
            let closing = || {
                if state.damaged() { unknown() } else { J::Null }
            };
            keys(
                J::Str(cr.at.clone()),
                J::Bool(before_launch),
                accepted,
                unfinished_reason(audit, state, lock).into(),
                closing(),
                closing(),
                closing(),
                closing(),
            )
        }
    }
}

pub fn run(reference: &str) -> Reply {
    let audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, vec![]),
    };
    let mut state = log::read(&audit);
    log::sabotage_unknown_as_absent(&mut state);
    let v = view(&audit, &state);
    let mut diagnostics = v.diagnostics;
    let allowances = match state.limits() {
        None => J::Null,
        Some(limits) if state.damaged() => {
            // Placements beyond the damage may have charged usage.
            let one = |limit: u64| {
                J::obj()
                    .with("used", "unknown")
                    .with("reported", "unknown")
                    .with("estimated", "unknown")
                    .with("limit", limit)
            };
            J::obj()
                .with("turns", one(limits.turns))
                .with("input_tokens", one(limits.input_tokens))
                .with("output_tokens", one(limits.output_tokens))
        }
        Some(limits) => {
            let (used, problems) = crate::runs::cumulative_usage(&audit, &state);
            for p in problems {
                diagnostics.push(J::obj().with("record", "runs").with(
                    "cause",
                    format!("usage accounting could not read a record: {p}"),
                ));
            }
            limits.allowances_j(&used)
        }
    };
    let (seal, seal_diag) = seal_j(&audit, &state);
    diagnostics.extend(seal_diag);
    let answer = if state.damaged() && state.launched() {
        J::obj()
            .with("revision", "unknown")
            .with("entries", "unknown")
    } else {
        answer_j(&state)
    };
    let provider = state.placements().last().map(|p| p.start.provider.clone());
    let mut data = J::obj()
        .with("headline", v.headline)
        .with("condition", v.condition)
        .with("summary", v.summary)
        .with("evidence", J::Arr(v.evidence))
        .with("runs", runs_j(&state, v.lock))
        .with("allowances", allowances)
        .with("answer", answer)
        .with("seal", seal)
        .with("deliveries", deliveries_j(&audit, &state))
        .with("closure", closure_j(&audit, &state, v.lock))
        .with("diagnostics", J::Arr(diagnostics))
        .with(
            "provider_url_override",
            provider
                .as_ref()
                .filter(|p| p.overridden)
                .map(|p| p.base_url.as_str()),
        )
        .with(
            "provider_proxy",
            provider.as_ref().and_then(|p| p.proxy.as_deref()),
        )
        .with(
            "receipt_line",
            if state.accepted().is_some() {
                json::strs(&audit.argv(&["receipt", &audit.reference]))
            } else {
                J::Null
            },
        );
    if let Some(why) = &audit.archive.moved {
        data.push("archive_notice", format!("This archive was moved or copied ({why}); status can read it, but mutations are refused here."));
    }
    let mut reply = Reply::completed(OP, vec![], data);
    reply.next = v.next;
    reply
}

/// `status --archive ROOT`: every reference in creation order. Selects nothing.
pub fn run_archive(root_path: &str) -> Reply {
    match archive_inner(root_path) {
        Ok(r) => r,
        Err(f) => f.into_reply(OP, vec![]),
    }
}

fn archive_inner(root_path: &str) -> Result<Reply, Fail> {
    let root = archive::open_root(root_path)?;
    let (bytes, _) = root
        .read_regular(archive::STORE_FILE, archive::RECORD_LIMIT)
        .map_err(|e| match e {
            crate::fsx::ReadError::Missing => Fail::refused(
                "archive_not_a_store",
                format!("{root_path} has no Stewart store marker."),
            ),
            other => Fail::refused(
                "archive_unavailable",
                format!(
                    "{root_path}/{} cannot be read: {}.",
                    archive::STORE_FILE,
                    other.describe()
                ),
            ),
        })?;
    let marker = archive::decode_marker(&bytes).map_err(|e| {
        Fail::refused(
            "archive_unavailable",
            format!("The store marker cannot be decoded: {e}."),
        )
    })?;
    let mut rows: Vec<(String, String, J)> = Vec::new();
    let audits = root.open_dir("audits").ok();
    let names = audits
        .as_ref()
        .and_then(|a| a.names().ok())
        .unwrap_or_default();
    for id in names {
        if !ids::is_id(&id, 'a') {
            continue;
        }
        let reference = ids::encode_reference(&id, &marker.store, root_path);
        let row = match Audit::open(&reference) {
            Ok(audit) => {
                let state = log::read(&audit);
                let v = view(&audit, &state);
                let settings = state.latest_prepared().and_then(|p| {
                    p.body_obj().obj("settings").ok().map(|s| {
                        (
                            s.opt_str("inquiry").ok().flatten().map(String::from),
                            s.opt_str("varies").ok().flatten().map(String::from),
                        )
                    })
                });
                let (inquiry, varies) = settings.unwrap_or((None, None));
                let at = audit.refile.at.clone();
                (
                    at,
                    id.clone(),
                    J::obj()
                        .with("reference", reference.as_str())
                        .with("folder", audit.refile.folder.as_str())
                        .with("inquiry", inquiry)
                        .with("varies", varies)
                        .with("headline", v.headline)
                        .with("condition", v.condition),
                )
            }
            Err(f) => (
                String::new(),
                id.clone(),
                J::obj().with("reference", reference.as_str()).with(
                    "diagnostic",
                    J::obj()
                        .with("reason", f.reason)
                        .with("message", f.message.as_str()),
                ),
            ),
        };
        rows.push(row);
    }
    // Creation order: the time recorded in each REFERENCE.json, then the identifier.
    rows.sort_by(|a, b| (a.0.as_str(), a.1.as_str()).cmp(&(b.0.as_str(), b.1.as_str())));
    let data = J::obj()
        .with("archive", root_path)
        .with("store", marker.store.as_str())
        .with(
            "references",
            J::Arr(rows.into_iter().map(|r| r.2).collect()),
        );
    Ok(Reply::completed(OP, vec![], data))
}
