#![cfg(feature = "claude-code")]
mod answer_support;
mod common;
use answer_support::Live;
use std::time::{Duration, Instant};
use stewart::claude_code::gate::Gate;
use stewart::json;

#[test]
fn core_recording_obeys_stop_and_fresh_call_invariance() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() + Duration::from_secs(60));
    gate.within(|| live.call("record_account", r#"{"text":"firing control"}"#))
        .ok();
    let revision = live.state().revision();
    let stopped = gate.call();
    stopped.cancel();
    let reply = stopped.within(|| live.call("record_account", r#"{"text":"must not publish"}"#));
    assert_eq!(reply.outcome(), "refused", "{}", reply.text());
    assert_eq!(reply.reason(), "placement_stopped");
    assert_eq!(live.state().revision(), revision);
    gate.call()
        .within(|| live.call("record_account", r#"{"text":"fresh invariance"}"#))
        .ok();
    assert_eq!(live.state().revision(), revision + 1);
}

#[test]
fn expired_deadline_cannot_publish_a_core_record() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() - Duration::from_millis(1));
    let reply = gate.within(|| live.call("record_account", r#"{"text":"late"}"#));
    assert_eq!(reply.reason(), "placement_stopped");
    assert_eq!(live.state().revision(), 0);
}

#[test]
fn confirmed_submission_preserves_cancellation_stop_and_deadline_refusals() {
    for condition in ["cancel", "stop", "deadline"] {
        let mut live = Live::new();
        live.call("record_account", r#"{"text":"recorded before the stop"}"#)
            .ok();
        let prepared = live.call("prepare", "{}").str(&["prepared"]).to_string();
        let parent = Gate::new(Instant::now() + Duration::from_secs(60));
        let gate = match condition {
            "deadline" => Gate::new(Instant::now() - Duration::from_millis(1)),
            _ => parent.call(),
        };
        match condition {
            "cancel" => gate.cancel(),
            "stop" => gate.stop(),
            _ => (),
        }
        let input = format!(r#"{{"prepared":"{prepared}","confirm":true}}"#);
        let refusal = gate.within(|| live.call("submit", &input));
        assert_eq!(
            refusal.outcome(),
            "refused",
            "{condition}: {}",
            refusal.text()
        );
        assert_eq!(refusal.reason(), "placement_stopped");
        assert_eq!(refusal.effect("seal"), "none");
        assert_eq!(
            refusal.ex.end, None,
            "a refused publication is not a write failure"
        );
        assert!(live.state().seal().is_none());
        assert_eq!(live.state().revision(), 1);
        if condition == "cancel" {
            // A fresh sibling of the cancelled invocation can seal the same
            // exact preparation. This also proves the prepared input was valid.
            let accepted = parent.call().within(|| live.call("submit", &input));
            accepted.ok();
            assert_eq!(accepted.effect("seal"), "recorded");
            assert!(accepted.ex.sealed);
        } else {
            let accepted = Gate::new(Instant::now() + Duration::from_secs(60))
                .within(|| live.call("submit", &input));
            accepted.ok();
            assert!(accepted.ex.sealed);
        }
    }
}

/// The launch surface as the runtime contract's worked example gives it,
/// copied here so these cases do not ask the binary under test for its digest.
const SURFACE: &str = concat!(
    r#"{"schema":"stewart.claude-code.surface/1","#,
    r#""working_directory":"{workspace}","#,
    r#""auth_argv":["auth","status"],"#,
    r#""model_argv":["-p","--input-format","stream-json","--output-format","stream-json","#,
    r#""--verbose","--restricted","--tools","","--setting-sources","","--settings","#,
    r#""{workspace}/settings.json","--strict-mcp-config","--mcp-config","{workspace}/mcp.json","#,
    r#""--allowedTools","mcp__stewart__{tool}","--permission-mode","dontAsk","#,
    r#""--permission-prompts","none","--system-prompt-file","{workspace}/system.txt","--model","#,
    r#""{model}","--max-turns","200","--no-session-persistence"],"#,
    r#""effort_argv":["--effort","{effort}"],"#,
    r#""settings":{"forceLoginMethod":"claudeai","fastMode":false,"fallbackModel":[],"#,
    r#""hooks":{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","#,
    r#""command":"'{writer}' __stewart-cc-hook 'h'","timeout":5}]}]}},"#,
    r#""mcp_config":{"mcpServers":{"stewart":{"type":"stdio","command":"{writer}","#,
    r#""args":["__stewart-cc-relay","m"]}}},"#,
    r#""environment":{"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","LANG":"en_US.UTF-8","#,
    r#""DISABLE_UPDATES":"1","CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC":"1","#,
    r#""CLAUDE_CODE_DISABLE_AUTO_MEMORY":"1","CLAUDE_CODE_DISABLE_BACKGROUND_TASKS":"1","#,
    r#""CLAUDE_CODE_DISABLE_AGENT_VIEW":"1","CLAUDE_CODE_DISABLE_FAST_MODE":"1","#,
    r#""ENABLE_CLAUDEAI_MCP_SERVERS":"false","ENABLE_TOOL_SEARCH":"false","#,
    r#""CLAUDE_CODE_MAX_RETRIES":"0","CLAUDE_CODE_MAX_OUTPUT_TOKENS":"16000","HOME":"{home}","#,
    r#""TMPDIR":"{temporary_directory}","CLAUDE_CONFIG_DIR":"{config_directory}"},"#,
    r#""controls":{"harness_max_turns":200,"harness_max_output_tokens":16000},"#,
    r#""system_prompt":"{orientation}\n\n{guidance}","#,
    r#""input":{"type":"user","session_id":"","parent_tool_use_id":null,"#,
    r#""message":{"role":"user","content":"{text}"}},"#,
    r#""mcp_initialize":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"#,
    r#""serverInfo":{"name":"stewart","version":"1"}},"#,
    r#""hook_replies":{"allow":{},"deny":{"hookSpecificOutput":{"hookEventName":"PreToolUse","#,
    r#""permissionDecision":"deny","#,
    r#""permissionDecisionReason":"Tool is outside the validated active commission."}}},"#,
    r#""texts":{"orientation":"stewart.orientation/claude-code/2","#,
    r#""orientation_sha256":"ce0357e115a83092ebeb4b2e9ae34cd455120df26565d74bb5776c91746ed2bd","#,
    r#""reminder_sha256":"a863022bc2ca6682a1162aca9b402293efd296d2bc24669574d0308e193dcdda","#,
    r#""near_limit_sha256":"14dc131ac9bd703c9f8d945db4e78a98a2418b5b27d6535a4870e6ddf5a437d0","#,
    r#""continuation_sha256":"0cced8b9aae42fb09e5c321e64a44037413d0bd244b0e4d2e855e7d3ce850ac0","#,
    r#""compacted_sha256":"976166dc9bf95de048376eedbe5b05e78192eebad57c97032b82f173f5059e17"}}"#,
);
const SURFACE_SHA256: &str = "e8182ecf0009ee1f3889b8e89902bec5eaef34c8bf4c079c2b78c34684780db5";

/// What the synthetic executable does when run. The default is never run:
/// `prepare` hashes it without executing it.
const INERT: &str = "not executed\n";

/// A folder whose question selects the runtime by naming `profile.json`.
/// No harness exists: the pinned executable is a synthetic file.
struct Prepared {
    env: common::Env,
    reference: String,
    executable: String,
}

impl Prepared {
    fn new() -> Self {
        Self::with(INERT, &Self::fields)
    }

    /// The three runtime lines that replace the scaffold's three limits.
    fn fields(env: &common::Env) -> String {
        format!(
            "runtime-profile: {}\nmax-placements: 2\nplacement-timeout-seconds: 60\n",
            env.path("profile.json")
        )
    }

    /// `executable` is the synthetic file's content; `fields` gives the front
    /// matter lines after the common ones.
    fn with(executable: &str, fields: &dyn Fn(&common::Env) -> String) -> Self {
        let env = common::Env::new();
        let reference = env.new_ref();
        std::fs::write(
            format!("{}/question.md", env.folder),
            format!(
                "---\nstewart: question/1\nfamily: open-inquiry\nmodel: fixture-model\ndestination: {}\n{}---\nIs the note consistent?\n",
                env.dest,
                fields(&env)
            ),
        )
        .unwrap();
        std::fs::write(format!("{}/materials/note.txt", env.folder), "A note.\n").unwrap();
        use std::os::unix::fs::PermissionsExt;
        std::fs::write(env.path("harness"), executable).unwrap();
        std::fs::set_permissions(env.path("harness"), std::fs::Permissions::from_mode(0o755))
            .unwrap();
        for directory in ["config", "home", "tmp"] {
            std::fs::create_dir(env.path(directory)).unwrap();
        }
        Self {
            env,
            reference,
            executable: executable.into(),
        }
    }

    /// Write a profile whose check holds `binding: surface`, with every other
    /// binding valid for this folder and platform.
    fn profile(&self, schema: &str, binding: &str, surface: &str) {
        let digest = stewart::util::sha256_hex;
        let executable = digest(self.executable.as_bytes());
        let launch = format!(
            r#"{{"executable":"{}","sha256":"{executable}","version":"2.1.322","platform":"{}-{}","config_directory":"{}","home":"{}","temporary_directory":"{}"}}"#,
            self.env.path("harness"),
            std::env::consts::OS,
            std::env::consts::ARCH,
            self.env.path("config"),
            self.env.path("home"),
            self.env.path("tmp"),
        );
        let family = stewart::forms::family("open-inquiry").unwrap();
        let tools =
            stewart::claude_code::mcp_tools(&stewart::forms::tools(family).bytes()).unwrap();
        let profile = format!(
            r#"{{"schema":"{schema}","launch":{launch},"installation":{{"manifest_sha256":"{}","signer":"31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE","binary_sha256":"{executable}"}},"check":{{"{binding}":"{surface}","launch_sha256":"{}","tools_sha256":"{}","model":"fixture-model","checked_at":"2026-11-11","evidence_sha256":"{}","outcome":"observed"}}}}"#,
            "1".repeat(64),
            digest(launch.as_bytes()),
            digest(&tools),
            "2".repeat(64),
        );
        std::fs::write(self.env.path("profile.json"), profile).unwrap();
    }

    fn prepare(&self) -> common::Out {
        self.env.run(&["prepare", &self.reference, "--json"])
    }
}

/// The surface a refusal reports: its exact document bytes and its digest.
fn reported_surface(out: &common::Out) -> (Vec<u8>, String) {
    let reply = out.json();
    let surface = common::at(&reply, &["data", "surface"]);
    assert_eq!(
        common::s(surface, &["schema"]),
        "stewart.claude-code.surface/1"
    );
    let document = common::at(surface, &["document"]);
    (
        out.stdout[document.start..document.end].to_vec(),
        common::s(surface, &["sha256"]).to_string(),
    )
}

#[test]
fn prepare_accepts_a_check_of_this_surface_and_pins_the_document() {
    assert_eq!(
        stewart::util::sha256_hex(SURFACE.as_bytes()),
        SURFACE_SHA256
    );
    let p = Prepared::new();
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let reply = out.json();
    assert_eq!(common::s(&reply, &["outcome"]), "completed");
    // The machine arrangement holds the document's exact bytes and its digest.
    let raw = std::fs::read(common::s(&reply, &["data", "arrangement", "machine"])).unwrap();
    let record = stewart::json::parse(&raw).unwrap();
    let body = common::at(&record, &["body"]);
    assert_eq!(
        common::s(body, &["schema"]),
        "stewart.claude-code.arrangement/2"
    );
    let pinned = common::at(body, &["surface"]);
    assert_eq!(&raw[pinned.start..pinned.end], SURFACE.as_bytes());
    assert_eq!(common::s(body, &["surface_sha256"]), SURFACE_SHA256);
    let readable =
        std::fs::read_to_string(common::s(&reply, &["data", "arrangement", "readable"])).unwrap();
    assert!(readable.contains(SURFACE_SHA256), "{readable}");
    // The check carries no binding to the binary that prepared the audit.
    let profile = std::fs::read_to_string(p.env.path("profile.json")).unwrap();
    assert!(!profile.contains("writer"));
}

#[test]
fn prepare_refuses_a_check_of_another_surface_and_reports_its_own() {
    let p = Prepared::new();
    // Firing control: the same profile with one digit of the binding changed.
    let other = format!("0{}", &SURFACE_SHA256[1..]);
    assert_ne!(other, SURFACE_SHA256);
    p.profile("stewart.claude-code.profile/2", "surface_sha256", &other);
    let out = p.prepare();
    let reply = out.json();
    assert_eq!(common::s(&reply, &["outcome"]), "refused", "{}", out.text());
    assert_eq!(common::s(&reply, &["reason"]), "runtime_profile_invalid");
    let message = common::s(&reply, &["message"]);
    assert!(message.contains(&other), "{message}");
    assert!(message.contains(SURFACE_SHA256), "{message}");
    assert!(message.contains("No harness was launched"), "{message}");
    let (document, sha256) = reported_surface(&out);
    assert_eq!(document, SURFACE.as_bytes());
    assert_eq!(sha256, SURFACE_SHA256);
    assert_eq!(common::s(&reply, &["effects", "preparation"]), "none");
    // Invariance: correcting only the binding makes the same folder prepare.
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
}

#[test]
fn an_unannotated_tools_check_refuses_before_any_harness_start() {
    let mut p = Prepared::new();
    let witness = p.env.path("launch-witness");
    p.executable = format!(
        "#!/bin/sh\n: > '{}'\nexit 99\n",
        witness.replace('\'', "'\\''")
    );
    std::fs::write(p.env.path("harness"), &p.executable).unwrap();
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let profile_path = p.env.path("profile.json");
    let current_profile = std::fs::read_to_string(&profile_path).unwrap();
    let family = stewart::forms::family("open-inquiry").unwrap();
    let original = stewart::forms::tools(family).bytes();
    let original_json = json::parse(&original).unwrap();
    // The earlier mapped form had only these three fields, in this order.
    // Construct its real digest, rather than substituting an arbitrary hash.
    let old_tools = json::J::Arr(
        original_json
            .as_arr()
            .unwrap()
            .iter()
            .map(|tool| {
                let tool = tool.obj("").unwrap();
                let schema = tool.req("input_schema").unwrap();
                json::J::obj()
                    .with("name", tool.str("name").unwrap())
                    .with("description", tool.str("description").unwrap())
                    .with(
                        "inputSchema",
                        json::J::Raw(original[schema.start..schema.end].to_vec()),
                    )
            })
            .collect(),
    )
    .bytes();
    let old_digest = stewart::util::sha256_hex(&old_tools);
    let current = json::parse(current_profile.as_bytes()).unwrap();
    let current_digest = common::s(&current, &["check", "tools_sha256"]);
    assert_ne!(old_digest, current_digest);
    assert_eq!(current_profile.matches(current_digest).count(), 1);
    std::fs::write(
        &profile_path,
        current_profile.replace(current_digest, &old_digest),
    )
    .unwrap();

    let out = p.prepare();
    let reply = out.json();
    assert_eq!(out.code, Some(3), "{}{}", out.text(), out.stderr);
    assert_eq!(common::s(&reply, &["reason"]), "runtime_profile_invalid");
    assert_eq!(common::s(&reply, &["effects", "preparation"]), "none");
    let message = common::s(&reply, &["message"]);
    assert!(message.contains("MCP tool surface"), "{message}");
    assert!(message.contains("No harness was launched"), "{message}");
    assert_eq!(
        reported_surface(&out),
        (SURFACE.as_bytes().to_vec(), SURFACE_SHA256.to_string())
    );
    assert!(!std::path::Path::new(&witness).exists());
    assert_eq!(p.env.log_kinds(&p.reference), ["reference"]);

    // Only the tool-definition binding changes: the same launch surface,
    // executable, model and question now prepare successfully without a start.
    std::fs::write(&profile_path, current_profile).unwrap();
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    assert!(!std::path::Path::new(&witness).exists());
    assert_eq!(p.env.log_kinds(&p.reference), ["reference", "prepared"]);
}

#[test]
fn another_profile_form_is_refused_by_name() {
    let p = Prepared::new();
    // The earlier identifier, here with members that would otherwise pass.
    p.profile(
        "stewart.claude-code.profile/1",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let out = p.prepare();
    let reply = out.json();
    assert_eq!(common::s(&reply, &["reason"]), "runtime_profile_invalid");
    let message = common::s(&reply, &["message"]);
    assert!(
        message.contains("stewart.claude-code.profile/1")
            && message.contains("stewart.claude-code.profile/2"),
        "{message}"
    );
    assert_eq!(reported_surface(&out).1, SURFACE_SHA256);
    // A binding to the writer is not a member of the current form.
    p.profile(
        "stewart.claude-code.profile/2",
        "writer_sha256",
        SURFACE_SHA256,
    );
    let out = p.prepare();
    let reply = out.json();
    assert_eq!(common::s(&reply, &["reason"]), "runtime_profile_invalid");
    assert!(
        common::s(&reply, &["message"]).contains("writer_sha256"),
        "{}",
        out.text()
    );
}

/// The prepare reply for `p` after replacing `from` with `to` in question.md.
fn prepare_with(p: &Prepared, from: &str, to: &str) -> common::Out {
    let path = format!("{}/question.md", p.env.folder);
    let text = std::fs::read_to_string(&path).unwrap();
    assert!(text.contains(from), "{from:?} is in the fixture");
    std::fs::write(&path, text.replacen(from, to, 1)).unwrap();
    p.prepare()
}

/// The reply refused the question with exactly one defect: this reason on this key.
fn one_defect(out: &common::Out, reason: &str, key: &str) -> String {
    let reply = out.json();
    assert_eq!(common::s(&reply, &["outcome"]), "refused", "{}", out.text());
    assert_eq!(common::s(&reply, &["reason"]), reason, "{}", out.text());
    let defects = common::at(&reply, &["data", "defects"]).as_arr().unwrap();
    assert_eq!(defects.len(), 1, "{}", out.text());
    assert_eq!(common::s(&defects[0], &["reason"]), reason);
    assert_eq!(common::s(&defects[0], &["key"]), key);
    assert_eq!(common::s(&reply, &["effects", "preparation"]), "none");
    common::s(&defects[0], &["message"]).to_string()
}

const API_LIMITS: &str =
    "limit-turns: 200\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\n";

#[test]
fn the_removed_question_version_refuses_by_name() {
    let p = Prepared::new();
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let out = prepare_with(&p, "stewart: question/1", "stewart: question/claude-code/1");
    let message = one_defect(&out, "setting_invalid", "stewart");
    assert!(
        message.contains("question/claude-code/1") && message.contains("exactly question/1"),
        "{message}"
    );
    // Invariance: the same folder on the one version prepares.
    let out = prepare_with(&p, "stewart: question/claude-code/1", "stewart: question/1");
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
}

#[test]
fn api_limits_and_placement_fields_do_not_mix() {
    // Each API limit beside a profile refuses, although its value is valid.
    for limit in API_LIMITS.lines() {
        let p = Prepared::with(INERT, &|env| format!("{}{limit}\n", Prepared::fields(env)));
        p.profile(
            "stewart.claude-code.profile/2",
            "surface_sha256",
            SURFACE_SHA256,
        );
        let key = limit.split(':').next().unwrap();
        let message = one_defect(&p.prepare(), "setting_invalid", key);
        assert!(message.contains("runtime-profile"), "{message}");
    }
    // Each placement field without a profile refuses.
    for field in ["max-placements: 2", "placement-timeout-seconds: 60"] {
        let p = Prepared::with(INERT, &|_| format!("{API_LIMITS}{field}\n"));
        let key = field.split(':').next().unwrap();
        let message = one_defect(&p.prepare(), "setting_invalid", key);
        assert!(message.contains("runtime-profile"), "{message}");
    }
    // A profile without one of its placement fields lacks a required key.
    let p = Prepared::new();
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let out = prepare_with(&p, "max-placements: 2\n", "");
    one_defect(&out, "setting_missing", "max-placements");
}

/// Invariance: in this build a question without a profile is a Messages API
/// question, with the common arrangement and run requirements.
#[test]
fn a_question_without_a_profile_is_a_messages_question() {
    let p = Prepared::with(INERT, &|_| API_LIMITS.to_string());
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let reply = out.json();
    let settings = common::at(&reply, &["data", "settings"]);
    assert!(!common::has(settings, "runtime"));
    assert_eq!(
        common::at(settings, &["limits", "turns"]).as_u64(),
        Some(200)
    );
    let raw = std::fs::read(common::s(&reply, &["data", "arrangement", "machine"])).unwrap();
    let record = stewart::json::parse(&raw).unwrap();
    assert_eq!(
        common::s(&record, &["body", "schema"]),
        "stewart.arrangement/2"
    );
    assert_eq!(
        common::s(&record, &["body", "orientation"]),
        "stewart.orientation/1"
    );
    let out = p
        .env
        .commission(&p.reference, common::s(&reply, &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let needs = common::strs(&out.json(), &["data", "run_needs"]);
    assert_eq!(needs.len(), 3);
    assert!(needs[0].contains("--key-fd"), "{needs:?}");
}

#[test]
fn help_leads_to_the_runtime_topic_and_the_scaffold_is_the_common_one() {
    let env = common::Env::new();
    let overview = env.run(&["help"]).text();
    let notice = overview.split("\n\n").next().unwrap();
    assert!(notice.starts_with("Stewart development build: claude-code\n"));
    assert!(notice.contains("stewart help runtime"), "{notice}");
    assert!(!notice.contains("docs/"), "{notice}");
    assert!(
        overview.ends_with(
            "Topics: stewart help commands | forms | limits | reader | close | runtime\n"
        )
    );
    let out = env.run(&["help", "runtime"]);
    assert_eq!(out.code, Some(0));
    let topic = out.text();
    for fact in [
        "stewart: question/1",
        "limit-turns",
        "runtime-profile",
        "max-placements",
        "placement-timeout-seconds",
        "stewart.claude-code.profile/2",
        "launch surface",
        "runtime_profile_invalid",
        "subscription login",
        "--key-fd",
        "in the background",
        "partial or unknown",
    ] {
        assert!(topic.contains(fact), "the runtime topic lacks {fact:?}");
    }
    let unknown = env.run(&["help", "nope"]);
    assert_eq!(unknown.code, Some(2));
    assert!(unknown.stderr.contains("reader, close, runtime"));
    // The usage synopsis is the common one in both builds.
    assert!(
        unknown
            .stderr
            .contains("stewart help [commands | forms | limits | reader | close]")
    );
    // `new` writes the ordinary scaffold: one version, the three API limits
    // and nothing about this runtime.
    env.new_ref();
    let scaffold = std::fs::read_to_string(format!("{}/question.md", env.folder)).unwrap();
    let control_lines: Vec<&str> = scaffold
        .lines()
        .filter(|line| !line.starts_with('#') && !line.is_empty())
        .collect();
    assert_eq!(
        control_lines,
        [
            "---",
            "stewart: question/1",
            "family: open-inquiry",
            "model: REPLACE-WITH-MODEL",
            "destination: REPLACE-WITH-ABSOLUTE-DIRECTORY",
            "limit-turns: 200",
            "limit-input-tokens: 20000000",
            "limit-output-tokens: 400000",
            "---"
        ]
    );
    assert!(scaffold.contains("stewart: question/1\n") && scaffold.contains("limit-turns: "));
    assert!(!scaffold.contains("runtime") && !scaffold.contains("placement"));
}

#[test]
fn people_see_the_profile_by_path_and_digest_and_what_run_needs() {
    let p = Prepared::new();
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let text = std::fs::read_to_string(p.env.path("profile.json")).unwrap();
    let shown = [
        format!("profile path: {}\n", p.env.path("profile.json")),
        format!(
            "profile sha256: {}\n",
            stewart::util::sha256_hex(text.as_bytes())
        ),
    ];
    let for_people = |out: common::Out| {
        assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
        let human = out.text();
        for line in &shown {
            assert!(human.contains(line.as_str()), "{human}");
        }
        // None of the profile's own members is printed.
        for member in ["manifest_sha256", "evidence_sha256", "checked_at", "signer"] {
            assert!(!human.contains(member), "{human}");
        }
    };
    for_people(p.env.run(&["prepare", &p.reference]));
    // The JSON reply keeps the exact captured text.
    let out = p.prepare();
    let reply = out.json();
    assert_eq!(
        common::s(&reply, &["data", "settings", "runtime", "profile"]),
        text
    );
    let out = p
        .env
        .commission(&p.reference, common::s(&reply, &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    for_people(p.env.run(&["receipt", &p.reference]));
    let receipt = p.env.run(&["receipt", &p.reference, "--json"]).json();
    assert_eq!(
        common::s(&receipt, &["data", "settings", "runtime", "profile"]),
        text
    );
    // Commission and receipt state the same four requirements.
    let needs = common::strs(&out.json(), &["data", "run_needs"]);
    assert_eq!(needs, common::strs(&receipt, &["data", "run_needs"]));
    assert_eq!(needs.len(), 4, "{needs:?}");
    for (item, facts) in [
        (
            0,
            &["authority", "bounded placement", "no automatic restart"][..],
        ),
        (
            1,
            &[
                "pinned harness",
                "subscription login",
                "extra usage disabled",
            ],
        ),
        (
            2,
            &[
                "no credential argument",
                "environment variable",
                "no API fallback",
            ],
        ),
        (
            3,
            &[
                "foreground",
                "placement ends",
                "deadline",
                "command timeouts",
                "in the background",
                "partial or unknown",
            ],
        ),
    ] {
        for fact in facts {
            assert!(needs[item].contains(fact), "item {item} lacks {fact:?}");
        }
    }
    // Before any start the summary counts nothing, in the plural.
    let status = p.env.run(&["status", &p.reference]).text();
    assert!(status.contains("0 used of 2; 2 remain."), "{status}");
    assert!(status.contains("60 seconds"), "{status}");
    assert!(
        status.contains("0 placements have a reported checkpoint")
            && status.contains("observed for 0 placements."),
        "{status}"
    );
}

/// A synthetic executable that records what it was started with and then
/// fails, as a status check that does not report a login would. It starts no
/// session; the placement it was reserved for is used and observed stopped.
const RECORDING: &str = "#!/bin/sh\n{ printf '%s\\n' \"$@\"; echo ---; /usr/bin/env; echo ---; pwd; } >> \"$HOME/observed\"\nexit 1\n";

#[test]
fn a_used_placement_is_counted_in_the_singular_with_its_deadline() {
    let p = Prepared::with(RECORDING, &Prepared::fields);
    // The runtime refuses a launch directory under project instructions.
    if std::path::Path::new(&p.env.path("tmp"))
        .ancestors()
        .any(|a| {
            [".git", "CLAUDE.md", "AGENTS.md", ".claude"]
                .iter()
                .any(|m| a.join(m).symlink_metadata().is_ok())
        })
    {
        panic!(
            "required scratch directory is under a project or configuration tree; rerun with a clean TMPDIR"
        );
    }
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let reply = p.prepare().json();
    let out = p
        .env
        .commission(&p.reference, common::s(&reply, &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);

    let run = p
        .env
        .run_env(&["run", &p.reference], &[("STEWART_IT_CALLER", "caller")]);
    let human = run.text();
    assert!(
        human.contains("1 used of 2; 1 remains."),
        "{human}{}",
        run.stderr
    );
    assert!(human.contains("deadline of 60 seconds"), "{human}");
    assert!(
        human.contains("0 placements have a reported checkpoint")
            && human.contains("1 placement has an uncovered interval")
            && human.contains("observed for 1 placement."),
        "{human}"
    );
    // The JSON summary is the same text, and the API-only status members
    // stay present and null.
    let status = p.env.run(&["status", &p.reference, "--json"]).json();
    let summary = common::s(&status, &["data", "summary"]);
    for line in summary.lines().filter(|l| l.contains("lacement")) {
        assert!(human.contains(line), "{line}");
    }
    assert!(summary.contains("1 used of 2; 1 remains.") && summary.contains("60 seconds"));
    for member in ["provider_url_override", "provider_proxy"] {
        assert!(common::at(&status, &["data", member]).is_null(), "{member}");
    }

    // What the executable was actually started with is the surface's
    // authentication leg: its arguments, the whole environment and a fresh
    // working directory under the pinned temporary directory.
    let observed = std::fs::read_to_string(p.env.path("home/observed")).unwrap();
    let parts: Vec<&str> = observed.split("---\n").collect();
    assert_eq!(parts.len(), 3, "{observed}");
    assert_eq!(parts[0], "auth\nstatus\n");
    let surface = stewart::json::parse(SURFACE.as_bytes()).unwrap();
    let json::V::Obj(expected) = &common::at(&surface, &["environment"]).v else {
        panic!("environment object");
    };
    let fill = |value: &str| {
        value
            .replace("{home}", &p.env.path("home"))
            .replace("{temporary_directory}", &p.env.path("tmp"))
            .replace("{config_directory}", &p.env.path("config"))
    };
    let seen: Vec<(&str, &str)> = parts[1]
        .lines()
        .map(|l| l.split_once('=').expect("NAME=value"))
        .collect();
    for (name, value) in expected {
        let value = fill(value.as_str().unwrap());
        assert!(
            seen.contains(&(name.as_str(), value.as_str())),
            "{name}={value} was not supplied: {seen:?}"
        );
    }
    // Nothing else arrives, apart from what the shell itself adds.
    for (name, _) in &seen {
        assert!(
            expected.iter().any(|(k, _)| k == name)
                || ["PWD", "OLDPWD", "SHLVL", "_"].contains(name),
            "{name} reached the executable"
        );
    }
    let cwd = parts[2].trim_end();
    let tmp = std::fs::canonicalize(p.env.path("tmp")).unwrap();
    let cwd = std::fs::canonicalize(std::path::Path::new(cwd).parent().unwrap())
        .map(|parent| (parent, cwd.rsplit('/').next().unwrap().to_string()));
    let (parent, name) = cwd.unwrap();
    assert_eq!(parent, tmp);
    assert!(name.starts_with("stewart-"), "{name}");

    // A second failed start uses the last slot; every count is now plural or zero.
    let human = p.env.run(&["run", &p.reference]).text();
    assert!(human.contains("2 used of 2; 0 remain."), "{human}");
    assert!(
        human.contains("2 placements have an uncovered interval")
            && human.contains("observed for 2 placements."),
        "{human}"
    );
    let refused = p.env.run(&["run", &p.reference, "--json"]).json();
    assert_eq!(common::s(&refused, &["outcome"]), "refused");
}

/// The raw bytes of one log record's body, from after its `prev` member.
fn body_after_prev(e: &common::Env, r: &str, n: usize) -> String {
    let raw = std::fs::read(format!("{}/log/{n}.json", e.audit_dir(r))).unwrap();
    let parsed = json::parse(&raw).unwrap();
    let body = common::at(&parsed, &["body"]);
    let text = String::from_utf8(raw[body.start..body.end].to_vec()).unwrap();
    assert!(text.starts_with(r#"{"prev":"#), "{text}");
    let at = text.find(r#","run":"#).expect("a run record");
    format!("{{{}", &text[at + 1..])
}

/// What a harness placement writes when its first start fails: the run
/// records and the usage checkpoint, byte for byte where the bytes do not
/// depend on the process or the machine.
#[test]
fn a_failed_start_leaves_the_harness_records_and_usage_checkpoint() {
    let p = Prepared::with(RECORDING, &Prepared::fields);
    // The runtime refuses a launch directory under project instructions.
    if std::path::Path::new(&p.env.path("tmp"))
        .ancestors()
        .any(|a| {
            [".git", "CLAUDE.md", "AGENTS.md", ".claude"]
                .iter()
                .any(|m| a.join(m).symlink_metadata().is_ok())
        })
    {
        panic!(
            "required scratch directory is under a project or configuration tree; rerun with a clean TMPDIR"
        );
    }
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let reply = p.prepare().json();
    let out = p
        .env
        .commission(&p.reference, common::s(&reply, &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let run = p
        .env
        .run_env(&["run", &p.reference], &[("STEWART_IT_CALLER", "caller")]);
    assert!(
        run.text().contains("Run 1 was interrupted (protocol_anomaly)."),
        "{}{}",
        run.text(),
        run.stderr
    );

    let kinds = p.env.log_kinds(&p.reference);
    assert_eq!(
        kinds,
        [
            "reference",
            "prepared",
            "intake_planned",
            "accepted",
            "run_started",
            "run_ended"
        ]
    );

    // run_started: the harness member follows the observations, the
    // provider is null, and the profile digest is that of the profile file.
    let arrangement = common::s(
        &p.env.log_record(&p.reference, 2),
        &["body", "arrangement_sha256"],
    )
    .to_string();
    let profile = std::fs::read(p.env.path("profile.json")).unwrap();
    let started = body_after_prev(&p.env, &p.reference, 5);
    let (head, rest) = started.split_once(r#""observations":"#).unwrap();
    let (observations, runtime) = rest.split_once(r#","runtime":"#).unwrap();
    assert_eq!(
        head,
        format!(
            r#"{{"run":1,"continuing":false,"dir":"runs/1","arrangement_sha256":"{arrangement}","provider":null,"#
        )
    );
    // The values are the process's own; the order is the record's.
    let order: Vec<usize> = ["pid", "start_ticks", "uid", "host", "boot_id"]
        .iter()
        .map(|k| observations.find(&format!(r#""{k}":"#)).unwrap())
        .collect();
    assert!(order.windows(2).all(|w| w[0] < w[1]), "{observations}");
    assert_eq!(
        runtime,
        format!(
            r#"{{"kind":"claude-code/1","profile_sha256":"{}","placement_timeout_seconds":60}}}}"#,
            stewart::util::sha256_hex(&profile)
        )
    );

    // run_ended: the usage is the reserved placement, observed stopped.
    let summary = r#"{"runtime":"claude-code/1","placements":1,"unknown_intervals":1,"stopped":1,"reported_placements":0,"reported_main_loop":null,"provider_completeness":"unverified"}"#;
    let ended = body_after_prev(&p.env, &p.reference, 6);
    let (ended, _message) = ended.split_once(r#","message":"#).unwrap();
    assert_eq!(
        ended,
        format!(
            r#"{{"run":1,"ending":"interrupted","cause":"protocol_anomaly","recorded_by":"run","provider":null,"requests":0,"attempts":0,"usage":{summary},"notices":[],"seal":null"#
        )
    );
    // The checkpoint file holds the same summary, with no trailing newline.
    let checkpoint = format!("{}/runs/1/runtime-usage-1.json", p.env.audit_dir(&p.reference));
    assert_eq!(std::fs::read_to_string(checkpoint).unwrap(), summary);
}

/// A commissioned audit whose pinned harness is the synthetic `executable`,
/// with two placements of 60 seconds each.
fn commissioned(executable: &str) -> Prepared {
    let p = Prepared::with(executable, &Prepared::fields);
    // The runtime refuses a launch directory under project instructions.
    if std::path::Path::new(&p.env.path("tmp"))
        .ancestors()
        .any(|a| {
            [".git", "CLAUDE.md", "AGENTS.md", ".claude"]
                .iter()
                .any(|m| a.join(m).symlink_metadata().is_ok())
        })
    {
        panic!(
            "required scratch directory is under a project or configuration tree; rerun with a clean TMPDIR"
        );
    }
    p.profile(
        "stewart.claude-code.profile/2",
        "surface_sha256",
        SURFACE_SHA256,
    );
    let reply = p.prepare().json();
    let out = p
        .env
        .commission(&p.reference, common::s(&reply, &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    p
}

/// The startup event a synthetic harness prints, as the runtime validates
/// it: the profile's version and model, the commission's tools, the Stewart
/// MCP server and the built-in plugins.
fn init_event() -> String {
    let family = stewart::forms::family("open-inquiry").unwrap();
    let tools = json::parse(&stewart::forms::tools(family).bytes()).unwrap();
    let names: Vec<String> = tools
        .as_arr()
        .unwrap()
        .iter()
        .map(|t| format!(r#""mcp__stewart__{}""#, common::s(t, &["name"])))
        .collect();
    let plugins: Vec<String> = [
        "cc-plugin-agents-md",
        "cc-plugin-privacy",
        "cc-plugin-plugin-authoring",
    ]
    .iter()
    .map(|n| format!(r#"{{"name":"{n}","path":"builtin","source":"{n}@builtin"}}"#))
    .collect();
    format!(
        r#"{{"type":"system","subtype":"init","session_id":"s1","apiKeySource":"none","claude_code_version":"2.1.322","model":"fixture-model","permissionMode":"dontAsk","tools":[{}],"mcp_servers":[{{"name":"stewart","status":"connected"}}],"plugins":[{}]}}"#,
        names.join(","),
        plugins.join(",")
    )
}

/// A synthetic harness that passes the authentication check, then reads the
/// question, starts and ends its first turn. Given the reminder, it ends a
/// second turn and waits to be stopped.
fn two_turns() -> String {
    let result = |turns: u64| {
        format!(
            r#"{{"type":"result","session_id":"s1","is_error":false,"num_turns":{turns},"usage":{{"input_tokens":{turns},"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":{turns}}}}}"#
        )
    };
    format!(
        concat!(
            "#!/bin/sh\n",
            "if [ \"$1\" = auth ]; then\n",
            "  printf '{{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"configDirectory\":\"%s\"}}\\n' \"$CLAUDE_CONFIG_DIR\"\n",
            "  exit 0\n",
            "fi\n",
            "IFS= read -r question\n",
            "printf '%s\\n' '{}'\n",
            "printf '%s\\n' '{}'\n",
            "IFS= read -r reminder || exit 0\n",
            "printf '%s\\n' '{}'\n",
            "while :; do sleep 1; done\n",
        ),
        init_event(),
        result(1),
        result(2)
    )
}

/// The harness's placement claims the reminder as its first notice, sends
/// it, and lists it as sent; the harness's second turn then ends the
/// placement without a submission.
#[test]
fn a_transmitted_reminder_is_listed_by_its_placement_as_sent() {
    let p = commissioned(&two_turns());
    let reply = p.env.run(&["run", &p.reference, "--json"]).json();
    let kinds = p.env.log_kinds(&p.reference);
    let ended = p.env.log_record(&p.reference, kinds.len());
    // A refused Unix socket, as in a sandbox, ends the placement early;
    // the recorded message says so.
    assert_eq!(
        common::s(&reply, &["data", "ending"]),
        "ended_unsubmitted",
        "{}",
        common::s(&ended, &["body", "message"])
    );
    assert_eq!(kinds[4..], ["run_started", "notice", "run_ended"]);
    let notice = p.env.log_record(&p.reference, 6);
    assert_eq!(common::s(&notice, &["body", "type"]), "reminder");
    assert_eq!(common::at(&notice, &["body", "request"]).as_u64(), Some(1));
    assert_eq!(
        common::s(&ended, &["body", "notices", "0", "record"]),
        "log/6.json"
    );
    assert_eq!(common::s(&ended, &["body", "notices", "0", "sent"]), "sent");
    assert_eq!(common::s(&reply, &["data", "notices", "0", "sent"]), "sent");
}

/// A reminder claim linked without confirmed durability stands in the log:
/// the placement stops before sending it, and its `run_ended` and the run
/// reply list it as `not_sent`. The control's claim was never linked, so
/// nothing lists it.
#[cfg(feature = "fault-injection")]
#[test]
fn a_linked_but_unconfirmed_reminder_is_listed_by_its_placement_as_not_sent() {
    for (fault, linked) in [
        ("log.dirsync:notice=eio", true),
        ("log.publish:notice=eio", false),
    ] {
        let p = commissioned(&two_turns());
        let reply = p
            .env
            .run_env(
                &["run", &p.reference, "--json"],
                &[("STEWART_TEST_FAULT", fault)],
            )
            .json();
        let kinds = p.env.log_kinds(&p.reference);
        let ended = p.env.log_record(&p.reference, kinds.len());
        assert_eq!(
            common::s(&reply, &["data", "cause"]),
            "archive_write_failed",
            "{fault}: {}",
            common::s(&ended, &["body", "message"])
        );
        let in_record = common::at(&ended, &["body", "notices"]).as_arr().unwrap();
        let in_reply = common::at(&reply, &["data", "notices"]).as_arr().unwrap();
        if linked {
            assert_eq!(
                kinds[4..],
                ["run_started", "notice", "run_ended"],
                "{fault}"
            );
            assert_eq!((in_record.len(), in_reply.len()), (1, 1), "{fault}");
            assert_eq!(common::s(&in_record[0], &["type"]), "reminder");
            assert_eq!(common::s(&in_record[0], &["record"]), "log/6.json");
            assert_eq!(common::s(&in_record[0], &["sent"]), "not_sent");
            assert_eq!(common::s(&in_reply[0], &["type"]), "reminder");
            assert_eq!(common::s(&in_reply[0], &["sent"]), "not_sent");
        } else {
            assert_eq!(kinds[4..], ["run_started", "run_ended"], "{fault}");
            assert!(in_record.is_empty() && in_reply.is_empty(), "{fault}");
        }
    }
}
