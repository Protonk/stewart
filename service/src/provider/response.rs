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
//! could carry it faithfully.
//!
//! Integers are written with digits only and fit in 64 bits; a sign, fraction
//! or exponent makes a usage count another type.

use crate::json::J;
use crate::provider::Outcome;
use crate::provider::StopCause;
use crate::provider::http::BodyEnd;
use crate::provider::tolerant::{self, Kind, Member, Span};
use crate::provider::transport::{Attempt, Failure, Written};

/// Most bytes of `error.message` recorded (Appendix B), cut on a character boundary.
pub const ERROR_MESSAGE_LIMIT: usize = 1024;

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
    /// Any other string, kept as received.
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
}

/// A message's usage report. An absent or null cache count is 0.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Usage {
    pub input_tokens: u64,
    pub cache_creation_input_tokens: u64,
    pub cache_read_input_tokens: u64,
    pub output_tokens: u64,
}

impl Usage {
    /// The input charge: `input_tokens` plus both cache counts (6.4).
    pub fn input_charge(&self) -> u64 {
        self.input_tokens
            .saturating_add(self.cache_creation_input_tokens)
            .saturating_add(self.cache_read_input_tokens)
    }

    /// The attempt record's `usage`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("input_tokens", self.input_tokens)
            .with(
                "cache_creation_input_tokens",
                self.cache_creation_input_tokens,
            )
            .with("cache_read_input_tokens", self.cache_read_input_tokens)
            .with("output_tokens", self.output_tokens)
    }
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
    pub model: Option<String>,
    pub usage: Usage,
}

impl Message {
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
    let usage = match tolerant::once(&ms, "usage") {
        Member::Present(s) if tolerant::kind(body, s) == Kind::Object => usage(body, s)?,
        Member::Present(_) => return Err("the message's usage is not an object".into()),
        m => {
            return Err(format!(
                "the message's usage is {}",
                m.defect().unwrap_or("")
            ));
        }
    };
    let model = tolerant::as_string(body, tolerant::once(&ms, "model")).ok();

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
    })
}

fn usage(b: &[u8], s: Span) -> Result<Usage, String> {
    let ms = tolerant::members(b, s)?;
    let required = |k: &str| -> Result<u64, String> {
        match tolerant::once(&ms, k) {
            Member::Present(v) => tolerant::integer(b, v)
                .ok_or_else(|| format!("usage.{k} is not a non-negative integer")),
            m => Err(format!("usage.{k} is {}", m.defect().unwrap_or(""))),
        }
    };
    let cache = |k: &str| -> Result<u64, String> {
        match tolerant::once(&ms, k) {
            Member::Missing => Ok(0),
            Member::Present(v) if tolerant::kind(b, v) == Kind::Null => Ok(0),
            Member::Present(v) => tolerant::integer(b, v)
                .ok_or_else(|| format!("usage.{k} is not a non-negative integer or null")),
            m => Err(format!("usage.{k} is {}", m.defect().unwrap_or(""))),
        }
    };
    Ok(Usage {
        input_tokens: required("input_tokens")?,
        cache_creation_input_tokens: cache("cache_creation_input_tokens")?,
        cache_read_input_tokens: cache("cache_read_input_tokens")?,
        output_tokens: required("output_tokens")?,
    })
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
        id: tolerant::as_string(b, tolerant::once(&ms, "id")),
        name: tolerant::as_string(b, tolerant::once(&ms, "name")),
        input: tolerant::once(&ms, "input"),
    }))
}

/// The members of an error body that are recorded.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ErrorBody {
    pub error_type: Option<String>,
    /// Cut to at most 1,024 bytes on a character boundary.
    pub message: Option<String>,
    pub request_id: Option<String>,
}

impl ErrorBody {
    /// The attempt record's `error`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("type", self.error_type.clone())
            .with("message", self.message.clone())
            .with("request_id", self.request_id.clone())
    }
}

/// Decode `{"type":"error","error":{"type":…,"message":…},"request_id":…}`.
/// A body decodes as an error body when it is a JSON object whose `error`
/// member appears once and is an object; the top-level `type` is not
/// interpreted. Each recorded member is `None` unless it is a string that
/// appears once in its object.
pub fn decode_error_body(body: &[u8]) -> Option<ErrorBody> {
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
    Some(ErrorBody {
        error_type: tolerant::as_string(body, tolerant::once(&es, "type")).ok(),
        message: tolerant::as_string(body, tolerant::once(&es, "message"))
            .ok()
            .map(|m| cut(&m, ERROR_MESSAGE_LIMIT).to_string()),
        request_id: tolerant::as_string(body, tolerant::once(&ms, "request_id")).ok(),
    })
}

