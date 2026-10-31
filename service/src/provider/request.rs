//! The pinned arrangement and the messages of a placement (INTERFACE 4.5,
//! 6.2).
//!
//! The body of request `k` of a placement is spliced by
//! `runs::request_body` from the arrangement's exact bytes for `model`,
//! `system`, `tools` and `request_extra`, the request's `max_tokens`, and
//! what requests 1 to `k` appended. This module decodes the arrangement once,
//! keeping those exact bytes, and builds the appended messages. Nothing is
//! re-serialized from a parsed structure: captured response content is copied
//! as bytes, and Stewart's own strings (the question, notices, tool use IDs)
//! are written with the pinned escaping of `stewart.answer/1`.
//!
//! Request 1 appends the first user message. Each later request appends the
//! assistant message of the previous response and the user message that
//! answers it.

use std::time::Duration;

use crate::forms::{self, ARRANGEMENT_SCHEMA, Family};
use crate::json::{self, JsonError, value_err};
use crate::provider::policy::RetryPolicy;
use crate::runs;
use crate::usage::Limits;

/// A pinned arrangement read back from `prep/<n>/arrangement.json` (6.2):
/// what the run splices into requests, as exact bytes, and what the tools
/// and the seal need. The run loads it through the `accepted` record, the
/// receipt and the receipt's `arrangement` member, checking each digest.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pinned {
    /// The family ID and version, `open-inquiry/1`.
    pub family: String,
    pub model: String,
    /// The exact bytes of the `model` value (a JSON string).
    pub model_raw: Vec<u8>,
    pub anthropic_version: String,
    pub max_tokens_per_request: u64,
    /// The exact bytes of the `system` array.
    pub system_raw: Vec<u8>,
    /// The exact bytes of the `tools` array.
    pub tools_raw: Vec<u8>,
    /// The tool names, in `tools` order.
    pub tool_names: Vec<String>,
    /// Each member of `request_extra` as its raw `"key":value` bytes: none,
    /// or the manager's effort as `output_config` (see `admitted_extra`).
    pub request_extra: Vec<Vec<u8>>,
    pub reminder: String,
    /// The near-limit template, with `{turns}`, `{input_tokens}` and
    /// `{output_tokens}` to fill.
    pub near_limit: String,
    pub continuation: String,
    pub limits: Limits,
    pub near_limit_percent: u64,
    pub retry_attempts: u64,
    pub retry_delays_seconds: Vec<u64>,
    pub retry_after_ceiling_seconds: u64,
    pub request_timeout_seconds: u64,
    pub reader: String,
    pub renderer: String,
    pub question_body_sha256: String,
    pub material_index_sha256: String,
}

/// The members of a `request_extra` object this release admits (6.2), or
/// `None` when it admits none of it. The allowlist is exact bytes: `{}`, or
/// `{"output_config":{"effort":"<level>"}}` for a level of 3.2, as the
/// arrangement writes it. Effort adds nothing the model reads; no provider
/// feature may put model-visible content outside the arrangement.
pub fn admitted_extra(raw: &[u8]) -> Option<Vec<Vec<u8>>> {
    if raw == b"{}" {
        return Some(Vec::new());
    }
    crate::frontmatter::EFFORT_LEVELS
        .iter()
        .any(|level| raw == forms::request_extra(Some(level)).as_slice())
        .then(|| vec![raw[1..raw.len() - 1].to_vec()])
}

impl Pinned {
    /// The family this arrangement pins, if this release knows it.
    pub fn family(&self) -> Option<&'static Family> {
        let (id, version) = self.family.split_once('/')?;
        forms::family(id).filter(|f| f.version.to_string() == version)
    }

    /// The pinned retry policy (6.6).
    pub fn retry_policy(&self) -> RetryPolicy {
        RetryPolicy {
            attempts: self.retry_attempts as u32,
            delays_ms: self.retry_delays_seconds.iter().map(|s| s * 1000).collect(),
            retry_after_ceiling_seconds: self.retry_after_ceiling_seconds,
        }
    }

    /// The pinned request timeout.
    pub fn request_timeout(&self) -> Duration {
        Duration::from_secs(self.request_timeout_seconds)
    }
}

