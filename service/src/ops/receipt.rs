//! `stewart receipt REF [--verify]` and `stewart receipt REF --read ITEM`
//! (INTERFACE 5.5). Readback is local and read-only, works while a run is
//! active and after close, and never consults the live folder or the
//! currently installed forms.

use crate::archive::{Audit, Fail, RECORD_LIMIT};
use crate::fsx::ReadError;
use crate::json::{self, J};
use crate::log::{self, Body};
use crate::records::{self, Receipt};
use crate::reply::{Next, Reply};
use crate::util;

const OP: &str = "receipt";

/// One readable item of the fixed commission.
pub struct Item {
    pub id: String,
    pub size: u64,
    pub sha256: String,
    /// Archive-relative path of the file holding the bytes.
    pub file: String,
    /// For `question-body`: the byte offset within the question capture,
    /// whose own size and digest must also verify.
    pub within: Option<(u64, u64, String)>,
}

pub fn items(r: &Receipt) -> Vec<Item> {
    let q = &r.manifest.question;
    let mut v = vec![
        Item {
            id: "question-file".into(),
            size: q.file_bytes,
            sha256: q.file_sha256.clone(),
            file: r.question_capture.clone(),
            within: None,
        },
        Item {
            id: "question-body".into(),
            size: q.body_bytes,
            sha256: q.body_sha256.clone(),
            file: r.question_capture.clone(),
            within: Some((q.body_offset, q.file_bytes, q.file_sha256.clone())),
        },
        Item {
            id: "arrangement".into(),
            size: r.manifest.arrangement_size,
            sha256: r.manifest.arrangement_sha256.clone(),
            file: format!("prep/{}/arrangement.json", r.prep),
            within: None,
        },
        Item {
            id: "arrangement-readable".into(),
            size: r.manifest.readable_size,
            sha256: r.manifest.readable_sha256.clone(),
            file: format!("prep/{}/arrangement.md", r.prep),
            within: None,
        },
    ];
    for (f, cap) in &r.captures {
        v.push(Item {
            id: f.name.clone(),
            size: f.size,
            sha256: f.sha256.clone(),
            file: cap.clone(),
            within: None,
        });
    }
    v
}

#[derive(Debug, PartialEq)]
pub enum Check {
    Verified(Vec<u8>),
    Damaged(String),
    Missing,
    Unreadable(String),
    Unsupported(String),
}

impl Check {
    pub fn name(&self) -> &'static str {
        match self {
            Check::Verified(_) => "verified",
            Check::Damaged(_) => "damaged",
            Check::Missing => "missing",
            Check::Unreadable(_) => "unreadable",
            Check::Unsupported(_) => "unsupported",
        }
    }
    pub fn reason(&self) -> &'static str {
        match self {
            Check::Verified(_) => "verified",
            Check::Damaged(_) => "item_damaged",
            Check::Missing => "item_missing",
            Check::Unreadable(_) => "item_unreadable",
            Check::Unsupported(_) => "item_unsupported",
        }
    }
    pub fn detail(&self) -> String {
        match self {
            Check::Verified(_) => "size and SHA-256 match the record".into(),
            Check::Damaged(s) | Check::Unreadable(s) | Check::Unsupported(s) => s.clone(),
            Check::Missing => "the captured file is missing".into(),
        }
    }
}

/// Read one item's recorded bytes and verify them against the receipt.
pub fn check(audit: &Audit, it: &Item) -> Check {
    let (dir_rel, name) = match it.file.rsplit_once('/') {
        Some(x) => x,
        None => ("", it.file.as_str()),
    };
    let mut dir = match audit.dir.open_dir_bytes(b".", true) {
        Ok(d) => d,
        Err(e) => return Check::Unreadable(util::describe(&e)),
    };
    for comp in dir_rel.split('/').filter(|c| !c.is_empty()) {
        dir = match dir.open_dir(comp) {
            Ok(d) => d,
            Err(e) if e.raw_os_error() == Some(libc::ENOENT) => return Check::Missing,
            Err(e)
                if e.raw_os_error() == Some(libc::ENOTDIR)
                    || e.raw_os_error() == Some(libc::ELOOP) =>
            {
                return Check::Unsupported(format!("{dir_rel} is not a directory"));
            }
            Err(e) => return Check::Unreadable(util::describe(&e)),
        };
    }
    let (expect_size, expect_sha) = match &it.within {
        Some((_, file_size, file_sha)) => (*file_size, file_sha.clone()),
        None => (it.size, it.sha256.clone()),
    };
    let bytes = match dir.read_regular(name, expect_size.max(RECORD_LIMIT)) {
        Ok((b, _)) => b,
        Err(ReadError::Missing) => return Check::Missing,
        Err(ReadError::NotRegular(k)) => {
            return Check::Unsupported(format!("{} is a {}", it.file, k.name()));
        }
        Err(ReadError::TooLarge { size, .. }) => {
            return Check::Damaged(format!(
                "{} holds {size} bytes; {expect_size} were recorded",
                it.file
            ));
        }
        Err(e) => return Check::Unreadable(e.describe()),
    };
    if bytes.len() as u64 != expect_size || util::sha256_hex(&bytes) != expect_sha {
        return Check::Damaged(format!(
            "{} holds {} bytes with a different SHA-256 than recorded",
            it.file,
            bytes.len()
        ));
    }
    match &it.within {
        Some((offset, _, _)) => {
            let body = bytes.get(*offset as usize..).unwrap_or(&[]).to_vec();
            if body.len() as u64 != it.size || util::sha256_hex(&body) != it.sha256 {
                return Check::Damaged(
                    "the question body does not match its recorded digest".into(),
                );
            }
            Check::Verified(body)
        }
        None => Check::Verified(bytes),
    }
}

