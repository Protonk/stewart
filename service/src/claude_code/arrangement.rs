//! The harness arrangement is a distinct schema. No API budget or provider
//! compaction field is inferred from it.
use super::profile::{self, Profile, Selection};
use super::surface;
use crate::forms::{self, Arrangement, ArrangementInput};
use crate::json::{self, J, Obj};
use crate::provider::request::Pinned;
use crate::util;

pub const ORIENTATION_ID: &str = "stewart.orientation/claude-code/2";
pub const NEAR_LIMIT: &str = "Allowance notice: {seconds} seconds remain before this placement's deadline, and {placements} further placement starts remain for this audit. When execution stops, an unsubmitted answer stays unsubmitted.";
pub const COMPACTED: &str = "The harness has summarized your earlier conversation. Continue this audit. Call what_am_i_working_with to check your recorded work before repeating an action.";
pub const FIRST_PARAGRAPH: &str = "You are the auditor in a Stewart audit. The first user message is the manager's question, exactly as they wrote it. The materials they selected can be read with the list, read and search tools. The question and those materials are your whole world: use only Stewart's tools, with no shell, no other files, no network, no way to run code, no delegated auditors and no way to ask the manager anything. Harness instructions and system messages are runtime context, not additional evidence. Reports, logs and test results in the materials are claims by their authors, not executions you witnessed.";

