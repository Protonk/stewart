//! `stewart status REF` and `stewart status --archive ROOT` (INTERFACE 5.6).
//!
//! Status is read-only: it never launches, repairs, seals, copies or closes
//! anything, and it writes nothing. Liveness comes only from the active lock
//! (tested without being taken), never from elapsed time.

use super::headline;
use crate::archive::{self, Audit, Fail};
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

pub struct View {
    pub condition: &'static str,
    pub summary: String,
    pub evidence: Vec<J>,
    pub next: Vec<Next>,
    pub headline: J,
    pub closure: J,
    pub diagnostics: Vec<J>,
    pub accepted_limits: Option<(u64, u64, u64)>,
}

/// Establish the pre-launch condition and its evidence from the log and lock.
pub fn view(audit: &Audit, state: &LogState) -> View {
    let mut evidence = Vec::new();
    let mut diagnostics: Vec<J> = Vec::new();
    let r = audit.reference.as_str();
    let held = audit.lock_held();
    if let Err(e) = &held {
        diagnostics.push(J::obj().with("record", archive::LOCK_FILE).with(
            "cause",
            format!("the active lock cannot be tested: {}", util::describe(e)),
        ));
    }
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
    for c in unpublished_candidates(audit, state) {
        diagnostics.push(J::obj().with("record", c).with(
            "cause",
            "unpublished_candidate: no log record names it; it is not a record",
        ));
    }
    for d in recorded_diagnostics(audit) {
        diagnostics.push(d);
    }
    let hl = headline(state);
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
    let mut closure = J::Null;
    let accepted_limits = accepted.and_then(|a| match &a.body {
        Body::Accepted { prep, .. } => state.prepared(*prep).and_then(|p| {
            let s = p.body_obj().obj("settings").ok()?;
            let l = s.obj("limits").ok()?;
            Some((
                l.u64("turns", u64::MAX).ok()?,
                l.u64("input_tokens", u64::MAX).ok()?,
                l.u64("output_tokens", u64::MAX).ok()?,
            ))
        }),
        _ => None,
    });

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
        let (before, was_accepted) = match &c.body {
            Body::Closed(c) => (c.before_launch(), c.accepted),
            _ => (true, false),
        };
        evidence.push(ev("closed", format!("closed record log/{}.json", c.n)));
        closure = J::obj()
            .with("closed_at", c.at.as_str())
            .with("before_launch", before)
            .with("accepted", was_accepted);
        (
            "closed_before_launch",
            if was_accepted {
                "Closed before any auditor launch. The accepted commission stays in the archive; no answer was created.".to_string()
            } else {
                "Closed before any commission was accepted. No answer was created.".to_string()
            },
        )
    } else if let Some(cr) = state.close_requested() {
        // Held with an open intake: that intake is still running. Held
        // otherwise: another close holds it. Free: the last close stopped
        // before recording the end, and repeating close completes it.
        let reason = match (&held, state.open_intake()) {
            (Ok(true), Some(_)) => J::Str("intake_still_running".into()),
            (Ok(true), None) => J::Str("close_in_progress".into()),
            _ => J::Null,
        };
        evidence.push(ev(
            "close requested",
            format!("close_requested record log/{}.json without closed", cr.n),
        ));
        match &held {
            Ok(true) => evidence.push(ev("a process holds the active lock", "lock held")),
            Ok(false) => evidence.push(ev("no process holds the active lock", "lock free")),
            Err(_) => evidence.push(ev("lock state unknown", "the lock could not be tested")),
        }
        closure = J::obj()
            .with("requested_at", cr.at.as_str())
            .with("unfinished_reason", reason);
        next.push(n(
            &["close", r],
            "Continue the close; it reconciles and records the end.",
        ));
        (
            "close_unfinished",
            "Close was requested but has not finished; repeat close to continue it.".to_string(),
        )
    } else if matches!(held, Ok(true)) || (held.is_err() && state.open_intake().is_some()) {
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
        closure,
        diagnostics,
        accepted_limits,
    }
}

/// Files no log record names: preparations and intake receipts.
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

pub fn run(reference: &str) -> Reply {
    let audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, vec![]),
    };
    let mut state = log::read(&audit);
    log::sabotage_unknown_as_absent(&mut state);
    let v = view(&audit, &state);
    let allowances = v.accepted_limits.map(|(t, i, o)| {
        let a = |limit: u64| {
            J::obj()
                .with("used", 0u64)
                .with("reported", 0u64)
                .with("estimated", 0u64)
                .with("limit", limit)
        };
        J::obj()
            .with("turns", a(t))
            .with("input_tokens", a(i))
            .with("output_tokens", a(o))
    });
    let mut data = J::obj()
        .with("headline", v.headline)
        .with("condition", v.condition)
        .with("summary", v.summary)
        .with("evidence", J::Arr(v.evidence))
        .with(
            "runs",
            J::obj()
                .with("count", 0u64)
                .with("held", false)
                .with("last", J::Null),
        )
        .with("allowances", allowances)
        .with("answer", J::Null)
        .with("seal", J::Null)
        .with("deliveries", J::Arr(vec![]))
        .with("closure", v.closure)
        .with("diagnostics", J::Arr(v.diagnostics))
        .with("provider_url_override", J::Null)
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
