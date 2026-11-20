//! Read-only observations shared by manager replies. These are views of evidence,
//! not another lifecycle or a permission to continue work.

use super::status::Lock;
use crate::archive::{self, Audit};
use crate::json::J;
use crate::log::LogState;
use crate::usage::{Limits, MIN_OUTPUT_FOR_REQUEST};

fn unknown_usage(limits: &Limits) -> J {
    #[cfg(feature = "claude-code")]
    if let Some(h) = limits.harness {
        return J::obj()
            .with("runtime", "claude-code/1")
            .with(
                "placements",
                J::obj()
                    .with("used", "unknown")
                    .with("limit", h.max_placements)
                    .with("remaining", "unknown"),
            )
            .with("placement_timeout_seconds", h.placement_timeout_seconds)
            .with("usage", "unknown");
    }
    let one = |limit| {
        J::obj()
            .with("used", "unknown")
            .with("reported", "unknown")
            .with("estimated", "unknown")
            .with("limit", limit)
    };
    J::obj()
        .with("turns", one(limits.turns))
        .with("input_tokens", one(limits.input_tokens))
        .with("output_tokens", one(limits.output_tokens))
}

pub fn allowances(audit: &Audit, state: &LogState, lock: Lock, diagnostics: &mut Vec<J>) -> J {
    let Some(limits) = state.limits() else {
        return if state.damaged() || state.accepted().is_some() {
            J::Str("unknown".into())
        } else {
            J::Null
        };
    };
    if state.damaged() {
        return unknown_usage(&limits);
    }
    #[cfg(feature = "claude-code")]
    if limits.harness.is_some() {
        let (used, problems) = crate::runs::cumulative_usage(audit, state, lock != Lock::Free);
        for problem in problems {
            diagnostics.push(J::obj().with("record", "runs").with("cause", problem));
        }
        return limits.allowances_j(&used);
    }
    let open = state.latest_placement().is_some_and(|p| p.ended.is_none());
    if open && lock == Lock::Unknown {
        diagnostics.push(J::obj().with("record", archive::LOCK_FILE).with(
            "cause", "Cumulative usage is unknown: whether the open placement's process is gone cannot be established, so its in-flight charge cannot be determined."));
        return unknown_usage(&limits);
    }
    let (used, problems) = crate::runs::cumulative_usage(audit, state, lock != Lock::Free);
    if !problems.is_empty() {
        for p in problems {
            diagnostics.push(J::obj().with("record", "runs").with(
                "cause", format!("Cumulative usage is unknown because an accounting record could not be read: {p}")));
        }
        return unknown_usage(&limits);
    }
    limits.allowances_j(&used)
}

/// Explain only exhaustion established by the same allowance observation the
/// reply presents. Unknown usage is not zero usage, and runtime placements do
/// not have Messages token or turn allowances.
pub fn request_unavailable(allowances: &J) -> Option<String> {
    let remaining = |key| {
        let allowance = allowances.get(key)?;
        match (allowance.get("used"), allowance.get("limit")) {
            (Some(J::Int(used)), Some(J::Int(limit))) => Some(limit.saturating_sub(*used)),
            _ => None,
        }
    };
    #[cfg(feature = "claude-code")]
    if remaining("placements") == Some(0) {
        return Some(PLACEMENTS_EXHAUSTED.into());
    }
    let reason = if remaining("turns") == Some(0) {
        "the turn allowance is exhausted".to_string()
    } else if remaining("input_tokens") == Some(0) {
        "the input token allowance is exhausted".to_string()
    } else if let Some(output) = remaining("output_tokens").filter(|n| *n < MIN_OUTPUT_FOR_REQUEST)
    {
        format!(
            "the output token allowance has {output} tokens remaining, fewer than the 1,024 required"
        )
    } else {
        return None;
    };
    Some(format!(
        "No further provider request can be sent: {reason}."
    ))
}

/// What may follow an interrupted placement, as status and run advise it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Continuation {
    /// Another placement may start under the same cumulative limits.
    Open,
    /// No further request can be sent, for the reason given; authoring stays
    /// open until close ends it.
    Unavailable(String),
    /// The final permitted placement ended, and authoring ended with it as
    /// `limit` (1.6): no placement start remains.
    PlacementsExhausted,
    /// A placement's stopping is unknown, so run and close would refuse
    /// until status observes its launched process groups absent.
    StopUnknown,
}

