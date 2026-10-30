//! What every tool shares: the call context, the account a tool returns,
//! the authoring check, entry handles and the selection, payload checks and
//! cursors.

use super::{Call, End, Placement};
use crate::archive::{Audit, Fail};
use crate::bodies::{Citation, Payload};
use crate::fsx::ReadError;
use crate::ids;
use crate::json::J;
use crate::log::{EndedBy, LogState, VersionState};
use crate::reply::ToolNext;
use crate::util;
use crate::world::World;

/// The call being executed and what it was given.
pub struct Ctx<'a> {
    pub audit: &'a Audit,
    pub world: &'a World,
    pub placement: &'a Placement,
    pub call: &'a Call<'a>,
    /// The tool's name, one of the arrangement's tools.
    pub tool: &'static str,
    /// The log as read when the call began.
    pub state: LogState,
}

impl Ctx<'_> {
    pub fn store(&self) -> &str {
        &self.audit.archive.store
    }
    pub fn audit_id(&self) -> &str {
        &self.audit.id
    }
    /// A handle of `kind` for `object`, bound to `binding` (2.3).
    pub fn handle(&self, kind: &str, object: &str, binding: &[&str]) -> String {
        ids::handle(self.store(), self.audit_id(), kind, object, binding)
    }
}

/// What a tool did, before it becomes an envelope and content.
pub struct Out {
    /// The reply's data, or the refusal or failure.
    pub result: Result<J, Fail>,
    /// The `answer` effect of an edit tool.
    pub answer: &'static str,
    /// The `seal` effect of `submit`.
    pub seal: &'static str,
    /// The auditor next calls, on completion and refusal alike.
    pub next: Vec<ToolNext>,
    /// The exact text for a second text block (7.1).
    pub text: Option<String>,
    pub log_record: Option<String>,
    pub sealed: bool,
    pub end: Option<End>,
    /// The revision after the call when the tool knows it; otherwise the
    /// log is read again.
    pub revision: Option<u64>,
}

impl Out {
    pub fn done(data: J) -> Out {
        Out {
            result: Ok(data),
            answer: "unchanged",
            seal: "none",
            next: Vec::new(),
            text: None,
            log_record: None,
            sealed: false,
            end: None,
            revision: None,
        }
    }
    pub fn fail(f: Fail) -> Out {
        Out {
            result: Err(f),
            ..Out::done(J::Null)
        }
    }
    pub fn next(mut self, n: ToolNext) -> Out {
        self.next.push(n);
        self
    }
    pub fn end(mut self, e: End) -> Out {
        self.end = Some(e);
        self
    }
}

impl From<Fail> for Out {
    fn from(f: Fail) -> Out {
        Out::fail(f)
    }
}

pub fn refused(reason: &'static str, message: impl Into<String>) -> Fail {
    Fail::refused(reason, message)
}

/// The refusal of every mutation after a seal or close (7.1): what ended
/// authoring and, if a seal exists, who sealed.
pub fn authoring_ended(ctx: &Ctx, state: &LogState) -> Option<Fail> {
    let end = state.authoring_end()?;
    if !matches!(end.by, EndedBy::Seal | EndedBy::Close) {
        // A placement's ending is recorded only after its last call.
        return None;
    }
    Some(ended_fail(ctx, state, end.by, end.record.n))
}

pub fn ended_fail(ctx: &Ctx, state: &LogState, by: EndedBy, n: u64) -> Fail {
    let seal = state.seal();
    let close = state.close_requested();
    let what = match by {
        EndedBy::Close => format!("the manager requested close (log/{n}.json) before any seal"),
        _ => match seal.map(|(_, s)| s.actor.name()) {
            Some(a) => format!("the answer was sealed by the {a} (log/{n}.json)"),
            None => format!("authoring ended (log/{n}.json)"),
        },
    };
    let sealed_by = seal.map(|(_, s)| {
        if by == EndedBy::Close {
            format!(" It was sealed afterwards by the {}.", s.actor.name())
        } else {
            String::new()
        }
    });
    refused(
        "authoring_ended",
        format!(
            "Authoring has ended: {what}, so the answer cannot change.{}",
            sealed_by.unwrap_or_default()
        ),
    )
    .data(
        J::obj()
            .with("ended_by", by.name())
            .with("record", crate::names::log_name(n))
            .with("close_requested_at", close.map(|c| c.at.as_str()))
            .with(
                "seal",
                seal.map(|(_, s)| {
                    ids::seal_handle(ctx.store(), ctx.audit_id(), &s.manifest_sha256)
                }),
            )
            .with("sealer", seal.map(|(_, s)| s.actor.name())),
    )
}

// ---------------------------------------------------------------------------
// The selection the tools see.

/// One entry version as the tools see it.
#[derive(Debug, Clone)]
pub struct Item {
    pub id: String,
    pub version: u64,
    /// The recording tool.
    pub kind: String,
    pub label: String,
    pub payload: Payload,
    pub encoding: Option<String>,
    pub citations: Option<Vec<Citation>>,
    /// The `entry` record that created the version and its SHA-256.
    pub record: u64,
    pub record_sha256: String,
}

