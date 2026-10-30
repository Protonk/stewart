//! The submission folder scan (INTERFACE 3.1, 3.3).
//!
//! The scan walks through descriptors opened relative to the folder with
//! `O_NOFOLLOW`, classifies entries with `fstatat(AT_SYMLINK_NOFOLLOW)`, opens
//! regular files with `O_NONBLOCK` and rechecks their type on the descriptor.
//! Bounds are enforced while scanning: no directory listing, file read or
//! running total is allowed to grow past its bound before it is refused.

use crate::frontmatter::first_non_text;
use crate::fsx::{self, Dir, Kind, ReadError, Stat};
use crate::json::J;
use crate::util;
use std::collections::BTreeMap;

pub const QUESTION_BYTES: u64 = 262_144;
pub const FILES: usize = 128;
pub const FILE_BYTES: u64 = 16_777_216;
pub const TOTAL_BYTES: u64 = 134_217_728;
pub const DIRECTORIES: usize = 256;
pub const PATH_BYTES: usize = 1024;
pub const PATH_COMPONENTS: usize = 32;
pub const COMPONENT_BYTES: usize = 255;

pub fn bounds_j() -> J {
    J::obj()
        .with("question_bytes", QUESTION_BYTES)
        .with("files", FILES)
        .with("file_bytes", FILE_BYTES)
        .with("total_bytes", TOTAL_BYTES)
        .with("directories", DIRECTORIES)
        .with("path_bytes", PATH_BYTES)
        .with("path_components", PATH_COMPONENTS)
        .with("component_bytes", COMPONENT_BYTES)
}

/// A mechanical intake refusal: stable reason, sentence, and the entry.
#[derive(Debug)]
pub struct Refusal {
    pub reason: &'static str,
    pub message: String,
    pub data: J,
}

fn refusal(reason: &'static str, message: impl Into<String>, data: J) -> Refusal {
    Refusal {
        reason,
        message: message.into(),
        data,
    }
}

fn bound(name: &'static str, limit: u64, entry: &str, observed: u64) -> Refusal {
    refusal(
        "bound_exceeded",
        format!(
            "{entry} exceeds the {name} bound of {limit} (observed at least {observed}); nothing was excluded silently."
        ),
        J::obj()
            .with("bound", name)
            .with("limit", limit)
            .with("entry", entry)
            .with("observed", observed),
    )
}

/// Locations a scanned directory must not be (INTERFACE 3.3).
pub struct Exclude {
    pub ids: Vec<((u64, u64), String)>,
}

pub struct QuestionFile {
    pub bytes: Vec<u8>,
    pub stat: Stat,
}

#[derive(Debug, Clone)]
pub struct Material {
    /// Public name, `materials/<path>`.
    pub name: String,
    pub stat: Stat,
    pub sha256: String,
    pub lines: u64,
}

#[derive(Debug, Clone)]
pub struct DirEntry {
    /// `materials` or `materials/<path>`.
    pub name: String,
    pub stat: Stat,
}

pub struct Scan {
    pub question: QuestionFile,
    pub files: Vec<Material>,
    pub dirs: Vec<DirEntry>,
}

impl Scan {
    pub fn material_bytes(&self) -> u64 {
        self.files.iter().map(|m| m.stat.size).sum()
    }
}

/// Lines: LF count, plus one if the file is non-empty and does not end in LF.
pub fn line_count(bytes: &[u8]) -> u64 {
    let lf = bytes.iter().filter(|b| **b == b'\n').count() as u64;
    if !bytes.is_empty() && *bytes.last().expect("non-empty") != b'\n' {
        lf + 1
    } else {
        lf
    }
}

fn nofollow() -> bool {
    !crate::sabotage!("follow_symlinks")
}

