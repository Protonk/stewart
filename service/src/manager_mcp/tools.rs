//! Manager tool inventory and replies (INTERFACE 5.11, QUESTION-FORMS registry).
use super::assessment;
use crate::forms::{self, FAMILIES, Family};
use crate::json::{self, J, JsonError, Obj, strs};
use crate::roles::REGISTRY;

#[derive(Clone, Copy)]
pub(super) enum Tool {
    Discover,
    Explain,
    Assess,
}

const TOOLS: [Tool; 3] = [Tool::Discover, Tool::Explain, Tool::Assess];

fn object(properties: J, required: &[&str]) -> J {
    J::obj()
        .with("type", "object")
        .with("properties", properties)
        .with("required", strs(required))
        .with("additionalProperties", false)
}

fn array(items: J) -> J {
    J::obj().with("type", "array").with("items", items)
}

impl Tool {
    pub(super) fn named(name: &str) -> Option<Self> {
        TOOLS.into_iter().find(|tool| tool.name() == name)
    }

    fn name(self) -> &'static str {
        match self {
            Self::Discover => "discover",
            Self::Explain => "explain",
            Self::Assess => "assess",
        }
    }

    fn description(self) -> &'static str {
        match self {
            Self::Discover => "List the available question families and their purposes.",
            Self::Explain => {
                "Explain a versioned family ID from discover. In question.md use the family name without its /version suffix."
            }
            Self::Assess => {
                "Check a prospective question and declared inventory. Reports errors and advice without reading files or commissioning an audit."
            }
        }
    }

    fn required(self) -> &'static [&'static str] {
        match self {
            Self::Discover => &[],
            Self::Explain => &["family"],
            Self::Assess => &["question_file", "guidance", "directories", "files"],
        }
    }

    fn schema(self) -> J {
        let string = || J::obj().with("type", "string");
        let properties = match self {
            Self::Discover => J::obj(),
            Self::Explain => J::obj().with("family", string()),
            Self::Assess => {
                let file = object(
                    J::obj().with("name", string()).with(
                        "size",
                        J::obj()
                            .with("type", "integer")
                            .with("minimum", 0u64)
                            .with("maximum", u64::MAX),
                    ),
                    &["name", "size"],
                );
                J::obj()
                    .with("question_file", string())
                    .with("guidance", J::obj().with("type", strs(&["string", "null"])))
                    .with("directories", array(string()))
                    .with("files", array(file))
            }
        };
        object(
            properties.with(
                "detail",
                string()
                    .with("enum", strs(&["brief", "full"]))
                    .with("default", "brief"),
            ),
            self.required(),
        )
    }

    pub(super) fn call(self, bytes: &[u8]) -> J {
        let checked = || {
            let value = json::parse(bytes)?;
            let args = value.obj("")?;
            let mut allowed = self.required().to_vec();
            allowed.push("detail");
            args.only(&allowed)?;
            let full = match args.opt_str("detail")? {
                None | Some("brief") => false,
                Some("full") => true,
                Some(_) => return Err(args.invalid("detail", "Use brief or full.")),
            };
            self.evaluate(&args, full)
        };
        let evaluation = checked().unwrap_or_else(|e: JsonError| {
            ToolResult::refusal(
                "input_invalid",
                &e.pointer,
                &e.to_string(),
                "Correct the indicated argument using this tool's input schema.",
            )
        });
        evaluation.reply(self.name())
    }

    fn evaluate(self, args: &Obj, full: bool) -> Result<ToolResult, JsonError> {
        match self {
            Self::Discover => {
                let families = FAMILIES
                    .iter()
                    .map(|f| {
                        J::obj()
                            .with("family", f.versioned_id())
                            .with("available", true)
                            .with("purpose", f.purpose)
                    })
                    .collect();
                Ok(ToolResult::completed(
                    J::obj().with("families", J::Arr(families)),
                    full,
                    "Choose the family that fits your question. Call explain with its versioned ID for the roles and an example.",
                ))
            }
            Self::Explain => {
                let id = args.str("family")?;
                let Some(family) = forms::pinned_family(id) else {
                    let available = FAMILIES
                        .iter()
                        .map(Family::versioned_id)
                        .collect::<Vec<_>>()
                        .join(", ");
                    return Ok(ToolResult::refusal(
                        "family_unknown",
                        "/family",
                        &format!("Unknown or unavailable question family {id:?}."),
                        &format!("Choose an available family: {available}."),
                    ));
                };
                let (example, guidance) = worked_example(family);
                let explanation = format!("Use `family: {}` in question.md. {guidance}", family.id);
                Ok(ToolResult::completed(
                    J::obj()
                        .with("descriptor", family.descriptor())
                        .with("example", example),
                    full,
                    &explanation,
                ))
            }
            Self::Assess => {
                let data = assessment::assess(args)?;
                let valid = data.get("valid") == Some(&J::Bool(true));
                let explanation = if valid {
                    "You can prepare these files with the CLI for commissioning, or edit the question or materials and assess again. Warnings and suggestions are optional. The CLI checks the actual files and locations."
                } else {
                    "Correct the reported errors and assess again. The CLI checks the actual files and locations before you can commission the selection."
                };
                Ok(ToolResult::completed(data, full, explanation))
            }
        }
    }
}

