//! The auditor's tools (INTERFACE 7; QUESTION-FORMS): executing one
//! `tool_use` block of a live placement, preparing the answer and sealing it.
//!
//! Division of work with the run adapter (6.3, 4.5): the run owns the
//! conversation and `runs/<n>`. It captures each block (`call-<c>.json`)
//! before calling [`execute`], handles a replayed block (same ID, name and
//! input bytes: the recorded result is resent without execution) itself, and
//! records the result (`result-<c>.json`) from the returned [`Executed`]
//! before the next block. This module owns everything a call does to the
//! audit: payloads (`names::write_payload`), `entry` and `seal` records,
//! auditor preparations, and the reply envelope (`Reply::auditor_j`) inside
//! the content it returns.
//!
//! [`prepare`] and [`seal`] are shared with close, which prepares the
//! selection current at its `close_requested` and seals it with manager
//! attribution (5.8, 8.1).

use crate::archive::{Audit, Fail};
use crate::bodies::{Actor, Invocation, Payload};
use crate::forms::Family;
use crate::json::J;
use crate::log::{EndedBy, LogState};
use crate::reply::{Cause, Outcome, Reply};
use crate::returns::{Member, Unproduced};
use crate::usage::{Limits, Usage};
use crate::world::World;

mod b64;
mod common;
mod edit;
mod input;
mod prep;
mod reading;
mod reentry;

pub use edit::retained;
pub use prep::{answer_json, existing_seal, render};

// Bounds of recording and re-entry (7.3, 7.4, 7.5; Appendix B). Reading
// bounds are in `forms`.
/// Citations per entry.
pub const CITATIONS_PER_ENTRY: usize = 64;
/// Occurrences listed by a `quote_ambiguous` refusal.
pub const AMBIGUOUS_OCCURRENCES: usize = 8;
/// A label, in characters.
pub const LABEL_CHARS: usize = 200;
/// Current entries (`entry_limit`).
pub const ENTRIES: usize = 256;
/// One entry's payload (the core's bound; through the model adapter a call
/// carries at most `forms::TOOL_INPUT_BYTES`).
pub const ENTRY_BYTES: u64 = 64 * 1024 * 1024;
/// The current selection's payloads (`selection_limit`).
pub const SELECTION_BYTES: u64 = 256 * 1024 * 1024;
/// Retained superseded and deleted payloads: past this, edits larger than
/// `CAPPED_EDIT_BYTES` are refused (`retained_payload_cap`) and smaller ones
/// draw on `RETAINED_RESERVE_BYTES` (`retained_payload_reserve_exhausted`).
pub const RETAINED_CAP_BYTES: u64 = 1024 * 1024 * 1024;
pub const CAPPED_EDIT_BYTES: u64 = 1024 * 1024;
pub const RETAINED_RESERVE_BYTES: u64 = 64 * 1024 * 1024;
/// Re-entry: entries per page, receipts listed and preview bytes.
pub const REENTRY_ENTRIES_PER_PAGE: usize = 64;
pub const REENTRY_RECEIPTS: usize = 16;
pub const PREVIEW_BYTES: usize = 200;

/// The placement a call runs in, with what re-entry (7.5) reports about it.
#[derive(Debug, Clone)]
pub struct Placement {
    /// The placement number; its captures are in `runs/<run>`.
    pub run: u64,
    /// True when `run` is above 1.
    pub continuing: bool,
    /// Usage so far across the audit: every ended placement's `run_ended`
    /// usage plus this placement's charges so far, reported and estimated
    /// kept apart. Re-entry reports these cumulative figures, never this
    /// placement's alone.
    pub used: Usage,
    /// The audit's cumulative limits.
    pub limits: Limits,
    /// Whether each notice is used audit-wide (a `notice` record exists).
    pub notices_used: NoticesUsed,
}

/// Re-entry's `notices_used`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct NoticesUsed {
    pub reminder: bool,
    pub near_limit: bool,
}

/// One `tool_use` block to execute.
#[derive(Debug, Clone, Copy)]
pub struct Call<'a> {
    /// The call number `c` in this placement; `call-<c>.json` is already
    /// captured, so effects report `raw_capture: recorded`.
    pub call: u64,
    /// The block's `id` (a block without a string `id` is unanswerable and
    /// never reaches this module).
    pub tool_use_id: &'a str,
    /// The block's `name` when present once and a string; `None` is refused
    /// `tool_unknown`, naming the arrangement's tools.
    pub name: Option<&'a str>,
    /// The raw bytes of the block's `input` value when present once; `None`
    /// is refused `input_invalid`. Decoded strictly (1.2) here; at most 4 MiB
    /// (`input_too_large`).
    pub input: Option<&'a [u8]>,
}