impl Item {
    pub fn is_artifact(&self) -> bool {
        self.kind == crate::bodies::ARTIFACT_TOOL
    }
    pub fn is_binary(&self) -> bool {
        self.encoding.as_deref() == Some("binary")
    }
    pub fn handle(&self, audit: &Audit) -> String {
        ids::entry_handle(
            &audit.archive.store,
            &audit.id,
            &self.id,
            self.version,
            &self.record_sha256,
        )
    }
}

fn item(c: &crate::log::Current) -> Item {
    let v = c.version;
    Item {
        id: v.id.clone(),
        version: v.version,
        kind: v.kind.clone(),
        label: v.label.clone(),
        payload: v.payload.clone(),
        encoding: v.encoding.clone(),
        citations: v.citations.clone(),
        record: c.record.n,
        record_sha256: c.record.sha256.clone(),
    }
}

/// The selection at log position `through`, in order of first creation.
/// `placement` is the placement whose tools see it, if any.
pub fn selection(
    audit: &Audit,
    state: &LogState,
    through: u64,
    placement: Option<&Placement>,
) -> Vec<Item> {
    let mut items: Vec<Item> = state.selection_through(through).iter().map(item).collect();
    if crate::sabotage!("fresh_ledger_on_continuation") {
        // Sabotage control: a continuing placement ignores entries recorded
        // before its run_started.
        if let Some(p) = placement.filter(|p| p.continuing) {
            let start = state
                .placements()
                .iter()
                .find(|x| x.run == p.run)
                .map_or(0, |x| x.started.n);
            items.retain(|i| i.record > start);
        }
    }
    if crate::sabotage!("torn_as_entry") {
        items.extend(torn_entries(audit, state));
    }
    items
}

/// Adds staged but never linked (the `torn_as_entry` sabotage control only).
fn torn_entries(audit: &Audit, state: &LogState) -> Vec<Item> {
    let Ok(stage) = audit.dir.open_dir("stage") else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for name in crate::log::unlinked_stage(audit, state) {
        let Some(file) = name.strip_prefix("stage/") else {
            continue;
        };
        let Ok((bytes, _)) = stage.read_regular(file, crate::archive::RECORD_LIMIT) else {
            continue;
        };
        let Ok(r) = crate::archive::decode_record(&bytes) else {
            continue;
        };
        if r.kind != "entry" {
            continue;
        }
        if let Ok(e) = crate::bodies::EntryRec::decode(&r.body()) {
            if let Some(v) = e.created.filter(|_| e.action == crate::bodies::Action::Add) {
                out.push(Item {
                    id: v.id.clone(),
                    version: v.version,
                    kind: v.kind.clone(),
                    label: v.label.clone(),
                    payload: v.payload.clone(),
                    encoding: v.encoding.clone(),
                    citations: v.citations.clone(),
                    record: 0,
                    record_sha256: util::sha256_hex(&bytes),
                });
            }
        }
    }
    out
}

/// What a presented entry handle names.
pub enum Named<'a> {
    Current(Item),
    /// Replaced: the current version.
    Replaced(Item),
    /// Removed by this `delete` record.
    Removed(&'a crate::log::LogRec),
}

/// Resolve an entry handle: its shape, its record and its check. A handle
/// of the wrong shape, store or audit, or with a wrong check, is refused
/// `handle_invalid` without revealing whether a similar object exists.
pub fn resolve<'a>(ctx: &Ctx, state: &'a LogState, handle: &str) -> Result<Named<'a>, Fail> {
    let invalid = || {
        refused(
            "handle_invalid",
            format!(
                "{handle:?} is not an entry handle of this audit. Use handles exactly as tools return them."
            ),
        )
    };
    let (id, version) = ids::parse_entry_handle(handle).ok_or_else(invalid)?;
    let created = state.version_created(id, version).ok_or_else(invalid)?;
    if ids::entry_handle(
        ctx.store(),
        ctx.audit_id(),
        id,
        version,
        &created.record.sha256,
    ) != handle
    {
        return Err(invalid());
    }
    Ok(match state.version_state(id, version) {
        VersionState::Current(c) => Named::Current(item(&c)),
        VersionState::Replaced { current } => Named::Replaced(item(&current)),
        VersionState::Removed { by } => Named::Removed(by),
        VersionState::Unknown => return Err(invalid()),
    })
}

// ---------------------------------------------------------------------------
// Payloads.

/// Why a payload could not be supplied: `missing`, `unreadable` or `damaged`.
pub type Failure = &'static str;

