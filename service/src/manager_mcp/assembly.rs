//! The `assemble` tool (MANAGER-PREPARATION "Assemble" and "Filesystem
//! authority and interruption"). It generates a candidate's exact question
//! file and inventory from explicit inputs, checks them with the shared
//! intake, front matter and role rules, and on explicit request creates the
//! candidate folder in the launcher's workspace. Each call stands alone.

use super::assessment::{self, Snapshot};
use super::tools::ToolResult;
use super::workspace::{Acquire, Created, PACKAGE_PREFIX, SOURCES, Workspace, Writes};
use crate::archive::STORE_FILE;
use crate::frontmatter::{self, KEYS};
use crate::intake::{self, Component, PATH_BYTES, PATH_COMPONENTS};
use crate::json::{J, Json, JsonError, Obj, V, strs};
use crate::util;

/// The front matter keys a manager supplies in `fields`: the build's
/// question keys other than `stewart`, which generation writes itself.
pub(super) fn field_keys() -> Vec<&'static str> {
    let keys = KEYS.iter().copied().filter(|k| *k != "stewart");
    #[cfg(feature = "claude-code")]
    let keys = keys.chain(crate::claude_code::profile::EXTRA_KEYS);
    keys.collect()
}

const ROLES: &str = "material-roles";

/// One supplied front matter value.
enum Value<'a> {
    Text(&'a str),
    Roles(&'a [Json]),
}

struct File<'a> {
    name: &'a str,
    from: &'a str,
}

struct Args<'a> {
    fields: Vec<(&'a str, Value<'a>)>,
    body: &'a str,
    guidance: Option<&'a str>,
    directories: Vec<&'a str>,
    files: Vec<File<'a>>,
    destination: &'a str,
    create: bool,
}

impl<'a> Args<'a> {
    fn parse(args: &Obj<'a>) -> Result<Self, JsonError> {
        let object = args.obj("fields")?;
        object.only(&field_keys())?;
        let mut fields = Vec::new();
        for (key, _) in object.members {
            let value = if key == ROLES {
                Value::Roles(object.arr(key)?)
            } else {
                let text = object.str(key)?;
                if text.contains(['\r', '\n']) {
                    return Err(object.invalid(
                        key,
                        "a field value cannot contain CR or LF, which would insert a line or end the front matter",
                    ));
                }
                Value::Text(text)
            };
            fields.push((key.as_str(), value));
        }
        let files = args
            .arr("files")?
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let file = v.obj(&format!("/files/{i}"))?;
                file.exactly(&["name", "from"])?;
                Ok(File {
                    name: file.str("name")?,
                    from: file.str("from")?,
                })
            })
            .collect::<Result<Vec<_>, JsonError>>()?;
        Ok(Self {
            fields,
            body: args.str("body")?,
            guidance: args.str_or_null("guidance")?,
            directories: args.strs("directories")?,
            files,
            destination: args.str("destination")?,
            create: match args.get("create") {
                None => false,
                Some(_) => args.bool("create")?,
            },
        })
    }

    fn text(&self, key: &str) -> Option<&'a str> {
        self.fields.iter().find_map(|(k, v)| match v {
            Value::Text(t) if *k == key => Some(*t),
            _ => None,
        })
    }
}

/// Encode one declaration as given, with `role`, `source` and `label`
/// first in that order and any other members after them in supplied order.
fn declaration(item: &Json) -> J {
    let V::Obj(members) = &item.v else {
        return item.to_j();
    };
    let known = ["role", "source", "label"];
    let mut out = J::obj();
    for key in known {
        if let Some((_, v)) = members.iter().find(|(k, _)| k == key) {
            out.push(key, v.to_j());
        }
    }
    for (k, v) in members {
        if !known.contains(&k.as_str()) {
            out.push(k, v.to_j());
        }
    }
    out
}

/// The question file: LF front matter starting with the schema line, the
/// present fields in bytewise key order, then the body's exact bytes.
fn question_file(fields: &[(&str, Value)], body: &str) -> String {
    let mut present: Vec<&(&str, Value)> = fields.iter().collect();
    present.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
    let mut text = String::from("---\nstewart: question/2\n");
    for (key, value) in present {
        let value = match value {
            Value::Text(t) => (*t).to_string(),
            Value::Roles(items) => J::Arr(items.iter().map(declaration).collect()).string(),
        };
        text.push_str(&format!("{key}: {value}\n"));
    }
    text.push_str("---\n");
    text.push_str(body);
    text
}