/// Check the folder's root: exactly `question.md` (a regular file) and
/// `materials/` (a directory).
pub fn check_root(folder: &Dir) -> Result<(), Refusal> {
    let (names, more) = folder.names_bounded(64).map_err(|e| {
        refusal(
            "source_unreadable",
            format!(
                "The folder {} cannot be listed: {}.",
                folder.path,
                util::describe(&e)
            ),
            J::obj()
                .with("entry", folder.path.as_str())
                .with("error", util::errno_name(&e)),
        )
    })?;
    let has = |n: &str| names.iter().any(|x| x == n.as_bytes());
    let missing: Vec<&str> = ["question.md", "materials"]
        .into_iter()
        .filter(|n| !has(n))
        .collect();
    if !missing.is_empty() {
        return Err(refusal(
            "folder_incomplete",
            format!(
                "The folder {} has no {}; it needs exactly question.md and materials/.",
                folder.path,
                missing.join(" and no ")
            ),
            J::obj().with("missing", crate::json::strs(&missing)),
        ));
    }
    let mut extra: Vec<String> = names
        .iter()
        .filter(|n| n.as_slice() != b"question.md" && n.as_slice() != b"materials")
        .map(|n| String::from_utf8_lossy(n).into_owned())
        .collect();
    extra.sort();
    if let Some(first) = extra.first() {
        let more_note = if more { " (and possibly more)" } else { "" };
        return Err(refusal(
            "unexpected_root_entry",
            format!(
                "{first:?} is at the root of the folder{more_note}. The root holds only question.md and materials/: move it under materials/ if the auditor should read it, or out of the folder."
            ),
            J::obj().with("entries", crate::json::strs(&extra)),
        ));
    }
    for (name, want) in [("question.md", Kind::File), ("materials", Kind::Dir)] {
        let st = folder
            .stat_at_bytes(name.as_bytes(), nofollow())
            .map_err(|e| {
                refusal(
                    "source_unreadable",
                    format!("{name} cannot be examined: {}.", util::describe(&e)),
                    J::obj().with("entry", name),
                )
            })?;
        if st.kind != want {
            return Err(refusal(
                "unsupported_entry",
                format!(
                    "{name} is a {}; it must be a {}. Links and special files are refused unread.",
                    st.kind.name(),
                    want.name()
                ),
                J::obj().with("entry", name).with("type", st.kind.name()),
            ));
        }
    }
    Ok(())
}

/// Read `question.md` under its bound and the text reader rule.
pub fn read_question(folder: &Dir) -> Result<QuestionFile, Refusal> {
    let (f, st) = folder
        .open_regular_bytes(b"question.md", nofollow())
        .map_err(|e| source_error("question.md", e))?;
    if st.size > QUESTION_BYTES {
        return Err(bound(
            "question_bytes",
            QUESTION_BYTES,
            "question.md",
            st.size,
        ));
    }
    let bytes = fsx::read_bounded(f, &st, QUESTION_BYTES).map_err(|e| match e {
        ReadError::TooLarge { size, .. } => {
            bound("question_bytes", QUESTION_BYTES, "question.md", size)
        }
        other => source_error("question.md", other),
    })?;
    if let Some(off) = first_non_text(&bytes) {
        return Err(not_text("question.md", off));
    }
    Ok(QuestionFile { bytes, stat: st })
}

fn not_text(entry: &str, offset: usize) -> Refusal {
    refusal(
        "material_not_text",
        format!(
            "{entry} is not valid UTF-8 text without NUL: the first invalid byte is at offset {offset}. The reader (utf8-text/1) serves exact text only; supply a text export."
        ),
        J::obj().with("entry", entry).with("offset", offset as u64),
    )
}

pub fn source_error(entry: &str, e: ReadError) -> Refusal {
    match e {
        ReadError::NotRegular(k) => refusal(
            "unsupported_entry",
            format!(
                "{entry} is a {}; only regular files and directories are admitted, and links and special files are refused unread.",
                k.name()
            ),
            J::obj().with("entry", entry).with("type", k.name()),
        ),
        ReadError::Io(err) => refusal(
            "source_unreadable",
            format!(
                "{entry} could not be opened or read: {}.",
                util::describe(&err)
            ),
            J::obj()
                .with("entry", entry)
                .with("error", util::errno_name(&err)),
        ),
        ReadError::Missing => refusal(
            "source_unreadable",
            format!("{entry} disappeared while the folder was being scanned."),
            J::obj().with("entry", entry).with("error", "ENOENT"),
        ),
        ReadError::Changed => refusal(
            "source_unreadable",
            format!("{entry} changed while it was being read; finish editing, then prepare again."),
            J::obj()
                .with("entry", entry)
                .with("error", "changed_during_read"),
        ),
        ReadError::TooLarge { size, limit } => bound("file_bytes", limit, entry, size),
    }
}

