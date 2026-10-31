//! The loop of one placement (INTERFACE 6.3–6.6, 4.5).
//!
//! ```text
//! before each request: if close_requested → end stopped_by_close
//!                      if a limit is exhausted → end limit_reached
//! capture the request, send it with retries, account usage
//! no response to use → end as 6.5 states
//! execute every tool_use block of the response in order
//! if the log holds a seal recorded during this response → deliver, then end sealed
//! otherwise follow the stop reason (policy::after_response)
//! ```
//!
//! Whether a seal was recorded is read from the log, never from the calls'
//! replies: a submit that replied `seal_uncertain` while its seal was in fact
//! linked still leads to delivery and the ending `sealed`. While the log holds
//! a seal the placement sends no request and publishes no notice, and the
//! stop path no longer applies (6.3, 6.8).
//!
//! Every raw capture is written before what it captures is used: the request
//! capture before its first attempt, the response capture before its body is
//! decoded, the call capture before its block runs. Linked records follow:
//! an attempt record when the attempt ends, a result record after its block.
//! A failed archive write ends the placement `interrupted`
//! (`archive_write_failed`); an attempt whose record could not be written is
//! charged as an estimated attempt, as a dead placement's would be (6.4).
//!
//! The loop publishes `notice` records but never `run_started` or
//! `run_ended`: those are the operation's (`ops::run`), which records the
//! [`Ended`] this returns.

use std::collections::{BTreeMap, HashMap};
use std::time::Duration;

use crate::answer::{self, Call, Executed, NoticesUsed};
use crate::archive::{Audit, Fail};
use crate::bodies::{Notice, ProviderFacts};
use crate::delivery::{self, By, Delivered, Destination};
use crate::json::J;
use crate::log::{self, LogState, PubErr};
use crate::provider::policy::{self, Next, RetryPolicy, Then};
use crate::provider::request::{Conversation, Parts, first_user_message, turn, user_message};
use crate::provider::response::{Message, classify};
use crate::provider::stop::Flags;
use crate::provider::transport::{AbortHandle, Attempt, Client, Written};
use crate::provider::{Cause, Ending, Member, StopCause};
use crate::reply::{self, Outcome as CallOutcome};
use crate::runs::{self, ProviderAttempt, ResponseFile, RunDir, ToolResult};
use crate::usage::{Charge, Remaining, Usage};
use crate::util;
use crate::world::World;

/// What a placement starts from.
pub struct Live<'a> {
    pub audit: &'a Audit,
    pub world: &'a World,
    pub run: u64,
    pub dir: &'a RunDir,
    pub client: &'a Client,
    pub abort: &'a AbortHandle,
    pub flags: &'a Flags,
    /// The pinned bytes each request splices (as sent).
    pub parts: Parts,
    /// The question body exactly as the first user message carries it.
    pub question: String,
    /// The audit's cumulative usage before this placement.
    pub used_before: Usage,
    /// Whether each notice was used before this placement (audit-wide).
    pub notices_used: NoticesUsed,
    /// The commissioned destination, for delivery after a seal.
    pub destination: String,
    pub retry: RetryPolicy,
    /// The answer revision when the placement starts.
    pub revision: u64,
}

/// A `notice` record this placement published.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Published {
    /// `reminder` or `near_limit`.
    pub kind: &'static str,
    /// `log/<n>.json`.
    pub record: String,
    /// The request planned to carry it.
    pub request: u64,
}

/// What this placement's records establish about one request (6.4).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Seen {
    /// Its capture was written completely.
    pub captured: bool,
    /// An attempt record of it states `request_written` other than `none`.
    pub written: bool,
}

