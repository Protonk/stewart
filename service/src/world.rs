//! The auditor's world for one placement (INTERFACE 5.7 step 5, 7.2): the
//! accepted commission's question and material captures, verified against
//! the receipt and held open, and the pinned arrangement.
//!
//! `run` loads the world before it publishes `run_started`; a failure
//! refuses `commission_damaged` with `data.items`. Reads and searches are
//! then served from these descriptors for the whole placement, never from
//! the preparation folder and never from a path opened again later.

use crate::archive::{Audit, RECORD_LIMIT};
use crate::fsx::{Dir, ReadError};
use crate::json::J;
use crate::log::{Body, LogState};
use crate::provider::request::{Pinned, decode_arrangement};
use crate::records;
use crate::util;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io;
use std::os::unix::fs::FileExt;

/// One readable source: the question body or a material.
pub struct Source {
    /// `question` or `materials/<public name>`.
    pub name: String,
    pub size: u64,
    pub sha256: String,
    /// LF bytes, plus one if the last byte is not LF and the source is not empty.
    pub lines: u64,
    /// The capture, opened through descriptors and verified at load.
    pub file: File,
    /// Where the source begins in the capture (the question body follows
    /// its front matter in `q.bin`; a material begins at 0).
    pub offset: u64,
}

impl Source {
    /// `len` bytes from `start` (clipped to the source), by positioned
    /// reads, so no read depends on a shared file offset.
    pub fn read(&self, start: u64, len: u64) -> io::Result<Vec<u8>> {
        let start = start.min(self.size);
        let len = len.min(self.size - start);
        let mut buf = vec![0u8; len as usize];
        self.file.read_exact_at(&mut buf, self.offset + start)?;
        Ok(buf)
    }
    /// The whole source.
    pub fn bytes(&self) -> io::Result<Vec<u8>> {
        self.read(0, self.size)
    }
}

/// The world of a placement.
pub struct World {
    pub question: Source,
    /// Materials in index order (bytewise order of public names).
    pub materials: Vec<Source>,
    /// Directory names of the selection, as the receipt lists them.
    pub directories: Vec<String>,
    /// The pinned arrangement and the SHA-256 of its record.
    pub arrangement: Pinned,
    pub arrangement_sha256: String,
}

impl World {
    /// A source by its exact name (`question` or `materials/<name>`).
    pub fn source(&self, name: &str) -> Option<&Source> {
        if name == "question" {
            return Some(&self.question);
        }
        self.materials.iter().find(|m| m.name == name)
    }
    /// Total bytes of the materials.
    pub fn material_bytes(&self) -> u64 {
        self.materials.iter().map(|m| m.size).sum()
    }
}

/// A receipt item that failed to load: `commission_damaged`'s `data.items`,
/// named by receipt item IDs (2.4), or `receipt` for the receipt itself.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ItemProblem {
    pub item: String,
    pub problem: String,
}

