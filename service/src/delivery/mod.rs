//! Delivery of a recorded seal (INTERFACE 8.3, 8.4): planning an attempt,
//! writing and verifying its package at a destination, and recording its
//! outcome; and presenting attempts as `run`, `close` and status show them.
//!
//! A run delivers after an auditor seal, before exiting; close delivers any
//! other owed copy. Every attempt uses a fresh package and keeps earlier
//! attempts. Stewart never removes anything at a destination: a package name
//! that already exists ends the attempt `name_taken` and a new attempt is
//! planned, so an existing path is never adopted, emptied or overwritten.
//!
//! One attempt, in order:
//!
//! 1. Claim `delivery/<attempt>.json` and write the plan (`returns::DeliveryPlan`
//!    via `names::write_plan`): `manifest.json`, then the manifest's members,
//!    each with the archive file it is copied from. The plan's members are
//!    null when the manifest cannot be read and checked against the seal's
//!    digest: membership is then unknown and the attempt ends `failed`, never
//!    as an empty return.
//! 2. Publish `delivery_planned`.
//! 3. Check location overlap and create the package with `mkdirat`.
//! 4. Write `manifest.json` first, then each member in plan order as an
//!    exclusive, synced file, from a source read through descriptors and
//!    checked for size and digest. A source that fails its check is not
//!    written and becomes a delivery-stage loss; a write failure stops the
//!    attempt. Then sync the package and the destination.
//! 5. Reopen every written member by name and verify it.
//! 6. Publish `delivery_ended` (`bodies::DeliveryEnded`).
//!
//! The confirmation token and loss IDs are computed from the published
//! `delivery_ended` record (8.4), so no record contains a handle that binds it.

use crate::archive::Audit;
use crate::bodies::{DeliveryEnded, DeliveryPlanned, Loss, MemberResult, SealRec};
use crate::fsx::{self, Dir, ReadError};
use crate::json::J;
use crate::log::{self, LogState, PubErr};
use crate::names;
use crate::reply::Cause;
use crate::returns::{self, DeliveryPlan, MANIFEST_MEMBER, Manifest, PlanDestination, PlanMember};
use crate::util;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

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

impl Destination {
    pub fn commissioned(path: impl Into<String>) -> Destination {
        Destination {
            path: path.into(),
            source: "commissioned",
        }
    }
    pub fn replacement(path: impl Into<String>) -> Destination {
        Destination {
            path: path.into(),
            source: "replacement",
        }
    }
    /// An earlier attempt's destination, keeping its source: a destination
    /// inherited from a replacement attempt is itself a replacement.
    pub fn of(plan: &DeliveryPlanned) -> Destination {
        Destination {
            path: plan.destination.clone(),
            source: if plan.destination_source == "replacement" {
                "replacement"
            } else {
                "commissioned"
            },
        }
    }
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
    /// The run's stop input (6.8): a flag its signal receiver sets on
    /// SIGTERM, SIGINT or SIGHUP. It is checked before each member is written
    /// and before verification; once set, the attempt writes and verifies
    /// nothing more, still publishes its `delivery_ended`, and ends `failed`
    /// with cause `signal`, while the placement ends `sealed`. Close passes
    /// none.
    pub stop: Option<Arc<AtomicBool>>,
}

