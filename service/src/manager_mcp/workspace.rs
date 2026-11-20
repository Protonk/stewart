//! The launcher's candidate workspace (MANAGER-PREPARATION "Filesystem
//! authority and interruption"): admission at launch, reading named sources
//! under `sources/`, and exclusive creation of one candidate folder.
//!
//! Every access below the workspace goes through descriptors with
//! `O_NOFOLLOW`; names are compared exactly, so a host that folds case or
//! normalization cannot substitute another entry. The checks cover this
//! workspace only; they are not operating-system confinement.

use crate::archive::STORE_FILE;
use crate::fsx::{self, Dir, Kind, ReadError};
use crate::intake::{self, Refusal};
use crate::util;
use std::collections::BTreeMap;
use std::io::{self, Write};

/// The directory name prefix of a delivery package (`names::package_name`).
pub(crate) const PACKAGE_PREFIX: &str = "stewart-return-";
/// The directory under the workspace that holds the caller's sources.
pub(crate) const SOURCES: &str = "sources";

pub(crate) struct Workspace {
    dir: Dir,
    /// DIR as given, for path comparisons and messages; never re-resolved.
    pub(crate) path: String,
    dev: u64,
}

/// Why a source could not be acquired.
pub(crate) enum Acquire {
    /// A path-policy violation (`candidate_path_invalid`).
    PathInvalid(String),
    /// The source cannot be opened or read, or changed (`candidate_source_failed`).
    Failed(String),
    /// Its bytes break an intake rule: the CLI diagnostic (`candidate_invalid`).
    Intake(Refusal),
}

/// What a creation established (the `writes` member).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct Writes {
    pub(crate) created: Vec<String>,
    pub(crate) incomplete: Vec<String>,
    /// A failed operation left an entry's existence unobservable.
    pub(crate) unknown: bool,
    /// Every proposed entry, for telling complete from partial.
    pub(crate) proposed: usize,
}

impl Writes {
    pub(crate) fn state(&self) -> &'static str {
        if self.unknown {
            "unknown"
        } else if self.created.is_empty() && self.incomplete.is_empty() {
            "none"
        } else if self.incomplete.is_empty() && self.created.len() == self.proposed {
            "complete"
        } else {
            "partial"
        }
    }
}

/// The result of an explicit creation.
pub(crate) enum Created {
    Done(Writes),
    /// The candidate name was taken when it was claimed.
    Exists,
    Failed(Writes, String),
}

fn errno(e: &io::Error) -> String {
    util::errno_name(e)
}

impl Workspace {
    /// Admit DIR at launch. DIR is already absolute in the CLI's form; it is
    /// opened following symlinks. Err is the usage error's reason.
    pub(crate) fn open(path: &str) -> Result<Workspace, String> {
        if let Some(c) = path.split('/').find(|c| c.starts_with(PACKAGE_PREFIX)) {
            return Err(format!(
                "--workspace {path:?} is inside a delivery package ({c}); choose a candidate-only workspace separate from archives and delivery locations"
            ));
        }
        let dir = Dir::open_follow(path).map_err(|e| match e.raw_os_error() {
            Some(libc::ENOENT) => format!("--workspace {path:?} does not exist"),
            Some(libc::ENOTDIR) => format!("--workspace {path:?} is not a directory"),
            _ => format!(
                "--workspace {path:?} cannot be opened: {}",
                util::describe(&e)
            ),
        })?;
        let dev = dir
            .stat()
            .map_err(|e| {
                format!(
                    "--workspace {path:?} cannot be examined: {}",
                    util::describe(&e)
                )
            })?
            .dev;
        let workspace = Workspace {
            dir,
            path: path.to_string(),
            dev,
        };
        workspace.check_store()?;
        Ok(workspace)
    }

    /// Refuse a workspace in a Stewart store: look for the store marker in
    /// the workspace and each actual parent, reached through `..` from the
    /// held descriptor (metadata only; parents need only search permission).
    fn check_store(&self) -> Result<(), String> {
        let path = &self.path;
        let mut up = String::new();
        let mut id = self
            .dir
            .stat()
            .map_err(|e| format!("{path:?} cannot be examined: {}", util::describe(&e)))?
            .id();
        for _ in 0..4096 {
            match self.dir.stat_at(&format!("{up}{STORE_FILE}")) {
                Ok(_) => {
                    return Err(format!(
                        "--workspace {path:?} is inside a Stewart store ({up}{STORE_FILE} exists); choose a candidate-only workspace separate from archives and delivery locations"
                    ));
                }
                Err(e) if e.raw_os_error() == Some(libc::ENOENT) => {}
                Err(e) => {
                    return Err(format!(
                        "the ancestry of --workspace {path:?} cannot be examined for a Stewart store: {}",
                        util::describe(&e)
                    ));
                }
            }
            let parent = self
                .dir
                .stat_at_bytes(format!("{up}..").as_bytes(), false)
                .map_err(|e| {
                    format!(
                        "the ancestry of --workspace {path:?} cannot be examined: {}",
                        util::describe(&e)
                    )
                })?
                .id();
            if parent == id {
                return Ok(());
            }
            id = parent;
            up.push_str("../");
        }
        Err(format!(
            "the ancestry of --workspace {path:?} is deeper than 4096 levels"
        ))
    }

