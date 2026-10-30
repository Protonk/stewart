//! Usage, charges and allowances (INTERFACE 6.4).
//!
//! Usage is kept in two parts for each of turns, input tokens and output
//! tokens: `reported`, what the provider's usage reports state, and
//! `estimated`, what Stewart charged for an attempt whose response it could
//! not use. They are never merged into one figure in a record or a reply; a
//! limit counts their sum. Totals are cumulative across every placement of an
//! audit: a continuing placement starts from the recorded totals, never from
//! zero.

use crate::json::{J, JsonError, Obj};

/// A request is not sent, and no retry either, when fewer output tokens than
/// this remain.
pub const MIN_OUTPUT_FOR_REQUEST: u64 = 1_024;

/// Upper bound for a decoded usage figure: generous, but small enough that
/// sums of every recorded figure cannot overflow `u64`.
pub const FIGURE_MAX: u64 = 1 << 48;

/// One quantity, reported and estimated kept apart.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Split {
    pub reported: u64,
    pub estimated: u64,
}

impl Split {
    /// What a limit counts: reported plus estimated.
    pub fn used(&self) -> u64 {
        self.reported.saturating_add(self.estimated)
    }
    pub fn add(&mut self, other: Split) {
        self.reported = self.reported.saturating_add(other.reported);
        self.estimated = self.estimated.saturating_add(other.estimated);
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("reported", self.reported)
            .with("estimated", self.estimated)
    }
    pub fn decode(o: &Obj) -> Result<Split, JsonError> {
        o.exactly(&["reported", "estimated"])?;
        Ok(Split {
            reported: o.u64("reported", FIGURE_MAX)?,
            estimated: o.u64("estimated", FIGURE_MAX)?,
        })
    }
}

/// Usage of a placement, or of the audit so far: `run_ended.usage` (4.4),
/// the `usage` of the run reply (5.7).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Usage {
    pub turns: Split,
    pub input_tokens: Split,
    pub output_tokens: Split,
}

impl Usage {
    pub fn add(&mut self, other: &Usage) {
        self.turns.add(other.turns);
        self.input_tokens.add(other.input_tokens);
        self.output_tokens.add(other.output_tokens);
    }
    /// Add one attempt's charge, on the side its basis names.
    pub fn charge(&mut self, c: &Charge) {
        let side = |n: u64| match c.basis {
            Basis::Reported => Split {
                reported: n,
                estimated: 0,
            },
            Basis::Estimated => Split {
                reported: 0,
                estimated: n,
            },
            Basis::None => Split::default(),
        };
        self.turns.add(side(c.turns));
        self.input_tokens.add(side(c.input_tokens));
        self.output_tokens.add(side(c.output_tokens));
    }
    /// `{"turns":{reported,estimated},"input_tokens":…,"output_tokens":…}`.
    pub fn to_j(&self) -> J {
        J::obj()
            .with("turns", self.turns.to_j())
            .with("input_tokens", self.input_tokens.to_j())
            .with("output_tokens", self.output_tokens.to_j())
    }
    pub fn decode(o: &Obj) -> Result<Usage, JsonError> {
        o.exactly(&["turns", "input_tokens", "output_tokens"])?;
        Ok(Usage {
            turns: Split::decode(&o.obj("turns")?)?,
            input_tokens: Split::decode(&o.obj("input_tokens")?)?,
            output_tokens: Split::decode(&o.obj("output_tokens")?)?,
        })
    }
}

/// The basis of an attempt's charge (`provider_attempt.charged.basis`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Basis {
    Reported,
    Estimated,
    None,
}

impl Basis {
    pub const NAMES: [&'static str; 3] = ["reported", "estimated", "none"];
    pub fn name(self) -> &'static str {
        match self {
            Basis::Reported => "reported",
            Basis::Estimated => "estimated",
            Basis::None => "none",
        }
    }
    pub fn parse(s: &str) -> Option<Basis> {
        match s {
            "reported" => Some(Basis::Reported),
            "estimated" => Some(Basis::Estimated),
            "none" => Some(Basis::None),
            _ => None,
        }
    }
}