/// How a placement ended, for its `run_ended` and the run reply.
#[derive(Debug)]
pub struct Ended {
    pub ending: Ending,
    /// The log was found damaged: nothing more may be published, and the run
    /// fails `log_damaged` (6.5).
    pub log_damaged: bool,
    /// The last attempt's facts, for `provider_unavailable` and
    /// `provider_rejected`.
    pub provider: Option<ProviderFacts>,
    /// Complete request captures.
    pub requests: u64,
    /// Attempt records published.
    pub attempts: u64,
    /// This placement's charge.
    pub usage: Usage,
    pub notices: Vec<Published>,
    pub seen: BTreeMap<u64, Seen>,
    /// This invocation recorded an entry.
    pub entries: bool,
    /// The `seal` record published during the placement.
    pub seal: Option<String>,
    pub delivered: Option<Delivered>,
    /// Prose for `run_ended.message`.
    pub message: String,
}

impl Ended {
    /// A notice's `sent` (6.4): `sent` when an attempt record of its planned
    /// request has `request_written` other than `none`, `not_sent` when that
    /// request was never captured, `unknown` otherwise.
    pub fn sent(&self, request: u64) -> &'static str {
        match self.seen.get(&request) {
            Some(s) if s.written => "sent",
            Some(s) if s.captured => "unknown",
            _ => "not_sent",
        }
    }
}

/// Why the loop stops.
enum Stop {
    Ending(Ending, String),
    LogDamaged(String),
}

fn archive_failed(c: &reply::Cause) -> Stop {
    Stop::Ending(
        Ending::Interrupted(Cause::ArchiveWriteFailed),
        format!(
            "An archive write failed ({} failed: {}); the run stopped.",
            c.operation, c.error
        ),
    )
}

fn damaged(state: &LogState) -> Stop {
    Stop::LogDamaged(format!(
        "The audit log was found damaged ({}); the run published nothing more.",
        state.bad_names()
    ))
}

fn stopped(cause: StopCause) -> Stop {
    match cause {
        StopCause::Close => Stop::Ending(
            Ending::StoppedByClose,
            "Close was requested; the run stopped before its next step.".into(),
        ),
        StopCause::Signal => Stop::Ending(
            Ending::Interrupted(Cause::Signal),
            "A stop signal arrived; the run stopped and may be continued.".into(),
        ),
    }
}

/// A call already executed in this placement, for replays (6.3).
struct Prior {
    call: u64,
    name: Option<String>,
    input: Option<Vec<u8>>,
    content: Vec<u8>,
    is_error: bool,
    outcome: CallOutcome,
    reason: Option<String>,
}

struct State<'l, 'a> {
    live: &'l Live<'a>,
    usage: Usage,
    requests: u64,
    attempts: u64,
    seen: BTreeMap<u64, Seen>,
    notices: Vec<Published>,
    reminder_used: bool,
    near_used: bool,
    /// The near-limit text and the request planned to carry it.
    pending: Option<(u64, String)>,
    calls: u64,
    executed: HashMap<String, Prior>,
    revision: u64,
    entries: bool,
    seal: Option<String>,
    provider: Option<ProviderFacts>,
    delivered: Option<Delivered>,
}

/// Run the placement to its end.
pub fn run(live: &Live) -> Ended {
    let mut s = State {
        live,
        usage: Usage::default(),
        requests: 0,
        attempts: 0,
        seen: BTreeMap::new(),
        notices: Vec::new(),
        reminder_used: live.notices_used.reminder,
        near_used: live.notices_used.near_limit,
        pending: None,
        calls: 0,
        executed: HashMap::new(),
        revision: live.revision,
        entries: false,
        seal: None,
        provider: None,
        delivered: None,
    };
    let continuation = (live.run > 1).then_some(live.world.arrangement.continuation.as_str());
    let mut conv = Conversation::new(first_user_message(&live.question, continuation));
    let stop = s.drive(&mut conv);
    let (ending, log_damaged, message) = match stop {
        Stop::Ending(e, m) => (e, false, m),
        Stop::LogDamaged(m) => (Ending::Interrupted(Cause::ArchiveWriteFailed), true, m),
    };
    Ended {
        ending,
        log_damaged,
        provider: s.provider,
        requests: s.requests,
        attempts: s.attempts,
        usage: s.usage,
        notices: s.notices,
        seen: s.seen,
        entries: s.entries,
        seal: s.seal,
        delivered: s.delivered,
        message,
    }
}

