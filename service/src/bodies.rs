//! Log record bodies after launch (INTERFACE 4.4, "Record bodies"):
//! `run_started`, `run_ended`, `entry`, `seal`, `notice`, `delivery_planned`,
//! `delivery_ended`, and `close_requested` and `closed` in every state.
//!
//! Each body type writes its members after `prev` in the order the interface
//! lists (`to_j`, for `log::publish`) and decodes strictly (`decode`): every
//! listed key is present, including those whose value may be `null`, no other
//! key is, and each value has its type and comes from its closed set. Facts
//! the interface derives from others (`continuing` from `run`, `dir` from
//! `run`, `plan` from `attempt`, `before_launch` from the record's form) are
//! computed when writing and checked when reading, so a writer cannot record
//! them inconsistently.
//!
//! A body that breaks a rule makes its record unreadable, so the log is
//! damaged (4.4); a decoder never guesses a missing fact. Rules that depend on
//! other records, such as an entry's target or the revision count, belong to
//! the log queries, which compute from the records rather than trusting a
//! recorded count.

use crate::json::{J, JsonError, Obj};
use crate::names;
use crate::reply::Cause;
use crate::usage::{Remaining, Usage};

// ---------------------------------------------------------------------------
// Recorded values (Appendix A).

pub const RUN_ENDINGS: [&str; 6] = [
    "sealed",
    "ended_unsubmitted",
    "limit_reached",
    "stopped_by_close",
    "damaged",
    "interrupted",
];
/// Causes of an `interrupted` ending; every other ending has a null cause.
pub const RUN_CAUSES: [&str; 9] = [
    "signal",
    "provider_unavailable",
    "provider_rejected",
    "context_exhausted",
    "provider_refusal",
    "max_tokens",
    "protocol_anomaly",
    "archive_write_failed",
    "process_gone",
];
/// The causes for which `run_ended.provider` holds the last attempt's facts.
pub const PROVIDER_CAUSES: [&str; 2] = ["provider_unavailable", "provider_rejected"];
/// `recorded_by` of `run_ended` and `delivery_ended` (and `by` of a delivery).
pub const RECORDERS: [&str; 2] = ["run", "close"];
pub const NOTICE_TYPES: [&str; 2] = ["reminder", "near_limit"];
pub const NOTICE_SENT: [&str; 3] = ["sent", "not_sent", "unknown"];
pub const ENCODINGS: [&str; 2] = ["utf-8", "binary"];
pub const ARTIFACT_TOOL: &str = "record_artifact";
pub const DELIVERY_OUTCOMES: [&str; 5] = [
    "verified",
    "verified_with_losses",
    "partial",
    "failed",
    "name_taken",
];
/// Outcomes after which a delivery attempt is incomplete (8.3).
pub const INCOMPLETE_OUTCOMES: [&str; 3] = ["partial", "failed", "name_taken"];
/// Outcomes that make a verified attempt (5.8).
pub const VERIFIED_OUTCOMES: [&str; 2] = ["verified", "verified_with_losses"];
pub const DESTINATION_SOURCES: [&str; 2] = ["commissioned", "replacement"];
/// Roles of return members (8.2) and of delivery members (8.3).
pub const MEMBER_ROLES: [&str; 4] = ["manifest", "answer", "rendering", "artifact"];
pub const MEMBER_FAILURES: [&str; 6] = [
    "source_missing",
    "source_unreadable",
    "source_damaged",
    "write_failed",
    "not_verified",
    "not_attempted",
];
/// Roles a loss can have: an unproduced entry, or a member the return owes.
pub const LOSS_ROLES: [&str; 4] = ["entry", "answer", "rendering", "artifact"];
pub const LOSS_FAILURES: [&str; 4] = ["missing", "unreadable", "damaged", "not_rendered"];
pub const LOSS_STAGES: [&str; 2] = ["seal", "delivery"];
pub const CLOSED_BEFORE_LAUNCH: [&str; 2] = [
    "closed_without_acceptance",
    "closed_after_acceptance_before_launch",
];
pub const CLOSED_AFTER_LAUNCH: [&str; 2] = ["closed_delivered", "closed_with_surrendered_losses"];
pub const PLACEMENTS: [&str; 2] = ["confirmed", "delivered_before_close"];

/// Bound on decoded counts and numbers in bodies.
const NUM_MAX: u64 = 1 << 48;

fn log_ref(o: &Obj, k: &str) -> Result<String, JsonError> {
    let s = o.str(k)?;
    if names::parse_log_name(s).is_none() {
        return Err(o.invalid(k, "expected a log record name, log/<n>.json"));
    }
    Ok(s.to_string())
}

fn log_ref_or_null(o: &Obj, k: &str) -> Result<Option<String>, JsonError> {
    if o.req(k)?.is_null() {
        Ok(None)
    } else {
        log_ref(o, k).map(Some)
    }
}

fn entry_id(o: &Obj, k: &str) -> Result<String, JsonError> {
    let s = o.str(k)?;
    if names::parse_entry_id(s).is_none() {
        return Err(o.invalid(k, "expected an entry ID, e<n>"));
    }
    Ok(s.to_string())
}

fn opt_string(o: &Obj, k: &str) -> Result<Option<String>, JsonError> {
    Ok(o.str_or_null(k)?.map(str::to_string))
}

fn items<'a>(o: &Obj<'a>, k: &str) -> Result<Vec<Obj<'a>>, JsonError> {
    let ptr = o.ptr(k);
    o.arr(k)?
        .iter()
        .enumerate()
        .map(|(i, v)| v.obj(&format!("{ptr}/{i}")))
        .collect()
}

fn opt_items<'a>(o: &Obj<'a>, k: &str) -> Result<Option<Vec<Obj<'a>>>, JsonError> {
    if o.req(k)?.is_null() {
        Ok(None)
    } else {
        items(o, k).map(Some)
    }
}

fn pair(o: &Obj, k: &str) -> Result<(u64, u64), JsonError> {
    let a = o.arr(k)?;
    match a {
        [x, y] => match (x.as_u64(), y.as_u64()) {
            (Some(x), Some(y)) => Ok((x, y)),
            _ => Err(o.invalid(k, "expected two integers")),
        },
        _ => Err(o.invalid(k, "expected two integers")),
    }
}

fn pair_j(p: (u64, u64)) -> J {
    J::Arr(vec![J::Int(p.0), J::Int(p.1)])
}

fn cause_j(c: &Option<Cause>) -> J {
    match c {
        Some(c) => c.to_j(),
        None => J::Null,
    }
}

fn decode_cause(o: &Obj, k: &str) -> Result<Option<Cause>, JsonError> {
    match o.obj_or_null(k)? {
        None => Ok(None),
        Some(c) => {
            c.exactly(&["operation", "error"])?;
            Ok(Some(Cause::new(c.str("operation")?, c.str("error")?)))
        }
    }
}

// ---------------------------------------------------------------------------
// `run_started`.

/// The provider in use for a placement (6.1).
#[derive(Debug, Clone, PartialEq)]
pub struct ProviderUse {
    /// The provider base in use.
    pub base_url: String,
    /// Whether `STEWART_PROVIDER_URL` supplied `base_url`.
    pub overridden: bool,
    /// The `HTTPS_PROXY` value in use, or `None`.
    pub proxy: Option<String>,
    pub anthropic_version: String,
}

/// What Stewart observed about the placement's process: observations only,
/// never identity. `start_ticks` is field 22 of `/proc/self/stat`; it and
/// `host` and `boot_id` are `None` where the platform cannot report them.
#[derive(Debug, Clone, PartialEq)]
pub struct RunObservations {
    pub pid: u64,
    pub start_ticks: Option<u64>,
    pub uid: u64,
    pub host: Option<String>,
    pub boot_id: Option<String>,
}

