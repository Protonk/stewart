//! The question families, their pinned texts and tool definitions, and the
//! arrangement prepare pins (QUESTION-FORMS; INTERFACE 6.2).
//!
//! Texts are exact. In the pinned bytes the lines of a quoted paragraph are
//! joined by single spaces, paragraphs are joined by `\n\n`, and a text has no
//! trailing LF. They change only with a new version identifier.

use crate::json::{J, quote};

pub const ORIENTATION_ID: &str = "stewart.orientation/1";
pub const RENDERER_ID: &str = "stewart.render/1";
pub const READER_ID: &str = "utf8-text/1";
pub const ARRANGEMENT_SCHEMA: &str = "stewart.arrangement/1";
/// The Messages API version this release pins (INTERFACE 6.1): the
/// `anthropic-version` header of every request and the arrangement's
/// `anthropic_version` member.
pub const ANTHROPIC_VERSION: &str = "2026-10-21";
/// Output tokens requested per provider request (before the remaining
/// allowance lowers it). Pinned by the release.
pub const MAX_TOKENS_PER_REQUEST: u64 = 16_000;
pub const NEAR_LIMIT_PERCENT: u64 = 20;
pub const REQUEST_TIMEOUT_SECONDS: u64 = 600;
/// Provider retry policy (INTERFACE 6.6): attempts per request, the delays
/// before attempts 2, 3 and 4, and the longest `retry-after` waited for.
pub const RETRY_ATTEMPTS: u64 = 4;
pub const RETRY_DELAYS_SECONDS: [u64; 3] = [2, 8, 30];
pub const RETRY_AFTER_CEILING_SECONDS: u64 = 60;

pub const ORIENTATION: &str = concat!(
    "You are the auditor in a Stewart audit. The first user message is the manager's question, exactly as they wrote it. The materials they selected can be read with the list, read and search tools. The question and those materials are your whole world: you have no shell, no other files, no network, no way to run code and no way to ask the manager anything. Reports, logs and test results in the materials are claims by their authors, not executions you witnessed.",
    "\n\n",
    "Your answer is the entries you record with the record tools, and each entry is attributed to you. You may record that the material is inadequate, that you are uncertain, that you disagree with the question's premise or that you found no supported finding. None of these needs a defect, a winner or a repair. An answer with missing sections, or with no entries, can be submitted.",
    "\n\n",
    "Record your account early, even briefly, and replace it as your work develops. Replacing an entry keeps its place. To cite, use the ranges that read and search return, or give a quote of exact text. Searching for distinctive text gives a ready citation. Citations are checked only for exact location and quotation, never for whether they support what you say.",
    "\n\n",
    "Use handles exactly as tools return them. If a tool says a handle is stale, read the current one before replacing it. If your context was summarized, or you are unsure what you have recorded, call what_am_i_working_with.",
    "\n\n",
    "When you are ready, call prepare to see exactly what would be sealed, then call submit with that handle and confirm set to true. Submitting seals your answer, and it cannot be edited afterwards. Your limits are cumulative across the whole audit; what_am_i_working_with shows what remains."
);

pub const OPEN_INQUIRY: &str = "Address the question from the supplied materials. Begin your account with your direct response to the question and its reach, including when you cannot answer it as asked; do not leave a decisive inability only in a final limitation. Record observations that connect what you found to its basis in the materials. Record limits on what the materials let you establish. No positive finding and no universal assurance is required. When you use a label from the materials, such as a requirement number, explain it in ordinary words the first time.";

pub const INQUIRY_FRAMING: &str = "The manager has described a concern. Formulate a working question that the supplied materials can bear on, record it, and record how it relates to the original concern. Then investigate it in this audit and record what you find. The manager's question stays as written; if it is already precise, it can be your working question. If useful bounded investigation is not possible with these materials, say so and explain why. Begin your account with your direct response and its reach. Record observations with their basis and record the limits of what you could establish. When you use a label from the materials, explain it in ordinary words the first time.";

pub const COMPARISON: &str = "Compare the alternatives the question names, using the supplied evidence. Record the criterion, saying what the manager supplied and what is your interpretation of it. Use a comparison entry for a finding that relates the alternatives to each other, and an observation for a finding about one alternative or about the materials. Distinguish what you reasoned from the source yourself from what supplied materials report. If the evidence is unequal, the criterion is unavailable or a comparison is not possible, say so; no winner is required. Begin your account with your direct response and its reach, and record the limits of what you could establish. When you use a label from the materials, explain it in ordinary words the first time.";

