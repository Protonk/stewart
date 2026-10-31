//! Decoding provider bodies and classifying attempts (INTERFACE 6.2, 6.6, 4.5).
//!
//! A message is decoded tolerantly (see `tolerant`). Stewart interprets only
//! these members, each of which must appear exactly once in its object:
//!
//! - in the message: `content` (an array), `stop_reason` (a string) and
//!   `usage` (`input_tokens` and `output_tokens` integers; each cache count an
//!   integer, null or absent, and at most once). A 200 body that is not a JSON
//!   object, or in which one of these is missing, of another type or
//!   repeated, is undecodable. `model` is recorded when it is a string that
//!   appears once.
//! - in each content element: `type`. An element that is not an object, or
//!   whose `type` is missing, repeated or not a string, is a block of unknown
//!   type, echoed and never interpreted.
//! - in a `tool_use` block: `id`, `name` and `input`, each kept with how it
//!   falls short, so that the loop can apply 6.2's refusals. `input` is kept
//!   as raw bytes; the auditor tools decode it strictly when the call runs.
//! - in an error body: `error.type`, `error.message` and `request_id`,
//!   recorded when they are strings that appear once.
//!
//! "A string" means a JSON string that decodes to Unicode: a string holding a
//! lone surrogate escape counts as another type, because no record or reply
//! could carry it faithfully. Records hold only strings strict decoding
//! accepts (1.2), so a string containing U+0000 is never recorded: an `id`
//! with it makes the block unanswerable, a `name` with it is refused
//! `tool_unknown`, a `stop_reason` with it is an unknown stop reason recorded
//! as null, and `model` and the error members with it are recorded as null.
//! The raw capture keeps the bytes.
//!
//! Integers are written with digits only and are at most `usage::FIGURE_MAX`,
//! the bound every recorded usage figure has; a sign, fraction, exponent or
//! larger value makes a usage count another type.

use crate::provider::Outcome;
use crate::provider::StopCause;
use crate::provider::http::BodyEnd;
use crate::provider::tolerant::{self, Kind, Member, Span};
use crate::provider::transport::{Attempt, Failure, Written};
use crate::runs::{self, ErrorFacts, ReportedUsage};

/// A message's `stop_reason`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StopReason {
    EndTurn,
    MaxTokens,
    StopSequence,
    ToolUse,
    PauseTurn,
    Refusal,
    ModelContextWindowExceeded,
    /// Any other string, kept as received (it may contain U+0000, and is
    /// then recorded as null).
    Other(String),
}

impl StopReason {
    pub fn parse(s: &str) -> StopReason {
        match s {
            "end_turn" => StopReason::EndTurn,
            "max_tokens" => StopReason::MaxTokens,
            "stop_sequence" => StopReason::StopSequence,
            "tool_use" => StopReason::ToolUse,
            "pause_turn" => StopReason::PauseTurn,
            "refusal" => StopReason::Refusal,
            "model_context_window_exceeded" => StopReason::ModelContextWindowExceeded,
            other => StopReason::Other(other.to_string()),
        }
    }

    pub fn as_str(&self) -> &str {
        match self {
            StopReason::EndTurn => "end_turn",
            StopReason::MaxTokens => "max_tokens",
            StopReason::StopSequence => "stop_sequence",
            StopReason::ToolUse => "tool_use",
            StopReason::PauseTurn => "pause_turn",
            StopReason::Refusal => "refusal",
            StopReason::ModelContextWindowExceeded => "model_context_window_exceeded",
            StopReason::Other(s) => s,
        }
    }

    /// The attempt record's `stop_reason`: the string, or `None` when it
    /// contains U+0000.
    pub fn recorded(&self) -> Option<String> {
        recordable(self.as_str().to_string())
    }
}

/// A string a record can hold: `None` when it contains U+0000.
pub fn recordable(s: String) -> Option<String> {
    (!s.contains('\0')).then_some(s)
}

/// The interpreted members of a `tool_use` block.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ToolUse {
    /// Not `Present`: the block cannot be answered (6.3).
    pub id: Member<String>,
    /// Not `Present`: the call is refused `tool_unknown`.
    pub name: Member<String>,
    /// The raw span of the `input` value. `Missing` or `Repeated`: the call is
    /// refused `input_invalid`.
    pub input: Member<Span>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockKind {
    ToolUse(ToolUse),
    /// Any other block, including `text` and `thinking`, or an element whose
    /// `type` is missing, repeated or not a string.
    Other,
}

/// One element of `content`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Block {
    /// Its position in `content`, counted from 0 (the result record's `block`).
    pub index: usize,
    /// The element's bytes, from its `{` to its `}` for an object (the call capture).
    pub span: Span,
    pub kind: BlockKind,
}

