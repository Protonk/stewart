//! One reserved placement, with an independent supervisor and one Rust tool
//! executor. Reader threads forward bytes only; interpretation follows capture.
use super::{
    accounting::{self, Summary},
    events::{Event, Observed},
    gate::Gate,
    process,
    wire::{self, Action, Value},
};
use crate::archive::{Audit, Fail};
use crate::provider::{
    Cause, Ending,
    placement::Ended,
    stop::{self, Flags},
    transport::AbortHandle,
};
use crate::reply::Reply;
use crate::usage::Usage;
use crate::{
    answer, bodies, delivery,
    json::{self, J},
    log, runs, util, world,
};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::{
    Arc,
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
        return reject("runtime_stop_unknown", e);
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
    if let Err(e) = h.profile.check(
        &audit.refile.writer_sha256,
        &world.arrangement.model,
        &h.mcp_tools,
    ) {
        return reject("runtime_profile_invalid", e);
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
        if let Err(f) = crate::ops::run::reconcile(&audit, &state, p.run, p.started.n) {
            return crate::ops::run::refuse(&audit, f, Some(&state));
        }
    }
    let state = log::read(&audit);
    let used_before = state.recorded_usage();
    if world.arrangement.limits.exhausted(&used_before) {
        return reject(
            "authoring_ended",
            "The commissioned placement allowance is exhausted.".into(),
        );
    }
    let abort = AbortHandle::new();
    let flags = Flags::default();
    if let Err(e) =
        stop::block_signals().and_then(|_| stop::receive_signals(abort.clone(), flags.clone()))
    {
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
    let published = log::publish(&audit, "run_started", |s| {
        if let Some(f) = crate::ops::run::state_refusal(&audit, s) {
            return Err(f);
        }
        if s.open_placement().is_some() || s.next_run() != run {
            return Err(Fail::refused("run_held", "Another placement started."));
        }
        if world.arrangement.limits.exhausted(&s.recorded_usage()) {
            return Err(Fail::refused(
                "authoring_ended",
                "No placement starts remain.",
            ));
        }
        Ok(started.to_j())
    });
    let started_n = match published {
        Ok(p) => p.n,
        Err(e) => {
            return reject(
                "record_failed",
                format!(
                    "The start reservation was not confirmed ({}); no harness was launched.",
                    publication_error(e)
                ),
            );
        }
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
        notices: vec![],
        seen: BTreeMap::new(),
        entries: false,
        seal: None,
        delivered: None,
        message: String::new(),
    };
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
                question: &question,
                deadline,
                used_before,
                flags: &flags,
                record_failed: AtomicBool::new(false),
            };
            if let Err(e) = execute(&live, &mut ended) {
                ended.message = e;
            }
            if live.record_failed.load(Ordering::SeqCst) {
                ended.ending = Ending::Interrupted(Cause::ArchiveWriteFailed);
                ended.usage.harness.as_mut().unwrap().unknown_intervals = 1;
            } else if Instant::now() >= deadline
                && matches!(ended.ending, Ending::Interrupted(Cause::ProtocolAnomaly))
            {
                ended.ending = if run >= h.selection.limits.max_placements {
                    Ending::LimitReached
                } else {
                    Ending::Interrupted(Cause::PlacementDeadline)
                };
            }
            let groups = accounting::groups_gone(&audit, run);
            ended.usage.harness.as_mut().unwrap().stopped = u64::from(matches!(groups, Ok(true)));
            if !matches!(groups, Ok(true)) {
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
                .with("groups_gone", matches!(groups, Ok(true)));
            if let Err(e) = dir.dir.write_excl("runtime-stop.json", &stop.bytes()) {
                ended.ending = Ending::Interrupted(Cause::ArchiveWriteFailed);
                ended.message.push_str(&format!(
                    " Stop observation could not be retained: {}.",
                    e.err
                ));
            }
            if let Err(e) = checkpoint(&dir, ended.usage.harness.unwrap()) {
                ended.ending = Ending::Interrupted(Cause::ArchiveWriteFailed);
                ended
                    .message
                    .push_str(&format!(" Usage checkpoint could not be retained: {e}."));
            }
        }
    }
    let current = log::read(&audit);
    if current.seal().is_none() {
        if current.close_requested().is_some() {
            ended.ending = Ending::StoppedByClose;
        } else if flags.signalled.load(Ordering::SeqCst) {
            ended.ending = Ending::Interrupted(Cause::Signal);
        }
    }
    ended.entries = current.entries().any(|(_, e)| e.invocation.run == run);
    if let Some((rec, _)) = current.seal().filter(|(rec, _)| rec.n > started_n) {
        flags.set_sealed();
        ended.seal = Some(rec.name());
        ended.ending = Ending::Sealed;
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
    crate::ops::run::finish(&audit, run, started_n, ended)
}

