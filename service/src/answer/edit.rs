//! Recording and editing (INTERFACE 7.3, 7.4): `record_<kind>`,
//! `record_artifact`, `replace` and `delete`, their citations and bounds.
//!
//! Each add and replace stores its bytes in a new payload file before its
//! `entry` record is published; a delete writes no payload, and no payload
//! is ever rewritten or removed. The `entry` record is published with the
//! log's single rule: read to the end, check the preconditions, link the next
//! number, and on a taken number re-read and re-check. A `close_requested`
//! or `seal` that takes the slot first ends authoring, and the edit is
//! refused `authoring_ended`.

use super::common::{
    Ctx, Item, Named, Out, authoring_ended, label_ok, lines, refused, resolve, selection,
};
use super::{
    AMBIGUOUS_OCCURRENCES, CAPPED_EDIT_BYTES, CITATIONS_PER_ENTRY, ENTRIES, ENTRY_BYTES, End,
    LABEL_CHARS, RETAINED_CAP_BYTES, RETAINED_RESERVE_BYTES, SELECTION_BYTES, b64, input,
};
use crate::archive::Fail;
use crate::bodies::{ARTIFACT_TOOL, Action, Citation, EntryRec, Located, Payload, Target, Version};
use crate::json::{self, J, Json, Obj};
use crate::log::{self, LogState, PubErr, VersionState};
use crate::names;
use crate::reply::ToolNext;
use crate::util;
use std::collections::HashMap;

fn citation_invalid(index: usize, defect: impl Into<String>) -> Fail {
    let defect = defect.into();
    refused(
        "citation_invalid",
        format!("Citation {index} is not valid: {defect}. Nothing was recorded."),
    )
    .data(J::obj().with("index", index).with("defect", defect))
}

/// Decode and check the citations of one call (7.3). A defective citation
/// refuses the whole call.
pub fn citations(ctx: &Ctx, items: Option<&[Json]>) -> Result<Vec<Citation>, Fail> {
    let Some(items) = items else {
        return Ok(Vec::new());
    };
    if items.len() > CITATIONS_PER_ENTRY {
        return Err(citation_invalid(
            CITATIONS_PER_ENTRY,
            format!(
                "an entry takes at most {CITATIONS_PER_ENTRY} citations; {} were given",
                items.len()
            ),
        ));
    }
    let mut out = Vec::new();
    for (i, v) in items.iter().enumerate() {
        let ptr = format!("/citations/{i}");
        let o: Obj = v.obj(&ptr).map_err(|e| input::invalid(&e, None))?;
        input::keys(&o, &["source", "start", "end", "quote"], &["source"])?;
        let source = input::req_str(&o, "source")?;
        let start = input::opt_u64(&o, "start")?;
        let end = input::opt_u64(&o, "end")?;
        let quote = input::opt_str(&o, "quote")?;
        let Some(src) = ctx.world.source(source) else {
            let h = super::common::hints(ctx.world, source);
            return Err(citation_invalid(
                i,
                format!(
                    "{source:?} is not a citable source; cite question or materials/<name> (closest: {})",
                    h.join(", ")
                ),
            ));
        };
        let bytes = src.bytes().map_err(|e| {
            Fail::failed(
                "source_unreadable",
                format!(
                    "{source} could not be read from its capture: {}.",
                    util::describe(&e)
                ),
            )
        })?;
        let (s, e, located) = match (start, end, quote) {
            (Some(s), Some(e), q) => {
                let (su, eu) = (s as usize, e as usize);
                if s >= e {
                    return Err(citation_invalid(
                        i,
                        format!("start {s} is not less than end {e}"),
                    ));
                }
                if e > bytes.len() as u64 {
                    return Err(citation_invalid(
                        i,
                        format!(
                            "end {e} is past the end of {source} ({} bytes)",
                            bytes.len()
                        ),
                    ));
                }
                if !super::common::boundary(&bytes, su) || !super::common::boundary(&bytes, eu) {
                    return Err(citation_invalid(
                        i,
                        format!("[{s}, {e}) does not begin and end on UTF-8 character boundaries"),
                    ));
                }
                if let Some(q) = q {
                    if q.as_bytes() != &bytes[su..eu] {
                        return Err(citation_invalid(
                            i,
                            format!("the quote does not equal the bytes of {source} at [{s}, {e})"),
                        ));
                    }
                }
                (su, eu, false)
            }
            (None, None, Some(q)) if !q.is_empty() => {
                let qb = q.as_bytes();
                let found: Vec<usize> = bytes
                    .windows(qb.len())
                    .enumerate()
                    .filter(|(_, w)| *w == qb)
                    .map(|(k, _)| k)
                    .collect();
                match found.len() {
                    0 => {
                        return Err(refused(
                            "quote_not_found",
                            format!("Citation {i}: the quote does not occur in {source}. Matching is exact; nothing was recorded."),
                        )
                        .data(J::obj().with("index", i).with("source", source)));
                    }
                    1 => (found[0], found[0] + qb.len(), true),
                    n => {
                        let occ: Vec<J> = found
                            .iter()
                            .take(AMBIGUOUS_OCCURRENCES)
                            .map(|&k| {
                                J::obj()
                                    .with("source", source)
                                    .with("start", k)
                                    .with("end", k + qb.len())
                            })
                            .collect();
                        return Err(refused(
                            "quote_ambiguous",
                            format!("Citation {i}: the quote occurs {n} times in {source}. Cite one occurrence by its range; nothing was recorded."),
                        )
                        .data(
                            J::obj()
                                .with("index", i)
                                .with("source", source)
                                .with("count", n)
                                .with("occurrences", J::Arr(occ)),
                        ));
                    }
                }
            }
            _ => {
                return Err(citation_invalid(
                    i,
                    "a citation is {source, start, end, quote?} or {source, quote} with a non-empty quote",
                ));
            }
        };
        out.push(Citation {
            source: source.to_string(),
            start,
            end,
            quote: quote.map(str::to_string),
            stewart: Located {
                name: source.to_string(),
                sha256: src.sha256.clone(),
                range: located.then_some((s as u64, e as u64)),
                lines: lines(&bytes, s, e).expect("a citation is non-empty"),
            },
        });
    }
    Ok(out)
}

