//! Test-build failure points and sabotage controls (INTERFACE Appendix C).
//!
//! Both exist only when the crate is built with the `fault-injection` or
//! `sabotage` cargo features (the `stewart-test` build). Without them the
//! `fault!`, `fault_corrupt!` and `sabotage!` macros expand to constants, so
//! the release binary contains neither this code nor the environment variable
//! names it reads.
//!
//! Fault points take `point=action` items, comma-separated. A point may carry
//! one argument after a colon (`commission.after_capture:2=kill`). An item
//! without an argument matches every argument of that point. Actions: `kill`,
//! `eio`, `enospc`, `epipe`, `corrupt` and `pause` (see `pause` below).
//!
//! `POINTS` and `SABOTAGE` list every name Appendix C defines. A point or
//! control is available once its name is listed; code that hits a name not
//! listed fails a debug assertion, and a configured name that is not listed
//! is reported on stderr because it can never fire. The transport variables
//! (`transport`) are compiled with `fault-injection` as well; without it
//! their accessors return nothing and name no variable.

/// Every fault point of Appendix C.1, by its name before any `:<argument>`.
#[cfg(feature = "fault-injection")]
pub const POINTS: &[&str] = &[
    // Manager foundation.
    "prepare.before_prepared_link",
    "commission.after_capture",
    "commission.source_read",
    "commission.capture_write",
    "commission.capture_corrupt",
    "commission.receipt_write",
    "commission.before_accepted_link",
    "commission.accepted_dirsync",
    "commission.after_accepted_link",
    "log.publish",
    "close.before_closed_link",
    "diag.write",
    "reply.write",
    // Records, the answer protocol and the run.
    "stage.torn",
    "log.dirsync",
    "runs.publish",
    "run.after_started",
    "provider.request_capture",
    "provider.sent",
    "provider.response_capture",
    "run.between_turns",
    "tool.before",
    "entry.payload_write",
    "entry.payload_corrupt",
    "entry.after_link",
    "prepared.write",
    "seal.manifest_write",
    "seal.after_link",
    // Delivery and close.
    "delivery.source_read",
    "delivery.member_write",
    "delivery.member_corrupt",
    "delivery.after_member",
    "delivery.after_ended",
    "close.after_requested",
    "close.after_seal",
    "close.after_closed_link",
];

/// The fault actions (Appendix C.1).
#[cfg(feature = "fault-injection")]
pub const ACTIONS: &[&str] = &["kill", "eio", "enospc", "epipe", "corrupt", "pause"];

/// Every sabotage control of Appendix C.2.
#[cfg(feature = "sabotage")]
pub const SABOTAGE: &[&str] = &[
    "accept_without_affirmation",
    "accept_changed_source",
    "skip_hidden_entries",
    "normalize_newlines",
    "follow_symlinks",
    "readback_live_source",
    "regenerate_arrangement",
    "rewrite_record_in_place",
    "remove_partial_on_retry",
    "unknown_as_absent",
    "select_newer_store",
    "accept_unknown_field",
    "omit_effects_on_refusal",
    "whole_from_one_member",
    "extra_tool",
    "arrangement_mismatch",
    "read_live_source",
    "normalize_read",
    "paraphrase_question",
    "read_truncate_silently",
    "search_omit_last_page",
    "torn_as_entry",
    "merge_equal_adds",
    "replay_reexecutes",
    "stale_target_overwrites",
    "manager_seal_as_auditor",
    "reentry_omit_entry",
    "reentry_truncate_page",
    "reentry_omit_last_page",
    "reentry_mix_revisions",
    "reentry_placement_allowances",
    "drop_last_entry",
    "skip_delivery_verification",
    "deliver_conversation",
    "regenerate_rendering",
    "render_conclusion",
    "remove_superseded_payload",
    "remove_partial_package",
    "skip_search_capture",
    "framing_task_elsewhere",
    "grade_support",
    "block_incomplete",
    "reset_notice_allowance",
    "skip_confirmation",
    "seal_as_stopped",
    "empty_return_before_launch",
    "slow_list",
    "relative_run_line",
    "commission_over_network",
    "reset_limits_on_continuation",
    "fresh_ledger_on_continuation",
    "drop_refused_capture",
    "manifest_verdict",
    "ended_as_submitted",
    "seal_as_delivered",
    "unknown_membership_empty",
    "stale_preparation_retargets",
    "prepare_claims_seal",
    "leak_custody_path",
    "accept_unknown_tool_field",
    "seal_uncertain_as_none",
    "submit_claims_delivery",
];

#[cfg(feature = "fault-injection")]
pub mod points {
    use std::io;
    use std::sync::OnceLock;

    struct Item {
        point: String,
        arg: Option<String>,
        spec: String,
        action: String,
    }

