//! Disposable prototype. See ../README.md and the root-owned process contract.
mod control;
mod safe;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::cell::Cell;
use std::collections::{BTreeMap, BTreeSet};
use std::io::{Read, Write};

const MEMBER_LIMIT: usize = 2 * 1024 * 1024;
const PAYLOAD_LIMIT: usize = 1024 * 1024;
type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Serialize)]
struct Error {
    ok: bool,
    reason: String,
    message: String,
    paths: Vec<String>,
    next_step: String,
    effect: String,
}
impl Error {
    fn new(
        reason: impl Into<String>,
        message: impl Into<String>,
        path: impl Into<String>,
        next: impl Into<String>,
    ) -> Self {
        let p = path.into();
        Self {
            ok: false,
            reason: reason.into(),
            message: message.into(),
            paths: if p.is_empty() { vec![] } else { vec![p] },
            next_step: next.into(),
            effect: "unchanged".into(),
        }
    }
}
fn err(reason: &str, message: impl Into<String>) -> Error {
    Error::new(
        reason,
        message,
        "",
        "Inspect the same store and request; preserve all retained evidence.",
    )
}
fn integrity(message: impl Into<String>, path: impl Into<String>) -> Error {
    let mut e = Error::new(
        "integrity_error",
        message,
        path,
        "Preserve the damaged record and payloads; do not reconstruct or overwrite history.",
    );
    e.effect = "uncertain".into();
    e
}
fn digest(b: &[u8]) -> String {
    format!("{:x}", Sha256::digest(b))
}
fn bytes<T: Serialize>(t: &T) -> Result<Vec<u8>> {
    serde_json::to_vec(t).map_err(|e| err("internal_error", e.to_string()))
}
fn random() -> String {
    let mut b = [0u8; 16];
    unsafe {
        libc::arc4random_buf(b.as_mut_ptr().cast(), b.len());
    }
    b.iter().map(|x| format!("{x:02x}")).collect()
}
fn sha(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}
fn short(s: &str) -> bool {
    !s.is_empty() && s.len() <= 512 && !s.chars().any(char::is_control)
}
fn request_name(id: &str) -> String {
    format!("request-{}.json", digest(id.as_bytes()))
}
fn cancel_name(id: &str) -> String {
    format!("cancel-{}.json", digest(id.as_bytes()))
}
fn stage(kind: &str) -> String {
    format!("stage-{}-{kind}", random())
}
fn commit_name(n: u64) -> String {
    format!("commit-{n:020}.json")
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Input {
    Init {
        audit: String,
        commission_sha256: String,
        request_id: String,
    },
    Add {
        request_id: String,
        name: String,
        source: String,
        size: u64,
        sha256: String,
    },
    Replace {
        request_id: String,
        handle: String,
        name: String,
        source: String,
        size: u64,
        sha256: String,
    },
    Delete {
        request_id: String,
        handle: String,
    },
    Inspect,
    Read {
        handle: String,
    },
    Prepare {
        request_id: String,
    },
    Submit {
        handle: String,
        #[serde(default)]
        submit: bool,
    },
    Resolve {
        request_id: String,
    },
    Resume {
        request_id: String,
    },
    Cancel {
        request_id: String,
        reason: String,
    },
}
impl Input {
    fn key(&self) -> Option<&str> {
        match self {
            Self::Init { request_id, .. }
            | Self::Add { request_id, .. }
            | Self::Replace { request_id, .. }
            | Self::Delete { request_id, .. }
            | Self::Prepare { request_id }
            | Self::Resolve { request_id }
            | Self::Resume { request_id }
            | Self::Cancel { request_id, .. } => Some(request_id),
            Self::Submit {
                handle,
                submit: true,
            } => Some(handle),
            _ => None,
        }
    }
    fn source(&self) -> Option<(&str, u64, &str)> {
        match self {
            Self::Add {
                source,
                size,
                sha256,
                ..
            }
            | Self::Replace {
                source,
                size,
                sha256,
                ..
            } => Some((source, *size, sha256)),
            _ => None,
        }
    }
    fn validate(&self) -> Result<()> {
        if self.key().is_some_and(|x| !short(x)) {
            return Err(err(
                "invalid_request",
                "request_id must be 1..512 printable UTF-8 bytes",
            ));
        }
        match self {
            Self::Init {
                audit,
                commission_sha256,
                ..
            } => {
                if !short(audit) || !sha(commission_sha256) {
                    return Err(err(
                        "invalid_request",
                        "audit and lowercase SHA-256 commission identity required",
                    ));
                }
            }
            Self::Add {
                name,
                size,
                sha256,
                source,
                ..
            }
            | Self::Replace {
                name,
                size,
                sha256,
                source,
                ..
            } => {
                if name.len() > 512 || source.len() > 8192 || !sha(sha256) {
                    return Err(err(
                        "invalid_request",
                        "name/source bounds or lowercase SHA-256 identity invalid",
                    ));
                }
                if *size > PAYLOAD_LIMIT as u64 {
                    return Err(err("limit_exceeded", "Element exceeds 1 MiB test bound"));
                }
            }
            Self::Cancel { reason, .. } => {
                if !short(reason) {
                    return Err(err(
                        "invalid_request",
                        "Cancellation requires a bounded nonempty reason",
                    ));
                }
            }
            _ => (),
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Element {
    id: String,
    version: u64,
    handle: String,
    name: String,
    size: u64,
    sha256: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct State {
    audit: String,
    instance: String,
    revision: u64,
    elements: Vec<Element>,
    submitted: bool,
    submission_handle: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Manifest {
    audit: String,
    instance: String,
    revision: u64,
    commission_sha256: String,
    elements: Vec<Element>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Ref {
    name: String,
    sha256: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Blob {
    name: String,
    element: Element,
    source: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Preparation {
    handle: String,
    manifest: Manifest,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Plan {
    schema: String,
    writer_sha256: String,
    request_id: String,
    intent: Input,
    base: Option<Ref>,
    commission_sha256: String,
    candidate: State,
    commit_name: Option<String>,
    outcome_name: String,
    blob: Option<Blob>,
    preparation: Option<Preparation>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Commit {
    schema: String,
    sequence: u64,
    previous: Option<Ref>,
    request: Ref,
    state: State,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct Issuance {
    schema: String,
    request: Ref,
    preparation: Preparation,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Attempt {
    schema: String,
    request: Ref,
    blob_stage: Option<String>,
    record_stage: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Cancellation {
    schema: String,
    request: Ref,
    attribution: String,
    reason: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Outcome {
    schema: String,
    request: Ref,
    publication: Ref,
    result: Value,
}
struct History {
    writer: String,
    tip: Option<Ref>,
    state: Option<State>,
    commission: String,
    commits: Vec<(Commit, Plan)>,
    blobs: BTreeMap<String, Blob>,
}
struct Store {
    dir: safe::Dir,
    writer: String,
    effect: Cell<&'static str>,
}
impl Store {
    fn record<T: serde::de::DeserializeOwned>(&self, name: &str, schema: &str) -> Result<T> {
        let raw = self.dir.read(name, MEMBER_LIMIT).map_err(|e| {
            integrity(
                format!("{}: {}", e.reason, e.message),
                format!("{}/{name}", self.dir.label),
            )
        })?;
        control::parse(&raw, schema, name)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), name))
    }
    fn plan(&self, id: &str) -> Result<(Plan, Ref)> {
        let name = request_name(id);
        if !self.dir.exists(&name)? {
            return Err(err(
                "unknown_request",
                "No published binding exists for this request ID",
            ));
        }
        let raw = self
            .dir
            .read(&name, MEMBER_LIMIT)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
        let p: Plan = control::parse(&raw, "prototype-request-v1", &name)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
        if p.request_id != id || p.intent.key() != Some(id) {
            return Err(integrity(
                "Request identity differs from its filename or intent",
                &name,
            ));
        }
        p.intent
            .validate()
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
        Ok((
            p,
            Ref {
                name,
                sha256: digest(&raw),
            },
        ))
    }
    fn receipt<T: Serialize>(&self, name: &str, t: &T) -> Result<()> {
        if self.effect.get() == "unchanged" {
            self.effect.set("partial");
        }
        self.dir.write_receipt(name, &stage("receipt"), &bytes(t)?)
    }
    fn state<'a>(&self, h: &'a History) -> Result<&'a State> {
        h.state.as_ref().ok_or_else(|| {
            err(
                "not_initialized",
                "Initialize this explicit empty store first",
            )
        })
    }
    fn history(&self) -> Result<History> {
        let mut h = History {
            writer: String::new(),
            tip: None,
            state: None,
            commission: String::new(),
            commits: vec![],
            blobs: BTreeMap::new(),
        };
        let names = self.dir.names()?;
        let cs: Vec<_> = names.iter().filter(|n| n.starts_with("commit-")).collect();
        for (i, name) in cs.iter().enumerate() {
            if **name != commit_name(i as u64) {
                return Err(integrity("Commit chain has a gap or invalid name", *name));
            }
            let raw = self
                .dir
                .read(name, MEMBER_LIMIT)
                .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), *name))?;
            let c: Commit = control::parse(&raw, "prototype-commit-v1", name)
                .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), *name))?;
            let p: Plan = self.record(&c.request.name, "prototype-request-v1")?;
            let (verified, r) = self.plan(&p.request_id)?;
            if p != verified
                || c.request != r
                || c.sequence != i as u64
                || c.previous != h.tip
                || p.base != h.tip
                || p.commit_name.as_ref() != Some(*name)
                || c.state != p.candidate
            {
                return Err(integrity(
                    "Commit/request/predecessor binding differs",
                    *name,
                ));
            }
            self.validate_plan(&p, &h)?;
            let expected = Commit {
                schema: "prototype-commit-v1".into(),
                sequence: i as u64,
                previous: h.tip.clone(),
                request: r,
                state: p.candidate.clone(),
            };
            if c != expected {
                return Err(integrity("Commit differs from planned exact state", *name));
            }
            if self.dir.exists(&cancel_name(&p.request_id))? {
                return Err(integrity("Committed request also has cancellation", *name));
            }
            if let Some(b) = &p.blob {
                h.blobs.insert(b.element.handle.clone(), b.clone());
            }
            h.writer = p.writer_sha256.clone();
            h.commission = p.commission_sha256.clone();
            h.state = Some(c.state.clone());
            h.tip = Some(Ref {
                name: (*name).clone(),
                sha256: digest(&raw),
            });
            h.commits.push((c, p));
        }
        if let Some(s) = &h.state {
            self.verify_elements(s, &h)?;
        }
        // Only state-changing outcomes are chain dependencies. An unused issuance
        // does not make healthy selected bytes or unrelated edits depend on it.
        for n in names
            .iter()
            .filter(|n| n.starts_with("state-outcome-") && n.ends_with(".json"))
        {
            let o: Outcome = self.record(n, "prototype-outcome-v1")?;
            let p: Plan = self.record(&o.request.name, "prototype-request-v1")?;
            let (_, r) = self.plan(&p.request_id)?;
            if p.commit_name.is_none() || p.outcome_name != *n || o.request != r {
                return Err(integrity(
                    "State outcome differs from its planned state-changing request",
                    n,
                ));
            }
            self.validate_bound_plan(&p, &h)?;
            self.validate_outcome(&p, &r)?;
        }
        Ok(h)
    }
    fn validate_bound_plan(&self, p: &Plan, h: &History) -> Result<()> {
        let mut prefix = History {
            writer: String::new(),
            tip: None,
            state: None,
            commission: String::new(),
            commits: vec![],
            blobs: BTreeMap::new(),
        };
        if let Some(base) = &p.base {
            let mut found = false;
            for (i, (c, prior)) in h.commits.iter().enumerate() {
                let name = commit_name(i as u64);
                let raw = self
                    .dir
                    .read(&name, MEMBER_LIMIT)
                    .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
                prefix.tip = Some(Ref {
                    name,
                    sha256: digest(&raw),
                });
                prefix.state = Some(c.state.clone());
                prefix.commission = prior.commission_sha256.clone();
                prefix.writer = prior.writer_sha256.clone();
                if let Some(b) = &prior.blob {
                    prefix.blobs.insert(b.element.handle.clone(), b.clone());
                }
                prefix.commits.push((c.clone(), prior.clone()));
                if prefix.tip.as_ref() == Some(base) {
                    found = true;
                    break;
                }
            }
            if !found {
                return Err(integrity(
                    "Request predecessor is missing or differs from the verified chain",
                    request_name(&p.request_id),
                ));
            }
        }
        self.validate_plan(p, &prefix)
    }
    fn verify_elements(&self, s: &State, h: &History) -> Result<()> {
        let mut ids = BTreeSet::new();
        let mut size = 0;
        for e in &s.elements {
            if !ids.insert(&e.id)
                || e.version == 0
                || e.handle != format!("e-{}-{}-{}", s.instance, e.id, e.version)
                || !sha(&e.sha256)
                || e.size > PAYLOAD_LIMIT as u64
            {
                return Err(integrity(
                    "Invalid element identity, version or bounds",
                    &e.handle,
                ));
            }
            let b = h.blobs.get(&e.handle).ok_or_else(|| {
                integrity(
                    "Selected element has no committed payload binding",
                    &e.handle,
                )
            })?;
            if b.element != *e {
                return Err(integrity(
                    "Payload metadata differs from selected descriptor",
                    &e.handle,
                ));
            }
            self.payload(b)?;
            size += e.size;
        }
        if s.elements.len() > 32 || size > 8 * 1024 * 1024 {
            return Err(integrity(
                "Recorded active selection exceeds test bounds",
                &self.dir.label,
            ));
        }
        Ok(())
    }
    fn payload(&self, b: &Blob) -> Result<Vec<u8>> {
        let raw = self
            .dir
            .read(&b.name, PAYLOAD_LIMIT)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &b.name))?;
        if raw.len() as u64 != b.element.size || digest(&raw) != b.element.sha256 {
            return Err(integrity(
                "Held payload differs from its recorded exact identity",
                &b.name,
            ));
        }
        Ok(raw)
    }
    fn validate_plan(&self, p: &Plan, h: &History) -> Result<()> {
        let expected_outcome = if matches!(p.intent, Input::Prepare { .. }) {
            p.preparation
                .as_ref()
                .map(|x| format!("prepare-outcome-{}.json", x.handle))
                .ok_or_else(|| {
                    integrity(
                        "Preparation lacks planned issuance",
                        request_name(&p.request_id),
                    )
                })?
        } else {
            format!("state-outcome-{}.json", digest(p.request_id.as_bytes()))
        };
        if p.outcome_name != expected_outcome {
            return Err(integrity(
                "Outcome name differs from planned request identity",
                request_name(&p.request_id),
            ));
        }
        if p.base != h.tip || p.intent.key() != Some(p.request_id.as_str()) {
            return Err(integrity(
                "Plan base or request identity mismatch",
                request_name(&p.request_id),
            ));
        }
        if !sha(&p.writer_sha256) || (!h.writer.is_empty() && p.writer_sha256 != h.writer) {
            return Err(integrity(
                "Request writer differs from initial binary identity",
                request_name(&p.request_id),
            ));
        }
        if !sha(&p.commission_sha256) {
            return Err(integrity(
                "Invalid planned commission identity",
                request_name(&p.request_id),
            ));
        }
        let old = h.state.as_ref();
        let s = &p.candidate;
        match &p.intent {
            Input::Init {
                audit,
                commission_sha256,
                ..
            } => {
                if old.is_some()
                    || s.audit != *audit
                    || p.commission_sha256 != *commission_sha256
                    || s.instance.len() != 32
                    || !s.instance.bytes().all(|c| c.is_ascii_hexdigit())
                    || s.revision != 0
                    || !s.elements.is_empty()
                    || s.submitted
                    || s.submission_handle.is_some()
                    || p.blob.is_some()
                    || p.preparation.is_some()
                {
                    return Err(integrity("Invalid init plan", request_name(&p.request_id)));
                }
            }
            Input::Add { .. } | Input::Replace { .. } | Input::Delete { .. } => {
                let old =
                    old.ok_or_else(|| integrity("Edit without init", request_name(&p.request_id)))?;
                if old.submitted
                    || s.audit != old.audit
                    || s.instance != old.instance
                    || p.commission_sha256 != h.commission
                    || s.revision != old.revision + 1
                    || s.submitted
                    || s.submission_handle.is_some()
                    || p.preparation.is_some()
                {
                    return Err(integrity(
                        "Edit plan violates state transition",
                        request_name(&p.request_id),
                    ));
                }
                let mut expected = old.elements.clone();
                match &p.intent {
                    Input::Add {
                        name,
                        source,
                        size,
                        sha256,
                        ..
                    }
                    | Input::Replace {
                        name,
                        source,
                        size,
                        sha256,
                        ..
                    } => {
                        let b = p.blob.as_ref().ok_or_else(|| {
                            integrity("Edit lacks payload plan", request_name(&p.request_id))
                        })?;
                        if b.source != *source
                            || b.element.name != *name
                            || b.element.size != *size
                            || b.element.sha256 != *sha256
                            || !b.name.starts_with("blob-")
                            || !b.name.ends_with(".bin")
                        {
                            return Err(integrity("Payload plan differs from intent", &b.name));
                        }
                        if let Input::Replace { handle, .. } = &p.intent {
                            let i = expected
                                .iter()
                                .position(|e| e.handle == *handle)
                                .ok_or_else(|| {
                                    integrity("Replacement lacks current element", handle)
                                })?;
                            if b.element.id != expected[i].id
                                || b.element.version != expected[i].version + 1
                            {
                                return Err(integrity(
                                    "Replacement identity/version mismatch",
                                    handle,
                                ));
                            }
                            expected[i] = b.element.clone();
                        } else {
                            if b.element.version != 1
                                || expected.iter().any(|e| e.id == b.element.id)
                            {
                                return Err(integrity(
                                    "Addition identity/version mismatch",
                                    &b.name,
                                ));
                            }
                            expected.push(b.element.clone());
                        }
                    }
                    Input::Delete { handle, .. } => {
                        let i = expected
                            .iter()
                            .position(|e| e.handle == *handle)
                            .ok_or_else(|| integrity("Delete lacks current element", handle))?;
                        expected.remove(i);
                        if p.blob.is_some() {
                            return Err(integrity("Delete has unrelated payload", handle));
                        }
                    }
                    _ => unreachable!(),
                }
                if s.elements != expected {
                    return Err(integrity(
                        "Candidate selection differs from exact edit",
                        request_name(&p.request_id),
                    ));
                }
            }
            Input::Submit {
                handle,
                submit: true,
            } => {
                let old = old.ok_or_else(|| integrity("Submit without init", handle))?;
                let mut expected = old.clone();
                expected.submitted = true;
                expected.submission_handle = Some(handle.clone());
                if old.submitted
                    || s != &expected
                    || p.commission_sha256 != h.commission
                    || p.blob.is_some()
                    || p.preparation.is_some()
                {
                    return Err(integrity("Submit transition differs", handle));
                }
                self.issuance(handle, h, true)?;
            }
            Input::Prepare { .. } => {
                let old = old.ok_or_else(|| {
                    integrity("Prepare without init", request_name(&p.request_id))
                })?;
                let prep = p.preparation.as_ref().ok_or_else(|| {
                    integrity("Missing planned preparation", request_name(&p.request_id))
                })?;
                if old != s
                    || p.commit_name.is_some()
                    || p.blob.is_some()
                    || p.commission_sha256 != h.commission
                    || prep.manifest != manifest(s, &h.commission)
                    || !prep.handle.starts_with(&format!("p-{}-", s.instance))
                {
                    return Err(integrity(
                        "Preparation plan differs from selection",
                        &prep.handle,
                    ));
                }
            }
            _ => {
                return Err(integrity(
                    "Unsupported operation in request binding",
                    request_name(&p.request_id),
                ));
            }
        }
        if !matches!(p.intent, Input::Prepare { .. })
            && p.commit_name != Some(commit_name(h.commits.len() as u64))
        {
            return Err(integrity(
                "Planned commit name differs from chain position",
                request_name(&p.request_id),
            ));
        }
        if s.elements.len() > 32 || s.elements.iter().map(|e| e.size).sum::<u64>() > 8 * 1024 * 1024
        {
            return Err(integrity(
                "Planned selection exceeds test bounds",
                request_name(&p.request_id),
            ));
        }
        Ok(())
    }
    fn issuance(&self, handle: &str, h: &History, check_current: bool) -> Result<Preparation> {
        let s = self.state(h)?;
        if handle.len() > 128
            || !handle
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || c == b'-')
            || !handle.starts_with(&format!("p-{}-", s.instance))
        {
            return Err(err(
                "invalid_handle",
                "Preparation handle was not issued for this store lifetime",
            ));
        }
        // A handle directly locates its own acknowledgement, including when its
        // issuance was lost. No unrelated preparation records need to be scanned.
        let own_outcome = format!("prepare-outcome-{handle}.json");
        if self.dir.exists(&own_outcome)? {
            let o: Outcome = self.record(&own_outcome, "prototype-outcome-v1")?;
            let p: Plan = self.record(&o.request.name, "prototype-request-v1")?;
            let (_, r) = self.plan(&p.request_id)?;
            if o.request != r
                || p.outcome_name != own_outcome
                || p.preparation.as_ref().map(|x| x.handle.as_str()) != Some(handle)
            {
                return Err(integrity(
                    "Preparation outcome differs from its issued handle",
                    own_outcome,
                ));
            }
            self.validate_bound_plan(&p, h)?;
            self.validate_outcome(&p, &r)?;
        }
        let name = format!("prepare-{handle}.json");
        if !self.dir.exists(&name)? {
            return Err(err(
                "invalid_handle",
                "No issued preparation exists for this handle",
            ));
        }
        let issue: Issuance = self.record(&name, "prototype-issuance-v1")?;
        let raw = self
            .dir
            .read(&issue.request.name, MEMBER_LIMIT)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &issue.request.name))?;
        if digest(&raw) != issue.request.sha256 {
            return Err(integrity("Preparation request digest mismatch", &name));
        }
        let p: Plan = control::parse(&raw, "prototype-request-v1", &issue.request.name)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
        let (_, r) = self.plan(&p.request_id)?;
        if r != issue.request
            || !matches!(p.intent, Input::Prepare { .. })
            || p.preparation.as_ref() != Some(&issue.preparation)
            || issue.preparation.handle != handle
            || p.commission_sha256 != h.commission
        {
            return Err(integrity("Issuance differs from bound preparation", &name));
        }
        self.validate_bound_plan(&p, h)?;
        self.validate_outcome(&p, &r)?;
        let m = &issue.preparation.manifest;
        if m.audit != s.audit || m.instance != s.instance || m.commission_sha256 != h.commission {
            return Err(integrity(
                "Issuance has incompatible audit/commission",
                &name,
            ));
        }
        if check_current && *m != manifest(s, &h.commission) {
            return Err(err(
                "stale_preparation",
                "An edit changed the issued selection; inspect and prepare again",
            ));
        }
        Ok(issue.preparation)
    }
    fn check_handle<'a>(&self, handle: &str, h: &'a History) -> Result<&'a Element> {
        if let Some(e) = self.state(h)?.elements.iter().find(|e| e.handle == handle) {
            return Ok(e);
        }
        if h.blobs.contains_key(handle) {
            Err(err(
                "stale_handle",
                "Element version is no longer selected; inspect current elements",
            ))
        } else {
            Err(err(
                "invalid_handle",
                "Handle was not issued for an element in this store lifetime",
            ))
        }
    }
    fn cancellation(&self, p: &Plan, r: &Ref) -> Result<Option<Cancellation>> {
        let name = cancel_name(&p.request_id);
        if !self.dir.exists(&name)? {
            return Ok(None);
        }
        let c: Cancellation = self.record(&name, "prototype-cancel-v1")?;
        if c.request != *r || c.attribution != "caller" || !short(&c.reason) {
            return Err(integrity("Cancellation binding invalid", name));
        }
        Ok(Some(c))
    }
    fn outcome(&self, p: &Plan) -> Value {
        let mut v = json!({"ok":true,"request_id":p.request_id,"state":p.candidate});
        if let Some(b) = &p.blob {
            v["element"] = json!(b.element);
        }
        if let Some(pr) = &p.preparation {
            v["handle"] = json!(pr.handle);
            v["manifest"] = json!(pr.manifest);
        }
        if let Input::Submit { handle, .. } = &p.intent {
            v["handle"] = json!(handle);
            v["dry_run"] = json!(false);
        }
        v
    }
    /// Verify a requested undertaking's completion evidence, without extending
    /// that dependency to unrelated preparation records.
    fn validate_outcome(&self, p: &Plan, r: &Ref) -> Result<bool> {
        if !self.dir.exists(&p.outcome_name)? {
            return Ok(false);
        }
        let o: Outcome = self.record(&p.outcome_name, "prototype-outcome-v1")?;
        if o.request != *r || o.result != self.outcome(p) {
            return Err(integrity(
                "Outcome differs from its recorded request",
                &p.outcome_name,
            ));
        }
        let target = p
            .commit_name
            .clone()
            .or_else(|| {
                p.preparation
                    .as_ref()
                    .map(|x| format!("prepare-{}.json", x.handle))
            })
            .ok_or_else(|| integrity("Outcome has no planned publication", &p.outcome_name))?;
        if target != o.publication.name {
            return Err(integrity(
                "Outcome publication differs from planned identity",
                &p.outcome_name,
            ));
        }
        let published = self
            .dir
            .read(&target, MEMBER_LIMIT)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &target))?;
        if digest(&published) != o.publication.sha256 {
            return Err(integrity(
                "Acknowledged publication differs from retained outcome",
                &target,
            ));
        }
        Ok(true)
    }
    fn committed(&self, p: &Plan, r: &Ref, h: &History) -> Result<bool> {
        self.validate_outcome(p, r)?;
        if let Some(name) = &p.commit_name {
            if !self.dir.exists(name)? {
                return Ok(false);
            }
            // The same sequence can have been taken by another request after interruption.
            let c: Commit = self.record(name, "prototype-commit-v1")?;
            if c.request != *r {
                return Ok(false);
            }
            if !h.commits.iter().any(|(x, y)| x.request == *r && y == p) {
                return Err(integrity(
                    "Planned committed outcome is not verified in chain",
                    name,
                ));
            }
            self.verify_elements(&p.candidate, h)?;
            Ok(true)
        } else if let Some(prep) = &p.preparation {
            let name = format!("prepare-{}.json", prep.handle);
            if !self.dir.exists(&name)? {
                return Ok(false);
            }
            let issued = self.issuance(&prep.handle, h, false)?;
            if issued != *prep {
                return Err(integrity("Issued preparation differs from outcome", name));
            }
            self.verify_elements(&p.candidate, h)?;
            Ok(true)
        } else {
            Err(integrity("Request has no planned result", &r.name))
        }
    }
    fn attempts(&self, r: &Ref) -> Result<Vec<Attempt>> {
        let request_digest = r
            .name
            .strip_prefix("request-")
            .and_then(|n| n.strip_suffix(".json"))
            .ok_or_else(|| integrity("Invalid request filename for attempt lookup", &r.name))?;
        let prefix = format!("attempt-{request_digest}-");
        let mut out = vec![];
        // A filename scopes recovery to this undertaking before any record is decoded.
        // Selected records must still bind its exact request bytes, not merely its key.
        for n in self
            .dir
            .names()?
            .iter()
            .filter(|n| n.starts_with(&prefix) && n.ends_with(".json"))
        {
            let a: Attempt = self.record(n, "prototype-attempt-v1")?;
            if a.request != *r {
                return Err(integrity(
                    "Attempt filename and stored request binding differ",
                    n,
                ));
            }
            out.push(a);
        }
        Ok(out)
    }
    fn source_bytes(&self, p: &Plan) -> Result<Vec<u8>> {
        let (source, size, hash) = p
            .intent
            .source()
            .ok_or_else(|| err("internal_error", "No source in request"))?;
        let b = safe::read_absolute(source, PAYLOAD_LIMIT)?;
        if b.len() as u64 != size || digest(&b) != hash {
            return Err(Error::new(
                "source_mismatch",
                "Source bytes differ from the requested size/SHA-256",
                source,
                "Supply the original exact bytes for resume, or cancel this pending request.",
            ));
        }
        Ok(b)
    }
    fn finish(&self, p: &Plan, r: &Ref) -> Result<Value> {
        let name = p
            .commit_name
            .clone()
            .or_else(|| {
                p.preparation
                    .as_ref()
                    .map(|x| format!("prepare-{}.json", x.handle))
            })
            .ok_or_else(|| integrity("No planned publication", &r.name))?;
        let raw = self
            .dir
            .read(&name, MEMBER_LIMIT)
            .map_err(|e| integrity(format!("{}: {}", e.reason, e.message), &name))?;
        let outcome = Outcome {
            schema: "prototype-outcome-v1".into(),
            request: r.clone(),
            publication: Ref {
                name,
                sha256: digest(&raw),
            },
            result: self.outcome(p),
        };
        if self.dir.exists(&p.outcome_name)? {
            let existing: Outcome = self.record(&p.outcome_name, "prototype-outcome-v1")?;
            if existing.request != outcome.request
                || existing.publication != outcome.publication
                || existing.result != outcome.result
            {
                return Err(integrity(
                    "Existing outcome differs from the same request",
                    &p.outcome_name,
                ));
            }
        } else {
            self.receipt(&p.outcome_name, &outcome)?;
        }
        self.dir.ensure_location()?;
        Ok(outcome.result)
    }
    fn complete(&self, p: &Plan, r: &Ref, h: &History, source: Option<Vec<u8>>) -> Result<Value> {
        if p.writer_sha256 != self.writer {
            return Err(err(
                "writer_mismatch",
                "Resume requires the exact request writer binary",
            ));
        }
        self.validate_bound_plan(p, h)?;
        if self.committed(p, r, h)? {
            self.effect.set("uncertain");
            return self.finish(p, r);
        }
        if self.cancellation(p, r)?.is_some() {
            return Err(err(
                "request_cancelled",
                "This request has an attributed cancellation; use a new request ID for new intent",
            ));
        }
        if p.base != h.tip {
            return Err(err(
                "stale_request",
                "Another commit superseded this request's pinned predecessor; cancel this request",
            ));
        }
        self.validate_plan(p, h)?;
        self.effect.set("partial");
        let attempt = Attempt {
            schema: "prototype-attempt-v1".into(),
            request: r.clone(),
            blob_stage: p.blob.as_ref().map(|_| stage("blob")),
            record_stage: stage("record"),
        };
        let prior = self.attempts(r)?;
        self.receipt(
            &format!(
                "attempt-{}-{}.json",
                digest(p.request_id.as_bytes()),
                random()
            ),
            &attempt,
        )?;
        if let Some(b) = &p.blob {
            if self.dir.exists(&b.name)? {
                self.payload(b)?;
            } else {
                let mut held = None;
                for a in &prior {
                    if let Some(n) = &a.blob_stage {
                        if self.dir.exists(n)? {
                            // Only complete exact planned stages may be adopted. Partial stages remain.
                            match self.dir.read(n, PAYLOAD_LIMIT) {
                                Ok(raw)
                                    if raw.len() as u64 == b.element.size
                                        && digest(&raw) == b.element.sha256 =>
                                {
                                    held = Some(raw);
                                    break;
                                }
                                Ok(_) => (),
                                Err(e) if e.reason == "limit_exceeded" => (),
                                Err(e) => {
                                    return Err(integrity(
                                        format!("{}: {}", e.reason, e.message),
                                        n,
                                    ));
                                }
                            }
                        }
                    }
                }
                let raw = match held.or(source) {
                    Some(x) => x,
                    None => self.source_bytes(p)?,
                };
                let sn = attempt.blob_stage.as_ref().unwrap();
                self.dir.write_exclusive(sn, &raw)?;
                self.dir.publish_unsynced(&b.name, sn, &raw)?;
                self.dir.sync()?;
                self.payload(b)?;
            }
        }
        if let Some(prep) = &p.preparation {
            let issue = Issuance {
                schema: "prototype-issuance-v1".into(),
                request: r.clone(),
                preparation: prep.clone(),
            };
            let raw = bytes(&issue)?;
            self.dir.write_exclusive(&attempt.record_stage, &raw)?;
            self.dir.publish_unsynced(
                &format!("prepare-{}.json", prep.handle),
                &attempt.record_stage,
                &raw,
            )?;
            self.dir.sync()?;
            self.dir.ensure_location()?;
            return self.finish(p, r);
        }
        hook(
            "after_stage",
            &p.request_id,
            p.commit_name.as_ref().unwrap(),
        )?;
        let c = Commit {
            schema: "prototype-commit-v1".into(),
            sequence: h.commits.len() as u64,
            previous: h.tip.clone(),
            request: r.clone(),
            state: p.candidate.clone(),
        };
        let raw = bytes(&c)?;
        let name = p.commit_name.as_ref().unwrap();
        // Reverify candidate payloads immediately before complete commit publication.
        let mut candidate_blobs = h.blobs.clone();
        if let Some(b) = &p.blob {
            candidate_blobs.insert(b.element.handle.clone(), b.clone());
        }
        let candidate_h = History {
            writer: h.writer.clone(),
            tip: h.tip.clone(),
            state: Some(p.candidate.clone()),
            commission: h.commission.clone(),
            commits: vec![],
            blobs: candidate_blobs,
        };
        self.verify_elements(&p.candidate, &candidate_h)?;
        self.dir.write_exclusive(&attempt.record_stage, &raw)?;
        hook("before_publish", &p.request_id, name)?;
        self.dir.ensure_location()?;
        self.effect.set("uncertain");
        self.dir
            .publish_unsynced(name, &attempt.record_stage, &raw)?;
        hook("after_publish", &p.request_id, name)?;
        self.dir.sync()?;
        hook("after_sync", &p.request_id, name)?;
        self.dir.ensure_location()?;
        self.finish(p, r)
    }
    fn new_plan(&self, input: Input, h: &History) -> Result<(Plan, Option<Vec<u8>>)> {
        let id = input.key().unwrap().to_owned();
        let mut source = None;
        let mut s = match &input {
            Input::Init { audit, .. } => {
                if !self.dir.names()?.is_empty() {
                    return Err(err(
                        "store_not_empty",
                        "Init requires an empty ordinary directory; resolve a recorded init instead",
                    ));
                }
                State {
                    audit: audit.clone(),
                    instance: random(),
                    revision: 0,
                    elements: vec![],
                    submitted: false,
                    submission_handle: None,
                }
            }
            _ => self.state(h)?.clone(),
        };
        let commission = match &input {
            Input::Init {
                commission_sha256, ..
            } => commission_sha256.clone(),
            _ => h.commission.clone(),
        };
        let mut blob = None;
        let mut prep = None;
        match &input {
            Input::Init { .. } => (),
            Input::Add {
                name,
                source: path,
                size,
                sha256,
                ..
            }
            | Input::Replace {
                name,
                source: path,
                size,
                sha256,
                ..
            } => {
                if s.submitted {
                    return Err(err(
                        "already_submitted",
                        format!(
                            "Editing ended at {}",
                            s.submission_handle.as_deref().unwrap_or("unknown")
                        ),
                    ));
                }
                let (eid, version, index) = if let Input::Replace { handle, .. } = &input {
                    let e = self.check_handle(handle, h)?;
                    (
                        e.id.clone(),
                        e.version + 1,
                        s.elements.iter().position(|x| x.handle == *handle),
                    )
                } else {
                    (random(), 1, None)
                };
                let e = Element {
                    id: eid.clone(),
                    version,
                    handle: format!("e-{}-{eid}-{version}", s.instance),
                    name: name.clone(),
                    size: *size,
                    sha256: sha256.clone(),
                };
                if let Some(i) = index {
                    s.elements[i] = e.clone();
                } else {
                    s.elements.push(e.clone());
                }
                if s.elements.len() > 32
                    || s.elements.iter().map(|e| e.size).sum::<u64>() > 8 * 1024 * 1024
                {
                    return Err(err(
                        "limit_exceeded",
                        "Active selection exceeds 32 elements or 8 MiB",
                    ));
                }
                s.revision += 1;
                blob = Some(Blob {
                    name: format!("blob-{}.bin", random()),
                    element: e,
                    source: path.clone(),
                });
            }
            Input::Delete { handle, .. } => {
                if s.submitted {
                    return Err(err(
                        "already_submitted",
                        format!(
                            "Editing ended at {}",
                            s.submission_handle.as_deref().unwrap_or("unknown")
                        ),
                    ));
                }
                self.check_handle(handle, h)?;
                s.elements.retain(|e| e.handle != *handle);
                s.revision += 1;
            }
            Input::Prepare { .. } => {
                if s.submitted {
                    return Err(err("already_submitted", "Selection already submitted"));
                }
                prep = Some(Preparation {
                    handle: format!("p-{}-{}", s.instance, random()),
                    manifest: manifest(&s, &commission),
                });
            }
            Input::Submit {
                handle,
                submit: true,
            } => {
                if s.submitted {
                    return Err(err(
                        "already_submitted",
                        format!(
                            "Selection already submitted with {}",
                            s.submission_handle.as_deref().unwrap_or("unknown")
                        ),
                    ));
                }
                self.issuance(handle, h, true)?;
                s.submitted = true;
                s.submission_handle = Some(handle.clone());
            }
            _ => {
                return Err(err(
                    "invalid_request",
                    "Operation cannot create a request plan",
                ));
            }
        }
        let p = Plan {
            schema: "prototype-request-v1".into(),
            writer_sha256: self.writer.clone(),
            request_id: id.clone(),
            intent: input,
            base: h.tip.clone(),
            commission_sha256: commission,
            candidate: s,
            outcome_name: if let Some(pr) = &prep {
                format!("prepare-outcome-{}.json", pr.handle)
            } else {
                format!("state-outcome-{}.json", digest(id.as_bytes()))
            },
            commit_name: if prep.is_some() {
                None
            } else {
                Some(commit_name(h.commits.len() as u64))
            },
            blob,
            preparation: prep,
        };
        if p.blob.is_some() {
            source = Some(self.source_bytes(&p)?);
        }
        self.validate_plan(&p, h)?;
        Ok((p, source))
    }
    fn execute(&self, input: Input) -> Result<Value> {
        input.validate()?;
        let h = self.history()?;
        let mutates = !matches!(
            input,
            Input::Inspect
                | Input::Read { .. }
                | Input::Resolve { .. }
                | Input::Submit { submit: false, .. }
        );
        if mutates && !h.writer.is_empty() && h.writer != self.writer {
            return Err(err(
                "writer_mismatch",
                "Mutation requires the exact creating binary; preserve this store and use its recorded writer",
            ));
        }
        match &input {
            Input::Inspect => Ok(json!({"ok":true,"state":self.state(&h)?})),
            Input::Read { handle } => {
                let e = self.check_handle(handle, &h)?;
                let b = h.blobs.get(handle).unwrap();
                let raw = self.payload(b)?;
                let hex: String = raw.iter().map(|x| format!("{x:02x}")).collect();
                Ok(json!({"ok":true,"element":e,"bytes_hex":hex}))
            }
            Input::Submit {
                handle,
                submit: false,
            } => {
                let s = self.state(&h)?;
                if s.submitted {
                    return Err(err(
                        "already_submitted",
                        format!(
                            "Selection already submitted with {}",
                            s.submission_handle.as_deref().unwrap_or("unknown")
                        ),
                    ));
                }
                self.issuance(handle, &h, true)?;
                Ok(json!({"ok":true,"dry_run":true,"would_submit":true,"state":s}))
            }
            Input::Resolve { request_id } => {
                let (p, r) = self.plan(request_id)?;
                self.validate_bound_plan(&p, &h)?;
                let done = self.committed(&p, &r, &h)?;
                let c = self.cancellation(&p, &r)?;
                if done && c.is_some() {
                    return Err(integrity("Request is both committed and cancelled", r.name));
                }
                Ok(
                    json!({"ok":true,"request_id":request_id,"status":if done{"committed"}else if c.is_some(){"cancelled"}else{"pending"},"operation":p.intent,"outcome":if done{self.outcome(&p)}else{Value::Null},"cancellation":c.map(|x|json!({"attribution":x.attribution,"reason":x.reason}))}),
                )
            }
            Input::Resume { request_id } => {
                let (p, r) = self.plan(request_id)?;
                self.complete(&p, &r, &h, None)
            }
            Input::Cancel { request_id, reason } => {
                let (p, r) = self.plan(request_id)?;
                self.validate_bound_plan(&p, &h)?;
                if self.committed(&p, &r, &h)? {
                    return Err(err(
                        "already_committed",
                        "Committed operation cannot be cancelled; resolve its fixed outcome",
                    ));
                }
                if let Some(c) = self.cancellation(&p, &r)? {
                    if c.reason != *reason {
                        return Err(err(
                            "request_conflict",
                            "Cancellation already records a different caller reason",
                        ));
                    }
                } else {
                    // A damaged planned payload or existing own result cannot be hidden by cancellation.
                    if let Some(b) = &p.blob {
                        if self.dir.exists(&b.name)? {
                            self.payload(b)?;
                        }
                    }
                    self.receipt(
                        &cancel_name(request_id),
                        &Cancellation {
                            schema: "prototype-cancel-v1".into(),
                            request: r,
                            attribution: "caller".into(),
                            reason: reason.clone(),
                        },
                    )?;
                }
                Ok(
                    json!({"ok":true,"request_id":request_id,"status":"cancelled","cancellation":{"attribution":"caller","reason":reason}}),
                )
            }
            _ => {
                let id = input.key().unwrap();
                if self.dir.exists(&request_name(id))? {
                    let (p, r) = self.plan(id)?;
                    if p.intent != input {
                        return Err(err(
                            "request_conflict",
                            "Request ID is already bound to different exact intent",
                        ));
                    }
                    return self.complete(&p, &r, &h, None);
                }
                let (p, source) = self.new_plan(input, &h)?;
                let name = request_name(&p.request_id);
                let raw = bytes(&p)?;
                self.effect.set("partial");
                self.dir.write_receipt(&name, &stage("request"), &raw)?;
                self.complete(
                    &p,
                    &Ref {
                        name,
                        sha256: digest(&raw),
                    },
                    &h,
                    source,
                )
            }
        }
    }
}
fn manifest(s: &State, commission: &str) -> Manifest {
    Manifest {
        audit: s.audit.clone(),
        instance: s.instance.clone(),
        revision: s.revision,
        commission_sha256: commission.into(),
        elements: s.elements.clone(),
    }
}
fn hook(point: &str, id: &str, commit: &str) -> Result<()> {
    if std::env::var("STEWART_PROTO_PAUSE").ok().as_deref() == Some(point) {
        let mut e = std::io::stderr().lock();
        writeln!(
            e,
            "{}",
            json!({"hook":point,"request_id":id,"commit":commit})
        )
        .map_err(|x| err("io_error", x.to_string()))?;
        e.flush().map_err(|x| err("io_error", x.to_string()))?;
        unsafe {
            libc::raise(libc::SIGSTOP);
        }
    }
    Ok(())
}
const HELP: &str = "stewart-submission-prototype --store ABSOLUTE_EXISTING_DIRECTORY\n\nDevelopment-only atomic answer editing. One JSON request on stdin, one JSON\noutcome on stdout (success 0, refusal 2). Init requires an empty ordinary store.\nNo symlink traversal; every operation may refuse busy while another holds its lock.\n\nOperations: init(audit,commission_sha256,request_id); add(request_id,name,source,\nsize,sha256); replace(request_id,handle,name,source,size,sha256);\ndelete(request_id,handle); inspect; read(handle); prepare(request_id);\nsubmit(handle,submit=false). Only explicit true ends editing.\nEvery object also has op with the listed operation name. Exact source identity is\nrequired; source is an absolute ordinary-file path. Names are descriptive.\n\nInterrupted-operation probes: resolve(request_id), resume(request_id),\ncancel(request_id,reason). Confirmed submit uses its issued handle as request_id.\nMatching intent recovers the same outcome. Changed intent refuses request_conflict.\nOld element versions and preparations refuse; inspect current state then prepare.\n\nTest bounds: 32 active elements, 1 MiB each, 8 MiB total, 64 KiB request.\nAll obsolete payloads, receipts and partials remain; delete changes membership only.\nNo product access confinement, physical removal, delivery, process stop or close.\nSTEWART_PROTO_PAUSE=after_stage|before_publish|after_publish|after_sync is a\ndevelopment-only SIGSTOP barrier with a flushed stderr JSON witness.\n";
fn run() -> Result<Value> {
    let a: Vec<_> = std::env::args().skip(1).collect();
    if a.len() != 2 || a[0] != "--store" {
        return Err(err(
            "invalid_arguments",
            "Use --help or --store ABSOLUTE_EXISTING_DIRECTORY",
        ));
    }
    let mut raw = vec![];
    std::io::stdin()
        .take(64 * 1024 + 1)
        .read_to_end(&mut raw)
        .map_err(|e| err("io_error", e.to_string()))?;
    if raw.len() > 64 * 1024 {
        return Err(err("limit_exceeded", "Control input exceeds 64 KiB"));
    }
    let v = control::value(&raw, "stdin")?;
    let object = v
        .as_object()
        .ok_or_else(|| err("invalid_request", "Control input must be one JSON object"))?;
    let op = object
        .get("op")
        .and_then(Value::as_str)
        .ok_or_else(|| err("invalid_request", "String op is required"))?;
    let allowed: &[&str] = match op {
        "init" => &["op", "audit", "commission_sha256", "request_id"],
        "add" => &["op", "request_id", "name", "source", "size", "sha256"],
        "replace" => &[
            "op",
            "request_id",
            "handle",
            "name",
            "source",
            "size",
            "sha256",
        ],
        "delete" => &["op", "request_id", "handle"],
        "inspect" => &["op"],
        "read" => &["op", "handle"],
        "prepare" | "resolve" | "resume" => &["op", "request_id"],
        "submit" => &["op", "handle", "submit"],
        "cancel" => &["op", "request_id", "reason"],
        _ => return Err(err("invalid_request", "Unknown operation")),
    };
    if let Some(k) = object.keys().find(|k| !allowed.contains(&k.as_str())) {
        return Err(err(
            "invalid_request",
            format!("Unknown field {k} for {op}"),
        ));
    }
    let input: Input =
        serde_json::from_value(v).map_err(|e| err("invalid_request", e.to_string()))?;
    let d = safe::Dir::open(&a[1])?;
    d.lock()?;
    let executable =
        std::env::current_exe().map_err(|e| err("writer_unavailable", e.to_string()))?;
    let writer = digest(&safe::read_absolute(
        executable
            .to_str()
            .ok_or_else(|| err("writer_unavailable", "Binary path is not UTF-8"))?,
        128 * 1024 * 1024,
    )?);
    let store = Store {
        dir: d,
        writer,
        effect: Cell::new("unchanged"),
    };
    store.execute(input).map_err(|mut e| {
        if e.effect == "unchanged" && store.effect.get() != "unchanged" {
            e.effect = store.effect.get().into();
        }
        e
    })
}
fn main() {
    if std::env::args().skip(1).collect::<Vec<_>>() == ["--help"] {
        print!("{HELP}");
        return;
    }
    match run() {
        Ok(v) => println!("{v}"),
        Err(e) => {
            println!("{}", serde_json::to_string(&e).unwrap());
            std::process::exit(2)
        }
    }
}
