//! `stewart run REF` (INTERFACE 5.7, section 6): place the auditor into the
//! arrangement in the foreground and exit when the placement ends.
//!
//! Before it launches anything, run checks, in order: the reference, archive,
//! writer and log; the audit's state; the environment (key, provider URL,
//! proxy and, in a test build, the transport variables); the active lock;
//! and the commission, loading the world through descriptors. A refusal
//! changes nothing.
//!
//! It then records the ending of a dead placement (6.7), publishes
//! `run_started`, creates `runs/<n>` and runs the loop (`provider::placement`)
//! while holding the active lock, with the close watcher and the signal
//! thread as its stop path (6.8). Once `run_started` is published, run
//! replies `completed` whenever it recorded the placement's ending, and
//! `failed` when it could not.

use std::os::unix::ffi::OsStrExt;
use std::time::Duration;

use crate::answer::NoticesUsed;
use crate::archive::{Audit, Fail};
use crate::bodies::{NoticeReport, ProviderUse, RunEnded, RunObservations, RunStarted};
use crate::ids;
use crate::json::J;
use crate::log::{self, Body, EndedBy, LogState, PubErr};
use crate::ops::close::delivery_value;
use crate::provider::placement::{self, Ended, Live};
use crate::provider::request::Parts;
use crate::provider::stop::{self, Flags};
use crate::provider::tls::Tls;
use crate::provider::transport::{AbortHandle, Client, REQUEST_TIMEOUT};
use crate::provider::url::{self, Proxy, Route};
use crate::provider::{Cause as EndCause, Ending};
use crate::reply::{Cause, Next, Reply};
use crate::returns;
use crate::runs::{self, RunDir};
use crate::usage::Usage;
use crate::util;
use crate::world::{self, World};

const OP: &str = "run";

/// Effects of an invocation that started nothing: the recorded facts as
/// they stand. `held` is whether the active lock is held, when known. A
/// refusal makes and presents no delivery, so `delivery` is the outcome of
/// the newest recorded attempt, or `none` without one (1.4).
fn eff(state: Option<&LogState>, held: Option<bool>) -> Vec<(&'static str, &'static str)> {
    let delivery = match state {
        Some(s) if !s.damaged() => s
            .deliveries()
            .last()
            .map_or("none", |d| delivery_value(d.outcome())),
        _ => "unknown",
    };
    let (run, seal) = match state {
        Some(s) if !s.damaged() => (
            if !s.launched() {
                "not_started"
            } else if s.open_placement().is_none() {
                "ended"
            } else {
                match held {
                    Some(true) => "still_held",
                    Some(false) => "ended",
                    None => "unknown",
                }
            },
            if s.seal().is_some() {
                "existing"
            } else {
                "none"
            },
        ),
        _ => ("unknown", "unknown"),
    };
    vec![
        ("run", run),
        ("answer", "unchanged"),
        ("seal", seal),
        ("delivery", delivery),
    ]
}

fn refuse(audit: &Audit, f: Fail, state: Option<&LogState>) -> Reply {
    let held = audit.lock_held().ok();
    let mut reply = f.into_reply(OP, eff(state, held));
    audit.diagnose(
        &mut reply,
        J::obj().with("reference", audit.reference.as_str()),
    );
    reply
}

fn status_next(audit: &Audit) -> Next {
    Next::new(
        audit.argv(&["status", &audit.reference]),
        "See where the audit stands.",
    )
}

fn close_next(audit: &Audit, why: &str) -> Next {
    Next::new(audit.argv(&["close", &audit.reference]), why)
}

fn run_next(audit: &Audit, why: &str) -> Next {
    Next::new(audit.argv(&["run", &audit.reference]), why)
}

