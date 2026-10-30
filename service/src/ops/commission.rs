//! `stewart commission REF HANDLE --i-am-finished` (INTERFACE 5.4).
//!
//! Acceptance copies the prepared selection into `intake/<attempt>/` through
//! descriptors, verifies each copy by reading it back, rescans the folder and
//! only then publishes `accepted`. Every attempt keeps its own captures and
//! records; a failed attempt is ended in the log before the reply, and a
//! planned attempt whose process is gone is reconciled by the next one.
//! These are cooperative interference checks, not a snapshot claim.

use crate::archive::{self, Audit, Fail};
use crate::fsx::{self, Dir, Kind, ReadError, Stat};
use crate::ids;
use crate::json::{self, J};
use crate::log::{self, Body, LogState, PubErr};
use crate::records::{self, CHECKS, MFile, Manifest, ReceiptParts};
use crate::reply::{Cause, Next, Reply};
use crate::scan;
use crate::util;
use std::collections::BTreeMap;

const OP: &str = "commission";

fn eff(acceptance: &'static str, attempt: &'static str) -> Vec<(&'static str, &'static str)> {
    vec![("acceptance", acceptance), ("attempt", attempt)]
}

pub fn run(reference: &str, handle: &str, affirmed: bool) -> Reply {
    let mut audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, eff("unknown", "none")),
    };
    let mut state = log::read(&audit);
    log::sabotage_unknown_as_absent(&mut state);
    let acceptance_now = if state.accepted().is_some() {
        "accepted"
    } else if state.damaged() {
        "unknown"
    } else {
        "absent"
    };
    if !affirmed && !crate::sabotage!("accept_without_affirmation") {
        return Fail::refused(
            "affirmation_missing",
            "commission needs --i-am-finished: your declaration that you have finished assembling the selection and will leave the folder unchanged until commission returns. Nothing was accepted.",
        )
        .next(Next::new(audit.argv(&["commission", &audit.reference, handle, "--i-am-finished"]), "Commission this preparation once you have finished editing."))
        .into_reply(OP, eff(acceptance_now, "none"));
    }
    if let Err(f) = audit.require_mutation() {
        return f.into_reply(OP, eff(acceptance_now, "none"));
    }
    let mut reply = commission(&audit, handle, affirmed, state);
    audit.diagnose(
        &mut reply,
        J::obj()
            .with("reference", audit.reference.as_str())
            .with("handle", handle),
    );
    reply
}

/// What the reply reports when acceptance is (or already was) recorded.
fn accepted_data(
    audit: &Audit,
    at: &str,
    receipt_sha: &str,
    already: bool,
    checks: &[String],
    declared: bool,
    count: usize,
    bytes: u64,
) -> J {
    J::obj()
        .with("reference", audit.reference.as_str())
        .with("accepted_at", at)
        .with("receipt_sha256", receipt_sha)
        .with("already_accepted", already)
        .with("checks", json::strs(checks))
        .with("declaration", J::obj().with("i_am_finished", declared))
        .with(
            "materials",
            J::obj().with("count", count).with("bytes", bytes),
        )
        .with(
            "run_line",
            json::strs(&audit.argv(&["run", &audit.reference])),
        )
        .with("run_needs", super::run_needs())
        .with(
            "receipt_line",
            json::strs(&audit.argv(&["receipt", &audit.reference])),
        )
}

fn accepted_next(audit: &Audit) -> Vec<Next> {
    vec![
        Next::new(
            audit.argv(&["run", &audit.reference]),
            "Start the audit; it needs what run_needs lists.",
        ),
        Next::new(
            audit.argv(&["close", &audit.reference]),
            "End the commission without running it.",
        ),
    ]
}

fn already_accepted(audit: &Audit, rec: &log::LogRec) -> Reply {
    let Body::Accepted {
        receipt,
        receipt_sha256,
        ..
    } = &rec.body
    else {
        unreachable!("accepted record")
    };
    let mut reply = match records::load_receipt(audit, receipt, receipt_sha256) {
        Ok((r, _)) => Reply::completed(
            OP,
            eff("accepted", "none"),
            accepted_data(
                audit,
                &rec.at,
                receipt_sha256,
                true,
                &r.checks,
                r.i_am_finished,
                r.captures.len(),
                r.captures.iter().map(|(f, _)| f.size).sum(),
            ),
        ),
        Err(e) => {
            // Acceptance is recorded; its receipt file cannot be shown now.
            let mut data = accepted_data(audit, &rec.at, receipt_sha256, true, &[], true, 0, 0);
            data.push(
                "receipt_problem",
                J::obj()
                    .with("reason", e.reason())
                    .with("message", e.describe()),
            );
            Reply::completed(OP, eff("accepted", "none"), data)
        }
    };
    reply.next = accepted_next(audit);
    reply
}

