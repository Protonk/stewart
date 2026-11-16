//! Evidence about echoed tool replies, separate from usage and lifecycle.
//! Originals remain in the ordinary captures; this observer never opens a
//! harness-reported path or treats the auxiliary result copy as conversation.
use super::wire::Value;
use crate::{
    archive::Audit,
    json::{self, J, V},
    log, util,
};
use std::collections::{BTreeMap, BTreeSet};

pub const SCHEMA: &str = "stewart.claude-code.fidelity/1";
pub const FILE: &str = "runtime-fidelity.json";
pub const REASON: &str = "runtime_reply_mismatch";

fn canonical(raw: &[u8]) -> Option<Vec<u8>> {
    fn ordered(v: &json::Json) -> J {
        match &v.v {
            V::Obj(m) => J::Obj(
                m.iter()
                    .map(|(k, v)| (k.clone(), ordered(v)))
                    .collect::<BTreeMap<_, _>>()
                    .into_iter()
                    .collect(),
            ),
            V::Arr(a) => J::Arr(a.iter().map(ordered).collect()),
            _ => v.to_j(),
        }
    }
    Some(ordered(&json::parse(raw).ok()?).bytes())
}
fn optional_text(v: Value<'_>, name: &str) -> Result<Option<String>, String> {
    v.field(name)?.map(|x| x.string()).transpose()
}
#[derive(Clone)]
struct Witness {
    session: Option<String>,
    name: String,
    arguments: Vec<u8>,
}
impl Witness {
    fn read(v: Value<'_>, session: Option<String>, name: &str, arguments: &str) -> Option<Self> {
        Some(Self {
            session,
            name: v.text(name).ok()?,
            arguments: canonical(v.req(arguments).ok()?.bytes())?,
        })
    }
}
#[derive(Clone)]
struct Echo {
    session: Option<String>,
    content: Option<Vec<u8>>,
    text: Option<String>,
    error: Option<bool>,
    reference: J,
}
struct Supplied {
    call: u64,
    id: Option<String>,
    witness: Option<Witness>,
    content: Vec<u8>,
    error: bool,
    single_text: Option<String>,
    result_sha256: String,
    diagnosed: bool,
}
#[derive(Default)]
pub struct Observer {
    session: Option<String>,
    assistant: BTreeMap<String, Vec<Option<Witness>>>,
    hooks: BTreeMap<String, Vec<Option<Witness>>>,
    echoes: BTreeMap<String, Vec<Echo>>,
    unidentified: u64,
    supplied: Vec<Supplied>,
    supplied_ids: BTreeMap<String, Vec<usize>>,
    changed: BTreeSet<String>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Verdict {
    Exact,
    Mismatch,
    Unknown,
}

impl Observer {
    pub fn hook(&mut self, raw: &[u8], admitted: bool) {
        let Ok(v) = Value::parse(raw) else { return };
        let Ok(id) = v.text("tool_use_id") else {
            return;
        };
        let witness = if admitted && v.text("hook_event_name").as_deref() == Ok("PreToolUse") {
            optional_text(v, "session_id")
                .ok()
                .and_then(|session| Witness::read(v, session, "tool_name", "tool_input"))
        } else {
            None
        };
        self.changed.insert(id.clone());
        self.hooks.entry(id).or_default().push(witness);
    }

