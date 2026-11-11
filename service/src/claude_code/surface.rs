//! The launch surface: everything Stewart supplies to the harness that is the
//! same for every audit and is not bound by the profile's launch, tool or
//! model bindings. A profile's check names this surface's digest, so a rebuild
//! that leaves these values alone keeps its check and a changed value refuses
//! until the surface is checked again.
//!
//! This module is the only construction of those values. A launch calls the
//! builders below with its real paths and model; [`document`] calls the same
//! builders with the named slots. The digest therefore describes what a launch
//! actually supplies, and two builds at different paths agree on it.
//! The runtime contract pins the document's members, order and bytes.

use super::{arrangement, process, profile, wire};
use crate::json::{self, J};
use crate::{forms, util};

pub const SCHEMA: &str = "stewart.claude-code.surface/1";
/// Socket names relative to the private working directory.
pub const MCP_SOCKET: &str = "m";
pub const HOOK_SOCKET: &str = "h";
pub const TOOL_PREFIX: &str = "mcp__stewart__";
pub const HOOK_TIMEOUT_SECONDS: u64 = 5;
pub const HOOK_DENIAL: &str = "Tool is outside the validated active commission.";
/// Joins the orientation and the effective family text in the prompt file.
pub const SEPARATOR: &str = "\n\n";

/// The values that differ between launches. Everything else is fixed here.
pub struct Slots<'a> {
    pub workspace: &'a str,
    pub writer: &'a str,
    pub home: &'a str,
    pub temporary_directory: &'a str,
    pub config_directory: &'a str,
    pub model: &'a str,
}

/// The slots as the surface document spells them.
pub const NAMED: Slots<'static> = Slots {
    workspace: "{workspace}",
    writer: "{writer}",
    home: "{home}",
    temporary_directory: "{temporary_directory}",
    config_directory: "{config_directory}",
    model: "{model}",
};
pub const TOOL_SLOT: &str = "{tool}";
pub const EFFORT_SLOT: &str = "{effort}";
pub const ORIENTATION_SLOT: &str = "{orientation}";
pub const GUIDANCE_SLOT: &str = "{guidance}";
pub const TEXT_SLOT: &str = "{text}";

impl<'a> Slots<'a> {
    pub fn launch(profile: &'a profile::Profile, workspace: &'a str, writer: &'a str) -> Self {
        Self {
            workspace,
            writer,
            home: &profile.home,
            temporary_directory: &profile.temporary_directory,
            config_directory: &profile.config_directory,
            model: &profile.model,
        }
    }
}

/// The harness-assigned name of one pinned tool.
pub fn tool_name(base: &str) -> String {
    format!("{TOOL_PREFIX}{base}")
}

fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

pub fn auth_argv() -> Vec<String> {
    ["auth", "status"].map(String::from).to_vec()
}

/// The model invocation without the optional effort arguments. Each pinned
/// tool contributes one prefixed argument after `--allowedTools`.
pub fn model_argv<S: AsRef<str>>(s: &Slots, tools: &[S]) -> Vec<String> {
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
        format!("{}/settings.json", s.workspace),
        "--strict-mcp-config".into(),
        "--mcp-config".into(),
        format!("{}/mcp.json", s.workspace),
        "--allowedTools".into(),
    ]);
    args.extend(tools.iter().map(|n| tool_name(n.as_ref())));
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
        format!("{}/system.txt", s.workspace),
        "--model".into(),
        s.model.into(),
        "--max-turns".into(),
        profile::MAX_TURNS.to_string(),
        "--no-session-persistence".into(),
    ]);
    args
}

/// Appended to the model invocation when the question selects an effort.
pub fn effort_argv(effort: &str) -> Vec<String> {
    vec!["--effort".into(), effort.into()]
}

pub fn settings(s: &Slots) -> J {
    let command = format!(
        "{} {} {}",
        shell_quote(s.writer),
        process::HOOK,
        shell_quote(HOOK_SOCKET)
    );
    J::obj()
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
                                .with("command", command)
                                .with("timeout", HOOK_TIMEOUT_SECONDS),
                        ]),
                )]),
            ),
        )
}

pub fn mcp_config(s: &Slots) -> J {
    J::obj().with(
        "mcpServers",
        J::obj().with(
            "stewart",
            J::obj()
                .with("type", "stdio")
                .with("command", s.writer)
                .with("args", json::strs(&[process::RELAY, MCP_SOCKET])),
        ),
    )
}

