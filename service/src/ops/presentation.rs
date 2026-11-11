//! Read-only observations shared by manager replies. These are views of evidence,
//! not another lifecycle or a permission to continue work.

use super::status::Lock;
use crate::archive::{self, Audit};
use crate::json::J;
use crate::log::LogState;
use crate::usage::Limits;

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