/// The audit's state (the second check of 5.7).
fn state_refusal(audit: &Audit, state: &LogState) -> Option<Fail> {
    if state.accepted().is_none() {
        return Some(
            Fail::refused(
                "not_accepted",
                "This reference has no accepted commission, so there is nothing to run. Prepare and commission it first.",
            )
            .next(status_next(audit)),
        );
    }
    if let Some(r) = state.close_requested() {
        return Some(
            Fail::refused(
                "reference_closed",
                format!("Close was requested ({}), so no run can start.", r.name()),
            )
            .data(J::obj().with("record", r.name()))
            .next(close_next(audit, "Continue the close."))
            .next(status_next(audit)),
        );
    }
    let end = state.authoring_end()?;
    if end.by == EndedBy::Close {
        return None;
    }
    Some(
        Fail::refused(
            "authoring_ended",
            format!(
                "Authoring has ended ({} {}), so no run can start; close returns or seals the recorded selection.",
                end.by.name(),
                end.record.name()
            ),
        )
        .data(
            J::obj()
                .with("ended_by", end.by.name())
                .with("record", end.record.name()),
        )
        .next(close_next(
            audit,
            "Close the audit; it seals the recorded selection with manager attribution if no seal exists.",
        ))
        .next(status_next(audit)),
    )
}

/// What run takes from its environment (the third check of 5.7).
struct Environment {
    key: String,
    route: Route,
    overridden: bool,
    tls: Tls,
    timeout: Duration,
    delays: Option<[u64; 3]>,
}

fn env_fail(audit: &Audit, reason: &'static str, message: String) -> Fail {
    Fail::refused(reason, message).next(run_next(
        audit,
        "Run again once the environment is set as the message says.",
    ))
}

fn environment(audit: &Audit) -> Result<Environment, Fail> {
    let key = std::env::var_os("ANTHROPIC_API_KEY").unwrap_or_default();
    if key.is_empty() {
        return Err(env_fail(
            audit,
            "provider_key_missing",
            "ANTHROPIC_API_KEY is unset or empty; run needs the provider key.".into(),
        ));
    }
    if !key.as_bytes().iter().all(|b| (0x21..=0x7E).contains(b)) {
        return Err(env_fail(
            audit,
            "provider_key_invalid",
            "ANTHROPIC_API_KEY has a byte outside visible ASCII (0x21-0x7E), so it cannot be sent as a header.".into(),
        ));
    }
    let key = String::from_utf8_lossy(key.as_bytes()).into_owned();
    let (endpoint, overridden) = url::provider_setting(
        std::env::var_os("STEWART_PROVIDER_URL").as_deref(),
    )
    .map_err(|e| {
        env_fail(
            audit,
            "provider_url_invalid",
            format!("STEWART_PROVIDER_URL is not usable: {e}."),
        )
    })?;
    let proxy = url::proxy_setting(
        std::env::var_os("HTTPS_PROXY").as_deref(),
        std::env::var_os("https_proxy").as_deref(),
    )
    .map_err(|e| {
        env_fail(
            audit,
            "provider_proxy_invalid",
            format!("The proxy setting is not usable: {e}."),
        )
    })?;
    let tls = tls(audit)?;
    let timeout = crate::fault::transport::provider_timeout()
        .map_err(|e| env_fail(audit, "test_variable_invalid", format!("{e}.")))?
        .map_or(REQUEST_TIMEOUT, Duration::from_secs);
    let delays = crate::fault::transport::retry_delays()
        .map_err(|e| env_fail(audit, "test_variable_invalid", format!("{e}.")))?;
    Ok(Environment {
        key,
        route: Route::new(endpoint, proxy),
        overridden,
        tls,
        timeout,
        delays,
    })
}

fn route_proxy(r: &Route) -> Option<&Proxy> {
    r.proxy.as_ref()
}

