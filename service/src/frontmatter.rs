//! The `question/2` front matter grammar of `question.md` (INTERFACE 3.2).

use crate::ids;
use crate::json::{J, JsonError, Obj};
use crate::usage::Limits;
use crate::util;

/// The values `family:` accepts: the IDs of the families this release
/// defines, in their order, which the refusal lists and `nearest` breaks
/// ties by.
pub fn family_ids() -> Vec<&'static str> {
    crate::forms::FAMILIES.iter().map(|f| f.id).collect()
}

pub const KEYS: [&str; 12] = [
    "stewart",
    "family",
    "guidance",
    "material-roles",
    "model",
    "effort",
    "destination",
    "limit-turns",
    "limit-input-tokens",
    "limit-output-tokens",
    "inquiry",
    "varies",
];
const REQUIRED: [&str; 7] = [
    "stewart",
    "family",
    "model",
    "destination",
    "limit-turns",
    "limit-input-tokens",
    "limit-output-tokens",
];
/// The effort levels of the pinned API version (INTERFACE 3.2). Which levels
/// a model accepts is the provider's to say, not Stewart's.
pub const EFFORT_LEVELS: [&str; 5] = ["low", "medium", "high", "xhigh", "max"];
pub const MODEL_PLACEHOLDER: &str = "REPLACE-WITH-MODEL";
pub const DESTINATION_PLACEHOLDER: &str = "REPLACE-WITH-ABSOLUTE-DIRECTORY";

pub const MAX_TURNS: u64 = 10_000;
pub const MAX_INPUT_TOKENS: u64 = 2_000_000_000;
pub const MAX_OUTPUT_TOKENS: u64 = 200_000_000;

/// The scaffold `new` writes into an absent folder.
pub fn scaffold() -> String {
    [
        "---",
        "stewart: question/2",
        "# Question family: open-inquiry, inquiry-framing or comparison.",
        "# Run `stewart help forms` to read each family's instructions.",
        "family: open-inquiry",
        "# Provider model used for every run of this audit.",
        &format!("model: {MODEL_PLACEHOLDER}"),
        "# Optional effort for every request: low, medium, high, xhigh or max, as a",
        "# line such as \"effort: high\". Without one, the model's provider default applies.",
        "# Existing directory in which Stewart creates the return package.",
        &format!("destination: {DESTINATION_PLACEHOLDER}"),
        "# Cumulative limits across all runs, from the provider's usage reports.",
        "limit-turns: 200",
        "limit-input-tokens: 20000000",
        "limit-output-tokens: 400000",
        "# Put the files the auditor may read under materials/. Edit with ordinary tools.",
        "# Finish editing before prepare, and leave this folder unchanged until commission returns.",
        "# Write your question below the closing --- line.",
        "---",
        "",
    ]
    .join("\n")
}

/// A Messages API question's cumulative limits across all runs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MessagesLimits {
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl MessagesLimits {
    /// The `limits` member, as settings and the Messages arrangement write it.
    pub fn to_j(self) -> J {
        J::obj()
            .with("turns", self.turns)
            .with("input_tokens", self.input_tokens)
            .with("output_tokens", self.output_tokens)
    }
    /// The three values of a `limits` member whose keys the caller has
    /// checked, each within the front matter's bound.
    pub fn decode_values(l: &Obj) -> Result<Self, JsonError> {
        Ok(Self {
            turns: l.u64("turns", MAX_TURNS)?,
            input_tokens: l.u64("input_tokens", MAX_INPUT_TOKENS)?,
            output_tokens: l.u64("output_tokens", MAX_OUTPUT_TOKENS)?,
        })
    }
}

/// The runtime a question commissions, with that runtime's own limits: the
/// Messages API's cumulative limits or, in the development build, the agent
/// runtime's profile selection, which carries its placement limits. Neither
/// runtime's allowance is expressed in the other's units.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeSettings {
    Messages(MessagesLimits),
    #[cfg(feature = "claude-code")]
    Agent(crate::claude_code::profile::Selection),
}

impl RuntimeSettings {
    pub(crate) fn requires_profile(&self) -> bool {
        match self {
            Self::Messages(_) => false,
            #[cfg(feature = "claude-code")]
            Self::Agent(_) => true,
        }
    }

    /// The audit's cumulative limits as accounting reads them.
    pub fn limits(&self) -> Limits {
        match self {
            RuntimeSettings::Messages(limits) => Limits::from(*limits),
            #[cfg(feature = "claude-code")]
            RuntimeSettings::Agent(selection) => Limits::from(selection.limits),
        }
    }
}

// The one conversion from a runtime's own limits to the accounting limits,
// which still hold both runtimes' members; the other runtime's are zero.
impl From<MessagesLimits> for Limits {
    fn from(l: MessagesLimits) -> Limits {
        Limits {
            #[cfg(feature = "claude-code")]
            harness: None,
            turns: l.turns,
            input_tokens: l.input_tokens,
            output_tokens: l.output_tokens,
        }
    }
}