pub const REMINDER: &str = "This turn ended without a submission. Your recorded answer remains unsealed. If you intend to submit it, use prepare and confirm its handle with submit.";

pub const NEAR_LIMIT: &str = "Allowance notice: {turns} turns, {input_tokens} input tokens and {output_tokens} output tokens remain for this audit. When an allowance runs out the run stops, and an unsubmitted answer stays unsubmitted.";

pub const CONTINUATION: &str = "This audit is continuing in a new conversation after an earlier run ended. Your recorded work is preserved, but this conversation does not contain it. Call what_am_i_working_with to see what you have recorded. Your last action before the interruption may or may not have been recorded; check before repeating it.";

pub struct Family {
    pub id: &'static str,
    pub version: u32,
    pub title: &'static str,
    pub instructions: &'static str,
    /// Recording tools, in tools-array order.
    pub tools: &'static [&'static str],
    /// Recording tools whose absence prepare's notices name.
    pub sections: &'static [&'static str],
}

pub const FAMILIES: [Family; 3] = [
    Family {
        id: "open-inquiry",
        version: 1,
        title: "Open inquiry",
        instructions: OPEN_INQUIRY,
        tools: &["record_account", "record_observation", "record_limit"],
        sections: &["record_account", "record_observation", "record_limit"],
    },
    Family {
        id: "inquiry-framing",
        version: 1,
        title: "Inquiry framing",
        instructions: INQUIRY_FRAMING,
        tools: &[
            "record_working_question",
            "record_relation",
            "record_observation",
            "record_account",
            "record_limit",
        ],
        sections: &[
            "record_working_question",
            "record_relation",
            "record_observation",
            "record_account",
            "record_limit",
        ],
    },
    Family {
        id: "comparison",
        version: 1,
        title: "Comparison",
        instructions: COMPARISON,
        tools: &[
            "record_criterion",
            "record_comparison",
            "record_observation",
            "record_account",
            "record_limit",
        ],
        sections: &[
            "record_criterion",
            "record_comparison",
            "record_account",
            "record_limit",
        ],
    },
];

pub fn family(id: &str) -> Option<&'static Family> {
    FAMILIES.iter().find(|f| f.id == id)
}

impl Family {
    pub fn versioned_id(&self) -> String {
        format!("{}/{}", self.id, self.version)
    }
}

pub fn tool_description(name: &str) -> &'static str {
    match name {
        "list" => {
            "List the captured materials: their names (materials/…), sizes and line counts. Long lists come in pages."
        }
        "read" => {
            "Read exact text from the question (source \"question\"), a material (materials/…), one of your entries (its handle) or a prepared view. Returns up to 64 KiB per call, and a next call when more remains. For the question and materials, the reply's cite is a ready citation for what was returned. The exact text is the second content block, or the reply's text field when the page is blank; bytes recorded as base64 come in its base64 field."
        }
        "search" => {
            "Find exact, case-sensitive text in the question and all materials, or in the sources you name. Each hit's cite is a ready citation. The reply says whether the whole scope was searched; an incomplete search does not show that text is absent."
        }
        "record_account" => {
            "Record your account: the direct response to the question and its reach, including any inability to answer it as asked."
        }
        "record_observation" => "Record one observation and its basis in the materials.",
        "record_limit" => "Record a limit on what the materials let you establish.",
        "record_working_question" => "Record the working question you will investigate.",
        "record_relation" => {
            "Record how the working question relates to the manager's original concern."
        }
        "record_criterion" => {
            "Record the criterion for the comparison, saying what the manager supplied and what is your interpretation."
        }
        "record_comparison" => "Record a finding that relates the alternatives to each other.",
        "record_artifact" => {
            "Record a free-form artifact with a label: text, or base64 for bytes that are not text. It belongs to your answer but fills no section."
        }
        "replace" => {
            "Replace exactly one version of an entry, given its handle. Supply every field: text, citations and label for a recorded entry; label and text or base64 for an artifact. The entry keeps its place."
        }
        "delete" => "Remove exactly one version of an entry from your answer.",
        "what_am_i_working_with" => {
            "Show the audit's state: what you have recorded and its handles, recent edits and refusals, the question and materials, and your remaining allowances. Use it when continuing or after your context was summarized."
        }
        "prepare" => {
            "Make the exact candidate that submit would seal, with its Markdown rendering and factual notes on empty sections. It changes nothing, and you can keep editing."
        }
        "submit" => {
            "Seal a prepared candidate as your answer. Without confirm set to true this is a dry run. After a confirmed submit the answer cannot be edited."
        }
        _ => "",
    }
}