fn component(raw: &str) -> Result<(), String> {
    match intake::component_problem(raw.as_bytes()) {
        None => Ok(()),
        Some(Component::NotUtf8) => Err("is not valid UTF-8".into()),
        Some(Component::Control) => Err("contains a control character".into()),
        Some(Component::TooLong(n)) => Err(format!(
            "has a component of {n} bytes, over the bound of {}",
            intake::COMPONENT_BYTES
        )),
        Some(Component::NotOneName) => {
            Err("has an empty, `.` or `..` component, or is not one name".into())
        }
    }
}

/// The candidate destination is one new name, never a reserved one.
fn candidate_name_problem(name: &str) -> Option<String> {
    if let Err(e) = component(name) {
        return Some(format!("The candidate destination {name:?} {e}."));
    }
    if name.starts_with("stw1:") {
        return Some(format!(
            "The candidate destination {name:?} looks like an audit reference; give one new folder name."
        ));
    }
    if name == SOURCES || name == STORE_FILE || name.starts_with(PACKAGE_PREFIX) {
        return Some(format!(
            "The candidate destination {name:?} is reserved: it may not be {SOURCES} or {STORE_FILE}, or begin with {PACKAGE_PREFIX}."
        ));
    }
    None
}

/// The path policy of a source name relative to `sources/`.
fn source_path_problem(from: &str) -> Option<String> {
    if from.starts_with('/') {
        return Some(format!(
            "{from:?} is absolute; name a source relative to {SOURCES}/."
        ));
    }
    if from.starts_with("stw1:") {
        return Some(format!(
            "{from:?} looks like an audit reference; name a file under {SOURCES}/."
        ));
    }
    if from.len() > PATH_BYTES {
        return Some(format!(
            "{from:?} has {} bytes, over the bound of {PATH_BYTES}.",
            from.len()
        ));
    }
    let components: Vec<&str> = from.split('/').collect();
    if components.len() > PATH_COMPONENTS {
        return Some(format!(
            "{from:?} has {} components, over the bound of {PATH_COMPONENTS}.",
            components.len()
        ));
    }
    for c in &components {
        if let Err(e) = component(c) {
            return Some(format!("The source name {from:?} {e}."));
        }
    }
    let (_, directories) = components.split_last().expect("split yields one");
    if let Some(d) = directories.iter().find(|d| d.starts_with(PACKAGE_PREFIX)) {
        return Some(format!(
            "{from:?} passes through {d:?}, a delivery package name, which the workspace never reads."
        ));
    }
    None
}

/// Path components after dropping empty and `.` ones; `..` is kept as text.
fn components(path: &str) -> Vec<&str> {
    path.split('/')
        .filter(|c| !c.is_empty() && *c != ".")
        .collect()
}

/// Whether an answer destination names the candidate, a path inside it or
/// a directory containing it, by comparing path components.
fn overlaps(destination: &str, workspace: &str, name: &str) -> bool {
    let d = components(destination);
    let mut c = components(workspace);
    c.push(name);
    let shorter = d.len().min(c.len());
    d[..shorter] == c[..shorter]
}

fn writes_j(w: &Writes) -> J {
    J::obj()
        .with("state", w.state())
        .with("created", strs(&w.created))
        .with("incomplete", strs(&w.incomplete))
}

fn none() -> J {
    writes_j(&Writes::default())
}