    /// Called for every complete stdout frame, including frames drained after
    /// submission. Offset and digest refer to the original frame, including LF.
    pub fn stdout(&mut self, raw: &[u8], offset: u64) {
        let Ok(v) = Value::parse(raw) else { return };
        let Ok(kind) = v.text("type") else { return };
        let session = optional_text(v, "session_id");
        if kind == "system" && v.text("subtype").as_deref() == Ok("init") {
            self.session = session.ok().flatten();
            return;
        }
        if kind != "assistant" && kind != "user" {
            return;
        }
        let Ok(blocks) = v
            .req("message")
            .and_then(|m| m.req("content"))
            .and_then(|c| c.array())
        else {
            return;
        };
        for (index, block) in blocks.into_iter().enumerate() {
            if kind == "assistant" && block.text("type").as_deref() == Ok("tool_use") {
                if let Ok(id) = block.text("id") {
                    self.changed.insert(id.clone());
                    let witness = session
                        .clone()
                        .ok()
                        .and_then(|s| Witness::read(block, s, "name", "input"));
                    self.assistant.entry(id).or_default().push(witness);
                }
            } else if kind == "user" && block.text("type").as_deref() == Ok("tool_result") {
                let Ok(id) = block.text("tool_use_id") else {
                    self.unidentified += 1;
                    continue;
                };
                self.changed.insert(id.clone());
                let content = block.req("content").ok();
                self.echoes.entry(id).or_default().push(Echo {
                    session: session.clone().ok().flatten(),
                    content: if session.is_ok() {
                        content.and_then(|c| canonical(c.bytes()))
                    } else {
                        None
                    },
                    text: content.and_then(|c| c.string().ok()),
                    error: block
                        .field("is_error")
                        .and_then(|v| v.map(|v| v.boolean()).transpose())
                        .map(|v| v.unwrap_or(false))
                        .ok(),
                    reference: J::obj()
                        .with("offset", offset)
                        .with("length", raw.len() as u64)
                        .with("sha256", util::sha256_hex(raw))
                        .with("block_index", index as u64),
                });
            }
        }
    }

    pub fn supplied(
        &mut self,
        call: u64,
        request: &[u8],
        content: &[u8],
        error: bool,
        result: &[u8],
    ) {
        let params = Value::parse(request)
            .ok()
            .and_then(|v| v.req("params").ok());
        let id = params
            .and_then(|p| p.req("_meta").ok())
            .and_then(|m| m.text("claudecode/toolUseId").ok());
        let witness = params
            .and_then(|p| Witness::read(p, None, "name", "arguments"))
            .map(|mut w| {
                w.name = super::surface::tool_name(&w.name);
                w
            });
        let single_text = (|| {
            let v = Value::parse(content).ok()?.array().ok()?;
            if v.len() != 1 || v[0].text("type").ok()? != "text" {
                return None;
            }
            // Flattening must not discard additional members of the block.
            let text = v[0].text("text").ok()?;
            let plain = J::Arr(vec![
                J::obj().with("type", "text").with("text", text.as_str()),
            ]);
            (canonical(content)? == canonical(&plain.bytes())?).then_some(text)
        })();
        if let Some(id) = &id {
            self.changed.insert(id.clone());
            self.supplied_ids
                .entry(id.clone())
                .or_default()
                .push(self.supplied.len());
        }
        self.supplied.push(Supplied {
            call,
            id,
            witness,
            content: canonical(content).unwrap_or_default(),
            error,
            single_text,
            result_sha256: util::sha256_hex(result),
            diagnosed: false,
        });
    }

    fn verdict(&self, supplied: &Supplied) -> Verdict {
        let Some(id) = &supplied.id else {
            return Verdict::Unknown;
        };
        if self.supplied_ids.get(id).map(Vec::len) != Some(1) {
            return Verdict::Unknown;
        }
        let Some(expected) = &supplied.witness else {
            return Verdict::Unknown;
        };
        let one = |map: &BTreeMap<String, Vec<Option<Witness>>>| {
            map.get(id)
                .filter(|v| v.len() == 1)
                .and_then(|v| v[0].clone())
        };
        let (Some(assistant), Some(hook), Some(echo)) = (
            one(&self.assistant),
            one(&self.hooks),
            self.echoes.get(id).filter(|v| v.len() == 1).map(|v| &v[0]),
        ) else {
            return Verdict::Unknown;
        };
        let sessions = [
            self.session.as_deref(),
            assistant.session.as_deref(),
            hook.session.as_deref(),
            echo.session.as_deref(),
        ];
        let session = sessions.into_iter().flatten().next();
        if session.is_none()
            || sessions.into_iter().flatten().any(|s| Some(s) != session)
            || [assistant, hook]
                .iter()
                .any(|w| w.name != expected.name || w.arguments != expected.arguments)
        {
            return Verdict::Unknown;
        }
        let (Some(content), Some(error)) = (&echo.content, echo.error) else {
            return Verdict::Unknown;
        };
        if error == supplied.error
            && (content == &supplied.content
                || (error && echo.text.is_some() && echo.text == supplied.single_text))
        {
            Verdict::Exact
        } else {
            Verdict::Mismatch
        }
    }

