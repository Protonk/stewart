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

use crate::archive::Audit;
use crate::bodies::{Actor, Invocation};
use crate::forms::Family;
use crate::log::{EndedBy, LogState};
use crate::reply::{Cause, Outcome};
use crate::returns::{Member, Unproduced};
use crate::usage::{Limits, Usage};
use crate::world::World;

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

/// Execute one block of a live placement and return its account. Never
/// panics on auditor input; every refusal or failure is an envelope with
/// `effects` (a failed call also writes a diagnostic, 4.8). Mutations refuse
/// `authoring_ended` once a seal or `close_requested` exists, and an
/// in-progress mutation that loses its log slot to `close_requested`
/// reports `authoring_ended` too (6.8).
pub fn execute(audit: &Audit, world: &World, placement: &Placement, call: &Call) -> Executed {
    let _ = (audit, world, placement, call);
    unimplemented!("the auditor's tools are not implemented in this build")
}

/// The account of a block whose call capture could not be written: the call
/// did not run (`raw_capture: failed`), it fails `record_failed` with
/// `cause`, and the placement ends `archive_write_failed` (1.4, 7.1).
pub fn capture_failed(call: &Call, cause: &Cause, revision: u64) -> Executed {
    let _ = (call, cause, revision);
    unimplemented!("the auditor's tools are not implemented in this build")
}

/// The refusal of a block that reuses an executed `tool_use` ID of this
/// placement with a different name or input (`invocation_id_reused`, 6.3).
/// `original` is the call number that executed the ID.
pub fn reused(call: &Call, original: u64, revision: u64) -> Executed {
    let _ = (call, original, revision);
    unimplemented!("the auditor's tools are not implemented in this build")
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
    let _ = (audit, family, state, through, preparer);
    unimplemented!("preparing the answer is not implemented in this build")
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
    let _ = (audit, family, prepared, sealer);
    unimplemented!("sealing is not implemented in this build")
}