/// The whole child environment, in the order the surface lists it. Nothing is
/// inherited from the caller.
pub fn environment(s: &Slots) -> Vec<(String, String)> {
    let output = profile::MAX_OUTPUT_TOKENS.to_string();
    [
        ("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        ("LANG", "en_US.UTF-8"),
        ("DISABLE_UPDATES", "1"),
        ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1"),
        ("CLAUDE_CODE_DISABLE_AUTO_MEMORY", "1"),
        ("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", "1"),
        ("CLAUDE_CODE_DISABLE_AGENT_VIEW", "1"),
        ("CLAUDE_CODE_DISABLE_FAST_MODE", "1"),
        ("ENABLE_CLAUDEAI_MCP_SERVERS", "false"),
        ("ENABLE_TOOL_SEARCH", "false"),
        ("CLAUDE_CODE_MAX_RETRIES", "0"),
        ("CLAUDE_CODE_MAX_OUTPUT_TOKENS", output.as_str()),
        ("HOME", s.home),
        ("TMPDIR", s.temporary_directory),
        ("CLAUDE_CONFIG_DIR", s.config_directory),
    ]
    .iter()
    .map(|(k, v)| (k.to_string(), v.to_string()))
    .collect()
}

pub fn environment_j(s: &Slots) -> J {
    J::Obj(
        environment(s)
            .into_iter()
            .map(|(k, v)| (k, J::from(v)))
            .collect(),
    )
}

/// The bytes of the system prompt file.
pub fn system_prompt(orientation: &str, guidance: &str) -> String {
    format!("{orientation}{SEPARATOR}{guidance}")
}

/// What the hook helper prints for an admitted or a denied tool.
pub fn hook_reply(allowed: bool) -> J {
    if allowed {
        return J::obj();
    }
    J::obj().with(
        "hookSpecificOutput",
        J::obj()
            .with("hookEventName", "PreToolUse")
            .with("permissionDecision", "deny")
            .with("permissionDecisionReason", HOOK_DENIAL),
    )
}

fn text_sha256(text: &str) -> String {
    util::sha256_hex(text.as_bytes())
}

/// The surface document. Its compact bytes are what the check binds.
pub fn document() -> J {
    let s = NAMED;
    J::obj()
        .with("schema", SCHEMA)
        .with("working_directory", s.workspace)
        .with("auth_argv", json::strs(&auth_argv()))
        .with("model_argv", json::strs(&model_argv(&s, &[TOOL_SLOT])))
        .with("effort_argv", json::strs(&effort_argv(EFFORT_SLOT)))
        .with("settings", settings(&s))
        .with("mcp_config", mcp_config(&s))
        .with("environment", environment_j(&s))
        .with(
            "controls",
            J::obj()
                .with("harness_max_turns", profile::MAX_TURNS)
                .with("harness_max_output_tokens", profile::MAX_OUTPUT_TOKENS),
        )
        .with(
            "system_prompt",
            system_prompt(ORIENTATION_SLOT, GUIDANCE_SLOT),
        )
        .with("input", wire::user_message(TEXT_SLOT))
        .with("mcp_initialize", wire::initialize_result())
        .with(
            "hook_replies",
            J::obj()
                .with("allow", hook_reply(true))
                .with("deny", hook_reply(false)),
        )
        .with(
            "texts",
            J::obj()
                .with("orientation", arrangement::ORIENTATION_ID)
                .with(
                    "orientation_sha256",
                    text_sha256(&arrangement::orientation()),
                )
                .with("reminder_sha256", text_sha256(forms::REMINDER))
                .with("near_limit_sha256", text_sha256(arrangement::NEAR_LIMIT))
                .with("continuation_sha256", text_sha256(forms::CONTINUATION))
                .with("compacted_sha256", text_sha256(arrangement::COMPACTED)),
        )
}

pub fn bytes() -> Vec<u8> {
    document().bytes()
}

pub fn sha256() -> String {
    util::sha256_hex(&bytes())
}

/// What a refusal reports so that a manager can learn this binary's surface
/// without any launch: the schema, the digest and the exact document.
pub fn report() -> J {
    J::obj().with(
        "surface",
        J::obj()
            .with("schema", SCHEMA)
            .with("sha256", sha256())
            .with("document", J::Raw(bytes())),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The worked example in the runtime contract, read from the repository
    /// as an independent witness: the fenced block that opens with this
    /// schema, its lines joined without their endings, and the first digest
    /// the contract states after it.
    fn contract_example() -> (String, String) {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../docs/claude-code/CONTRACT.md"
        );
        let doc = std::fs::read_to_string(path)
            .expect("docs/claude-code/CONTRACT.md is part of the repository");
        let opening = format!("```json\n{{\"schema\":\"{SCHEMA}\"");
        assert_eq!(doc.matches(&opening).count(), 1, "one worked example");
        let from = doc.find(&opening).unwrap() + "```json\n".len();
        let (block, after) = doc[from..].split_once("\n```\n").expect("a closed fence");
        let digest = after
            .split('`')
            .find(|part| part.len() == 64 && part.bytes().all(|b| b.is_ascii_hexdigit()))
            .expect("the contract states the example's digest");
        (block.split('\n').collect(), digest.to_string())
    }

    #[test]
    fn the_contract_example_is_this_surface_byte_for_byte() {
        let (example, digest) = contract_example();
        assert_eq!(String::from_utf8(bytes()).unwrap(), example);
        assert_eq!(sha256(), digest);
        assert_eq!(util::sha256_hex(example.as_bytes()), digest);
        // The document is strict control JSON, so an arrangement can pin it.
        let parsed = json::parse(&bytes()).unwrap();
        assert_eq!(parsed.obj("").unwrap().str("schema").unwrap(), SCHEMA);
    }

    fn launch_bytes(s: &Slots, tools: &[&str], effort: &str) -> Vec<Vec<u8>> {
        vec![
            json::strs(&model_argv(s, tools)).bytes(),
            json::strs(&effort_argv(effort)).bytes(),
            settings(s).bytes(),
            mcp_config(s).bytes(),
            environment_j(s).bytes(),
        ]
    }

    /// Invariance: a launch differs from the surface only where a slot is
    /// named, so two installations at different paths share one surface.
    #[test]
    fn launch_values_fill_exactly_the_named_slots() {
        let named = launch_bytes(&NAMED, &[TOOL_SLOT], EFFORT_SLOT);
        for (workspace, writer, home, tmp, config, model, tool, effort) in [
            (
                "/t/w1",
                "/opt/a/stewart",
                "/h1",
                "/t",
                "/c1",
                "model-one",
                "list",
                "low",
            ),
            (
                "/var/x/w2",
                "/usr/local/bin/stewart",
                "/h2",
                "/var/x",
                "/c2",
                "model-two",
                "submit",
                "high",
            ),
        ] {
            let real = Slots {
                workspace,
                writer,
                home,
                temporary_directory: tmp,
                config_directory: config,
                model,
            };
            let filled: Vec<Vec<u8>> = named
                .iter()
                .map(|b| {
                    String::from_utf8(b.clone())
                        .unwrap()
                        .replace(NAMED.workspace, workspace)
                        .replace(NAMED.writer, writer)
                        .replace(NAMED.home, home)
                        .replace(NAMED.temporary_directory, tmp)
                        .replace(NAMED.config_directory, config)
                        .replace(NAMED.model, model)
                        .replace(TOOL_SLOT, tool)
                        .replace(EFFORT_SLOT, effort)
                        .into_bytes()
                })
                .collect();
            assert_eq!(launch_bytes(&real, &[tool], effort), filled);
        }
        // One argument per pinned tool, in the pinned order.
        let argv = model_argv(&NAMED, &["list", "read"]);
        let at = argv.iter().position(|a| a == "--allowedTools").unwrap();
        assert_eq!(
            argv[at + 1..at + 4],
            [
                "mcp__stewart__list",
                "mcp__stewart__read",
                "--permission-mode"
            ]
        );
        // The writer path is single-quoted for the hook's shell.
        let quoted = settings(&Slots {
            writer: "/o'dd/stewart",
            ..NAMED
        })
        .string();
        assert!(quoted.contains(r#""command":"'/o'\\''dd/stewart' __stewart-cc-hook 'h'""#));
    }

    /// Firing control: each supplied value is inside the digest. Changing one
    /// literal of the document changes it, and the texts are bound by digest.
    #[test]
    fn a_changed_surface_value_changes_the_digest() {
        let original = String::from_utf8(bytes()).unwrap();
        for (from, to) in [
            (
                r#""CLAUDE_CODE_MAX_RETRIES":"0""#,
                r#""CLAUDE_CODE_MAX_RETRIES":"1""#,
            ),
            (r#""fastMode":false"#, r#""fastMode":true"#),
            (r#""timeout":5"#, r#""timeout":6"#),
            (r#""--max-turns","200""#, r#""--max-turns","201""#),
            (
                r#""protocolVersion":"2025-11-25""#,
                r#""protocolVersion":"2025-06-18""#,
            ),
            (r#""session_id":"""#, r#""session_id":"x""#),
        ] {
            assert_eq!(original.matches(from).count(), 1, "{from}");
            let changed = original.replace(from, to);
            assert_ne!(util::sha256_hex(changed.as_bytes()), sha256(), "{from}");
        }
        for (key, text) in [
            ("orientation_sha256", arrangement::orientation()),
            ("reminder_sha256", forms::REMINDER.to_string()),
            ("near_limit_sha256", arrangement::NEAR_LIMIT.to_string()),
            ("continuation_sha256", forms::CONTINUATION.to_string()),
            ("compacted_sha256", arrangement::COMPACTED.to_string()),
        ] {
            let member = format!(r#""{key}":"{}""#, text_sha256(&text));
            assert_eq!(original.matches(&member).count(), 1, "{key}");
            assert_ne!(text_sha256(&format!("{text} ")), text_sha256(&text));
        }
    }

    #[test]
    fn the_refusal_report_carries_the_exact_document() {
        let report = report().bytes();
        let parsed = json::parse(&report).unwrap();
        let surface = parsed.obj("").unwrap().obj("surface").unwrap();
        surface.exactly(&["schema", "sha256", "document"]).unwrap();
        let span = surface.req("document").unwrap();
        assert_eq!(report[span.start..span.end], bytes()[..]);
        assert_eq!(
            surface.sha256("sha256").unwrap(),
            util::sha256_hex(&report[span.start..span.end])
        );
    }
}