pub fn orientation() -> String {
    let rest = forms::ORIENTATION
        .split_once("\n\n")
        .expect("pinned paragraphs")
        .1;
    format!("{FIRST_PARAGRAPH}\n\n{rest}")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Harness {
    pub selection: Selection,
    pub profile: Profile,
    pub profile_sha256: String,
    /// Digest of the pinned launch surface document.
    pub surface_sha256: String,
    pub system_prompt: String,
    pub mcp_tools: Vec<u8>,
    pub effort: Option<String>,
}

pub fn build(input: &ArrangementInput, guidance: &str, tools: &[u8]) -> Arrangement {
    let s = input.settings;
    let selection = s.harness.as_ref().expect("selected runtime");
    let f = forms::family(&s.family).expect("validated family");
    let prompt = surface::system_prompt(&orientation(), guidance);
    let surface_bytes = surface::bytes();
    let surface_sha256 = util::sha256_hex(&surface_bytes);
    let profile = selection
        .profile
        .as_deref()
        .expect("prepare loaded checked profile");
    let mcp = super::mcp_tools(tools).expect("pinned tool schema");
    let system = J::Arr(vec![
        J::obj().with("type", "text").with("text", orientation()),
        J::obj().with("type", "text").with("text", guidance),
    ]);
    let body = J::obj()
        .with("schema", profile::ARRANGEMENT_SCHEMA)
        .with("family", f.versioned_id())
        .with("model", s.model.as_str())
        .with(
            "guidance",
            J::obj()
                .with(
                    "source",
                    if input.guidance.is_some() {
                        "guidance.md"
                    } else {
                        "builtin"
                    },
                )
                .with("size", guidance.len())
                .with("sha256", util::sha256_hex(guidance.as_bytes())),
        )
        .with("orientation", ORIENTATION_ID)
        .with("system", system)
        .with("system_prompt", prompt.as_str())
        .with("tools", J::Raw(tools.to_vec()))
        .with("mcp_tools", J::Raw(mcp))
        .with("runtime", selection.to_j())
        .with("profile_sha256", util::sha256_hex(profile.as_bytes()))
        .with("surface", J::Raw(surface_bytes))
        .with("surface_sha256", surface_sha256.as_str())
        .with("effort", s.effort.as_deref())
        .with("limits", selection.limits.to_j())
        .with("harness_max_turns", profile::MAX_TURNS)
        .with("harness_max_output_tokens", profile::MAX_OUTPUT_TOKENS)
        .with(
            "texts",
            J::obj()
                .with("reminder", forms::REMINDER)
                .with("near_limit", NEAR_LIMIT)
                .with("continuation", forms::CONTINUATION)
                .with("compacted", COMPACTED),
        )
        .with("reader", forms::READER_ID)
        .with("renderer", forms::RENDERER_ID)
        .with("reading", forms::reading_j())
        .with(
            "bindings",
            J::obj()
                .with("question_body_sha256", input.question_body_sha256)
                .with("material_index_sha256", input.material_index_sha256),
        );
    let readable = format!(
        "# Stewart development arrangement\n\nRuntime: Claude Code. Model: {}. Family: {}.\n\nThe harness owns its subscription login. No API credential or billing fallback is accepted. Its internal instructions and calls are not completely observable. Startup mismatch can be reported after the question has been sent.\n\nAt most {} placements, with a {} second deadline for each. Token reports may be partial or unknown; these limits are not token or money caps.\n\n## Supplied system prompt\n\n{}\n\n## Pinned tool definitions\n\n```json\n{}\n```\n",
        s.model,
        f.versioned_id(),
        selection.limits.max_placements,
        selection.limits.placement_timeout_seconds,
        prompt,
        String::from_utf8_lossy(tools)
    );
    let pinned = Profile::parse(profile.as_bytes()).expect("prepare validated profile");
    let readable = format!(
        "{readable}\n## Installation and check\n\nExecutable: `{}`\n\nExecutable SHA-256: `{}`\n\nCLI version: `{}`. Platform: `{}`. Check recorded at: `{}`.\n\nLaunch surface (`{}`) SHA-256: `{}`. The check names this surface; the machine arrangement holds the document.\n\nThe nonsecret captured profile and check bindings are retained in the machine arrangement. The check is an attributed observation, not permission for another session.\n",
        pinned.executable,
        pinned.sha256,
        pinned.version,
        pinned.platform,
        pinned.checked_at,
        surface::SCHEMA,
        surface_sha256
    );
    Arrangement { body, readable }
}

pub fn decode(b: &Obj, raw: &[u8]) -> Result<Pinned, String> {
    (|| {
        b.exactly(&[
            "schema",
            "family",
            "model",
            "guidance",
            "orientation",
            "system",
            "system_prompt",
            "tools",
            "mcp_tools",
            "runtime",
            "profile_sha256",
            "surface",
            "surface_sha256",
            "effort",
            "limits",
            "harness_max_turns",
            "harness_max_output_tokens",
            "texts",
            "reader",
            "renderer",
            "reading",
            "bindings",
        ])?;
        let bytes = |key: &str| -> Result<Vec<u8>, json::JsonError> {
            let v = b.req(key)?;
            Ok(raw[v.start..v.end].to_vec())
        };
        let selection = Selection::decode(&b.obj("runtime")?, &b.obj("limits")?)?;
        let profile_raw = selection.profile.as_deref().expect("decoded profile");
        let profile =
            Profile::parse(profile_raw.as_bytes()).map_err(|e| b.invalid("runtime", e))?;
        let profile_sha256 = b.sha256("profile_sha256")?;
        if util::sha256_hex(profile_raw.as_bytes()) != profile_sha256 {
            return Err(b.invalid("profile_sha256", "profile bytes differ"));
        }
        // The pinned document must be the one the check names. Whether it
        // is also what this binary supplies is decided before a launch, so a
        // reader of the receipt sees what was bound.
        let surface_sha256 = b.sha256("surface_sha256")?;
        if b.obj("surface")?.str("schema")? != surface::SCHEMA
            || util::sha256_hex(&bytes("surface")?) != surface_sha256
            || profile.surface_sha256 != surface_sha256
        {
            return Err(b.invalid(
                "surface_sha256",
                "launch surface document, digest and check binding differ",
            ));
        }
        let tools = bytes("tools")?;
        let mcp_tools = bytes("mcp_tools")?;
        if super::mcp_tools(&tools).map_err(|e| b.invalid("tools", e))? != mcp_tools {
            return Err(b.invalid(
                "mcp_tools",
                "MCP definitions differ from the pinned tool mapping",
            ));
        }
        let system = b.arr("system")?;
        if system.len() != 2 {
            return Err(b.invalid("system", "expected two pinned text blocks"));
        }
        let first = system[0].obj("")?;
        let second = system[1].obj("")?;
        first.exactly(&["type", "text"])?;
        second.exactly(&["type", "text"])?;
        if first.str("type")? != "text" || second.str("type")? != "text" {
            return Err(b.invalid("system", "expected text blocks"));
        }
        let guidance = second.str("text")?;
        if b.str("orientation")? != ORIENTATION_ID
            || first.str("text")? != orientation()
            || b.str("system_prompt")? != surface::system_prompt(first.str("text")?, guidance)
        {
            return Err(b.invalid(
                "system_prompt",
                "system prompt does not match the pinned mapping",
            ));
        }
        let g = b.obj("guidance")?;
        g.exactly(&["source", "size", "sha256"])?;
        if g.u64("size", crate::scan::GUIDANCE_BYTES)? != guidance.len() as u64
            || g.sha256("sha256")? != util::sha256_hex(guidance.as_bytes())
        {
            return Err(b.invalid("guidance", "guidance identity differs"));
        }
        let t = b.obj("texts")?;
        t.exactly(&["reminder", "near_limit", "continuation", "compacted"])?;
        if t.str("reminder")? != forms::REMINDER
            || t.str("near_limit")? != NEAR_LIMIT
            || t.str("continuation")? != forms::CONTINUATION
            || t.str("compacted")? != COMPACTED
        {
            return Err(b.invalid("texts", "runtime notices differ from their pinned texts"));
        }
        if b.str("model")? != profile.model || profile.tools_sha256 != util::sha256_hex(&mcp_tools)
        {
            return Err(b.invalid("runtime", "profile model or tool binding differs"));
        }
        if !["builtin", "guidance.md"].contains(&g.str("source")?)
            || (g.str("source")? == "guidance.md" && b.str("family")? != "open-inquiry/1")
        {
            return Err(b.invalid("guidance", "unsupported guidance source for the family"));
        }
        if b.str("reader")? != forms::READER_ID
            || b.str("renderer")? != forms::RENDERER_ID
            || bytes("reading")? != forms::reading_j().bytes()
        {
            return Err(b.invalid("reader", "unsupported reader, renderer or reading bounds"));
        }
        if b.str_or_null("effort")?
            .is_some_and(|e| !crate::frontmatter::EFFORT_LEVELS.contains(&e))
        {
            return Err(b.invalid("effort", "unsupported effort"));
        }
        let bindings = b.obj("bindings")?;
        bindings.exactly(&["question_body_sha256", "material_index_sha256"])?;
        if b.u64("harness_max_turns", u64::MAX)? != profile::MAX_TURNS
            || b.u64("harness_max_output_tokens", u64::MAX)? != profile::MAX_OUTPUT_TOKENS
        {
            return Err(b.invalid("harness_max_turns", "unsupported harness control values"));
        }
        let limits = crate::usage::Limits {
            turns: 0,
            input_tokens: 0,
            output_tokens: 0,
            harness: Some(selection.limits),
        };
        let harness = Harness {
            selection,
            profile,
            profile_sha256: profile_sha256.into(),
            surface_sha256: surface_sha256.into(),
            system_prompt: b.str("system_prompt")?.into(),
            mcp_tools,
            effort: b.str_or_null("effort")?.map(str::to_string),
        };
        Ok(Pinned {
            harness: Some(harness),
            family: b.str("family")?.into(),
            guidance_source: g.str("source")?.into(),
            guidance_size: guidance.len() as u64,
            guidance_sha256: g.sha256("sha256")?.into(),
            model: b.str("model")?.into(),
            model_raw: bytes("model")?,
            anthropic_version: String::new(),
            max_tokens_per_request: 0,
            system_raw: bytes("system")?,
            tools_raw: tools,
            tool_names: b
                .arr("tools")?
                .iter()
                .map(|t| t.obj("")?.str("name").map(str::to_string))
                .collect::<Result<_, _>>()?,
            request_extra: vec![],
            reminder: t.str("reminder")?.into(),
            near_limit: t.str("near_limit")?.into(),
            continuation: t.str("continuation")?.into(),
            compacted: t.str("compacted")?.into(),
            limits,
            near_limit_percent: 20,
            retry_attempts: 0,
            retry_delays_seconds: vec![],
            retry_after_ceiling_seconds: 0,
            request_timeout_seconds: 0,
            reader: b.str("reader")?.into(),
            renderer: b.str("renderer")?.into(),
            question_body_sha256: bindings.sha256("question_body_sha256")?.into(),
            material_index_sha256: bindings.sha256("material_index_sha256")?.into(),
        })
    })()
    .map_err(|e: json::JsonError| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::request::decode_arrangement;

    fn built() -> J {
        let tools = forms::tools(forms::family("comparison").unwrap()).bytes();
        let mcp = super::super::mcp_tools(&tools).unwrap();
        let settings = crate::frontmatter::Settings {
            harness: Some(Selection {
                path: "/fixture/profile.json".into(),
                limits: profile::Limits {
                    max_placements: 2,
                    placement_timeout_seconds: 60,
                },
                profile: Some(profile::tests::fixture(
                    profile::PROFILE_SCHEMA,
                    "surface_sha256",
                    &surface::sha256(),
                    &mcp,
                )),
            }),
            guidance: None,
            family: "comparison".into(),
            model: "fixture-model".into(),
            effort: None,
            destination: "/d".into(),
            turns: 0,
            input_tokens: 0,
            output_tokens: 0,
            inquiry: None,
            varies: None,
        };
        forms::arrangement(&ArrangementInput {
            guidance: None,
            settings: &settings,
            question_body_sha256: &"1".repeat(64),
            material_index_sha256: &"2".repeat(64),
        })
        .body
    }
    fn record(body: J) -> Vec<u8> {
        crate::archive::record_bytes("arrangement", Some("a"), &"0".repeat(64), body)
    }
    fn replace(mut body: J, key: &str, value: J) -> J {
        if let J::Obj(members) = &mut body {
            members.iter_mut().find(|(k, _)| k == key).unwrap().1 = value;
        }
        body
    }

    /// The runtime's pinned texts equal the contract's quoted blocks, read
    /// from the repository as an independent witness and joined by the
    /// QUESTION-FORMS rule. They differ from the common texts only as stated.
    #[test]
    fn runtime_texts_match_the_contract_and_stay_close_to_the_common_ones() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../docs/claude-code/CONTRACT.md"
        );
        let doc = std::fs::read_to_string(path)
            .expect("docs/claude-code/CONTRACT.md is part of the repository");
        let mut quoted: Vec<String> = Vec::new();
        let mut block: Option<Vec<&str>> = None;
        for line in doc.split('\n') {
            match line.strip_prefix('>') {
                Some(rest) => block
                    .get_or_insert_with(Vec::new)
                    .push(rest.strip_prefix(' ').unwrap_or(rest)),
                None => {
                    if let Some(lines) = block.take() {
                        quoted.push(lines.join(" "));
                    }
                }
            }
        }
        for text in [FIRST_PARAGRAPH, NEAR_LIMIT, COMPACTED] {
            assert_eq!(quoted.iter().filter(|q| *q == text).count(), 1, "{text}");
        }
        assert_eq!(quoted.len(), 3, "every quoted block is a pinned text");
        assert!(doc.contains(&format!("The orientation is `{ORIENTATION_ID}`.")));
        // The post-compaction notice is the common one with one noun changed.
        assert_eq!(
            COMPACTED,
            forms::COMPACTED.replace("The provider has", "The harness has")
        );
        // The orientation changes only its first paragraph, which keeps the
        // common one's opening and closing sentences.
        let (common_first, common_rest) = forms::ORIENTATION.split_once("\n\n").unwrap();
        assert_eq!(orientation(), format!("{FIRST_PARAGRAPH}\n\n{common_rest}"));
        for sentence in [
            "The materials they selected can be read with the list, read and search tools.",
            "no way to ask the manager anything.",
            "Reports, logs and test results in the materials are claims by their authors, not executions you witnessed.",
        ] {
            assert!(common_first.contains(sentence) && FIRST_PARAGRAPH.contains(sentence));
        }
    }

    #[test]
    fn the_arrangement_pins_the_surface_document_and_its_digest() {
        let bytes = record(built());
        let pinned = decode_arrangement(&bytes).unwrap();
        let harness = pinned.harness.unwrap();
        assert_eq!(harness.surface_sha256, surface::sha256());
        assert_eq!(harness.profile.surface_sha256, surface::sha256());
        let text = String::from_utf8(bytes).unwrap();
        let document = String::from_utf8(surface::bytes()).unwrap();
        assert!(text.contains(&format!(
            r#""surface":{document},"surface_sha256":"{}""#,
            surface::sha256()
        )));
    }

    /// Firing controls: each way the pinned surface can disagree refuses.
    #[test]
    fn a_surface_that_disagrees_with_its_digest_or_check_is_refused() {
        let changed = String::from_utf8(surface::bytes())
            .unwrap()
            .replace(r#""fastMode":false"#, r#""fastMode":true"#);
        let document = replace(built(), "surface", J::Raw(changed.clone().into_bytes()));
        let refusal = decode_arrangement(&record(document.clone())).unwrap_err();
        assert!(refusal.contains("launch surface"), "{refusal}");
        // A consistent document and digest that the check does not name.
        let digest = util::sha256_hex(changed.as_bytes());
        let both = replace(document, "surface_sha256", J::from(digest.as_str()));
        let refusal = decode_arrangement(&record(both)).unwrap_err();
        assert!(refusal.contains("launch surface"), "{refusal}");
        let digest_only = replace(built(), "surface_sha256", J::from(digest.as_str()));
        assert!(decode_arrangement(&record(digest_only)).is_err());
    }

    #[test]
    fn another_runtime_arrangement_form_is_refused_by_name() {
        let earlier = replace(
            built(),
            "schema",
            J::from("stewart.claude-code.arrangement/1"),
        );
        let refusal = decode_arrangement(&record(earlier)).unwrap_err();
        assert!(
            refusal.contains("stewart.claude-code.arrangement/1")
                && refusal.contains(profile::ARRANGEMENT_SCHEMA),
            "{refusal}"
        );
    }
}