    /// The per-call check: DIR still opens as the admitted directory and is
    /// still outside any Stewart store.
    pub(crate) fn recheck(&self) -> Result<(), String> {
        let path = &self.path;
        let held = self.dir.stat().map_err(|e| {
            format!(
                "the workspace {path:?} cannot be examined: {}",
                util::describe(&e)
            )
        })?;
        let now = Dir::open_follow(path).and_then(|d| d.stat()).map_err(|e| {
            format!(
                "the workspace {path:?} no longer opens as a directory: {}",
                util::describe(&e)
            )
        })?;
        if now.id() != held.id() {
            return Err(format!(
                "the workspace {path:?} was removed or replaced since the server started; restart it with the intended --workspace"
            ));
        }
        self.check_store()
    }

    /// Whether an entry with this name exists, under the host's name rules.
    pub(crate) fn exists(&self, name: &str) -> io::Result<bool> {
        self.dir.exists(name)
    }

    /// The dry-run sabotage: claim the candidate directory anyway.
    pub(crate) fn sabotage_claim(&self, name: &str) {
        let _ = self.dir.mkdir(name);
    }

    /// Read `sources/<from>` for the public material `public`, applying the
    /// path policy, then access, then the intake text rule and bounds with
    /// `prior` bytes already counted. `index` is the file's 1-based count.
    pub(crate) fn acquire(
        &self,
        from: &str,
        public: &str,
        index: usize,
        prior: u64,
    ) -> Result<Vec<u8>, Acquire> {
        let shown = format!("{SOURCES}/{from}");
        let components: Vec<&str> = std::iter::once(SOURCES).chain(from.split('/')).collect();
        let (file_name, directories) = components.split_last().expect("at least sources/");
        let mut held: Option<Dir> = None;
        let mut at = String::new();
        for component in directories {
            let parent = held.as_ref().unwrap_or(&self.dir);
            at = if at.is_empty() {
                component.to_string()
            } else {
                format!("{at}/{component}")
            };
            let st = self.entry(parent, component, &at)?;
            match st.kind {
                Kind::Dir => {}
                Kind::File => {
                    return Err(Acquire::Failed(format!(
                        "{at} is a regular file, so {shown} cannot be opened."
                    )));
                }
                other => {
                    return Err(Acquire::PathInvalid(format!(
                        "{at} is a {}; sources are reached through directories only, without links or special entries.",
                        other.name()
                    )));
                }
            }
            let dir = parent.open_dir(component).map_err(|e| {
                Acquire::Failed(format!("{at} cannot be opened: {}.", util::describe(&e)))
            })?;
            let opened = dir.stat().map_err(|e| {
                Acquire::Failed(format!("{at} cannot be examined: {}.", util::describe(&e)))
            })?;
            if opened.id() != st.id() {
                return Err(Acquire::Failed(format!(
                    "{at} changed while it was opened."
                )));
            }
            match dir.exists(STORE_FILE) {
                Ok(false) => {}
                Ok(true) => {
                    return Err(Acquire::PathInvalid(format!(
                        "{at} holds {STORE_FILE}: it is a Stewart store, which the workspace never reads."
                    )));
                }
                Err(e) => {
                    return Err(Acquire::Failed(format!(
                        "{at} cannot be examined for a store marker: {}.",
                        util::describe(&e)
                    )));
                }
            }
            held = Some(dir);
        }
        let parent = held.as_ref().unwrap_or(&self.dir);
        let st = self.entry(parent, file_name, &shown)?;
        if st.kind != Kind::File {
            return Err(Acquire::PathInvalid(format!(
                "{shown} is a {}; a source is a regular file, never a link, directory or special entry.",
                st.kind.name()
            )));
        }
        let (file, opened) = parent.open_regular(file_name).map_err(|e| match e {
            ReadError::NotRegular(k) => Acquire::PathInvalid(format!(
                "{shown} is a {}; a source is a regular file.",
                k.name()
            )),
            other => Acquire::Failed(format!("{shown} cannot be opened: {}.", other.describe())),
        })?;
        if opened.id() != st.id() {
            return Err(Acquire::Failed(format!(
                "{shown} changed while it was opened."
            )));
        }
        let links = fsx::link_count(&file).map_err(|e| {
            Acquire::Failed(format!(
                "{shown} cannot be examined: {}.",
                util::describe(&e)
            ))
        })?;
        if links > 1 {
            return Err(Acquire::PathInvalid(format!(
                "{shown} has {links} hard links; a source must have exactly one, so no other name can alias it."
            )));
        }
        intake::check_file(public, index, opened.size, prior).map_err(Acquire::Intake)?;
        let bytes = crate::scan::read_material(file, &opened, public, prior).map_err(|r| {
            if r.reason == "bound_exceeded" {
                Acquire::Intake(r)
            } else {
                Acquire::Failed(format!(
                    "{shown} could not be read completely or changed while it was read: {}",
                    r.message
                ))
            }
        })?;
        intake::check_text(public, &bytes).map_err(Acquire::Intake)?;
        Ok(bytes)
    }