impl Continuation {
    /// The continuation an interrupted placement's advice offers, from the
    /// same observations the reply presents: the placements whose stopping
    /// is unknown, the authoring state and the allowances.
    pub fn of(state: &LogState, allowances: &J, stop_unknown: &StopUnknown) -> Continuation {
        if !stop_unknown.is_empty() {
            Continuation::StopUnknown
        } else if state
            .authoring_end()
            .is_some_and(|e| e.by == crate::log::EndedBy::Limit)
        {
            Continuation::PlacementsExhausted
        } else {
            match request_unavailable(allowances) {
                Some(reason) => Continuation::Unavailable(reason),
                None => Continuation::Open,
            }
        }
    }
    /// Whether advice offers `run`.
    pub fn may_run(&self) -> bool {
        *self == Continuation::Open
    }
}

pub fn interrupted_advice(run: u64, continuation: &Continuation) -> String {
    let action = match continuation {
        Continuation::Open => {
            " Run continues it under the same cumulative limits, or close ends authoring."
                .to_string()
        }
        Continuation::Unavailable(reason) => format!(
            " {reason} Close ends authoring and seals the recorded selection with manager attribution."
        ),
        Continuation::PlacementsExhausted => format!(
            " {PLACEMENTS_EXHAUSTED} Close seals the recorded selection with manager attribution."
        ),
        // The summary's stopping line says what waits and why.
        Continuation::StopUnknown => String::new(),
    };
    format!("Run {run} was interrupted; the answer is not submitted.{action}")
}

const PLACEMENTS_EXHAUSTED: &str =
    "No further runtime placement can start: the placement allowance is exhausted.";

/// The placements that make run and close refuse `runtime_stop_unknown`
/// (runtime contract, harness accounting record), by the check those
/// refusals use, so status and run replies offer neither while any remains.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct StopUnknown {
    /// Placements whose launched process groups were not observed absent.
    pub groups: Vec<u64>,
    /// Placements without a recorded ending whose runtime observations
    /// cannot be read.
    pub records: Vec<u64>,
}

impl StopUnknown {
    pub fn is_empty(&self) -> bool {
        self.groups.is_empty() && self.records.is_empty()
    }
    /// The summary lines naming each such placement and why.
    pub fn lines(&self) -> String {
        let mut lines = Vec::new();
        if !self.groups.is_empty() {
            lines.push(stop_unknown_line(&self.groups));
        }
        if !self.records.is_empty() {
            lines.push(unreadable_line(&self.records));
        }
        lines.join("\n")
    }
}

/// The placements that block a start and close cleanup. `live` is a
/// placement that may still be running under the active lock: its owner
/// observes its stopping, which is pending rather than unknown. The
/// Messages runtime launches no process groups.
pub fn stop_unknown(audit: &Audit, state: &LogState, live: Option<u64>) -> StopUnknown {
    #[cfg(feature = "claude-code")]
    {
        use crate::claude_code::accounting::{StopBlock, stop_block};
        let mut found = StopUnknown::default();
        for p in state
            .placements()
            .iter()
            .filter(|p| p.start.runtime.is_some() && Some(p.run) != live)
        {
            match stop_block(audit, p) {
                Some(StopBlock::Groups(_)) => found.groups.push(p.run),
                Some(StopBlock::Records(_)) => found.records.push(p.run),
                None => (),
            }
        }
        found
    }
    #[cfg(not(feature = "claude-code"))]
    {
        let _ = (audit, state, live);
        StopUnknown::default()
    }
}

/// The summary line naming each placement whose stopping is unknown.
pub fn stop_unknown_line(runs: &[u64]) -> String {
    let names: Vec<String> = runs.iter().map(u64::to_string).collect();
    let (placements, their) = if runs.len() == 1 {
        ("placement", "its")
    } else {
        ("placements", "their")
    };
    format!(
        "Stopping of {placements} {} is unknown: {their} launched process groups were not observed absent. Run and close would refuse runtime_stop_unknown until they are; status observes stopping again.",
        names.join(", ")
    )
}

