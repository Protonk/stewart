//! Stewart: bounded audit commissions with faithful custody and verified return.
//!
//! This crate is the Rust audit service. `docs/INTERFACE.md` is the exact
//! interface it implements and `CONTRACTS.md` the behavioral authority. This
//! build holds the manager foundation: the reference and archive, the
//! submission folder, prepare and commission, receipt readback, status, and
//! close before launch. The run adapter and the auditor's tools come later.
//!
//! Layout:
//! - `json`: strict control JSON and the deterministic writer.
//! - `ids`: identifiers, handle checks and the `stw1:` reference.
//! - `platform`: the Linux-only calls, with development fallbacks.
//! - `fsx`: descriptor-relative filesystem access and exclusive writes.
//! - `archive`, `log`, `records`: the archive, its log and its records.
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

pub mod archive;
pub mod cli;
pub mod forms;
pub mod frontmatter;
pub mod fsx;
pub mod help;
pub mod ids;
pub mod json;
pub mod log;
pub mod ops;
pub mod platform;
pub mod records;
pub mod reply;
pub mod scan;
pub mod util;
