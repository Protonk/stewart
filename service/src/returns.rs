//! The return: its manifest (`stewart.return/1`, INTERFACE 8.2), written at
//! seal, and the plan of each delivery attempt (`delivery_plan`, 8.3).
//!
//! The manifest is not a `stewart.record/1` record. It is one line of
//! compact JSON and an LF, keys in a fixed order and strings escaped as in
//! `stewart.answer/1`, so its bytes are reproducible and verify the package
//! without the archive. Decoding checks the layout by writing the decoded
//! value back and comparing bytes. It never contains the seal handle; the
//! handle binds the manifest.
//!
//! A delivery plan is a record of kind `delivery_plan` in
//! `delivery/<attempt>.json`, claimed exclusively (`names::write_plan`).

use crate::archive::{Audit, RECORD_LIMIT, decode_record};
use crate::bodies::{Actor, DESTINATION_SOURCES, MEMBER_ROLES, RECORDERS};
use crate::fsx::ReadError;
use crate::json::{self, J, JsonError, Obj};
use crate::names;
use crate::util;

pub const RETURN_SCHEMA: &str = "stewart.return/1";
pub const MANIFEST_MEMBER: &str = "manifest.json";
pub const ANSWER_MEMBER: &str = "answer.json";
pub const RENDERING_MEMBER: &str = "answer.md";
/// Failures of an unproduced entry.
pub const ENTRY_FAILURES: [&str; 3] = ["missing", "unreadable", "damaged"];

const NUM_MAX: u64 = 1 << 48;

/// A produced member of the return.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Member {
    pub name: String,
    /// `answer`, `rendering` or `artifact`.
    pub role: String,
    pub size: u64,
    pub sha256: String,
}

/// A member the seal could not produce: an entry (named by its ID) whose
/// bytes could not be read or verified, or the rendering that depends on it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Unproduced {
    pub name: String,
    /// `entry` or `rendering`.
    pub role: String,
    /// `missing`, `unreadable` or `damaged` for an entry; `not_rendered`.
    pub failure: String,
    /// For the rendering, the unproduced entries it depends on; else `None`.
    pub dependency: Option<Vec<String>>,
}

/// The return manifest (8.2).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Manifest {
    pub audit: String,
    pub store: String,
    /// The family ID and version, `open-inquiry/1`.
    pub family: String,
    /// The renderer version.
    pub renderer: String,
    /// The SHA-256 of the sealing executable.
    pub writer: String,
    pub actor: Actor,
    /// When Stewart wrote the manifest, immediately before publishing the
    /// seal (UTC, milliseconds).
    pub sealed_at: String,
    /// The sealed selection's answer revision.
    pub revision: u64,
    /// `answer.json`, then `answer.md` unless unproduced, then each produced
    /// artifact in selection order.
    pub members: Vec<Member>,
    /// Each unproduced entry in selection order, then an unproduced rendering.
    pub unproduced: Vec<Unproduced>,
}

impl Manifest {
    /// The exact bytes: one line of compact JSON and an LF.
    pub fn bytes(&self) -> Vec<u8> {
        let seal = J::obj()
            .with("actor", self.actor.name())
            .with("sealed_at", self.sealed_at.as_str());
        let mut j = J::obj()
            .with("schema", RETURN_SCHEMA)
            .with("audit", self.audit.as_str())
            .with("store", self.store.as_str())
            .with("family", self.family.as_str())
            .with("renderer", self.renderer.as_str())
            .with("writer", self.writer.as_str())
            .with("seal", seal)
            .with("revision", self.revision)
            .with(
                "members",
                J::Arr(
                    self.members
                        .iter()
                        .map(|m| {
                            J::obj()
                                .with("name", m.name.as_str())
                                .with("role", m.role.as_str())
                                .with("size", m.size)
                                .with("sha256", m.sha256.as_str())
                        })
                        .collect(),
                ),
            )
            .with(
                "unproduced",
                J::Arr(
                    self.unproduced
                        .iter()
                        .map(|u| {
                            J::obj()
                                .with("name", u.name.as_str())
                                .with("role", u.role.as_str())
                                .with("failure", u.failure.as_str())
                                .with(
                                    "dependency",
                                    u.dependency
                                        .as_ref()
                                        .map(|d| json::strs(d))
                                        .unwrap_or(J::Null),
                                )
                        })
                        .collect(),
                ),
            );
        if crate::sabotage!("manifest_verdict") {
            // Sabotage control: the manifest grades the return.
            j.push("verdict", "complete");
        }
        let mut b = j.bytes();
        b.push(b'\n');
        b
    }