/// The summary line naming each placement without a recorded ending whose
/// runtime observations cannot be read.
pub fn unreadable_line(runs: &[u64]) -> String {
    let names: Vec<String> = runs.iter().map(u64::to_string).collect();
    let (placements, has, their) = if runs.len() == 1 {
        ("Placement", "has", "its")
    } else {
        ("Placements", "have", "their")
    };
    format!(
        "{placements} {} {has} no recorded ending, and {their} runtime observations cannot be read. Run and close would refuse runtime_stop_unknown until they can; status reads them again.",
        names.join(", ")
    )
}

/// The one next call while stopping is unknown: status, which observes it
/// again.
pub fn observe_stopping_next(audit: &Audit) -> crate::reply::Next {
    crate::reply::Next::new(
        audit.argv(&["status", &audit.reference]),
        "Observe stopping again; once the launched process groups are observed absent and the runtime observations can be read, status offers run or close as the audit allows.",
    )
}

fn text(value: Option<&J>) -> &str {
    match value {
        Some(J::Str(s)) => s,
        _ => "unknown",
    }
}

/// A compact account whose facts remain independent. A known seal never implies
/// delivery, stopped execution, completed close, or intellectual adequacy.
pub fn summary(state: &LogState, headline: &J, allowances: &J) -> String {
    let mut lines = Vec::new();
    lines.push(
        match text(headline.get("accepted")) {
            "yes" => "Commission: accepted.",
            "no" => "Commission: not accepted.",
            _ => "Commission: acceptance is unknown.",
        }
        .to_string(),
    );
    if let Some(p) = state.latest_placement() {
        let prefix = if state.damaged() {
            "Last readable run"
        } else {
            "Run"
        };
        let ending = match p.ended {
            Some((_, e)) => match e.ending.as_str() {
                "sealed" => "ended after auditor submission".to_string(),
                "ended_unsubmitted" => "ended without auditor submission".to_string(),
                "limit_reached" => "stopped at the audit's limits".to_string(),
                "stopped_by_close" => "stopped after close was requested".to_string(),
                "damaged" => "stopped because recorded answer bytes were damaged".to_string(),
                "interrupted" => format!(
                    "was interrupted ({})",
                    e.cause.as_deref().unwrap_or("cause unknown")
                ),
                _ => "has an unknown ending".to_string(),
            },
            None => {
                "has no recorded ending; this alone does not establish whether it is still running"
                    .to_string()
            }
        };
        lines.push(format!("{prefix} {} {ending}.", p.run));
        if let Some((_, end)) = p.ended {
            lines.push(end.message.clone());
        }
    } else if state.damaged() {
        lines.push("Run: whether execution started is unknown.".into());
    } else {
        lines.push("Run: not started.".into());
    }
    match state.seal() {
        Some((_, seal)) => {
            let extra = if seal.actor.name() == "manager" {
                " The auditor did not submit it."
            } else {
                ""
            };
            lines.push(format!(
                "Answer: revision {} sealed by the {}.{extra}",
                seal.revision,
                seal.actor.name()
            ));
        }
        None if state.damaged() => lines.push("Answer: whether it is sealed is unknown.".into()),
        None if !state.launched() => {
            lines.push("Answer: no auditor answer has been created.".into())
        }
        None => lines.push(format!(
            "Answer: revision {}, {} recorded entries, unsealed.",
            state.revision(),
            state.selection().len()
        )),
    }
    if let Some(end) = state.authoring_end() {
        if end.by != crate::log::EndedBy::Seal {
            let reason = match end.by {
                crate::log::EndedBy::Close => "close was requested",
                crate::log::EndedBy::OrdinaryEnding => "the run ended without submission",
                crate::log::EndedBy::Limit => "an audit limit was reached",
                crate::log::EndedBy::Damage => "recorded answer bytes were damaged",
                crate::log::EndedBy::Seal => unreachable!(),
            };
            lines.push(format!("Authoring ended when {reason}."));
        }
    } else if state.damaged() {
        lines.push("Whether authoring has ended is unknown.".into());
    }
    if state.damaged() {
        lines.push("Delivery: its current verification and placement cannot be established from the damaged log.".into());
    } else {
        let deliveries = state.deliveries();
        match deliveries.last() {
            Some(d) => {
                let outcome = match d.outcome() {
                    Some("verified") => "verified",
                    Some("verified_with_losses") => {
                        "verified only for the supplied members, with named losses; this is not a complete delivery"
                    }
                    Some("partial") => "partial and not verified as complete",
                    Some("failed" | "name_taken") => "failed",
                    _ => "without a recorded outcome",
                };
                let location = d
                    .ended
                    .and_then(|(_, e)| e.package.as_deref())
                    .map(|p| format!(" at {p}"))
                    .unwrap_or_default();
                lines.push(format!(
                    "Delivery: attempt {} is {outcome}{location}.",
                    d.attempt
                ));
            }
            None => lines.push("Delivery: no attempt is recorded.".into()),
        }
    }
    if let Some(closed) = state.closed().and_then(|c| c.closed_body()) {
        match &closed.after {
            None => {
                lines.push("Audit: closed before launch; no auditor return was created.".into())
            }
            Some(after) => {
                let placement = if after.placement == "delivered_before_close" {
                    "Ordinary close confirmed placement of the copy delivered before close was requested."
                } else {
                    "Placement of the delivered copy was explicitly confirmed."
                };
                let losses = if after.surrendered.is_empty() {
                    ""
                } else {
                    " Named losses were explicitly surrendered; closure does not establish complete delivery."
                };
                lines.push(format!("Audit: closed. {placement}{losses}"));
            }
        }
    } else if state.damaged() {
        lines.push("Audit: completed closure cannot be established.".into());
    } else if state.close_requested().is_some() {
        lines.push("Audit: close was requested and remains unfinished. Follow the supplied continuation and confirmation requirements.".into());
    } else {
        lines.push("Audit: open.".into());
        if state
            .newest_verified()
            .is_some_and(|d| d.outcome() == Some("verified"))
        {
            lines.push("Ordinary close can settle placement of the already-delivered copy; no confirmation token is required for that path.".into());
        }
    }
    #[cfg(feature = "claude-code")]
    if matches!(allowances.get("runtime"), Some(J::Str(s)) if s == "claude-code/1") {
        lines.extend(runtime_lines(allowances));
        return lines.join("\n");
    }
    if let J::Obj(dimensions) = allowances {
        let mut usage = Vec::new();
        for (name, dimension) in dimensions {
            let show = |key| match dimension.get(key) {
                Some(J::Int(n)) => n.to_string(),
                _ => "unknown".to_string(),
            };
            usage.push(format!(
                "{name} {}/{} (reported {}; estimated {})",
                show("used"),
                show("limit"),
                show("reported"),
                show("estimated")
            ));
        }
        lines.push(format!("Cumulative usage / limits: {}.", usage.join(", ")));
    } else if !matches!(allowances, J::Null) {
        lines.push("Cumulative usage and limits are unknown.".into());
    }
    lines.join("\n")
}