impl Call<'_> {
    /// The invocation an `entry` or `seal` record names.
    pub fn invocation(&self, run: u64) -> Invocation {
        Invocation {
            run,
            tool_use_id: self.tool_use_id.to_string(),
            call: self.call,
        }
    }
}

/// Why the placement must end after a call (6.5, 7.1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum End {
    /// An archive write failed during the call (its payload, its log
    /// record or, for the run, its result record): the call failed
    /// `record_failed`, and the placement ends `interrupted` with cause
    /// `archive_write_failed`.
    ArchiveWriteFailed,
    /// A read or prepare found damaged answer bytes (`answer_damaged`): the
    /// placement ends `damaged`.
    AnswerDamaged,
    /// The log was found damaged: the run publishes nothing more, sends no
    /// further request and exits 4.
    LogDamaged,
}

/// The account of one executed call: what its `tool_result` block carries
/// and what its result record states (4.5).
#[derive(Debug, Clone)]
pub struct Executed {
    /// The exact bytes of the block's `content` array: a text block holding
    /// the `stewart.reply/1` envelope, then, for a text read whose page is
    /// not blank, a text block holding the exact text (7.1).
    pub content: Vec<u8>,
    /// True exactly when `outcome` is not completed.
    pub is_error: bool,
    pub outcome: Outcome,
    /// The envelope's reason; `None` when completed.
    pub reason: Option<String>,
    /// The answer revision after the call.
    pub revision: u64,
    /// The `entry` or `seal` record the call published, `log/<n>.json`.
    pub log_record: Option<String>,
    /// This call published the seal: the run delivers after executing the
    /// response's blocks, then ends `sealed` (6.3).
    pub sealed: bool,
    /// The placement must end after this call; no later block of the
    /// response is captured or executed.
    pub end: Option<End>,
}

/// Every tool name a family's arrangement can hold.
const TOOLS: [&str; 16] = [
    "list",
    "read",
    "search",
    "record_account",
    "record_observation",
    "record_limit",
    "record_working_question",
    "record_relation",
    "record_criterion",
    "record_comparison",
    "record_artifact",
    "replace",
    "delete",
    "what_am_i_working_with",
    "prepare",
    "submit",
];

/// The operation name a reply uses internally for a block that names no
/// tool of the arrangement; the envelope shows the name the block gave.
const NO_TOOL: &str = "tool_unknown";

fn known(name: Option<&str>) -> Option<&'static str> {
    TOOLS.iter().copied().find(|t| Some(*t) == name)
}

/// Assemble the account of a call: the envelope (with `effects` for the
/// tool), the content blocks and the result record's facts. A failed call
/// writes a diagnostic (4.8); a refused one does not.
fn finish(
    audit: Option<&Audit>,
    op: &'static str,
    shown: Option<&str>,
    call: &Call,
    raw_capture: &'static str,
    revision: u64,
    out: common::Out,
) -> Executed {
    let effects: Vec<(&'static str, &'static str)> = crate::reply::auditor_effect_keys(op)
        .iter()
        .map(|k| {
            (
                *k,
                match *k {
                    "answer" => out.answer,
                    "seal" => out.seal,
                    _ => raw_capture,
                },
            )
        })
        .collect();
    let mut reply = match out.result {
        Ok(data) => Reply::completed(op, effects, data),
        Err(f) => f.into_reply(op, effects),
    };
    reply.tool_next = out.next;
    if reply.outcome == Outcome::Failed {
        if let Some(a) = audit {
            a.diagnose(
                &mut reply,
                J::obj()
                    .with("tool", shown.unwrap_or(op))
                    .with("tool_use_id", call.tool_use_id)
                    .with("call", call.call),
            );
        }
    }
    let mut env = reply.auditor_j();
    if let (Some(name), J::Obj(m)) = (shown, &mut env) {
        if let Some(slot) = m.iter_mut().find(|(k, _)| k == "operation") {
            slot.1 = J::Str(name.to_string());
        }
    }
    let mut blocks = vec![J::obj().with("type", "text").with("text", env.string())];
    if let Some(t) = out.text {
        blocks.push(J::obj().with("type", "text").with("text", t));
    }
    Executed {
        content: J::Arr(blocks).bytes(),
        is_error: reply.outcome != Outcome::Completed,
        outcome: reply.outcome,
        reason: reply.reason.clone(),
        revision: out.revision.unwrap_or(revision),
        log_record: out.log_record,
        sealed: out.sealed,
        end: out.end,
    }
}

