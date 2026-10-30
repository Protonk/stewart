//! The preparation manifest (`stewart.preparation/1`) and the acceptance
//! receipt (`stewart.receipt/1`): their bodies, and strict decoders that also
//! check the bindings the log holds for them.

use crate::archive::{Audit, RECORD_LIMIT, decode_record};
use crate::frontmatter::Settings;
use crate::json::{self, J, JsonError, Obj};
use crate::util;

pub const PREPARATION_SCHEMA: &str = "stewart.preparation/1";
pub const RECEIPT_SCHEMA: &str = "stewart.receipt/1";

pub const CHECKS: [&str; 3] = [
    "capture_digests_match_preparation",
    "source_identity_unchanged_during_copy",
    "final_scan_matches_preparation",
];

pub fn reader_j() -> J {
    J::obj()
        .with("id", crate::forms::READER_ID)
        .with("transformations", "none")
}

pub fn decode_settings(s: &Obj) -> Result<Settings, JsonError> {
    s.only(&[
        "family",
        "model",
        "destination",
        "limits",
        "inquiry",
        "varies",
    ])?;
    let l = s.obj("limits")?;
    l.only(&["turns", "input_tokens", "output_tokens"])?;
    Ok(Settings {
        family: s.str("family")?.to_string(),
        model: s.str("model")?.to_string(),
        destination: s.str("destination")?.to_string(),
        turns: l.u64("turns", crate::frontmatter::MAX_TURNS)?,
        input_tokens: l.u64("input_tokens", crate::frontmatter::MAX_INPUT_TOKENS)?,
        output_tokens: l.u64("output_tokens", crate::frontmatter::MAX_OUTPUT_TOKENS)?,
        inquiry: s.opt_str("inquiry")?.map(|x| x.to_string()),
        varies: s.opt_str("varies")?.map(|x| x.to_string()),
    })
}

#[derive(Debug, Clone)]
pub struct QInfo {
    pub file_bytes: u64,
    pub file_sha256: String,
    pub body_offset: u64,
    pub body_bytes: u64,
    pub body_sha256: String,
    pub mtime: String,
}

impl QInfo {
    /// The question member as replies show it.
    pub fn summary_j(&self) -> J {
        J::obj()
            .with("file_bytes", self.file_bytes)
            .with("file_sha256", self.file_sha256.as_str())
            .with("body_bytes", self.body_bytes)
            .with("body_sha256", self.body_sha256.as_str())
    }
}

#[derive(Debug, Clone)]
pub struct MFile {
    pub name: String,
    pub size: u64,
    pub sha256: String,
    pub lines: u64,
    pub mtime: String,
}

impl MFile {
    pub fn index_j(&self) -> J {
        J::obj()
            .with("name", self.name.as_str())
            .with("size", self.size)
            .with("sha256", self.sha256.as_str())
            .with("lines", self.lines)
    }
}

/// The material index: the exact bytes the arrangement binds.
pub fn index_bytes(files: &[MFile], dirs: &[String]) -> Vec<u8> {
    J::obj()
        .with("files", J::Arr(files.iter().map(|f| f.index_j()).collect()))
        .with("directories", json::strs(dirs))
        .bytes()
}

pub struct Manifest {
    pub prep: u64,
    pub folder: String,
    pub question: QInfo,
    pub settings: Settings,
    pub files: Vec<MFile>,
    pub dirs: Vec<String>,
    pub index_sha256: String,
    pub arrangement_sha256: String,
    pub arrangement_size: u64,
    pub readable_sha256: String,
    pub readable_size: u64,
}

impl Manifest {
    pub fn material_bytes(&self) -> u64 {
        self.files.iter().map(|f| f.size).sum()
    }
    pub fn materials_j(&self) -> J {
        J::obj()
            .with("count", self.files.len())
            .with("bytes", self.material_bytes())
            .with("directories", json::strs(&self.dirs))
            .with(
                "files",
                J::Arr(self.files.iter().map(|f| f.index_j()).collect()),
            )
    }
}

