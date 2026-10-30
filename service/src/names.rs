//! Names Stewart generates in an audit directory (INTERFACE 4.2, 4.3, 7.4,
//! 8.2) and the claims that allocate the numbered ones.
//!
//! No manager or auditor string becomes a path component: every name here is
//! built from numbers, entry identifiers Stewart assigned (`e<n>`) and the
//! audit identifier.
//!
//! Every numbered name outside `runs/` is claimed, never assumed free: a file
//! with `O_EXCL`, a directory with `mkdirat`, advancing to the next number on
//! `EEXIST`. A claimed name that no log record names is an unpublished
//! candidate; status reports it and never treats it as a record. Names inside
//! `runs/<n>` are assigned in sequence by the lock holder (see `runs`).

use crate::archive::Audit;
use crate::fsx::{Dir, Step, WriteError};
use crate::reply::Cause;
use crate::util;
use std::io;

/// How far a claim advances past taken numbers before giving up.
const CLAIM_SPAN: u64 = 1_000_000;

/// A decimal number as Stewart writes it in names: digits, no sign, no
/// leading zero, at least 1.
pub fn parse_num(s: &str) -> Option<u64> {
    if s.is_empty() || s.len() > 19 || !s.bytes().all(|b| b.is_ascii_digit()) || s.starts_with('0')
    {
        return None;
    }
    s.parse().ok()
}

/// `log/<n>.json`, the name a log record has relative to the audit directory.
pub fn log_name(n: u64) -> String {
    format!("log/{n}.json")
}

pub fn parse_log_name(s: &str) -> Option<u64> {
    parse_num(s.strip_prefix("log/")?.strip_suffix(".json")?)
}

/// An entry's identifier, `e<n>`, numbering entries from 1 in order of creation.
pub fn entry_id(n: u64) -> String {
    format!("e{n}")
}

pub fn parse_entry_id(s: &str) -> Option<u64> {
    parse_num(s.strip_prefix('e')?)
}

/// The payload file of an entry version (7.4): `payload/<id>.v<version>.bin`
/// for the first try, then `payload/<id>.v<version>-<i>.bin` for i = 2, 3, …
/// when an interrupted edit left the earlier name taken.
pub fn payload_name(id: &str, version: u64, i: u64) -> String {
    if i <= 1 {
        format!("payload/{id}.v{version}.bin")
    } else {
        format!("payload/{id}.v{version}-{i}.bin")
    }
}

/// Whether `name` is one of the payload names of this entry version.
pub fn is_payload_name(name: &str, id: &str, version: u64) -> bool {
    let Some(rest) = name
        .strip_prefix("payload/")
        .and_then(|r| r.strip_prefix(id))
        .and_then(|r| r.strip_prefix(&format!(".v{version}")))
        .and_then(|r| r.strip_suffix(".bin"))
    else {
        return false;
    };
    rest.is_empty()
        || rest
            .strip_prefix('-')
            .and_then(parse_num)
            .is_some_and(|i| i >= 2)
}

/// `prepared/<n>`, a preparation of the answer (7.6, 8.1).
pub fn prepared_dir(n: u64) -> String {
    format!("prepared/{n}")
}

/// `seal/manifest-<k>.json`, a return manifest written at seal (8.2).
pub fn manifest_name(k: u64) -> String {
    format!("seal/manifest-{k}.json")
}

pub fn parse_manifest_name(s: &str) -> Option<u64> {
    parse_num(s.strip_prefix("seal/manifest-")?.strip_suffix(".json")?)
}

/// `delivery/<attempt>.json`, a delivery attempt's plan (8.3).
pub fn plan_name(attempt: u64) -> String {
    format!("delivery/{attempt}.json")
}

/// The package directory of a delivery attempt (8.2):
/// `stewart-return-<audit-id>-<nnn>`, the attempt zero-padded to at least
/// three digits.
pub fn package_name(audit: &str, attempt: u64) -> String {
    format!("stewart-return-{audit}-{attempt:03}")
}

/// The return member holding an artifact entry's bytes: `artifact-<id>.bin`.
pub fn artifact_member(id: &str) -> String {
    format!("artifact-{id}.bin")
}

/// A loss's member token (2.3): an entry ID stays as it is; a member file
/// name has each `.` replaced by `-` (`answer.md` gives `answer-md`).
pub fn member_token(member: &str) -> String {
    member.replace('.', "-")
}

// ---------------------------------------------------------------------------
// Claims.

/// Claim the lowest free numbered directory `<parent>/<n>`, n ≥ 1, with
/// `mkdirat`, and open it.
pub fn claim_dir(parent: &Dir) -> io::Result<(u64, Dir)> {
    for n in 1..=CLAIM_SPAN {
        match parent.mkdir(&n.to_string()) {
            Ok(()) => return Ok((n, parent.open_dir(&n.to_string())?)),
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => continue,
            Err(e) => return Err(e),
        }
    }
    Err(io::Error::from_raw_os_error(libc::ENOSPC))
}

