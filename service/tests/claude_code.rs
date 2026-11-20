//! The development runtime through the real binary, and its call dispatch in
//! process. These cases keep what the independent runtime driver does not
//! check: exact record and reply bytes, archive state that only the
//! implementation names, and failure points and boundaries that no driver
//! case reaches. Behavior the driver checks belongs to the driver.
//!
//! The cases that need the test build's failure points are in `faults`,
//! compiled only with `fault-injection`. Placements start synthetic
//! executables that connect through a private Unix socket, so they need a
//! host that permits binding one and observing process groups, and a scratch
//! directory outside any project or configuration tree.
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

/// A call whose gate closed before it started, by cancellation, a stop or
/// the placement deadline, is refused `placement_stopped` before its tool
/// runs: the revision stays, no stage or payload candidate is written, no
/// seal exists and the refusal is not a write failure. Invariance: the same
/// input under an open gate (a fresh sibling of a cancelled call, otherwise
/// a fresh gate) is accepted, so the input itself was valid.
#[test]
fn a_closed_gate_refuses_a_call_before_its_tool_runs() {
    for tool in ["record_account", "submit"] {
        for condition in ["cancel", "stop", "deadline"] {
            let case = format!("{tool} after {condition}");
            let mut live = Live::new();
            live.call("record_account", r#"{"text":"recorded before the stop"}"#)
                .ok();
            let input = match tool {
                "submit" => {
                    let prepared = live.call("prepare", "{}").str(&["prepared"]).to_string();
                    format!(r#"{{"prepared":"{prepared}","confirm":true}}"#)
                }
                _ => r#"{"text":"must not publish"}"#.to_string(),
            };
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
            let revision = live.state().revision();
            let before = candidates(&live);
            let refusal = dispatched(&mut live, &gate, tool, &input);
            assert_eq!(refusal.outcome(), "refused", "{case}: {}", refusal.text());
            assert_eq!(refusal.reason(), "placement_stopped", "{case}");
            assert_eq!(
                refusal.ex.end, None,
                "{case}: a refused call is not a write failure"
            );
            assert_eq!(live.state().revision(), revision, "{case}");
            assert_eq!(
                candidates(&live),
                before,
                "{case}: the call entered no tool"
            );
            assert!(live.state().seal().is_none(), "{case}");
            if tool == "submit" {
                assert_eq!(refusal.effect("seal"), "none", "{case}");
            }
            let open = match condition {
                "cancel" => parent.call(),
                _ => Gate::new(Instant::now() + Duration::from_secs(60)),
            };
            let accepted = dispatched(&mut live, &open, tool, &input);
            accepted.ok();
            match tool {
                "submit" => assert!(accepted.ex.sealed, "{case}"),
                _ => assert_eq!(live.state().revision(), revision + 1, "{case}"),
            }
        }
    }
}

/// The launch surface document and its digest as the runtime contract's
/// worked example states them, read from the repository so that these cases
/// do not ask the binary under test for either: the fenced block that opens
/// with the surface schema, its lines joined without their endings, and the
/// first digest stated after it.
fn contract_surface() -> &'static (String, String) {
    static SURFACE: std::sync::OnceLock<(String, String)> = std::sync::OnceLock::new();
    SURFACE.get_or_init(|| {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../docs/claude-code/CONTRACT.md"
        );
        let doc = std::fs::read_to_string(path)
            .expect("docs/claude-code/CONTRACT.md is part of the repository");
        let opening = "```json\n{\"schema\":\"stewart.claude-code.surface/1\"";
        assert_eq!(doc.matches(opening).count(), 1, "one worked example");
        let from = doc.find(opening).unwrap() + "```json\n".len();
        let (block, after) = doc[from..].split_once("\n```\n").expect("a closed fence");
        let digest = after
            .split('`')
            .find(|part| part.len() == 64 && part.bytes().all(|b| b.is_ascii_hexdigit()))
            .expect("the contract states the example's digest");
        let document: String = block.split('\n').collect();
        assert_eq!(
            stewart::util::sha256_hex(document.as_bytes()),
            digest,
            "the worked example has the digest the contract states"
        );
        (document, digest.to_string())
    })
}

