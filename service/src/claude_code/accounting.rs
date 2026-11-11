//! Harness reports are checkpoints, not API charges. Missing intervals remain
//! unknown; an earlier report is never erased by a crash-zeroed result.
use crate::json::{J, JsonError, Obj};

#[derive(Debug, Clone, PartialEq)]
pub struct Start {
    pub profile_sha256: String,
    pub placement_timeout_seconds: u64,
}
impl Start {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("kind", "claude-code/1")
            .with("profile_sha256", self.profile_sha256.as_str())
            .with("placement_timeout_seconds", self.placement_timeout_seconds)
    }
    pub fn decode(o: &Obj) -> Result<Self, JsonError> {
        o.exactly(&["kind", "profile_sha256", "placement_timeout_seconds"])?;
        if o.str("kind")? != "claude-code/1" {
            return Err(o.invalid("kind", "unsupported runtime"));
        }
        let seconds = o.u64("placement_timeout_seconds", super::profile::MAX_SECONDS)?;
        if seconds == 0 {
            return Err(o.invalid("placement_timeout_seconds", "expected a positive timeout"));
        }
        Ok(Self {
            profile_sha256: o.sha256("profile_sha256")?.into(),
            placement_timeout_seconds: seconds,
        })
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Summary {
    pub placements: u64,
    pub unknown_intervals: u64,
    pub stopped: u64,
    pub reported_placements: u64,
    pub input: u64,
    pub cache_creation: u64,
    pub cache_read: u64,
    pub output: u64,
    pub turns: u64,
}

impl Summary {
    pub fn reserved() -> Self {
        Self {
            placements: 1,
            unknown_intervals: 1,
            ..Self::default()
        }
    }
    pub fn add(&mut self, other: Self) {
        self.placements = self.placements.saturating_add(other.placements);
        self.unknown_intervals = self
            .unknown_intervals
            .saturating_add(other.unknown_intervals);
        self.stopped = self.stopped.saturating_add(other.stopped);
        self.reported_placements = self
            .reported_placements
            .saturating_add(other.reported_placements);
        self.input = self.input.saturating_add(other.input);
        self.cache_creation = self.cache_creation.saturating_add(other.cache_creation);
        self.cache_read = self.cache_read.saturating_add(other.cache_read);
        self.output = self.output.saturating_add(other.output);
        self.turns = self.turns.saturating_add(other.turns);
    }
    pub fn to_j(self) -> J {
        J::obj()
            .with("runtime", "claude-code/1")
            .with("placements", self.placements)
            .with("unknown_intervals", self.unknown_intervals)
            .with("stopped", self.stopped)
            .with("reported_placements", self.reported_placements)
            .with(
                "reported_main_loop",
                if self.reported_placements == 0 {
                    J::Null
                } else {
                    J::obj()
                        .with("input_tokens", self.input)
                        .with("cache_creation_input_tokens", self.cache_creation)
                        .with("cache_read_input_tokens", self.cache_read)
                        .with("output_tokens", self.output)
                        .with("harness_turns", self.turns)
                },
            )
            .with("provider_completeness", "unverified")
    }
    pub fn decode(o: &Obj) -> Result<Self, JsonError> {
        o.exactly(&[
            "runtime",
            "placements",
            "unknown_intervals",
            "stopped",
            "reported_placements",
            "reported_main_loop",
            "provider_completeness",
        ])?;
        if o.str("runtime")? != "claude-code/1" || o.str("provider_completeness")? != "unverified" {
            return Err(o.invalid("runtime", "unsupported harness accounting scope"));
        }
        let r = o.obj_or_null("reported_main_loop")?;
        if let Some(r) = &r {
            r.exactly(&[
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
                "harness_turns",
            ])?;
        }
        let max = crate::usage::FIGURE_MAX;
        let count = |key: &str| -> Result<u64, JsonError> {
            r.as_ref()
                .map(|r| r.u64(key, max))
                .transpose()
                .map(|v| v.unwrap_or(0))
        };
        let s = Self {
            placements: o.u64("placements", max)?,
            unknown_intervals: o.u64("unknown_intervals", max)?,
            stopped: o.u64("stopped", max)?,
            reported_placements: o.u64("reported_placements", max)?,
            input: count("input_tokens")?,
            cache_creation: count("cache_creation_input_tokens")?,
            cache_read: count("cache_read_input_tokens")?,
            output: count("output_tokens")?,
            turns: count("harness_turns")?,
        };
        if s.unknown_intervals > s.placements
            || s.stopped > s.placements
            || s.reported_placements > s.placements
            || (r.is_some() != (s.reported_placements > 0))
        {
            return Err(o.invalid(
                "reported_placements",
                "report/stop counts must agree with reserved placements and report presence",
            ));
        }
        Ok(s)
    }

    pub fn allowances(self, limits: super::profile::Limits) -> J {
        J::obj()
            .with("runtime", "claude-code/1")
            .with(
                "placements",
                J::obj()
                    .with("used", self.placements)
                    .with("limit", limits.max_placements)
                    .with(
                        "remaining",
                        limits.max_placements.saturating_sub(self.placements),
                    ),
            )
            .with(
                "placement_timeout_seconds",
                limits.placement_timeout_seconds,
            )
            .with("usage", self.to_j())
    }
}

/// Observe every recorded group. No launch can precede its durable process
/// record; an absent run/process file therefore means no child was permitted.
pub fn groups_gone(audit: &crate::archive::Audit, run: u64) -> Result<bool, String> {
    let dir = match crate::runs::open(audit, run) {
        Ok(d) => d,
        Err(e) if e.raw_os_error() == Some(libc::ENOENT) => return Ok(true),
        Err(e) => return Err(e.to_string()),
    };
    let stop = match dir.read_regular("runtime-stop.json", 4096) {
        Ok((raw, _)) => Some(raw),
        Err(crate::fsx::ReadError::Missing) => None,
        Err(e) => return Err(format!("runtime-stop.json: {}", e.describe())),
    };
    if let Some(raw) = stop {
        let parsed = crate::json::parse(&raw).map_err(|e| e.to_string())?;
        let o = parsed.obj("").map_err(|e| e.to_string())?;
        o.exactly(&["elapsed_ms", "deadline_ms", "groups_gone"])
            .map_err(|e| e.to_string())?;
        o.u64("elapsed_ms", u64::MAX).map_err(|e| e.to_string())?;
        o.u64("deadline_ms", super::profile::MAX_SECONDS * 1000)
            .map_err(|e| e.to_string())?;
        if o.bool("groups_gone").map_err(|e| e.to_string())? {
            return Ok(true);
        }
    }
    for role in ["auth", "model"] {
        let name = format!("process-{role}.json");
        let raw = match dir.read_regular(&name, 4096) {
            Ok((b, _)) => b,
            Err(crate::fsx::ReadError::Missing) => continue,
            Err(e) => return Err(format!("{name}: {}", e.describe())),
        };
        let parsed = crate::json::parse(&raw).map_err(|e| e.to_string())?;
        let o = parsed.obj("").map_err(|e| e.to_string())?;
        let group = (|| {
            o.exactly(&["schema", "group", "role"])?;
            if o.str("schema")? != "stewart.claude-code.process/1" || o.str("role")? != role {
                return Err(o.invalid("schema", "process observation differs"));
            }
            o.u64("group", i32::MAX as u64)
        })()
        .map_err(|e| e.to_string())?;
        if !super::process::gone(group as i32)? {
            return Ok(false);
        }
    }
    Ok(true)
}

pub fn ensure_stopped(
    audit: &crate::archive::Audit,
    state: &crate::log::LogState,
) -> Result<(), String> {
    for p in state
        .placements()
        .iter()
        .filter(|p| p.start.runtime.is_some())
    {
        if !groups_gone(audit, p.run)? {
            return Err(format!(
                "Placement {} still has an observed process group. The active lock alone does not establish stopping; no new placement or close cleanup is permitted.",
                p.run
            ));
        }
        if p.ended.is_none() {
            let accounted = account(audit, p.run);
            if !accounted.problems.is_empty() {
                return Err(format!(
                    "Placement {} has unreadable runtime observations: {}. Resolve them before starting or disposing of its evidence.",
                    p.run,
                    accounted.problems.join("; ")
                ));
            }
        }
    }
    Ok(())
}

pub fn account(audit: &crate::archive::Audit, run: u64) -> crate::runs::Account {
    let mut acc = crate::runs::Account::default();
    let mut usage = Summary::reserved();
    let read = (|| -> Result<(), String> {
        let dir = match crate::runs::open(audit, run) {
            Ok(d) => d,
            Err(e) if e.raw_os_error() == Some(libc::ENOENT) => return Ok(()),
            Err(e) => return Err(e.to_string()),
        };
        let mut checkpoints = dir
            .names()
            .map_err(|e| e.to_string())?
            .into_iter()
            .filter_map(|name| {
                let n = name
                    .strip_prefix("runtime-usage-")?
                    .strip_suffix(".json")?
                    .parse::<u64>()
                    .ok()?;
                Some((n, name))
            })
            .collect::<Vec<_>>();
        checkpoints.sort();
        for (_, name) in checkpoints {
            let (raw, _) = dir.read_regular(&name, 65536).map_err(|e| e.describe())?;
            let parsed = crate::json::parse(&raw).map_err(|e| e.to_string())?;
            let next = Summary::decode(&parsed.obj("").map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
            if next.placements != 1
                || next.reported_placements < usage.reported_placements
                || next.input < usage.input
                || next.output < usage.output
                || next.cache_creation < usage.cache_creation
                || next.cache_read < usage.cache_read
                || next.turns < usage.turns
            {
                return Err(format!("{name} regresses or changes the checkpoint scope"));
            }
            usage = next;
        }
        Ok(())
    })();
    if let Err(e) = read {
        usage.unknown_intervals = 1;
        acc.problems.push(e);
    }
    match groups_gone(audit, run) {
        Ok(gone) => usage.stopped = u64::from(gone),
        Err(e) => {
            usage.stopped = 0;
            acc.problems.push(e);
        }
    }
    // Without a retained terminal stop, later activity may have followed the
    // last checkpoint. Keep its counts and mark the uncovered interval.
    if crate::runs::open(audit, run)
        .ok()
        .is_none_or(|d| !d.exists("runtime-stop.json").unwrap_or(false))
    {
        usage.unknown_intervals = 1;
    }
    acc.usage.harness = Some(usage);
    acc.recorded = acc.usage;
    for (_, notice) in crate::log::read(audit)
        .notices()
        .iter()
        .filter(|(_, n)| n.run == run)
    {
        // A claim consumed the allowance. Without the owner's ending, no
        // durable transmission observation proves sent or not_sent.
        acc.seen.insert(
            notice.request,
            crate::runs::RequestSeen {
                complete: true,
                written: false,
                unreadable_attempt: false,
            },
        );
    }
    acc
}
