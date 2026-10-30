//! The `question/1` front matter grammar of `question.md` (INTERFACE 3.2).

use crate::ids;
use crate::json::J;
use crate::util;

pub const FAMILIES: [&str; 3] = ["open-inquiry", "inquiry-framing", "comparison"];
pub const KEYS: [&str; 9] = [
    "stewart",
    "family",
    "model",
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
pub const MODEL_PLACEHOLDER: &str = "REPLACE-WITH-MODEL";
pub const DESTINATION_PLACEHOLDER: &str = "REPLACE-WITH-ABSOLUTE-DIRECTORY";

pub const MAX_TURNS: u64 = 10_000;
pub const MAX_INPUT_TOKENS: u64 = 2_000_000_000;
pub const MAX_OUTPUT_TOKENS: u64 = 200_000_000;

/// The scaffold `new` writes into an absent folder.
pub fn scaffold() -> String {
    [
        "---",
        "stewart: question/1",
        "# Question family: open-inquiry, inquiry-framing or comparison.",
        "# Run `stewart help forms` to read each family's instructions.",
        "family: open-inquiry",
        "# Provider model used for every run of this audit.",
        &format!("model: {MODEL_PLACEHOLDER}"),
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

#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub family: String,
    pub model: String,
    pub destination: String,
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub inquiry: Option<String>,
    pub varies: Option<String>,
}

impl Settings {
    /// The settings as reported and recorded (INTERFACE 5.3).
    pub fn to_j(&self) -> J {
        let mut o = J::obj()
            .with("family", self.family.as_str())
            .with("model", self.model.as_str())
            .with("destination", self.destination.as_str())
            .with(
                "limits",
                J::obj()
                    .with("turns", self.turns)
                    .with("input_tokens", self.input_tokens)
                    .with("output_tokens", self.output_tokens),
            );
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
    /// Byte offset of the body within the file.
    pub body_offset: usize,
    pub line_ending: &'static str,
}

/// One thing wrong with the question file, naming what to edit.
#[derive(Debug, Clone, PartialEq)]
pub struct Defect {
    pub reason: &'static str,
    pub line: Option<usize>,
    pub key: Option<String>,
    pub message: String,
}

impl Defect {
    fn new(
        reason: &'static str,
        line: Option<usize>,
        key: Option<&str>,
        message: impl Into<String>,
    ) -> Defect {
        Defect {
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
        if !KEYS.contains(&key) {
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

    let mut settings = Settings {
        family: String::new(),
        model: String::new(),
        destination: String::new(),
        turns: 0,
        input_tokens: 0,
        output_tokens: 0,
        inquiry: None,
        varies: None,
    };
    if let Some((v, l)) = get("stewart") {
        if v != "question/1" {
            invalid(
                "stewart",
                l,
                format!("line {l}: stewart must be exactly question/1, not {v:?}."),
            );
        }
    }
    if let Some((v, l)) = get("family") {
        if FAMILIES.contains(&v) {
            settings.family = v.to_string();
        } else {
            invalid(
                "family",
                l,
                format!(
                    "line {l}: family must be open-inquiry, inquiry-framing or comparison; {v:?} is none of these (nearest: {}).",
                    util::nearest(v, &FAMILIES)
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
            settings.model = v.to_string();
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
            settings.destination = v.to_string();
        }
    }
    for (key, max, slot) in [
        ("limit-turns", MAX_TURNS, &mut settings.turns),
        (
            "limit-input-tokens",
            MAX_INPUT_TOKENS,
            &mut settings.input_tokens,
        ),
        (
            "limit-output-tokens",
            MAX_OUTPUT_TOKENS,
            &mut settings.output_tokens,
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
            settings.inquiry = Some(v.to_string());
        }
    }
    if let Some((v, l)) = get("varies") {
        match ids::decode_reference(v) {
            Ok(_) => settings.varies = Some(v.to_string()),
            Err(e) => invalid(
                "varies",
                l,
                format!("line {l}: varies must be a stw1: reference ({e})."),
            ),
        }
    }
    for key in REQUIRED {
        if get(key).is_none() {
            defects.push(Defect::new(
                "setting_missing",
                None,
                Some(key),
                format!("the required key {key} is missing from the front matter."),
            ));
        }
    }
    let body = &text[body_offset..];
    if !body.chars().any(|c| !c.is_whitespace()) {
        defects.push(Defect::new(
            "question_empty",
            None,
            None,
            "the question body (after the closing --- line) has no non-whitespace character. Write your question there; the provider cannot carry an empty or blank text block, so this refusal is mechanical.",
        ));
    }
    if defects.is_empty() {
        Ok(Question {
            settings,
            body_offset,
            line_ending: if ending == "\n" { "LF" } else { "CRLF" },
        })
    } else {
        Err(defects)
    }
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

    const GOOD: &str = "---\nstewart: question/1\n# comment\nfamily: open-inquiry\nmodel: claude-opus-5-5\ndestination: /home/ana/returns\n\nlimit-turns: 200\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\n---\nAudit our app to make sure there are no bugs.\n";

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
        assert_eq!(q.settings.turns, 200);
        assert_eq!(q.settings.family, "open-inquiry");
        assert_eq!(q.line_ending, "LF");
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
        assert_eq!(reasons("stewart: question/1\n"), ["front_matter_invalid"]);
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
            reasons(&GOOD.replace("question/1", "question/2")),
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
}
