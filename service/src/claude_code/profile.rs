//! Checked, nonsecret launch inputs. This module never invokes a process or
//! opens the harness credential directory. A check receipt is an attributed
//! installation/check record, not authority to start a model session.

use crate::archive::Fail;
use crate::fsx::Dir;
use crate::json::{self, J, JsonError, Obj};
use crate::{ids, util};
use sha2::{Digest, Sha256};
use std::io::Read;

pub const PROFILE_SCHEMA: &str = "stewart.claude-code.profile/2";
pub const ARRANGEMENT_SCHEMA: &str = "stewart.claude-code.arrangement/2";
pub const SIGNER: &str = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE";
pub const MAX_PROFILE_BYTES: u64 = 64 * 1024;
pub const MAX_PLACEMENTS: u64 = 10_000;
pub const MAX_SECONDS: u64 = 86_400;
pub const MAX_TURNS: u64 = 200;
pub const MAX_OUTPUT_TOKENS: u64 = 16_000;
/// The front matter field whose presence selects this runtime, on the one
/// question version. Without it a question is a Messages API question.
pub const SELECTOR: &str = "runtime-profile";
pub const EXTRA_KEYS: [&str; 3] = [SELECTOR, "max-placements", "placement-timeout-seconds"];

pub fn frontmatter(
    fields: &[(String, String, usize)],
    selected: bool,
    settings: &mut crate::frontmatter::Settings,
    defects: &mut Vec<crate::frontmatter::Defect>,
) {
    use crate::frontmatter::Defect;
    let get = |key: &str| fields.iter().find(|(k, _, _)| k == key);
    let mut invalid = |key: &str, message: &str| {
        defects.push(Defect::new(
            "setting_invalid",
            get(key).map(|(_, _, l)| *l),
            Some(key),
            message,
        ));
    };
    if !selected {
        // Without a profile this is a Messages API question; the placement
        // fields have no meaning there.
        for key in EXTRA_KEYS {
            if get(key).is_some() {
                invalid(
                    key,
                    &format!(
                        "{key} applies only to a question that names {SELECTOR}; without it the question uses limit-turns, limit-input-tokens and limit-output-tokens"
                    ),
                );
            }
        }
        return;
    }
    for key in ["limit-turns", "limit-input-tokens", "limit-output-tokens"] {
        if get(key).is_some() {
            invalid(
                key,
                &format!(
                    "{key} is a Messages API limit; a question that names {SELECTOR} takes max-placements and placement-timeout-seconds instead"
                ),
            );
        }
    }
    let path = get(SELECTOR).map(|(_, v, _)| v.as_str()).unwrap_or("");
    if ids::check_absolute(path).is_err() {
        invalid(SELECTOR, "a runtime profile must be an absolute file path");
    }
    let mut missing = Vec::new();
    let mut value = |key: &'static str, max: u64| {
        let Some((_, v, _)) = get(key) else {
            missing.push(key);
            return 0;
        };
        match v.parse::<u64>() {
            Ok(n) if n > 0 && n <= max && n.to_string() == *v => n,
            _ => {
                invalid(
                    key,
                    &format!("{key} must be an integer from 1 to {max} without leading zeros"),
                );
                0
            }
        }
    };
    let limits = Limits {
        max_placements: value("max-placements", MAX_PLACEMENTS),
        placement_timeout_seconds: value("placement-timeout-seconds", MAX_SECONDS),
    };
    // A missing placement field is reported as any missing required key is.
    for key in missing {
        defects.push(Defect::new(
            "setting_missing",
            None,
            Some(key),
            format!(
                "the required key {key} is missing from the front matter; a question that names {SELECTOR} needs it."
            ),
        ));
    }
    settings.harness = Some(Selection {
        path: path.into(),
        limits,
        profile: None,
    });
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Limits {
    pub max_placements: u64,
    pub placement_timeout_seconds: u64,
}