/// Validate a manager preparation handle against this audit's log.
pub fn resolve_handle<'a>(
    audit: &Audit,
    state: &'a LogState,
    handle: &str,
) -> Result<&'a log::LogRec, Fail> {
    let invalid = || {
        Fail::refused(
            "handle_invalid",
            format!("{handle:?} is not a manager preparation handle of this audit. Use the handle exactly as prepare returned it."),
        )
        .next(Next::new(audit.argv(&["prepare", &audit.reference]), "Prepare the folder to get a handle for its current selection."))
    };
    let (n, check) = ids::parse_mp(handle).ok_or_else(invalid)?;
    let rec = state.prepared(n).ok_or_else(invalid)?;
    if ids::check(
        &audit.archive.store,
        &audit.id,
        "mp",
        &format!("mp{n}"),
        &[&rec.sha256],
    ) != check
    {
        return Err(invalid());
    }
    Ok(rec)
}

struct Item {
    /// Public name: `question.md` or `materials/…`.
    name: String,
    /// The receipt item for the question file is `question-file`.
    capture: String,
    size: u64,
    sha256: String,
    mtime: String,
}

enum Ending {
    Changed {
        added: Vec<String>,
        removed: Vec<String>,
        changed: Vec<String>,
        unobserved: Vec<String>,
    },
    Unreadable {
        name: String,
        cause: Cause,
    },
    CaptureFailed {
        name: String,
        cause: Cause,
    },
    CaptureUnverified {
        name: String,
        detail: String,
    },
}

