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
/// process exits. `before_observation` orders any runtime publication gate
/// before the signal flag becomes visible to the placement loop.
pub fn receive_signals(
    abort: AbortHandle,
    flags: Flags,
    before_observation: impl Fn() + Send + 'static,
) -> std::io::Result<()> {
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
                observe_signal(&abort, &flags, &before_observation);
            }
        })
        .map(|_| ())
}

/// The callback can order publication against this observation. It runs in
/// the sigwait thread, not in an asynchronous signal handler, so it may lock.
fn observe_signal(abort: &AbortHandle, flags: &Flags, before_observation: &impl Fn()) {
    before_observation();
    flags.signalled.store(true, Ordering::SeqCst);
    if !flags.sealed() {
        abort.abort(StopCause::Signal);
    }
}

/// The close watcher: every 250 ms it reads the log, and when a
/// `close_requested` record is there and the log holds no seal, it fires
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
            // The stop path applies only while no seal exists, whatever the
            // submit that linked one replied.
            if state.close_requested().is_some() && state.seal().is_none() && !flags.sealed() {
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

#[cfg(all(test, feature = "claude-code"))]
mod tests {
    use super::*;
    use crate::claude_code::gate::Gate;
    use crate::log::{self, PubErr};
    use std::time::Instant;

    #[test]
    fn observed_signal_prevents_publication_without_an_event_loop_poll() {
        let (path, audit) = log::tests::scratch_audit();
        let gate = Gate::new(Instant::now() + Duration::from_secs(60));
        assert!(
            gate.within(|| log::publish(&audit, "reference", |_| Ok(log::tests::reference_body())))
                .is_ok()
        );
        let flags = Flags::default();
        let abort = AbortHandle::new();
        let result = gate.within(|| {
            log::publish(&audit, "close_requested", |_| {
                // The receiver observes the signal after the tool started,
                // before its publication permit. No event-loop poll intervenes.
                observe_signal(&abort, &flags, &|| gate.stop());
                Ok(log::tests::close_body())
            })
        });
        assert!(flags.signalled.load(Ordering::SeqCst));
        assert_eq!(abort.cause(), Some(StopCause::Signal));
        assert!(matches!(result, Err(PubErr::Refused(f)) if f.reason == "placement_stopped"));
        assert_eq!(log::read(&audit).recs.len(), 1);
        assert_eq!(log::unlinked_stage(&audit, &log::read(&audit)).len(), 1);
        let fresh = Gate::new(Instant::now() + Duration::from_secs(60));
        assert!(
            fresh
                .within(|| log::publish(
                    &audit,
                    "close_requested",
                    |_| Ok(log::tests::close_body())
                ))
                .is_ok()
        );
        assert_eq!(log::read(&audit).recs.len(), 2);
        std::fs::remove_dir_all(path).unwrap();
    }

    #[test]
    fn a_publication_permit_orders_before_a_later_signal_observation() {
        let gate = Gate::new(Instant::now() + Duration::from_secs(60));
        let flags = Flags::default();
        let abort = AbortHandle::new();
        let permit = gate.permit().unwrap();
        std::thread::scope(|scope| {
            let (entering, entered) = mpsc::sync_channel(0);
            let (gate, flags, abort) = (&gate, &flags, &abort);
            scope.spawn(move || {
                observe_signal(abort, flags, &|| {
                    entering.send(()).unwrap();
                    gate.stop();
                });
            });
            entered.recv().unwrap();
            assert!(!flags.signalled.load(Ordering::SeqCst));
            assert_eq!(abort.cause(), None);
            drop(permit);
        });
        assert!(flags.signalled.load(Ordering::SeqCst));
        assert_eq!(abort.cause(), Some(StopCause::Signal));
        assert_eq!(gate.permit().err().unwrap().reason, "placement_stopped");
    }
}