pub(super) fn list() -> J {
    J::Arr(
        TOOLS
            .iter()
            .map(|tool| {
                J::obj()
                    .with("name", tool.name())
                    .with("description", tool.description())
                    .with("inputSchema", tool.schema())
            })
            .collect(),
    )
}

fn worked_example(family: &Family) -> (J, &'static str) {
    let role = |id: &str, source: &str| J::obj().with("role", id).with("source", source);
    let context = role("context", "materials/requirements.txt");
    let subject = role("subject", "materials/a.py");
    let report = role("report", "materials/supplied-report.txt");
    match family.id {
        "open-inquiry" => (
            J::Arr(vec![subject, context, report]),
            "With only the supplied report, you may ask the broad question and record limits on what the report establishes.",
        ),
        "inquiry-framing" => (
            J::Arr(vec![context, subject, report]),
            "Requirements alone can frame a concern. An implementation or finished working question is optional.",
        ),
        "comparison" => (
            J::Arr(vec![
                role("alternative", "materials/a.py").with("label", "A"),
                role("alternative", "materials/b.py").with("label", "B"),
                role("criterion", "materials/requirements.txt"),
            ]),
            "With only A and the criterion, you may proceed with a one-sided comparison, or add the other alternative and assess again.",
        ),
        _ => unreachable!("every available family has a worked packet"),
    }
}

struct ToolResult {
    data: J,
    problem: J,
    explanation: J,
}

impl ToolResult {
    fn completed(data: J, full: bool, explanation: &str) -> Self {
        Self {
            data,
            problem: J::Null,
            explanation: if full {
                strs(&[explanation])
            } else {
                J::Arr(vec![])
            },
        }
    }
    fn refusal(reason: &str, pointer: &str, message: &str, remedy: &str) -> Self {
        Self {
            data: J::Null,
            problem: J::obj()
                .with("reason", reason)
                .with("pointer", pointer)
                .with("message", message)
                .with("remedy", remedy),
            explanation: J::Arr(vec![]),
        }
    }
    fn reply(self, name: &str) -> J {
        let refused = self.problem != J::Null;
        let body = J::obj()
            .with("schema", "stewart.manager-preparation/1")
            .with("registry", REGISTRY)
            .with("question_schema", "question/2")
            .with("tool", name)
            .with("outcome", if refused { "refused" } else { "completed" })
            .with("problem", self.problem)
            .with("data", self.data)
            .with(
                "writes",
                J::obj()
                    .with("state", "none")
                    .with("created", J::Arr(vec![]))
                    .with("incomplete", J::Arr(vec![])),
            )
            .with("explanation", self.explanation);
        let content = J::obj().with("type", "text").with("text", body.string());
        J::obj()
            .with("isError", refused)
            .with("structuredContent", body)
            .with("content", J::Arr(vec![content]))
    }
}
