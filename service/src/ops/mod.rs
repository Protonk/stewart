//! Manager operations (INTERFACE 5). Each returns one `Reply`; the CLI
//! presents it as JSON or for people.

pub mod close;
pub mod commission;
pub mod new;
pub mod prepare;
pub(crate) mod presentation;
pub mod receipt;
pub mod run;
pub mod status;

use crate::archive::{Audit, Fail};
use crate::bodies::{NoticeReport, RunEnded};
use crate::delivery::By;
use crate::fsx::Dir;
use crate::json::J;
use crate::log::{LogState, Placement};
use crate::util;

/// What `run` needs from its environment (commission and receipt replies).
pub fn run_needs(_audit: &Audit) -> J {
    #[cfg(feature = "claude-code")]
    if crate::log::read(_audit)
        .limits()
        .is_some_and(|l| l.harness.is_some())
    {
        return crate::json::strs(&[
            "explicit authority for this bounded placement; no automatic restart",
            "the pinned harness installation and its own subscription login, with paid extra usage disabled",
            "no credential argument or credential environment variable; no API fallback",
            "runs in the foreground until the placement ends or reaches its deadline; callers with command timeouts should start it in the background; usage may remain partial or unknown",
        ]);
    }
    crate::json::strs(&[
        "provider credential through --key-fd or ANTHROPIC_API_KEY",
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
    pub authoring: J,
    pub seal: J,
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
            .with("authoring", self.authoring.clone())
            .with("seal", self.seal.clone())
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
        authoring: state.authoring_j(),
        seal: match sealed_by {
            "none" => J::obj().with("state", "absent").with("actor", J::Null),
            "unknown" => J::obj().with("state", "unknown").with("actor", J::Null),
            actor => J::obj().with("state", "present").with("actor", actor),
        },
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
        return (state.seal_observation_j(), None);
    };
    let handle = crate::ids::seal_handle(&audit.archive.store, &audit.id, &s.manifest_sha256);
    let base = |sealed_at: J, unproduced: J| {
        state
            .seal_observation_j()
            .with("handle", handle.as_str())
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

// ---------------------------------------------------------------------------
// Placement endings.

/// The `notices` of placement `run`'s `run_ended` (4.4): every `notice`
/// record the log holds for that placement, in log order, each with `sent`
/// as `sent` judges its planned request from the evidence the recorder has
/// (6.4). Only the placement's own process links its notices, so this is
/// exactly what the placement published, whether or not that process
/// confirmed the publication.
pub(crate) fn placement_notices(
    state: &LogState,
    run: u64,
    sent: impl Fn(u64) -> &'static str,
) -> Vec<NoticeReport> {
    state
        .notices()
        .iter()
        .filter(|(_, n)| n.run == run)
        .map(|(rec, n)| NoticeReport {
            kind: n.kind.clone(),
            record: rec.name(),
            sent: sent(n.request).to_string(),
        })
        .collect()
}

/// The `run_ended` of a placement whose process is gone (6.4, 6.7), as `by`
/// records it under a free lock: usage accounted from its run directory,
/// its notices with what their requests show and the seal published during
/// it. The recorders differ only in `recorded_by` and their message.
///
/// A run directory that cannot be accounted charges nothing. Its notices
/// are `not_sent` when it was never created (a crash right after
/// `run_started`), since no request carried them, and `unknown` when it
/// exists but cannot be read.
pub fn gone_run_ended(audit: &Audit, state: &LogState, p: &Placement, by: By) -> RunEnded {
    let run = p.run;
    let account = crate::runs::account(audit, run);
    let missing_dir = crate::runs::open(audit, run)
        .err()
        .is_some_and(|e| e.raw_os_error() == Some(libc::ENOENT));
    let notices = placement_notices(state, run, |request| match &account {
        Ok(a) => a.notice_sent(request),
        Err(_) if missing_dir => "not_sent",
        Err(_) => "unknown",
    });
    let seal = state
        .seal()
        .filter(|(rec, _)| rec.n > p.started.n)
        .map(|(rec, _)| rec.name());
    let message = match by {
        By::Run => {
            let mut m = format!(
                "Placement {run}'s process was gone with the active lock free; run recorded its ending, accounted from runs/{run}."
            );
            let problems: Vec<&str> = match &account {
                Ok(a) => a.problems.iter().map(String::as_str).collect(),
                Err(why) => vec![why.as_str()],
            };
            if !problems.is_empty() {
                m.push_str(&format!(" Not readable: {}.", problems.join("; ")));
            }
            m
        }
        By::Close => {
            let note = match &account {
                Ok(_) => String::new(),
                Err(why) => format!(" Its run directory could not be accounted ({why})."),
            };
            format!(
                "Placement {run}'s process ended without recording its ending; reconciled by close under a free lock.{note}"
            )
        }
    };
    let (usage, requests, attempts) = match &account {
        Ok(a) => (a.usage, a.requests, a.attempts),
        Err(_) => (Default::default(), 0, 0),
    };
    RunEnded {
        run,
        ending: "interrupted".to_string(),
        cause: Some("process_gone".to_string()),
        recorded_by: by.name().to_string(),
        provider: None,
        requests,
        attempts,
        usage,
        notices,
        seal,
        message,
    }
}