impl Request {
    /// Whether the stop input is set.
    fn stopped(&self) -> bool {
        self.stop.as_ref().is_some_and(|f| f.load(Ordering::SeqCst))
    }
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
            .with("unverified_members", self.unverified_j())
            .with("losses", self.losses_j())
            .with(
                "cause",
                self.cause.as_ref().map(|c| c.to_j()).unwrap_or(J::Null),
            )
    }

    /// `unverified_members`: each `{name, failure}`.
    pub fn unverified_j(&self) -> J {
        J::Arr(
            self.unverified_members
                .iter()
                .map(|(n, f)| {
                    J::obj()
                        .with("name", n.as_str())
                        .with("failure", f.as_str())
                })
                .collect(),
        )
    }

    /// `losses`: each `{loss, member, role, failure, stage}`.
    pub fn losses_j(&self) -> J {
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
        )
    }

    /// The loss IDs, in record order.
    pub fn loss_ids(&self) -> Vec<String> {
        self.losses.iter().filter_map(|l| l.loss.clone()).collect()
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
/// `delivery.after_ended`. `request.stop` ends an attempt `failed` with
/// cause `signal`.
pub fn deliver(audit: &Audit, state: &LogState, request: &Request) -> Delivered {
    let stop = || request.stopped();
    let mut out = Delivered {
        attempts: Vec::new(),
        stopped: None,
    };
    // The seal never changes once published, so the caller's view of it
    // serves every attempt; everything else is re-read before each attempt.
    let Some((seal_rec, seal)) = state.seal() else {
        out.stopped = Some(Cause::new("deliver", "no seal is recorded"));
        return out;
    };
    let seal_name = seal_rec.name();
    for _ in 0..ATTEMPTS_PER_INVOCATION {
        let now = log::read(audit);
        if now.damaged() {
            out.stopped = Some(Cause::new(
                "read log",
                format!("the log is damaged: {}", now.bad_names()),
            ));
            return out;
        }
        match attempt(audit, &now, &seal_name, seal, request, &stop) {
            Step::Ended(view) => {
                let again = view.outcome.as_deref() == Some("name_taken");
                out.attempts.push(view);
                if !again {
                    return out;
                }
            }
            Step::Stopped(view, cause) => {
                out.attempts.extend(view);
                out.stopped = Some(cause);
                return out;
            }
        }
    }
    out
}

enum Step {
    /// The attempt's `delivery_ended` is published.
    Ended(AttemptView),
    /// An archive write failed; the attempt (if any was planned) has no
    /// established outcome.
    Stopped(Option<AttemptView>, Cause),
}

/// A view of an attempt whose outcome this invocation could not establish.
fn unknown_view(attempt: u64) -> AttemptView {
    AttemptView {
        attempt,
        outcome: None,
        location: None,
        verified_members: Vec::new(),
        unverified_members: Vec::new(),
        losses: Vec::new(),
        cause: None,
    }
}

fn pub_cause(kind: &str, e: &PubErr) -> Cause {
    match e {
        PubErr::NotPublished(c) | PubErr::Uncertain { cause: c, .. } => c.clone(),
        PubErr::Refused(f) => Cause::new(format!("publish {kind}"), f.message.clone()),
        PubErr::Damaged(s) => Cause::new(
            format!("publish {kind}"),
            format!("the log is damaged: {}", s.bad_names()),
        ),
    }
}

fn attempt(
    audit: &Audit,
    state: &LogState,
    seal_name: &str,
    seal: &SealRec,
    request: &Request,
    stop: &dyn Fn() -> bool,
) -> Step {
    let membership = plan_members(audit, state, seal);
    let dest = Dir::open_follow(&request.destination.path);
    let (device, inode) = match dest.as_ref().map(|d| d.stat()) {
        Ok(Ok(st)) => (Some(st.dev), Some(st.ino)),
        _ => (None, None),
    };
    let deliveries = state.deliveries();
    let replaces = request.retries_losses_of.or_else(|| {
        deliveries
            .iter()
            .rev()
            .find(|d| d.incomplete())
            .map(|d| d.attempt)
    });
    // The newest earlier package (only the remove_partial_package control
    // touches it).
    let previous_package = deliveries
        .iter()
        .rev()
        .find_map(|d| d.ended.and_then(|(_, e)| e.package.clone()));
    let members = membership.as_ref().ok().map(|(_, m)| m.clone());
    let plan_for = |attempt: u64| DeliveryPlan {
        attempt,
        seal: seal_name.to_string(),
        manifest: seal.manifest.clone(),
        manifest_sha256: seal.manifest_sha256.clone(),
        destination: PlanDestination {
            path: request.destination.path.clone(),
            source: request.destination.source.to_string(),
            device,
            inode,
        },
        package: names::package_name(&audit.id, attempt),
        replaces,
        by: request.by.name().to_string(),
        members: members.clone(),
    };
    let (attempt, plan_bytes) =
        match names::write_plan(audit, |n| audit.record("delivery_plan", plan_for(n).to_j())) {
            Ok(x) => x,
            Err(c) => return Step::Stopped(None, c),
        };
    let plan = plan_for(attempt);
    let planned = DeliveryPlanned {
        attempt,
        plan_sha256: util::sha256_hex(&plan_bytes),
        by: request.by.name().to_string(),
        destination: request.destination.path.clone(),
        destination_source: request.destination.source.to_string(),
        package: plan.package.clone(),
        replaces,
    };
    let published = log::publish(audit, "delivery_planned", |s| {
        if s.seal().is_none() {
            return Err(crate::archive::Fail::refused(
                "record_failed",
                "a delivery is planned only for a recorded seal",
            ));
        }
        if let Some(open) = s.deliveries().iter().find(|d| d.ended.is_none()) {
            return Err(crate::archive::Fail::refused(
                "record_failed",
                format!(
                    "delivery attempt {} has no recorded outcome yet",
                    open.attempt
                ),
            ));
        }
        Ok(planned.to_j())
    });
    if let Err(e) = published {
        let view = matches!(e, PubErr::Uncertain { .. }).then(|| unknown_view(attempt));
        return Step::Stopped(view, pub_cause("delivery_planned", &e));
    }

    let work = carry_out(audit, &plan, membership, dest, stop, previous_package);
    let ended = DeliveryEnded {
        attempt,
        outcome: work.outcome.to_string(),
        recorded_by: request.by.name().to_string(),
        cause: work.cause,
        manifest_sha256: seal.manifest_sha256.clone(),
        package: work.package,
        members: work.members,
        losses: work.losses,
    };
    let published = log::publish(audit, "delivery_ended", |s| {
        match s.deliveries().iter().find(|d| d.attempt == attempt) {
            Some(d) if d.ended.is_none() => Ok(ended.to_j()),
            Some(_) => Err(crate::archive::Fail::refused(
                "record_failed",
                format!("delivery attempt {attempt} already has an outcome"),
            )),
            None => Err(crate::archive::Fail::refused(
                "record_failed",
                format!("delivery attempt {attempt} is not planned in the log"),
            )),
        }
    });
    if let Err(e) = published {
        return Step::Stopped(Some(unknown_view(attempt)), pub_cause("delivery_ended", &e));
    }
    // A kill here leaves a recorded outcome and no reply: continuation reads
    // the record rather than copying again.
    let _ = crate::fault!("delivery.after_ended");
    let now = log::read(audit);
    Step::Ended(view(audit, &now, attempt).unwrap_or_else(|| unknown_view(attempt)))
}

/// The manifest and the plan's members: `manifest.json`, then each member
/// of the manifest with the archive file it is copied from. An error says
/// why membership is unknown.
fn plan_members(
    audit: &Audit,
    state: &LogState,
    seal: &SealRec,
) -> Result<(Manifest, Vec<PlanMember>), String> {
    let (manifest, bytes) = returns::load_manifest(audit, &seal.manifest, &seal.manifest_sha256)?;
    if manifest.revision != seal.revision || manifest.actor != seal.actor {
        return Err(format!(
            "{} does not state the revision and sealer its seal record binds",
            seal.manifest
        ));
    }
    let prepared = names::prepared_dir(seal.prepared);
    let selection = sealed_selection(state, seal.revision);
    let mut members = vec![PlanMember {
        name: MANIFEST_MEMBER.to_string(),
        role: "manifest".to_string(),
        size: bytes.len() as u64,
        sha256: seal.manifest_sha256.clone(),
        source: seal.manifest.clone(),
    }];
    for m in &manifest.members {
        let source = match m.role.as_str() {
            "answer" => format!("{prepared}/answer.json"),
            "rendering" => format!("{prepared}/answer.md"),
            _ => {
                // An artifact's bytes are its entry version's payload. The
                // version is the one current in the sealed selection.
                let id = m
                    .name
                    .strip_prefix("artifact-")
                    .and_then(|r| r.strip_suffix(".bin"))
                    .unwrap_or_default();
                match selection.iter().find(|(v, _)| v == id) {
                    Some((_, file)) => file.clone(),
                    None => {
                        return Err(format!(
                            "{} lists {}, which the sealed selection does not hold",
                            seal.manifest, m.name
                        ));
                    }
                }
            }
        };
        members.push(PlanMember {
            name: m.name.clone(),
            role: m.role.clone(),
            size: m.size,
            sha256: m.sha256.clone(),
            source,
        });
    }
    Ok((manifest, members))
}

/// The selection at answer revision `revision` as (entry ID, payload file):
/// the selection through the `revision`-th `entry` record.
fn sealed_selection(state: &LogState, revision: u64) -> Vec<(String, String)> {
    if revision == 0 {
        return Vec::new();
    }
    let Some((rec, _)) = state.entries().nth(revision as usize - 1) else {
        return Vec::new();
    };
    state
        .selection_through(rec.n)
        .iter()
        .map(|c| (c.version.id.clone(), c.version.payload.file.clone()))
        .collect()
}

/// What an attempt achieved, before its `delivery_ended` is published.
struct Work {
    outcome: &'static str,
    cause: Option<Cause>,
    package: Option<String>,
    members: Option<Vec<MemberResult>>,
    losses: Option<Vec<Loss>>,
}

/// Why a member's archive source could not be supplied.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SourceFailure {
    Missing,
    Unreadable,
    Damaged,
}

