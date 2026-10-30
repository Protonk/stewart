//! Request bodies by splicing pinned bytes, and request captures
//! (INTERFACE 4.5, 6.2).
//!
//! The body of request `k` of a placement is exactly
//!
//! ```text
//! {"model":<M>,"max_tokens":<T>,"system":<S>,"tools":<U><X>,"messages":[<A_1>,…,<A_k>]}
//! ```
//!
//! where `M`, `S` and `U` are the bytes of the arrangement's `model`, `system`
//! and `tools` values, `X` is a comma and the bytes of each `request_extra`
//! member (none in this release), `T` is the request's `max_tokens`, and
//! `A_i` is what request `i` appends, its messages joined by commas. Nothing
//! is re-serialized from a parsed structure: pinned values and captured
//! response content are copied as bytes, and Stewart's own strings (the
//! question, notices, tool use IDs) are written with the pinned escaping of
//! `stewart.answer/1`.
//!
//! Request 1 appends the first user message. Each later request appends the
//! assistant message of the previous response and the user message that
//! answers it.

use crate::archive::decode_record;
use crate::forms;
use crate::json::{self, JsonError, Obj};
use crate::provider::Span;
use crate::provider::account::Limits;
use crate::provider::policy::RetryPolicy;
use crate::util;

/// The notice texts the arrangement pins.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Texts {
    pub reminder: String,
    /// The near-limit template, with `{turns}`, `{input_tokens}` and `{output_tokens}`.
    pub near_limit: String,
    pub continuation: String,
}

/// What a run takes from the pinned arrangement.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pinned {
    /// The exact bytes of the `model` value (a JSON string, quotes included).
    pub model: Vec<u8>,
    /// The exact bytes of the `system` array.
    pub system: Vec<u8>,
    /// The exact bytes of the `tools` array.
    pub tools: Vec<u8>,
    /// The exact bytes of each `request_extra` member (`"key":value`); empty,
    /// since this release's allowlist is empty.
    pub extra: Vec<Vec<u8>>,
    pub anthropic_version: String,
    pub max_tokens_per_request: u64,
    pub texts: Texts,
    pub limits: Limits,
    pub near_limit_percent: u64,
    pub retry: RetryPolicy,
    pub request_timeout_seconds: u64,
}

/// The members of a `stewart.arrangement/1` body.
const ARRANGEMENT_KEYS: [&str; 18] = [
    "schema",
    "family",
    "orientation",
    "model",
    "anthropic_version",
    "max_tokens_per_request",
    "system",
    "tools",
    "request_extra",
    "texts",
    "limits",
    "near_limit_percent",
    "retry",
    "request_timeout_seconds",
    "reader",
    "renderer",
    "reading",
    "bindings",
];

/// Top-level request parameters `request_extra` may hold. Empty in this
/// release: no provider feature may put model-visible content outside the
/// arrangement.
pub const REQUEST_EXTRA_ALLOWLIST: [&str; 0] = [];

impl Pinned {
    /// Take the pinned members from the arrangement record's exact bytes,
    /// which the caller has already checked against the digest the receipt
    /// binds. The record is decoded strictly (1.2); spliced members keep
    /// their stored bytes.
    pub fn from_arrangement(record: &[u8]) -> Result<Pinned, String> {
        let rec = decode_record(record).map_err(|e| format!("the arrangement record: {e}"))?;
        if rec.kind != "arrangement" {
            return Err(format!(
                "the record is a {:?} record, not an arrangement",
                rec.kind
            ));
        }
        decode_body(record, &rec.body()).map_err(|e| format!("the arrangement: {e}"))
    }
}

