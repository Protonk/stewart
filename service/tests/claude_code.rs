#![cfg(feature = "claude-code")]
mod answer_support;
mod common;
use answer_support::{Live, Res};
use std::time::{Duration, Instant};
use stewart::gate::Gate;
use stewart::json;

/// A call as the harness runtime dispatches it, under `gate`.
fn dispatched(live: &mut Live, gate: &Gate, tool: &str, input: &str) -> Res {
    live.call_by(
        Some(tool),
        Some(input.as_bytes()),
        |audit, world, placement, call| {
            stewart::claude_code::run::dispatch(audit, world, placement, call, gate)
        },
    )
}

/// The files in the audit's `stage` and `payload` directories: a call that
/// entered a recording tool leaves its payload and stage candidates there.
fn candidates(live: &Live) -> usize {
    ["stage", "payload"]
        .iter()
        .map(|d| {
            std::fs::read_dir(format!("{}/{d}", live.audit_dir()))
                .map_or(0, |entries| entries.count())
        })
        .sum()
}

#[test]
fn core_recording_obeys_stop_and_fresh_call_invariance() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() + Duration::from_secs(60));
    dispatched(
        &mut live,
        &gate,
        "record_account",
        r#"{"text":"firing control"}"#,
    )
    .ok();
    let revision = live.state().revision();
    let before = candidates(&live);
    let stopped = gate.call();
    stopped.cancel();
    let reply = dispatched(
        &mut live,
        &stopped,
        "record_account",
        r#"{"text":"must not publish"}"#,
    );
    assert_eq!(reply.outcome(), "refused", "{}", reply.text());
    assert_eq!(reply.reason(), "placement_stopped");
    assert_eq!(live.state().revision(), revision);
    assert_eq!(
        candidates(&live),
        before,
        "a call whose gate closed before it started enters no tool"
    );
    dispatched(
        &mut live,
        &gate.call(),
        "record_account",
        r#"{"text":"fresh invariance"}"#,
    )
    .ok();
    assert_eq!(live.state().revision(), revision + 1);
}

#[test]
fn expired_deadline_cannot_publish_a_core_record() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() - Duration::from_millis(1));
    let reply = dispatched(&mut live, &gate, "record_account", r#"{"text":"late"}"#);
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
        let refusal = dispatched(&mut live, &gate, "submit", &input);
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
            let accepted = dispatched(&mut live, &parent.call(), "submit", &input);
            accepted.ok();
            assert_eq!(accepted.effect("seal"), "recorded");
            assert!(accepted.ex.sealed);
        } else {
            let fresh = Gate::new(Instant::now() + Duration::from_secs(60));
            let accepted = dispatched(&mut live, &fresh, "submit", &input);
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
                "---\nstewart: question/2\nfamily: open-inquiry\nmodel: fixture-model\ndestination: {}\n{}---\nIs the note consistent?\n",
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
        "stewart.claude-code.arrangement/3"
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
    let out = prepare_with(&p, "stewart: question/2", "stewart: question/claude-code/1");
    let message = one_defect(&out, "setting_invalid", "stewart");
    assert!(
        message.contains("question/claude-code/1") && message.contains("exactly question/2"),
        "{message}"
    );
    // Invariance: the same folder on the one version prepares.
    let out = prepare_with(&p, "stewart: question/claude-code/1", "stewart: question/2");
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
        "stewart.arrangement/3"
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
        "stewart: question/2",
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
            "stewart: question/2",
            "family: open-inquiry",
            "model: REPLACE-WITH-MODEL",
            "destination: REPLACE-WITH-ABSOLUTE-DIRECTORY",
            "limit-turns: 200",
            "limit-input-tokens: 20000000",
            "limit-output-tokens: 400000",
            "---"
        ]
    );
    assert!(scaffold.contains("stewart: question/2\n") && scaffold.contains("limit-turns: "));
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
    commissioned_for(executable, 2, 60)
}