struct Live<'a> {
    audit: &'a Audit,
    world: &'a world::World,
    dir: &'a runs::RunDir,
    run: u64,
    question: &'a str,
    deadline: Instant,
    used_before: Usage,
    flags: &'a Flags,
    record_failed: AtomicBool,
}

impl Live<'_> {
    fn record_error(&self, message: impl Into<String>) -> String {
        self.record_failed.store(true, Ordering::SeqCst);
        message.into()
    }
    fn write(&self, name: &str, bytes: &[u8]) -> Result<(), String> {
        self.dir
            .dir
            .write_excl(name, bytes)
            .map_err(|e| self.record_error(format!("retain {name}: {}", e.err)))
    }
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
impl Capture<'_> {
    fn raw(&mut self, channel: &str, bytes: &[u8]) -> Result<(), String> {
        self.sequence += 1;
        self.dir
            .dir
            .write_excl(&format!("runtime-{}-{channel}.bin", self.sequence), bytes)
            .map_err(|e| {
                self.record_failed.store(true, Ordering::SeqCst);
                format!(
                    "capture failed before interpretation/transmission: {}",
                    e.err
                )
            })?;
        self.bytes = self.bytes.saturating_add(bytes.len());
        if self.bytes > 256 * 1024 * 1024 {
            return Err(
                "placement capture exceeded 256 MiB; stopping with an uncovered interval".into(),
            );
        }
        Ok(())
    }
    fn send(&mut self, channel: &str, out: &mut impl Write, bytes: &[u8]) -> Result<(), String> {
        if Instant::now() >= self.deadline {
            return Err("placement deadline reached before transmission".into());
        }
        self.raw(channel, bytes)?;
        out.write_all(bytes)
            .map_err(|e| format!("{channel} write failed: {e}"))
    }
}