/// Decode an arrangement record strictly (1.2), keeping the pinned members'
/// bytes. `bytes` are the record's exact bytes, which the caller has checked
/// against the digest the receipt binds.
pub fn decode_arrangement(bytes: &[u8]) -> Result<Pinned, String> {
    let r = crate::archive::decode_record(bytes)?;
    if r.kind != "arrangement" {
        return Err(format!("the arrangement has kind {:?}", r.kind));
    }
    let b = r.body();
    let raw = |k: &str| -> Result<Vec<u8>, JsonError> {
        let v = b.req(k)?;
        Ok(bytes[v.start..v.end].to_vec())
    };
    let res = (|| {
        b.exactly(&[
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
        ])?;
        if b.str("schema")? != ARRANGEMENT_SCHEMA {
            return Err(b.invalid("schema", format!("expected {ARRANGEMENT_SCHEMA}")));
        }
        let mut tool_names = Vec::new();
        for (i, t) in b.arr("tools")?.iter().enumerate() {
            tool_names.push(t.obj(&format!("/body/tools/{i}"))?.str("name")?.to_string());
        }
        b.arr("system")?;
        let extra = b.obj("request_extra")?;
        let request_extra = admitted_extra(&raw("request_extra")?).ok_or_else(|| {
            value_err(
                &extra.pointer,
                extra.at,
                "this release's request_extra allowlist admits only {} or the effort as {\"output_config\":{\"effort\":<level>}}",
            )
        })?;
        let anthropic_version = b.str("anthropic_version")?;
        if anthropic_version.is_empty()
            || !anthropic_version
                .bytes()
                .all(|c| (0x21..=0x7E).contains(&c))
        {
            return Err(b.invalid("anthropic_version", "expected a header value"));
        }
        let max_tokens_per_request = b.u64("max_tokens_per_request", u32::MAX as u64)?;
        if max_tokens_per_request == 0 {
            return Err(b.invalid("max_tokens_per_request", "expected at least 1"));
        }
        let t = b.obj("texts")?;
        t.exactly(&["reminder", "near_limit", "continuation"])?;
        let l = b.obj("limits")?;
        l.exactly(&["turns", "input_tokens", "output_tokens"])?;
        let limits = Limits {
            turns: l.u64("turns", crate::frontmatter::MAX_TURNS)?,
            input_tokens: l.u64("input_tokens", crate::frontmatter::MAX_INPUT_TOKENS)?,
            output_tokens: l.u64("output_tokens", crate::frontmatter::MAX_OUTPUT_TOKENS)?,
        };
        // Bounds that keep the run's arithmetic and waits finite; the release
        // pins 4 attempts, 2, 8 and 30 s, 60 s and 600 s.
        let retry = b.obj("retry")?;
        retry.exactly(&["attempts", "delays_seconds", "retry_after_ceiling_seconds"])?;
        let attempts = retry.u64("attempts", 16)?;
        let delays = retry
            .arr("delays_seconds")?
            .iter()
            .map(|d| {
                d.as_u64().filter(|s| *s <= 86_400).ok_or_else(|| {
                    value_err(
                        "/body/retry/delays_seconds",
                        d.start,
                        "expected whole seconds up to 86400",
                    )
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        if attempts == 0 || delays.len() as u64 != attempts - 1 {
            return Err(retry.invalid(
                "delays_seconds",
                "expected one delay before each attempt after the first",
            ));
        }
        let timeout = b.u64("request_timeout_seconds", 86_400)?;
        if timeout == 0 {
            return Err(b.invalid("request_timeout_seconds", "expected at least 1"));
        }
        let bind = b.obj("bindings")?;
        bind.exactly(&["question_body_sha256", "material_index_sha256"])?;
        Ok::<_, JsonError>(Pinned {
            family: b.str("family")?.to_string(),
            model: b.str("model")?.to_string(),
            model_raw: raw("model")?,
            anthropic_version: anthropic_version.to_string(),
            max_tokens_per_request,
            system_raw: raw("system")?,
            tools_raw: raw("tools")?,
            tool_names,
            request_extra,
            reminder: t.str("reminder")?.to_string(),
            near_limit: t.str("near_limit")?.to_string(),
            continuation: t.str("continuation")?.to_string(),
            limits,
            near_limit_percent: b.u64("near_limit_percent", 100)?,
            retry_attempts: attempts,
            retry_delays_seconds: delays,
            retry_after_ceiling_seconds: retry.u64("retry_after_ceiling_seconds", 86_400)?,
            request_timeout_seconds: timeout,
            reader: b.str("reader")?.to_string(),
            renderer: b.str("renderer")?.to_string(),
            question_body_sha256: bind.sha256("question_body_sha256")?.to_string(),
            material_index_sha256: bind.sha256("material_index_sha256")?.to_string(),
        })
    })();
    res.map_err(|e| e.to_string())
}

/// The pinned bytes a request body splices: the arrangement's, unless a
/// test build's sabotage control alters what is sent (never what is pinned).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Parts {
    pub model: Vec<u8>,
    pub system: Vec<u8>,
    pub tools: Vec<u8>,
    pub extra: Vec<Vec<u8>>,
}

impl Parts {
    pub fn of(p: &Pinned) -> Parts {
        Parts {
            model: p.model_raw.clone(),
            system: p.system_raw.clone(),
            tools: p.tools_raw.clone(),
            extra: p.request_extra.clone(),
        }
    }

    /// The body of a request with `max_tokens`, appending `appended` (what
    /// requests 1…k appended, in order).
    pub fn body<A: AsRef<[u8]>>(&self, max_tokens: u64, appended: &[A]) -> Vec<u8> {
        let extra: Vec<&[u8]> = self.extra.iter().map(Vec::as_slice).collect();
        let messages: Vec<&[u8]> = appended.iter().map(AsRef::as_ref).collect();
        runs::request_body(
            &self.model,
            max_tokens,
            &self.system,
            &self.tools,
            &extra,
            &messages,
        )
    }
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

/// The user message answering a response: one `tool_result` block per
/// `tool_use` block, in order (`runs::tool_result_block`), then the reminder
/// when it is sent, then the near-limit notice when it is pending.
pub fn user_message(results: &[Vec<u8>], reminder: Option<&str>, notice: Option<&str>) -> Vec<u8> {
    let mut blocks: Vec<Vec<u8>> = results.to_vec();
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
    pub fn body(&self, parts: &Parts, max_tokens: u64) -> Vec<u8> {
        parts.body(max_tokens, &self.appended)
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::archive::{decode_record, record_bytes};
    use crate::forms::{ArrangementInput, arrangement};
    use crate::frontmatter::Settings;
    use crate::json::J;
    use crate::util;

    pub fn settings(family: &str, model: &str) -> Settings {
        Settings {
            family: family.into(),
            model: model.into(),
            effort: None,
            destination: "/tmp/returns".into(),
            turns: 200,
            input_tokens: 20_000_000,
            output_tokens: 400_000,
            inquiry: None,
            varies: None,
        }
    }

    pub fn arrangement_record(s: &Settings) -> Vec<u8> {
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

    pub fn pinned() -> Pinned {
        decode_arrangement(&arrangement_record(&settings(
            "open-inquiry",
            "claude-test-1",
        )))
        .unwrap()
    }

    #[test]
    fn pinned_members_are_the_arrangement_bytes() {
        let s = settings("comparison", "claude-\"quoted\"-model");
        let rec = arrangement_record(&s);
        let p = decode_arrangement(&rec).unwrap();
        let f = forms::family("comparison").unwrap();
        assert_eq!(p.family().map(|x| x.versioned_id()), Some(f.versioned_id()));
        assert_eq!(
            p.model_raw,
            json::quote("claude-\"quoted\"-model").into_bytes()
        );
        assert_eq!(p.system_raw, forms::system(f));
        assert_eq!(p.tools_raw, forms::tools(f).bytes());
        assert!(p.request_extra.is_empty());
        assert_eq!(p.anthropic_version, forms::ANTHROPIC_VERSION);
        assert_eq!(p.max_tokens_per_request, 16_000);
        assert_eq!(p.reminder, forms::REMINDER);
        assert_eq!(p.near_limit, forms::NEAR_LIMIT);
        assert_eq!(p.continuation, forms::CONTINUATION);
        assert_eq!(
            p.limits,
            Limits {
                turns: 200,
                input_tokens: 20_000_000,
                output_tokens: 400_000
            }
        );
        assert_eq!(p.near_limit_percent, 20);
        assert_eq!(p.retry_policy(), RetryPolicy::default());
        assert_eq!(p.request_timeout(), Duration::from_secs(600));
        assert_eq!(p.question_body_sha256, "a".repeat(64));
        // Every spliced member occurs verbatim in the record.
        let hay = String::from_utf8(rec).unwrap();
        for m in [&p.model_raw, &p.system_raw, &p.tools_raw] {
            assert!(hay.contains(std::str::from_utf8(m).unwrap()));
        }
    }

    #[test]
    fn the_effort_is_one_pinned_top_level_member() {
        let plain = settings("open-inquiry", "claude-opus-5-5");
        let mut with = plain.clone();
        with.effort = Some("xhigh".into());
        let p0 = decode_arrangement(&arrangement_record(&plain)).unwrap();
        let p1 = decode_arrangement(&arrangement_record(&with)).unwrap();
        assert!(p0.request_extra.is_empty());
        assert_eq!(
            p1.request_extra,
            [br#""output_config":{"effort":"xhigh"}"#.to_vec()]
        );
        // Everything the model reads is the same with and without the effort.
        assert_eq!(
            (&p0.system_raw, &p0.tools_raw, &p0.model_raw),
            (&p1.system_raw, &p1.tools_raw, &p1.model_raw)
        );
        let appended = [br#"{"role":"user","content":[{"type":"text","text":"Q"}]}"#.to_vec()];
        let b0 = Parts::of(&p0).body(16_000, &appended);
        let b1 = Parts::of(&p1).body(16_000, &appended);
        let tools_end = b"],\"messages\":[";
        let at = b0
            .windows(tools_end.len())
            .position(|w| w == tools_end)
            .unwrap()
            + 1;
        let mut expected = b0[..at].to_vec();
        expected.extend_from_slice(br#","output_config":{"effort":"xhigh"}"#);
        expected.extend_from_slice(&b0[at..]);
        assert_eq!(
            String::from_utf8(b1).unwrap(),
            String::from_utf8(expected).unwrap()
        );
        for level in crate::frontmatter::EFFORT_LEVELS {
            let raw = forms::request_extra(Some(level));
            assert_eq!(admitted_extra(&raw).map(|m| m.len()), Some(1), "{level}");
        }
        assert_eq!(admitted_extra(b"{}"), Some(Vec::new()));
    }

    fn replace_body_member(rec: &[u8], key: &str, value: J) -> Vec<u8> {
        let r = decode_record(rec).unwrap();
        let J::Obj(mut members) = r.json.obj("").unwrap().get("body").unwrap().to_j() else {
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

    #[test]
    fn arrangement_refusals() {
        let rec = arrangement_record(&settings("open-inquiry", "m"));
        let refuse = |bytes: Vec<u8>, why: &str| {
            let e = decode_arrangement(&bytes).unwrap_err();
            assert!(e.contains(why), "{why}: {e}");
        };
        for extra in [
            r#"{"stream":true}"#,
            r#"{"output_config":{"effort":"hgih"}}"#,
            r#"{"output_config":{"effort":"High"}}"#,
            r#"{"output_config":{"eefort":"high"}}"#,
            r#"{"output_config":{"effort":"high","task_budget":{"type":"tokens","total":20000}}}"#,
            r#"{"output_config":{"effort":"high"},"stream":true}"#,
            r#"{"output_config":{}}"#,
            r#"{"output_config": {"effort":"high"}}"#,
            r#"{"output_config":{"effort":"high" }}"#,
        ] {
            refuse(
                replace_body_member(&rec, "request_extra", J::Raw(extra.as_bytes().to_vec())),
                "allowlist admits only",
            );
        }
        refuse(replace_body_member(&rec, "surprise", J::Int(1)), "surprise");
        refuse(replace_body_member(&rec, "model", J::Int(1)), "/body/model");
        refuse(
            replace_body_member(&rec, "schema", "stewart.arrangement/9".into()),
            "schema",
        );
        refuse(
            replace_body_member(&rec, "max_tokens_per_request", J::Int(0)),
            "at least 1",
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
            "one delay before each attempt",
        );
        let other = record_bytes("receipt", None, &"c".repeat(64), J::obj());
        refuse(other, "kind");
        assert!(decode_arrangement(b"{}").is_err());
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
        let parts = Parts::of(&p);
        // Captured response content with odd spacing, unknown blocks and a
        // signed thinking block: copied as is, never re-serialized.
        let content = r#"[ {"type":"thinking","thinking":"hmm","signature":"c2ln+/=="} ,{"type":"tool_use","id":"toolu_1","name":"read","input":{"source" : "materials/a.py"}},{"type":"mystery","x":1.50e3}]"#;
        let question =
            "Is the restart safe?\n\tLine two with \"quotes\" and a \\ and \u{1}\u{7f} é.";
        let mut conv = Conversation::new(first_user_message(question, Some(&p.continuation)));
        let result_content = br#"[{"type":"text","text":"{\"schema\":\"stewart.reply/1\"}"}]"#;
        let results = vec![runs::tool_result_block("toolu_1", result_content, false)];
        let notice =
            "Allowance notice: 1 turns, 2 input tokens and 3 output tokens remain for this audit.";
        conv.push(turn(
            content.as_bytes(),
            &user_message(&results, Some(&p.reminder), Some(notice)),
        ));
        assert_eq!(conv.request(), 2);
        let got = conv.body(&parts, 12_345);

        let first = format!(
            "{{\"role\":\"user\",\"content\":[{{\"type\":\"text\",\"text\":{}}},{{\"type\":\"text\",\"text\":{}}}]}}",
            "\"Is the restart safe?\\n\\tLine two with \\\"quotes\\\" and a \\\\ and \\u0001\u{7f} é.\"",
            json::quote(&p.continuation),
        );
        let assistant = format!("{{\"role\":\"assistant\",\"content\":{content}}}");
        let user = format!(
            "{{\"role\":\"user\",\"content\":[{{\"type\":\"tool_result\",\"tool_use_id\":\"toolu_1\",\"content\":{},\"is_error\":false}},{{\"type\":\"text\",\"text\":{}}},{{\"type\":\"text\",\"text\":{}}}]}}",
            std::str::from_utf8(result_content).unwrap(),
            json::quote(&p.reminder),
            json::quote(notice),
        );
        let want = independent_body(
            "\"claude-test-1\"",
            12_345,
            std::str::from_utf8(&p.system_raw).unwrap(),
            std::str::from_utf8(&p.tools_raw).unwrap(),
            &[first, assistant, user],
        );
        assert_eq!(String::from_utf8(got.clone()).unwrap(), want);
        // The assembled body is one JSON text.
        crate::provider::tolerant::validate(&got).unwrap();
        // A capture of it rebuilds to exactly the body sent.
        let c1 = runs::request_capture(
            1,
            16_000,
            &parts.body(
                16_000,
                &[first_user_message(question, Some(&p.continuation))],
            ),
            &[&first_user_message(question, Some(&p.continuation))],
        );
        let c2 = runs::request_capture(2, 12_345, &got, &[conv.latest()]);
        let extra: Vec<&[u8]> = Vec::new();
        assert_eq!(
            runs::rebuild_body(
                &p.model_raw,
                &p.system_raw,
                &p.tools_raw,
                &extra,
                &[&c1, &c2]
            )
            .unwrap(),
            got
        );
        assert_eq!(util::sha256_hex(&got).len(), 64);
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
        let two = vec![
            runs::tool_result_block("a\"b", b"[]", true),
            runs::tool_result_block("c", b"[]", false),
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
}
