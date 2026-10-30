//! Re-entry: `what_am_i_working_with(page?)` (INTERFACE 7.5). It reports
//! recorded facts, never what the auditor has read or concluded, and no
//! mutation requires it.

use super::common::{
    Ctx, Item, Out, cursor_position, invalid_cursor, payload_head, refused, selection,
};
use super::{PREVIEW_BYTES, REENTRY_ENTRIES_PER_PAGE, REENTRY_RECEIPTS, input};
use crate::archive::Fail;
use crate::bodies::Action;
use crate::ids;
use crate::json::{J, Json};
use crate::names;
use crate::reply::ToolNext;
use crate::runs;

fn entry_j(ctx: &Ctx, i: &Item) -> J {
    let binary = i.is_binary();
    let (preview, complete, problem) = if binary {
        (None, false, None)
    } else {
        match payload_head(ctx.audit, &i.payload, PREVIEW_BYTES as u64 + 3) {
            Ok(b) => {
                let cut = super::common::floor_boundary(&b, PREVIEW_BYTES.min(b.len()));
                let whole = b.len() as u64 == i.payload.size && cut == b.len();
                (
                    Some(String::from_utf8_lossy(&b[..cut]).into_owned()),
                    whole,
                    None,
                )
            }
            Err(f) => (None, false, Some(f)),
        }
    };
    J::obj()
        .with("id", i.id.as_str())
        .with("entry", i.handle(ctx.audit))
        .with("kind", i.kind.as_str())
        .with("label", i.label.as_str())
        .with("encoding", i.encoding.as_deref())
        .with("size", i.payload.size)
        .with("preview", preview)
        .with("preview_complete", complete)
        .with("problem", problem)
}

/// The 16 most recent `entry` records across placements, newest first.
fn receipts(ctx: &Ctx) -> J {
    let state = &ctx.state;
    let handle_of = |id: &str, version: u64| {
        state
            .version_created(id, version)
            .map(|c| ids::entry_handle(ctx.store(), ctx.audit_id(), id, version, &c.record.sha256))
    };
    let mut out = Vec::new();
    for (r, e) in state
        .entries()
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .take(REENTRY_RECEIPTS)
    {
        let target = e.target.as_ref().and_then(|t| handle_of(&t.id, t.version));
        let entry = e
            .created
            .as_ref()
            .map(|v| ids::entry_handle(ctx.store(), ctx.audit_id(), &v.id, v.version, &r.sha256));
        out.push(
            J::obj()
                .with("run", e.invocation.run)
                .with("tool_use_id", e.invocation.tool_use_id.as_str())
                .with("tool", e.tool.as_str())
                .with("action", e.action.name())
                .with("target", target)
                .with("entry", entry)
                .with("revision", e.revision),
        );
    }
    let _ = Action::Add;
    J::Arr(out)
}

/// For each tool of the arrangement, the latest refused or failed result
/// record across placements (other than a replay), newest first; and each
/// result record that could not be read.
fn refusals_and_gaps(ctx: &Ctx) -> (J, J) {
    let tools = &ctx.world.arrangement.tool_names;
    let mut latest: Vec<((u64, u64), J, String)> = Vec::new();
    let mut gaps = Vec::new();
    for p in ctx.state.placements() {
        let Ok(dir) = runs::open(ctx.audit, p.run) else {
            continue;
        };
        let Ok(listing) = runs::list(&dir) else {
            gaps.push(
                J::obj()
                    .with("run", p.run)
                    .with("call", J::Null)
                    .with("problem", "the run directory cannot be listed"),
            );
            continue;
        };
        for c in listing.results {
            match runs::read_result(ctx.audit, &dir, c) {
                Err(problem) => gaps.push(
                    J::obj()
                        .with("run", p.run)
                        .with("call", c)
                        .with("problem", problem),
                ),
                Ok(r) => {
                    let Some(tool) = r.tool.clone().filter(|t| tools.contains(t)) else {
                        continue;
                    };
                    if r.outcome == "completed" || r.replay_of.is_some() {
                        continue;
                    }
                    let j = J::obj()
                        .with("run", p.run)
                        .with("tool_use_id", r.tool_use_id.as_str())
                        .with("tool", tool.as_str())
                        .with("outcome", r.outcome.as_str())
                        .with("reason", r.reason.as_deref())
                        .with("revision", r.revision);
                    latest.retain(|(_, _, t)| *t != tool);
                    latest.push(((p.run, c), j, tool));
                }
            }
        }
    }
    latest.sort_by_key(|x| std::cmp::Reverse(x.0));
    (
        J::Arr(latest.into_iter().map(|(_, j, _)| j).collect()),
        J::Arr(gaps),
    )
}

fn page_cursor(ctx: &Ctx, revision: u64, pos: usize) -> String {
    ctx.handle(
        "pg",
        &format!("pg.{pos}"),
        &[&revision.to_string(), &pos.to_string()],
    )
}

pub fn what_am_i_working_with(ctx: &Ctx, v: &Json) -> Out {
    match inner(ctx, v) {
        Ok(o) => o,
        Err(f) => f.into(),
    }
}

