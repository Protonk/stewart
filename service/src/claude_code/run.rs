//! One reserved placement, with an independent supervisor and one Rust tool
//! executor. Reader threads forward bytes only; interpretation follows capture.
use super::{
    accounting::{self, Summary},
    events::{Event, Observed},
    fidelity, process, profile, surface,
    wire::{self, Action},
};
use crate::archive::{Audit, Fail};
use crate::gate::Gate;
use crate::provider::{
    Cause, Ending,
    placement::Ended,
    stop::{self, Flags},
    transport::AbortHandle,
};
use crate::reply::Reply;
use crate::rpc::Value;
use crate::usage::Usage;
use crate::{
    answer, bodies, delivery,
    json::{self, J},
    log, runs, world,
};
use std::collections::{BTreeMap, VecDeque};
use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
    mpsc,
};
use std::time::{Duration, Instant};

pub fn run(audit: Audit, state: log::LogState, input: crate::credential::Input) -> Reply {
    let reject = |reason, message: String| {
        crate::ops::run::refuse(&audit, Fail::refused(reason, message), Some(&state))
    };
    let credential_present = !unsafe { libc::getenv(c"ANTHROPIC_API_KEY".as_ptr()) }.is_null()
        || !unsafe { libc::getenv(c"CLAUDE_CODE_OAUTH_TOKEN".as_ptr()) }.is_null();
    if !matches!(input, crate::credential::Input::Environment) || credential_present {
        return reject("runtime_credential_forbidden", "This runtime accepts only the harness-owned subscription login. Remove credential arguments and credential environment variables; no credential was read.".into());
    }
    drop(input);
    let _lock = match audit.try_lock() {
        Ok(Some(lock)) => lock,
        Ok(None) => {
            return reject(
                "run_held",
                "Another process holds this audit's active lock.".into(),
            );
        }
        Err(e) => {
            return reject(
                "record_failed",
                format!("The active lock could not be opened: {e}"),
            );
        }
    };
    let state = log::read(&audit);
    if state.damaged() {
        return crate::ops::run::refuse(&audit, log::damaged_fail(&audit, &state), Some(&state));
    }
    if let Some(f) = crate::ops::run::state_refusal(&audit, &state) {
        return crate::ops::run::refuse(&audit, f, Some(&state));
    }
    if let Err(e) = accounting::ensure_stopped(&audit, &state) {
        // Status observes stopping and the runtime records again; run and
        // close keep refusing until it finds them settled.
        let f = Fail::refused("runtime_stop_unknown", e)
            .next(crate::ops::presentation::observe_stopping_next(&audit));
        return crate::ops::run::refuse(&audit, f, Some(&state));
    }
    let world = match world::load(&audit, &state) {
        Ok(w) => w, Err(_) => return reject("commission_damaged", "The accepted commission could not be loaded intact. Run receipt --verify; no harness was launched.".into()),
    };
    let Some(h) = &world.arrangement.harness else {
        return reject(
            "commission_damaged",
            "Runtime settings and arrangement differ.".into(),
        );
    };
    // The arrangement pins the surface this audit was prepared with; the
    // check must still name the surface this binary supplies.
    let supplied = surface::sha256();
    let checked = if h.surface_sha256 == supplied {
        h.profile
            .check(&supplied, &world.arrangement.model, &h.mcp_tools)
    } else {
        Err(profile::surface_differs(&h.surface_sha256, &supplied))
    };
    if let Err(e) = checked {
        return reject(
            "runtime_profile_invalid",
            format!("{e}. No harness was launched."),
        );
    }
    // A temporary directory that cannot hold a launch directory refuses
    // here, before a start is reserved; the fresh directory is checked again
    // once it exists.
    if let Err(problem) = launch_directory(&audit, &h.profile.temporary_directory) {
        let refusal = Fail::refused(
            "runtime_profile_invalid",
            format!(
                "The profile's temporary_directory cannot hold the private launch directory: {problem}. No placement start was used and no harness was launched."
            ),
        )
        .data(surface::report());
        return crate::ops::run::refuse(&audit, refusal, Some(&state));
    }
    let question = match world
        .question
        .bytes()
        .ok()
        .and_then(|b| String::from_utf8(b).ok())
    {
        Some(q) => q,
        None => {
            return reject(
                "commission_damaged",
                "The captured question cannot be read as UTF-8.".into(),
            );
        }
    };
    if let Some(p) = state.open_placement() {
        if let Err(f) = crate::ops::run::reconcile(&audit, &state, &p) {
            return crate::ops::run::refuse(&audit, f, Some(&state));
        }
    }
    let state = log::read(&audit);
    let used_before = state.recorded_usage();
    let abort = AbortHandle::new();
    let flags = Flags::default();
    if let Err(e) = stop::block_signals() {
        return reject(
            "record_failed",
            format!("Could not prepare stop handling: {e}"),
        );
    }
    let run = state.next_run();
    let started = bodies::RunStarted {
        run,
        arrangement_sha256: world.arrangement_sha256.clone(),
        provider: None,
        runtime: Some(accounting::Start {
            profile_sha256: h.profile_sha256.clone(),
            placement_timeout_seconds: h.selection.limits.placement_timeout_seconds,
        }),
        observations: bodies::RunObservations::current(),
    };
    let began = Instant::now();
    let deadline = began + Duration::from_secs(h.selection.limits.placement_timeout_seconds);
    let gate = Gate::new(deadline);
    let signal_gate = gate.clone();
    if let Err(e) = stop::receive_signals(abort.clone(), flags.clone(), move || signal_gate.stop())
    {
        return reject(
            "record_failed",
            format!("Could not prepare stop handling: {e}"),
        );
    }
    // The slot is reserved as on the Messages runtime. A start beyond the
    // placement allowance is refused there: the final placement's ending
    // ended authoring (INTERFACE 1.6).
    let reserved = crate::ops::run::reserve(&audit, &state, &started);
    let started_n = match reserved {
        Ok(n) => n,
        Err(reply) => return reply,
    };
    let mut ended = Ended {
        ending: Ending::Interrupted(Cause::ProtocolAnomaly),
        log_damaged: false,
        provider: None,
        requests: 0,
        attempts: 0,
        usage: Usage {
            harness: Some(Summary::reserved()),
            ..Usage::default()
        },
        seen: BTreeMap::new(),
        entries: false,
        seal: None,
        delivered: None,
        message: String::new(),
    };
    let mut fidelity_diagnostics = Vec::new();
    let mut later = Later::default();
    match runs::RunDir::create(&audit, run) {
        Err(e) => {
            ended.ending = Ending::Interrupted(Cause::ArchiveWriteFailed);
            ended.message = e.error;
            ended.usage.harness.as_mut().unwrap().stopped = 1;
        }
        Ok(dir) => {
            let live = Live {
                audit: &audit,
                world: &world,
                dir: &dir,
                run,
                max_placements: h.selection.limits.max_placements,
                question: &question,
                deadline,
                used_before,
                flags: &flags,
                gate: &gate,
                record_failed: AtomicBool::new(false),
                fidelity_diagnostics: Mutex::new(Vec::new()),
            };
            let mut workspace = None;
            if let Err(e) = execute(&live, &mut ended, &mut later, &mut workspace) {
                ended.message = e;
            }
            fidelity_diagnostics = live
                .fidelity_diagnostics
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .clone();
            // From here on the ending is decided. What the owner observes
            // now, including its own failures to retain the stop observation
            // or the final checkpoint, changes the accounting, not the ending.
            let usage = ended.usage.harness.as_mut().unwrap();
            if live.record_failed.load(Ordering::SeqCst) {
                usage.unknown_intervals = 1;
            }
            let groups = accounting::groups_gone(&audit, run);
            let gone = matches!(groups, Ok(true));
            usage.stopped = u64::from(gone);
            if gone {
                // Absence is established, so nothing launched can still be
                // using the private launch directory.
                if let Some(workspace) = &workspace {
                    let _ = std::fs::remove_dir_all(workspace);
                }
            } else {
                ended.message.push_str(&format!(" Stopping is unconfirmed: {groups:?}. Further starts and close cleanup are blocked."));
            }
            let stop = J::obj()
                .with(
                    "elapsed_ms",
                    began.elapsed().as_millis().min(u64::MAX as u128) as u64,
                )
                .with(
                    "deadline_ms",
                    h.selection.limits.placement_timeout_seconds * 1000,
                )
                .with("groups_gone", gone);
            if let Err(e) = dir.dir.write_excl("runtime-stop.json", &stop.bytes()) {
                // Without its retained observation, stopping stays unknown.
                usage.stopped = 0;
                ended.message.push_str(&format!(
                    " Stop observation could not be retained: {}.",
                    e.err
                ));
            }
            if let Err(e) = checkpoint(&dir, *usage) {
                usage.unknown_intervals = 1;
                ended
                    .message
                    .push_str(&format!(" Usage checkpoint could not be retained: {e}."));
            }
        }
    }
    let current = log::read(&audit);
    let sealed_here = current
        .seal()
        .filter(|(rec, _)| rec.n > started_n)
        .map(|(rec, _)| rec.name());
    later.sealed_here = sealed_here.is_some();
    ended.ending = ending(ended.ending, &later);
    ended.entries = current.entries().any(|(_, e)| e.invocation.run == run);
    if let Some(seal) = sealed_here {
        flags.set_sealed();
        ended.seal = Some(seal);
        if ended.usage.harness.unwrap().stopped == 1 {
            if let Some(destination) = crate::ops::run::destination(&current) {
                ended.delivered = Some(delivery::deliver(
                    &audit,
                    &current,
                    &delivery::Request {
                        by: delivery::By::Run,
                        destination: delivery::Destination {
                            path: destination,
                            source: "commissioned",
                        },
                        retries_losses_of: None,
                        stop: Some(flags.signalled.clone()),
                    },
                ));
            }
        }
    }
    if ended.message.is_empty() {
        ended.message =
            "The harness placement stopped; retained captures describe the observed boundary."
                .into();
    }
    let mut reply = crate::ops::run::finish(&audit, run, started_n, ended);
    for diagnostic in fidelity_diagnostics {
        match diagnostic {
            Ok(path) => {
                if !reply.retained.contains(&path) {
                    reply.retained.push(path);
                }
                if !reply.effects.contains(&("diagnostic", "reported_only")) {
                    reply.set_effect("diagnostic", "durable");
                }
            }
            Err(cause) => {
                reply.set_effect("diagnostic", "reported_only");
                reply
                    .causes
                    .push(crate::reply::Cause::new("run", fidelity::REASON));
                reply.causes.push(cause);
                if let Some(J::Obj(data)) = &mut reply.data {
                    if let Some((_, J::Str(summary))) =
                        data.iter_mut().find(|(key, _)| key == "summary")
                    {
                        summary.push_str("\nWarning: runtime_reply_mismatch was observed, but its diagnostic could not be retained. Original captures remain the evidence; review before continuation.");
                    }
                }
            }
        }
    }
    reply
}