/// Locate the accepted commission and its receipt.
fn accepted(audit: &Audit) -> Result<(Receipt, String, String, String), Fail> {
    let state = log::read(audit);
    let Some(rec) = state.accepted() else {
        let f = if state.damaged() {
            Fail::refused(
                "not_accepted",
                format!("No accepted commission is among the readable log records, and the log is damaged ({}), so acceptance cannot be established.", state.bad_names()),
            )
            .data(J::obj().with("acceptance", "unknown").with("bad_records", state.bad_j()))
        } else {
            Fail::refused("not_accepted", "This reference has no accepted commission, so there is no receipt; an incomplete commission is never given one.")
                .data(J::obj().with("acceptance", "absent"))
        };
        return Err(f.next(Next::new(
            audit.argv(&["status", &audit.reference]),
            "See where the reference stands.",
        )));
    };
    let Body::Accepted {
        receipt,
        receipt_sha256,
        prepared,
        ..
    } = &rec.body
    else {
        unreachable!("accepted record")
    };
    let (r, _) = records::load_receipt(audit, receipt, receipt_sha256).map_err(|e| {
        Fail::refused(e.reason(), format!("Acceptance is recorded (log/{}.json), but its receipt {receipt} cannot be used: {}.", rec.n, e.describe()))
            .retain(audit.abs(receipt))
            .next(Next::new(audit.argv(&["status", &audit.reference]), "See the audit's state and diagnostics."))
    })?;
    Ok((r, rec.at.clone(), receipt_sha256.clone(), prepared.clone()))
}

pub fn run(reference: &str, verify: bool) -> Reply {
    let audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => return f.into_reply(OP, vec![]),
    };
    let (r, at, rsha, prepared) = match accepted(&audit) {
        Ok(x) => x,
        Err(f) => return f.into_reply(OP, vec![]),
    };
    let list = items(&r);
    let mut item_js = Vec::new();
    let mut all_known_good = true;
    let mut first_verified = false;
    for it in &list {
        let mut o = J::obj()
            .with("id", it.id.as_str())
            .with("size", it.size)
            .with("sha256", it.sha256.as_str())
            .with(
                "read",
                json::strs(&audit.argv(&["receipt", &audit.reference, "--read", &it.id])),
            );
        if verify {
            let c = if crate::sabotage!("whole_from_one_member") && first_verified {
                Check::Verified(Vec::new())
            } else {
                check(&audit, it)
            };
            if matches!(c, Check::Verified(_)) {
                first_verified = true;
            } else {
                all_known_good = false;
                o.push("problem", c.detail());
            }
            o.push("verification", c.name());
        }
        item_js.push(o);
    }
    let m = &r.manifest;
    let mut data = J::obj()
        .with("reference", audit.reference.as_str())
        .with("accepted_at", at.as_str())
        .with("prepared", prepared.as_str())
        .with("receipt_sha256", rsha.as_str())
        .with("question", m.question.summary_j())
        .with("settings", m.settings.to_j())
        .with("materials", m.materials_j())
        .with(
            "arrangement",
            J::obj()
                .with("sha256", m.arrangement_sha256.as_str())
                .with(
                    "readable",
                    audit.abs(&format!("prep/{}/arrangement.md", r.prep)),
                )
                .with(
                    "machine",
                    audit.abs(&format!("prep/{}/arrangement.json", r.prep)),
                ),
        )
        .with("checks", json::strs(&r.checks))
        .with(
            "declaration",
            J::obj().with("i_am_finished", r.i_am_finished),
        )
        .with("reader", records::reader_j())
        .with(
            "custody",
            J::obj()
                .with("archive", audit.archive.path.as_str())
                .with("location", audit.abs(&format!("intake/{}", r.attempt))),
        )
        .with(
            "run_line",
            json::strs(&audit.argv(&["run", &audit.reference])),
        )
        .with("run_needs", super::run_needs())
        .with("items", J::Arr(item_js));
    let verification = if verify {
        J::obj()
            .with("performed", true)
            .with(
                "scope",
                "each item separately; one item's result says nothing about another",
            )
            .with("all_items_verified", all_known_good)
    } else {
        J::obj().with("performed", false).with(
            "scope",
            "recorded facts only; the bytes were not re-verified (use --verify)",
        )
    };
    data.push("verification", verification);
    if let Some(why) = &audit.archive.moved {
        data.push("archive_notice", format!("This archive was moved or copied ({why}); it can be read, but it is not the archive the commission was accepted into."));
    }
    let mut reply = Reply::completed(OP, vec![], data);
    reply.next.push(Next::new(
        audit.argv(&["status", &audit.reference]),
        "See where the audit stands.",
    ));
    if !verify {
        reply.next.push(Next::new(
            audit.argv(&["receipt", &audit.reference, "--verify"]),
            "Read and hash every item now.",
        ));
    }
    reply
}