/// The summary's account of a runtime audit's allowances: placement starts
/// with the per-placement deadline, then what usage and stopping were
/// observed. The runtime contract states the facts these lines carry.
#[cfg(feature = "claude-code")]
fn runtime_lines(allowances: &J) -> Vec<String> {
    let mut lines = Vec::new();
    let slots = allowances.get("placements");
    let count = |key| match slots.and_then(|s| s.get(key)) {
        Some(J::Int(n)) => n.to_string(),
        _ => "unknown".into(),
    };
    // Number agreement: exactly one takes the singular; zero, several and
    // an unknown count take the plural.
    let one = |n: &str| n == "1";
    let remaining = count("remaining");
    let timeout = match allowances.get("placement_timeout_seconds") {
        Some(J::Int(n)) => n.to_string(),
        _ => "unknown".into(),
    };
    lines.push(format!(
        "Placement starts: {} used of {}; {} {}. Each placement has a deadline of {} {}. Token reports cover the observed harness main loop only; provider completeness is unverified.",
        count("used"),
        count("limit"),
        remaining,
        if one(&remaining) { "remains" } else { "remain" },
        timeout,
        if one(&timeout) { "second" } else { "seconds" },
    ));
    if let Some(usage) = allowances.get("usage") {
        let count = |key| match usage.get(key) {
            Some(J::Int(n)) => n.to_string(),
            _ => "unknown".into(),
        };
        let placements = |n: &str| if one(n) { "placement" } else { "placements" };
        let have = |n: &str| if one(n) { "has" } else { "have" };
        let (reported, uncovered, stopped) = (
            count("reported_placements"),
            count("unknown_intervals"),
            count("stopped"),
        );
        lines.push(format!(
            "Usage: {reported} {} {} a reported checkpoint; {uncovered} {} {} an uncovered interval. Stopping was observed for {stopped} {}.",
            placements(&reported),
            have(&reported),
            placements(&uncovered),
            have(&uncovered),
            placements(&stopped),
        ));
    }
    lines
}