/// What the synthetic executable holds until a case supplies its script.
/// `prepare` hashes it without executing it.
const INERT: &str = "not executed\n";

/// A folder whose question has `fields` after the common front matter, with
/// a synthetic executable and the directories a profile names.
struct Prepared {
    env: common::Env,
    reference: String,
    executable: String,
}

impl Prepared {
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

    fn prepare(&self) -> common::Out {
        self.env.run(&["prepare", &self.reference, "--json"])
    }
}

/// Write `p`'s `profile.json`: a check of the contract's launch surface,
/// with every other binding valid for its folder, executable and platform.
fn write_profile(p: &Prepared) {
    let digest = stewart::util::sha256_hex;
    let executable = digest(p.executable.as_bytes());
    let launch = format!(
        r#"{{"executable":"{}","sha256":"{executable}","version":"2.1.322","platform":"{}-{}","config_directory":"{}","home":"{}","temporary_directory":"{}"}}"#,
        p.env.path("harness"),
        std::env::consts::OS,
        std::env::consts::ARCH,
        p.env.path("config"),
        p.env.path("home"),
        p.env.path("tmp"),
    );
    let family = stewart::forms::family("open-inquiry").unwrap();
    let tools = stewart::claude_code::mcp_tools(&stewart::forms::tools(family).bytes()).unwrap();
    let profile = format!(
        r#"{{"schema":"stewart.claude-code.profile/2","launch":{launch},"installation":{{"manifest_sha256":"{}","signer":"31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE","binary_sha256":"{executable}"}},"check":{{"surface_sha256":"{}","launch_sha256":"{}","tools_sha256":"{}","model":"fixture-model","checked_at":"2026-11-11","evidence_sha256":"{}","outcome":"observed"}}}}"#,
        "1".repeat(64),
        contract_surface().1,
        digest(launch.as_bytes()),
        digest(&tools),
        "2".repeat(64),
    );
    std::fs::write(p.env.path("profile.json"), profile).unwrap();
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

const API_LIMITS: &str =
    "limit-turns: 200\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\n";

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

/// A commissioned audit of `max` placements of `timeout` seconds whose
/// synthetic executable is `script(p)`, which may name the audit's paths.
fn commissioned(max: u64, timeout: u64, script: &dyn Fn(&Prepared) -> String) -> Prepared {
    let mut p = Prepared::with(INERT, &placements(max, timeout));
    require_clean_scratch(&p);
    p.executable = script(&p);
    std::fs::write(p.env.path("harness"), &p.executable).unwrap();
    write_profile(&p);
    let out = p.prepare();
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    let out = p
        .env
        .commission(&p.reference, common::s(&out.json(), &["data", "prepared"]));
    assert_eq!(out.code, Some(0), "{}{}", out.text(), out.stderr);
    p
}

/// `stewart args` for `p` with `vars` added to its environment, started in
/// the background with its output piped.
fn started(p: &Prepared, args: &[&str], vars: &[(&str, &str)]) -> std::process::Child {
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

/// The operation each next call offers (its `argv[1]`).
fn offered(reply: &json::Json) -> Vec<String> {
    common::at(reply, &["next"])
        .as_arr()
        .unwrap()
        .iter()
        .map(|n| common::s(n, &["argv", "1"]).to_string())
        .collect()
}

/// The authentication leg every synthetic harness that starts a session
/// passes.
const AUTH_LEG: &str = concat!(
    "#!/bin/sh\n",
    "if [ \"$1\" = auth ]; then\n",
    "  printf '{\"loggedIn\":true,\"authMethod\":\"claude.ai\",\"configDirectory\":\"%s\"}\\n' \"$CLAUDE_CONFIG_DIR\"\n",
    "  exit 0\n",
    "fi\n",
);

/// A synthetic executable that records what it was started with and then
/// fails, as a status check that does not report a login would. It starts no
/// session; the placement it was reserved for is used and observed stopped.
const RECORDING: &str = "#!/bin/sh\n{ printf '%s\\n' \"$@\"; echo ---; /usr/bin/env; echo ---; pwd; } >> \"$HOME/observed\"\nexit 1\n";

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
    let mut s = String::from(AUTH_LEG);
    s += "IFS= read -r question\n";
    s += &emit(&init_event());
    s += &emit(&result_event(1, false));
    s += "IFS= read -r reminder || exit 0\n";
    s += &emit(&result_event(2, false));
    s += "while :; do sleep 1; done\n";
    s
}

/// `two_turns`, with `setup` run once the harness has read the question.
fn two_turns_after(setup: &str) -> String {
    two_turns().replacen(
        "IFS= read -r question\n",
        &format!("IFS= read -r question\n{setup}"),
        1,
    )
}

// ---------------------------------------------------------------------------
// Records and replies, byte for byte.

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
    let p = commissioned(2, 60, &|_| RECORDING.to_string());
    let run = p.env.run(&["run", &p.reference]);
    assert!(
        run.text()
            .contains("Run 1 was interrupted (protocol_anomaly)."),
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
    let checkpoint = format!(
        "{}/runs/1/runtime-usage-1.json",
        p.env.audit_dir(&p.reference)
    );
    assert_eq!(std::fs::read_to_string(checkpoint).unwrap(), summary);
}

/// A synthetic harness that passes the authentication check, reads the
/// question and starts its session, then, through Stewart's MCP relay at
/// `writer`, initializes and makes two tool calls: `list`, which completes,
/// and `nope`, which is not a tool of the arrangement. Once both replies
/// have arrived it closes its side of the relay, which stays to forward
/// replies, and ends two turns as `two_turns` does.
fn two_tool_calls(writer: &str) -> String {
    let mut s = String::from(AUTH_LEG);
    s += "IFS= read -r question\n";
    s += &emit(&init_event());
    s += "sleep 0.5\n{\n";
    for frame in [
        r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"clientInfo":{"name":"fixture","version":"1"}}}"#,
        r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
        r#"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list","arguments":{}}}"#,
        r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"nope","arguments":{}}}"#,
    ] {
        s += &emit(frame);
    }
    s += "  while ! grep -q '\"id\":3,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n";
    s += &format!("}} | '{writer}' __stewart-cc-relay m > \"$HOME/mcp-out\" &\n");
    s += "while ! grep -q '\"id\":3,' \"$HOME/mcp-out\" 2>/dev/null; do sleep 0.05; done\n";
    s += &emit(&result_event(1, false));
    s += "IFS= read -r reminder || exit 0\n";
    s += &emit(&result_event(2, false));
    s += "while :; do sleep 1; done\n";
    s
}