    /// Classify one component under `parent` without following it. The
    /// exact name must be an entry of the directory, and the entry must be
    /// on the workspace's filesystem.
    fn entry(&self, parent: &Dir, name: &str, shown: &str) -> Result<fsx::Stat, Acquire> {
        let absent = || {
            Acquire::Failed(format!(
                "{shown} is absent: no entry of its directory has exactly that name."
            ))
        };
        let st = match parent.stat_at(name) {
            Ok(st) => st,
            Err(e) if e.raw_os_error() == Some(libc::ENOENT) => return Err(absent()),
            Err(e) => {
                return Err(Acquire::Failed(format!(
                    "{shown} cannot be examined: {}.",
                    util::describe(&e)
                )));
            }
        };
        let (names, _) = parent.names_bounded(usize::MAX).map_err(|e| {
            Acquire::Failed(format!(
                "the directory of {shown} cannot be listed: {}.",
                util::describe(&e)
            ))
        })?;
        if !names.iter().any(|n| n.as_slice() == name.as_bytes()) {
            return Err(absent());
        }
        if st.dev != self.dev {
            return Err(Acquire::PathInvalid(format!(
                "{shown} is on another filesystem; sources may not cross a mount below the workspace."
            )));
        }
        Ok(st)
    }

    /// Create the candidate `name` with its directories and files, in that
    /// order, each exclusively and each file verified by rereading.
    /// `directories` and `files` are candidate-relative and sorted; a
    /// parent always precedes its children.
    pub(crate) fn create(
        &self,
        name: &str,
        directories: &[&str],
        files: &[(&str, &[u8])],
    ) -> Created {
        let overwrite = crate::sabotage!("candidate_overwrites_existing");
        let mut w = Writes {
            proposed: 1 + directories.len() + files.len(),
            ..Writes::default()
        };
        // One step's failure: stop, keep what was established.
        macro_rules! fail {
            ($w:expr, $($msg:tt)*) => {{
                let message = format!($($msg)*);
                return Created::Failed($w, message);
            }};
        }
        // Entries count in creation order, as the created list does.
        macro_rules! entry_done {
            ($w:expr, $rel:expr) => {{
                $w.created.push($rel);
                if let Err(e) =
                    crate::fault!("candidate.after_entry", &$w.created.len().to_string())
                {
                    fail!(
                        $w,
                        "Creation stopped after {} ({}).",
                        $w.created.last().unwrap(),
                        errno(&e)
                    );
                }
            }};
        }

        match self.dir.mkdir(name) {
            Ok(()) => {}
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) && !overwrite => {
                return Created::Exists;
            }
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {}
            Err(e) => {
                w.unknown = !matches!(self.dir.stat_at(name), Err(ref s) if s.raw_os_error() == Some(libc::ENOENT));
                fail!(
                    w,
                    "Creating the candidate directory {name} failed ({}).",
                    errno(&e)
                );
            }
        }
        let candidate = match self.dir.open_dir(name) {
            Ok(d) => d,
            Err(e) => {
                w.created.push(name.to_string());
                fail!(
                    w,
                    "The new candidate directory {name} cannot be opened ({}).",
                    errno(&e)
                );
            }
        };
        if let Err(e) = self.dir.sync() {
            w.created.push(name.to_string());
            fail!(
                w,
                "Synchronizing the workspace after creating {name} failed ({}).",
                errno(&e)
            );
        }
        entry_done!(w, name.to_string());

