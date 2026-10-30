//! `stewart prepare REF` (INTERFACE 5.3): scan the folder, check the
//! mechanical intake rules, pin the arrangement and return a manager
//! preparation handle. It accepts nothing and preserves no source bytes.

use super::{Place, check_overlap};
use crate::archive::{Audit, Fail};
use crate::forms::{self, ArrangementInput};
use crate::frontmatter;
use crate::fsx::Dir;
use crate::ids;
use crate::json::{self, J};
use crate::log::{self, PubErr};
use crate::records::{self, MFile, ManifestParts, QInfo};
use crate::reply::{Cause, Next, Reply};
use crate::scan::{self, Exclude};
use crate::util;

const OP: &str = "prepare";

fn eff(v: &'static str) -> Vec<(&'static str, &'static str)> {
    vec![("preparation", v)]
}

pub fn run(reference: &str) -> Reply {
    let mut audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, eff("none")),
    };
    if let Err(f) = audit.require_mutation() {
        return f.into_reply(OP, eff("none"));
    }
    let mut reply = match prepare(&audit) {
        Ok(r) => r,
        Err(f) => f.into_reply(OP, eff("none")),
    };
    audit.diagnose(
        &mut reply,
        J::obj().with("reference", audit.reference.as_str()),
    );
    reply
}

fn scan_fail(f: scan::Refusal) -> Fail {
    Fail::refused(f.reason, f.message).data(f.data)
}

/// The precondition every preparation checks: no acceptance, no close request.
fn precondition(audit: &Audit, state: &log::LogState) -> Result<(), Fail> {
    if state.damaged() {
        return Err(log::damaged_fail(audit, state));
    }
    if let Some(a) = state.accepted() {
        return Err(Fail::refused(
            "reference_already_accepted",
            format!("This reference already has an accepted commission (log/{}.json); another commission needs its own reference from new.", a.n),
        )
        .next(Next::new(audit.argv(&["receipt", &audit.reference]), "Read the accepted commission."))
        .next(Next::new(audit.argv(&["status", &audit.reference]), "See where the audit stands.")));
    }
    if let Some(c) = state.close_requested() {
        return Err(Fail::refused("reference_closed", format!("Close was requested for this reference (log/{}.json); it accepts no further preparation.", c.n))
            .next(Next::new(audit.argv(&["status", &audit.reference]), "See how the reference ended.")));
    }
    Ok(())
}