#[cfg(test)]
mod allowance_tests {
    use super::*;

    #[test]
    fn unknown_usage_does_not_establish_request_exhaustion() {
        let limits = Limits {
            #[cfg(feature = "claude-code")]
            harness: None,
            turns: 4,
            input_tokens: 1_000,
            output_tokens: 16_000,
        };
        assert!(request_unavailable(&unknown_usage(&limits)).is_none());
        assert!(request_unavailable(&J::Str("unknown".into())).is_none());
        assert!(request_unavailable(&J::Null).is_none());
    }

    /// Advice reads the allowances a reply presents, while the placement
    /// stops by `Limits::exhausted`. At every allowance boundary the two
    /// agree, estimated charges count as used, and the advice names the
    /// allowance that stops the next request.
    #[test]
    fn request_advice_agrees_with_the_stop_rule_at_each_boundary() {
        use crate::usage::Usage;
        let limits = Limits {
            #[cfg(feature = "claude-code")]
            harness: None,
            turns: 4,
            input_tokens: 1_000,
            output_tokens: 16_000,
        };
        let used = |turns, input, output, estimated_output| {
            let mut u = Usage::default();
            u.turns.reported = turns;
            u.input_tokens.reported = input;
            u.output_tokens.reported = output;
            u.output_tokens.estimated = estimated_output;
            u
        };
        let output = |n: u64| {
            format!(
                "the output token allowance has {n} tokens remaining, fewer than the 1,024 required"
            )
        };
        let turns = "the turn allowance is exhausted".to_string();
        let input = "the input token allowance is exhausted".to_string();
        for (label, u, reason) in [
            ("sufficient", used(1, 100, 8_000, 0), None),
            ("output 1,024", used(1, 100, 14_976, 0), None),
            ("output 1,023", used(1, 100, 14_977, 0), Some(output(1_023))),
            ("output zero", used(1, 100, 16_000, 0), Some(output(0))),
            (
                "estimated output",
                used(1, 100, 8_000, 8_000),
                Some(output(0)),
            ),
            ("turns zero", used(4, 100, 100, 0), Some(turns.clone())),
            ("input zero", used(1, 1_000, 100, 0), Some(input.clone())),
            (
                "input exceeded",
                used(1, 1_001, 100, 0),
                Some(input.clone()),
            ),
        ] {
            let advice = request_unavailable(&limits.allowances_j(&u));
            assert_eq!(
                advice,
                reason.map(|r| format!("No further provider request can be sent: {r}.")),
                "{label}"
            );
            assert_eq!(advice.is_some(), limits.exhausted(&u), "{label}");
        }
    }

    #[test]
    fn interrupted_advice_follows_what_may_continue() {
        let advice = |c: Continuation| interrupted_advice(3, &c);
        let head = "Run 3 was interrupted; the answer is not submitted.";
        assert_eq!(
            advice(Continuation::Open),
            format!(
                "{head} Run continues it under the same cumulative limits, or close ends authoring."
            )
        );
        assert_eq!(
            advice(Continuation::Unavailable("No turn remains.".into())),
            format!(
                "{head} No turn remains. Close ends authoring and seals the recorded selection with manager attribution."
            )
        );
        // Authoring has already ended, so close only seals.
        assert_eq!(
            advice(Continuation::PlacementsExhausted),
            format!(
                "{head} No further runtime placement can start: the placement allowance is exhausted. Close seals the recorded selection with manager attribution."
            )
        );
        // The stopping line names what waits; the advice offers nothing.
        assert_eq!(advice(Continuation::StopUnknown), head);
        assert!(Continuation::Open.may_run());
        for c in [
            Continuation::Unavailable(String::new()),
            Continuation::PlacementsExhausted,
            Continuation::StopUnknown,
        ] {
            assert!(!c.may_run(), "{c:?}");
        }
    }