pub struct ManifestParts<'a> {
    pub prep: u64,
    pub folder: &'a str,
    pub question: &'a QInfo,
    pub settings: &'a Settings,
    pub index: &'a [u8],
    pub files: &'a [MFile],
    pub dir_mtimes: &'a [(String, String)],
    pub arrangement: (&'a str, u64),
    pub readable: (&'a str, u64),
}

pub fn manifest_body(p: &ManifestParts) -> J {
    J::obj()
        .with("schema", PREPARATION_SCHEMA)
        .with("prep", p.prep)
        .with("folder", p.folder)
        .with(
            "question",
            J::obj()
                .with("file", "question.md")
                .with("file_bytes", p.question.file_bytes)
                .with("file_sha256", p.question.file_sha256.as_str())
                .with("body_offset", p.question.body_offset)
                .with("body_bytes", p.question.body_bytes)
                .with("body_sha256", p.question.body_sha256.as_str())
                .with("mtime", p.question.mtime.as_str()),
        )
        .with("settings", p.settings.to_j())
        .with("index", J::Raw(p.index.to_vec()))
        .with(
            "observations",
            J::obj()
                .with(
                    "files",
                    J::Arr(
                        p.files
                            .iter()
                            .map(|f| {
                                J::obj()
                                    .with("name", f.name.as_str())
                                    .with("mtime", f.mtime.as_str())
                            })
                            .collect(),
                    ),
                )
                .with(
                    "directories",
                    J::Arr(
                        p.dir_mtimes
                            .iter()
                            .map(|(n, m)| {
                                J::obj().with("name", n.as_str()).with("mtime", m.as_str())
                            })
                            .collect(),
                    ),
                ),
        )
        .with("bounds", crate::scan::bounds_j())
        .with("reader", reader_j())
        .with(
            "arrangement",
            J::obj()
                .with("machine", format!("prep/{}/arrangement.json", p.prep))
                .with("sha256", p.arrangement.0)
                .with("size", p.arrangement.1)
                .with("readable", format!("prep/{}/arrangement.md", p.prep))
                .with("readable_sha256", p.readable.0)
                .with("readable_size", p.readable.1),
        )
}

pub fn decode_manifest(bytes: &[u8]) -> Result<Manifest, String> {
    let r = decode_record(bytes)?;
    if r.kind != "preparation" {
        return Err(format!("the manifest has kind {:?}", r.kind));
    }
    let b = r.body();
    let res = (|| {
        b.only(&[
            "schema",
            "prep",
            "folder",
            "question",
            "settings",
            "index",
            "observations",
            "bounds",
            "reader",
            "arrangement",
        ])?;
        let schema = b.str("schema")?;
        if schema != PREPARATION_SCHEMA {
            return Err(json::value_err(
                "/body/schema",
                0,
                format!("unsupported schema {schema:?}"),
            ));
        }
        let q = b.obj("question")?;
        q.only(&[
            "file",
            "file_bytes",
            "file_sha256",
            "body_offset",
            "body_bytes",
            "body_sha256",
            "mtime",
        ])?;
        let question = QInfo {
            file_bytes: q.u64("file_bytes", u64::MAX)?,
            file_sha256: q.str("file_sha256")?.to_string(),
            body_offset: q.u64("body_offset", u64::MAX)?,
            body_bytes: q.u64("body_bytes", u64::MAX)?,
            body_sha256: q.str("body_sha256")?.to_string(),
            mtime: q.str("mtime")?.to_string(),
        };
        let settings = decode_settings(&b.obj("settings")?)?;
        let index = b.req("index")?;
        let io = index.obj("/body/index")?;
        io.only(&["files", "directories"])?;
        let obs = b.obj("observations")?;
        obs.only(&["files", "directories"])?;
        let mtimes = obs.arr("files")?;
        let mut files = Vec::new();
        for (i, f) in io.arr("files")?.iter().enumerate() {
            let o = f.obj(&format!("/body/index/files/{i}"))?;
            o.only(&["name", "size", "sha256", "lines"])?;
            let name = o.str("name")?.to_string();
            let mtime = mtimes
                .get(i)
                .and_then(|m| m.obj("").ok())
                .filter(|m| m.str("name").ok() == Some(name.as_str()))
                .and_then(|m| m.str("mtime").ok())
                .ok_or_else(|| {
                    json::value_err(
                        "/body/observations/files",
                        0,
                        format!("no mtime observation for {name}"),
                    )
                })?
                .to_string();
            files.push(MFile {
                name,
                size: o.u64("size", u64::MAX)?,
                sha256: o.str("sha256")?.to_string(),
                lines: o.u64("lines", u64::MAX)?,
                mtime,
            });
        }
        let dirs = io
            .strs("directories")?
            .into_iter()
            .map(|s| s.to_string())
            .collect();
        let a = b.obj("arrangement")?;
        a.only(&[
            "machine",
            "sha256",
            "size",
            "readable",
            "readable_sha256",
            "readable_size",
        ])?;
        Ok::<_, JsonError>(Manifest {
            prep: b.u64("prep", u64::MAX)?,
            folder: b.str("folder")?.to_string(),
            question,
            settings,
            files,
            dirs,
            index_sha256: util::sha256_hex(&bytes[index.start..index.end]),
            arrangement_sha256: a.str("sha256")?.to_string(),
            arrangement_size: a.u64("size", u64::MAX)?,
            readable_sha256: a.str("readable_sha256")?.to_string(),
            readable_size: a.u64("readable_size", u64::MAX)?,
        })
    })();
    res.map_err(|e| e.to_string())
}

/// Read `prep/<n>/manifest.json` and check it against the digest the
/// `prepared` record binds.
pub fn load_manifest(audit: &Audit, prep: u64, want_sha256: &str) -> Result<Manifest, String> {
    let dir = audit
        .dir
        .open_dir("prep")
        .and_then(|d| d.open_dir(&prep.to_string()))
        .map_err(|e| format!("prep/{prep} cannot be opened: {}", util::describe(&e)))?;
    let (bytes, _) = dir
        .read_regular("manifest.json", RECORD_LIMIT)
        .map_err(|e| format!("prep/{prep}/manifest.json: {}", e.describe()))?;
    if util::sha256_hex(&bytes) != want_sha256 {
        return Err(format!(
            "prep/{prep}/manifest.json no longer matches the digest its prepared record binds"
        ));
    }
    let m = decode_manifest(&bytes).map_err(|e| format!("prep/{prep}/manifest.json: {e}"))?;
    if m.prep != prep {
        return Err(format!(
            "prep/{prep}/manifest.json names preparation {}",
            m.prep
        ));
    }
    Ok(m)
}

// ---------------------------------------------------------------------------
// The acceptance receipt.

pub struct Receipt {
    pub attempt: u64,
    pub prepared: String,
    pub prep: u64,
    pub manifest: Manifest,
    pub captures: Vec<(MFile, String)>,
    pub question_capture: String,
    pub checks: Vec<String>,
    pub i_am_finished: bool,
    pub json: json::Json,
}

pub struct ReceiptParts<'a> {
    pub audit: &'a Audit,
    pub attempt: u64,
    pub prepared: &'a str,
    pub manifest_sha256: &'a str,
    pub m: &'a Manifest,
    pub question_capture: &'a str,
    pub captures: &'a [(MFile, String)],
    pub checks: &'a [&'a str],
    pub i_am_finished: bool,
}