fn citations_j(cs: &[Citation]) -> J {
    J::Arr(cs.iter().map(|c| c.to_j()).collect())
}

/// One edit as the retained-payload accounting sees it.
pub enum Edit<'a> {
    /// An add or replace of entry `id` with a payload of `size` bytes.
    Store { id: &'a str, size: u64 },
    /// A delete of entry `id`.
    Remove { id: &'a str },
}

/// Retained superseded and deleted payload bytes after `edits`, in log
/// order, and how much of the reserve the edits made since the retained
/// bytes first reached the cap have drawn.
pub fn retained_over<'a>(edits: impl IntoIterator<Item = Edit<'a>>) -> (u64, u64) {
    let mut current: HashMap<&str, u64> = HashMap::new();
    let (mut kept, mut reserve, mut reached) = (0u64, 0u64, false);
    for e in edits {
        match e {
            Edit::Store { id, size } => {
                if reached {
                    reserve += size;
                }
                kept += current.insert(id, size).unwrap_or(0);
            }
            Edit::Remove { id } => kept += current.remove(id).unwrap_or(0),
        }
        reached |= kept >= RETAINED_CAP_BYTES;
    }
    (kept, reserve)
}

/// `retained_over` the log's `entry` records.
pub fn retained(state: &LogState) -> (u64, u64) {
    retained_over(
        state
            .entries()
            .filter_map(|(_, e)| match (&e.created, &e.target) {
                (Some(v), _) => Some(Edit::Store {
                    id: &v.id,
                    size: v.payload.size,
                }),
                (None, Some(t)) => Some(Edit::Remove { id: &t.id }),
                _ => None,
            }),
    )
}

/// Refuse an edit of `size` bytes under the retained-payload cap and reserve
/// (7.4), given the accounting so far. Delete, prepare and submit never
/// refuse on the cap.
pub fn cap_refusal(kept: u64, reserve: u64, size: u64) -> Option<&'static str> {
    if kept < RETAINED_CAP_BYTES {
        None
    } else if size > CAPPED_EDIT_BYTES {
        Some("retained_payload_cap")
    } else if reserve + size > RETAINED_RESERVE_BYTES {
        Some("retained_payload_reserve_exhausted")
    } else {
        None
    }
}