impl State<'_, '_> {
    fn pinned(&self) -> &crate::provider::request::Pinned {
        &self.live.world.arrangement
    }

    /// Usage across the audit: earlier placements and this one so far.
    fn cumulative(&self) -> Usage {
        let mut u = self.live.used_before;
        u.add(&self.usage);
        u
    }

    /// The checks before each request and after each retry delay. No
    /// request is sent while the log holds a seal: the placement delivers it
    /// and ends `sealed`, and the stop path no longer applies.
    fn before_request(&mut self) -> Option<Stop> {
        let state = log::read(self.live.audit);
        if state.damaged() {
            return Some(damaged(&state));
        }
        if let Some(stop) = self.sealed_in_log(&state) {
            return Some(stop);
        }
        if let Some(c) = self.live.abort.cause() {
            return Some(stopped(c));
        }
        if state.close_requested().is_some() {
            return Some(stopped(StopCause::Close));
        }
        let limits = self.pinned().limits;
        if limits.exhausted(&self.cumulative()) {
            return Some(Stop::Ending(Ending::LimitReached, self.limit_message()));
        }
        None
    }

    /// When the log holds a seal, take it as this placement's seal (the run
    /// refuses to start once a seal exists, so any seal in the log was
    /// recorded during this placement), deliver it and end `sealed`.
    fn sealed_in_log(&mut self, state: &LogState) -> Option<Stop> {
        let (rec, _) = state.seal()?;
        self.seal = Some(rec.name());
        self.live.flags.set_sealed();
        Some(self.deliver())
    }

    fn limit_message(&self) -> String {
        let limits = self.pinned().limits;
        let r = limits.remaining(&self.cumulative());
        let mut out = Vec::new();
        if r.turns == 0 {
            out.push(format!("no turn of {} remains", limits.turns));
        }
        if r.input_tokens == 0 {
            out.push(format!(
                "the {} input tokens are used up",
                limits.input_tokens
            ));
        }
        if r.output_tokens < crate::usage::MIN_OUTPUT_FOR_REQUEST {
            out.push(format!(
                "{} of {} output tokens remain, fewer than one request needs",
                r.output_tokens, limits.output_tokens
            ));
        }
        format!("A limit was reached: {}.", out.join("; "))
    }

    fn drive(&mut self, conv: &mut Conversation) -> Stop {
        loop {
            if let Some(stop) = self.before_request() {
                return stop;
            }
            let k = conv.request();
            let pinned = self.pinned();
            let max_tokens = pinned
                .limits
                .max_tokens(&self.cumulative(), pinned.max_tokens_per_request);
            let body = conv.body(&self.live.parts, max_tokens);
            let capture = runs::request_capture(k, max_tokens, &body, &[conv.latest()]);
            if let Err(c) = self.live.dir.write_request(k, &capture) {
                return archive_failed(&c);
            }
            self.requests += 1;
            self.seen.entry(k).or_default().captured = true;
            let (a, attempt, msg) = match self.send(k, &body, max_tokens) {
                Ok(x) => x,
                Err(stop) => return stop,
            };
            let response = attempt
                .reply
                .as_ref()
                .map(|r| r.body.clone())
                .unwrap_or_default();
            match self.respond(conv, k, a, &response, &msg) {
                Ok(()) => {}
                Err(stop) => return stop,
            }
        }
    }

