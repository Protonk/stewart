//! Validate a caller's complete prospective inventory (INTERFACE 3 and 5.11).
//! Membership, sizes and directory structure are assertions. The filesystem
//! scanner checks the same name and size limits while it acquires actual bytes.

use crate::frontmatter::{self, Defect};
use crate::intake::{self, Refusal};
use crate::json::{J, JsonError, Obj, strs};
use std::collections::BTreeMap;

fn diagnostic(failure: Refusal, source: &str, pointer: &str) -> Defect {
    let mut defect = failure.defect().expect("a mechanical intake refusal");
    defect.source = Some(source.into());
    defect.pointer = Some(pointer.into());
    defect
}

fn check_name(name: &str, directory: bool) -> Result<(), Refusal> {
    if directory && name == "materials" {
        return Ok(());
    }
    let Some(relative) = name.strip_prefix("materials/") else {
        return Err(intake::refusal(
            "name_invalid",
            format!("{name:?} must name an entry below materials/."),
            J::obj(),
        ));
    };
    let mut parent = "materials".to_string();
    for component in relative.split('/') {
        parent = intake::material_path(&parent, component.as_bytes())?;
    }
    Ok(())
}

#[derive(Default)]
struct Inventory<'a> {
    directories: BTreeMap<&'a str, usize>,
    files: BTreeMap<&'a str, (usize, u64)>,
}