/// A decoded message. Spans index the response body it was decoded from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Message {
    /// The raw `content` array, copied byte for byte into the next request.
    pub content: Span,
    pub blocks: Vec<Block>,
    pub stop_reason: StopReason,
    /// `model` when it is a recordable string that appears once.
    pub model: Option<String>,
    pub usage: ReportedUsage,
    /// Top-level input/cache/output counts estimate the next ordinary context.
    /// These are distinct from billed totals when iterations are present.
    pub context_tokens: u64,
    pub compaction_usage: bool,
}

impl Message {
    /// A summary is usable only with its complete signed block. Preserve the
    /// array's raw bytes on success; never decode/re-encode its signed content.
    pub fn valid_summary(&self, body: &[u8]) -> bool {
        if self.stop_reason.as_str() != "compaction" || self.blocks.len() != 1 {
            return false;
        }
        let Ok(members) = tolerant::members(body, self.blocks[0].span) else {
            return false;
        };
        let text = |name| tolerant::as_string(body, tolerant::once(&members, name)).ok();
        text("type").as_deref() == Some("compaction")
            && text("content").is_some_and(|s| !s.is_empty())
            && text("signature").is_some_and(|s| !s.is_empty())
    }

    /// Whether any block is a `tool_use` block.
    pub fn has_tool_use(&self) -> bool {
        self.tool_uses().next().is_some()
    }

    /// The `tool_use` blocks, in order.
    pub fn tool_uses(&self) -> impl Iterator<Item = (&Block, &ToolUse)> {
        self.blocks.iter().filter_map(|b| match &b.kind {
            BlockKind::ToolUse(t) => Some((b, t)),
            BlockKind::Other => None,
        })
    }
}

/// Decode an HTTP 200 body as a message; the error is the attempt record's
/// `problem` prose.
pub fn decode_message(body: &[u8]) -> Result<Message, String> {
    let top = tolerant::validate(body)?;
    if tolerant::kind(body, top) != Kind::Object {
        return Err("the body is not a JSON object".into());
    }
    let ms = tolerant::members(body, top)?;

    let content = match tolerant::once(&ms, "content") {
        Member::Present(s) if tolerant::kind(body, s) == Kind::Array => s,
        Member::Present(_) => return Err("the message's content is not an array".into()),
        m => {
            return Err(format!(
                "the message's content is {}",
                m.defect().unwrap_or("")
            ));
        }
    };
    let stop_reason = match tolerant::as_string(body, tolerant::once(&ms, "stop_reason")) {
        Member::Present(s) => StopReason::parse(&s),
        m => {
            return Err(format!(
                "the message's stop_reason is {}",
                m.defect().unwrap_or("")
            ));
        }
    };
    let (usage, context_tokens, compaction_usage) = match tolerant::once(&ms, "usage") {
        Member::Present(s) if tolerant::kind(body, s) == Kind::Object => usage_iterations(body, s)?,
        Member::Present(_) => return Err("the message's usage is not an object".into()),
        m => {
            return Err(format!(
                "the message's usage is {}",
                m.defect().unwrap_or("")
            ));
        }
    };
    let model = tolerant::as_string(body, tolerant::once(&ms, "model"))
        .ok()
        .and_then(recordable);

    let mut blocks = Vec::new();
    for (index, span) in tolerant::elements(body, content)?.into_iter().enumerate() {
        blocks.push(Block {
            index,
            span,
            kind: block_kind(body, span)?,
        });
    }
    Ok(Message {
        content,
        blocks,
        stop_reason,
        model,
        usage,
        context_tokens,
        compaction_usage,
    })
}

fn usage_iterations(b: &[u8], s: Span) -> Result<(ReportedUsage, u64, bool), String> {
    let top = usage(b, s)?;
    let context = top.charge().input_tokens + top.output_tokens;
    let ms = tolerant::members(b, s)?;
    let span = match tolerant::once(&ms, "iterations") {
        Member::Missing => return Ok((top, context, false)),
        Member::Present(v) if tolerant::kind(b, v) == Kind::Null => {
            return Ok((top, context, false));
        }
        Member::Present(v) if tolerant::kind(b, v) == Kind::Array => v,
        _ => return Err("usage.iterations must be one nonempty array or null".into()),
    };
    let iterations = tolerant::elements(b, span)?;
    if iterations.is_empty() {
        return Err("usage.iterations is empty".into());
    }
    let mut sum = ReportedUsage {
        input_tokens: 0,
        cache_creation_input_tokens: 0,
        cache_read_input_tokens: 0,
        output_tokens: 0,
    };
    let mut compaction = false;
    let add = |a: u64, v: u64| {
        a.checked_add(v)
            .filter(|n| *n <= crate::usage::FIGURE_MAX)
            .ok_or_else(|| "summed usage.iterations count exceeds 2^48".to_string())
    };
    for span in iterations {
        if tolerant::kind(b, span) != Kind::Object {
            return Err("usage.iterations member is not an object".into());
        }
        let members = tolerant::members(b, span)?;
        match tolerant::as_string(b, tolerant::once(&members, "type"))
            .ok()
            .as_deref()
        {
            Some("message") => {}
            Some("compaction") => compaction = true,
            _ => {
                return Err(
                    "usage.iterations type must occur once and be message or compaction".into(),
                );
            }
        }
        let u = usage(b, span)?;
        sum.input_tokens = add(sum.input_tokens, u.input_tokens)?;
        sum.cache_creation_input_tokens = add(
            sum.cache_creation_input_tokens,
            u.cache_creation_input_tokens,
        )?;
        sum.cache_read_input_tokens = add(sum.cache_read_input_tokens, u.cache_read_input_tokens)?;
        sum.output_tokens = add(sum.output_tokens, u.output_tokens)?;
    }
    if crate::sabotage!("ignore_compaction_usage") {
        sum = top;
    }
    Ok((sum, context, compaction))
}