        let mut held: BTreeMap<&str, Dir> = BTreeMap::new();
        for &rel in directories {
            let (parent_rel, component) = rel.rsplit_once('/').unwrap_or(("", rel));
            let parent = if parent_rel.is_empty() {
                &candidate
            } else {
                &held[parent_rel]
            };
            let shown = format!("{name}/{rel}");
            match parent.mkdir(component) {
                Ok(()) => {}
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) && overwrite => {}
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {
                    fail!(
                        w,
                        "{shown} already exists in the new candidate; creation stopped."
                    );
                }
                Err(e) => {
                    w.unknown = !matches!(parent.stat_at(component), Err(ref s) if s.raw_os_error() == Some(libc::ENOENT));
                    fail!(w, "Creating {shown} failed ({}).", errno(&e));
                }
            }
            let dir = match parent.open_dir(component) {
                Ok(d) => d,
                Err(e) => {
                    w.created.push(shown.clone());
                    fail!(
                        w,
                        "The new directory {shown} cannot be opened ({}).",
                        errno(&e)
                    );
                }
            };
            if let Err(e) = parent.sync() {
                w.created.push(shown.clone());
                fail!(
                    w,
                    "Synchronizing after creating {shown} failed ({}).",
                    errno(&e)
                );
            }
            entry_done!(w, shown);
            held.insert(rel, dir);
        }

        for &(rel, bytes) in files {
            let (parent_rel, component) = rel.rsplit_once('/').unwrap_or(("", rel));
            let parent = if parent_rel.is_empty() {
                &candidate
            } else {
                &held[parent_rel]
            };
            let shown = format!("{name}/{rel}");
            let created = match parent.create_excl(component) {
                Ok(f) => Ok(f),
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) && overwrite => {
                    #[cfg(feature = "sabotage")]
                    let reopened = parent.sabotage_open_truncate(component);
                    #[cfg(not(feature = "sabotage"))]
                    let reopened = Err(e);
                    reopened
                }
                Err(e) => Err(e),
            };
            let mut file = match created {
                Ok(f) => f,
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {
                    fail!(
                        w,
                        "{shown} already exists in the new candidate; creation stopped."
                    );
                }
                Err(e) => {
                    w.incomplete.push(shown.clone());
                    fail!(w, "Creating {shown} failed ({}).", errno(&e));
                }
            };
            let written = crate::fault!("candidate.entry_write", rel)
                .and_then(|_| file.write_all(bytes))
                .and_then(|_| file.sync_all())
                .and_then(|_| parent.sync());
            if let Err(e) = written {
                w.incomplete.push(shown.clone());
                fail!(w, "Writing {shown} failed ({}).", errno(&e));
            }
            #[cfg(feature = "fault-injection")]
            if crate::fault_corrupt!("candidate.entry_corrupt", rel) {
                let _ = parent.corrupt_file(component);
            }
            if let Err(problem) = verify(parent, component, &file, bytes) {
                w.incomplete.push(shown.clone());
                fail!(w, "{shown} did not verify: {problem}.");
            }
            entry_done!(w, shown);
        }
        Created::Done(w)
    }
}

/// Reread a file just written through a fresh descriptor and compare its
/// identity with the writer's and its bytes with the proposal.
fn verify(
    parent: &Dir,
    component: &str,
    written: &std::fs::File,
    bytes: &[u8],
) -> Result<(), String> {
    let identity = fsx::fstat(written).map_err(|e| util::describe(&e))?.id();
    let (file, st) = parent.open_regular(component).map_err(|e| e.describe())?;
    if st.id() != identity {
        return Err("another entry replaced it".into());
    }
    let read = fsx::read_bounded(file, &st, bytes.len() as u64).map_err(|e| e.describe())?;
    if read != bytes {
        return Err("its bytes differ from the proposal".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn writes(created: usize, incomplete: usize, unknown: bool) -> Writes {
        Writes {
            created: (0..created).map(|i| format!("c/{i}")).collect(),
            incomplete: (0..incomplete).map(|i| format!("c/f{i}")).collect(),
            unknown,
            proposed: 4,
        }
    }

    /// The writes state names what creation established (MANAGER-PREPARATION
    /// "Creation order"): an incomplete file keeps the state partial even
    /// when every other entry exists, and an unobservable effect is unknown.
    #[test]
    fn the_writes_state_follows_what_was_established() {
        assert_eq!(writes(0, 0, false).state(), "none");
        assert_eq!(writes(4, 0, false).state(), "complete");
        assert_eq!(writes(2, 0, false).state(), "partial");
        assert_eq!(writes(3, 1, false).state(), "partial");
        assert_eq!(writes(0, 1, false).state(), "partial");
        assert_eq!(writes(0, 0, true).state(), "unknown");
        assert_eq!(writes(2, 1, true).state(), "unknown");
    }

    /// The reserved prefix is the one delivery gives package directories.
    #[test]
    fn the_package_prefix_is_the_delivery_package_prefix() {
        assert!(crate::names::package_name("aqm3x7kd2hz5vw4ny", 1).starts_with(PACKAGE_PREFIX));
    }
}