/// The two observations that still change a placement's ending once the
/// first stopping condition its owner observed has decided it (runtime
/// contract). Nothing else the owner observes later, during shutdown, the
/// drain or its own final writes, reaches the ending: not a signal, a close
/// request, the deadline, a call that finished during the drain, or a
/// failure to retain the stop observation or the final checkpoint.
#[derive(Clone, Copy, Debug, Default)]
struct Later {
    /// A changed tool reply was first observed during the shutdown drain.
    drain_mismatch: bool,
    /// The log, read after shutdown, holds a seal this placement published,
    /// after its `run_started`.
    sealed_here: bool,
}

/// The ending a placement records when the first stopping condition its
/// owner observed decided `decided` and the owner then observed `later`: a
/// seal this placement published makes it `sealed`, and a reply mismatch
/// first observed during the drain turns `ended_unsubmitted` into
/// `interrupted` (`protocol_anomaly`), since the auditor ended after
/// receiving a changed reply. Any other decided ending stands.
fn ending(decided: Ending, later: &Later) -> Ending {
    if later.sealed_here {
        Ending::Sealed
    } else if later.drain_mismatch && decided == Ending::EndedUnsubmitted {
        Ending::Interrupted(Cause::ProtocolAnomaly)
    } else {
        decided
    }
}

/// The ending a passed deadline gives placement `run`: `interrupted`
/// (`placement_deadline`) while further starts remain, `limit_reached` on
/// the last commissioned placement.
fn deadline_ending(run: u64, max_placements: u64) -> Ending {
    if run >= max_placements {
        Ending::LimitReached
    } else {
        Ending::Interrupted(Cause::PlacementDeadline)
    }
}

/// What the owner sees of the conditions that stop a placement from outside
/// it, at one point: a close request and a seal in the log, a received stop
/// signal and the deadline.
#[derive(Clone, Copy, Debug, Default)]
struct Outside {
    sealed: bool,
    close_requested: bool,
    signalled: bool,
    past_deadline: bool,
}

impl Outside {
    /// The ending of the condition among them that stops the placement at
    /// this point, if any: close precedes a signal, and a signal precedes
    /// the deadline. Close and a signal stop a placement only while it has
    /// no seal; the seal decides then.
    fn ending(self, run: u64, max_placements: u64) -> Option<Ending> {
        if !self.sealed && self.close_requested {
            Some(Ending::StoppedByClose)
        } else if !self.sealed && self.signalled {
            Some(Ending::Interrupted(Cause::Signal))
        } else if self.past_deadline {
            Some(deadline_ending(run, max_placements))
        } else {
            None
        }
    }
}

/// A stopping condition the placement's owner observed, with what the
/// placement's `run_ended` message says about it. The first one observed
/// decides the placement's ending (runtime contract).
#[derive(Debug)]
struct Stopped {
    condition: Condition,
    message: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Condition {
    /// The ending the owner established where it observed the condition.
    Ending(Ending),
    /// The deadline, observed by a clock check alone. Close and a received
    /// signal, observed at the same point, precede it.
    Deadline,
    /// A condition the contract gives no other cause, such as a harness
    /// error, exit or violation, a startup or wire rule violation, or a
    /// frame or capture bound: `interrupted` with cause `protocol_anomaly`.
    Unexplained,
}

impl Stopped {
    fn ending(ending: Ending, message: impl Into<String>) -> Self {
        Self {
            condition: Condition::Ending(ending),
            message: message.into(),
        }
    }
    /// An archive write of the placement failed.
    fn write_failed(message: impl Into<String>) -> Self {
        Self::ending(Ending::Interrupted(Cause::ArchiveWriteFailed), message)
    }
}

impl From<String> for Stopped {
    fn from(message: String) -> Self {
        Self {
            condition: Condition::Unexplained,
            message,
        }
    }
}

impl From<&str> for Stopped {
    fn from(message: &str) -> Self {
        message.to_string().into()
    }
}

struct Live<'a> {
    audit: &'a Audit,
    world: &'a world::World,
    dir: &'a runs::RunDir,
    run: u64,
    max_placements: u64,
    question: &'a str,
    deadline: Instant,
    used_before: Usage,
    flags: &'a Flags,
    gate: &'a Gate,
    record_failed: AtomicBool,
    fidelity_diagnostics: Mutex<Vec<Result<String, crate::reply::Cause>>>,
}

impl Live<'_> {
    fn record_error(&self, message: impl Into<String>) -> Stopped {
        self.record_failed.store(true, Ordering::SeqCst);
        Stopped::write_failed(message)
    }
    fn write(&self, name: &str, bytes: &[u8]) -> Result<(), Stopped> {
        self.dir
            .dir
            .write_excl(name, bytes)
            .map_err(|e| self.record_error(format!("retain {name}: {}", e.err)))
    }
    /// The outside conditions as the owner observes them now.
    fn outside(&self) -> Outside {
        let state = log::read(self.audit);
        Outside {
            sealed: state.seal().is_some(),
            close_requested: state.close_requested().is_some(),
            signalled: self.flags.signalled.load(Ordering::SeqCst),
            past_deadline: Instant::now() >= self.deadline,
        }
    }
    /// The ending `condition` gives, decided now: the deadline yields to a
    /// close request or a signal observed with it.
    fn decide(&self, condition: Condition) -> Ending {
        match condition {
            Condition::Ending(ending) => ending,
            Condition::Deadline => Outside {
                past_deadline: true,
                ..self.outside()
            }
            .ending(self.run, self.max_placements)
            .expect("a passed deadline stops the placement"),
            Condition::Unexplained => Ending::Interrupted(Cause::ProtocolAnomaly),
        }
    }
    /// A stop whose clock check found the deadline passed, decided now.
    fn at_deadline(&self, message: impl Into<String>) -> Stopped {
        Stopped::ending(self.decide(Condition::Deadline), message)
    }
    /// The harness, or part of it, ended without a settled result. Once the
    /// deadline has passed, its supervisor stopped it at the deadline, so
    /// the deadline is the condition observed; before it the exit is
    /// unexplained.
    fn harness_ended(&self, message: impl Into<String>) -> Stopped {
        if Instant::now() >= self.deadline {
            self.at_deadline(message)
        } else {
            Stopped::from(message.into())
        }
    }
}

/// Why `path` cannot hold the private launch directory, if it cannot
/// (runtime contract): neither it nor any ancestor may hold an entry named
/// `.git`, `CLAUDE.md`, `AGENTS.md` or `.claude`, every ancestor must be
/// inspectable, and it may not be or lie within the archive, the submission
/// folder or the writer's directory.
fn launch_directory(audit: &Audit, path: &str) -> Result<(), String> {
    for parent in std::path::Path::new(path).ancestors() {
        for marker in [".git", "CLAUDE.md", "AGENTS.md", ".claude"] {
            match std::fs::symlink_metadata(parent.join(marker)) {
                Ok(_) => {
                    return Err(format!(
                        "{} holds {marker}, so the harness would find project or configuration files there; choose a temporary_directory outside any such tree",
                        parent.display()
                    ));
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                Err(e) => {
                    return Err(format!(
                        "cannot inspect {} for project or configuration files: {e}",
                        parent.display()
                    ));
                }
            }
        }
    }
    let writer = &audit.refile.writer_path;
    for (what, root) in [
        ("the archive", audit.archive.path.as_str()),
        ("the submission folder", audit.refile.folder.as_str()),
        (
            "the writer's directory",
            match writer.rsplit_once('/') {
                Some(("", _)) => "/",
                Some((dir, _)) => dir,
                None => writer.as_str(),
            },
        ),
    ] {
        let inside = root.trim_end_matches('/');
        if path == root || path.starts_with(&format!("{inside}/")) {
            return Err(format!("{path} is or lies within {what}, {root}"));
        }
    }
    Ok(())
}

fn checkpoint(dir: &runs::RunDir, usage: Summary) -> Result<(), String> {
    let next = dir
        .dir
        .names()
        .map_err(|e| e.to_string())?
        .iter()
        .filter_map(|n| {
            n.strip_prefix("runtime-usage-")?
                .strip_suffix(".json")?
                .parse::<u64>()
                .ok()
        })
        .max()
        .unwrap_or(0)
        + 1;
    dir.dir
        .write_excl(&format!("runtime-usage-{next}.json"), &usage.to_j().bytes())
        .map_err(|e| e.err.to_string())
}
struct Capture<'a> {
    dir: &'a runs::RunDir,
    sequence: u64,
    bytes: usize,
    record_failed: &'a AtomicBool,
    deadline: Instant,
}
const CAPTURE_LIMIT: usize = 256 * 1024 * 1024;
const CAPTURE_EXCEEDED: &str =
    "placement capture exceeded 256 MiB; stopping with an uncovered interval";