    /// Returns each new mismatch once. Calling code closes the publication
    /// gate before persisting these contexts; later ambiguity cannot undo it.
    pub fn mismatches(&mut self, run: u64, phase: &str) -> Vec<J> {
        let indexes: Vec<_> = std::mem::take(&mut self.changed)
            .iter()
            .filter_map(|id| {
                self.supplied_ids
                    .get(id)
                    .filter(|v| v.len() == 1)
                    .map(|v| v[0])
            })
            .filter(|i| {
                !self.supplied[*i].diagnosed
                    && self.verdict(&self.supplied[*i]) == Verdict::Mismatch
            })
            .collect();
        indexes
            .into_iter()
            .map(|i| {
                let s = &mut self.supplied[i];
                s.diagnosed = true;
                let id = s.id.as_ref().unwrap();
                J::obj()
                    .with("run", run)
                    .with("call", s.call)
                    .with("tool_use_id", id.as_str())
                    .with("phase", phase)
                    .with("seal_record", J::Null)
                    .with(
                        "expected_result",
                        J::obj()
                            .with("path", format!("runs/{run}/result-{}.json", s.call))
                            .with("sha256", s.result_sha256.as_str()),
                    )
                    .with("observed_stdout", self.echoes[id][0].reference.clone())
            })
            .collect()
    }

    pub fn report(&self, run: u64, capture_complete: bool) -> Report {
        let mut r = Report {
            run,
            supplied: self.supplied.len() as u64,
            capture_complete,
            ..Report::default()
        };
        for s in &self.supplied {
            match self.verdict(s) {
                Verdict::Exact => r.exact += 1,
                Verdict::Mismatch => r.mismatch += 1,
                Verdict::Unknown => r.unknown += 1,
            }
        }
        r.unmatched = self.unidentified
            + self
                .echoes
                .iter()
                .filter(|(id, _)| self.supplied_ids.get(*id).map(Vec::len) != Some(1))
                .map(|(_, v)| v.len() as u64)
                .sum::<u64>();
        r
    }
}

#[derive(Default, Debug, PartialEq, Eq)]
pub struct Report {
    pub run: u64,
    pub supplied: u64,
    pub exact: u64,
    pub mismatch: u64,
    pub unknown: u64,
    pub unmatched: u64,
    pub capture_complete: bool,
}
impl Report {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("schema", SCHEMA)
            .with("run", self.run)
            .with("supplied", self.supplied)
            .with("exact", self.exact)
            .with("mismatch", self.mismatch)
            .with("unknown", self.unknown)
            .with("unmatched", self.unmatched)
            .with("capture_complete", self.capture_complete)
    }
    pub fn decode(raw: &[u8], run: u64) -> Result<Self, String> {
        let parsed = json::parse(raw).map_err(|e| e.to_string())?;
        let o = parsed.obj("").map_err(|e| e.to_string())?;
        o.exactly(&[
            "schema",
            "run",
            "supplied",
            "exact",
            "mismatch",
            "unknown",
            "unmatched",
            "capture_complete",
        ])
        .map_err(|e| e.to_string())?;
        let n = |key| {
            o.u64(key, crate::usage::FIGURE_MAX)
                .map_err(|e| e.to_string())
        };
        let r = Self {
            run: n("run")?,
            supplied: n("supplied")?,
            exact: n("exact")?,
            mismatch: n("mismatch")?,
            unknown: n("unknown")?,
            unmatched: n("unmatched")?,
            capture_complete: o.bool("capture_complete").map_err(|e| e.to_string())?,
        };
        if o.str("schema").map_err(|e| e.to_string())? != SCHEMA
            || r.run == 0
            || r.run != run
            || r.exact
                .checked_add(r.mismatch)
                .and_then(|n| n.checked_add(r.unknown))
                != Some(r.supplied)
        {
            return Err("invalid reply-fidelity schema, placement or counts".into());
        }
        Ok(r)
    }
}