fn prepare(audit: &Audit) -> Result<Reply, Fail> {
    let state = log::read(audit);
    precondition(audit, &state)?;
    let folder_path = audit.refile.folder.clone();
    let retry = Next::new(
        audit.argv(&["prepare", &audit.reference]),
        "Correct the folder, finish editing, then prepare again.",
    );
    let close = Next::new(
        audit.argv(&["close", &audit.reference]),
        "End this reference without commissioning.",
    );
    let with_next = |f: Fail| f.next(retry.clone()).next(close.clone());

    let folder = Dir::open_follow(&folder_path).map_err(|e| {
        with_next(
            if e.raw_os_error() == Some(libc::ENOENT) {
                Fail::refused(
                    "folder_incomplete",
                    format!("The folder {folder_path} recorded for this reference does not exist."),
                )
            } else {
                Fail::refused(
                    "source_unreadable",
                    format!(
                        "The folder {folder_path} cannot be opened: {}.",
                        util::describe(&e)
                    ),
                )
            }
            .cause(Cause::io("open folder", &e).at(folder_path.as_str())),
        )
    })?;
    check_overlap(&[
        Place {
            what: "archive",
            path: &audit.archive.path,
            dir: &audit.archive.root,
        },
        Place {
            what: "folder",
            path: &folder_path,
            dir: &folder,
        },
    ])
    .map_err(with_next)?;

    scan::check_root(&folder)
        .map_err(scan_fail)
        .map_err(with_next)?;
    let qf = scan::read_question(&folder)
        .map_err(scan_fail)
        .map_err(with_next)?;
    let q = frontmatter::parse(&qf.bytes).map_err(|defects| {
        let first = defects[0].reason;
        let msg = if defects.len() == 1 {
            format!("question.md: {}", defects[0].message)
        } else {
            let items: Vec<String> = defects.iter().map(|d| d.message.clone()).collect();
            format!(
                "question.md needs {} edits: {}",
                defects.len(),
                items.join(" ")
            )
        };
        with_next(Fail::refused(first, msg).data(J::obj().with(
            "defects",
            J::Arr(defects.iter().map(|d| d.to_j()).collect()),
        )))
    })?;
    let settings = q.settings.clone();

    // The destination must exist, be a directory and overlap neither location.
    let dest = Dir::open_follow(&settings.destination).map_err(|e| {
        let why = match e.raw_os_error() {
            Some(libc::ENOENT) => "does not exist".to_string(),
            Some(libc::ENOTDIR) => "is not a directory".to_string(),
            _ => format!("cannot be opened ({})", util::describe(&e)),
        };
        with_next(
            Fail::refused("destination_invalid", format!("The destination {} {why}; it must be an existing directory in which Stewart creates the return package.", settings.destination))
                .data(J::obj().with("destination", settings.destination.as_str())),
        )
    })?;
    check_overlap(&[
        Place {
            what: "archive",
            path: &audit.archive.path,
            dir: &audit.archive.root,
        },
        Place {
            what: "folder",
            path: &folder_path,
            dir: &folder,
        },
        Place {
            what: "destination",
            path: &settings.destination,
            dir: &dest,
        },
    ])
    .map_err(with_next)?;

    let exclude = Exclude {
        ids: vec![
            (
                audit
                    .archive
                    .root
                    .stat()
                    .map(|s| s.id())
                    .unwrap_or((u64::MAX, u64::MAX)),
                "archive root".to_string(),
            ),
            (
                dest.stat().map(|s| s.id()).unwrap_or((u64::MAX, u64::MAX)),
                "destination".to_string(),
            ),
        ],
    };
    eprintln!(
        "stewart prepare: scanning {folder_path}/materials (bounds: {} files, {} bytes in total)",
        scan::FILES,
        scan::TOTAL_BYTES
    );
    let s = scan::scan(&folder, &exclude)
        .map_err(scan_fail)
        .map_err(with_next)?;
    if s.question.bytes != qf.bytes {
        return Err(with_next(Fail::refused(
            "source_unreadable",
            "question.md changed while the folder was being prepared; finish editing, then prepare again.",
        )));
    }
    eprintln!(
        "stewart prepare: {} files, {} bytes; pinning the arrangement",
        s.files.len(),
        s.material_bytes()
    );

    let body = &qf.bytes[q.body_offset..];
    let question = QInfo {
        file_bytes: qf.bytes.len() as u64,
        file_sha256: util::sha256_hex(&qf.bytes),
        body_offset: q.body_offset as u64,
        body_bytes: body.len() as u64,
        body_sha256: util::sha256_hex(body),
        mtime: qf.stat.mtime(),
    };
    let files: Vec<MFile> = s
        .files
        .iter()
        .map(|m| MFile {
            name: m.name.clone(),
            size: m.stat.size,
            sha256: m.sha256.clone(),
            lines: m.lines,
            mtime: m.stat.mtime(),
        })
        .collect();
    let dirs: Vec<String> = s.dirs.iter().map(|d| d.name.clone()).collect();
    let dir_mtimes: Vec<(String, String)> = s
        .dirs
        .iter()
        .map(|d| (d.name.clone(), d.stat.mtime()))
        .collect();
    let index = records::index_bytes(&files, &dirs);
    let index_sha = util::sha256_hex(&index);
    let arr = forms::arrangement(&ArrangementInput {
        settings: &settings,
        question_body_sha256: &question.body_sha256,
        material_index_sha256: &index_sha,
    });

    // Claim prep/<n> and write its records.
    let prep_root = audit
        .sub("prep")
        .map_err(|e| record_failed(audit, "open prep directory", &e, None))?;
    let mut n = 1u64;
    let pdir = loop {
        match prep_root.mkdir(&n.to_string()) {
            Ok(()) => {
                break prep_root.open_dir(&n.to_string()).map_err(|e| {
                    record_failed(audit, "open preparation directory", &e, Some(n))
                })?;
            }
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => n += 1,
            Err(e) => {
                return Err(record_failed(
                    audit,
                    "claim preparation directory",
                    &e,
                    None,
                ));
            }
        }
    };
    let arrangement_bytes = audit.record("arrangement", arr.body);
    let readable_bytes = arr.readable.into_bytes();
    let arrangement_sha = util::sha256_hex(&arrangement_bytes);
    let readable_sha = util::sha256_hex(&readable_bytes);
    let manifest_bytes = audit.record(
        "preparation",
        records::manifest_body(&ManifestParts {
            prep: n,
            folder: &folder_path,
            question: &question,
            settings: &settings,
            index: &index,
            files: &files,
            dir_mtimes: &dir_mtimes,
            arrangement: (&arrangement_sha, arrangement_bytes.len() as u64),
            readable: (&readable_sha, readable_bytes.len() as u64),
        }),
    );
    let manifest_sha = util::sha256_hex(&manifest_bytes);
    for (name, bytes) in [
        ("arrangement.json", &arrangement_bytes),
        ("arrangement.md", &readable_bytes),
        ("manifest.json", &manifest_bytes),
    ] {
        pdir.write_excl(name, bytes).map_err(|e| {
            record_failed(
                audit,
                &format!("write prep/{n}/{name} ({})", e.step.name()),
                &e.err,
                Some(n),
            )
        })?;
    }
    crate::fault!("prepare.before_prepared_link")
        .map_err(|e| record_failed(audit, "link prepared record", &e, Some(n)))?;

    let settings_j = settings.to_j();
    let published = log::publish(audit, "prepared", |st| {
        precondition(audit, st)?;
        Ok(J::obj()
            .with("prep", n)
            .with("manifest", format!("prep/{n}/manifest.json"))
            .with("manifest_sha256", manifest_sha.as_str())
            .with("arrangement_sha256", arrangement_sha.as_str())
            .with("readable_sha256", readable_sha.as_str())
            .with("settings", settings_j.clone())
            .with("question", question.summary_j())
            .with(
                "materials",
                J::obj()
                    .with("count", files.len())
                    .with("bytes", s.material_bytes()),
            ))
    });
    let p = match published {
        Ok(p) => p,
        Err(PubErr::Refused(f)) => return Err(f.retain(audit.abs(&format!("prep/{n}")))),
        Err(PubErr::Damaged(st)) => {
            return Err(log::damaged_fail(audit, &st).retain(audit.abs(&format!("prep/{n}"))));
        }
        Err(PubErr::NotPublished(c)) => {
            return Err(Fail::failed("record_failed", format!("The preparation records were written but the prepared record could not be published ({}: {}); no preparation was recorded.", c.operation, c.error))
                .cause(c)
                .retain(audit.abs(&format!("prep/{n}")))
                .next(Next::new(audit.argv(&["prepare", &audit.reference]), "Prepare again; this attempt's files stay as an unpublished candidate.")));
        }
        Err(PubErr::Uncertain { n: logn, cause }) => {
            let mut r = Fail::failed(
                "record_failed",
                format!("The prepared record was linked as log/{logn}.json, but Stewart could not confirm it is durable; status reports whether it stands."),
            )
            .cause(cause)
            .retain(audit.abs(&format!("prep/{n}")))
            .next(Next::new(audit.argv(&["status", &audit.reference]), "Status reports whether the preparation was recorded."))
            .into_reply(OP, eff("unknown"));
            r.data = None;
            return Ok(r);
        }
    };
    let handle = ids::handle(
        &audit.archive.store,
        &audit.id,
        "mp",
        &format!("mp{n}"),
        &[&p.sha256],
    );
    let data = J::obj()
        .with("prepared", handle.as_str())
        .with("question", question.summary_j())
        .with("settings", settings_j)
        .with(
            "materials",
            J::obj()
                .with("count", files.len())
                .with("bytes", s.material_bytes())
                .with("directories", json::strs(&dirs))
                .with("files", J::Arr(files.iter().map(|f| f.index_j()).collect())),
        )
        .with("reader", records::reader_j())
        .with("bounds", scan::bounds_j())
        .with(
            "arrangement",
            J::obj()
                .with("sha256", arrangement_sha.as_str())
                .with("readable", audit.abs(&format!("prep/{n}/arrangement.md")))
                .with("machine", audit.abs(&format!("prep/{n}/arrangement.json"))),
        );
    let mut reply = Reply::completed(OP, eff("recorded"), data);
    reply.next.push(Next::new(
        audit.argv(&["commission", &audit.reference, &handle, "--i-am-finished"]),
        "Accept exactly this selection. Leave the folder unchanged until commission returns.",
    ));
    Ok(reply)
}

fn record_failed(audit: &Audit, op: &str, e: &std::io::Error, prep: Option<u64>) -> Fail {
    let mut f = Fail::failed("record_failed", format!("Stewart could not write the preparation records ({op}: {}); no preparation was recorded.", util::describe(e)))
        .cause(Cause::io(op, e))
        .next(Next::new(audit.argv(&["prepare", &audit.reference]), "Prepare again once the archive is writable."));
    if let Some(n) = prep {
        f = f.retain(audit.abs(&format!("prep/{n}")));
    }
    f
}