fn commission(audit: &Audit, handle: &str, declared: bool, state: LogState) -> Reply {
    if state.damaged() {
        return log::damaged_fail(audit, &state)
            .next(Next::new(audit.argv(&["status", &audit.reference]), "Status reports what the readable records establish, once you have restored your storage."))
            .into_reply(OP, eff("unknown", "none"));
    }
    let prepared = match resolve_handle(audit, &state, handle) {
        Ok(r) => r,
        Err(f) => {
            return f.into_reply(
                OP,
                eff(
                    if state.accepted().is_some() {
                        "accepted"
                    } else {
                        "absent"
                    },
                    "none",
                ),
            );
        }
    };
    if let Some(acc) = state.accepted() {
        if matches!(&acc.body, Body::Accepted { prepared, .. } if prepared == handle) {
            return already_accepted(audit, acc);
        }
        return Fail::refused(
            "reference_already_accepted",
            format!("This reference already accepted another preparation (log/{}.json); another commission needs its own reference from new.", acc.n),
        )
        .next(Next::new(audit.argv(&["receipt", &audit.reference]), "Read the accepted commission."))
        .into_reply(OP, eff("accepted", "none"));
    }
    if state.close_requested().is_some() {
        return Fail::refused(
            "reference_closed",
            "Close was requested for this reference, so it accepts no commission.",
        )
        .next(Next::new(
            audit.argv(&["status", &audit.reference]),
            "See how the reference ended.",
        ))
        .into_reply(OP, eff("absent", "none"));
    }
    let Body::Prepared {
        prep,
        manifest_sha256,
        arrangement_sha256,
        readable_sha256,
        ..
    } = &prepared.body
    else {
        unreachable!("prepared record")
    };
    let prep = *prep;
    // The pinned arrangement is verified before use: commission accepts the
    // arrangement prepare pinned, never a regenerated one.
    let pinned = records::load_manifest(audit, prep, manifest_sha256).and_then(|m| {
        if m.arrangement_sha256 != *arrangement_sha256 || m.readable_sha256 != *readable_sha256 {
            return Err(format!(
                "prep/{prep}/manifest.json names another arrangement than its prepared record"
            ));
        }
        verify_pinned(audit, prep, "arrangement.json", arrangement_sha256)?;
        verify_pinned(audit, prep, "arrangement.md", readable_sha256)?;
        Ok(m)
    });
    let manifest = match pinned {
        Ok(m) => m,
        Err(e) => {
            return Fail::failed("record_failed", format!("The preparation's pinned records cannot be used ({e}); nothing was captured. Prepare again."))
                .retain(audit.abs(&format!("prep/{prep}")))
                .next(Next::new(audit.argv(&["prepare", &audit.reference]), "Prepare the folder again and commission the new handle."))
                .into_reply(OP, eff("absent", "none"));
        }
    };

    // Step 2: the active lock, reconciliation and the planned attempt.
    let _lock = match audit.try_lock() {
        Ok(Some(f)) => f,
        Ok(None) => {
            return Fail::refused(
                "intake_in_progress",
                "Another commission holds this audit's active lock; its intake is in progress.",
            )
            .next(Next::new(
                audit.argv(&["status", &audit.reference]),
                "See whether that intake ended.",
            ))
            .next(Next::new(
                audit.argv(&["close", &audit.reference]),
                "End this reference; close waits for the intake to finish.",
            ))
            .into_reply(OP, eff("absent", "none"));
        }
        Err(e) => {
            return Fail::failed(
                "record_failed",
                format!(
                    "The active lock {} cannot be taken: {}.",
                    audit.abs(archive::LOCK_FILE),
                    util::describe(&e)
                ),
            )
            .cause(Cause::io("lock active.lock", &e).at(audit.abs(archive::LOCK_FILE)))
            .into_reply(OP, eff("absent", "none"));
        }
    };
    // Reconcile under the lock from a fresh read: an intake planned without
    // an outcome now belongs to a process that is gone.
    let mut notes = Vec::new();
    let fresh = log::read(audit);
    if let Some(gone) = fresh.open_intake() {
        match end_intake(
            audit,
            gone,
            "process_gone",
            "The intake's process ended without recording an outcome; reconciled by the next commission under a free lock.",
            None,
            None,
        ) {
            Ok(()) => notes.push(format!(
                "intake {gone} ended without an outcome; recorded as process_gone"
            )),
            Err(e) => {
                return Fail::failed("record_failed", format!("The earlier intake {gone} could not be reconciled ({e}); nothing new was captured."))
                    .next(Next::new(audit.argv(&["status", &audit.reference]), "See the audit's state."))
                    .into_reply(OP, eff("absent", "none"));
            }
        }
    }
    let intake_root = match audit.sub("intake") {
        Ok(d) => d,
        Err(e) => return capture_dir_failed(audit, &e),
    };
    let mut attempt = 1u64;
    loop {
        match intake_root.mkdir(&attempt.to_string()) {
            Ok(()) => break,
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => attempt += 1,
            Err(e) => return capture_dir_failed(audit, &e),
        }
    }
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("remove_partial_on_retry") && attempt > 1 {
        if let Ok(d) = intake_root.open_dir(&(attempt - 1).to_string()) {
            d.sabotage_remove_files();
        }
    }
    let idir = match intake_root.open_dir(&attempt.to_string()) {
        Ok(d) => d,
        Err(e) => return capture_dir_failed(audit, &e),
    };
    let attempt_path = audit.abs(&format!("intake/{attempt}"));

    let mut items = vec![Item {
        name: "question.md".into(),
        capture: "q.bin".into(),
        size: manifest.question.file_bytes,
        sha256: manifest.question.file_sha256.clone(),
        mtime: manifest.question.mtime.clone(),
    }];
    for (i, f) in manifest.files.iter().enumerate() {
        items.push(Item {
            name: f.name.clone(),
            capture: format!("m{:04}.bin", i + 1),
            size: f.size,
            sha256: f.sha256.clone(),
            mtime: f.mtime.clone(),
        });
    }
    let captures_j = J::Arr(
        items
            .iter()
            .map(|it| {
                J::obj()
                    .with(
                        "item",
                        if it.capture == "q.bin" {
                            "question-file"
                        } else {
                            it.name.as_str()
                        },
                    )
                    .with("file", it.capture.as_str())
            })
            .collect(),
    );
    let planned = log::publish(audit, "intake_planned", |st| {
        if st.prepared(prep).is_none() {
            return Err(Fail::refused(
                "handle_invalid",
                "The preparation is no longer in the log.",
            ));
        }
        if st.accepted().is_some() {
            return Err(Fail::refused(
                "reference_already_accepted",
                "Another commission was accepted meanwhile.",
            ));
        }
        if st.close_requested().is_some() {
            return Err(Fail::refused(
                "reference_closed",
                "Close was requested for this reference, so it accepts no commission.",
            ));
        }
        if let Some(open) = st.open_intake() {
            return Err(Fail::refused(
                "intake_in_progress",
                format!("Intake {open} has no outcome yet."),
            ));
        }
        Ok(J::obj()
            .with("attempt", attempt)
            .with("prepared", handle)
            .with("prep", prep)
            .with("declaration", J::obj().with("i_am_finished", declared))
            .with("captures", captures_j.clone())
            .with("observations", archive::observations()))
    });
    match planned {
        Ok(_) => {}
        Err(PubErr::Refused(f)) => {
            let acc = if f.reason == "reference_already_accepted" {
                "accepted"
            } else {
                "absent"
            };
            return f
                .retain(attempt_path)
                .next(Next::new(
                    audit.argv(&["status", &audit.reference]),
                    "See the audit's state.",
                ))
                .into_reply(OP, eff(acc, "none"));
        }
        Err(PubErr::Damaged(st)) => {
            return log::damaged_fail(audit, &st).into_reply(OP, eff("unknown", "none"));
        }
        Err(PubErr::NotPublished(c)) => {
            return Fail::failed(
                "record_failed",
                format!(
                    "The intake could not be planned in the log ({}: {}); nothing was captured.",
                    c.operation, c.error
                ),
            )
            .cause(c)
            .retain(attempt_path)
            .next(Next::new(
                audit.argv(&["commission", &audit.reference, handle, "--i-am-finished"]),
                "Commission again once the archive is writable.",
            ))
            .into_reply(OP, eff("absent", "none"));
        }
        Err(PubErr::Uncertain { cause, .. }) => {
            return Fail::failed("record_failed", "The intake plan was linked but could not be confirmed durable; nothing was captured.")
                .cause(cause)
                .retain(attempt_path)
                .next(Next::new(audit.argv(&["status", &audit.reference]), "Status reports the recorded state."))
                .into_reply(OP, eff("absent", "unknown"));
        }
    }

    // Steps 3–4: copy, verify, rescan.
    let folder = match Dir::open_follow(&audit.refile.folder) {
        Ok(d) => d,
        Err(e) => {
            return end_with(
                audit,
                handle,
                attempt,
                Ending::Unreadable {
                    name: audit.refile.folder.clone(),
                    cause: Cause::io("open folder", &e).at(audit.refile.folder.as_str()),
                },
            );
        }
    };
    eprintln!(
        "stewart commission: capturing {} files ({} bytes) into {attempt_path}",
        items.len(),
        manifest.question.file_bytes + manifest.material_bytes()
    );
    let skip = crate::sabotage!("accept_changed_source");
    let mut observed: BTreeMap<String, Stat> = BTreeMap::new();
    for (k, it) in items.iter().enumerate() {
        match copy_one(&folder, &idir, it, k + 1, skip) {
            Ok(st) => {
                observed.insert(it.name.clone(), st);
            }
            Err(ending) => return end_with(audit, handle, attempt, ending),
        }
    }
    let mut checks: Vec<&str> = vec![CHECKS[1]];
    if !skip {
        checks = CHECKS.to_vec();
        if let Some(ending) = final_scan(&folder, &manifest, &observed) {
            return end_with(audit, handle, attempt, ending);
        }
    }

    // Step 5: the receipt, then acceptance.
    let captures: Vec<(MFile, String)> = manifest
        .files
        .iter()
        .zip(items.iter().skip(1))
        .map(|(f, it)| (f.clone(), format!("intake/{attempt}/{}", it.capture)))
        .collect();
    let rbody = records::receipt_body(&ReceiptParts {
        audit,
        attempt,
        prepared: handle,
        manifest_sha256,
        m: &manifest,
        question_capture: &format!("intake/{attempt}/q.bin"),
        captures: &captures,
        checks: &checks,
        i_am_finished: declared,
    });
    let rbytes = audit.record("receipt", rbody);
    let rsha = util::sha256_hex(&rbytes);
    let wrote = crate::fault!("commission.receipt_write")
        .map_err(|e| Cause::io("write receipt", &e))
        .and_then(|_| {
            idir.write_excl("receipt.json", &rbytes)
                .map_err(|e| Cause::io(format!("write receipt ({})", e.step.name()), &e.err))
        })
        .and_then(|_| {
            crate::fault!("commission.before_accepted_link")
                .map_err(|e| Cause::io("publish accepted", &e))
        });
    if let Err(c) = wrote {
        return receipt_failed(
            audit,
            handle,
            attempt,
            c.at(audit.abs(&format!("intake/{attempt}/receipt.json"))),
        );
    }
    let receipt_rel = format!("intake/{attempt}/receipt.json");
    let published = log::publish(audit, "accepted", |st| {
        if st.close_requested().is_some() {
            return Err(Fail::refused(
                "reference_closed",
                "Close was requested before acceptance was recorded.",
            ));
        }
        if st.accepted().is_some() {
            return Err(Fail::refused(
                "reference_already_accepted",
                "Another commission was accepted meanwhile.",
            ));
        }
        if st
            .intakes()
            .iter()
            .any(|i| i.attempt == attempt && i.ended.is_some())
        {
            return Err(Fail::refused(
                "record_failed",
                format!("Intake {attempt} already has an outcome."),
            ));
        }
        Ok(J::obj()
            .with("attempt", attempt)
            .with("prepared", handle)
            .with("prep", prep)
            .with("receipt", receipt_rel.as_str())
            .with("receipt_sha256", rsha.as_str()))
    });
    let p = match published {
        Ok(p) => p,
        Err(PubErr::Refused(f)) if f.reason == "reference_closed" => {
            let ended = end_intake(
                audit,
                attempt,
                "closed",
                "Close was requested before this intake's acceptance was recorded; it was not accepted.",
                None,
                None,
            );
            let mut r = Fail::refused("reference_closed", "Close was requested before acceptance could be recorded, so this selection was not accepted. Its captures stay recorded.")
                .retain(audit.abs(&format!("intake/{attempt}")))
                .next(Next::new(audit.argv(&["status", &audit.reference]), "See how the reference ended."))
                .into_reply(OP, eff("absent", "partial"));
            if let Err(e) = ended {
                r.message = Some(format!(
                    "{} The intake's ending could not be recorded ({e}); the next close reconciles it.",
                    r.message.unwrap_or_default()
                ));
            }
            return r;
        }
        Err(PubErr::Refused(f)) => {
            return f
                .retain(attempt_path)
                .into_reply(OP, eff("unknown", "partial"));
        }
        Err(PubErr::Damaged(st)) => {
            return log::damaged_fail(audit, &st)
                .retain(attempt_path)
                .into_reply(OP, eff("unknown", "partial"));
        }
        Err(PubErr::NotPublished(c)) => return receipt_failed(audit, handle, attempt, c),
        Err(PubErr::Uncertain { cause, .. }) => {
            return Fail::failed("acceptance_record_uncertain", "Stewart could not confirm that the acceptance record was published.")
                .cause(cause)
                .retain(attempt_path)
                .next(Next::new(audit.argv(&["status", &audit.reference]), "Status reports whether acceptance was recorded."))
                .next(Next::new(
                    audit.argv(&["commission", &audit.reference, handle, "--i-am-finished"]),
                    "Repeating with the same handle returns the recorded acceptance; it never captures twice.",
                ))
                .into_reply(OP, eff("unknown", "recorded"));
        }
    };
    let _ = crate::fault!("commission.after_accepted_link");
    let checks_owned: Vec<String> = checks.iter().map(|s| s.to_string()).collect();
    let mut data = accepted_data(
        audit,
        &p.at,
        &rsha,
        false,
        &checks_owned,
        declared,
        manifest.files.len(),
        manifest.material_bytes(),
    );
    if !notes.is_empty() {
        data.push("reconciled", json::strs(&notes));
    }
    let mut reply = Reply::completed(OP, eff("accepted", "recorded"), data);
    reply.next = accepted_next(audit);
    reply
}

