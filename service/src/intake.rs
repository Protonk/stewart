//! Mechanical intake rules over supplied bytes, names and sizes (INTERFACE 3).
//! Acquisition and custody stay with the caller. The scanner applies each
//! limit as it encounters an entry, before allocating or reading its contents.

use crate::frontmatter::first_non_text;
use crate::json::J;

pub const QUESTION_BYTES: u64 = 262_144;
pub const GUIDANCE_BYTES: u64 = 262_144;
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
        .with("guidance_bytes", GUIDANCE_BYTES)
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

pub(crate) fn refusal(reason: &'static str, message: impl Into<String>, data: J) -> Refusal {
    Refusal {
        reason,
        message: message.into(),
        data,
    }
}

pub(crate) fn bound(name: &'static str, limit: u64, entry: &str, observed: u64) -> Refusal {
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

pub(crate) fn check_text(entry: &str, bytes: &[u8]) -> Result<(), Refusal> {
    if let Some(offset) = first_non_text(bytes) {
        return Err(not_text(entry, offset));
    }
    Ok(())
}

pub(crate) fn check_guidance(bytes: &[u8]) -> Result<(), Refusal> {
    check_text("guidance.md", bytes)?;
    if !std::str::from_utf8(bytes)
        .expect("text checked")
        .chars()
        .any(|c| !c.is_whitespace())
    {
        return Err(refusal(
            "guidance_empty",
            "guidance.md must contain a non-whitespace character; the provider cannot carry a blank text block.",
            J::obj().with("entry", "guidance.md"),
        ));
    }
    Ok(())
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

/// Append one component to a previously validated material directory.
/// The initial parent is the index root, `materials`.
pub(crate) fn material_path(parent: &str, raw: &[u8]) -> Result<String, Refusal> {
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
    let path = format!("{parent}/{s}");
    if s.is_empty() || matches!(s, "." | "..") || s.contains('/') {
        return Err(refusal(
            "name_invalid",
            format!("{s:?} must be one literal material name component."),
            J::obj().with("entry", path),
        ));
    }
    let rel_len = path.len() - "materials/".len();
    if rel_len > PATH_BYTES {
        return Err(bound(
            "path_bytes",
            PATH_BYTES as u64,
            &path,
            rel_len as u64,
        ));
    }
    let depth = parent.split('/').count();
    if depth > PATH_COMPONENTS {
        return Err(bound(
            "path_components",
            PATH_COMPONENTS as u64,
            &path,
            depth as u64,
        ));
    }
    Ok(path)
}

pub(crate) fn check_directory_count(entry: &str, count: usize) -> Result<(), Refusal> {
    if count > DIRECTORIES {
        return Err(bound(
            "directories",
            DIRECTORIES as u64,
            entry,
            count as u64,
        ));
    }
    Ok(())
}

/// `prior_bytes` includes the question, selected guidance and preceding files.
pub(crate) fn check_file(
    entry: &str,
    count: usize,
    size: u64,
    prior_bytes: u64,
) -> Result<(), Refusal> {
    if count > FILES {
        return Err(bound("files", FILES as u64, entry, count as u64));
    }
    if size > FILE_BYTES {
        return Err(bound("file_bytes", FILE_BYTES, entry, size));
    }
    let total = prior_bytes.saturating_add(size);
    if total > TOTAL_BYTES {
        return Err(bound("total_bytes", TOTAL_BYTES, entry, total));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn supplied_components_are_literal_names_below_materials() {
        assert_eq!(
            material_path("materials", " .報告 ".as_bytes()).unwrap(),
            "materials/ .報告 "
        );
        for component in [b"".as_slice(), b".", b"..", b"a/b", b"x\n", b"\xff"] {
            let refusal = material_path("materials", component).unwrap_err();
            assert_eq!(refusal.reason, "name_invalid", "{component:?}");
        }
        assert_eq!(
            material_path("materials/a", b"..txt").unwrap(),
            "materials/a/..txt"
        );
    }

    #[test]
    fn the_reported_bound_distinguishes_one_file_from_the_whole_selection() {
        let entry = "materials/report";
        check_file(entry, FILES, FILE_BYTES, TOTAL_BYTES - FILE_BYTES).unwrap();
        for (count, size, previous, expected) in [
            (FILES + 1, 0, 0, "files"),
            (1, FILE_BYTES + 1, 0, "file_bytes"),
            (
                FILES,
                FILE_BYTES,
                TOTAL_BYTES - FILE_BYTES + 1,
                "total_bytes",
            ),
        ] {
            let refusal = check_file(entry, count, size, previous).unwrap_err();
            assert_eq!(refusal.reason, "bound_exceeded");
            assert_eq!(refusal.data.get("bound"), Some(&J::from(expected)));
        }
    }
}