impl RunObservations {
    /// This process's observations.
    pub fn current() -> RunObservations {
        RunObservations {
            pid: crate::platform::pid() as u64,
            start_ticks: crate::platform::start_ticks(),
            uid: crate::platform::uid() as u64,
            host: crate::platform::host_name(),
            boot_id: crate::platform::boot_id(),
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("pid", self.pid)
            .with("start_ticks", self.start_ticks)
            .with("uid", self.uid)
            .with("host", self.host.as_deref())
            .with("boot_id", self.boot_id.as_deref())
    }
    pub fn decode(o: &Obj) -> Result<RunObservations, JsonError> {
        o.exactly(&["pid", "start_ticks", "uid", "host", "boot_id"])?;
        Ok(RunObservations {
            pid: o.u64("pid", u32::MAX as u64)?,
            start_ticks: o.u64_or_null("start_ticks", u64::MAX)?,
            uid: o.u64("uid", u32::MAX as u64)?,
            host: opt_string(o, "host")?,
            boot_id: opt_string(o, "boot_id")?,
        })
    }
}

/// `run_started`: placement `run` began in `runs/<run>`.
#[derive(Debug, Clone, PartialEq)]
pub struct RunStarted {
    pub run: u64,
    pub arrangement_sha256: String,
    pub provider: ProviderUse,
    pub observations: RunObservations,
}

impl RunStarted {
    /// True when the placement is above 1.
    pub fn continuing(&self) -> bool {
        self.run > 1
    }
    /// The placement's run directory, relative to the audit directory.
    pub fn dir(&self) -> String {
        format!("runs/{}", self.run)
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("run", self.run)
            .with("continuing", self.continuing())
            .with("dir", self.dir())
            .with("arrangement_sha256", self.arrangement_sha256.as_str())
            .with(
                "provider",
                J::obj()
                    .with("base_url", self.provider.base_url.as_str())
                    .with("override", self.provider.overridden)
                    .with("proxy", self.provider.proxy.as_deref())
                    .with(
                        "anthropic_version",
                        self.provider.anthropic_version.as_str(),
                    ),
            )
            .with("observations", self.observations.to_j())
    }
    pub fn decode(b: &Obj) -> Result<RunStarted, JsonError> {
        b.exactly(&[
            "prev",
            "run",
            "continuing",
            "dir",
            "arrangement_sha256",
            "provider",
            "observations",
        ])?;
        let run = b.u64("run", NUM_MAX)?;
        if run == 0 {
            return Err(b.invalid("run", "placements are numbered from 1"));
        }
        if b.bool("continuing")? != (run > 1) {
            return Err(b.invalid(
                "continuing",
                "continuing is true exactly when run is above 1",
            ));
        }
        if b.str("dir")? != format!("runs/{run}") {
            return Err(b.invalid("dir", format!("expected runs/{run}")));
        }
        let p = b.obj("provider")?;
        p.exactly(&["base_url", "override", "proxy", "anthropic_version"])?;
        Ok(RunStarted {
            run,
            arrangement_sha256: b.sha256("arrangement_sha256")?.to_string(),
            provider: ProviderUse {
                base_url: p.str("base_url")?.to_string(),
                overridden: p.bool("override")?,
                proxy: opt_string(&p, "proxy")?,
                anthropic_version: p.str("anthropic_version")?.to_string(),
            },
            observations: RunObservations::decode(&b.obj("observations")?)?,
        })
    }
}

// ---------------------------------------------------------------------------
// `run_ended`.

/// The last attempt's facts for a `provider_unavailable` or
/// `provider_rejected` ending; each fact is `None` when it was not observed.
#[derive(Debug, Clone, PartialEq)]
pub struct ProviderFacts {
    pub status: Option<u64>,
    /// The error body's `error.type`.
    pub error_type: Option<String>,
    /// The error body's `error.message`, cut as in the attempt record: the
    /// provider's own words, reported as given.
    pub error_message: Option<String>,
    /// The `request-id` header, else the error body's `request_id`.
    pub request_id: Option<String>,
    pub request: u64,
    pub attempt: u64,
}

impl ProviderFacts {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("status", self.status)
            .with("error_type", self.error_type.as_deref())
            .with("error_message", self.error_message.as_deref())
            .with("request_id", self.request_id.as_deref())
            .with("request", self.request)
            .with("attempt", self.attempt)
    }
    pub fn decode(o: &Obj) -> Result<ProviderFacts, JsonError> {
        o.exactly(&[
            "status",
            "error_type",
            "error_message",
            "request_id",
            "request",
            "attempt",
        ])?;
        Ok(ProviderFacts {
            status: o.u64_or_null("status", 999)?,
            error_type: opt_string(o, "error_type")?,
            error_message: opt_string(o, "error_message")?,
            request_id: opt_string(o, "request_id")?,
            request: o.u64("request", NUM_MAX)?,
            attempt: o.u64("attempt", NUM_MAX)?,
        })
    }
}

/// One `notice` record published during a placement, as `run_ended` reports it.
#[derive(Debug, Clone, PartialEq)]
pub struct NoticeReport {
    /// `reminder` or `near_limit`.
    pub kind: String,
    /// The `notice` record, `log/<n>.json`.
    pub record: String,
    /// `sent`, `not_sent` or `unknown` (6.4).
    pub sent: String,
}

impl NoticeReport {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("type", self.kind.as_str())
            .with("record", self.record.as_str())
            .with("sent", self.sent.as_str())
    }
    pub fn decode(o: &Obj) -> Result<NoticeReport, JsonError> {
        o.exactly(&["type", "record", "sent"])?;
        Ok(NoticeReport {
            kind: o.one_of("type", &NOTICE_TYPES)?.to_string(),
            record: log_ref(o, "record")?,
            sent: o.one_of("sent", &NOTICE_SENT)?.to_string(),
        })
    }
}

/// `run_ended`: placement `run` ended, and how (6.5).
#[derive(Debug, Clone, PartialEq)]
pub struct RunEnded {
    pub run: u64,
    /// One of `RUN_ENDINGS`.
    pub ending: String,
    /// One of `RUN_CAUSES` for `interrupted`, else `None`.
    pub cause: Option<String>,
    /// `run` or `close`: the operation that published the record.
    pub recorded_by: String,
    /// Present exactly for the causes in `PROVIDER_CAUSES`.
    pub provider: Option<ProviderFacts>,
    /// Complete request captures of the placement.
    pub requests: u64,
    /// Attempt records of the placement.
    pub attempts: u64,
    /// The placement's charge, reported and estimated kept apart.
    pub usage: Usage,
    pub notices: Vec<NoticeReport>,
    /// The `seal` record published during the placement, `log/<n>.json`.
    pub seal: Option<String>,
    /// Prose.
    pub message: String,
}

impl RunEnded {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("run", self.run)
            .with("ending", self.ending.as_str())
            .with("cause", self.cause.as_deref())
            .with("recorded_by", self.recorded_by.as_str())
            .with(
                "provider",
                self.provider.as_ref().map(|p| p.to_j()).unwrap_or(J::Null),
            )
            .with("requests", self.requests)
            .with("attempts", self.attempts)
            .with("usage", self.usage.to_j())
            .with(
                "notices",
                J::Arr(self.notices.iter().map(|n| n.to_j()).collect()),
            )
            .with("seal", self.seal.as_deref())
            .with("message", self.message.as_str())
    }
    pub fn decode(b: &Obj) -> Result<RunEnded, JsonError> {
        b.exactly(&[
            "prev",
            "run",
            "ending",
            "cause",
            "recorded_by",
            "provider",
            "requests",
            "attempts",
            "usage",
            "notices",
            "seal",
            "message",
        ])?;
        let ending = b.one_of("ending", &RUN_ENDINGS)?.to_string();
        let cause = opt_string(b, "cause")?;
        match (&cause, ending.as_str()) {
            (Some(c), "interrupted") if RUN_CAUSES.contains(&c.as_str()) => {}
            (None, e) if e != "interrupted" => {}
            (Some(_), "interrupted") | (None, _) => {
                return Err(b.invalid(
                    "cause",
                    format!(
                        "an interrupted ending names one of: {}",
                        RUN_CAUSES.join(", ")
                    ),
                ));
            }
            (Some(_), _) => {
                return Err(b.invalid("cause", "only an interrupted ending has a cause"));
            }
        }
        let provider = match b.obj_or_null("provider")? {
            Some(p) => Some(ProviderFacts::decode(&p)?),
            None => None,
        };
        let wants_provider = cause
            .as_deref()
            .is_some_and(|c| PROVIDER_CAUSES.contains(&c));
        if provider.is_some() != wants_provider {
            return Err(b.invalid(
                "provider",
                "provider holds the last attempt's facts exactly for provider_unavailable and provider_rejected",
            ));
        }
        let seal = log_ref_or_null(b, "seal")?;
        if ending == "sealed" && seal.is_none() {
            return Err(b.invalid("seal", "a sealed ending names its seal record"));
        }
        let notices = items(b, "notices")?
            .iter()
            .map(NoticeReport::decode)
            .collect::<Result<_, _>>()?;
        Ok(RunEnded {
            run: b.u64("run", NUM_MAX)?,
            ending,
            cause,
            recorded_by: b.one_of("recorded_by", &RECORDERS)?.to_string(),
            provider,
            requests: b.u64("requests", NUM_MAX)?,
            attempts: b.u64("attempts", NUM_MAX)?,
            usage: Usage::decode(&b.obj("usage")?)?,
            notices,
            seal,
            message: b.str("message")?.to_string(),
        })
    }
}

