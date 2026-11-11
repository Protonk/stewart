//! Development-only subscription harness adapter.
//!
//! Keep all adapter code here (or in child modules). Launch code constructs
//! its child environment in one function inside this boundary.
//! The build identifier is reachable through help so the release-absence
//! check has a firing control even under fat LTO.

/// Printed before the help overview. It names the help topic, which ships
/// with the binary, instead of a path in a source tree the manager may lack.
pub(crate) const BUILD_NOTICE: &str = "Stewart development build: claude-code\n\
A question that names runtime-profile is placed through a pinned Claude Code harness instead of the Messages API.\n\
Run `stewart help runtime` for the fields, the profile, login and what run needs.\n\n";

/// The help topic this build adds.
pub(crate) const HELP_TOPIC: &str = "runtime";

/// `stewart help runtime`: how a manager turns the ordinary scaffold into a
/// runtime question and what that changes. The runtime contract states what
/// this text must cover.
pub(crate) fn help() -> String {
    format!(
        "\
Claude Code runtime questions (development build)

This build can place the auditor through a pinned Claude Code installation
instead of the Messages API. The audit, its records, the auditor's tools, the
answer and the return are the same. What differs is how the auditor is run and
how a run is bounded.

Turning the scaffold into a runtime question
  stewart new writes the ordinary scaffold. In question.md keep
    stewart: question/1
  and replace the three limit lines (limit-turns, limit-input-tokens and
  limit-output-tokens) with these three:
    runtime-profile: the absolute path of the profile described below
    max-placements: placement starts allowed for the whole audit, 1 to {placements}
    placement-timeout-seconds: the deadline of each placement, 1 to {seconds}
  Naming runtime-profile selects this runtime. The two placement fields are
  then required and every limit-* field is refused. Without runtime-profile
  the question is an ordinary Messages API question, and the two placement
  fields are refused. model must be the model the profile's check records.
  The other fields, the question body and the materials are as help commands
  describes them.

The profile
  A nonsecret JSON file of at most 64 KiB with schema
  {profile}. It pins the harness executable with its
  digest, version and platform, the configuration, home and temporary
  directories the harness is given, an installation attestation, and a check.
  The check records that this arrangement was exercised with the real harness:
  it names the model, the tool definitions and the launch surface, which is
  everything Stewart supplies to the harness in every audit. Prepare captures
  the profile's exact text and hashes the executable. It launches nothing and
  never opens the configuration directory. A profile or its check grants no
  permission to start a session.

The launch surface digest
  A check must name the launch surface of the binary that prepares the audit.
  To learn it, prepare a question whose profile does not pass: a prepare
  refused as runtime_profile_invalid reports the surface schema, the SHA-256
  a check must name and the exact surface document in its data (use --json for
  the exact bytes), and a mismatch states both digests in its message. A
  rebuild that leaves the surface unchanged accepts the same profile.

Login and credentials
  The harness keeps its own subscription login, with paid extra usage
  disabled. Stewart holds no credential for this runtime. Run refuses --key-fd
  and the variables ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN, and it never
  falls back to the Messages API.

Running
  stewart run REF starts one placement: one fresh harness session with a
  deadline of placement-timeout-seconds, counted from the start. Each start
  uses one of max-placements, including a start whose authentication check
  fails, and nothing restarts automatically. Run stays in the foreground until
  the placement ends or reaches its deadline; callers with command timeouts
  should start it in the background. Usage is what the harness reports and may
  remain partial or unknown. The placement limits are not token or money caps,
  and help limits describes allowances that do not apply to a runtime question.
",
        placements = profile::MAX_PLACEMENTS,
        seconds = profile::MAX_SECONDS,
        profile = profile::PROFILE_SCHEMA,
    )
}

pub mod accounting;
pub mod arrangement;
pub mod events;
pub mod gate;
pub mod process;
pub mod profile;
pub mod run;
pub mod surface;
pub mod wire;

/// Convert only the transport field name, splicing the original schema bytes.
/// The harness assigns its MCP prefix; the core continues to use base names.
pub fn mcp_tools(bytes: &[u8]) -> Result<Vec<u8>, String> {
    use crate::json::{self, J};
    let parsed = json::parse(bytes).map_err(|e| e.to_string())?;
    let tools = parsed.as_arr().ok_or("expected the pinned tool array")?;
    let mut mapped = Vec::new();
    for tool in tools {
        let o = tool.obj("").map_err(|e| e.to_string())?;
        let schema = o.req("input_schema").map_err(|e| e.to_string())?;
        mapped.push(
            J::obj()
                .with("name", o.str("name").map_err(|e| e.to_string())?)
                .with(
                    "description",
                    o.str("description").map_err(|e| e.to_string())?,
                )
                .with(
                    "inputSchema",
                    J::Raw(bytes[schema.start..schema.end].to_vec()),
                ),
        );
    }
    Ok(J::Arr(mapped).bytes())
}