/// Check one pinned arrangement file against the digest its record binds.
fn verify_pinned(audit: &Audit, prep: u64, name: &str, want: &str) -> Result<(), String> {
    let dir = audit
        .dir
        .open_dir("prep")
        .and_then(|d| d.open_dir(&prep.to_string()))
        .map_err(|e| format!("prep/{prep} cannot be opened: {}", util::describe(&e)))?;
    let (bytes, _) = dir
        .read_regular(name, archive::RECORD_LIMIT)
        .map_err(|e| format!("prep/{prep}/{name}: {}", e.describe()))?;
    if util::sha256_hex(&bytes) != want {
        return Err(format!(
            "prep/{prep}/{name} no longer matches the digest its prepared record binds"
        ));
    }
    Ok(())
}

fn capture_dir_failed(audit: &Audit, e: &std::io::Error) -> Reply {
    Fail::failed(
        "capture_failed",
        format!(
            "The intake directory could not be created: {}; nothing was captured.",
            util::describe(e)
        ),
    )
    .cause(Cause::io("claim intake directory", e).at(audit.abs("intake")))
    .into_reply(OP, eff("absent", "none"))
}

/// Open a source by its public name through descriptors, without following links.
fn open_source(folder: &Dir, name: &str) -> Result<(Dir, String), std::io::Error> {
    let nofollow = !crate::sabotage!("follow_symlinks");
    let parts: Vec<&str> = name.split('/').collect();
    let (leaf, dirs) = parts.split_last().expect("non-empty name");
    let mut cur = folder.open_dir_bytes(b".", true)?;
    for d in dirs {
        cur = cur.open_dir_bytes(d.as_bytes(), nofollow)?;
    }
    Ok((cur, leaf.to_string()))
}