/// A commissioned audit whose pinned harness is the synthetic `executable`,
/// with `placements` placements of `seconds` seconds each.
fn commissioned_for(executable: &str, placements: u64, seconds: u64) -> Prepared {
    let fields = |env: &common::Env| {
        format!(
            "runtime-profile: {}\nmax-placements: {placements}\nplacement-timeout-seconds: {seconds}\n",
            env.path("profile.json")
        )
    };
    let p = Prepared::with(executable, &fields);
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

/// A `run` of this binary under `env`, with its output piped, started in
/// the background.
#[cfg(feature = "fault-injection")]
fn spawned(e: &common::Env, args: &[&str], vars: &[(&str, &str)]) -> std::process::Child {
    let mut c = std::process::Command::new(common::bin());
    c.args(args)
        .current_dir(&e.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE");
    for (k, v) in vars {
        c.env(k, v);
    }
    c.stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap()
}

/// Wait up to 30 seconds for `ready`.
#[cfg(feature = "fault-injection")]
fn until(ready: impl Fn() -> bool) -> bool {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(30) {
        if ready() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    false
}

/// The harness runtime reserves its start as the Messages runtime does
/// (INTERFACE 5.7). A `run_started` that was not linked started nothing:
/// `failed` `record_failed`, `effects.run` `not_started`, and the slot stays
/// free. One linked without confirmed durability may stand and so consumes
/// its slot: `failed` `record_failed`, `effects.run` `unknown`, no harness
/// launched, and the next run reconciles that placement as gone before
/// using the second slot.
#[cfg(feature = "fault-injection")]
#[test]
fn a_harness_start_reservation_reports_what_it_linked() {
    let p = commissioned(RECORDING);
    let reference = p.reference.as_str();
    let launched = || std::path::Path::new(&p.env.path("home/observed")).exists();
    let faulted = |fault: &str| {
        p.env.run_env(
            &["run", reference, "--json"],
            &[("STEWART_TEST_FAULT", fault)],
        )
    };
    for (fault, run, linked, operation) in [
        (
            "log.publish:run_started=eio",
            "not_started",
            false,
            "link run_started record",
        ),
        (
            "log.dirsync:run_started=eio",
            "unknown",
            true,
            "fsync log directory",
        ),
    ] {
        let out = faulted(fault);
        let reply = out.json();
        assert_eq!(out.code, Some(4), "{fault}: {}{}", out.text(), out.stderr);
        assert_eq!(
            (
                common::s(&reply, &["outcome"]),
                common::s(&reply, &["reason"])
            ),
            ("failed", "record_failed"),
            "{fault}: {}",
            out.text()
        );
        for (effect, value) in [
            ("run", run),
            ("answer", "unchanged"),
            ("seal", "none"),
            ("delivery", "none"),
            ("diagnostic", "durable"),
        ] {
            assert_eq!(common::s(&reply, &["effects", effect]), value, "{fault}");
        }
        assert_eq!(
            common::s(&reply, &["causes", "0", "operation"]),
            operation,
            "{fault}"
        );
        let kinds = p.env.log_kinds(reference);
        if linked {
            assert_eq!(
                common::s(&reply, &["message"]),
                "run_started was linked as log/5.json but its durability could not be confirmed; the run did not continue."
            );
            assert_eq!(common::strs(&reply, &["next", "0", "argv"])[1], "status");
            assert_eq!(kinds[4..], ["run_started"], "{fault}");
        } else {
            assert_eq!(
                common::s(&reply, &["message"]),
                "run_started could not be recorded, so no placement started."
            );
            assert_eq!(kinds.len(), 4, "{fault}: {kinds:?}");
        }
        assert!(!launched(), "{fault}: no harness is launched");
        let dir = format!("{}/runs/1", p.env.audit_dir(reference));
        assert!(!std::path::Path::new(&dir).exists(), "{fault}");
    }
    // The linked placement used the first slot; the next run records it as
    // gone and uses the second.
    let human = p.env.run(&["run", reference]).text();
    assert!(human.contains("2 used of 2; 0 remain."), "{human}");
    let kinds = p.env.log_kinds(reference);
    assert_eq!(
        kinds[4..],
        ["run_started", "run_ended", "run_started", "run_ended"]
    );
    let gone = p.env.log_record(reference, 6);
    assert_eq!(common::at(&gone, &["body", "run"]).as_u64(), Some(1));
    assert_eq!(common::s(&gone, &["body", "cause"]), "process_gone");
    assert_eq!(common::s(&gone, &["body", "recorded_by"]), "run");
    assert!(launched());
}

/// A close linked while the harness runtime's reservation waits to link
/// wins the log slot, and run refuses `reference_closed` with the data and
/// next calls of the state check, as it does once that close is settled
/// (INTERFACE 5.7); nothing starts and the close completes. Control: the
/// same pause released without a close reserves the start and launches the
/// harness.
#[cfg(feature = "fault-injection")]
#[test]
fn a_close_that_wins_the_harness_start_reservation_is_refused_reference_closed() {
    for close in [false, true] {
        let p = commissioned(RECORDING);
        let reference = p.reference.as_str();
        let faults = p.env.path("faults");
        std::fs::create_dir(&faults).unwrap();
        let run = spawned(
            &p.env,
            &["run", reference, "--json"],
            &[
                ("STEWART_TEST_FAULT", "log.publish:run_started=pause"),
                ("STEWART_TEST_FAULT_DIR", &faults),
            ],
        );
        let paused = format!("{faults}/log.publish:run_started.paused");
        assert!(until(|| std::path::Path::new(&paused).exists()));
        let closing = close.then(|| {
            let child = spawned(&p.env, &["close", reference, "--json"], &[]);
            assert!(until(|| p
                .env
                .log_kinds(reference)
                .iter()
                .any(|k| k == "close_requested")));
            child
        });
        std::fs::write(format!("{faults}/log.publish:run_started.go"), b"").unwrap();
        let out = run.wait_with_output().unwrap();
        let reply = json::parse(&out.stdout).unwrap();
        let launched = std::path::Path::new(&p.env.path("home/observed")).exists();
        let kinds = p.env.log_kinds(reference);
        if !close {
            assert_eq!(out.status.code(), Some(5), "control");
            assert_eq!(common::s(&reply, &["data", "ending"]), "interrupted");
            assert_eq!(kinds[4..], ["run_started", "run_ended"], "control");
            assert!(launched, "control");
            continue;
        }
        assert_eq!(
            out.status.code(),
            Some(3),
            "{}{}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr)
        );
        assert_eq!(
            (
                common::s(&reply, &["outcome"]),
                common::s(&reply, &["reason"]),
                common::s(&reply, &["message"]),
                common::s(&reply, &["effects", "run"]),
            ),
            (
                "refused",
                "reference_closed",
                "Close was requested (log/5.json), so no run can start.",
                "not_started"
            )
        );
        assert_eq!(common::s(&reply, &["data", "record"]), "log/5.json");
        assert_eq!(offered(&reply), ["close", "status"]);
        assert!(!launched);
        let closed = closing.unwrap().wait_with_output().unwrap();
        assert_eq!(
            closed.status.code(),
            Some(0),
            "{}",
            String::from_utf8_lossy(&closed.stdout)
        );
        let kinds = p.env.log_kinds(reference);
        assert_eq!(kinds[4], "close_requested");
        assert!(!kinds.iter().any(|k| k == "run_started"), "{kinds:?}");
        // Once the close is settled, the state check refuses the same way.
        let settled = p.env.run(&["run", reference, "--json"]);
        assert_eq!(settled.code, Some(3));
        assert_eq!(common::s(&settled.json(), &["reason"]), "reference_closed");
    }
}

/// A synthetic harness that passes the authentication check, reads the
/// question and starts its session, then, through Stewart's MCP relay at
/// `writer`, initializes and makes two tool calls: `list`, which completes,
/// and `nope`, which is not a tool of the arrangement. Once both replies
/// have arrived it closes its side of the relay, which stays to forward
/// replies, and ends two turns as `two_turns` does.
fn two_tool_calls(writer: &str) -> String {
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
            "printf '%s\\n' '{init}'\n",
            "sleep 0.5\n",
            "{{\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{{\"tools\":{{}}}},\"clientInfo\":{{\"name\":\"fixture\",\"version\":\"1\"}}}}}}'\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}}'\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{{\"name\":\"list\",\"arguments\":{{}}}}}}'\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{{\"name\":\"nope\",\"arguments\":{{}}}}}}'\n",
            "  while ! grep -q '\"id\":3,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n",
            "}} | '{writer}' __stewart-cc-relay m > \"$HOME/mcp-out\" &\n",
            "while ! grep -q '\"id\":3,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n",
            "printf '%s\\n' '{first}'\n",
            "IFS= read -r reminder || exit 0\n",
            "printf '%s\\n' '{second}'\n",
            "while :; do sleep 1; done\n",
        ),
        init = init_event(),
        writer = writer,
        first = result(1),
        second = result(2),
    )
}

/// The result records a harness placement writes for its MCP calls, and the
/// replies it sends, byte for byte: request and attempt 1, the call number
/// as the block, an `mcp-<call>` invocation ID, and the reply's content and
/// error flag as the record states them.
#[test]
fn harness_tool_calls_keep_their_result_records_and_replies() {
    let p = commissioned(&two_tool_calls(common::bin()));
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
    let dir = format!("{}/runs/1", p.env.audit_dir(&p.reference));
    let body = |name: &str| {
        let raw = std::fs::read(format!("{dir}/{name}")).unwrap();
        let record = json::parse(&raw).unwrap();
        let body = common::at(&record, &["body"]);
        String::from_utf8(raw[body.start..body.end].to_vec()).unwrap()
    };
    let results = [body("result-1.json"), body("result-2.json")];
    let mut chunks: Vec<(u64, String)> = std::fs::read_dir(&dir)
        .unwrap()
        .filter_map(|d| {
            let name = d.ok()?.file_name().into_string().ok()?;
            let n = name
                .strip_prefix("runtime-")?
                .strip_suffix("-mcp-out.bin")?;
            Some((n.parse().ok()?, name))
        })
        .collect();
    chunks.sort();
    let sent: Vec<u8> = chunks
        .iter()
        .flat_map(|(_, name)| std::fs::read(format!("{dir}/{name}")).unwrap())
        .collect();
    let sent = String::from_utf8(sent).unwrap();
    assert_eq!(results[0], RESULT_1);
    assert_eq!(results[1], RESULT_2);
    assert_eq!(sent, MCP_OUT);
}

/// The result records of `harness_tool_calls_keep_their_result_records_and_replies`.
const RESULT_1: &str = r#"{"call":1,"request":1,"attempt":1,"block":1,"call_file":"call-1.json","call_bytes":87,"call_sha256":"fcd3575cdfbfe38151c1a3674efbd21aa79c6242cc919394a4ceca05e9319597","tool_use_id":"mcp-1","tool":"list","input_sha256":"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a","replay_of":null,"outcome":"completed","reason":null,"revision":0,"log_record":null,"is_error":false,"content":[{"type":"text","text":"{\"schema\":\"stewart.reply/3\",\"operation\":\"list\",\"outcome\":\"completed\",\"effects\":{\"raw_capture\":\"recorded\"},\"next\":[],\"data\":{\"materials\":[{\"source\":\"materials/note.txt\",\"size\":8,\"lines\":1}],\"directories\":[\"materials\"],\"returned\":1,\"total\":1,\"complete\":true}}"}]}"#;
const RESULT_2: &str = r#"{"call":2,"request":1,"attempt":1,"block":2,"call_file":"call-2.json","call_bytes":87,"call_sha256":"c0c0c0affcabc6a834cf5eb553c28925318a69a0d5ec6e2a09accf1e75272af3","tool_use_id":"mcp-2","tool":"nope","input_sha256":"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a","replay_of":null,"outcome":"refused","reason":"tool_unknown","revision":0,"log_record":null,"is_error":true,"content":[{"type":"text","text":"{\"schema\":\"stewart.reply/3\",\"operation\":\"nope\",\"outcome\":\"refused\",\"reason\":\"tool_unknown\",\"message\":\"No tool is named \\\"nope\\\". The tools are: list, read, search, record_account, record_observation, record_limit, record_artifact, replace, delete, what_am_i_working_with, prepare, submit.\",\"effects\":{\"raw_capture\":\"recorded\"},\"next\":[],\"data\":{\"tool\":\"nope\",\"tools\":[\"list\",\"read\",\"search\",\"record_account\",\"record_observation\",\"record_limit\",\"record_artifact\",\"replace\",\"delete\",\"what_am_i_working_with\",\"prepare\",\"submit\"]}}"}]}"#;
/// What the harness placement sent on its MCP connection: the
/// initialization result and the two tool replies.
const MCP_OUT: &str = concat!(
    r#"{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"stewart","version":"1"}}}"#,
    "\n",
    r#"{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{\"schema\":\"stewart.reply/3\",\"operation\":\"list\",\"outcome\":\"completed\",\"effects\":{\"raw_capture\":\"recorded\"},\"next\":[],\"data\":{\"materials\":[{\"source\":\"materials/note.txt\",\"size\":8,\"lines\":1}],\"directories\":[\"materials\"],\"returned\":1,\"total\":1,\"complete\":true}}"}],"isError":false}}"#,
    "\n",
    r#"{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"schema\":\"stewart.reply/3\",\"operation\":\"nope\",\"outcome\":\"refused\",\"reason\":\"tool_unknown\",\"message\":\"No tool is named \\\"nope\\\". The tools are: list, read, search, record_account, record_observation, record_limit, record_artifact, replace, delete, what_am_i_working_with, prepare, submit.\",\"effects\":{\"raw_capture\":\"recorded\"},\"next\":[],\"data\":{\"tool\":\"nope\",\"tools\":[\"list\",\"read\",\"search\",\"record_account\",\"record_observation\",\"record_limit\",\"record_artifact\",\"replace\",\"delete\",\"what_am_i_working_with\",\"prepare\",\"submit\"]}}"}],"isError":true}}"#,
    "\n",
);

/// A synthetic harness that starts its session and, through Stewart's MCP
/// relay at `writer`, initializes and calls `record_account` once. It keeps
/// its side of the relay open and waits to be stopped.
#[cfg(feature = "fault-injection")]
fn one_recording_call(writer: &str) -> String {
    format!(
        concat!(
            "#!/bin/sh\n",
            "if [ \"$1\" = auth ]; then\n",
            "  printf '{{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"configDirectory\":\"%s\"}}\\n' \"$CLAUDE_CONFIG_DIR\"\n",
            "  exit 0\n",
            "fi\n",
            "IFS= read -r question\n",
            "printf '%s\\n' '{init}'\n",
            "sleep 0.5\n",
            "{{\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{{\"tools\":{{}}}},\"clientInfo\":{{\"name\":\"fixture\",\"version\":\"1\"}}}}}}'\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}}'\n",
            "  printf '%s\\n' '{{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{{\"name\":\"record_account\",\"arguments\":{{\"text\":\"Recorded around a stop.\"}}}}}}'\n",
            "  while :; do sleep 1; done\n",
            "}} | '{writer}' __stewart-cc-relay m > \"$HOME/mcp-out\" &\n",
            "while :; do sleep 1; done\n",
        ),
        init = init_event(),
        writer = writer,
    )
}

/// A stop signal closes the gate of the harness call that is executing
/// (runtime contract). A `record_account` paused just before its entry's
/// link, and released after the harness group is gone and the transport
/// drain interval has elapsed, is refused
/// `placement_stopped`, links nothing and keeps its result record; the
/// placement ends `interrupted` with cause `signal`. The control releases
/// the call before the signal: its entry links and stands, and the same
/// signal then ends the placement the same way.
#[cfg(feature = "fault-injection")]
#[test]
fn a_signal_stops_a_harness_mutation_paused_before_its_link() {
    for signal_first in [true, false] {
        let p = commissioned(&one_recording_call(common::bin()));
        let faults = p.env.path("faults");
        std::fs::create_dir(&faults).unwrap();
        let child = spawned(
            &p.env,
            &["run", &p.reference, "--json"],
            &[
                ("STEWART_TEST_FAULT", "log.publish:entry=pause"),
                ("STEWART_TEST_FAULT_DIR", &faults),
            ],
        );
        let paused = format!("{faults}/log.publish:entry.paused");
        assert!(
            until(|| std::path::Path::new(&paused).exists()),
            "the call never paused before its link (signal first: {signal_first})"
        );
        // SAFETY: sending a signal to our own child process.
        let term = || unsafe { libc::kill(child.id() as i32, libc::SIGTERM) };
        if signal_first {
            assert_eq!(term(), 0);
            let process = format!(
                "{}/runs/1/process-model.json",
                p.env.audit_dir(&p.reference)
            );
            let record = json::parse(&std::fs::read(process).unwrap()).unwrap();
            let group = common::at(&record, &["group"]).as_u64().unwrap() as i32;
            // SAFETY: signal zero observes the fixture's process group.
            assert!(until(|| unsafe { libc::kill(-group, 0) } != 0));
            std::thread::sleep(Duration::from_secs(4));
        }
        std::fs::write(format!("{faults}/log.publish:entry.go"), b"").unwrap();
        if !signal_first {
            assert!(until(|| p
                .env
                .log_kinds(&p.reference)
                .iter()
                .any(|k| k == "entry")));
            assert_eq!(term(), 0);
        }
        let out = child.wait_with_output().unwrap();
        let reply = json::parse(&out.stdout).unwrap_or_else(|e| {
            panic!(
                "{e}: {}{}",
                String::from_utf8_lossy(&out.stdout),
                String::from_utf8_lossy(&out.stderr)
            )
        });
        let kinds = p.env.log_kinds(&p.reference);
        let ended = p.env.log_record(&p.reference, kinds.len());
        assert_eq!(
            (
                out.status.code(),
                common::s(&reply, &["data", "ending"]),
                common::s(&reply, &["data", "cause"]),
            ),
            (Some(5), "interrupted", "signal"),
            "signal first: {signal_first}: {}",
            common::s(&ended, &["body", "message"])
        );
        let raw = std::fs::read(format!(
            "{}/runs/1/result-1.json",
            p.env.audit_dir(&p.reference)
        ))
        .unwrap();
        let result = json::parse(&raw).unwrap();
        let field = |k: &str| {
            common::at(&result, &["body", k])
                .as_str()
                .map(str::to_string)
        };
        if signal_first {
            assert_eq!(
                (field("outcome"), field("reason"), field("log_record")),
                (
                    Some("refused".into()),
                    Some("placement_stopped".into()),
                    None
                )
            );
            assert_eq!(kinds[4..], ["run_started", "run_ended"]);
        } else {
            assert_eq!(
                (field("outcome"), field("reason"), field("log_record")),
                (Some("completed".into()), None, Some("log/6.json".into()))
            );
            assert_eq!(kinds[4..], ["run_started", "entry", "run_ended"]);
        }
    }
}

// ---------------------------------------------------------------------------
// The placement allowance and authoring; advice while stopping is unknown.

/// The operation each next call offers (its `argv[1]`).
fn offered(reply: &json::Json) -> Vec<String> {
    common::at(reply, &["next"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|n| common::s(n, &["argv", "1"]).to_string())
        .collect()
}

/// The headline's authoring observation: its state and `ended_by`.
fn authoring(reply: &json::Json) -> (String, Option<String>) {
    let a = common::at(reply, &["data", "headline", "authoring"]);
    (
        common::s(a, &["state"]).to_string(),
        common::at(a, &["ended_by"]).as_str().map(str::to_string),
    )
}

/// A reply's bytes with this test's locations, binary and reference
/// replaced by fixed names, so that the rest compares byte for byte.
fn normalized_reply(p: &Prepared, stdout: &[u8]) -> String {
    String::from_utf8(stdout.to_vec())
        .unwrap()
        .replace(&p.reference, "<ref>")
        .replace(common::bin(), "<bin>")
        .replace(&p.env.audit_dir(&p.reference), "<audit>")
        .replace(p.env.base.to_str().unwrap(), "<base>")
}

/// The `authoring_ended` refusal a run gives once the final permitted
/// placement's ending at `log/<record>.json` ended authoring as `limit`,
/// with the diagnostic it retains.
fn limit_refusal(record: usize, diagnostic: usize) -> String {
    format!(
        concat!(
            r#"{{"schema":"stewart.reply/3","operation":"run","outcome":"refused","reason":"authoring_ended","#,
            r#""message":"Authoring has ended (limit log/{record}.json), so no run can start; close returns or seals the recorded selection.","#,
            r#""effects":{{"run":"ended","answer":"unchanged","seal":"none","delivery":"none","diagnostic":"durable"}},"#,
            r#""retained":["<audit>/diag/{diagnostic}.json"],"#,
            r#""next":[{{"argv":["<bin>","close","<ref>"],"why":"Close the audit; it seals the recorded selection with manager attribution if no seal exists."}},"#,
            r#"{{"argv":["<bin>","status","<ref>"],"why":"See where the audit stands."}}],"#,
            r#""data":{{"ended_by":"limit","record":"log/{record}.json"}}}}"#,
            "\n"
        ),
        record = record,
        diagnostic = diagnostic
    )
}

/// The final permitted placement's `interrupted` ending ends authoring as
/// `limit`, with its `run_ended` as the establishing record (INTERFACE 1.6;
/// runtime contract, limits). The run and status headlines say so; status
/// keeps the recorded ending, cause and condition, offers close but not run,
/// and says that no placement start remains; a later run refuses
/// `authoring_ended` with the data and next calls of 5.7 step 2 and records
/// nothing. Control: an earlier placement's identical interruption leaves
/// authoring open and run offered.
#[test]
fn the_final_placements_interruption_ends_authoring_as_limit() {
    for placements in [1u64, 2] {
        let p = commissioned_for(RECORDING, placements, 60);
        let r = p.reference.as_str();
        for run in 1..=placements {
            let out = p.env.run(&["run", r, "--json"]);
            assert_eq!(out.code, Some(5), "{}{}", out.text(), out.stderr);
            let reply = out.json();
            assert_eq!(
                (
                    common::s(&reply, &["data", "ending"]),
                    common::s(&reply, &["data", "cause"])
                ),
                ("interrupted", "protocol_anomaly")
            );
            let status = p.env.run(&["status", r, "--json"]).json();
            assert_eq!(common::s(&status, &["data", "condition"]), "interrupted");
            let label = format!("placement {run} of {placements}");
            if run < placements {
                for reply in [&reply, &status] {
                    assert_eq!(authoring(reply), ("open".into(), None), "{label}");
                    assert_eq!(offered(reply), ["run", "close"], "{label}");
                }
                continue;
            }
            for reply in [&reply, &status] {
                assert_eq!(
                    authoring(reply),
                    ("ended".into(), Some("limit".into())),
                    "{label}"
                );
                assert_eq!(offered(reply), ["close"], "{label}");
                let summary = common::s(reply, &["data", "summary"]);
                for line in [
                    format!("{placements} used of {placements}; 0 remain."),
                    format!(
                        "Run {run} was interrupted; the answer is not submitted. No further runtime placement can start: the placement allowance is exhausted. Close seals the recorded selection with manager attribution."
                    ),
                    "Authoring ended when an audit limit was reached.".to_string(),
                ] {
                    assert!(summary.contains(&line), "{label}: {line:?} in {summary}");
                }
            }
            assert_eq!(
                common::s(&status, &["next", "0", "why"]),
                "Close the audit; it seals the recorded selection with manager attribution."
            );
            let last = common::at(&status, &["data", "runs", "last"]);
            assert_eq!(
                (common::s(last, &["ending"]), common::s(last, &["cause"])),
                ("interrupted", "protocol_anomaly")
            );
            let kinds = p.env.log_kinds(r);
            assert_eq!(kinds.last().unwrap(), "run_ended");
            let refused = p.env.run(&["run", r, "--json"]);
            assert_eq!(refused.code, Some(3), "{label}");
            assert_eq!(
                normalized_reply(&p, &refused.stdout),
                limit_refusal(kinds.len(), 1),
                "{label}"
            );
            assert_eq!(
                p.env.log_kinds(r),
                kinds,
                "{label}: the refusal records nothing"
            );
        }
    }
}

/// A synthetic harness that passes the authentication check and then
/// neither reads nor writes, so only the placement deadline stops it.
const SILENT: &str = concat!(
    "#!/bin/sh\n",
    "if [ \"$1\" = auth ]; then\n",
    "  printf '{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"configDirectory\":\"%s\"}\\n' \"$CLAUDE_CONFIG_DIR\"\n",
    "  exit 0\n",
    "fi\n",
    "while :; do sleep 1; done\n",
);

/// A deadline interrupts an earlier placement with `placement_deadline`,
/// leaving authoring open, and still ends the final permitted placement
/// `limit_reached`, whose `run_ended` ends authoring as `limit` with the
/// condition `limit_reached` (runtime contract, limits).
#[test]
fn a_deadline_on_the_final_placement_still_reaches_the_limit() {
    let p = commissioned_for(SILENT, 2, 1);
    let r = p.reference.as_str();
    for (run, ending, cause, code) in [
        (1, "interrupted", Some("placement_deadline"), 5),
        (2, "limit_reached", None, 0),
    ] {
        let out = p.env.run(&["run", r, "--json"]);
        assert_eq!(out.code, Some(code), "{}{}", out.text(), out.stderr);
        let reply = out.json();
        assert_eq!(
            (
                common::s(&reply, &["data", "ending"]),
                common::at(&reply, &["data", "cause"]).as_str()
            ),
            (ending, cause),
            "placement {run}"
        );
        let status = p.env.run(&["status", r, "--json"]).json();
        if run == 1 {
            assert_eq!(authoring(&status), ("open".into(), None));
            assert_eq!(offered(&status), ["run", "close"]);
            continue;
        }
        assert_eq!(common::s(&status, &["data", "condition"]), "limit_reached");
        for reply in [&reply, &status] {
            assert_eq!(authoring(reply), ("ended".into(), Some("limit".into())));
            assert_eq!(offered(reply), ["close"]);
        }
        let kinds = p.env.log_kinds(r);
        let refused = p.env.run(&["run", r, "--json"]);
        assert_eq!(refused.code, Some(3));
        assert_eq!(
            normalized_reply(&p, &refused.stdout),
            limit_refusal(kinds.len(), 1)
        );
    }
}

/// When the final permitted placement's process is gone without a
/// `run_ended`, run first records its ending (`interrupted`, cause
/// `process_gone`), keeps that record, and refuses `authoring_ended`
/// without starting anything; that record ended authoring as `limit`, as
/// status and a later run show (runtime contract, limits).
#[cfg(feature = "fault-injection")]
#[test]
fn a_gone_final_placement_is_recorded_and_then_refused() {
    let p = commissioned_for(RECORDING, 1, 60);
    let r = p.reference.as_str();
    let linked = p.env.run_env(
        &["run", r, "--json"],
        &[("STEWART_TEST_FAULT", "log.dirsync:run_started=eio")],
    );
    assert_eq!(linked.code, Some(4), "{}", linked.text());
    assert_eq!(p.env.log_kinds(r)[4..], ["run_started"]);
    let out = p.env.run(&["run", r, "--json"]);
    assert_eq!(out.code, Some(3), "{}{}", out.text(), out.stderr);
    assert_eq!(common::s(&out.json(), &["reason"]), "authoring_ended");
    assert_eq!(p.env.log_kinds(r)[4..], ["run_started", "run_ended"]);
    let gone = p.env.log_record(r, 6);
    assert_eq!(
        (
            common::at(&gone, &["body", "run"]).as_u64(),
            common::s(&gone, &["body", "ending"]),
            common::s(&gone, &["body", "cause"]),
            common::s(&gone, &["body", "recorded_by"]),
        ),
        (Some(1), "interrupted", "process_gone", "run")
    );
    assert!(!std::path::Path::new(&p.env.path("home/observed")).exists());
    let status = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(common::s(&status, &["data", "condition"]), "interrupted");
    assert_eq!(authoring(&status), ("ended".into(), Some("limit".into())));
    assert_eq!(offered(&status), ["close"]);
    let again = p.env.run(&["run", r, "--json"]);
    assert_eq!(again.code, Some(3));
    let diagnostics = std::fs::read_dir(format!("{}/diag", p.env.audit_dir(r)))
        .unwrap()
        .count();
    assert_eq!(
        normalized_reply(&p, &again.stdout),
        limit_refusal(6, diagnostics)
    );
}

/// A synthetic harness that fails its authentication check at once, as
/// `RECORDING` does, unless `$HOME/hold` exists: then it reports itself
/// ready in `$HOME/ready` and waits for `$HOME/go` before failing.
const HELD: &str = concat!(
    "#!/bin/sh\n",
    "if [ -e \"$HOME/hold\" ]; then\n",
    "  : > \"$HOME/ready\"\n",
    "  while [ ! -e \"$HOME/go\" ]; do sleep 0.05; done\n",
    "fi\n",
    "exit 1\n",
);

/// A process group of its own that stays alive until dropped.
struct LiveGroup(std::process::Child);

impl LiveGroup {
    fn start() -> LiveGroup {
        use std::os::unix::process::CommandExt;
        LiveGroup(
            std::process::Command::new("sleep")
                .arg("120")
                .process_group(0)
                .spawn()
                .unwrap(),
        )
    }
    fn id(&self) -> u32 {
        self.0.id()
    }
}

impl Drop for LiveGroup {
    fn drop(&mut self) {
        // SAFETY: signalling the process group this test started.
        unsafe { libc::kill(-(self.0.id() as i32), libc::SIGKILL) };
        let _ = self.0.wait();
    }
}

/// While a placement's launched process groups are not observed absent,
/// run and close would refuse `runtime_stop_unknown`, so the run reply and
/// status offer only status, and their summaries name that placement
/// (runtime contract, harness accounting record). Placement 1's stop
/// observation is replaced by one naming a live group while placement 2
/// runs. Controls: before that, both offer run and close, and status during
/// placement 2 gives the live run's ordinary advice, since its owner
/// observes its stopping; once the group is gone, status offers run and
/// close again.
#[test]
fn unknown_stopping_offers_only_status_until_it_is_observed() {
    let p = commissioned_for(HELD, 3, 60);
    let r = p.reference.as_str();
    let line =
        "Stopping of placement 1 is unknown: its launched process groups were not observed absent.";
    let first = p.env.run(&["run", r, "--json"]);
    assert_eq!(first.code, Some(5), "{}{}", first.text(), first.stderr);
    let status = p.env.run(&["status", r, "--json"]).json();
    for reply in [&first.json(), &status] {
        assert_eq!(offered(reply), ["run", "close"]);
        assert!(!common::s(reply, &["data", "summary"]).contains("Stopping of"));
    }

    std::fs::write(p.env.path("home/hold"), b"").unwrap();
    let second = std::process::Command::new(common::bin())
        .args(["run", r, "--json"])
        .current_dir(&p.env.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    let ready = std::path::Path::new(&p.env.path("home/ready")).to_path_buf();
    let start = Instant::now();
    while !ready.exists() {
        assert!(
            start.elapsed() < Duration::from_secs(30),
            "placement 2 never started"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
    let live = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(common::s(&live, &["data", "condition"]), "run_active");
    assert_eq!(offered(&live), ["status", "close"]);
    assert!(!common::s(&live, &["data", "summary"]).contains("Stopping of"));
    let group = LiveGroup::start();
    let runs1 = format!("{}/runs/1", p.env.audit_dir(r));
    std::fs::remove_file(format!("{runs1}/runtime-stop.json")).unwrap();
    std::fs::write(
        format!("{runs1}/runtime-stop.json"),
        r#"{"elapsed_ms":1,"deadline_ms":60000,"groups_gone":false}"#,
    )
    .unwrap();
    std::fs::write(
        format!("{runs1}/process-model.json"),
        format!(
            r#"{{"schema":"stewart.claude-code.process/1","group":{},"role":"model"}}"#,
            group.id()
        ),
    )
    .unwrap();
    // Placement 1 now blocks run and close, and placement 2 is still live.
    let live = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(common::s(&live, &["data", "condition"]), "run_active");
    assert_eq!(offered(&live), ["status"]);
    assert!(common::s(&live, &["data", "summary"]).contains(line));
    std::fs::write(p.env.path("home/go"), b"").unwrap();
    let out = second.wait_with_output().unwrap();
    let reply = json::parse(&out.stdout).unwrap_or_else(|e| {
        panic!(
            "{e}: {}{}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr)
        )
    });
    assert_eq!(out.status.code(), Some(5));
    assert_eq!(common::at(&reply, &["data", "run"]).as_u64(), Some(2));
    let status = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(common::s(&status, &["data", "condition"]), "interrupted");
    for reply in [&reply, &status] {
        assert_eq!(offered(reply), ["status"]);
        assert!(
            common::s(reply, &["next", "0", "why"]).starts_with("Observe stopping again;"),
            "{}",
            common::s(reply, &["next", "0", "why"])
        );
        let summary = common::s(reply, &["data", "summary"]);
        assert!(summary.contains(line), "{summary}");
        assert!(!summary.contains("placement 2 is unknown"), "{summary}");
        assert!(!summary.contains("Run continues"), "{summary}");
    }
    // The advice describes what run would do, and its refusal offers the
    // same next call.
    let refused = p.env.run(&["run", r, "--json"]);
    assert_eq!(
        common::s(&refused.json(), &["reason"]),
        "runtime_stop_unknown"
    );
    assert_eq!(offered(&refused.json()), ["status"]);

    drop(group);
    let status = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(offered(&status), ["run", "close"]);
    assert!(!common::s(&status, &["data", "summary"]).contains("Stopping of"));
}

// ---------------------------------------------------------------------------
// A placement's ending is decided by the first stopping condition its owner
// observes; the launch directory is checked before a start is reserved; a
// notice is `sent` only once captured and written in full; the private
// launch directory goes once stopping is observed; and a condition with no
// other cause ends `interrupted` with cause `protocol_anomaly` (runtime
// contract).

/// The authentication leg every synthetic harness below passes.
const AUTH_LEG: &str = concat!(
    "#!/bin/sh\n",
    "if [ \"$1\" = auth ]; then\n",
    "  printf '{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"configDirectory\":\"%s\"}\\n' \"$CLAUDE_CONFIG_DIR\"\n",
    "  exit 0\n",
    "fi\n",
);

/// A shell line that prints `line`, which holds no single quote.
fn emit(line: &str) -> String {
    assert!(!line.contains('\''));
    format!("printf '%s\\n' '{line}'\n")
}

/// A harness `result` event ending turn `turns`.
fn result_event(turns: u64, error: bool) -> String {
    format!(
        r#"{{"type":"result","session_id":"s1","is_error":{error},"num_turns":{turns},"usage":{{"input_tokens":{turns},"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":{turns}}}}}"#
    )
}

const QUOTA_REJECTED: &str =
    r#"{"type":"rate_limit_event","rate_limit_info":{"status":"rejected"}}"#;

/// Front matter for `max` placements of `timeout` seconds each.
fn placements(max: u64, timeout: u64) -> impl Fn(&common::Env) -> String {
    move |env: &common::Env| {
        format!(
            "runtime-profile: {}\nmax-placements: {max}\nplacement-timeout-seconds: {timeout}\n",
            env.path("profile.json")
        )
    }
}

/// The runtime refuses a launch directory under project instructions, so
/// these cases need a scratch directory outside any such tree.
fn require_clean_scratch(p: &Prepared) {
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
}

/// `Prepared::profile` for this surface, with `temporary_directory` in
/// place of the folder's `tmp`.
fn profile_with_temporary_directory(p: &Prepared, temporary_directory: &str) {
    let digest = stewart::util::sha256_hex;
    let executable = digest(p.executable.as_bytes());
    let launch = format!(
        r#"{{"executable":"{}","sha256":"{executable}","version":"2.1.322","platform":"{}-{}","config_directory":"{}","home":"{}","temporary_directory":"{temporary_directory}"}}"#,
        p.env.path("harness"),
        std::env::consts::OS,
        std::env::consts::ARCH,
        p.env.path("config"),
        p.env.path("home"),
    );
    let family = stewart::forms::family("open-inquiry").unwrap();
    let tools = stewart::claude_code::mcp_tools(&stewart::forms::tools(family).bytes()).unwrap();
    let profile = format!(
        r#"{{"schema":"stewart.claude-code.profile/2","launch":{launch},"installation":{{"manifest_sha256":"{}","signer":"31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE","binary_sha256":"{executable}"}},"check":{{"surface_sha256":"{SURFACE_SHA256}","launch_sha256":"{}","tools_sha256":"{}","model":"fixture-model","checked_at":"2026-11-11","evidence_sha256":"{}","outcome":"observed"}}}}"#,
        "1".repeat(64),
        digest(launch.as_bytes()),
        digest(&tools),
        "2".repeat(64),
    );
    std::fs::write(p.env.path("profile.json"), profile).unwrap();
}

/// A commissioned audit with `fields` whose harness is `script(p)`, which
/// may use the audit's paths. `temporary_directory` defaults to `tmp`.
fn commissioned_harness(
    fields: &dyn Fn(&common::Env) -> String,
    temporary_directory: Option<&dyn Fn(&common::Env) -> String>,
    script: &dyn Fn(&Prepared) -> String,
) -> Prepared {
    let mut p = Prepared::with(INERT, fields);
    require_clean_scratch(&p);
    p.executable = script(&p);
    std::fs::write(p.env.path("harness"), &p.executable).unwrap();
    let tmp = temporary_directory.map_or_else(|| p.env.path("tmp"), |t| t(&p.env));
    profile_with_temporary_directory(&p, &tmp);
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let out = p
        .env
        .commission(&p.reference, common::s(&out.json(), &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    p
}

/// `stewart args` for `p`, started in the background with its output piped.
fn started(p: &Prepared, args: &[&str]) -> std::process::Child {
    std::process::Command::new(common::bin())
        .args(args)
        .current_dir(&p.env.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap()
}

/// The exit status and JSON reply of a started process.
fn finished(child: std::process::Child) -> (Option<i32>, json::Json) {
    let out = child.wait_with_output().unwrap();
    let reply = json::parse(&out.stdout).unwrap_or_else(|e| {
        panic!(
            "{e}: {}{}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr)
        )
    });
    (out.status.code(), reply)
}

/// Wait up to `seconds` for `ready`.
fn within(seconds: u64, ready: impl Fn() -> bool) -> bool {
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(seconds) {
        if ready() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    false
}

fn exists(path: &str) -> bool {
    std::path::Path::new(path).exists()
}

fn signal(child: &std::process::Child, sig: libc::c_int) {
    // SAFETY: signalling our own child process.
    assert_eq!(unsafe { libc::kill(child.id() as i32, sig) }, 0);
}

/// The last `run_ended` record of `p`'s log.
fn last_run_ended(p: &Prepared) -> json::Json {
    let kinds = p.env.log_kinds(&p.reference);
    let n = kinds
        .iter()
        .rposition(|k| k == "run_ended")
        .expect("a run_ended")
        + 1;
    p.env.log_record(&p.reference, n)
}

/// Status's authoring headline: its state and what ended it.
fn authoring_of(p: &Prepared) -> (String, Option<String>) {
    let status = p.env.run(&["status", &p.reference, "--json"]).json();
    let a = common::at(&status, &["data", "headline", "authoring"]);
    (
        common::s(a, &["state"]).to_string(),
        common::at(a, &["ended_by"]).as_str().map(str::to_string),
    )
}

/// What is left in the profile's temporary directory.
fn left_in_tmp(p: &Prepared) -> Vec<String> {
    std::fs::read_dir(p.env.path("tmp"))
        .unwrap()
        .map(|e| e.unwrap().file_name().into_string().unwrap())
        .collect()
}

/// A harness that ends two turns around the reminder, as `two_turns` does,
/// ignoring TERM. `gated` makes it wait for `home/go` after reading the
/// reminder. After its second result it reads its input to the end, which
/// comes only once the placement's owner has decided the ending and closed
/// the harness's input, and then notes `home/decided`.
fn ordinary_ending(gated: bool) -> String {
    let mut s = String::from(AUTH_LEG);
    s += "trap '' TERM INT HUP\nIFS= read -r question\n";
    s += &emit(&init_event());
    s += &emit(&result_event(1, false));
    s += "IFS= read -r reminder\n";
    if gated {
        s += ": > \"$HOME/reminder-read\"\nwhile [ ! -e \"$HOME/go\" ]; do sleep 0.05; done\n";
    }
    s += &emit(&result_event(2, false));
    s += "while IFS= read -r more; do :; done\n: > \"$HOME/decided\"\nwhile :; do sleep 1; done\n";
    s
}

/// R1. A signal or close the owner observes only after it decided an
/// ordinary ending, while it stops the harness, leaves that ending: the run
/// ends `ended_unsubmitted` with exit 0, and a close still ends authoring
/// through its own record. Firing control: the same placement with no stop.
/// Invariance: a signal or close observed before the second result decides
/// the ending itself. The private launch directory is removed each time.
#[test]
fn a_signal_or_close_observed_after_an_ordinary_ending_leaves_it() {
    // (case, gated, stop, ending, cause, exit, authoring state, ended_by)
    let cases: [(&str, bool, &str, &str, Option<&str>, i32, &str, &str); 5] = [
        (
            "no stop",
            false,
            "none",
            "ended_unsubmitted",
            None,
            0,
            "ended",
            "ordinary_ending",
        ),
        (
            "signal after the ending",
            false,
            "signal",
            "ended_unsubmitted",
            None,
            0,
            "ended",
            "ordinary_ending",
        ),
        (
            "signal before the ending",
            true,
            "signal",
            "interrupted",
            Some("signal"),
            5,
            "open",
            "",
        ),
        (
            "close after the ending",
            false,
            "close",
            "ended_unsubmitted",
            None,
            0,
            "ended",
            "close",
        ),
        (
            "close before the ending",
            true,
            "close",
            "stopped_by_close",
            None,
            0,
            "ended",
            "close",
        ),
    ];
    std::thread::scope(|scope| {
        for (case, gated, stop, ending, cause, exit, state, ended_by) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|_| ordinary_ending(gated));
                let run = started(&p, &["run", &p.reference, "--json"]);
                let home = |f: &str| p.env.path(&format!("home/{f}"));
                let mut close = None;
                if stop != "none" {
                    let marker = if gated { "reminder-read" } else { "decided" };
                    assert!(within(30, || exists(&home(marker))), "{case}: no {marker}");
                    if stop == "signal" {
                        signal(&run, libc::SIGTERM);
                        if gated {
                            std::thread::sleep(Duration::from_secs(1));
                            std::fs::write(home("go"), b"").unwrap();
                        }
                    } else {
                        close = Some(started(&p, &["close", &p.reference, "--json"]));
                    }
                }
                let (code, reply) = finished(run);
                let ended = last_run_ended(&p);
                assert_eq!(
                    (
                        code,
                        common::s(&reply, &["data", "ending"]),
                        common::at(&reply, &["data", "cause"]).as_str(),
                    ),
                    (Some(exit), ending, cause),
                    "{case}: {}",
                    common::s(&ended, &["body", "message"])
                );
                assert_eq!(common::s(&ended, &["body", "ending"]), ending, "{case}");
                assert_eq!(common::s(&ended, &["body", "recorded_by"]), "run", "{case}");
                if let Some(close) = close {
                    let (code, reply) = finished(close);
                    assert_eq!(code, Some(0), "{case}: {}", common::s(&reply, &["message"]));
                }
                let (now, by) = authoring_of(&p);
                assert_eq!(now, state, "{case}");
                assert_eq!(by.as_deref().unwrap_or(""), ended_by, "{case}");
                assert_eq!(left_in_tmp(&p), Vec::<String>::new(), "{case}");
            });
        }
    });
}

/// A harness that starts its session, waits for `home/go`, then reports
/// that the subscription quota rejected the placement and ignores TERM.
fn rejected_on_go() -> String {
    let mut s = String::from(AUTH_LEG);
    s += "trap '' TERM INT HUP\nIFS= read -r question\n";
    s += &emit(&init_event());
    s += "while [ ! -e \"$HOME/go\" ]; do sleep 0.05; done\n";
    s += &emit(QUOTA_REJECTED);
    s += "while :; do sleep 1; done\n";
    s
}

/// R1b. A quota rejection observed 1.5 s before the deadline decides the
/// ending, `interrupted` with cause `protocol_anomaly`, although stopping
/// the harness takes at least the supervisor's 2 s grace, so the deadline
/// has passed when the owner records the ending. Control: a rejection well
/// before the deadline ends the same way. Invariance: with no rejection the
/// deadline decides, `interrupted` with cause `placement_deadline`.
#[test]
fn a_deadline_passing_while_the_harness_stops_does_not_replace_the_cause() {
    const TIMEOUT: u64 = 10;
    // (case, go after the reservation, cause, past the deadline at exit)
    let cases: [(&str, Option<Duration>, &str, bool); 3] = [
        (
            "rejected 1.5 s before the deadline",
            Some(Duration::from_millis(TIMEOUT * 1000 - 1500)),
            "protocol_anomaly",
            true,
        ),
        (
            "rejected at once",
            Some(Duration::ZERO),
            "protocol_anomaly",
            false,
        ),
        ("never rejected", None, "placement_deadline", true),
    ];
    std::thread::scope(|scope| {
        for (case, go, cause, late) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, TIMEOUT), None, &|_| rejected_on_go());
                let run = started(&p, &["run", &p.reference, "--json"]);
                assert!(
                    within(30, || p
                        .env
                        .log_kinds(&p.reference)
                        .iter()
                        .any(|k| k == "run_started")),
                    "{case}: no reservation"
                );
                // The deadline counts from before the reservation was linked.
                let reserved = Instant::now();
                if let Some(go) = go {
                    std::thread::sleep(go);
                    std::fs::write(p.env.path("home/go"), b"").unwrap();
                }
                let (code, reply) = finished(run);
                let elapsed = reserved.elapsed();
                let ended = last_run_ended(&p);
                assert_eq!(
                    (
                        code,
                        common::s(&reply, &["data", "ending"]),
                        common::s(&reply, &["data", "cause"]),
                    ),
                    (Some(5), "interrupted", cause),
                    "{case}: {}",
                    common::s(&ended, &["body", "message"])
                );
                assert_eq!(common::s(&ended, &["body", "cause"]), cause, "{case}");
                // The measured case reaches the condition it is about: the
                // run ended after the deadline.
                assert_eq!(
                    elapsed > Duration::from_secs(TIMEOUT),
                    late,
                    "{case}: {elapsed:?}"
                );
                assert_eq!(authoring_of(&p).0, "open", "{case}");
            });
        }
    });
}

