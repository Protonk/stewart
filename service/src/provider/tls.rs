//! TLS client configuration for the provider connection (INTERFACE 6.1).
//!
//! The release verifies the provider against the web PKI roots built into it
//! (`webpki-roots`), with the `ring` provider and rustls's safe default
//! protocol versions. A test build can add roots from a PEM file
//! (Appendix C; `fault::transport` reads it); the code that adds them is
//! compiled only into test builds, so the release has no way to trust
//! anything else.

use std::sync::Arc;

use rustls::{ClientConfig, RootCertStore};

#[cfg(any(test, feature = "fault-injection"))]
use rustls::pki_types::CertificateDer;

/// The TLS client configuration every attempt uses.
#[derive(Clone)]
pub struct Tls {
    config: Arc<ClientConfig>,
}

impl std::fmt::Debug for Tls {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Tls")
    }
}

impl Tls {
    /// Verification against the built-in web PKI roots only.
    pub fn web_pki() -> Result<Tls, String> {
        Tls::build(web_roots())
    }

    /// The web PKI roots plus `extra`, for a test provider's certificate.
    #[cfg(any(test, feature = "fault-injection"))]
    pub fn with_extra_roots(extra: &[CertificateDer<'static>]) -> Result<Tls, String> {
        let mut roots = web_roots();
        for (i, c) in extra.iter().enumerate() {
            roots
                .add(c.clone())
                .map_err(|e| format!("test root certificate {} is not usable: {e}", i + 1))?;
        }
        Tls::build(roots)
    }

    fn build(roots: RootCertStore) -> Result<Tls, String> {
        let provider = Arc::new(rustls::crypto::ring::default_provider());
        let config = ClientConfig::builder_with_provider(provider)
            .with_safe_default_protocol_versions()
            .map_err(|e| format!("the TLS configuration could not be built: {e}"))?
            .with_root_certificates(roots)
            .with_no_client_auth();
        Ok(Tls {
            config: Arc::new(config),
        })
    }

    pub(crate) fn config(&self) -> Arc<ClientConfig> {
        Arc::clone(&self.config)
    }
}

fn web_roots() -> RootCertStore {
    RootCertStore {
        roots: webpki_roots::TLS_SERVER_ROOTS.to_vec(),
    }
}

/// The certificates of a PEM text, in order. Sections of other kinds are
/// skipped; a malformed PEM text, or one without a certificate, is an error.
#[cfg(any(test, feature = "fault-injection"))]
pub fn pem_certificates(bytes: &[u8]) -> Result<Vec<CertificateDer<'static>>, String> {
    use rustls::pki_types::pem::{PemObject, SectionKind};
    let mut out = Vec::new();
    for item in <(SectionKind, Vec<u8>)>::pem_slice_iter(bytes) {
        match item {
            Ok((SectionKind::Certificate, der)) => out.push(CertificateDer::from(der)),
            Ok(_) => {}
            Err(e) => return Err(format!("it is not a valid PEM text: {e:?}")),
        }
    }
    if out.is_empty() {
        return Err("it holds no certificate".into());
    }
    Ok(out)
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    pub const CA_PEM: &[u8] = include_bytes!("../../tests/fixtures/provider/ca.pem");
    pub const UNTRUSTED_CA_PEM: &[u8] =
        include_bytes!("../../tests/fixtures/provider/untrusted-ca.pem");
    pub const SERVER_PEM: &[u8] = include_bytes!("../../tests/fixtures/provider/server.pem");
    pub const SERVER_KEY_PEM: &[u8] =
        include_bytes!("../../tests/fixtures/provider/server.key.pem");

    /// A client configuration trusting the test CA.
    pub fn test_tls() -> Tls {
        Tls::with_extra_roots(&pem_certificates(CA_PEM).unwrap()).unwrap()
    }

    /// A server configuration presenting the test leaf (`localhost`,
    /// `api.provider.test`, `127.0.0.1`).
    pub fn server_config() -> Arc<rustls::ServerConfig> {
        use rustls::pki_types::PrivateKeyDer;
        use rustls::pki_types::pem::PemObject;
        let chain = pem_certificates(SERVER_PEM).unwrap();
        let key = PrivateKeyDer::from_pem_slice(SERVER_KEY_PEM).unwrap();
        let provider = Arc::new(rustls::crypto::ring::default_provider());
        Arc::new(
            rustls::ServerConfig::builder_with_provider(provider)
                .with_safe_default_protocol_versions()
                .unwrap()
                .with_no_client_auth()
                .with_single_cert(chain, key)
                .unwrap(),
        )
    }

    #[test]
    fn pem_parsing() {
        assert_eq!(pem_certificates(CA_PEM).unwrap().len(), 1);
        let mut two = CA_PEM.to_vec();
        two.extend_from_slice(SERVER_KEY_PEM);
        two.extend_from_slice(UNTRUSTED_CA_PEM);
        assert_eq!(pem_certificates(&two).unwrap().len(), 2);
        assert!(
            pem_certificates(SERVER_KEY_PEM)
                .unwrap_err()
                .contains("no certificate")
        );
        assert!(
            pem_certificates(b"")
                .unwrap_err()
                .contains("no certificate")
        );
        let broken = b"-----BEGIN CERTIFICATE-----\n!!!!\n-----END CERTIFICATE-----\n";
        assert!(pem_certificates(broken).is_err());
    }

    #[test]
    fn configurations_build() {
        Tls::web_pki().unwrap();
        test_tls();
        let junk = CertificateDer::from(vec![1u8, 2, 3]);
        assert!(
            Tls::with_extra_roots(&[junk])
                .unwrap_err()
                .contains("not usable")
        );
    }
}