    /// Decode strictly and check the layout: the decoded value must write
    /// back to exactly these bytes.
    pub fn decode(bytes: &[u8]) -> Result<Manifest, String> {
        let v = json::parse(bytes).map_err(|e| format!("not strict control JSON: {e}"))?;
        let m = decode_value(&v.obj("").map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        if m.bytes() != bytes {
            return Err("the manifest is not in the stewart.return/1 layout (one compact line, keys in order, an LF)".into());
        }
        Ok(m)
    }

    /// The member names a delivery writes after `manifest.json`, in order.
    pub fn member_names(&self) -> Vec<&str> {
        self.members.iter().map(|m| m.name.as_str()).collect()
    }
}

fn decode_value(o: &Obj) -> Result<Manifest, JsonError> {
    let mut keys = vec![
        "schema",
        "audit",
        "store",
        "family",
        "renderer",
        "writer",
        "seal",
        "revision",
        "members",
        "unproduced",
    ];
    if crate::sabotage!("manifest_verdict") {
        keys.push("verdict");
    }
    o.exactly(&keys)?;
    if o.str("schema")? != RETURN_SCHEMA {
        return Err(o.invalid("schema", format!("expected {RETURN_SCHEMA}")));
    }
    let seal = o.obj("seal")?;
    seal.exactly(&["actor", "sealed_at"])?;
    let actor = match seal.one_of("actor", &["auditor", "manager"])? {
        "auditor" => Actor::Auditor,
        _ => Actor::Manager,
    };
    if !util::is_utc_ms(seal.str("sealed_at")?) {
        return Err(seal.invalid("sealed_at", "expected a UTC time with milliseconds"));
    }
    let mut members = Vec::new();
    for (i, v) in o.arr("members")?.iter().enumerate() {
        let m = v.obj(&format!("{}/{i}", o.ptr("members")))?;
        m.exactly(&["name", "role", "size", "sha256"])?;
        members.push(Member {
            name: m.str("name")?.to_string(),
            role: m
                .one_of("role", &["answer", "rendering", "artifact"])?
                .to_string(),
            size: m.u64("size", NUM_MAX)?,
            sha256: m.sha256("sha256")?.to_string(),
        });
    }
    let mut unproduced = Vec::new();
    for (i, v) in o.arr("unproduced")?.iter().enumerate() {
        let u = v.obj(&format!("{}/{i}", o.ptr("unproduced")))?;
        u.exactly(&["name", "role", "failure", "dependency"])?;
        let role = u.one_of("role", &["entry", "rendering"])?.to_string();
        let (failure, dependency) = if role == "entry" {
            if !u.req("dependency")?.is_null() {
                return Err(u.invalid("dependency", "an unproduced entry depends on nothing"));
            }
            (u.one_of("failure", &ENTRY_FAILURES)?.to_string(), None)
        } else {
            let d = u
                .strs("dependency")?
                .into_iter()
                .map(str::to_string)
                .collect();
            (u.one_of("failure", &["not_rendered"])?.to_string(), Some(d))
        };
        unproduced.push(Unproduced {
            name: u.str("name")?.to_string(),
            role,
            failure,
            dependency,
        });
    }
    // Membership order: answer.json, answer.md unless unproduced, artifacts.
    let rendering_unproduced = unproduced.iter().any(|u| u.role == "rendering");
    let mut want = vec![(ANSWER_MEMBER, "answer")];
    if !rendering_unproduced {
        want.push((RENDERING_MEMBER, "rendering"));
    }
    let heads: Vec<(&str, &str)> = members
        .iter()
        .take(want.len())
        .map(|m| (m.name.as_str(), m.role.as_str()))
        .collect();
    let artifacts_ok = members.iter().skip(want.len()).all(|m| {
        m.role == "artifact"
            && m.name
                .strip_prefix("artifact-")
                .and_then(|r| r.strip_suffix(".bin"))
                .and_then(names::parse_entry_id)
                .is_some()
    });
    if heads != want || !artifacts_ok {
        return Err(o.invalid(
            "members",
            "members are answer.json, then answer.md unless it is unproduced, then artifact-<id>.bin members",
        ));
    }
    Ok(Manifest {
        audit: o.str("audit")?.to_string(),
        store: o.str("store")?.to_string(),
        family: o.str("family")?.to_string(),
        renderer: o.str("renderer")?.to_string(),
        writer: o.sha256("writer")?.to_string(),
        actor,
        sealed_at: seal.str("sealed_at")?.to_string(),
        revision: o.u64("revision", NUM_MAX)?,
        members,
        unproduced,
    })
}

/// Read a seal's manifest and check it against the digest the `seal` record
/// binds. Returns the manifest and its exact bytes. An error is the reason
/// membership is unknown (8.3).
pub fn load_manifest(
    audit: &Audit,
    name: &str,
    want_sha256: &str,
) -> Result<(Manifest, Vec<u8>), String> {
    let file = name
        .strip_prefix("seal/")
        .filter(|_| names::parse_manifest_name(name).is_some())
        .ok_or_else(|| format!("{name:?} is not a seal manifest name"))?;
    let dir = audit
        .dir
        .open_dir("seal")
        .map_err(|e| format!("seal/ cannot be opened: {}", util::describe(&e)))?;
    let (bytes, _) = dir.read_regular(file, RECORD_LIMIT).map_err(|e| match e {
        ReadError::Missing => format!("{name} is missing"),
        other => format!("{name} cannot be read: {}", other.describe()),
    })?;
    if util::sha256_hex(&bytes) != want_sha256 {
        return Err(format!(
            "{name} does not match the digest its seal record binds"
        ));
    }
    let m = Manifest::decode(&bytes).map_err(|e| format!("{name}: {e}"))?;
    if m.audit != audit.id || m.store != audit.archive.store {
        return Err(format!("{name} names another audit or store"));
    }
    Ok((m, bytes))
}

// ---------------------------------------------------------------------------
// Delivery plans.

/// Where an attempt delivers.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlanDestination {
    /// The destination directory's absolute path.
    pub path: String,
    /// `commissioned` or `replacement`.
    pub source: String,
    /// The destination's device and inode, `None` when it could not be opened.
    pub device: Option<u64>,
    pub inode: Option<u64>,
}