    fn items() -> &'static Vec<Item> {
        static ITEMS: OnceLock<Vec<Item>> = OnceLock::new();
        ITEMS.get_or_init(|| {
            let raw = std::env::var("STEWART_TEST_FAULT").unwrap_or_default();
            raw.split(',')
                .filter(|s| !s.trim().is_empty())
                .filter_map(|item| {
                    let (spec, action) = item.trim().rsplit_once('=')?;
                    let (point, arg) = match spec.split_once(':') {
                        Some((p, a)) => (p.to_string(), Some(a.to_string())),
                        None => (spec.to_string(), None),
                    };
                    if !super::POINTS.contains(&point.as_str()) {
                        eprintln!("stewart-test: STEWART_TEST_FAULT names no fault point {point:?}; it never fires");
                    }
                    if !super::ACTIONS.contains(&action) {
                        eprintln!("stewart-test: STEWART_TEST_FAULT names no fault action {action:?}");
                    }
                    Some(Item {
                        point,
                        arg,
                        spec: spec.to_string(),
                        action: action.to_string(),
                    })
                })
                .collect()
        })
    }

    fn matching(point: &str, arg: Option<&str>) -> impl Iterator<Item = &'static Item> {
        let arg = arg.map(|s| s.to_string());
        items()
            .iter()
            .filter(move |it| it.point == point && (it.arg.is_none() || it.arg == arg))
    }

    /// Run the actions configured for this point (other than `corrupt`).
    pub fn hit(point: &str, arg: Option<&str>) -> io::Result<()> {
        debug_assert!(
            super::POINTS.contains(&point),
            "unlisted fault point {point}"
        );
        for it in matching(point, arg) {
            match it.action.as_str() {
                "kill" => unsafe {
                    libc::kill(libc::getpid(), libc::SIGKILL);
                    // SIGKILL cannot be caught; this is not reached.
                    loop {
                        libc::pause();
                    }
                },
                "eio" => return Err(io::Error::from_raw_os_error(libc::EIO)),
                "enospc" => return Err(io::Error::from_raw_os_error(libc::ENOSPC)),
                "epipe" => return Err(io::Error::from_raw_os_error(libc::EPIPE)),
                "pause" => pause(&it.spec),
                _ => {}
            }
        }
        Ok(())
    }

    /// Whether `corrupt` is configured for this point.
    pub fn corrupt(point: &str, arg: Option<&str>) -> bool {
        debug_assert!(
            super::POINTS.contains(&point),
            "unlisted fault point {point}"
        );
        matching(point, arg).any(|it| it.action == "corrupt")
    }

    /// Whether any action is configured for this point, for points that
    /// change how an operation proceeds before their action runs
    /// (`stage.torn` writes half a record first).
    pub fn armed(point: &str, arg: Option<&str>) -> bool {
        debug_assert!(
            super::POINTS.contains(&point),
            "unlisted fault point {point}"
        );
        matching(point, arg).next().is_some()
    }

    /// Create `$STEWART_TEST_FAULT_DIR/<point>.paused` exclusively, then wait
    /// until `<point>.go` exists there, polling every 10 ms. After 60 s the
    /// process aborts. A point pauses once per process: a later hit of a
    /// point this process already paused at continues. A `.paused` file this
    /// process did not create is stale, left by an earlier process: the
    /// process names it and aborts rather than continue unpaused, which
    /// would silently defeat the synchronization a test relies on.
    fn pause(spec: &str) {
        static PAUSED: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());
        let mut done = PAUSED.lock().unwrap_or_else(|e| e.into_inner());
        if done.iter().any(|s| s == spec) {
            return;
        }
        let Ok(dir) = std::env::var("STEWART_TEST_FAULT_DIR") else {
            eprintln!("stewart-test: pause at {spec} needs STEWART_TEST_FAULT_DIR; aborting");
            std::process::abort();
        };
        let paused = std::path::Path::new(&dir).join(format!("{spec}.paused"));
        let go = std::path::Path::new(&dir).join(format!("{spec}.go"));
        match std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&paused)
        {
            Ok(_) => done.push(spec.to_string()),
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => {
                eprintln!(
                    "stewart-test: {} already exists, so the pause at {spec} cannot be observed; use a fault directory without this point's files; aborting",
                    paused.display()
                );
                std::process::abort();
            }
            Err(e) => {
                eprintln!(
                    "stewart-test: cannot create {}: {e}; aborting",
                    paused.display()
                );
                std::process::abort();
            }
        }
        // Another thread may pause at another point meanwhile.
        drop(done);
        let start = std::time::Instant::now();
        while !go.exists() {
            if start.elapsed() > std::time::Duration::from_secs(60) {
                eprintln!("stewart-test: no {} after 60 s; aborting", go.display());
                std::process::abort();
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
    }
}