/// What one provider attempt added to the allowances (`charged`, 4.5).
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
    /// A used response: one turn; input, cache-creation and cache-read input
    /// tokens together; the reported output tokens.
    pub fn reported(input: u64, cache_creation: u64, cache_read: u64, output: u64) -> Charge {
        Charge {
            basis: Basis::Reported,
            turns: 1,
            input_tokens: input
                .saturating_add(cache_creation)
                .saturating_add(cache_read),
            output_tokens: output,
        }
    }
    /// A response Stewart could not use after request bytes were written:
    /// one turn, the request's `max_tokens` output tokens and
    /// ceil(body bytes / 3) input tokens.
    pub fn estimated(max_tokens: u64, body_bytes: u64) -> Charge {
        Charge {
            basis: Basis::Estimated,
            turns: 1,
            input_tokens: body_bytes.div_ceil(3),
            output_tokens: max_tokens,
        }
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("basis", self.basis.name())
            .with("turns", self.turns)
            .with("input_tokens", self.input_tokens)
            .with("output_tokens", self.output_tokens)
    }
    pub fn decode(o: &Obj) -> Result<Charge, JsonError> {
        o.exactly(&["basis", "turns", "input_tokens", "output_tokens"])?;
        let basis = Basis::parse(o.one_of("basis", &Basis::NAMES)?).expect("one of the names");
        let c = Charge {
            basis,
            turns: o.u64("turns", FIGURE_MAX)?,
            input_tokens: o.u64("input_tokens", FIGURE_MAX)?,
            output_tokens: o.u64("output_tokens", FIGURE_MAX)?,
        };
        if basis == Basis::None && (c.turns, c.input_tokens, c.output_tokens) != (0, 0, 0) {
            return Err(o.invalid("basis", "a charge with basis none charges nothing"));
        }
        Ok(c)
    }
}

/// Remaining amounts, max(0, limit − used): the near-limit notice's template
/// values and its record's `remaining` (4.4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Remaining {
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl Remaining {
    pub fn to_j(&self) -> J {
        J::obj()
            .with("turns", self.turns)
            .with("input_tokens", self.input_tokens)
            .with("output_tokens", self.output_tokens)
    }
    pub fn decode(o: &Obj) -> Result<Remaining, JsonError> {
        o.exactly(&["turns", "input_tokens", "output_tokens"])?;
        Ok(Remaining {
            turns: o.u64("turns", FIGURE_MAX)?,
            input_tokens: o.u64("input_tokens", FIGURE_MAX)?,
            output_tokens: o.u64("output_tokens", FIGURE_MAX)?,
        })
    }
    /// The near-limit notice text: the pinned template with each value
    /// written as a decimal integer.
    pub fn fill(&self, template: &str) -> String {
        template
            .replace("{turns}", &self.turns.to_string())
            .replace("{input_tokens}", &self.input_tokens.to_string())
            .replace("{output_tokens}", &self.output_tokens.to_string())
    }
}

