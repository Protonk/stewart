//! The archive (INTERFACE 4): store marker, reference resolution, audit
//! directories, record headers, the active lock and diagnostics.

use crate::fsx::{Dir, WalkError};
use crate::ids::{self, Reference};
use crate::json::{self, J};
use crate::platform::{self, Exe};
use crate::reply::{Cause, Next, Outcome, Reply};
use crate::util;
use std::fs::File;
use std::io;
use std::os::fd::FromRawFd;

pub const RECORD_SCHEMA: &str = "stewart.record/1";
pub const RECORD_LIMIT: u64 = 4 * 1024 * 1024;
pub const STORE_FILE: &str = "STORE.json";
pub const REFERENCE_FILE: &str = "REFERENCE.json";
pub const LOCK_FILE: &str = "active.lock";
/// Directories of an audit, created by `new` (and on demand if missing).
pub const AUDIT_DIRS: [&str; 10] = [
    "log", "stage", "prep", "intake", "payload", "prepared", "seal", "runs", "delivery", "diag",
];

/// A refusal or failure on its way to a reply: stable reason, sentence,
/// retained locations, causes and useful data. Operations add their effects
/// and next calls.
#[derive(Debug, Clone)]
pub struct Fail {
    pub outcome: Outcome,
    pub reason: &'static str,
    pub message: String,
    pub retained: Vec<String>,
    pub causes: Vec<Cause>,
    pub data: Option<J>,
    pub next: Vec<Next>,
}

impl Fail {
    pub fn refused(reason: &'static str, message: impl Into<String>) -> Fail {
        Fail {
            outcome: Outcome::Refused,
            reason,
            message: message.into(),
            retained: vec![],
            causes: vec![],
            data: None,
            next: vec![],
        }
    }
    pub fn failed(reason: &'static str, message: impl Into<String>) -> Fail {
        Fail {
            outcome: Outcome::Failed,
            reason,
            message: message.into(),
            retained: vec![],
            causes: vec![],
            data: None,
            next: vec![],
        }
    }
    pub fn data(mut self, d: J) -> Fail {
        self.data = Some(d);
        self
    }
    pub fn cause(mut self, c: Cause) -> Fail {
        self.causes.push(c);
        self
    }
    pub fn retain(mut self, p: impl Into<String>) -> Fail {
        self.retained.push(p.into());
        self
    }
    pub fn next(mut self, n: Next) -> Fail {
        self.next.push(n);
        self
    }
    pub fn into_reply(
        self,
        operation: &'static str,
        effects: Vec<(&'static str, &'static str)>,
    ) -> Reply {
        Reply {
            operation,
            outcome: self.outcome,
            reason: Some(self.reason.to_string()),
            message: Some(self.message),
            effects,
            retained: self.retained,
            causes: self.causes,
            next: self.next,
            tool_next: Vec::new(),
            data: self.data,
        }
    }
}

/// The record header (INTERFACE 4.3).
pub fn record_bytes(kind: &str, audit: Option<&str>, writer: &str, body: J) -> Vec<u8> {
    let mut b = J::obj()
        .with("record", RECORD_SCHEMA)
        .with("kind", kind)
        .with("audit", audit)
        .with("writer", writer)
        .with("at", util::now_utc())
        .with("body", body)
        .bytes();
    b.push(b'\n');
    b
}

/// A decoded record: header fields and the raw body span.
pub struct Record {
    pub kind: String,
    pub audit: Option<String>,
    pub writer: String,
    pub at: String,
    pub json: json::Json,
}

impl Record {
    pub fn body(&self) -> json::Obj<'_> {
        self.json
            .obj("")
            .expect("checked")
            .get("body")
            .expect("checked")
            .obj("/body")
            .expect("checked")
    }
}