// ---------------------------------------------------------------------------
// `entry`.

/// The tool invocation behind an entry or a seal: the placement, the
/// `tool_use` block's ID and its call number in that placement (4.5).
#[derive(Debug, Clone, PartialEq)]
pub struct Invocation {
    pub run: u64,
    pub tool_use_id: String,
    pub call: u64,
}

impl Invocation {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("run", self.run)
            .with("tool_use_id", self.tool_use_id.as_str())
            .with("call", self.call)
    }
    pub fn decode(o: &Obj) -> Result<Invocation, JsonError> {
        o.exactly(&["run", "tool_use_id", "call"])?;
        Ok(Invocation {
            run: o.u64("run", NUM_MAX)?,
            tool_use_id: o.str("tool_use_id")?.to_string(),
            call: o.u64("call", NUM_MAX)?,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Add,
    Replace,
    Delete,
}

impl Action {
    pub fn name(self) -> &'static str {
        match self {
            Action::Add => "add",
            Action::Replace => "replace",
            Action::Delete => "delete",
        }
    }
}

/// The version an edit replaced or removed, and the record that created it.
#[derive(Debug, Clone, PartialEq)]
pub struct Target {
    pub id: String,
    pub version: u64,
    /// The `entry` record that created this version, `log/<n>.json`.
    pub record: String,
}

impl Target {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("id", self.id.as_str())
            .with("version", self.version)
            .with("record", self.record.as_str())
    }
    pub fn decode(o: &Obj) -> Result<Target, JsonError> {
        o.exactly(&["id", "version", "record"])?;
        Ok(Target {
            id: entry_id(o, "id")?,
            version: o.u64("version", NUM_MAX)?,
            record: log_ref(o, "record")?,
        })
    }
}

/// A stored payload: name, digest and size (7.4).
#[derive(Debug, Clone, PartialEq)]
pub struct Payload {
    /// Audit-relative, `payload/<id>.v<version>[-<i>].bin`.
    pub file: String,
    pub sha256: String,
    pub size: u64,
}

impl Payload {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("file", self.file.as_str())
            .with("sha256", self.sha256.as_str())
            .with("size", self.size)
    }
    pub fn decode(o: &Obj) -> Result<Payload, JsonError> {
        o.exactly(&["file", "sha256", "size"])?;
        Ok(Payload {
            file: o.str("file")?.to_string(),
            sha256: o.sha256("sha256")?.to_string(),
            size: o.u64("size", NUM_MAX)?,
        })
    }
}

impl From<names::StoredPayload> for Payload {
    fn from(s: names::StoredPayload) -> Payload {
        Payload {
            file: s.file,
            sha256: s.sha256,
            size: s.size,
        }
    }
}

/// Stewart's attributed additions to a citation (7.3).
#[derive(Debug, Clone, PartialEq)]
pub struct Located {
    /// The cited source's name.
    pub name: String,
    /// The SHA-256 of the cited source's captured bytes.
    pub sha256: String,
    /// The range Stewart located from a quote; `None` when the auditor gave
    /// the range.
    pub range: Option<(u64, u64)>,
    /// 1-based lines of the first and last cited byte.
    pub lines: (u64, u64),
}

/// A recorded citation (7.3): the auditor's operands at the top level and
/// Stewart's additions under `stewart`. Keys appear in the order `source`,
/// `start`, `end`, `quote`, `stewart` {`name`, `sha256`, `range`, `lines`},
/// absent ones omitted. The same form appears in `answer.json`.
#[derive(Debug, Clone, PartialEq)]
pub struct Citation {
    pub source: String,
    pub start: Option<u64>,
    pub end: Option<u64>,
    pub quote: Option<String>,
    pub stewart: Located,
}

impl Citation {
    pub fn to_j(&self) -> J {
        let mut c = J::obj().with("source", self.source.as_str());
        if let Some(s) = self.start {
            c.push("start", s);
        }
        if let Some(e) = self.end {
            c.push("end", e);
        }
        if let Some(q) = &self.quote {
            c.push("quote", q.as_str());
        }
        let mut s = J::obj()
            .with("name", self.stewart.name.as_str())
            .with("sha256", self.stewart.sha256.as_str());
        if let Some(r) = self.stewart.range {
            s.push("range", pair_j(r));
        }
        s.push("lines", pair_j(self.stewart.lines));
        if crate::sabotage!("grade_support") {
            // Sabotage control: Stewart's additions grade the citation.
            s.push("supports", true);
        }
        c.with("stewart", s)
    }
    pub fn decode(o: &Obj) -> Result<Citation, JsonError> {
        o.only(&["source", "start", "end", "quote", "stewart"])?;
        let start = match o.get("start") {
            Some(_) => Some(o.u64("start", NUM_MAX)?),
            None => None,
        };
        let end = match o.get("end") {
            Some(_) => Some(o.u64("end", NUM_MAX)?),
            None => None,
        };
        let quote = o.opt_str("quote")?.map(str::to_string);
        let s = o.obj("stewart")?;
        let mut known = vec!["name", "sha256", "range", "lines"];
        if crate::sabotage!("grade_support") {
            known.push("supports");
        }
        s.only(&known)?;
        let range = match s.get("range") {
            Some(_) => Some(pair(&s, "range")?),
            None => None,
        };
        let lines = pair(&s, "lines")?;
        match (start, end, &quote, range) {
            (Some(a), Some(b), _, None) if a < b => {}
            (None, None, Some(_), Some((a, b))) if a < b => {}
            _ => {
                return Err(o.invalid(
                    "stewart",
                    "a citation is {source, start, end, quote?} with start < end, or {source, quote} with the range Stewart located",
                ));
            }
        }
        if lines.0 == 0 || lines.0 > lines.1 {
            return Err(s.invalid("lines", "lines are 1-based, first ≤ last"));
        }
        Ok(Citation {
            source: o.str("source")?.to_string(),
            start,
            end,
            quote,
            stewart: Located {
                name: s.str("name")?.to_string(),
                sha256: s.sha256("sha256")?.to_string(),
                range,
                lines,
            },
        })
    }
    /// The cited range: the auditor's, else the one Stewart located.
    pub fn range(&self) -> (u64, u64) {
        match (self.start, self.end, self.stewart.range) {
            (Some(a), Some(b), _) => (a, b),
            (_, _, Some(r)) => r,
            _ => (0, 0),
        }
    }
}

/// The version an add or replace created.
#[derive(Debug, Clone, PartialEq)]
pub struct Version {
    pub id: String,
    pub version: u64,
    /// The record tool's name: `record_<kind>` or `record_artifact`.
    pub kind: String,
    /// As given; `""` when omitted.
    pub label: String,
    pub payload: Payload,
    /// `utf-8` or `binary` for an artifact; `None` otherwise.
    pub encoding: Option<String>,
    /// The recorded citations; `None` for an artifact.
    pub citations: Option<Vec<Citation>>,
}

impl Version {
    pub fn is_artifact(&self) -> bool {
        self.kind == ARTIFACT_TOOL
    }
}

/// `entry`: one add, replace or delete (7.4).
#[derive(Debug, Clone, PartialEq)]
pub struct EntryRec {
    pub action: Action,
    /// The tool that made the edit: the record tool, `replace` or `delete`.
    pub tool: String,
    pub invocation: Invocation,
    /// The replaced or removed version; `None` for an add.
    pub target: Option<Target>,
    /// The version created; `None` for a delete.
    pub created: Option<Version>,
    /// The resulting answer revision.
    pub revision: u64,
}