fn decode_body(raw: &[u8], b: &Obj) -> Result<Pinned, String> {
    let e = |e: JsonError| e.to_string();
    b.only(&ARRANGEMENT_KEYS).map_err(e)?;
    let schema = b.str("schema").map_err(e)?;
    if schema != forms::ARRANGEMENT_SCHEMA {
        return Err(format!(
            "schema {schema:?} is not {}",
            forms::ARRANGEMENT_SCHEMA
        ));
    }
    b.str("model").map_err(e)?;
    b.arr("system").map_err(e)?;
    b.arr("tools").map_err(e)?;
    let extra = b.obj("request_extra").map_err(e)?;
    let mut extra_members = Vec::new();
    for (k, v) in extra.members {
        if !REQUEST_EXTRA_ALLOWLIST.contains(&k.as_str()) {
            return Err(format!(
                "request_extra holds {k:?}, which this release does not allow"
            ));
        }
        // Unreachable while the allowlist is empty: a future member would be
        // spliced as `"key":value`, its key written with the pinned escaping
        // and its value as stored.
        let mut m = json::quote(k).into_bytes();
        m.push(b':');
        m.extend_from_slice(&raw[v.start..v.end]);
        extra_members.push(m);
    }
    let span = |k: &str| -> Result<Vec<u8>, String> {
        let v = b.req(k).map_err(e)?;
        Ok(raw[v.start..v.end].to_vec())
    };
    let anthropic_version = b.str("anthropic_version").map_err(e)?.to_string();
    if anthropic_version.is_empty()
        || !anthropic_version
            .bytes()
            .all(|c| (0x21..=0x7E).contains(&c))
    {
        return Err("anthropic_version is not a header value".into());
    }
    let max_tokens_per_request = b
        .u64("max_tokens_per_request", u32::MAX as u64)
        .map_err(e)?;
    if max_tokens_per_request == 0 {
        return Err("max_tokens_per_request is 0".into());
    }
    let t = b.obj("texts").map_err(e)?;
    t.only(&["reminder", "near_limit", "continuation"])
        .map_err(e)?;
    let texts = Texts {
        reminder: t.str("reminder").map_err(e)?.to_string(),
        near_limit: t.str("near_limit").map_err(e)?.to_string(),
        continuation: t.str("continuation").map_err(e)?.to_string(),
    };
    let l = b.obj("limits").map_err(e)?;
    l.only(&["turns", "input_tokens", "output_tokens"])
        .map_err(e)?;
    let limits = Limits {
        turns: l.u64("turns", crate::frontmatter::MAX_TURNS).map_err(e)?,
        input_tokens: l
            .u64("input_tokens", crate::frontmatter::MAX_INPUT_TOKENS)
            .map_err(e)?,
        output_tokens: l
            .u64("output_tokens", crate::frontmatter::MAX_OUTPUT_TOKENS)
            .map_err(e)?,
    };
    if limits.turns == 0 || limits.input_tokens == 0 || limits.output_tokens == 0 {
        return Err("a limit is 0".into());
    }
    let near_limit_percent = b.u64("near_limit_percent", 100).map_err(e)?;
    let r = b.obj("retry").map_err(e)?;
    r.only(&["attempts", "delays_seconds", "retry_after_ceiling_seconds"])
        .map_err(e)?;
    let attempts = r.u64("attempts", 16).map_err(e)?;
    let delays = r.arr("delays_seconds").map_err(e)?;
    if attempts == 0 || delays.len() as u64 != attempts - 1 {
        return Err("retry.delays_seconds does not have one delay per retry".into());
    }
    let mut delays_ms = Vec::with_capacity(delays.len());
    for (i, d) in delays.iter().enumerate() {
        match d.as_u64() {
            Some(s) if s <= 86_400 => delays_ms.push(s * 1000),
            _ => {
                return Err(format!(
                    "retry.delays_seconds/{i} is not a whole number of seconds up to 86400"
                ));
            }
        }
    }
    let retry = RetryPolicy {
        attempts: attempts as u32,
        delays_ms,
        retry_after_ceiling_seconds: r.u64("retry_after_ceiling_seconds", 86_400).map_err(e)?,
    };
    let request_timeout_seconds = b.u64("request_timeout_seconds", 86_400).map_err(e)?;
    if request_timeout_seconds == 0 {
        return Err("request_timeout_seconds is 0".into());
    }
    Ok(Pinned {
        model: span("model")?,
        system: span("system")?,
        tools: span("tools")?,
        extra: extra_members,
        anthropic_version,
        max_tokens_per_request,
        texts,
        limits,
        near_limit_percent,
        retry,
        request_timeout_seconds,
    })
}

/// `{"type":"text","text":<text>}`.
pub fn text_block(text: &str) -> Vec<u8> {
    let mut out = br#"{"type":"text","text":"#.to_vec();
    json::escape_into(text, &mut out);
    out.push(b'}');
    out
}

/// The first user message: the question body exactly, then the continuation
/// notice in a continuing placement.
pub fn first_user_message(question: &str, continuation: Option<&str>) -> Vec<u8> {
    let mut blocks = vec![text_block(question)];
    if let Some(c) = continuation {
        blocks.push(text_block(c));
    }
    message("user", &blocks)
}