    /// Send request `k` with retries (6.6) until a response is used or the
    /// placement ends.
    fn send(
        &mut self,
        k: u64,
        body: &[u8],
        max_tokens: u64,
    ) -> Result<(u64, Attempt, Message), Stop> {
        let live = self.live;
        let mut a = 0u64;
        loop {
            a += 1;
            let attempt = live.client.send(body, live.abort, &mut || {
                crate::fault!("provider.sent", k.to_string().as_str())
            });
            let c = classify(&attempt);
            let estimated = Charge::estimated(max_tokens, body.len() as u64);
            let response = match &attempt.reply {
                Some(r) => match live.dir.write_response(k, a, &r.body) {
                    Ok(()) => Some(ResponseFile {
                        file: runs::response_name(k, a),
                        bytes: r.body.len() as u64,
                        sha256: util::sha256_hex(&r.body),
                        complete: r.complete(),
                    }),
                    Err(cause) => {
                        // This attempt will have no record; it is charged as
                        // an unrecorded attempt is (6.4).
                        self.usage.charge(&estimated);
                        return Err(archive_failed(&cause));
                    }
                },
                None => None,
            };
            let usage = c.message.as_ref().map(|m| m.usage);
            let charge = policy::charge(
                c.outcome,
                attempt.written,
                usage.as_ref(),
                body.len() as u64,
                max_tokens,
            );
            let then = policy::decide(
                c.outcome,
                attempt.status(),
                attempt.retry_after(),
                a as u32,
                &live.retry,
            );
            let record = ProviderAttempt {
                request: k,
                attempt: a,
                started_at: attempt.started_at_utc(),
                ended_at: attempt.ended_at_utc(),
                elapsed_ms: attempt.elapsed_ms(),
                timeout_seconds: attempt.timeout_seconds(),
                request_written: attempt.written.as_str().to_string(),
                outcome: c.outcome.as_str().to_string(),
                status: attempt.status().map(u64::from),
                headers: attempt
                    .reply
                    .as_ref()
                    .map(|r| r.headers.clone())
                    .unwrap_or_default(),
                response,
                error: c.error.clone(),
                stop_reason: c.message.as_ref().and_then(|m| m.stop_reason.recorded()),
                model: c.message.as_ref().and_then(|m| m.model.clone()),
                usage,
                charged: charge,
                problem: c.problem.clone(),
                then: then.as_str().to_string(),
                delay_ms: then.delay_ms(),
            };
            if let Err(cause) = live.dir.publish(
                live.audit,
                "provider_attempt",
                &runs::attempt_name(k, a),
                record.to_j(),
            ) {
                self.usage.charge(&estimated);
                return Err(archive_failed(&cause));
            }
            self.attempts += 1;
            self.usage.charge(&charge);
            if attempt.written != Written::None {
                self.seen.entry(k).or_default().written = true;
            }
            if let Some(stop) = self.near_limit(k + 1) {
                return Err(stop);
            }
            match then {
                Then::Use => {
                    let msg = c.message.expect("a used response is a decoded message");
                    return Ok((a, attempt, msg));
                }
                Then::End(ending) => {
                    if matches!(
                        ending,
                        Ending::Interrupted(Cause::ProviderUnavailable | Cause::ProviderRejected)
                    ) {
                        self.provider = Some(ProviderFacts {
                            status: attempt.status().map(u64::from),
                            error_type: c.error.as_ref().and_then(|e| e.kind.clone()),
                            error_message: if crate::sabotage!("hide_provider_message") {
                                None
                            } else {
                                c.error.as_ref().and_then(|e| e.message.clone())
                            },
                            request_id: attempt
                                .request_id()
                                .map(str::to_string)
                                .or_else(|| c.error.as_ref().and_then(|e| e.request_id.clone())),
                            request: k,
                            attempt: a,
                        });
                    }
                    return Err(Stop::Ending(
                        ending,
                        end_message(ending, k, a, &attempt, &c),
                    ));
                }
                Then::Retry { delay_ms } => {
                    if let Some(cause) = live.abort.sleep(Duration::from_millis(delay_ms)) {
                        return Err(stopped(cause));
                    }
                    if let Some(stop) = self.before_request() {
                        return Err(stop);
                    }
                }
            }
        }
    }