#[cfg(feature = "claude-code")]
impl From<crate::claude_code::profile::Limits> for Limits {
    fn from(l: crate::claude_code::profile::Limits) -> Limits {
        Limits {
            harness: Some(l),
            turns: 0,
            input_tokens: 0,
            output_tokens: 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub family: String,
    pub model: String,
    /// Explicit fixed-file family guidance selection.
    pub guidance: Option<String>,
    /// The manager's effort level, sent as a request parameter; `None` sends
    /// no effort, so the provider's default for the model applies.
    pub effort: Option<String>,
    pub destination: String,
    pub runtime: RuntimeSettings,
    pub inquiry: Option<String>,
    pub varies: Option<String>,
}

impl Settings {
    /// The settings as reported and recorded (INTERFACE 5.3): the runtime's
    /// `limits` follow the destination, and the agent runtime's selection
    /// follows its limits.
    pub fn to_j(&self) -> J {
        let mut o = J::obj()
            .with("family", self.family.as_str())
            .with("model", self.model.as_str())
            .with("destination", self.destination.as_str());
        match &self.runtime {
            RuntimeSettings::Messages(limits) => o.push("limits", limits.to_j()),
            #[cfg(feature = "claude-code")]
            RuntimeSettings::Agent(selection) => {
                o.push("limits", selection.limits.to_j());
                o.push("runtime", selection.to_j());
            }
        }
        if let Some(g) = &self.guidance {
            o.push("guidance", g.as_str());
        }
        if let Some(e) = &self.effort {
            o.push("effort", e.as_str());
        }
        if let Some(i) = &self.inquiry {
            o.push("inquiry", i.as_str());
        }
        if let Some(v) = &self.varies {
            o.push("varies", v.as_str());
        }
        o
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Question {
    pub settings: Settings,
    pub material_roles: crate::roles::Declarations,
    /// Byte offset of the body within the file.
    pub body_offset: usize,
    pub line_ending: &'static str,
}

impl Question {
    /// Resolve declared sources and produce family advice against a complete
    /// literal inventory, whether acquired by prepare or supplied for assessment.
    pub(crate) fn assess_roles<'a>(
        &self,
        names: impl Iterator<Item = &'a str>,
        errors: Vec<Defect>,
    ) -> Result<Vec<Defect>, Vec<Defect>> {
        self.material_roles
            .assess(crate::forms::family(&self.settings.family), names, errors)
    }
}

/// One thing wrong with the question file, naming what to edit.
#[derive(Debug, Clone, PartialEq)]
pub struct Defect {
    pub reason: &'static str,
    pub line: Option<usize>,
    pub key: Option<String>,
    pub message: String,
    pub severity: &'static str,
    pub pointer: Option<String>,
    pub source: Option<String>,
    pub role: Option<String>,
    pub remedy: String,
}

impl Defect {
    pub(crate) fn new(
        reason: &'static str,
        line: Option<usize>,
        key: Option<&str>,
        message: impl Into<String>,
    ) -> Defect {
        let remedy = match reason {
            "question_empty" => "Write your question below the closing --- line.".to_owned(),
            "setting_missing" => format!("Add the required {} field.", key.unwrap_or("setting")),
            "setting_invalid" => format!(
                "Correct the {} value as described.",
                key.unwrap_or("setting")
            ),
            "material_not_text" => "Supply UTF-8 text without NUL.".to_owned(),
            _ => "Correct the indicated front matter in question.md and prepare again.".to_owned(),
        };
        Defect {
            severity: "error",
            pointer: None,
            source: None,
            role: None,
            remedy,
            reason,
            line,
            key: key.map(|k| k.to_string()),
            message: message.into(),
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("reason", self.reason)
            .with("line", self.line.map(|l| l as u64))
            .with("key", self.key.clone())
            .with("message", self.message.as_str())
            .with("severity", self.severity)
            .with("pointer", self.pointer.as_deref())
            .with("source", self.source.as_deref())
            .with("role", self.role.as_deref())
            .with("remedy", self.remedy.as_str())
    }
}

/// The first byte offset that breaks the text reader rule (`utf8-text/1`:
/// valid UTF-8 without NUL), if any.
pub fn first_non_text(bytes: &[u8]) -> Option<usize> {
    let valid = match std::str::from_utf8(bytes) {
        Ok(_) => bytes.len(),
        Err(e) => e.valid_up_to(),
    };
    if let Some(p) = bytes[..valid].iter().position(|b| *b == 0) {
        return Some(p);
    }
    if valid < bytes.len() {
        Some(valid)
    } else {
        None
    }
}

fn is_control(c: char) -> bool {
    let u = c as u32;
    u <= 0x1F || (0x7F..=0x9F).contains(&u)
}

/// Parse `question.md`. The bytes must already satisfy the text reader rule.
/// Grammar defects stop parsing; setting defects and an empty body are all
/// collected, so one refusal can name every edit the scaffold needs.
pub fn parse(bytes: &[u8]) -> Result<Question, Vec<Defect>> {
    let (question, defects) = candidate(bytes)?;
    if defects.is_empty() {
        Ok(question)
    } else {
        Err(defects)
    }
}

/// A decodable question and independent field errors. A caller with a complete
/// inventory can also diagnose references in well-formed declarations.
pub(crate) fn candidate(bytes: &[u8]) -> Result<(Question, Vec<Defect>), Vec<Defect>> {
    let text = std::str::from_utf8(bytes).map_err(|_| {
        vec![Defect::new(
            "material_not_text",
            None,
            None,
            "question.md is not valid UTF-8",
        )]
    })?;
    let start = if text.starts_with('\u{feff}') { 3 } else { 0 };
    let rest = &text[start..];
    let ending: &'static str = if rest.starts_with("---\r\n") {
        "\r\n"
    } else if rest.starts_with("---\n") {
        "\n"
    } else {
        return Err(vec![Defect::new(
            "front_matter_invalid",
            Some(1),
            None,
            "question.md must begin with a line holding exactly --- (after an optional byte-order mark).",
        )]);
    };
    let mut pos = start + 3 + ending.len();
    let mut line_no = 1usize;
    let mut fields: Vec<(String, String, usize)> = Vec::new();
    let body_offset;
    loop {
        line_no += 1;
        let (line, next) = match text[pos..].find('\n') {
            Some(i) => (&text[pos..pos + i], Some(pos + i + 1)),
            None => (&text[pos..], None),
        };
        let line = match next {
            Some(_) if ending == "\r\n" => match line.strip_suffix('\r') {
                Some(l) => l,
                None => {
                    return Err(vec![Defect::new(
                        "front_matter_invalid",
                        Some(line_no),
                        None,
                        format!(
                            "line {line_no} ends with LF, but the front matter uses CRLF line endings (set by its first line)."
                        ),
                    )]);
                }
            },
            Some(_) => {
                if line.ends_with('\r') {
                    return Err(vec![Defect::new(
                        "front_matter_invalid",
                        Some(line_no),
                        None,
                        format!(
                            "line {line_no} ends with CRLF, but the front matter uses LF line endings (set by its first line)."
                        ),
                    )]);
                }
                line
            }
            None => line,
        };
        if line == "---" {
            body_offset = next.unwrap_or(text.len());
            break;
        }
        let Some(next) = next else {
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                None,
                "the front matter has no closing --- line.",
            )]);
        };
        pos = next;
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once(':') else {
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                None,
                format!("line {line_no} is not a field (key: value), a comment (#…) or empty."),
            )]);
        };
        let Some(value) = value.strip_prefix(' ') else {
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                Some(key),
                format!("line {line_no}: a field is the key, one colon, one space and the value."),
            )]);
        };
        if value.is_empty()
            || value.starts_with(char::is_whitespace)
            || value.ends_with(char::is_whitespace)
        {
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                Some(key),
                format!(
                    "line {line_no}: the value of {key} must be non-empty, with no leading or trailing whitespace."
                ),
            )]);
        }
        #[cfg(feature = "claude-code")]
        let runtime_key = crate::claude_code::profile::EXTRA_KEYS.contains(&key);
        #[cfg(not(feature = "claude-code"))]
        let runtime_key = false;
        if !KEYS.contains(&key) && !runtime_key {
            if crate::sabotage!("accept_unknown_field") {
                continue;
            }
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                Some(key),
                format!(
                    "line {line_no}: unknown key {key:?}; the nearest known key is {:?}.",
                    util::nearest(key, &KEYS)
                ),
            )]);
        }
        if let Some((_, _, first)) = fields.iter().find(|(k, _, _)| k == key) {
            return Err(vec![Defect::new(
                "front_matter_invalid",
                Some(line_no),
                Some(key),
                format!(
                    "line {line_no}: {key} already appeared on line {first}; each key appears at most once."
                ),
            )]);
        }
        fields.push((key.to_string(), value.to_string(), line_no));
    }

    #[cfg(feature = "claude-code")]
    let is_harness = fields
        .iter()
        .any(|(k, _, _)| k == crate::claude_code::profile::SELECTOR);
    #[cfg(not(feature = "claude-code"))]
    let is_harness = false;
    let mut defects = Vec::new();
    let get = |k: &str| {
        fields
            .iter()
            .find(|(key, _, _)| key == k)
            .map(|(_, v, l)| (v.as_str(), *l))
    };
    let mut invalid = |key: &str, line: usize, msg: String| {
        defects.push(Defect::new("setting_invalid", Some(line), Some(key), msg))
    };

    // Each value is kept only when the parse has no defect, so every
    // required one has then been set.
    let mut family = String::new();
    let mut guidance = None;
    let mut model = String::new();
    let mut effort = None;
    let mut destination = String::new();
    let mut limits = MessagesLimits {
        turns: 0,
        input_tokens: 0,
        output_tokens: 0,
    };
    let mut inquiry = None;
    let mut varies = None;
    if let Some((v, l)) = get("stewart") {
        if v != "question/2" {
            invalid(
                "stewart",
                l,
                format!("line {l}: stewart must be exactly question/2, not {v:?}."),
            );
        }
    }
    if let Some((v, l)) = get("family") {
        let ids = family_ids();
        if ids.contains(&v) {
            family = v.to_string();
        } else {
            invalid(
                "family",
                l,
                format!(
                    "line {l}: family must be {}; {v:?} is none of these (nearest: {}).",
                    util::alternatives(&ids),
                    util::nearest(v, &ids)
                ),
            );
        }
    }
    if let Some((v, l)) = get("guidance") {
        let admitted =
            crate::forms::family(&family).is_some_and(crate::forms::Family::admits_guidance_file);
        if v == "guidance.md" && admitted {
            guidance = Some(v.to_string());
        } else {
            invalid(
                "guidance",
                l,
                format!(
                    "line {l}: guidance must be exactly guidance.md and requires family: {}; no other path or family is supported.",
                    crate::forms::guidance_family_ids()
                ),
            );
        }
    }
    if let Some((v, l)) = get("model") {
        let ok_chars = v
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | ':' | '-'));
        if v == MODEL_PLACEHOLDER {
            invalid(
                "model",
                l,
                format!(
                    "line {l}: replace {MODEL_PLACEHOLDER} with the provider model to use for every run of this audit."
                ),
            );
        } else if v.chars().count() > 128 || !ok_chars {
            invalid(
                "model",
                l,
                format!("line {l}: model must be 1–128 characters from A–Z a–z 0–9 . _ : -."),
            );
        } else {
            model = v.to_string();
        }
    }
    if let Some((v, l)) = get("effort") {
        if EFFORT_LEVELS.contains(&v) {
            effort = Some(v.to_string());
        } else {
            invalid(
                "effort",
                l,
                format!(
                    "line {l}: effort must be low, medium, high, xhigh or max; {v:?} is none of these (nearest: {}).",
                    util::nearest(v, &EFFORT_LEVELS)
                ),
            );
        }
    }
    if let Some((v, l)) = get("destination") {
        if v == DESTINATION_PLACEHOLDER {
            invalid(
                "destination",
                l,
                format!(
                    "line {l}: replace {DESTINATION_PLACEHOLDER} with the absolute path of an existing directory for the return package."
                ),
            );
        } else if !v.starts_with('/') {
            invalid(
                "destination",
                l,
                format!("line {l}: destination must be an absolute path."),
            );
        } else if v.len() > 1024 {
            invalid(
                "destination",
                l,
                format!("line {l}: destination must be at most 1,024 bytes."),
            );
        } else if v.chars().any(is_control) {
            invalid(
                "destination",
                l,
                format!("line {l}: destination must not contain control characters."),
            );
        } else {
            destination = v.to_string();
        }
    }
    for (key, max, slot) in [
        ("limit-turns", MAX_TURNS, &mut limits.turns),
        (
            "limit-input-tokens",
            MAX_INPUT_TOKENS,
            &mut limits.input_tokens,
        ),
        (
            "limit-output-tokens",
            MAX_OUTPUT_TOKENS,
            &mut limits.output_tokens,
        ),
    ] {
        if let Some((v, l)) = get(key) {
            match parse_bounded(v, max) {
                Some(n) => *slot = n,
                None => invalid(
                    key,
                    l,
                    format!(
                        "line {l}: {key} must be a whole number from 1 to {max}, written without sign, separators or leading zeros."
                    ),
                ),
            }
        }
    }
    if let Some((v, l)) = get("inquiry") {
        if v.chars().count() > 128 || v.chars().any(is_control) {
            invalid(
                "inquiry",
                l,
                format!("line {l}: inquiry must be 1–128 characters with no control characters."),
            );
        } else {
            inquiry = Some(v.to_string());
        }
    }
    if let Some((v, l)) = get("varies") {
        match ids::decode_reference(v) {
            Ok(_) => varies = Some(v.to_string()),
            Err(e) => invalid(
                "varies",
                l,
                format!("line {l}: varies must be a stw1: reference ({e})."),
            ),
        }
    }
    for key in REQUIRED {
        if is_harness && key.starts_with("limit-") {
            continue;
        }
        if get(key).is_none() {
            defects.push(Defect::new(
                "setting_missing",
                None,
                Some(key),
                format!("the required key {key} is missing from the front matter."),
            ));
        }
    }
    // A question that names a profile takes the agent runtime, valid or not;
    // its checks follow the common ones.
    #[cfg(feature = "claude-code")]
    let runtime = match crate::claude_code::profile::frontmatter(&fields, is_harness, &mut defects)
    {
        Some(selection) => RuntimeSettings::Agent(selection),
        None => RuntimeSettings::Messages(limits),
    };
    #[cfg(not(feature = "claude-code"))]
    let runtime = RuntimeSettings::Messages(limits);
    let body = &text[body_offset..];
    if !body.chars().any(|c| !c.is_whitespace()) {
        defects.push(Defect::new(
            "question_empty",
            None,
            None,
            "the question body (after the closing --- line) has no non-whitespace character. Write your question there; the provider cannot carry an empty or blank text block, so this refusal is mechanical.",
        ));
    }
    let material_roles = crate::roles::Declarations::parse(
        get("material-roles"),
        crate::forms::family(&family),
        &mut defects,
    );
    sort_defects(&mut defects);
    Ok((
        Question {
            material_roles,
            settings: Settings {
                family,
                model,
                guidance,
                effort,
                destination,
                runtime,
                inquiry,
                varies,
            },
            body_offset,
            line_ending: if ending == "\n" { "LF" } else { "CRLF" },
        },
        defects,
    ))
}

