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
use crate::fsx::Dir;
use crate::json::{self, J, JsonError, Obj};
use crate::reply::Cause;
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
    CloseRequested,
    Closed {
        before_launch: bool,
        accepted: bool,
    },
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

fn decode_body(kind: &str, b: &Obj) -> Result<Body, JsonError> {
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
        "close_requested" => {
            b.only(&["prev", "flags", "observations"])?;
            let f = b.obj("flags")?;
            f.only(&["confirm", "surrender", "destination"])?;
            f.str_or_null("confirm")?;
            f.strs("surrender")?;
            f.str_or_null("destination")?;
            b.obj("observations")?;
            Body::CloseRequested
        }
        "closed" => {
            b.only(&["prev", "before_launch", "accepted", "outcome"])?;
            b.str("outcome")?;
            Body::Closed {
                before_launch: b.bool("before_launch")?,
                accepted: b.bool("accepted")?,
            }
        }
        other => {
            return Err(json::value_err(
                "/kind",
                0,
                format!(
                    "records of kind {other:?} are not supported by this writer, which writes only the manager-foundation kinds"
                ),
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
    let typed = decode_body(&r.kind, &body).map_err(|e| e.to_string())?;
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
        stage_dir.write_excl(&stage_name, &bytes).map_err(|e| {
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
        let synced = log_dir.sync().and_then(|_| {
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
mod tests {
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
            .with("observations", J::obj())
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