/// The bounds of 7.4 for an add or replace of `size` bytes (`replacing`
/// is the version replaced).
fn bounds(ctx: &Ctx, sel: &[Item], size: u64, replacing: Option<&Item>) -> Result<(), Fail> {
    if replacing.is_none() && sel.len() >= ENTRIES {
        return Err(refused(
            "entry_limit",
            format!(
                "The answer already holds {ENTRIES} current entries, the most it can hold. Replace or delete one first."
            ),
        ));
    }
    if size > ENTRY_BYTES {
        return Err(refused(
            "entry_limit",
            format!("An entry holds at most {ENTRY_BYTES} bytes; this one has {size}."),
        ));
    }
    let total: u64 = sel.iter().map(|i| i.payload.size).sum::<u64>()
        - replacing.map_or(0, |r| r.payload.size)
        + size;
    if total > SELECTION_BYTES {
        return Err(refused(
            "selection_limit",
            format!(
                "The current selection would hold {total} bytes; it holds at most {SELECTION_BYTES}."
            ),
        ));
    }
    let (kept, reserve) = retained(&ctx.state);
    match cap_refusal(kept, reserve, size) {
        Some(reason @ "retained_payload_cap") => Err(refused(
            reason,
            format!(
                "Superseded and deleted payloads have reached {RETAINED_CAP_BYTES} bytes, so edits larger than {CAPPED_EDIT_BYTES} bytes are refused."
            ),
        )),
        Some(reason) => Err(refused(
            reason,
            format!(
                "The {RETAINED_RESERVE_BYTES}-byte reserve for edits after the retained-payload cap is used up."
            ),
        )),
        None => Ok(()),
    }
}

fn label_notices(ctx: &Ctx, sel: &[Item], label: &str, id: &str) -> J {
    if label.is_empty() {
        return J::Arr(vec![]);
    }
    let same: Vec<String> = sel
        .iter()
        .filter(|i| i.id != id && i.label == label)
        .map(|i| i.handle(ctx.audit))
        .collect();
    if same.is_empty() {
        return J::Arr(vec![]);
    }
    J::Arr(vec![
        J::obj()
            .with("reason", "label_duplicate")
            .with(
                "message",
                format!("Another current entry has the label {label:?}; it was recorded anyway."),
            )
            .with("entries", json::strs(&same)),
    ])
}

/// What an add or replace creates.
struct New {
    id: String,
    version: u64,
    kind: String,
    label: String,
    bytes: Vec<u8>,
    encoding: Option<String>,
    citations: Option<Vec<Citation>>,
}

fn authoring(ctx: &Ctx) -> Result<(), Fail> {
    match authoring_ended(ctx, &ctx.state) {
        Some(f) => Err(f),
        None => Ok(()),
    }
}

fn record_failed(message: String, cause: crate::reply::Cause) -> Fail {
    Fail::failed("record_failed", message).cause(cause)
}