/// `two_turns`, with `setup` run once the harness has read the question.
fn two_turns_after(setup: &str) -> String {
    two_turns().replacen(
        "IFS= read -r question\n",
        &format!("IFS= read -r question\n{setup}"),
        1,
    )
}

/// A failure to retain `runtime-stop.json`, observed after the placement
/// ended ordinarily, leaves stopping unknown with its diagnostic and leaves
/// the ending. Here the harness put a stop observation in the way. Control:
/// the same placement retains its stop observation. Invariance: a capture
/// failure observed while the placement runs decides `archive_write_failed`,
/// and the reminder it never captured is `not_sent`.
#[test]
fn a_stop_observation_that_cannot_be_retained_leaves_the_ending() {
    let planted = r#"{"elapsed_ms":0,"deadline_ms":60000,"groups_gone":false}"#;
    // (case, setup, ending, cause, exit, stopped, notice sent)
    let cases: [(&str, &str, &str, Option<&str>, i32, u64, &str); 3] = [
        ("retained", "", "ended_unsubmitted", None, 0, 1, "sent"),
        (
            "stop observation in the way",
            "stop",
            "ended_unsubmitted",
            None,
            0,
            0,
            "sent",
        ),
        (
            "capture in the way",
            "capture",
            "interrupted",
            Some("archive_write_failed"),
            5,
            1,
            "not_sent",
        ),
    ];
    std::thread::scope(|scope| {
        for (case, setup, ending, cause, exit, stopped, sent) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|p| {
                    let runs = format!("{}/runs/1", p.env.audit_dir(&p.reference));
                    two_turns_after(&match setup {
                        "stop" => format!("printf '%s' '{planted}' > '{runs}/runtime-stop.json'\n"),
                        // Every later input capture name is taken.
                        "capture" => format!(
                            "i=2; while [ \"$i\" -le 400 ]; do : > '{runs}/runtime-'\"$i\"'-input.bin'; i=$((i+1)); done\n"
                        ),
                        _ => String::new(),
                    })
                });
                let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"]));
                let ended = last_run_ended(&p);
                let message = common::s(&ended, &["body", "message"]);
                assert_eq!(
                    (
                        code,
                        common::s(&reply, &["data", "ending"]),
                        common::at(&reply, &["data", "cause"]).as_str(),
                    ),
                    (Some(exit), ending, cause),
                    "{case}: {message}"
                );
                assert_eq!(
                    common::at(&ended, &["body", "usage", "stopped"]).as_u64(),
                    Some(stopped),
                    "{case}: {message}"
                );
                assert_eq!(
                    common::s(&ended, &["body", "notices", "0", "sent"]),
                    sent,
                    "{case}"
                );
                let stop = std::fs::read_to_string(format!(
                    "{}/runs/1/runtime-stop.json",
                    p.env.audit_dir(&p.reference)
                ))
                .unwrap();
                if setup == "stop" {
                    assert_eq!(stop, planted);
                    assert!(
                        message.contains("Stop observation could not be retained"),
                        "{message}"
                    );
                } else {
                    assert!(stop.contains(r#""groups_gone":true"#), "{case}: {stop}");
                    assert!(!message.contains("could not be retained"), "{case}: {message}");
                }
            });
        }
    });
}