impl Limits {
    pub fn to_j(self) -> J {
        J::obj()
            .with("max_placements", self.max_placements)
            .with("placement_timeout_seconds", self.placement_timeout_seconds)
    }
    pub fn decode(o: &Obj) -> Result<Self, JsonError> {
        o.exactly(&["max_placements", "placement_timeout_seconds"])?;
        let result = Self {
            max_placements: o.u64("max_placements", MAX_PLACEMENTS)?,
            placement_timeout_seconds: o.u64("placement_timeout_seconds", MAX_SECONDS)?,
        };
        if result.max_placements == 0 || result.placement_timeout_seconds == 0 {
            return Err(o.invalid("max_placements", "placement limits must be positive"));
        }
        Ok(result)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Selection {
    pub path: String,
    pub limits: Limits,
    /// Filled locally at prepare and retained exactly in settings/arrangement.
    pub profile: Option<String>,
}

impl Selection {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("kind", "claude-code/1")
            .with("profile_path", self.path.as_str())
            .with("profile", self.profile.as_deref())
    }
    pub fn decode(o: &Obj, limits: &Obj) -> Result<Self, JsonError> {
        o.exactly(&["kind", "profile_path", "profile"])?;
        if o.str("kind")? != "claude-code/1" {
            return Err(o.invalid("kind", "unsupported runtime"));
        }
        let path = o.str("profile_path")?;
        ids::check_absolute(path).map_err(|e| o.invalid("profile_path", e))?;
        let profile = o.str("profile")?;
        Profile::parse(profile.as_bytes()).map_err(|e| o.invalid("profile", e))?;
        Ok(Self {
            path: path.into(),
            limits: Limits::decode(limits)?,
            profile: Some(profile.into()),
        })
    }
}

/// Reply data as people read it: wherever a runtime selection appears, its
/// captured profile text is replaced by that text's SHA-256, beside the path.
/// The digest is the arrangement's `profile_sha256`. JSON replies are not
/// passed through here and keep the exact text.
pub fn for_people(data: &J) -> J {
    match data {
        J::Obj(members) => {
            let selection = matches!(data.get("kind"), Some(J::Str(k)) if k == "claude-code/1")
                && data.get("profile_path").is_some();
            J::Obj(
                members
                    .iter()
                    .map(|(key, value)| match value {
                        J::Str(text) if selection && key == "profile" => (
                            "profile_sha256".to_string(),
                            J::Str(util::sha256_hex(text.as_bytes())),
                        ),
                        _ => (key.clone(), for_people(value)),
                    })
                    .collect(),
            )
        }
        J::Arr(items) => J::Arr(items.iter().map(for_people).collect()),
        other => other.clone(),
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Profile {
    pub executable: String,
    pub sha256: String,
    pub version: String,
    pub platform: String,
    pub config_directory: String,
    pub home: String,
    pub temporary_directory: String,
    /// The launch surface the check session exercised.
    pub surface_sha256: String,
    pub tools_sha256: String,
    pub model: String,
    pub checked_at: String,
}

fn absolute(o: &Obj, key: &str) -> Result<String, JsonError> {
    let value = o.str(key)?;
    ids::check_absolute(value).map_err(|e| o.invalid(key, e))?;
    Ok(value.into())
}

impl Profile {
    pub fn parse(raw: &[u8]) -> Result<Self, String> {
        if raw.len() as u64 > MAX_PROFILE_BYTES {
            return Err("runtime profile exceeds 64 KiB".into());
        }
        let parsed = json::parse(raw).map_err(|e| e.to_string())?;
        (|| {
            let o = parsed.obj("")?;
            // One profile form is read. Any other identifier, including an
            // earlier one, is refused by name before its members are examined.
            let schema = o.str("schema")?;
            if schema != PROFILE_SCHEMA {
                return Err(o.invalid(
                    "schema",
                    format!(
                        "unsupported profile schema {schema:?}; this binary reads only {PROFILE_SCHEMA}"
                    ),
                ));
            }
            o.exactly(&["schema", "launch", "installation", "check"])?;
            let l = o.obj("launch")?;
            l.exactly(&[
                "executable",
                "sha256",
                "version",
                "platform",
                "config_directory",
                "home",
                "temporary_directory",
            ])?;
            let i = o.obj("installation")?;
            i.exactly(&["manifest_sha256", "signer", "binary_sha256"])?;
            i.sha256("manifest_sha256")?;
            if i.str("signer")? != SIGNER || i.sha256("binary_sha256")? != l.sha256("sha256")? {
                return Err(i.invalid(
                    "signer",
                    "installation attestation does not bind this binary and release signer",
                ));
            }
            let c = o.obj("check")?;
            c.exactly(&[
                "surface_sha256",
                "launch_sha256",
                "tools_sha256",
                "model",
                "checked_at",
                "evidence_sha256",
                "outcome",
            ])?;
            let span = o.req("launch")?;
            if c.sha256("launch_sha256")? != util::sha256_hex(&raw[span.start..span.end])
                || c.str("outcome")? != "observed"
            {
                return Err(c.invalid(
                    "launch_sha256",
                    "check must report observed and bind the exact launch object",
                ));
            }
            c.sha256("evidence_sha256")?;
            let version = l.str("version")?;
            if version.is_empty() || version.len() > 128 {
                return Err(l.invalid("version", "expected a pinned CLI version"));
            }
            Ok(Self {
                executable: absolute(&l, "executable")?,
                sha256: l.sha256("sha256")?.into(),
                version: version.into(),
                platform: l.str("platform")?.into(),
                config_directory: absolute(&l, "config_directory")?,
                home: absolute(&l, "home")?,
                temporary_directory: absolute(&l, "temporary_directory")?,
                surface_sha256: c.sha256("surface_sha256")?.into(),
                tools_sha256: c.sha256("tools_sha256")?.into(),
                model: c.str("model")?.into(),
                checked_at: c.str("checked_at")?.into(),
            })
        })()
        .map_err(|e: JsonError| e.to_string())
    }

    /// The check's bindings to what this binary and this question supply.
    /// `surface` is the running binary's own launch surface digest.
    pub fn bindings(&self, surface: &str, model: &str, tools: &[u8]) -> Result<(), String> {
        if self.surface_sha256 != surface {
            return Err(surface_differs(&self.surface_sha256, surface));
        }
        if self.model != model || self.tools_sha256 != util::sha256_hex(tools) {
            return Err("runtime check does not bind this model and MCP tool surface; a separately commissioned check is needed".into());
        }
        if self.platform != format!("{}-{}", std::env::consts::OS, std::env::consts::ARCH) {
            return Err("runtime check belongs to another platform".into());
        }
        Ok(())
    }

    /// The bindings, then the pinned executable's digest. Reads the
    /// executable without executing it.
    pub fn check(&self, surface: &str, model: &str, tools: &[u8]) -> Result<(), String> {
        self.bindings(surface, model, tools)?;
        let (mut file, _) = open_regular(&self.executable)?;
        let mut hash = Sha256::new();
        let mut chunk = [0; 65536];
        loop {
            let count = file.read(&mut chunk).map_err(|e| e.to_string())?;
            if count == 0 {
                break;
            }
            hash.update(&chunk[..count]);
        }
        if util::hex(&hash.finalize()) != self.sha256 {
            return Err("pinned harness executable changed".into());
        }
        Ok(())
    }
}

/// The diagnostic for a check of another surface. It states the digest this
/// binary supplies, so a manager learns it without any launch.
pub fn surface_differs(named: &str, supplied: &str) -> String {
    format!(
        "the runtime check names launch surface {named}, but this binary's launch surface ({}) has SHA-256 {supplied}; a separately commissioned check of this surface is needed",
        super::surface::SCHEMA
    )
}

pub fn open_regular(path: &str) -> Result<(std::fs::File, crate::fsx::Stat), String> {
    ids::check_absolute(path).map_err(|e| e.to_string())?;
    let (parent, name) = path.rsplit_once('/').ok_or("expected an absolute path")?;
    let dir = Dir::open_nofollow(if parent.is_empty() { "/" } else { parent })
        .map_err(|e| format!("{e:?}"))?;
    dir.open_regular(name).map_err(|e| e.describe())
}

/// Load and check the selected profile for `prepare`. Every refusal carries
/// this binary's launch surface, so the digest a check must name is available
/// without a launch.
pub fn prepare(settings: &mut crate::frontmatter::Settings) -> Result<(), Fail> {
    let Some(selection) = &mut settings.harness else {
        return Ok(());
    };
    let fail = |e: String| {
        Fail::refused(
            "runtime_profile_invalid",
            format!("The runtime profile cannot be prepared: {e}. No harness was launched."),
        )
        .data(super::surface::report())
    };
    let (file, stat) = open_regular(&selection.path).map_err(fail)?;
    if stat.size > MAX_PROFILE_BYTES {
        return Err(fail("profile exceeds 64 KiB".into()));
    }
    let mut raw = Vec::new();
    file.take(MAX_PROFILE_BYTES + 1)
        .read_to_end(&mut raw)
        .map_err(|e| fail(e.to_string()))?;
    let profile = Profile::parse(&raw).map_err(fail)?;
    let family = crate::forms::family(&settings.family).expect("validated family");
    let tools = super::mcp_tools(&crate::forms::tools(family).bytes()).map_err(fail)?;
    profile
        .check(&super::surface::sha256(), &settings.model, &tools)
        .map_err(fail)?;
    selection.profile = Some(String::from_utf8(raw).map_err(|e| fail(e.to_string()))?);
    Ok(())
}

#[cfg(test)]
pub(crate) mod tests {
    use super::super::surface;
    use super::*;

    /// A profile text whose check holds `binding: surface`. Its other
    /// bindings are valid for `model` and `tools` on this platform.
    pub(crate) fn fixture(schema: &str, binding: &str, surface: &str, tools: &[u8]) -> String {
        let launch = format!(
            r#"{{"executable":"/fixture/harness","sha256":"{}","version":"2.1.322","platform":"{}-{}","config_directory":"/fixture/config","home":"/fixture/home","temporary_directory":"/fixture/tmp"}}"#,
            "a".repeat(64),
            std::env::consts::OS,
            std::env::consts::ARCH
        );
        format!(
            r#"{{"schema":"{schema}","launch":{launch},"installation":{{"manifest_sha256":"{}","signer":"{SIGNER}","binary_sha256":"{}"}},"check":{{"{binding}":"{surface}","launch_sha256":"{}","tools_sha256":"{}","model":"fixture-model","checked_at":"2026-11-11","evidence_sha256":"{}","outcome":"observed"}}}}"#,
            "b".repeat(64),
            "a".repeat(64),
            util::sha256_hex(launch.as_bytes()),
            util::sha256_hex(tools),
            "c".repeat(64),
        )
    }

    #[test]
    fn the_check_binds_the_surface_and_not_the_writer() {
        let own = surface::sha256();
        let text = fixture(PROFILE_SCHEMA, "surface_sha256", &own, b"[]");
        let profile = Profile::parse(text.as_bytes()).unwrap();
        // The bindings take no writer identity: any build supplying this
        // surface accepts the same profile bytes.
        profile.bindings(&own, "fixture-model", b"[]").unwrap();
        // Firing control: a build supplying another surface refuses, and
        // says which digest it supplies.
        let other = util::sha256_hex(b"another surface");
        let refusal = profile
            .bindings(&other, "fixture-model", b"[]")
            .unwrap_err();
        assert!(
            refusal.contains(&own) && refusal.contains(&other),
            "{refusal}"
        );
        assert!(refusal.contains(surface::SCHEMA), "{refusal}");
        // The other bindings still refuse on their own.
        assert!(profile.bindings(&own, "another-model", b"[]").is_err());
        assert!(profile.bindings(&own, "fixture-model", b"[{}]").is_err());
    }

    #[test]
    fn people_see_the_profile_path_and_digest_not_its_text() {
        let text = fixture(PROFILE_SCHEMA, "surface_sha256", &surface::sha256(), b"[]");
        let selection = Selection {
            path: "/fixture/profile.json".into(),
            limits: Limits {
                max_placements: 2,
                placement_timeout_seconds: 60,
            },
            profile: Some(text.clone()),
        };
        let data = J::obj().with("prepared", "mp1.aaaaaa").with(
            "settings",
            J::obj()
                .with("model", "fixture-model")
                .with("runtime", selection.to_j()),
        );
        let shown = for_people(&data).string();
        assert!(shown.contains(r#""profile_path":"/fixture/profile.json""#));
        assert!(shown.contains(&format!(
            r#""profile_sha256":"{}""#,
            util::sha256_hex(text.as_bytes())
        )));
        assert!(!shown.contains("installation") && !shown.contains(r#""profile":"#));
        // The reply itself is untouched and keeps the exact text.
        assert!(data.string().contains(&crate::json::quote(&text)));
        // Invariance: data without a runtime selection is shown as it is,
        // including a member that merely shares the name.
        let other = J::obj().with("settings", J::obj().with("profile", "kept"));
        assert_eq!(for_people(&other), other);
    }

    #[test]
    fn only_the_current_profile_form_is_read() {
        let own = surface::sha256();
        let earlier = fixture(
            "stewart.claude-code.profile/1",
            "surface_sha256",
            &own,
            b"[]",
        );
        let refusal = Profile::parse(earlier.as_bytes()).unwrap_err();
        assert!(
            refusal.contains("stewart.claude-code.profile/1") && refusal.contains(PROFILE_SCHEMA),
            "{refusal}"
        );
        let writer_bound = fixture(PROFILE_SCHEMA, "writer_sha256", &own, b"[]");
        assert!(Profile::parse(writer_bound.as_bytes()).is_err());
        let malformed = fixture(PROFILE_SCHEMA, "surface_sha256", "not-a-digest", b"[]");
        assert!(Profile::parse(malformed.as_bytes()).is_err());
    }
}
