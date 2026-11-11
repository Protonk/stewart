//! Checked, nonsecret launch inputs. This module never invokes a process or
//! opens the harness credential directory. A check receipt is an attributed
//! installation/check record, not authority to start a model session.

use crate::archive::{Audit, Fail};
use crate::fsx::Dir;
use crate::json::{self, J, JsonError, Obj};
use crate::{ids, util};
use sha2::{Digest, Sha256};
use std::io::Read;

pub const QUESTION_SCHEMA: &str = "question/claude-code/1";
pub const PROFILE_SCHEMA: &str = "stewart.claude-code.profile/1";
pub const ARRANGEMENT_SCHEMA: &str = "stewart.claude-code.arrangement/1";
pub const SIGNER: &str = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE";
pub const MAX_PROFILE_BYTES: u64 = 64 * 1024;
pub const MAX_PLACEMENTS: u64 = 10_000;
pub const MAX_SECONDS: u64 = 86_400;
pub const MAX_TURNS: u64 = 200;
pub const MAX_OUTPUT_TOKENS: u64 = 16_000;
pub const EXTRA_KEYS: [&str; 3] = [
    "runtime-profile",
    "max-placements",
    "placement-timeout-seconds",
];

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
        for key in EXTRA_KEYS {
            if get(key).is_some() {
                invalid(key, "runtime fields require question/claude-code/1");
            }
        }
        return;
    }
    for key in ["limit-turns", "limit-input-tokens", "limit-output-tokens"] {
        if get(key).is_some() {
            invalid(
                key,
                "API turn/token limits are not supported by this runtime; use placement limits",
            );
        }
    }
    let path = get("runtime-profile")
        .map(|(_, v, _)| v.as_str())
        .unwrap_or("");
    if ids::check_absolute(path).is_err() {
        invalid(
            "runtime-profile",
            "a runtime profile must be an absolute file path",
        );
    }
    let mut value = |key: &str, max: u64| {
        let v = get(key).map(|(_, v, _)| v.as_str()).unwrap_or("");
        match v.parse::<u64>() {
            Ok(n) if n > 0 && n <= max && n.to_string() == v => n,
            _ => {
                invalid(
                    key,
                    &format!(
                        "{key} is required, as an integer from 1 to {max} without leading zeros"
                    ),
                );
                0
            }
        }
    };
    settings.harness = Some(Selection {
        path: path.into(),
        limits: Limits {
            max_placements: value("max-placements", MAX_PLACEMENTS),
            placement_timeout_seconds: value("placement-timeout-seconds", MAX_SECONDS),
        },
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Profile {
    pub executable: String,
    pub sha256: String,
    pub version: String,
    pub platform: String,
    pub config_directory: String,
    pub home: String,
    pub temporary_directory: String,
    pub writer_sha256: String,
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
            o.exactly(&["schema", "launch", "installation", "check"])?;
            if o.str("schema")? != PROFILE_SCHEMA {
                return Err(o.invalid("schema", format!("expected {PROFILE_SCHEMA}")));
            }
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
                "writer_sha256",
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
                writer_sha256: c.sha256("writer_sha256")?.into(),
                tools_sha256: c.sha256("tools_sha256")?.into(),
                model: c.str("model")?.into(),
                checked_at: c.str("checked_at")?.into(),
            })
        })()
        .map_err(|e: JsonError| e.to_string())
    }

    pub fn check(&self, writer: &str, model: &str, tools: &[u8]) -> Result<(), String> {
        if self.writer_sha256 != writer
            || self.model != model
            || self.tools_sha256 != util::sha256_hex(tools)
        {
            return Err("runtime check does not bind this writer, model and MCP tool surface; a separately commissioned check is needed".into());
        }
        if self.platform != format!("{}-{}", std::env::consts::OS, std::env::consts::ARCH) {
            return Err("runtime check belongs to another platform".into());
        }
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

pub fn open_regular(path: &str) -> Result<(std::fs::File, crate::fsx::Stat), String> {
    ids::check_absolute(path).map_err(|e| e.to_string())?;
    let (parent, name) = path.rsplit_once('/').ok_or("expected an absolute path")?;
    let dir = Dir::open_nofollow(if parent.is_empty() { "/" } else { parent })
        .map_err(|e| format!("{e:?}"))?;
    dir.open_regular(name).map_err(|e| e.describe())
}

pub fn prepare(audit: &Audit, settings: &mut crate::frontmatter::Settings) -> Result<(), Fail> {
    let Some(selection) = &mut settings.harness else {
        return Ok(());
    };
    let fail = |e: String| {
        Fail::refused(
            "runtime_profile_invalid",
            format!("The runtime profile cannot be prepared: {e}. No harness was launched."),
        )
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
        .check(&audit.refile.writer_sha256, &settings.model, &tools)
        .map_err(fail)?;
    selection.profile = Some(String::from_utf8(raw).map_err(|e| fail(e.to_string()))?);
    Ok(())
}
