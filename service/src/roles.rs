//! Manager declarations, family descriptors and commissioning advice (INTERFACE 3.2, 5.3).
//! These rules consume a literal selection's names. They do not acquire files.

use crate::forms::{Family, MaterialRole};
use crate::frontmatter::{Defect, sort_defects};
use crate::json::{self, J, Json, JsonError, Obj};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write;

const REGISTRY: &str = "stewart.family-registry/1";
const FIELD: &str = "material-roles";
const MAX_DECLARATIONS: usize = 512;

impl MaterialRole {
    fn labeled(&self) -> bool {
        self.id == "alternative"
    }

    fn minimum(&self) -> usize {
        if self.labeled() {
            2
        } else {
            usize::from(self.advice.is_some())
        }
    }

    fn severity(&self) -> Option<&'static str> {
        self.advice.map(|_| {
            if self.labeled() {
                "warning"
            } else {
                "suggestion"
            }
        })
    }

    fn descriptor(&self) -> J {
        J::obj()
            .with("id", self.id)
            .with("meaning", self.meaning)
            .with("label", if self.labeled() { "required" } else { "absent" })
            .with("minimum_recommended", self.minimum())
            .with("severity", self.severity())
            .with("remedy", self.advice)
    }
}

impl Family {
    pub fn descriptor(&self) -> J {
        J::obj()
            .with("family", self.versioned_id())
            .with("available", true)
            .with("purpose", self.purpose)
            .with(
                "roles",
                J::Arr(
                    self.material_roles
                        .iter()
                        .map(MaterialRole::descriptor)
                        .collect(),
                ),
            )
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
struct Mapping {
    role: String,
    source: String,
    label: Option<String>,
}

impl Mapping {
    fn to_j(&self) -> J {
        let mut value = J::obj()
            .with("role", self.role.as_str())
            .with("source", self.source.as_str());
        if let Some(label) = &self.label {
            value.push("label", label.as_str());
        }
        value
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Declarations {
    line: Option<usize>,
    entries: Vec<(usize, Mapping)>,
}

fn role_error(
    line: Option<usize>,
    reason: &'static str,
    pointer: String,
    message: String,
    remedy: &str,
) -> Defect {
    let mut defect = Defect::new(reason, line, Some(FIELD), message);
    defect.pointer = Some(pointer);
    defect.remedy = remedy.to_owned();
    defect
}

fn malformed(line: usize, e: JsonError) -> Defect {
    let message = e.to_string();
    role_error(
        Some(line),
        "role_declaration_invalid",
        e.pointer,
        message,
        "Supply a JSON array of objects with string role and source. Give each alternative a label.",
    )
}

fn mapping_label<'a>(obj: &Obj<'a>, labeled: bool) -> Result<Option<&'a str>, JsonError> {
    if !labeled {
        obj.exactly(&["role", "source"])?;
        return Ok(None);
    }
    obj.exactly(&["role", "source", "label"])?;
    let label = obj.str("label")?;
    if label.len() > 128 || label.trim().is_empty() || label.chars().any(char::is_control) {
        return Err(obj.invalid(
            "label",
            "use a nonblank label of 1–128 UTF-8 bytes without control characters",
        ));
    }
    Ok(Some(label))
}

fn read_mapping(
    item: &Json,
    index: usize,
    line: usize,
    family: Option<&Family>,
) -> Result<Option<Mapping>, Defect> {
    let at = format!("/{index}");
    let bad = |e| malformed(line, e);
    let obj = item.obj(&at).map_err(bad)?;
    obj.only(&["role", "source", "label"]).map_err(bad)?;
    let role = obj.str("role").map_err(bad)?;
    let source = obj.str("source").map_err(bad)?;
    let Some(family) = family else {
        return Ok(None);
    };
    let bad = |e| {
        let mut d = malformed(line, e);
        d.role = Some(role.into());
        d.source = Some(source.into());
        d
    };
    let Some(spec) = family.material_roles.iter().find(|r| r.id == role) else {
        let admitted = family
            .material_roles
            .iter()
            .map(|r| r.id)
            .collect::<Vec<_>>()
            .join(", ");
        let mut error = role_error(
            Some(line),
            "role_unsupported",
            obj.ptr("role"),
            format!("The {} family has no role {role:?}.", family.id),
            &format!("Use one of these roles: {admitted}."),
        );
        error.role = Some(role.into());
        error.source = Some(source.into());
        return Err(error);
    };
    let label = mapping_label(&obj, spec.labeled())
        .map_err(bad)?
        .map(str::to_owned);
    Ok(Some(Mapping {
        role: role.into(),
        source: source.into(),
        label,
    }))
}

impl Declarations {
    pub(crate) fn parse(
        field: Option<(&str, usize)>,
        family: Option<&Family>,
        defects: &mut Vec<Defect>,
    ) -> Self {
        let Some((text, line)) = field else {
            return Self::default();
        };
        let mut result = Self {
            line: Some(line),
            entries: Vec::new(),
        };
        let array = match json::parse(text.as_bytes()) {
            Ok(value) => value,
            Err(e) => {
                defects.push(malformed(line, e));
                return result;
            }
        };
        let Some(entries) = array.as_arr().filter(|a| a.len() <= MAX_DECLARATIONS) else {
            defects.push(role_error(
                Some(line),
                "role_declaration_invalid",
                String::new(),
                "material-roles must be an array of at most 512 declarations.".into(),
                "Supply up to 512 mappings in one JSON array.",
            ));
            return result;
        };
        let mut seen = BTreeMap::new();
        for (index, entry) in entries.iter().enumerate() {
            match read_mapping(entry, index, line, family) {
                Ok(Some(m)) => {
                    if let Some(first) = seen.get(&m) {
                        let mut error = role_error(
                            Some(line),
                            "role_duplicate",
                            format!("/{index}"),
                            format!("This declaration repeats the one at index {first}."),
                            "Keep one copy of the mapping.",
                        );
                        error.role = Some(m.role.clone());
                        error.source = Some(m.source.clone());
                        defects.push(error);
                    } else {
                        seen.insert(m.clone(), index);
                        result.entries.push((index, m));
                    }
                }
                Ok(None) => (),
                Err(e) => defects.push(e),
            }
        }
        result
    }

    pub fn has_mappings(&self) -> bool {
        !self.entries.is_empty()
    }

    /// Resolve names only against a complete inventory, and produce advice
    /// only after every independent error has been collected.
    pub fn assess<'a>(
        &self,
        family: Option<&Family>,
        names: impl Iterator<Item = &'a str>,
        mut errors: Vec<Defect>,
    ) -> Result<Vec<Defect>, Vec<Defect>> {
        let selected: BTreeSet<_> = names.collect();
        for (index, m) in &self.entries {
            if !selected.contains(m.source.as_str()) {
                let mut error = role_error(
                    self.line,
                    "role_source_unknown",
                    format!("/{index}/source"),
                    format!("{:?} does not name a selected regular material.", m.source),
                    "Correct the exact public name, supply the file, or remove the mapping.",
                );
                error.role = Some(m.role.clone());
                error.source = Some(m.source.clone());
                errors.push(error);
            }
        }
        if !errors.is_empty() {
            sort_defects(&mut errors);
            return Err(errors);
        }
        let family = family.expect("a valid question selects a family");
        Ok(family
            .material_roles
            .iter()
            .filter_map(|role| self.advice(role))
            .collect())
    }

    fn mapped<'a>(&'a self, role: &'a MaterialRole) -> impl Iterator<Item = &'a Mapping> {
        self.entries
            .iter()
            .map(|(_, m)| m)
            .filter(|m| m.role == role.id)
    }

    fn count(&self, role: &MaterialRole) -> usize {
        self.mapped(role)
            .map(|m| m.label.as_deref().unwrap_or(&m.source))
            .collect::<BTreeSet<_>>()
            .len()
    }

    fn advice(&self, role: &MaterialRole) -> Option<Defect> {
        let severity = role.severity()?;
        let count = self.count(role);
        if count >= role.minimum() {
            return None;
        }
        let message = match (role.labeled(), count) {
            (true, 1) => "The declarations identify one alternative label.".into(),
            (true, _) => "The declarations identify no alternative labels.".into(),
            _ => format!("No source is mapped to the {} role.", role.id),
        };
        let mut d = Defect::new("role_unmapped", None, Some(FIELD), message);
        d.severity = severity;
        d.role = Some(role.id.into());
        d.remedy = role.advice?.into();
        Some(d)
    }

    pub fn commissioning(&self, family: &Family) -> J {
        J::obj()
            .with("registry", REGISTRY)
            .with("descriptor", family.descriptor())
            .with(
                "material_roles",
                J::Arr(self.entries.iter().map(|(_, m)| m.to_j()).collect()),
            )
    }

    pub fn append_readable(&self, family: &Family, text: &mut String) {
        writeln!(
            text,
            "\n## Manager's declared material roles\n\n{} ({REGISTRY})",
            family.purpose
        )
        .unwrap();
        for role in family.material_roles {
            writeln!(
                text,
                "\n### {}\n\n{} Mapped {}: {}.",
                role.id,
                role.meaning,
                if role.labeled() { "labels" } else { "sources" },
                self.count(role)
            )
            .unwrap();
            for m in self.mapped(role) {
                writeln!(text, "\n    {}", m.to_j().string()).unwrap();
            }
            if let Some(d) = self.advice(role) {
                writeln!(text, "\n{}: {}", d.severity, d.remedy).unwrap();
            }
        }
    }
}

/// Validate the pinned member's format using its own descriptor. Its human
/// wording and role map never enter an auditor request.
pub fn check_capture(body: &Obj) -> Result<(), JsonError> {
    let member = body.obj("commissioning")?;
    member.exactly(&["registry", "descriptor", "material_roles"])?;
    member.one_of("registry", &[REGISTRY])?;
    let descriptor = member.obj("descriptor")?;
    descriptor.exactly(&["family", "available", "purpose", "roles"])?;
    if descriptor.str("family")? != body.str("family")? || !descriptor.bool("available")? {
        return Err(descriptor.invalid("family", "expected the selected available family"));
    }
    descriptor.str("purpose")?;
    let mut roles = BTreeMap::new();
    for (i, role) in descriptor.arr("roles")?.iter().enumerate() {
        let role = role.obj(&format!("{}/{i}", descriptor.ptr("roles")))?;
        role.exactly(&[
            "id",
            "meaning",
            "label",
            "minimum_recommended",
            "severity",
            "remedy",
        ])?;
        role.str("meaning")?;
        let labeled = role.one_of("label", &["required", "absent"])? == "required";
        let min = role.u64("minimum_recommended", MAX_DECLARATIONS as u64)?;
        let severity = role.str_or_null("severity")?;
        let remedy = role.str_or_null("remedy")?;
        if !matches!(
            (min, severity, remedy),
            (0, None, None) | (1.., Some("warning" | "suggestion"), Some(_))
        ) {
            return Err(role.invalid("severity", "advisory minimum, severity and remedy disagree"));
        }
        if roles.insert(role.str("id")?, labeled).is_some() {
            return Err(role.invalid("id", "duplicate role in the descriptor"));
        }
    }
    let mappings = member.arr("material_roles")?;
    if mappings.len() > MAX_DECLARATIONS {
        return Err(member.invalid("material_roles", "too many declarations"));
    }
    let mut seen = BTreeSet::new();
    for (i, value) in mappings.iter().enumerate() {
        let m = value.obj(&format!("{}/{i}", member.ptr("material_roles")))?;
        let role = m.str("role")?;
        let Some(&labeled) = roles.get(role) else {
            return Err(m.invalid("role", "role absent from the captured descriptor"));
        };
        let label = mapping_label(&m, labeled)?;
        if !seen.insert((role, m.str("source")?, label)) {
            return Err(m.invalid("source", "duplicate declaration"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn compare(text: &str, names: &[&str]) -> Result<Vec<Defect>, Vec<Defect>> {
        let family = crate::forms::family("comparison");
        let mut defects = Vec::new();
        let declarations = Declarations::parse(Some((text, 7)), family, &mut defects);
        declarations.assess(family, names.iter().copied(), defects)
    }

    #[test]
    fn array_and_utf8_label_limits_include_the_exact_boundary() {
        let source = "materials/a";
        let field = |count| {
            J::Arr(
                (0..count)
                    .map(|i| {
                        J::obj()
                            .with("role", "alternative")
                            .with("source", source)
                            .with("label", i.to_string())
                    })
                    .collect(),
            )
            .string()
        };
        let advice = compare(&field(512usize), &[source]).unwrap();
        assert_eq!(advice.len(), 1);
        assert_eq!(advice[0].role.as_deref(), Some("criterion"));
        let errors = compare(&field(513usize), &[source]).unwrap_err();
        assert_eq!(errors.len(), 1);
        assert_eq!(errors[0].pointer.as_deref(), Some(""));
        let label = |value| {
            J::Arr(vec![
                J::obj()
                    .with("role", "alternative")
                    .with("source", source)
                    .with("label", value),
            ])
            .string()
        };
        assert!(compare(&label("é".repeat(64)), &[source]).is_ok());
        for invalid in ["é".repeat(65), "  ".into(), "A\u{0085}".into()] {
            let d = compare(&label(invalid), &[source]).unwrap_err();
            assert_eq!(d.len(), 1);
            assert_eq!(d[0].reason, "role_declaration_invalid");
            assert_eq!(d[0].pointer.as_deref(), Some("/0/label"));
        }
    }

    #[test]
    fn duplicate_and_missing_sources_follow_numeric_declaration_order() {
        let mut entries = Vec::new();
        for i in 0..12 {
            entries.push(
                J::obj()
                    .with("role", "alternative")
                    .with(
                        "source",
                        if i == 2 || i == 10 {
                            "materials/missing"
                        } else {
                            "materials/a"
                        },
                    )
                    .with("label", i.to_string()),
            );
        }
        entries.push(entries[1].clone());
        let errors = compare(&J::Arr(entries).string(), &["materials/a"]).unwrap_err();
        assert_eq!(
            errors
                .iter()
                .map(|d| (d.reason, d.pointer.as_deref()))
                .collect::<Vec<_>>(),
            [
                ("role_source_unknown", Some("/2/source")),
                ("role_source_unknown", Some("/10/source")),
                ("role_duplicate", Some("/12"))
            ]
        );
        assert!(errors[2].message.contains("index 1"));
    }

    #[test]
    fn strict_json_and_shape_failures_stop_dependent_lookups() {
        for (text, pointer) in [
            (
                r#"[{"role":"report","r\u006fle":"criterion","source":"absent"}]"#,
                "/0/role",
            ),
            (
                r#"[{"role":"report","source":"absent","label":"unused"}]"#,
                "/0/label",
            ),
            (r#"[{"role":"alternative","source":"absent"}]"#, "/0/label"),
            (r#"[{"role":"context","source":5}]"#, "/0/source"),
            (r#"[[]]"#, "/0"),
            (r#"{}"#, ""),
        ] {
            let errors = compare(text, &[]).unwrap_err();
            assert_eq!(errors.len(), 1, "{text}");
            assert_eq!(
                (errors[0].reason, errors[0].pointer.as_deref()),
                ("role_declaration_invalid", Some(pointer))
            );
        }
    }
}