/// Claim the lowest free numbered file `name(n)`, n ≥ 1, in `dir` with
/// `O_EXCL` and publish `bytes(n)` in it (write, `fsync`, `fsync` the
/// directory). The bytes may depend on the number claimed. Returns the
/// number, the name and the bytes written. A failure after the file was
/// created leaves it in place as evidence.
pub fn claim_file(
    dir: &Dir,
    name: impl Fn(u64) -> String,
    bytes: impl Fn(u64) -> Vec<u8>,
) -> Result<(u64, String, Vec<u8>), WriteError> {
    for n in 1..=CLAIM_SPAN {
        let file = name(n);
        let b = bytes(n);
        match dir.write_excl(&file, &b) {
            Ok(()) => return Ok((n, file, b)),
            Err(e) if e.step == Step::Create && e.err.raw_os_error() == Some(libc::EEXIST) => {
                continue;
            }
            Err(e) => return Err(e),
        }
    }
    Err(WriteError {
        step: Step::Create,
        err: io::Error::from_raw_os_error(libc::ENOSPC),
    })
}

fn write_cause(what: &str, e: &WriteError, at: String) -> Cause {
    Cause::io(format!("{what} ({})", e.step.name()), &e.err).at(at)
}

/// Claim `prepared/<n>` for a new preparation of the answer.
pub fn claim_prepared(audit: &Audit) -> Result<(u64, Dir), Cause> {
    let root = audit
        .sub("prepared")
        .map_err(|e| Cause::io("open prepared directory", &e).at(audit.abs("prepared")))?;
    claim_dir(&root)
        .map_err(|e| Cause::io("claim preparation of the answer", &e).at(audit.abs("prepared")))
}

/// Write one file of a claimed `prepared/<n>` exclusively (fault point
/// `prepared.write`). Returns the file's SHA-256.
pub fn write_prepared_file(
    audit: &Audit,
    dir: &Dir,
    n: u64,
    name: &str,
    bytes: &[u8],
) -> Result<String, Cause> {
    let at = audit.abs(&format!("{}/{name}", prepared_dir(n)));
    crate::fault!("prepared.write").map_err(|e| Cause::io("write prepared file", &e).at(&at))?;
    dir.write_excl(name, bytes)
        .map_err(|e| write_cause("write prepared file", &e, at))?;
    Ok(util::sha256_hex(bytes))
}

/// Claim `seal/manifest-<k>.json` and write the return manifest in it (fault
/// point `seal.manifest_write`). Returns `k` and the audit-relative name.
pub fn write_manifest(audit: &Audit, bytes: &[u8]) -> Result<(u64, String), Cause> {
    let dir = audit
        .sub("seal")
        .map_err(|e| Cause::io("open seal directory", &e).at(audit.abs("seal")))?;
    crate::fault!("seal.manifest_write")
        .map_err(|e| Cause::io("write seal manifest", &e).at(audit.abs("seal")))?;
    let (k, _, _) = claim_file(&dir, |k| format!("manifest-{k}.json"), |_| bytes.to_vec())
        .map_err(|e| write_cause("write seal manifest", &e, audit.abs("seal")))?;
    Ok((k, manifest_name(k)))
}

/// Claim `delivery/<attempt>.json` and write the attempt's plan in it. The
/// plan names its own attempt, so `bytes` receives the number claimed.
/// Returns the attempt and the bytes written.
pub fn write_plan(audit: &Audit, bytes: impl Fn(u64) -> Vec<u8>) -> Result<(u64, Vec<u8>), Cause> {
    let dir = audit
        .sub("delivery")
        .map_err(|e| Cause::io("open delivery directory", &e).at(audit.abs("delivery")))?;
    let (attempt, _, written) = claim_file(&dir, |n| format!("{n}.json"), &bytes)
        .map_err(|e| write_cause("write delivery plan", &e, audit.abs("delivery")))?;
    Ok((attempt, written))
}

/// A stored entry payload: what its `entry` record binds.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoredPayload {
    /// Audit-relative name, `payload/<id>.v<version>[-<i>].bin`.
    pub file: String,
    pub sha256: String,
    pub size: u64,
}