/// The TLS roots: the release's, plus a test build's extra roots.
fn tls(audit: &Audit) -> Result<Tls, Fail> {
    let invalid = |m: String| env_fail(audit, "test_tls_root_invalid", m);
    match crate::fault::transport::tls_root().map_err(|e| invalid(format!("{e}.")))? {
        #[cfg(feature = "fault-injection")]
        Some((path, bytes)) => {
            let certs = crate::provider::tls::pem_certificates(&bytes)
                .map_err(|e| invalid(format!("The test root file {path}: {e}.")))?;
            Tls::with_extra_roots(&certs).map_err(|e| invalid(format!("{e}.")))
        }
        #[cfg(not(feature = "fault-injection"))]
        Some(_) => Err(invalid("test roots exist only in a test build.".into())),
        None => Tls::web_pki().map_err(|e| {
            Fail::failed(
                "record_failed",
                "The TLS configuration could not be built; nothing was started.",
            )
            .cause(Cause::new("build TLS configuration", e))
        }),
    }
}

/// The commissioned destination, from the accepted preparation's settings.
fn destination(state: &LogState) -> Option<String> {
    let prep = match &state.accepted()?.body {
        Body::Accepted { prep, .. } => *prep,
        _ => return None,
    };
    let p = state.prepared(prep)?;
    let d = p
        .body_obj()
        .obj("settings")
        .ok()?
        .str("destination")
        .ok()?
        .to_string();
    Some(d)
}

/// Record the ending of a placement whose process is gone (6.7): accounted
/// from its run directory as 6.4 states.
fn reconcile(audit: &Audit, state: &LogState, run: u64, started_n: u64) -> Result<(), Fail> {
    let (acc, problem) = match runs::account(audit, run) {
        Ok(a) => (a, None),
        Err(e) => (runs::Account::default(), Some(e)),
    };
    let notices = state
        .notices()
        .iter()
        .filter(|(_, n)| n.run == run)
        .map(|(r, n)| NoticeReport {
            kind: n.kind.clone(),
            record: r.name(),
            sent: acc.notice_sent(n.request).to_string(),
        })
        .collect();
    let seal = state
        .seal()
        .filter(|(r, _)| r.n > started_n)
        .map(|(r, _)| r.name());
    let mut message = format!(
        "Placement {run}'s process was gone with the active lock free; run recorded its ending, accounted from runs/{run}."
    );
    let problems: Vec<String> = problem.into_iter().chain(acc.problems.clone()).collect();
    if !problems.is_empty() {
        message.push_str(&format!(" Not readable: {}.", problems.join("; ")));
    }
    let body = RunEnded {
        run,
        ending: "interrupted".into(),
        cause: Some("process_gone".into()),
        recorded_by: "run".into(),
        provider: None,
        requests: acc.requests,
        attempts: acc.attempts,
        usage: acc.usage,
        notices,
        seal,
        message,
    };
    publish_ended(audit, run, &body).map(|_| ()).map_err(|e| match e {
        PubErr::Damaged(s) => log::damaged_fail(audit, &s),
        PubErr::Refused(f) => f,
        PubErr::NotPublished(c) | PubErr::Uncertain { cause: c, .. } => Fail::failed(
            "record_failed",
            format!("The ending of placement {run}, whose process is gone, could not be recorded; no run was started."),
        )
        // The failed publication's stage file stays in stage/; status reports
        // it as an interrupted publication, so `retained` does not list it.
        .cause(c),
    })
}

fn publish_ended(audit: &Audit, run: u64, body: &RunEnded) -> Result<log::Published, PubErr> {
    log::publish(audit, "run_ended", |st| {
        let open = st
            .placements()
            .iter()
            .any(|p| p.run == run && p.ended.is_none());
        if !open {
            return Err(Fail::refused(
                "run_ended",
                format!("Placement {run} already has its ending recorded."),
            ));
        }
        Ok(body.to_j())
    })
}