pub(super) fn assemble(
    args: &Obj,
    workspace: Option<&Workspace>,
    full: bool,
) -> Result<ToolResult, JsonError> {
    let a = Args::parse(args)?;
    let name = a.destination;
    if let Some(message) = candidate_name_problem(name) {
        return Ok(ToolResult::refusal(
            "candidate_path_invalid",
            Some("/destination"),
            &message,
            &format!(
                "Give one new folder name: not {SOURCES} or {STORE_FILE}, not beginning with {PACKAGE_PREFIX} or stw1:."
            ),
        ));
    }
    if workspace.is_none() && (a.create || !a.files.is_empty()) {
        let (pointer, needs) = if a.create {
            ("/create", "Creating a candidate")
        } else {
            ("/files", "Reading source files")
        };
        return Ok(ToolResult::refusal(
            "workspace_required",
            Some(pointer),
            &format!("{needs} needs the workspace the launcher designates; this server has none."),
            "Restart the server with --workspace DIR, or dry-run without source files.",
        ));
    }
    if let (Some(ws), Some(destination)) = (workspace, a.text("destination")) {
        if frontmatter::destination_problem(destination).is_none()
            && overlaps(destination, &ws.path, name)
        {
            return Ok(ToolResult::refusal(
                "candidate_path_invalid",
                Some("/fields/destination"),
                &format!(
                    "The answer destination {destination:?} names the candidate {}/{name}, a path inside it or a directory containing it.",
                    ws.path
                ),
                "Name an answer destination outside the candidate folder and the directories that contain it.",
            ));
        }
    }

    let question = question_file(&a.fields, a.body);
    let named: Vec<(&str, u64)> = a.files.iter().map(|f| (f.name, 0)).collect();
    // Before any source is read every size counts as zero, and the
    // material bytes remain unchecked.
    let first = assessment::snapshot(&question, a.guidance, &a.directories, &named, false);
    if !first.valid {
        return Ok(invalid(first.data, None));
    }

    if let Some(ws) = workspace {
        if let Err(message) = ws.recheck() {
            return Ok(ToolResult::refusal(
                "candidate_path_invalid",
                None,
                &message,
                "Use a candidate-only workspace separate from archives and delivery locations.",
            ));
        }
        match ws.exists(name) {
            Ok(false) => {}
            Ok(true) if a.create && crate::sabotage!("candidate_overwrites_existing") => {}
            Ok(true) => return Ok(exists(ws, name)),
            Err(e) => {
                return Ok(ToolResult::refusal(
                    "candidate_path_invalid",
                    Some("/destination"),
                    &format!(
                        "The candidate destination {name:?} cannot be examined in the workspace: {}.",
                        util::describe(&e)
                    ),
                    "Check the workspace's permissions and choose a fresh destination.",
                ));
            }
        }
    }

    let prior = question.len() as u64 + a.guidance.map_or(0, |g| g.len() as u64);
    let mut total = prior;
    let mut materials: Vec<(&str, Vec<u8>)> = Vec::with_capacity(a.files.len());
    for (i, file) in a.files.iter().enumerate() {
        let pointer = format!("/files/{i}/from");
        if let Some(message) = source_path_problem(file.from) {
            return Ok(ToolResult::refusal(
                "candidate_path_invalid",
                Some(&pointer),
                &message,
                "Name a source relative to the workspace's sources/ directory.",
            ));
        }
        let ws = workspace.expect("source files require a workspace");
        match ws.acquire(file.from, file.name, i + 1, total) {
            Ok(bytes) => {
                total += bytes.len() as u64;
                materials.push((file.name, bytes));
            }
            Err(Acquire::PathInvalid(message)) => {
                return Ok(ToolResult::refusal(
                    "candidate_path_invalid",
                    Some(&pointer),
                    &message,
                    "Name a regular, singly linked file under sources/ reached without links, special entries, mounts or stores.",
                ));
            }
            Err(Acquire::Failed(message)) => {
                return Ok(ToolResult::refusal(
                    "candidate_source_failed",
                    Some(&pointer),
                    &message,
                    "Supply the source under sources/ with exactly that name, leave it unchanged, and assemble again.",
                ));
            }
            Err(Acquire::Intake(refusal)) => {
                let defect = refusal.defect().expect("a mechanical intake refusal");
                return Ok(invalid(
                    assessment::data(Err(vec![defect]), false, first.profile),
                    Some(&pointer),
                ));
            }
        }
    }

    let sized: Vec<(&str, u64)> = materials
        .iter()
        .map(|(n, b)| (*n, b.len() as u64))
        .collect();
    let Snapshot { valid, data, .. } =
        assessment::snapshot(&question, a.guidance, &a.directories, &sized, true);
    if !valid {
        return Ok(invalid(data, None));
    }

    let mut directories = a.directories.clone();
    directories.sort_by(|x, y| x.as_bytes().cmp(y.as_bytes()));
    let mut proposed: Vec<(&str, &[u8])> = vec![("question.md", question.as_bytes())];
    if let Some(g) = a.guidance {
        proposed.push(("guidance.md", g.as_bytes()));
    }
    proposed.extend(materials.iter().map(|(n, b)| (*n, b.as_slice())));
    proposed.sort_by(|x, y| x.0.as_bytes().cmp(y.0.as_bytes()));
    let result = J::obj()
        .with("question_file", question.as_str())
        .with("directories", strs(&directories))
        .with(
            "files",
            J::Arr(
                proposed
                    .iter()
                    .map(|(n, b)| {
                        J::obj()
                            .with("name", *n)
                            .with("size", b.len() as u64)
                            .with("sha256", util::sha256_hex(b))
                    })
                    .collect(),
            ),
        )
        .with("assessment", data);

    if !a.create {
        if let Some(ws) = workspace
            && crate::sabotage!("candidate_dry_run_writes")
        {
            ws.sabotage_claim(name);
        }
        let mut writes = none();
        if crate::sabotage!("candidate_forecast_as_written") {
            let mut created = vec![name.to_string()];
            created.extend(directories.iter().map(|d| format!("{name}/{d}")));
            created.extend(proposed.iter().map(|(f, _)| format!("{name}/{f}")));
            writes = J::obj()
                .with("state", "complete")
                .with("created", strs(&created))
                .with("incomplete", J::Arr(vec![]));
        }
        return Ok(ToolResult::completed(
            result,
            full,
            "This is a dry run: nothing was written. The same arguments with create:true create the candidate folder, which the CLI then prepares. Warnings and suggestions are optional.",
        )
        .with_writes(writes));
    }

    let ws = workspace.expect("creation requires a workspace");
    match ws.create(name, &directories, &proposed) {
        Created::Done(w) => Ok(ToolResult::completed(
            result,
            full,
            &format!(
                "Created the candidate folder {}/{name}. Use it as the FOLDER of stewart new, then prepare and commission it with the CLI.",
                ws.path
            ),
        )
        .with_writes(writes_j(&w))),
        Created::Exists => Ok(exists(ws, name)),
        Created::Failed(w, message) => {
            let writes = if crate::sabotage!("candidate_unreported_partial") {
                none()
            } else {
                writes_j(&w)
            };
            Ok(ToolResult::failed(
                "candidate_write_failed",
                &message,
                "Inspect the named entries with ordinary file tools; they are left in place. Create again with a fresh destination.",
                result,
                writes,
                full,
            ))
        }
    }
}