impl Capture<'_> {
    /// Retain `bytes` as the next capture of `channel`. `Ok` means the
    /// capture is complete; it holds false once the placement's captures
    /// exceed their bound, so the placement must stop.
    fn retain(&mut self, channel: &str, bytes: &[u8]) -> Result<bool, Stopped> {
        self.sequence += 1;
        self.dir
            .dir
            .write_excl(&format!("runtime-{}-{channel}.bin", self.sequence), bytes)
            .map_err(|e| {
                self.record_failed.store(true, Ordering::SeqCst);
                Stopped::write_failed(format!(
                    "capture failed before interpretation/transmission: {}",
                    e.err
                ))
            })?;
        self.bytes = self.bytes.saturating_add(bytes.len());
        Ok(self.bytes <= CAPTURE_LIMIT)
    }
    fn raw(&mut self, channel: &str, bytes: &[u8]) -> Result<(), Stopped> {
        if !self.retain(channel, bytes)? {
            return Err(CAPTURE_EXCEEDED.into());
        }
        Ok(())
    }
    /// Capture bytes about to be transmitted on `channel`: nothing is
    /// captured once the deadline has passed. As for `retain`, `Ok` means
    /// the capture is complete.
    fn outgoing(&mut self, channel: &str, bytes: &[u8]) -> Result<bool, Stopped> {
        if Instant::now() >= self.deadline {
            return Err(Stopped {
                condition: Condition::Deadline,
                message: "placement deadline reached before transmission".into(),
            });
        }
        self.retain(channel, bytes)
    }
    fn send(&mut self, channel: &str, out: &mut impl Write, bytes: &[u8]) -> Result<(), Stopped> {
        self.for_send(channel, bytes)?;
        out.write_all(bytes)
            .map_err(|e| self.write_failed(channel, e))
    }
    /// The stop a failed write on `channel` gives. The supervisor stops the
    /// harness group at the deadline on its own clock, so a write found
    /// failed once the deadline has passed failed at that stop: the
    /// deadline is the condition observed, as for a harness exit. Before
    /// it the failure is unexplained.
    fn write_failed(&self, channel: &str, e: std::io::Error) -> Stopped {
        let message = format!("{channel} write failed: {e}");
        if Instant::now() >= self.deadline {
            Stopped {
                condition: Condition::Deadline,
                message,
            }
        } else {
            message.into()
        }
    }
    fn for_send(&mut self, channel: &str, bytes: &[u8]) -> Result<(), Stopped> {
        if !self.outgoing(channel, bytes)? {
            return Err(CAPTURE_EXCEEDED.into());
        }
        Ok(())
    }
}

/// Transmit a notice's input `frame` to the harness: capture it completely,
/// then write it in full to `out`. `seen` records how far it got, which is
/// what the notice's `sent` reports (runtime contract): nothing while the
/// frame was never captured completely (`not_sent`), captured once it was
/// (`unknown`, also when its write did not complete), and written once it
/// was written in full (`sent`).
fn transmit(
    cap: &mut Capture<'_>,
    out: &mut impl Write,
    frame: &[u8],
    seen: &mut Option<crate::provider::placement::Seen>,
) -> Result<(), Stopped> {
    let within = cap.outgoing("input", frame)?;
    *seen = Some(crate::provider::placement::Seen {
        captured: true,
        written: false,
    });
    if !within {
        return Err(CAPTURE_EXCEEDED.into());
    }
    out.write_all(frame)
        .map_err(|e| cap.write_failed("input", e))?;
    *seen = Some(crate::provider::placement::Seen {
        captured: true,
        written: true,
    });
    Ok(())
}

/// Report the changed replies the fidelity observer found, if any. A
/// mismatch closes the gate before any diagnostic I/O and decides the
/// placement's ending when it is the first condition observed; a
/// diagnostic that cannot be retained is reported, and the mismatch still
/// decides.
fn fidelity_mismatches(
    live: &Live,
    fidelity: &mut fidelity::Observer,
    phase: &str,
) -> Result<bool, Stopped> {
    let contexts = fidelity.mismatches(live.run, phase);
    if contexts.is_empty() {
        return Ok(false);
    }
    live.gate.stop();
    let seal = log::read(live.audit).seal().map(|(r, _)| r.name());
    for mut context in contexts {
        if let J::Obj(fields) = &mut context {
            for (key, value) in fields {
                if key == "seal_record" {
                    *value = seal.clone().map(J::Str).unwrap_or(J::Null);
                }
            }
        }
        let diagnostic = live.audit.write_diag(J::obj()
            .with("operation", "run").with("outcome", "failed")
            .with("reason", fidelity::REASON)
            .with("message", "The captured conversation changed a supplied tool reply. The placement gate stopped further authoring; already published effects and any seal remain unchanged.")
            .with("context", context));
        live.fidelity_diagnostics
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .push(diagnostic.clone());
        diagnostic.map_err(|e| {
            let unretained = live.record_error(format!(
                "runtime_reply_mismatch; diagnostic could not be retained: {}: {}",
                e.operation, e.error
            ));
            Stopped::ending(
                Ending::Interrupted(Cause::ProtocolAnomaly),
                unretained.message,
            )
        })?;
    }
    Ok(true)
}

fn drain_stdout(
    live: &Live,
    observed: &mut Observed,
    fidelity: &mut fidelity::Observer,
    output: &mut Vec<u8>,
    offset: &mut u64,
    drain_mismatch: &mut bool,
    error: &mut Option<String>,
) {
    let h = live.world.arrangement.harness.as_ref().unwrap();
    while let Some(end) = output.iter().position(|b| *b == b'\n') {
        let raw: Vec<_> = output.drain(..=end).collect();
        let at = *offset;
        *offset += raw.len() as u64;
        if end > wire::FRAME_LIMIT {
            *error = Some("runtime frame exceeds 8 MiB during drain".into());
            continue;
        }
        if raw.iter().all(u8::is_ascii_whitespace) {
            continue;
        }
        if let Err(e) = observed.receive(&raw, h, &live.world.arrangement.tool_names) {
            *error = Some(e);
        }
        fidelity.stdout(&raw, at);
        match fidelity_mismatches(live, fidelity, "drain") {
            Ok(true) => *drain_mismatch = true,
            Ok(false) => (),
            Err(e) => {
                *drain_mismatch = true;
                *error = Some(e.message);
            }
        }
    }
}