pub fn receipt_body(p: &ReceiptParts) -> J {
    let m = p.m;
    J::obj()
        .with("schema", RECEIPT_SCHEMA)
        .with("reference", p.audit.reference.as_str())
        .with("audit", p.audit.id.as_str())
        .with("store", p.audit.archive.store.as_str())
        .with("attempt", p.attempt)
        .with("prepared", p.prepared)
        .with("prep", m.prep)
        .with("manifest", format!("prep/{}/manifest.json", m.prep))
        .with("manifest_sha256", p.manifest_sha256)
        .with(
            "question",
            J::obj()
                .with("file_bytes", m.question.file_bytes)
                .with("file_sha256", m.question.file_sha256.as_str())
                .with("body_offset", m.question.body_offset)
                .with("body_bytes", m.question.body_bytes)
                .with("body_sha256", m.question.body_sha256.as_str())
                .with("capture", p.question_capture),
        )
        .with("settings", m.settings.to_j())
        .with(
            "materials",
            J::obj()
                .with("count", p.captures.len())
                .with("bytes", p.captures.iter().map(|(f, _)| f.size).sum::<u64>())
                .with("directories", json::strs(&m.dirs))
                .with(
                    "files",
                    J::Arr(
                        p.captures
                            .iter()
                            .map(|(f, c)| {
                                J::obj()
                                    .with("name", f.name.as_str())
                                    .with("size", f.size)
                                    .with("sha256", f.sha256.as_str())
                                    .with("lines", f.lines)
                                    .with("capture", c.as_str())
                            })
                            .collect(),
                    ),
                ),
        )
        .with(
            "arrangement",
            J::obj()
                .with("machine", format!("prep/{}/arrangement.json", m.prep))
                .with("sha256", m.arrangement_sha256.as_str())
                .with("size", m.arrangement_size)
                .with("readable", format!("prep/{}/arrangement.md", m.prep))
                .with("readable_sha256", m.readable_sha256.as_str())
                .with("readable_size", m.readable_size),
        )
        .with("checks", json::strs(p.checks))
        .with(
            "declaration",
            J::obj().with("i_am_finished", p.i_am_finished),
        )
        .with("reader", reader_j())
        .with("bounds", crate::scan::bounds_j())
        .with(
            "custody",
            J::obj()
                .with("archive", p.audit.archive.path.as_str())
                .with(
                    "location",
                    format!("audits/{}/intake/{}", p.audit.id, p.attempt),
                ),
        )
}

