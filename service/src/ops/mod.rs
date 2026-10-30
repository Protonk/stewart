//! Manager operations (INTERFACE 5). Each returns one `Reply`; the CLI
//! presents it as JSON or for people.

pub mod close;
pub mod commission;
pub mod new;
pub mod prepare;
pub mod receipt;
pub mod run;
pub mod status;

use crate::archive::{Audit, Fail};
use crate::fsx::Dir;
use crate::json::J;
use crate::log::LogState;
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

/// The run line of the commission and receipt replies: the recorded writer
/// path, `run` and the reference (C12).
pub fn run_line(audit: &Audit) -> J {
    #[allow(unused_mut)]
    let mut argv = audit.argv(&["run", &audit.reference]);
    #[cfg(feature = "sabotage")]
    if crate::sabotage!("relative_run_line") {
        // Sabotage control: the writer path relative to the commissioning
        // directory, which works only from there.
        if let Ok(cwd) = std::env::current_dir() {
            argv[0] = relative_to(&argv[0], &cwd.to_string_lossy());
        }
    }
    crate::json::strs(&argv)
}

/// `path` relative to the directory `from` (both absolute).
#[cfg(feature = "sabotage")]
fn relative_to(path: &str, from: &str) -> String {
    let p: Vec<&str> = path.split('/').filter(|c| !c.is_empty()).collect();
    let f: Vec<&str> = from.split('/').filter(|c| !c.is_empty()).collect();
    let common = p.iter().zip(&f).take_while(|(a, b)| a == b).count();
    let mut parts: Vec<&str> = vec![".."; f.len() - common];
    parts.extend(&p[common..]);
    parts.join("/")
}

/// The `commission_over_network` sabotage control: commission demands the
/// provider key and opens a connection to the provider before accepting.
/// The product's commission is local; only `run` reaches the provider.
/// The control connects only to an explicit `STEWART_PROVIDER_URL` (a test's
/// fake provider) and never to the real provider's default address.
#[cfg(feature = "sabotage")]
pub fn sabotage_reach_provider() -> Result<(), Fail> {
    let key = std::env::var("ANTHROPIC_API_KEY").unwrap_or_default();
    if key.is_empty() {
        return Err(Fail::refused(
            "provider_key_missing",
            "ANTHROPIC_API_KEY is not set.",
        ));
    }
    let Ok(base) = std::env::var("STEWART_PROVIDER_URL") else {
        return Ok(());
    };
    let (rest, port) = match base.split_once("://") {
        Some(("http", r)) => (r, 80),
        Some((_, r)) => (r, 443),
        None => (base.as_str(), 443),
    };
    let authority = rest.split('/').next().unwrap_or_default();
    let (host, port) = match authority.rsplit_once(':') {
        Some((h, p)) => (h.to_string(), p.parse().unwrap_or(port)),
        None => (authority.to_string(), port),
    };
    let _ = std::net::TcpStream::connect((host.as_str(), port));
    Ok(())
}

/// The accepted commission's settings, from the `prepared` record of the
/// accepted preparation.
pub fn accepted_settings(state: &LogState) -> Option<crate::frontmatter::Settings> {
    let prep = match &state.accepted()?.body {
        crate::log::Body::Accepted { prep, .. } => *prep,
        _ => return None,
    };
    let p = state.prepared(prep)?;
    crate::records::decode_settings(&p.body_obj().obj("settings").ok()?).ok()
}

/// What the headline says about delivery (INTERFACE 5.6).
pub enum DeliveredFacts {
    /// The log is damaged: neither verification nor confirmation can be
    /// established.
    Unknown,
    Known {
        /// True only for a `verified` delivery; a `verified_with_losses`
        /// delivery is never called complete.
        verified: bool,
        /// True once `closed` records the delivery's placement.
        confirmed: bool,
        /// The newest verified attempt's package path.
        location: Option<String>,
        /// The loss IDs of a `verified_with_losses` delivery.
        losses: Option<Vec<String>>,
    },
}

/// The headline facts a manager tracks (INTERFACE 5.6), in order: accepted,
/// launched, sealed and by whom, delivery verified and confirmed, closed.
pub struct Headline {
    pub accepted: &'static str,
    pub launched: &'static str,
    pub sealed_by: &'static str,
    pub delivered: DeliveredFacts,
    pub closed: &'static str,
}

