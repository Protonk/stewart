//! Preparing and sealing the answer (INTERFACE 7.6, 8.1; QUESTION-FORMS):
//! the structured answer `stewart.answer/1`, the renderer `stewart.render/1`,
//! the auditor's `prepare` and `submit`, and the preparation and seal shared
//! with close.

use super::common::{Ctx, Item, Out, ended_fail, read_payload, refused, selection};
use super::{
    DamagedEntry, End, PrepareError, PrepareNotice, Prepared, Preparer, SealError, Sealed, Sealer,
    input,
};
use crate::archive::{Audit, Fail};
use crate::bodies::{ARTIFACT_TOOL, Actor, SealRec};
use crate::forms::{Family, RENDERER_ID};
use crate::ids;
use crate::json::{self, J, Json};
use crate::log::{self, EndedBy, LogState, PubErr};
use crate::names;
use crate::reply::{Cause, ToolNext};
use crate::returns::{self, Manifest, Member, Unproduced};
use crate::util;

pub const ANSWER_SCHEMA: &str = "stewart.answer/1";
const RENDER_FIRST_LINE: &str = "Rendered by Stewart. Entry text is attributed to the auditor.";
const RENDER_EMPTY: &str = "No answer entries recorded.";

/// One entry of a prepared selection, with its bytes or why they are missing.
pub enum Prepped {
    Produced(Item, Vec<u8>),
    Unproduced(Item, &'static str),
}

impl Prepped {
    fn item(&self) -> &Item {
        match self {
            Prepped::Produced(i, _) | Prepped::Unproduced(i, _) => i,
        }
    }
}

/// `answer.json` (QUESTION-FORMS): keys in the pinned order, no whitespace,
/// each entry on its own line, one LF at the end.
pub fn answer_json(revision: u64, entries: &[Prepped]) -> Vec<u8> {
    let head = format!("{{\"schema\":\"{ANSWER_SCHEMA}\",\"revision\":{revision},\"entries\":[");
    let mut b = head.into_bytes();
    for (k, p) in entries.iter().enumerate() {
        b.extend_from_slice(if k == 0 { b"\n" } else { b",\n" });
        let i = p.item();
        let mut e = J::obj()
            .with("id", i.id.as_str())
            .with("version", i.version)
            .with("kind", i.kind.as_str())
            .with("label", i.label.as_str());
        match p {
            Prepped::Unproduced(_, failure) => e.push(
                "unproduced",
                J::obj()
                    .with("sha256", i.payload.sha256.as_str())
                    .with("size", i.payload.size)
                    .with("failure", *failure),
            ),
            Prepped::Produced(_, _) if i.is_artifact() => {
                e.push("encoding", i.encoding.as_deref());
                e.push("member", names::artifact_member(&i.id));
                e.push("size", i.payload.size);
                e.push("sha256", i.payload.sha256.as_str());
            }
            Prepped::Produced(_, bytes) => {
                e.push("text", String::from_utf8_lossy(bytes).into_owned());
                e.push(
                    "citations",
                    J::Arr(i.citations.iter().flatten().map(|c| c.to_j()).collect()),
                );
            }
        }
        e.write(&mut b);
    }
    b.extend_from_slice(b"]}\n");
    b
}

fn heading_kind(kind: &str) -> String {
    if kind == ARTIFACT_TOOL {
        return "Artifact".into();
    }
    let words = kind
        .strip_prefix("record_")
        .unwrap_or(kind)
        .replace('_', " ");
    let mut c = words.chars();
    match c.next() {
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
        None => String::new(),
    }
}

/// `answer.md` by the rules of `stewart.render/1`. It never reorders,
/// combines or judges entries and never fills a gap.
pub fn render(entries: &[(&Item, &[u8])]) -> Vec<u8> {
    let mut lines: Vec<String> = Vec::new();
    if entries.is_empty() {
        lines.push(RENDER_EMPTY.into());
    } else {
        lines.push(RENDER_FIRST_LINE.into());
    }
    for (i, bytes) in entries {
        lines.push(String::new());
        let mut heading = format!("## {} — {}", heading_kind(&i.kind), i.id);
        if !i.label.is_empty() {
            heading.push_str(&format!(" · {}", i.label));
        }
        lines.push(heading);
        lines.push(String::new());
        if i.is_binary() {
            lines.push(format!(
                "Binary artifact, {} bytes, SHA-256 {}, delivered as {}.",
                i.payload.size,
                i.payload.sha256,
                names::artifact_member(&i.id)
            ));
        } else if bytes.is_empty() {
            lines.push("*No text recorded.*".into());
        } else {
            let text = String::from_utf8_lossy(bytes);
            let body = text.strip_suffix('\n').unwrap_or(&text);
            for l in body.split('\n') {
                lines.push(if l.is_empty() {
                    ">".into()
                } else {
                    format!("> {l}")
                });
            }
        }
        let cits = i.citations.as_deref().unwrap_or(&[]);
        if !cits.is_empty() {
            lines.push(String::new());
            let parts: Vec<String> = cits
                .iter()
                .map(|c| {
                    let (a, b) = c.stewart.lines;
                    let l = if a == b {
                        format!("line {a}")
                    } else {
                        format!("lines {a}–{b}")
                    };
                    let (s, e) = c.range();
                    let mut p = format!("{} {l} [{s}, {e})", c.source);
                    if let Some(q) = &c.quote {
                        p.push(' ');
                        p.push_str(&json::quote(q));
                    }
                    p
                })
                .collect();
            lines.push(format!("Citations: {}.", parts.join("; ")));
        }
    }
    if crate::sabotage!("render_conclusion") {
        // Sabotage control: the renderer adds a conclusion of its own.
        lines.push("No issues found.".into());
    }
    let mut out = lines.join("\n");
    out.push('\n');
    out.into_bytes()
}

fn counts_and_notices(family: &Family, items: &[Item]) -> (Vec<(String, u64)>, Vec<PrepareNotice>) {
    let count = |t: &str| items.iter().filter(|i| i.kind == t).count() as u64;
    let mut counts: Vec<(String, u64)> = family
        .tools
        .iter()
        .map(|t| (t.to_string(), count(t)))
        .collect();
    counts.push((ARTIFACT_TOOL.to_string(), count(ARTIFACT_TOOL)));
    let notices = if items.is_empty() {
        vec![PrepareNotice {
            reason: "answer_empty".into(),
            tool: None,
            message: "No answer entries are recorded.".into(),
        }]
    } else {
        family
            .sections
            .iter()
            .filter(|t| count(t) == 0)
            .map(|t| PrepareNotice {
                reason: "section_unfilled".into(),
                tool: Some(t.to_string()),
                message: format!("No {t} entries are recorded."),
            })
            .collect()
    };
    (counts, notices)
}

/// Prepare `items` (the selection to prepare, at `revision`) into a new
/// `prepared/<n>`.
pub fn prepare_items(
    audit: &Audit,
    family: &Family,
    mut items: Vec<Item>,
    revision: u64,
    preparer: Preparer,
) -> Result<Prepared, PrepareError> {
    if crate::sabotage!("drop_last_entry") {
        // Sabotage control: the preparation leaves out the last entry.
        items.pop();
    }
    let mut prepped = Vec::new();
    let mut damaged = Vec::new();
    for i in &items {
        match read_payload(audit, &i.payload) {
            Ok(b) => prepped.push(Prepped::Produced(i.clone(), b)),
            Err(f) => {
                damaged.push(DamagedEntry {
                    id: i.id.clone(),
                    failure: f.to_string(),
                });
                prepped.push(Prepped::Unproduced(i.clone(), f));
            }
        }
    }
    if preparer == Preparer::Auditor && !damaged.is_empty() {
        return Err(PrepareError::Damaged(damaged));
    }
    let answer = answer_json(revision, &prepped);
    let rendering = damaged.is_empty().then(|| {
        let produced: Vec<(&Item, &[u8])> = prepped
            .iter()
            .filter_map(|p| match p {
                Prepped::Produced(i, b) => Some((i, b.as_slice())),
                Prepped::Unproduced(..) => None,
            })
            .collect();
        render(&produced)
    });
    let (n, dir) = names::claim_prepared(audit).map_err(PrepareError::WriteFailed)?;
    let answer_sha = names::write_prepared_file(audit, &dir, n, returns::ANSWER_MEMBER, &answer)
        .map_err(PrepareError::WriteFailed)?;
    let rendering_member = match &rendering {
        Some(r) => Some(Member {
            name: returns::RENDERING_MEMBER.into(),
            role: "rendering".into(),
            size: r.len() as u64,
            sha256: names::write_prepared_file(audit, &dir, n, returns::RENDERING_MEMBER, r)
                .map_err(PrepareError::WriteFailed)?,
        }),
        None => None,
    };
    let mut unproduced: Vec<Unproduced> = damaged
        .iter()
        .map(|d| Unproduced {
            name: d.id.clone(),
            role: "entry".into(),
            failure: d.failure.clone(),
            dependency: None,
        })
        .collect();
    if !damaged.is_empty() {
        unproduced.push(Unproduced {
            name: returns::RENDERING_MEMBER.into(),
            role: "rendering".into(),
            failure: "not_rendered".into(),
            dependency: Some(damaged.iter().map(|d| d.id.clone()).collect()),
        });
    }
    let artifacts = prepped
        .iter()
        .filter_map(|p| match p {
            Prepped::Produced(i, _) if i.is_artifact() => Some((
                Member {
                    name: names::artifact_member(&i.id),
                    role: "artifact".into(),
                    size: i.payload.size,
                    sha256: i.payload.sha256.clone(),
                },
                i.payload.file.clone(),
            )),
            _ => None,
        })
        .collect();
    let payloads = prepped
        .iter()
        .filter_map(|p| match p {
            Prepped::Produced(i, _) => Some(i.payload.clone()),
            Prepped::Unproduced(..) => None,
        })
        .collect();
    let (counts, notices) = counts_and_notices(family, &items);
    Ok(Prepared {
        n,
        revision,
        entry_count: items.len() as u64,
        answer: Member {
            name: returns::ANSWER_MEMBER.into(),
            role: "answer".into(),
            size: answer.len() as u64,
            sha256: answer_sha,
        },
        rendering: rendering_member,
        artifacts,
        unproduced,
        counts,
        notices,
        payloads,
    })
}

/// The selection at `through` for close (no placement's view applies).
pub fn prepare(
    audit: &Audit,
    family: &Family,
    state: &LogState,
    through: u64,
    preparer: Preparer,
) -> Result<Prepared, PrepareError> {
    let items = selection(audit, state, through, None);
    prepare_items(
        audit,
        family,
        items,
        state.revision_through(through),
        preparer,
    )
}

// ---------------------------------------------------------------------------
// Auditor preparations read back.

/// An auditor preparation's files, checked against its handle.
pub struct PrepFiles {
    pub n: u64,
    pub answer: Vec<u8>,
    pub rendering: Vec<u8>,
    pub revision: u64,
}

fn read_prep_file(audit: &Audit, n: u64, name: &str) -> Option<Vec<u8>> {
    let dir = audit
        .dir
        .open_dir("prepared")
        .ok()?
        .open_dir(&n.to_string())
        .ok()?;
    dir.read_regular(name, 1 << 30).ok().map(|(b, _)| b)
}

/// The revision `answer.json` states, read from its fixed first bytes.
fn answer_revision(answer: &[u8]) -> Option<u64> {
    let rest = answer
        .strip_prefix(format!("{{\"schema\":\"{ANSWER_SCHEMA}\",\"revision\":").as_bytes())?;
    let n = rest.iter().take_while(|c| c.is_ascii_digit()).count();
    std::str::from_utf8(&rest[..n]).ok()?.parse().ok()
}

/// Read the preparation an `ap<n>.<check>` handle names and check the handle
/// against its files' digests and revision: `handle_invalid` otherwise.
pub fn load_auditor_prep(ctx: &Ctx, handle: &str) -> Result<PrepFiles, Fail> {
    let invalid = || {
        refused(
            "handle_invalid",
            format!(
                "{handle:?} is not a preparation handle of this audit. Use the handle prepare returned."
            ),
        )
    };
    let n = ids::parse_ap(handle).ok_or_else(invalid)?;
    let answer = read_prep_file(ctx.audit, n, returns::ANSWER_MEMBER).ok_or_else(invalid)?;
    let rendering = read_prep_file(ctx.audit, n, returns::RENDERING_MEMBER).ok_or_else(invalid)?;
    let revision = answer_revision(&answer).ok_or_else(invalid)?;
    let want = ids::ap_handle(
        ctx.store(),
        ctx.audit_id(),
        n,
        &util::sha256_hex(&answer),
        &util::sha256_hex(&rendering),
        revision,
    );
    if want != handle {
        return Err(invalid());
    }
    Ok(PrepFiles {
        n,
        answer,
        rendering,
        revision,
    })
}

/// Rebuild a `Prepared` from an auditor preparation's files and the records
/// of the versions its `answer.json` names.
fn prepared_from(ctx: &Ctx, f: &PrepFiles) -> Result<Prepared, Fail> {
    let damaged = |why: &str| {
        Fail::failed(
            "answer_damaged",
            format!("Preparation {} cannot be read back: {why}.", f.n),
        )
    };
    let v = json::parse(&f.answer).map_err(|e| damaged(&e.to_string()))?;
    let o = v.obj("").map_err(|e| damaged(&e.to_string()))?;
    let entries = o.arr("entries").map_err(|e| damaged(&e.to_string()))?;
    let mut artifacts = Vec::new();
    let mut payloads = Vec::new();
    let mut items = Vec::new();
    for e in entries {
        let eo = e.obj("").map_err(|e| damaged(&e.to_string()))?;
        let id = eo.str("id").map_err(|e| damaged(&e.to_string()))?;
        let version = eo
            .u64("version", u64::MAX)
            .map_err(|e| damaged(&e.to_string()))?;
        let created = ctx
            .state
            .version_created(id, version)
            .ok_or_else(|| damaged(&format!("{id}.v{version} has no entry record")))?;
        let p = created.version.payload.clone();
        if created.version.kind == ARTIFACT_TOOL {
            artifacts.push((
                Member {
                    name: names::artifact_member(id),
                    role: "artifact".into(),
                    size: p.size,
                    sha256: p.sha256.clone(),
                },
                p.file.clone(),
            ));
        }
        items.push(created.version.kind.clone());
        payloads.push(p);
    }
    let family = ctx
        .world
        .arrangement
        .family()
        .ok_or_else(|| damaged("the family is unknown"))?;
    let count = |t: &str| items.iter().filter(|k| *k == t).count() as u64;
    let mut counts: Vec<(String, u64)> = family
        .tools
        .iter()
        .map(|t| (t.to_string(), count(t)))
        .collect();
    counts.push((ARTIFACT_TOOL.into(), count(ARTIFACT_TOOL)));
    Ok(Prepared {
        n: f.n,
        revision: f.revision,
        entry_count: items.len() as u64,
        answer: Member {
            name: returns::ANSWER_MEMBER.into(),
            role: "answer".into(),
            size: f.answer.len() as u64,
            sha256: util::sha256_hex(&f.answer),
        },
        rendering: Some(Member {
            name: returns::RENDERING_MEMBER.into(),
            role: "rendering".into(),
            size: f.rendering.len() as u64,
            sha256: util::sha256_hex(&f.rendering),
        }),
        artifacts,
        unproduced: Vec::new(),
        counts,
        notices: Vec::new(),
        payloads,
    })
}

// ---------------------------------------------------------------------------
// The `prepare` tool.

fn damaged_out(entries: &[DamagedEntry]) -> Out {
    let list: Vec<String> = entries
        .iter()
        .map(|d| format!("{} ({})", d.id, d.failure))
        .collect();
    Out::fail(
        refused(
            "answer_damaged",
            format!(
                "Recorded answer bytes no longer match what was recorded: {}. The run stops here.",
                list.join(", ")
            ),
        )
        .data(
            J::obj().with(
                "entries",
                J::Arr(
                    entries
                        .iter()
                        .map(|d| {
                            J::obj()
                                .with("id", d.id.as_str())
                                .with("failure", d.failure.as_str())
                        })
                        .collect(),
                ),
            ),
        ),
    )
    .end(End::AnswerDamaged)
}

fn write_failed(cause: Cause) -> Out {
    Out::fail(
        Fail::failed(
            "record_failed",
            format!(
                "The preparation could not be written ({}: {}).",
                cause.operation, cause.error
            ),
        )
        .cause(cause),
    )
    .end(End::ArchiveWriteFailed)
}

fn notices_j(n: &[PrepareNotice]) -> J {
    J::Arr(
        n.iter()
            .map(|x| {
                let mut j = J::obj().with("reason", x.reason.as_str());
                if let Some(t) = &x.tool {
                    j.push("tool", t.as_str());
                }
                j.with("message", x.message.as_str())
            })
            .collect(),
    )
}

fn ap_of(ctx: &Ctx, p: &Prepared) -> String {
    ids::ap_handle(
        ctx.store(),
        ctx.audit_id(),
        p.n,
        &p.answer.sha256,
        &p.rendering
            .as_ref()
            .map(|r| r.sha256.clone())
            .unwrap_or_default(),
        p.revision,
    )
}

pub fn prepare_tool(ctx: &Ctx, v: &Json) -> Out {
    if let Err(f) = input::object(v, &[], &[]) {
        return f.into();
    }
    let Some(family) = ctx.world.arrangement.family() else {
        return Out::fail(Fail::failed(
            "record_failed",
            "The pinned family is not one this release knows.",
        ));
    };
    let items = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
    if crate::sabotage!("block_incomplete") {
        // Sabotage control: an unfilled section blocks preparation.
        let (_, notices) = counts_and_notices(family, &items);
        if let Some(n) = notices.iter().find(|n| n.reason == "section_unfilled") {
            return Out::fail(refused("section_unfilled", n.message.clone()));
        }
    }
    let p = match prepare_items(
        ctx.audit,
        family,
        items,
        ctx.state.revision(),
        Preparer::Auditor,
    ) {
        Ok(p) => p,
        Err(PrepareError::Damaged(d)) => return damaged_out(&d),
        Err(PrepareError::WriteFailed(c)) => return write_failed(c),
    };
    let ap = ap_of(ctx, &p);
    let mut counts = J::obj();
    for (t, c) in &p.counts {
        counts.push(t, *c);
    }
    let mut data = J::obj()
        .with("prepared", ap.as_str())
        .with("revision", p.revision)
        .with("entry_count", p.entry_count)
        .with("counts", counts)
        .with("notices", notices_j(&p.notices))
        .with(
            "rendering",
            J::obj()
                .with("source", format!("{ap}/rendering"))
                .with("size", p.rendering.as_ref().map_or(0, |r| r.size)),
        )
        .with(
            "selection",
            J::obj()
                .with("source", format!("{ap}/selection"))
                .with("size", p.answer.size),
        );
    if crate::sabotage!("prepare_claims_seal") {
        // Sabotage control: preparing claims a seal.
        data.push("sealer", "auditor");
    }
    Out::done(data)
        .next(ToolNext::new(
            "read",
            J::obj().with("source", format!("{ap}/rendering")),
            "Read exactly what would be sealed.",
        ))
        .next(ToolNext::new(
            "submit",
            J::obj().with("prepared", ap.as_str()).with("confirm", true),
            "Seal this candidate as your answer; it cannot be edited afterwards.",
        ))
}

// ---------------------------------------------------------------------------
// Seal.

/// The seal that stands, if one exists, as `Sealed` with `existing: true`.
pub fn existing_seal(audit: &Audit, state: &LogState) -> Option<Sealed> {
    let (rec, s) = state.seal()?;
    let sealed_at = returns::load_manifest(audit, &s.manifest, &s.manifest_sha256)
        .map(|(m, _)| m.sealed_at)
        .unwrap_or_else(|_| rec.at.clone());
    Some(Sealed {
        record: names::log_name(rec.n),
        handle: ids::seal_handle(&audit.archive.store, &audit.id, &s.manifest_sha256),
        actor: s.actor,
        sealed_at,
        revision: s.revision,
        manifest_sha256: s.manifest_sha256.clone(),
        existing: true,
    })
}

fn reverify(audit: &Audit, p: &Prepared) -> Result<(), String> {
    let dir = audit
        .dir
        .open_dir("prepared")
        .and_then(|d| d.open_dir(&p.n.to_string()))
        .map_err(|e| format!("prepared/{} cannot be opened: {}", p.n, util::describe(&e)))?;
    for m in std::iter::once(&p.answer).chain(p.rendering.as_ref()) {
        match dir.read_regular(&m.name, m.size + 1) {
            Ok((b, _)) if b.len() as u64 == m.size && util::sha256_hex(&b) == m.sha256 => {}
            _ => {
                return Err(format!(
                    "prepared/{}/{} does not match its digest",
                    p.n, m.name
                ));
            }
        }
    }
    for pl in &p.payloads {
        if let Err(f) = read_payload(audit, pl) {
            return Err(format!("{} is {f}", pl.file));
        }
    }
    Ok(())
}

/// Seal a preparation (8.1).
pub fn seal(
    audit: &Audit,
    family: &str,
    prepared: &Prepared,
    sealer: Sealer,
) -> Result<Sealed, SealError> {
    reverify(audit, prepared).map_err(SealError::Damaged)?;
    let mut actor = match sealer {
        Sealer::Auditor(_) => Actor::Auditor,
        Sealer::Manager => Actor::Manager,
    };
    if actor == Actor::Manager && crate::sabotage!("manager_seal_as_auditor") {
        // Sabotage control: close's seal is attributed to the auditor.
        actor = Actor::Auditor;
    }
    let writer = audit
        .exe
        .as_ref()
        .map_or(audit.refile.writer_sha256.clone(), |e| e.sha256.clone());
    let mut members = vec![prepared.answer.clone()];
    members.extend(prepared.rendering.clone());
    members.extend(prepared.artifacts.iter().map(|(m, _)| m.clone()));
    let manifest = Manifest {
        audit: audit.id.clone(),
        store: audit.archive.store.clone(),
        family: family.to_string(),
        renderer: RENDERER_ID.into(),
        writer,
        actor,
        sealed_at: util::now_utc(),
        revision: prepared.revision,
        members,
        unproduced: prepared.unproduced.clone(),
    };
    let bytes = manifest.bytes();
    let manifest_sha = util::sha256_hex(&bytes);
    let (_, manifest_name) =
        names::write_manifest(audit, &bytes).map_err(SealError::NotPublished)?;
    let invocation = match &sealer {
        Sealer::Auditor(i) => Some(i.clone()),
        Sealer::Manager => None,
    };
    let body = SealRec {
        actor,
        prepared: prepared.n,
        answer_sha256: prepared.answer.sha256.clone(),
        rendering_sha256: prepared.rendering.as_ref().map(|r| r.sha256.clone()),
        revision: prepared.revision,
        manifest: manifest_name,
        manifest_sha256: manifest_sha.clone(),
        invocation,
    };
    let auditor = matches!(sealer, Sealer::Auditor(_));
    let p = log::publish(audit, "seal", |st| {
        if st.seal().is_some() {
            return Err(Fail::refused("sealed", "a seal stands"));
        }
        let close = st.close_requested();
        if auditor {
            if close.is_some() {
                return Err(Fail::refused("closed", "close was requested"));
            }
            if st.revision() != prepared.revision {
                return Err(Fail::refused("stale", "the revision changed"));
            }
        } else if close.is_none() {
            return Err(Fail::failed("record_failed", "close_requested is missing"));
        }
        Ok(body.to_j())
    });
    match p {
        Ok(published) => {
            let _ = crate::fault!("seal.after_link");
            Ok(Sealed {
                record: names::log_name(published.n),
                handle: ids::seal_handle(&audit.archive.store, &audit.id, &manifest_sha),
                actor,
                sealed_at: manifest.sealed_at,
                revision: prepared.revision,
                manifest_sha256: manifest_sha,
                existing: false,
            })
        }
        Err(PubErr::Refused(f)) => {
            let st = log::read(audit);
            match f.reason {
                "stale" => Err(SealError::Stale {
                    revision_now: st.revision(),
                }),
                "sealed" | "closed" => {
                    let end = st.authoring_end();
                    Err(SealError::AuthoringEnded {
                        by: end.as_ref().map_or(EndedBy::Seal, |e| e.by),
                        record: end.map_or(String::new(), |e| names::log_name(e.record.n)),
                        seal: existing_seal(audit, &st),
                    })
                }
                _ => Err(SealError::NotPublished(Cause::new(
                    "publish seal",
                    f.message,
                ))),
            }
        }
        Err(PubErr::Damaged(_)) => Err(SealError::LogDamaged),
        Err(PubErr::NotPublished(c)) => Err(SealError::NotPublished(c)),
        Err(PubErr::Uncertain { cause, .. }) => Err(SealError::Uncertain(cause)),
    }
}

// ---------------------------------------------------------------------------
// The `submit` tool.

fn sealed_data(s: &Sealed, already: bool) -> J {
    let mut d = J::obj()
        .with("seal", s.handle.as_str())
        .with("sealer", s.actor.name())
        .with("sealed_at", s.sealed_at.as_str())
        .with("revision", s.revision)
        .with("manifest_sha256", s.manifest_sha256.as_str());
    if already {
        d.push("already_sealed", true);
    }
    d
}

fn stale(ctx: &Ctx, revision_now: u64, prepared: &str) -> Out {
    let _ = ctx;
    Out::fail(
        refused(
            "stale_preparation",
            format!("The answer changed after {prepared} was prepared (it is now at revision {revision_now}); prepare again and submit the new handle."),
        )
        .data(J::obj().with("revision_now", revision_now)),
    )
    .next(ToolNext::new("prepare", J::obj(), "Prepare the current selection."))
}

pub fn submit(ctx: &Ctx, v: &Json) -> Out {
    match submit_inner(ctx, v) {
        Ok(o) => o,
        Err(f) => f.into(),
    }
}

fn submit_inner(ctx: &Ctx, v: &Json) -> Result<Out, Fail> {
    let o = input::object(v, &["prepared", "confirm"], &["prepared"])?;
    let handle = input::req_str(&o, "prepared")?;
    let confirm = input::opt_bool(&o, "confirm")?.unwrap_or(false);
    let files = load_auditor_prep(ctx, handle)?;
    let state = &ctx.state;
    let seal_effect = if state.seal().is_some() {
        "existing"
    } else {
        "none"
    };
    let with_seal = |mut out: Out| {
        out.seal = seal_effect;
        out
    };
    // A seal of this preparation stands: the repeat returns it.
    if let Some((rec, s)) = state.seal() {
        if confirm && s.actor == Actor::Auditor && s.prepared == files.n {
            let sealed = existing_seal(ctx.audit, state).expect("a seal exists");
            let started = state
                .placements()
                .iter()
                .find(|p| p.run == ctx.placement.run)
                .map_or(0, |p| p.started.n);
            let mut out = with_seal(Out::done(sealed_data(&sealed, true)));
            // A seal published earlier in this placement (whose first reply
            // may have been uncertain) marks this call sealed too, so the stop
            // path no longer applies; the run delivers the seal from the log.
            out.sealed = rec.n > started;
            out.log_record = Some(names::log_name(rec.n));
            return Ok(out);
        }
    }
    if confirm {
        if let Some(end) = state.authoring_end() {
            if matches!(end.by, EndedBy::Seal | EndedBy::Close) {
                return Ok(with_seal(Out::fail(ended_fail(
                    ctx,
                    state,
                    end.by,
                    end.record.n,
                ))));
            }
        }
    }
    let revision_now = state.revision();
    let retarget =
        files.revision != revision_now && crate::sabotage!("stale_preparation_retargets");
    if files.revision != revision_now && !retarget {
        return Ok(with_seal(stale(ctx, revision_now, handle)));
    }
    let mut prepared = prepared_from(ctx, &files)?;
    if !confirm {
        return Ok(with_seal(Out::done(
            J::obj()
                .with("dry_run", true)
                .with("revision", prepared.revision)
                .with("entry_count", prepared.entry_count)
                .with(
                    "rendering",
                    J::obj()
                        .with("source", format!("{handle}/rendering"))
                        .with("size", files.rendering.len()),
                ),
        )));
    }
    let family = ctx.world.arrangement.family().ok_or_else(|| {
        Fail::failed(
            "record_failed",
            "The pinned family is not one this release knows.",
        )
    })?;
    if retarget {
        // Sabotage control: a stale handle seals the current selection.
        let items = selection(ctx.audit, state, u64::MAX, Some(ctx.placement));
        prepared = match prepare_items(ctx.audit, family, items, revision_now, Preparer::Auditor) {
            Ok(p) => p,
            Err(PrepareError::Damaged(d)) => return Ok(damaged_out(&d)),
            Err(PrepareError::WriteFailed(c)) => return Ok(write_failed(c)),
        };
    }
    let invocation = ctx.call.invocation(ctx.placement.run);
    match seal(
        ctx.audit,
        &family.versioned_id(),
        &prepared,
        Sealer::Auditor(invocation),
    ) {
        Ok(s) => {
            let mut data = sealed_data(&s, false);
            if crate::sabotage!("submit_claims_delivery") {
                // Sabotage control: the reply claims a delivery.
                data.push("delivered", true);
            }
            let mut out = Out::done(data);
            out.seal = "recorded";
            out.sealed = true;
            out.log_record = Some(s.record.clone());
            Ok(out)
        }
        Err(SealError::Stale { revision_now }) => Ok(with_seal(stale(ctx, revision_now, handle))),
        Err(SealError::AuthoringEnded { .. }) => {
            let st = log::read(ctx.audit);
            let mut out = match st.authoring_end() {
                Some(end) => Out::fail(ended_fail(ctx, &st, end.by, end.record.n)),
                None => Out::fail(Fail::failed("record_failed", "authoring ended")),
            };
            out.seal = if st.seal().is_some() {
                "existing"
            } else {
                "none"
            };
            Ok(out)
        }
        Err(SealError::Damaged(why)) => Ok(with_seal(
            Out::fail(refused(
                "answer_damaged",
                format!("The preparation no longer verifies: {why}. The run stops here."),
            ))
            .end(End::AnswerDamaged),
        )),
        Err(SealError::Uncertain(cause)) => {
            let mut out = Out::fail(
                Fail::failed(
                    "seal_uncertain",
                    "The seal record was linked, but Stewart could not confirm it is durable; repeating the same submit returns the recorded seal or seals.",
                )
                .cause(cause),
            )
            .next(ToolNext::new(
                "submit",
                J::obj().with("prepared", handle).with("confirm", true),
                "Repeat the same submit; it returns the recorded seal, or seals.",
            ));
            out.seal = if crate::sabotage!("seal_uncertain_as_none") {
                // Sabotage control: uncertainty is reported as no seal.
                "none"
            } else {
                "unknown"
            };
            Ok(out)
        }
        Err(SealError::NotPublished(cause)) => Ok(with_seal(
            Out::fail(
                Fail::failed(
                    "record_failed",
                    format!(
                        "The seal could not be recorded ({}: {}); nothing was sealed.",
                        cause.operation, cause.error
                    ),
                )
                .cause(cause),
            )
            .end(End::ArchiveWriteFailed),
        )),
        Err(SealError::LogDamaged) => Ok(Out::fail(Fail::failed(
            "log_damaged",
            "The audit log is damaged; nothing was sealed.",
        ))
        .end(End::LogDamaged)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bodies::{Citation, Located, Payload};

    fn item(
        id: &str,
        kind: &str,
        label: &str,
        encoding: Option<&str>,
        cits: Option<Vec<Citation>>,
    ) -> Item {
        Item {
            id: id.into(),
            version: 2,
            kind: kind.into(),
            label: label.into(),
            payload: Payload {
                file: format!("payload/{id}.v2.bin"),
                sha256: "a".repeat(64),
                size: 120,
            },
            encoding: encoding.map(str::to_string),
            citations: cits,
            record: 9,
            record_sha256: "b".repeat(64),
        }
    }

    fn cites() -> Vec<Citation> {
        vec![
            Citation {
                source: "materials/a.py".into(),
                start: Some(50),
                end: Some(119),
                quote: None,
                stewart: Located {
                    name: "materials/a.py".into(),
                    sha256: "c".repeat(64),
                    range: None,
                    lines: (4, 6),
                },
            },
            Citation {
                source: "question".into(),
                start: None,
                end: None,
                quote: Some("R1. A \"reminder\"".into()),
                stewart: Located {
                    name: "question".into(),
                    sha256: "d".repeat(64),
                    range: Some((0, 46)),
                    lines: (1, 1),
                },
            },
        ]
    }

    #[test]
    fn the_rendering_follows_its_rules_exactly() {
        let obs = item(
            "e3",
            "record_observation",
            "restart duplicate",
            None,
            Some(cites()),
        );
        let wq = item("e5", "record_working_question", "", None, Some(vec![]));
        let empty = item("e6", "record_limit", "x", None, Some(vec![]));
        let bin = item("e4", ARTIFACT_TOOL, "trace", Some("binary"), None);
        let text =
            b"Implementation A can send the same reminder twice\r\n\nafter sending.\n".as_slice();
        let out = render(&[
            (&obs, text),
            (&wq, b"\n"),
            (&empty, b""),
            (&bin, b"\x00\xff"),
        ]);
        let want = format!(
            "Rendered by Stewart. Entry text is attributed to the auditor.\n\
             \n\
             ## Observation — e3 · restart duplicate\n\
             \n\
             > Implementation A can send the same reminder twice\r\n\
             >\n\
             > after sending.\n\
             \n\
             Citations: materials/a.py lines 4–6 [50, 119); question line 1 [0, 46) \"R1. A \\\"reminder\\\"\".\n\
             \n\
             ## Working question — e5\n\
             \n\
             >\n\
             \n\
             ## Limit — e6 · x\n\
             \n\
             *No text recorded.*\n\
             \n\
             ## Artifact — e4 · trace\n\
             \n\
             Binary artifact, 120 bytes, SHA-256 {}, delivered as artifact-e4.bin.\n",
            "a".repeat(64)
        );
        assert_eq!(String::from_utf8(out).unwrap(), want);
        assert_eq!(render(&[]), b"No answer entries recorded.\n");
    }

    #[test]
    fn the_structured_answer_is_byte_exact() {
        let a = item("e1", "record_account", "", None, Some(cites()));
        let art = item("e4", ARTIFACT_TOOL, "trace", Some("utf-8"), None);
        let lost = item("e3", "record_observation", "gone", None, Some(vec![]));
        let b = answer_json(
            7,
            &[
                Prepped::Produced(a, b"Line\n\t\"q\"\x01\x7f\xc3\xa9".to_vec()),
                Prepped::Unproduced(lost, "damaged"),
                Prepped::Produced(art, b"ignored".to_vec()),
            ],
        );
        let c = cites();
        let want = format!(
            "{{\"schema\":\"stewart.answer/1\",\"revision\":7,\"entries\":[\n\
             {{\"id\":\"e1\",\"version\":2,\"kind\":\"record_account\",\"label\":\"\",\"text\":\"Line\\n\\t\\\"q\\\"\\u0001\u{7f}é\",\"citations\":[{},{}]}},\n\
             {{\"id\":\"e3\",\"version\":2,\"kind\":\"record_observation\",\"label\":\"gone\",\"unproduced\":{{\"sha256\":\"{}\",\"size\":120,\"failure\":\"damaged\"}}}},\n\
             {{\"id\":\"e4\",\"version\":2,\"kind\":\"record_artifact\",\"label\":\"trace\",\"encoding\":\"utf-8\",\"member\":\"artifact-e4.bin\",\"size\":120,\"sha256\":\"{}\"}}]}}\n",
            c[0].to_j().string(),
            c[1].to_j().string(),
            "a".repeat(64),
            "a".repeat(64),
        );
        assert_eq!(String::from_utf8(b.clone()).unwrap(), want);
        assert_eq!(answer_revision(&b), Some(7));
        assert_eq!(
            answer_json(3, &[]),
            b"{\"schema\":\"stewart.answer/1\",\"revision\":3,\"entries\":[]}\n"
        );
        assert!(json::parse(&b).is_ok());
    }
}
