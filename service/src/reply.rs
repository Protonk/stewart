//! The `stewart.reply/1` envelope (INTERFACE 1.3–1.6) and its human presentation.
//!
//! Both presentations are produced from the same `Reply` value; the human one
//! never adds or hides a fact.

use crate::json::J;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    Completed,
    Refused,
    Failed,
}

impl Outcome {
    pub fn name(self) -> &'static str {
        match self {
            Outcome::Completed => "completed",
            Outcome::Refused => "refused",
            Outcome::Failed => "failed",
        }
    }
}

/// One supported next call (manager form): an argv and why.
#[derive(Debug, Clone, PartialEq)]
pub struct Next {
    pub argv: Vec<String>,
    pub why: String,
}

impl Next {
    pub fn new(argv: Vec<String>, why: impl Into<String>) -> Next {
        Next {
            argv,
            why: why.into(),
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("argv", crate::json::strs(&self.argv))
            .with("why", self.why.as_str())
    }
}

/// One supported next call in an auditor reply (1.5): a tool call with its
/// input, and why. Auditor replies never carry manager argv.
#[derive(Debug, Clone, PartialEq)]
pub struct ToolNext {
    pub tool: String,
    pub input: J,
    pub why: String,
}

impl ToolNext {
    pub fn new(tool: impl Into<String>, input: J, why: impl Into<String>) -> ToolNext {
        ToolNext {
            tool: tool.into(),
            input,
            why: why.into(),
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("tool", self.tool.as_str())
            .with("input", self.input.clone())
            .with("why", self.why.as_str())
    }
}

/// One cause of a failure: what operation, and the error observed.
#[derive(Debug, Clone, PartialEq)]
pub struct Cause {
    pub operation: String,
    pub error: String,
    pub path: Option<String>,
}

impl Cause {
    pub fn new(operation: impl Into<String>, error: impl Into<String>) -> Cause {
        Cause {
            operation: operation.into(),
            error: error.into(),
            path: None,
        }
    }
    pub fn at(mut self, path: impl Into<String>) -> Cause {
        self.path = Some(path.into());
        self
    }
    pub fn io(operation: impl Into<String>, e: &std::io::Error) -> Cause {
        Cause::new(operation, crate::util::errno_name(e))
    }
    /// The wire form is `{operation, error}` (INTERFACE 5.4); the location,
    /// when known, is shown to people and kept in `retained`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("operation", self.operation.as_str())
            .with("error", self.error.as_str())
    }
}

#[derive(Debug, Clone)]
pub struct Reply {
    pub operation: &'static str,
    pub outcome: Outcome,
    pub reason: Option<String>,
    pub message: Option<String>,
    /// Effects in their published order (INTERFACE 1.4).
    pub effects: Vec<(&'static str, &'static str)>,
    pub retained: Vec<String>,
    pub causes: Vec<Cause>,
    /// Manager next calls; used by `to_j`.
    pub next: Vec<Next>,
    /// Auditor next calls; used by `auditor_j`.
    pub tool_next: Vec<ToolNext>,
    pub data: Option<J>,
}

/// The closed set of effect values (1.4).
pub const EFFECT_VALUES: [(&str, &[&str]); 11] = [
    ("reference", &["none", "created", "unknown"]),
    ("preparation", &["none", "recorded", "unknown"]),
    ("attempt", &["none", "recorded", "partial", "unknown"]),
    ("acceptance", &["absent", "accepted", "unknown"]),
    (
        "run",
        &["not_started", "started", "ended", "still_held", "unknown"],
    ),
    ("answer", &["unchanged", "changed", "unknown"]),
    ("seal", &["none", "recorded", "existing", "unknown"]),
    (
        "delivery",
        &[
            "none",
            "failed",
            "partial",
            "verified_with_losses",
            "verified",
            "unknown",
        ],
    ),
    (
        "closure",
        &["none", "requested", "unfinished", "complete", "unknown"],
    ),
    ("raw_capture", &["recorded", "failed", "not_applicable"]),
    ("diagnostic", &["durable", "reported_only"]),
];

/// The effect keys each manager operation reports, in order (1.4).
/// `diagnostic` may follow any of them.
pub const MANAGER_EFFECTS: [(&str, &[&str]); 7] = [
    ("new", &["reference"]),
    ("prepare", &["preparation"]),
    ("commission", &["acceptance", "attempt"]),
    ("receipt", &[]),
    ("status", &[]),
    ("run", &["run", "answer", "seal", "delivery"]),
    ("close", &["run", "seal", "delivery", "closure"]),
];

/// The effect keys an auditor tool's reply reports (1.4): the record tools,
/// `replace` and `delete` report `answer` and `raw_capture`; `submit`
/// reports `seal` and `raw_capture`; every other tool, including a name no
/// tool has, reports `raw_capture`.
pub fn auditor_effect_keys(tool: &str) -> &'static [&'static str] {
    if tool.starts_with("record_") || tool == "replace" || tool == "delete" {
        &["answer", "raw_capture"]
    } else if tool == "submit" {
        &["seal", "raw_capture"]
    } else {
        &["raw_capture"]
    }
}