/// The stderr line of a raw readback.
pub struct ReadResult {
    pub bytes: Option<Vec<u8>>,
    pub line: J,
    pub exit: i32,
}

pub fn read(reference: &str, item: &str) -> ReadResult {
    let fail = |reason: &str, message: String, exit: i32| ReadResult {
        bytes: None,
        line: J::obj()
            .with("item", item)
            .with("verified", false)
            .with("diagnostic", reason)
            .with("message", message),
        exit,
    };
    let audit = match Audit::open(reference) {
        Ok(a) => a,
        Err(f) => {
            return fail(
                f.reason,
                f.message,
                if f.outcome == crate::reply::Outcome::Failed {
                    4
                } else {
                    3
                },
            );
        }
    };
    let (r, ..) = match accepted(&audit) {
        Ok(x) => x,
        Err(f) => return fail(f.reason, f.message, 3),
    };
    let list = items(&r);
    let Some(it) = list.iter().find(|i| i.id == item) else {
        let ids: Vec<&str> = list.iter().map(|i| i.id.as_str()).collect();
        let mut near: Vec<&str> = ids.clone();
        near.sort_by_key(|c| util::edit_distance(item, c));
        near.truncate(3);
        return ReadResult {
            bytes: None,
            line: J::obj()
                .with("item", item)
                .with("verified", false)
                .with("diagnostic", "item_unknown")
                .with("message", "No such receipt item; names are exact.")
                .with("closest", json::strs(&near)),
            exit: 3,
        };
    };
    if crate::sabotage!("readback_live_source") {
        // Sabotage control: read the live preparation folder instead of the capture.
        let live = if item.starts_with("materials/") {
            Some(item.to_string())
        } else if item == "question-file" {
            Some("question.md".into())
        } else {
            None
        };
        if let Some(rel) = live {
            if let Ok(b) = std::fs::read(format!("{}/{rel}", audit.refile.folder)) {
                return ReadResult {
                    line: J::obj()
                        .with("item", item)
                        .with("size", b.len())
                        .with("sha256", it.sha256.as_str())
                        .with("verified", true),
                    bytes: Some(b),
                    exit: 0,
                };
            }
        }
    }
    if crate::sabotage!("regenerate_arrangement")
        && (item == "arrangement" || item == "arrangement-readable")
    {
        if let Some(b) = sabotage_regenerate(&audit, item == "arrangement") {
            return ReadResult {
                line: J::obj()
                    .with("item", item)
                    .with("size", b.len())
                    .with("sha256", it.sha256.as_str())
                    .with("verified", true),
                bytes: Some(b),
                exit: 0,
            };
        }
    }
    match check(&audit, it) {
        Check::Verified(b) => ReadResult {
            line: J::obj()
                .with("item", item)
                .with("size", b.len())
                .with("sha256", util::sha256_hex(&b))
                .with("verified", true),
            bytes: Some(b),
            exit: 0,
        },
        c => {
            let exit = if matches!(c, Check::Unreadable(_)) {
                4
            } else {
                3
            };
            ReadResult {
                bytes: None,
                line: J::obj()
                    .with("item", item)
                    .with("verified", false)
                    .with("diagnostic", c.reason())
                    .with("message", c.detail())
                    .with("size", it.size)
                    .with("sha256", it.sha256.as_str()),
                exit,
            }
        }
    }
}

/// Regenerate the arrangement from the live folder and current forms (the
/// `regenerate_arrangement` sabotage control only).
fn sabotage_regenerate(audit: &Audit, machine: bool) -> Option<Vec<u8>> {
    let folder = crate::fsx::Dir::open_follow(&audit.refile.folder).ok()?;
    let (q, _) = folder
        .read_regular("question.md", crate::scan::QUESTION_BYTES)
        .ok()?;
    let parsed = crate::frontmatter::parse(&q).ok()?;
    let body = &q[parsed.body_offset..];
    let a = crate::forms::arrangement(&crate::forms::ArrangementInput {
        settings: &parsed.settings,
        question_body_sha256: &util::sha256_hex(body),
        material_index_sha256: &util::sha256_hex(b"regenerated"),
    });
    Some(if machine {
        audit.record("arrangement", a.body)
    } else {
        a.readable.into_bytes()
    })
}