/// The longest prefix of `s` of at most `max` bytes that ends on a character boundary.
pub fn cut(s: &str, max: usize) -> &str {
    if s.len() <= max {
        return s;
    }
    let mut end = max;
    while !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

/// An attempt's outcome and what was decoded from it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Classified {
    pub outcome: Outcome,
    /// The decoded message when the outcome is `response`.
    pub message: Option<Message>,
    /// The error body's members when the body decodes as one (any outcome
    /// other than `response`).
    pub error: Option<ErrorBody>,
    /// Why a status-200 body was undecodable; `None` otherwise.
    pub problem: Option<String>,
}

/// Classify an attempt (6.6).
///
/// Precedence, so that each attempt has exactly one outcome:
/// 1. the stop path shut the connection down: `aborted_by_close` or
///    `aborted_by_signal`, at whatever stage;
/// 2. the request timeout passed before the response was complete: `timeout`;
/// 3. a status line was received: status 200 is `response` when its body is
///    complete, within 32 MiB, in identity coding and decodes as a message,
///    else `response_undecodable` (which includes a body cut off by the
///    connection ending or failing); any other status is `http_error`;
/// 4. no status line: `connection_failed` when no request byte was written,
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
        BodyEnd::CutOff => match &a.failure {
            Some(Failure::Broken(m)) => format!("the body was cut off ({m})"),
            _ => "the body was cut off".into(),
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
    use crate::provider::http::{RecordedHeaders, Reply};
    use std::time::{Duration, SystemTime};

    /// A JSON escape (backslash, u, four hex digits) built at run time.
    fn u(hex: &str) -> String {
        format!("{}u{hex}", '\\')
    }

    const THINKING: &str = r#"{"type":"thinking","thinking":"Let me look at a.py first.","signature":"EqQBCkYIBxgCKkB4Zm9v+/=="}"#;

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
            Usage {
                input_tokens: 120,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 30,
                output_tokens: 45
            }
        );
        assert_eq!(m.usage.input_charge(), 150);
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
        assert_eq!(e.error_type.as_deref(), Some("overloaded_error"));
        assert_eq!(e.message.as_deref(), Some("Overloaded"));
        assert_eq!(e.request_id.as_deref(), Some("req_011"));
        assert_eq!(
            e.to_j().string(),
            r#"{"type":"overloaded_error","message":"Overloaded","request_id":"req_011"}"#
        );
        let e = decode_error_body(
            br#"{"error":{"type":1,"message":"a","message":"b"},"request_id":null}"#,
        )
        .unwrap();
        assert_eq!(e, ErrorBody::default());
        assert_eq!(
            e.to_j().string(),
            r#"{"type":null,"message":null,"request_id":null}"#
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
        assert_eq!(cut("abc", 2), "ab");
        assert_eq!(cut("é", 1), "");
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
            headers: RecordedHeaders::default(),
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
                Outcome::ResponseUndecodable,
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
        assert_eq!(
            c.error.unwrap().error_type.as_deref(),
            Some("overloaded_error")
        );
        assert!(c.problem.is_none());
        assert!(
            classify(&cases[1].0)
                .problem
                .unwrap()
                .contains("content is missing")
        );
        assert!(
            classify(&cases[2].0)
                .problem
                .unwrap()
                .contains("cut off (reset)")
        );
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
        assert_eq!(c.error.unwrap().error_type.as_deref(), Some("api_error"));
    }

    #[test]
    fn usage_record_shape() {
        let u = Usage {
            input_tokens: 1,
            cache_creation_input_tokens: 2,
            cache_read_input_tokens: 3,
            output_tokens: 4,
        };
        assert_eq!(
            u.to_j().string(),
            r#"{"input_tokens":1,"cache_creation_input_tokens":2,"cache_read_input_tokens":3,"output_tokens":4}"#
        );
        let big = Usage {
            input_tokens: u64::MAX,
            cache_creation_input_tokens: 1,
            ..Usage::default()
        };
        assert_eq!(big.input_charge(), u64::MAX);
    }
}