pub(crate) fn sort_defects(defects: &mut [Defect]) {
    let index = |d: &Defect| {
        d.pointer
            .as_deref()?
            .split('/')
            .nth(1)?
            .parse::<usize>()
            .ok()
    };
    defects.sort_by(|a, b| {
        (
            a.line.unwrap_or(usize::MAX),
            index(a),
            &a.key,
            &a.pointer,
            a.reason,
        )
            .cmp(&(
                b.line.unwrap_or(usize::MAX),
                index(b),
                &b.key,
                &b.pointer,
                b.reason,
            ))
    });
}

fn parse_bounded(v: &str, max: u64) -> Option<u64> {
    if v.is_empty()
        || !v.bytes().all(|b| b.is_ascii_digit())
        || (v.len() > 1 && v.starts_with('0'))
        || v.len() > 12
    {
        return None;
    }
    let n: u64 = v.parse().ok()?;
    if n == 0 || n > max { None } else { Some(n) }
}

#[cfg(test)]
mod tests {
    use super::*;

    const GOOD: &str = "---\nstewart: question/2\n# comment\nfamily: open-inquiry\nmodel: claude-opus-5-5\ndestination: /home/ana/returns\n\nlimit-turns: 200\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\n---\nAudit our app to make sure there are no bugs.\n";

