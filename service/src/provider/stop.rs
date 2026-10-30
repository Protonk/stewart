//! The stop path of a placement (INTERFACE 6.8): the close watcher and the
//! signals SIGTERM, SIGINT and SIGHUP.
//!
//! Both fire the placement's [`AbortHandle`], which shuts down any in-flight
//! provider request and is checked before every request and every tool call.
//! Neither fires once a seal is recorded: the run then finishes its delivery
//! first, and the placement ends `sealed`.
//!
//! Signals are blocked in every thread of the process and received by one
//! dedicated thread with `sigwait`, so no code runs in a signal handler and
//! nothing allocates there. The mask must be set before any other thread
//! starts, since threads inherit it.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::time::Duration;

use crate::archive::Audit;
use crate::provider::StopCause;
use crate::provider::transport::AbortHandle;

/// How often the watcher checks for `close_requested` (Appendix B).
pub const WATCH_INTERVAL: Duration = Duration::from_millis(250);

/// What the stop path shares with the loop.
#[derive(Clone, Default)]
pub struct Flags {
    /// A seal was recorded: the stop path no longer applies (6.3, 6.8).
    pub sealed: Arc<AtomicBool>,
    /// A stop signal arrived (also after a seal, when it no longer aborts).
    pub signalled: Arc<AtomicBool>,
}

impl Flags {
    pub fn sealed(&self) -> bool {
        self.sealed.load(Ordering::SeqCst)
    }
    pub fn set_sealed(&self) {
        self.sealed.store(true, Ordering::SeqCst);
    }
}

fn stop_set() -> libc::sigset_t {
    // SAFETY: sigemptyset initializes the set before sigaddset reads it.
    unsafe {
        let mut set: libc::sigset_t = std::mem::zeroed();
        libc::sigemptyset(&mut set);
        libc::sigaddset(&mut set, libc::SIGTERM);
        libc::sigaddset(&mut set, libc::SIGINT);
        libc::sigaddset(&mut set, libc::SIGHUP);
        set
    }
}

/// Block SIGTERM, SIGINT and SIGHUP in the calling thread, and so in every
/// thread it starts afterwards.
pub fn block_signals() -> std::io::Result<()> {
    let set = stop_set();
    // SAFETY: a valid set and a null old-set pointer.
    let rc = unsafe { libc::pthread_sigmask(libc::SIG_BLOCK, &set, std::ptr::null_mut()) };
    if rc != 0 {
        return Err(std::io::Error::from_raw_os_error(rc));
    }
    Ok(())
}

/// Start the thread that receives the blocked stop signals. Each one before
/// a seal fires the stop path with [`StopCause::Signal`]; after a seal it is
/// noted and the delivery in progress continues. The thread lives until the
/// process exits.
pub fn receive_signals(abort: AbortHandle, flags: Flags) -> std::io::Result<()> {
    std::thread::Builder::new()
        .name("stewart-signals".into())
        .spawn(move || {
            let set = stop_set();
            loop {
                let mut sig: libc::c_int = 0;
                // SAFETY: the set is valid and `sig` is a valid out pointer.
                let rc = unsafe { libc::sigwait(&set, &mut sig) };
                if rc != 0 {
                    continue;
                }
                flags.signalled.store(true, Ordering::SeqCst);
                if !flags.sealed() {
                    abort.abort(StopCause::Signal);
                }
            }
        })
        .map(|_| ())
}

/// The close watcher: every 250 ms it reads the log, and when a
/// `close_requested` record is there and no seal has been recorded, it fires
/// the stop path with [`StopCause::Close`]. Dropping the returned guard
/// stops the watcher.
pub struct Watcher {
    stop: Option<mpsc::Sender<()>>,
}

impl Drop for Watcher {
    fn drop(&mut self) {
        // Closing the channel ends the watcher's wait at once.
        self.stop.take();
    }
}

/// Start the watcher in `scope`, reading `audit`'s log.
pub fn watch<'scope, 'env>(
    scope: &'scope std::thread::Scope<'scope, 'env>,
    audit: &'env Audit,
    abort: AbortHandle,
    flags: Flags,
) -> Watcher {
    let (tx, rx) = mpsc::channel::<()>();
    scope.spawn(move || {
        loop {
            if abort.cause().is_some() {
                return;
            }
            let state = crate::log::read(audit);
            if state.close_requested().is_some() && !flags.sealed() {
                abort.abort(StopCause::Close);
                return;
            }
            match rx.recv_timeout(WATCH_INTERVAL) {
                Err(RecvTimeoutError::Timeout) => {}
                _ => return,
            }
        }
    });
    Watcher { stop: Some(tx) }
}
