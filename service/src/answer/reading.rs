//! `list`, `read` and `search` (INTERFACE 7.1, 7.2). Reads and searches are
//! served from the placement's verified captures through the descriptors the
//! world holds, never from the preparation folder.

use super::common::{
    Ctx, Named, Out, blank, boundary, ceil_boundary, cursor_position, floor_boundary,
    invalid_cursor, line_of, lines, pair, read_payload, refused, resolve, source_unknown,
};
use super::{End, b64, input};
use crate::forms::{
    BINARY_PAGE_BYTES, CONTEXT_BYTES_PER_HIT, LIST_PAGE_MATERIALS, READ_PAGE_BYTES,
    SEARCH_CONTEXT_BYTES_PER_PAGE, SEARCH_HITS_PER_PAGE, SEARCH_SOURCES, SEARCH_TEXT_BYTES,
};
use crate::ids;
use crate::json::{self, J, Json};
use crate::reply::ToolNext;
use crate::util;

/// The longest source name a `read` accepts.
const SOURCE_BYTES: usize = 1_034;

fn position(s: &str) -> Option<usize> {
    if s == "0" {
        return Some(0);
    }
    crate::names::parse_num(s).map(|n| n as usize)
}

// ---------------------------------------------------------------------------
// list

pub fn list(ctx: &Ctx, v: &Json) -> Out {
    match list_inner(ctx, v) {
        Ok(o) => o,
        Err(f) => f.into(),
    }
}