pub fn decode_receipt(bytes: &[u8]) -> Result<Receipt, String> {
    let r = decode_record(bytes)?;
    if r.kind != "receipt" {
        return Err(format!("the receipt has kind {:?}", r.kind));
    }
    let b = r.body();
    let res = (|| {
        b.only(&[
            "schema",
            "reference",
            "audit",
            "store",
            "attempt",
            "prepared",
            "prep",
            "manifest",
            "manifest_sha256",
            "question",
            "settings",
            "materials",
            "arrangement",
            "checks",
            "declaration",
            "reader",
            "bounds",
            "custody",
        ])?;
        let schema = b.str("schema")?;
        if schema != RECEIPT_SCHEMA {
            return Err(json::value_err(
                "/body/schema",
                0,
                format!("unsupported schema {schema:?}"),
            ));
        }
        let q = b.obj("question")?;
        q.only(&[
            "file_bytes",
            "file_sha256",
            "body_offset",
            "body_bytes",
            "body_sha256",
            "capture",
        ])?;
        let question = QInfo {
            file_bytes: q.u64("file_bytes", u64::MAX)?,
            file_sha256: q.str("file_sha256")?.to_string(),
            body_offset: q.u64("body_offset", u64::MAX)?,
            body_bytes: q.u64("body_bytes", u64::MAX)?,
            body_sha256: q.str("body_sha256")?.to_string(),
            mtime: String::new(),
        };
        let settings = decode_settings(&b.obj("settings")?)?;
        let mats = b.obj("materials")?;
        mats.only(&["count", "bytes", "directories", "files"])?;
        let mut captures = Vec::new();
        for (i, f) in mats.arr("files")?.iter().enumerate() {
            let o = f.obj(&format!("/body/materials/files/{i}"))?;
            o.only(&["name", "size", "sha256", "lines", "capture"])?;
            captures.push((
                MFile {
                    name: o.str("name")?.to_string(),
                    size: o.u64("size", u64::MAX)?,
                    sha256: o.str("sha256")?.to_string(),
                    lines: o.u64("lines", u64::MAX)?,
                    mtime: String::new(),
                },
                o.str("capture")?.to_string(),
            ));
        }
        let dirs: Vec<String> = mats
            .strs("directories")?
            .into_iter()
            .map(|s| s.to_string())
            .collect();
        let a = b.obj("arrangement")?;
        a.only(&[
            "machine",
            "sha256",
            "size",
            "readable",
            "readable_sha256",
            "readable_size",
        ])?;
        let d = b.obj("declaration")?;
        d.only(&["i_am_finished"])?;
        let manifest = Manifest {
            prep: b.u64("prep", u64::MAX)?,
            folder: String::new(),
            question,
            settings,
            files: captures.iter().map(|(f, _)| f.clone()).collect(),
            dirs,
            index_sha256: String::new(),
            arrangement_sha256: a.str("sha256")?.to_string(),
            arrangement_size: a.u64("size", u64::MAX)?,
            readable_sha256: a.str("readable_sha256")?.to_string(),
            readable_size: a.u64("readable_size", u64::MAX)?,
        };
        Ok::<_, JsonError>(Receipt {
            attempt: b.u64("attempt", u64::MAX)?,
            prepared: b.str("prepared")?.to_string(),
            prep: b.u64("prep", u64::MAX)?,
            question_capture: q.str("capture")?.to_string(),
            manifest,
            captures,
            checks: b
                .strs("checks")?
                .into_iter()
                .map(|s| s.to_string())
                .collect(),
            i_am_finished: d.bool("i_am_finished")?,
            json: r.json.clone(),
        })
    })();
    res.map_err(|e| e.to_string())
}

