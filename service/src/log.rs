//! The audit log (INTERFACE 4.4): `log/<n>.json`, n = 1, 2, 3, …, each a
//! linked record whose body's `prev` is the SHA-256 of record n-1.
//!
//! Reading: the log is readable only if its names are exactly `1.json` to
//! `N.json`, every record decodes strictly and the `prev` chain matches.
//! Otherwise it is damaged; the readable prefix before the first bad record
//! is kept for status, and every mutation refuses. Stewart never repairs it.
//!
//! Publishing: read to the end, check the preconditions against that state,
//! write the complete record to a fresh stage file, then `linkat` it to the
//! next number. `EEXIST` means another writer won that number: re-read,
//! re-check and either try the next number or refuse with the state found.

use crate::archive::{Audit, Fail, RECORD_LIMIT, decode_record};
use crate::bodies::{
    Action, CloseRequested, Closed, DeliveryEnded, DeliveryPlanned, EntryRec, Notice, RunEnded,
    RunStarted, SealRec, Version,
};
use crate::fsx::Dir;
use crate::json::{self, J, JsonError, Obj};
use crate::names;
use crate::reply::Cause;
use crate::usage::{Limits, Usage};
use crate::util;

pub const KINDS: [&str; 14] = [
    "reference",
    "prepared",
    "intake_planned",
    "intake_ended",
    "accepted",
    "run_started",
    "entry",
    "seal",
    "run_ended",
    "delivery_planned",
    "delivery_ended",
    "notice",
    "close_requested",
    "closed",
];

pub const INTAKE_OUTCOMES: [&str; 7] = [
    "selection_changed",
    "source_unreadable",
    "capture_failed",
    "capture_unverified",
    "receipt_record_failed",
    "closed",
    "process_gone",
];

#[derive(Debug, Clone)]
pub enum Body {
    Reference {
        folder: String,
    },
    Prepared {
        prep: u64,
        manifest: String,
        manifest_sha256: String,
        arrangement_sha256: String,
        readable_sha256: String,
    },
    IntakePlanned {
        attempt: u64,
        prepared: String,
        prep: u64,
    },
    IntakeEnded {
        attempt: u64,
        outcome: String,
        recorded_by: String,
    },
    Accepted {
        attempt: u64,
        prepared: String,
        prep: u64,
        receipt: String,
        receipt_sha256: String,
    },
    RunStarted(RunStarted),
    RunEnded(RunEnded),
    Entry(EntryRec),
    Seal(SealRec),
    Notice(Notice),
    DeliveryPlanned(DeliveryPlanned),
    DeliveryEnded(DeliveryEnded),
    CloseRequested(CloseRequested),
    Closed(Closed),
}

pub struct LogRec {
    pub n: u64,
    pub kind: String,
    pub at: String,
    pub sha256: String,
    pub body: Body,
    /// The whole decoded record, for presenting recorded facts.
    pub json: json::Json,
    pub ino: (u64, u64),
}

impl LogRec {
    pub fn body_obj(&self) -> Obj<'_> {
        self.json
            .obj("")
            .expect("checked")
            .get("body")
            .expect("checked")
            .obj("/body")
            .expect("checked")
    }
    pub fn name(&self) -> String {
        format!("log/{}.json", self.n)
    }
}

#[derive(Debug, Clone)]
pub struct Bad {
    pub name: String,
    pub problem: String,
}

impl Bad {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("record", self.name.as_str())
            .with("problem", self.problem.as_str())
    }
}

pub struct LogState {
    pub recs: Vec<LogRec>,
    pub damage: Vec<Bad>,
}

pub struct Intake<'a> {
    pub attempt: u64,
    pub planned: &'a LogRec,
    /// The record that gave the intake its outcome: `intake_ended` or `accepted`.
    pub ended: Option<&'a LogRec>,
}

impl<'a> Intake<'a> {
    pub fn outcome(&self) -> Option<&str> {
        match self.ended.map(|r| &r.body) {
            Some(Body::IntakeEnded { outcome, .. }) => Some(outcome),
            Some(Body::Accepted { .. }) => Some("accepted"),
            _ => None,
        }
    }
    pub fn prepared(&self) -> &str {
        match &self.planned.body {
            Body::IntakePlanned { prepared, .. } => prepared,
            _ => "",
        }
    }
}

impl LogState {
    pub fn damaged(&self) -> bool {
        !self.damage.is_empty()
    }
    pub fn last_sha(&self) -> Option<&str> {
        self.recs.last().map(|r| r.sha256.as_str())
    }
    pub fn find(&self, kind: &str) -> Option<&LogRec> {
        self.recs.iter().find(|r| r.kind == kind)
    }
    pub fn accepted(&self) -> Option<&LogRec> {
        self.find("accepted")
    }
    pub fn close_requested(&self) -> Option<&LogRec> {
        self.find("close_requested")
    }
    pub fn closed(&self) -> Option<&LogRec> {
        self.find("closed")
    }
    pub fn launched(&self) -> bool {
        self.find("run_started").is_some()
    }
    pub fn prepared(&self, n: u64) -> Option<&LogRec> {
        self.recs
            .iter()
            .find(|r| matches!(r.body, Body::Prepared { prep, .. } if prep == n))
    }
    pub fn latest_prepared(&self) -> Option<&LogRec> {
        self.recs.iter().rev().find(|r| r.kind == "prepared")
    }
    pub fn intakes(&self) -> Vec<Intake<'_>> {
        let mut out = Vec::new();
        for r in &self.recs {
            if let Body::IntakePlanned { attempt, .. } = r.body {
                let ended = self.recs.iter().find(|e| match &e.body {
                    Body::IntakeEnded { attempt: a, .. } | Body::Accepted { attempt: a, .. } => {
                        *a == attempt
                    }
                    _ => false,
                });
                out.push(Intake {
                    attempt,
                    planned: r,
                    ended,
                });
            }
        }
        out
    }
    /// An intake planned without an outcome (live, or its process is gone).
    pub fn open_intake(&self) -> Option<u64> {
        self.intakes()
            .iter()
            .find(|i| i.ended.is_none())
            .map(|i| i.attempt)
    }
    pub fn bad_j(&self) -> J {
        J::Arr(self.damage.iter().map(|b| b.to_j()).collect())
    }
    pub fn bad_names(&self) -> String {
        self.damage
            .iter()
            .map(|b| format!("{} ({})", b.name, b.problem))
            .collect::<Vec<_>>()
            .join("; ")
    }
}