impl SourceFailure {
    fn member_failure(self) -> &'static str {
        match self {
            SourceFailure::Missing => "source_missing",
            SourceFailure::Unreadable => "source_unreadable",
            SourceFailure::Damaged => "source_damaged",
        }
    }
    fn loss_failure(self) -> &'static str {
        match self {
            SourceFailure::Missing => "missing",
            SourceFailure::Unreadable => "unreadable",
            SourceFailure::Damaged => "damaged",
        }
    }
}

/// Read a planned member's archive source through descriptors, without
/// following links, and check its size and digest (fault point
/// `delivery.source_read:<member>`).
fn read_source(audit: &Audit, m: &PlanMember) -> Result<Vec<u8>, SourceFailure> {
    crate::fault!("delivery.source_read", &m.name).map_err(|_| SourceFailure::Unreadable)?;
    let (dir_rel, file) = m.source.rsplit_once('/').unwrap_or(("", m.source.as_str()));
    let mut dir = audit
        .dir
        .open_dir_bytes(b".", true)
        .map_err(|_| SourceFailure::Unreadable)?;
    for comp in dir_rel.split('/').filter(|c| !c.is_empty()) {
        dir = dir.open_dir(comp).map_err(|e| {
            if e.raw_os_error() == Some(libc::ENOENT) {
                SourceFailure::Missing
            } else {
                SourceFailure::Unreadable
            }
        })?;
    }
    let (bytes, _) = dir.read_regular(file, m.size).map_err(|e| match e {
        ReadError::Missing => SourceFailure::Missing,
        ReadError::TooLarge { .. } => SourceFailure::Damaged,
        _ => SourceFailure::Unreadable,
    })?;
    if bytes.len() as u64 != m.size || util::sha256_hex(&bytes) != m.sha256 {
        return Err(SourceFailure::Damaged);
    }
    Ok(bytes)
}