/// One member an attempt plans to write, with its archive source.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlanMember {
    pub name: String,
    /// `manifest`, `answer`, `rendering` or `artifact`.
    pub role: String,
    pub size: u64,
    pub sha256: String,
    /// The audit-relative archive file the member is copied from.
    pub source: String,
}

/// A `delivery_plan` record's body (8.3).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeliveryPlan {
    pub attempt: u64,
    /// The `seal` record, `log/<n>.json`.
    pub seal: String,
    /// `seal/manifest-<k>.json`.
    pub manifest: String,
    pub manifest_sha256: String,
    pub destination: PlanDestination,
    /// `stewart-return-<audit>-<nnn>`.
    pub package: String,
    pub replaces: Option<u64>,
    /// `run` or `close`.
    pub by: String,
    /// `manifest.json`, then the manifest's members in order; `None` when the
    /// manifest cannot be read and checked against the seal's digest.
    pub members: Option<Vec<PlanMember>>,
}

impl DeliveryPlan {
    pub fn to_j(&self) -> J {
        let d = &self.destination;
        J::obj()
            .with("attempt", self.attempt)
            .with("seal", self.seal.as_str())
            .with("manifest", self.manifest.as_str())
            .with("manifest_sha256", self.manifest_sha256.as_str())
            .with(
                "destination",
                J::obj()
                    .with("path", d.path.as_str())
                    .with("source", d.source.as_str())
                    .with("device", d.device)
                    .with("inode", d.inode),
            )
            .with("package", self.package.as_str())
            .with("replaces", self.replaces)
            .with("by", self.by.as_str())
            .with(
                "members",
                match &self.members {
                    Some(ms) => J::Arr(
                        ms.iter()
                            .map(|m| {
                                J::obj()
                                    .with("name", m.name.as_str())
                                    .with("role", m.role.as_str())
                                    .with("size", m.size)
                                    .with("sha256", m.sha256.as_str())
                                    .with("source", m.source.as_str())
                            })
                            .collect(),
                    ),
                    None => J::Null,
                },
            )
    }