/// Append observations without changing the manager reply shape or lifecycle.
pub fn present(
    audit: &Audit,
    state: &log::LogState,
    summary: &mut String,
    diagnostics: &mut Vec<J>,
) {
    let mut runtime = false;
    for p in state
        .placements()
        .iter()
        .filter(|p| p.start.runtime.is_some())
    {
        runtime = true;
        let path = format!("runs/{}/{}", p.run, FILE);
        let report = read_report(audit, p.run);
        match report {
            Ok(r) => {
                summary.push_str(&format!("\nRun {} reply fidelity: {} supplied; {} exact, {} mismatch, {} unknown; {} unmatched echoes.{}", r.run,r.supplied,r.exact,r.mismatch,r.unknown,r.unmatched,
                    if r.capture_complete { " These are captured conversation observations, not provider completeness." } else { " Capture is incomplete; reply fidelity remains partly unknown." }));
                if !r.capture_complete || r.unknown > 0 || r.unmatched > 0 || r.mismatch > 0 {
                    diagnostics.push(J::obj().with("record", path).with("cause", "Reply fidelity contains mismatched or unknown evidence; see the observed counts in the summary."));
                }
                if r.mismatch > 0 {
                    summary.push_str(&format!("\nWarning: a runtime reply mismatch was observed (runs/{}/{}). Review the original captures before any explicit continuation; published effects and seals remain unchanged.",r.run,FILE));
                }
            }
            Err(e) => {
                summary.push_str(&format!("\nRun {} reply fidelity is unknown: its final observation is missing or unreadable.",p.run));
                diagnostics.push(
                    J::obj()
                        .with("record", path)
                        .with("cause", format!("Reply fidelity is unknown: {e}")),
                );
            }
        }
    }
    if !runtime {
        return;
    }
    for d in crate::ops::status::recorded_diagnostics(audit)
        .into_iter()
        .filter(|d| matches!(d.get("reason"),Some(J::Str(s)) if s==REASON))
    {
        let record = match d.get("record") {
            Some(J::Str(s)) => s.as_str(),
            _ => "diag",
        };
        summary.push_str(&format!("\nWarning: a runtime reply mismatch was observed ({record}). Published effects and any seal remain unchanged; review this diagnostic before an explicit continuation."));
        if !diagnostics
            .iter()
            .any(|old| old.get("record") == d.get("record"))
        {
            diagnostics.push(d);
        }
    }
}

fn read_report(audit: &Audit, run: u64) -> Result<Report, String> {
    crate::runs::open(audit, run)
        .map_err(|e| e.to_string())
        .and_then(|d| {
            d.read_regular(FILE, 4096)
                .map(|(b, _)| b)
                .map_err(|e| e.describe())
        })
        .and_then(|b| Report::decode(&b, run))
}

#[cfg(test)]
mod tests {
    use super::*;

    const REQUEST: &[u8] = br#"{"params":{"name":"read","arguments":{"source":"materials/a","start":0},"_meta":{"claudecode/toolUseId":"tool-1"}}}"#;
    const ASSISTANT: &[u8] = br#"{"type":"assistant","session_id":"session","message":{"id":"shared-message","content":[{"type":"tool_use","id":"tool-1","name":"mcp__stewart__read","input":{"start":0,"source":"materials/a"}}]}}"#;
    const HOOK: &[u8] = br#"{"session_id":"session","hook_event_name":"PreToolUse","tool_use_id":"tool-1","tool_name":"mcp__stewart__read","tool_input":{"source":"materials/a","start":0}}"#;

    fn setup(content: &[u8], error: bool) -> Observer {
        let mut o = Observer::default();
        o.stdout(
            br#"{"type":"system","subtype":"init","session_id":"session"}"#,
            0,
        );
        o.stdout(ASSISTANT, 100);
        o.hook(HOOK, true);
        o.supplied(1, REQUEST, content, error, b"original result record");
        o
    }
    fn block(content: J, error: Option<bool>) -> J {
        let mut b = J::obj()
            .with("type", "tool_result")
            .with("tool_use_id", "tool-1")
            .with("content", content);
        if let Some(error) = error {
            b.push("is_error", error);
        }
        b
    }
    fn user(blocks: Vec<J>) -> Vec<u8> {
        let mut raw = J::obj()
            .with("type", "user")
            .with("session_id", "session")
            .with("message", J::obj().with("content", J::Arr(blocks)))
            // A plausible auxiliary copy is deliberately unrelated.
            .with(
                "tool_use_result",
                J::Arr(vec![
                    J::obj().with("type", "text").with("text", "auxiliary"),
                ]),
            )
            .bytes();
        raw.push(b'\n');
        raw
    }
    fn content(text: &str) -> J {
        J::Arr(vec![J::obj().with("type", "text").with("text", text)])
    }