/// Store an entry version's bytes in a new payload file before its `entry`
/// record is published (7.4). The first free name among
/// `payload/<id>.v<version>.bin`, `…-2.bin`, `…-3.bin` is used. Fault points
/// `entry.payload_write` (before writing) and `entry.payload_corrupt` (after
/// writing; the result still states the intended digest).
pub fn write_payload(
    audit: &Audit,
    id: &str,
    version: u64,
    bytes: &[u8],
) -> Result<StoredPayload, Cause> {
    let dir = audit
        .sub("payload")
        .map_err(|e| Cause::io("open payload directory", &e).at(audit.abs("payload")))?;
    crate::fault!("entry.payload_write")
        .map_err(|e| Cause::io("write payload", &e).at(audit.abs("payload")))?;
    let local = |i: u64| {
        payload_name(id, version, i)
            .strip_prefix("payload/")
            .expect("payload names start with payload/")
            .to_string()
    };
    let (i, name, _) = claim_file(&dir, local, |_| bytes.to_vec())
        .map_err(|e| write_cause("write payload", &e, audit.abs("payload")))?;
    #[cfg(feature = "fault-injection")]
    if crate::fault_corrupt!("entry.payload_corrupt") {
        let _ = dir.corrupt_file(&name);
    }
    let _ = name;
    Ok(StoredPayload {
        file: payload_name(id, version, i),
        sha256: util::sha256_hex(bytes),
        size: bytes.len() as u64,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_have_the_specified_shapes() {
        assert_eq!(log_name(9), "log/9.json");
        assert_eq!(parse_log_name("log/9.json"), Some(9));
        for bad in [
            "log/09.json",
            "log/0.json",
            "log/9",
            "logs/9.json",
            "log/9.json/",
        ] {
            assert_eq!(parse_log_name(bad), None, "{bad}");
        }
        assert_eq!(entry_id(3), "e3");
        assert_eq!(parse_entry_id("e3"), Some(3));
        assert_eq!(parse_entry_id("e03"), None);
        assert_eq!(payload_name("e2", 2, 1), "payload/e2.v2.bin");
        assert_eq!(payload_name("e2", 2, 3), "payload/e2.v2-3.bin");
        assert!(is_payload_name("payload/e2.v2.bin", "e2", 2));
        assert!(is_payload_name("payload/e2.v2-2.bin", "e2", 2));
        assert!(!is_payload_name("payload/e2.v2-1.bin", "e2", 2));
        assert!(!is_payload_name("payload/e2.v3.bin", "e2", 2));
        assert!(!is_payload_name("payload/e22.v2.bin", "e2", 2));
        assert_eq!(manifest_name(1), "seal/manifest-1.json");
        assert_eq!(parse_manifest_name("seal/manifest-12.json"), Some(12));
        assert_eq!(plan_name(3), "delivery/3.json");
        assert_eq!(
            package_name("aqm3x7kd2hz5vw4ny", 1),
            "stewart-return-aqm3x7kd2hz5vw4ny-001"
        );
        assert_eq!(
            package_name("aqm3x7kd2hz5vw4ny", 1234),
            "stewart-return-aqm3x7kd2hz5vw4ny-1234"
        );
        assert_eq!(member_token("answer.md"), "answer-md");
        assert_eq!(member_token("artifact-e4.bin"), "artifact-e4-bin");
        assert_eq!(member_token("e3"), "e3");
        assert_eq!(artifact_member("e4"), "artifact-e4.bin");
    }

    #[test]
    fn claims_advance_past_taken_numbers_and_never_overwrite() {
        let (p, audit) = crate::log::tests::scratch_audit();
        let (n1, _) = claim_prepared(&audit).unwrap();
        let (n2, d2) = claim_prepared(&audit).unwrap();
        assert_eq!((n1, n2), (1, 2));
        write_prepared_file(&audit, &d2, n2, "answer.json", b"{}\n").unwrap();
        assert!(write_prepared_file(&audit, &d2, n2, "answer.json", b"x").is_err());
        assert_eq!(
            std::fs::read(p.join("a/prepared/2/answer.json")).unwrap(),
            b"{}\n"
        );
        // A manifest name another writer took is skipped.
        std::fs::create_dir_all(p.join("a/seal")).unwrap();
        std::fs::write(p.join("a/seal/manifest-1.json"), b"other").unwrap();
        assert_eq!(
            write_manifest(&audit, b"m\n").unwrap(),
            (2, "seal/manifest-2.json".into())
        );
        assert_eq!(
            std::fs::read(p.join("a/seal/manifest-1.json")).unwrap(),
            b"other"
        );
        // The plan's bytes name the attempt claimed.
        std::fs::create_dir_all(p.join("a/delivery")).unwrap();
        std::fs::write(p.join("a/delivery/1.json"), b"left behind").unwrap();
        let (attempt, bytes) = write_plan(&audit, |n| format!("plan {n}").into_bytes()).unwrap();
        assert_eq!((attempt, bytes.as_slice()), (2, b"plan 2".as_slice()));
        // A payload name left by an interrupted edit is skipped, never reused.
        std::fs::create_dir_all(p.join("a/payload")).unwrap();
        std::fs::write(p.join("a/payload/e1.v1.bin"), b"interrupted").unwrap();
        let s = write_payload(&audit, "e1", 1, b"text").unwrap();
        assert_eq!(s.file, "payload/e1.v1-2.bin");
        assert_eq!(s.size, 4);
        assert_eq!(s.sha256, util::sha256_hex(b"text"));
        assert_eq!(
            std::fs::read(p.join("a/payload/e1.v1.bin")).unwrap(),
            b"interrupted"
        );
        std::fs::remove_dir_all(p).unwrap();
    }
}