/// Execute one block of a live placement and return its account. Never
/// panics on auditor input; every refusal or failure is an envelope with
/// `effects` (a failed call also writes a diagnostic, 4.8). Mutations refuse
/// `authoring_ended` once a seal or `close_requested` exists, and an
/// in-progress mutation that loses its log slot to `close_requested`
/// reports `authoring_ended` too (6.8).
pub fn execute(audit: &Audit, world: &World, placement: &Placement, call: &Call) -> Executed {
    let state = crate::log::read(audit);
    let revision = state.revision();
    let tool = known(call.name).filter(|t| world.arrangement.tool_names.iter().any(|n| n == t));
    let Some(tool) = tool else {
        let tools = &world.arrangement.tool_names;
        let out: common::Out = common::refused(
            "tool_unknown",
            match call.name {
                Some(n) => format!(
                    "No tool is named {n:?}. The tools are: {}.",
                    tools.join(", ")
                ),
                None => format!(
                    "The tool_use block names no tool. The tools are: {}.",
                    tools.join(", ")
                ),
            },
        )
        .data(
            J::obj()
                .with("tool", call.name)
                .with("tools", crate::json::strs(tools)),
        )
        .into();
        let shown = call.name.unwrap_or("");
        return finish(
            Some(audit),
            NO_TOOL,
            Some(shown),
            call,
            "recorded",
            revision,
            out,
        );
    };
    if state.damaged() {
        let out = common::Out::fail(Fail::failed(
            "log_damaged",
            format!(
                "The audit log is damaged ({}); Stewart records nothing more in this placement.",
                state.bad_names()
            ),
        ))
        .end(End::LogDamaged);
        return finish(Some(audit), tool, None, call, "recorded", revision, out);
    }
    let v = match input::decode(call.input) {
        Ok(v) => v,
        Err(f) => {
            return finish(
                Some(audit),
                tool,
                None,
                call,
                "recorded",
                revision,
                f.into(),
            );
        }
    };
    let ctx = common::Ctx {
        audit,
        world,
        placement,
        call,
        tool,
        state,
    };
    let mut out = match tool {
        "list" => reading::list(&ctx, &v),
        "read" => reading::read(&ctx, &v),
        "search" => reading::search(&ctx, &v),
        "record_artifact" => edit::artifact(&ctx, &v),
        "replace" => edit::replace(&ctx, &v),
        "delete" => edit::delete(&ctx, &v),
        "what_am_i_working_with" => reentry::what_am_i_working_with(&ctx, &v),
        "prepare" => prep::prepare_tool(&ctx, &v),
        "submit" => prep::submit(&ctx, &v),
        _ => edit::record(&ctx, &v),
    };
    if out.revision.is_none() && (out.answer == "unknown" || out.seal == "unknown") {
        let st = crate::log::read(audit);
        if !st.damaged() {
            out.revision = Some(st.revision());
        }
    }
    finish(Some(audit), tool, None, call, "recorded", revision, out)
}

/// The account of a block whose call capture could not be written: the call
/// did not run (`raw_capture: failed`), it fails `record_failed` with
/// `cause`, and the placement ends `archive_write_failed` (1.4, 7.1). No
/// diagnostic is attempted here: the archive is failing, and the run's own
/// account of the ending covers it.
pub fn capture_failed(call: &Call, cause: &Cause, revision: u64) -> Executed {
    let op = known(call.name).unwrap_or(NO_TOOL);
    let mut out = common::Out::fail(
        Fail::failed(
            "record_failed",
            format!(
                "The call could not be captured ({}: {}), so it did not run.",
                cause.operation, cause.error
            ),
        )
        .cause(cause.clone()),
    )
    .end(End::ArchiveWriteFailed);
    out.seal = "unknown";
    let shown = (op == NO_TOOL).then(|| call.name.unwrap_or(""));
    finish(None, op, shown, call, "failed", revision, out)
}

/// The refusal of a block that reuses an executed `tool_use` ID of this
/// placement with a different name or input (`invocation_id_reused`, 6.3).
/// `original` is the call number that executed the ID.
pub fn reused(call: &Call, original: u64, revision: u64) -> Executed {
    let op = known(call.name).unwrap_or(NO_TOOL);
    let mut out = common::Out::fail(
        common::refused(
            "invocation_id_reused",
            format!(
                "The tool_use ID {:?} was already executed in this placement (call {original}) with a different name or input; it was not executed again. A new call needs a new ID.",
                call.tool_use_id
            ),
        )
        .data(
            J::obj()
                .with("tool_use_id", call.tool_use_id)
                .with("original_call", original),
        ),
    );
    out.seal = "unknown";
    let shown = (op == NO_TOOL).then(|| call.name.unwrap_or(""));
    finish(None, op, shown, call, "recorded", revision, out)
}

// ---------------------------------------------------------------------------
// Preparation and seal, shared with close.

/// Whose preparation of the answer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Preparer {
    /// The `prepare` tool: damaged selected bytes refuse (`answer_damaged`).
    Auditor,
    /// Close: an entry that cannot be read or verified becomes a named,
    /// unproduced member, and so does the rendering, which is not run (8.1).
    Manager,
}

