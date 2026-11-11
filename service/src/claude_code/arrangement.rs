//! The harness arrangement is a distinct schema. No API budget or provider
//! compaction field is inferred from it.
use super::profile::{self, Profile, Selection};
use crate::forms::{self, Arrangement, ArrangementInput};
use crate::json::{self, J, Obj};
use crate::provider::request::Pinned;
use crate::util;

pub const ORIENTATION_ID: &str = "stewart.orientation/claude-code/1";
pub const NEAR_LIMIT: &str = "Allowance notice: {seconds} seconds remain before this placement's deadline, and {placements} further placement starts remain for this audit. When execution stops, an unsubmitted answer stays unsubmitted.";
pub const COMPACTED: &str = "The harness reports that it summarized earlier conversation. Continue this audit from your recorded work; call what_am_i_working_with before repeating an action.";
pub const FIRST_PARAGRAPH: &str = "You are the auditor in a Stewart audit. The first user message is the manager's question, exactly as they wrote it. Use only the commissioned question, captured materials and Stewart's MCP tools for this inquiry. Do not use shell, general file access, network retrieval, project execution or delegated auditors. Harness instructions and system messages are runtime context, not additional evidence. Reports, logs and test results in the materials are claims by their authors, not executions you witnessed.";

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
    pub system_prompt: String,
    pub mcp_tools: Vec<u8>,
    pub effort: Option<String>,
}

pub fn build(input: &ArrangementInput, guidance: &str, tools: &[u8]) -> Arrangement {
    let s = input.settings;
    let selection = s.harness.as_ref().expect("selected runtime");
    let f = forms::family(&s.family).expect("validated family");
    let prompt = format!("{}\n\n{guidance}", orientation());
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
        "{readable}\n## Installation and check\n\nExecutable: `{}`\n\nExecutable SHA-256: `{}`\n\nCLI version: `{}`. Platform: `{}`. Check recorded at: `{}`.\n\nThe nonsecret captured profile and check bindings are retained in the machine arrangement. The check is an attributed observation, not permission for another session.\n",
        pinned.executable, pinned.sha256, pinned.version, pinned.platform, pinned.checked_at
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
            || b.str("system_prompt")? != format!("{}\n\n{guidance}", first.str("text")?)
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