fn usage(b: &[u8], s: Span) -> Result<ReportedUsage, String> {
    let ms = tolerant::members(b, s)?;
    let figure = |v: Span| tolerant::integer(b, v).filter(|n| *n <= crate::usage::FIGURE_MAX);
    let required = |k: &str| -> Result<u64, String> {
        match tolerant::once(&ms, k) {
            Member::Present(v) => figure(v)
                .ok_or_else(|| format!("usage.{k} is not a non-negative integer up to 2^48")),
            m => Err(format!("usage.{k} is {}", m.defect().unwrap_or(""))),
        }
    };
    let cache = |k: &str| -> Result<u64, String> {
        match tolerant::once(&ms, k) {
            Member::Missing => Ok(0),
            Member::Present(v) if tolerant::kind(b, v) == Kind::Null => Ok(0),
            Member::Present(v) => figure(v).ok_or_else(|| {
                format!("usage.{k} is not a non-negative integer up to 2^48, or null")
            }),
            m => Err(format!("usage.{k} is {}", m.defect().unwrap_or(""))),
        }
    };
    Ok(ReportedUsage {
        input_tokens: required("input_tokens")?,
        cache_creation_input_tokens: cache("cache_creation_input_tokens")?,
        cache_read_input_tokens: cache("cache_read_input_tokens")?,
        output_tokens: required("output_tokens")?,
    })
}

/// A string member that records may hold: one that contains U+0000 counts as
/// another type.
fn recordable_member(b: &[u8], m: Member<Span>) -> Member<String> {
    match tolerant::as_string(b, m) {
        Member::Present(s) if s.contains('\0') => Member::WrongType,
        other => other,
    }
}

fn block_kind(b: &[u8], s: Span) -> Result<BlockKind, String> {
    if tolerant::kind(b, s) != Kind::Object {
        return Ok(BlockKind::Other);
    }
    let ms = tolerant::members(b, s)?;
    match tolerant::as_string(b, tolerant::once(&ms, "type")) {
        Member::Present(t) if t == "tool_use" => {}
        _ => return Ok(BlockKind::Other),
    }
    Ok(BlockKind::ToolUse(ToolUse {
        id: recordable_member(b, tolerant::once(&ms, "id")),
        name: recordable_member(b, tolerant::once(&ms, "name")),
        input: tolerant::once(&ms, "input"),
    }))
}

/// Decode `{"type":"error","error":{"type":…,"message":…},"request_id":…}`.
/// A body decodes as an error body when it is a JSON object whose `error`
/// member appears once and is an object; the top-level `type` is not
/// interpreted. Each recorded member is `None` unless it is a recordable
/// string that appears once in its object; the message is cut to at most
/// 1,024 bytes on a character boundary.
pub fn decode_error_body(body: &[u8]) -> Option<ErrorFacts> {
    let top = tolerant::validate(body).ok()?;
    if tolerant::kind(body, top) != Kind::Object {
        return None;
    }
    let ms = tolerant::members(body, top).ok()?;
    let err = tolerant::once(&ms, "error").ok()?;
    if tolerant::kind(body, err) != Kind::Object {
        return None;
    }
    let es = tolerant::members(body, err).ok()?;
    let string = |m: Member<Span>| recordable_member(body, m).ok();
    Some(ErrorFacts {
        kind: string(tolerant::once(&es, "type")),
        message: string(tolerant::once(&es, "message"))
            .map(|m| runs::cut(&m, runs::ERROR_MESSAGE_BYTES).to_string()),
        request_id: string(tolerant::once(&ms, "request_id")),
    })
}