enum Input {
    Bytes(&'static str, Vec<u8>),
    Eof(&'static str),
    Error(String),
    Mcp(UnixStream),
    Hook(UnixStream, Vec<u8>),
    ToolFinished,
}
fn accepted_stream(stream: UnixStream) -> std::io::Result<UnixStream> {
    // BSD sockets inherit the listener's nonblocking flag. Only accept is
    // polled; each connected reader must wait through idle intervals.
    stream.set_nonblocking(false)?;
    Ok(stream)
}

const MCP_READ_INTERVAL: Duration = Duration::from_millis(100);

struct McpInput(UnixStream);
impl McpInput {
    fn new(stream: UnixStream) -> std::io::Result<Self> {
        // On the development Mac, a blocked socket read can miss a peer's
        // write-half shutdown even though a new read observes EOF. Periodic
        // reads recover that observation without treating idle time as loss.
        // The placement supervisor still owns the execution deadline.
        stream.set_read_timeout(Some(MCP_READ_INTERVAL))?;
        Ok(Self(stream))
    }
}
impl Read for McpInput {
    fn read(&mut self, bytes: &mut [u8]) -> std::io::Result<usize> {
        loop {
            match self.0.read(bytes) {
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                    ) => {}
                result => return result,
            }
        }
    }
}

fn reader(mut input: impl Read, channel: &'static str, tx: mpsc::SyncSender<Input>) {
    loop {
        let mut bytes = vec![0; 65536];
        match input.read(&mut bytes) {
            Ok(0) => {
                let _ = tx.send(Input::Eof(channel));
                break;
            }
            Ok(n) => {
                bytes.truncate(n);
                if tx.send(Input::Bytes(channel, bytes)).is_err() {
                    break;
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => (),
            Err(e) => {
                let _ = tx.send(Input::Error(format!("{channel} read failed: {e}")));
                break;
            }
        }
    }
}
/// Run placement `live` and set `ended.ending` to the ending decided by the
/// first stopping condition its owner observed, returning the message its
/// `run_ended` gives that condition. The private launch directory, once
/// created, is named in `workspace`; the caller removes it once it observes
/// that the launched groups are gone.
fn execute(
    live: &Live,
    ended: &mut Ended,
    later: &mut Later,
    workspace: &mut Option<String>,
) -> Result<(), String> {
    place(live, ended, later, workspace).map_err(|stopped| {
        ended.ending = live.decide(stopped.condition);
        stopped.message
    })
}

/// Launch the harness for placement `live` and run its owner loop.
fn place(
    live: &Live,
    ended: &mut Ended,
    later: &mut Later,
    created: &mut Option<String>,
) -> Result<(), Stopped> {
    let h = live.world.arrangement.harness.as_ref().unwrap();
    let tmp = crate::fsx::Dir::open_nofollow(&h.profile.temporary_directory)
        .map_err(|e| format!("private working directory parent: {e:?}"))?;
    let name = format!(
        "stewart-{}",
        crate::ids::random_token().map_err(|e| e.to_string())?
    );
    tmp.mkdir(&name).map_err(|e| e.to_string())?;
    let workspace = format!(
        "{}/{}",
        h.profile.temporary_directory.trim_end_matches('/'),
        name
    );
    *created = Some(workspace.clone());
    let cwd = tmp.open_dir(&name).map_err(|e| e.to_string())?;
    // The temporary directory passed these checks before the start was
    // reserved. Check the fresh directory, as it now exists, before the
    // first harness invocation; a failure here has used the start.
    launch_directory(live.audit, &workspace)
        .map_err(|problem| format!("private launch directory refused: {problem}"))?;
    // The owner and both harness helpers use this same private working
    // directory. Relative socket names avoid sockaddr_un's short path bound
    // on macOS, including its normal long TMPDIR. All audit I/O is descriptor
    // relative or absolute; the signal thread does not use the working directory.
    std::env::set_current_dir(&workspace).map_err(|e| e.to_string())?;
    let mut cap = Capture {
        dir: live.dir,
        sequence: 0,
        bytes: 0,
        record_failed: &live.record_failed,
        deadline: live.deadline,
    };
    let auth = authenticate(live, &workspace)?;
    live.write("runtime-auth.json", &auth.bytes())?;
    let mcp_path = surface::MCP_SOCKET;
    let hook_path = surface::HOOK_SOCKET;
    let mcp_listener = UnixListener::bind(mcp_path)
        .map_err(|e| format!("bind private MCP socket in {workspace}: {e}"))?;
    let hook_listener = UnixListener::bind(hook_path)
        .map_err(|e| format!("bind private hook socket in {workspace}: {e}"))?;
    mcp_listener
        .set_nonblocking(true)
        .map_err(|e| e.to_string())?;
    hook_listener
        .set_nonblocking(true)
        .map_err(|e| e.to_string())?;
    // Every value supplied to the harness comes from the launch surface's
    // builders, filled with this placement's paths and the pinned model.
    let slots = surface::Slots::launch(&h.profile, &workspace, &live.audit.refile.writer_path);
    let environment = surface::environment(&slots);
    for (name, bytes) in [
        ("settings.json", surface::settings(&slots).bytes()),
        ("mcp.json", surface::mcp_config(&slots).bytes()),
        ("system.txt", h.system_prompt.as_bytes().to_vec()),
    ] {
        live.write(&format!("runtime-{name}"), &bytes)?;
        cwd.write_excl(name, &bytes)
            .map_err(|e| e.err.to_string())?;
    }
    let mut args = surface::model_argv(&slots, &live.world.arrangement.tool_names);
    if let Some(effort) = &h.effort {
        args.extend(surface::effort_argv(effort));
    }
    let launch = J::obj()
        .with("argv", json::strs(&args))
        .with("cwd", slots.workspace)
        .with("environment", surface::environment_j(&slots));
    live.write("runtime-launch.json", &launch.bytes())?;
    if Instant::now() >= live.deadline {
        return Err(live.at_deadline("placement deadline expired during startup"));
    }
    let mut owner = process::Owned::start(
        slots.writer,
        &h.profile.executable,
        &environment,
        slots.workspace,
        &args,
        live.deadline.saturating_duration_since(Instant::now()),
        live.dir,
        "model",
    )?;
    let mut stdin = owner.child.stdin.take().ok_or("missing harness stdin")?;
    let stdout = owner.child.stdout.take().ok_or("missing harness stdout")?;
    let stderr = owner.child.stderr.take().ok_or("missing harness stderr")?;
    let gate = live.gate;
    let quitting = Arc::new(AtomicBool::new(false));
    std::thread::scope(|scope| {
        let (tx, rx) = mpsc::sync_channel(16);
        for (channel, input) in [
            ("stdout", Box::new(stdout) as Box<dyn Read + Send>),
            ("stderr", Box::new(stderr)),
        ] {
            let tx = tx.clone();
            scope.spawn(move || reader(input, channel, tx));
        }
        let tx_m = tx.clone();
        let quit_m = quitting.clone();
        scope.spawn(move || {
            while !quit_m.load(Ordering::SeqCst) {
                match mcp_listener.accept().and_then(|(s, _)| accepted_stream(s)) {
                    Ok(stream) => {
                        let _ = tx_m.send(Input::Mcp(stream));
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(Duration::from_millis(10))
                    }
                    Err(e) => {
                        let _ = tx_m.send(Input::Error(e.to_string()));
                        break;
                    }
                }
            }
        });
        let tx_h = tx.clone();
        let quit_h = quitting.clone();
        scope.spawn(move || {
            while !quit_h.load(Ordering::SeqCst) {
                match hook_listener.accept().and_then(|(s, _)| accepted_stream(s)) {
                    Ok(mut stream) => {
                        let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
                        let mut b = Vec::new();
                        match (&mut stream)
                            .take(wire::FRAME_LIMIT as u64 + 1)
                            .read_to_end(&mut b)
                        {
                            Ok(_) => {
                                if tx_h.send(Input::Hook(stream, b)).is_err() {
                                    break;
                                }
                            }
                            Err(e) => {
                                let _ = tx_h.send(Input::Error(format!("hook capture read: {e}")));
                                break;
                            }
                        }
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(Duration::from_millis(10))
                    }
                    Err(e) => {
                        let _ = tx_h.send(Input::Error(e.to_string()));
                        break;
                    }
                }
            }
        });
        let mut connection: Option<UnixStream> = None;
        let mut observed = Observed::default();
        let mut fidelity = fidelity::Observer::default();
        let mut stdout_offset = 0u64;
        let mut drain_mismatch = false;
        let mut mcp = wire::Mcp::default();
        let mut output = Vec::new();
        let mut incoming = Vec::new();
        let mut pending: Option<RunningCall<'_>> = None;
        let mut waiting = Waiting::default();
        let start_tool = |task: Pending, usage: Summary| {
            let mut used = live.used_before;
            used.add(&Usage {
                harness: Some(usage),
                ..Usage::default()
            });
            let state = log::read(live.audit);
            let placement = answer::Placement {
                run: live.run,
                continuing: live.run > 1,
                used,
                limits: live.world.arrangement.limits,
                notices_used: answer::NoticesUsed {
                    reminder: state.notice_used("reminder"),
                    near_limit: state.notice_used("near_limit"),
                },
            };
            let worker = task.clone();
            let tx = tx.clone();
            let handle = scope.spawn(move || {
                let call_id = format!("mcp-{}", worker.call);
                let call = worker.as_call(&call_id);
                let result = dispatch(live.audit, live.world, &placement, &call, &worker.gate);
                let _ = tx.send(Input::ToolFinished);
                result
            });
            RunningCall { task, handle }
        };
        let mut calls = 0u64;
        let mut readers = 2usize;
        let mut eof = std::collections::BTreeSet::new();
        // The loop returns at the first stopping condition the owner
        // observes, with the ending that condition gives.
        let outcome = (|| -> Result<Ending, Stopped> {
            cap.send("input", &mut stdin, &wire::user(live.question))?;
            if live.run > 1 {
                cap.send(
                    "input",
                    &mut stdin,
                    &wire::user(&live.world.arrangement.continuation),
                )?;
            }
            loop {
                let state = log::read(live.audit);
                if state.damaged() {
                    ended.log_damaged = true;
                    return Err("audit log damaged during placement".into());
                }
                let outside = Outside {
                    sealed: state.seal().is_some(),
                    close_requested: state.close_requested().is_some(),
                    signalled: live.flags.signalled.load(Ordering::SeqCst),
                    past_deadline: Instant::now() >= live.deadline,
                };
                match outside.ending(live.run, live.max_placements) {
                    Some(
                        ending @ (Ending::StoppedByClose | Ending::Interrupted(Cause::Signal)),
                    ) => {
                        return Ok(ending);
                    }
                    Some(deadline) => {
                        return Err(Stopped::ending(
                            deadline,
                            "placement deadline reached; stopping the harness group",
                        ));
                    }
                    None => (),
                }
                if observed.initialized && !state.notice_used("near_limit") {
                    let left = live.deadline.saturating_duration_since(Instant::now());
                    if let Some((text, remaining)) = near_limit_notice(
                        left,
                        h.selection.limits,
                        live.run,
                        &live.world.arrangement.near_limit,
                    ) {
                        notice(
                            live,
                            ended,
                            &mut cap,
                            &mut stdin,
                            "near_limit",
                            &text,
                            Some(remaining),
                        )?;
                    }
                }
                let event = match rx.recv_timeout(Duration::from_millis(25)) {
                    Ok(e) => e,
                    Err(mpsc::RecvTimeoutError::Timeout) => continue,
                    Err(_) => return Err("runtime observers disconnected".into()),
                };
                match event {
                    Input::Error(e) => return Err(e.into()),
                    Input::Eof(channel) => {
                        eof.insert(channel);
                        if channel == "stdout" {
                            return Err(live.harness_ended(
                                "harness stdout ended without a settled placement result",
                            ));
                        }
                        if channel == "mcp" && pending.is_some() {
                            return Err(
                                live.harness_ended("MCP disconnected with a tool in flight")
                            );
                        }
                    }
                    Input::Mcp(stream) => {
                        if connection.is_some() {
                            return Err("unexpected second MCP attachment".into());
                        }
                        stream
                            .set_write_timeout(Some(Duration::from_secs(2)))
                            .map_err(|e| e.to_string())?;
                        let input = McpInput::new(stream.try_clone().map_err(|e| e.to_string())?)
                            .map_err(|e| format!("configure MCP reader: {e}"))?;
                        let tx = tx.clone();
                        scope.spawn(move || reader(input, "mcp", tx));
                        connection = Some(stream);
                        readers += 1;
                    }
                    Input::Hook(mut stream, bytes) => {
                        cap.raw("hook-in", &bytes)?;
                        if bytes.len() > wire::FRAME_LIMIT {
                            return Err("hook frame too large".into());
                        }
                        let allowed = Value::parse(&bytes)
                            .and_then(|v| v.text("tool_name"))
                            .is_ok_and(|name| {
                                observed.initialized
                                    && live
                                        .world
                                        .arrangement
                                        .tool_names
                                        .iter()
                                        .any(|n| name == surface::tool_name(n))
                            })
                            && gate.permit().is_ok();
                        let reply = surface::hook_reply(allowed);
                        cap.send("hook-out", &mut stream, &wire::line(reply))?;
                        fidelity.hook(&bytes, allowed);
                        if fidelity_mismatches(live, &mut fidelity, "live")? {
                            return Err(mismatch());
                        }
                    }
                    Input::Bytes(channel, bytes) => {
                        cap.raw(channel, &bytes)?;
                        let buffer = match channel {
                            "stdout" => &mut output,
                            "mcp" => &mut incoming,
                            _ => continue,
                        };
                        buffer.extend_from_slice(&bytes);
                        while let Some(end) = buffer.iter().position(|b| *b == b'\n') {
                            if end > wire::FRAME_LIMIT {
                                return Err("runtime frame exceeds 8 MiB".into());
                            }
                            let raw: Vec<u8> = buffer.drain(..=end).collect();
                            let at = stdout_offset;
                            if channel == "stdout" {
                                stdout_offset += raw.len() as u64;
                            }
                            if raw.iter().all(u8::is_ascii_whitespace) {
                                continue;
                            }
                            if channel == "stdout" {
                                let event = observed.receive(
                                    &raw,
                                    h,
                                    &live.world.arrangement.tool_names,
                                )?;
                                fidelity.stdout(&raw, at);
                                if fidelity_mismatches(live, &mut fidelity, "live")? {
                                    return Err(mismatch());
                                }
                                match event {
                                    Event::Compacted => {
                                        cap.send(
                                            "input",
                                            &mut stdin,
                                            &wire::user(&live.world.arrangement.compacted),
                                        )?;
                                    }
                                    Event::Result { error } => {
                                        checkpoint(live.dir, observed.usage)
                                            .map_err(|e| live.record_error(e))?;
                                        if error {
                                            return Err("harness returned an error result; earlier usage checkpoints retained".into());
                                        }
                                        if pending.is_some() {
                                            return Err(
                                                "result arrived while a tool was still executing"
                                                    .into(),
                                            );
                                        }
                                        if log::read(live.audit).seal().is_some() {
                                            // No reminder follows a seal. A
                                            // seal this placement published
                                            // makes the ending `sealed`;
                                            // otherwise this stop has no
                                            // other cause.
                                            return Ok(Ending::Interrupted(Cause::ProtocolAnomaly));
                                        }
                                        if !log::read(live.audit).notice_used("reminder") {
                                            notice(
                                                live,
                                                ended,
                                                &mut cap,
                                                &mut stdin,
                                                "reminder",
                                                &live.world.arrangement.reminder,
                                                None,
                                            )?;
                                            observed.usage.unknown_intervals = 1;
                                        } else {
                                            return Ok(Ending::EndedUnsubmitted);
                                        }
                                    }
                                    _ => (),
                                }
                            } else {
                                match mcp.receive(&raw, &h.mcp_tools) {
                                    Action::Silent => (),
                                    Action::Cancel(key) => {
                                        if let Some(p) = &pending {
                                            if p.task.key == key {
                                                p.task.gate.cancel();
                                            }
                                        }
                                        waiting.cancel(&key);
                                    }
                                    Action::Reply(value) => cap.send(
                                        "mcp-out",
                                        connection.as_mut().ok_or("MCP missing")?,
                                        &wire::line(value),
                                    )?,
                                    Action::Call {
                                        id,
                                        key,
                                        name,
                                        arguments,
                                    } => {
                                        if !observed.initialized || gate.permit().is_err() {
                                            cap.send(
                                                "mcp-out",
                                                connection.as_mut().unwrap(),
                                                &wire::line(crate::rpc::error(
                                                    &id,
                                                    -32000,
                                                    "startup is unvalidated or placement stopped",
                                                )),
                                            )?;
                                            continue;
                                        }
                                        if pending.is_some() && !waiting.can_admit(raw.len()) {
                                            cap.send("mcp-out", connection.as_mut().unwrap(), &wire::line(crate::rpc::error(&id, -32000, "tool queue limit: at most 32 waiting calls and 16 MiB of request frames; this call was not admitted")))?;
                                            continue;
                                        }
                                        calls += 1;
                                        live.dir
                                            .write_call(calls, &raw)
                                            .map_err(|e| live.record_error(e.error))?;
                                        let task = Pending {
                                            id,
                                            key,
                                            name,
                                            arguments,
                                            raw,
                                            call: calls,
                                            gate: gate.call(),
                                        };
                                        if pending.is_some() {
                                            waiting.push(task);
                                        } else {
                                            pending = Some(start_tool(task, observed.usage));
                                        }
                                    }
                                }
                            }
                        }
                        if buffer.len() > wire::FRAME_LIMIT {
                            return Err("unterminated runtime frame exceeds 8 MiB".into());
                        }
                    }
                    Input::ToolFinished => {
                        let (p, result) = pending
                            .take()
                            .ok_or("tool result without a pending call")?
                            .finish()?;
                        let (record, result_bytes) = retain_tool(live, &p, &result)?;
                        let reply_bytes = wire::line(crate::rpc::result(
                            &p.id,
                            J::obj()
                                .with("content", J::Raw(record.content.clone()))
                                .with("isError", record.is_error),
                        ));
                        cap.for_send("mcp-out", &reply_bytes)?;
                        fidelity.supplied(
                            p.call,
                            &p.raw,
                            &record.content,
                            record.is_error,
                            &result_bytes,
                        );
                        if fidelity_mismatches(live, &mut fidelity, "live")? {
                            return Err(mismatch());
                        }
                        connection
                            .as_mut()
                            .ok_or("MCP missing")?
                            .write_all(&reply_bytes)
                            .map_err(|e| format!("mcp-out write failed: {e}"))?;
                        if result.sealed {
                            live.flags.set_sealed();
                            return Ok(Ending::Sealed);
                        }
                        if let Some(end) = result.end {
                            let message =
                                "core tool required the placement to stop; see its retained result";
                            return Err(match end {
                                answer::End::LogDamaged => {
                                    ended.log_damaged = true;
                                    message.into()
                                }
                                answer::End::AnswerDamaged => {
                                    Stopped::ending(Ending::Damaged, message)
                                }
                                answer::End::ArchiveWriteFailed => Stopped::write_failed(message),
                            });
                        }
                        if let Some(task) = waiting.pop() {
                            pending = Some(start_tool(task, observed.usage));
                        }
                    }
                }
            }
        })();
        // The ending is decided now, at the loop's exit and before shutdown:
        // nothing the owner observes from here on replaces it, apart from
        // this placement's seal and a reply mismatch first observed in the
        // drain (`ending`).
        let (decided, failure) = match outcome {
            Ok(ending) => (ending, None),
            Err(stopped) => (live.decide(stopped.condition), Some(stopped.message)),
        };
        gate.stop();
        if let Some(p) = &pending {
            p.task.gate.cancel();
        }
        quitting.store(true, Ordering::SeqCst);
        if let Some(c) = &connection {
            let _ = c.shutdown(std::net::Shutdown::Both);
        }
        drop(stdin);
        let stopped = owner.stop();
        // Readers may already have observed chunks while the stop was being
        // enforced. Drain them to capture before joining; no tool is dispatched.
        let drain_deadline = Instant::now() + Duration::from_secs(3);
        let mut drain_error = None;
        drain_stdout(
            live,
            &mut observed,
            &mut fidelity,
            &mut output,
            &mut stdout_offset,
            &mut drain_mismatch,
            &mut drain_error,
        );
        let mut tool_finished = pending.is_none();
        while eof.len() < readers || !tool_finished {
            if Instant::now() >= drain_deadline {
                drain_error = Some(
                    "shutdown observer drain did not finish; capture interval is incomplete"
                        .to_string(),
                );
                break;
            }
            match rx.recv_timeout(Duration::from_millis(25)) {
                Ok(Input::Bytes(channel, bytes)) => {
                    if let Err(e) = cap.raw(channel, &bytes) {
                        drain_error = Some(e.message);
                        continue;
                    }
                    if channel == "stdout" {
                        output.extend_from_slice(&bytes);
                        drain_stdout(
                            live,
                            &mut observed,
                            &mut fidelity,
                            &mut output,
                            &mut stdout_offset,
                            &mut drain_mismatch,
                            &mut drain_error,
                        );
                    }
                }
                Ok(Input::Eof(channel)) => {
                    eof.insert(channel);
                }
                Ok(Input::ToolFinished) => tool_finished = true,
                Ok(Input::Hook(_, bytes)) => {
                    if let Err(e) = cap.raw("hook-in", &bytes) {
                        drain_error = Some(e.message);
                        continue;
                    }
                    fidelity.hook(&bytes, false);
                }
                Ok(Input::Error(e)) => {
                    drain_error = Some(e);
                }
                Ok(Input::Mcp(stream)) => {
                    let _ = stream.shutdown(std::net::Shutdown::Both);
                    drain_error = Some("MCP attached during shutdown".into());
                }
                Err(mpsc::RecvTimeoutError::Timeout) => (),
                Err(_) => break,
            }
        }
        // Disconnect the bounded observer queue before joining: the worker
        // may still be sending its completion notification. Its actual result
        // belongs to the placement, even after the transport drain expires.
        drop(rx);
        if let Some(running) = pending {
            let retained = running.finish().and_then(|(task, result)| {
                if result.end == Some(answer::End::LogDamaged) {
                    ended.log_damaged = true;
                }
                retain_tool(live, &task, &result)
            });
            if let Err(e) = retained {
                drain_error = Some(e.message);
            }
        }
        // These requests were admitted and captured, but never dispatched.
        // Retain their refusals after the running worker settles so revisions
        // reflect all observed effects. Do not execute them during shutdown.
        while let Some(task) = waiting.pop() {
            let call_id = format!("mcp-{}", task.call);
            let refusal = answer::refused_before_execution(
                &task.as_call(&call_id),
                log::read(live.audit).revision(),
                task.gate.permit().err().expect("placement gate is stopped"),
            );
            if let Err(e) = retain_tool(live, &task, &refusal) {
                drain_error = Some(e.message);
            }
        }
        if !output.is_empty() || !incoming.is_empty() {
            drain_error =
                Some("runtime ended with a partial frame; original chunks retained".into());
        }
        let complete = drain_error.is_none()
            && eof.len() == readers
            && !live.record_failed.load(Ordering::SeqCst)
            && cap.bytes <= CAPTURE_LIMIT;
        if let Err(e) = live.write(
            fidelity::FILE,
            &fidelity.report(live.run, complete).to_j().bytes(),
        ) {
            drain_error = Some(e.message);
        }
        later.drain_mismatch = drain_mismatch;
        if drain_error.is_some() {
            observed.usage.unknown_intervals = 1;
        }
        observed.usage.stopped = u64::from(matches!(stopped, Ok(true)));
        ended.usage.harness = Some(observed.usage);
        let message = match (failure, drain_error) {
            (None, None) if drain_mismatch => Some("runtime_reply_mismatch: captured conversation differs from a supplied reply; see the retained diagnostic".into()),
            (None, drained) => drained,
            (Some(e), Some(d)) => Some(format!("{e} Shutdown: {d}")),
            (Some(e), None) => Some(e),
        };
        match message {
            Some(message) => Err(Stopped::ending(decided, message)),
            None => {
                ended.ending = decided;
                Ok(())
            }
        }
    })
}

/// A reply mismatch observed while the placement runs.
fn mismatch() -> Stopped {
    Stopped::ending(
        Ending::Interrupted(Cause::ProtocolAnomaly),
        "runtime_reply_mismatch: captured conversation differs from the supplied reply",
    )
}

#[derive(Clone)]
struct Pending {
    id: Vec<u8>,
    key: String,
    name: String,
    arguments: Vec<u8>,
    raw: Vec<u8>,
    call: u64,
    gate: Gate,
}

struct RunningCall<'scope> {
    task: Pending,
    handle: std::thread::ScopedJoinHandle<'scope, answer::Executed>,
}

impl RunningCall<'_> {
    fn finish(self) -> Result<(Pending, answer::Executed), Stopped> {
        let result = self
            .handle
            .join()
            .map_err(|_| "tool worker panicked before returning a result")?;
        Ok((self.task, result))
    }
}

impl Pending {
    fn as_call<'a>(&'a self, call_id: &'a str) -> answer::Call<'a> {
        answer::Call {
            call: self.call,
            tool_use_id: call_id,
            name: Some(&self.name),
            input: Some(&self.arguments),
        }
    }
}

const WAITING_CALLS: usize = 32;
const WAITING_BYTES: usize = 16 * 1024 * 1024;

/// Only waiting calls count against these bounds. Cancellation leaves a call
/// in its ordered slot until its refusal is retained and returned.
#[derive(Default)]
struct Waiting {
    calls: VecDeque<Pending>,
    bytes: usize,
}
impl Waiting {
    fn can_admit(&self, bytes: usize) -> bool {
        self.calls.len() < WAITING_CALLS && bytes <= WAITING_BYTES - self.bytes
    }
    fn push(&mut self, task: Pending) {
        assert!(self.can_admit(task.raw.len()));
        self.bytes += task.raw.len();
        self.calls.push_back(task);
    }
    fn pop(&mut self) -> Option<Pending> {
        let task = self.calls.pop_front()?;
        self.bytes -= task.raw.len();
        Some(task)
    }
    fn cancel(&self, key: &str) {
        if let Some(task) = self.calls.iter().find(|task| task.key == key) {
            task.gate.cancel();
        }
    }
}

/// Execute an MCP call as this runtime dispatches it, under its call gate. A
/// call whose gate closed before it starts (the placement stopped, the call
/// was cancelled or the deadline passed) is refused `placement_stopped`
/// without entering a tool. A call that starts links its entry or seal only
/// while its gate stays open; the authoring-ended precondition still takes
/// precedence at the link (runtime contract).
pub fn dispatch(
    audit: &Audit,
    world: &world::World,
    placement: &answer::Placement,
    call: &answer::Call,
    gate: &Gate,
) -> answer::Executed {
    let revision = log::read(audit).revision();
    if let Err(stopped) = gate.permit() {
        return answer::refused_before_execution(call, revision, stopped);
    }
    answer::execute(audit, world, placement, call, Some(gate))
}

/// Publish the result record of MCP call `p`, whose account is `result`,
/// and return it with its record bytes. This placement's one MCP connection
/// places every call at request and attempt 1, with the call number as its
/// block and `mcp-<call>` as its invocation ID.
fn retain_tool(
    live: &Live,
    p: &Pending,
    result: &answer::Executed,
) -> Result<(runs::ToolResult, Vec<u8>), Stopped> {
    let call_id = format!("mcp-{}", p.call);
    let record = runs::ToolResult::of(&p.as_call(&call_id), &p.raw, (1, 1, p.call), result, None);
    let bytes = live
        .dir
        .publish(
            live.audit,
            "tool_result",
            &runs::result_name(p.call),
            record.to_j(),
        )
        .map_err(|e| live.record_error(e.error))?;
    Ok((record, bytes))
}

/// The near-limit notice due when `left` remains before the placement
/// deadline, from that one observation: its text and its record's
/// `remaining` both give the whole seconds left, rounded down, and the
/// unused placement slots. It is due once those seconds are at most a fifth
/// of the placement time, itself rounded down to whole seconds.
fn near_limit_notice(
    left: Duration,
    limits: profile::Limits,
    run: u64,
    template: &str,
) -> Option<(String, crate::usage::Remaining)> {
    let seconds = left.as_secs();
    if seconds > limits.placement_timeout_seconds / 5 {
        return None;
    }
    let placements = limits.max_placements.saturating_sub(run);
    let text = template
        .replace("{seconds}", &seconds.to_string())
        .replace("{placements}", &placements.to_string());
    let remaining = crate::usage::Remaining {
        turns: 0,
        input_tokens: 0,
        output_tokens: 0,
        harness: Some((seconds, placements)),
    };
    Some((text, remaining))
}

/// Claim the audit-wide `kind` allowance with a `notice` record, then send
/// `text` to the harness. The record's `request` is the notice's position
/// among this placement's notice records in log order, starting at 1. The
/// placement's `run_ended` lists the notice as `sent` once its input frame
/// was captured completely and then written in full, `not_sent` while it was
/// never captured completely, and `unknown` otherwise (`transmit`).
///
/// A failed claim ends the placement before anything is sent; one that was
/// linked although its durability is unconfirmed stays in the log, and is
/// listed as `not_sent`. A claim refused because close, the seal or the
/// deadline came first stops the placement with that condition.
fn notice(
    live: &Live,
    ended: &mut Ended,
    cap: &mut Capture<'_>,
    out: &mut impl Write,
    kind: &'static str,
    text: &str,
    remaining: Option<crate::usage::Remaining>,
) -> Result<(), Stopped> {
    let mut n = 0;
    log::publish(live.audit, "notice", |s| {
        if s.close_requested().is_some() || s.seal().is_some() || Instant::now() >= live.deadline {
            return Err(Fail::refused(
                "placement_stopped",
                "The authoring boundary closed before this notice.",
            ));
        }
        if s.notice_used(kind) {
            return Err(Fail::refused(
                "notice_used",
                "The notice allowance is already used.",
            ));
        }
        n = s
            .notices()
            .iter()
            .filter(|(_, x)| x.run == live.run)
            .count() as u64
            + 1;
        let body = bodies::Notice {
            run: live.run,
            kind: kind.into(),
            request: n,
            text: text.into(),
            remaining,
        };
        Ok(body.to_j())
    })
    .map_err(|e| {
        let stopped = matches!(&e, log::PubErr::Refused(f) if f.reason == "placement_stopped");
        let refused = matches!(&e, log::PubErr::Refused(_));
        let message = format!("notice claim failed: {}", publication_error(e));
        if !refused {
            return live.record_error(message);
        }
        // The stopping condition the refusal found is observed here, with
        // close and a signal preceding the deadline. A seal alone decides
        // nothing here; it makes the ending `sealed` afterwards.
        match stopped.then(|| live.outside().ending(live.run, live.max_placements)) {
            Some(Some(ending)) => Stopped::ending(ending, message),
            _ => Stopped::from(message),
        }
    })?;
    let mut seen = None;
    let sent = transmit(cap, out, &wire::user(text), &mut seen);
    if let Some(seen) = seen {
        ended.seen.insert(n, seen);
    }
    sent
}

fn authenticate(live: &Live, workspace: &str) -> Result<J, Stopped> {
    let h = live.world.arrangement.harness.as_ref().unwrap();
    if Instant::now() >= live.deadline {
        return Err(live.at_deadline("placement deadline expired before auth check"));
    }
    let slots = surface::Slots::launch(&h.profile, workspace, &live.audit.refile.writer_path);
    let mut owner = process::Owned::start(
        slots.writer,
        &h.profile.executable,
        &surface::environment(&slots),
        slots.workspace,
        &surface::auth_argv(),
        live.deadline
            .saturating_duration_since(Instant::now())
            .min(Duration::from_secs(30)),
        live.dir,
        "auth",
    )?;
    drop(owner.child.stdin.take());
    let stdout = owner.child.stdout.take().ok_or("auth stdout missing")?;
    let stderr = owner.child.stderr.take().ok_or("auth stderr missing")?;
    // Bound both drains without copying their contents into any error message.
    let output = std::thread::scope(|scope| {
        let (tx, rx) = mpsc::sync_channel(4);
        let out_tx = tx.clone();
        scope.spawn(move || reader(stdout, "stdout", out_tx));
        scope.spawn(move || reader(stderr, "stderr", tx));
        let mut out = Vec::new();
        let mut err_bytes = 0;
        let mut eof = 0;
        let result = (|| -> Result<Vec<u8>, Stopped> {
            while eof < 2 {
                if let Some(ending) = live.outside().ending(live.run, live.max_placements) {
                    return Err(Stopped::ending(
                        ending,
                        "authentication check stopped before a model session; no raw output retained",
                    ));
                }
                match rx.recv_timeout(Duration::from_millis(25)) {
                    Ok(Input::Bytes("stdout", b)) => out.extend_from_slice(&b),
                    Ok(Input::Bytes(_, b)) => err_bytes += b.len(),
                    Ok(Input::Eof(_)) => eof += 1,
                    Ok(Input::Error(_)) | Err(mpsc::RecvTimeoutError::Disconnected) => {
                        return Err(
                            "authentication observer failed; raw output was not retained".into(),
                        );
                    }
                    Err(mpsc::RecvTimeoutError::Timeout) => (),
                    _ => (),
                }
                if out.len() > 65536 || err_bytes > 65536 {
                    return Err(
                        "authentication output exceeded its bound; raw output was not retained"
                            .into(),
                    );
                }
            }
            Ok(out)
        })();
        // Its supervisor ends the check at the deadline, so a check that
        // ended once the deadline had passed stopped at the deadline. Decide
        // that now, not after the bounded stop below.
        let ended = (Instant::now() >= live.deadline).then(|| live.decide(Condition::Deadline));
        let stopped = owner.stop();
        drop(rx);
        if stopped != Ok(true) {
            return Err("authentication process stopping is unconfirmed".into());
        }
        result.map(|out| (out, ended))
    });
    let (output, ended) = output?;
    if owner.exit_code != Some(0) {
        let message =
            "authentication check did not complete successfully; raw output was not retained";
        return Err(match ended {
            Some(ending) => Stopped::ending(ending, message),
            None => message.into(),
        });
    }
    let valid = (|| {
        let v = Value::parse(&output)?;
        let logged = v.req("loggedIn")?.boolean()?;
        let method = v.text("authMethod")?;
        let config = v.text("configDirectory")?;
        if !logged || method != "claude.ai" || config != h.profile.config_directory {
            return Err("selected authentication is not the pinned subscription login".into());
        }
        Ok(J::obj()
            .with("loggedIn", logged)
            .with("authMethod", method)
            .with("configDirectory", config))
    })();
    valid.map_err(|_: String| Stopped::from("authentication report did not verify the selected subscription login; raw output was not retained"))
}

fn publication_error(error: log::PubErr) -> String {
    match error {
        log::PubErr::Refused(f) => f.message,
        log::PubErr::Damaged(s) => format!("damaged log: {}", s.bad_names()),
        log::PubErr::NotPublished(c) => format!("{}: {}", c.operation, c.error),
        log::PubErr::Uncertain { n, cause } => format!(
            "log/{n}.json was linked but durability is uncertain: {}",
            cause.error
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn queued_call(gate: &Gate, call: u64, bytes: usize) -> Pending {
        Pending {
            id: call.to_string().into_bytes(),
            key: format!("n:{call}"),
            name: "record_account".into(),
            arguments: b"{}".to_vec(),
            raw: vec![b' '; bytes],
            call,
            gate: gate.call(),
        }
    }

    #[test]
    fn waiting_cancellation_prevents_publication_and_preserves_sibling_order() {
        let (path, audit) = log::tests::scratch_audit();
        let gate = Gate::new(Instant::now() + Duration::from_secs(60));
        // Prove that the real publication path fires before altering cancellation.
        assert!(
            log::publish_under(&audit, "reference", Some(&gate), |_| Ok(
                log::tests::reference_body()
            ))
            .is_ok()
        );
        let count = audit.sub("log").unwrap().names().unwrap().len();
        let mut waiting = Waiting::default();
        waiting.push(queued_call(&gate, 2, 10));
        waiting.push(queued_call(&gate, 3, 10));
        waiting.cancel("n:99");
        assert!(waiting.calls.iter().all(|c| c.gate.permit().is_ok()));
        // The cancelled call is still waiting: no executor has taken it.
        waiting.cancel("n:2");
        let cancelled = waiting.pop().unwrap();
        assert_eq!(cancelled.call, 2);
        let result = log::publish_under(&audit, "close_requested", Some(&cancelled.gate), |_| {
            Ok(log::tests::close_body())
        });
        assert!(matches!(result, Err(log::PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert_eq!(audit.sub("log").unwrap().names().unwrap().len(), count);
        let reply = answer::refused_before_execution(
            &cancelled.as_call("mcp-2"),
            0,
            cancelled.gate.permit().err().unwrap(),
        );
        assert_eq!(reply.reason.as_deref(), Some("placement_stopped"));
        assert!(reply.log_record.is_none());
        assert!(reply.is_error);
        let sibling = waiting.pop().unwrap();
        assert_eq!(sibling.call, 3);
        assert!(
            log::publish_under(&audit, "close_requested", Some(&sibling.gate), |_| Ok(
                log::tests::close_body()
            ))
            .is_ok()
        );
        assert_eq!(audit.sub("log").unwrap().names().unwrap().len(), count + 1);
        assert_eq!(waiting.bytes, 0);
        assert!(waiting.pop().is_none());
        std::fs::remove_dir_all(path).unwrap();
    }

    fn limits(placement_timeout_seconds: u64) -> profile::Limits {
        profile::Limits {
            max_placements: 3,
            placement_timeout_seconds,
        }
    }

    #[test]
    fn a_near_limit_notice_states_one_observation_in_its_text_and_record() {
        // Either edge of the whole second: a second clock reading, earlier
        // or later, would state another second in one of the two.
        for millis in [12_000, 12_999] {
            let left = Duration::from_millis(millis);
            let (text, remaining) = near_limit_notice(
                left,
                limits(60),
                1,
                crate::claude_code::arrangement::NEAR_LIMIT,
            )
            .expect("due at 12 of 60 seconds");
            assert_eq!(
                text,
                "Allowance notice: 12 seconds remain before this placement's deadline, and 2 further placement starts remain for this audit. When execution stops, an unsubmitted answer stays unsubmitted.",
                "{millis} ms"
            );
            assert_eq!(
                String::from_utf8(remaining.to_j().bytes()).unwrap(),
                r#"{"runtime":"claude-code/1","seconds":12,"placements":2}"#,
                "{millis} ms"
            );
            // The last permitted placement has no further starts.
            let (text, remaining) =
                near_limit_notice(left, limits(60), 3, "{seconds}/{placements}")
                    .expect("due at 12 of 60 seconds");
            assert_eq!((text.as_str(), remaining.harness), ("12/0", Some((12, 0))));
        }
    }

    #[test]
    fn a_near_limit_notice_is_due_at_a_fifth_of_the_placement_time_in_whole_seconds() {
        // (placement time, time left, whole seconds stated or not yet due)
        let cases = [
            (60, 13_000, None),
            (60, 12_999, Some(12)),
            (60, 0, Some(0)),
            // A fifth of 9 seconds is 1 whole second, so 1.999 s is due.
            (9, 2_000, None),
            (9, 1_999, Some(1)),
            // Below 5 seconds, only the final partial second is due.
            (4, 1_000, None),
            (4, 999, Some(0)),
        ];
        for (timeout, millis, due) in cases {
            let notice = near_limit_notice(
                Duration::from_millis(millis),
                limits(timeout),
                1,
                "{seconds}",
            );
            assert_eq!(
                notice.as_ref().map(|(_, r)| r.harness.unwrap().0),
                due,
                "{millis} ms of {timeout} s"
            );
            if let Some((text, _)) = notice {
                assert_eq!(text, due.unwrap().to_string());
            }
        }
    }

    /// The agent owner's recorded ending: the ending the first stopping
    /// condition decided, changed afterwards only by this placement's seal
    /// and by a reply mismatch first observed in the drain. Two rows of the
    /// earlier derivation flipped with this rule: a signal received after an
    /// ordinary ending, and the deadline passing after an unexplained stop,
    /// no longer reach the ending at all, so `Later` has no field for them.
    /// The independent runtime driver checks both through the binary.
    #[test]
    fn a_decided_ending_changes_only_for_its_seal_or_a_drained_mismatch() {
        use Cause::{ArchiveWriteFailed, PlacementDeadline, ProtocolAnomaly, Signal};
        use Ending::{
            Damaged, EndedUnsubmitted, Interrupted, LimitReached, Sealed, StoppedByClose,
        };
        let decided = [
            EndedUnsubmitted,
            Sealed,
            Damaged,
            LimitReached,
            StoppedByClose,
            Interrupted(Signal),
            Interrupted(PlacementDeadline),
            Interrupted(ArchiveWriteFailed),
            Interrupted(ProtocolAnomaly),
        ];
        let nothing = Later::default();
        let mismatch = Later {
            drain_mismatch: true,
            ..nothing
        };
        let sealed = Later {
            sealed_here: true,
            ..nothing
        };
        let both = Later {
            drain_mismatch: true,
            sealed_here: true,
        };
        for ending in decided {
            // Invariance: nothing observed later leaves the decision.
            assert_eq!(super::ending(ending, &nothing), ending, "{ending:?}");
            // This placement's seal outranks every decided ending.
            assert_eq!(super::ending(ending, &sealed), Sealed, "{ending:?}");
            assert_eq!(super::ending(ending, &both), Sealed, "{ending:?}");
            // A drained mismatch changes only an ordinary ending.
            let expected = if ending == EndedUnsubmitted {
                Interrupted(ProtocolAnomaly)
            } else {
                ending
            };
            assert_eq!(super::ending(ending, &mismatch), expected, "{ending:?}");
        }
        // The loop's own deadline check uses the same rule.
        assert_eq!(deadline_ending(1, 2), Interrupted(PlacementDeadline));
        assert_eq!(deadline_ending(2, 2), LimitReached);
    }

    /// Conditions the owner observes at one point: close precedes a signal,
    /// a signal precedes the deadline, and a seal in the log keeps close
    /// and a signal from stopping the placement.
    #[test]
    fn close_precedes_a_signal_and_a_signal_precedes_the_deadline() {
        use Cause::{PlacementDeadline, Signal};
        use Ending::{Interrupted, LimitReached, StoppedByClose};
        for bits in 0..16u8 {
            let outside = Outside {
                sealed: bits & 1 != 0,
                close_requested: bits & 2 != 0,
                signalled: bits & 4 != 0,
                past_deadline: bits & 8 != 0,
            };
            let expected = if !outside.sealed && outside.close_requested {
                Some(StoppedByClose)
            } else if !outside.sealed && outside.signalled {
                Some(Interrupted(Signal))
            } else if outside.past_deadline {
                Some(Interrupted(PlacementDeadline))
            } else {
                None
            };
            assert_eq!(outside.ending(1, 2), expected, "{outside:?}");
            // On the last placement the deadline reaches the limit.
            let last = expected.map(|e| match e {
                Interrupted(PlacementDeadline) => LimitReached,
                other => other,
            });
            assert_eq!(outside.ending(2, 2), last, "{outside:?}");
        }
        // Spot checks of the precedence itself.
        let all = Outside {
            sealed: false,
            close_requested: true,
            signalled: true,
            past_deadline: true,
        };
        assert_eq!(all.ending(1, 2), Some(StoppedByClose));
        let signal_and_deadline = Outside {
            close_requested: false,
            ..all
        };
        assert_eq!(signal_and_deadline.ending(1, 2), Some(Interrupted(Signal)));
    }

    /// A notice's `sent` follows how far its input frame got: written in
    /// full after a complete capture is `sent`; captured completely but not
    /// written in full is `unknown`; never captured completely is
    /// `not_sent`, whether the deadline came first or the capture failed.
    /// Every write to the harness captures its bytes first, so a capture
    /// that fails writes nothing and marks the placement's records failed.
    #[test]
    fn a_notice_is_sent_only_when_captured_and_written_in_full() {
        struct Broken;
        impl Write for Broken {
            fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
                Err(std::io::ErrorKind::BrokenPipe.into())
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        let (path, audit) = log::tests::scratch_audit();
        audit.dir.mkdir("runs").unwrap();
        let dir = runs::RunDir::create(&audit, 1).unwrap();
        let failed = AtomicBool::new(false);
        let capture = |deadline| Capture {
            dir: &dir,
            sequence: 0,
            bytes: 0,
            record_failed: &failed,
            deadline,
        };
        let open = Instant::now() + Duration::from_secs(60);
        let frame = b"notice frame\n";
        let sent_as = |seen: Option<crate::provider::placement::Seen>| {
            let mut ended = Ended {
                ending: Ending::EndedUnsubmitted,
                log_damaged: false,
                provider: None,
                requests: 0,
                attempts: 0,
                usage: Usage::default(),
                seen: BTreeMap::new(),
                entries: false,
                seal: None,
                delivered: None,
                message: String::new(),
            };
            if let Some(seen) = seen {
                ended.seen.insert(1, seen);
            }
            ended.sent(1)
        };
        // Firing control: captured, then written in full.
        let mut cap = capture(open);
        let (mut out, mut seen) = (Vec::new(), None);
        assert!(transmit(&mut cap, &mut out, frame, &mut seen).is_ok());
        assert_eq!(out, frame);
        assert_eq!(
            dir.dir.read_regular("runtime-1-input.bin", 100).unwrap().0,
            frame
        );
        assert_eq!(sent_as(seen), "sent");
        // Captured completely, but the write did not complete.
        let mut seen = None;
        let stopped = transmit(&mut cap, &mut Broken, frame, &mut seen).unwrap_err();
        assert_eq!(stopped.condition, Condition::Unexplained);
        assert_eq!(
            dir.dir.read_regular("runtime-2-input.bin", 100).unwrap().0,
            frame
        );
        assert_eq!(sent_as(seen), "unknown");
        // Never captured: the deadline came first. Nothing is written.
        let mut late = capture(Instant::now() - Duration::from_millis(1));
        let (mut out, mut seen) = (Vec::new(), None);
        let stopped = transmit(&mut late, &mut out, frame, &mut seen).unwrap_err();
        assert_eq!(stopped.condition, Condition::Deadline);
        assert!(out.is_empty());
        assert_eq!(sent_as(seen), "not_sent");
        assert!(!failed.load(Ordering::SeqCst));
        // Never captured completely: the capture failed. Nothing is written.
        dir.dir
            .write_excl("runtime-3-input.bin", b"independent obstruction")
            .unwrap();
        let (mut out, mut seen) = (Vec::new(), None);
        let stopped = transmit(&mut cap, &mut out, frame, &mut seen).unwrap_err();
        assert_eq!(
            stopped.condition,
            Condition::Ending(Ending::Interrupted(Cause::ArchiveWriteFailed))
        );
        assert!(out.is_empty());
        assert!(failed.load(Ordering::SeqCst));
        assert_eq!(sent_as(seen), "not_sent");
        // Any other write follows the same order.
        dir.dir
            .write_excl("runtime-4-input.bin", b"independent obstruction")
            .unwrap();
        let mut out = Vec::new();
        assert!(cap.send("input", &mut out, frame).is_err());
        assert!(out.is_empty(), "capture failure must precede transmission");
        assert_eq!(
            dir.dir.read_regular("runtime-4-input.bin", 100).unwrap().0,
            b"independent obstruction"
        );
        // A write blocked until the supervisor's deadline stop, then found
        // failed: the deadline is the condition observed, not a harness
        // error, and the captured frame stays unknown. The unexplained
        // failure above, found before the deadline, is the invariance case.
        struct BrokenAt(Instant);
        impl Write for BrokenAt {
            fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
                std::thread::sleep(self.0.saturating_duration_since(Instant::now()));
                Err(std::io::ErrorKind::BrokenPipe.into())
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        let later = runs::RunDir::create(&audit, 2).unwrap();
        let mut blocked = Capture {
            dir: &later,
            sequence: 0,
            bytes: 0,
            record_failed: &AtomicBool::new(false),
            deadline: Instant::now() + Duration::from_millis(50),
        };
        let stop = blocked.deadline + Duration::from_millis(50);
        let mut seen = None;
        let stopped = transmit(&mut blocked, &mut BrokenAt(stop), frame, &mut seen).unwrap_err();
        assert_eq!(stopped.condition, Condition::Deadline);
        assert_eq!(stopped.message, "input write failed: broken pipe");
        assert_eq!(
            later
                .dir
                .read_regular("runtime-1-input.bin", 100)
                .unwrap()
                .0,
            frame
        );
        assert_eq!(sent_as(seen), "unknown");
        // Every write to the harness follows the same rule.
        blocked.deadline = Instant::now() + Duration::from_millis(50);
        let stop = blocked.deadline + Duration::from_millis(50);
        let stopped = blocked
            .send("mcp-out", &mut BrokenAt(stop), frame)
            .unwrap_err();
        assert_eq!(stopped.condition, Condition::Deadline);
        blocked.deadline = Instant::now() + Duration::from_secs(60);
        let stopped = blocked.send("mcp-out", &mut Broken, frame).unwrap_err();
        assert_eq!(stopped.condition, Condition::Unexplained);
        std::fs::remove_dir_all(path).unwrap();
    }

    #[test]
    fn waiting_bounds_refuse_overflow_without_discarding_accepted_calls() {
        let gate = Gate::new(Instant::now() + Duration::from_secs(60));
        let mut waiting = Waiting::default();
        for n in 1..=WAITING_CALLS {
            assert!(waiting.can_admit(1));
            waiting.push(queued_call(&gate, n as u64, 1));
        }
        assert!(!waiting.can_admit(1));
        waiting.cancel("n:1");
        assert!(!waiting.can_admit(1), "cancellation keeps its ordered slot");
        for n in 1..=WAITING_CALLS {
            assert_eq!(waiting.pop().unwrap().call, n as u64);
            assert!(waiting.can_admit(1));
        }
        for n in 1..=2 {
            assert!(waiting.can_admit(WAITING_BYTES / 2));
            waiting.push(queued_call(&gate, n, WAITING_BYTES / 2));
        }
        assert!(!waiting.can_admit(1));
        assert_eq!(waiting.pop().unwrap().call, 1);
        assert!(waiting.can_admit(WAITING_BYTES / 2));
        gate.stop();
        assert_eq!(
            waiting.pop().unwrap().gate.permit().err().unwrap().reason,
            "placement_stopped"
        );
        assert_eq!(waiting.bytes, 0);
    }

    #[test]
    fn accepted_connection_waits_through_idle_intervals() {
        use std::os::fd::AsRawFd;

        // A plain timed read fails while the peer is idle. The MCP wrapper
        // must survive multiple such intervals without reporting disconnect.
        let (mut control, _control_peer) = UnixStream::pair().unwrap();
        control.set_read_timeout(Some(MCP_READ_INTERVAL)).unwrap();
        assert!(matches!(
            control.read(&mut [0; 1]).unwrap_err().kind(),
            std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
        ));
        for inherited_nonblocking in [true, false] {
            let (stream, peer) = UnixStream::pair().unwrap();
            stream.set_nonblocking(inherited_nonblocking).unwrap();
            if inherited_nonblocking {
                assert_eq!(
                    (&stream).read(&mut [0; 1]).unwrap_err().kind(),
                    std::io::ErrorKind::WouldBlock,
                    "the inherited-mode control must fire before normalization"
                );
            }
            let stream = accepted_stream(stream).unwrap();
            // Retrying timeouts must not mask a nonblocking busy loop.
            let mode = unsafe { libc::fcntl(stream.as_raw_fd(), libc::F_GETFL) };
            assert!(mode >= 0);
            assert_eq!(mode & libc::O_NONBLOCK, 0);
            let input = McpInput::new(stream).unwrap();
            let (tx, rx) = mpsc::sync_channel(4);
            std::thread::scope(|scope| {
                let mut peer = peer;
                scope.spawn(move || reader(input, "mcp", tx));
                for bytes in [b"first\n".as_slice(), b"second\n".as_slice()] {
                    assert!(matches!(
                        rx.recv_timeout(MCP_READ_INTERVAL * 3),
                        Err(mpsc::RecvTimeoutError::Timeout)
                    ));
                    peer.write_all(bytes).unwrap();
                    assert!(matches!(
                        rx.recv_timeout(Duration::from_secs(2)),
                        Ok(Input::Bytes("mcp", got)) if got == bytes
                    ));
                }
                peer.shutdown(std::net::Shutdown::Write).unwrap();
                match rx.recv_timeout(Duration::from_secs(2)) {
                    Ok(Input::Eof("mcp")) => (),
                    Ok(Input::Error(error)) => panic!(
                        "reader failed after peer half-close (inherited nonblocking: {inherited_nonblocking}): {error}"
                    ),
                    Ok(Input::Bytes(channel, bytes)) => {
                        panic!("unexpected {channel} bytes after peer half-close: {bytes:?}")
                    }
                    Ok(_) => panic!("unexpected reader event after peer half-close"),
                    Err(error) => panic!(
                        "no EOF after peer half-close (inherited nonblocking: {inherited_nonblocking}): {error}"
                    ),
                }
            });
        }
    }
}