enum Input {
    Bytes(&'static str, Vec<u8>),
    Eof(&'static str),
    Error(String),
    Mcp(UnixStream),
    Hook(UnixStream, Vec<u8>),
    Tool(answer::Executed),
}
fn accepted_stream(stream: UnixStream) -> std::io::Result<UnixStream> {
    // BSD sockets inherit the listener's nonblocking flag. Only accept is
    // polled; each connected reader must wait through idle intervals.
    stream.set_nonblocking(false)?;
    Ok(stream)
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
fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

fn execute(live: &Live, ended: &mut Ended) -> Result<(), String> {
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
    let cwd = tmp.open_dir(&name).map_err(|e| e.to_string())?;
    for parent in std::path::Path::new(&workspace).ancestors() {
        for marker in [".git", "CLAUDE.md", "AGENTS.md", ".claude"] {
            match std::fs::symlink_metadata(parent.join(marker)) {
                Ok(_) => {
                    return Err(format!(
                        "private launch directory has project/configuration ancestry at {}; choose a temporary_directory outside it",
                        parent.display()
                    ));
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                Err(e) => {
                    return Err(format!(
                        "cannot inspect launch ancestry {}: {e}",
                        parent.display()
                    ));
                }
            }
        }
    }
    // Freshness is not enough if the requested temporary root is under a
    // submission/archive/project. Refuse before the first harness invocation.
    for forbidden in [
        &live.audit.archive.path,
        &live.audit.refile.folder,
        &live.audit.refile.writer_path,
    ] {
        let root = if forbidden == &live.audit.refile.writer_path {
            forbidden.rsplit_once('/').map(|p| p.0).unwrap_or(forbidden)
        } else {
            forbidden.as_str()
        };
        if workspace.starts_with(&format!("{root}/")) {
            return Err("temporary working directory overlaps archive or writer tree".into());
        }
    }
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
    let mcp_path = "m".to_string();
    let hook_path = "h".to_string();
    let mcp_listener = UnixListener::bind(&mcp_path)
        .map_err(|e| format!("bind private MCP socket in {workspace}: {e}"))?;
    let hook_listener = UnixListener::bind(&hook_path)
        .map_err(|e| format!("bind private hook socket in {workspace}: {e}"))?;
    mcp_listener
        .set_nonblocking(true)
        .map_err(|e| e.to_string())?;
    hook_listener
        .set_nonblocking(true)
        .map_err(|e| e.to_string())?;
    let hook_command = format!(
        "{} {} {}",
        shell_quote(&live.audit.refile.writer_path),
        process::HOOK,
        shell_quote(&hook_path)
    );
    let settings = J::obj()
        .with("forceLoginMethod", "claudeai")
        .with("fastMode", false)
        .with("fallbackModel", J::Arr(vec![]))
        .with(
            "hooks",
            J::obj().with(
                "PreToolUse",
                J::Arr(vec![J::obj().with("matcher", "*").with(
                    "hooks",
                    J::Arr(vec![
                            J::obj()
                                .with("type", "command")
                                .with("command", hook_command)
                                .with("timeout", 5u64),
                        ]),
                )]),
            ),
        );
    let config = J::obj().with(
        "mcpServers",
        J::obj().with(
            "stewart",
            J::obj()
                .with("type", "stdio")
                .with("command", live.audit.refile.writer_path.as_str())
                .with("args", json::strs(&[process::RELAY, &mcp_path])),
        ),
    );
    for (name, bytes) in [
        ("settings.json", settings.bytes()),
        ("mcp.json", config.bytes()),
        ("system.txt", h.system_prompt.as_bytes().to_vec()),
    ] {
        live.write(&format!("runtime-{name}"), &bytes)?;
        cwd.write_excl(name, &bytes)
            .map_err(|e| e.err.to_string())?;
    }
    let mut args = [
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--restricted",
        "--tools",
        "",
        "--setting-sources",
        "",
        "--settings",
    ]
    .map(String::from)
    .to_vec();
    args.extend([
        format!("{workspace}/settings.json"),
        "--strict-mcp-config".into(),
        "--mcp-config".into(),
        format!("{workspace}/mcp.json"),
        "--allowedTools".into(),
    ]);
    args.extend(
        live.world
            .arrangement
            .tool_names
            .iter()
            .map(|n| format!("mcp__stewart__{n}")),
    );
    args.extend(
        [
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--system-prompt-file",
        ]
        .map(String::from),
    );
    args.extend([
        format!("{workspace}/system.txt"),
        "--model".into(),
        h.profile.model.clone(),
        "--max-turns".into(),
        "200".into(),
        "--no-session-persistence".into(),
    ]);
    if let Some(effort) = &h.effort {
        args.extend(["--effort".into(), effort.clone()]);
    }
    let launch = J::obj()
        .with("argv", json::strs(&args))
        .with("cwd", workspace.as_str())
        .with(
            "environment",
            J::Obj(
                process::environment(&h.profile)
                    .into_iter()
                    .map(|(k, v)| (k, J::from(v)))
                    .collect(),
            ),
        );
    live.write("runtime-launch.json", &launch.bytes())?;
    if Instant::now() >= live.deadline {
        return Err("placement deadline expired during startup".into());
    }
    let mut owner = process::Owned::start(
        &live.audit.refile.writer_path,
        &h.profile,
        &workspace,
        &args,
        live.deadline.saturating_duration_since(Instant::now()),
        live.dir,
        "model",
    )?;
    let mut stdin = owner.child.stdin.take().ok_or("missing harness stdin")?;
    let stdout = owner.child.stdout.take().ok_or("missing harness stdout")?;
    let stderr = owner.child.stderr.take().ok_or("missing harness stderr")?;
    let gate = Gate::new(live.deadline);
    let quitting = Arc::new(AtomicBool::new(false));
    let result = std::thread::scope(|scope| {
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
        let mut mcp = wire::Mcp::default();
        let mut output = Vec::new();
        let mut incoming = Vec::new();
        let mut pending: Option<Pending> = None;
        let mut calls = 0u64;
        let mut readers = 2usize;
        let mut eof = std::collections::BTreeSet::new();
        let outcome = (|| {
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
                if state.close_requested().is_some() && state.seal().is_none() {
                    ended.ending = Ending::StoppedByClose;
                    return Ok(());
                }
                if live.flags.signalled.load(Ordering::SeqCst) && state.seal().is_none() {
                    ended.ending = Ending::Interrupted(Cause::Signal);
                    return Ok(());
                }
                if Instant::now() >= live.deadline {
                    ended.ending = if live.run >= h.selection.limits.max_placements {
                        Ending::LimitReached
                    } else {
                        Ending::Interrupted(Cause::PlacementDeadline)
                    };
                    return Err("placement deadline reached; stopping the harness group".into());
                }
                let seconds = live
                    .deadline
                    .saturating_duration_since(Instant::now())
                    .as_secs();
                if observed.initialized
                    && !state.notice_used("near_limit")
                    && seconds <= h.selection.limits.placement_timeout_seconds / 5
                {
                    let text = live
                        .world
                        .arrangement
                        .near_limit
                        .replace("{seconds}", &seconds.to_string())
                        .replace(
                            "{placements}",
                            &h.selection
                                .limits
                                .max_placements
                                .saturating_sub(live.run)
                                .to_string(),
                        );
                    notice(live, ended, &mut cap, &mut stdin, "near_limit", &text)?;
                }
                let event = match rx.recv_timeout(Duration::from_millis(25)) {
                    Ok(e) => e,
                    Err(mpsc::RecvTimeoutError::Timeout) => continue,
                    Err(_) => return Err("runtime observers disconnected".into()),
                };
                match event {
                    Input::Error(e) => return Err(e),
                    Input::Eof(channel) => {
                        eof.insert(channel);
                        if channel == "stdout" {
                            return Err(
                                "harness stdout ended without a settled placement result".into()
                            );
                        }
                        if channel == "mcp" && pending.is_some() {
                            return Err("MCP disconnected with a tool in flight".into());
                        }
                    }
                    Input::Mcp(stream) => {
                        if connection.is_some() {
                            return Err("unexpected second MCP attachment".into());
                        }
                        stream
                            .set_write_timeout(Some(Duration::from_secs(2)))
                            .map_err(|e| e.to_string())?;
                        let input = stream.try_clone().map_err(|e| e.to_string())?;
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
                                        .any(|n| name == format!("mcp__stewart__{n}"))
                            })
                            && gate.permit().is_ok();
                        let reply = if allowed {
                            J::obj()
                        } else {
                            J::obj().with(
                                "hookSpecificOutput",
                                J::obj()
                                    .with("hookEventName", "PreToolUse")
                                    .with("permissionDecision", "deny")
                                    .with(
                                        "permissionDecisionReason",
                                        "Tool is outside the validated active commission.",
                                    ),
                            )
                        };
                        cap.send("hook-out", &mut stream, &wire::line(reply))?;
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
                            if raw.iter().all(u8::is_ascii_whitespace) {
                                continue;
                            }
                            if channel == "stdout" {
                                match observed.receive(
                                    &raw,
                                    h,
                                    &live.world.arrangement.tool_names,
                                )? {
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
                                            return Ok(());
                                        }
                                        if !log::read(live.audit).notice_used("reminder") {
                                            notice(
                                                live,
                                                ended,
                                                &mut cap,
                                                &mut stdin,
                                                "reminder",
                                                &live.world.arrangement.reminder,
                                            )?;
                                            observed.usage.unknown_intervals = 1;
                                        } else {
                                            ended.ending = Ending::EndedUnsubmitted;
                                            return Ok(());
                                        }
                                    }
                                    _ => (),
                                }
                            } else {
                                match mcp.receive(&raw, &h.mcp_tools) {
                                    Action::Silent => (),
                                    Action::Cancel(key) => {
                                        if let Some(p) = &pending {
                                            if p.key == key {
                                                p.gate.cancel();
                                            }
                                        }
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
                                        if !observed.initialized
                                            || pending.is_some()
                                            || gate.permit().is_err()
                                        {
                                            cap.send("mcp-out", connection.as_mut().unwrap(), &wire::line(wire::error(&id, -32000, "startup is unvalidated, placement stopped, or another tool is pending")))?;
                                            continue;
                                        }
                                        calls += 1;
                                        live.dir
                                            .write_call(calls, &raw)
                                            .map_err(|e| live.record_error(e.error))?;
                                        let mut used = live.used_before;
                                        used.add(&Usage {
                                            harness: Some(observed.usage),
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
                                        let call_gate = gate.call();
                                        let task = Pending {
                                            id,
                                            key,
                                            name,
                                            arguments,
                                            raw,
                                            call: calls,
                                            gate: call_gate.clone(),
                                        };
                                        let worker = task.clone();
                                        let tx = tx.clone();
                                        scope.spawn(move || {
                                            let call = answer::Call {
                                                call: worker.call,
                                                tool_use_id: &format!("mcp-{}", worker.call),
                                                name: Some(&worker.name),
                                                input: Some(&worker.arguments),
                                            };
                                            let result = call_gate.within(|| {
                                                answer::execute(
                                                    live.audit, live.world, &placement, &call,
                                                )
                                            });
                                            let _ = tx.send(Input::Tool(result));
                                        });
                                        pending = Some(task);
                                    }
                                }
                            }
                        }
                        if buffer.len() > wire::FRAME_LIMIT {
                            return Err("unterminated runtime frame exceeds 8 MiB".into());
                        }
                    }
                    Input::Tool(result) => {
                        let p = pending.take().ok_or("tool result without a pending call")?;
                        let record = runs::ToolResult {
                            call: p.call,
                            request: 1,
                            attempt: 1,
                            block: p.call,
                            call_bytes: p.raw.len() as u64,
                            call_sha256: util::sha256_hex(&p.raw),
                            tool_use_id: format!("mcp-{}", p.call),
                            tool: Some(p.name),
                            input_sha256: Some(util::sha256_hex(&p.arguments)),
                            replay_of: None,
                            outcome: result.outcome.name().into(),
                            reason: result.reason,
                            revision: result.revision,
                            log_record: result.log_record,
                            is_error: result.is_error,
                            content: result.content,
                        };
                        live.dir
                            .publish(
                                live.audit,
                                "tool_result",
                                &runs::result_name(p.call),
                                record.to_j(),
                            )
                            .map_err(|e| live.record_error(e.error))?;
                        cap.send(
                            "mcp-out",
                            connection.as_mut().ok_or("MCP missing")?,
                            &wire::line(wire::result(
                                &p.id,
                                J::obj()
                                    .with("content", J::Raw(record.content))
                                    .with("isError", record.is_error),
                            )),
                        )?;
                        if result.sealed {
                            live.flags.set_sealed();
                            ended.ending = Ending::Sealed;
                            return Ok(());
                        }
                        if let Some(end) = result.end {
                            match end {
                                answer::End::LogDamaged => ended.log_damaged = true,
                                answer::End::AnswerDamaged => ended.ending = Ending::Damaged,
                                answer::End::ArchiveWriteFailed => {
                                    ended.ending = Ending::Interrupted(Cause::ArchiveWriteFailed)
                                }
                            }
                            return Err(
                                "core tool required the placement to stop; see its retained result"
                                    .into(),
                            );
                        }
                    }
                }
            }
        })();
        gate.stop();
        if let Some(p) = &pending {
            p.gate.cancel();
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
        while eof.len() < readers || pending.is_some() {
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
                        drain_error = Some(e);
                    }
                    if channel == "stdout" {
                        output.extend_from_slice(&bytes);
                        while let Some(end) = output.iter().position(|b| *b == b'\n') {
                            let raw: Vec<_> = output.drain(..=end).collect();
                            if raw.iter().all(u8::is_ascii_whitespace) {
                                continue;
                            }
                            if let Err(e) =
                                observed.receive(&raw, h, &live.world.arrangement.tool_names)
                            {
                                drain_error = Some(e);
                            }
                        }
                    }
                }
                Ok(Input::Eof(channel)) => {
                    eof.insert(channel);
                }
                Ok(Input::Tool(result)) => {
                    if let Some(p) = pending.take() {
                        if let Err(e) = retain_tool(live, &p, &result) {
                            drain_error = Some(e);
                        }
                    }
                }
                Ok(Input::Hook(_, bytes)) => {
                    if let Err(e) = cap.raw("hook-in", &bytes) {
                        drain_error = Some(e);
                    }
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
        if !output.is_empty() || !incoming.is_empty() {
            drain_error =
                Some("runtime ended with a partial frame; original chunks retained".into());
        }
        if drain_error.is_some() {
            observed.usage.unknown_intervals = 1;
        }
        observed.usage.stopped = u64::from(matches!(stopped, Ok(true)));
        ended.usage.harness = Some(observed.usage);
        // Disconnect first, so bounded reader queues cannot block scoped joins.
        drop(rx);
        drop(tx);
        match (outcome, drain_error) {
            (Ok(()), Some(e)) => Err(e),
            (Err(e), Some(d)) => Err(format!("{e} Shutdown: {d}")),
            (result, None) => result,
        }
    });
    if ended.usage.harness.is_some_and(|u| u.stopped == 1) {
        let _ = std::fs::remove_dir_all(&workspace);
    }
    result
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

fn retain_tool(live: &Live, p: &Pending, result: &answer::Executed) -> Result<(), String> {
    let record = runs::ToolResult {
        call: p.call,
        request: 1,
        attempt: 1,
        block: p.call,
        call_bytes: p.raw.len() as u64,
        call_sha256: util::sha256_hex(&p.raw),
        tool_use_id: format!("mcp-{}", p.call),
        tool: Some(p.name.clone()),
        input_sha256: Some(util::sha256_hex(&p.arguments)),
        replay_of: None,
        outcome: result.outcome.name().into(),
        reason: result.reason.clone(),
        revision: result.revision,
        log_record: result.log_record.clone(),
        is_error: result.is_error,
        content: result.content.clone(),
    };
    live.dir
        .publish(
            live.audit,
            "tool_result",
            &runs::result_name(p.call),
            record.to_j(),
        )
        .map_err(|e| live.record_error(e.error))?;
    Ok(())
}

fn notice(
    live: &Live,
    ended: &mut Ended,
    cap: &mut Capture<'_>,
    out: &mut impl Write,
    kind: &'static str,
    text: &str,
) -> Result<(), String> {
    let n = ended.notices.len() as u64 + 1;
    let limits = live
        .world
        .arrangement
        .harness
        .as_ref()
        .unwrap()
        .selection
        .limits;
    let remaining = (kind == "near_limit").then(|| crate::usage::Remaining {
        turns: 0,
        input_tokens: 0,
        output_tokens: 0,
        harness: Some((
            live.deadline
                .saturating_duration_since(Instant::now())
                .as_secs(),
            limits.max_placements.saturating_sub(live.run),
        )),
    });
    let body = bodies::Notice {
        run: live.run,
        kind: kind.into(),
        request: n,
        text: text.into(),
        remaining,
    };
    let record = log::publish(live.audit, "notice", |s| {
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
        Ok(body.to_j())
    })
    .map_err(|e| {
        if !matches!(&e, log::PubErr::Refused(_)) {
            live.record_failed.store(true, Ordering::SeqCst);
        }
        format!("notice claim failed: {}", publication_error(e))
    })?;
    ended.notices.push(crate::provider::placement::Published {
        kind,
        record: format!("log/{}.json", record.n),
        request: n,
    });
    cap.send("input", out, &wire::user(text))?;
    ended.seen.insert(
        n,
        crate::provider::placement::Seen {
            captured: true,
            written: true,
        },
    );
    Ok(())
}

fn authenticate(live: &Live, workspace: &str) -> Result<J, String> {
    let h = live.world.arrangement.harness.as_ref().unwrap();
    if Instant::now() >= live.deadline {
        return Err("placement deadline expired before auth check".into());
    }
    let mut owner = process::Owned::start(
        &live.audit.refile.writer_path,
        &h.profile,
        workspace,
        &["auth".into(), "status".into()],
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
        let result = (|| -> Result<Vec<u8>, String> {
            while eof < 2 {
                if Instant::now() >= live.deadline
                    || live.flags.signalled.load(Ordering::SeqCst)
                    || log::read(live.audit).close_requested().is_some()
                {
                    return Err("authentication check stopped before a model session; no raw output retained".into());
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
        let stopped = owner.stop();
        drop(rx);
        if stopped != Ok(true) {
            return Err("authentication process stopping is unconfirmed".into());
        }
        result
    });
    let output = output?;
    if owner.exit_code != Some(0) {
        return Err(
            "authentication check did not complete successfully; raw output was not retained"
                .into(),
        );
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
    valid.map_err(|_: String| "authentication report did not verify the selected subscription login; raw output was not retained".into())
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
    #[test]
    fn accepted_connection_waits_through_idle_intervals() {
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
            let (tx, rx) = mpsc::sync_channel(4);
            std::thread::scope(|scope| {
                let mut peer = peer;
                scope.spawn(move || reader(stream, "mcp", tx));
                for bytes in [b"first\n".as_slice(), b"second\n".as_slice()] {
                    assert!(matches!(
                        rx.recv_timeout(Duration::from_millis(30)),
                        Err(mpsc::RecvTimeoutError::Timeout)
                    ));
                    peer.write_all(bytes).unwrap();
                    assert!(matches!(
                        rx.recv_timeout(Duration::from_secs(2)),
                        Ok(Input::Bytes("mcp", got)) if got == bytes
                    ));
                }
                peer.shutdown(std::net::Shutdown::Write).unwrap();
                assert!(matches!(
                    rx.recv_timeout(Duration::from_secs(2)),
                    Ok(Input::Eof("mcp"))
                ));
            });
        }
    }

    #[test]
    fn transmission_requires_a_durable_capture_with_failure_and_invariance_controls() {
        let (path, audit) = log::tests::scratch_audit();
        audit.dir.mkdir("runs").unwrap();
        let dir = runs::RunDir::create(&audit, 1).unwrap();
        let failure = AtomicBool::new(false);
        let mut cap = Capture {
            dir: &dir,
            sequence: 0,
            bytes: 0,
            record_failed: &failure,
            deadline: Instant::now() + Duration::from_secs(60),
        };
        let bytes = b"exact outgoing bytes\n";
        let mut sent = Vec::new();
        cap.send("input", &mut sent, bytes).unwrap();
        assert_eq!(sent, bytes);
        assert_eq!(
            dir.dir.read_regular("runtime-1-input.bin", 100).unwrap().0,
            bytes
        );
        dir.dir
            .write_excl("runtime-2-input.bin", b"independent obstruction")
            .unwrap();
        let mut denied = Vec::new();
        assert!(cap.send("input", &mut denied, bytes).is_err());
        assert!(
            denied.is_empty(),
            "capture failure must precede transmission"
        );
        assert!(failure.load(Ordering::SeqCst));
        assert_eq!(
            dir.dir.read_regular("runtime-2-input.bin", 100).unwrap().0,
            b"independent obstruction"
        );
        let fresh = runs::RunDir::create(&audit, 2).unwrap();
        let mut cap = Capture {
            dir: &fresh,
            sequence: 0,
            bytes: 0,
            record_failed: &AtomicBool::new(false),
            deadline: Instant::now() + Duration::from_secs(60),
        };
        let mut sent = Vec::new();
        cap.send("input", &mut sent, bytes).unwrap();
        assert_eq!(sent, bytes);
        std::fs::remove_dir_all(path).unwrap();
    }
}