/// Decode a record strictly and check its header.
pub fn decode_record(bytes: &[u8]) -> Result<Record, String> {
    let v = json::parse(bytes).map_err(|e| format!("not strict control JSON: {e}"))?;
    let (kind, audit, writer, at) = {
        let o = v.obj("").map_err(|e| e.to_string())?;
        o.only(&["record", "kind", "audit", "writer", "at", "body"])
            .map_err(|e| e.to_string())?;
        let schema = o.str("record").map_err(|e| e.to_string())?;
        if schema != RECORD_SCHEMA {
            return Err(format!(
                "record schema {schema:?} is not supported by this writer"
            ));
        }
        let kind = o.str("kind").map_err(|e| e.to_string())?.to_string();
        let audit = o
            .str_or_null("audit")
            .map_err(|e| e.to_string())?
            .map(|s| s.to_string());
        let writer = o.str("writer").map_err(|e| e.to_string())?.to_string();
        if !util::is_hex64(&writer) {
            return Err("the writer is not a SHA-256 digest".into());
        }
        let at = o.str("at").map_err(|e| e.to_string())?.to_string();
        if !util::is_utc_ms(&at) {
            return Err("at is not a UTC time with milliseconds".into());
        }
        o.obj("body").map_err(|e| e.to_string())?;
        (kind, audit, writer, at)
    };
    Ok(Record {
        kind,
        audit,
        writer,
        at,
        json: v,
    })
}

// ---------------------------------------------------------------------------
// Opening the archive root.

/// Open the archive root by walking its path without following links.
pub fn open_root(path: &str) -> Result<Dir, Fail> {
    Dir::open_nofollow(path).map_err(|e| walk_fail(path, e))
}

pub fn walk_fail(path: &str, e: WalkError) -> Fail {
    match e {
        WalkError::Symlink(at) => Fail::refused(
            "archive_path_symlink",
            format!("The archive path {path} has a symbolic link component at {at}; the archive root's path must have none. Use the path without links."),
        )
        .data(J::obj().with("component", at)),
        WalkError::Missing(at) => Fail::refused("archive_unavailable", format!("The archive root {path} cannot be opened: {at} does not exist."))
            .data(J::obj().with("missing", at)),
        WalkError::NotDir(at) => Fail::refused("archive_unavailable", format!("The archive root {path} cannot be opened: {at} is not a directory.")),
        WalkError::Io(at, err) => Fail::refused("archive_unavailable", format!("The archive root {path} cannot be opened at {at}: {}.", util::describe(&err)))
            .cause(Cause::io("open archive root", &err).at(at)),
    }
}

/// The filesystem allowlist (INTERFACE 4.1).
pub fn check_filesystem(dir: &Dir) -> Result<platform::FsInfo, Fail> {
    let fs = platform::filesystem(&dir.file).map_err(|e| {
        Fail::failed(
            "archive_unavailable",
            format!(
                "The filesystem of {} could not be examined: {}.",
                dir.path,
                util::describe(&e)
            ),
        )
        .cause(Cause::io("statfs", &e).at(dir.path.clone()))
    })?;
    if !fs.supported {
        return Err(Fail::refused(
            "archive_filesystem_unsupported",
            format!(
                "The archive at {} is on a {} filesystem. The archive needs local ext4, xfs or btrfs (exclusive links, advisory locks and directory synchronization); choose a location on one of those.",
                dir.path, fs.name
            ),
        )
        .data(J::obj().with("observed", fs.name.as_str())));
    }
    Ok(fs)
}

pub struct Marker {
    pub store: String,
    pub created_path: String,
    pub inode: u64,
    pub birth: Option<String>,
}

pub fn marker_body(store: &str, path: &str, root: &Dir) -> io::Result<J> {
    let st = root.stat()?;
    let birth = platform::birth_time(&root.file)?;
    let fsid = platform::filesystem(&root.file).map(|f| f.fsid).ok();
    Ok(J::obj()
        .with("store", store)
        .with("created_path", path)
        .with("root", J::obj().with("inode", st.ino).with("birth", birth))
        .with(
            "observations",
            J::obj().with("fsid", fsid).with("device", st.dev),
        ))
}

pub fn decode_marker(bytes: &[u8]) -> Result<Marker, String> {
    let r = decode_record(bytes)?;
    if r.kind != "store" {
        return Err(format!("the store marker has kind {:?}", r.kind));
    }
    let b = r.body();
    let res = (|| {
        b.only(&["store", "created_path", "root", "observations"])?;
        let store = b.str("store")?.to_string();
        let created_path = b.str("created_path")?.to_string();
        let root = b.obj("root")?;
        root.only(&["inode", "birth"])?;
        let inode = root.u64("inode", u64::MAX)?;
        let birth = root.str_or_null("birth")?.map(|s| s.to_string());
        let obs = b.obj("observations")?;
        obs.only(&["fsid", "device"])?;
        obs.str_or_null("fsid")?;
        obs.u64("device", u64::MAX)?;
        Ok::<_, json::JsonError>(Marker {
            store,
            created_path,
            inode,
            birth,
        })
    })()
    .map_err(|e| e.to_string())?;
    if !ids::is_id(&res.store, 's') {
        return Err("the store identifier is malformed".into());
    }
    Ok(res)
}