fn prop(ty: &str, description: &str) -> J {
    J::obj().with("type", ty).with("description", description)
}

fn int_prop(minimum: u64, description: &str) -> J {
    J::obj()
        .with("type", "integer")
        .with("minimum", minimum)
        .with("description", description)
}

fn arr_prop(items: J, max_items: u64, description: &str) -> J {
    J::obj()
        .with("type", "array")
        .with("items", items)
        .with("maxItems", max_items)
        .with("description", description)
}

/// The citation item schema, exactly as QUESTION-FORMS gives it.
pub fn citation_schema() -> J {
    J::obj()
        .with("type", "object")
        .with(
            "properties",
            J::obj()
                .with("source", prop("string", "question or materials/<name>."))
                .with(
                    "start",
                    int_prop(0, "Byte offset where the cited span begins."),
                )
                .with("end", int_prop(1, "Byte offset just after the cited span."))
                .with("quote", prop("string", "Exact text of the cited span.")),
        )
        .with("required", crate::json::strs(&["source"]))
        .with("additionalProperties", false)
}

fn tool(name: &str, properties: J, required: &[&str]) -> J {
    J::obj()
        .with("name", name)
        .with("description", tool_description(name))
        .with(
            "input_schema",
            J::obj()
                .with("type", "object")
                .with("properties", properties)
                .with("required", crate::json::strs(required))
                .with("additionalProperties", false),
        )
}

fn record_tool(name: &str) -> J {
    tool(
        name,
        J::obj()
            .with("text", prop("string", "Entry text. It may be empty."))
            .with(
                "citations",
                arr_prop(citation_schema(), 64, "Citations: {source, start, end, quote?} from read or search, or {source, quote} with exact text."),
            )
            .with("label", prop("string", "Optional short label shown in the rendering.")),
        &["text"],
    )
}

/// The tools array for a family, in the pinned order.
pub fn tools(f: &Family) -> J {
    let mut out = vec![
        tool("list", J::obj().with("cursor", prop("string", "Cursor from the previous list reply's next call, for the next page.")), &[]),
        tool(
            "read",
            J::obj()
                .with("source", prop("string", "What to read: question, materials/<name>, one of your entry handles or a prepared view."))
                .with("start", int_prop(0, "Byte offset to start from. Default 0; use the start that a reply's next call gives.")),
            &["source"],
        ),
        tool(
            "search",
            J::obj()
                .with("text", prop("string", "Exact text to find. Matching is literal and case-sensitive."))
                .with("sources", arr_prop(J::obj().with("type", "string"), 128, "Sources to search. Default: the question and every material."))
                .with("cursor", prop("string", "Cursor from the previous search reply's next call. Give it with the same text and sources.")),
            &["text"],
        ),
    ];
    for t in f.tools {
        out.push(record_tool(t));
    }
    out.push(tool(
        "record_artifact",
        J::obj()
            .with(
                "label",
                prop(
                    "string",
                    "Required short label for the artifact, shown in the rendering.",
                ),
            )
            .with("text", prop("string", "Artifact content as text."))
            .with(
                "base64",
                prop(
                    "string",
                    "Artifact bytes as base64, for content that is not text.",
                ),
            ),
        &["label"],
    ));
    out.push(tool(
        "replace",
        J::obj()
            .with("entry", prop("string", "The exact handle of the entry version to replace."))
            .with("label", prop("string", "Required label for the replacement, shown in the rendering. Give the current label to keep it."))
            .with("text", prop("string", "Replacement text."))
            .with("citations", arr_prop(citation_schema(), 64, "Replacement citations, as for the record tools. Use [] for none."))
            .with("base64", prop("string", "Replacement artifact bytes as base64.")),
        &["entry", "label"],
    ));
    out.push(tool(
        "delete",
        J::obj().with(
            "entry",
            prop("string", "The exact handle of the entry version to remove."),
        ),
        &["entry"],
    ));
    out.push(tool(
        "what_am_i_working_with",
        J::obj().with(
            "page",
            prop(
                "string",
                "Cursor from the previous reply's next call, for the next page of entries.",
            ),
        ),
        &[],
    ));
    out.push(tool("prepare", J::obj(), &[]));
    out.push(tool(
        "submit",
        J::obj()
            .with(
                "prepared",
                prop("string", "The handle that prepare returned."),
            )
            .with(
                "confirm",
                prop(
                    "boolean",
                    "Set to true to seal. Otherwise this is a dry run.",
                ),
            ),
        &["prepared"],
    ));
    J::Arr(out)
}