/// Apply the test build's request sabotage to what is sent (never to what
/// is pinned): an extra tool, a changed orientation word, a trimmed question,
/// a misspelled effort parameter, or the effort moved into the question.
fn sabotaged(mut parts: Parts, mut question: String) -> (Parts, String) {
    if crate::sabotage!("extra_tool") && parts.tools.ends_with(b"]") {
        parts.tools.pop();
        let comma = if parts.tools.ends_with(b"[") { "" } else { "," };
        parts.tools.extend_from_slice(
            format!(r#"{comma}{{"name":"extra_tool","description":"Sabotage control.","input_schema":{{"type":"object"}}}}]"#)
                .as_bytes(),
        );
    }
    if crate::sabotage!("arrangement_mismatch") {
        let s = String::from_utf8_lossy(&parts.system).replacen(
            "You are the auditor",
            "You are the reviewer",
            1,
        );
        parts.system = s.into_bytes();
    }
    if crate::sabotage!("paraphrase_question") {
        question = question.trim().to_string();
    }
    if crate::sabotage!("misspell_effort") {
        for m in &mut parts.extra {
            *m = String::from_utf8_lossy(m)
                .replacen(r#""effort":"#, r#""eefort":"#, 1)
                .into_bytes();
        }
    }
    if crate::sabotage!("effort_in_prompt") {
        let level = parts.extra.iter().find_map(|m| {
            let m = std::str::from_utf8(m).ok()?;
            let rest = m.strip_prefix(r#""output_config":{"effort":""#)?;
            Some(rest.strip_suffix(r#""}"#)?.to_string())
        });
        if let Some(level) = level {
            parts.extra.clear();
            if !question.ends_with('\n') {
                question.push('\n');
            }
            question.push_str(&format!("Effort: {level}.\n"));
        }
    }
    (parts, question)
}

pub fn run(reference: &str) -> Reply {
    // 1. The reference, archive, writer and log.
    let mut audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, eff(None, None)),
    };
    if let Err(f) = audit.require_mutation() {
        return refuse(&audit, f, None);
    }
    let state = log::read(&audit);
    if state.damaged() {
        let f = log::damaged_fail(&audit, &state).next(status_next(&audit));
        return refuse(&audit, f, Some(&state));
    }
    // 2. The audit's state.
    if let Some(f) = state_refusal(&audit, &state) {
        return refuse(&audit, f, Some(&state));
    }
    // 3. The environment.
    let env = match environment(&audit) {
        Ok(e) => e,
        Err(f) => return refuse(&audit, f, Some(&state)),
    };
    // 4. The lock, held for the rest of the invocation.
    let _lock = match audit.try_lock() {
        Ok(Some(f)) => f,
        Ok(None) => {
            let mut f = Fail::refused(
                "run_held",
                "Another process holds this audit's active lock, so no run can start now.",
            )
            .next(status_next(&audit))
            .next(close_next(
                &audit,
                "Close the audit; close stops a live run.",
            ));
            if let Some(p) = state.open_placement() {
                f = f.data(
                    J::obj()
                        .with("run", p.run)
                        .with("holder", p.start.observations.to_j()),
                );
            }
            return refuse(&audit, f, Some(&state));
        }
        Err(e) => {
            let f = Fail::failed(
                "record_failed",
                format!(
                    "The active lock could not be opened: {}.",
                    util::describe(&e)
                ),
            )
            .cause(Cause::io("open active lock", &e).at(audit.abs("active.lock")));
            return refuse(&audit, f, Some(&state));
        }
    };
    // Under the lock, the state is read again: an earlier holder may have
    // changed it.
    let state = log::read(&audit);
    if state.damaged() {
        let f = log::damaged_fail(&audit, &state).next(status_next(&audit));
        return refuse(&audit, f, Some(&state));
    }
    if let Some(f) = state_refusal(&audit, &state) {
        return refuse(&audit, f, Some(&state));
    }
    // 5. The commission.
    let world = match world::load(&audit, &state) {
        Ok(w) => w,
        Err(items) => {
            let f = Fail::refused(
                "commission_damaged",
                "The accepted commission could not be loaded intact (see data.items); nothing was started.",
            )
            .data(J::obj().with("items", J::Arr(items.iter().map(|i| i.to_j()).collect())))
            .next(Next::new(
                audit.argv(&["receipt", &audit.reference, "--verify"]),
                "Verify each receipt item.",
            ))
            .next(close_next(&audit, "Close the audit."));
            return refuse(&audit, f, Some(&state));
        }
    };
    let question = match world.question.bytes().map(String::from_utf8) {
        Ok(Ok(q)) => q,
        _ => {
            let f = Fail::refused(
                "commission_damaged",
                "The question body could not be read as UTF-8 text from its capture; nothing was started.",
            )
            .data(J::obj().with(
                "items",
                J::Arr(vec![
                    J::obj()
                        .with("item", "question-body")
                        .with("problem", "the captured question body could not be read as UTF-8"),
                ]),
            ))
            .next(close_next(&audit, "Close the audit."));
            return refuse(&audit, f, Some(&state));
        }
    };
    let Some(destination) = destination(&state) else {
        let f = Fail::refused(
            "commission_damaged",
            "The accepted preparation's destination could not be read; nothing was started.",
        )
        .data(J::obj().with(
            "items",
            J::Arr(vec![J::obj().with("item", "receipt").with(
                "problem",
                "the accepted preparation's settings are unreadable",
            )]),
        ));
        return refuse(&audit, f, Some(&state));
    };
    let pinned = &world.arrangement;
    let client = match Client::new(
        env.route.clone(),
        env.tls.clone(),
        &env.key,
        &pinned.anthropic_version,
        env.timeout,
    ) {
        Ok(c) => c,
        Err(e) => {
            let f = Fail::refused(
                "commission_damaged",
                format!("The pinned arrangement cannot be sent: {e}."),
            );
            return refuse(&audit, f, Some(&state));
        }
    };

    // A dead placement's ending is recorded first (6.7).
    if let Some(p) = state.open_placement() {
        if let Err(f) = reconcile(&audit, &state, p.run, p.started.n) {
            return refuse(&audit, f, Some(&state));
        }
    }
    let state = log::read(&audit);
    if state.damaged() {
        let f = log::damaged_fail(&audit, &state).next(status_next(&audit));
        return refuse(&audit, f, Some(&state));
    }

    // The stop signals are blocked before any thread starts, so only the
    // signal thread receives them.
    let abort = AbortHandle::new();
    let flags = Flags::default();
    let signals = stop::block_signals()
        .map_err(|e| Cause::io("block stop signals", &e))
        .and_then(|_| {
            stop::receive_signals(abort.clone(), flags.clone())
                .map_err(|e| Cause::io("start the signal thread", &e))
        });
    if let Err(c) = signals {
        let f = Fail::failed(
            "record_failed",
            format!(
                "The run could not prepare its signal handling ({}); nothing was started.",
                c.error
            ),
        )
        .cause(c);
        return refuse(&audit, f, Some(&state));
    }

    // run_started.
    let run = state.next_run();
    let started = RunStarted {
        run,
        arrangement_sha256: world.arrangement_sha256.clone(),
        provider: ProviderUse {
            base_url: env.route.endpoint.url.clone(),
            overridden: env.overridden,
            proxy: route_proxy(&env.route).map(|p| p.value.clone()),
            anthropic_version: pinned.anthropic_version.clone(),
        },
        observations: RunObservations::current(),
    };
    let published = log::publish(&audit, "run_started", |st| {
        if st.accepted().is_none() {
            return Err(Fail::refused("not_accepted", "No accepted commission."));
        }
        if st.close_requested().is_some() {
            return Err(Fail::refused(
                "reference_closed",
                "Close was requested before the run could start.",
            ));
        }
        if let Some(end) = st.authoring_end() {
            return Err(Fail::refused(
                "authoring_ended",
                format!("Authoring ended ({} {}).", end.by.name(), end.record.name()),
            ));
        }
        if st.open_placement().is_some() || st.next_run() != run {
            return Err(Fail::refused(
                "run_held",
                "Another placement started before this one.",
            ));
        }
        Ok(started.to_j())
    });
    let started_n = match published {
        Ok(p) => p.n,
        Err(PubErr::Refused(f)) => return refuse(&audit, f, Some(&state)),
        Err(PubErr::Damaged(s)) => {
            let f = log::damaged_fail(&audit, &s);
            return refuse(&audit, f, Some(&s));
        }
        Err(PubErr::NotPublished(c)) => {
            let f = Fail::failed(
                "record_failed",
                "run_started could not be recorded, so no placement started.",
            )
            .cause(c);
            return refuse(&audit, f, Some(&state));
        }
        Err(PubErr::Uncertain { n, cause }) => {
            let mut reply = Fail::failed(
                "record_failed",
                format!("run_started was linked as log/{n}.json but its durability could not be confirmed; the run did not continue."),
            )
            .cause(cause)
            .next(status_next(&audit))
            .into_reply(
                OP,
                vec![
                    ("run", "unknown"),
                    ("answer", "unchanged"),
                    ("seal", "none"),
                    ("delivery", eff(Some(&state), None)[3].1),
                ],
            );
            audit.diagnose(&mut reply, J::obj().with("run", run));
            return reply;
        }
    };

    let used_before = if crate::sabotage!("reset_limits_on_continuation") && run > 1 {
        Usage::default()
    } else {
        state.recorded_usage()
    };
    let reset_notices = crate::sabotage!("reset_notice_allowance") && run > 1;
    let notices_used = NoticesUsed {
        reminder: !reset_notices && state.notice_used("reminder"),
        near_limit: !reset_notices && state.notice_used("near_limit"),
    };
    let ended = match RunDir::create(&audit, run) {
        Err(c) => Ended {
            ending: Ending::Interrupted(EndCause::ArchiveWriteFailed),
            log_damaged: false,
            provider: None,
            requests: 0,
            attempts: 0,
            usage: Usage::default(),
            notices: Vec::new(),
            seen: Default::default(),
            entries: false,
            seal: None,
            delivered: None,
            message: format!(
                "runs/{run} could not be created ({} failed: {}); the run stopped before its first request.",
                c.operation, c.error
            ),
        },
        Ok(dir) => {
            let _ = crate::fault!("run.after_started");
            let mut retry = pinned.retry_policy();
            if let Some(d) = env.delays {
                retry = retry.with_delays_ms(d);
            }
            let (parts, question) = sabotaged(Parts::of(pinned), question);
            let live = Live {
                audit: &audit,
                world: &world,
                run,
                dir: &dir,
                client: &client,
                abort: &abort,
                flags: &flags,
                parts,
                question,
                used_before,
                notices_used,
                destination,
                retry,
                revision: state.revision(),
            };
            std::thread::scope(|scope| {
                let _watcher = stop::watch(scope, &audit, abort.clone(), flags.clone());
                placement::run(&live)
            })
        }
    };
    finish(&audit, &world, run, started_n, ended)
}

/// Every location a placement created and kept, for a failed reply's
/// `retained` (1.3): its run directory, the payloads of its entries, the
/// sealed preparation and its manifest, and its delivery plans and packages.
/// Auditor preparations that were never sealed are inspection candidates no
/// record names, and are not listed.
fn kept(audit: &Audit, run: u64, started_n: u64, e: &Ended) -> Vec<String> {
    let mut out = Vec::new();
    if runs::open(audit, run).is_ok() {
        out.push(audit.abs(&format!("runs/{run}")));
    }
    let state = log::read(audit);
    for (r, entry) in state.entries() {
        if r.n > started_n && entry.invocation.run == run {
            if let Some(v) = &entry.created {
                out.push(audit.abs(&v.payload.file));
            }
        }
    }
    if let Some((r, s)) = state.seal() {
        if r.n > started_n {
            out.push(audit.abs(&crate::names::prepared_dir(s.prepared)));
            out.push(audit.abs(&s.manifest));
        }
    }
    if let Some(d) = &e.delivered {
        for a in &d.attempts {
            out.push(audit.abs(&crate::names::plan_name(a.attempt)));
            if let Some(l) = &a.location {
                out.push(l.clone());
            }
        }
    }
    out.dedup();
    out
}

/// Record the placement's ending and build the reply.
fn finish(audit: &Audit, world: &World, run: u64, started_n: u64, e: Ended) -> Reply {
    // The newest attempt this invocation made; `unknown` when delivery
    // stopped before an attempt's outcome could be established.
    let delivery_effect = match &e.delivered {
        None => "none",
        Some(d) => match d.attempts.last() {
            Some(v) => delivery_value(v.outcome.as_deref()),
            None if d.stopped.is_some() => "unknown",
            None => "none",
        },
    };
    let kept = kept(audit, run, started_n, &e);
    let seal_effect = if e.seal.is_some() { "recorded" } else { "none" };
    let answer_effect = if e.entries { "changed" } else { "unchanged" };
    if e.log_damaged {
        let mut f = Fail::failed("log_damaged", e.message.clone())
            .cause(Cause::new("read the audit log", e.message.clone()).at(audit.abs("log")))
            .retain(audit.abs("log"));
        for k in &kept {
            f = f.retain(k.clone());
        }
        let mut reply = f.next(status_next(audit)).into_reply(
            OP,
            vec![
                ("run", "started"),
                ("answer", answer_effect),
                ("seal", seal_effect),
                ("delivery", delivery_effect),
            ],
        );
        audit.diagnose(&mut reply, J::obj().with("run", run));
        return reply;
    }
    let notices = e
        .notices
        .iter()
        .map(|n| NoticeReport {
            kind: n.kind.to_string(),
            record: n.record.clone(),
            sent: e.sent(n.request).to_string(),
        })
        .collect();
    let body = RunEnded {
        run,
        ending: e.ending.as_str().to_string(),
        cause: e.ending.cause().map(|c| c.as_str().to_string()),
        recorded_by: "run".into(),
        provider: e.provider.clone(),
        requests: e.requests,
        attempts: e.attempts,
        usage: e.usage,
        notices,
        seal: e.seal.clone(),
        message: e.message.clone(),
    };
    let effects = |run_effect| {
        vec![
            ("run", run_effect),
            ("answer", answer_effect),
            ("seal", seal_effect),
            ("delivery", delivery_effect),
        ]
    };
    match publish_ended(audit, run, &body) {
        Ok(_) => {}
        Err(PubErr::Damaged(s)) => {
            let mut reply = log::damaged_fail(audit, &s);
            reply.outcome = crate::reply::Outcome::Failed;
            let mut reply = reply.cause(
                Cause::new(
                    "publish run_ended",
                    format!("the audit log is damaged ({})", s.bad_names()),
                )
                .at(audit.abs("log")),
            );
            for k in &kept {
                reply = reply.retain(k.clone());
            }
            let mut reply = reply.into_reply(OP, effects("started"));
            audit.diagnose(&mut reply, J::obj().with("run", run));
            return reply;
        }
        Err(err) => {
            let (cause, run_effect) = match err {
                PubErr::Uncertain { cause, .. } => (cause, "unknown"),
                PubErr::NotPublished(c) => (c, "started"),
                PubErr::Refused(f) => (Cause::new("publish run_ended", f.message), "unknown"),
                PubErr::Damaged(_) => unreachable!("handled above"),
            };
            let reply = Fail::failed(
                "record_failed",
                format!(
                    "Placement {run} ended {} but its ending could not be recorded; the next run or close records it.",
                    e.ending.as_str()
                ),
            )
            // The unrecorded ending's stage file stays in stage/, where
            // status reports it; `retained` lists only created locations.
            .cause(cause);
            let mut reply = kept
                .iter()
                .fold(reply, |f, k| f.retain(k.clone()))
                .next(status_next(audit))
                .into_reply(OP, effects(run_effect));
            audit.diagnose(&mut reply, J::obj().with("run", run));
            return reply;
        }
    }

    let state = log::read(audit);
    let used = state.recorded_usage();
    let limits = world.arrangement.limits;
    let delivery = e
        .delivered
        .as_ref()
        .and_then(|d| d.attempts.last())
        .map(|v| v.to_j())
        .unwrap_or(J::Null);
    let data = J::obj()
        .with("run", run)
        .with("continuing", run > 1)
        .with("ending", e.ending.as_str())
        .with("cause", e.ending.cause().map(|c| c.as_str()))
        .with(
            "provider",
            e.provider.as_ref().map(|p| p.to_j()).unwrap_or(J::Null),
        )
        .with("usage", e.usage.to_j())
        .with("allowances", limits.allowances_j(&used))
        .with(
            "answer",
            J::obj()
                .with("revision", state.revision())
                .with("entries", state.selection().len()),
        )
        .with("seal", seal_view(audit, &state))
        .with("delivery", delivery)
        .with("notices", placement::notices_j(&e));
    let mut reply = Reply::completed(OP, effects("ended"), data);
    reply.next = next_calls(audit, &e);
    reply
}

fn next_calls(audit: &Audit, e: &Ended) -> Vec<Next> {
    match e.ending {
        Ending::Interrupted(_) => vec![
            run_next(
                audit,
                "Continue the audit in a new conversation under the same cumulative limits.",
            ),
            close_next(
                audit,
                "Close the audit; it seals the recorded selection with manager attribution.",
            ),
        ],
        Ending::EndedUnsubmitted | Ending::LimitReached | Ending::Damaged => vec![close_next(
            audit,
            "Close the audit; it seals the recorded selection with manager attribution.",
        )],
        Ending::StoppedByClose => vec![
            status_next(audit),
            close_next(audit, "Continue the close another invocation requested."),
        ],
        Ending::Sealed => {
            let incomplete = e
                .delivered
                .as_ref()
                .and_then(|d| d.attempts.last())
                .is_some_and(|v| {
                    !matches!(
                        v.outcome.as_deref(),
                        Some("verified") | Some("verified_with_losses")
                    )
                });
            vec![close_next(
                audit,
                if incomplete {
                    "Close the audit. The run's delivery was incomplete; close can deliver again, or to another directory with --destination DIR."
                } else {
                    "Close the audit. An ordinary close confirms where the delivered copy is."
                },
            )]
        }
    }
}

/// The seal as status presents it (5.6), or null.
fn seal_view(audit: &Audit, state: &LogState) -> J {
    let Some((_, s)) = state.seal() else {
        return J::Null;
    };
    let (sealed_at, unproduced) =
        match returns::load_manifest(audit, &s.manifest, &s.manifest_sha256) {
            Ok((m, _)) => (
                J::Str(m.sealed_at.clone()),
                crate::json::strs(
                    &m.unproduced
                        .iter()
                        .map(|u| u.name.clone())
                        .collect::<Vec<_>>(),
                ),
            ),
            Err(_) => (J::Null, J::Arr(Vec::new())),
        };
    J::obj()
        .with(
            "handle",
            ids::seal_handle(&audit.archive.store, &audit.id, &s.manifest_sha256),
        )
        .with("actor", s.actor.name())
        .with("sealed_at", sealed_at)
        .with("revision", s.revision)
        .with("manifest_sha256", s.manifest_sha256.as_str())
        .with("unproduced", unproduced)
}