pub struct Archive {
    pub root: Dir,
    pub path: String,
    pub store: String,
    /// Why this root is not the archive the marker was created in, if so.
    pub moved: Option<String>,
}

/// Open the archive a reference names: root, marker, store identity.
pub fn open_archive(r: &Reference) -> Result<Archive, Fail> {
    let root = open_root(&r.root)?;
    let (bytes, _) = match root.read_regular(STORE_FILE, RECORD_LIMIT) {
        Ok(x) => x,
        Err(crate::fsx::ReadError::Missing) => {
            return Err(Fail::refused(
                "archive_replaced",
                format!(
                    "{} holds no Stewart store marker, so it is not the store this reference names; Stewart does not create or substitute a store.",
                    r.root
                ),
            ));
        }
        Err(e) => {
            return Err(Fail::refused(
                "archive_unavailable",
                format!(
                    "The store marker {}/{STORE_FILE} cannot be read: {}.",
                    r.root,
                    e.describe()
                ),
            ));
        }
    };
    let m = decode_marker(&bytes).map_err(|e| {
        Fail::refused(
            "archive_unavailable",
            format!(
                "The store marker {}/{STORE_FILE} cannot be decoded: {e}.",
                r.root
            ),
        )
    })?;
    if m.store != r.store && !crate::sabotage!("select_newer_store") {
        return Err(Fail::refused(
            "archive_replaced",
            format!("{} holds store {}, not store {} that this reference names. Stewart never substitutes another store.", r.root, m.store, r.store),
        )
        .data(J::obj().with("found_store", m.store.as_str()).with("expected_store", r.store.as_str())));
    }
    let st = root.stat().map_err(|e| {
        Fail::failed(
            "archive_unavailable",
            format!(
                "The archive root {} cannot be examined: {}.",
                r.root,
                util::describe(&e)
            ),
        )
    })?;
    let birth = platform::birth_time(&root.file).ok().flatten();
    let mut moved = None;
    if st.ino != m.inode {
        moved = Some(format!(
            "the root's inode is {} but the store marker recorded {}",
            st.ino, m.inode
        ));
    } else if m.birth.is_some() && birth.is_some() && m.birth != birth {
        moved = Some(format!(
            "the root's birth time is {} but the store marker recorded {}",
            birth.unwrap_or_default(),
            m.birth.clone().unwrap_or_default()
        ));
    }
    Ok(Archive {
        root,
        path: r.root.clone(),
        store: m.store,
        moved,
    })
}

// ---------------------------------------------------------------------------
// Audits.

pub struct RefFile {
    pub audit: String,
    pub store: String,
    pub folder: String,
    pub writer_path: String,
    pub writer_sha256: String,
    pub at: String,
    pub sha256: String,
}

pub fn decode_reference_file(bytes: &[u8]) -> Result<RefFile, String> {
    let r = decode_record(bytes)?;
    if r.kind != "reference" {
        return Err(format!("REFERENCE.json has kind {:?}", r.kind));
    }
    let at = r.at.clone();
    let b = r.body();
    (|| {
        b.only(&["audit", "store", "archive", "folder", "writer"])?;
        let w = b.obj("writer")?;
        w.only(&["path", "sha256"])?;
        b.str("archive")?;
        Ok::<_, json::JsonError>(RefFile {
            audit: b.str("audit")?.to_string(),
            store: b.str("store")?.to_string(),
            folder: b.str("folder")?.to_string(),
            writer_path: w.str("path")?.to_string(),
            writer_sha256: w.str("sha256")?.to_string(),
            at,
            sha256: util::sha256_hex(bytes),
        })
    })()
    .map_err(|e| e.to_string())
}

pub struct Audit {
    pub archive: Archive,
    pub id: String,
    pub dir: Dir,
    /// The canonical reference string.
    pub reference: String,
    pub refile: RefFile,
    /// The running executable, once a mutation has been authorized.
    pub exe: Option<Exe>,
}