// ---------------------------------------------------------------------------
// Queries after launch. Every fact here is computed from the records in log
// order, never from a count a record states about itself.

impl LogRec {
    pub fn run_started(&self) -> Option<&RunStarted> {
        match &self.body {
            Body::RunStarted(b) => Some(b),
            _ => None,
        }
    }
    pub fn run_ended(&self) -> Option<&RunEnded> {
        match &self.body {
            Body::RunEnded(b) => Some(b),
            _ => None,
        }
    }
    pub fn entry(&self) -> Option<&EntryRec> {
        match &self.body {
            Body::Entry(b) => Some(b),
            _ => None,
        }
    }
    pub fn seal(&self) -> Option<&SealRec> {
        match &self.body {
            Body::Seal(b) => Some(b),
            _ => None,
        }
    }
    pub fn notice(&self) -> Option<&Notice> {
        match &self.body {
            Body::Notice(b) => Some(b),
            _ => None,
        }
    }
    pub fn delivery_planned(&self) -> Option<&DeliveryPlanned> {
        match &self.body {
            Body::DeliveryPlanned(b) => Some(b),
            _ => None,
        }
    }
    pub fn delivery_ended(&self) -> Option<&DeliveryEnded> {
        match &self.body {
            Body::DeliveryEnded(b) => Some(b),
            _ => None,
        }
    }
    pub fn closed_body(&self) -> Option<&Closed> {
        match &self.body {
            Body::Closed(b) => Some(b),
            _ => None,
        }
    }
}

/// A placement: its `run_started` and, once recorded, its `run_ended`.
pub struct Placement<'a> {
    pub run: u64,
    pub started: &'a LogRec,
    pub start: &'a RunStarted,
    pub ended: Option<(&'a LogRec, &'a RunEnded)>,
}

/// One entry version: the `entry` record that created it, and the version.
#[derive(Clone, Copy)]
pub struct Current<'a> {
    pub record: &'a LogRec,
    pub version: &'a Version,
}

/// Where one entry version stands at the end of the log (7.2, 7.4).
pub enum VersionState<'a> {
    /// No `entry` record created this version.
    Unknown,
    /// The version is in the current selection.
    Current(Current<'a>),
    /// Its entry is current at a later version, `current`.
    Replaced { current: Current<'a> },
    /// Its entry is not in the current selection; `by` is the `delete`
    /// record that removed the entry's last version (the one its target
    /// names, which may be this version or a later one).
    Removed { by: &'a LogRec },
}

/// One delivery attempt: its `delivery_planned` and, once recorded, its
/// `delivery_ended`.
pub struct Delivery<'a> {
    pub attempt: u64,
    pub planned: &'a LogRec,
    pub plan: &'a DeliveryPlanned,
    pub ended: Option<(&'a LogRec, &'a DeliveryEnded)>,
}

impl Delivery<'_> {
    pub fn outcome(&self) -> Option<&str> {
        self.ended.map(|(_, e)| e.outcome.as_str())
    }
    /// Ended `verified` or `verified_with_losses` (5.8).
    pub fn verified(&self) -> bool {
        self.outcome()
            .is_some_and(|o| crate::bodies::VERIFIED_OUTCOMES.contains(&o))
    }
    /// Ended `partial`, `failed` or `name_taken` (8.3).
    pub fn incomplete(&self) -> bool {
        self.outcome()
            .is_some_and(|o| crate::bodies::INCOMPLETE_OUTCOMES.contains(&o))
    }
}

/// What ended authoring (5.7, 7.1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EndedBy {
    /// A `seal` record.
    Seal,
    /// A placement ended `ended_unsubmitted`.
    OrdinaryEnding,
    /// A placement ended `limit_reached`.
    Limit,
    /// A placement ended `damaged`.
    Damage,
    /// A `close_requested` record.
    Close,
}

impl EndedBy {
    /// The `data.ended_by` value of an `authoring_ended` refusal.
    pub fn name(self) -> &'static str {
        match self {
            EndedBy::Seal => "seal",
            EndedBy::OrdinaryEnding => "ordinary_ending",
            EndedBy::Limit => "limit",
            EndedBy::Damage => "damage",
            EndedBy::Close => "close",
        }
    }
}

pub struct AuthoringEnd<'a> {
    pub by: EndedBy,
    /// The record that ended authoring.
    pub record: &'a LogRec,
}