/// Write one member at the destination as an exclusive, synced file (fault
/// point `delivery.member_write:<member>`).
fn write_member(pkg: &Dir, name: &str, bytes: &[u8]) -> Result<(), Cause> {
    let at = fsx::join(&pkg.path, name);
    crate::fault!("delivery.member_write", name)
        .map_err(|e| Cause::io(format!("write {name}"), &e).at(&at))?;
    pkg.write_excl(name, bytes)
        .map_err(|e| Cause::io(format!("write {name} ({})", e.step.name()), &e.err).at(at))
}

fn carry_out(
    audit: &Audit,
    plan: &DeliveryPlan,
    membership: Result<(Manifest, Vec<PlanMember>), String>,
    dest: std::io::Result<Dir>,
    stop: &dyn Fn() -> bool,
    previous_package: Option<String>,
) -> Work {
    #[cfg(not(feature = "sabotage"))]
    let _ = previous_package;
    let failed = |cause: Cause,
                  package: Option<String>,
                  members: Option<Vec<MemberResult>>,
                  losses: Option<Vec<Loss>>| Work {
        outcome: "failed",
        cause: Some(cause),
        package,
        members,
        losses,
    };
    let unknown = || Cause::new("read seal manifest", "manifest_unavailable");
    let (manifest, members) = match membership {
        Ok(x) => x,
        Err(_) => {
            #[cfg(feature = "sabotage")]
            if crate::sabotage!("unknown_membership_empty") {
                if let Ok(d) = &dest {
                    return sabotage::empty_return(d, &plan.package);
                }
            }
            // Unknown membership is never an empty return: nothing is
            // written and no loss can be named.
            return failed(unknown(), None, None, None);
        }
    };
    let seal_losses: Vec<Loss> = manifest
        .unproduced
        .iter()
        .map(|u| Loss {
            member: u.name.clone(),
            role: u.role.clone(),
            failure: u.failure.clone(),
            stage: "seal".to_string(),
        })
        .collect();
    let mut results: Vec<MemberResult> = members
        .iter()
        .map(|m| MemberResult {
            name: m.name.clone(),
            role: m.role.clone(),
            written: false,
            verified: false,
            failure: Some("not_attempted".to_string()),
        })
        .collect();
    let dest = match dest {
        Ok(d) => d,
        Err(e) => {
            return failed(
                Cause::io("open destination", &e).at(&plan.destination.path),
                None,
                Some(results),
                Some(seal_losses),
            );
        }
    };
    // The destination never overlaps the archive or the preparation folder,
    // compared by device and inode along each opened directory's ancestry.
    let folder = Dir::open_follow(&audit.refile.folder).ok();
    let mut places = vec![
        crate::ops::Place {
            what: "destination",
            path: &plan.destination.path,
            dir: &dest,
        },
        crate::ops::Place {
            what: "archive",
            path: &audit.archive.path,
            dir: &audit.archive.root,
        },
    ];
    if let Some(f) = &folder {
        places.push(crate::ops::Place {
            what: "submission folder",
            path: &audit.refile.folder,
            dir: f,
        });
    }
    if let Err(f) = crate::ops::check_overlap(&places) {
        let cause = if f.outcome == crate::reply::Outcome::Refused {
            Cause::new("check location overlap", "location_overlap")
        } else {
            f.causes
                .first()
                .cloned()
                .unwrap_or_else(|| Cause::new("check location overlap", "location_overlap"))
        };
        return failed(cause, None, Some(results), Some(seal_losses));
    }
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("remove_partial_package") {
        if let Some(p) = previous_package {
            sabotage::remove_package(&p);
        }
    }
    let package_path = fsx::join(&plan.destination.path, &plan.package);
    if let Err(e) = dest.mkdir(&plan.package) {
        let cause = Cause::io("create package", &e).at(&package_path);
        if e.raw_os_error() == Some(libc::EEXIST) {
            // The existing path is evidence, never Stewart's to adopt.
            return Work {
                outcome: "name_taken",
                cause: Some(cause),
                package: None,
                members: Some(results),
                losses: Some(seal_losses),
            };
        }
        return failed(cause, None, Some(results), Some(seal_losses));
    }
    let package = Some(package_path.clone());
    let pkg = match dest.open_dir(&plan.package) {
        Ok(p) => p,
        Err(e) => {
            return failed(
                Cause::io("open package", &e).at(&package_path),
                package,
                Some(results),
                Some(seal_losses),
            );
        }
    };

    let mut delivery_losses: Vec<Loss> = Vec::new();
    let mut first_failure: Option<Cause> = None;
    let mut signalled = false;
    // What each written member must read back as: its size and digest.
    let mut expected: Vec<Option<(u64, String)>> = vec![None; members.len()];
    for (i, m) in members.iter().enumerate() {
        if stop() {
            signalled = true;
            break;
        }
        let bytes = match read_source(audit, m) {
            Ok(b) => b,
            Err(f) => {
                results[i].failure = Some(f.member_failure().to_string());
                if m.name == MANIFEST_MEMBER {
                    // Without the manifest, membership is unknown: nothing
                    // further is written and no loss can be named.
                    return failed(unknown(), package, None, None);
                }
                delivery_losses.push(Loss {
                    member: m.name.clone(),
                    role: m.role.clone(),
                    failure: f.loss_failure().to_string(),
                    stage: "delivery".to_string(),
                });
                continue;
            }
        };
        #[cfg(feature = "sabotage")]
        let bytes = if m.role == "rendering" && crate::sabotage!("regenerate_rendering") {
            sabotage::regenerated(&bytes)
        } else {
            bytes
        };
        if let Err(c) = write_member(&pkg, &m.name, &bytes) {
            results[i].failure = Some("write_failed".to_string());
            first_failure.get_or_insert(c);
            // A write failure stops the attempt; later members stay
            // `not_attempted`.
            break;
        }
        results[i].written = true;
        results[i].failure = None;
        expected[i] = Some((bytes.len() as u64, util::sha256_hex(&bytes)));
        #[cfg(feature = "fault-injection")]
        if crate::fault_corrupt!("delivery.member_corrupt", &m.name) {
            let _ = pkg.corrupt_file(&m.name);
        }
        let _ = crate::fault!("delivery.after_member", &(i + 1).to_string());
    }
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("deliver_conversation") {
        sabotage::add_conversation(audit, &pkg);
    }
    for (what, d) in [("package", &pkg), ("destination", &dest)] {
        if let Err(e) = d.sync() {
            first_failure.get_or_insert(Cause::io(format!("fsync {what}"), &e).at(&d.path));
        }
    }
    // A stop before verification leaves the written members unverified,
    // without claiming that any failed to read back.
    signalled = signalled || stop();
    for (i, m) in members.iter().enumerate() {
        let Some((size, sha)) = &expected[i] else {
            continue;
        };
        if signalled {
            break;
        }
        if crate::sabotage!("skip_delivery_verification") {
            results[i].verified = true;
            continue;
        }
        match pkg.read_regular(&m.name, *size) {
            Ok((b, _)) if util::sha256_hex(&b) == *sha && b.len() as u64 == *size => {
                results[i].verified = true;
            }
            Ok(_) | Err(ReadError::TooLarge { .. }) => {
                results[i].failure = Some("not_verified".to_string());
                first_failure.get_or_insert(
                    Cause::new(format!("verify {}", m.name), "not_verified")
                        .at(fsx::join(&package_path, &m.name)),
                );
            }
            Err(e) => {
                results[i].failure = Some("not_verified".to_string());
                let error = match e {
                    ReadError::Io(io) => util::errno_name(&io),
                    other => other.describe(),
                };
                first_failure.get_or_insert(
                    Cause::new(format!("verify {}", m.name), error)
                        .at(fsx::join(&package_path, &m.name)),
                );
            }
        }
    }
    let mut losses = seal_losses;
    losses.extend(delivery_losses);
    if signalled {
        return failed(
            Cause::new("deliver", "signal"),
            package,
            Some(results),
            Some(losses),
        );
    }
    if !results[0].written {
        let cause = first_failure.unwrap_or_else(unknown);
        return failed(cause, package, Some(results), Some(losses));
    }
    // A member the archive supplied (its source read and checked) that was
    // not written or not verified makes the attempt partial.
    let incomplete = results.iter().any(|r| {
        !r.verified
            && !matches!(
                r.failure.as_deref(),
                Some("source_missing" | "source_unreadable" | "source_damaged")
            )
    });
    if incomplete || first_failure.is_some() {
        let cause = first_failure.unwrap_or_else(|| Cause::new("deliver", "not_verified"));
        return Work {
            outcome: "partial",
            cause: Some(cause),
            package,
            members: Some(results),
            losses: Some(losses),
        };
    }
    Work {
        outcome: if losses.is_empty() {
            "verified"
        } else {
            "verified_with_losses"
        },
        cause: None,
        package,
        members: Some(results),
        losses: Some(losses),
    }
}