fn changed(name: &str) -> Ending {
    Ending::Changed {
        added: vec![],
        removed: vec![],
        changed: vec![name.to_string()],
        unobserved: vec![],
    }
}

/// Copy one source into the attempt: check, read, write exclusively, verify.
fn copy_one(folder: &Dir, idir: &Dir, it: &Item, k: usize, skip: bool) -> Result<Stat, Ending> {
    let nofollow = !crate::sabotage!("follow_symlinks");
    let (parent, leaf) = match open_source(folder, &it.name) {
        Ok(x) => x,
        Err(e) if e.raw_os_error() == Some(libc::ENOENT) => {
            return Err(Ending::Changed {
                added: vec![],
                removed: vec![it.name.clone()],
                changed: vec![],
                unobserved: vec![],
            });
        }
        Err(e) => {
            return Err(Ending::Unreadable {
                name: it.name.clone(),
                cause: Cause::io("open source directory", &e),
            });
        }
    };
    let st0 = match parent.stat_at_bytes(leaf.as_bytes(), nofollow) {
        Ok(s) => s,
        Err(e) if e.raw_os_error() == Some(libc::ENOENT) => {
            return Err(Ending::Changed {
                added: vec![],
                removed: vec![it.name.clone()],
                changed: vec![],
                unobserved: vec![],
            });
        }
        Err(e) => {
            return Err(Ending::Unreadable {
                name: it.name.clone(),
                cause: Cause::io("examine source", &e),
            });
        }
    };
    if st0.kind != Kind::File || (!skip && (st0.size != it.size || st0.mtime() != it.mtime)) {
        return Err(changed(&it.name));
    }
    let (f, before) = match parent.open_regular_bytes(leaf.as_bytes(), nofollow) {
        Ok(x) => x,
        Err(ReadError::Io(e)) => {
            return Err(Ending::Unreadable {
                name: it.name.clone(),
                cause: Cause::io("open source", &e),
            });
        }
        Err(ReadError::Missing) => {
            return Err(Ending::Changed {
                added: vec![],
                removed: vec![it.name.clone()],
                changed: vec![],
                unobserved: vec![],
            });
        }
        Err(_) => return Err(changed(&it.name)),
    };
    if before.id() != st0.id() {
        return Err(changed(&it.name));
    }
    // The question file answers to both `question` (its public source name)
    // and `question.md` at this failure point.
    #[cfg(feature = "fault-injection")]
    {
        let public = if it.name == "question.md" {
            "question"
        } else {
            it.name.as_str()
        };
        let injected = crate::fault!("commission.source_read", public).and_then(|_| {
            if it.name == "question.md" {
                crate::fault!("commission.source_read", "question.md")
            } else {
                Ok(())
            }
        });
        if let Err(e) = injected {
            return Err(Ending::Unreadable {
                name: it.name.clone(),
                cause: Cause::io("read source", &e),
            });
        }
    }
    let limit = if skip {
        scan::FILE_BYTES.max(scan::QUESTION_BYTES)
    } else {
        it.size
    };
    let bytes = match fsx::read_bounded(f, &before, limit) {
        Ok(b) => b,
        Err(ReadError::Io(e)) => {
            return Err(Ending::Unreadable {
                name: it.name.clone(),
                cause: Cause::io("read source", &e),
            });
        }
        Err(_) => return Err(changed(&it.name)),
    };
    if !skip && util::sha256_hex(&bytes) != it.sha256 {
        return Err(changed(&it.name));
    }
    let capture: Vec<u8> = if crate::sabotage!("normalize_newlines") {
        normalize(&bytes)
    } else {
        bytes
    };
    let wrote = crate::fault!("commission.capture_write")
        .map_err(|e| Cause::io("write capture", &e))
        .and_then(|_| {
            idir.write_excl(&it.capture, &capture)
                .map_err(|e| Cause::io(format!("write capture ({})", e.step.name()), &e.err))
        });
    if let Err(c) = wrote {
        return Err(Ending::CaptureFailed {
            name: it.name.clone(),
            cause: c.at(format!("{}/{}", idir.path, it.capture)),
        });
    }
    #[cfg(feature = "fault-injection")]
    if crate::fault_corrupt!("commission.capture_corrupt") {
        let _ = idir.corrupt_file(&it.capture);
    }
    let _ = crate::fault!("commission.after_capture", &k.to_string());
    let _ = k;
    let want = util::sha256_hex(&capture);
    match idir.read_regular(&it.capture, capture.len() as u64 + 1) {
        Ok((back, _)) if util::sha256_hex(&back) == want => Ok(before),
        Ok(_) => Err(Ending::CaptureUnverified {
            name: it.name.clone(),
            detail: format!("{} read back with a different SHA-256", it.capture),
        }),
        Err(e) => Err(Ending::CaptureUnverified {
            name: it.name.clone(),
            detail: format!("{} could not be read back: {}", it.capture, e.describe()),
        }),
    }
}

