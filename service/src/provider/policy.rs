//! Retry decisions and the step after a response (INTERFACE 6.3, 6.5, 6.6).
//!
//! These are pure: the loop supplies the attempt's outcome, status and
//! headers, the attempt number and the state of the limits and notices, and
//! acts on the decision. Waiting, checking the limits again after a delay and
//! watching for close are the loop's.

use crate::provider::response::StopReason;
use crate::provider::{Cause, Ending, Outcome};

/// HTTP statuses retried (6.6).
pub const RETRYABLE_STATUSES: [u16; 7] = [408, 429, 500, 502, 503, 504, 529];

/// The retry policy pinned in the arrangement (`retry`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RetryPolicy {
    /// Attempts per request, the first included.
    pub attempts: u32,
    /// The delay before attempt 2, 3, … in milliseconds; `attempts - 1` values.
    pub delays_ms: Vec<u64>,
    /// A `retry-after` above this many seconds is not waited for.
    pub retry_after_ceiling_seconds: u64,
}

impl Default for RetryPolicy {
    /// 4 attempts; 2, 8 and 30 seconds; a 60-second ceiling (Appendix B).
    fn default() -> RetryPolicy {
        RetryPolicy {
            attempts: 4,
            delays_ms: vec![2_000, 8_000, 30_000],
            retry_after_ceiling_seconds: 60,
        }
    }
}

impl RetryPolicy {
    /// The policy with a test build's delays in place of the pinned ones; a
    /// `retry-after` value still applies.
    pub fn with_delays_ms(mut self, delays: [u64; 3]) -> RetryPolicy {
        self.delays_ms = delays.to_vec();
        self
    }
}

/// A test build's retry delays: three comma-separated whole numbers of
/// milliseconds, each 0–30,000 (Appendix C).
#[cfg(feature = "fault-injection")]
pub fn parse_test_delays(v: &str) -> Result<[u64; 3], String> {
    let bad = || {
        format!(
            "the test retry delays {v:?} are not three comma-separated milliseconds from 0 to 30000"
        )
    };
    let parts: Vec<&str> = v.split(',').collect();
    if parts.len() != 3 {
        return Err(bad());
    }
    let mut out = [0u64; 3];
    for (slot, p) in out.iter_mut().zip(parts) {
        if p.is_empty() || p.len() > 5 || !p.bytes().all(|c| c.is_ascii_digit()) {
            return Err(bad());
        }
        let n: u64 = p.parse().map_err(|_| bad())?;
        if n > 30_000 {
            return Err(bad());
        }
        *slot = n;
    }
    Ok(out)
}

/// The `retry-after` header's first value as whole seconds, when it is a
/// decimal integer; any other form is ignored. A value too large for 64 bits
/// counts as the largest one, so it is over any ceiling.
pub fn retry_after_seconds(values: &[String]) -> Option<u64> {
    let v = values.first()?;
    if v.is_empty() || !v.bytes().all(|c| c.is_ascii_digit()) {
        return None;
    }
    Some(v.parse().unwrap_or(u64::MAX))
}

/// What follows an attempt (the attempt record's `then`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Then {
    /// The response is used.
    Use,
    /// Another attempt follows after `delay_ms`.
    Retry { delay_ms: u64 },
    /// The placement ends.
    End(Ending),
}

impl Then {
    pub fn as_str(self) -> &'static str {
        match self {
            Then::Use => "use",
            Then::Retry { .. } => "retry",
            Then::End(_) => "end",
        }
    }

    /// The attempt record's `delay_ms`: set only for a retry.
    pub fn delay_ms(self) -> Option<u64> {
        match self {
            Then::Retry { delay_ms } => Some(delay_ms),
            _ => None,
        }
    }
}

/// Decide after attempt `attempt` (counted from 1) of a request.
///
/// - `response`: use it.
/// - `response_undecodable`: end `interrupted` (`protocol_anomaly`).
/// - `http_error` with a status other than 408, 429, 500, 502, 503, 504 and
///   529: end `interrupted` (`provider_rejected`).
/// - `aborted_by_close`: end `stopped_by_close`; `aborted_by_signal`: end
///   `interrupted` (`signal`).
/// - Otherwise the outcome is retryable: on the last attempt, or when the
///   first `retry-after` value is a decimal integer over the ceiling, end
///   `interrupted` (`provider_unavailable`); else retry after that value, or
///   after the policy's delay for this attempt when there is none.
pub fn decide(
    outcome: Outcome,
    status: Option<u16>,
    retry_after: &[String],
    attempt: u32,
    policy: &RetryPolicy,
) -> Then {
    match outcome {
        Outcome::Response => return Then::Use,
        Outcome::ResponseUndecodable => {
            return Then::End(Ending::Interrupted(Cause::ProtocolAnomaly));
        }
        Outcome::HttpError => {
            if !status.is_some_and(|s| RETRYABLE_STATUSES.contains(&s)) {
                return Then::End(Ending::Interrupted(Cause::ProviderRejected));
            }
        }
        Outcome::AbortedByClose => return Then::End(Ending::StoppedByClose),
        Outcome::AbortedBySignal => return Then::End(Ending::Interrupted(Cause::Signal)),
        Outcome::Timeout | Outcome::ConnectionFailed | Outcome::ConnectionLost => {}
    }
    let unavailable = Then::End(Ending::Interrupted(Cause::ProviderUnavailable));
    if attempt >= policy.attempts {
        return unavailable;
    }
    let delay_ms = match retry_after_seconds(retry_after) {
        Some(s) if s > policy.retry_after_ceiling_seconds => return unavailable,
        Some(s) => s.saturating_mul(1000),
        None => match policy.delays_ms.get(attempt.saturating_sub(1) as usize) {
            Some(d) => *d,
            // A policy with fewer delays than attempts cannot retry further.
            None => return unavailable,
        },
    };
    Then::Retry { delay_ms }
}