/// A written preparation of the answer, `prepared/<n>` (7.6, 8.1).
#[derive(Debug, Clone)]
pub struct Prepared {
    pub n: u64,
    /// The prepared selection's answer revision.
    pub revision: u64,
    pub entry_count: u64,
    /// `answer.json` as a return member.
    pub answer: Member,
    /// `answer.md` as a return member; `None` when it is unproduced.
    pub rendering: Option<Member>,
    /// Each produced artifact entry's member (`artifact-<id>.bin`) in
    /// selection order, with the payload file it is copied from.
    pub artifacts: Vec<(Member, String)>,
    /// Unproduced entries in selection order, then an unproduced rendering,
    /// as the return manifest lists them. Empty for the auditor.
    pub unproduced: Vec<Unproduced>,
    /// One count per recording tool of the family, then `record_artifact`,
    /// in tools order.
    pub counts: Vec<(String, u64)>,
    /// Prepare's notices, in tools order: `section_unfilled` per expected
    /// section without an entry, or the single `answer_empty`.
    pub notices: Vec<PrepareNotice>,
    /// The payloads of the produced entries, which the seal re-verifies.
    pub payloads: Vec<Payload>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrepareNotice {
    /// `section_unfilled` or `answer_empty`.
    pub reason: String,
    /// The section's recording tool; `None` for `answer_empty`.
    pub tool: Option<String>,
    pub message: String,
}

/// A selected entry whose payload failed verification.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DamagedEntry {
    pub id: String,
    /// `missing`, `unreadable` or `damaged`.
    pub failure: String,
}

#[derive(Debug)]
pub enum PrepareError {
    /// Selected bytes failed verification (auditor only): `answer_damaged`,
    /// and the placement ends `damaged`.
    Damaged(Vec<DamagedEntry>),
    /// Claiming or writing `prepared/<n>` failed.
    WriteFailed(Cause),
}

/// Prepare the selection at log position `through` (the end of the log for
/// the auditor; the `close_requested` record for close) into a new
/// `prepared/<n>`: re-verify each selected payload's size and digest, claim
/// `prepared/<n>` and write `answer.json` and `answer.md` (QUESTION-FORMS)
/// as exclusive files (fault point `prepared.write`, via
/// `names::write_prepared_file`). No log record names a preparation unless
/// it is sealed.
pub fn prepare(
    audit: &Audit,
    family: &Family,
    state: &LogState,
    through: u64,
    preparer: Preparer,
) -> Result<Prepared, PrepareError> {
    prep::prepare(audit, family, state, through, preparer)
}

/// Who seals.
#[derive(Debug, Clone, PartialEq)]
pub enum Sealer {
    /// A confirmed submit, with its invocation.
    Auditor(Invocation),
    /// Close.
    Manager,
}

/// A seal that stands.
#[derive(Debug, Clone)]
pub struct Sealed {
    /// The `seal` record, `log/<n>.json`.
    pub record: String,
    /// `seal.<check>`.
    pub handle: String,
    pub actor: Actor,
    /// The manifest's `sealed_at`.
    pub sealed_at: String,
    pub revision: u64,
    pub manifest_sha256: String,
    /// The seal existed before this call: a repeated confirmed submit, or a
    /// seal another actor published first, which stands.
    pub existing: bool,
}

#[derive(Debug)]
pub enum SealError {
    /// The preparation's revision is no longer current (auditor):
    /// `stale_preparation` with `revision_now`.
    Stale { revision_now: u64 },
    /// Authoring ended before this seal (`authoring_ended`): what ended it,
    /// its record and, if a seal exists, that seal.
    AuthoringEnded {
        by: EndedBy,
        record: String,
        seal: Option<Sealed>,
    },
    /// The preparation's files or a selected payload failed re-verification.
    Damaged(String),
    /// The `seal` record was linked but its durability could not be
    /// confirmed (`seal_uncertain`, `effects.seal: "unknown"`).
    Uncertain(Cause),
    /// Nothing was published (`record_failed`).
    NotPublished(Cause),
    /// The log is damaged.
    LogDamaged,
}

/// Seal a preparation (8.1): re-verify its files and each selected
/// payload, write `seal/manifest-<k>.json` (`names::write_manifest`, fault
/// point `seal.manifest_write`), then publish the `seal` record. If the slot
/// is taken by an edit the auditor's submit is stale; by `close_requested`,
/// authoring has ended; by another `seal`, that seal stands. `family` is the
/// pinned family's versioned ID (`open-inquiry/1`) the manifest records.
pub fn seal(
    audit: &Audit,
    family: &str,
    prepared: &Prepared,
    sealer: Sealer,
) -> Result<Sealed, SealError> {
    prep::seal(audit, family, prepared, sealer)
}