// ---------------------------------------------------------------------------
// Presenting recorded attempts.

/// Present a recorded attempt from the log (status, close and a lost-reply
/// continuation read these records rather than copying again).
pub fn view(audit: &Audit, state: &LogState, attempt: u64) -> Option<AttemptView> {
    let d = state
        .deliveries()
        .into_iter()
        .find(|d| d.attempt == attempt)?;
    Some(view_of(audit, &d))
}

/// Present one attempt of `LogState::deliveries`.
pub fn view_of(audit: &Audit, d: &log::Delivery) -> AttemptView {
    let Some((rec, e)) = d.ended else {
        return unknown_view(d.attempt);
    };
    let members = e.members.as_deref().unwrap_or(&[]);
    let losses = if e.outcome == "verified_with_losses" {
        e.losses
            .as_deref()
            .unwrap_or(&[])
            .iter()
            .map(|l| LossView {
                loss: Some(crate::ids::loss_handle(
                    &audit.archive.store,
                    &audit.id,
                    &names::member_token(&l.member),
                    &e.manifest_sha256,
                    &rec.sha256,
                )),
                recorded: l.clone(),
            })
            .collect()
    } else {
        Vec::new()
    };
    AttemptView {
        attempt: d.attempt,
        outcome: Some(e.outcome.clone()),
        location: e.package.clone(),
        verified_members: members
            .iter()
            .filter(|m| m.verified)
            .map(|m| m.name.clone())
            .collect(),
        unverified_members: members
            .iter()
            .filter(|m| !m.verified)
            .filter_map(|m| match m.failure.as_deref() {
                Some("not_attempted") => None,
                Some(f) => Some((m.name.clone(), f.to_string())),
                None if m.written => Some((m.name.clone(), "not_verified".to_string())),
                None => None,
            })
            .collect(),
        losses,
        cause: e.cause.clone(),
    }
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

/// Whether the newest verified attempt needs the manager's confirmation
/// through `close --confirm` (8.4): it ended after the first
/// `close_requested`, or it has losses. A copy that verified before close
/// was first requested is the manager's own decision once close is asked
/// for, so it needs none.
pub fn confirmation_required(state: &LogState, d: &log::Delivery) -> bool {
    let Some((rec, e)) = d.ended else {
        return false;
    };
    let after_close = state.close_requested().is_some_and(|cr| rec.n > cr.n);
    let has_losses = e.losses.as_ref().is_some_and(|l| !l.is_empty());
    after_close || has_losses
}

/// The outstanding confirmation, if any: the newest verified attempt and its
/// token, while `closed` is not published and confirmation is required.
pub fn outstanding(audit: &Audit, state: &LogState) -> Option<(u64, String)> {
    if state.closed().is_some() {
        return None;
    }
    let d = state.newest_verified()?;
    if !confirmation_required(state, &d) {
        return None;
    }
    Some((d.attempt, confirmation(audit, state, d.attempt)?))
}

/// Whether every delivery-stage loss of `attempt` now reads and verifies
/// in the archive against the manifest's size and digest (5.8). False when
/// it has none, or its plan cannot be read.
pub fn delivery_losses_now_verify(audit: &Audit, state: &LogState, attempt: u64) -> bool {
    let Some(d) = state
        .deliveries()
        .into_iter()
        .find(|d| d.attempt == attempt)
    else {
        return false;
    };
    let Some((_, e)) = d.ended else {
        return false;
    };
    let pending: Vec<&Loss> = e
        .losses
        .as_deref()
        .unwrap_or(&[])
        .iter()
        .filter(|l| l.stage == "delivery")
        .collect();
    if pending.is_empty() {
        return false;
    }
    let Ok(plan) = returns::load_plan(audit, attempt, &d.plan.plan_sha256) else {
        return false;
    };
    let Some(members) = plan.members else {
        return false;
    };
    pending.iter().all(|l| {
        members
            .iter()
            .find(|m| m.name == l.member)
            .is_some_and(|m| read_source(audit, m).is_ok())
    })
}

/// Sabotage controls of delivery (Appendix C.2). Each breaks exactly one
/// property; none exists in the release build.
#[cfg(feature = "sabotage")]
mod sabotage {
    use super::Work;
    use crate::archive::Audit;
    use crate::bodies::MemberResult;
    use crate::fsx::Dir;

    /// `unknown_membership_empty`: with the manifest unreadable, write an
    /// empty return and record it verified.
    pub fn empty_return(dest: &Dir, package: &str) -> Work {
        let empty = b"{\"schema\":\"stewart.answer/1\",\"revision\":0,\"entries\":[]}\n";
        let written = dest.mkdir(package).is_ok()
            && dest
                .open_dir(package)
                .is_ok_and(|p| p.write_excl("answer.json", empty).is_ok());
        Work {
            outcome: "verified",
            cause: None,
            package: Some(crate::fsx::join(&dest.path, package)),
            members: Some(vec![MemberResult {
                name: "answer.json".into(),
                role: "answer".into(),
                written,
                verified: written,
                failure: None,
            }]),
            losses: Some(vec![]),
        }
    }

    /// `remove_partial_package`: remove the previous attempt's package.
    pub fn remove_package(path: &str) {
        let _ = std::fs::remove_dir_all(path);
    }

    /// `regenerate_rendering`: a fresh rendering with a changed first line.
    pub fn regenerated(bytes: &[u8]) -> Vec<u8> {
        let rest = match bytes.iter().position(|b| *b == b'\n') {
            Some(i) => &bytes[i..],
            None => &[][..],
        };
        let mut out = b"Rendered again by Stewart at delivery.".to_vec();
        out.extend_from_slice(rest);
        out
    }

    /// `deliver_conversation`: add the run's request captures to the
    /// package as `conversation.json`.
    pub fn add_conversation(audit: &Audit, pkg: &Dir) {
        let mut all = Vec::new();
        if let Ok(runs) = audit.dir.open_dir("runs") {
            for r in runs.names().unwrap_or_default() {
                let Ok(d) = runs.open_dir(&r) else { continue };
                for n in d.names().unwrap_or_default() {
                    if n.starts_with("request-") {
                        if let Ok((b, _)) = d.read_regular(&n, 64 * 1024 * 1024) {
                            all.extend_from_slice(&b);
                        }
                    }
                }
            }
        }
        let _ = pkg.write_excl("conversation.json", &all);
    }
}