/// An assistant message: the response's `content` bytes, copied exactly.
pub fn assistant_message(content: &[u8]) -> Vec<u8> {
    let mut out = br#"{"role":"assistant","content":"#.to_vec();
    out.extend_from_slice(content);
    out.push(b'}');
    out
}

/// The parts of a `tool_result` block, as its result record holds them.
#[derive(Debug, Clone, Copy)]
pub struct ToolResult<'a> {
    pub tool_use_id: &'a str,
    /// The exact bytes of the result record's `content` value.
    pub content: &'a [u8],
    pub is_error: bool,
}

/// `{"type":"tool_result","tool_use_id":<ID>,"content":<content>,"is_error":<is_error>}`.
pub fn tool_result_block(r: &ToolResult) -> Vec<u8> {
    let mut out = br#"{"type":"tool_result","tool_use_id":"#.to_vec();
    json::escape_into(r.tool_use_id, &mut out);
    out.extend_from_slice(br#","content":"#);
    out.extend_from_slice(r.content);
    out.extend_from_slice(br#","is_error":"#);
    out.extend_from_slice(if r.is_error { b"true" } else { b"false" });
    out.push(b'}');
    out
}

/// The user message answering a response: one `tool_result` block per
/// `tool_use` block, in order, then the reminder when it is sent, then the
/// near-limit notice when it is pending.
pub fn user_message(
    results: &[ToolResult],
    reminder: Option<&str>,
    notice: Option<&str>,
) -> Vec<u8> {
    let mut blocks: Vec<Vec<u8>> = results.iter().map(tool_result_block).collect();
    if let Some(r) = reminder {
        blocks.push(text_block(r));
    }
    if let Some(n) = notice {
        blocks.push(text_block(n));
    }
    message("user", &blocks)
}

fn message(role: &str, blocks: &[Vec<u8>]) -> Vec<u8> {
    let mut out = br#"{"role":"#.to_vec();
    json::escape_into(role, &mut out);
    out.extend_from_slice(br#","content":["#);
    out.extend_from_slice(&blocks.join(&b","[..]));
    out.extend_from_slice(b"]}");
    out
}

/// What a request appends after the first: the assistant message of the
/// previous response and the user message answering it, joined by a comma.
pub fn turn(assistant_content: &[u8], user: &[u8]) -> Vec<u8> {
    let mut out = assistant_message(assistant_content);
    out.push(b',');
    out.extend_from_slice(user);
    out
}

/// The body of a request appending `appended[k-1]` after the earlier ones.
pub fn body<A: AsRef<[u8]>>(p: &Pinned, max_tokens: u64, appended: &[A]) -> Vec<u8> {
    let mut out = br#"{"model":"#.to_vec();
    out.extend_from_slice(&p.model);
    out.extend_from_slice(br#","max_tokens":"#);
    out.extend_from_slice(max_tokens.to_string().as_bytes());
    out.extend_from_slice(br#","system":"#);
    out.extend_from_slice(&p.system);
    out.extend_from_slice(br#","tools":"#);
    out.extend_from_slice(&p.tools);
    for m in &p.extra {
        out.push(b',');
        out.extend_from_slice(m);
    }
    out.extend_from_slice(br#","messages":["#);
    for (i, a) in appended.iter().enumerate() {
        if i > 0 {
            out.push(b',');
        }
        out.extend_from_slice(a.as_ref());
    }
    out.extend_from_slice(b"]}");
    out
}

/// A placement's conversation: what each request appended, in order.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Conversation {
    appended: Vec<Vec<u8>>,
}

impl Conversation {
    /// Start with request 1's first user message.
    pub fn new(first_user_message: Vec<u8>) -> Conversation {
        Conversation {
            appended: vec![first_user_message],
        }
    }

    /// Add what the next request appends (see [`turn`]).
    pub fn push(&mut self, appended: Vec<u8>) {
        self.appended.push(appended);
    }

    /// The number of the latest request.
    pub fn request(&self) -> u64 {
        self.appended.len() as u64
    }

    /// What the latest request appends.
    pub fn latest(&self) -> &[u8] {
        self.appended.last().map_or(&[][..], Vec::as_slice)
    }

    /// The latest request's body.
    pub fn body(&self, p: &Pinned, max_tokens: u64) -> Vec<u8> {
        body(p, max_tokens, &self.appended)
    }
}

/// `request-<k>.json`: one compact JSON line binding the body, then an LF.
pub fn request_capture(k: u64, max_tokens: u64, body: &[u8], appended: &[u8]) -> Vec<u8> {
    let mut out = format!(
        r#"{{"request":{k},"max_tokens":{max_tokens},"body_bytes":{},"body_sha256":"{}","appended":["#,
        body.len(),
        util::sha256_hex(body)
    )
    .into_bytes();
    out.extend_from_slice(appended);
    out.extend_from_slice(b"]}\n");
    out
}

/// A request capture read back by its layout.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RequestCapture {
    pub request: u64,
    pub max_tokens: u64,
    pub body_bytes: u64,
    pub body_sha256: String,
    /// What the request appended, between the capture's `[` and `]`.
    pub appended: Span,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CaptureDefect {
    /// The capture does not end with `]}` and an LF: a kill cut it off, and
    /// its request was never sent.
    CutOff,
    /// The capture does not have the layout Stewart writes.
    Malformed(String),
}

/// Read a request capture by its exact layout. Captures are raw evidence,
/// decoded by their layout, never as control records.
pub fn parse_request_capture(bytes: &[u8]) -> Result<RequestCapture, CaptureDefect> {
    if !bytes.ends_with(b"]}\n") {
        return Err(CaptureDefect::CutOff);
    }
    let bad = |m: &str| CaptureDefect::Malformed(m.to_string());
    let mut at = 0usize;
    let lit = |want: &[u8], at: &mut usize| -> Result<(), CaptureDefect> {
        if bytes[*at..].starts_with(want) {
            *at += want.len();
            Ok(())
        } else {
            Err(bad(&format!(
                "expected {} at byte {at}",
                String::from_utf8_lossy(want)
            )))
        }
    };
    let num = |at: &mut usize| -> Result<u64, CaptureDefect> {
        let start = *at;
        while bytes.get(*at).is_some_and(u8::is_ascii_digit) {
            *at += 1;
        }
        let digits = &bytes[start..*at];
        if digits.is_empty() || (digits.len() > 1 && digits[0] == b'0') {
            return Err(bad(&format!("expected a number at byte {start}")));
        }
        std::str::from_utf8(digits)
            .ok()
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| bad(&format!("the number at byte {start} is too large")))
    };
    lit(br#"{"request":"#, &mut at)?;
    let request = num(&mut at)?;
    lit(br#","max_tokens":"#, &mut at)?;
    let max_tokens = num(&mut at)?;
    lit(br#","body_bytes":"#, &mut at)?;
    let body_bytes = num(&mut at)?;
    lit(br#","body_sha256":""#, &mut at)?;
    let digest = bytes
        .get(at..at + 64)
        .and_then(|d| std::str::from_utf8(d).ok())
        .filter(|d| util::is_hex64(d))
        .ok_or_else(|| bad("body_sha256 is not a SHA-256 digest"))?
        .to_string();
    at += 64;
    lit(br#"","appended":["#, &mut at)?;
    let end = bytes.len() - 3;
    if end < at {
        return Err(bad("the capture ends inside its fields"));
    }
    if bytes[at..end].contains(&b'\n') {
        return Err(bad("the capture has more than one line"));
    }
    Ok(RequestCapture {
        request,
        max_tokens,
        body_bytes,
        body_sha256: digest,
        appended: Span { start: at, end },
    })
}

/// Rebuild the body of the last of `captures` (requests 1…k of a placement,
/// in order) from the arrangement and every capture's appended messages, and
/// check it against the last capture's length and digest.
pub fn rebuild_body(p: &Pinned, captures: &[&[u8]]) -> Result<Vec<u8>, String> {
    let mut appended = Vec::with_capacity(captures.len());
    let mut last = None;
    for (i, c) in captures.iter().enumerate() {
        let k = i as u64 + 1;
        let cap = parse_request_capture(c).map_err(|d| match d {
            CaptureDefect::CutOff => format!("request capture {k} was cut off"),
            CaptureDefect::Malformed(m) => format!("request capture {k} is malformed: {m}"),
        })?;
        if cap.request != k {
            return Err(format!("request capture {k} names request {}", cap.request));
        }
        appended.push(cap.appended.of(c));
        last = Some(cap);
    }
    let last = last.ok_or("there is no request capture")?;
    let b = body(p, last.max_tokens, &appended);
    if b.len() as u64 != last.body_bytes || util::sha256_hex(&b) != last.body_sha256 {
        return Err(format!(
            "the rebuilt body of request {} does not match its capture's length and digest",
            last.request
        ));
    }
    Ok(b)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::archive::record_bytes;
    use crate::forms::{ArrangementInput, arrangement};
    use crate::frontmatter::Settings;
    use crate::json::J;

    fn settings(family: &str, model: &str) -> Settings {
        Settings {
            family: family.into(),
            model: model.into(),
            destination: "/tmp/returns".into(),
            turns: 200,
            input_tokens: 20_000_000,
            output_tokens: 400_000,
            inquiry: None,
            varies: None,
        }
    }

    fn arrangement_record(s: &Settings) -> Vec<u8> {
        let a = arrangement(&ArrangementInput {
            settings: s,
            question_body_sha256: &"a".repeat(64),
            material_index_sha256: &"b".repeat(64),
        });
        record_bytes(
            "arrangement",
            Some("aqm3x7kd2hz5vw4ny"),
            &"c".repeat(64),
            a.body,
        )
    }

    fn pinned() -> Pinned {
        Pinned::from_arrangement(&arrangement_record(&settings(
            "open-inquiry",
            "claude-test-1",
        )))
        .unwrap()
    }

    #[test]
    fn pinned_members_are_the_arrangement_bytes() {
        let s = settings("comparison", "claude-\"quoted\"-model");
        let rec = arrangement_record(&s);
        let p = Pinned::from_arrangement(&rec).unwrap();
        let f = forms::family("comparison").unwrap();
        assert_eq!(p.model, json::quote("claude-\"quoted\"-model").into_bytes());
        assert_eq!(p.system, forms::system(f));
        assert_eq!(p.tools, forms::tools(f).bytes());
        assert!(p.extra.is_empty());
        assert_eq!(p.anthropic_version, forms::ANTHROPIC_VERSION);
        assert_eq!(p.max_tokens_per_request, 16_000);
        assert_eq!(p.texts.reminder, forms::REMINDER);
        assert_eq!(p.texts.near_limit, forms::NEAR_LIMIT);
        assert_eq!(p.texts.continuation, forms::CONTINUATION);
        assert_eq!(
            p.limits,
            Limits {
                turns: 200,
                input_tokens: 20_000_000,
                output_tokens: 400_000
            }
        );
        assert_eq!(p.near_limit_percent, 20);
        assert_eq!(p.retry, RetryPolicy::default());
        assert_eq!(p.request_timeout_seconds, 600);
        // Every spliced member occurs verbatim in the record.
        let hay = String::from_utf8(rec).unwrap();
        for m in [&p.model, &p.system, &p.tools] {
            assert!(hay.contains(std::str::from_utf8(m).unwrap()));
        }
    }

    fn replace_body_member(rec: &[u8], key: &str, value: J) -> Vec<u8> {
        let r = decode_record(rec).unwrap();
        let J::Obj(mut members) = r.body_j() else {
            unreachable!()
        };
        match members.iter_mut().find(|(k, _)| k == key) {
            Some(slot) => slot.1 = value,
            None => members.push((key.to_string(), value)),
        }
        record_bytes(
            "arrangement",
            Some("aqm3x7kd2hz5vw4ny"),
            &"c".repeat(64),
            J::Obj(members),
        )
    }

    trait BodyJ {
        fn body_j(&self) -> J;
    }
    impl BodyJ for crate::archive::Record {
        fn body_j(&self) -> J {
            self.json.obj("").unwrap().get("body").unwrap().to_j()
        }
    }

    #[test]
    fn arrangement_refusals() {
        let rec = arrangement_record(&settings("open-inquiry", "m"));
        let refuse = |bytes: Vec<u8>, why: &str| {
            let e = Pinned::from_arrangement(&bytes).unwrap_err();
            assert!(e.contains(why), "{why}: {e}");
        };
        refuse(
            replace_body_member(
                &rec,
                "request_extra",
                J::Raw(br#"{"stream":true}"#.to_vec()),
            ),
            "does not allow",
        );
        refuse(
            replace_body_member(&rec, "surprise", J::Int(1)),
            "unknown key",
        );
        refuse(replace_body_member(&rec, "model", J::Int(1)), "/body/model");
        refuse(
            replace_body_member(&rec, "schema", "stewart.arrangement/9".into()),
            "schema",
        );
        refuse(
            replace_body_member(&rec, "max_tokens_per_request", J::Int(0)),
            "0",
        );
        refuse(
            replace_body_member(&rec, "anthropic_version", "2026 10 21".into()),
            "header value",
        );
        refuse(
            replace_body_member(
                &rec,
                "retry",
                J::obj()
                    .with("attempts", 4u64)
                    .with("delays_seconds", J::Arr(vec![J::Int(2)]))
                    .with("retry_after_ceiling_seconds", 60u64),
            ),
            "one delay per retry",
        );
        let other = record_bytes("receipt", None, &"c".repeat(64), J::obj());
        refuse(other, "not an arrangement");
        refuse(b"{}".to_vec(), "arrangement record");
    }

    /// An independent assembly of a body, by string formatting over the
    /// pieces, for comparing with the splicing writer.
    fn independent_body(
        model: &str,
        max: u64,
        system: &str,
        tools: &str,
        messages: &[String],
    ) -> String {
        format!(
            "{{\"model\":{model},\"max_tokens\":{max},\"system\":{system},\"tools\":{tools},\"messages\":[{}]}}",
            messages.join(",")
        )
    }

    #[test]
    fn splicing_is_byte_exact() {
        let p = pinned();
        // Captured response content with odd spacing, unknown blocks and a
        // signed thinking block: copied as is, never re-serialized.
        let content = r#"[ {"type":"thinking","thinking":"hmm","signature":"c2ln+/=="} ,{"type":"tool_use","id":"toolu_1","name":"read","input":{"source" : "materials/a.py"}},{"type":"mystery","x":1.50e3}]"#;
        let question =
            "Is the restart safe?\n\tLine two with \"quotes\" and a \\ and \u{1}\u{7f} é.";
        let mut conv = Conversation::new(first_user_message(question, Some(&p.texts.continuation)));
        let result_content = br#"[{"type":"text","text":"{\"schema\":\"stewart.reply/1\"}"}]"#;
        let results = [ToolResult {
            tool_use_id: "toolu_1",
            content: result_content,
            is_error: false,
        }];
        let notice =
            "Allowance notice: 1 turns, 2 input tokens and 3 output tokens remain for this audit.";
        conv.push(turn(
            content.as_bytes(),
            &user_message(&results, Some(&p.texts.reminder), Some(notice)),
        ));
        assert_eq!(conv.request(), 2);
        let got = conv.body(&p, 12_345);

        let first = format!(
            "{{\"role\":\"user\",\"content\":[{{\"type\":\"text\",\"text\":{}}},{{\"type\":\"text\",\"text\":{}}}]}}",
            "\"Is the restart safe?\\n\\tLine two with \\\"quotes\\\" and a \\\\ and \\u0001\u{7f} é.\"",
            json::quote(&p.texts.continuation),
        );
        let assistant = format!("{{\"role\":\"assistant\",\"content\":{content}}}");
        let user = format!(
            "{{\"role\":\"user\",\"content\":[{{\"type\":\"tool_result\",\"tool_use_id\":\"toolu_1\",\"content\":{},\"is_error\":false}},{{\"type\":\"text\",\"text\":{}}},{{\"type\":\"text\",\"text\":{}}}]}}",
            std::str::from_utf8(result_content).unwrap(),
            json::quote(&p.texts.reminder),
            json::quote(notice),
        );
        let want = independent_body(
            "\"claude-test-1\"",
            12_345,
            std::str::from_utf8(&p.system).unwrap(),
            std::str::from_utf8(&p.tools).unwrap(),
            &[first, assistant, user],
        );
        assert_eq!(String::from_utf8(got.clone()).unwrap(), want);
        // The assembled body is one JSON text.
        crate::provider::tolerant::validate(&got).unwrap();
    }

    #[test]
    fn messages_without_optional_parts() {
        assert_eq!(
            first_user_message("q", None),
            br#"{"role":"user","content":[{"type":"text","text":"q"}]}"#
        );
        assert_eq!(
            user_message(&[], Some("r"), None),
            br#"{"role":"user","content":[{"type":"text","text":"r"}]}"#
        );
        let two = [
            ToolResult {
                tool_use_id: "a\"b",
                content: b"[]",
                is_error: true,
            },
            ToolResult {
                tool_use_id: "c",
                content: b"[]",
                is_error: false,
            },
        ];
        assert_eq!(
            user_message(&two, None, None),
            br#"{"role":"user","content":[{"type":"tool_result","tool_use_id":"a\"b","content":[],"is_error":true},{"type":"tool_result","tool_use_id":"c","content":[],"is_error":false}]}"#
        );
        assert_eq!(
            assistant_message(b"[]"),
            br#"{"role":"assistant","content":[]}"#
        );
    }

    #[test]
    fn extra_members_follow_tools() {
        let mut p = pinned();
        p.extra = vec![br#""a":1"#.to_vec(), br#""b":{"c":[]}"#.to_vec()];
        let b = body(&p, 5, &[b"{}".to_vec()]);
        let s = String::from_utf8(b).unwrap();
        let tools = std::str::from_utf8(&p.tools).unwrap();
        assert!(s.ends_with(&format!(
            r#""tools":{tools},"a":1,"b":{{"c":[]}},"messages":[{{}}]}}"#
        )));
    }

    #[test]
    fn capture_layout_and_rebuild() {
        let p = pinned();
        let mut conv = Conversation::new(first_user_message("question", None));
        let b1 = conv.body(&p, 16_000);
        let c1 = request_capture(1, 16_000, &b1, conv.latest());
        let first = br#"{"role":"user","content":[{"type":"text","text":"question"}]}"#;
        assert_eq!(
            c1,
            [
                format!(
                    r#"{{"request":1,"max_tokens":16000,"body_bytes":{},"body_sha256":"{}","appended":["#,
                    b1.len(),
                    util::sha256_hex(&b1)
                )
                .as_bytes(),
                first,
                b"]}\n"
            ]
            .concat()
        );
        conv.push(turn(
            br#"[{"type":"text","text":"done"}]"#,
            &user_message(&[], Some("remind"), None),
        ));
        let b2 = conv.body(&p, 9_000);
        let c2 = request_capture(2, 9_000, &b2, conv.latest());

        let cap = parse_request_capture(&c2).unwrap();
        assert_eq!(
            (cap.request, cap.max_tokens, cap.body_bytes),
            (2, 9_000, b2.len() as u64)
        );
        assert_eq!(cap.body_sha256, util::sha256_hex(&b2));
        assert_eq!(cap.appended.of(&c2), conv.latest());
        assert_eq!(rebuild_body(&p, &[&c1, &c2]).unwrap(), b2);
        assert_eq!(rebuild_body(&p, &[&c1]).unwrap(), b1);

        // Order, numbering and completeness are checked.
        assert!(
            rebuild_body(&p, &[&c2])
                .unwrap_err()
                .contains("names request 2")
        );
        assert!(
            rebuild_body(&p, &[&c1, &c2[..c2.len() - 1]])
                .unwrap_err()
                .contains("cut off")
        );
        assert!(rebuild_body(&p, &[]).is_err());
        let mut other = p.clone();
        other.model = b"\"another\"".to_vec();
        assert!(
            rebuild_body(&other, &[&c1, &c2])
                .unwrap_err()
                .contains("does not match")
        );
    }

    #[test]
    fn capture_defects() {
        let p = pinned();
        let conv = Conversation::new(first_user_message("q", None));
        let b = conv.body(&p, 1);
        let c = request_capture(1, 1, &b, conv.latest());
        for n in [0, 1, 10, c.len() - 2, c.len() - 1] {
            assert_eq!(
                parse_request_capture(&c[..n]),
                Err(CaptureDefect::CutOff),
                "{n}"
            );
        }
        let malformed = |bytes: &[u8]| {
            assert!(
                matches!(
                    parse_request_capture(bytes),
                    Err(CaptureDefect::Malformed(_))
                ),
                "{}",
                String::from_utf8_lossy(bytes)
            )
        };
        malformed(b"{\"request\":01,\"max_tokens\":1,\"body_bytes\":1,\"body_sha256\":\"x\",\"appended\":[]}\n");
        malformed(b"{\"request\":1, \"max_tokens\":1}\n]}\n");
        malformed(format!("{{\"request\":1,\"max_tokens\":1,\"body_bytes\":1,\"body_sha256\":\"{}\",\"appended\":[]}}\n", "g".repeat(64)).as_bytes());
        malformed(format!("{{\"request\":1,\"max_tokens\":1,\"body_bytes\":1,\"body_sha256\":\"{}\",\"appended\":[\n]}}\n", "a".repeat(64)).as_bytes());
        malformed(b"]}\n");
    }
}
