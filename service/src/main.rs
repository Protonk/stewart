//! Apparatus check binary: links the release dependency set and reports what it
//! was built for. The audit service replaces this in step 3.
use std::sync::Arc;

fn main() {
    let provider = Arc::new(rustls::crypto::ring::default_provider());
    let mut roots = rustls::RootCertStore::empty();
    roots.extend(webpki_roots::TLS_SERVER_ROOTS.iter().cloned());
    let config = rustls::ClientConfig::builder_with_provider(provider)
        .with_safe_default_protocol_versions()
        .expect("ring supports the default protocol versions")
        .with_root_certificates(roots)
        .with_no_client_auth();
    use sha2::Digest;
    let digest = sha2::Sha256::digest(b"stewart");
    println!(
        "stewart apparatus check: arch={} os={} env={} roots={} alpn={} sha256(stewart)={:x} pid={}",
        std::env::consts::ARCH,
        std::env::consts::OS,
        if cfg!(target_env = "musl") { "musl" } else { "other" },
        webpki_roots::TLS_SERVER_ROOTS.len(),
        config.alpn_protocols.len(),
        digest,
        unsafe { libc::getpid() },
    );
}