/// The exact `system` array: orientation block, then family instructions.
pub fn system(f: &Family) -> Vec<u8> {
    format!(
        r#"[{{"type":"text","text":{}}},{{"type":"text","text":{}}}]"#,
        quote(ORIENTATION),
        quote(f.instructions)
    )
    .into_bytes()
}

// Bounds of the auditor's reading tools (Appendix B).
/// A `read` page of text.
pub const READ_PAGE_BYTES: u64 = 65_536;
/// A `read` page of a binary artifact, before base64.
pub const BINARY_PAGE_BYTES: u64 = 49_152;
/// `search` text, at most.
pub const SEARCH_TEXT_BYTES: u64 = 1_024;
pub const SEARCH_HITS_PER_PAGE: u64 = 128;
pub const SEARCH_CONTEXT_BYTES_PER_PAGE: u64 = 32_768;
pub const CONTEXT_BYTES_PER_HIT: u64 = 240;
/// `search` names at most this many sources.
pub const SEARCH_SOURCES: u64 = 128;
pub const LIST_PAGE_MATERIALS: u64 = 128;
/// One tool call's input, at most (`input_too_large`).
pub const TOOL_INPUT_BYTES: u64 = 4 * 1024 * 1024;

/// Bounds and pagination rules of the auditor's reading tools, pinned so the
/// manager can see the truncation and continuation rules before commissioning.
pub fn reading_j() -> J {
    J::obj()
        .with("read_page_bytes", READ_PAGE_BYTES)
        .with("binary_page_bytes", BINARY_PAGE_BYTES)
        .with("search_text_bytes", SEARCH_TEXT_BYTES)
        .with("search_hits_per_page", SEARCH_HITS_PER_PAGE)
        .with(
            "search_context_bytes_per_page",
            SEARCH_CONTEXT_BYTES_PER_PAGE,
        )
        .with("context_bytes_per_hit", CONTEXT_BYTES_PER_HIT)
        .with("list_page_materials", LIST_PAGE_MATERIALS)
        .with("tool_input_bytes", TOOL_INPUT_BYTES)
}

pub struct Arrangement {
    /// The `body` of the arrangement record.
    pub body: J,
    pub readable: String,
}

pub struct ArrangementInput<'a> {
    pub settings: &'a crate::frontmatter::Settings,
    pub question_body_sha256: &'a str,
    pub material_index_sha256: &'a str,
}

pub fn arrangement(input: &ArrangementInput) -> Arrangement {
    let s = input.settings;
    let f = family(&s.family).expect("family validated by the front matter parser");
    let system = system(f);
    let tools = tools(f).bytes();
    let body = J::obj()
        .with("schema", ARRANGEMENT_SCHEMA)
        .with("family", f.versioned_id())
        .with("orientation", ORIENTATION_ID)
        .with("model", s.model.as_str())
        .with("anthropic_version", ANTHROPIC_VERSION)
        .with("max_tokens_per_request", MAX_TOKENS_PER_REQUEST)
        .with("system", J::Raw(system.clone()))
        .with("tools", J::Raw(tools.clone()))
        .with("request_extra", J::Raw(b"{}".to_vec()))
        .with(
            "texts",
            J::obj()
                .with("reminder", REMINDER)
                .with("near_limit", NEAR_LIMIT)
                .with("continuation", CONTINUATION),
        )
        .with(
            "limits",
            J::obj()
                .with("turns", s.turns)
                .with("input_tokens", s.input_tokens)
                .with("output_tokens", s.output_tokens),
        )
        .with("near_limit_percent", NEAR_LIMIT_PERCENT)
        .with(
            "retry",
            J::obj()
                .with("attempts", RETRY_ATTEMPTS)
                .with(
                    "delays_seconds",
                    J::Arr(RETRY_DELAYS_SECONDS.iter().map(|d| J::Int(*d)).collect()),
                )
                .with("retry_after_ceiling_seconds", RETRY_AFTER_CEILING_SECONDS),
        )
        .with("request_timeout_seconds", REQUEST_TIMEOUT_SECONDS)
        .with("reader", READER_ID)
        .with("renderer", RENDERER_ID)
        .with("reading", reading_j())
        .with(
            "bindings",
            J::obj()
                .with("question_body_sha256", input.question_body_sha256)
                .with("material_index_sha256", input.material_index_sha256),
        );
    let readable = readable(f, input, &tools);
    Arrangement { body, readable }
}