impl LogState {
    /// Every placement in order of its `run_started`.
    pub fn placements(&self) -> Vec<Placement<'_>> {
        let mut out = Vec::new();
        for r in &self.recs {
            if let Some(start) = r.run_started() {
                let ended = self
                    .recs
                    .iter()
                    .find_map(|e| e.run_ended().filter(|b| b.run == start.run).map(|b| (e, b)));
                out.push(Placement {
                    run: start.run,
                    started: r,
                    start,
                    ended,
                });
            }
        }
        out
    }
    pub fn latest_placement(&self) -> Option<Placement<'_>> {
        self.placements().pop()
    }
    /// A placement without `run_ended`: live while a process holds the
    /// active lock, its process gone when the lock is free (4.6).
    pub fn open_placement(&self) -> Option<Placement<'_>> {
        self.placements().into_iter().find(|p| p.ended.is_none())
    }
    /// The placement number the next `run_started` takes.
    pub fn next_run(&self) -> u64 {
        self.placements().last().map_or(1, |p| p.run + 1)
    }

    /// Every `entry` record in log order.
    pub fn entries(&self) -> impl Iterator<Item = (&LogRec, &EntryRec)> {
        self.recs.iter().filter_map(|r| r.entry().map(|e| (r, e)))
    }
    /// The answer revision: the number of `entry` records so far.
    pub fn revision(&self) -> u64 {
        self.entries().count() as u64
    }
    /// The answer revision at log position `n` (records 1 to `n`).
    pub fn revision_through(&self, n: u64) -> u64 {
        self.entries().filter(|(r, _)| r.n <= n).count() as u64
    }
    /// The identifier the next add creates: entries are numbered from 1 in
    /// order of creation.
    pub fn next_entry_id(&self) -> String {
        let adds = self
            .entries()
            .filter(|(_, e)| e.action == Action::Add)
            .count() as u64;
        names::entry_id(adds + 1)
    }
    /// The current selection: every entry added and not since deleted, at
    /// its latest version, in order of first creation.
    pub fn selection(&self) -> Vec<Current<'_>> {
        self.selection_through(u64::MAX)
    }
    /// The selection at log position `n` (records 1 to `n`), such as the
    /// selection current at `close_requested`.
    pub fn selection_through(&self, n: u64) -> Vec<Current<'_>> {
        let mut sel: Vec<Current<'_>> = Vec::new();
        for (r, e) in self.entries().filter(|(r, _)| r.n <= n) {
            match (e.action, &e.created, &e.target) {
                (Action::Add, Some(v), _) => sel.push(Current {
                    record: r,
                    version: v,
                }),
                (Action::Replace, Some(v), _) => {
                    if let Some(slot) = sel.iter_mut().find(|c| c.version.id == v.id) {
                        *slot = Current {
                            record: r,
                            version: v,
                        };
                    }
                }
                (Action::Delete, _, Some(t)) => sel.retain(|c| c.version.id != t.id),
                _ => {}
            }
        }
        sel
    }
    /// The record that created entry version `id`.v`version`, if any.
    pub fn version_created(&self, id: &str, version: u64) -> Option<Current<'_>> {
        self.entries().find_map(|(r, e)| {
            e.created
                .as_ref()
                .filter(|v| v.id == id && v.version == version)
                .map(|v| Current {
                    record: r,
                    version: v,
                })
        })
    }
    /// Where entry version `id`.v`version` stands now.
    pub fn version_state(&self, id: &str, version: u64) -> VersionState<'_> {
        if self.version_created(id, version).is_none() {
            return VersionState::Unknown;
        }
        if let Some(c) = self.selection().into_iter().find(|c| c.version.id == id) {
            return if c.version.version == version {
                VersionState::Current(c)
            } else {
                VersionState::Replaced { current: c }
            };
        }
        match self
            .entries()
            .filter(|(_, e)| {
                e.action == Action::Delete && e.target.as_ref().is_some_and(|t| t.id == id)
            })
            .last()
        {
            Some((r, _)) => VersionState::Removed { by: r },
            None => VersionState::Unknown,
        }
    }

    /// The seal, if one exists. At most one `seal` record is ever published.
    pub fn seal(&self) -> Option<(&LogRec, &SealRec)> {
        self.recs.iter().find_map(|r| r.seal().map(|s| (r, s)))
    }
    /// Every `notice` record in log order.
    pub fn notices(&self) -> Vec<(&LogRec, &Notice)> {
        self.recs
            .iter()
            .filter_map(|r| r.notice().map(|n| (r, n)))
            .collect()
    }
    /// Whether a notice of this type (`reminder`, `near_limit`) has been
    /// used: each is sent at most once per audit, so a published record
    /// uses it whether or not its request was sent (6.4).
    pub fn notice_used(&self, kind: &str) -> bool {
        self.notices().iter().any(|(_, n)| n.kind == kind)
    }
    /// Every delivery attempt in order of its `delivery_planned`.
    pub fn deliveries(&self) -> Vec<Delivery<'_>> {
        let mut out = Vec::new();
        for r in &self.recs {
            if let Some(plan) = r.delivery_planned() {
                let ended = self.recs.iter().find_map(|e| {
                    e.delivery_ended()
                        .filter(|b| b.attempt == plan.attempt)
                        .map(|b| (e, b))
                });
                out.push(Delivery {
                    attempt: plan.attempt,
                    planned: r,
                    plan,
                    ended,
                });
            }
        }
        out
    }
    /// The newest attempt that ended `verified` or `verified_with_losses`.
    pub fn newest_verified(&self) -> Option<Delivery<'_>> {
        self.deliveries().into_iter().rev().find(|d| d.verified())
    }
    /// What ended authoring, if anything has: the earliest seal,
    /// `close_requested`, or placement ending `ended_unsubmitted`,
    /// `limit_reached` or `damaged`.
    pub fn authoring_end(&self) -> Option<AuthoringEnd<'_>> {
        self.recs.iter().find_map(|r| {
            let by = match &r.body {
                Body::Seal(_) => EndedBy::Seal,
                Body::CloseRequested(_) => EndedBy::Close,
                Body::RunEnded(e) => match e.ending.as_str() {
                    "ended_unsubmitted" => EndedBy::OrdinaryEnding,
                    "limit_reached" => EndedBy::Limit,
                    "damaged" => EndedBy::Damage,
                    _ => return None,
                },
                _ => return None,
            };
            Some(AuthoringEnd { by, record: r })
        })
    }
    /// The usage recorded in every `run_ended`. A placement without one is
    /// accounted from its run directory (`runs::account`), and the totals add
    /// that to this.
    pub fn recorded_usage(&self) -> Usage {
        let mut u = Usage::default();
        for r in &self.recs {
            if let Some(e) = r.run_ended() {
                u.add(&e.usage);
            }
        }
        u
    }
    /// The accepted commission's cumulative limits, from the `prepared`
    /// record of the accepted preparation.
    pub fn limits(&self) -> Option<Limits> {
        let prep = match &self.accepted()?.body {
            Body::Accepted { prep, .. } => *prep,
            _ => return None,
        };
        let p = self.prepared(prep)?;
        let l = p.body_obj().obj("settings").ok()?.obj("limits").ok()?;
        Some(Limits {
            turns: l.u64("turns", u64::MAX).ok()?,
            input_tokens: l.u64("input_tokens", u64::MAX).ok()?,
            output_tokens: l.u64("output_tokens", u64::MAX).ok()?,
        })
    }
}

