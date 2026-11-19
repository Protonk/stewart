//! `stewart prepare REF` (INTERFACE 5.3): scan the folder, check the
//! mechanical intake rules, pin the arrangement and return a manager
//! preparation handle. It accepts nothing and preserves no source bytes.

use super::{Place, check_overlap};
use crate::archive::{Audit, Fail};
use crate::forms::{self, ArrangementInput};
use crate::frontmatter;
use crate::fsx::Dir;
use crate::ids;
use crate::intake;
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

fn scan_fail(mut f: intake::Refusal) -> Fail {
    let remedy = match f.reason {
        "bound_exceeded" => Some("Reduce the named entry or selection to the reported bound."),
        "material_not_text" => Some("Supply UTF-8 text without NUL."),
        "guidance_empty" => {
            Some("Supply nonblank guidance text or remove the guidance selection and file.")
        }
        "name_invalid" => Some("Rename the entry to a permitted literal UTF-8 name."),
        "folder_incomplete" => Some("Supply the required entry in the submission folder."),
        "unexpected_root_entry" => {
            Some("Move the entry under materials/ to include it, or outside the submission.")
        }
        "unsupported_entry" => Some("Supply regular files and directories in the submission."),
        _ => None,
    };
    if let Some(remedy) = remedy {
        let mut d = frontmatter::Defect::new(f.reason, None, None, f.message.clone());
        if let Some(J::Str(name)) = f.data.get("entry") {
            d.source = Some(name.clone());
        }
        d.remedy = remedy.into();
        f.data.push("defects", J::Arr(vec![d.to_j()]));
    }
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

    scan::check_root(&folder, true)
        .map_err(scan_fail)
        .map_err(with_next)?;
    let qf = scan::read_question(&folder)
        .map_err(scan_fail)
        .map_err(with_next)?;
    let rule_failure = |defects: Vec<frontmatter::Defect>| {
        let message = defects
            .iter()
            .map(|d| d.message.as_str())
            .collect::<Vec<_>>()
            .join(" ");
        with_next(
            Fail::refused(defects[0].reason, format!("question.md: {message}")).data(
                J::obj().with(
                    "defects",
                    J::Arr(defects.iter().map(|d| d.to_j()).collect()),
                ),
            ),
        )
    };
    let (q, errors) = frontmatter::candidate(&qf.bytes).map_err(&rule_failure)?;
    if !errors.is_empty() && !q.material_roles.has_mappings() {
        return Err(rule_failure(errors));
    }
    #[allow(unused_mut)]
    let mut settings = q.settings.clone();

    let excluded = |dir: &Dir, what: &str| {
        dir.stat()
            .map(|stat| (stat.id(), what.to_owned()))
            .map_err(|e| {
                with_next(
                    Fail::failed(
                        "location_overlap",
                        format!("The {what} could not be identified before scanning."),
                    )
                    .cause(Cause::io("identify excluded directory", &e).at(dir.path.as_str())),
                )
            })
    };
    let mut exclude = Exclude {
        ids: vec![excluded(&audit.archive.root, "archive root")?],
    };
    // An invalid or absent destination is already a setting error. The material
    // inventory can still identify broken references before refusing the question.
    let _destination_guard = if !settings.destination.is_empty() {
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

        exclude.ids.push(excluded(&dest, "destination")?);
        Some(dest) // Keep the excluded directory identity held during the scan.
    } else {
        None
    };
    eprintln!(
        "stewart prepare: scanning {folder_path}/materials (bounds: {} files, {} bytes in total)",
        intake::FILES,
        intake::TOTAL_BYTES
    );
    let s = scan::scan(&folder, &exclude, settings.guidance.is_some())
        .map_err(scan_fail)
        .map_err(with_next)?;
    if s.question.bytes != qf.bytes {
        return Err(with_next(Fail::refused(
            "source_unreadable",
            "question.md changed while the folder was being prepared; finish editing, then prepare again.",
        )));
    }
    let advice = q
        .material_roles
        .assess(
            forms::family(&settings.family),
            s.files.iter().map(|file| file.name.as_str()),
            errors,
        )
        .map_err(rule_failure)?;
    #[cfg(feature = "claude-code")]
    crate::claude_code::profile::prepare(&mut settings)?;
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
    let guidance = s.guidance.as_ref().map(|g| records::GuidanceFile {
        size: g.bytes.len() as u64,
        sha256: util::sha256_hex(&g.bytes),
        mtime: g.stat.mtime(),
    });
    let arr = forms::arrangement(&ArrangementInput {
        material_roles: &q.material_roles,
        guidance: s
            .guidance
            .as_ref()
            .map(|g| std::str::from_utf8(&g.bytes).expect("validated guidance")),
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
            guidance: guidance.as_ref(),
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
            .with("guidance", records::guidance_summary(guidance.as_ref()))
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
        .with("guidance", records::guidance_summary(guidance.as_ref()))
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
        .with("bounds", intake::bounds_j())
        .with(
            "arrangement",
            J::obj()
                .with("sha256", arrangement_sha.as_str())
                .with("readable", audit.abs(&format!("prep/{n}/arrangement.md")))
                .with("machine", audit.abs(&format!("prep/{n}/arrangement.json"))),
        );
    let data = data.with("defects", J::Arr(advice.iter().map(|d| d.to_j()).collect()));
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
