//! Development-only subscription harness adapter.
//!
//! Keep all adapter code here (or in child modules). Launch code constructs
//! its child environment in one function inside this boundary.
//! The build identifier is reachable through help so the release-absence
//! check has a firing control even under fat LTO.

pub(crate) const BUILD_NOTICE: &str = "Stewart development build: claude-code\n\
Claude Code questions require question/claude-code/1, runtime-profile, max-placements and placement-timeout-seconds.\n\
Harness login stays in Claude Code; --key-fd and API credentials are refused for this runtime.\n\
See docs/claude-code/CONTRACT.md for the development boundary and setup inputs.\n\n";

pub mod accounting;
pub mod arrangement;
pub mod events;
pub mod gate;
pub mod process;
pub mod profile;
pub mod run;
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