/// A pinned arrangement read back from `prep/<n>/arrangement.json` (6.2):
/// what the run splices into requests, as exact bytes, and what the tools
/// and the seal need. The run loads it through the `accepted` record, the
/// receipt and the receipt's `arrangement` member, checking each digest.
#[derive(Debug, Clone)]
pub struct Pinned {
    /// The family ID and version, `open-inquiry/1`.
    pub family: String,
    pub model: String,
    /// The exact bytes of the `model` value (a JSON string).
    pub model_raw: Vec<u8>,
    pub anthropic_version: String,
    pub max_tokens_per_request: u64,
    /// The exact bytes of the `system` array.
    pub system_raw: Vec<u8>,
    /// The exact bytes of the `tools` array.
    pub tools_raw: Vec<u8>,
    /// The tool names, in `tools` order.
    pub tool_names: Vec<String>,
    /// Each member of `request_extra` as its raw `"key":value` bytes. The
    /// release's allowlist is empty, so an arrangement with members is refused.
    pub request_extra: Vec<Vec<u8>>,
    pub reminder: String,
    /// The near-limit template, with `{turns}`, `{input_tokens}` and
    /// `{output_tokens}` to fill.
    pub near_limit: String,
    pub continuation: String,
    pub limits: crate::usage::Limits,
    pub near_limit_percent: u64,
    pub retry_attempts: u64,
    pub retry_delays_seconds: Vec<u64>,
    pub retry_after_ceiling_seconds: u64,
    pub request_timeout_seconds: u64,
    pub reader: String,
    pub renderer: String,
    pub question_body_sha256: String,
    pub material_index_sha256: String,
}

impl Pinned {
    /// The family this arrangement pins, if this release knows it.
    pub fn family(&self) -> Option<&'static Family> {
        let (id, version) = self.family.split_once('/')?;
        family(id).filter(|f| f.version.to_string() == version)
    }
}