/// Read the receipt an `accepted` record names, checking its digest.
pub fn load_receipt(
    audit: &Audit,
    rel: &str,
    want_sha256: &str,
) -> Result<(Receipt, Vec<u8>), ReceiptLoadError> {
    let mut parts = rel.split('/');
    let (Some("intake"), Some(attempt), Some("receipt.json"), None) =
        (parts.next(), parts.next(), parts.next(), parts.next())
    else {
        return Err(ReceiptLoadError::Damaged(format!(
            "the accepted record names {rel:?}, which is not an intake receipt"
        )));
    };
    let dir = audit
        .dir
        .open_dir("intake")
        .and_then(|d| d.open_dir(attempt))
        .map_err(|e| {
            if e.raw_os_error() == Some(libc::ENOENT) {
                ReceiptLoadError::Missing
            } else {
                ReceiptLoadError::Unreadable(util::describe(&e))
            }
        })?;
    let (bytes, _) = dir
        .read_regular("receipt.json", RECORD_LIMIT)
        .map_err(|e| match e {
            crate::fsx::ReadError::Missing => ReceiptLoadError::Missing,
            crate::fsx::ReadError::NotRegular(k) => {
                ReceiptLoadError::Unsupported(format!("it is a {}", k.name()))
            }
            other => ReceiptLoadError::Unreadable(other.describe()),
        })?;
    if util::sha256_hex(&bytes) != want_sha256 {
        return Err(ReceiptLoadError::Damaged(format!(
            "{rel} no longer matches the digest the accepted record binds"
        )));
    }
    let r =
        decode_receipt(&bytes).map_err(|e| ReceiptLoadError::Unsupported(format!("{rel}: {e}")))?;
    Ok((r, bytes))
}

pub enum ReceiptLoadError {
    Missing,
    Damaged(String),
    Unreadable(String),
    Unsupported(String),
}

impl ReceiptLoadError {
    pub fn reason(&self) -> &'static str {
        match self {
            ReceiptLoadError::Missing => "item_missing",
            ReceiptLoadError::Damaged(_) => "item_damaged",
            ReceiptLoadError::Unreadable(_) => "item_unreadable",
            ReceiptLoadError::Unsupported(_) => "item_unsupported",
        }
    }
    pub fn describe(&self) -> String {
        match self {
            ReceiptLoadError::Missing => "the acceptance receipt is missing".into(),
            ReceiptLoadError::Damaged(s)
            | ReceiptLoadError::Unreadable(s)
            | ReceiptLoadError::Unsupported(s) => s.clone(),
        }
    }
}