fn decode_body(kind: &str, b: &Obj, audit: &str) -> Result<Body, JsonError> {
    Ok(match kind {
        "reference" => {
            b.only(&["prev", "file", "file_sha256", "folder", "writer"])?;
            b.str("file")?;
            b.str("file_sha256")?;
            let w = b.obj("writer")?;
            w.only(&["path", "sha256"])?;
            w.str("path")?;
            w.str("sha256")?;
            Body::Reference {
                folder: b.str("folder")?.to_string(),
            }
        }
        "prepared" => {
            b.only(&[
                "prev",
                "prep",
                "manifest",
                "manifest_sha256",
                "arrangement_sha256",
                "readable_sha256",
                "settings",
                "question",
                "materials",
            ])?;
            let s = b.obj("settings")?;
            s.only(&[
                "family",
                "model",
                "destination",
                "limits",
                "effort",
                "inquiry",
                "varies",
            ])?;
            s.str("family")?;
            s.str("model")?;
            s.str("destination")?;
            let l = s.obj("limits")?;
            l.only(&["turns", "input_tokens", "output_tokens"])?;
            l.u64("turns", crate::frontmatter::MAX_TURNS)?;
            l.u64("input_tokens", crate::frontmatter::MAX_INPUT_TOKENS)?;
            l.u64("output_tokens", crate::frontmatter::MAX_OUTPUT_TOKENS)?;
            if let Some(e) = s.opt_str("effort")? {
                if !crate::frontmatter::EFFORT_LEVELS.contains(&e) {
                    return Err(s.invalid("effort", "expected an effort level"));
                }
            }
            s.opt_str("inquiry")?;
            s.opt_str("varies")?;
            let q = b.obj("question")?;
            q.only(&["file_bytes", "file_sha256", "body_bytes", "body_sha256"])?;
            let m = b.obj("materials")?;
            m.only(&["count", "bytes"])?;
            Body::Prepared {
                prep: b.u64("prep", u64::MAX)?,
                manifest: b.str("manifest")?.to_string(),
                manifest_sha256: b.str("manifest_sha256")?.to_string(),
                arrangement_sha256: b.str("arrangement_sha256")?.to_string(),
                readable_sha256: b.str("readable_sha256")?.to_string(),
            }
        }
        "intake_planned" => {
            b.only(&[
                "prev",
                "attempt",
                "prepared",
                "prep",
                "declaration",
                "captures",
                "observations",
            ])?;
            let d = b.obj("declaration")?;
            d.only(&["i_am_finished"])?;
            d.bool("i_am_finished")?;
            for (i, c) in b.arr("captures")?.iter().enumerate() {
                let o = c.obj(&format!("/body/captures/{i}"))?;
                o.only(&["item", "file"])?;
                o.str("item")?;
                o.str("file")?;
            }
            b.obj("observations")?;
            Body::IntakePlanned {
                attempt: b.u64("attempt", u64::MAX)?,
                prepared: b.str("prepared")?.to_string(),
                prep: b.u64("prep", u64::MAX)?,
            }
        }
        "intake_ended" => {
            b.only(&[
                "prev",
                "attempt",
                "outcome",
                "recorded_by",
                "message",
                "cause",
                "changes",
            ])?;
            let outcome = b.str("outcome")?;
            if !INTAKE_OUTCOMES.contains(&outcome) {
                return Err(json::value_err(
                    &b.ptr("outcome"),
                    0,
                    format!("unknown intake outcome {outcome:?}"),
                ));
            }
            b.str("message")?;
            b.req("cause")?;
            b.req("changes")?;
            Body::IntakeEnded {
                attempt: b.u64("attempt", u64::MAX)?,
                outcome: outcome.to_string(),
                recorded_by: b.str("recorded_by")?.to_string(),
            }
        }
        "accepted" => {
            b.only(&[
                "prev",
                "attempt",
                "prepared",
                "prep",
                "receipt",
                "receipt_sha256",
            ])?;
            Body::Accepted {
                attempt: b.u64("attempt", u64::MAX)?,
                prepared: b.str("prepared")?.to_string(),
                prep: b.u64("prep", u64::MAX)?,
                receipt: b.str("receipt")?.to_string(),
                receipt_sha256: b.str("receipt_sha256")?.to_string(),
            }
        }
        "run_started" => Body::RunStarted(RunStarted::decode(b)?),
        "run_ended" => Body::RunEnded(RunEnded::decode(b)?),
        "entry" => Body::Entry(EntryRec::decode(b)?),
        "seal" => Body::Seal(SealRec::decode(b)?),
        "notice" => Body::Notice(Notice::decode(b)?),
        "delivery_planned" => Body::DeliveryPlanned(DeliveryPlanned::decode(b, audit)?),
        "delivery_ended" => Body::DeliveryEnded(DeliveryEnded::decode(b)?),
        "close_requested" => Body::CloseRequested(CloseRequested::decode(b)?),
        "closed" => Body::Closed(Closed::decode(b)?),
        other => {
            return Err(json::value_err(
                "/kind",
                0,
                format!("records of kind {other:?} are not log records"),
            ));
        }
    })
}

fn open_log(audit: &Audit) -> Result<Dir, Bad> {
    audit.dir.open_dir("log").map_err(|e| Bad {
        name: "log/".into(),
        problem: format!("cannot be opened: {}", util::describe(&e)),
    })
}

/// Read and validate the whole log.
pub fn read(audit: &Audit) -> LogState {
    let mut state = LogState {
        recs: Vec::new(),
        damage: Vec::new(),
    };
    let dir = match open_log(audit) {
        Ok(d) => d,
        Err(b) => {
            state.damage.push(b);
            return state;
        }
    };
    let names = match dir.names_bounded(usize::MAX) {
        Ok((n, _)) => n,
        Err(e) => {
            state.damage.push(Bad {
                name: "log/".into(),
                problem: format!("cannot be listed: {}", util::describe(&e)),
            });
            return state;
        }
    };
    let mut numbers = Vec::new();
    for raw in &names {
        let s = String::from_utf8_lossy(raw).into_owned();
        let n = s
            .strip_suffix(".json")
            .filter(|d| {
                !d.is_empty() && d.bytes().all(|b| b.is_ascii_digit()) && !d.starts_with('0')
            })
            .and_then(|d| d.parse::<u64>().ok());
        match n {
            Some(n) => numbers.push(n),
            None => state.damage.push(Bad {
                name: format!("log/{s}"),
                problem: "is not a log record name (1.json, 2.json, …)".into(),
            }),
        }
    }
    numbers.sort_unstable();
    let max = numbers.last().copied().unwrap_or(0);
    let mut prev_sha: Option<String> = None;
    // A stray name damages the log but does not hide the records before a
    // gap or a bad record; those remain the readable prefix.
    let mut broken = false;
    for n in 1..=max {
        if numbers.binary_search(&n).is_err() {
            state.damage.push(Bad {
                name: format!("log/{n}.json"),
                problem: format!("is missing while log/{max}.json exists"),
            });
            broken = true;
            continue;
        }
        if broken {
            continue;
        }
        let name = format!("{n}.json");
        let (bytes, st) = match dir.read_regular(&name, RECORD_LIMIT) {
            Ok(x) => x,
            Err(e) => {
                state.damage.push(Bad {
                    name: format!("log/{name}"),
                    problem: format!("cannot be read: {}", e.describe()),
                });
                broken = true;
                continue;
            }
        };
        match decode_log_record(audit, n, &bytes, prev_sha.as_deref()) {
            Ok((kind, at, body, json)) => {
                let sha = util::sha256_hex(&bytes);
                prev_sha = Some(sha.clone());
                state.recs.push(LogRec {
                    n,
                    kind,
                    at,
                    sha256: sha,
                    body,
                    json,
                    ino: st.id(),
                });
            }
            Err(problem) => {
                state.damage.push(Bad {
                    name: format!("log/{name}"),
                    problem,
                });
                broken = true;
            }
        }
    }
    state
}