    /// Publish a notice record of `kind` for `request`. `Ok(None)`: it was
    /// not published because the notice is already used.
    fn publish_notice(
        &mut self,
        kind: &'static str,
        request: u64,
        text: &str,
        remaining: Option<Remaining>,
    ) -> Result<Option<String>, Stop> {
        let live = self.live;
        let body = Notice {
            kind: kind.to_string(),
            run: live.run,
            request,
            text: text.to_string(),
            remaining,
        };
        let reset = crate::sabotage!("reset_notice_allowance") && live.run > 1;
        let published = log::publish(live.audit, "notice", |state| {
            if state.seal().is_some() {
                return Err(Fail::refused(
                    "sealed",
                    "The log holds a seal; no notice follows it.",
                ));
            }
            if !reset && state.notice_used(kind) {
                return Err(Fail::refused(
                    "notice_used",
                    format!("The {kind} notice was already used in this audit."),
                ));
            }
            if state
                .placements()
                .iter()
                .any(|p| p.run == live.run && p.ended.is_some())
            {
                return Err(Fail::refused(
                    "run_ended",
                    "This placement already has its run_ended record.",
                ));
            }
            Ok(body.to_j())
        });
        match published {
            Ok(p) => {
                let record = format!("log/{}.json", p.n);
                self.notices.push(Published {
                    kind,
                    record: record.clone(),
                    request,
                });
                Ok(Some(record))
            }
            Err(PubErr::Refused(f)) if f.reason == "sealed" => {
                let state = log::read(live.audit);
                if state.damaged() {
                    return Err(damaged(&state));
                }
                match self.sealed_in_log(&state) {
                    Some(stop) => Err(stop),
                    None => Ok(None),
                }
            }
            Err(PubErr::Refused(_)) => Ok(None),
            Err(PubErr::Damaged(state)) => Err(Stop::LogDamaged(format!(
                "The audit log was found damaged ({}) while recording a notice; the run published nothing more.",
                state.bad_names()
            ))),
            Err(PubErr::NotPublished(c)) | Err(PubErr::Uncertain { cause: c, .. }) => {
                Err(archive_failed(&c))
            }
        }
    }

    /// After an attempt is accounted: trigger the near-limit notice once per
    /// audit, naming the next request, which carries it (6.4).
    fn near_limit(&mut self, next: u64) -> Option<Stop> {
        if self.near_used {
            return None;
        }
        let pinned = self.pinned();
        let used = self.cumulative();
        if !pinned.limits.near_limit(&used, pinned.near_limit_percent) {
            return None;
        }
        let remaining = pinned.limits.remaining(&used);
        let text = remaining.fill(&pinned.near_limit);
        match self.publish_notice("near_limit", next, &text, Some(remaining)) {
            Ok(Some(_)) => {
                self.near_used = true;
                self.pending = Some((next, text));
                None
            }
            Ok(None) => {
                self.near_used = true;
                None
            }
            Err(stop) => Some(stop),
        }
    }

    /// The near-limit text, if it is pending for `request`.
    fn take_pending(&mut self, request: u64) -> Option<String> {
        match self.pending.take() {
            Some((r, text)) if r == request => Some(text),
            other => {
                self.pending = other;
                None
            }
        }
    }

    fn placement(&self) -> answer::Placement {
        answer::Placement {
            run: self.live.run,
            continuing: self.live.run > 1,
            used: self.cumulative(),
            limits: self.pinned().limits,
            notices_used: NoticesUsed {
                reminder: self.reminder_used,
                near_limit: self.near_used,
            },
        }
    }