fn check_name(raw: &[u8], parent: &str) -> Result<String, Refusal> {
    let Ok(s) = std::str::from_utf8(raw) else {
        let shown = format!("{parent}/{}", String::from_utf8_lossy(raw));
        return Err(refusal(
            "name_invalid",
            format!(
                "{shown:?} is not a valid UTF-8 name; names are kept exactly, so rename it with ordinary tools."
            ),
            J::obj().with("entry", shown),
        ));
    };
    if s.chars()
        .any(|c| (c as u32) <= 0x1F || (0x7F..=0x9F).contains(&(c as u32)))
    {
        let shown = format!("{parent}/{s}");
        return Err(refusal(
            "name_invalid",
            format!(
                "{shown:?} contains a control character; names are kept exactly, so rename it with ordinary tools."
            ),
            J::obj().with("entry", shown),
        ));
    }
    if raw.len() > COMPONENT_BYTES {
        return Err(bound(
            "component_bytes",
            COMPONENT_BYTES as u64,
            &format!("{parent}/{s}"),
            raw.len() as u64,
        ));
    }
    Ok(s.to_string())
}

/// Scan `materials/` fully, reading and hashing each file.
pub fn scan(folder: &Dir, exclude: &Exclude) -> Result<Scan, Refusal> {
    check_root(folder)?;
    let question = read_question(folder)?;
    let mut total = question.stat.size;
    let mut files: Vec<Material> = Vec::new();
    let mut dirs: Vec<DirEntry> = Vec::new();

    let root = folder
        .open_dir_bytes(b"materials", nofollow())
        .map_err(|e| {
            refusal(
                "source_unreadable",
                format!("materials/ cannot be opened: {}.", util::describe(&e)),
                J::obj().with("entry", "materials"),
            )
        })?;
    // (directory, public name, components below materials/)
    let mut stack: Vec<(Dir, String, usize)> = Vec::new();
    let st = root.stat().map_err(|e| {
        refusal(
            "source_unreadable",
            format!("materials/ cannot be examined: {}.", util::describe(&e)),
            J::obj().with("entry", "materials"),
        )
    })?;
    check_excluded(&st, "materials", exclude)?;
    dirs.push(DirEntry {
        name: "materials".into(),
        stat: st,
    });
    stack.push((root, "materials".into(), 0));

    while let Some((dir, public, depth)) = stack.pop() {
        let budget = FILES + DIRECTORIES + 1;
        let (mut names, _) = dir.names_bounded(budget).map_err(|e| {
            refusal(
                "source_unreadable",
                format!("{public}/ cannot be listed: {}.", util::describe(&e)),
                J::obj()
                    .with("entry", public.as_str())
                    .with("error", util::errno_name(&e)),
            )
        })?;
        names.sort();
        for raw in names {
            if crate::sabotage!("skip_hidden_entries") && raw.starts_with(b".") {
                continue;
            }
            let name = check_name(&raw, &public)?;
            let child = format!("{public}/{name}");
            let rel_len = child.len() - "materials/".len();
            if rel_len > PATH_BYTES {
                return Err(bound(
                    "path_bytes",
                    PATH_BYTES as u64,
                    &child,
                    rel_len as u64,
                ));
            }
            if depth + 1 > PATH_COMPONENTS {
                return Err(bound(
                    "path_components",
                    PATH_COMPONENTS as u64,
                    &child,
                    (depth + 1) as u64,
                ));
            }
            let st = dir.stat_at_bytes(&raw, nofollow()).map_err(|e| {
                refusal(
                    "source_unreadable",
                    format!("{child} cannot be examined: {}.", util::describe(&e)),
                    J::obj()
                        .with("entry", child.as_str())
                        .with("error", util::errno_name(&e)),
                )
            })?;
            match st.kind {
                Kind::Dir => {
                    if dirs.len() + 1 > DIRECTORIES {
                        return Err(bound(
                            "directories",
                            DIRECTORIES as u64,
                            &child,
                            (dirs.len() + 1) as u64,
                        ));
                    }
                    check_excluded(&st, &child, exclude)?;
                    let sub = dir.open_dir_bytes(&raw, nofollow()).map_err(|e| {
                        refusal(
                            "source_unreadable",
                            format!("{child}/ cannot be opened: {}.", util::describe(&e)),
                            J::obj()
                                .with("entry", child.as_str())
                                .with("error", util::errno_name(&e)),
                        )
                    })?;
                    let held = sub.stat().map_err(|e| {
                        refusal(
                            "source_unreadable",
                            format!("{child}/ cannot be examined: {}.", util::describe(&e)),
                            J::obj().with("entry", child.as_str()),
                        )
                    })?;
                    if held.id() != st.id() {
                        return Err(source_error(&child, ReadError::Changed));
                    }
                    dirs.push(DirEntry {
                        name: child.clone(),
                        stat: st,
                    });
                    stack.push((sub, child, depth + 1));
                }
                Kind::File => {
                    if files.len() + 1 > FILES {
                        return Err(bound(
                            "files",
                            FILES as u64,
                            &child,
                            (files.len() + 1) as u64,
                        ));
                    }
                    if st.size > FILE_BYTES {
                        return Err(bound("file_bytes", FILE_BYTES, &child, st.size));
                    }
                    if total + st.size > TOTAL_BYTES {
                        return Err(bound("total_bytes", TOTAL_BYTES, &child, total + st.size));
                    }
                    let (f, held) = dir
                        .open_regular_bytes(&raw, nofollow())
                        .map_err(|e| source_error(&child, e))?;
                    if held.id() != st.id() {
                        return Err(source_error(&child, ReadError::Changed));
                    }
                    let bytes = fsx::read_bounded(f, &held, FILE_BYTES)
                        .map_err(|e| source_error(&child, e))?;
                    if let Some(off) = first_non_text(&bytes) {
                        return Err(not_text(&child, off));
                    }
                    total += bytes.len() as u64;
                    files.push(Material {
                        name: child,
                        stat: held,
                        sha256: util::sha256_hex(&bytes),
                        lines: line_count(&bytes),
                    });
                }
                other => {
                    return Err(refusal(
                        "unsupported_entry",
                        format!(
                            "{child} is a {}; only regular files and directories are admitted. It was not followed or read.",
                            other.name()
                        ),
                        J::obj()
                            .with("entry", child.as_str())
                            .with("type", other.name()),
                    ));
                }
            }
        }
    }
    files.sort_by(|a, b| a.name.as_bytes().cmp(b.name.as_bytes()));
    dirs.sort_by(|a, b| a.name.as_bytes().cmp(b.name.as_bytes()));
    Ok(Scan {
        question,
        files,
        dirs,
    })
}