/// The `unknown_as_absent` sabotage control: readers that decide acceptance
/// treat a damaged log as if its readable prefix were the whole log.
pub fn sabotage_unknown_as_absent(state: &mut LogState) {
    if crate::sabotage!("unknown_as_absent") {
        state.damage.clear();
    }
}

fn decode_log_record(
    audit: &Audit,
    n: u64,
    bytes: &[u8],
    prev: Option<&str>,
) -> Result<(String, String, Body, json::Json), String> {
    let r = decode_record(bytes)?;
    if !KINDS.contains(&r.kind.as_str()) {
        return Err(format!("unknown record kind {:?}", r.kind));
    }
    if r.audit.as_deref() != Some(audit.id.as_str()) {
        return Err("the record names another audit".into());
    }
    let body = r.body();
    let p = body.req("prev").map_err(|e| e.to_string())?;
    match (prev, &p.v) {
        (None, json::V::Null) => {}
        (Some(want), json::V::Str(got)) if got == want => {}
        (None, _) => return Err("record 1 must have prev null".into()),
        (Some(_), _) => {
            return Err(format!(
                "prev does not match the SHA-256 of log/{}.json",
                n - 1
            ));
        }
    }
    if (n == 1) != (r.kind == "reference") {
        return Err("the log begins with exactly one reference record".into());
    }
    let typed = decode_body(&r.kind, &body, &audit.id).map_err(|e| e.to_string())?;
    Ok((r.kind.clone(), r.at.clone(), typed, r.json))
}

/// Stage files whose inode no log record shares: interrupted or lost publications.
pub fn unlinked_stage(audit: &Audit, state: &LogState) -> Vec<String> {
    let Ok(stage) = audit.dir.open_dir("stage") else {
        return Vec::new();
    };
    let Ok(names) = stage.names() else {
        return Vec::new();
    };
    names
        .into_iter()
        .filter(|n| match stage.stat_at(n) {
            Ok(st) => !state.recs.iter().any(|r| r.ino == st.id()),
            Err(_) => true,
        })
        .map(|n| format!("stage/{n}"))
        .collect()
}

// ---------------------------------------------------------------------------
// Publication.

pub enum PubErr {
    /// A precondition failed against the current log.
    Refused(Fail),
    /// The log is damaged; nothing was published.
    Damaged(LogState),
    /// Known not published (the final name was not linked).
    NotPublished(Cause),
    /// Linked, but its durability could not be confirmed.
    Uncertain { n: u64, cause: Cause },
}

pub struct Published {
    pub n: u64,
    pub sha256: String,
    pub at: String,
}