/// Publish one `entry` record (after storing the payload of an add or
/// replace) and build the reply.
fn publish(ctx: &Ctx, action: Action, tool: &str, target: Option<&Item>, new: Option<New>) -> Out {
    let payload: Option<Payload> = match &new {
        None => None,
        Some(n) => match names::write_payload(ctx.audit, &n.id, n.version, &n.bytes) {
            Ok(p) => Some(p.into()),
            Err(cause) => {
                return Out::fail(record_failed(
                    format!(
                        "The bytes of {} could not be stored ({}: {}); nothing was recorded.",
                        n.id, cause.operation, cause.error
                    ),
                    cause,
                ))
                .end(End::ArchiveWriteFailed);
            }
        },
    };
    let target_rec = target.map(|t| Target {
        id: t.id.clone(),
        version: t.version,
        record: names::log_name(t.record),
    });
    let created = new.as_ref().map(|n| Version {
        id: n.id.clone(),
        version: n.version,
        kind: n.kind.clone(),
        label: n.label.clone(),
        payload: payload.clone().expect("stored"),
        encoding: n.encoding.clone(),
        citations: n.citations.clone(),
    });
    let invocation = ctx.call.invocation(ctx.placement.run);
    let run = ctx.placement.run;
    let mut revision = 0;
    let p = log::publish(ctx.audit, "entry", |st| {
        if let Some(f) = authoring_ended(ctx, st) {
            return Err(f);
        }
        let live = st
            .latest_placement()
            .is_some_and(|p| p.run == run && p.ended.is_none());
        if !live {
            return Err(Fail::failed(
                "record_failed",
                format!("Placement {run} is no longer the live placement, so it cannot record."),
            ));
        }
        if action == Action::Add {
            let id = &created.as_ref().expect("an add creates").id;
            if st.next_entry_id() != *id {
                return Err(Fail::failed(
                    "record_failed",
                    format!(
                        "The entry identifier {id} was taken while the edit was being recorded."
                    ),
                ));
            }
        }
        if let Some(t) = target {
            let current = matches!(st.version_state(&t.id, t.version), VersionState::Current(_));
            if !current && !crate::sabotage!("stale_target_overwrites") {
                return Err(refused(
                    "stale_entry",
                    format!(
                        "{}.v{} was replaced or removed while this edit was being recorded.",
                        t.id, t.version
                    ),
                ));
            }
        }
        revision = st.revision() + 1;
        Ok(EntryRec {
            action,
            tool: tool.to_string(),
            invocation: invocation.clone(),
            target: target_rec.clone(),
            created: created.clone(),
            revision,
        }
        .to_j())
    });
    let published = match p {
        Ok(p) => p,
        Err(PubErr::Refused(f)) => {
            let failed = f.outcome == crate::reply::Outcome::Failed;
            let mut out = Out::fail(f);
            if failed {
                out = out.end(End::ArchiveWriteFailed);
            }
            return out;
        }
        Err(PubErr::Damaged(st)) => {
            return Out::fail(Fail::failed(
                "log_damaged",
                format!(
                    "The audit log is damaged ({}); nothing was recorded.",
                    st.bad_names()
                ),
            ))
            .end(End::LogDamaged);
        }
        Err(PubErr::NotPublished(cause)) => {
            return Out::fail(record_failed(
                format!(
                    "The entry record could not be published ({}: {}); nothing was recorded.",
                    cause.operation, cause.error
                ),
                cause,
            ))
            .end(End::ArchiveWriteFailed);
        }
        Err(PubErr::Uncertain { cause, .. }) => {
            let mut out = Out::fail(record_failed(
                format!("The entry record was linked, but Stewart could not confirm it is durable ({}: {}).", cause.operation, cause.error),
                cause,
            ))
            .end(End::ArchiveWriteFailed);
            out.answer = "unknown";
            return out;
        }
    };
    let _ = crate::fault!("entry.after_link");
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("remove_superseded_payload") && action == Action::Replace {
        // Sabotage control: the superseded payload file is removed.
        if let (Some(t), Ok(dir)) = (target, ctx.audit.dir.open_dir("payload")) {
            if let Some(name) = t.payload.file.strip_prefix("payload/") {
                if let Ok(c) = crate::fsx::cstr(name) {
                    unsafe {
                        libc::unlinkat(std::os::fd::AsRawFd::as_raw_fd(&dir.file), c.as_ptr(), 0)
                    };
                }
            }
        }
    }
    let record = names::log_name(published.n);
    let mut out = match (&created, target) {
        (Some(v), _) => {
            let handle = crate::ids::entry_handle(
                ctx.store(),
                ctx.audit_id(),
                &v.id,
                v.version,
                &published.sha256,
            );
            let sel = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
            let mut data = J::obj()
                .with("entry", handle)
                .with("id", v.id.as_str())
                .with("version", v.version)
                .with("revision", revision);
            if v.kind == ARTIFACT_TOOL {
                data.push("encoding", v.encoding.as_deref());
                data.push("size", v.payload.size);
            } else {
                data.push(
                    "citations",
                    citations_j(v.citations.as_deref().unwrap_or(&[])),
                );
            }
            data.push("notices", label_notices(ctx, &sel, &v.label, &v.id));
            Out::done(data)
        }
        (None, Some(t)) => Out::done(
            J::obj()
                .with(
                    "removed",
                    J::obj()
                        .with("id", t.id.as_str())
                        .with("version", t.version),
                )
                .with("revision", revision)
                .with("already_removed", false),
        ),
        (None, None) => unreachable!("an edit creates or removes"),
    };
    out.answer = "changed";
    out.log_record = Some(record);
    out.revision = Some(revision);
    out
}