impl<'a> Inventory<'a> {
    fn check(
        directories: &[&'a str],
        files: &[(&'a str, u64)],
        initial_size: u64,
    ) -> Result<Self, Defect> {
        let mut inventory = Self::default();
        // Check oversized inventories before building name indexes. For a valid
        // count, compare names in byte order and keep pointers into the input.
        if directories.len() > intake::DIRECTORIES {
            let err = intake::bound(
                "directories",
                intake::DIRECTORIES as u64,
                "materials",
                directories.len() as u64,
            );
            return Err(diagnostic(err, "materials", "/directories"));
        }
        if files.len() > intake::FILES {
            let err = intake::bound(
                "files",
                intake::FILES as u64,
                "materials",
                files.len() as u64,
            );
            return Err(diagnostic(err, "materials", "/files"));
        }
        let mut dir_names: Vec<_> = directories.iter().copied().enumerate().collect();
        dir_names.sort_by_key(|(_, name)| *name);
        let mut file_entries: Vec<_> = files.iter().copied().enumerate().collect();
        file_entries.sort_by_key(|(_, (name, size))| (*name, *size));
        let duplicate = |name: &str, pointer: &str| {
            diagnostic(
                intake::refusal(
                    "name_invalid",
                    format!("{name:?} occurs more than once in the supplied inventory."),
                    J::obj(),
                ),
                name,
                pointer,
            )
        };
        for (i, name) in dir_names {
            let pointer = format!("/directories/{i}");
            check_name(name, true).map_err(|f| diagnostic(f, name, &pointer))?;
            if inventory.directories.insert(name, i).is_some() {
                return Err(duplicate(name, &pointer));
            }
        }
        for (i, (name, size)) in file_entries {
            let pointer = format!("/files/{i}/name");
            check_name(name, false).map_err(|f| diagnostic(f, name, &pointer))?;
            if inventory.directories.contains_key(name)
                || inventory.files.insert(name, (i, size)).is_some()
            {
                return Err(duplicate(name, &pointer));
            }
        }
        let missing = |source: &str, pointer: &str, parent: &str| {
            diagnostic(
                intake::refusal(
                    "folder_incomplete",
                    format!("Include the directory {parent:?} in the supplied inventory."),
                    J::obj(),
                ),
                source,
                pointer,
            )
        };
        if !inventory.directories.contains_key("materials") {
            return Err(missing("materials", "/directories", "materials"));
        }
        let check_parent = |name: &str, pointer: &str| {
            if let Some((parent, _)) = name.rsplit_once('/')
                && !inventory.directories.contains_key(parent)
            {
                if inventory.files.contains_key(parent) {
                    return Err(diagnostic(
                        intake::refusal(
                            "name_invalid",
                            format!(
                                "{parent:?} is listed as a file but is also a parent directory of {name:?}."
                            ),
                            J::obj(),
                        ),
                        name,
                        pointer,
                    ));
                }
                return Err(missing(name, pointer, parent));
            }
            Ok(())
        };
        for (name, i) in &inventory.directories {
            check_parent(name, &format!("/directories/{i}"))?;
        }
        let mut total = initial_size;
        for (name, (i, size)) in &inventory.files {
            check_parent(name, &format!("/files/{i}/name"))?;
            intake::check_file(name, files.len(), *size, total)
                .map_err(|f| diagnostic(f, name, &format!("/files/{i}/size")))?;
            total += size;
        }
        Ok(inventory)
    }
}

pub(super) fn assess(args: &Obj) -> Result<J, JsonError> {
    let question = args.str("question_file")?;
    let guidance = args.str_or_null("guidance")?;
    let dirs = args.strs("directories")?;
    let files = args
        .arr("files")?
        .iter()
        .enumerate()
        .map(|(i, v)| {
            let file = v.obj(&format!("/files/{i}"))?;
            file.exactly(&["name", "size"])?;
            Ok((file.str("name")?, file.u64("size", u64::MAX)?))
        })
        .collect::<Result<Vec<_>, JsonError>>()?;

    Ok(snapshot(question, guidance, &dirs, &files, false).data)
}

/// An assessment of one snapshot: its data, and whether a runtime profile
/// is selected (which adds `runtime_profile` to what remains unchecked).
pub(super) struct Snapshot {
    pub(super) valid: bool,
    pub(super) data: J,
    pub(super) profile: bool,
}

/// Assess a question, guidance and inventory. `bytes_checked` says every
/// supplied material byte was actually read and checked, so
/// `material_bytes` is left out of what remains unchecked.
pub(super) fn snapshot(
    question: &str,
    guidance: Option<&str>,
    dirs: &[&str],
    files: &[(&str, u64)],
    bytes_checked: bool,
) -> Snapshot {
    let mut unchecked = vec!["filesystem", "source_stability"];
    let outcome = check_snapshot(question, guidance, dirs, files, &mut unchecked);
    let profile = unchecked.len() > 2;
    Snapshot {
        valid: outcome.is_ok(),
        data: data(outcome, bytes_checked, profile),
        profile,
    }
}

/// Assessment data from an outcome: errors, or the advice of a valid snapshot.
pub(super) fn data(
    outcome: Result<Vec<Defect>, Vec<Defect>>,
    bytes_checked: bool,
    profile: bool,
) -> J {
    let mut unchecked = Vec::new();
    if !bytes_checked {
        unchecked.push("material_bytes");
    }
    unchecked.extend(["filesystem", "source_stability"]);
    if profile {
        unchecked.push("runtime_profile");
    }
    unchecked.push("acceptance");
    let valid = outcome.is_ok();
    let defects = outcome.unwrap_or_else(|e| e);
    J::obj()
        .with("valid", valid)
        .with(
            "defects",
            J::Arr(defects.iter().map(Defect::to_j).collect()),
        )
        .with("unchecked", strs(&unchecked))
}

fn check_snapshot(
    question: &str,
    guidance: Option<&str>,
    dirs: &[&str],
    files: &[(&str, u64)],
    unchecked: &mut Vec<&'static str>,
) -> Result<Vec<Defect>, Vec<Defect>> {
    let qsize = question.len() as u64;
    intake::check_size(
        "question_bytes",
        intake::QUESTION_BYTES,
        "question.md",
        qsize,
    )
    .and_then(|_| intake::check_text("question.md", question.as_bytes()))
    .map_err(|f| vec![diagnostic(f, "question.md", "/question_file")])?;
    let (candidate, errors) = frontmatter::candidate(question.as_bytes())?;
    if candidate.settings.runtime.requires_profile() {
        unchecked.push("runtime_profile");
    }
    if !errors.is_empty() && !candidate.material_roles.has_mappings() {
        return Err(errors);
    }
    let selected = candidate.settings.guidance.is_some();
    match (selected, guidance) {
        (true, None) => {
            return Err(vec![diagnostic(
                intake::missing_guidance(),
                "guidance.md",
                "/guidance",
            )]);
        }
        (false, Some(_)) => {
            return Err(vec![diagnostic(
                intake::unexpected_root(&["guidance.md".into()], false),
                "guidance.md",
                "/guidance",
            )]);
        }
        (true, Some(text)) => intake::check_size(
            "guidance_bytes",
            intake::GUIDANCE_BYTES,
            "guidance.md",
            text.len() as u64,
        )
        .and_then(|_| intake::check_guidance(text.as_bytes()))
        .map_err(|f| vec![diagnostic(f, "guidance.md", "/guidance")])?,
        (false, None) => {}
    }
    let inventory = Inventory::check(dirs, files, qsize + guidance.map_or(0, |s| s.len() as u64))
        .map_err(|e| vec![e])?;
    candidate.assess_roles(inventory.files.keys().copied(), errors)
}

#[cfg(test)]
mod tests {
    use super::*;

    // A file that is also an implied parent cannot be repaired merely by adding
    // a missing directory to the inventory.
    #[test]
    fn file_cannot_be_an_implied_directory() {
        let check =
            |files: &[(&str, u64)]| Inventory::check(&["materials"], files, 0).err().unwrap();
        let parent = ("materials/entry", 2);
        let child = ("materials/entry/notes", 1);
        for (files, pointer) in [
            ([parent, child], "/files/1/name"),
            ([child, parent], "/files/0/name"),
        ] {
            let defect = check(&files);
            assert_eq!(defect.reason, "name_invalid");
            assert_eq!(defect.pointer.as_deref(), Some(pointer));
            assert_eq!(defect.source.as_deref(), Some(child.0));
        }
    }

    #[cfg(feature = "claude-code")]
    #[test]
    fn a_selected_profile_is_explicitly_unchecked() {
        let question = "---\nstewart: question/2\nfamily: open-inquiry\nmodel: example\ndestination: /absent/return\nruntime-profile: /absent/profile\nmax-placements: 1\nplacement-timeout-seconds: 4\n---\nWhat can these notes establish?";
        let bytes = J::obj()
            .with("question_file", question)
            .with("guidance", J::Null)
            .with("directories", strs(&["materials"]))
            .with("files", J::Arr(vec![]))
            .bytes();
        let input = crate::json::parse(&bytes).unwrap();
        let data = assess(&input.obj("").unwrap()).unwrap();
        assert_eq!(data.get("valid"), Some(&J::Bool(true)));
        assert_eq!(
            data.get("unchecked"),
            Some(&strs(&[
                "material_bytes",
                "filesystem",
                "source_stability",
                "runtime_profile",
                "acceptance"
            ]))
        );
    }
}
