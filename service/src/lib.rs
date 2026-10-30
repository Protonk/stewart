//! Stewart: bounded audit commissions with faithful custody and verified return.
//!
//! This crate is the Rust audit service. `docs/INTERFACE.md` is the exact
//! interface it implements and `CONTRACTS.md` the behavioral authority. It
//! holds the whole audit: the reference and archive, the submission folder,
//! prepare and commission, receipt readback, the run adapter and the
//! auditor's tools, seal, delivery, status, and close from every state.
//!
//! Layout:
//! - `json`: strict control JSON and the deterministic writer.
//! - `util`: digests, UTC timestamps, errno names and edit distance.
//! - `ids`: identifiers, handle checks and the `stw1:` reference.
//! - `platform`: the Linux-only calls, with development fallbacks.
//! - `fsx`: descriptor-relative filesystem access and exclusive writes.
//! - `archive`, `log`, `records`: the archive, its log and its records.
//! - `bodies`: the log record bodies after launch; `usage`: allowances.
//! - `names`: generated archive names and numbered claims.
//! - `runs`: run directories, raw captures and their linked records.
//! - `returns`: the return manifest and delivery plans.
//! - `world`: a placement's verified captures and pinned arrangement.
//! - `answer`, `delivery`: the auditor's tools, preparation and seal; delivery.
//! - `provider`: the provider transport and the placement loop.
//! - `frontmatter`, `scan`, `forms`: the submission folder and the arrangement.
//! - `reply`: the `stewart.reply/1` envelope and its human presentation.
//! - `ops`, `help`, `cli`: manager operations and their presentation.
//! - `fault`: test-build failure points and sabotage controls.
//!
//! Calling libc: in the fat-LTO static release build, a function that std
//! also declares weak (for its own fallback) can link to nothing when this
//! crate calls it through `libc::`, because LTO merges the two declarations
//! and std's weak one wins. Such a call silently does nothing on aarch64 and
//! crashes on x86_64, and debug, thin-LTO and macOS builds never show it.
//! Make these calls through `libc::syscall` instead, as
//! `platform::random_fill` does. For the musl targets and the pinned
//! toolchain they are `getrandom`, `copy_file_range`, `gettid`,
//! `pidfd_spawnp` and `pidfd_getpid`. The list depends on target and
//! toolchain: when either changes, recheck which of std's `weak!` and
//! `syscall!` uses under `library/std/src/sys` compile for it.

// Refusals carry their account (reason, message, retained locations, causes,
// data, next calls) by value; boxing them would add noise without benefit.
#![allow(
    clippy::result_large_err,
    clippy::collapsible_if,
    clippy::too_many_arguments
)]

#[macro_use]
pub mod fault;

pub mod answer;
pub mod archive;
pub mod bodies;
pub mod cli;
pub mod delivery;
pub mod forms;
pub mod frontmatter;
pub mod fsx;
pub mod help;
pub mod ids;
pub mod json;
pub mod log;
pub mod names;
pub mod ops;
pub mod platform;
pub mod provider;
pub mod records;
pub mod reply;
pub mod returns;
pub mod runs;
pub mod scan;
pub mod usage;
pub mod util;
pub mod world;
