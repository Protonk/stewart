#![cfg(feature = "claude-code")]
mod answer_support;
mod common;
use answer_support::Live;
use std::time::{Duration, Instant};
use stewart::claude_code::gate::Gate;

#[test]
fn core_recording_obeys_stop_and_fresh_call_invariance() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() + Duration::from_secs(60));
    gate.within(|| live.call("record_account", r#"{"text":"firing control"}"#))
        .ok();
    let revision = live.state().revision();
    let stopped = gate.call();
    stopped.cancel();
    let reply = stopped.within(|| live.call("record_account", r#"{"text":"must not publish"}"#));
    assert_eq!(reply.outcome(), "refused", "{}", reply.text());
    assert_eq!(reply.reason(), "placement_stopped");
    assert_eq!(live.state().revision(), revision);
    gate.call()
        .within(|| live.call("record_account", r#"{"text":"fresh invariance"}"#))
        .ok();
    assert_eq!(live.state().revision(), revision + 1);
}

#[test]
fn expired_deadline_cannot_publish_a_core_record() {
    let mut live = Live::new();
    let gate = Gate::new(Instant::now() - Duration::from_millis(1));
    let reply = gate.within(|| live.call("record_account", r#"{"text":"late"}"#));
    assert_eq!(reply.reason(), "placement_stopped");
    assert_eq!(live.state().revision(), 0);
}