impl EntryRec {
    pub fn to_j(&self) -> J {
        let v = self.created.as_ref();
        J::obj()
            .with("action", self.action.name())
            .with("tool", self.tool.as_str())
            .with("invocation", self.invocation.to_j())
            .with(
                "target",
                self.target.as_ref().map(|t| t.to_j()).unwrap_or(J::Null),
            )
            .with("id", v.map(|v| v.id.as_str()))
            .with("version", v.map(|v| v.version))
            .with("kind", v.map(|v| v.kind.as_str()))
            .with("label", v.map(|v| v.label.as_str()))
            .with("payload", v.map(|v| v.payload.to_j()).unwrap_or(J::Null))
            .with("encoding", v.and_then(|v| v.encoding.as_deref()))
            .with(
                "citations",
                match v.and_then(|v| v.citations.as_ref()) {
                    Some(cs) => J::Arr(cs.iter().map(|c| c.to_j()).collect()),
                    None => J::Null,
                },
            )
            .with("revision", self.revision)
    }
    pub fn decode(b: &Obj) -> Result<EntryRec, JsonError> {
        b.exactly(&[
            "prev",
            "action",
            "tool",
            "invocation",
            "target",
            "id",
            "version",
            "kind",
            "label",
            "payload",
            "encoding",
            "citations",
            "revision",
        ])?;
        let action = match b.one_of("action", &["add", "replace", "delete"])? {
            "add" => Action::Add,
            "replace" => Action::Replace,
            _ => Action::Delete,
        };
        let tool = b.str("tool")?.to_string();
        let invocation = Invocation::decode(&b.obj("invocation")?)?;
        let target = match b.obj_or_null("target")? {
            Some(t) => Some(Target::decode(&t)?),
            None => None,
        };
        let revision = b.u64("revision", NUM_MAX)?;
        if action == Action::Delete {
            for k in [
                "id",
                "version",
                "kind",
                "label",
                "payload",
                "encoding",
                "citations",
            ] {
                if !b.req(k)?.is_null() {
                    return Err(b.invalid(k, "a delete creates no version, so this is null"));
                }
            }
            if tool != "delete" {
                return Err(b.invalid("tool", "a delete is made by the delete tool"));
            }
            if target.is_none() {
                return Err(b.invalid("target", "a delete names the version it removes"));
            }
            return Ok(EntryRec {
                action,
                tool,
                invocation,
                target,
                created: None,
                revision,
            });
        }
        let id = entry_id(b, "id")?;
        let version = b.u64("version", NUM_MAX)?;
        let kind = b.str("kind")?.to_string();
        let payload = Payload::decode(&b.obj("payload")?)?;
        let encoding = match b.str_or_null("encoding")? {
            Some(_) => Some(b.one_of("encoding", &ENCODINGS)?.to_string()),
            None => None,
        };
        let citations = match b.arr_or_null("citations")? {
            Some(_) => Some(
                items(b, "citations")?
                    .iter()
                    .map(Citation::decode)
                    .collect::<Result<Vec<_>, _>>()?,
            ),
            None => None,
        };
        if !kind.starts_with("record_") {
            return Err(b.invalid("kind", "an entry's kind is the record tool that created it"));
        }
        let artifact = kind == ARTIFACT_TOOL;
        if artifact != encoding.is_some() || artifact == citations.is_some() {
            return Err(b.invalid(
                "encoding",
                "an artifact has an encoding and null citations; another entry has citations and a null encoding",
            ));
        }
        match (action, &target) {
            (Action::Add, None) => {
                if tool != kind {
                    return Err(b.invalid("tool", "an add's tool is its kind"));
                }
                if version != 1 {
                    return Err(b.invalid("version", "an add creates version 1"));
                }
            }
            (Action::Replace, Some(t)) => {
                if tool != "replace" {
                    return Err(b.invalid("tool", "a replace is made by the replace tool"));
                }
                if t.id != id || t.version.checked_add(1) != Some(version) {
                    return Err(b.invalid(
                        "version",
                        "a replace keeps the target's ID and creates its next version",
                    ));
                }
            }
            _ => {
                return Err(b.invalid(
                    "target",
                    "an add has no target; a replace names the version it replaces",
                ));
            }
        }
        if !names::is_payload_name(&payload.file, &id, version) {
            return Err(b.invalid(
                "payload",
                format!("expected payload/{id}.v{version}.bin or a numbered alternative"),
            ));
        }
        Ok(EntryRec {
            action,
            tool,
            invocation,
            target,
            created: Some(Version {
                id,
                version,
                kind,
                label: b.str("label")?.to_string(),
                payload,
                encoding,
                citations,
            }),
            revision,
        })
    }
}

// ---------------------------------------------------------------------------
// `seal`.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Actor {
    /// The auditor's confirmed submit.
    Auditor,
    /// Close, sealing the selection current at its request.
    Manager,
}

impl Actor {
    pub fn name(self) -> &'static str {
        match self {
            Actor::Auditor => "auditor",
            Actor::Manager => "manager",
        }
    }
    fn decode(o: &Obj, k: &str) -> Result<Actor, JsonError> {
        Ok(match o.one_of(k, &["auditor", "manager"])? {
            "auditor" => Actor::Auditor,
            _ => Actor::Manager,
        })
    }
}

/// `seal`: one preparation sealed (8.1).
#[derive(Debug, Clone, PartialEq)]
pub struct SealRec {
    pub actor: Actor,
    /// The sealed `prepared/<n>`.
    pub prepared: u64,
    pub answer_sha256: String,
    /// `None` when the rendering is unproduced.
    pub rendering_sha256: Option<String>,
    /// The sealed selection's answer revision.
    pub revision: u64,
    /// `seal/manifest-<k>.json`.
    pub manifest: String,
    pub manifest_sha256: String,
    /// The submit call; `None` for a manager seal.
    pub invocation: Option<Invocation>,
}

impl SealRec {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("actor", self.actor.name())
            .with("prepared", self.prepared)
            .with("answer_sha256", self.answer_sha256.as_str())
            .with("rendering_sha256", self.rendering_sha256.as_deref())
            .with("revision", self.revision)
            .with("manifest", self.manifest.as_str())
            .with("manifest_sha256", self.manifest_sha256.as_str())
            .with(
                "invocation",
                self.invocation
                    .as_ref()
                    .map(|i| i.to_j())
                    .unwrap_or(J::Null),
            )
    }
    pub fn decode(b: &Obj) -> Result<SealRec, JsonError> {
        b.exactly(&[
            "prev",
            "actor",
            "prepared",
            "answer_sha256",
            "rendering_sha256",
            "revision",
            "manifest",
            "manifest_sha256",
            "invocation",
        ])?;
        let actor = Actor::decode(b, "actor")?;
        let manifest = b.str("manifest")?.to_string();
        if names::parse_manifest_name(&manifest).is_none() {
            return Err(b.invalid("manifest", "expected seal/manifest-<k>.json"));
        }
        let invocation = match b.obj_or_null("invocation")? {
            Some(i) => Some(Invocation::decode(&i)?),
            None => None,
        };
        if actor == Actor::Manager && invocation.is_some() {
            return Err(b.invalid("invocation", "a manager seal has no tool invocation"));
        }
        Ok(SealRec {
            actor,
            prepared: b.u64("prepared", NUM_MAX)?,
            answer_sha256: b.sha256("answer_sha256")?.to_string(),
            rendering_sha256: b.sha256_or_null("rendering_sha256")?.map(str::to_string),
            revision: b.u64("revision", NUM_MAX)?,
            manifest,
            manifest_sha256: b.sha256("manifest_sha256")?.to_string(),
            invocation,
        })
    }
}

// ---------------------------------------------------------------------------
// `notice`.

/// `notice`: the reminder or the near-limit notice, published before the
/// request planned to carry it (6.4).
#[derive(Debug, Clone, PartialEq)]
pub struct Notice {
    /// `reminder` or `near_limit`.
    pub kind: String,
    pub run: u64,
    /// The request of placement `run` planned to carry the text.
    pub request: u64,
    /// The exact text.
    pub text: String,
    /// The remaining amounts for `near_limit`; `None` for the reminder.
    pub remaining: Option<Remaining>,
}

impl Notice {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("type", self.kind.as_str())
            .with("run", self.run)
            .with("request", self.request)
            .with("text", self.text.as_str())
            .with(
                "remaining",
                self.remaining.map(|r| r.to_j()).unwrap_or(J::Null),
            )
    }
    pub fn decode(b: &Obj) -> Result<Notice, JsonError> {
        b.exactly(&["prev", "type", "run", "request", "text", "remaining"])?;
        let kind = b.one_of("type", &NOTICE_TYPES)?.to_string();
        let remaining = match b.obj_or_null("remaining")? {
            Some(r) => Some(Remaining::decode(&r)?),
            None => None,
        };
        if (kind == "near_limit") != remaining.is_some() {
            return Err(b.invalid(
                "remaining",
                "the near-limit notice states the remaining amounts; the reminder has null",
            ));
        }
        Ok(Notice {
            kind,
            run: b.u64("run", NUM_MAX)?,
            request: b.u64("request", NUM_MAX)?,
            text: b.str("text")?.to_string(),
            remaining,
        })
    }
}

