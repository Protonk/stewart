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
        matching(point, arg).any(|it| it.action == "corrupt")
    }

    /// Create `$STEWART_TEST_FAULT_DIR/<point>.paused` exclusively, then wait
    /// until `<point>.go` exists there, polling every 10 ms. After 60 s the
    /// process aborts. A point pauses once per process: a second hit finds
    /// its `.paused` file taken and continues.
    fn pause(spec: &str) {
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
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => return,
            Err(e) => {
                eprintln!(
                    "stewart-test: cannot create {}: {e}; aborting",
                    paused.display()
                );
                std::process::abort();
            }
        }
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
        static NAME: OnceLock<String> = OnceLock::new();
        NAME.get_or_init(|| std::env::var("STEWART_TEST_SABOTAGE").unwrap_or_default())
            .as_str()
            == name
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

/// `fault_corrupt!("point")`: whether to alter the bytes just written.
#[cfg(feature = "fault-injection")]
#[macro_export]
macro_rules! fault_corrupt {
    ($point:expr) => {
        $crate::fault::points::corrupt($point, None)
    };
}

#[cfg(not(feature = "fault-injection"))]
#[macro_export]
macro_rules! fault_corrupt {
    ($point:expr) => {
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