    pub fn decode(b: &Obj, audit: &str) -> Result<DeliveryPlan, JsonError> {
        b.exactly(&[
            "attempt",
            "seal",
            "manifest",
            "manifest_sha256",
            "destination",
            "package",
            "replaces",
            "by",
            "members",
        ])?;
        let attempt = b.u64("attempt", NUM_MAX)?;
        let package = b.str("package")?.to_string();
        if package != names::package_name(audit, attempt) {
            return Err(b.invalid(
                "package",
                format!("expected {}", names::package_name(audit, attempt)),
            ));
        }
        let seal = b.str("seal")?.to_string();
        if names::parse_log_name(&seal).is_none() {
            return Err(b.invalid("seal", "expected a log record name, log/<n>.json"));
        }
        let manifest = b.str("manifest")?.to_string();
        if names::parse_manifest_name(&manifest).is_none() {
            return Err(b.invalid("manifest", "expected seal/manifest-<k>.json"));
        }
        let d = b.obj("destination")?;
        d.exactly(&["path", "source", "device", "inode"])?;
        let members = match b.arr_or_null("members")? {
            None => None,
            Some(items) => {
                let mut out = Vec::new();
                for (i, v) in items.iter().enumerate() {
                    let m = v.obj(&format!("{}/{i}", b.ptr("members")))?;
                    m.exactly(&["name", "role", "size", "sha256", "source"])?;
                    out.push(PlanMember {
                        name: m.str("name")?.to_string(),
                        role: m.one_of("role", &MEMBER_ROLES)?.to_string(),
                        size: m.u64("size", NUM_MAX)?,
                        sha256: m.sha256("sha256")?.to_string(),
                        source: m.str("source")?.to_string(),
                    });
                }
                if out.first().map(|m| (m.name.as_str(), m.role.as_str()))
                    != Some((MANIFEST_MEMBER, "manifest"))
                {
                    return Err(b.invalid("members", "a plan's members begin with manifest.json"));
                }
                Some(out)
            }
        };
        Ok(DeliveryPlan {
            attempt,
            seal,
            manifest,
            manifest_sha256: b.sha256("manifest_sha256")?.to_string(),
            destination: PlanDestination {
                path: d.str("path")?.to_string(),
                source: d.one_of("source", &DESTINATION_SOURCES)?.to_string(),
                device: d.u64_or_null("device", u64::MAX)?,
                inode: d.u64_or_null("inode", u64::MAX)?,
            },
            package,
            replaces: b.u64_or_null("replaces", NUM_MAX)?,
            by: b.one_of("by", &RECORDERS)?.to_string(),
            members,
        })
    }
}