// ---------------------------------------------------------------------------
// `delivery_planned` and `delivery_ended`.

/// `delivery_planned`: an attempt's plan was written to `delivery/<attempt>.json`.
#[derive(Debug, Clone, PartialEq)]
pub struct DeliveryPlanned {
    pub attempt: u64,
    pub plan_sha256: String,
    /// `run` or `close`.
    pub by: String,
    /// The destination directory's absolute path.
    pub destination: String,
    /// `commissioned` or `replacement`.
    pub destination_source: String,
    /// The package directory's name, `stewart-return-<audit>-<nnn>`.
    pub package: String,
    /// The attempt this one replaces (8.3).
    pub replaces: Option<u64>,
}

impl DeliveryPlanned {
    /// The plan's audit-relative name.
    pub fn plan(&self) -> String {
        names::plan_name(self.attempt)
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("attempt", self.attempt)
            .with("plan", self.plan())
            .with("plan_sha256", self.plan_sha256.as_str())
            .with("by", self.by.as_str())
            .with("destination", self.destination.as_str())
            .with("destination_source", self.destination_source.as_str())
            .with("package", self.package.as_str())
            .with("replaces", self.replaces)
    }
    pub fn decode(b: &Obj, audit: &str) -> Result<DeliveryPlanned, JsonError> {
        b.exactly(&[
            "prev",
            "attempt",
            "plan",
            "plan_sha256",
            "by",
            "destination",
            "destination_source",
            "package",
            "replaces",
        ])?;
        let attempt = b.u64("attempt", NUM_MAX)?;
        if attempt == 0 {
            return Err(b.invalid("attempt", "delivery attempts are numbered from 1"));
        }
        if b.str("plan")? != names::plan_name(attempt) {
            return Err(b.invalid("plan", format!("expected {}", names::plan_name(attempt))));
        }
        let package = b.str("package")?.to_string();
        if package != names::package_name(audit, attempt) {
            return Err(b.invalid(
                "package",
                format!("expected {}", names::package_name(audit, attempt)),
            ));
        }
        let replaces = b.u64_or_null("replaces", NUM_MAX)?;
        if replaces.is_some_and(|r| r >= attempt) {
            return Err(b.invalid("replaces", "an attempt replaces an earlier attempt"));
        }
        Ok(DeliveryPlanned {
            attempt,
            plan_sha256: b.sha256("plan_sha256")?.to_string(),
            by: b.one_of("by", &RECORDERS)?.to_string(),
            destination: b.str("destination")?.to_string(),
            destination_source: b
                .one_of("destination_source", &DESTINATION_SOURCES)?
                .to_string(),
            package,
            replaces,
        })
    }
}

/// One planned member's result in `delivery_ended.members`.
#[derive(Debug, Clone, PartialEq)]
pub struct MemberResult {
    pub name: String,
    /// One of `MEMBER_ROLES`.
    pub role: String,
    pub written: bool,
    pub verified: bool,
    /// One of `MEMBER_FAILURES`, or `None`.
    pub failure: Option<String>,
}

impl MemberResult {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("name", self.name.as_str())
            .with("role", self.role.as_str())
            .with("written", self.written)
            .with("verified", self.verified)
            .with("failure", self.failure.as_deref())
    }
    pub fn decode(o: &Obj) -> Result<MemberResult, JsonError> {
        o.exactly(&["name", "role", "written", "verified", "failure"])?;
        let failure = match o.str_or_null("failure")? {
            Some(_) => Some(o.one_of("failure", &MEMBER_FAILURES)?.to_string()),
            None => None,
        };
        Ok(MemberResult {
            name: o.str("name")?.to_string(),
            role: o.one_of("role", &MEMBER_ROLES)?.to_string(),
            written: o.bool("written")?,
            verified: o.bool("verified")?,
            failure,
        })
    }
}

/// A member the return owes but an attempt could not supply (8.3).
#[derive(Debug, Clone, PartialEq)]
pub struct Loss {
    /// The entry ID of an unproduced entry, else a member name.
    pub member: String,
    /// One of `LOSS_ROLES`.
    pub role: String,
    /// One of `LOSS_FAILURES`.
    pub failure: String,
    /// `seal` (unproduced at seal) or `delivery` (the archive could not supply it).
    pub stage: String,
}

impl Loss {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("member", self.member.as_str())
            .with("role", self.role.as_str())
            .with("failure", self.failure.as_str())
            .with("stage", self.stage.as_str())
    }
    pub fn decode(o: &Obj) -> Result<Loss, JsonError> {
        o.exactly(&["member", "role", "failure", "stage"])?;
        Ok(Loss {
            member: o.str("member")?.to_string(),
            role: o.one_of("role", &LOSS_ROLES)?.to_string(),
            failure: o.one_of("failure", &LOSS_FAILURES)?.to_string(),
            stage: o.one_of("stage", &LOSS_STAGES)?.to_string(),
        })
    }
}

/// `delivery_ended`: an attempt's outcome (8.3).
#[derive(Debug, Clone, PartialEq)]
pub struct DeliveryEnded {
    pub attempt: u64,
    /// One of `DELIVERY_OUTCOMES`.
    pub outcome: String,
    /// `run` or `close`.
    pub recorded_by: String,
    /// `None` unless the outcome is `failed`, `partial` or `name_taken`.
    pub cause: Option<Cause>,
    /// The seal's manifest digest.
    pub manifest_sha256: String,
    /// The package directory's absolute path, or `None` when none was created.
    pub package: Option<String>,
    /// Following the plan; `None` (with `losses`) when membership is unknown.
    pub members: Option<Vec<MemberResult>>,
    pub losses: Option<Vec<Loss>>,
}

impl DeliveryEnded {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("attempt", self.attempt)
            .with("outcome", self.outcome.as_str())
            .with("recorded_by", self.recorded_by.as_str())
            .with("cause", cause_j(&self.cause))
            .with("manifest_sha256", self.manifest_sha256.as_str())
            .with("package", self.package.as_deref())
            .with(
                "members",
                match &self.members {
                    Some(m) => J::Arr(m.iter().map(|x| x.to_j()).collect()),
                    None => J::Null,
                },
            )
            .with(
                "losses",
                match &self.losses {
                    Some(l) => J::Arr(l.iter().map(|x| x.to_j()).collect()),
                    None => J::Null,
                },
            )
    }
    pub fn decode(b: &Obj) -> Result<DeliveryEnded, JsonError> {
        b.exactly(&[
            "prev",
            "attempt",
            "outcome",
            "recorded_by",
            "cause",
            "manifest_sha256",
            "package",
            "members",
            "losses",
        ])?;
        let outcome = b.one_of("outcome", &DELIVERY_OUTCOMES)?.to_string();
        let cause = decode_cause(b, "cause")?;
        if cause.is_some() && !INCOMPLETE_OUTCOMES.contains(&outcome.as_str()) {
            return Err(b.invalid(
                "cause",
                "a cause is recorded only for failed, partial or name_taken",
            ));
        }
        let members = match opt_items(b, "members")? {
            Some(v) => Some(
                v.iter()
                    .map(MemberResult::decode)
                    .collect::<Result<Vec<_>, _>>()?,
            ),
            None => None,
        };
        let losses = match opt_items(b, "losses")? {
            Some(v) => Some(v.iter().map(Loss::decode).collect::<Result<Vec<_>, _>>()?),
            None => None,
        };
        if members.is_some() != losses.is_some() {
            return Err(b.invalid(
                "losses",
                "members and losses are both null exactly when membership is unknown",
            ));
        }
        Ok(DeliveryEnded {
            attempt: b.u64("attempt", NUM_MAX)?,
            outcome,
            recorded_by: b.one_of("recorded_by", &RECORDERS)?.to_string(),
            cause,
            manifest_sha256: b.sha256("manifest_sha256")?.to_string(),
            package: opt_string(b, "package")?,
            members,
            losses,
        })
    }
}

// ---------------------------------------------------------------------------
// `close_requested` and `closed`.

/// The options of the close call that published `close_requested`.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct CloseFlags {
    pub confirm: Option<String>,
    pub surrender: Vec<String>,
    pub destination: Option<String>,
}