/// Candidate errors, with the assessment that lists them. A source's
/// bytes point at that source; other errors carry their own pointers.
fn invalid(assessment: J, pointer: Option<&str>) -> ToolResult {
    ToolResult::refusal(
        "candidate_invalid",
        pointer,
        "The candidate has errors; the assessment lists them. Nothing was written.",
        "Correct the reported errors and assemble again.",
    )
    .with_data(J::obj().with("assessment", assessment))
}

fn exists(ws: &Workspace, name: &str) -> ToolResult {
    ToolResult::refusal(
        "destination_exists",
        Some("/destination"),
        &format!(
            "An entry named {name:?} already exists in the workspace {} under this host's name rules. An existing candidate, even an incomplete one, is never reused.",
            ws.path
        ),
        "Inspect the existing folder with ordinary file tools, then choose a fresh destination.",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parsed(text: &str) -> Json {
        crate::json::parse(text.as_bytes()).unwrap()
    }

    /// Generation writes the schema line, then the present fields in
    /// bytewise key order, then the body's exact bytes with no newline added.
    #[test]
    fn the_question_file_has_bytewise_key_order_and_the_exact_body() {
        let fields = [
            ("model", Value::Text("example-model")),
            ("limit-turns", Value::Text("4")),
            ("family", Value::Text("open-inquiry")),
            ("destination", Value::Text("/home/ana/returns")),
            ("limit-output-tokens", Value::Text("8000")),
            ("limit-input-tokens", Value::Text("32000")),
        ];
        assert_eq!(
            question_file(&fields, "What can these materials establish?"),
            "---\nstewart: question/2\ndestination: /home/ana/returns\nfamily: open-inquiry\nlimit-input-tokens: 32000\nlimit-output-tokens: 8000\nlimit-turns: 4\nmodel: example-model\n---\nWhat can these materials establish?"
        );
        // The body is kept exactly, CRLF and all; an empty one stays empty.
        assert!(question_file(&[], "a\r\nb\n\n").ends_with("---\na\r\nb\n\n"));
        assert_eq!(question_file(&[], ""), "---\nstewart: question/2\n---\n");
    }

    /// Role declarations are compact, in declaration order, with `role`,
    /// `source` and `label` first and other members after them as supplied,
    /// so the shared parser reports a malformed one.
    #[test]
    fn role_declarations_are_encoded_compactly_in_interface_key_order() {
        let roles = parsed(
            r#"[{"label":"A","source":"materials/a.py","role":"alternative"},{"note":1,"source":"materials/r é.txt","x":[true],"role":"criterion"},"loose"]"#,
        );
        let fields = [(ROLES, Value::Roles(roles.as_arr().unwrap()))];
        assert_eq!(
            question_file(&fields, "Q"),
            "---\nstewart: question/2\nmaterial-roles: [{\"role\":\"alternative\",\"source\":\"materials/a.py\",\"label\":\"A\"},{\"role\":\"criterion\",\"source\":\"materials/r é.txt\",\"note\":1,\"x\":[true]},\"loose\"]\n---\nQ"
        );
        let empty = parsed("[]");
        assert_eq!(
            question_file(&[(ROLES, Value::Roles(empty.as_arr().unwrap()))], "Q"),
            "---\nstewart: question/2\nmaterial-roles: []\n---\nQ"
        );
    }

    #[test]
    fn candidate_names_are_one_unreserved_component() {
        for ok in ["first-inquiry", "Sources", "store.json.bak", "a b", "é"] {
            assert_eq!(candidate_name_problem(ok), None, "{ok}");
        }
        for bad in [
            "",
            ".",
            "..",
            "a/b",
            "/abs",
            "tab\there",
            "sources",
            "STORE.json",
            "stewart-return-x",
            "stw1:aqm3x7kd2hz5vw4ny",
            &"n".repeat(256),
        ] {
            assert!(candidate_name_problem(bad).is_some(), "{bad:?}");
        }
        assert_eq!(candidate_name_problem(&"n".repeat(255)), None);
    }

    #[test]
    fn source_names_are_relative_component_paths() {
        for ok in [
            "a.txt",
            "sub/dir/a.txt",
            ".hidden",
            "stewart-return-notes.txt",
        ] {
            assert_eq!(source_path_problem(ok), None, "{ok}");
        }
        for bad in [
            "/etc/hosts",
            "",
            "a//b",
            "a/",
            "./a",
            "a/../b",
            "..",
            "stw1:x",
            "stewart-return-1/a.txt",
            "x/stewart-return-1/a.txt",
            "a\nb",
        ] {
            assert!(source_path_problem(bad).is_some(), "{bad:?}");
        }
        let deep = vec!["d"; PATH_COMPONENTS].join("/");
        assert_eq!(source_path_problem(&deep), None);
        assert!(source_path_problem(&format!("{deep}/x")).is_some());
        let long = "a/".repeat(PATH_BYTES / 2) + "b";
        assert!(long.len() > PATH_BYTES);
        assert!(source_path_problem(&long).is_some());
    }

    /// A destination naming the candidate, a path inside it or a directory
    /// containing it overlaps; components are compared after dropping empty
    /// and `.` ones, and `..` is not resolved.
    #[test]
    fn answer_destination_overlap_compares_path_components() {
        let ws = "/home/ana/work";
        for overlapping in [
            "/home/ana/work/cand",
            "/home/ana/work/cand/",
            "/home/ana/work/cand/returns",
            "/home//ana/./work/cand",
            "/home/ana/work",
            "/home",
            "/",
        ] {
            assert!(overlaps(overlapping, ws, "cand"), "{overlapping}");
        }
        for separate in [
            "/home/ana/work/candidate",
            "/home/ana/work/other",
            "/home/ana/returns",
            "/home/ana/work/x/../cand",
            "/home/ana/workspace",
        ] {
            assert!(!overlaps(separate, ws, "cand"), "{separate}");
        }
    }

    /// Before any source is read, sizes count as zero and the material
    /// bytes stay unchecked; once every supplied source (here none) has been
    /// read and checked, the final assessment omits them.
    #[test]
    fn material_bytes_stay_unchecked_until_every_source_is_read() {
        let complete = r#"{"fields":{"family":"open-inquiry","model":"m","destination":"/r","limit-turns":"4","limit-input-tokens":"32000","limit-output-tokens":"8000"},"body":"Q?","guidance":null,"directories":["materials"],"files":[],"destination":"c"}"#;
        let unchecked = |args: &str| {
            let reply = super::super::tools::Tool::named("assemble")
                .unwrap()
                .call(args.as_bytes(), None);
            let content = reply.get("structuredContent").unwrap();
            content
                .get("data")
                .and_then(|d| d.get("assessment"))
                .and_then(|a| a.get("unchecked"))
                .cloned()
                .unwrap_or_else(|| panic!("{}", content.string()))
        };
        assert_eq!(
            unchecked(complete),
            strs(&["filesystem", "source_stability", "acceptance"])
        );
        let early = complete.replace(r#""model":"m","#, "");
        assert_eq!(
            unchecked(&early),
            strs(&[
                "material_bytes",
                "filesystem",
                "source_stability",
                "acceptance"
            ])
        );
    }

    #[test]
    fn field_keys_are_the_question_keys_without_stewart() {
        let keys = field_keys();
        assert!(!keys.contains(&"stewart"));
        for k in KEYS.iter().filter(|k| **k != "stewart") {
            assert!(keys.contains(k), "{k}");
        }
        #[cfg(not(feature = "claude-code"))]
        assert_eq!(keys.len(), KEYS.len() - 1);
        #[cfg(feature = "claude-code")]
        assert!(keys.contains(&crate::claude_code::profile::SELECTOR));
    }
}