/// What the loop does after executing a used response's blocks (6.3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Next {
    /// Send the tool results (and any pending notice) in the next request.
    SendResults,
    /// Publish the reminder notice, then send it in the next request with
    /// the response's tool results, if any, and any pending notice.
    SendReminder,
    /// End the placement. For `sealed`, the run delivers first.
    End(Ending),
}

/// The step after a response whose blocks were all executed.
///
/// `sealed`: a seal was recorded during this response. `has_tool_use`: the
/// response had a `tool_use` block. `exhausted`: a limit is exhausted after
/// this response was accounted. `reminder_used`: the audit's reminder was
/// already sent or planned. Early stops during execution (an unanswerable
/// block, `record_failed`, damage, the stop path) end the placement before
/// this is consulted.
pub fn after_response(
    stop: &StopReason,
    has_tool_use: bool,
    sealed: bool,
    exhausted: bool,
    reminder_used: bool,
) -> Next {
    if sealed {
        return Next::End(Ending::Sealed);
    }
    let anomaly = Next::End(Ending::Interrupted(Cause::ProtocolAnomaly));
    match stop {
        StopReason::ToolUse if has_tool_use => Next::SendResults,
        StopReason::ToolUse => anomaly,
        StopReason::EndTurn | StopReason::StopSequence => {
            if exhausted {
                Next::End(Ending::LimitReached)
            } else if !reminder_used {
                Next::SendReminder
            } else {
                Next::End(Ending::EndedUnsubmitted)
            }
        }
        StopReason::MaxTokens if has_tool_use => Next::SendResults,
        StopReason::MaxTokens => Next::End(Ending::Interrupted(Cause::MaxTokens)),
        StopReason::ModelContextWindowExceeded => {
            Next::End(Ending::Interrupted(Cause::ContextExhausted))
        }
        StopReason::Refusal => Next::End(Ending::Interrupted(Cause::ProviderRefusal)),
        StopReason::PauseTurn | StopReason::Other(_) => anomaly,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ra(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    const UNAVAILABLE: Then = Then::End(Ending::Interrupted(Cause::ProviderUnavailable));

    #[test]
    fn retry_after_parsing() {
        assert_eq!(retry_after_seconds(&ra(&["5"])), Some(5));
        assert_eq!(retry_after_seconds(&ra(&["0"])), Some(0));
        assert_eq!(retry_after_seconds(&ra(&["007"])), Some(7));
        assert_eq!(retry_after_seconds(&ra(&["5", "99"])), Some(5));
        assert_eq!(
            retry_after_seconds(&ra(&["99999999999999999999999"])),
            Some(u64::MAX)
        );
        for ignored in [
            "",
            "1.5",
            "-1",
            "+3",
            "5s",
            "Wed, 21 Oct 2026 07:28:00 GMT",
            "%C3%A9",
        ] {
            assert_eq!(retry_after_seconds(&ra(&[ignored])), None, "{ignored:?}");
        }
        // Only the first value counts, even when a later one is usable.
        assert_eq!(retry_after_seconds(&ra(&["soon", "5"])), None);
        assert_eq!(retry_after_seconds(&[]), None);
    }

    #[test]
    fn retryable_outcomes_wait_the_pinned_delays() {
        let p = RetryPolicy::default();
        for o in [
            Outcome::Timeout,
            Outcome::ConnectionFailed,
            Outcome::ConnectionLost,
        ] {
            assert_eq!(decide(o, None, &[], 1, &p), Then::Retry { delay_ms: 2_000 });
            assert_eq!(decide(o, None, &[], 2, &p), Then::Retry { delay_ms: 8_000 });
            assert_eq!(
                decide(o, None, &[], 3, &p),
                Then::Retry { delay_ms: 30_000 }
            );
            assert_eq!(decide(o, None, &[], 4, &p), UNAVAILABLE);
        }
        for s in RETRYABLE_STATUSES {
            assert_eq!(
                decide(Outcome::HttpError, Some(s), &[], 1, &p),
                Then::Retry { delay_ms: 2_000 },
                "{s}"
            );
            assert_eq!(decide(Outcome::HttpError, Some(s), &[], 4, &p), UNAVAILABLE);
        }
    }

    #[test]
    fn retry_after_replaces_the_delay_up_to_the_ceiling() {
        let p = RetryPolicy::default();
        let d = |v: &str, attempt| decide(Outcome::HttpError, Some(529), &ra(&[v]), attempt, &p);
        assert_eq!(d("0", 1), Then::Retry { delay_ms: 0 });
        assert_eq!(d("60", 2), Then::Retry { delay_ms: 60_000 });
        assert_eq!(d("61", 1), UNAVAILABLE);
        assert_eq!(d("later", 3), Then::Retry { delay_ms: 30_000 });
        // The last attempt ends whatever the header says.
        assert_eq!(d("0", 4), UNAVAILABLE);
    }

    #[test]
    fn other_outcomes_end_or_use() {
        let p = RetryPolicy::default();
        assert_eq!(decide(Outcome::Response, Some(200), &[], 1, &p), Then::Use);
        assert_eq!(
            decide(Outcome::ResponseUndecodable, Some(200), &[], 1, &p),
            Then::End(Ending::Interrupted(Cause::ProtocolAnomaly))
        );
        for s in [400, 401, 403, 404, 413, 422, 201, 301, 501, 505] {
            assert_eq!(
                decide(Outcome::HttpError, Some(s), &ra(&["1"]), 1, &p),
                Then::End(Ending::Interrupted(Cause::ProviderRejected)),
                "{s}"
            );
        }
        assert_eq!(
            decide(Outcome::AbortedByClose, None, &[], 1, &p),
            Then::End(Ending::StoppedByClose)
        );
        assert_eq!(
            decide(Outcome::AbortedBySignal, None, &[], 1, &p),
            Then::End(Ending::Interrupted(Cause::Signal))
        );
    }

    #[test]
    fn then_values() {
        assert_eq!(Then::Use.as_str(), "use");
        assert_eq!(Then::Use.delay_ms(), None);
        assert_eq!(Then::Retry { delay_ms: 5 }.as_str(), "retry");
        assert_eq!(Then::Retry { delay_ms: 5 }.delay_ms(), Some(5));
        assert_eq!(UNAVAILABLE.as_str(), "end");
        assert_eq!(UNAVAILABLE.delay_ms(), None);
    }

    #[test]
    fn test_delays_replace_the_pinned_ones() {
        let p = RetryPolicy::default().with_delays_ms([0, 10, 20]);
        assert_eq!(
            decide(Outcome::Timeout, None, &[], 1, &p),
            Then::Retry { delay_ms: 0 }
        );
        assert_eq!(
            decide(Outcome::Timeout, None, &[], 3, &p),
            Then::Retry { delay_ms: 20 }
        );
        assert_eq!(
            decide(Outcome::HttpError, Some(503), &ra(&["2"]), 1, &p),
            Then::Retry { delay_ms: 2_000 }
        );
    }

    #[cfg(feature = "fault-injection")]
    #[test]
    fn test_delay_values() {
        assert_eq!(parse_test_delays("0,10,30000").unwrap(), [0, 10, 30_000]);
        for bad in [
            "",
            "1,2",
            "1,2,3,4",
            "1,2,30001",
            "1, 2,3",
            "a,b,c",
            "-1,2,3",
            "1,,3",
        ] {
            assert!(parse_test_delays(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn the_step_after_each_stop_reason() {
        use Next::*;
        let anomaly = End(Ending::Interrupted(Cause::ProtocolAnomaly));
        let s = |r: StopReason, tools: bool| after_response(&r, tools, false, false, false);
        assert_eq!(s(StopReason::ToolUse, true), SendResults);
        assert_eq!(s(StopReason::ToolUse, false), anomaly);
        assert_eq!(s(StopReason::MaxTokens, true), SendResults);
        assert_eq!(
            s(StopReason::MaxTokens, false),
            End(Ending::Interrupted(Cause::MaxTokens))
        );
        assert_eq!(
            s(StopReason::ModelContextWindowExceeded, true),
            End(Ending::Interrupted(Cause::ContextExhausted))
        );
        assert_eq!(
            s(StopReason::Refusal, false),
            End(Ending::Interrupted(Cause::ProviderRefusal))
        );
        assert_eq!(s(StopReason::PauseTurn, false), anomaly);
        assert_eq!(s(StopReason::Other("new".into()), true), anomaly);
        for r in [StopReason::EndTurn, StopReason::StopSequence] {
            for tools in [false, true] {
                assert_eq!(after_response(&r, tools, false, false, false), SendReminder);
                assert_eq!(
                    after_response(&r, tools, false, false, true),
                    End(Ending::EndedUnsubmitted)
                );
                assert_eq!(
                    after_response(&r, tools, false, true, false),
                    End(Ending::LimitReached)
                );
                assert_eq!(
                    after_response(&r, tools, false, true, true),
                    End(Ending::LimitReached)
                );
            }
        }
        // A seal recorded during the response ends it sealed whatever the stop reason.
        for r in [
            StopReason::ToolUse,
            StopReason::EndTurn,
            StopReason::Refusal,
            StopReason::PauseTurn,
        ] {
            assert_eq!(
                after_response(&r, true, true, true, true),
                End(Ending::Sealed)
            );
        }
    }
}
