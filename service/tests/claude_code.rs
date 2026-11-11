#![cfg(feature = "claude-code")]
mod answer_support;
mod common;
use answer_support::Live;
use std::time::{Duration, Instant};
use stewart::claude_code::gate::Gate;

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
    r#""texts":{"orientation":"stewart.orientation/claude-code/1","#,
    r#""orientation_sha256":"2d12b500300537f665a3265c368f132794284bb543e9f5659decd5b2af439b82","#,
    r#""reminder_sha256":"a863022bc2ca6682a1162aca9b402293efd296d2bc24669574d0308e193dcdda","#,
    r#""near_limit_sha256":"14dc131ac9bd703c9f8d945db4e78a98a2418b5b27d6535a4870e6ddf5a437d0","#,
    r#""continuation_sha256":"0cced8b9aae42fb09e5c321e64a44037413d0bd244b0e4d2e855e7d3ce850ac0","#,
    r#""compacted_sha256":"08dd7b07e1cb01dea350c3bd7c42bda0a55fc2b1439a089ff825a71f90cf67d4"}}"#,
);
const SURFACE_SHA256: &str = "bd49da58770c7115c39fe54fb784e31b3616449c9d14f63cc7c49c9474b6b755";

/// A folder whose question selects the runtime and names `profile.json`.
/// No harness exists: the pinned executable is an inert file that `prepare`
/// hashes and never executes.
struct Prepared {
    env: common::Env,
    reference: String,
}

impl Prepared {
    fn new() -> Self {
        let env = common::Env::new();
        let reference = env.new_ref();
        std::fs::write(
            format!("{}/question.md", env.folder),
            format!(
                "---\nstewart: question/claude-code/1\nfamily: open-inquiry\nmodel: fixture-model\ndestination: {}\nruntime-profile: {}\nmax-placements: 2\nplacement-timeout-seconds: 60\n---\nIs the note consistent?\n",
                env.dest,
                env.path("profile.json")
            ),
        )
        .unwrap();
        std::fs::write(format!("{}/materials/note.txt", env.folder), "A note.\n").unwrap();
        std::fs::write(env.path("harness"), "not executed\n").unwrap();
        Self { env, reference }
    }

    /// Write a profile whose check holds `binding: surface`, with every other
    /// binding valid for this folder and platform.
    fn profile(&self, schema: &str, binding: &str, surface: &str) {
        let digest = stewart::util::sha256_hex;
        let executable = digest(b"not executed\n");
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