/// A harness whose first placement ends its first turn with its input
/// closed and its supervisor gone, so nothing reads what Stewart writes
/// next, and exits. Its second placement waits for the near-limit notice
/// and exits once it has read it.
fn input_closed_then_near_limit() -> String {
    let mut s = String::from(AUTH_LEG);
    s += "IFS= read -r question\n";
    s += "if [ ! -e \"$HOME/first\" ]; then\n  : > \"$HOME/first\"\n";
    s += &format!("  {}", emit(&init_event()));
    s += "  exec 0<&-\n  kill -9 \"$PPID\"\n  sleep 0.2\n";
    s += &format!("  {}", emit(&result_event(1, false)));
    s += "  exit 0\nfi\nIFS= read -r continuation\n";
    s += &emit(&init_event());
    s += "IFS= read -r notice\n: > \"$HOME/notice-read\"\nexit 0\n";
    s
}

/// A reminder captured completely whose write to the harness failed is
/// listed `unknown`, not `not_sent`; the write failure has no other cause,
/// so the placement ends `interrupted` (`protocol_anomaly`). The next
/// placement's near-limit notice, written in full, is `sent` (control), and
/// each notice's `request` is its position among its own placement's
/// notices: 1 in both.
#[test]
fn a_notice_whose_write_failed_after_its_capture_is_unknown() {
    let p = commissioned_harness(&placements(2, 10), None, &|_| {
        input_closed_then_near_limit()
    });
    let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"]));
    let ended = last_run_ended(&p);
    let message = common::s(&ended, &["body", "message"]).to_string();
    assert_eq!(
        (code, common::s(&reply, &["data", "cause"])),
        (Some(5), "protocol_anomaly"),
        "{message}"
    );
    assert!(message.contains("input write failed"), "{message}");
    let kinds = p.env.log_kinds(&p.reference);
    assert_eq!(kinds[4..], ["run_started", "notice", "run_ended"]);
    let reminder = p.env.log_record(&p.reference, 6);
    assert_eq!(common::s(&reminder, &["body", "type"]), "reminder");
    assert_eq!(
        common::at(&reminder, &["body", "request"]).as_u64(),
        Some(1)
    );
    // The frame was captured completely before the write was tried.
    let dir = format!("{}/runs/1", p.env.audit_dir(&p.reference));
    let text = common::s(&reminder, &["body", "text"]);
    let frame = std::fs::read_dir(&dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().into_string().unwrap())
        .filter(|n| n.ends_with("-input.bin"))
        .map(|n| std::fs::read(format!("{dir}/{n}")).unwrap())
        .find(|b| String::from_utf8_lossy(b).contains(text));
    assert!(frame.is_some(), "no complete capture of the reminder");
    assert_eq!(
        common::s(&ended, &["body", "notices", "0", "sent"]),
        "unknown"
    );
    assert_eq!(
        common::s(&reply, &["data", "notices", "0", "sent"]),
        "unknown"
    );

    let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"]));
    assert!(exists(&p.env.path("home/notice-read")));
    let ended = last_run_ended(&p);
    assert_eq!(
        (code, common::s(&reply, &["data", "cause"])),
        (Some(5), "protocol_anomaly"),
        "{}",
        common::s(&ended, &["body", "message"])
    );
    let kinds = p.env.log_kinds(&p.reference);
    assert_eq!(
        kinds[4..],
        [
            "run_started",
            "notice",
            "run_ended",
            "run_started",
            "notice",
            "run_ended"
        ]
    );
    let near = p.env.log_record(&p.reference, 9);
    assert_eq!(common::s(&near, &["body", "type"]), "near_limit");
    assert_eq!(common::at(&near, &["body", "run"]).as_u64(), Some(2));
    assert_eq!(common::at(&near, &["body", "request"]).as_u64(), Some(1));
    assert_eq!(common::s(&ended, &["body", "notices", "0", "sent"]), "sent");
}