#[cfg(feature = "sabotage")]
pub mod controls {
    use std::sync::OnceLock;

    /// Whether the named sabotage control is the one configured.
    pub fn on(name: &str) -> bool {
        debug_assert!(
            super::SABOTAGE.contains(&name),
            "unlisted sabotage control {name}"
        );
        static NAME: OnceLock<String> = OnceLock::new();
        NAME.get_or_init(|| {
            let v = std::env::var("STEWART_TEST_SABOTAGE").unwrap_or_default();
            if !v.is_empty() && !super::SABOTAGE.contains(&v.as_str()) {
                eprintln!("stewart-test: STEWART_TEST_SABOTAGE names no sabotage control {v:?}");
            }
            v
        })
        .as_str()
            == name
    }
}

/// Provider and transport variables for the fake provider (Appendix C.1).
/// Compiled only with `fault-injection`; otherwise every accessor returns
/// nothing and the variable names are absent from the binary.
#[cfg(feature = "fault-injection")]
pub mod transport {
    /// The size bound of the `STEWART_TEST_TLS_ROOT` PEM file.
    pub const TLS_ROOT_LIMIT: u64 = 1024 * 1024;

    fn var(name: &str) -> Option<String> {
        std::env::var(name).ok().filter(|v| !v.is_empty())
    }

    fn small_decimal(s: &str, max: u64) -> Option<u64> {
        let ok = !s.is_empty()
            && s.len() <= 6
            && s.bytes().all(|b| b.is_ascii_digit())
            && (s == "0" || !s.starts_with('0'));
        ok.then(|| s.parse().ok()).flatten().filter(|n| *n <= max)
    }

    /// `STEWART_TEST_TLS_ROOT`: the bytes of a PEM file of further trust
    /// roots for the provider connection. `Ok(None)` when unset. An error
    /// (not absolute, missing, unreadable, over 1 MiB) refuses `run` before
    /// any request with `test_tls_root_invalid`; the caller also refuses a
    /// file holding no certificate.
    pub fn tls_root() -> Result<Option<(String, Vec<u8>)>, String> {
        use std::io::Read;
        let Some(path) = var("STEWART_TEST_TLS_ROOT") else {
            return Ok(None);
        };
        if !path.starts_with('/') {
            return Err(format!(
                "STEWART_TEST_TLS_ROOT {path:?} is not an absolute path"
            ));
        }
        let f = std::fs::File::open(&path)
            .map_err(|e| format!("STEWART_TEST_TLS_ROOT {path:?} cannot be opened: {e}"))?;
        let mut bytes = Vec::new();
        f.take(TLS_ROOT_LIMIT + 1)
            .read_to_end(&mut bytes)
            .map_err(|e| format!("STEWART_TEST_TLS_ROOT {path:?} cannot be read: {e}"))?;
        if bytes.len() as u64 > TLS_ROOT_LIMIT {
            return Err(format!(
                "STEWART_TEST_TLS_ROOT {path:?} is larger than 1 MiB"
            ));
        }
        Ok(Some((path, bytes)))
    }

    /// `STEWART_TEST_PROVIDER_TIMEOUT`: the request timeout in seconds,
    /// 1–600, in place of the pinned 600. `Ok(None)` when unset; an error
    /// for any other value.
    pub fn provider_timeout() -> Result<Option<u64>, String> {
        let Some(v) = var("STEWART_TEST_PROVIDER_TIMEOUT") else {
            return Ok(None);
        };
        match small_decimal(&v, 600) {
            Some(n) if n >= 1 => Ok(Some(n)),
            _ => Err(format!(
                "STEWART_TEST_PROVIDER_TIMEOUT {v:?} is not a whole number of seconds from 1 to 600"
            )),
        }
    }

    /// `STEWART_TEST_RETRY_DELAYS`: three comma-separated delays in
    /// milliseconds, each 0–30,000, in place of 2, 8 and 30 seconds. A
    /// `retry-after` value still applies. `Ok(None)` when unset.
    pub fn retry_delays() -> Result<Option<[u64; 3]>, String> {
        let Some(v) = var("STEWART_TEST_RETRY_DELAYS") else {
            return Ok(None);
        };
        let parts: Vec<Option<u64>> = v.split(',').map(|p| small_decimal(p, 30_000)).collect();
        match parts.as_slice() {
            [Some(a), Some(b), Some(c)] => Ok(Some([*a, *b, *c])),
            _ => Err(format!(
                "STEWART_TEST_RETRY_DELAYS {v:?} is not three comma-separated delays of 0 to 30000 milliseconds"
            )),
        }
    }
}

