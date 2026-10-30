//! Delivery of a recorded seal (INTERFACE 8.3, 8.4): planning an attempt,
//! writing and verifying its package at a destination, and recording its
//! outcome; and presenting attempts as `run`, `close` and status show them.
//!
//! A run delivers after an auditor seal, before exiting; close delivers any
//! other owed copy. Every attempt uses a fresh package and keeps earlier
//! attempts. Stewart never removes anything at a destination. The plan is a
//! `returns::DeliveryPlan` written with `names::write_plan`; its outcome is
//! a `bodies::DeliveryEnded` record.

use crate::archive::Audit;
use crate::bodies::Loss;
use crate::json::J;
use crate::log::LogState;
use crate::reply::Cause;

/// One invocation plans at most this many attempts (a `name_taken` attempt
/// is followed by a new plan), then reports the delivery incomplete.
pub const ATTEMPTS_PER_INVOCATION: u64 = 16;

/// Which operation delivers: `delivery_planned.by` and `recorded_by`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum By {
    Run,
    Close,
}

impl By {
    pub fn name(self) -> &'static str {
        match self {
            By::Run => "run",
            By::Close => "close",
        }
    }
}

/// Where an attempt delivers.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Destination {
    /// An absolute directory path.
    pub path: String,
    /// `commissioned`, or `replacement` for a destination given with
    /// `--destination` or inherited from a replacement attempt (5.8).
    pub source: &'static str,
}

/// One delivery request.
#[derive(Debug, Clone)]
pub struct Request {
    pub by: By,
    pub destination: Destination,
    /// The `verified_with_losses` attempt whose delivery-stage losses this
    /// attempt retries (close, 5.8). Otherwise `replaces` is computed from
    /// the log: the newest earlier attempt of the seal that ended `partial`,
    /// `failed` or `name_taken`, else none.
    pub retries_losses_of: Option<u64>,
}

/// A loss as replies present it: the recorded loss with its loss ID, issued
/// only for a `verified_with_losses` attempt.
#[derive(Debug, Clone, PartialEq)]
pub struct LossView {
    /// `loss.<member token>.<check>`; `None` where no ID is issued.
    pub loss: Option<String>,
    pub recorded: Loss,
}

/// One delivery attempt as `run`, `close` and status present it (5.6, 5.7).
#[derive(Debug, Clone, PartialEq)]
pub struct AttemptView {
    pub attempt: u64,
    /// The `delivery_ended` outcome; `None` while it has none, or when this
    /// invocation could not establish it (effects then state `unknown`).
    pub outcome: Option<String>,
    /// The package directory's absolute path, or `None`.
    pub location: Option<String>,
    /// The members verified at the destination.
    pub verified_members: Vec<String>,
    /// Each member written or attempted and not verified, with its failure.
    pub unverified_members: Vec<(String, String)>,
    /// Losses, only for a `verified_with_losses` attempt; otherwise empty.
    pub losses: Vec<LossView>,
    pub cause: Option<Cause>,
}

impl AttemptView {
    /// The `delivery` member of the run and close replies: `attempt`,
    /// `outcome`, `location`, `verified_members`, `unverified_members`,
    /// `losses` and `cause`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("attempt", self.attempt)
            .with("outcome", self.outcome.as_deref())
            .with("location", self.location.as_deref())
            .with(
                "verified_members",
                crate::json::strs(&self.verified_members),
            )
            .with(
                "unverified_members",
                J::Arr(
                    self.unverified_members
                        .iter()
                        .map(|(n, f)| {
                            J::obj()
                                .with("name", n.as_str())
                                .with("failure", f.as_str())
                        })
                        .collect(),
                ),
            )
            .with(
                "losses",
                J::Arr(
                    self.losses
                        .iter()
                        .map(|l| {
                            J::obj()
                                .with("loss", l.loss.as_deref())
                                .with("member", l.recorded.member.as_str())
                                .with("role", l.recorded.role.as_str())
                                .with("failure", l.recorded.failure.as_str())
                                .with("stage", l.recorded.stage.as_str())
                        })
                        .collect(),
                ),
            )
            .with(
                "cause",
                self.cause.as_ref().map(|c| c.to_j()).unwrap_or(J::Null),
            )
    }
}

/// What one delivery invocation did.
#[derive(Debug, Clone)]
pub struct Delivered {
    /// Every attempt this invocation planned, in order; the last is the
    /// newest, whose outcome `effects.delivery` reports.
    pub attempts: Vec<AttemptView>,
    /// Set when the invocation stopped because an archive write failed (a
    /// plan, `delivery_planned` or `delivery_ended` could not be recorded);
    /// effects then state `unknown` where the outcome cannot be established.
    pub stopped: Option<Cause>,
}

/// Deliver the recorded seal (8.3): claim and write the plan, publish
/// `delivery_planned`, create the package with `mkdirat` (planning a new
/// attempt on `name_taken`), write `manifest.json` then each member as
/// exclusive synced files from sources read through descriptors and checked,
/// read every written member back, and publish `delivery_ended`. The caller
/// holds the active lock and has established that a seal exists. Fault
/// points: `delivery.source_read:<member>`, `delivery.member_write:<member>`,
/// `delivery.member_corrupt:<member>`, `delivery.after_member:<k>`,
/// `delivery.after_ended`.
pub fn deliver(audit: &Audit, state: &LogState, request: &Request) -> Delivered {
    let _ = (audit, state, request);
    unimplemented!("delivery is not implemented in this build")
}

/// Present a recorded attempt from the log (status, close and a lost-reply
/// continuation read these records rather than copying again).
pub fn view(audit: &Audit, state: &LogState, attempt: u64) -> Option<AttemptView> {
    let _ = (audit, state, attempt);
    unimplemented!("delivery is not implemented in this build")
}

/// The confirmation token of a `verified` or `verified_with_losses`
/// attempt, `cf<n>.<check>` (8.4), or `None` for any other attempt.
pub fn confirmation(audit: &Audit, state: &LogState, attempt: u64) -> Option<String> {
    let d = state
        .deliveries()
        .into_iter()
        .find(|d| d.attempt == attempt)?;
    let (rec, ended) = d.ended?;
    if !crate::bodies::VERIFIED_OUTCOMES.contains(&ended.outcome.as_str()) {
        return None;
    }
    Some(crate::ids::cf_handle(
        &audit.archive.store,
        &audit.id,
        attempt,
        &ended.manifest_sha256,
        &rec.sha256,
    ))
}