/// An attempt's outcome and what was decoded from it.
#[derive(Debug, Clone, PartialEq)]
pub struct Classified {
    pub outcome: Outcome,
    /// The decoded message when the outcome is `response`.
    pub message: Option<Message>,
    /// The error body's members when the body decodes as one (any outcome
    /// other than `response`).
    pub error: Option<ErrorFacts>,
    /// Why a status-200 body was undecodable; `None` otherwise.
    pub problem: Option<String>,
}

/// Classify an attempt (6.6).
///
/// Precedence, so that each attempt has exactly one outcome:
/// 1. the stop path shut the connection down: `aborted_by_close` or
///    `aborted_by_signal`, at whatever stage;
/// 2. the request timeout passed before the response was complete: `timeout`;
/// 3. a status line other than 200 was received: `http_error`, even when its
///    body was cut off;
/// 4. status 200 whose body was cut off by the connection ending or failing:
///    `connection_lost`;
/// 5. status 200 whose body is complete: `response` when it is in identity
///    coding and decodes as a message, else `response_undecodable`; a body
///    over 32 MiB, or one whose framing cannot be followed, is
///    `response_undecodable` too;
/// 6. no status line: `connection_failed` when no request byte was written,
///    else `connection_lost`.
pub fn classify(a: &Attempt) -> Classified {
    let simple = |outcome| Classified {
        outcome,
        message: None,
        error: None,
        problem: None,
    };
    match &a.failure {
        Some(Failure::Aborted(StopCause::Close)) => return simple(Outcome::AbortedByClose),
        Some(Failure::Aborted(StopCause::Signal)) => return simple(Outcome::AbortedBySignal),
        Some(Failure::Timeout) => return simple(Outcome::Timeout),
        _ => {}
    }
    let Some(r) = &a.reply else {
        return simple(if a.written == Written::None {
            Outcome::ConnectionFailed
        } else {
            Outcome::ConnectionLost
        });
    };
    let error = || {
        if r.coding.is_none() {
            decode_error_body(&r.body)
        } else {
            None
        }
    };
    if r.status != 200 {
        return Classified {
            outcome: Outcome::HttpError,
            message: None,
            error: error(),
            problem: None,
        };
    }
    let problem = match &r.end {
        BodyEnd::CutOff => return simple(Outcome::ConnectionLost),
        BodyEnd::Complete => match &r.coding {
            Some(c) => c.clone(),
            None => match decode_message(&r.body) {
                Ok(m) => {
                    return Classified {
                        outcome: Outcome::Response,
                        message: Some(m),
                        error: None,
                        problem: None,
                    };
                }
                Err(p) => p,
            },
        },
        BodyEnd::TooLarge => "the body exceeds 32 MiB".into(),
        BodyEnd::Malformed(m) => format!("the response framing is malformed: {m}"),
    };
    Classified {
        outcome: Outcome::ResponseUndecodable,
        message: None,
        error: error(),
        problem: Some(problem),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::http::Reply;
    use crate::runs::Headers;
    use std::time::{Duration, SystemTime};

    /// A JSON escape (backslash, u, four hex digits) built at run time.
    fn u(hex: &str) -> String {
        format!("{}u{hex}", '\\')
    }

    const THINKING: &str = r#"{"type":"thinking","thinking":"Let me look at a.py first.","signature":"EqQBCkYIBxgCKkB4Zm9v+/=="}"#;

    #[test]
    fn iteration_usage_is_counted_once_and_malformed_usage_is_not_ignored() {
        let response = |iterations: &str| {
            format!(
                r#"{{"content":[],"stop_reason":"tool_use","usage":{{"input_tokens":40,"output_tokens":5,"iterations":{iterations}}}}}"#
            )
        };
        let valid = r#"[{"type":"compaction","input_tokens":100,"output_tokens":20,"cache_read_input_tokens":7},{"type":"message","input_tokens":40,"output_tokens":5,"cache_creation_input_tokens":3}]"#;
        let m = decode_message(response(valid).as_bytes()).unwrap();
        assert_eq!(m.usage.input_tokens, 140);
        assert_eq!(m.usage.output_tokens, 25);
        assert_eq!(m.usage.charge().input_tokens, 150);
        assert_eq!(m.context_tokens, 45);
        assert!(m.compaction_usage);
        assert_eq!(
            decode_message(response("null").as_bytes())
                .unwrap()
                .usage
                .input_tokens,
            40
        );
        for bad in [
            "[]",
            "{}",
            "[null]",
            r#"[{"type":"unknown","input_tokens":1,"output_tokens":2}]"#,
            r#"[{"type":"message","type":"compaction","input_tokens":1,"output_tokens":2}]"#,
            r#"[{"type":"compaction","input_tokens":1,"output_tokens":2,"output_tokens":3}]"#,
            r#"[{"type":"compaction","input_tokens":281474976710656,"output_tokens":0},{"type":"message","input_tokens":1,"output_tokens":0}]"#,
            r#"[{"type":"compaction","input_tokens":-1,"output_tokens":2}]"#,
            r#"[{"type":"compaction","input_tokens":1,"output_tokens":"2"}]"#,
        ] {
            assert!(decode_message(response(bad).as_bytes()).is_err(), "{bad}");
        }
    }

    #[test]
    fn signed_summary_requires_unique_complete_fields() {
        for (content, valid) in [
            (
                r#"[{"type":"compaction","content":"Remember the question.","signature":"signed","future":true}]"#,
                true,
            ),
            (
                r#"[{"type":"compaction","content":null,"signature":"signed"}]"#,
                false,
            ),
            (
                r#"[{"type":"compaction","content":"text","signature":""}]"#,
                false,
            ),
            (
                r#"[{"type":"compaction","content":"text","signature":"a","signature":"b"}]"#,
                false,
            ),
            (r#"[{"type":"compaction","content":"text"}]"#, false),
            (
                r#"[{"type":"compaction","content":"text","signature":"a"},{"type":"tool_use"}]"#,
                false,
            ),
            (r#"[7]"#, false),
        ] {
            let bytes = message(content, "compaction");
            assert_eq!(
                decode_message(bytes.as_bytes())
                    .unwrap()
                    .valid_summary(bytes.as_bytes()),
                valid,
                "{content}"
            );
        }
    }

    fn message(content: &str, stop: &str) -> String {
        format!(
            r#"{{"id":"msg_01","type":"message","role":"assistant","model":"claude-test","content":{content},"stop_reason":"{stop}","stop_sequence":null,"stop_details":{{"x":[1,2]}},"usage":{{"input_tokens":120,"cache_creation_input_tokens":null,"cache_read_input_tokens":30,"output_tokens":45,"service_tier":"standard"}},"future_member":{{"nested":[{{"deep":true}}]}}}}"#
        )
    }

    #[test]
    fn decodes_a_message_keeping_unknown_blocks_and_thinking() {
        let content = format!(
            r#"[{THINKING},{{"type":"text","text":"Reading."}},{{"type":"tool_use","id":"toolu_01","name":"read","input":{{"source":"materials/a.py", "page" : 1}}}},{{"type":"server_tool_use","id":"srv_1","name":"web","input":{{}}}},{{"type":"brand_new_block","payload":[1,2,3]}},7,{{"no_type":true}},{{"type":"text","type":"tool_use"}}]"#
        );
        let body = message(&content, "tool_use");
        let b = body.as_bytes();
        let m = decode_message(b).unwrap();
        assert_eq!(m.content.of(b), content.as_bytes());
        assert_eq!(m.stop_reason, StopReason::ToolUse);
        assert_eq!(m.model.as_deref(), Some("claude-test"));
        assert_eq!(
            m.usage,
            ReportedUsage {
                input_tokens: 120,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 30,
                output_tokens: 45
            }
        );
        assert_eq!(m.usage.charge().input_tokens, 150);
        assert_eq!(m.blocks.len(), 8);
        assert_eq!(m.blocks[0].span.of(b), THINKING.as_bytes());
        assert_eq!(m.blocks[0].kind, BlockKind::Other);
        let uses: Vec<_> = m.tool_uses().collect();
        assert_eq!(uses.len(), 1);
        let (blk, t) = uses[0];
        assert_eq!(blk.index, 2);
        assert_eq!(
            blk.span.of(b),
            br#"{"type":"tool_use","id":"toolu_01","name":"read","input":{"source":"materials/a.py", "page" : 1}}"#
        );
        assert_eq!(t.id, Member::Present("toolu_01".into()));
        assert_eq!(t.name, Member::Present("read".into()));
        // The raw input bytes, whitespace and all.
        assert_eq!(
            t.input.clone().ok().unwrap().of(b),
            br#"{"source":"materials/a.py", "page" : 1}"#
        );
        // Unknown, typeless and type-repeated elements are blocks of unknown type.
        for i in [3, 4, 5, 6, 7] {
            assert_eq!(m.blocks[i].kind, BlockKind::Other, "block {i}");
        }
        assert!(m.has_tool_use());
    }

    #[test]
    fn tool_use_member_defects_are_kept_for_the_loop() {
        let lone = format!("\"x{}\"", u("d800"));
        let content = format!(
            r#"[{{"type":"tool_use","name":"read","input":{{}}}},{{"type":"tool_use","id":"a","id":"b","name":1}},{{"type":"tool_use","id":{lone},"name":"x","name":"y","input":1,"input":2}},{{"type":"tool_u{}e","id":"esc","name":"list"}}]"#,
            u("0073")
        );
        let body = message(&content, "tool_use");
        let b = body.as_bytes();
        let m = decode_message(b).unwrap();
        let uses: Vec<&ToolUse> = m.tool_uses().map(|(_, t)| t).collect();
        assert_eq!(uses.len(), 4);
        assert_eq!(uses[0].id, Member::Missing);
        assert_eq!(uses[0].name, Member::Present("read".into()));
        assert_eq!(uses[1].id, Member::Repeated);
        assert_eq!(uses[1].name, Member::WrongType);
        assert_eq!(uses[1].input, Member::Missing);
        assert_eq!(uses[2].id, Member::WrongType);
        assert_eq!(uses[2].name, Member::Repeated);
        assert_eq!(uses[2].input, Member::Repeated);
        // `type` is compared after escape decoding.
        assert_eq!(uses[3].id, Member::Present("esc".into()));
        assert_eq!(uses[3].input, Member::Missing);
    }

    #[test]
    fn every_stop_reason() {
        for (s, want) in [
            ("end_turn", StopReason::EndTurn),
            ("max_tokens", StopReason::MaxTokens),
            ("stop_sequence", StopReason::StopSequence),
            ("tool_use", StopReason::ToolUse),
            ("pause_turn", StopReason::PauseTurn),
            ("refusal", StopReason::Refusal),
            (
                "model_context_window_exceeded",
                StopReason::ModelContextWindowExceeded,
            ),
            ("something_new", StopReason::Other("something_new".into())),
            ("", StopReason::Other(String::new())),
        ] {
            let m = decode_message(message("[]", s).as_bytes()).unwrap();
            assert_eq!(m.stop_reason, want);
            assert_eq!(m.stop_reason.as_str(), s);
        }
    }

    #[test]
    fn interpreted_members_must_appear_exactly_once() {
        let ok =
            r#""content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}"#;
        assert!(decode_message(format!("{{{ok}}}").as_bytes()).is_ok());
        for (body, why) in [
            (r#"[]"#.to_string(), "not a JSON object"),
            (r#""text""#.to_string(), "not a JSON object"),
            (r#"{"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}}"#.into(), "content is missing"),
            (format!(r#"{{{ok},"content":[]}}"#), "content is repeated"),
            (format!(r#"{{"cont{}nt":[],{ok}}}"#, u("0065")), "content is repeated"),
            (r#"{"content":{},"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}}"#.into(), "content is not an array"),
            (r#"{"content":[],"usage":{"input_tokens":1,"output_tokens":2}}"#.into(), "stop_reason is missing"),
            (r#"{"content":[],"stop_reason":null,"usage":{"input_tokens":1,"output_tokens":2}}"#.into(), "stop_reason is of another type"),
            (format!(r#"{{"content":[],"stop_reason":"x{}","usage":{{"input_tokens":1,"output_tokens":2}}}}"#, u("dc00")), "stop_reason is of another type"),
            (format!(r#"{{{ok},"stop_reason":"end_turn"}}"#), "stop_reason is repeated"),
            (r#"{"content":[],"stop_reason":"end_turn"}"#.into(), "usage is missing"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":[]}"#.into(), "usage is not an object"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"output_tokens":2}}"#.into(), "usage.input_tokens is missing"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2,"output_tokens":2}}"#.into(), "usage.output_tokens is repeated"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":-1,"output_tokens":2}}"#.into(), "input_tokens is not a non-negative integer"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1.0,"output_tokens":2}}"#.into(), "input_tokens is not a non-negative integer"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":"1","output_tokens":2}}"#.into(), "input_tokens is not a non-negative integer"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":null}}"#.into(), "output_tokens is not a non-negative integer"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2,"cache_read_input_tokens":"3"}}"#.into(), "cache_read_input_tokens is not"),
            (r#"{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2,"cache_creation_input_tokens":1,"cache_creation_input_tokens":null}}"#.into(), "cache_creation_input_tokens is repeated"),
            (format!(r#"{{{ok}}} x"#), "bytes after"),
            (format!("\u{feff}{{{ok}}}"), "byte-order mark"),
        ] {
            let e = decode_message(body.as_bytes()).unwrap_err();
            assert!(e.contains(why), "{body}: {e}");
        }
    }

    #[test]
    fn model_is_recorded_only_as_a_string_once() {
        let rest =
            r#""content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}"#;
        for (model, want) in [
            (r#""model":"m","#, Some("m")),
            (r#""model":7,"#, None),
            (r#""model":"a","model":"b","#, None),
            ("", None),
        ] {
            let m = decode_message(format!("{{{model}{rest}}}").as_bytes()).unwrap();
            assert_eq!(m.model.as_deref(), want, "{model}");
        }
    }

    #[test]
    fn deeply_nested_unknown_values_are_tolerated() {
        let deep = format!("{}{}", "[".repeat(10_000), "]".repeat(10_000));
        let body = message(
            &format!(r#"[{{"type":"tool_use","id":"t","name":"read","input":{deep}}}]"#),
            "tool_use",
        );
        let b = body.as_bytes();
        let m = decode_message(b).unwrap();
        let (_, t) = m.tool_uses().next().unwrap();
        assert_eq!(t.input.clone().ok().unwrap().of(b), deep.as_bytes());
    }

    #[test]
    fn error_bodies() {
        let e = decode_error_body(
            br#"{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"},"request_id":"req_011"}"#,
        )
        .unwrap();
        assert_eq!(e.kind.as_deref(), Some("overloaded_error"));
        assert_eq!(e.message.as_deref(), Some("Overloaded"));
        assert_eq!(e.request_id.as_deref(), Some("req_011"));
        let e = decode_error_body(
            br#"{"error":{"type":1,"message":"a","message":"b"},"request_id":null}"#,
        )
        .unwrap();
        assert_eq!(
            e,
            ErrorFacts {
                kind: None,
                message: None,
                request_id: None
            }
        );
        assert_eq!(decode_error_body(b"<html>bad gateway</html>"), None);
        assert_eq!(decode_error_body(br#"{"error":"text"}"#), None);
        assert_eq!(decode_error_body(br#"{"error":{},"error":{}}"#), None);
        assert_eq!(decode_error_body(b"[]"), None);
        // The message is cut to 1,024 bytes on a character boundary.
        let long = format!("{}{}", "a".repeat(1023), "é".repeat(10));
        let body = format!(r#"{{"error":{{"message":"{long}"}}}}"#);
        let e = decode_error_body(body.as_bytes()).unwrap();
        assert_eq!(e.message.unwrap(), "a".repeat(1023));
    }

    fn attempt(written: Written, reply: Option<Reply>, failure: Option<Failure>) -> Attempt {
        Attempt {
            started_at: SystemTime::UNIX_EPOCH,
            ended_at: SystemTime::UNIX_EPOCH,
            elapsed: Duration::ZERO,
            timeout: Duration::from_secs(600),
            body_bytes: 10,
            written,
            reply,
            failure,
        }
    }

    fn reply(status: u16, body: &str, end: BodyEnd) -> Reply {
        Reply {
            status,
            headers: Headers::default(),
            coding: None,
            body: body.as_bytes().to_vec(),
            end,
        }
    }

    #[test]
    fn classification_follows_the_precedence() {
        let good = message("[]", "end_turn");
        let err = r#"{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}"#;
        let broken = Some(Failure::Broken("reset".into()));
        let cases: Vec<(Attempt, Outcome)> = vec![
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, &good, BodyEnd::Complete)),
                    None,
                ),
                Outcome::Response,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, "{}", BodyEnd::Complete)),
                    None,
                ),
                Outcome::ResponseUndecodable,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, &good[..20], BodyEnd::CutOff)),
                    broken.clone(),
                ),
                Outcome::ConnectionLost,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, &good, BodyEnd::TooLarge)),
                    None,
                ),
                Outcome::ResponseUndecodable,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, "", BodyEnd::Malformed("x".into()))),
                    None,
                ),
                Outcome::ResponseUndecodable,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(529, err, BodyEnd::Complete)),
                    None,
                ),
                Outcome::HttpError,
            ),
            (
                attempt(
                    Written::Partial,
                    Some(reply(413, err, BodyEnd::CutOff)),
                    broken.clone(),
                ),
                Outcome::HttpError,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(201, &good, BodyEnd::Complete)),
                    None,
                ),
                Outcome::HttpError,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, &good[..20], BodyEnd::CutOff)),
                    Some(Failure::Timeout),
                ),
                Outcome::Timeout,
            ),
            (
                attempt(Written::None, None, Some(Failure::Timeout)),
                Outcome::Timeout,
            ),
            (
                attempt(Written::None, None, broken.clone()),
                Outcome::ConnectionFailed,
            ),
            (
                attempt(Written::Partial, None, broken.clone()),
                Outcome::ConnectionLost,
            ),
            (
                attempt(Written::Complete, None, broken.clone()),
                Outcome::ConnectionLost,
            ),
            (
                attempt(
                    Written::Complete,
                    Some(reply(200, &good[..20], BodyEnd::CutOff)),
                    Some(Failure::Aborted(StopCause::Close)),
                ),
                Outcome::AbortedByClose,
            ),
            (
                attempt(
                    Written::None,
                    None,
                    Some(Failure::Aborted(StopCause::Close)),
                ),
                Outcome::AbortedByClose,
            ),
            (
                attempt(
                    Written::Complete,
                    None,
                    Some(Failure::Aborted(StopCause::Signal)),
                ),
                Outcome::AbortedBySignal,
            ),
        ];
        for (i, (a, want)) in cases.iter().enumerate() {
            assert_eq!(classify(a).outcome, *want, "case {i}");
        }
        let c = classify(&cases[0].0);
        assert!(c.message.is_some() && c.error.is_none() && c.problem.is_none());
        let c = classify(&cases[5].0);
        assert_eq!(c.error.unwrap().kind.as_deref(), Some("overloaded_error"));
        assert!(c.problem.is_none());
        assert!(
            classify(&cases[1].0)
                .problem
                .unwrap()
                .contains("content is missing")
        );
        assert_eq!(classify(&cases[2].0).problem, None);
        assert!(classify(&cases[3].0).problem.unwrap().contains("32 MiB"));
        assert!(classify(&cases[4].0).problem.unwrap().contains("malformed"));
    }

    #[test]
    fn encoded_bodies_are_undecodable_and_not_read_as_errors() {
        let mut r = reply(200, &message("[]", "end_turn"), BodyEnd::Complete);
        r.coding = Some("the body has content-encoding gzip".into());
        let c = classify(&attempt(Written::Complete, Some(r), None));
        assert_eq!(c.outcome, Outcome::ResponseUndecodable);
        assert!(c.problem.unwrap().contains("gzip"));
        let mut r = reply(500, r#"{"error":{"type":"api_error"}}"#, BodyEnd::Complete);
        r.coding = Some("gzip".into());
        let c = classify(&attempt(Written::Complete, Some(r), None));
        assert_eq!((c.outcome, c.error), (Outcome::HttpError, None));
    }

    #[test]
    fn a_200_error_body_is_recorded_as_an_error() {
        let c = classify(&attempt(
            Written::Complete,
            Some(reply(
                200,
                r#"{"type":"error","error":{"type":"api_error","message":"m"}}"#,
                BodyEnd::Complete,
            )),
            None,
        ));
        assert_eq!(c.outcome, Outcome::ResponseUndecodable);
        assert_eq!(c.error.unwrap().kind.as_deref(), Some("api_error"));
    }

    #[test]
    fn strings_with_nul_are_never_recorded() {
        let nul = u("0000");
        let content = format!(
            r#"[{{"type":"tool_use","id":"a{nul}b","name":"read","input":{{}}}},{{"type":"tool_use","id":"ok","name":"re{nul}ad","input":{{}}}}]"#
        );
        let body = format!(
            r#"{{"model":"m{nul}","content":{content},"stop_reason":"end{nul}","usage":{{"input_tokens":1,"output_tokens":2}}}}"#
        );
        let m = decode_message(body.as_bytes()).unwrap();
        let uses: Vec<&ToolUse> = m.tool_uses().map(|(_, t)| t).collect();
        assert_eq!(
            uses[0].id,
            Member::WrongType,
            "an id with NUL is unanswerable"
        );
        assert_eq!(uses[0].name, Member::Present("read".into()));
        assert_eq!(uses[1].id, Member::Present("ok".into()));
        assert_eq!(
            uses[1].name,
            Member::WrongType,
            "a name with NUL is tool_unknown"
        );
        assert_eq!(m.model, None);
        assert_eq!(m.stop_reason, StopReason::Other("end\0".into()));
        assert_eq!(m.stop_reason.recorded(), None);
        assert_eq!(StopReason::EndTurn.recorded().as_deref(), Some("end_turn"));
        let e = decode_error_body(
            format!(r#"{{"error":{{"type":"x{nul}","message":"m{nul}"}},"request_id":"r{nul}"}}"#)
                .as_bytes(),
        )
        .unwrap();
        assert_eq!((e.kind, e.message, e.request_id), (None, None, None));
    }

    #[test]
    fn usage_figures_are_bounded_like_records() {
        let max = crate::usage::FIGURE_MAX;
        let ok = format!(
            r#"{{"content":[],"stop_reason":"end_turn","usage":{{"input_tokens":{max},"output_tokens":0}}}}"#
        );
        assert_eq!(
            decode_message(ok.as_bytes()).unwrap().usage.input_tokens,
            max
        );
        let over = format!(
            r#"{{"content":[],"stop_reason":"end_turn","usage":{{"input_tokens":{},"output_tokens":0}}}}"#,
            max + 1
        );
        assert!(
            decode_message(over.as_bytes())
                .unwrap_err()
                .contains("2^48")
        );
    }

    #[test]
    fn a_200_cut_off_in_its_head_is_a_lost_connection() {
        let c = classify(&attempt(
            Written::Complete,
            Some(reply(200, "", BodyEnd::CutOff)),
            Some(Failure::Broken("closed".into())),
        ));
        assert_eq!(c.outcome, Outcome::ConnectionLost);
        // Another status that arrived stays an HTTP error, cut off or not.
        let c = classify(&attempt(
            Written::Complete,
            Some(reply(503, "{\"err", BodyEnd::CutOff)),
            Some(Failure::Broken("closed".into())),
        ));
        assert_eq!((c.outcome, c.error), (Outcome::HttpError, None));
    }
}