fn label_of(o: &Obj, required: bool, min: usize) -> Result<String, Fail> {
    let label = if required {
        Some(input::req_str(o, "label")?)
    } else {
        input::opt_str(o, "label")?
    };
    let label = label.unwrap_or("");
    if !label_ok(label, min, LABEL_CHARS) {
        return Err(input::invalid_value(
            "/label",
            format!("a label is {min} to {LABEL_CHARS} characters without control characters"),
        ));
    }
    Ok(label.to_string())
}

/// The bytes of an artifact from exactly one of `text` and `base64`.
fn artifact_bytes(o: &Obj) -> Result<(Vec<u8>, &'static str), Fail> {
    let text = input::opt_str(o, "text")?;
    let base64 = input::opt_str(o, "base64")?;
    match (text, base64) {
        (Some(t), None) => Ok((t.as_bytes().to_vec(), "utf-8")),
        (None, Some(b)) => match b64::decode(b) {
            Some(bytes) => Ok((bytes, "binary")),
            None => Err(input::invalid_value(
                "/base64",
                "base64 is canonical RFC 4648 with padding and no whitespace",
            )),
        },
        _ => Err(refused(
            "fields_invalid",
            "An artifact takes exactly one of text and base64.",
        )
        .data(J::obj().with("exactly_one_of", json::strs(&["text", "base64"])))),
    }
}

/// `merge_equal_adds` sabotage control: an equal current entry is returned
/// instead of recording a new one.
fn merged(
    ctx: &Ctx,
    sel: &[Item],
    kind: &str,
    label: &str,
    bytes: &[u8],
    cits: &Option<Vec<Citation>>,
) -> Option<Out> {
    if !crate::sabotage!("merge_equal_adds") {
        return None;
    }
    let sha = util::sha256_hex(bytes);
    let same = sel.iter().find(|i| {
        i.kind == kind && i.label == label && i.payload.sha256 == sha && &i.citations == cits
    })?;
    let mut data = J::obj()
        .with("entry", same.handle(ctx.audit))
        .with("id", same.id.as_str())
        .with("version", same.version)
        .with("revision", ctx.state.revision());
    if kind == ARTIFACT_TOOL {
        data.push("encoding", same.encoding.as_deref());
        data.push("size", same.payload.size);
    } else {
        data.push(
            "citations",
            citations_j(same.citations.as_deref().unwrap_or(&[])),
        );
    }
    data.push("notices", J::Arr(vec![]));
    Some(Out::done(data))
}

/// `record_<kind>(text, citations = [], label = "")`.
pub fn record(ctx: &Ctx, v: &Json) -> Out {
    let go = || -> Result<Out, Fail> {
        let o = input::object(v, &["text", "citations", "label"], &["text"])?;
        let text = input::req_str(&o, "text")?;
        let label = label_of(&o, false, 0)?;
        let cits = citations(ctx, input::opt_arr(&o, "citations")?)?;
        authoring(ctx)?;
        let sel = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
        bounds(ctx, &sel, text.len() as u64, None)?;
        if let Some(m) = merged(
            ctx,
            &sel,
            ctx.tool,
            &label,
            text.as_bytes(),
            &Some(cits.clone()),
        ) {
            return Ok(m);
        }
        Ok(publish(
            ctx,
            Action::Add,
            ctx.tool,
            None,
            Some(New {
                id: ctx.state.next_entry_id(),
                version: 1,
                kind: ctx.tool.to_string(),
                label,
                bytes: text.as_bytes().to_vec(),
                encoding: None,
                citations: Some(cits),
            }),
        ))
    };
    go().unwrap_or_else(Out::fail)
}