impl ItemProblem {
    fn new(item: impl Into<String>, problem: impl Into<String>) -> ItemProblem {
        ItemProblem {
            item: item.into(),
            problem: problem.into(),
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("item", self.item.as_str())
            .with("problem", self.problem.as_str())
    }
}

/// Open an audit-relative file through descriptors, without following links.
fn open_rel(audit: &Audit, rel: &str) -> Result<(File, u64), String> {
    let (dir_rel, name) = rel.rsplit_once('/').unwrap_or(("", rel));
    let mut dir: Dir = audit
        .dir
        .open_dir_bytes(b".", true)
        .map_err(|e| util::describe(&e))?;
    for comp in dir_rel.split('/').filter(|c| !c.is_empty()) {
        dir = dir.open_dir(comp).map_err(|e| {
            if e.raw_os_error() == Some(libc::ENOENT) {
                format!("{rel} is missing")
            } else {
                format!("{rel} cannot be opened: {}", util::describe(&e))
            }
        })?;
    }
    let (f, st) = dir.open_regular(name).map_err(|e| match e {
        ReadError::Missing => format!("{rel} is missing"),
        other => format!("{rel} cannot be opened: {}", other.describe()),
    })?;
    Ok((f, st.size))
}

/// Hash `[offset, offset + len)` of `f` by positioned reads, counting lines.
fn digest(f: &File, offset: u64, len: u64) -> io::Result<(String, u64)> {
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    let mut at = 0u64;
    let mut lf = 0u64;
    let mut last = None;
    while at < len {
        let want = (len - at).min(buf.len() as u64) as usize;
        let n = f.read_at(&mut buf[..want], offset + at)?;
        if n == 0 {
            return Err(io::Error::from(io::ErrorKind::UnexpectedEof));
        }
        h.update(&buf[..n]);
        lf += buf[..n].iter().filter(|b| **b == b'\n').count() as u64;
        last = Some(buf[n - 1]);
        at += n as u64;
    }
    let lines = lf + u64::from(last.is_some_and(|b| b != b'\n'));
    Ok((util::hex(&h.finalize()), lines))
}

/// Open and verify one capture: its whole size and digest.
fn verified(
    audit: &Audit,
    item: &str,
    rel: &str,
    size: u64,
    sha256: &str,
) -> Result<(File, u64), ItemProblem> {
    let (f, actual) = open_rel(audit, rel).map_err(|p| ItemProblem::new(item, p))?;
    if actual != size {
        return Err(ItemProblem::new(
            item,
            format!("{rel} holds {actual} bytes; {size} were recorded"),
        ));
    }
    let (got, lines) = digest(&f, 0, size).map_err(|e| {
        ItemProblem::new(
            item,
            format!("{rel} cannot be read: {}", util::describe(&e)),
        )
    })?;
    if got != sha256 {
        return Err(ItemProblem::new(
            item,
            format!("{rel} does not match its recorded SHA-256"),
        ));
    }
    Ok((f, lines))
}

/// Load the accepted commission's world: the receipt the `accepted` record
/// names, the arrangement the receipt names and every capture, each checked
/// for size and digest through descriptors. Every failing item is reported.
pub fn load(audit: &Audit, state: &LogState) -> Result<World, Vec<ItemProblem>> {
    let Some(Body::Accepted {
        receipt,
        receipt_sha256,
        ..
    }) = state.accepted().map(|r| &r.body)
    else {
        return Err(vec![ItemProblem::new(
            "receipt",
            "no accepted record is in the log",
        )]);
    };
    let (r, _) = records::load_receipt(audit, receipt, receipt_sha256)
        .map_err(|e| vec![ItemProblem::new("receipt", e.describe())])?;
    let mut problems = Vec::new();

    let arr_rel = format!("prep/{}/arrangement.json", r.prep);
    let arrangement = match open_rel(audit, &arr_rel) {
        Err(p) => Err(ItemProblem::new("arrangement", p)),
        Ok((_, size)) if size > RECORD_LIMIT || size != r.manifest.arrangement_size => {
            Err(ItemProblem::new(
                "arrangement",
                format!(
                    "{arr_rel} holds {size} bytes; {} were recorded",
                    r.manifest.arrangement_size
                ),
            ))
        }
        Ok((f, size)) => {
            let mut bytes = vec![0u8; size as usize];
            match f.read_exact_at(&mut bytes, 0) {
                Err(e) => Err(ItemProblem::new(
                    "arrangement",
                    format!("{arr_rel} cannot be read: {}", util::describe(&e)),
                )),
                Ok(()) if util::sha256_hex(&bytes) != r.manifest.arrangement_sha256 => {
                    Err(ItemProblem::new(
                        "arrangement",
                        format!("{arr_rel} does not match its recorded SHA-256"),
                    ))
                }
                Ok(()) => decode_arrangement(&bytes)
                    .map(|p| (p, r.manifest.arrangement_sha256.clone()))
                    .map_err(|e| ItemProblem::new("arrangement", format!("{arr_rel}: {e}"))),
            }
        }
    };
    let arrangement = arrangement.map_err(|p| problems.push(p)).ok();

    let q = &r.manifest.question;
    let question = match verified(
        audit,
        "question-file",
        &r.question_capture,
        q.file_bytes,
        &q.file_sha256,
    ) {
        Err(p) => {
            problems.push(p);
            None
        }
        Ok((f, _)) => match digest(&f, q.body_offset, q.body_bytes) {
            Ok((sha, lines))
                if sha == q.body_sha256 && q.body_offset + q.body_bytes == q.file_bytes =>
            {
                Some(Source {
                    name: "question".into(),
                    size: q.body_bytes,
                    sha256: sha,
                    lines,
                    file: f,
                    offset: q.body_offset,
                })
            }
            Ok(_) => {
                problems.push(ItemProblem::new(
                    "question-body",
                    "the question body does not match its recorded digest",
                ));
                None
            }
            Err(e) => {
                problems.push(ItemProblem::new("question-body", util::describe(&e)));
                None
            }
        },
    };
    if let (Some(a), Some(_)) = (&arrangement, &question) {
        if a.0.question_body_sha256 != q.body_sha256 {
            problems.push(ItemProblem::new(
                "arrangement",
                "the arrangement binds another question body",
            ));
        }
    }

    let mut materials = Vec::new();
    for (m, cap) in &r.captures {
        match verified(audit, &m.name, cap, m.size, &m.sha256) {
            Ok((file, lines)) => materials.push(Source {
                name: m.name.clone(),
                size: m.size,
                sha256: m.sha256.clone(),
                lines,
                file,
                offset: 0,
            }),
            Err(p) => problems.push(p),
        }
    }
    match (arrangement, question) {
        (Some((arrangement, arrangement_sha256)), Some(question)) if problems.is_empty() => {
            Ok(World {
                question,
                materials,
                directories: r.manifest.dirs.clone(),
                arrangement,
                arrangement_sha256,
            })
        }
        _ => Err(problems),
    }
}