/// A harness that waits for the near-limit notice, ends a turn, reads the
/// reminder, notes `home/both` and then ignores TERM until it is killed.
fn both_notices() -> String {
    let mut s = String::from(AUTH_LEG);
    s += "trap '' TERM INT HUP\nIFS= read -r question\n";
    s += &emit(&init_event());
    s += "IFS= read -r near\n";
    s += &emit(&result_event(1, false));
    s += "IFS= read -r reminder\n: > \"$HOME/both\"\nwhile :; do sleep 1; done\n";
    s
}

/// A placement's notices are numbered 1 and 2 in log order. When the owner
/// records the ending, both are `sent`. When the owner is killed, the
/// placement reconciled later has no transmission observation, and every
/// claimed notice is `unknown`.
#[test]
fn a_reconciled_placement_lists_every_claimed_notice_as_unknown() {
    std::thread::scope(|scope| {
        for (case, sig, sent) in [
            ("owner recorded", libc::SIGTERM, "sent"),
            ("reconciled", libc::SIGKILL, "unknown"),
        ] {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 10), None, &|_| both_notices());
                let run = started(&p, &["run", &p.reference, "--json"]);
                assert!(within(30, || exists(&p.env.path("home/both"))), "{case}");
                signal(&run, sig);
                let out = run.wait_with_output().unwrap();
                if sig == libc::SIGKILL {
                    // The supervisor stops the group once its owner is gone.
                    let process = format!(
                        "{}/runs/1/process-model.json",
                        p.env.audit_dir(&p.reference)
                    );
                    let record = json::parse(&std::fs::read(process).unwrap()).unwrap();
                    let group = common::at(&record, &["group"]).as_u64().unwrap() as i32;
                    // SAFETY: signal zero only observes the group.
                    assert!(within(20, || unsafe { libc::kill(-group, 0) } != 0));
                    let closed = p.env.run(&["close", &p.reference, "--json"]);
                    assert_eq!(closed.code, Some(0), "{}{}", closed.text(), closed.stderr);
                } else {
                    assert_eq!(out.status.code(), Some(5), "{case}");
                }
                let kinds = p.env.log_kinds(&p.reference);
                assert_eq!(kinds[4..7], ["run_started", "notice", "notice"], "{case}");
                for (n, kind, request) in [(6, "near_limit", 1), (7, "reminder", 2)] {
                    let notice = p.env.log_record(&p.reference, n);
                    assert_eq!(common::s(&notice, &["body", "type"]), kind, "{case}");
                    assert_eq!(
                        common::at(&notice, &["body", "request"]).as_u64(),
                        Some(request),
                        "{case}"
                    );
                }
                let ended = last_run_ended(&p);
                let recorded_by = if sig == libc::SIGKILL { "close" } else { "run" };
                assert_eq!(
                    common::s(&ended, &["body", "recorded_by"]),
                    recorded_by,
                    "{case}"
                );
                for i in ["0", "1"] {
                    assert_eq!(
                        common::s(&ended, &["body", "notices", i, "sent"]),
                        sent,
                        "{case}: {}",
                        common::s(&ended, &["body", "message"])
                    );
                }
            });
        }
    });
}