/// `record_artifact(label, text | base64)`.
pub fn artifact(ctx: &Ctx, v: &Json) -> Out {
    let go = || -> Result<Out, Fail> {
        let o = input::object(v, &["label", "text", "base64"], &["label"])?;
        let label = label_of(&o, true, 1)?;
        let (bytes, encoding) = artifact_bytes(&o)?;
        authoring(ctx)?;
        let sel = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
        bounds(ctx, &sel, bytes.len() as u64, None)?;
        if let Some(m) = merged(ctx, &sel, ARTIFACT_TOOL, &label, &bytes, &None) {
            return Ok(m);
        }
        Ok(publish(
            ctx,
            Action::Add,
            ARTIFACT_TOOL,
            None,
            Some(New {
                id: ctx.state.next_entry_id(),
                version: 1,
                kind: ARTIFACT_TOOL.to_string(),
                label,
                bytes,
                encoding: Some(encoding.to_string()),
                citations: None,
            }),
        ))
    };
    go().unwrap_or_else(Out::fail)
}

/// The target of `replace` or `delete`: the exact current version, or the
/// refusal a stale or removed handle gets. A stale target never acts on a
/// newer version (except under the `stale_target_overwrites` sabotage
/// control).
fn target(ctx: &Ctx, handle: &str, tool: &str) -> Result<Result<Item, Out>, Fail> {
    match resolve(ctx, &ctx.state, handle)? {
        Named::Current(i) => Ok(Ok(i)),
        Named::Replaced(cur) if crate::sabotage!("stale_target_overwrites") => Ok(Ok(cur)),
        Named::Replaced(cur) => {
            let current = cur.handle(ctx.audit);
            Ok(Err(Out::fail(
                refused(
                    "stale_entry",
                    format!("{handle} was replaced; the current version is {current}. This makes no claim that the earlier replacement failed."),
                )
                .data(J::obj().with("entry", handle).with("current", current.as_str())),
            )
            .next(ToolNext::new(
                "read",
                J::obj().with("source", current.as_str()),
                "Read the current version first.",
            ))
            .next(ToolNext::new(
                tool,
                J::obj().with("entry", current.as_str()),
                if tool == "replace" {
                    "Replace the current version, supplying every field."
                } else {
                    "Delete the current version."
                },
            ))))
        }
        Named::Removed(by) => {
            let removed_this = by.entry().and_then(|e| e.target.as_ref()).is_some_and(|t| {
                crate::ids::parse_entry_handle(handle) == Some((t.id.as_str(), t.version))
            });
            if tool == "delete" && removed_this {
                // Repeating a delete returns the recorded removal.
                let e = by.entry().expect("a delete record");
                let t = e.target.as_ref().expect("a delete names its target");
                return Ok(Err(Out::done(
                    J::obj()
                        .with(
                            "removed",
                            J::obj()
                                .with("id", t.id.as_str())
                                .with("version", t.version),
                        )
                        .with("revision", e.revision)
                        .with("already_removed", true),
                )));
            }
            Err(refused(
                "entry_deleted",
                format!(
                    "{handle} was deleted from the answer ({}).",
                    names::log_name(by.n)
                ),
            )
            .data(J::obj().with("entry", handle)))
        }
    }
}