    /// Execute the used response of request `k` (attempt `a`), then follow
    /// its stop reason. `Ok` means the next request is planned in `conv`.
    fn respond(
        &mut self,
        conv: &mut Conversation,
        k: u64,
        a: u64,
        body: &[u8],
        msg: &Message,
    ) -> Result<(), Stop> {
        let (results, early) = self.execute_blocks(k, a, body, msg);
        // Whether a seal was recorded is read from the log, whatever the
        // calls replied; a seal is delivered before the placement ends,
        // whatever else happened (6.3, 6.8).
        let state = log::read(self.live.audit);
        if state.damaged() {
            return Err(damaged(&state));
        }
        if let Some(stop) = self.sealed_in_log(&state) {
            return Err(stop);
        }
        if let Some(stop) = early {
            return Err(stop);
        }
        let exhausted = self.pinned().limits.exhausted(&self.cumulative());
        let next = policy::after_response(
            &msg.stop_reason,
            msg.has_tool_use(),
            false,
            exhausted,
            self.reminder_used,
        );
        let content = msg.content.of(body);
        match next {
            Next::End(e) => Err(Stop::Ending(e, stop_reason_message(e, msg))),
            Next::SendResults => {
                let notice = self.take_pending(k + 1);
                conv.push(turn(
                    content,
                    &user_message(&results, None, notice.as_deref()),
                ));
                between_turns(k);
                Ok(())
            }
            Next::SendReminder => {
                let reminder = self.pinned().reminder.clone();
                let sent = self.publish_notice("reminder", k + 1, &reminder, None)?;
                self.reminder_used = true;
                if sent.is_none() {
                    // The reminder was already used: an ordinary ending.
                    return Err(Stop::Ending(
                        Ending::EndedUnsubmitted,
                        "The auditor's turn ended without a submission after the reminder was used."
                            .into(),
                    ));
                }
                let notice = self.take_pending(k + 1);
                conv.push(turn(
                    content,
                    &user_message(&results, Some(&reminder), notice.as_deref()),
                ));
                between_turns(k);
                Ok(())
            }
        }
    }

    /// Execute every `tool_use` block in order. Returns the `tool_result`
    /// blocks to send and, when execution stopped early, why.
    fn execute_blocks(
        &mut self,
        k: u64,
        a: u64,
        body: &[u8],
        msg: &Message,
    ) -> (Vec<Vec<u8>>, Option<Stop>) {
        let live = self.live;
        let mut results = Vec::new();
        for (block, tu) in msg.tool_uses() {
            if !live.flags.sealed() {
                if let Some(c) = live.abort.cause() {
                    // The stop path applies only while no seal exists; a
                    // submit's reply may not say that its seal was linked.
                    if log::read(live.audit).seal().is_none() {
                        return (results, Some(stopped(c)));
                    }
                    live.flags.set_sealed();
                }
            }
            self.calls += 1;
            let c = self.calls;
            let raw = block.span.of(body);
            let Member::Present(id) = &tu.id else {
                // An unanswerable block is captured; nothing after it runs.
                if let Err(cause) = live.dir.write_call(c, raw) {
                    return (results, Some(archive_failed(&cause)));
                }
                return (
                    results,
                    Some(Stop::Ending(
                        Ending::Interrupted(Cause::ProtocolAnomaly),
                        format!(
                            "Block {} of response {k} is a tool_use block without a usable id ({}); it cannot be answered.",
                            block.index,
                            tu.id.defect().unwrap_or("unusable")
                        ),
                    )),
                );
            };
            let name = tu.name.clone().ok();
            let input = tu.input.clone().ok().map(|s| s.of(body));
            let call = Call {
                call: c,
                tool_use_id: id,
                name: name.as_deref(),
                input,
            };
            // Sabotage controls that drop captures: search calls lose both
            // records; a refused record call loses both once it is refused.
            let skip = crate::sabotage!("skip_search_capture") && name.as_deref() == Some("search");
            let defer = crate::sabotage!("drop_refused_capture")
                && name.as_deref().is_some_and(|n| n.starts_with("record_"));
            if !skip && !defer {
                if let Err(cause) = live.dir.write_call(c, raw) {
                    let ex = answer::capture_failed(&call, &cause, self.revision);
                    let _ = self.record_result(k, a, block.index, raw, &call, &ex, None);
                    return (results, Some(archive_failed(&cause)));
                }
            }
            #[cfg(feature = "fault-injection")]
            if let Some(n) = &name {
                let _ = crate::fault!("tool.before", n.as_str());
            }
            let (ex, replay_of) = match self.executed.get(id) {
                Some(p)
                    if p.name == name
                        && p.input.as_deref() == input
                        && !crate::sabotage!("replay_reexecutes") =>
                {
                    (
                        Executed {
                            content: p.content.clone(),
                            is_error: p.is_error,
                            outcome: p.outcome,
                            reason: p.reason.clone(),
                            revision: self.revision,
                            log_record: None,
                            sealed: false,
                            end: None,
                        },
                        Some(p.call),
                    )
                }
                Some(p) if p.name != name || p.input.as_deref() != input => {
                    (answer::reused(&call, p.call, self.revision), None)
                }
                _ => (
                    answer::execute(live.audit, live.world, &self.placement(), &call),
                    None,
                ),
            };
            let dropped = defer && ex.outcome == CallOutcome::Refused;
            if defer && !dropped {
                if let Err(cause) = live.dir.write_call(c, raw) {
                    return (results, Some(archive_failed(&cause)));
                }
            }
            if !skip && !dropped {
                if let Err(cause) =
                    self.record_result(k, a, block.index, raw, &call, &ex, replay_of)
                {
                    self.note(&ex);
                    return (results, Some(archive_failed(&cause)));
                }
            }
            if replay_of.is_none() && !self.executed.contains_key(id) {
                self.executed.insert(
                    id.clone(),
                    Prior {
                        call: c,
                        name: name.clone(),
                        input: input.map(<[u8]>::to_vec),
                        content: ex.content.clone(),
                        is_error: ex.is_error,
                        outcome: ex.outcome,
                        reason: ex.reason.clone(),
                    },
                );
            }
            results.push(runs::tool_result_block(id, &ex.content, ex.is_error));
            self.note(&ex);
            if let Some(end) = ex.end {
                let stop = match end {
                    answer::End::ArchiveWriteFailed => Stop::Ending(
                        Ending::Interrupted(Cause::ArchiveWriteFailed),
                        format!(
                            "Call {c} failed record_failed: an archive write failed; the run stopped."
                        ),
                    ),
                    answer::End::AnswerDamaged => Stop::Ending(
                        Ending::Damaged,
                        format!("Call {c} found damaged answer bytes; authoring ended."),
                    ),
                    answer::End::LogDamaged => Stop::LogDamaged(format!(
                        "Call {c} found the audit log damaged; the run published nothing more."
                    )),
                };
                return (results, Some(stop));
            }
        }
        (results, None)
    }