/// Check a reply's effects against 1.4: exactly the operation's keys in
/// order, then optionally `diagnostic`, each with a value from its set.
pub fn check_effects(
    operation: &str,
    effects: &[(&'static str, &'static str)],
    auditor: bool,
) -> Result<(), String> {
    let want: &[&str] = if auditor {
        auditor_effect_keys(operation)
    } else {
        MANAGER_EFFECTS
            .iter()
            .find(|(op, _)| *op == operation)
            .map(|(_, k)| *k)
            .ok_or_else(|| format!("no effect keys are defined for operation {operation}"))?
    };
    let keys: Vec<&str> = effects
        .iter()
        .map(|(k, _)| *k)
        .filter(|k| *k != "diagnostic")
        .collect();
    if keys != want {
        return Err(format!(
            "{operation} reports effects {keys:?}; 1.4 gives {want:?}"
        ));
    }
    if let Some(i) = effects.iter().position(|(k, _)| *k == "diagnostic") {
        if i + 1 != effects.len() {
            return Err(format!("{operation}: diagnostic follows the other effects"));
        }
    }
    for (k, v) in effects {
        let values = EFFECT_VALUES
            .iter()
            .find(|(key, _)| key == k)
            .map(|(_, v)| *v)
            .unwrap_or(&[]);
        if !values.contains(v) {
            return Err(format!("{operation}: effect {k} has no value {v:?}"));
        }
    }
    Ok(())
}

impl Reply {
    pub fn completed(
        operation: &'static str,
        effects: Vec<(&'static str, &'static str)>,
        data: J,
    ) -> Reply {
        Reply {
            operation,
            outcome: Outcome::Completed,
            reason: None,
            message: None,
            effects,
            retained: Vec::new(),
            causes: Vec::new(),
            next: Vec::new(),
            tool_next: Vec::new(),
            data: Some(data),
        }
    }

