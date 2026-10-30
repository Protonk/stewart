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
//! - `ops`, `help`, `cli`: manager operations and their presentation.
//! - `fault`: test-build failure points and sabotage controls.

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