/// Read a payload and check its size and digest.
pub fn read_payload(audit: &Audit, p: &Payload) -> Result<Vec<u8>, Failure> {
    let Some(name) = p.file.strip_prefix("payload/") else {
        return Err("damaged");
    };
    let dir = match audit.dir.open_dir("payload") {
        Ok(d) => d,
        Err(e) if e.raw_os_error() == Some(libc::ENOENT) => return Err("missing"),
        Err(_) => return Err("unreadable"),
    };
    match dir.read_regular(name, p.size.saturating_add(1)) {
        Ok((b, _)) if b.len() as u64 == p.size && util::sha256_hex(&b) == p.sha256 => Ok(b),
        Ok(_) | Err(ReadError::TooLarge { .. }) => Err("damaged"),
        Err(ReadError::Missing) => Err("missing"),
        Err(_) => Err("unreadable"),
    }
}

/// Up to `max` leading bytes of a payload, without checking its digest
/// (re-entry previews).
pub fn payload_head(audit: &Audit, p: &Payload, max: u64) -> Result<Vec<u8>, Failure> {
    use std::io::Read;
    let name = p.file.strip_prefix("payload/").ok_or("missing")?;
    let dir = audit.dir.open_dir("payload").map_err(|_| "unreadable")?;
    let (f, _) = dir.open_regular(name).map_err(|e| match e {
        ReadError::Missing => "missing",
        _ => "unreadable",
    })?;
    let mut buf = Vec::new();
    f.take(max)
        .read_to_end(&mut buf)
        .map_err(|_| "unreadable")?;
    Ok(buf)
}

// ---------------------------------------------------------------------------
// Text helpers.

/// Whether byte `i` of `b` starts a character (or is the end).
pub fn boundary(b: &[u8], i: usize) -> bool {
    i == b.len() || (i < b.len() && (b[i] & 0xC0) != 0x80)
}

/// The largest character boundary at or before `i`.
pub fn floor_boundary(b: &[u8], mut i: usize) -> usize {
    i = i.min(b.len());
    while i > 0 && !boundary(b, i) {
        i -= 1;
    }
    i
}

/// The smallest character boundary at or after `i`.
pub fn ceil_boundary(b: &[u8], mut i: usize) -> usize {
    while i < b.len() && !boundary(b, i) {
        i += 1;
    }
    i.min(b.len())
}

/// 1-based line of byte `i`: one plus the LF bytes before it.
pub fn line_of(b: &[u8], i: usize) -> u64 {
    1 + b[..i.min(b.len())].iter().filter(|c| **c == b'\n').count() as u64
}

/// Lines of the first and last byte of `[start, end)`, `None` when empty.
pub fn lines(b: &[u8], start: usize, end: usize) -> Option<(u64, u64)> {
    (start < end).then(|| {
        let first = line_of(b, start);
        let between = b[start..end - 1].iter().filter(|c| **c == b'\n').count() as u64;
        (first, first + between)
    })
}

pub fn pair(p: (u64, u64)) -> J {
    J::Arr(vec![J::Int(p.0), J::Int(p.1)])
}

/// Whether a page has no non-whitespace character, so it cannot be its own
/// text block (7.1).
pub fn blank(text: &str) -> bool {
    text.chars().all(char::is_whitespace)
}

/// Names closest to `wanted` among the readable sources, as hints.
pub fn hints(world: &World, wanted: &str) -> Vec<String> {
    let mut names: Vec<&str> = vec!["question"];
    names.extend(world.materials.iter().map(|m| m.name.as_str()));
    let mut scored: Vec<(usize, &str)> = names
        .iter()
        .map(|n| (util::edit_distance(wanted, n), *n))
        .collect();
    scored.sort();
    scored
        .into_iter()
        .take(3)
        .map(|(_, n)| n.to_string())
        .collect()
}

/// `source_unknown` with the closest existing names (2.4): names are exact
/// and never normalized.
pub fn source_unknown(world: &World, source: &str) -> Fail {
    let h = hints(world, source);
    refused(
        "source_unknown",
        format!(
            "No source is named {source:?}. Names are exact; the closest are {}.",
            h.join(", ")
        ),
    )
    .data(
        J::obj()
            .with("source", source)
            .with("hints", crate::json::strs(&h)),
    )
}

/// A control character label rule: at most `max` characters, none of them
/// U+0000–U+001F or U+007F–U+009F.
pub fn label_ok(label: &str, min: usize, max: usize) -> bool {
    let n = label.chars().count();
    n >= min
        && n <= max
        && !label
            .chars()
            .any(|c| (c as u32) < 0x20 || (0x7F..=0x9F).contains(&(c as u32)))
}

// ---------------------------------------------------------------------------
// Cursors (2.3): `<kind>.<position>.<check>`, the check binding the cursor
// to its purpose. A cursor that does not match is `handle_invalid`.

/// Split a cursor of `kind` into its position.
pub fn cursor_position<'a>(cursor: &'a str, kind: &str) -> Option<&'a str> {
    let rest = cursor.strip_prefix(kind)?.strip_prefix('.')?;
    let (pos, check) = rest.rsplit_once('.')?;
    (!pos.is_empty() && check.len() == 6).then_some(pos)
}

pub fn invalid_cursor(cursor: &str) -> Fail {
    refused(
        "handle_invalid",
        format!(
            "{cursor:?} is not a cursor this call can continue. Use the cursor from the previous reply's next call, with the same inputs."
        ),
    )
}