/// A stopping condition the contract gives no other cause decides the
/// ending `interrupted` with cause `protocol_anomaly`: an error result, the
/// harness's exit, a quota rejection and a frame that is not JSON. Each
/// keeps authoring open while starts remain.
#[test]
fn a_condition_with_no_other_cause_ends_with_a_protocol_anomaly() {
    let cases = [
        ("error result", emit(&result_event(1, true))),
        ("harness exit", "exit 0\n".to_string()),
        ("quota rejection", emit(QUOTA_REJECTED)),
        ("frame that is not JSON", emit("not json")),
    ];
    std::thread::scope(|scope| {
        for (case, then) in &cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|_| {
                    format!(
                        "{AUTH_LEG}IFS= read -r question\n{}{then}while :; do sleep 1; done\n",
                        emit(&init_event())
                    )
                });
                let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"]));
                let ended = last_run_ended(&p);
                assert_eq!(
                    (
                        code,
                        common::s(&reply, &["data", "ending"]),
                        common::s(&reply, &["data", "cause"]),
                    ),
                    (Some(5), "interrupted", "protocol_anomaly"),
                    "{case}: {}",
                    common::s(&ended, &["body", "message"])
                );
                assert_eq!(authoring_of(&p).0, "open", "{case}");
            });
        }
    });
}

