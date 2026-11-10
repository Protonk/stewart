//! Development-only runtime boundary. No harness is launched yet.
//!
//! Keep all adapter code here (or in child modules). Future launch code must
//! construct its child environment in one function inside this boundary.
//! The build identifier is reachable through help so the release-absence
//! check has a firing control even under fat LTO.

pub(crate) const BUILD_NOTICE: &str = "Stewart development build: claude-code\n\
Claude Code adapter not implemented; run uses the Messages API.\n\n";