impl Audit {
    /// Resolve a reference to its audit, for reading.
    pub fn open(reference: &str) -> Result<Audit, Fail> {
        let r = ids::decode_reference(reference).map_err(|e| {
            Fail::refused(
                "reference_invalid",
                format!("{reference:?} is not a well-formed stw1: reference: {e}."),
            )
        })?;
        let archive = open_archive(&r)?;
        let audits = archive.root.open_dir("audits").map_err(|e| {
            Fail::refused(
                "reference_unknown",
                format!(
                    "Store {} at {} has no audits directory ({}).",
                    archive.store,
                    archive.path,
                    util::errno_name(&e)
                ),
            )
        })?;
        let dir = match audits.open_dir(&r.audit) {
            Ok(d) => d,
            Err(e) if e.raw_os_error() == Some(libc::ENOENT) => {
                return Err(Fail::refused(
                    "reference_unknown",
                    format!(
                        "Store {} at {} has no audit {}.",
                        archive.store, archive.path, r.audit
                    ),
                ));
            }
            Err(e) => {
                return Err(Fail::refused(
                    "archive_unavailable",
                    format!(
                        "Audit {} cannot be opened: {}.",
                        r.audit,
                        util::describe(&e)
                    ),
                ));
            }
        };
        let refile = match dir.read_regular(REFERENCE_FILE, RECORD_LIMIT) {
            Ok((bytes, _)) => decode_reference_file(&bytes).map_err(|e| {
                Fail::failed(
                    "reference_unknown",
                    format!("{}/{REFERENCE_FILE} cannot be decoded: {e}.", dir.path),
                )
                .retain(format!("{}/{REFERENCE_FILE}", dir.path))
            })?,
            Err(e) => {
                return Err(Fail::failed(
                    "reference_unknown",
                    format!(
                        "{}/{REFERENCE_FILE} cannot be read: {}.",
                        dir.path,
                        e.describe()
                    ),
                )
                .retain(dir.path.clone()));
            }
        };
        if refile.audit != r.audit || refile.store != archive.store {
            return Err(Fail::failed(
                "reference_unknown",
                format!(
                    "{}/{REFERENCE_FILE} names another audit or store.",
                    dir.path
                ),
            ));
        }
        let reference = ids::encode_reference(&r.audit, &r.store, &r.root);
        Ok(Audit {
            archive,
            id: r.audit,
            dir,
            reference,
            refile,
            exe: None,
        })
    }

    /// Authorize a mutation: the archive is the original (not moved or
    /// copied), on a supported filesystem, and this binary is the writer.
    pub fn require_mutation(&mut self) -> Result<(), Fail> {
        if let Some(why) = &self.archive.moved {
            return Err(Fail::refused(
                "archive_moved_or_copied",
                format!(
                    "The store marker at {} matches, but {why}: this is a moved or copied archive. Receipt and status can read it; a copy never acquires execution.",
                    self.archive.path
                ),
            ));
        }
        check_filesystem(&self.archive.root)?;
        let exe = platform::current_exe().map_err(|e| {
            Fail::refused(
                "writer_mismatch",
                format!("Stewart could not hash its own executable ({}), so it cannot show that it is this audit's writer.", util::describe(&e)),
            )
        })?;
        if exe.sha256 != self.refile.writer_sha256 {
            return Err(Fail::refused(
                "writer_mismatch",
                format!(
                    "This audit's writer is {} (SHA-256 {}); this binary ({}, SHA-256 {}) may read its records but not change them.",
                    self.refile.writer_path, self.refile.writer_sha256, exe.path, exe.sha256
                ),
            )
            .data(J::obj().with("writer", J::obj().with("path", self.refile.writer_path.as_str()).with("sha256", self.refile.writer_sha256.as_str()))));
        }
        self.exe = Some(exe);
        Ok(())
    }

    pub fn writer(&self) -> &str {
        &self.refile.writer_path
    }

    /// argv for a suggested call, beginning with the recorded writer path.
    pub fn argv(&self, args: &[&str]) -> Vec<String> {
        let mut v = vec![self.refile.writer_path.clone()];
        v.extend(args.iter().map(|s| s.to_string()));
        v
    }

    pub fn path(&self) -> &str {
        &self.dir.path
    }

    pub fn abs(&self, rel: &str) -> String {
        format!("{}/{rel}", self.dir.path)
    }

    pub fn sub(&self, name: &str) -> io::Result<Dir> {
        self.dir.ensure_dir(name)
    }