    #[test]
    fn exact_page_and_changed_middle_with_tail_invariance() {
        let page = format!("{}TAIL-LABEL: unchanged\n", "x".repeat(65515));
        let expected = content(&page);
        for (changed, wanted) in [(false, (1, 0)), (true, (0, 1))] {
            let mut o = setup(&expected.bytes(), false);
            let text = if changed {
                page.replacen('x', "y", 1)
            } else {
                page.clone()
            };
            o.stdout(&user(vec![block(content(&text), None)]), 999);
            let r = o.report(1, true);
            assert_eq!((r.exact, r.mismatch), wanted);
            assert_eq!(r.unknown, 0);
        }
    }
    #[test]
    fn decoded_objects_and_error_flattening_have_distinct_controls() {
        let expected = br#"[{"type":"text","text":"refusal\nexact"}]"#;
        for (is_error, flat, flag, wanted) in [
            (true, true, true, true),
            (true, true, false, false),
            (false, true, false, false),
            (false, false, false, true),
            (false, false, true, false),
        ] {
            let mut o = setup(expected, is_error);
            let value = if flat {
                J::Str("refusal\nexact".into())
            } else {
                J::Raw(br#"[ {"text":"refusal\u000aexact", "type":"text"} ]"#.to_vec())
            };
            o.stdout(&user(vec![block(value, Some(flag))]), 50);
            assert_eq!(o.report(1, true).exact, u64::from(wanted));
            assert_eq!(o.report(1, true).mismatch, u64::from(!wanted));
        }
    }
    #[test]
    fn missing_duplicate_and_contradictory_witnesses_are_unknown() {
        let expected = content("original");
        for change in [
            "absent",
            "duplicate-echo",
            "duplicate-assistant",
            "denied-hook",
            "wrong-arguments",
            "wrong-session",
            "duplicate-mcp",
        ] {
            let mut o = setup(&expected.bytes(), false);
            if change != "absent" {
                let mut blocks = vec![block(content("changed"), None)];
                if change == "duplicate-echo" {
                    blocks.push(block(expected.clone(), None));
                }
                let mut frame = user(blocks);
                if change == "wrong-session" {
                    frame = String::from_utf8(frame)
                        .unwrap()
                        .replace("\"session\"", "\"other\"")
                        .into_bytes();
                }
                o.stdout(&frame, 500);
            }
            match change {
                "duplicate-assistant" => o.stdout(ASSISTANT, 400),
                "denied-hook" => {
                    o.hooks.clear();
                    o.hook(HOOK, false);
                }
                "wrong-arguments" => {
                    o.hooks.clear();
                    o.hook(
                        &String::from_utf8(HOOK.to_vec())
                            .unwrap()
                            .replace("materials/a", "materials/b")
                            .into_bytes(),
                        true,
                    );
                }
                "duplicate-mcp" => o.supplied(2, REQUEST, &expected.bytes(), false, b"second"),
                _ => (),
            }
            assert!(o.mismatches(1, "live").is_empty(), "{change}");
            let r = o.report(1, true);
            assert_eq!(r.exact + r.mismatch, 0, "{change}");
            assert_eq!(r.unknown, r.supplied, "{change}");
        }
    }
    #[test]
    fn late_echo_references_original_frame_and_ambiguity_cannot_erase_stop() {
        let mut o = setup(&content("original").bytes(), false);
        assert!(o.mismatches(3, "live").is_empty());
        let raw = user(vec![block(content("changed"), None)]);
        o.stdout(&raw, 800);
        let d = o.mismatches(3, "drain");
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].get("phase"), Some(&J::Str("drain".into())));
        assert_eq!(
            d[0].get("expected_result").unwrap().get("sha256"),
            Some(&J::Str(util::sha256_hex(b"original result record")))
        );
        assert_eq!(
            d[0].get("observed_stdout"),
            Some(
                &J::obj()
                    .with("offset", 800u64)
                    .with("length", raw.len() as u64)
                    .with("sha256", util::sha256_hex(&raw))
                    .with("block_index", 0u64)
            )
        );
        o.stdout(&raw, 800 + raw.len() as u64);
        assert_eq!(o.report(3, true).unknown, 1);
        assert!(o.supplied[0].diagnosed);
        assert!(o.mismatches(3, "drain").is_empty());
    }
    #[test]
    fn unpaired_echoes_and_incomplete_capture_never_become_exact() {
        let mut o = Observer::default();
        o.stdout(&user(vec![block(content("unpaired"), None)]), 0);
        let r = o.report(1, false);
        assert_eq!(
            (r.supplied, r.exact, r.unmatched, r.capture_complete),
            (0, 0, 1, false)
        );
    }
    #[test]
    fn final_record_is_strict_and_missing_is_not_a_zero_report() {
        let (path, audit) = crate::log::tests::scratch_audit();
        std::fs::create_dir_all(path.join("a/runs/1")).unwrap();
        assert!(read_report(&audit, 1).is_err());
        let r = Report {
            run: 1,
            supplied: 2,
            exact: 1,
            unknown: 1,
            capture_complete: true,
            ..Report::default()
        };
        std::fs::write(path.join("a/runs/1").join(FILE), r.to_j().bytes()).unwrap();
        assert_eq!(read_report(&audit, 1).unwrap(), r);
        for bad in [
            r.to_j()
                .string()
                .replace("\"supplied\":2", "\"supplied\":3"),
            r.to_j().string().replace("\"run\":1", "\"run\":0"),
            r.to_j().string().replace("\"run\":1", "\"run\":2"),
            r.to_j()
                .string()
                .replace("\"run\":1", "\"run\":1,\"extra\":0"),
        ] {
            assert!(Report::decode(bad.as_bytes(), 1).is_err());
        }
        std::fs::write(path.join("a/runs/1").join(FILE), b"{").unwrap();
        assert!(read_report(&audit, 1).is_err());
        std::fs::remove_dir_all(path).unwrap();
    }

    #[test]
    fn manager_observation_preserves_warning_when_final_evidence_is_unknown() {
        let (path, audit) = crate::log::tests::scratch_audit();
        std::fs::create_dir_all(path.join("a/runs/1")).unwrap();
        std::fs::create_dir_all(path.join("a/diag")).unwrap();
        let start = crate::bodies::RunStarted {
            run: 1,
            arrangement_sha256: "0".repeat(64),
            provider: None,
            runtime: Some(super::super::accounting::Start {
                profile_sha256: "0".repeat(64),
                placement_timeout_seconds: 60,
            }),
            observations: crate::bodies::RunObservations::current(),
        };
        let state = log::LogState {
            damage: vec![],
            recs: vec![log::LogRec {
                n: 1,
                kind: "run_started".into(),
                at: "test".into(),
                sha256: "0".repeat(64),
                body: log::Body::RunStarted(start),
                json: json::parse(b"{}").unwrap(),
                ino: (0, 0),
            }],
        };
        let mut summary = String::new();
        let mut diagnostics = vec![];
        present(&audit, &state, &mut summary, &mut diagnostics);
        assert!(summary.contains("reply fidelity is unknown"));
        assert!(!summary.contains("0 exact"));
        audit
            .write_diag(
                J::obj()
                    .with("operation", "run")
                    .with("reason", REASON)
                    .with("message", "A changed reply was observed.")
                    .with(
                        "context",
                        J::obj().with("private", "not copied into summary"),
                    ),
            )
            .unwrap();
        let r = Report {
            run: 1,
            supplied: 2,
            exact: 1,
            unknown: 1,
            capture_complete: false,
            ..Report::default()
        };
        std::fs::write(path.join("a/runs/1").join(FILE), r.to_j().bytes()).unwrap();
        summary.clear();
        diagnostics.clear();
        present(&audit, &state, &mut summary, &mut diagnostics);
        assert!(summary.contains("2 supplied; 1 exact, 0 mismatch, 1 unknown; 0 unmatched"));
        assert!(summary.contains("Capture is incomplete"));
        assert!(summary.contains("Warning: a runtime reply mismatch"));
        assert!(summary.contains("diag/1.json"));
        assert!(!summary.contains("not copied into summary"));
        assert_eq!(diagnostics.len(), 2);
        std::fs::remove_dir_all(path).unwrap();
    }
}