fn list_inner(ctx: &Ctx, v: &Json) -> Result<Out, crate::archive::Fail> {
    let o = input::object(v, &["cursor"], &[])?;
    let cursor = input::opt_str(&o, "cursor")?;
    let total = ctx.world.materials.len();
    let index = ctx.world.arrangement.material_index_sha256.clone();
    let cursor_for =
        |pos: usize| ctx.handle("ls", &format!("ls.{pos}"), &[&index, &pos.to_string()]);
    let start = match cursor {
        None => 0,
        Some(c) => match cursor_position(c, "ls").and_then(position) {
            Some(pos) if pos <= total && cursor_for(pos) == c => pos,
            _ => return Err(invalid_cursor(c)),
        },
    };
    let end = (start + LIST_PAGE_MATERIALS as usize).min(total);
    if crate::sabotage!("slow_list") {
        // Sabotage control: the reply is delayed.
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    let complete = end == total;
    let data = J::obj()
        .with(
            "materials",
            J::Arr(
                ctx.world.materials[start..end]
                    .iter()
                    .map(|m| {
                        J::obj()
                            .with("source", m.name.as_str())
                            .with("size", m.size)
                            .with("lines", m.lines)
                    })
                    .collect(),
            ),
        )
        .with("directories", json::strs(&ctx.world.directories))
        .with("returned", end - start)
        .with("total", total)
        .with("complete", complete);
    let mut out = Out::done(data);
    if !complete {
        out = out.next(ToolNext::new(
            "list",
            J::obj().with("cursor", cursor_for(end)),
            "List the next page of materials.",
        ));
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// read

pub fn read(ctx: &Ctx, v: &Json) -> Out {
    match read_inner(ctx, v) {
        Ok(o) => o,
        Err(f) => f.into(),
    }
}

fn range_invalid(start: u64, b: &[u8]) -> crate::archive::Fail {
    let size = b.len() as u64;
    let (lower, upper) = if start > size {
        (size, None)
    } else {
        (
            floor_boundary(b, start as usize) as u64,
            Some(ceil_boundary(b, start as usize) as u64),
        )
    };
    let nearest: Vec<J> = std::iter::once(lower).chain(upper).map(J::Int).collect();
    refused(
        "range_invalid",
        if start > size {
            format!("start {start} is past the end of this {size}-byte source; the nearest start is {lower}.")
        } else {
            format!(
                "start {start} is inside a UTF-8 character; the nearest boundaries are {lower} and {}.",
                upper.unwrap_or(lower)
            )
        },
    )
    .data(
        J::obj()
            .with("start", start)
            .with("size", size)
            .with("nearest", J::Arr(nearest)),
    )
}

/// The end of the text page that begins at `start` (7.2): the source's end
/// if that is within 65,536 bytes; else just after the last LF in the
/// window; else the last UTF-8 boundary in it.
pub fn page_end(b: &[u8], start: usize) -> usize {
    let window = (start + READ_PAGE_BYTES as usize).min(b.len());
    if window == b.len() {
        return window;
    }
    match b[start..window].iter().rposition(|c| *c == b'\n') {
        Some(i) => start + i + 1,
        None => floor_boundary(b, window).max(start + 1).min(window),
    }
}

/// How a read page is shown: its data members, its text and its next call.
struct Page {
    data: J,
    text: Option<String>,
    complete: bool,
    end: usize,
}

fn text_page(
    source: &str,
    kind: &str,
    b: &[u8],
    start: u64,
    citable: bool,
) -> Result<Page, crate::archive::Fail> {
    if start > b.len() as u64 || !boundary(b, start as usize) {
        return Err(range_invalid(start, b));
    }
    let start = start as usize;
    let end = page_end(b, start);
    let mut text = String::from_utf8_lossy(&b[start..end]).into_owned();
    if crate::sabotage!("normalize_read") {
        // Sabotage control: CRLF is returned as LF.
        text = text.replace("\r\n", "\n");
    }
    let mut complete = end == b.len();
    if crate::sabotage!("read_truncate_silently") {
        // Sabotage control: a page that ends early claims to be the last.
        complete = true;
    }
    let cite = (citable && start < end).then(|| {
        J::obj()
            .with("source", source)
            .with("start", start)
            .with("end", end)
    });
    let mut data = J::obj()
        .with("source", source)
        .with("kind", kind)
        .with("size", b.len())
        .with("range", pair((start as u64, end as u64)))
        .with("lines", lines(b, start, end).map(pair))
        .with("complete", complete)
        .with("cite", cite);
    let carried = if blank(&text) {
        data.push("text", text);
        None
    } else {
        Some(text)
    };
    Ok(Page {
        data,
        text: carried,
        complete,
        end,
    })
}

fn binary_page(source: &str, b: &[u8], start: u64) -> Result<Page, crate::archive::Fail> {
    if start > b.len() as u64 {
        return Err(range_invalid(start, b));
    }
    let start = start as usize;
    let end = (start + BINARY_PAGE_BYTES as usize).min(b.len());
    let complete = end == b.len();
    let data = J::obj()
        .with("source", source)
        .with("kind", "entry")
        .with("size", b.len())
        .with("range", pair((start as u64, end as u64)))
        .with("lines", J::Null)
        .with("complete", complete)
        .with("cite", J::Null)
        .with("base64", b64::encode(&b[start..end]));
    Ok(Page {
        data,
        text: None,
        complete,
        end,
    })
}

fn finish(ctx: &Ctx, source: &str, mut page: Page, extra: J) -> Out {
    if let J::Obj(m) = extra {
        for (k, v) in m {
            page.data.push(&k, v);
        }
    }
    if crate::sabotage!("leak_custody_path") {
        // Sabotage control: a host path reaches the auditor.
        page.data.push("archive", ctx.audit.archive.path.as_str());
    }
    let mut out = Out::done(page.data);
    out.text = page.text;
    if !page.complete {
        out = out.next(ToolNext::new(
            "read",
            J::obj().with("source", source).with("start", page.end),
            "Read the rest of this source.",
        ));
    }
    out
}

fn read_inner(ctx: &Ctx, v: &Json) -> Result<Out, crate::archive::Fail> {
    let o = input::object(v, &["source", "start"], &["source"])?;
    let source = input::req_str(&o, "source")?;
    if source.is_empty() || source.len() > SOURCE_BYTES {
        return Err(input::invalid_value(
            "/source",
            format!("a source is 1 to {SOURCE_BYTES} bytes"),
        ));
    }
    let start = input::opt_u64(&o, "start")?.unwrap_or(0);
    if let Some(src) = ctx.world.source(source) {
        let mut bytes = src.bytes().map_err(|e| read_failed(ctx, source, &e))?;
        if crate::sabotage!("read_live_source") {
            // Sabotage control: the preparation folder's current file is
            // served instead of the capture.
            let name = if source == "question" {
                "question.md"
            } else {
                source
            };
            if let Ok(live) = std::fs::read(format!("{}/{name}", ctx.audit.refile.folder)) {
                bytes = live;
            }
        }
        let kind = if source == "question" {
            "question"
        } else {
            "material"
        };
        let page = text_page(source, kind, &bytes, start, true)?;
        return Ok(finish(ctx, source, page, J::obj()));
    }
    if let Some((ap, view)) = ids::parse_view(source) {
        let prep = super::prep::load_auditor_prep(ctx, ap)?;
        let bytes = match view {
            ids::View::Rendering => prep.rendering,
            ids::View::Selection => prep.answer,
        };
        let page = text_page(source, "view", &bytes, start, false)?;
        return Ok(finish(ctx, source, page, J::obj()));
    }
    if ids::parse_entry_handle(source).is_none() && ids::parse_ap(source).is_none() {
        return Err(source_unknown(ctx.world, source));
    }
    if ids::parse_ap(source).is_some() {
        return Err(refused(
            "source_unknown",
            format!("{source:?} is a preparation handle; read its views {source}/rendering or {source}/selection."),
        )
        .data(J::obj().with("source", source).with(
            "hints",
            json::strs(&[format!("{source}/rendering"), format!("{source}/selection")]),
        )));
    }
    match resolve(ctx, &ctx.state, source)? {
        Named::Current(item) => {
            let bytes = match read_payload(ctx.audit, &item.payload) {
                Ok(b) => b,
                Err(failure) => {
                    return Ok(Out::fail(
                        refused(
                            "answer_damaged",
                            format!(
                                "The recorded bytes of {} are {failure}; they no longer match what was recorded. The run stops here.",
                                item.id
                            ),
                        )
                        .data(
                            J::obj()
                                .with("entry", source)
                                .with("id", item.id.as_str())
                                .with("failure", failure),
                        ),
                    )
                    .end(End::AnswerDamaged));
                }
            };
            let page = if item.is_binary() {
                binary_page(source, &bytes, start)?
            } else {
                text_page(source, "entry", &bytes, start, false)?
            };
            let mut extra = J::obj()
                .with("entry", source)
                .with("id", item.id.as_str())
                .with("version", item.version)
                .with("entry_kind", item.kind.as_str())
                .with("label", item.label.as_str())
                .with(
                    "citations",
                    match &item.citations {
                        Some(cs) => J::Arr(cs.iter().map(|c| c.to_j()).collect()),
                        None => J::Null,
                    },
                );
            if let Some(enc) = &item.encoding {
                extra.push("artifact_encoding", enc.as_str());
            }
            Ok(finish(ctx, source, page, extra))
        }
        Named::Replaced(cur) => {
            let current = cur.handle(ctx.audit);
            Ok(Out::fail(
                refused(
                    "stale_entry",
                    format!("{source} was replaced; the current version is {current}."),
                )
                .data(
                    J::obj()
                        .with("entry", source)
                        .with("current", current.as_str()),
                ),
            )
            .next(ToolNext::new(
                "read",
                J::obj().with("source", current.as_str()),
                "Read the current version.",
            )))
        }
        Named::Removed(_) => Err(refused(
            "entry_deleted",
            format!("{source} was deleted from the answer."),
        )
        .data(J::obj().with("entry", source))),
    }
}

/// A verified capture that the held descriptor can no longer read.
fn read_failed(ctx: &Ctx, source: &str, e: &std::io::Error) -> crate::archive::Fail {
    let _ = ctx;
    crate::archive::Fail::failed(
        "source_unreadable",
        format!(
            "{source} could not be read from its capture: {}.",
            util::describe(e)
        ),
    )
    .cause(crate::reply::Cause::io("read capture", e))
}

// ---------------------------------------------------------------------------
// search

pub fn search(ctx: &Ctx, v: &Json) -> Out {
    match search_inner(ctx, v) {
        Ok(o) => o,
        Err(f) => f.into(),
    }
}

/// One page of a search: its hits and where the next page begins.
struct Scan {
    hits: Vec<J>,
    /// `(source index, offset)` of the next page, or `None` when complete.
    next: Option<(usize, usize)>,
}

fn context(b: &[u8], start: usize, end: usize) -> J {
    let line_start = b[..start]
        .iter()
        .rposition(|c| *c == b'\n')
        .map_or(0, |i| i + 1);
    let line_end = b[end..]
        .iter()
        .position(|c| *c == b'\n')
        .map_or(b.len(), |i| end + i);
    let max = CONTEXT_BYTES_PER_HIT as usize;
    let (mut ws, mut we) = (line_start, line_end);
    if line_end - line_start > max {
        if end - start >= max {
            ws = start;
            we = start + max;
        } else {
            let pad = (max - (end - start)) / 2;
            ws = start.saturating_sub(pad).max(line_start);
            we = (ws + max).min(line_end);
            ws = we.saturating_sub(max).max(line_start);
        }
        ws = ceil_boundary(b, ws);
        we = floor_boundary(b, we);
    }
    J::obj()
        .with("text", String::from_utf8_lossy(&b[ws..we]).into_owned())
        .with("truncated_before", ws > line_start)
        .with("truncated_after", we < line_end)
}

fn scan(sources: &[(String, Vec<u8>)], text: &[u8], from: (usize, usize)) -> Scan {
    let mut hits = Vec::new();
    let mut ctx_bytes = 0usize;
    for (i, (name, b)) in sources.iter().enumerate().skip(from.0) {
        let mut k = if i == from.0 { from.1 } else { 0 };
        while k + text.len() <= b.len() {
            let Some(off) = b[k..].windows(text.len()).position(|w| w == text) else {
                break;
            };
            let s = k + off;
            let e = s + text.len();
            let c = context(b, s, e);
            let c_len = c.get("text").and_then(|t| match t {
                J::Str(t) => Some(t.len()),
                _ => None,
            });
            let c_len = c_len.unwrap_or(0);
            if hits.len() as u64 >= SEARCH_HITS_PER_PAGE
                || (ctx_bytes + c_len) as u64 > SEARCH_CONTEXT_BYTES_PER_PAGE
            {
                return Scan {
                    hits,
                    next: Some((i, s)),
                };
            }
            ctx_bytes += c_len;
            hits.push(
                J::obj()
                    .with("source", name.as_str())
                    .with("start", s)
                    .with("end", e)
                    .with("line", line_of(b, s))
                    .with("context", c)
                    .with(
                        "cite",
                        J::obj()
                            .with("source", name.as_str())
                            .with("start", s)
                            .with("end", e),
                    ),
            );
            k = s + 1;
        }
    }
    Scan { hits, next: None }
}

fn search_inner(ctx: &Ctx, v: &Json) -> Result<Out, crate::archive::Fail> {
    let o = input::object(v, &["text", "sources", "cursor"], &["text"])?;
    let text = input::req_str(&o, "text")?;
    if text.is_empty() || text.len() as u64 > SEARCH_TEXT_BYTES {
        return Err(input::invalid_value(
            "/text",
            format!("search text is 1 to {SEARCH_TEXT_BYTES} bytes"),
        ));
    }
    let given = input::opt_arr(&o, "sources")?;
    let scope: Vec<String> = match given {
        None => std::iter::once("question".to_string())
            .chain(ctx.world.materials.iter().map(|m| m.name.clone()))
            .collect(),
        Some(items) => {
            if items.len() as u64 > SEARCH_SOURCES {
                return Err(input::invalid_value(
                    "/sources",
                    format!("at most {SEARCH_SOURCES} sources are searched at once"),
                ));
            }
            let mut names = Vec::new();
            for (i, it) in items.iter().enumerate() {
                let name = it.as_str().ok_or_else(|| {
                    input::invalid_value(&format!("/sources/{i}"), "expected a source name")
                })?;
                if ctx.world.source(name).is_none() {
                    return Err(source_unknown(ctx.world, name));
                }
                names.push(name.to_string());
            }
            names
        }
    };
    let text_sha = util::sha256_hex(text.as_bytes());
    let scope_sha = util::sha256_hex(
        scope
            .iter()
            .flat_map(|n| n.bytes().chain(std::iter::once(b'\n')))
            .collect::<Vec<u8>>()
            .as_slice(),
    );
    let cursor_for = |(i, off): (usize, usize)| {
        let pos = format!("{i}-{off}");
        ctx.handle("sc", &format!("sc.{pos}"), &[&text_sha, &scope_sha, &pos])
    };
    let from = match input::opt_str(&o, "cursor")? {
        None => (0, 0),
        Some(c) => {
            let pos = cursor_position(c, "sc").and_then(|p| {
                let (i, off) = p.split_once('-')?;
                Some((position(i)?, position(off)?))
            });
            match pos {
                Some(p) if p.0 < scope.len() && cursor_for(p) == c => p,
                _ => return Err(invalid_cursor(c)),
            }
        }
    };
    let mut sources = Vec::with_capacity(scope.len());
    for name in &scope {
        let src = ctx.world.source(name).expect("checked above");
        sources.push((
            name.clone(),
            src.bytes().map_err(|e| read_failed(ctx, name, &e))?,
        ));
    }
    let page = scan(&sources, text.as_bytes(), from);
    let mut next = page.next;
    if crate::sabotage!("search_omit_last_page") {
        // Sabotage control: the page before the last claims to be the last.
        if let Some(n) = next {
            if scan(&sources, text.as_bytes(), n).next.is_none() {
                next = None;
            }
        }
    }
    let returned = page.hits.len();
    let data = J::obj()
        .with("text", text)
        .with("scope", json::strs(&scope))
        .with("hits", J::Arr(page.hits))
        .with("returned", returned)
        .with("complete", next.is_none());
    let mut out = Out::done(data);
    if let Some(n) = next {
        let mut input = J::obj().with("text", text);
        if given.is_some() {
            input.push("sources", json::strs(&scope));
        }
        input.push("cursor", cursor_for(n));
        out = out.next(ToolNext::new(
            "search",
            input,
            "Continue the search; this page did not cover the whole scope, so it shows no absence.",
        ));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pages_end_at_the_end_a_line_or_a_character() {
        let short = b"abc\ndef";
        assert_eq!(page_end(short, 0), 7);
        let mut long = vec![b'x'; 70_000];
        long[100] = b'\n';
        long[60_000] = b'\n';
        assert_eq!(page_end(&long, 0), 60_001);
        assert_eq!(page_end(&long, 60_001), 70_000);
        // No LF in the window: the last character boundary.
        let mut wide = Vec::new();
        while wide.len() < 70_000 {
            wide.extend_from_slice("é".as_bytes());
        }
        let e = page_end(&wide, 0);
        assert!(e <= 65_536 && e.is_multiple_of(2) && e > 65_530);
    }

    #[test]
    fn context_is_the_line_clipped_around_the_hit() {
        let b = b"first\nsecond line with target here\nthird";
        let c = context(b, 18, 24);
        assert_eq!(
            c.get("text"),
            Some(&J::Str("second line with target here".into()))
        );
        assert_eq!(c.get("truncated_before"), Some(&J::Bool(false)));
        let mut long = vec![b'a'; 1000];
        long[500..506].copy_from_slice(b"needle");
        let c = context(&long, 500, 506);
        let J::Str(t) = c.get("text").unwrap() else {
            panic!()
        };
        assert_eq!(t.len(), 240);
        assert!(t.contains("needle"));
        assert_eq!(c.get("truncated_before"), Some(&J::Bool(true)));
        assert_eq!(c.get("truncated_after"), Some(&J::Bool(true)));
    }

    #[test]
    fn every_occurrence_is_found_including_overlapping_ones() {
        let s = vec![
            ("a".to_string(), b"aaaa".to_vec()),
            ("b".to_string(), b"xaa".to_vec()),
        ];
        let r = scan(&s, b"aa", (0, 0));
        let starts: Vec<(String, u64)> = r
            .hits
            .iter()
            .map(|h| match (h.get("source"), h.get("start")) {
                (Some(J::Str(n)), Some(J::Int(i))) => (n.clone(), *i),
                _ => panic!(),
            })
            .collect();
        assert_eq!(
            starts,
            [
                ("a".into(), 0),
                ("a".into(), 1),
                ("a".into(), 2),
                ("b".into(), 1)
            ]
        );
        assert!(r.next.is_none());
    }
}