    pub fn effect(&self, key: &str) -> Option<&'static str> {
        self.effects
            .iter()
            .find(|(k, _)| *k == key)
            .map(|(_, v)| *v)
    }

    pub fn set_effect(&mut self, key: &'static str, value: &'static str) {
        if let Some(slot) = self.effects.iter_mut().find(|(k, _)| *k == key) {
            slot.1 = value;
        } else {
            self.effects.push((key, value));
        }
    }

    /// Exit status (INTERFACE 1.6). A completed `run` whose placement ended
    /// `interrupted` exits 5: the ending is recorded and `run` may continue it.
    pub fn exit_code(&self) -> i32 {
        match self.outcome {
            Outcome::Completed
                if self.operation == "run"
                    && self.data.as_ref().and_then(|d| d.get("ending"))
                        == Some(&J::Str("interrupted".into())) =>
            {
                5
            }
            Outcome::Completed => 0,
            Outcome::Refused => 3,
            Outcome::Failed => 4,
        }
    }

    /// The manager envelope (1.3).
    pub fn to_j(&self) -> J {
        self.envelope(false)
    }

    /// The auditor envelope, the first text block of a `tool_result` (7.1):
    /// the same envelope without `retained`, with tool next calls. The
    /// caller keeps host and archive paths out of every member.
    pub fn auditor_j(&self) -> J {
        self.envelope(true)
    }

    fn envelope(&self, auditor: bool) -> J {
        debug_assert!(
            check_effects(self.operation, &self.effects, auditor).is_ok(),
            "{}",
            check_effects(self.operation, &self.effects, auditor).unwrap_err()
        );
        let mut o = J::obj()
            .with("schema", "stewart.reply/1")
            .with("operation", self.operation)
            .with("outcome", self.outcome.name());
        let failing = self.outcome != Outcome::Completed;
        if failing {
            o.push("reason", self.reason.clone().unwrap_or_default());
            o.push("message", self.message.clone().unwrap_or_default());
        }
        let omit_effects = failing
            && self.outcome == Outcome::Refused
            && crate::sabotage!("omit_effects_on_refusal");
        if !omit_effects {
            o.push(
                "effects",
                J::Obj(
                    self.effects
                        .iter()
                        .map(|(k, v)| (k.to_string(), J::Str(v.to_string())))
                        .collect(),
                ),
            );
        }
        if failing && !auditor {
            o.push("retained", crate::json::strs(&self.retained));
        }
        if self.outcome == Outcome::Failed || self.effect("diagnostic") == Some("reported_only") {
            o.push(
                "causes",
                J::Arr(self.causes.iter().map(|c| c.to_j()).collect()),
            );
        }
        let next = if auditor {
            self.tool_next.iter().map(|n| n.to_j()).collect()
        } else {
            self.next.iter().map(|n| n.to_j()).collect()
        };
        o.push("next", J::Arr(next));
        match &self.data {
            Some(d) if self.outcome == Outcome::Completed => o.push("data", d.clone()),
            Some(d) if !d.is_empty_obj() => o.push("data", d.clone()),
            _ => {}
        }
        o
    }

    /// The compact wire form followed by one LF.
    pub fn json_line(&self) -> Vec<u8> {
        let mut b = self.to_j().bytes();
        b.push(b'\n');
        b
    }

    /// The same result for people.
    pub fn human(&self) -> String {
        let mut s = String::new();
        match self.outcome {
            Outcome::Completed => s.push_str(&format!("stewart {}: completed\n", self.operation)),
            _ => s.push_str(&format!(
                "stewart {}: {} ({})\n",
                self.operation,
                self.outcome.name(),
                self.reason.as_deref().unwrap_or("")
            )),
        }
        if let Some(m) = &self.message {
            s.push_str(&format!("{m}\n"));
        }
        if let Some(lead) = self.data.as_ref().and_then(headline_line) {
            s.push_str(&lead);
        }
        if !self.effects.is_empty() {
            let e: Vec<String> = self
                .effects
                .iter()
                .map(|(k, v)| format!("{k} {v}"))
                .collect();
            s.push_str(&format!("Effects: {}\n", e.join(", ")));
        } else {
            s.push_str("Effects: none (read-only)\n");
        }
        if !self.retained.is_empty() {
            s.push_str("Retained:\n");
            for r in &self.retained {
                s.push_str(&format!("  {r}\n"));
            }
        }
        if !self.causes.is_empty() {
            s.push_str("Causes (original first):\n");
            for c in &self.causes {
                match &c.path {
                    Some(p) => s.push_str(&format!("  {}: {} ({p})\n", c.operation, c.error)),
                    None => s.push_str(&format!("  {}: {}\n", c.operation, c.error)),
                }
            }
        }
        if let Some(d) = &self.data {
            if !d.is_empty_obj() {
                s.push('\n');
                render(d, 0, &mut s);
            }
        }
        if self.next.is_empty() && self.outcome != Outcome::Completed {
            // A refusal without a supported call must not read as success.
            s.push_str("\nNext: no supported command follows; the message says what to change.\n");
        } else if self.next.is_empty() {
            s.push_str("\nNext: nothing further is needed.\n");
        } else {
            s.push_str("\nNext:\n");
            for n in &self.next {
                s.push_str(&format!("  {}\n      {}\n", shell_words(&n.argv), n.why));
            }
        }
        s
    }
}