/// The result records a harness placement writes for its MCP calls, and the
/// replies it sends, byte for byte: request and attempt 1, the call number
/// as the block, an `mcp-<call>` invocation ID, and the reply's content and
/// error flag as the record states them.
#[test]
fn harness_tool_calls_keep_their_result_records_and_replies() {
    let p = commissioned(2, 60, &|_| two_tool_calls(common::bin()));
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

/// Once the final permitted placement's interruption has ended authoring as
/// `limit` (INTERFACE 1.6; runtime contract, limits), `run` refuses
/// `authoring_ended` with exactly these bytes: the data and next calls of
/// INTERFACE 5.7 step 2, naming that placement's `run_ended` and the
/// diagnostic the refusal retains. The refusal records nothing.
#[test]
fn a_run_after_the_final_placement_refuses_with_its_exact_reply() {
    let p = commissioned(1, 60, &|_| RECORDING.to_string());
    let r = p.reference.as_str();
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
    let kinds = p.env.log_kinds(r);
    assert_eq!(kinds.last().unwrap(), "run_ended");
    let refused = p.env.run(&["run", r, "--json"]);
    assert_eq!(refused.code, Some(3));
    let expected = format!(
        concat!(
            r#"{{"schema":"stewart.reply/3","operation":"run","outcome":"refused","reason":"authoring_ended","#,
            r#""message":"Authoring has ended (limit log/{record}.json), so no run can start; close returns or seals the recorded selection.","#,
            r#""effects":{{"run":"ended","answer":"unchanged","seal":"none","delivery":"none","diagnostic":"durable"}},"#,
            r#""retained":["<audit>/diag/1.json"],"#,
            r#""next":[{{"argv":["<bin>","close","<ref>"],"why":"Close the audit; it seals the recorded selection with manager attribution if no seal exists."}},"#,
            r#"{{"argv":["<bin>","status","<ref>"],"why":"See where the audit stands."}}],"#,
            r#""data":{{"ended_by":"limit","record":"log/{record}.json"}}}}"#,
            "\n"
        ),
        record = kinds.len()
    );
    assert_eq!(normalized_reply(&p, &refused.stdout), expected);
    assert_eq!(p.env.log_kinds(r), kinds, "the refusal records nothing");
}

// ---------------------------------------------------------------------------
// Boundaries no driver case reaches.

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
/// (runtime contract, harness accounting record). Placement 1 ended with a
/// recorded ending; its stop observation is replaced by one naming a live
/// group while placement 2 runs. Controls: before that, both offer run and
/// close, and status during placement 2 gives the live run's ordinary
/// advice, since its owner observes its stopping; once the group is gone,
/// status offers run and close again.
#[test]
fn unknown_stopping_offers_only_status_until_it_is_observed() {
    let p = commissioned(3, 60, &|_| HELD.to_string());
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
    let second = started(&p, &["run", r, "--json"], &[]);
    assert!(
        within(30, || exists(&p.env.path("home/ready"))),
        "placement 2 never started"
    );
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
    let (code, reply) = finished(second);
    assert_eq!(code, Some(5));
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

/// A placement without a recorded ending whose runtime observations cannot
/// be read also makes run and close refuse `runtime_stop_unknown`, so status
/// offers only status and names that placement and why (runtime contract,
/// harness accounting record). Placement 1's owner is killed while its
/// authentication check holds, then an unreadable usage checkpoint is added.
/// Control: once it is removed, the ordinary advice returns. Invariance:
/// the same file beside a recorded ending blocks nothing.
#[test]
fn unreadable_runtime_observations_offer_only_status() {
    let p = commissioned(3, 60, &|_| HELD.to_string());
    let r = p.reference.as_str();
    let line = "Placement 1 has no recorded ending, and its runtime observations cannot be read.";
    std::fs::write(p.env.path("home/hold"), b"").unwrap();
    let mut owner = started(&p, &["run", r, "--json"], &[]);
    assert!(
        within(30, || exists(&p.env.path("home/ready"))),
        "placement 1 never reached its authentication check"
    );
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

/// What the owner observes after the ending is decided changes the
/// accounting, not the ending. Here the harness puts a stop observation in
/// the way of `runtime-stop.json`. When it is readable, the owner still
/// observes the groups gone and removes the private launch directory, but
/// cannot retain its own observation, so the placement is not counted as
/// observed stopped and a diagnostic says why. When it cannot be read,
/// stopping is unconfirmed and the launch directory stays. Control: the same
/// placement retains its stop observation and its launch directory goes.
/// Invariance: a capture failure observed while the placement runs decides
/// `archive_write_failed`, and the reminder it never captured is `not_sent`.
#[test]
fn a_stop_observation_that_cannot_be_retained_leaves_the_ending() {
    let readable = r#"{"elapsed_ms":0,"deadline_ms":60000,"groups_gone":false}"#;
    // (case, setup, ending, cause, exit, stopped, notice sent, directory left)
    let cases: [(&str, &str, &str, Option<&str>, i32, u64, &str, bool); 4] = [
        (
            "retained",
            "",
            "ended_unsubmitted",
            None,
            0,
            1,
            "sent",
            false,
        ),
        (
            "readable stop observation in the way",
            readable,
            "ended_unsubmitted",
            None,
            0,
            0,
            "sent",
            false,
        ),
        (
            "unreadable stop observation in the way",
            "unreadable",
            "ended_unsubmitted",
            None,
            0,
            0,
            "sent",
            true,
        ),
        (
            "capture in the way",
            "capture",
            "interrupted",
            Some("archive_write_failed"),
            5,
            1,
            "not_sent",
            false,
        ),
    ];
    std::thread::scope(|scope| {
        for (case, setup, ending, cause, exit, stopped, sent, left) in cases {
            scope.spawn(move || {
                let p = commissioned(2, 60, &|p| {
                    let runs = format!("{}/runs/1", p.env.audit_dir(&p.reference));
                    two_turns_after(&match setup {
                        "" => String::new(),
                        // Every later input capture name is taken.
                        "capture" => format!(
                            "i=2; while [ \"$i\" -le 400 ]; do : > '{runs}/runtime-'\"$i\"'-input.bin'; i=$((i+1)); done\n"
                        ),
                        planted => format!("printf '%s' '{planted}' > '{runs}/runtime-stop.json'\n"),
                    })
                });
                let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"], &[]));
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
                if !matches!(setup, "" | "capture") {
                    assert_eq!(stop, setup, "{case}");
                    assert!(
                        message.contains("Stop observation could not be retained"),
                        "{case}: {message}"
                    );
                    assert_eq!(
                        message.contains("Stopping is unconfirmed"),
                        left,
                        "{case}: {message}"
                    );
                } else {
                    assert!(stop.contains(r#""groups_gone":true"#), "{case}: {stop}");
                    assert!(!message.contains("could not be retained"), "{case}: {message}");
                }
                let entries = left_in_tmp(&p);
                assert_eq!(entries.len(), usize::from(left), "{case}: {entries:?}");
                assert!(
                    entries.iter().all(|e| e.starts_with("stewart-")),
                    "{case}: {entries:?}"
                );
            });
        }
    });
}

/// A stopping condition the contract gives no other cause decides the
/// ending `interrupted` with cause `protocol_anomaly`: a quota rejection and
/// a frame that is not JSON. Each keeps authoring open while starts remain.
#[test]
fn a_condition_with_no_other_cause_ends_with_a_protocol_anomaly() {
    let cases = [
        ("quota rejection", emit(QUOTA_REJECTED)),
        ("frame that is not JSON", emit("not json")),
    ];
    std::thread::scope(|scope| {
        for (case, then) in &cases {
            scope.spawn(move || {
                let p = commissioned(2, 60, &|_| {
                    format!(
                        "{AUTH_LEG}IFS= read -r question\n{}{then}while :; do sleep 1; done\n",
                        emit(&init_event())
                    )
                });
                let (code, reply) = finished(started(&p, &["run", &p.reference, "--json"], &[]));
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
/// start: one it cannot inspect, here a regular file in its place, refuses
/// `runtime_profile_invalid` with this binary's surface report, uses no
/// start and launches nothing. Invariance: on the same audit, a temporary
/// directory that passes these checks but is missing when the fresh
/// directory is made uses its start, which ends `interrupted`
/// (`protocol_anomaly`). Control: once the directory is back, the run
/// starts and launches the harness, whose authentication check fails, and
/// its fresh directory is removed once stopping is observed.
#[test]
fn a_temporary_directory_that_cannot_hold_the_launch_refuses_before_a_start() {
    let p = commissioned(2, 60, &|_| RECORDING.to_string());
    let reference = p.reference.as_str();
    let tmp = p.env.path("tmp");
    let launched = || exists(&p.env.path("home/observed"));
    std::fs::rename(&tmp, p.env.path("tmp.aside")).unwrap();
    std::fs::write(&tmp, b"").unwrap();
    let out = p.env.run(&["run", reference, "--json"]);
    let reply = out.json();
    assert_eq!(out.code, Some(3), "{}{}", out.text(), out.stderr);
    assert_eq!(
        (
            common::s(&reply, &["outcome"]),
            common::s(&reply, &["reason"]),
            common::s(&reply, &["effects", "run"]),
        ),
        ("refused", "runtime_profile_invalid", "not_started")
    );
    let message = common::s(&reply, &["message"]);
    assert!(
        message.contains("cannot inspect") && message.contains("No placement start was used"),
        "{message}"
    );
    let (document, digest) = contract_surface();
    assert_eq!(
        reported_surface(&out),
        (document.as_bytes().to_vec(), digest.clone())
    );
    assert_eq!(p.env.log_kinds(reference).len(), 4);
    assert!(!launched());
    std::fs::remove_file(&tmp).unwrap();

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
}

/// Cases at the test build's failure points (INTERFACE Appendix C), which
/// exist only with `fault-injection`.
#[cfg(feature = "fault-injection")]
mod faults {
    use super::*;

    /// A reminder claim stands in the log only once its record is linked.
    /// When linking the claim fails, the placement stops before sending it,
    /// ends `archive_write_failed`, and neither its `run_ended` nor the run
    /// reply lists a notice. Control: with no failure the claim links as
    /// `log/6.json`, the reminder is sent and both list it as `sent`.
    #[test]
    fn a_reminder_claim_that_was_not_linked_is_not_listed() {
        for (fault, cause, listed) in [
            ("", None, true),
            (
                "log.publish:notice=eio",
                Some("archive_write_failed"),
                false,
            ),
        ] {
            let p = commissioned(2, 60, &|_| two_turns());
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
                common::at(&reply, &["data", "cause"]).as_str(),
                cause,
                "{fault:?}: {}",
                common::s(&ended, &["body", "message"])
            );
            let in_record = common::at(&ended, &["body", "notices"]).as_arr().unwrap();
            let in_reply = common::at(&reply, &["data", "notices"]).as_arr().unwrap();
            if !listed {
                assert_eq!(kinds[4..], ["run_started", "run_ended"], "{fault:?}");
                assert!(in_record.is_empty() && in_reply.is_empty(), "{fault:?}");
                continue;
            }
            assert_eq!(kinds[4..], ["run_started", "notice", "run_ended"]);
            assert_eq!(common::s(&in_record[0], &["record"]), "log/6.json");
            for notices in [in_record, in_reply] {
                assert_eq!(notices.len(), 1);
                assert_eq!(common::s(&notices[0], &["type"]), "reminder");
                assert_eq!(common::s(&notices[0], &["sent"]), "sent");
            }
        }
    }

    /// The harness runtime reserves its start as the Messages runtime does
    /// (INTERFACE 5.7). A `run_started` that was not linked started nothing:
    /// `failed` `record_failed`, `effects.run` `not_started`, and the slot
    /// stays free. One linked without confirmed durability may stand and so
    /// consumes its slot: `failed` `record_failed`, `effects.run` `unknown`,
    /// no harness launched. The next run records that placement's ending
    /// (`interrupted`, `process_gone`). With a start remaining it then uses
    /// that start and launches the harness; when the linked placement was the
    /// final one, that record ended authoring as `limit`, and the run refuses
    /// `authoring_ended` naming it without launching anything (runtime
    /// contract, limits).
    #[test]
    fn a_harness_start_reservation_reports_what_it_linked() {
        for allowed in [2, 1] {
            let p = commissioned(allowed, 60, &|_| RECORDING.to_string());
            let reference = p.reference.as_str();
            let launched = || exists(&p.env.path("home/observed"));
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
                let case = format!("{fault} of {allowed}");
                let out = p.env.run_env(
                    &["run", reference, "--json"],
                    &[("STEWART_TEST_FAULT", fault)],
                );
                let reply = out.json();
                assert_eq!(out.code, Some(4), "{case}: {}{}", out.text(), out.stderr);
                assert_eq!(
                    (
                        common::s(&reply, &["outcome"]),
                        common::s(&reply, &["reason"])
                    ),
                    ("failed", "record_failed"),
                    "{case}: {}",
                    out.text()
                );
                for (effect, value) in [
                    ("run", run),
                    ("answer", "unchanged"),
                    ("seal", "none"),
                    ("delivery", "none"),
                    ("diagnostic", "durable"),
                ] {
                    assert_eq!(common::s(&reply, &["effects", effect]), value, "{case}");
                }
                assert_eq!(
                    common::s(&reply, &["causes", "0", "operation"]),
                    operation,
                    "{case}"
                );
                let kinds = p.env.log_kinds(reference);
                if linked {
                    assert_eq!(
                        common::s(&reply, &["message"]),
                        "run_started was linked as log/5.json but its durability could not be confirmed; the run did not continue."
                    );
                    assert_eq!(common::strs(&reply, &["next", "0", "argv"])[1], "status");
                    assert_eq!(kinds[4..], ["run_started"], "{case}");
                } else {
                    assert_eq!(
                        common::s(&reply, &["message"]),
                        "run_started could not be recorded, so no placement started."
                    );
                    assert_eq!(kinds.len(), 4, "{case}: {kinds:?}");
                }
                assert!(!launched(), "{case}: no harness is launched");
                let dir = format!("{}/runs/1", p.env.audit_dir(reference));
                assert!(!std::path::Path::new(&dir).exists(), "{case}");
            }
            let out = p.env.run(&["run", reference, "--json"]);
            let gone = p.env.log_record(reference, 6);
            assert_eq!(
                (
                    common::at(&gone, &["body", "run"]).as_u64(),
                    common::s(&gone, &["body", "ending"]),
                    common::s(&gone, &["body", "cause"]),
                    common::s(&gone, &["body", "recorded_by"]),
                ),
                (Some(1), "interrupted", "process_gone", "run"),
                "{allowed}"
            );
            let kinds = p.env.log_kinds(reference);
            if allowed == 1 {
                assert_eq!(out.code, Some(3), "{}{}", out.text(), out.stderr);
                let reply = out.json();
                assert_eq!(common::s(&reply, &["reason"]), "authoring_ended");
                assert_eq!(common::s(&reply, &["data", "record"]), "log/6.json");
                assert_eq!(kinds[4..], ["run_started", "run_ended"]);
                assert!(!launched());
            } else {
                assert_eq!(out.code, Some(5), "{}{}", out.text(), out.stderr);
                assert_eq!(
                    kinds[4..],
                    ["run_started", "run_ended", "run_started", "run_ended"]
                );
                assert!(launched());
            }
        }
    }

    /// A harness whose auditor makes one correlated `list` call (its
    /// assistant tool use, an admitted pre-tool hook and the MCP call, all
    /// naming `tool-1`) and ends its first turn, then ends a second turn
    /// given the reminder. When `changed`, it echoes the call's result into
    /// the conversation changed once the reply has arrived.
    fn correlated_call(writer: &str, changed: bool) -> String {
        let assistant = r#"{"type":"assistant","session_id":"s1","message":{"id":"m1","model":"fixture-model","content":[{"type":"tool_use","id":"tool-1","name":"mcp__stewart__list","input":{}}]}}"#;
        let hook = r#"{"session_id":"s1","hook_event_name":"PreToolUse","tool_use_id":"tool-1","tool_name":"mcp__stewart__list","tool_input":{}}"#;
        let mut s = String::from(AUTH_LEG);
        s += "IFS= read -r question\n";
        s += &emit(&init_event());
        s += &emit(assistant);
        s += &format!(
            "printf '%s' '{hook}' | '{writer}' __stewart-cc-hook h > \"$HOME/hook-out\"\n"
        );
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
        if changed {
            s += &emit(
                r#"{"type":"user","session_id":"s1","parent_tool_use_id":null,"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tool-1","content":[{"type":"text","text":"changed"}]}]}}"#,
            );
        }
        s += &emit(&result_event(1, false));
        s += "IFS= read -r reminder\n";
        s += &emit(&result_event(2, false));
        s += "while :; do sleep 1; done\n";
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

    /// A changed reply observed while the placement runs decides its ending,
    /// `interrupted` with cause `protocol_anomaly`, also when its diagnostic
    /// cannot then be written: that write failure comes after the mismatch
    /// and is reported (`effects.diagnostic` `reported_only`), not recorded
    /// as `archive_write_failed`. Control: the diagnostic written.
    /// Invariance: the same failing diagnostic write with no mismatch changes
    /// nothing, and the placement ends ordinarily.
    #[test]
    fn a_mismatch_decides_although_its_diagnostic_cannot_be_retained() {
        // (case, changed echo, fault, ending, cause, diagnostic effect)
        let cases = [
            (
                "written",
                true,
                "",
                "interrupted",
                Some("protocol_anomaly"),
                Some("durable"),
            ),
            (
                "unwritten",
                true,
                "diag.write=eio",
                "interrupted",
                Some("protocol_anomaly"),
                Some("reported_only"),
            ),
            (
                "no mismatch",
                false,
                "diag.write=eio",
                "ended_unsubmitted",
                None,
                None,
            ),
        ];
        std::thread::scope(|scope| {
            for (case, changed, fault, ending, cause, diagnostic) in cases {
                scope.spawn(move || {
                    let p = commissioned(2, 60, &|_| correlated_call(common::bin(), changed));
                    let run = started(
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
                        common::has(effects, "diagnostic")
                            .then(|| common::s(effects, &["diagnostic"])),
                        diagnostic,
                        "{case}"
                    );
                    assert_eq!(mismatches(&p), Some(u64::from(changed)), "{case}");
                });
            }
        });
    }
}
