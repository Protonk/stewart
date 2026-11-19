//! The C12 firing control for offline commission (INTERFACE Appendix C.2).
//! A loopback listener witnesses a connection when the control has a provider key.
#![cfg(feature = "sabotage")]

mod common;
use common::*;

const SAB: &str = "STEWART_TEST_SABOTAGE";

#[test]
fn commission_over_network() {
    let e = Env::new();
    let (r, h) = e.prepared(&[("a", b"a")]);
    let args = [
        "commission",
        r.as_str(),
        h.as_str(),
        "--i-am-finished",
        "--json",
    ];
    let o = e.run_env(&args, &[(SAB, "commission_over_network")]);
    assert_eq!(s(&o.json(), &["reason"]), "provider_key_missing");
    // With a key, it reaches the provider (a listener this test opened on
    // the loopback interface) before accepting.
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://127.0.0.1:{}", listener.local_addr().unwrap().port());
    listener.set_nonblocking(true).unwrap();
    let o = e.run_env(
        &args,
        &[
            (SAB, "commission_over_network"),
            ("ANTHROPIC_API_KEY", "test-key"),
            ("STEWART_PROVIDER_URL", &url),
        ],
    );
    assert_eq!(s(&o.json(), &["effects", "acceptance"]), "accepted");
    assert!(
        listener.accept().is_ok(),
        "the commission connected to the provider"
    );
}