    /// A record with this audit's header. Requires an authorized writer.
    pub fn record(&self, kind: &str, body: J) -> Vec<u8> {
        let writer = self
            .exe
            .as_ref()
            .map(|e| e.sha256.as_str())
            .unwrap_or(&self.refile.writer_sha256);
        record_bytes(kind, Some(&self.id), writer, body)
    }

    pub fn open_lock(&self, write: bool) -> io::Result<File> {
        let c = crate::fsx::cstr(LOCK_FILE)?;
        let flags = (if write { libc::O_RDWR } else { libc::O_RDONLY })
            | libc::O_NOFOLLOW
            | libc::O_CLOEXEC;
        let fd = unsafe {
            libc::openat(
                std::os::fd::AsRawFd::as_raw_fd(&self.dir.file),
                c.as_ptr(),
                flags,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(unsafe { File::from_raw_fd(fd) })
    }

    /// Try once to take the active lock. `Ok(None)`: another holder has it.
    pub fn try_lock(&self) -> io::Result<Option<File>> {
        let f = self.open_lock(true)?;
        if platform::lock_try(&f)? {
            Ok(Some(f))
        } else {
            Ok(None)
        }
    }

    /// Test the active lock without taking it.
    pub fn lock_held(&self) -> io::Result<bool> {
        let f = self.open_lock(false)?;
        platform::lock_held(&f)
    }

    /// Write a diagnostic record into `diag/` (INTERFACE 4.8), claiming the
    /// next free number. Returns the absolute path.
    pub fn write_diag(&self, body: J) -> Result<String, Cause> {
        crate::fault!("diag.write").map_err(|e| Cause::io("write diagnostic", &e))?;
        let diag = self
            .dir
            .open_dir("diag")
            .map_err(|e| Cause::io("open diag directory", &e).at(self.abs("diag")))?;
        let start = diag
            .names()
            .map(|ns| {
                ns.iter()
                    .filter_map(|n| n.strip_suffix(".json").and_then(|x| x.parse::<u64>().ok()))
                    .max()
                    .unwrap_or(0)
                    + 1
            })
            .unwrap_or(1);
        let bytes = self.record("diagnostic", body);
        for n in start..start + 10_000 {
            let name = format!("{n}.json");
            match diag.write_excl(&name, &bytes) {
                Ok(()) => return Ok(self.abs(&format!("diag/{name}"))),
                Err(e)
                    if e.step == crate::fsx::Step::Create
                        && e.err.raw_os_error() == Some(libc::EEXIST) =>
                {
                    continue;
                }
                Err(e) => {
                    return Err(
                        Cause::io(format!("write diagnostic ({})", e.step.name()), &e.err)
                            .at(self.abs(&format!("diag/{name}"))),
                    );
                }
            }
        }
        Err(Cause::new("write diagnostic", "no free diagnostic number"))
    }

    /// Record a refused or failed reply's account in `diag/` before the reply
    /// is written, and report whether it is durable (INTERFACE 4.8).
    pub fn diagnose(&self, reply: &mut Reply, extra: J) {
        if reply.outcome == Outcome::Completed {
            return;
        }
        let body = J::obj()
            .with("operation", reply.operation)
            .with("outcome", reply.outcome.name())
            .with("reason", reply.reason.clone())
            .with("message", reply.message.clone())
            .with(
                "effects",
                J::Obj(
                    reply
                        .effects
                        .iter()
                        .map(|(k, v)| (k.to_string(), J::Str(v.to_string())))
                        .collect(),
                ),
            )
            .with("retained", json::strs(&reply.retained))
            .with(
                "causes",
                J::Arr(reply.causes.iter().map(|c| c.to_j()).collect()),
            )
            .with("data", reply.data.clone())
            .with("context", extra);
        match self.write_diag(body) {
            Ok(path) => {
                reply.set_effect("diagnostic", "durable");
                reply.retained.push(path);
            }
            Err(cause) => {
                reply.set_effect("diagnostic", "reported_only");
                if reply.causes.is_empty() {
                    // The original cause comes first: the refusal itself.
                    reply.causes.push(Cause::new(
                        reply.operation,
                        reply.reason.clone().unwrap_or_default(),
                    ));
                }
                reply.causes.push(cause);
            }
        }
    }
}

/// Observations about this invocation, recorded as observations only.
pub fn observations() -> J {
    J::obj()
        .with("pid", platform::pid())
        .with("uid", platform::uid())
        .with("host", platform::host_name())
        .with("boot_id", platform::boot_id())
}
