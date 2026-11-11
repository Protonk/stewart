//! Validate the observed runtime boundary without parsing opaque provider cost
//! metadata as Stewart control JSON.
use super::{accounting::Summary, arrangement::Harness, wire::Value};
use std::collections::BTreeSet;

pub enum Event {
    Init,
    Compacted,
    Result { error: bool },
    Other,
}
pub struct Observed {
    pub initialized: bool,
    pub usage: Summary,
    session: Option<String>,
}
impl Default for Observed {
    fn default() -> Self {
        Self {
            initialized: false,
            usage: Summary::reserved(),
            session: None,
        }
    }
}
impl Observed {
    pub fn receive(&mut self, raw: &[u8], h: &Harness, names: &[String]) -> Result<Event, String> {
        let v = Value::parse(raw)?;
        if v.field("parent_tool_use_id")?.is_some_and(|p| !p.null()) {
            return Err("delegated session is outside this commission".into());
        }
        if let Some(session) = v.field("session_id")? {
            let session = session.string()?;
            if !session.is_empty() {
                if self.session.as_ref().is_some_and(|s| *s != session) {
                    return Err("harness session changed within one placement".into());
                }
                self.session = Some(session);
            }
        }
        let kind = v.text("type")?;
        let expected: BTreeSet<String> =
            names.iter().map(|n| super::surface::tool_name(n)).collect();
        if kind == "system" {
            match v.text("subtype")?.as_str() {
                "init" => {
                    if self.initialized {
                        return Err("repeated startup event".into());
                    }
                    if v.text("apiKeySource")? != "none"
                        || v.text("claude_code_version")? != h.profile.version
                        || v.text("model")? != h.profile.model
                        || v.text("permissionMode")? != "dontAsk"
                    {
                        return Err(
                            "startup version, model, credential source or permission mode differs"
                                .into(),
                        );
                    }
                    let tools = v
                        .req("tools")?
                        .array()?
                        .into_iter()
                        .map(|t| t.string())
                        .collect::<Result<Vec<_>, _>>()?;
                    if tools.len() != expected.len()
                        || tools.into_iter().collect::<BTreeSet<_>>() != expected
                    {
                        return Err("startup tool inventory differs".into());
                    }
                    let servers = v.req("mcp_servers")?.array()?;
                    if servers.len() != 1
                        || servers[0].text("name")? != "stewart"
                        || servers[0].text("status")? != "connected"
                    {
                        return Err("startup MCP server inventory differs".into());
                    }
                    let plugins = v.req("plugins")?.array()?;
                    let mut found = BTreeSet::new();
                    for p in &plugins {
                        let n = p.text("name")?;
                        if p.text("path")? != "builtin"
                            || p.text("source")? != format!("{n}@builtin")
                        {
                            return Err("startup plugin source differs".into());
                        }
                        found.insert(n);
                    }
                    let wanted = [
                        "cc-plugin-agents-md",
                        "cc-plugin-privacy",
                        "cc-plugin-plugin-authoring",
                    ]
                    .map(String::from)
                    .into_iter()
                    .collect::<BTreeSet<_>>();
                    if plugins.len() != 3 || found != wanted {
                        return Err("startup plugin inventory differs".into());
                    }
                    for key in ["plugin_errors", "mcp_server_errors"] {
                        if !v
                            .field(key)?
                            .map(|e| e.empty())
                            .transpose()?
                            .unwrap_or(true)
                        {
                            return Err(format!("startup reported {key}"));
                        }
                    }
                    self.initialized = true;
                    return Ok(Event::Init);
                }
                "compact_boundary" => {
                    if !self.initialized {
                        return Err("compaction before startup validation".into());
                    }
                    self.usage.unknown_intervals = 1;
                    return Ok(Event::Compacted);
                }
                "api_retry" | "plugin_install" | "task_started" | "background_tasks_changed" => {
                    return Err(
                        "harness reported uncommissioned retry, installation or background work"
                            .into(),
                    );
                }
                _ => (),
            }
        }
        if kind == "rate_limit_event" {
            let info = v.req("rate_limit_info")?;
            if info
                .field("status")?
                .map(|s| s.string())
                .transpose()?
                .as_deref()
                == Some("rejected")
            {
                return Err("subscription quota rejected this placement".into());
            }
            for key in ["overageEnabled", "isUsingOverage"] {
                if info
                    .field(key)?
                    .map(|v| v.boolean())
                    .transpose()?
                    .unwrap_or(false)
                {
                    return Err("paid extra usage was reported enabled or in use".into());
                }
            }
        }
        if kind == "assistant" {
            if !self.initialized {
                return Err("assistant output arrived before startup validation".into());
            }
            self.usage.unknown_intervals = 1;
            let m = v.req("message")?;
            let model = m.text("model")?;
            if model != h.profile.model && model != "<synthetic>" {
                return Err("assistant model differs from commission".into());
            }
            for block in m.req("content")?.array()? {
                if block.text("type")? == "tool_use" && !expected.contains(&block.text("name")?) {
                    return Err("assistant attempted a tool outside the commission".into());
                }
            }
        }
        if kind == "result" {
            if !self.initialized {
                return Err("result before startup validation".into());
            }
            let error = v.req("is_error")?.boolean()?;
            self.usage.unknown_intervals = 1;
            let checkpoint = (|| {
                let u = v.req("usage")?;
                Ok::<_, String>([
                    u.req("input_tokens")?.number()?,
                    u.req("cache_creation_input_tokens")?.number()?,
                    u.req("cache_read_input_tokens")?.number()?,
                    u.req("output_tokens")?.number()?,
                    v.req("num_turns")?.number()?,
                ])
            })();
            if let Ok(next) = checkpoint {
                let old = [
                    self.usage.input,
                    self.usage.cache_creation,
                    self.usage.cache_read,
                    self.usage.output,
                    self.usage.turns,
                ];
                if next.iter().zip(old).all(|(n, o)| *n >= o) {
                    [
                        self.usage.input,
                        self.usage.cache_creation,
                        self.usage.cache_read,
                        self.usage.output,
                        self.usage.turns,
                    ] = next;
                    self.usage.reported_placements = 1;
                    if !error {
                        self.usage.unknown_intervals = 0;
                    }
                }
            }
            return Ok(Event::Result { error });
        }
        Ok(Event::Other)
    }
}