impl CloseFlags {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("confirm", self.confirm.as_deref())
            .with("surrender", crate::json::strs(&self.surrender))
            .with("destination", self.destination.as_deref())
    }
    pub fn decode(o: &Obj) -> Result<CloseFlags, JsonError> {
        o.exactly(&["confirm", "surrender", "destination"])?;
        Ok(CloseFlags {
            confirm: opt_string(o, "confirm")?,
            surrender: o
                .strs("surrender")?
                .into_iter()
                .map(str::to_string)
                .collect(),
            destination: opt_string(o, "destination")?,
        })
    }
}

/// `close_requested`; the same body in every state. `observations` is
/// {`pid`, `uid`, `host`, `boot_id`} (`archive::observations`).
#[derive(Debug, Clone, PartialEq)]
pub struct CloseRequested {
    pub flags: CloseFlags,
}

impl CloseRequested {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("flags", self.flags.to_j())
            .with("observations", crate::archive::observations())
    }
    pub fn decode(b: &Obj) -> Result<CloseRequested, JsonError> {
        b.exactly(&["prev", "flags", "observations"])?;
        let o = b.obj("observations")?;
        o.exactly(&["pid", "uid", "host", "boot_id"])?;
        Ok(CloseRequested {
            flags: CloseFlags::decode(&b.obj("flags")?)?,
        })
    }
}

/// The seal a `closed` record names.
#[derive(Debug, Clone, PartialEq)]
pub struct ClosedSeal {
    /// The `seal` record, `log/<n>.json`.
    pub record: String,
    pub actor: Actor,
    pub manifest_sha256: String,
}

/// The delivery attempt whose placement a `closed` record confirms.
#[derive(Debug, Clone, PartialEq)]
pub struct ClosedDelivery {
    pub attempt: u64,
    /// Its `delivery_ended` record, `log/<n>.json`.
    pub record: String,
    /// `verified` or `verified_with_losses`.
    pub outcome: String,
    /// The package directory's absolute path.
    pub package: String,
}

/// A loss the manager gave up with `--surrender`.
#[derive(Debug, Clone, PartialEq)]
pub struct Surrendered {
    /// The loss ID, `loss.<member token>.<check>`.
    pub loss: String,
    pub member: String,
    pub role: String,
    pub failure: String,
    pub stage: String,
}

impl Surrendered {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("loss", self.loss.as_str())
            .with("member", self.member.as_str())
            .with("role", self.role.as_str())
            .with("failure", self.failure.as_str())
            .with("stage", self.stage.as_str())
    }
    pub fn decode(o: &Obj) -> Result<Surrendered, JsonError> {
        o.exactly(&["loss", "member", "role", "failure", "stage"])?;
        Ok(Surrendered {
            loss: o.str("loss")?.to_string(),
            member: o.str("member")?.to_string(),
            role: o.one_of("role", &LOSS_ROLES)?.to_string(),
            failure: o.one_of("failure", &LOSS_FAILURES)?.to_string(),
            stage: o.one_of("stage", &LOSS_STAGES)?.to_string(),
        })
    }
}

/// The after-launch part of `closed`.
#[derive(Debug, Clone, PartialEq)]
pub struct ClosedAfterLaunch {
    pub seal: ClosedSeal,
    pub delivery: ClosedDelivery,
    /// `confirmed` (by `--confirm`) or `delivered_before_close`.
    pub placement: String,
    /// The confirmation token given, or `None`.
    pub confirmation: Option<String>,
    pub surrendered: Vec<Surrendered>,
    /// The number of placements.
    pub runs: u64,
}

/// `closed`. Before launch the body is `before_launch` (true), `accepted`
/// and `outcome`; after launch it adds the seal, the confirmed delivery, the
/// placement, the confirmation, the surrendered losses and the run count.
#[derive(Debug, Clone, PartialEq)]
pub struct Closed {
    pub accepted: bool,
    /// One of `CLOSED_BEFORE_LAUNCH` or `CLOSED_AFTER_LAUNCH`, matching the form.
    pub outcome: String,
    /// `None` for a close before launch.
    pub after: Option<ClosedAfterLaunch>,
}