fn inner(ctx: &Ctx, v: &Json) -> Result<Out, Fail> {
    let o = input::object(v, &["page"], &[])?;
    let revision = ctx.state.revision();
    let mut sel = selection(ctx.audit, &ctx.state, u64::MAX, Some(ctx.placement));
    if crate::sabotage!("reentry_omit_entry") {
        // Sabotage control: the last current entry is left out.
        sel.pop();
    }
    let start = match input::opt_str(&o, "page")? {
        None => 0,
        Some(c) => {
            let pos = cursor_position(c, "pg").and_then(|p| {
                if p == "0" {
                    Some(0)
                } else {
                    names::parse_num(p).map(|n| n as usize)
                }
            });
            match pos {
                Some(p) if p <= sel.len() && page_cursor(ctx, revision, p) == c => p,
                Some(p) if (0..revision).any(|r| page_cursor(ctx, r, p) == c) => {
                    if crate::sabotage!("reentry_mix_revisions") {
                        // Sabotage control: a cursor bound to an earlier
                        // revision serves the current one.
                        p.min(sel.len())
                    } else {
                        return Ok(Out::fail(
                            refused(
                                "stale_view",
                                format!("The answer changed since this page was listed (it is now at revision {revision}); start again from the first page."),
                            )
                            .data(J::obj().with("revision_now", revision)),
                        )
                        .next(ToolNext::new(
                            "what_am_i_working_with",
                            J::obj(),
                            "Start again from the first page.",
                        )));
                    }
                }
                _ => return Err(invalid_cursor(c)),
            }
        }
    };
    let total = sel.len();
    let mut end = (start + REENTRY_ENTRIES_PER_PAGE).min(total);
    let mut complete = end == total;
    if crate::sabotage!("reentry_truncate_page") {
        // Sabotage control: a page stops after 32 entries and claims to be the last.
        end = (start + 32).min(total);
        complete = true;
    }
    if crate::sabotage!("reentry_omit_last_page")
        && !complete
        && end + REENTRY_ENTRIES_PER_PAGE >= total
    {
        // Sabotage control: the page before the last claims to be the last.
        complete = true;
    }
    let entries = J::Arr(sel[start..end].iter().map(|i| entry_j(ctx, i)).collect());
    let page = J::obj()
        .with("bound_revision", revision)
        .with("returned", end - start)
        .with("total", total)
        .with("complete", complete);
    let data = if start > 0 {
        J::obj().with("entries", entries).with("page", page)
    } else {
        let state = &ctx.state;
        let (condition, sealed_by) = match (state.seal(), state.close_requested()) {
            (Some((_, s)), _) => ("sealed", Some(s.actor.name())),
            (None, Some(_)) => ("closed", None),
            (None, None) => ("open", None),
        };
        let mut used = ctx.placement.used;
        if crate::sabotage!("reentry_placement_allowances") {
            // Sabotage control: this placement's usage instead of the audit's.
            let earlier = state.recorded_usage();
            let minus = |a: u64, b: u64| a.saturating_sub(b);
            used.turns.reported = minus(used.turns.reported, earlier.turns.reported);
            used.turns.estimated = minus(used.turns.estimated, earlier.turns.estimated);
            used.input_tokens.reported =
                minus(used.input_tokens.reported, earlier.input_tokens.reported);
            used.input_tokens.estimated =
                minus(used.input_tokens.estimated, earlier.input_tokens.estimated);
            used.output_tokens.reported =
                minus(used.output_tokens.reported, earlier.output_tokens.reported);
            used.output_tokens.estimated = minus(
                used.output_tokens.estimated,
                earlier.output_tokens.estimated,
            );
        }
        let (latest, gaps) = refusals_and_gaps(ctx);
        let q = &ctx.world.question;
        J::obj()
            .with("audit", ctx.audit_id())
            .with("condition", condition)
            .with("sealed_by", sealed_by)
            .with("revision", revision)
            .with(
                "run",
                J::obj()
                    .with("number", ctx.placement.run)
                    .with("continuing", ctx.placement.continuing),
            )
            .with("allowances", ctx.placement.limits.allowances_j(&used))
            .with(
                "notices_used",
                J::obj()
                    .with("reminder", ctx.placement.notices_used.reminder)
                    .with("near_limit", ctx.placement.notices_used.near_limit),
            )
            .with(
                "question",
                J::obj()
                    .with("source", "question")
                    .with("size", q.size)
                    .with("lines", q.lines),
            )
            .with(
                "materials",
                J::obj()
                    .with("count", ctx.world.materials.len())
                    .with("bytes", ctx.world.material_bytes()),
            )
            .with("entries", entries)
            .with("receipts", receipts(ctx))
            .with("latest_refusals", latest)
            .with("gaps", gaps)
            .with("page", page)
    };
    let mut out = Out::done(data).next(ToolNext::new("list", J::obj(), "List the materials."));
    if !complete {
        out = out.next(ToolNext::new(
            "what_am_i_working_with",
            J::obj().with("page", page_cursor(ctx, revision, end)),
            "Show the next page of entries.",
        ));
    }
    Ok(out)
}
