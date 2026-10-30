//! Charges, usage, limits and the near-limit notice (INTERFACE 6.4).
//!
//! Every attempt states its charge. A response is charged what the provider
//! reported. An attempt that may have been processed without Stewart seeing
//! the report is charged an estimate: one turn, the request's `max_tokens`
//! output tokens and ceil(body bytes / 3) input tokens. Reported and estimated
//! usage are kept apart; a limit counts their sum.

use crate::json::J;
use crate::provider::Outcome;
use crate::provider::response::Usage;
use crate::provider::transport::Written;

/// Fewer output tokens than this remaining exhausts the output allowance.
pub const MIN_OUTPUT_FOR_REQUEST: u64 = 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Basis {
    Reported,
    Estimated,
    None,
}

impl Basis {
    pub fn as_str(self) -> &'static str {
        match self {
            Basis::Reported => "reported",
            Basis::Estimated => "estimated",
            Basis::None => "none",
        }
    }
}

/// What one attempt adds to the allowances.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Charge {
    pub basis: Basis,
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl Charge {
    pub const NONE: Charge = Charge {
        basis: Basis::None,
        turns: 0,
        input_tokens: 0,
        output_tokens: 0,
    };

    /// The provider's report: one turn, input plus both cache counts, output.
    pub fn reported(u: &Usage) -> Charge {
        Charge {
            basis: Basis::Reported,
            turns: 1,
            input_tokens: u.input_charge(),
            output_tokens: u.output_tokens,
        }
    }

    /// The estimate for a request that may have been processed unseen. It is
    /// also what a dead placement is charged for each complete request
    /// capture whose latest attempt has no record.
    pub fn estimated(body_bytes: u64, max_tokens: u64) -> Charge {
        Charge {
            basis: Basis::Estimated,
            turns: 1,
            input_tokens: body_bytes.div_ceil(3),
            output_tokens: max_tokens,
        }
    }

    /// The attempt record's `charged`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("basis", self.basis.as_str())
            .with("turns", self.turns)
            .with("input_tokens", self.input_tokens)
            .with("output_tokens", self.output_tokens)
    }
}

/// The charge for an attempt (6.4's table). `usage` is the decoded message's
/// report, needed only for `response`.
pub fn charge(
    outcome: Outcome,
    written: Written,
    usage: Option<&Usage>,
    body_bytes: u64,
    max_tokens: u64,
) -> Charge {
    match outcome {
        Outcome::Response => match usage {
            Some(u) => Charge::reported(u),
            // A response always carries its decoded usage; without it the
            // request may still have been processed, so it is estimated.
            None => Charge::estimated(body_bytes, max_tokens),
        },
        Outcome::ResponseUndecodable | Outcome::ConnectionLost => {
            Charge::estimated(body_bytes, max_tokens)
        }
        Outcome::Timeout | Outcome::AbortedByClose | Outcome::AbortedBySignal => {
            if written == Written::None {
                Charge::NONE
            } else {
                Charge::estimated(body_bytes, max_tokens)
            }
        }
        Outcome::HttpError | Outcome::ConnectionFailed => Charge::NONE,
    }
}

/// One allowance's usage, split by basis.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Split {
    pub reported: u64,
    pub estimated: u64,
}

impl Split {
    /// What a limit counts: reported plus estimated.
    pub fn total(self) -> u64 {
        self.reported.saturating_add(self.estimated)
    }

    pub fn to_j(self) -> J {
        J::obj()
            .with("reported", self.reported)
            .with("estimated", self.estimated)
    }
}

/// Usage across the three allowances: a placement's, or cumulative.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Tally {
    pub turns: Split,
    pub input_tokens: Split,
    pub output_tokens: Split,
}

impl Tally {
    pub fn add(&mut self, c: &Charge) {
        let slot = |s: &mut Split, n: u64| match c.basis {
            Basis::Reported => s.reported = s.reported.saturating_add(n),
            Basis::Estimated => s.estimated = s.estimated.saturating_add(n),
            Basis::None => {}
        };
        slot(&mut self.turns, c.turns);
        slot(&mut self.input_tokens, c.input_tokens);
        slot(&mut self.output_tokens, c.output_tokens);
    }

    /// The sum of two tallies, such as earlier placements and this one.
    pub fn plus(&self, o: &Tally) -> Tally {
        let s = |a: Split, b: Split| Split {
            reported: a.reported.saturating_add(b.reported),
            estimated: a.estimated.saturating_add(b.estimated),
        };
        Tally {
            turns: s(self.turns, o.turns),
            input_tokens: s(self.input_tokens, o.input_tokens),
            output_tokens: s(self.output_tokens, o.output_tokens),
        }
    }

    /// `{"turns":{"reported":…,"estimated":…},"input_tokens":{…},"output_tokens":{…}}`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("turns", self.turns.to_j())
            .with("input_tokens", self.input_tokens.to_j())
            .with("output_tokens", self.output_tokens.to_j())
    }
}

/// The audit's cumulative limits (front matter, pinned in the arrangement).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Limits {
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