impl Closed {
    pub fn before_launch(&self) -> bool {
        self.after.is_none()
    }
    /// A close before launch: its outcome follows from `accepted`.
    pub fn before(accepted: bool) -> Closed {
        Closed {
            accepted,
            outcome: if accepted {
                "closed_after_acceptance_before_launch"
            } else {
                "closed_without_acceptance"
            }
            .to_string(),
            after: None,
        }
    }
    /// A close after launch: its outcome follows from what was surrendered.
    pub fn after(a: ClosedAfterLaunch) -> Closed {
        Closed {
            accepted: true,
            outcome: if a.surrendered.is_empty() {
                "closed_delivered"
            } else {
                "closed_with_surrendered_losses"
            }
            .to_string(),
            after: Some(a),
        }
    }
    pub fn to_j(&self) -> J {
        let o = J::obj()
            .with("before_launch", self.before_launch())
            .with("accepted", self.accepted)
            .with("outcome", self.outcome.as_str());
        let Some(a) = &self.after else {
            return o;
        };
        o.with(
            "seal",
            J::obj()
                .with("record", a.seal.record.as_str())
                .with("actor", a.seal.actor.name())
                .with("manifest_sha256", a.seal.manifest_sha256.as_str()),
        )
        .with(
            "delivery",
            J::obj()
                .with("attempt", a.delivery.attempt)
                .with("record", a.delivery.record.as_str())
                .with("outcome", a.delivery.outcome.as_str())
                .with("package", a.delivery.package.as_str()),
        )
        .with("placement", a.placement.as_str())
        .with("confirmation", a.confirmation.as_deref())
        .with(
            "surrendered",
            J::Arr(a.surrendered.iter().map(|s| s.to_j()).collect()),
        )
        .with("runs", a.runs)
    }
    pub fn decode(b: &Obj) -> Result<Closed, JsonError> {
        if b.bool("before_launch")? {
            b.exactly(&["prev", "before_launch", "accepted", "outcome"])?;
            let accepted = b.bool("accepted")?;
            let want = Closed::before(accepted).outcome;
            if b.one_of("outcome", &CLOSED_BEFORE_LAUNCH)? != want {
                return Err(b.invalid("outcome", format!("expected {want}")));
            }
            return Ok(Closed::before(accepted));
        }
        b.exactly(&[
            "prev",
            "before_launch",
            "accepted",
            "outcome",
            "seal",
            "delivery",
            "placement",
            "confirmation",
            "surrendered",
            "runs",
        ])?;
        if !b.bool("accepted")? {
            return Err(b.invalid("accepted", "a launched audit was accepted"));
        }
        let s = b.obj("seal")?;
        s.exactly(&["record", "actor", "manifest_sha256"])?;
        let d = b.obj("delivery")?;
        d.exactly(&["attempt", "record", "outcome", "package"])?;
        let surrendered = items(b, "surrendered")?
            .iter()
            .map(Surrendered::decode)
            .collect::<Result<Vec<_>, _>>()?;
        let c = Closed::after(ClosedAfterLaunch {
            seal: ClosedSeal {
                record: log_ref(&s, "record")?,
                actor: Actor::decode(&s, "actor")?,
                manifest_sha256: s.sha256("manifest_sha256")?.to_string(),
            },
            delivery: ClosedDelivery {
                attempt: d.u64("attempt", NUM_MAX)?,
                record: log_ref(&d, "record")?,
                outcome: d.one_of("outcome", &VERIFIED_OUTCOMES)?.to_string(),
                package: d.str("package")?.to_string(),
            },
            placement: b.one_of("placement", &PLACEMENTS)?.to_string(),
            confirmation: opt_string(b, "confirmation")?,
            surrendered,
            runs: b.u64("runs", NUM_MAX)?,
        });
        if b.one_of("outcome", &CLOSED_AFTER_LAUNCH)? != c.outcome {
            return Err(b.invalid(
                "outcome",
                "closed_delivered exactly when nothing was surrendered",
            ));
        }
        Ok(c)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json;

    /// Encode a body after `prev`, decode it strictly, and return both.
    fn round<T: PartialEq + std::fmt::Debug>(
        body: J,
        decode: impl Fn(&Obj) -> Result<T, JsonError>,
    ) -> (String, T) {
        let mut all = vec![("prev".to_string(), J::Null)];
        if let J::Obj(m) = body {
            all.extend(m);
        }
        let text = J::Obj(all).string();
        let v = json::parse(text.as_bytes()).unwrap();
        let t = decode(&v.obj("/body").unwrap()).unwrap_or_else(|e| panic!("{e}: {text}"));
        (text, t)
    }

    fn refuses(text: &str, decode: impl Fn(&Obj) -> Result<(), JsonError>) -> String {
        let v = json::parse(text.as_bytes()).unwrap();
        decode(&v.obj("/body").unwrap())
            .expect_err(text)
            .to_string()
    }

    fn h(c: char) -> String {
        c.to_string().repeat(64)
    }

    #[test]
    fn run_started_derives_continuing_and_dir() {
        let r = RunStarted {
            run: 2,
            arrangement_sha256: h('a'),
            provider: ProviderUse {
                base_url: "https://api.anthropic.com".into(),
                overridden: false,
                proxy: None,
                anthropic_version: "2026-10-21".into(),
            },
            observations: RunObservations {
                pid: 4182,
                start_ticks: Some(912873),
                uid: 1000,
                host: Some("ana-laptop".into()),
                boot_id: None,
            },
        };
        let (text, back) = round(r.to_j(), RunStarted::decode);
        assert_eq!(back, r);
        assert_eq!(
            text,
            format!(
                r#"{{"prev":null,"run":2,"continuing":true,"dir":"runs/2","arrangement_sha256":"{}","provider":{{"base_url":"https://api.anthropic.com","override":false,"proxy":null,"anthropic_version":"2026-10-21"}},"observations":{{"pid":4182,"start_ticks":912873,"uid":1000,"host":"ana-laptop","boot_id":null}}}}"#,
                h('a')
            )
        );
        let bad = text.replace(r#""continuing":true"#, r#""continuing":false"#);
        assert!(refuses(&bad, |o| RunStarted::decode(o).map(|_| ())).contains("continuing"));
        let bad = text.replace("runs/2", "runs/3");
        assert!(refuses(&bad, |o| RunStarted::decode(o).map(|_| ())).contains("/dir"));
    }

    #[test]
    fn run_ended_ties_cause_provider_and_seal_to_the_ending() {
        let mut usage = Usage::default();
        usage.turns.reported = 5;
        usage.input_tokens.reported = 412003;
        usage.output_tokens.reported = 18201;
        let r = RunEnded {
            run: 2,
            ending: "interrupted".into(),
            cause: Some("provider_unavailable".into()),
            recorded_by: "run".into(),
            provider: Some(ProviderFacts {
                status: Some(529),
                error_type: Some("overloaded_error".into()),
                error_message: Some("Overloaded".into()),
                request_id: Some("req_011".into()),
                request: 6,
                attempt: 4,
            }),
            requests: 6,
            attempts: 9,
            usage,
            notices: vec![NoticeReport {
                kind: "near_limit".into(),
                record: "log/40.json".into(),
                sent: "not_sent".into(),
            }],
            seal: None,
            message: "The provider was unavailable on 4 attempts of request 6.".into(),
        };
        let (text, back) = round(r.to_j(), RunEnded::decode);
        assert_eq!(back, r);
        assert_eq!(
            text,
            r#"{"prev":null,"run":2,"ending":"interrupted","cause":"provider_unavailable","recorded_by":"run","provider":{"status":529,"error_type":"overloaded_error","error_message":"Overloaded","request_id":"req_011","request":6,"attempt":4},"requests":6,"attempts":9,"usage":{"turns":{"reported":5,"estimated":0},"input_tokens":{"reported":412003,"estimated":0},"output_tokens":{"reported":18201,"estimated":0}},"notices":[{"type":"near_limit","record":"log/40.json","sent":"not_sent"}],"seal":null,"message":"The provider was unavailable on 4 attempts of request 6."}"#
        );
        let dec = |o: &Obj| RunEnded::decode(o).map(|_| ());
        // A cause on an ending that has none, a missing cause, provider facts
        // without a provider cause, a sealed ending without its seal.
        let sealed = text.replace(r#""interrupted""#, r#""sealed""#);
        assert!(refuses(&sealed, dec).contains("/cause"));
        let no_cause = text.replace(r#""provider_unavailable""#, "null");
        assert!(refuses(&no_cause, dec).contains("/cause"));
        let other = text.replace(r#""provider_unavailable""#, r#""signal""#);
        assert!(refuses(&other, dec).contains("/provider"));
        let sealed = text
            .replace(r#""interrupted","cause":"provider_unavailable""#, r#""sealed","cause":null"#)
            .replace(r#""provider":{"status":529,"error_type":"overloaded_error","error_message":"Overloaded","request_id":"req_011","request":6,"attempt":4}"#, r#""provider":null"#);
        assert!(refuses(&sealed, dec).contains("/seal"));
        assert!(
            json::parse(
                sealed
                    .replace(r#""seal":null"#, r#""seal":"log/30.json""#)
                    .as_bytes()
            )
            .map(|v| RunEnded::decode(&v.obj("").unwrap()).is_ok())
            .unwrap()
        );
    }

    fn citation_by_quote() -> Citation {
        Citation {
            source: "materials/src/a.py".into(),
            start: None,
            end: None,
            quote: Some("retry()".into()),
            stewart: Located {
                name: "materials/src/a.py".into(),
                sha256: h('c'),
                range: Some((1210, 1217)),
                lines: (42, 42),
            },
        }
    }

    #[test]
    fn citations_keep_operands_apart_from_stewarts_additions() {
        let c = citation_by_quote();
        assert_eq!(
            c.to_j().string(),
            format!(
                r#"{{"source":"materials/src/a.py","quote":"retry()","stewart":{{"name":"materials/src/a.py","sha256":"{}","range":[1210,1217],"lines":[42,42]}}}}"#,
                h('c')
            )
        );
        let ranged = Citation {
            start: Some(50),
            end: Some(119),
            quote: None,
            stewart: Located {
                range: None,
                lines: (4, 6),
                ..c.stewart.clone()
            },
            ..c.clone()
        };
        for x in [&c, &ranged] {
            let v = json::parse(&x.to_j().bytes()).unwrap();
            assert_eq!(&Citation::decode(&v.obj("").unwrap()).unwrap(), x);
        }
        assert_eq!(ranged.range(), (50, 119));
        assert_eq!(c.range(), (1210, 1217));
        // A range together with a located range, or a quote-only citation
        // without one, is not a recorded citation.
        for bad in [
            r#"{"source":"q","start":1,"end":2,"stewart":{"name":"q","sha256":"S","range":[1,2],"lines":[1,1]}}"#,
            r#"{"source":"q","quote":"x","stewart":{"name":"q","sha256":"S","lines":[1,1]}}"#,
            r#"{"source":"q","start":2,"end":2,"stewart":{"name":"q","sha256":"S","lines":[1,1]}}"#,
            r#"{"source":"q","start":1,"end":2,"stewart":{"name":"q","sha256":"S","lines":[1,1],"supports":true}}"#,
        ] {
            let t = bad.replace('S', &h('d'));
            let v = json::parse(t.as_bytes()).unwrap();
            assert!(Citation::decode(&v.obj("").unwrap()).is_err(), "{t}");
        }
    }

    fn entry(action: Action) -> EntryRec {
        let target = Target {
            id: "e2".into(),
            version: 1,
            record: "log/9.json".into(),
        };
        let created = Version {
            id: "e2".into(),
            version: if action == Action::Add { 1 } else { 2 },
            kind: "record_observation".into(),
            label: "restart duplicate".into(),
            payload: Payload {
                file: "payload/e2.v2.bin".into(),
                sha256: h('b'),
                size: 132,
            },
            encoding: None,
            citations: Some(vec![citation_by_quote()]),
        };
        match action {
            Action::Add => EntryRec {
                action,
                tool: "record_observation".into(),
                invocation: Invocation {
                    run: 2,
                    tool_use_id: "toolu_01A".into(),
                    call: 14,
                },
                target: None,
                created: Some(Version {
                    payload: Payload {
                        file: "payload/e2.v1.bin".into(),
                        ..created.payload.clone()
                    },
                    ..created
                }),
                revision: 8,
            },
            Action::Replace => EntryRec {
                action,
                tool: "replace".into(),
                invocation: Invocation {
                    run: 2,
                    tool_use_id: "toolu_01A".into(),
                    call: 14,
                },
                target: Some(target),
                created: Some(created),
                revision: 8,
            },
            Action::Delete => EntryRec {
                action,
                tool: "delete".into(),
                invocation: Invocation {
                    run: 2,
                    tool_use_id: "toolu_01A".into(),
                    call: 14,
                },
                target: Some(target),
                created: None,
                revision: 8,
            },
        }
    }

    #[test]
    fn entry_bodies_follow_the_action_table() {
        for a in [Action::Add, Action::Replace, Action::Delete] {
            let e = entry(a);
            let (_, back) = round(e.to_j(), EntryRec::decode);
            assert_eq!(back, e);
        }
        let (text, _) = round(entry(Action::Replace).to_j(), EntryRec::decode);
        assert_eq!(
            text,
            format!(
                r#"{{"prev":null,"action":"replace","tool":"replace","invocation":{{"run":2,"tool_use_id":"toolu_01A","call":14}},"target":{{"id":"e2","version":1,"record":"log/9.json"}},"id":"e2","version":2,"kind":"record_observation","label":"restart duplicate","payload":{{"file":"payload/e2.v2.bin","sha256":"{}","size":132}},"encoding":null,"citations":[{}],"revision":8}}"#,
                h('b'),
                citation_by_quote().to_j().string()
            )
        );
        let (del, _) = round(entry(Action::Delete).to_j(), EntryRec::decode);
        assert!(del.contains(r#""id":null,"version":null,"kind":null,"label":null,"payload":null,"encoding":null,"citations":null,"revision":8"#));
        let dec = |o: &Obj| EntryRec::decode(o).map(|_| ());
        // The replaced version must be the target's next one.
        assert!(
            refuses(&text.replace(r#""version":2"#, r#""version":3"#), dec).contains("version")
        );
        // The payload name belongs to the version created.
        assert!(refuses(&text.replace("e2.v2.bin", "e2.v1.bin"), dec).contains("payload"));
        // An artifact has an encoding and no citations.
        let artifact = Version {
            kind: ARTIFACT_TOOL.into(),
            encoding: Some("binary".into()),
            citations: None,
            ..entry(Action::Add).created.unwrap()
        };
        let a = EntryRec {
            tool: ARTIFACT_TOOL.into(),
            created: Some(artifact),
            ..entry(Action::Add)
        };
        let (atext, back) = round(a.to_j(), EntryRec::decode);
        assert_eq!(back, a);
        assert!(
            refuses(
                &atext.replace(r#""citations":null"#, r#""citations":[]"#),
                dec
            )
            .contains("encoding")
        );
    }

    #[test]
    fn seal_notice_and_delivery_bodies_round_trip() {
        let s = SealRec {
            actor: Actor::Auditor,
            prepared: 3,
            answer_sha256: h('1'),
            rendering_sha256: None,
            revision: 7,
            manifest: "seal/manifest-1.json".into(),
            manifest_sha256: h('2'),
            invocation: Some(Invocation {
                run: 2,
                tool_use_id: "toolu_01B".into(),
                call: 31,
            }),
        };
        let (text, back) = round(s.to_j(), SealRec::decode);
        assert_eq!(back, s);
        assert!(text.starts_with(r#"{"prev":null,"actor":"auditor","prepared":3,"#));
        let manager_with_call = text.replace(r#""auditor""#, r#""manager""#);
        assert!(
            refuses(&manager_with_call, |o| SealRec::decode(o).map(|_| ())).contains("invocation")
        );

        let n = Notice {
            kind: "near_limit".into(),
            run: 2,
            request: 9,
            text: "Allowance notice: 40 turns".into(),
            remaining: Some(Remaining {
                turns: 40,
                input_tokens: 3900000,
                output_tokens: 79000,
            }),
        };
        let (text, back) = round(n.to_j(), Notice::decode);
        assert_eq!(back, n);
        assert_eq!(
            text,
            r#"{"prev":null,"type":"near_limit","run":2,"request":9,"text":"Allowance notice: 40 turns","remaining":{"turns":40,"input_tokens":3900000,"output_tokens":79000}}"#
        );
        let reminder_with_amounts = text.replace(r#""near_limit""#, r#""reminder""#);
        assert!(
            refuses(&reminder_with_amounts, |o| Notice::decode(o).map(|_| ()))
                .contains("remaining")
        );

        let audit = "aqm3x7kd2hz5vw4ny";
        let p = DeliveryPlanned {
            attempt: 3,
            plan_sha256: h('3'),
            by: "close".into(),
            destination: "/home/ana/returns2".into(),
            destination_source: "replacement".into(),
            package: names::package_name(audit, 3),
            replaces: Some(2),
        };
        let (text, back) = round(p.to_j(), |o| DeliveryPlanned::decode(o, audit));
        assert_eq!(back, p);
        assert_eq!(
            text,
            format!(
                r#"{{"prev":null,"attempt":3,"plan":"delivery/3.json","plan_sha256":"{}","by":"close","destination":"/home/ana/returns2","destination_source":"replacement","package":"stewart-return-aqm3x7kd2hz5vw4ny-003","replaces":2}}"#,
                h('3')
            )
        );
        assert!(
            refuses(&text, |o| DeliveryPlanned::decode(o, "aother0000000000")
                .map(|_| ()))
            .contains("package")
        );

        let e = DeliveryEnded {
            attempt: 1,
            outcome: "verified_with_losses".into(),
            recorded_by: "close".into(),
            cause: None,
            manifest_sha256: h('4'),
            package: Some("/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001".into()),
            members: Some(vec![MemberResult {
                name: "manifest.json".into(),
                role: "manifest".into(),
                written: true,
                verified: true,
                failure: None,
            }]),
            losses: Some(vec![Loss {
                member: "e3".into(),
                role: "entry".into(),
                failure: "damaged".into(),
                stage: "seal".into(),
            }]),
        };
        let (text, back) = round(e.to_j(), DeliveryEnded::decode);
        assert_eq!(back, e);
        let with_cause = text.replace(
            r#""cause":null"#,
            r#""cause":{"operation":"deliver","error":"process_gone"}"#,
        );
        assert!(refuses(&with_cause, |o| DeliveryEnded::decode(o).map(|_| ())).contains("cause"));
        let unknown = DeliveryEnded {
            outcome: "failed".into(),
            cause: Some(Cause::new("deliver", "manifest_unavailable")),
            package: None,
            members: None,
            losses: None,
            ..e
        };
        let (text, back) = round(unknown.to_j(), DeliveryEnded::decode);
        assert_eq!(back, unknown);
        let half = text.replacen(r#""losses":null"#, r#""losses":[]"#, 1);
        assert!(refuses(&half, |o| DeliveryEnded::decode(o).map(|_| ())).contains("losses"));
    }

    #[test]
    fn closed_bodies_derive_their_outcome() {
        let (text, back) = round(Closed::before(true).to_j(), Closed::decode);
        assert_eq!(back, Closed::before(true));
        assert_eq!(
            text,
            r#"{"prev":null,"before_launch":true,"accepted":true,"outcome":"closed_after_acceptance_before_launch"}"#
        );
        let after = Closed::after(ClosedAfterLaunch {
            seal: ClosedSeal {
                record: "log/22.json".into(),
                actor: Actor::Manager,
                manifest_sha256: h('5'),
            },
            delivery: ClosedDelivery {
                attempt: 1,
                record: "log/24.json".into(),
                outcome: "verified_with_losses".into(),
                package: "/home/ana/returns/stewart-return-aqm3x7kd2hz5vw4ny-001".into(),
            },
            placement: "confirmed".into(),
            confirmation: Some("cf1.h3d7ws".into()),
            surrendered: vec![Surrendered {
                loss: "loss.e3.p6w2ze".into(),
                member: "e3".into(),
                role: "entry".into(),
                failure: "damaged".into(),
                stage: "seal".into(),
            }],
            runs: 2,
        });
        assert_eq!(after.outcome, "closed_with_surrendered_losses");
        let (text, back) = round(after.to_j(), Closed::decode);
        assert_eq!(back, after);
        assert!(text.starts_with(r#"{"prev":null,"before_launch":false,"accepted":true,"outcome":"closed_with_surrendered_losses","seal":{"record":"log/22.json","actor":"manager","#));
        let wrong = text.replace("closed_with_surrendered_losses", "closed_delivered");
        assert!(refuses(&wrong, |o| Closed::decode(o).map(|_| ())).contains("outcome"));
        let short =
            r#"{"prev":null,"before_launch":false,"accepted":true,"outcome":"closed_delivered"}"#;
        assert!(refuses(short, |o| Closed::decode(o).map(|_| ())).contains("missing"));
    }
}
