//! Manager operations (INTERFACE 5). Each returns one `Reply`; the CLI
//! presents it as JSON or for people.

pub mod close;
pub mod commission;
pub mod new;
pub mod prepare;
pub mod receipt;
pub mod run;
pub mod status;

use crate::archive::Fail;
use crate::fsx::Dir;
use crate::json::J;
use crate::util;

/// What `run` needs from its environment (commission and receipt replies).
pub fn run_needs() -> J {
    crate::json::strs(&[
        "ANTHROPIC_API_KEY in the environment",
        "network access to the provider",
        "runs in the foreground until the placement ends; callers with command timeouts should start it in the background",
    ])
}

/// A located directory for the overlap check.
pub struct Place<'a> {
    pub what: &'a str,
    pub path: &'a str,
    pub dir: &'a Dir,
}

/// Refuse when any two of the places contain one another or are the same
/// directory, comparing device and inode along each one's `..` ancestry
/// (INTERFACE 4.1).
pub fn check_overlap(places: &[Place]) -> Result<(), Fail> {
    let mut chains = Vec::new();
    for p in places {
        let chain = p.dir.ancestry().map_err(|e| {
            Fail::failed(
                "location_overlap",
                format!(
                    "The {} {} could not be examined for overlap: {}.",
                    p.what,
                    p.path,
                    util::describe(&e)
                ),
            )
            .cause(crate::reply::Cause::io("walk directory ancestry", &e).at(p.path))
        })?;
        chains.push(chain);
    }
    for i in 0..places.len() {
        for j in 0..places.len() {
            if i == j {
                continue;
            }
            // Is place i inside (or equal to) place j?
            if chains[i].contains(&chains[j][0]) {
                let (a, b) = (&places[i], &places[j]);
                let msg = if chains[i][0] == chains[j][0] {
                    format!(
                        "The {} {} and the {} {} are the same directory.",
                        a.what, a.path, b.what, b.path
                    )
                } else {
                    format!(
                        "The {} {} is inside the {} {}.",
                        a.what, a.path, b.what, b.path
                    )
                };
                return Err(Fail::refused(
                    "location_overlap",
                    format!("{msg} The submission folder, the archive and the destination must not contain one another; choose separate locations."),
                )
                .data(J::obj().with("inner", J::obj().with("location", a.what).with("path", a.path)).with("outer", J::obj().with("location", b.what).with("path", b.path))));
            }
        }
    }
    Ok(())
}

/// The headline facts a manager tracks (INTERFACE 5.6), as far as the
/// pre-launch records establish them.
pub struct Headline {
    pub accepted: &'static str,
    pub launched: &'static str,
    pub sealed_by: &'static str,
    pub delivered_known: bool,
    pub closed: &'static str,
}

impl Headline {
    pub fn to_j(&self) -> J {
        let delivered = if self.delivered_known {
            J::obj().with("verified", false).with("confirmed", false)
        } else {
            J::obj()
                .with("verified", "unknown")
                .with("confirmed", "unknown")
        };
        J::obj()
            .with("accepted", self.accepted)
            .with("launched", self.launched)
            .with("sealed", J::obj().with("by", self.sealed_by))
            .with("delivered", delivered)
            .with("closed", self.closed)
    }
}

pub fn headline(state: &crate::log::LogState) -> Headline {
    let damaged = state.damaged();
    let accepted = if state.accepted().is_some() {
        "yes"
    } else if damaged {
        "unknown"
    } else {
        "no"
    };
    let launched = if state.launched() {
        "yes"
    } else if damaged {
        "unknown"
    } else {
        "no"
    };
    let closed = if state.closed().is_some() {
        "yes"
    } else if damaged {
        "unknown"
    } else if state.close_requested().is_some() {
        "unfinished"
    } else {
        "no"
    };
    Headline {
        accepted,
        launched,
        sealed_by: if damaged && state.find("seal").is_none() {
            "unknown"
        } else {
            "none"
        },
        delivered_known: !damaged,
        closed,
    }
}