    /// Take what an executed call changed.
    fn note(&mut self, ex: &Executed) {
        self.revision = ex.revision;
        if ex.sealed {
            self.live.flags.set_sealed();
        } else if ex.log_record.is_some() {
            self.entries = true;
        }
    }

    /// Publish `result-<c>.json` for one block.
    fn record_result(
        &self,
        k: u64,
        a: u64,
        block: usize,
        raw: &[u8],
        call: &Call,
        ex: &Executed,
        replay_of: Option<u64>,
    ) -> Result<(), reply::Cause> {
        let completed = ex.outcome == CallOutcome::Completed;
        let r = ToolResult {
            call: call.call,
            request: k,
            attempt: a,
            block: block as u64,
            call_bytes: raw.len() as u64,
            call_sha256: util::sha256_hex(raw),
            tool_use_id: call.tool_use_id.to_string(),
            tool: call.name.map(str::to_string),
            input_sha256: call.input.map(util::sha256_hex),
            replay_of,
            outcome: ex.outcome.name().to_string(),
            reason: if completed { None } else { ex.reason.clone() },
            revision: ex.revision,
            log_record: ex.log_record.clone(),
            is_error: !completed,
            content: ex.content.clone(),
        };
        self.live
            .dir
            .publish(
                self.live.audit,
                "tool_result",
                &runs::result_name(call.call),
                r.to_j(),
            )
            .map(|_| ())
    }