/// `run` checks the profile's temporary directory before it reserves a
/// start: an entry named `.git`, `CLAUDE.md`, `AGENTS.md` or `.claude` in it
/// or an ancestor, an ancestor it cannot inspect, or a directory that is or
/// lies within the archive or the submission folder refuses
/// `runtime_profile_invalid` with the surface report, and uses no start and
/// launches nothing. Invariance: on the same audit, a temporary directory
/// that passes these checks but is missing when the fresh directory is made
/// uses its start, which ends `interrupted` (`protocol_anomaly`). Control:
/// once the directory is back, the run starts and launches the harness, and
/// its fresh directory is removed once stopping is observed.
#[test]
fn a_temporary_directory_that_cannot_hold_the_launch_refuses_before_a_start() {
    let p = commissioned_harness(&placements(2, 60), None, &|_| RECORDING.to_string());
    let reference = p.reference.as_str();
    let tmp = p.env.path("tmp");
    let launched = || exists(&p.env.path("home/observed"));
    let refused = |case: &str| {
        let out = p.env.run(&["run", reference, "--json"]);
        let reply = out.json();
        assert_eq!(out.code, Some(3), "{case}: {}{}", out.text(), out.stderr);
        assert_eq!(
            (
                common::s(&reply, &["outcome"]),
                common::s(&reply, &["reason"]),
                common::s(&reply, &["effects", "run"]),
            ),
            ("refused", "runtime_profile_invalid", "not_started"),
            "{case}"
        );
        assert!(
            common::s(&reply, &["message"]).contains("No placement start was used"),
            "{case}"
        );
        assert_eq!(
            reported_surface(&out),
            (SURFACE.as_bytes().to_vec(), SURFACE_SHA256.to_string()),
            "{case}"
        );
        assert_eq!(p.env.log_kinds(reference).len(), 4, "{case}");
        assert!(!launched(), "{case}");
        common::s(&reply, &["message"]).to_string()
    };
    for (place, marker, directory) in [
        (p.env.path(""), ".git", true),
        (p.env.path(""), "CLAUDE.md", false),
        (tmp.clone(), "AGENTS.md", false),
        (tmp.clone(), ".claude", true),
    ] {
        let path = format!("{}/{marker}", place.trim_end_matches('/'));
        if directory {
            std::fs::create_dir(&path).unwrap();
        } else {
            std::fs::write(&path, b"").unwrap();
        }
        let message = refused(marker);
        assert!(message.contains(marker), "{message}");
        if directory {
            std::fs::remove_dir(&path).unwrap();
        } else {
            std::fs::remove_file(&path).unwrap();
        }
    }
    // A regular file where the directory should be cannot be inspected.
    std::fs::rename(&tmp, p.env.path("tmp.aside")).unwrap();
    std::fs::write(&tmp, b"").unwrap();
    assert!(refused("not a directory").contains("cannot inspect"));
    std::fs::remove_file(&tmp).unwrap();
    let status = p.env.run(&["status", reference]).text();
    assert!(status.contains("0 used of 2; 2 remain."), "{status}");

    // Invariance: a missing directory passes the checks before the
    // reservation; making the fresh directory fails after it.
    let out = p.env.run(&["run", reference, "--json"]);
    let reply = out.json();
    assert_eq!(out.code, Some(5), "{}{}", out.text(), out.stderr);
    assert_eq!(
        (
            common::s(&reply, &["data", "ending"]),
            common::s(&reply, &["data", "cause"]),
        ),
        ("interrupted", "protocol_anomaly")
    );
    assert!(!launched());
    // Control: the same audit with its directory back starts and launches.
    std::fs::rename(p.env.path("tmp.aside"), &tmp).unwrap();
    let out = p.env.run(&["run", reference, "--json"]);
    assert_eq!(out.code, Some(5), "{}{}", out.text(), out.stderr);
    assert!(launched());
    assert_eq!(left_in_tmp(&p), Vec::<String>::new());
    let status = p.env.run(&["status", reference]).text();
    assert!(status.contains("2 used of 2; 0 remain."), "{status}");

    // A temporary directory that is or lies within the submission folder or
    // the archive refuses the same way.
    let overlapping: [(&str, &dyn Fn(&common::Env) -> String); 2] = [
        ("the submission folder", &|env| env.folder.clone()),
        ("the archive", &|env| format!("{}/tmp", env.archive)),
    ];
    for (what, place) in overlapping {
        let q = commissioned_harness(&placements(2, 60), Some(place), &|_| RECORDING.to_string());
        let out = q.env.run(&["run", &q.reference, "--json"]);
        let reply = out.json();
        assert_eq!(out.code, Some(3), "{what}: {}{}", out.text(), out.stderr);
        assert_eq!(
            common::s(&reply, &["reason"]),
            "runtime_profile_invalid",
            "{what}"
        );
        assert!(common::s(&reply, &["message"]).contains(what), "{what}");
        assert_eq!(q.env.log_kinds(&q.reference).len(), 4, "{what}");
        assert!(!exists(&q.env.path("home/observed")), "{what}");
    }
}

/// The private launch directory is removed once the run observes that the
/// placement's launched groups are gone, however the placement stopped: an
/// authentication check that fails before any model session (which used to
/// leave it) and an ordinary ending (control). Invariance: when stopping
/// cannot be established, here because an unreadable stop observation is
/// in the way, the directory stays.
#[test]
fn the_launch_directory_goes_once_the_groups_are_observed_gone() {
    // (case, unreadable stop observation, ordinary session, directory left)
    let cases = [
        ("failed authentication", false, false, false),
        ("ordinary ending", false, true, false),
        ("stopping unconfirmed", true, true, true),
    ];
    std::thread::scope(|scope| {
        for (case, unreadable, session, left) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|p| {
                    if !session {
                        return RECORDING.to_string();
                    }
                    let runs = format!("{}/runs/1", p.env.audit_dir(&p.reference));
                    two_turns_after(&if unreadable {
                        format!("printf 'unreadable' > '{runs}/runtime-stop.json'\n")
                    } else {
                        String::new()
                    })
                });
                let (_, reply) = finished(started(&p, &["run", &p.reference, "--json"]));
                let stopped = common::at(&reply, &["data", "usage", "stopped"]).as_u64();
                assert_eq!(stopped, Some(u64::from(!left)), "{case}");
                let entries = left_in_tmp(&p);
                assert_eq!(entries.len(), usize::from(left), "{case}: {entries:?}");
                assert!(
                    entries.iter().all(|e| e.starts_with("stewart-")),
                    "{entries:?}"
                );
            });
        }
    });
}

/// When a harness built by `correlated_call` echoes its call's result into
/// the conversation, changed.
#[derive(Clone, Copy, PartialEq)]
enum Echo {
    Never,
    /// Once the reply arrived, while the placement runs.
    Live,
    /// Once its input closed, which happens only after the owner decided
    /// the ending.
    Drain,
}