/// The audit's cumulative limits, from the accepted commission's front matter.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Limits {
    pub turns: u64,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl Limits {
    pub fn remaining(&self, used: &Usage) -> Remaining {
        Remaining {
            turns: self.turns.saturating_sub(used.turns.used()),
            input_tokens: self.input_tokens.saturating_sub(used.input_tokens.used()),
            output_tokens: self.output_tokens.saturating_sub(used.output_tokens.used()),
        }
    }
    /// A limit is exhausted, so no request or retry is sent, when no turn
    /// remains, the input allowance is used up or fewer than 1,024 output
    /// tokens remain.
    pub fn exhausted(&self, used: &Usage) -> bool {
        let r = self.remaining(used);
        r.turns == 0 || r.input_tokens == 0 || r.output_tokens < MIN_OUTPUT_FOR_REQUEST
    }
    /// The near-limit notice triggers when remaining × 100 ≤ percent × limit
    /// for any limit.
    pub fn near_limit(&self, used: &Usage, percent: u64) -> bool {
        let r = self.remaining(used);
        let hit = |rem: u64, limit: u64| (rem as u128) * 100 <= (percent as u128) * (limit as u128);
        hit(r.turns, self.turns)
            || hit(r.input_tokens, self.input_tokens)
            || hit(r.output_tokens, self.output_tokens)
    }
    /// A request's `max_tokens`: the lesser of the per-request maximum and
    /// the remaining output allowance, fixed when the request is captured.
    pub fn max_tokens(&self, used: &Usage, per_request: u64) -> u64 {
        per_request.min(self.remaining(used).output_tokens)
    }
    /// The allowances member of status, run and re-entry replies:
    /// each `{used, reported, estimated, limit}`.
    pub fn allowances_j(&self, used: &Usage) -> J {
        let one = |s: Split, limit: u64| {
            J::obj()
                .with("used", s.used())
                .with("reported", s.reported)
                .with("estimated", s.estimated)
                .with("limit", limit)
        };
        J::obj()
            .with("turns", one(used.turns, self.turns))
            .with("input_tokens", one(used.input_tokens, self.input_tokens))
            .with("output_tokens", one(used.output_tokens, self.output_tokens))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn used(t: u64, i: u64, o: u64) -> Usage {
        let mut u = Usage::default();
        u.charge(&Charge {
            basis: Basis::Reported,
            turns: t,
            input_tokens: i,
            output_tokens: o,
        });
        u
    }

    #[test]
    fn charges_land_on_their_side_and_sum_for_limits() {
        let mut u = Usage::default();
        u.charge(&Charge::reported(10, 2, 3, 7));
        u.charge(&Charge::estimated(16_000, 10));
        u.charge(&Charge::NONE);
        assert_eq!(
            u.turns,
            Split {
                reported: 1,
                estimated: 1
            }
        );
        assert_eq!(u.input_tokens.reported, 15);
        assert_eq!(u.input_tokens.estimated, 4, "ceil(10 / 3)");
        assert_eq!(u.output_tokens.used(), 16_007);
        let back = crate::json::parse(&u.to_j().bytes()).unwrap();
        assert_eq!(Usage::decode(&back.obj("").unwrap()).unwrap(), u);
        assert_eq!(
            u.to_j().string(),
            r#"{"turns":{"reported":1,"estimated":1},"input_tokens":{"reported":15,"estimated":4},"output_tokens":{"reported":7,"estimated":16000}}"#
        );
    }

    #[test]
    fn exhaustion_and_near_limit_follow_the_stated_thresholds() {
        let l = Limits {
            turns: 10,
            input_tokens: 1000,
            output_tokens: 5000,
        };
        assert!(!l.exhausted(&used(9, 999, 5000 - 1024)));
        assert!(l.exhausted(&used(10, 0, 0)), "no turn remains");
        assert!(l.exhausted(&used(0, 1000, 0)), "input used up");
        assert!(
            l.exhausted(&used(0, 0, 5000 - 1023)),
            "fewer than 1,024 output"
        );
        assert!(l.exhausted(&used(0, 2000, 0)), "input can exceed its limit");
        assert_eq!(l.max_tokens(&used(0, 0, 0), 16_000), 5000);
        assert_eq!(l.max_tokens(&used(0, 0, 4000), 16_000), 1000);
        assert!(!l.near_limit(&used(7, 0, 0), 20));
        assert!(l.near_limit(&used(8, 0, 0), 20), "2 × 100 ≤ 20 × 10");
        assert!(l.near_limit(&used(0, 800, 0), 20));
        let r = l.remaining(&used(8, 1200, 1));
        assert_eq!((r.turns, r.input_tokens, r.output_tokens), (2, 0, 4999));
        assert_eq!(
            r.fill(crate::forms::NEAR_LIMIT),
            "Allowance notice: 2 turns, 0 input tokens and 4999 output tokens remain for this audit. When an allowance runs out the run stops, and an unsubmitted answer stays unsubmitted."
        );
    }

    #[test]
    fn a_none_charge_charges_nothing() {
        let bad =
            crate::json::parse(br#"{"basis":"none","turns":1,"input_tokens":0,"output_tokens":0}"#)
                .unwrap();
        assert!(Charge::decode(&bad.obj("").unwrap()).is_err());
    }
}