/// max(0, limit − used) for each allowance.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Remaining {
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl Remaining {
    /// The `notice` record's `remaining`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("turns", self.turns)
            .with("input_tokens", self.input_tokens)
            .with("output_tokens", self.output_tokens)
    }
}

/// Which limits are exhausted.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Exhaustion {
    /// No turn remains.
    pub turns: bool,
    /// The input allowance is used up.
    pub input_tokens: bool,
    /// Fewer than 1,024 output tokens remain.
    pub output_tokens: bool,
}

impl Exhaustion {
    pub fn any(self) -> bool {
        self.turns || self.input_tokens || self.output_tokens
    }
}

impl Limits {
    pub fn remaining(&self, used: &Tally) -> Remaining {
        Remaining {
            turns: self.turns.saturating_sub(used.turns.total()),
            input_tokens: self.input_tokens.saturating_sub(used.input_tokens.total()),
            output_tokens: self
                .output_tokens
                .saturating_sub(used.output_tokens.total()),
        }
    }

    /// The exhaustion test before each request and retry.
    pub fn exhaustion(&self, used: &Tally) -> Exhaustion {
        let r = self.remaining(used);
        Exhaustion {
            turns: r.turns == 0,
            input_tokens: r.input_tokens == 0,
            output_tokens: r.output_tokens < MIN_OUTPUT_FOR_REQUEST,
        }
    }

    pub fn exhausted(&self, used: &Tally) -> bool {
        self.exhaustion(used).any()
    }

    /// A request's `max_tokens`: the lesser of the per-request maximum and
    /// the remaining output allowance, fixed when the request is captured.
    pub fn max_tokens(&self, used: &Tally, per_request: u64) -> u64 {
        per_request.min(self.remaining(used).output_tokens)
    }

    /// Whether the near-limit notice triggers: for any allowance,
    /// remaining × 100 ≤ percent × limit.
    pub fn near_limit(&self, used: &Tally, percent: u64) -> bool {
        let r = self.remaining(used);
        let near =
            |remaining: u64, limit: u64| remaining as u128 * 100 <= percent as u128 * limit as u128;
        near(r.turns, self.turns)
            || near(r.input_tokens, self.input_tokens)
            || near(r.output_tokens, self.output_tokens)
    }
}