    #[test]
    fn the_stopping_line_names_each_placement_in_number() {
        assert_eq!(
            stop_unknown_line(&[2]),
            "Stopping of placement 2 is unknown: its launched process groups were not observed absent. Run and close would refuse runtime_stop_unknown until they are; status observes stopping again."
        );
        assert!(
            stop_unknown_line(&[1, 3]).starts_with(
                "Stopping of placements 1, 3 is unknown: their launched process groups"
            )
        );
        assert_eq!(
            unreadable_line(&[2]),
            "Placement 2 has no recorded ending, and its runtime observations cannot be read. Run and close would refuse runtime_stop_unknown until they can; status reads them again."
        );
        let both = StopUnknown {
            groups: vec![1],
            records: vec![2],
        };
        assert_eq!(
            both.lines(),
            format!("{}\n{}", stop_unknown_line(&[1]), unreadable_line(&[2]))
        );
        assert!(StopUnknown::default().is_empty() && !both.is_empty());
    }
}

#[cfg(all(test, feature = "claude-code"))]
mod tests {
    use super::*;

    fn allowances(used: u64, limit: u64, timeout: u64, usage: Option<[u64; 3]>) -> J {
        let mut a = J::obj()
            .with("runtime", "claude-code/1")
            .with(
                "placements",
                J::obj()
                    .with("used", used)
                    .with("limit", limit)
                    .with("remaining", limit - used),
            )
            .with("placement_timeout_seconds", timeout);
        match usage {
            Some([reported, uncovered, stopped]) => a.push(
                "usage",
                J::obj()
                    .with("reported_placements", reported)
                    .with("unknown_intervals", uncovered)
                    .with("stopped", stopped),
            ),
            None => a.push("usage", "unknown"),
        }
        a
    }

    #[test]
    fn the_summary_states_the_deadline_and_agrees_in_number() {
        // Runtime placement accounting has its own continuation rule; Messages
        // token thresholds must not reinterpret it.
        assert!(
            request_unavailable(&allowances(2, 2, 600, Some([2, 0, 2])))
                .unwrap()
                .contains("placement allowance is exhausted")
        );
        assert!(request_unavailable(&allowances(1, 2, 600, None)).is_none());
        let lines = runtime_lines(&allowances(1, 2, 600, Some([1, 0, 1])));
        assert_eq!(lines.len(), 2);
        assert!(lines[0].contains("1 used of 2; 1 remains."), "{}", lines[0]);
        assert!(lines[0].contains("600 seconds"), "{}", lines[0]);
        assert!(
            lines[1].contains("1 placement has a reported checkpoint")
                && lines[1].contains("0 placements have an uncovered interval")
                && lines[1].ends_with("observed for 1 placement."),
            "{}",
            lines[1]
        );
        let lines = runtime_lines(&allowances(2, 4, 1, Some([2, 1, 0])));
        assert!(lines[0].contains("2 used of 4; 2 remain."), "{}", lines[0]);
        assert!(lines[0].contains("1 second."), "{}", lines[0]);
        assert!(
            lines[1].contains("2 placements have a reported checkpoint")
                && lines[1].contains("1 placement has an uncovered interval")
                && lines[1].ends_with("observed for 0 placements."),
            "{}",
            lines[1]
        );
        // An unknown count is not presented as one.
        let unknown = J::obj()
            .with("runtime", "claude-code/1")
            .with(
                "placements",
                J::obj()
                    .with("used", "unknown")
                    .with("limit", 3u64)
                    .with("remaining", "unknown"),
            )
            .with("placement_timeout_seconds", 60u64)
            .with("usage", "unknown");
        let lines = runtime_lines(&unknown);
        assert!(
            lines[0].contains("unknown used of 3; unknown remain."),
            "{}",
            lines[0]
        );
        assert!(lines[0].contains("60 seconds"));
        assert!(lines[1].contains("unknown placements have"), "{}", lines[1]);
    }
}