/// A harness whose auditor makes one correlated `list` call (its assistant
/// tool use, an admitted pre-tool hook and the MCP call, all naming
/// `tool-1`) and ends its first turn. Given the reminder it ends a second
/// turn when `second`, or else notes `home/reminder-read`. Once its input
/// closes it notes `home/decided`. `echo` says when it echoes the call's
/// result changed.
fn correlated_call(writer: &str, second: bool, echo: Echo) -> String {
    let assistant = r#"{"type":"assistant","session_id":"s1","message":{"id":"m1","model":"fixture-model","content":[{"type":"tool_use","id":"tool-1","name":"mcp__stewart__list","input":{}}]}}"#;
    let hook = r#"{"session_id":"s1","hook_event_name":"PreToolUse","tool_use_id":"tool-1","tool_name":"mcp__stewart__list","tool_input":{}}"#;
    let changed = emit(
        r#"{"type":"user","session_id":"s1","parent_tool_use_id":null,"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tool-1","content":[{"type":"text","text":"changed"}]}]}}"#,
    );
    let mut s = String::from(AUTH_LEG);
    s += "trap '' TERM INT HUP\nIFS= read -r question\n";
    s += &emit(&init_event());
    s += &emit(assistant);
    s += &format!("printf '%s' '{hook}' | '{writer}' __stewart-cc-hook h > \"$HOME/hook-out\"\n");
    s += "{\n";
    s += &emit(
        r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"clientInfo":{"name":"fixture","version":"1"}}}"#,
    );
    s += &emit(r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#);
    s += &emit(
        r#"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list","arguments":{},"_meta":{"claudecode/toolUseId":"tool-1"}}}"#,
    );
    s += "  while ! grep -q '\"id\":2,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n";
    s += &format!("}} | '{writer}' __stewart-cc-relay m > \"$HOME/mcp-out\" &\n");
    s += "while ! grep -q '\"id\":2,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n";
    if echo == Echo::Live {
        s += &changed;
    }
    s += &emit(&result_event(1, false));
    s += "IFS= read -r reminder\n";
    s += &if second {
        emit(&result_event(2, false))
    } else {
        ": > \"$HOME/reminder-read\"\n".to_string()
    };
    s += "while IFS= read -r more; do :; done\n";
    if echo == Echo::Drain {
        s += &changed;
    }
    s += ": > \"$HOME/decided\"\nwhile :; do sleep 1; done\n";
    s
}

/// The mismatch count of placement 1's final fidelity record.
fn mismatches(p: &Prepared) -> Option<u64> {
    let raw = std::fs::read(format!(
        "{}/runs/1/runtime-fidelity.json",
        p.env.audit_dir(&p.reference)
    ))
    .unwrap();
    common::at(&json::parse(&raw).unwrap(), &["mismatch"]).as_u64()
}

/// A changed reply first observed during the shutdown drain turns a decided
/// `ended_unsubmitted` into `interrupted` (`protocol_anomaly`), since the
/// auditor ended after receiving a changed reply. Control: without the
/// changed echo the placement ends `ended_unsubmitted`. Invariance: when a
/// signal decided the ending, the same drained mismatch is diagnosed and
/// the ending stays `interrupted` with cause `signal`.
#[test]
fn a_mismatch_first_observed_in_the_drain_changes_only_an_ordinary_ending() {
    // (case, second result, echo, signal, ending, cause, mismatches)
    let cases = [
        (
            "no echo",
            true,
            Echo::Never,
            false,
            "ended_unsubmitted",
            None,
            0,
        ),
        (
            "changed echo",
            true,
            Echo::Drain,
            false,
            "interrupted",
            Some("protocol_anomaly"),
            1,
        ),
        (
            "changed echo after a signal",
            false,
            Echo::Drain,
            true,
            "interrupted",
            Some("signal"),
            1,
        ),
    ];
    std::thread::scope(|scope| {
        for (case, second, echo, sig, ending, cause, mismatched) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|_| {
                    correlated_call(common::bin(), second, echo)
                });
                let run = started(&p, &["run", &p.reference, "--json"]);
                if sig {
                    let read = p.env.path("home/reminder-read");
                    assert!(within(30, || exists(&read)), "{case}");
                    signal(&run, libc::SIGTERM);
                }
                let (code, reply) = finished(run);
                let ended = last_run_ended(&p);
                assert_eq!(
                    (
                        common::s(&reply, &["data", "ending"]),
                        common::at(&reply, &["data", "cause"]).as_str(),
                    ),
                    (ending, cause),
                    "{case}: {}",
                    common::s(&ended, &["body", "message"])
                );
                assert_eq!(code, Some(if cause.is_some() { 5 } else { 0 }), "{case}");
                assert!(exists(&p.env.path("home/decided")), "{case}");
                let hook = std::fs::read_to_string(p.env.path("home/hook-out")).unwrap();
                assert_eq!(hook, "{}\n", "{case}: the hook was admitted");
                assert_eq!(mismatches(&p), Some(mismatched), "{case}");
            });
        }
    });
}

/// `started`, with `vars` added to the environment.
#[cfg(feature = "fault-injection")]
fn started_with(p: &Prepared, args: &[&str], vars: &[(&str, &str)]) -> std::process::Child {
    std::process::Command::new(common::bin())
        .args(args)
        .current_dir(&p.env.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .envs(vars.iter().copied())
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap()
}

/// A changed reply observed while the placement runs decides its ending,
/// `interrupted` with cause `protocol_anomaly`, also when its diagnostic
/// cannot then be written: that write failure comes after the mismatch and
/// is reported (`effects.diagnostic` `reported_only`), not recorded as
/// `archive_write_failed`. Control: the diagnostic written. Invariance: the
/// same failing diagnostic write with no mismatch changes nothing, and the
/// placement ends ordinarily.
#[cfg(feature = "fault-injection")]
#[test]
fn a_mismatch_decides_although_its_diagnostic_cannot_be_retained() {
    // (case, echo, fault, ending, cause, diagnostic effect)
    let cases = [
        (
            "written",
            Echo::Live,
            "",
            "interrupted",
            Some("protocol_anomaly"),
            Some("durable"),
        ),
        (
            "unwritten",
            Echo::Live,
            "diag.write=eio",
            "interrupted",
            Some("protocol_anomaly"),
            Some("reported_only"),
        ),
        (
            "no mismatch",
            Echo::Never,
            "diag.write=eio",
            "ended_unsubmitted",
            None,
            None,
        ),
    ];
    std::thread::scope(|scope| {
        for (case, echo, fault, ending, cause, diagnostic) in cases {
            scope.spawn(move || {
                let p = commissioned_harness(&placements(2, 60), None, &|_| {
                    correlated_call(common::bin(), true, echo)
                });
                let run = started_with(
                    &p,
                    &["run", &p.reference, "--json"],
                    &[("STEWART_TEST_FAULT", fault)],
                );
                let (_, reply) = finished(run);
                let ended = last_run_ended(&p);
                assert_eq!(
                    (
                        common::s(&reply, &["data", "ending"]),
                        common::at(&reply, &["data", "cause"]).as_str(),
                    ),
                    (ending, cause),
                    "{case}: {}",
                    common::s(&ended, &["body", "message"])
                );
                let effects = common::at(&reply, &["effects"]);
                assert_eq!(
                    common::has(effects, "diagnostic").then(|| common::s(effects, &["diagnostic"])),
                    diagnostic,
                    "{case}"
                );
                assert_eq!(
                    mismatches(&p),
                    Some(u64::from(echo == Echo::Live)),
                    "{case}"
                );
            });
        }
    });
}

/// A placement without a recorded ending whose runtime observations cannot
/// be read also makes run and close refuse `runtime_stop_unknown`, so status
/// offers only status and names that placement and why (runtime contract,
/// harness accounting record). Placement 1's owner is killed while its
/// authentication check holds, then an unreadable usage checkpoint is added.
/// Control: once it is removed, the ordinary advice returns. Invariance:
/// the same file beside a recorded ending blocks nothing.
#[test]
fn unreadable_runtime_observations_offer_only_status() {
    let p = commissioned_for(HELD, 3, 60);
    let r = p.reference.as_str();
    let line = "Placement 1 has no recorded ending, and its runtime observations cannot be read.";
    std::fs::write(p.env.path("home/hold"), b"").unwrap();
    let mut owner = std::process::Command::new(common::bin())
        .args(["run", r, "--json"])
        .current_dir(&p.env.cwd)
        .env_remove("STEWART_ARCHIVE")
        .env_remove("STEWART_TEST_FAULT")
        .env_remove("STEWART_TEST_SABOTAGE")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .unwrap();
    let ready = std::path::Path::new(&p.env.path("home/ready")).to_path_buf();
    let start = Instant::now();
    while !ready.exists() {
        assert!(
            start.elapsed() < Duration::from_secs(30),
            "placement 1 never reached its authentication check"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
    owner.kill().unwrap();
    owner.wait().unwrap();
    std::fs::remove_file(p.env.path("home/hold")).unwrap();
    let bad = format!("{}/runs/1/runtime-usage-9.json", p.env.audit_dir(r));
    std::fs::write(&bad, b"{").unwrap();

    // The supervisor stops the killed owner's group; status observes it.
    let start = Instant::now();
    let status = loop {
        let status = p.env.run(&["status", r, "--json"]).json();
        if common::s(&status, &["data", "summary"]).contains(line) {
            break status;
        }
        assert!(
            start.elapsed() < Duration::from_secs(30),
            "{}",
            common::s(&status, &["data", "summary"])
        );
        std::thread::sleep(Duration::from_millis(100));
    };
    assert_eq!(offered(&status), ["status"]);
    assert!(
        common::s(&status, &["next", "0", "why"]).contains("the runtime observations can be read"),
        "{}",
        common::s(&status, &["next", "0", "why"])
    );
    assert!(!common::s(&status, &["data", "summary"]).contains("Stopping of"));
    // The advice describes what run would do.
    let refused = p.env.run(&["run", r, "--json"]).json();
    assert_eq!(common::s(&refused, &["reason"]), "runtime_stop_unknown");
    assert_eq!(offered(&refused), ["status"]);
    assert!(
        common::s(&refused, &["message"])
            .contains("Placement 1 has unreadable runtime observations"),
        "{}",
        common::s(&refused, &["message"])
    );

    std::fs::remove_file(&bad).unwrap();
    let status = p.env.run(&["status", r, "--json"]).json();
    assert!(
        offered(&status).contains(&"run".to_string()),
        "{:?}",
        offered(&status)
    );
    assert!(!common::s(&status, &["data", "summary"]).contains(line));

    // The next run records placement 1's ending; the same file then blocks
    // nothing, since only a placement without an ending is read for it.
    let second = p.env.run(&["run", r, "--json"]);
    assert_eq!(second.code, Some(5), "{}{}", second.text(), second.stderr);
    std::fs::write(&bad, b"{").unwrap();
    let status = p.env.run(&["status", r, "--json"]).json();
    assert_eq!(offered(&status), ["run", "close"]);
    assert!(!common::s(&status, &["data", "summary"]).contains(line));
}