/// CRLF to LF (the `normalize_newlines` sabotage control only).
fn normalize(b: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'\r' && b.get(i + 1) == Some(&b'\n') {
            i += 1;
            continue;
        }
        out.push(b[i]);
        i += 1;
    }
    out
}

/// Step 4: membership, and each file's device, inode, size and mtime, must
/// equal what the copy saw.
fn final_scan(folder: &Dir, m: &Manifest, observed: &BTreeMap<String, Stat>) -> Option<Ending> {
    let r = scan::rescan(folder);
    let mut expected: BTreeMap<String, Option<&Stat>> = BTreeMap::new();
    for (name, st) in observed {
        expected.insert(name.clone(), Some(st));
    }
    for d in &m.dirs {
        expected.insert(d.clone(), None);
    }
    let mut added = Vec::new();
    let mut removed = Vec::new();
    let mut changed = Vec::new();
    for (name, st) in &r.entries {
        match expected.get(name) {
            None => added.push(name.clone()),
            Some(Some(seen)) => {
                if st.kind != Kind::File
                    || st.id() != seen.id()
                    || st.size != seen.size
                    || st.mtime() != seen.mtime()
                {
                    changed.push(name.clone());
                }
            }
            Some(None) => {
                if st.kind != Kind::Dir {
                    changed.push(name.clone());
                }
            }
        }
    }
    for name in expected.keys() {
        if !r.entries.contains_key(name) {
            removed.push(name.clone());
        }
    }
    if added.is_empty() && removed.is_empty() && changed.is_empty() && r.incomplete.is_empty() {
        None
    } else {
        Some(Ending::Changed {
            added,
            removed,
            changed,
            unobserved: r.incomplete,
        })
    }
}