impl Headline {
    pub fn to_j(&self) -> J {
        let delivered = match &self.delivered {
            DeliveredFacts::Unknown => J::obj()
                .with("verified", "unknown")
                .with("confirmed", "unknown"),
            DeliveredFacts::Known {
                verified,
                confirmed,
                location,
                losses,
            } => {
                let mut d = J::obj()
                    .with("verified", *verified)
                    .with("confirmed", *confirmed);
                if let Some(l) = location {
                    d.push("location", l.as_str());
                }
                if let Some(l) = losses {
                    d.push("losses", crate::json::strs(l));
                }
                d
            }
        };
        J::obj()
            .with("accepted", self.accepted)
            .with("launched", self.launched)
            .with("sealed", J::obj().with("by", self.sealed_by))
            .with("delivered", delivered)
            .with("closed", self.closed)
    }
}

/// The headline from the records. A fact that depends on an unreadable part
/// of a damaged log is `unknown`; a fact the readable prefix establishes
/// stands.
pub fn headline(audit: &Audit, state: &LogState) -> Headline {
    let damaged = state.damaged();
    let known = |present: bool| {
        if present {
            "yes"
        } else if damaged {
            "unknown"
        } else {
            "no"
        }
    };
    let accepted = known(state.accepted().is_some());
    let launched = known(state.launched());
    let closed = if state.closed().is_some() {
        "yes"
    } else if damaged {
        "unknown"
    } else if state.close_requested().is_some() {
        "unfinished"
    } else {
        "no"
    };
    let sealed_by = match state.seal() {
        Some((_, s)) => s.actor.name(),
        None if damaged => "unknown",
        None if crate::sabotage!("ended_as_submitted")
            && state.latest_placement().is_some_and(|p| {
                p.ended.is_some_and(|(_, e)| {
                    e.ending == "ended_unsubmitted" || e.ending == "limit_reached"
                })
            }) =>
        {
            // Sabotage control: an ordinary ending or a limit stop is
            // reported as the auditor's submission.
            "auditor"
        }
        None => "none",
    };
    let delivered = if damaged {
        DeliveredFacts::Unknown
    } else {
        let newest = state.newest_verified();
        let ended = newest.as_ref().and_then(|d| d.ended);
        let verified = ended.is_some_and(|(_, e)| e.outcome == "verified")
            || (crate::sabotage!("seal_as_delivered") && state.seal().is_some());
        let confirmed = match (state.closed().and_then(|c| c.closed_body()), &newest) {
            (Some(c), Some(d)) => c
                .after
                .as_ref()
                .is_some_and(|a| a.delivery.attempt == d.attempt),
            _ => false,
        };
        let losses = newest
            .as_ref()
            .filter(|_| ended.is_some_and(|(_, e)| e.outcome == "verified_with_losses"))
            .map(|d| crate::delivery::view_of(audit, d).loss_ids());
        DeliveredFacts::Known {
            verified,
            confirmed,
            location: ended.and_then(|(_, e)| e.package.clone()),
            losses,
        }
    };
    Headline {
        accepted,
        launched,
        sealed_by,
        delivered,
        closed,
    }
}

/// The seal as status, run and close present it (5.6): `handle`, `actor`,
/// `sealed_at` (the manifest's), `revision`, `manifest_sha256` and
/// `unproduced`, or null without a seal. When the manifest cannot be read,
/// `sealed_at` and `unproduced` are `unknown` and the second value is the
/// diagnostic naming why.
pub fn seal_j(audit: &Audit, state: &LogState) -> (J, Option<J>) {
    let Some((_, s)) = state.seal() else {
        return (J::Null, None);
    };
    let handle = crate::ids::seal_handle(&audit.archive.store, &audit.id, &s.manifest_sha256);
    let base = |sealed_at: J, unproduced: J| {
        J::obj()
            .with("handle", handle.as_str())
            .with("actor", s.actor.name())
            .with("sealed_at", sealed_at)
            .with("revision", s.revision)
            .with("manifest_sha256", s.manifest_sha256.as_str())
            .with("unproduced", unproduced)
    };
    match crate::returns::load_manifest(audit, &s.manifest, &s.manifest_sha256) {
        Ok((m, _)) => {
            let names: Vec<&str> = m.unproduced.iter().map(|u| u.name.as_str()).collect();
            (
                base(J::Str(m.sealed_at.clone()), crate::json::strs(&names)),
                None,
            )
        }
        Err(why) => (
            base(J::Str("unknown".into()), J::Str("unknown".into())),
            Some(J::obj().with("record", s.manifest.as_str()).with(
                "cause",
                format!("the seal's manifest cannot be read: {why}"),
            )),
        ),
    }
}

/// The answer as status and run present it: the revision and the number of
/// entries in the current selection, never their content. Null before launch.
pub fn answer_j(state: &LogState) -> J {
    if !state.launched() {
        return J::Null;
    }
    J::obj()
        .with("revision", state.revision())
        .with("entries", state.selection().len() as u64)
}
