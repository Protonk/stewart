//! A finite original-commission delivery, not an audit execution or result service.
mod control;
mod safe;
use safe::Dir;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;

const REQUEST_LIMIT: usize = 1024 * 1024;
const MEMBER_LIMIT: usize = 16 * 1024 * 1024;
const RECORD_LIMIT: usize = 4 * 1024 * 1024;
const REQUEST_SCHEMA: &str = "stewart.commission-request/1";
const INTENT_SCHEMA: &str = "stewart.commission-intent/1";
const ATTEMPT_SCHEMA: &str = "stewart.commission-attempt/1";
const ACCEPT_SCHEMA: &str = "stewart.commission-accepted/1";
const ABANDON_SCHEMA: &str = "stewart.commission-abandoned/1";
type Result<T> = std::result::Result<T, Error>;
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(deny_unknown_fields)]
struct Error {
    reason: String,
    message: String,
    paths: Vec<String>,
    next_step: String,
}
impl Error {
    fn new(reason: &str, message: impl Into<String>, path: impl Into<String>, next: &str) -> Self {
        Self {
            reason: reason.into(),
            message: message.into(),
            paths: vec![path.into()],
            next_step: next.into(),
        }
    }
}
fn digest(b: &[u8]) -> String {
    format!("{:x}", Sha256::digest(b))
}
fn encode<T: Serialize>(v: &T) -> Result<Vec<u8>> {
    let mut b = serde_json::to_vec_pretty(v).map_err(|e| {
        Error::new(
            "encoding_failed",
            e.to_string(),
            "",
            "Preserve state and report this implementation failure.",
        )
    })?;
    b.push(b'\n');
    Ok(b)
}
fn binding(msg: &str, path: &str) -> Error {
    Error::new(
        "binding_mismatch",
        msg,
        path,
        "Preserve the records; use the recorded original request or a fresh bundle for a new commission.",
    )
}
fn valid_hash(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn valid_id(s: &str) -> bool {
    (1..=64).contains(&s.len())
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(deny_unknown_fields)]
struct Member {
    id: String,
    role: String,
    source: String,
    view: String,
    size: u64,
    sha256: String,
}
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(deny_unknown_fields)]
struct Request {
    schema: String,
    request_id: String,
    custodian: String,
    grants: String,
    limits: String,
    members: Vec<Member>,
}
impl Request {
    fn validate(&self) -> Result<()> {
        if !valid_id(&self.request_id)
            || self.custodian.trim().is_empty()
            || self.grants.trim().is_empty()
            || self.limits.trim().is_empty()
        {
            return Err(Error::new(
                "invalid_request",
                "Request ID, custodian, grants and limits must be explicit",
                "request",
                "Supply the finite original undertaking and responsible custodian.",
            ));
        }
        if self.members.is_empty() || self.members.len() > 128 {
            return Err(Error::new(
                "limit_exceeded",
                "Require 1–128 selected members",
                "members",
                "Reduce the selected population.",
            ));
        }
        let mut ids = BTreeSet::new();
        let mut total = 0u64;
        let mut questions = 0;
        for m in &self.members {
            if !valid_id(&m.id)
                || !ids.insert(&m.id)
                || m.view.trim().is_empty()
                || !valid_hash(&m.sha256)
                || !matches!(
                    m.role.as_str(),
                    "question" | "instruction" | "material" | "guidance"
                )
            {
                return Err(Error::new(
                    "invalid_request",
                    "Invalid/duplicate member identity, role, view or digest",
                    &m.id,
                    "Give each selected member a unique ID, supported role, supplied view and lowercase SHA-256.",
                ));
            }
            if m.role == "question" {
                questions += 1;
            }
            if !m.source.starts_with('/')
                || m.source.split('/').any(|p| p == "." || p == "..")
                || m.source.contains('\0')
            {
                return Err(Error::new(
                    "unsafe_path",
                    "Source must be absolute without dot components",
                    &m.source,
                    "Supply an explicit regular-file path.",
                ));
            }
            if m.size > MEMBER_LIMIT as u64 {
                return Err(Error::new(
                    "limit_exceeded",
                    "Member exceeds 16 MiB",
                    &m.id,
                    "Reduce the selected population.",
                ));
            }
            total += m.size;
        }
        if questions != 1 {
            return Err(Error::new(
                "invalid_request",
                "Exactly one member must have role question",
                "members",
                "Identify the original question explicitly.",
            ));
        }
        if total > 128 * 1024 * 1024 {
            return Err(Error::new(
                "limit_exceeded",
                "Payload exceeds 128 MiB",
                "members",
                "Reduce the selected population.",
            ));
        }
        Ok(())
    }
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Intent {
    schema: String,
    writer_sha256: String,
    request_sha256: String,
    request_utf8: String,
}
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(deny_unknown_fields)]
struct Output {
    id: String,
    path: String,
    size: u64,
    sha256: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Attempt {
    schema: String,
    writer_sha256: String,
    intent_sha256: String,
    number: u32,
    request_copy: String,
    members: Vec<Output>,
    acceptance_stage: String,
    failure_record: String,
    failure_stage: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Accepted {
    schema: String,
    writer_sha256: String,
    intent_sha256: String,
    attempt: String,
    attempt_sha256: String,
    request_sha256: String,
    request_copy: String,
    members: Vec<Output>,
    custodian: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Abandoned {
    schema: String,
    writer_sha256: String,
    status: String,
    actor: String,
    reason: String,
    custodian: String,
    intent_sha256: Option<String>,
    prior_acceptance_diagnostic: Option<Error>,
    original_intent_diagnostic: Option<Error>,
    inventory: Value,
}
struct Loaded {
    intent: Intent,
    intent_raw: Vec<u8>,
    request: Request,
}
fn load(d: &Dir) -> Result<Loaded> {
    let raw = d.read("INTENT.json", RECORD_LIMIT)?;
    let i: Intent = control::parse(&raw, INTENT_SCHEMA, "INTENT.json")?;
    if i.request_utf8.len() > REQUEST_LIMIT
        || !valid_hash(&i.writer_sha256)
        || digest(i.request_utf8.as_bytes()) != i.request_sha256
    {
        return Err(binding(
            "Intent request bytes or writer identity do not match",
            "INTENT.json",
        ));
    }
    let r: Request = control::parse(
        i.request_utf8.as_bytes(),
        REQUEST_SCHEMA,
        "INTENT.json/request_utf8",
    )?;
    r.validate()?;
    Ok(Loaded {
        intent: i,
        intent_raw: raw,
        request: r,
    })
}
fn writer() -> Result<String> {
    let p = std::env::current_exe().map_err(|e| {
        Error::new(
            "writer_unavailable",
            e.to_string(),
            "current executable",
            "Use an available explicit installed binary.",
        )
    })?;
    let s = p.to_str().ok_or_else(|| {
        Error::new(
            "unsafe_path",
            "Executable path is not UTF-8",
            "current executable",
            "Install at a UTF-8 path.",
        )
    })?;
    Ok(digest(&safe::read_absolute(s, 64 * 1024 * 1024)?))
}
fn check_writer(i: &Intent, current: &str) -> Result<()> {
    if i.writer_sha256 != current {
        Err(Error::new(
            "writer_mismatch",
            "This mutation belongs to a different recorded binary",
            "INTENT.json",
            "Use the independently verified original binary; read-only inspection remains available. No recorded code is executed automatically.",
        ))
    } else {
        Ok(())
    }
}
fn verify(raw: &[u8], size: u64, sha: &str, path: &str) -> Result<()> {
    if raw.len() as u64 != size || digest(raw) != sha {
        Err(binding(
            "Observed bytes differ from the recorded size/digest",
            path,
        ))
    } else {
        Ok(())
    }
}
fn attempt_outputs(r: &Request, n: u32) -> Vec<Output> {
    r.members
        .iter()
        .enumerate()
        .map(|(k, m)| Output {
            id: m.id.clone(),
            path: format!("copy-{n:06}-{k:03}.bin"),
            size: m.size,
            sha256: m.sha256.clone(),
        })
        .collect()
}
fn acceptance(d: &Dir, l: &Loaded, pin: Option<&str>) -> Result<(Accepted, Vec<u8>)> {
    let raw = d.read("ACCEPTED.json", RECORD_LIMIT)?;
    if let Some(p) = pin {
        if !valid_hash(p) || digest(&raw) != p {
            return Err(binding(
                "Receipt differs from the caller's pinned identity",
                "ACCEPTED.json",
            ));
        }
    }
    let a: Accepted = control::parse(&raw, ACCEPT_SCHEMA, "ACCEPTED.json")?;
    if a.intent_sha256 != digest(&l.intent_raw)
        || a.request_sha256 != l.intent.request_sha256
        || a.writer_sha256 != l.intent.writer_sha256
        || a.custodian != l.request.custodian
    {
        return Err(binding(
            "Acceptance does not bind this original intent",
            "ACCEPTED.json",
        ));
    }
    let ar = d.read(&a.attempt, RECORD_LIMIT)?;
    if digest(&ar) != a.attempt_sha256 {
        return Err(binding("Attempt receipt digest differs", &a.attempt));
    }
    let plan: Attempt = control::parse(&ar, ATTEMPT_SCHEMA, &a.attempt)?;
    if plan.number == 0
        || plan.number > 999999
        || a.attempt != format!("ATTEMPT-{:06}.json", plan.number)
        || plan.intent_sha256 != a.intent_sha256
        || plan.writer_sha256 != a.writer_sha256
        || plan.members != attempt_outputs(&l.request, plan.number)
        || plan.request_copy != format!("copy-{:06}-request.json", plan.number)
        || plan.acceptance_stage != format!("ACCEPTED-{:06}.stage", plan.number)
        || plan.failure_record != format!("FAILURE-{:06}.json", plan.number)
        || plan.failure_stage != format!("FAILURE-{:06}.stage", plan.number)
        || a.members != plan.members
        || a.request_copy != plan.request_copy
    {
        return Err(binding(
            "Acceptance selection or attempt plan differs from original intent",
            "ACCEPTED.json",
        ));
    }
    if d.exists("ABANDONED.json")? {
        return Err(binding(
            "Accepted and abandoned outcomes coexist",
            "ACCEPTED.json",
        ));
    }
    Ok((a, raw))
}
fn material_checks(d: &Dir, l: &Loaded, a: &Accepted) -> Vec<Value> {
    let mut out = Vec::new();
    let entries = std::iter::once(Output {
        id: "@request".into(),
        path: a.request_copy.clone(),
        size: l.intent.request_utf8.len() as u64,
        sha256: l.intent.request_sha256.clone(),
    })
    .chain(a.members.clone());
    for o in entries {
        let got = d
            .read(&o.path, MEMBER_LIMIT)
            .and_then(|b| verify(&b, o.size, &o.sha256, &o.path));
        out.push(match got {Ok(())=>json!({"id":o.id,"path":o.path,"size":o.size,"sha256":o.sha256,"verified":true}),Err(e)=>json!({"id":o.id,"path":o.path,"size":o.size,"sha256":o.sha256,"verified":false,"diagnostic":e})});
    }
    out
}
fn view(d: &Dir, l: &Loaded, a: &Accepted, raw: &[u8], pin: Option<&str>) -> Value {
    let checks = material_checks(d, l, a);
    let intact = checks.iter().all(|x| x["verified"] == true);
    json!({"schema":"stewart.commission-inspection/1","state":"accepted","bundle":d.label,"receipt":"ACCEPTED.json","receipt_sha256":digest(raw),"request_id":l.request.request_id,"custodian":a.custodian,"integrity":if intact{"verified"}else{"damaged"},"externally_pinned":pin.is_some(),"original_undertaking":l.request,"members":checks,"qualification":"Recorded delivery of original commission only. Declarations are attributed, not enforcement or auditor activity. Self-consistency does not authenticate historical origin. Manager preserves this bundle."})
}
fn accepted_summary(d: &Dir, l: &Loaded) -> Result<Value> {
    let (a, raw) = acceptance(d, l, None)?;
    let v = view(d, l, &a, &raw, None);
    if v["integrity"] != "verified" {
        return Err(Error::new(
            "accepted_material_damaged",
            "Acceptance exists but retained material no longer verifies",
            &d.label,
            "Use inspect and read for independently verified members; preserve damage. Acceptance is not replayed.",
        ));
    }
    Ok(v)
}
fn next_attempt(d: &Dir) -> Result<u32> {
    let names = d.names()?;
    for n in 1..=999999u32 {
        let stem = format!("ATTEMPT-{n:06}");
        if !names.iter().any(|s| s.starts_with(&stem)) {
            return Ok(n);
        }
    }
    Err(Error::new(
        "limit_exceeded",
        "Attempt names exhausted",
        &d.label,
        "Preserve this bundle and its diagnostics.",
    ))
}
fn run_copy(d: &Dir, l: &Loaded, current: &str) -> Result<Value> {
    let n = next_attempt(d)?;
    let name = format!("ATTEMPT-{n:06}.json");
    let stage = format!("ATTEMPT-{n:06}.stage");
    let plan = Attempt {
        schema: ATTEMPT_SCHEMA.into(),
        writer_sha256: current.into(),
        intent_sha256: digest(&l.intent_raw),
        number: n,
        request_copy: format!("copy-{n:06}-request.json"),
        members: attempt_outputs(&l.request, n),
        acceptance_stage: format!("ACCEPTED-{n:06}.stage"),
        failure_record: format!("FAILURE-{n:06}.json"),
        failure_stage: format!("FAILURE-{n:06}.stage"),
    };
    let plan_raw = encode(&plan)?;
    d.write_receipt(&name, &stage, &plan_raw)?;
    let action = (|| -> Result<Value> {
        d.write_exclusive(&plan.request_copy, l.intent.request_utf8.as_bytes())?;
        for (m, o) in l.request.members.iter().zip(&plan.members) {
            let b = safe::read_absolute(&m.source, MEMBER_LIMIT)?;
            verify(&b, m.size, &m.sha256, &m.source)?;
            d.write_exclusive(&o.path, &b)?;
        }
        let a = Accepted {
            schema: ACCEPT_SCHEMA.into(),
            writer_sha256: current.into(),
            intent_sha256: digest(&l.intent_raw),
            attempt: name.clone(),
            attempt_sha256: digest(&plan_raw),
            request_sha256: l.intent.request_sha256.clone(),
            request_copy: plan.request_copy.clone(),
            members: plan.members.clone(),
            custodian: l.request.custodian.clone(),
        };
        let checks = material_checks(d, l, &a);
        if checks.iter().any(|v| v["verified"] != true) {
            return Err(Error::new(
                "copy_verification_failed",
                "Copied members did not verify before acceptance",
                &d.label,
                "Inspect retained attempts, then complete or acknowledge incomplete intake.",
            ));
        }
        d.ensure_location()?;
        let a_raw = encode(&a)?;
        d.write_receipt("ACCEPTED.json", &plan.acceptance_stage, &a_raw)?;
        d.ensure_location()?;
        accepted_summary(d, l)
    })();
    if let Err(ref failure) = action {
        let f = json!({"schema":"stewart.commission-failure/1","attempt":name,"attempt_sha256":digest(&plan_raw),"diagnostic":failure});
        if let Ok(raw) = encode(&f) {
            if let Err(record_error) =
                d.write_receipt(&plan.failure_record, &plan.failure_stage, &raw)
            {
                return Err(Error::new(
                    "failure_record_incomplete",
                    format!(
                        "Operation: {}; failure recording: {}. Both effects remain uncertain.",
                        failure.message, record_error.message
                    ),
                    &d.label,
                    "Keep all files and this diagnostic; inspect the known bundle reference before any completion or disposition.",
                ));
            }
        }
    }
    action
}
fn intake(bundle: &str, request_path: &str, resume: bool) -> Result<Value> {
    let raw = safe::read_absolute(request_path, REQUEST_LIMIT)?;
    let r: Request = control::parse(&raw, REQUEST_SCHEMA, request_path)?;
    r.validate()?;
    let utf8 = String::from_utf8(raw.clone()).map_err(|e| {
        Error::new(
            "invalid_json",
            e.to_string(),
            request_path,
            "Supply UTF-8 JSON.",
        )
    })?;
    let current = writer()?;
    let d = Dir::open(bundle)?;
    d.lock()?;
    if d.exists("ABANDONED.json")? {
        let (a, _) = disposition(&d, &load(&d))?;
        return Err(Error::new(
            if a.status == "incomplete_acknowledged" {
                "intake_disposed"
            } else {
                "intake_unresolved"
            },
            "An attributed acknowledgment exists; its recorded limits still apply",
            bundle,
            "Inspect this retained bundle; preserve unresolved obligations and use a fresh directory for a new commission.",
        ));
    }
    let mut created_intent = false;
    if !d.exists("INTENT.json")? {
        if resume {
            let staged = d.read("INTENT.stage", RECORD_LIMIT)?;
            let i: Intent = control::parse(&staged, INTENT_SCHEMA, "INTENT.stage")?;
            check_writer(&i, &current)?;
            if i.request_utf8.as_bytes() != raw || i.request_sha256 != digest(&raw) {
                return Err(binding(
                    "Staged intent differs from the request",
                    "INTENT.stage",
                ));
            }
            d.publish_staged("INTENT.json", "INTENT.stage", &staged)?;
        } else {
            if !d.names()?.is_empty() {
                return Err(Error::new(
                    "bundle_not_empty",
                    "First intake requires an empty designated directory",
                    bundle,
                    "Inspect existing partial evidence; complete or acknowledge it, or choose a new empty directory.",
                ));
            }
            let i = Intent {
                schema: INTENT_SCHEMA.into(),
                writer_sha256: current.clone(),
                request_sha256: digest(&raw),
                request_utf8: utf8,
            };
            d.write_receipt("INTENT.json", "INTENT.stage", &encode(&i)?)?;
            created_intent = true;
        }
    }
    let l = load(&d)?;
    if l.intent.request_utf8.as_bytes() != raw {
        return Err(binding(
            "This bundle is bound to different request bytes",
            "INTENT.json",
        ));
    }
    if d.exists("ACCEPTED.json")? {
        return accepted_summary(&d, &l);
    }
    check_writer(&l.intent, &current)?;
    if !resume && !created_intent {
        return Err(Error::new(
            "intake_incomplete",
            "A prior intent has no completed acceptance",
            bundle,
            "Inspect this same bundle, then use complete with the original request or abandon with an attributed acknowledgment.",
        ));
    }
    run_copy(&d, &l, &current)
}
fn inspect(bundle: &str, pin: Option<&str>) -> Result<(Value, i32)> {
    let d = Dir::open(bundle)?;
    let loaded = load(&d);
    if d.exists("ABANDONED.json")? {
        if pin.is_some() {
            return Err(binding(
                "An incomplete acknowledgment cannot establish the pinned acceptance",
                "ABANDONED.json",
            ));
        }
        let (a, _) = disposition(&d, &loaded)?;
        let code = if a.status == "incomplete_acknowledged" {
            0
        } else {
            3
        };
        let mut observation = json!({"schema":"stewart.commission-inspection/1","state":a.status,"bundle":bundle,"disposition":a,"original_intent_diagnostic":loaded.as_ref().err(),"inventory":safe::snapshot(&d)?});
        // A disposition changes the intake outcome, not the original question.
        // Only a validated intent supplies this projection; damaged intent keeps
        // its diagnostic and cannot be reconstructed from live source paths.
        if let Ok(l) = loaded.as_ref() {
            observation["request_id"] = json!(&l.request.request_id);
            observation["original_undertaking"] = json!(&l.request);
            observation["intent_sha256"] = json!(digest(&l.intent_raw));
        }
        return Ok((observation, code));
    }
    let l = match loaded {
        Ok(l) => l,
        Err(e) => {
            return Ok((
                json!({"schema":"stewart.commission-inspection/1","state":"unresolved","bundle":bundle,"diagnostic":e,"inventory":safe::snapshot(&d)?}),
                3,
            ));
        }
    };
    if d.exists("ACCEPTED.json")? {
        let (a, raw) = acceptance(&d, &l, pin)?;
        let v = view(&d, &l, &a, &raw, pin);
        let code = if v["integrity"] == "verified" { 0 } else { 3 };
        return Ok((v, code));
    }
    if pin.is_some() {
        return Err(binding("Pinned acceptance is missing", "ACCEPTED.json"));
    }
    Ok((
        json!({"schema":"stewart.commission-inspection/1","state":"incomplete","bundle":bundle,"request_id":l.request.request_id,"original_undertaking":l.request,"intent_sha256":digest(&l.intent_raw),"inventory":safe::snapshot(&d)?,"next_step":"Complete with the original request or explicitly acknowledge incomplete intake using abandon; retain all partial bytes."}),
        3,
    ))
}
fn validate_abandon(a: &Abandoned) -> Result<()> {
    if !matches!(
        a.status.as_str(),
        "incomplete_acknowledged" | "unresolved_acknowledged"
    ) || !valid_hash(&a.writer_sha256)
        || a.actor.trim().is_empty()
        || a.reason.trim().is_empty()
        || a.custodian.trim().is_empty()
        || !a.inventory.is_array()
    {
        Err(Error::new(
            "invalid_record",
            "Invalid incomplete disposition",
            "ABANDONED.json",
            "Preserve this record and its diagnostics.",
        ))
    } else {
        Ok(())
    }
}
/// Status, intake and disposition replay use this same binding validation.
fn disposition(d: &Dir, loaded: &Result<Loaded>) -> Result<(Abandoned, Vec<u8>)> {
    let raw = d.read("ABANDONED.json", RECORD_LIMIT)?;
    let a: Abandoned = control::parse(&raw, ABANDON_SCHEMA, "ABANDONED.json")?;
    validate_abandon(&a)?;
    if a.status == "incomplete_acknowledged" {
        let l = loaded.as_ref().map_err(Clone::clone)?;
        if a.intent_sha256.as_deref() != Some(digest(&l.intent_raw).as_str())
            || a.writer_sha256 != l.intent.writer_sha256
            || a.custodian != l.request.custodian
            || a.original_intent_diagnostic.is_some()
            || a.prior_acceptance_diagnostic.is_some()
            || d.exists("ACCEPTED.json")?
        {
            return Err(binding(
                "Disposition does not bind the original incomplete undertaking",
                "ABANDONED.json",
            ));
        }
    } else {
        if a.original_intent_diagnostic.is_none() && a.prior_acceptance_diagnostic.is_none() {
            return Err(binding(
                "Unresolved acknowledgment has no recorded uncertainty",
                "ABANDONED.json",
            ));
        }
        if let Some(ref recorded) = a.intent_sha256 {
            let l = loaded.as_ref().map_err(Clone::clone)?;
            if *recorded != digest(&l.intent_raw)
                || a.writer_sha256 != l.intent.writer_sha256
                || a.custodian != l.request.custodian
            {
                return Err(binding(
                    "Observation acknowledgment's available intent binding changed",
                    "ABANDONED.json",
                ));
            }
        } else if a.original_intent_diagnostic.is_none() {
            return Err(binding(
                "Observation without intent identity lacks its diagnostic",
                "ABANDONED.json",
            ));
        }
    }
    Ok((a, raw))
}
fn abandon(bundle: &str, actor: &str, reason: &str) -> Result<Value> {
    if actor.trim().is_empty() || reason.trim().is_empty() {
        return Err(Error::new(
            "invalid_request",
            "Actor and reason must be nonempty",
            bundle,
            "Name the responsible actor and reason for acknowledging incomplete intake.",
        ));
    }
    let d = Dir::open(bundle)?;
    d.lock()?;
    let l = load(&d);
    let current = writer()?;
    if let Ok(ref l) = l {
        check_writer(&l.intent, &current)?;
    }
    if d.exists("ABANDONED.json")? {
        let (a, raw) = disposition(&d, &l)?;
        if a.actor != actor || a.reason != reason {
            return Err(binding(
                "Acknowledgment replay differs from its recorded actor or reason",
                "ABANDONED.json",
            ));
        }
        return Ok(json!({"state":a.status,"disposition":a,"receipt_sha256":digest(&raw)}));
    }
    let mut previous = None;
    if d.exists("ACCEPTED.json")? {
        match &l {
            Ok(l) => match acceptance(&d, l, None) {
                Ok(_) => {
                    return Err(Error::new(
                        "already_accepted",
                        "Acceptance exists; abandonment is not a disposal operation",
                        bundle,
                        "Keep the accepted bundle; inspect damage and preserve independently verified members.",
                    ));
                }
                Err(e) => previous = Some(e),
            },
            Err(e) => previous = Some(e.clone()),
        }
    }
    if !d.exists("INTENT.json")? && !d.exists("INTENT.stage")? {
        return Err(Error::new(
            "no_intake",
            "No commission intent or intent stage exists",
            bundle,
            "Choose the exact intake directory; this operation does not claim arbitrary directories.",
        ));
    }
    let a = Abandoned {
        schema: ABANDON_SCHEMA.into(),
        writer_sha256: current,
        status: if l.is_err() || previous.is_some() {
            "unresolved_acknowledged"
        } else {
            "incomplete_acknowledged"
        }
        .into(),
        actor: actor.into(),
        reason: reason.into(),
        custodian: l
            .as_ref()
            .map(|x| x.request.custodian.clone())
            .unwrap_or_else(|_| actor.into()),
        intent_sha256: l.as_ref().ok().map(|x| digest(&x.intent_raw)),
        prior_acceptance_diagnostic: previous,
        original_intent_diagnostic: l.as_ref().err().cloned(),
        inventory: safe::snapshot(&d)?,
    };
    let raw = encode(&a)?;
    let names = d.names()?;
    let n = (1..=999999u32)
        .find(|n| !names.contains(&format!("ABANDONED-{n:06}.stage")))
        .ok_or_else(|| {
            Error::new(
                "limit_exceeded",
                "Disposition staging names exhausted",
                bundle,
                "Keep existing records.",
            )
        })?;
    let stage = format!("ABANDONED-{n:06}.stage");
    d.write_receipt("ABANDONED.json", &stage, &raw)?;
    Ok(
        json!({"state":a.status,"disposition":a,"receipt_sha256":digest(&raw),"qualification":"The named custodian retains all partial bytes. No deletion or acceptance is authorized. Any damaged prior outcome remains uncertain."}),
    )
}
fn read_member(bundle: &str, id: &str, pin: Option<&str>) -> Result<()> {
    let d = Dir::open(bundle)?;
    let l = load(&d)?;
    let (a, raw) = acceptance(&d, &l, pin)?;
    let o = if id == "@request" {
        Output {
            id: id.into(),
            path: a.request_copy.clone(),
            size: l.intent.request_utf8.len() as u64,
            sha256: l.intent.request_sha256.clone(),
        }
    } else {
        a.members
            .iter()
            .find(|m| m.id == id)
            .cloned()
            .ok_or_else(|| {
                Error::new(
                    "unknown_member",
                    "Member is not selected by this commission",
                    id,
                    "Inspect the explicit commission inventory and choose a listed ID.",
                )
            })?
    };
    let b = d.read(&o.path, MEMBER_LIMIT)?;
    verify(&b, o.size, &o.sha256, &o.path)?;
    let inspection = view(&d, &l, &a, &raw, pin);
    let qualification = json!({"member":id,"size":b.len(),"sha256":digest(&b),"receipt_sha256":digest(&raw),"externally_pinned":pin.is_some(),"whole_bundle_integrity":inspection["integrity"],"qualification":inspection["qualification"]});
    eprintln!("{}", qualification);
    std::io::stdout().lock().write_all(&b).map_err(|e| {
        Error::new(
            "output_failed",
            e.to_string(),
            "stdout",
            "Preserve the bundle; retry readback to a working output destination.",
        )
    })
}
const HELP: &str = "stewart-commission — original commission delivery and verified readback\n\naccept --request ABS --bundle EXISTING_ABS_DIR\ncomplete --request ABS --bundle EXISTING_ABS_DIR\ninspect --bundle ABS [--receipt-sha256 HEX]\nread --bundle ABS --member ID_OR_@request [--receipt-sha256 HEX]\nabandon --bundle ABS --actor NAME --reason TEXT\n\nCaller creates an empty directory and preserves it. accept delivers original\nquestion/material copies, not an audit execution or result. Lost replies: inspect\nthe same directory. Incomplete intake: complete its original request or abandon\nwith an explicit acknowledgment; neither overwrites nor deletes evidence.\nRead commands never execute the original writer or consult original sources.\nExit 0: requested operation succeeded; 2: refusal/error; 3: incomplete/damaged\ninspection. See the installed distribution README for request schema and limits.";
fn cli() -> Result<i32> {
    let mut args = std::env::args().skip(1);
    let Some(command) = args.next() else {
        println!("{HELP}");
        return Ok(0);
    };
    if command == "--help" || command == "help" {
        println!("{HELP}");
        return Ok(0);
    }
    if command == "--version" {
        println!("stewart-commission {}", env!("CARGO_PKG_VERSION"));
        return Ok(0);
    }
    let allowed: &[&str] = match command.as_str() {
        "accept" | "complete" => &["--request", "--bundle"],
        "inspect" => &["--bundle", "--receipt-sha256"],
        "read" => &["--bundle", "--member", "--receipt-sha256"],
        "abandon" => &["--bundle", "--actor", "--reason"],
        _ => {
            return Err(Error::new(
                "invalid_arguments",
                "Unknown command",
                command,
                "Run --help for the bounded interface.",
            ));
        }
    };
    let mut opts = BTreeMap::new();
    while let Some(k) = args.next() {
        if k == "--help" {
            println!("{HELP}");
            return Ok(0);
        }
        if !allowed.contains(&k.as_str()) || opts.contains_key(&k) {
            return Err(Error::new(
                "invalid_arguments",
                "Unknown or repeated option",
                k,
                "Run --help; supply each supported option once.",
            ));
        }
        let v = args.next().ok_or_else(|| {
            Error::new(
                "invalid_arguments",
                "Missing option value",
                &k,
                "Supply a value.",
            )
        })?;
        opts.insert(k, v);
    }
    let req = |key: &str| {
        opts.get(key).map(String::as_str).ok_or_else(|| {
            Error::new(
                "invalid_arguments",
                "Missing required option",
                key,
                "Run --help for required arguments.",
            )
        })
    };
    let bundle = req("--bundle")?;
    let pin = opts.get("--receipt-sha256").map(String::as_str);
    let (v, code) = match command.as_str() {
        "accept" | "complete" => (intake(bundle, req("--request")?, command == "complete")?, 0),
        "inspect" => inspect(bundle, pin)?,
        "read" => {
            read_member(bundle, req("--member")?, pin)?;
            return Ok(0);
        }
        "abandon" => (abandon(bundle, req("--actor")?, req("--reason")?)?, 0),
        _ => unreachable!(),
    };
    println!(
        "{}",
        String::from_utf8(encode(&v)?).map_err(|e| Error::new(
            "encoding_failed",
            e.to_string(),
            "stdout",
            "Report this implementation failure."
        ))?
    );
    Ok(code)
}
fn main() {
    let code = match cli() {
        Ok(code) => code,
        Err(e) => {
            eprintln!("{}", json!({"error":e}));
            2
        }
    };
    std::process::exit(code);
}
