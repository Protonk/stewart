//! The supervisor has no archive descriptor and never interprets tool calls.
//! Its process group lives until shutdown. Owner EOF and a monotonic deadline
//! independently terminate the group; the owner records its ID before GO.
use super::profile::Profile;
use crate::json::J;
use crate::runs::RunDir;
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

pub const SUPERVISOR: &str = "__stewart-cc-supervise";
pub const RELAY: &str = "__stewart-cc-relay";
pub const HOOK: &str = "__stewart-cc-hook";
const GRACE: Duration = Duration::from_secs(2);

/// The only construction of a harness environment. Nothing is inherited.
pub fn environment(profile: &Profile) -> Vec<(String, String)> {
    let mut e: Vec<(String, String)> = [
        ("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        ("LANG", "en_US.UTF-8"),
        ("DISABLE_UPDATES", "1"),
        ("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1"),
        ("CLAUDE_CODE_DISABLE_AUTO_MEMORY", "1"),
        ("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", "1"),
        ("CLAUDE_CODE_DISABLE_AGENT_VIEW", "1"),
        ("CLAUDE_CODE_DISABLE_FAST_MODE", "1"),
        ("ENABLE_CLAUDEAI_MCP_SERVERS", "false"),
        ("ENABLE_TOOL_SEARCH", "false"),
        ("CLAUDE_CODE_MAX_RETRIES", "0"),
        ("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "16000"),
    ]
    .iter()
    .map(|(k, v)| (k.to_string(), v.to_string()))
    .collect();
    e.extend([
        ("HOME".into(), profile.home.clone()),
        ("TMPDIR".into(), profile.temporary_directory.clone()),
        ("CLAUDE_CONFIG_DIR".into(), profile.config_directory.clone()),
    ]);
    e
}

pub fn gone(pgid: i32) -> Result<bool, String> {
    if pgid <= 1 {
        return Err("invalid supervisor group".into());
    }
    // Signal zero observes; recovery never signals a possibly reused ID.
    if unsafe { libc::kill(-pgid, 0) } == 0 {
        return Ok(false);
    }
    let e = io::Error::last_os_error();
    if e.raw_os_error() == Some(libc::ESRCH) {
        Ok(true)
    } else {
        Err(e.to_string())
    }
}

pub struct Owned {
    pub child: Child,
    control: UnixStream,
    pgid: i32,
    stopped: bool,
    pub exit_code: Option<i32>,
}
impl Owned {
    pub fn start(
        writer: &str,
        profile: &Profile,
        cwd: &str,
        args: &[String],
        remaining: Duration,
        dir: &RunDir,
        label: &str,
    ) -> Result<Self, String> {
        let (owner, peer) = UnixStream::pair().map_err(|e| e.to_string())?;
        let fd = peer.as_raw_fd();
        let mut command = Command::new(writer);
        command
            .arg(SUPERVISOR)
            .arg(fd.to_string())
            .arg(remaining.as_millis().max(1).to_string())
            .arg(&profile.executable)
            .args(args)
            .current_dir(cwd)
            .env_clear()
            .envs(environment(profile))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .process_group(0);
        // Only the supervisor inherits this control socket; its child closes it.
        unsafe {
            command.pre_exec(move || {
                if libc::fcntl(fd, libc::F_SETFD, 0) < 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            });
        }
        let child = command
            .spawn()
            .map_err(|e| format!("start supervisor: {e}"))?;
        drop(peer);
        let pgid = child.id() as i32;
        let mut owned = Self {
            child,
            control: owner,
            pgid,
            stopped: false,
            exit_code: None,
        };
        let record = J::obj()
            .with("schema", "stewart.claude-code.process/1")
            .with("group", pgid as u64)
            .with("role", label);
        dir.dir
            .write_excl(&format!("process-{label}.json"), &record.bytes())
            .map_err(|e| format!("record supervisor before launch: {}", e.err))?;
        owned.control.write_all(b"G").map_err(|e| e.to_string())?;
        Ok(owned)
    }
    pub fn stop(&mut self) -> Result<bool, String> {
        if self.stopped {
            return gone(self.pgid);
        }
        self.stopped = true;
        let _ = self.control.write_all(b"S");
        let until = Instant::now() + GRACE + Duration::from_secs(4);
        loop {
            let reaped = self.child.try_wait().map_err(|e| e.to_string())?.is_some();
            if reaped && gone(self.pgid)? {
                self.control
                    .set_nonblocking(true)
                    .map_err(|e| e.to_string())?;
                let mut report = Vec::new();
                let _ = self.control.read_to_end(&mut report);
                if report.len() == 5 && report[0] == b'X' {
                    self.exit_code = Some(i32::from_be_bytes(report[1..].try_into().unwrap()));
                }
                return Ok(true);
            }
            if Instant::now() >= until {
                return Ok(false);
            }
            std::thread::sleep(Duration::from_millis(20));
        }
    }
}
impl Drop for Owned {
    fn drop(&mut self) {
        if !self.stopped {
            let _ = self.stop();
        }
    }
}

fn reset_signals() -> io::Result<()> {
    unsafe {
        let mut set = std::mem::zeroed();
        libc::sigemptyset(&mut set);
        let rc = libc::pthread_sigmask(libc::SIG_SETMASK, &set, std::ptr::null_mut());
        if rc != 0 {
            return Err(io::Error::from_raw_os_error(rc));
        }
        for sig in [libc::SIGTERM, libc::SIGINT, libc::SIGHUP, libc::SIGPIPE] {
            libc::signal(sig, libc::SIG_DFL);
        }
    }
    Ok(())
}
fn supervisor(args: &[String]) -> Result<i32, String> {
    if args.len() < 4 {
        return Err(
            "supervisor needs a control descriptor, deadline, executable and arguments".into(),
        );
    }
    let fd = args[0].parse::<i32>().map_err(|e| e.to_string())?;
    if fd < 3 {
        return Err("invalid control descriptor".into());
    }
    let ms = args[1].parse::<u64>().map_err(|e| e.to_string())?;
    if ms == 0 || ms > super::profile::MAX_SECONDS * 1000 {
        return Err("invalid supervisor deadline".into());
    }
    let deadline = Instant::now() + Duration::from_millis(ms);
    let mut control = unsafe { UnixStream::from_raw_fd(fd) };
    control
        .set_read_timeout(Some(Duration::from_millis(ms)))
        .map_err(|e| e.to_string())?;
    let mut go = [0];
    if control.read(&mut go).map_err(|e| e.to_string())? != 1 || go != *b"G" {
        return Ok(0);
    }
    reset_signals().map_err(|e| e.to_string())?;
    unsafe {
        libc::signal(libc::SIGTERM, libc::SIG_IGN);
    }
    let mut cmd = Command::new(&args[2]);
    cmd.args(&args[3..])
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    unsafe {
        cmd.pre_exec(move || {
            libc::close(fd);
            reset_signals()
        });
    }
    let mut child = cmd.spawn().map_err(|e| format!("spawn harness: {e}"))?;
    let watched = (|| -> Result<(), String> {
        control
            .set_read_timeout(Some(Duration::from_millis(20)))
            .map_err(|e| e.to_string())?;
        loop {
            let mut byte = [0];
            let stop = match control.read(&mut byte) {
                Ok(_) => true,
                Err(e)
                    if matches!(
                        e.kind(),
                        io::ErrorKind::WouldBlock
                            | io::ErrorKind::TimedOut
                            | io::ErrorKind::Interrupted
                    ) =>
                {
                    false
                }
                Err(_) => true,
            };
            if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
                let mut report = vec![b'X'];
                report.extend_from_slice(&status.code().unwrap_or(-1).to_be_bytes());
                let _ = control.write_all(&report);
                break;
            }
            if stop || Instant::now() >= deadline {
                break;
            }
        }
        Ok(())
    })();
    // The supervisor itself keeps the PGID alive until the final group kill.
    unsafe {
        libc::kill(-libc::getpgrp(), libc::SIGTERM);
    }
    let until = Instant::now() + GRACE;
    while Instant::now() < until {
        let _ = child.try_wait();
        std::thread::sleep(Duration::from_millis(20));
    }
    unsafe {
        libc::kill(-libc::getpgrp(), libc::SIGKILL);
    }
    Err(format!(
        "supervisor survived group kill; stopping is unconfirmed ({watched:?})"
    ))
}

fn relay(path: &str) -> io::Result<()> {
    let mut stream = UnixStream::connect(path)?;
    let mut input = stream.try_clone()?;
    std::thread::spawn(move || {
        let _ = io::copy(&mut io::stdin().lock(), &mut input);
        let _ = input.shutdown(std::net::Shutdown::Write);
    });
    io::copy(&mut stream, &mut io::stdout().lock()).map(|_| ())
}
fn hook(path: &str) -> io::Result<()> {
    let mut stream = UnixStream::connect(path)?;
    stream.set_read_timeout(Some(Duration::from_secs(4)))?;
    let mut raw = Vec::new();
    io::stdin()
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut raw)?;
    if raw.len() > 8 * 1024 * 1024 {
        return Err(io::Error::other("hook input too large"));
    }
    stream.write_all(&raw)?;
    stream.shutdown(std::net::Shutdown::Write)?;
    let mut result = Vec::new();
    stream.take(65537).read_to_end(&mut result)?;
    if result.is_empty() || result.len() > 65536 {
        return Err(io::Error::other("hook owner did not reply"));
    }
    io::stdout().write_all(&result)
}
pub fn helper(args: &[String]) -> Option<i32> {
    let mode = args.first()?.as_str();
    let result = match mode {
        SUPERVISOR => supervisor(&args[1..]),
        RELAY | HOOK => {
            if args.len() == 2 {
                (if mode == RELAY {
                    relay(&args[1])
                } else {
                    hook(&args[1])
                })
                .map(|_| 0)
                .map_err(|e| e.to_string())
            } else {
                Err("private relay needs one socket path".into())
            }
        }
        _ => return None,
    };
    Some(match result {
        Ok(code) => code,
        Err(e) => {
            eprintln!("runtime helper stopped: {e}");
            2
        }
    })
}