/// One line for people: the facts a manager tracks, in order (CONTRACTS,
/// "Status answers with distinct facts").
fn headline_line(data: &J) -> Option<String> {
    let h = data.get("headline")?;
    let text = |v: Option<&J>| match v {
        Some(J::Str(s)) => s.clone(),
        Some(J::Bool(b)) => {
            if *b {
                "yes".into()
            } else {
                "no".into()
            }
        }
        _ => "unknown".into(),
    };
    let sealed = h.get("sealed").and_then(|s| s.get("by"));
    let delivered = h.get("delivered");
    let mut line = format!(
        "Accepted: {} | Launched: {} | Sealed by: {} | Delivery verified: {}, confirmed: {} | Closed: {}\n",
        text(h.get("accepted")),
        text(h.get("launched")),
        text(sealed),
        text(delivered.and_then(|d| d.get("verified"))),
        text(delivered.and_then(|d| d.get("confirmed"))),
        text(h.get("closed")),
    );
    if let (Some(J::Str(c)), Some(J::Str(summary))) = (data.get("condition"), data.get("summary")) {
        line.push_str(&format!("Condition: {c}. {summary}\n"));
    }
    Some(line)
}

/// Quote argv for display so it can be pasted into a POSIX shell.
pub fn shell_words(argv: &[String]) -> String {
    argv.iter()
        .map(|a| {
            if !a.is_empty()
                && a.bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"/._-:%+=@,".contains(&b))
            {
                a.clone()
            } else {
                format!("'{}'", a.replace('\'', "'\\''"))
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn scalar(v: &J) -> Option<String> {
    match v {
        J::Null => Some("none".into()),
        J::Bool(b) => Some(b.to_string()),
        J::Int(n) => Some(n.to_string()),
        J::Str(s) => Some(s.clone()),
        J::Raw(r) => Some(String::from_utf8_lossy(r).into_owned()),
        J::Arr(a) if a.is_empty() => Some("none".into()),
        J::Obj(m) if m.is_empty() => Some("none".into()),
        J::Arr(a) if a.iter().all(|x| matches!(x, J::Str(_) | J::Int(_))) => Some(
            a.iter()
                .map(|x| scalar(x).unwrap_or_default())
                .collect::<Vec<_>>()
                .join(" "),
        ),
        _ => None,
    }
}

/// An indented outline of a data object, key by key, in order.
fn render(v: &J, depth: usize, s: &mut String) {
    let pad = "  ".repeat(depth);
    match v {
        J::Obj(m) => {
            for (k, val) in m {
                let label = k.replace('_', " ");
                match scalar(val) {
                    Some(x) => s.push_str(&format!("{pad}{label}: {x}\n")),
                    None => {
                        s.push_str(&format!("{pad}{label}:\n"));
                        render(val, depth + 1, s);
                    }
                }
            }
        }
        J::Arr(a) => {
            for item in a {
                match scalar(item) {
                    Some(x) => s.push_str(&format!("{pad}- {x}\n")),
                    None => {
                        s.push_str(&format!("{pad}-\n"));
                        render(item, depth + 1, s);
                    }
                }
            }
        }
        other => s.push_str(&format!("{pad}{}\n", scalar(other).unwrap_or_default())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn envelope_keys_are_in_the_specified_order() {
        let mut r = Reply::completed(
            "prepare",
            vec![("preparation", "recorded")],
            J::obj().with("prepared", "mp1.aaaaaa"),
        );
        r.next.push(Next::new(
            vec!["/x/stewart".into(), "commission".into()],
            "why",
        ));
        assert_eq!(
            r.to_j().string(),
            r#"{"schema":"stewart.reply/1","operation":"prepare","outcome":"completed","effects":{"preparation":"recorded"},"next":[{"argv":["/x/stewart","commission"],"why":"why"}],"data":{"prepared":"mp1.aaaaaa"}}"#
        );
        let f = Reply {
            operation: "commission",
            outcome: Outcome::Failed,
            reason: Some("acceptance_record_uncertain".into()),
            message: Some("m".into()),
            effects: vec![
                ("acceptance", "unknown"),
                ("attempt", "recorded"),
                ("diagnostic", "durable"),
            ],
            retained: vec!["/a/intake/1".into()],
            causes: vec![Cause::new("fsync log directory", "EIO")],
            next: vec![],
            tool_next: vec![],
            data: None,
        };
        assert_eq!(
            f.to_j().string(),
            r#"{"schema":"stewart.reply/1","operation":"commission","outcome":"failed","reason":"acceptance_record_uncertain","message":"m","effects":{"acceptance":"unknown","attempt":"recorded","diagnostic":"durable"},"retained":["/a/intake/1"],"causes":[{"operation":"fsync log directory","error":"EIO"}],"next":[]}"#
        );
        assert_eq!(f.exit_code(), 4);
        assert!(f.human().contains("acceptance unknown"));
    }

    #[test]
    fn auditor_envelopes_drop_retained_and_carry_tool_calls() {
        let mut r = Reply::completed(
            "read",
            vec![("raw_capture", "recorded")],
            J::obj().with("complete", false),
        );
        r.retained.push("/archive/path".into());
        r.next.push(Next::new(vec!["/x".into()], "manager only"));
        r.tool_next.push(ToolNext::new(
            "read",
            J::obj().with("source", "question").with("start", 65536u64),
            "Read the rest.",
        ));
        assert_eq!(
            r.auditor_j().string(),
            r#"{"schema":"stewart.reply/1","operation":"read","outcome":"completed","effects":{"raw_capture":"recorded"},"next":[{"tool":"read","input":{"source":"question","start":65536},"why":"Read the rest."}],"data":{"complete":false}}"#
        );
        r.outcome = Outcome::Refused;
        r.reason = Some("range_invalid".into());
        r.message = Some("m".into());
        assert!(!r.auditor_j().string().contains("retained"));
    }

    #[test]
    fn effects_follow_the_closed_sets() {
        assert!(
            check_effects(
                "commission",
                &[
                    ("acceptance", "unknown"),
                    ("attempt", "recorded"),
                    ("diagnostic", "durable")
                ],
                false
            )
            .is_ok()
        );
        assert!(
            check_effects(
                "commission",
                &[("attempt", "recorded"), ("acceptance", "unknown")],
                false
            )
            .is_err()
        );
        assert!(
            check_effects(
                "close",
                &[
                    ("run", "ended"),
                    ("seal", "recorded"),
                    ("delivery", "verified_with_losses"),
                    ("closure", "unfinished")
                ],
                false
            )
            .is_ok()
        );
        assert!(
            check_effects(
                "close",
                &[
                    ("run", "ended"),
                    ("seal", "sealed"),
                    ("delivery", "none"),
                    ("closure", "none")
                ],
                false
            )
            .is_err()
        );
        assert!(check_effects("prepare", &[("raw_capture", "recorded")], true).is_ok());
        assert!(check_effects("prepare", &[("raw_capture", "recorded")], false).is_err());
        assert!(
            check_effects(
                "record_observation",
                &[("answer", "changed"), ("raw_capture", "recorded")],
                true
            )
            .is_ok()
        );
        assert!(
            check_effects(
                "submit",
                &[
                    ("seal", "unknown"),
                    ("raw_capture", "recorded"),
                    ("diagnostic", "reported_only")
                ],
                true
            )
            .is_ok()
        );
        assert!(check_effects("status", &[], false).is_ok());
    }

    #[test]
    fn an_interrupted_run_exits_five() {
        let mut r = Reply::completed(
            "run",
            vec![
                ("run", "ended"),
                ("answer", "unchanged"),
                ("seal", "none"),
                ("delivery", "none"),
            ],
            J::obj().with("run", 1u64).with("ending", "interrupted"),
        );
        assert_eq!(r.exit_code(), 5);
        r.data = Some(J::obj().with("ending", "sealed"));
        assert_eq!(r.exit_code(), 0);
        r.operation = "close";
        r.data = Some(J::obj().with("ending", "interrupted"));
        assert_eq!(r.exit_code(), 0);
    }

    #[test]
    fn shell_words_quote_when_needed() {
        assert_eq!(
            shell_words(&["/a b".into(), "x".into(), "it's".into()]),
            r"'/a b' x 'it'\''s'"
        );
    }
}