/// Publish one log record of `kind`. `body` checks preconditions against the
/// freshly read log and returns the body members (without `prev`).
pub fn publish<F>(audit: &Audit, kind: &'static str, mut body: F) -> Result<Published, PubErr>
where
    F: FnMut(&LogState) -> Result<J, Fail>,
{
    let log_dir = open_log(audit)
        .map_err(|b| PubErr::NotPublished(Cause::new("open log directory", b.problem)))?;
    let stage_dir = audit.sub("stage").map_err(|e| {
        PubErr::NotPublished(Cause::io("open stage directory", &e).at(audit.abs("stage")))
    })?;
    for _ in 0..100_000 {
        let state = read(audit);
        if state.damaged() {
            return Err(PubErr::Damaged(state));
        }
        let members = match body(&state).map_err(PubErr::Refused)? {
            J::Obj(m) => m,
            _ => Vec::new(),
        };
        let prev = match state.last_sha() {
            Some(s) => J::Str(s.to_string()),
            None => J::Null,
        };
        let mut all = vec![("prev".to_string(), prev)];
        all.extend(members);
        let bytes = audit.record(kind, J::Obj(all));
        let n = state.recs.len() as u64 + 1;
        let stage_name = format!(
            "{}.json",
            crate::ids::random_token()
                .map_err(|e| PubErr::NotPublished(Cause::io("random stage name", &e)))?
        );
        write_stage(&stage_dir, &stage_name, &bytes, kind).map_err(|e| {
            PubErr::NotPublished(
                Cause::io(format!("write stage record ({})", e.step.name()), &e.err)
                    .at(audit.abs(&format!("stage/{stage_name}"))),
            )
        })?;
        crate::fault!("log.publish", kind)
            .map_err(|e| PubErr::NotPublished(Cause::io(format!("link {kind} record"), &e)))?;
        let final_name = format!("{n}.json");
        #[cfg(feature = "sabotage")]
        if crate::sabotage!("rewrite_record_in_place") && n > 1 {
            // Sabotage control: overwrite the current last record in place.
            let tail = format!("{}.json", n - 1);
            stage_dir
                .sabotage_rename_over(&stage_name, &log_dir, &tail)
                .map_err(|e| PubErr::NotPublished(Cause::io("rename record", &e)))?;
            let _ = log_dir.sync();
            return Ok(Published {
                n: n - 1,
                sha256: util::sha256_hex(&bytes),
                at: at_of(&bytes),
            });
        }
        match stage_dir.link_to(&stage_name, &log_dir, &final_name) {
            Ok(()) => {}
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => continue,
            Err(e) => {
                // The link may or may not exist; look before deciding.
                let ours = stage_dir.stat_at(&stage_name).ok().map(|s| s.id());
                let there = log_dir.stat_at(&final_name).ok().map(|s| s.id());
                if ours.is_none() || ours != there {
                    return Err(PubErr::NotPublished(
                        Cause::io(format!("link {kind} record"), &e)
                            .at(audit.abs(&format!("log/{final_name}"))),
                    ));
                }
            }
        }
        // `commission.accepted_dirsync` names the same point as
        // `log.dirsync:accepted`.
        let synced = log_dir.sync().and_then(|_| {
            crate::fault!("log.dirsync", kind)?;
            if kind == "accepted" {
                crate::fault!("commission.accepted_dirsync")
            } else {
                Ok(())
            }
        });
        if let Err(e) = synced {
            return Err(PubErr::Uncertain {
                n,
                cause: Cause::io("fsync log directory", &e).at(audit.abs("log")),
            });
        }
        return Ok(Published {
            n,
            sha256: util::sha256_hex(&bytes),
            at: at_of(&bytes),
        });
    }
    Err(PubErr::NotPublished(Cause::new(
        format!("link {kind} record"),
        "too many concurrent publications",
    )))
}

/// Write a linked record's stage file exclusively (4.3). With the fault
/// point `stage.torn:<kind>` armed, the first half of the bytes is written and
/// synced, then the point's action runs (`kill` leaves a torn stage file);
/// if the process continues, the rest is written.
pub fn write_stage(
    stage: &Dir,
    name: &str,
    bytes: &[u8],
    kind: &str,
) -> Result<(), crate::fsx::WriteError> {
    #[cfg(feature = "fault-injection")]
    if crate::fault_armed!("stage.torn", kind) {
        use crate::fsx::{Step, WriteError};
        use std::io::Write;
        let fail = |step: Step| move |err| WriteError { step, err };
        let mut f = stage.create_excl(name).map_err(fail(Step::Create))?;
        let half = bytes.len() / 2;
        f.write_all(&bytes[..half]).map_err(fail(Step::Write))?;
        f.sync_all().map_err(fail(Step::SyncFile))?;
        crate::fault!("stage.torn", kind).map_err(fail(Step::Write))?;
        f.write_all(&bytes[half..]).map_err(fail(Step::Write))?;
        f.sync_all().map_err(fail(Step::SyncFile))?;
        return stage.sync().map_err(fail(Step::SyncDir));
    }
    #[cfg(not(feature = "fault-injection"))]
    let _ = kind;
    stage.write_excl(name, bytes)
}

fn at_of(bytes: &[u8]) -> String {
    decode_record(bytes).map(|r| r.at).unwrap_or_default()
}

/// Reply data and effects helpers for publication errors.
impl PubErr {
    pub fn describe(&self) -> String {
        match self {
            PubErr::Refused(f) => f.message.clone(),
            PubErr::Damaged(s) => format!("the log is damaged: {}", s.bad_names()),
            PubErr::NotPublished(c) => format!("{} failed: {}", c.operation, c.error),
            PubErr::Uncertain { cause, .. } => {
                format!("{} failed: {}", cause.operation, cause.error)
            }
        }
    }
}

/// The refusal every mutation gives on a damaged log.
pub fn damaged_fail(audit: &Audit, state: &LogState) -> Fail {
    Fail::refused(
        "log_damaged",
        format!(
            "The audit log is damaged ({}). Stewart diagnoses this and never repairs the log or restarts the audit; restore your own storage, or start a new reference.",
            state.bad_names()
        ),
    )
    .data(J::obj().with("bad_records", state.bad_j()))
    .retain(audit.abs("log"))
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::archive::{Archive, RefFile};
    use crate::platform::Exe;

    pub(crate) fn scratch_audit() -> (std::path::PathBuf, Audit) {
        let base = std::fs::canonicalize(std::env::temp_dir()).unwrap();
        let p = base.join(format!(
            "stewart-log-{}",
            crate::ids::random_token().unwrap()
        ));
        std::fs::create_dir_all(p.join("a/log")).unwrap();
        std::fs::create_dir_all(p.join("a/stage")).unwrap();
        let root = Dir::open_follow(p.to_str().unwrap()).unwrap();
        let dir = Dir::open_follow(p.join("a").to_str().unwrap()).unwrap();
        let id = crate::ids::new_id('a').unwrap();
        let audit = Audit {
            archive: Archive {
                root,
                path: p.to_str().unwrap().into(),
                store: "s".into(),
                moved: None,
            },
            id,
            dir,
            reference: String::new(),
            refile: RefFile {
                audit: String::new(),
                store: String::new(),
                folder: String::new(),
                writer_path: "/w".into(),
                writer_sha256: "0".repeat(64),
                at: String::new(),
                sha256: String::new(),
            },
            exe: Some(Exe {
                path: "/w".into(),
                sha256: "0".repeat(64),
            }),
        };
        (p, audit)
    }

    fn reference_body() -> J {
        J::obj()
            .with("file", "REFERENCE.json")
            .with("file_sha256", "0".repeat(64))
            .with("folder", "/f")
            .with(
                "writer",
                J::obj().with("path", "/w").with("sha256", "0".repeat(64)),
            )
    }

    fn close_body() -> J {
        J::obj()
            .with(
                "flags",
                J::obj()
                    .with("confirm", J::Null)
                    .with("surrender", J::Arr(vec![]))
                    .with("destination", J::Null),
            )
            .with("observations", crate::archive::observations())
    }

    #[test]
    fn publishes_a_chain_and_refuses_on_preconditions() {
        let (p, a) = scratch_audit();
        let r1 = publish(&a, "reference", |s| {
            if s.recs.is_empty() {
                Ok(reference_body())
            } else {
                Err(Fail::refused("x", "not empty"))
            }
        })
        .ok()
        .unwrap();
        assert_eq!(r1.n, 1);
        let r2 = publish(&a, "close_requested", |_| Ok(close_body()))
            .ok()
            .unwrap();
        assert_eq!(r2.n, 2);
        let state = read(&a);
        assert!(!state.damaged(), "{}", state.bad_names());
        assert_eq!(state.recs.len(), 2);
        // A second reference is refused by its precondition.
        assert!(matches!(
            publish(&a, "reference", |s| if s.recs.is_empty() {
                Ok(reference_body())
            } else {
                Err(Fail::refused("x", "not empty"))
            }),
            Err(PubErr::Refused(_))
        ));
        // Stage files remain as evidence and share the records' inodes.
        assert!(unlinked_stage(&a, &state).is_empty());
        std::fs::remove_dir_all(p).unwrap();
    }

    #[test]
    fn concurrent_publishers_each_get_their_own_number() {
        let (p, a) = scratch_audit();
        publish(&a, "reference", |_| Ok(reference_body()))
            .ok()
            .unwrap();
        let a = std::sync::Arc::new(a);
        let mut threads = Vec::new();
        for _ in 0..8 {
            let a = a.clone();
            threads.push(std::thread::spawn(move || {
                let mut ns = Vec::new();
                for _ in 0..10 {
                    ns.push(
                        publish(&a, "close_requested", |_| Ok(close_body()))
                            .ok()
                            .unwrap()
                            .n,
                    );
                }
                ns
            }));
        }
        let mut all: Vec<u64> = threads
            .into_iter()
            .flat_map(|t| t.join().unwrap())
            .collect();
        all.sort_unstable();
        assert_eq!(all, (2..=81).collect::<Vec<_>>());
        let state = read(&a);
        assert!(!state.damaged(), "{}", state.bad_names());
        assert_eq!(state.recs.len(), 81);
        // Losers' stage files stay, and are reported as unlinked, never as records.
        let unlinked = unlinked_stage(&a, &state);
        let stage_count = std::fs::read_dir(p.join("a/stage")).unwrap().count();
        assert_eq!(stage_count, 81 + unlinked.len());
        std::fs::remove_dir_all(p).unwrap();
    }

    /// Publish a body after `prev` and return its record number.
    fn put(a: &Audit, kind: &'static str, body: J) -> u64 {
        match publish(a, kind, |_| Ok(body.clone())) {
            Ok(p) => p.n,
            Err(e) => panic!("{kind}: {}", e.describe()),
        }
    }

    fn started(run: u64) -> J {
        RunStarted {
            run,
            arrangement_sha256: "a".repeat(64),
            provider: crate::bodies::ProviderUse {
                base_url: "https://api.anthropic.com".into(),
                overridden: false,
                proxy: None,
                anthropic_version: crate::forms::ANTHROPIC_VERSION.into(),
            },
            observations: crate::bodies::RunObservations::current(),
        }
        .to_j()
    }

    fn ended(run: u64, ending: &str, cause: Option<&str>, seal: Option<&str>, turns: u64) -> J {
        let mut usage = Usage::default();
        usage.turns.reported = turns;
        usage.output_tokens.estimated = 100 * turns;
        RunEnded {
            run,
            ending: ending.into(),
            cause: cause.map(str::to_string),
            recorded_by: "run".into(),
            provider: None,
            requests: turns,
            attempts: turns,
            usage,
            notices: vec![],
            seal: seal.map(str::to_string),
            message: "m".into(),
        }
        .to_j()
    }

    fn edit(
        action: Action,
        id: &str,
        version: u64,
        target: Option<(u64, u64)>,
        revision: u64,
    ) -> J {
        use crate::bodies::{Invocation, Payload, Target};
        let created = (action != Action::Delete).then(|| Version {
            id: id.into(),
            version,
            kind: "record_observation".into(),
            label: String::new(),
            payload: Payload {
                file: crate::names::payload_name(id, version, 1),
                sha256: "b".repeat(64),
                size: 1,
            },
            encoding: None,
            citations: Some(vec![]),
        });
        EntryRec {
            action,
            tool: match action {
                Action::Add => "record_observation",
                Action::Replace => "replace",
                Action::Delete => "delete",
            }
            .into(),
            invocation: Invocation {
                run: 1,
                tool_use_id: format!("toolu_{revision}"),
                call: revision,
            },
            target: target.map(|(v, rec)| Target {
                id: id.into(),
                version: v,
                record: crate::names::log_name(rec),
            }),
            created,
            revision,
        }
        .to_j()
    }

    #[test]
    fn queries_follow_the_records_after_launch() {
        use crate::bodies::{
            Actor, CloseFlags, DeliveryEnded, DeliveryPlanned, Invocation, MemberResult, Notice,
            SealRec,
        };
        let (p, a) = scratch_audit();
        put(&a, "reference", reference_body());
        assert_eq!(put(&a, "run_started", started(1)), 2);
        let e1 = put(&a, "entry", edit(Action::Add, "e1", 1, None, 1));
        put(&a, "entry", edit(Action::Add, "e2", 1, None, 2));
        put(
            &a,
            "entry",
            edit(Action::Replace, "e1", 2, Some((1, e1)), 3),
        );
        let before_e3 = 5;
        put(&a, "entry", edit(Action::Add, "e3", 1, None, 4));
        let del = put(&a, "entry", edit(Action::Delete, "e2", 0, Some((1, 4)), 5));
        let notice = Notice {
            kind: "reminder".into(),
            run: 1,
            request: 3,
            text: crate::forms::REMINDER.into(),
            remaining: None,
        };
        put(&a, "notice", notice.to_j());
        put(
            &a,
            "run_ended",
            ended(1, "interrupted", Some("signal"), None, 2),
        );
        let open = read(&a);
        assert!(
            open.authoring_end().is_none(),
            "an interruption does not end authoring"
        );
        put(&a, "run_started", started(2));
        assert!(read(&a).open_placement().is_some_and(|p| p.run == 2));
        let seal = SealRec {
            actor: Actor::Auditor,
            prepared: 1,
            answer_sha256: "c".repeat(64),
            rendering_sha256: Some("d".repeat(64)),
            revision: 5,
            manifest: "seal/manifest-1.json".into(),
            manifest_sha256: "e".repeat(64),
            invocation: Some(Invocation {
                run: 2,
                tool_use_id: "toolu_s".into(),
                call: 1,
            }),
        };
        let seal_n = put(&a, "seal", seal.to_j());
        put(
            &a,
            "run_ended",
            ended(2, "sealed", None, Some(&crate::names::log_name(seal_n)), 3),
        );
        let planned = |attempt: u64, replaces: Option<u64>| DeliveryPlanned {
            attempt,
            plan_sha256: "f".repeat(64),
            by: "run".into(),
            destination: "/d".into(),
            destination_source: "commissioned".into(),
            package: crate::names::package_name(&a.id, attempt),
            replaces,
        };
        let finished = |attempt: u64, outcome: &str| DeliveryEnded {
            attempt,
            outcome: outcome.into(),
            recorded_by: "run".into(),
            cause: (outcome == "failed").then(|| Cause::new("deliver", "ENOENT")),
            manifest_sha256: "e".repeat(64),
            package: None,
            members: Some(vec![MemberResult {
                name: "manifest.json".into(),
                role: "manifest".into(),
                written: outcome != "failed",
                verified: outcome != "failed",
                failure: None,
            }]),
            losses: Some(vec![]),
        };
        put(&a, "delivery_planned", planned(1, None).to_j());
        put(&a, "delivery_ended", finished(1, "failed").to_j());
        put(&a, "delivery_planned", planned(2, Some(1)).to_j());
        let ended2 = put(&a, "delivery_ended", finished(2, "verified").to_j());
        put(
            &a,
            "close_requested",
            CloseRequested {
                flags: CloseFlags::default(),
            }
            .to_j(),
        );

        let s = read(&a);
        assert!(!s.damaged(), "{}", s.bad_names());
        let ps = s.placements();
        assert_eq!(ps.iter().map(|p| p.run).collect::<Vec<_>>(), [1, 2]);
        assert!(ps.iter().all(|p| p.ended.is_some()));
        assert!(s.open_placement().is_none());
        assert_eq!(s.next_run(), 3);
        assert!(ps[1].start.continuing());

        // Order of first creation; a replace keeps its place; a delete removes.
        let ids = |sel: Vec<Current>| {
            sel.iter()
                .map(|c| format!("{}.v{}", c.version.id, c.version.version))
                .collect::<Vec<_>>()
        };
        assert_eq!(ids(s.selection()), ["e1.v2", "e3.v1"]);
        assert_eq!(ids(s.selection_through(before_e3)), ["e1.v2", "e2.v1"]);
        assert_eq!(s.revision(), 5);
        assert_eq!(s.revision_through(before_e3), 3);
        assert_eq!(s.next_entry_id(), "e4");
        assert!(
            matches!(s.version_state("e1", 1), VersionState::Replaced { current } if current.version.version == 2)
        );
        assert!(matches!(s.version_state("e1", 2), VersionState::Current(_)));
        assert!(matches!(s.version_state("e2", 1), VersionState::Removed { by } if by.n == del));
        assert!(matches!(s.version_state("e9", 1), VersionState::Unknown));
        assert!(matches!(s.version_state("e1", 3), VersionState::Unknown));

        assert!(s.notice_used("reminder"));
        assert!(!s.notice_used("near_limit"));
        assert_eq!(
            s.seal().map(|(r, b)| (r.n, b.actor)),
            Some((seal_n, Actor::Auditor))
        );
        let end = s.authoring_end().expect("sealed");
        assert_eq!(
            (end.by, end.by.name(), end.record.n),
            (EndedBy::Seal, "seal", seal_n)
        );

        let d = s.deliveries();
        assert_eq!(d.len(), 2);
        assert!(d[0].incomplete() && !d[0].verified());
        assert_eq!(d[1].plan.replaces, Some(1));
        assert_eq!(s.newest_verified().map(|d| d.attempt), Some(2));
        let rec2 = &s.recs[ended2 as usize - 1];
        assert_eq!(
            crate::delivery::confirmation(&a, &s, 2),
            Some(crate::ids::cf_handle(
                &a.archive.store,
                &a.id,
                2,
                &"e".repeat(64),
                &rec2.sha256
            ))
        );
        assert_eq!(crate::delivery::confirmation(&a, &s, 1), None);

        let u = s.recorded_usage();
        assert_eq!((u.turns.reported, u.output_tokens.estimated), (5, 500));
        for live in [false, true] {
            let (cumulative, problems) = crate::runs::cumulative_usage(&a, &s, live);
            assert_eq!(cumulative, u, "every placement has its run_ended");
            assert!(problems.is_empty());
        }
        let (_, problems) = crate::runs::cumulative_usage(&a, &s, false);
        assert!(problems.is_empty());
        std::fs::remove_dir_all(p).unwrap();
    }

    #[test]
    fn ordinary_endings_limits_and_damage_end_authoring() {
        for (ending, by) in [
            ("ended_unsubmitted", EndedBy::OrdinaryEnding),
            ("limit_reached", EndedBy::Limit),
            ("damaged", EndedBy::Damage),
        ] {
            let (p, a) = scratch_audit();
            put(&a, "reference", reference_body());
            put(&a, "run_started", started(1));
            let n = put(&a, "run_ended", ended(1, ending, None, None, 1));
            put(&a, "close_requested", close_body());
            let s = read(&a);
            let end = s.authoring_end().unwrap();
            assert_eq!((end.by, end.record.n), (by, n), "{ending}");
            std::fs::remove_dir_all(p).unwrap();
        }
        let (p, a) = scratch_audit();
        put(&a, "reference", reference_body());
        let n = put(&a, "close_requested", close_body());
        let s = read(&a);
        assert_eq!(
            s.authoring_end().map(|e| (e.by, e.record.n)),
            Some((EndedBy::Close, n))
        );
        std::fs::remove_dir_all(p).unwrap();
    }

    #[test]
    fn damage_is_detected_and_named() {
        let (p, a) = scratch_audit();
        publish(&a, "reference", |_| Ok(reference_body()))
            .ok()
            .unwrap();
        publish(&a, "close_requested", |_| Ok(close_body()))
            .ok()
            .unwrap();
        publish(&a, "close_requested", |_| Ok(close_body()))
            .ok()
            .unwrap();
        // A gap: 4.json missing while 5.json exists.
        std::fs::write(p.join("a/log/5.json"), b"{}").unwrap();
        let s = read(&a);
        assert!(s.damaged());
        assert_eq!(s.damage[0].name, "log/4.json");
        assert_eq!(s.recs.len(), 3);
        assert!(matches!(
            publish(&a, "close_requested", |_| Ok(close_body())),
            Err(PubErr::Damaged(_))
        ));
        std::fs::remove_file(p.join("a/log/5.json")).unwrap();
        // A broken prev chain at record 2.
        let two = std::fs::read(p.join("a/log/2.json")).unwrap();
        let mut changed = two.clone();
        let i = changed.windows(6).position(|w| w == b"\"prev\"").unwrap() + 9;
        changed[i] = if changed[i] == b'a' { b'b' } else { b'a' };
        std::fs::remove_file(p.join("a/log/2.json")).unwrap();
        std::fs::write(p.join("a/log/2.json"), &changed).unwrap();
        let s = read(&a);
        assert_eq!(s.damage[0].name, "log/2.json");
        assert!(
            s.damage[0].problem.contains("prev"),
            "{}",
            s.damage[0].problem
        );
        assert_eq!(s.recs.len(), 1);
        // A stray name.
        std::fs::remove_file(p.join("a/log/2.json")).unwrap();
        std::fs::write(p.join("a/log/2.json"), &two).unwrap();
        std::fs::write(p.join("a/log/02.json"), &two).unwrap();
        assert_eq!(read(&a).damage[0].name, "log/02.json");
        std::fs::remove_dir_all(p).unwrap();
    }
}