/// The near-limit notice text: the pinned template with `{turns}`,
/// `{input_tokens}` and `{output_tokens}` replaced by the remaining amounts
/// in decimal.
pub fn near_limit_text(template: &str, r: &Remaining) -> String {
    template
        .replace("{turns}", &r.turns.to_string())
        .replace("{input_tokens}", &r.input_tokens.to_string())
        .replace("{output_tokens}", &r.output_tokens.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    const LIMITS: Limits = Limits {
        turns: 200,
        input_tokens: 20_000_000,
        output_tokens: 400_000,
    };

    fn used(turns: u64, input: u64, output: u64) -> Tally {
        let mut t = Tally::default();
        t.add(&Charge {
            basis: Basis::Reported,
            turns,
            input_tokens: input,
            output_tokens: output,
        });
        t
    }

    #[test]
    fn charges_follow_the_table() {
        let u = Usage {
            input_tokens: 100,
            cache_creation_input_tokens: 20,
            cache_read_input_tokens: 3,
            output_tokens: 40,
        };
        let reported = Charge {
            basis: Basis::Reported,
            turns: 1,
            input_tokens: 123,
            output_tokens: 40,
        };
        // ceil(10 / 3) = 4.
        let estimated = Charge {
            basis: Basis::Estimated,
            turns: 1,
            input_tokens: 4,
            output_tokens: 16_000,
        };
        assert_eq!(
            charge(Outcome::Response, Written::Complete, Some(&u), 10, 16_000),
            reported
        );
        for o in [Outcome::ResponseUndecodable, Outcome::ConnectionLost] {
            for w in [Written::Partial, Written::Complete] {
                assert_eq!(charge(o, w, None, 10, 16_000), estimated, "{o:?}");
            }
        }
        for o in [
            Outcome::Timeout,
            Outcome::AbortedByClose,
            Outcome::AbortedBySignal,
        ] {
            assert_eq!(
                charge(o, Written::Partial, None, 10, 16_000),
                estimated,
                "{o:?}"
            );
            assert_eq!(
                charge(o, Written::Complete, None, 10, 16_000),
                estimated,
                "{o:?}"
            );
            assert_eq!(
                charge(o, Written::None, None, 10, 16_000),
                Charge::NONE,
                "{o:?}"
            );
        }
        for o in [Outcome::HttpError, Outcome::ConnectionFailed] {
            for w in [Written::None, Written::Partial, Written::Complete] {
                assert_eq!(charge(o, w, None, 10, 16_000), Charge::NONE, "{o:?}");
            }
        }
        assert_eq!(Charge::estimated(9, 1).input_tokens, 3);
        assert_eq!(Charge::estimated(0, 1).input_tokens, 0);
        assert_eq!(
            Charge::estimated(u64::MAX, 1).input_tokens,
            u64::MAX.div_ceil(3)
        );
        assert_eq!(
            estimated.to_j().string(),
            r#"{"basis":"estimated","turns":1,"input_tokens":4,"output_tokens":16000}"#
        );
        assert_eq!(
            Charge::NONE.to_j().string(),
            r#"{"basis":"none","turns":0,"input_tokens":0,"output_tokens":0}"#
        );
    }

    #[test]
    fn tallies_keep_bases_apart() {
        let mut t = Tally::default();
        t.add(&Charge::reported(&Usage {
            input_tokens: 10,
            output_tokens: 5,
            ..Usage::default()
        }));
        t.add(&Charge::estimated(30, 100));
        t.add(&Charge::NONE);
        assert_eq!(
            t.turns,
            Split {
                reported: 1,
                estimated: 1
            }
        );
        assert_eq!(
            t.input_tokens,
            Split {
                reported: 10,
                estimated: 10
            }
        );
        assert_eq!(t.output_tokens.total(), 105);
        let sum = t.plus(&t);
        assert_eq!(sum.turns.total(), 4);
        assert_eq!(
            t.to_j().string(),
            r#"{"turns":{"reported":1,"estimated":1},"input_tokens":{"reported":10,"estimated":10},"output_tokens":{"reported":5,"estimated":100}}"#
        );
    }

    #[test]
    fn exhaustion_edges() {
        assert!(!LIMITS.exhausted(&Tally::default()));
        // Turns: the last turn remains, then none.
        assert!(!LIMITS.exhausted(&used(199, 0, 0)));
        assert!(LIMITS.exhaustion(&used(200, 0, 0)).turns);
        assert!(LIMITS.exhaustion(&used(201, 0, 0)).turns);
        // Input: one token left is not used up; over by one is.
        assert!(!LIMITS.exhausted(&used(0, 19_999_999, 0)));
        let e = LIMITS.exhaustion(&used(0, 20_000_000, 0));
        assert!(e.input_tokens && !e.turns && !e.output_tokens);
        assert!(LIMITS.exhaustion(&used(0, 20_000_001, 0)).input_tokens);
        // Output: exactly 1,024 remaining still permits a request; 1,023 does not.
        assert!(!LIMITS.exhausted(&used(0, 0, 400_000 - 1024)));
        assert_eq!(LIMITS.max_tokens(&used(0, 0, 400_000 - 1024), 16_000), 1024);
        assert!(LIMITS.exhaustion(&used(0, 0, 400_000 - 1023)).output_tokens);
        // Estimates count toward the limits like reports.
        let mut t = Tally::default();
        t.add(&Charge::estimated(3, 400_000));
        assert!(LIMITS.exhaustion(&t).output_tokens);
        assert_eq!(LIMITS.remaining(&t).output_tokens, 0);
    }

    #[test]
    fn max_tokens_is_the_lesser() {
        assert_eq!(LIMITS.max_tokens(&Tally::default(), 16_000), 16_000);
        assert_eq!(LIMITS.max_tokens(&used(0, 0, 390_000), 16_000), 10_000);
        assert_eq!(LIMITS.max_tokens(&used(0, 0, 500_000), 16_000), 0);
    }

    #[test]
    fn near_limit_trigger_and_text() {
        // 20% of 200 turns is 40: 41 remaining does not trigger, 40 does.
        assert!(!LIMITS.near_limit(&used(159, 0, 0), 20));
        assert!(LIMITS.near_limit(&used(160, 0, 0), 20));
        // Any allowance triggers it.
        assert!(LIMITS.near_limit(&used(0, 16_000_000, 0), 20));
        assert!(!LIMITS.near_limit(&used(0, 15_999_999, 0), 20));
        assert!(LIMITS.near_limit(&used(0, 0, 320_000), 20));
        // Over the limit, remaining is 0.
        assert!(LIMITS.near_limit(&used(0, 30_000_000, 0), 20));
        // Large limits do not overflow.
        let big = Limits {
            turns: 10_000,
            input_tokens: 2_000_000_000,
            output_tokens: 200_000_000,
        };
        assert!(!big.near_limit(&Tally::default(), 20));
        assert!(!big.near_limit(&Tally::default(), 0));
        assert!(big.near_limit(&Tally::default(), 100));
        let r = LIMITS.remaining(&used(160, 16_100_000, 321_000));
        assert_eq!(
            r,
            Remaining {
                turns: 40,
                input_tokens: 3_900_000,
                output_tokens: 79_000
            }
        );
        assert_eq!(
            near_limit_text(crate::forms::NEAR_LIMIT, &r),
            "Allowance notice: 40 turns, 3900000 input tokens and 79000 output tokens remain for this audit. When an allowance runs out the run stops, and an unsubmitted answer stays unsubmitted."
        );
        assert_eq!(
            r.to_j().string(),
            r#"{"turns":40,"input_tokens":3900000,"output_tokens":79000}"#
        );
    }
}