#[cfg(test)]
mod tests {
    use super::super::profile::{Limits, Profile, Selection};
    use super::*;
    use crate::json::J;
    fn harness() -> Harness {
        Harness {
            selection: Selection {
                path: "/profile".into(),
                profile: None,
                limits: Limits {
                    max_placements: 3,
                    placement_timeout_seconds: 60,
                },
            },
            profile: Profile {
                executable: "/fake".into(),
                sha256: "0".repeat(64),
                version: "2.1.322".into(),
                platform: "test".into(),
                config_directory: "/config".into(),
                home: "/home".into(),
                temporary_directory: "/tmp".into(),
                surface_sha256: "0".repeat(64),
                tools_sha256: "0".repeat(64),
                model: "fixture-model".into(),
                checked_at: "test".into(),
            },
            profile_sha256: "0".repeat(64),
            surface_sha256: "0".repeat(64),
            system_prompt: String::new(),
            mcp_tools: b"[]".to_vec(),
            effort: None,
        }
    }
    fn init() -> J {
        J::obj()
            .with("type", "system")
            .with("subtype", "init")
            .with("session_id", "session-one")
            .with("apiKeySource", "none")
            .with("claude_code_version", "2.1.322")
            .with("model", "fixture-model")
            .with("permissionMode", "dontAsk")
            .with(
                "tools",
                J::Arr(vec![J::from("mcp__stewart__record_account")]),
            )
            .with(
                "mcp_servers",
                J::Arr(vec![
                    J::obj().with("name", "stewart").with("status", "connected"),
                ]),
            )
            .with(
                "plugins",
                J::Arr(
                    [
                        "cc-plugin-agents-md",
                        "cc-plugin-privacy",
                        "cc-plugin-plugin-authoring",
                    ]
                    .iter()
                    .map(|n| {
                        J::obj()
                            .with("name", *n)
                            .with("path", "builtin")
                            .with("source", format!("{n}@builtin"))
                    })
                    .collect(),
                ),
            )
    }
    fn replace(mut value: J, key: &str, new: J) -> J {
        if let J::Obj(ref mut fields) = value {
            fields.retain(|(k, _)| k != key);
            fields.push((key.into(), new));
        }
        value
    }
    fn report(n: u64, error: bool) -> Vec<u8> {
        J::obj()
            .with("type", "result")
            .with("session_id", "session-one")
            .with("is_error", error)
            .with("num_turns", n)
            .with(
                "usage",
                J::obj()
                    .with("input_tokens", n)
                    .with("cache_creation_input_tokens", n)
                    .with("cache_read_input_tokens", n)
                    .with("output_tokens", n),
            )
            .with(
                "modelUsage",
                J::obj().with("fixture-model", J::obj().with("inputTokens", 999999u64)),
            )
            .with("total_cost_usd", J::Raw(b"0.0001".to_vec()))
            .bytes()
    }
    fn receive(o: &mut Observed, raw: &[u8]) -> Result<Event, String> {
        o.receive(raw, &harness(), &["record_account".into()])
    }
    #[test]
    fn init_comparison_and_fresh_invariance() {
        assert!(matches!(
            receive(&mut Observed::default(), &init().bytes()),
            Ok(Event::Init)
        ));
        for (key, value) in [
            ("model", J::from("other")),
            ("apiKeySource", J::from("api_key")),
            ("tools", J::Arr(vec![])),
            ("plugins", J::Arr(vec![])),
            ("permissionMode", J::from("bypassPermissions")),
            ("claude_code_version", J::from("changed")),
        ] {
            let mut o = Observed::default();
            assert!(
                receive(&mut o, &replace(init(), key, value).bytes()).is_err(),
                "{key}"
            );
            assert!(!o.initialized);
        }
        assert!(receive(&mut Observed::default(), &init().bytes()).is_ok());
    }
    #[test]
    fn cumulative_checkpoints_do_not_double_count_or_erase_prior_reports() {
        let mut o = Observed::default();
        receive(&mut o, &init().bytes()).unwrap();
        receive(&mut o, &report(12, false)).unwrap();
        assert_eq!(
            (
                o.usage.input,
                o.usage.output,
                o.usage.reported_placements,
                o.usage.unknown_intervals
            ),
            (12, 12, 1, 0)
        );
        receive(&mut o, &report(12, false)).unwrap();
        assert_eq!(o.usage.input, 12);
        receive(&mut o, &report(0, true)).unwrap();
        assert_eq!((o.usage.input, o.usage.unknown_intervals), (12, 1));
        receive(&mut o, &report(20, false)).unwrap();
        assert_eq!((o.usage.input, o.usage.unknown_intervals), (20, 0));
        receive(
            &mut o,
            br#"{"type":"result","is_error":false,"usage":{"input_tokens":-1.5}}"#,
        )
        .unwrap();
        assert_eq!((o.usage.input, o.usage.unknown_intervals), (20, 1));
    }
    #[test]
    fn paid_extra_usage_and_quota_are_stop_events() {
        for info in [
            r#"{"status":"rejected"}"#,
            r#"{"overageEnabled":true}"#,
            r#"{"isUsingOverage":true}"#,
        ] {
            assert!(
                receive(
                    &mut Observed::default(),
                    format!(r#"{{"type":"rate_limit_event","rate_limit_info":{info}}}"#).as_bytes()
                )
                .is_err()
            );
        }
        assert!(receive(&mut Observed::default(), br#"{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","overageEnabled":false,"isUsingOverage":false}}"#).is_ok());
    }
    #[test]
    fn compaction_preserves_session_and_prior_usage() {
        let mut o = Observed::default();
        receive(&mut o, &init().bytes()).unwrap();
        receive(&mut o, &report(12, false)).unwrap();
        assert!(matches!(receive(&mut o, br#"{"type":"system","subtype":"compact_boundary","session_id":"session-one","metadata":{"fraction":-2.5}}"#), Ok(Event::Compacted)));
        assert_eq!((o.usage.input, o.usage.unknown_intervals), (12, 1));
        assert!(
            receive(
                &mut o,
                br#"{"type":"system","subtype":"compact_boundary","session_id":"different"}"#
            )
            .is_err()
        );
    }
}