/// Read `delivery/<attempt>.json` and check it against the digest its
/// `delivery_planned` record binds.
pub fn load_plan(audit: &Audit, attempt: u64, want_sha256: &str) -> Result<DeliveryPlan, String> {
    let name = names::plan_name(attempt);
    let dir = audit
        .dir
        .open_dir("delivery")
        .map_err(|e| format!("delivery/ cannot be opened: {}", util::describe(&e)))?;
    let (bytes, _) = dir
        .read_regular(&format!("{attempt}.json"), RECORD_LIMIT)
        .map_err(|e| format!("{name}: {}", e.describe()))?;
    if util::sha256_hex(&bytes) != want_sha256 {
        return Err(format!(
            "{name} does not match the digest its delivery_planned record binds"
        ));
    }
    let r = decode_record(&bytes).map_err(|e| format!("{name}: {e}"))?;
    if r.kind != "delivery_plan" || r.audit.as_deref() != Some(audit.id.as_str()) {
        return Err(format!("{name} is not this audit's delivery plan"));
    }
    let p = DeliveryPlan::decode(&r.body(), &audit.id).map_err(|e| format!("{name}: {e}"))?;
    if p.attempt != attempt {
        return Err(format!("{name} names attempt {}", p.attempt));
    }
    Ok(p)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn manifest(unproduced: bool) -> Manifest {
        let h = |c: char| c.to_string().repeat(64);
        let mut members = vec![Member {
            name: ANSWER_MEMBER.into(),
            role: "answer".into(),
            size: 3904,
            sha256: h('1'),
        }];
        if !unproduced {
            members.push(Member {
                name: RENDERING_MEMBER.into(),
                role: "rendering".into(),
                size: 2210,
                sha256: h('2'),
            });
        }
        members.push(Member {
            name: "artifact-e4.bin".into(),
            role: "artifact".into(),
            size: 120,
            sha256: h('3'),
        });
        Manifest {
            audit: "aqm3x7kd2hz5vw4ny".into(),
            store: "s7tq2bk6xm3ra4pfe".into(),
            family: "open-inquiry/1".into(),
            renderer: "stewart.render/1".into(),
            writer: h('f'),
            actor: Actor::Auditor,
            sealed_at: "2026-11-02T15:20:04.118Z".into(),
            revision: 9,
            members,
            unproduced: if unproduced {
                vec![
                    Unproduced {
                        name: "e3".into(),
                        role: "entry".into(),
                        failure: "damaged".into(),
                        dependency: None,
                    },
                    Unproduced {
                        name: RENDERING_MEMBER.into(),
                        role: "rendering".into(),
                        failure: "not_rendered".into(),
                        dependency: Some(vec!["e3".into()]),
                    },
                ]
            } else {
                vec![]
            },
        }
    }

    #[test]
    fn manifests_have_the_pinned_layout() {
        let m = manifest(false);
        let b = m.bytes();
        let h = |c: char| c.to_string().repeat(64);
        assert_eq!(
            String::from_utf8(b.clone()).unwrap(),
            format!(
                "{{\"schema\":\"stewart.return/1\",\"audit\":\"aqm3x7kd2hz5vw4ny\",\"store\":\"s7tq2bk6xm3ra4pfe\",\"family\":\"open-inquiry/1\",\"renderer\":\"stewart.render/1\",\"writer\":\"{}\",\"seal\":{{\"actor\":\"auditor\",\"sealed_at\":\"2026-11-02T15:20:04.118Z\"}},\"revision\":9,\"members\":[{{\"name\":\"answer.json\",\"role\":\"answer\",\"size\":3904,\"sha256\":\"{}\"}},{{\"name\":\"answer.md\",\"role\":\"rendering\",\"size\":2210,\"sha256\":\"{}\"}},{{\"name\":\"artifact-e4.bin\",\"role\":\"artifact\",\"size\":120,\"sha256\":\"{}\"}}],\"unproduced\":[]}}\n",
                h('f'),
                h('1'),
                h('2'),
                h('3')
            )
        );
        assert_eq!(Manifest::decode(&b).unwrap(), m);
        let u = manifest(true);
        let ub = u.bytes();
        assert!(String::from_utf8_lossy(&ub).contains(r#""unproduced":[{"name":"e3","role":"entry","failure":"damaged","dependency":null},{"name":"answer.md","role":"rendering","failure":"not_rendered","dependency":["e3"]}]"#));
        assert_eq!(Manifest::decode(&ub).unwrap(), u);
        // Spacing, a missing LF, or answer.md listed while unproduced is refused.
        let spaced = String::from_utf8(b.clone()).unwrap().replacen(",", ", ", 1);
        assert!(Manifest::decode(spaced.as_bytes()).is_err());
        assert!(Manifest::decode(&b[..b.len() - 1]).is_err());
        let mut both = manifest(true);
        both.members = manifest(false).members;
        assert!(Manifest::decode(&both.bytes()).is_err());
    }

    #[test]
    fn delivery_plans_round_trip_and_name_their_attempt() {
        let audit = "aqm3x7kd2hz5vw4ny";
        let p = DeliveryPlan {
            attempt: 3,
            seal: "log/22.json".into(),
            manifest: "seal/manifest-1.json".into(),
            manifest_sha256: "a".repeat(64),
            destination: PlanDestination {
                path: "/home/ana/returns2".into(),
                source: "replacement".into(),
                device: Some(64769),
                inode: Some(1835011),
            },
            package: names::package_name(audit, 3),
            replaces: Some(2),
            by: "close".into(),
            members: Some(vec![PlanMember {
                name: MANIFEST_MEMBER.into(),
                role: "manifest".into(),
                size: 611,
                sha256: "b".repeat(64),
                source: "seal/manifest-1.json".into(),
            }]),
        };
        let text = p.to_j().string();
        assert!(text.starts_with(
            r#"{"attempt":3,"seal":"log/22.json","manifest":"seal/manifest-1.json","#
        ));
        let v = json::parse(text.as_bytes()).unwrap();
        assert_eq!(DeliveryPlan::decode(&v.obj("").unwrap(), audit).unwrap(), p);
        let unknown = DeliveryPlan {
            members: None,
            destination: PlanDestination {
                device: None,
                inode: None,
                ..p.destination.clone()
            },
            ..p.clone()
        };
        let v = json::parse(&unknown.to_j().bytes()).unwrap();
        assert_eq!(
            DeliveryPlan::decode(&v.obj("").unwrap(), audit).unwrap(),
            unknown
        );
    }
}