/// Publish `intake_ended` for an attempt that has no outcome.
fn end_intake(
    audit: &Audit,
    attempt: u64,
    outcome: &'static str,
    message: &str,
    cause: Option<&Cause>,
    changes: Option<J>,
) -> Result<(), String> {
    let by = "commission";
    log::publish(audit, "intake_ended", |st| {
        let has = st
            .intakes()
            .iter()
            .any(|i| i.attempt == attempt && i.ended.is_none());
        if !has {
            return Err(Fail::refused(
                "record_failed",
                format!("intake {attempt} has no open plan"),
            ));
        }
        Ok(J::obj()
            .with("attempt", attempt)
            .with("outcome", outcome)
            .with("recorded_by", by)
            .with("message", message)
            .with("cause", cause.map(|c| c.to_j()))
            .with("changes", changes.clone()))
    })
    .map(|_| ())
    .map_err(|e| e.describe())
}

fn end_with(audit: &Audit, handle: &str, attempt: u64, ending: Ending) -> Reply {
    let retained = audit.abs(&format!("intake/{attempt}"));
    let again = Next::new(
        audit.argv(&["commission", &audit.reference, handle, "--i-am-finished"]),
        "Commission this preparation again once the problem is corrected.",
    );
    let prepare = Next::new(
        audit.argv(&["prepare", &audit.reference]),
        "Prepare the current folder, then commission the new handle.",
    );
    let close = Next::new(
        audit.argv(&["close", &audit.reference]),
        "End this reference without commissioning.",
    );
    let (outcome, mut fail, changes, cause) = match ending {
        Ending::Changed {
            added,
            removed,
            changed,
            unobserved,
        } => {
            let mut parts = Vec::new();
            if !changed.is_empty() {
                parts.push(format!("{} changed", changed.join(", ")));
            }
            if !added.is_empty() {
                parts.push(format!("{} appeared", added.join(", ")));
            }
            if !removed.is_empty() {
                parts.push(format!("{} disappeared", removed.join(", ")));
            }
            if !unobserved.is_empty() {
                parts.push(format!(
                    "the final scan could not observe everything ({})",
                    unobserved.join("; ")
                ));
            }
            let changes = J::obj()
                .with("added", json::strs(&added))
                .with("removed", json::strs(&removed))
                .with("changed", json::strs(&changed));
            let mut data = changes.clone();
            if !unobserved.is_empty() {
                data.push("unobserved", json::strs(&unobserved));
            }
            let f = Fail::refused(
                "selection_changed",
                format!(
                    "{} after preparation, so this selection was not accepted.",
                    parts.join("; ")
                ),
            )
            .data(data)
            .next(prepare)
            .next(close);
            ("selection_changed", f, Some(changes), None)
        }
        Ending::Unreadable { name, cause } => {
            let f = Fail::refused(
                "source_unreadable",
                format!(
                    "{name} could not be opened or read ({}), so this selection was not accepted.",
                    cause.error
                ),
            )
            .cause(cause.clone())
            .data(
                J::obj()
                    .with("entry", name.as_str())
                    .with("error", cause.error.as_str()),
            )
            .next(again)
            .next(prepare)
            .next(close);
            ("source_unreadable", f, None, Some(cause))
        }
        Ending::CaptureFailed { name, cause } => {
            let f = Fail::failed(
                "capture_failed",
                format!(
                    "The capture of {name} could not be written ({}); nothing was accepted.",
                    cause.error
                ),
            )
            .cause(cause.clone())
            .data(J::obj().with("entry", name.as_str()))
            .next(again)
            .next(close);
            ("capture_failed", f, None, Some(cause))
        }
        Ending::CaptureUnverified { name, detail } => {
            let cause = Cause::new("verify capture", detail.clone());
            let f = Fail::failed(
                "capture_unverified",
                format!("The capture of {name} did not verify ({detail}); nothing was accepted."),
            )
            .cause(cause.clone())
            .data(J::obj().with("entry", name.as_str()))
            .next(again)
            .next(close);
            ("capture_unverified", f, None, Some(cause))
        }
    };
    fail = fail.retain(retained);
    let msg = fail.message.clone();
    let ended = end_intake(audit, attempt, outcome, &msg, cause.as_ref(), changes);
    let mut r = fail.into_reply(OP, eff("absent", "partial"));
    if let Err(e) = ended {
        r.message = Some(format!(
            "{} The intake's ending could not be recorded ({e}); the next commission or close reconciles it.",
            r.message.unwrap_or_default()
        ));
    }
    r
}

fn receipt_failed(audit: &Audit, handle: &str, attempt: u64, cause: Cause) -> Reply {
    let msg = format!(
        "The acceptance receipt could not be recorded ({}: {}); nothing was accepted.",
        cause.operation, cause.error
    );
    let ended = end_intake(
        audit,
        attempt,
        "receipt_record_failed",
        &msg,
        Some(&cause),
        None,
    );
    let mut r = Fail::failed("receipt_record_failed", msg)
        .cause(cause)
        .retain(audit.abs(&format!("intake/{attempt}")))
        .next(Next::new(
            audit.argv(&["commission", &audit.reference, handle, "--i-am-finished"]),
            "Commission again once the archive is writable; a new attempt captures afresh.",
        ))
        .next(Next::new(
            audit.argv(&["close", &audit.reference]),
            "End this reference without commissioning.",
        ))
        .into_reply(OP, eff("absent", "partial"));
    if let Err(e) = ended {
        r.message = Some(format!(
            "{} The intake's ending could not be recorded ({e}); the next commission or close reconciles it.",
            r.message.unwrap_or_default()
        ));
    }
    r
}