/// `replace(entry, …)`: every field of the entry's kind is required.
pub fn replace(ctx: &Ctx, v: &Json) -> Out {
    let go = || -> Result<Out, Fail> {
        let o = input::object(
            v,
            &["entry", "label", "text", "citations", "base64"],
            &["entry", "label"],
        )?;
        let handle = input::req_str(&o, "entry")?;
        authoring(ctx)?;
        let t = match target(ctx, handle, "replace")? {
            Ok(t) => t,
            Err(out) => return Ok(out),
        };
        let artifact = t.kind == ARTIFACT_TOOL;
        let has = |k: &str| o.get(k).is_some();
        let (missing, unexpected): (Vec<&str>, Vec<&str>) = if artifact {
            (
                vec![],
                ["citations"].into_iter().filter(|k| has(k)).collect(),
            )
        } else {
            (
                ["text", "citations"]
                    .into_iter()
                    .filter(|k| !has(k))
                    .collect(),
                ["base64"].into_iter().filter(|k| has(k)).collect(),
            )
        };
        if !missing.is_empty() || !unexpected.is_empty() {
            return Err(refused(
                "fields_invalid",
                format!(
                    "Replacing a {} entry takes {}; missing: {}; not allowed: {}.",
                    t.kind,
                    if artifact {
                        "label and exactly one of text and base64"
                    } else {
                        "text, citations and label"
                    },
                    if missing.is_empty() {
                        "none".into()
                    } else {
                        missing.join(", ")
                    },
                    if unexpected.is_empty() {
                        "none".into()
                    } else {
                        unexpected.join(", ")
                    },
                ),
            )
            .data(
                J::obj()
                    .with("entry_kind", t.kind.as_str())
                    .with("missing", json::strs(&missing))
                    .with("not_allowed", json::strs(&unexpected)),
            ));
        }
        let label = label_of(&o, true, if artifact { 1 } else { 0 })?;
        let (bytes, encoding, cits) = if artifact {
            let (b, enc) = artifact_bytes(&o)?;
            (b, Some(enc.to_string()), None)
        } else {
            let text = input::req_str(&o, "text")?;
            let cits = citations(ctx, input::opt_arr(&o, "citations")?)?;
            (text.as_bytes().to_vec(), None, Some(cits))
        };
        let sel = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
        bounds(ctx, &sel, bytes.len() as u64, Some(&t))?;
        Ok(publish(
            ctx,
            Action::Replace,
            "replace",
            Some(&t),
            Some(New {
                id: t.id.clone(),
                version: t.version + 1,
                kind: t.kind.clone(),
                label,
                bytes,
                encoding,
                citations: cits,
            }),
        ))
    };
    go().unwrap_or_else(Out::fail)
}

/// `delete(entry)`: removes exactly that version from current membership.
pub fn delete(ctx: &Ctx, v: &Json) -> Out {
    let go = || -> Result<Out, Fail> {
        let o = input::object(v, &["entry"], &["entry"])?;
        let handle = input::req_str(&o, "entry")?;
        authoring(ctx)?;
        let t = match target(ctx, handle, "delete")? {
            Ok(t) => t,
            Err(out) => return Ok(out),
        };
        Ok(publish(ctx, Action::Delete, "delete", Some(&t), None))
    };
    go().unwrap_or_else(Out::fail)
}

#[cfg(test)]
mod tests {
    use super::*;

    const MIB: u64 = 1024 * 1024;

    #[test]
    fn the_retained_cap_and_reserve_follow_superseded_and_deleted_bytes() {
        // 17 replacements of a 64 MiB entry retain 1 GiB of superseded bytes.
        let mut edits = vec![Edit::Store {
            id: "e1",
            size: 64 * MIB,
        }];
        for _ in 0..16 {
            edits.push(Edit::Store {
                id: "e1",
                size: 64 * MIB,
            });
        }
        let (kept, reserve) = retained_over(edits);
        assert_eq!((kept, reserve), (1024 * MIB, 0));
        assert_eq!(
            cap_refusal(kept, reserve, MIB + 1),
            Some("retained_payload_cap")
        );
        assert_eq!(cap_refusal(kept, reserve, MIB), None);
        assert_eq!(
            cap_refusal(kept, 64 * MIB - 10, 11),
            Some("retained_payload_reserve_exhausted")
        );
        assert_eq!(
            cap_refusal(kept - 1, 64 * MIB, 64 * MIB),
            None,
            "below the cap nothing refuses"
        );
        // Edits after the cap draw on the reserve; a delete retains the
        // removed bytes and draws nothing.
        let mut edits = vec![
            Edit::Store {
                id: "e1",
                size: 1024 * MIB,
            },
            Edit::Remove { id: "e1" },
        ];
        edits.push(Edit::Store { id: "e2", size: 10 });
        edits.push(Edit::Store { id: "e2", size: 20 });
        edits.push(Edit::Remove { id: "e2" });
        assert_eq!(retained_over(edits), (1024 * MIB + 30, 30));
    }
}