/// Without `fault-injection` the transport variables do not exist.
#[cfg(not(feature = "fault-injection"))]
pub mod transport {
    pub fn tls_root() -> Result<Option<(String, Vec<u8>)>, String> {
        Ok(None)
    }
    pub fn provider_timeout() -> Result<Option<u64>, String> {
        Ok(None)
    }
    pub fn retry_delays() -> Result<Option<[u64; 3]>, String> {
        Ok(None)
    }
}

/// `fault!("point")` or `fault!("point", arg)`: `io::Result<()>`.
#[cfg(feature = "fault-injection")]
#[macro_export]
macro_rules! fault {
    ($point:expr) => {
        $crate::fault::points::hit($point, None)
    };
    ($point:expr, $arg:expr) => {
        $crate::fault::points::hit($point, Some($arg))
    };
}

#[cfg(not(feature = "fault-injection"))]
#[macro_export]
macro_rules! fault {
    ($point:expr) => {
        ::std::io::Result::<()>::Ok(())
    };
    ($point:expr, $arg:expr) => {
        ::std::io::Result::<()>::Ok(())
    };
}

/// `fault_corrupt!("point")` or `fault_corrupt!("point", arg)`: whether to
/// alter the bytes just written.
#[cfg(feature = "fault-injection")]
#[macro_export]
macro_rules! fault_corrupt {
    ($point:expr) => {
        $crate::fault::points::corrupt($point, None)
    };
    ($point:expr, $arg:expr) => {
        $crate::fault::points::corrupt($point, Some($arg))
    };
}

#[cfg(not(feature = "fault-injection"))]
#[macro_export]
macro_rules! fault_corrupt {
    ($point:expr) => {
        false
    };
    ($point:expr, $arg:expr) => {
        false
    };
}

/// `fault_armed!("point", arg)`: whether any action is configured there.
#[cfg(feature = "fault-injection")]
#[macro_export]
macro_rules! fault_armed {
    ($point:expr, $arg:expr) => {
        $crate::fault::points::armed($point, Some($arg))
    };
}

#[cfg(not(feature = "fault-injection"))]
#[macro_export]
macro_rules! fault_armed {
    ($point:expr, $arg:expr) => {
        false
    };
}

/// `sabotage!("name")`: whether that control is active.
#[cfg(feature = "sabotage")]
#[macro_export]
macro_rules! sabotage {
    ($name:expr) => {
        $crate::fault::controls::on($name)
    };
}

#[cfg(not(feature = "sabotage"))]
#[macro_export]
macro_rules! sabotage {
    ($name:expr) => {
        false
    };
}

/// The registries equal Appendix C's tables. This reads the specification in
/// the repository as an independent witness.
#[cfg(all(test, feature = "fault-injection", feature = "sabotage"))]
mod tests {
    fn appendix_c() -> std::collections::BTreeMap<String, Vec<String>> {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../docs/INTERFACE.md");
        let doc =
            std::fs::read_to_string(path).expect("docs/INTERFACE.md is part of the repository");
        let c = &doc[doc.find("## Appendix C").expect("Appendix C")..];
        let mut tables: std::collections::BTreeMap<String, Vec<String>> = Default::default();
        let mut header = String::new();
        for line in c.lines() {
            if !line.starts_with('|') {
                header.clear();
                continue;
            }
            if header.is_empty() {
                header = line.split('|').nth(1).unwrap_or("").trim().to_string();
                continue;
            }
            let first = line.split('|').nth(1).unwrap_or("").trim();
            // Every backticked name in the first cell, without its `:<argument>`.
            for name in first.split('`').skip(1).step_by(2) {
                let name = name.split(':').next().unwrap_or(name).to_string();
                tables.entry(header.clone()).or_default().push(name);
            }
        }
        tables
    }

    #[test]
    fn registries_list_exactly_appendix_c() {
        let t = appendix_c();
        let mut points = t["Point"].clone();
        points.sort();
        points.dedup();
        let mut ours: Vec<String> = super::POINTS.iter().map(|s| s.to_string()).collect();
        ours.sort();
        assert_eq!(ours, points);
        let mut sab = t["Name"].clone();
        sab.sort();
        let mut ours: Vec<String> = super::SABOTAGE.iter().map(|s| s.to_string()).collect();
        ours.sort();
        assert_eq!(ours, sab, "sabotage controls");
        let mut actions = t["Action"].clone();
        actions.sort();
        let mut ours: Vec<String> = super::ACTIONS.iter().map(|s| s.to_string()).collect();
        ours.sort();
        assert_eq!(ours, actions, "actions");
        assert_eq!(
            t["Variable"],
            [
                "STEWART_TEST_TLS_ROOT",
                "STEWART_TEST_PROVIDER_TIMEOUT",
                "STEWART_TEST_RETRY_DELAYS"
            ]
        );
    }
}