    /// Deliver the recorded seal (8.3), then end `sealed`.
    fn deliver(&mut self) -> Stop {
        let live = self.live;
        let state = log::read(live.audit);
        let request = delivery::Request {
            by: By::Run,
            destination: Destination {
                path: live.destination.clone(),
                source: "commissioned",
            },
            retries_losses_of: None,
            // A stop signal after the seal ends the delivery attempt
            // `failed` with cause `signal`; the placement still ends `sealed`.
            stop: Some(live.flags.signalled.clone()),
        };
        let d = delivery::deliver(live.audit, &state, &request);
        let outcome = d
            .attempts
            .last()
            .and_then(|v| v.outcome.clone())
            .unwrap_or_else(|| "unknown".into());
        self.delivered = Some(d);
        Stop::Ending(
            Ending::Sealed,
            format!(
                "The auditor submitted its answer and the seal was recorded; the run's delivery ended {outcome}."
            ),
        )
    }
}

/// The `run.between_turns:<k>` failure point: every block of response `k`
/// is executed and recorded and request `k+1` is planned, not yet captured.
fn between_turns(k: u64) {
    #[cfg(feature = "fault-injection")]
    let _ = crate::fault!("run.between_turns", k.to_string().as_str());
    #[cfg(not(feature = "fault-injection"))]
    let _ = k;
}

fn end_message(
    ending: Ending,
    k: u64,
    a: u64,
    attempt: &Attempt,
    c: &crate::provider::response::Classified,
) -> String {
    let what = || match (attempt.status(), &attempt.failure_text()) {
        (Some(s), _) => format!("status {s}"),
        (None, Some(f)) => f.clone(),
        (None, None) => c.outcome.as_str().to_string(),
    };
    match ending {
        Ending::Interrupted(Cause::ProviderUnavailable) => format!(
            "The provider was unavailable on attempt {a} of request {k} ({}); the run may be continued.",
            what()
        ),
        Ending::Interrupted(Cause::ProviderRejected) => format!(
            "The provider rejected request {k} with {}{}; the run may be continued.",
            what(),
            c.error
                .as_ref()
                .and_then(|e| e.kind.as_deref())
                .map(|t| format!(" ({t})"))
                .unwrap_or_default()
        ),
        Ending::Interrupted(Cause::ProtocolAnomaly) => format!(
            "Response {k} could not be used: {}.",
            c.problem.as_deref().unwrap_or("it was undecodable")
        ),
        Ending::Interrupted(Cause::Signal) => {
            "A stop signal arrived during a provider request; the run stopped and may be continued."
                .into()
        }
        Ending::StoppedByClose => {
            "Close was requested during a provider request; the run stopped.".into()
        }
        other => format!("The run ended {}.", other.as_str()),
    }
}

fn stop_reason_message(e: Ending, msg: &Message) -> String {
    let reason = msg.stop_reason.as_str().replace('\0', "\\u0000");
    match e {
        Ending::EndedUnsubmitted => {
            "The auditor's turn ended without a submission after the reminder was used.".into()
        }
        Ending::LimitReached => "A limit was reached after the auditor's turn ended.".into(),
        Ending::Interrupted(Cause::MaxTokens) => {
            "The response reached its max_tokens without a tool call; the run may be continued."
                .into()
        }
        Ending::Interrupted(Cause::ContextExhausted) => {
            "The model's context window was exhausted; continuing starts a fresh conversation."
                .into()
        }
        Ending::Interrupted(Cause::ProviderRefusal) => {
            "The provider refused to continue (stop_reason refusal); the run may be continued."
                .into()
        }
        Ending::Interrupted(Cause::ProtocolAnomaly) => format!(
            "The response's stop_reason {reason:?} cannot be followed; the run may be continued."
        ),
        other => format!("The run ended {}.", other.as_str()),
    }
}

/// The run reply's `notices`: each notice published during the placement
/// with its `sent` value.
pub fn notices_j(e: &Ended) -> J {
    J::Arr(
        e.notices
            .iter()
            .map(|n| {
                J::obj()
                    .with("type", n.kind)
                    .with("sent", e.sent(n.request))
            })
            .collect(),
    )
}