fn check_excluded(st: &Stat, entry: &str, exclude: &Exclude) -> Result<(), Refusal> {
    for (id, what) in &exclude.ids {
        if *id == st.id() {
            return Err(refusal(
                "location_overlap",
                format!(
                    "{entry} is the {what} (same device and inode); the folder, archive and destination must not contain one another."
                ),
                J::obj()
                    .with("entry", entry)
                    .with("location", what.as_str()),
            ));
        }
    }
    Ok(())
}

/// Membership and identity observed by a metadata-only rescan.
pub struct Rescan {
    /// Every entry by name: `question.md`, root extras, `materials`, and
    /// `materials/…` files, directories and other entries.
    pub entries: BTreeMap<String, Stat>,
    /// Why the rescan could not see everything (listing failures, bounds).
    pub incomplete: Vec<String>,
}

/// Walk the folder again without reading contents (commission step 4).
pub fn rescan(folder: &Dir) -> Rescan {
    let mut entries = BTreeMap::new();
    let mut incomplete = Vec::new();
    let cap = FILES + DIRECTORIES + 64;
    match folder.names_bounded(64) {
        Ok((names, more)) => {
            if more {
                incomplete.push("the folder root holds more than 64 entries".to_string());
            }
            for raw in names {
                let name = String::from_utf8_lossy(&raw).into_owned();
                match folder.stat_at_bytes(&raw, nofollow()) {
                    Ok(st) => {
                        entries.insert(name, st);
                    }
                    Err(e) => incomplete.push(format!("{name}: {}", util::describe(&e))),
                }
            }
        }
        Err(e) => incomplete.push(format!("folder root: {}", util::describe(&e))),
    }
    if entries.get("materials").map(|s| s.kind) == Some(Kind::Dir) {
        if let Ok(root) = folder.open_dir_bytes(b"materials", nofollow()) {
            let mut stack = vec![(root, "materials".to_string(), 0usize)];
            while let Some((dir, public, depth)) = stack.pop() {
                let (names, more) = match dir.names_bounded(cap) {
                    Ok(x) => x,
                    Err(e) => {
                        incomplete.push(format!("{public}: {}", util::describe(&e)));
                        continue;
                    }
                };
                if more {
                    incomplete.push(format!("{public} holds more entries than the bounds admit"));
                }
                for raw in names {
                    if crate::sabotage!("skip_hidden_entries") && raw.starts_with(b".") {
                        continue;
                    }
                    let child = format!("{public}/{}", String::from_utf8_lossy(&raw));
                    match dir.stat_at_bytes(&raw, nofollow()) {
                        Ok(st) => {
                            if st.kind == Kind::Dir && depth < PATH_COMPONENTS {
                                match dir.open_dir_bytes(&raw, nofollow()) {
                                    Ok(sub) => stack.push((sub, child.clone(), depth + 1)),
                                    Err(e) => {
                                        incomplete.push(format!("{child}: {}", util::describe(&e)))
                                    }
                                }
                            }
                            entries.insert(child, st);
                        }
                        Err(e) => incomplete.push(format!("{child}: {}", util::describe(&e))),
                    }
                    if entries.len() > cap {
                        incomplete
                            .push("the folder holds more entries than the bounds admit".into());
                        return Rescan {
                            entries,
                            incomplete,
                        };
                    }
                }
            }
        } else {
            incomplete.push("materials/ cannot be opened".into());
        }
    }
    Rescan {
        entries,
        incomplete,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;

    struct Tmp(std::path::PathBuf);
    impl Drop for Tmp {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    fn tmp() -> (Tmp, String) {
        let base = std::fs::canonicalize(std::env::temp_dir()).unwrap();
        let p = base.join(format!(
            "stewart-scan-{}",
            crate::ids::random_token().unwrap()
        ));
        std::fs::create_dir(&p).unwrap();
        let s = p.to_str().unwrap().to_string();
        (Tmp(p), s)
    }
    fn folder(question: &[u8]) -> (Tmp, String) {
        let (t, p) = tmp();
        std::fs::write(format!("{p}/question.md"), question).unwrap();
        std::fs::create_dir(format!("{p}/materials")).unwrap();
        (t, p)
    }
    fn run(p: &str) -> Result<Scan, Refusal> {
        scan(&Dir::open_follow(p).unwrap(), &Exclude { ids: vec![] })
    }

    #[test]
    fn admits_hidden_empty_and_nested_entries_in_bytewise_order() {
        let (_t, p) = folder(b"q");
        std::fs::create_dir_all(format!("{p}/materials/a/empty")).unwrap();
        std::fs::write(format!("{p}/materials/a.txt"), b"x\r\ny").unwrap();
        std::fs::write(format!("{p}/materials/a/b"), b"").unwrap();
        std::fs::write(format!("{p}/materials/.hidden"), b"h\n").unwrap();
        std::fs::write(format!("{p}/materials/\u{e9}"), "\u{feff}bom\n".as_bytes()).unwrap();
        let s = run(&p).unwrap();
        let names: Vec<_> = s.files.iter().map(|m| m.name.as_str()).collect();
        assert_eq!(
            names,
            [
                "materials/.hidden",
                "materials/a.txt",
                "materials/a/b",
                "materials/\u{e9}"
            ]
        );
        let lines: Vec<_> = s.files.iter().map(|m| m.lines).collect();
        assert_eq!(lines, [1, 2, 0, 1]);
        let dirs: Vec<_> = s.dirs.iter().map(|d| d.name.as_str()).collect();
        assert_eq!(dirs, ["materials", "materials/a", "materials/a/empty"]);
    }

    #[test]
    fn refuses_links_and_special_files_unread() {
        let (_t, p) = folder(b"q");
        std::fs::write(format!("{p}/target"), b"t").unwrap();
        symlink(format!("{p}/target"), format!("{p}/materials/link")).unwrap();
        let e = run(&p).err().unwrap();
        // The extra root entry is reported first.
        assert_eq!(e.reason, "unexpected_root_entry");
        std::fs::remove_file(format!("{p}/target")).unwrap();
        let e = run(&p).err().unwrap();
        assert_eq!(e.reason, "unsupported_entry");
        assert_eq!(e.data.get("type"), Some(&J::Str("symbolic link".into())));
        std::fs::remove_file(format!("{p}/materials/link")).unwrap();
        let fifo = std::ffi::CString::new(format!("{p}/materials/pipe")).unwrap();
        assert_eq!(unsafe { libc::mkfifo(fifo.as_ptr(), 0o600) }, 0);
        let e = run(&p).err().unwrap();
        assert_eq!(e.reason, "unsupported_entry");
        assert_eq!(e.data.get("type"), Some(&J::Str("FIFO".into())));
    }

    #[test]
    fn refuses_question_md_as_a_link() {
        let (_t, p) = tmp();
        std::fs::create_dir(format!("{p}/materials")).unwrap();
        symlink("/etc/hosts", format!("{p}/question.md")).unwrap();
        assert_eq!(run(&p).err().unwrap().reason, "unsupported_entry");
    }

    #[test]
    fn root_layout() {
        let (_t, p) = tmp();
        assert_eq!(run(&p).err().unwrap().reason, "folder_incomplete");
        std::fs::write(format!("{p}/question.md"), b"q").unwrap();
        assert_eq!(run(&p).err().unwrap().reason, "folder_incomplete");
        std::fs::create_dir(format!("{p}/materials")).unwrap();
        std::fs::write(format!("{p}/notes.txt"), b"n").unwrap();
        let e = run(&p).err().unwrap();
        assert_eq!(e.reason, "unexpected_root_entry");
        assert!(e.message.contains("move it under materials/"));
    }

    #[test]
    fn text_rule_names_the_offset() {
        let (_t, p) = folder(b"q");
        std::fs::write(format!("{p}/materials/bin"), b"abc\xff").unwrap();
        let e = run(&p).err().unwrap();
        assert_eq!(e.reason, "material_not_text");
        assert_eq!(e.data.get("offset"), Some(&J::Int(3)));
        std::fs::write(format!("{p}/materials/bin"), b"a\0").unwrap();
        assert_eq!(run(&p).err().unwrap().data.get("offset"), Some(&J::Int(1)));
        let (_t2, p2) = folder(b"q\xc3");
        assert_eq!(run(&p2).err().unwrap().reason, "material_not_text");
    }

    #[test]
    fn names_must_be_text_without_controls() {
        let (_t, p) = folder(b"q");
        std::fs::write(format!("{p}/materials/a\tb"), b"x").unwrap();
        assert_eq!(run(&p).err().unwrap().reason, "name_invalid");
    }

    #[test]
    fn bounds_are_exact() {
        let (_t, p) = folder(b"q");
        for i in 0..FILES {
            std::fs::write(format!("{p}/materials/f{i:03}"), b"").unwrap();
        }
        assert!(run(&p).is_ok());
        std::fs::write(format!("{p}/materials/f128"), b"").unwrap();
        let e = run(&p).err().unwrap();
        assert_eq!(e.reason, "bound_exceeded");
        assert_eq!(e.data.get("bound"), Some(&J::Str("files".into())));

        let (_t, p) = folder(&vec![b'q'; QUESTION_BYTES as usize]);
        assert!(run(&p).is_ok());
        let (_t, p) = folder(&vec![b'q'; QUESTION_BYTES as usize + 1]);
        assert_eq!(
            run(&p).err().unwrap().data.get("bound"),
            Some(&J::Str("question_bytes".into()))
        );

        // 32 components below materials/ are admitted; 33 are not.
        let (_t, p) = folder(b"q");
        let deep: String = (0..31).map(|i| format!("/d{i}")).collect();
        std::fs::create_dir_all(format!("{p}/materials{deep}")).unwrap();
        std::fs::write(format!("{p}/materials{deep}/f"), b"").unwrap();
        assert!(run(&p).is_ok());
        std::fs::create_dir(format!("{p}/materials{deep}/d31")).unwrap();
        std::fs::write(format!("{p}/materials{deep}/d31/f"), b"").unwrap();
        assert_eq!(
            run(&p).err().unwrap().data.get("bound"),
            Some(&J::Str("path_components".into()))
        );

        let (_t, p) = folder(b"q");
        for i in 0..(DIRECTORIES - 1) {
            std::fs::create_dir(format!("{p}/materials/d{i:03}")).unwrap();
        }
        assert!(run(&p).is_ok());
        std::fs::create_dir(format!("{p}/materials/d999")).unwrap();
        assert_eq!(
            run(&p).err().unwrap().data.get("bound"),
            Some(&J::Str("directories".into()))
        );
    }

    #[test]
    fn rescan_sees_membership_without_reading() {
        let (_t, p) = folder(b"q");
        std::fs::write(format!("{p}/materials/a"), b"x").unwrap();
        let fifo = std::ffi::CString::new(format!("{p}/materials/pipe")).unwrap();
        assert_eq!(unsafe { libc::mkfifo(fifo.as_ptr(), 0o600) }, 0);
        let r = rescan(&Dir::open_follow(&p).unwrap());
        let names: Vec<_> = r.entries.keys().cloned().collect();
        assert_eq!(
            names,
            ["materials", "materials/a", "materials/pipe", "question.md"]
        );
        assert!(r.incomplete.is_empty());
    }
}