/// Decode an arrangement record strictly, keeping the pinned members' bytes.
pub fn decode_arrangement(bytes: &[u8]) -> Result<Pinned, String> {
    use crate::json::{JsonError, value_err};
    let r = crate::archive::decode_record(bytes)?;
    if r.kind != "arrangement" {
        return Err(format!("the arrangement has kind {:?}", r.kind));
    }
    let b = r.body();
    let raw = |k: &str| -> Result<Vec<u8>, JsonError> {
        let v = b.req(k)?;
        Ok(bytes[v.start..v.end].to_vec())
    };
    let res = (|| {
        b.exactly(&[
            "schema",
            "family",
            "orientation",
            "model",
            "anthropic_version",
            "max_tokens_per_request",
            "system",
            "tools",
            "request_extra",
            "texts",
            "limits",
            "near_limit_percent",
            "retry",
            "request_timeout_seconds",
            "reader",
            "renderer",
            "reading",
            "bindings",
        ])?;
        if b.str("schema")? != ARRANGEMENT_SCHEMA {
            return Err(b.invalid("schema", format!("expected {ARRANGEMENT_SCHEMA}")));
        }
        let mut tool_names = Vec::new();
        for (i, t) in b.arr("tools")?.iter().enumerate() {
            tool_names.push(t.obj(&format!("/body/tools/{i}"))?.str("name")?.to_string());
        }
        b.arr("system")?;
        let extra = b.obj("request_extra")?;
        if !extra.members.is_empty() {
            return Err(value_err(
                "/body/request_extra",
                extra.at,
                "this release's request_extra allowlist is empty",
            ));
        }
        let t = b.obj("texts")?;
        t.exactly(&["reminder", "near_limit", "continuation"])?;
        let l = b.obj("limits")?;
        l.exactly(&["turns", "input_tokens", "output_tokens"])?;
        let retry = b.obj("retry")?;
        retry.exactly(&["attempts", "delays_seconds", "retry_after_ceiling_seconds"])?;
        let delays = retry
            .arr("delays_seconds")?
            .iter()
            .map(|d| {
                d.as_u64().ok_or_else(|| {
                    value_err("/body/retry/delays_seconds", d.start, "expected integers")
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        let bind = b.obj("bindings")?;
        bind.exactly(&["question_body_sha256", "material_index_sha256"])?;
        Ok::<_, JsonError>(Pinned {
            family: b.str("family")?.to_string(),
            model: b.str("model")?.to_string(),
            model_raw: raw("model")?,
            anthropic_version: b.str("anthropic_version")?.to_string(),
            max_tokens_per_request: b.u64("max_tokens_per_request", u64::MAX)?,
            system_raw: raw("system")?,
            tools_raw: raw("tools")?,
            tool_names,
            request_extra: Vec::new(),
            reminder: t.str("reminder")?.to_string(),
            near_limit: t.str("near_limit")?.to_string(),
            continuation: t.str("continuation")?.to_string(),
            limits: crate::usage::Limits {
                turns: l.u64("turns", crate::frontmatter::MAX_TURNS)?,
                input_tokens: l.u64("input_tokens", crate::frontmatter::MAX_INPUT_TOKENS)?,
                output_tokens: l.u64("output_tokens", crate::frontmatter::MAX_OUTPUT_TOKENS)?,
            },
            near_limit_percent: b.u64("near_limit_percent", 100)?,
            retry_attempts: retry.u64("attempts", u64::MAX)?,
            retry_delays_seconds: delays,
            retry_after_ceiling_seconds: retry.u64("retry_after_ceiling_seconds", u64::MAX)?,
            request_timeout_seconds: b.u64("request_timeout_seconds", u64::MAX)?,
            reader: b.str("reader")?.to_string(),
            renderer: b.str("renderer")?.to_string(),
            question_body_sha256: bind.sha256("question_body_sha256")?.to_string(),
            material_index_sha256: bind.sha256("material_index_sha256")?.to_string(),
        })
    })();
    res.map_err(|e| e.to_string())
}

fn quoted_block(text: &str) -> String {
    text.split('\n')
        .map(|l| {
            if l.is_empty() {
                ">".to_string()
            } else {
                format!("> {l}")
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn readable(f: &Family, input: &ArrangementInput, tools_bytes: &[u8]) -> String {
    let s = input.settings;
    let mut md = String::new();
    md.push_str("# Stewart arrangement\n\n");
    md.push_str("This is the readable form of the arrangement pinned by this preparation. The machine form, arrangement.json, holds the exact bytes the run sends; this file restates them for inspection. Commissioning uses the pinned arrangement, never a later installation's forms.\n\n");
    md.push_str("## Identity\n\n");
    md.push_str(&format!("- Schema: {ARRANGEMENT_SCHEMA}\n"));
    md.push_str(&format!(
        "- Family: {} ({}). The auditor never sees the family name.\n",
        f.versioned_id(),
        f.title
    ));
    md.push_str(&format!("- Orientation: {ORIENTATION_ID}\n"));
    md.push_str(&format!("- Reader: {READER_ID}: the exact UTF-8 bytes of each file, with no transformation (no newline normalization, transcoding, extraction or execution).\n"));
    md.push_str(&format!("- Renderer: {RENDERER_ID}\n"));
    md.push_str(&format!("- Model: {} (every run of this audit)\n", s.model));
    md.push_str(&format!("- Provider API version: {ANTHROPIC_VERSION}; at most {MAX_TOKENS_PER_REQUEST} output tokens per request\n\n"));
    md.push_str("## Limits\n\n");
    md.push_str("Cumulative across every run of the audit, from the provider's usage reports, with stated estimates for lost responses:\n\n");
    md.push_str(&format!(
        "- Turns: {}\n- Input tokens: {}\n- Output tokens: {}\n",
        s.turns, s.input_tokens, s.output_tokens
    ));
    md.push_str(&format!("- Near-limit notice: once per audit, when {NEAR_LIMIT_PERCENT}% or less of any allowance remains\n"));
    md.push_str("- Provider retry: at most 4 attempts per request, waiting 2, 8 and 30 seconds (or a retry-after of at most 60 seconds); request timeout 600 seconds\n\n");
    md.push_str("## Bindings\n\n");
    md.push_str(&format!(
        "- Question body SHA-256: {}\n",
        input.question_body_sha256
    ));
    md.push_str(&format!(
        "- Material index SHA-256: {} (the exact bytes of the index member of manifest.json)\n\n",
        input.material_index_sha256
    ));
    md.push_str("## Orientation (first system block)\n\n");
    md.push_str(&quoted_block(ORIENTATION));
    md.push_str("\n\n## Family instructions (second system block)\n\n");
    md.push_str(&quoted_block(f.instructions));
    md.push_str("\n\n## Stopping and notices\n\n");
    md.push_str("After an ordinary turn ends without submission, at most once per audit and only while no limit is exhausted, the auditor receives this reminder:\n\n");
    md.push_str(&quoted_block(REMINDER));
    md.push_str(
        "\n\nAt most once per audit, near a limit, with the remaining amounts filled in:\n\n",
    );
    md.push_str(&quoted_block(NEAR_LIMIT));
    md.push_str("\n\nWhen an interrupted audit continues in a new conversation, its first message holds the question and then:\n\n");
    md.push_str(&quoted_block(CONTINUATION));
    md.push_str("\n\nAnother turn that ends without submission ends the run; close then seals the recorded answer with manager attribution. When a limit is exhausted the run stops and the answer stays unsubmitted.\n\n");
    md.push_str("## Reading, truncation and continuation\n\n");
    md.push_str("- read returns at most 65,536 bytes of text per page, ending at the source's end, or just after the last LF in the window, or at the last UTF-8 boundary; a ready next call continues it. Binary artifacts come in 49,152-byte base64 pages.\n");
    md.push_str("- search is literal and case-sensitive, 1–1,024 bytes of text, at most 128 hits and 32 KiB of context per page, with 240 bytes of context per hit. An incomplete search never reports absence.\n");
    md.push_str("- list returns at most 128 materials per page.\n");
    md.push_str("- One tool call carries at most 4 MiB of input.\n\n");
    md.push_str("## Tools\n\n");
    md.push_str("The tool definitions below are the exact JSON the run sends, in order.\n\n");
    if let Ok(parsed) = crate::json::parse(tools_bytes) {
        if let Some(arr) = parsed.as_arr() {
            for t in arr {
                let name = t
                    .obj("")
                    .ok()
                    .and_then(|o| o.str("name").ok())
                    .unwrap_or("");
                md.push_str(&format!("### {name}\n\n{}\n\n", tool_description(name)));
                md.push_str("```json\n");
                md.push_str(&String::from_utf8_lossy(&tools_bytes[t.start..t.end]));
                md.push_str("\n```\n\n");
            }
        }
    }
    md
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tools_follow_the_pinned_order_and_shape() {
        for f in &FAMILIES {
            let bytes = tools(f).bytes();
            let parsed = crate::json::parse(&bytes).expect("tools are strict JSON");
            let names: Vec<String> = parsed
                .as_arr()
                .unwrap()
                .iter()
                .map(|t| t.obj("").unwrap().str("name").unwrap().to_string())
                .collect();
            let mut want = vec!["list", "read", "search"];
            want.extend(f.tools.iter().copied());
            want.extend([
                "record_artifact",
                "replace",
                "delete",
                "what_am_i_working_with",
                "prepare",
                "submit",
            ]);
            assert_eq!(names, want);
            for t in parsed.as_arr().unwrap() {
                let o = t.obj("").unwrap();
                o.only(&["name", "description", "input_schema"]).unwrap();
                assert!(!tool_description(o.str("name").unwrap()).is_empty());
                let s = o.obj("input_schema").unwrap();
                s.only(&["type", "properties", "required", "additionalProperties"])
                    .unwrap();
                assert!(!s.bool("additionalProperties").unwrap());
            }
        }
        let open = tools(&FAMILIES[0]).string();
        assert!(open.starts_with(r#"[{"name":"list","description":"List the captured materials: their names (materials/…), sizes and line counts. Long lists come in pages.","input_schema":{"type":"object","properties":{"cursor":{"type":"string","description":"Cursor from the previous list reply's next call, for the next page."}},"required":[],"additionalProperties":false}}"#));
        assert!(open.contains(r#"{"name":"prepare","description":"Make the exact candidate that submit would seal, with its Markdown rendering and factual notes on empty sections. It changes nothing, and you can keep editing.","input_schema":{"type":"object","properties":{},"required":[],"additionalProperties":false}}"#));
        assert!(open.contains(r#""start":{"type":"integer","minimum":0,"description":"Byte offset to start from. Default 0; use the start that a reply's next call gives."}"#));
        assert!(open.contains(r#""sources":{"type":"array","items":{"type":"string"},"maxItems":128,"description":"Sources to search. Default: the question and every material."}"#));
    }

    #[test]
    fn a_pinned_arrangement_reads_back_with_its_exact_bytes() {
        let settings = crate::frontmatter::Settings {
            family: "comparison".into(),
            model: "claude-opus-5-5".into(),
            destination: "/d".into(),
            turns: 200,
            input_tokens: 20_000_000,
            output_tokens: 400_000,
            inquiry: None,
            varies: None,
        };
        let a = arrangement(&ArrangementInput {
            settings: &settings,
            question_body_sha256: &"1".repeat(64),
            material_index_sha256: &"2".repeat(64),
        });
        let bytes = crate::archive::record_bytes("arrangement", Some("a"), &"0".repeat(64), a.body);
        let p = decode_arrangement(&bytes).unwrap();
        assert_eq!(p.family, "comparison/1");
        assert_eq!(p.family().map(|f| f.id), Some("comparison"));
        assert_eq!(p.model_raw, br#""claude-opus-5-5""#);
        assert_eq!(p.anthropic_version, "2026-10-21");
        assert_eq!(p.system_raw, system(&FAMILIES[2]));
        assert_eq!(p.tools_raw, tools(&FAMILIES[2]).bytes());
        assert_eq!(p.tool_names[3], "record_criterion");
        assert_eq!(p.near_limit, NEAR_LIMIT);
        assert_eq!(p.limits.output_tokens, 400_000);
        assert_eq!(p.retry_delays_seconds, [2, 8, 30]);
        assert_eq!(p.request_timeout_seconds, 600);
        assert!(p.request_extra.is_empty());
        let text = String::from_utf8(bytes).unwrap();
        let extra = text.replace(r#""request_extra":{}"#, r#""request_extra":{"x":1}"#);
        assert!(
            decode_arrangement(extra.as_bytes())
                .unwrap_err()
                .contains("allowlist")
        );
    }

    #[test]
    fn citation_schema_is_exact() {
        assert_eq!(
            citation_schema().string(),
            r#"{"type":"object","properties":{"source":{"type":"string","description":"question or materials/<name>."},"start":{"type":"integer","minimum":0,"description":"Byte offset where the cited span begins."},"end":{"type":"integer","minimum":1,"description":"Byte offset just after the cited span."},"quote":{"type":"string","description":"Exact text of the cited span."}},"required":["source"],"additionalProperties":false}"#
        );
    }

    #[test]
    fn system_blocks_are_compact_json() {
        let s = system(&FAMILIES[2]);
        let parsed = crate::json::parse(&s).unwrap();
        let blocks = parsed.as_arr().unwrap();
        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0].obj("").unwrap().str("text").unwrap(), ORIENTATION);
        assert_eq!(blocks[1].obj("").unwrap().str("text").unwrap(), COMPARISON);
        assert!(s.starts_with(br#"[{"type":"text","text":"You are the auditor"#));
    }

    /// The pinned texts equal QUESTION-FORMS' quoted blocks, joined by its rule.
    /// This reads the specification in the repository as an independent witness.
    #[test]
    fn pinned_texts_match_question_forms() {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../docs/QUESTION-FORMS.md");
        let doc = std::fs::read_to_string(path)
            .expect("docs/QUESTION-FORMS.md is part of the repository");
        let mut blocks: Vec<Vec<String>> = Vec::new();
        let mut cur: Option<Vec<String>> = None;
        for line in doc.split('\n') {
            if let Some(rest) = line.strip_prefix('>') {
                cur.get_or_insert_with(Vec::new)
                    .push(rest.strip_prefix(' ').unwrap_or(rest).to_string());
            } else if let Some(b) = cur.take() {
                blocks.push(b);
            }
        }
        let joined: Vec<String> = blocks
            .iter()
            .map(|b| {
                let mut paras = Vec::new();
                let mut p: Vec<&str> = Vec::new();
                for l in b {
                    if l.is_empty() {
                        if !p.is_empty() {
                            paras.push(p.join(" "));
                            p.clear();
                        }
                    } else {
                        p.push(l);
                    }
                }
                if !p.is_empty() {
                    paras.push(p.join(" "));
                }
                paras.join("\n\n")
            })
            .collect();
        for text in [
            ORIENTATION,
            OPEN_INQUIRY,
            INQUIRY_FRAMING,
            COMPARISON,
            REMINDER,
            NEAR_LIMIT,
            CONTINUATION,
        ] {
            assert!(
                joined.iter().any(|j| j == text),
                "pinned text not found in QUESTION-FORMS: {text}"
            );
        }
        assert_eq!(
            &joined[..7],
            &[
                ORIENTATION,
                OPEN_INQUIRY,
                INQUIRY_FRAMING,
                COMPARISON,
                REMINDER,
                NEAR_LIMIT,
                CONTINUATION
            ]
        );
        // Tool and property descriptions appear verbatim in its tables.
        for f in &FAMILIES {
            let t = tools(f).string();
            let parsed = crate::json::parse(t.as_bytes()).unwrap();
            for tool in parsed.as_arr().unwrap() {
                let o = tool.obj("").unwrap();
                assert!(
                    doc.contains(o.str("description").unwrap()),
                    "{}",
                    o.str("name").unwrap()
                );
                for (_, p) in o
                    .obj("input_schema")
                    .unwrap()
                    .obj("properties")
                    .unwrap()
                    .members
                {
                    let d = p.obj("").unwrap().str("description").unwrap();
                    assert!(doc.contains(d), "{d}");
                }
            }
        }
    }
}