    /// The limits `GOOD` sets.
    const EXAMPLE_LIMITS: MessagesLimits = MessagesLimits {
        turns: 200,
        input_tokens: 20_000_000,
        output_tokens: 400_000,
    };

    fn reasons(s: &str) -> Vec<&'static str> {
        parse(s.as_bytes())
            .unwrap_err()
            .iter()
            .map(|d| d.reason)
            .collect()
    }

    #[test]
    fn accepts_the_example_and_keeps_the_body_exact() {
        let q = parse(GOOD.as_bytes()).unwrap();
        assert_eq!(
            &GOOD[q.body_offset..],
            "Audit our app to make sure there are no bugs.\n"
        );
        assert_eq!(
            q.settings.runtime,
            RuntimeSettings::Messages(EXAMPLE_LIMITS)
        );
        assert_eq!(q.settings.family, "open-inquiry");
        assert_eq!(q.line_ending, "LF");
    }

    /// The development runtime's three fields. The release build knows none
    /// of them; the development build reads them on the one question version.
    const RUNTIME: &str = "---\nstewart: question/2\nfamily: open-inquiry\nmodel: claude-opus-5-5\ndestination: /home/ana/returns\nruntime-profile: /home/ana/profile.json\nmax-placements: 3\nplacement-timeout-seconds: 600\n---\nAudit our app to make sure there are no bugs.\n";

    #[cfg(not(feature = "claude-code"))]
    #[test]
    fn the_release_build_knows_no_runtime_field_or_version() {
        let defects = parse(RUNTIME.as_bytes()).unwrap_err();
        assert_eq!(defects.len(), 1);
        assert_eq!(defects[0].reason, "front_matter_invalid");
        assert_eq!(defects[0].key.as_deref(), Some("runtime-profile"));
        // Each field alone beside the ordinary limits is equally unknown.
        for key in [
            "runtime-profile",
            "max-placements",
            "placement-timeout-seconds",
        ] {
            let line = RUNTIME
                .lines()
                .find(|l| l.starts_with(key))
                .expect("fixture line");
            let one = GOOD.replace("limit-turns: 200\n", &format!("limit-turns: 200\n{line}\n"));
            let defects = parse(one.as_bytes()).unwrap_err();
            assert_eq!(defects.len(), 1, "{key}");
            assert_eq!(defects[0].reason, "front_matter_invalid", "{key}");
            assert_eq!(defects[0].key.as_deref(), Some(key));
            assert!(defects[0].message.contains("unknown key"), "{key}");
        }
        let version = GOOD.replace("stewart: question/2", "stewart: question/claude-code/1");
        let defects = parse(version.as_bytes()).unwrap_err();
        assert_eq!(defects.len(), 1);
        assert_eq!(defects[0].reason, "setting_invalid");
        assert_eq!(defects[0].key.as_deref(), Some("stewart"));
        // Invariance: the ordinary question still parses.
        assert!(parse(GOOD.as_bytes()).is_ok());
    }

    #[cfg(feature = "claude-code")]
    #[test]
    fn the_profile_field_selects_the_runtime_on_the_one_version() {
        let q = parse(RUNTIME.as_bytes()).unwrap();
        let RuntimeSettings::Agent(selected) = q.settings.runtime else {
            panic!("runtime selected: {:?}", q.settings.runtime);
        };
        assert_eq!(selected.path, "/home/ana/profile.json");
        assert_eq!(selected.limits.max_placements, 3);
        assert_eq!(selected.limits.placement_timeout_seconds, 600);
        assert_eq!(selected.profile, None);
        // Invariance: without the field the question is a Messages question.
        let q = parse(GOOD.as_bytes()).unwrap();
        assert_eq!(
            q.settings.runtime,
            RuntimeSettings::Messages(EXAMPLE_LIMITS)
        );

        let defects = |text: &str| -> Vec<(&'static str, Option<String>, String)> {
            parse(text.as_bytes())
                .unwrap_err()
                .into_iter()
                .map(|d| (d.reason, d.key, d.message))
                .collect()
        };
        // The removed version refuses by name, with or without runtime fields.
        for text in [RUNTIME, GOOD] {
            let found =
                defects(&text.replace("stewart: question/2", "stewart: question/claude-code/1"));
            assert_eq!(found.len(), 1, "{found:?}");
            assert_eq!(found[0].0, "setting_invalid");
            assert_eq!(found[0].1.as_deref(), Some("stewart"));
            assert!(
                found[0].2.contains("question/claude-code/1")
                    && found[0].2.contains("exactly question/2"),
                "{found:?}"
            );
        }
        // Each API limit beside a profile refuses, although its value is valid.
        for limit in [
            "limit-turns: 200",
            "limit-input-tokens: 20000000",
            "limit-output-tokens: 400000",
        ] {
            let key = limit.split(':').next().unwrap();
            let found = defects(&RUNTIME.replace(
                "max-placements: 3\n",
                &format!("max-placements: 3\n{limit}\n"),
            ));
            assert_eq!(found.len(), 1, "{found:?}");
            assert_eq!(found[0].0, "setting_invalid");
            assert_eq!(found[0].1.as_deref(), Some(key));
        }
        // Each placement field without a profile refuses.
        for line in ["max-placements: 3", "placement-timeout-seconds: 600"] {
            let key = line.split(':').next().unwrap();
            let found = defects(
                &GOOD.replace("limit-turns: 200\n", &format!("limit-turns: 200\n{line}\n")),
            );
            assert_eq!(found.len(), 1, "{found:?}");
            assert_eq!(found[0].0, "setting_invalid");
            assert_eq!(found[0].1.as_deref(), Some(key));
            assert!(found[0].2.contains("runtime-profile"), "{found:?}");
        }
        // A missing placement field is a missing required key; a bad one is invalid.
        let found = defects(&RUNTIME.replace("max-placements: 3\n", ""));
        assert_eq!(found.len(), 1, "{found:?}");
        assert_eq!(found[0].0, "setting_missing");
        assert_eq!(found[0].1.as_deref(), Some("max-placements"));
        let found = defects(&RUNTIME.replace("-seconds: 600", "-seconds: 0600"));
        assert_eq!(found.len(), 1, "{found:?}");
        assert_eq!(found[0].0, "setting_invalid");
        assert_eq!(found[0].1.as_deref(), Some("placement-timeout-seconds"));
        // The scaffold is the common one and names no runtime field.
        assert!(!scaffold().contains("runtime") && !scaffold().contains("placement"));
    }

    /// The selector's presence, not its validity, decides which limits a
    /// question takes, and diagnostics follow source line order. Each
    /// list is every defect in its reported order.
    #[cfg(feature = "claude-code")]
    #[test]
    fn a_profile_beside_an_api_limit_reports_each_defect_in_order() {
        let all = |text: &str| -> Vec<(&'static str, Option<usize>, Option<String>, String)> {
            parse(text.as_bytes())
                .unwrap_err()
                .into_iter()
                .map(|d| (d.reason, d.line, d.key, d.message))
                .collect()
        };
        let d = |reason, line, key: &str, message: &str| {
            (reason, line, Some(key.to_string()), message.to_string())
        };
        let api = "limit-turns is a Messages API limit; a question that names runtime-profile takes max-placements and placement-timeout-seconds instead";
        let range = "line 8: limit-turns must be a whole number from 1 to 10000, written without sign, separators or leading zeros.";
        let placement = "max-placements applies only to a question that names runtime-profile; without it the question uses limit-turns, limit-input-tokens and limit-output-tokens";
        let with_limit = |limit: &str| {
            RUNTIME.replace(
                "max-placements: 3\n",
                &format!("max-placements: 3\nlimit-turns: {limit}\n"),
            )
        };
        // A profile that is not an absolute path still selects the runtime:
        // the API limit is refused, and no API limit is reported missing.
        assert_eq!(
            all(&with_limit("200").replace(": /home/ana/profile.json", ": profile.json")),
            [
                d(
                    "setting_invalid",
                    Some(6),
                    "runtime-profile",
                    "a runtime profile must be an absolute file path"
                ),
                d("setting_invalid", Some(8), "limit-turns", api),
            ]
        );
        // An API limit with a bad value beside a profile: its own check, then the runtime's.
        assert_eq!(
            all(&with_limit("0")),
            [
                d("setting_invalid", Some(8), "limit-turns", range),
                d("setting_invalid", Some(8), "limit-turns", api),
            ]
        );
        // Missing fields follow the error with a source line.
        let text = RUNTIME
            .replace("family: open-inquiry\n", "")
            .replace("max-placements: 3\n", "limit-turns: 200\n");
        assert_eq!(
            all(&text),
            [
                d("setting_invalid", Some(6), "limit-turns", api),
                (
                    "setting_missing",
                    None,
                    Some("family".to_string()),
                    "the required key family is missing from the front matter.".to_string()
                ),
                (
                    "setting_missing",
                    None,
                    Some("max-placements".to_string()),
                    "the required key max-placements is missing from the front matter; a question that names runtime-profile needs it.".to_string()
                ),
            ]
        );
        // Without a profile, the API limits are checked and required, then
        // the placement field is refused.
        assert_eq!(
            all(&GOOD.replace("limit-turns: 200\n", "limit-turns: 0\nmax-placements: 3\n")),
            [
                d("setting_invalid", Some(8), "limit-turns", range),
                d("setting_invalid", Some(9), "max-placements", placement),
            ]
        );
        assert_eq!(
            all(&GOOD.replace("limit-turns: 200\n", "max-placements: 3\n")),
            [
                d("setting_invalid", Some(8), "max-placements", placement),
                (
                    "setting_missing",
                    None,
                    Some("limit-turns".to_string()),
                    "the required key limit-turns is missing from the front matter.".to_string()
                ),
            ]
        );
    }

    #[test]
    fn bom_and_crlf() {
        let crlf = GOOD.replace('\n', "\r\n");
        let with_bom = format!("\u{feff}{crlf}");
        let q = parse(with_bom.as_bytes()).unwrap();
        assert_eq!(
            &with_bom[q.body_offset..],
            "Audit our app to make sure there are no bugs.\r\n"
        );
        assert_eq!(q.line_ending, "CRLF");
        // Mixed endings inside the front matter are refused, naming the line.
        let mixed = GOOD.replacen("family: open-inquiry\n", "family: open-inquiry\r\n", 1);
        let d = parse(mixed.as_bytes()).unwrap_err();
        assert_eq!(d[0].reason, "front_matter_invalid");
        assert_eq!(d[0].line, Some(4));
        let mixed2 = crlf.replacen("family: open-inquiry\r\n", "family: open-inquiry\n", 1);
        assert_eq!(reasons(&mixed2), ["front_matter_invalid"]);
        // The body may use any endings.
        let body_mixed = format!("{}a\r\nb\n", &GOOD[..GOOD.find("Audit").unwrap()]);
        assert!(parse(body_mixed.as_bytes()).is_ok());
    }

    #[test]
    fn delimiters_fields_and_keys() {
        assert_eq!(reasons("stewart: question/2\n"), ["front_matter_invalid"]);
        assert_eq!(
            reasons(&GOOD.replace("\n---\nAudit", "\nAudit")),
            ["front_matter_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("model: claude", "model:  claude")),
            ["front_matter_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("model: claude-opus-5-5", "model:claude")),
            ["front_matter_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("# comment", "  # comment")),
            ["front_matter_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("# comment", "free text")),
            ["front_matter_invalid"]
        );
        let dup = GOOD.replace("# comment", "family: comparison");
        let d = parse(dup.as_bytes()).unwrap_err();
        assert_eq!(d[0].reason, "front_matter_invalid");
        assert!(d[0].message.contains("already appeared"));
        let unknown = GOOD.replace("# comment", "limit-turn: 3");
        let d = parse(unknown.as_bytes()).unwrap_err();
        assert!(d[0].message.contains("limit-turns"), "{}", d[0].message);
        assert_eq!(d[0].line, Some(3));
    }

    #[test]
    fn settings_are_checked_and_collected() {
        assert_eq!(
            reasons(&GOOD.replace("family: open-inquiry\n", "")),
            ["setting_missing"]
        );
        assert_eq!(
            reasons(&GOOD.replace("limit-turns: 200", "limit-turns: 0")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("limit-turns: 200", "limit-turns: 10001")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("limit-turns: 200", "limit-turns: 0200")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("limit-turns: 200", "limit-turns: +200")),
            ["setting_invalid"]
        );
        assert!(
            parse(
                GOOD.replace("limit-turns: 200", "limit-turns: 10000")
                    .as_bytes()
            )
            .is_ok()
        );
        assert_eq!(
            reasons(&GOOD.replace("question/2", "question/1")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("/home/ana/returns", "returns")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("claude-opus-5-5", "claude opus")),
            ["setting_invalid"]
        );
        assert_eq!(
            reasons(&GOOD.replace("claude-opus-5-5", "REPLACE-WITH-MODEL")),
            ["setting_invalid"]
        );
        let with_optional = GOOD.replace(
            "# comment",
            "inquiry: reminders\nvaries: stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x",
        );
        let q = parse(with_optional.as_bytes()).unwrap();
        assert_eq!(q.settings.inquiry.as_deref(), Some("reminders"));
        assert_eq!(
            reasons(&GOOD.replace("# comment", "varies: elsewhere")),
            ["setting_invalid"]
        );
    }

    #[test]
    fn effort_is_optional_and_only_a_known_level() {
        assert_eq!(parse(GOOD.as_bytes()).unwrap().settings.effort, None);
        for level in EFFORT_LEVELS {
            let q = parse(
                GOOD.replace("# comment", &format!("effort: {level}"))
                    .as_bytes(),
            )
            .unwrap();
            assert_eq!(q.settings.effort.as_deref(), Some(level));
        }
        for bad in ["hgih", "High", "HIGH", "extra-high", "high!"] {
            let d = parse(
                GOOD.replace("# comment", &format!("effort: {bad}"))
                    .as_bytes(),
            )
            .unwrap_err();
            assert_eq!(d.len(), 1, "{bad}");
            assert_eq!(
                (d[0].reason, d[0].key.as_deref(), d[0].line),
                ("setting_invalid", Some("effort"), Some(3)),
                "{bad}"
            );
        }
        let d = parse(GOOD.replace("# comment", "effort: hgih").as_bytes()).unwrap_err();
        assert!(d[0].message.contains("(nearest: high)"), "{}", d[0].message);
        let twice = GOOD.replace("# comment", "effort: high\neffort: low");
        assert_eq!(reasons(&twice), ["front_matter_invalid"]);
        // Reported after the limits, before the optional labels, only when given.
        let q = parse(
            GOOD.replace("# comment", "effort: max\ninquiry: reminders")
                .as_bytes(),
        )
        .unwrap();
        let j = q.settings.to_j().string();
        assert!(
            j.ends_with(r#""output_tokens":400000},"effort":"max","inquiry":"reminders"}"#),
            "{j}"
        );
        let plain = parse(GOOD.as_bytes()).unwrap().settings.to_j().string();
        assert!(!plain.contains("effort"), "{plain}");
    }

    #[test]
    fn the_scaffold_sets_no_effort() {
        // The scaffold explains the setting in comments only: an effort line
        // would be a Stewart default, and there is none.
        let text = scaffold();
        assert!(text.contains("# Optional effort for every request"));
        assert!(!text.lines().any(|l| l.starts_with("effort")));
        let editable = text
            .replace("REPLACE-WITH-MODEL", "fixture-model")
            .replace("REPLACE-WITH-ABSOLUTE-DIRECTORY", "/fixture/returns")
            + "Question?\n";
        assert_eq!(parse(editable.as_bytes()).unwrap().settings.effort, None);
        let explicit = editable.replacen(
            "\nfamily: open-inquiry\n",
            "\nfamily: open-inquiry\neffort: high\n",
            1,
        );
        assert_eq!(
            parse(explicit.as_bytes())
                .unwrap()
                .settings
                .effort
                .as_deref(),
            Some("high")
        );
    }

    #[test]
    fn the_scaffold_is_refused_naming_every_edit() {
        let d = parse(scaffold().as_bytes()).unwrap_err();
        let r: Vec<_> = d.iter().map(|x| (x.reason, x.key.clone())).collect();
        assert_eq!(
            r,
            [
                ("setting_invalid", Some("model".to_string())),
                ("setting_invalid", Some("destination".to_string())),
                ("question_empty", None)
            ]
        );
        assert!(scaffold().contains("# Write your question below the closing --- line.\n---\n"));
    }

    #[test]
    fn blank_bodies_are_question_empty() {
        let head = &GOOD[..GOOD.find("Audit").unwrap()];
        assert_eq!(reasons(&format!("{head} \n\t\n")), ["question_empty"]);
        assert_eq!(reasons(head.trim_end_matches('\n')), ["question_empty"]);
    }

    #[test]
    fn text_rule_offsets() {
        assert_eq!(first_non_text(b"ok"), None);
        assert_eq!(first_non_text(b"ab\0c"), Some(2));
        assert_eq!(first_non_text(b"ab\xffc"), Some(2));
        assert_eq!(first_non_text(b"\xe2\x82"), Some(0));
    }

    #[test]
    fn family_vocabulary_is_the_forms_families() {
        let ids: Vec<&str> = crate::forms::FAMILIES.iter().map(|f| f.id).collect();
        assert_eq!(family_ids(), ids);
        let scaffold = scaffold();
        let commands = crate::help::topic("commands").unwrap();
        for id in ids {
            assert!(scaffold.contains(id), "scaffold names {id}");
            assert!(commands.contains(id), "help names {id}");
        }
    }

    #[test]
    fn an_unknown_family_names_the_choices_and_nearest() {
        for (family, quoted, nearest) in [
            ("survey", "\"survey\"", "comparison"),
            ("comparision", "\"comparision\"", "comparison"),
            ("open-inquiries", "\"open-inquiries\"", "open-inquiry"),
        ] {
            let defects = parse(
                GOOD.replace("family: open-inquiry", &format!("family: {family}"))
                    .as_bytes(),
            )
            .unwrap_err();
            assert_eq!(defects.len(), 1, "{family}");
            assert_eq!(defects[0].reason, "setting_invalid");
            assert_eq!(defects[0].key.as_deref(), Some("family"));
            assert_eq!(
                defects[0].message,
                format!(
                    "line 4: family must be open-inquiry, inquiry-framing or comparison; {quoted} is none of these (nearest: {nearest})."
                )
            );
        }
    }

    #[test]
    fn guidance_follows_the_family() {
        let with = |family: &str, guidance: &str| {
            GOOD.replace(
                "family: open-inquiry\n",
                &format!("family: {family}\nguidance: {guidance}\n"),
            )
        };
        let q = parse(with("open-inquiry", "guidance.md").as_bytes()).unwrap();
        assert_eq!(q.settings.guidance.as_deref(), Some("guidance.md"));
        assert_eq!(q.settings.family, "open-inquiry");
        let refused = "line 5: guidance must be exactly guidance.md and requires family: open-inquiry; no other path or family is supported.";
        for (family, guidance) in [
            ("comparison", "guidance.md"),
            ("inquiry-framing", "guidance.md"),
            ("open-inquiry", "notes/guidance.md"),
        ] {
            let defects = parse(with(family, guidance).as_bytes()).unwrap_err();
            assert_eq!(defects.len(), 1, "{family} {guidance}");
            assert_eq!(defects[0].reason, "setting_invalid");
            assert_eq!(defects[0].key.as_deref(), Some("guidance"));
            assert_eq!(defects[0].message, refused, "{family} {guidance}");
        }
    }
}
