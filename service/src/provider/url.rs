//! The provider base URL and the HTTPS proxy setting (INTERFACE 6.1).
//!
//! Both are checked before any request: a value outside the grammar below is
//! refused (`provider_url_invalid`, `provider_proxy_invalid`), never repaired.
//!
//! - Base: `https://`, or `http://` for a loopback host only, then a host (a
//!   DNS name, an IPv4 address or a bracketed IPv6 address), an optional
//!   `:port` and an optional path without a trailing `/`; no user
//!   information, query or fragment.
//! - Proxy: `http://host:port`, optionally with one trailing `/`, without
//!   credentials.
//! - Loopback hosts are `localhost` (compared without regard to ASCII case and
//!   connected at 127.0.0.1 without the resolver), 127.0.0.0/8 and `[::1]`.
//!
//! The proxy is used only for an `https://` provider whose host is not
//! loopback; `NO_PROXY` is not consulted.

use std::ffi::OsStr;
use std::net::{Ipv4Addr, Ipv6Addr};

/// The provider base unless `STEWART_PROVIDER_URL` overrides it.
pub const DEFAULT_BASE_URL: &str = "https://api.anthropic.com";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Host {
    /// A DNS name, as written.
    Name(String),
    V4(Ipv4Addr),
    V6(Ipv6Addr),
}

impl Host {
    pub fn is_loopback(&self) -> bool {
        match self {
            Host::Name(n) => n.eq_ignore_ascii_case("localhost"),
            Host::V4(a) => a.octets()[0] == 127,
            Host::V6(a) => *a == Ipv6Addr::LOCALHOST,
        }
    }

    /// Whether the host is an address rather than a name (TLS sends no SNI then).
    pub fn is_address(&self) -> bool {
        !matches!(self, Host::Name(_))
    }
}

/// A checked provider base URL.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Endpoint {
    /// The URL exactly as given.
    pub url: String,
    /// `https://` (true) or loopback `http://` (false).
    pub tls: bool,
    pub host: Host,
    /// The host as written in the URL; an IPv6 address keeps its brackets.
    pub host_text: String,
    /// The port in use: the URL's, else 443 or 80.
    pub port: u16,
    /// Whether the URL names the port (the `host` header carries it only then).
    pub port_given: bool,
    /// The base path: empty, or `/`-separated segments without a trailing `/`.
    pub path: String,
}

impl Endpoint {
    pub fn parse(url: &str) -> Result<Endpoint, String> {
        let (tls, rest) = if let Some(r) = url.strip_prefix("https://") {
            (true, r)
        } else if let Some(r) = url.strip_prefix("http://") {
            (false, r)
        } else {
            return Err(
                "the provider URL must begin with https://, or http:// for a loopback host".into(),
            );
        };
        if rest.contains('?') || rest.contains('#') {
            return Err("the provider URL must not have a query or fragment".into());
        }
        let (authority, path) = match rest.find('/') {
            Some(i) => (&rest[..i], &rest[i..]),
            None => (rest, ""),
        };
        let (host, host_text, port) = authority_parts(authority, "provider URL")?;
        if !path.is_empty() {
            check_path(path)?;
        }
        if !tls && !host.is_loopback() {
            return Err(format!(
                "http:// is allowed only for a loopback host (localhost, 127.0.0.0/8 or [::1]), not {host_text}"
            ));
        }
        Ok(Endpoint {
            url: url.to_string(),
            tls,
            host,
            host_text,
            port: port.unwrap_or(if tls { 443 } else { 80 }),
            port_given: port.is_some(),
            path: path.to_string(),
        })
    }

    /// The pinned base, `https://api.anthropic.com`.
    pub fn default_base() -> Endpoint {
        Endpoint::parse(DEFAULT_BASE_URL).expect("the default base URL is valid")
    }

    /// The `host` header value: the host, and the port only when the URL names one.
    pub fn host_header(&self) -> String {
        if self.port_given {
            format!("{}:{}", self.host_text, self.port)
        } else {
            self.host_text.clone()
        }
    }

    /// The request target, `<path>/v1/messages`.
    pub fn target(&self) -> String {
        format!("{}/v1/messages", self.path)
    }

    /// `<host>:<port>` for the proxy's CONNECT line and its `host` header.
    pub fn authority(&self) -> String {
        format!("{}:{}", self.host_text, self.port)
    }
}

/// The provider base from the `STEWART_PROVIDER_URL` value: the default when
/// unset, else the override. The flag says whether an override supplied it.
/// An override that is set but empty or not UTF-8 is refused: it names no URL,
/// and falling back to the real provider would contradict the caller's intent.
pub fn provider_setting(value: Option<&OsStr>) -> Result<(Endpoint, bool), String> {
    match value {
        None => Ok((Endpoint::default_base(), false)),
        Some(v) => {
            let s = v
                .to_str()
                .ok_or("STEWART_PROVIDER_URL is not valid UTF-8")?;
            if s.is_empty() {
                return Err("STEWART_PROVIDER_URL is set but empty".into());
            }
            Endpoint::parse(s).map(|e| (e, true))
        }
    }
}

/// A checked HTTPS proxy.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Proxy {
    /// The value exactly as given (recorded in `run_started` when in use).
    pub value: String,
    pub host: Host,
    pub host_text: String,
    pub port: u16,
}

impl Proxy {
    pub fn parse(value: &str) -> Result<Proxy, String> {
        let rest = value
            .strip_prefix("http://")
            .ok_or("the proxy must be http://host:port")?;
        let authority = rest.strip_suffix('/').unwrap_or(rest);
        if authority.contains(['/', '?', '#']) {
            return Err(
                "the proxy must be http://host:port, with at most one trailing / and no path, query or fragment"
                    .into(),
            );
        }
        let (host, host_text, port) = authority_parts(authority, "proxy")?;
        let port = port.ok_or("the proxy must name a port (http://host:port)")?;
        Ok(Proxy {
            value: value.to_string(),
            host,
            host_text,
            port,
        })
    }
}

/// The proxy setting from the `HTTPS_PROXY` and `https_proxy` values. The
/// upper-case name is consulted first; a variable that is unset or empty
/// counts as unset. A set value that is invalid is refused even when the other
/// variable holds a valid one: the caller's first choice is never replaced.
pub fn proxy_setting(
    upper: Option<&OsStr>,
    lower: Option<&OsStr>,
) -> Result<Option<Proxy>, String> {
    for (name, v) in [("HTTPS_PROXY", upper), ("https_proxy", lower)] {
        let Some(v) = v else { continue };
        if v.is_empty() {
            continue;
        }
        let s = v
            .to_str()
            .ok_or_else(|| format!("{name} is not valid UTF-8"))?;
        return Proxy::parse(s)
            .map(Some)
            .map_err(|e| format!("{name}: {e}"));
    }
    Ok(None)
}

/// Where an attempt connects: the provider, through the proxy when one is in use.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Route {
    pub endpoint: Endpoint,
    /// The proxy in use: set only for an `https://` provider with a non-loopback host.
    pub proxy: Option<Proxy>,
}

impl Route {
    pub fn new(endpoint: Endpoint, proxy: Option<Proxy>) -> Route {
        let proxied = endpoint.tls && !endpoint.host.is_loopback();
        Route {
            proxy: proxy.filter(|_| proxied),
            endpoint,
        }
    }

    /// The proxy value in use, as `run_started.provider.proxy` records it.
    pub fn proxy_value(&self) -> Option<&str> {
        self.proxy.as_ref().map(|p| p.value.as_str())
    }
}

/// Host, host text and optional port of an authority without user information.
fn authority_parts(a: &str, what: &str) -> Result<(Host, String, Option<u16>), String> {
    if a.is_empty() {
        return Err(format!("the {what} names no host"));
    }
    if a.contains('@') {
        return Err(format!(
            "the {what} must not carry user information or credentials"
        ));
    }
    let (host, host_text, port_text) = if let Some(inner) = a.strip_prefix('[') {
        let close = inner
            .find(']')
            .ok_or_else(|| format!("the {what}'s IPv6 address must end with ]"))?;
        let addr: Ipv6Addr = inner[..close].parse().map_err(|_| {
            format!(
                "the {what}'s host [{}] is not an IPv6 address",
                &inner[..close]
            )
        })?;
        let rest = &inner[close + 1..];
        let port =
            if rest.is_empty() {
                None
            } else {
                Some(rest.strip_prefix(':').ok_or_else(|| {
                    format!("the {what} has unexpected text after its IPv6 address")
                })?)
            };
        (Host::V6(addr), a[..close + 2].to_string(), port)
    } else {
        let (h, p) = match a.split_once(':') {
            Some((h, p)) => (h, Some(p)),
            None => (a, None),
        };
        (host(h, what)?, h.to_string(), p)
    };
    let port = match port_text {
        None => None,
        Some(p) => Some(port(p, what)?),
    };
    Ok((host, host_text, port))
}

fn host(h: &str, what: &str) -> Result<Host, String> {
    if h.is_empty() {
        return Err(format!("the {what} names no host"));
    }
    // Text made only of digits and dots is an IPv4 address or nothing: a
    // resolver would read `1.2.3` or `010.0.0.1` in surprising ways.
    if h.bytes().all(|c| c.is_ascii_digit() || c == b'.') {
        return h
            .parse::<Ipv4Addr>()
            .map(Host::V4)
            .map_err(|_| format!("the {what}'s host {h} is not a dotted-quad IPv4 address"));
    }
    if h.len() > 253 {
        return Err(format!(
            "the {what}'s host name is longer than 253 characters"
        ));
    }
    for label in h.split('.') {
        let ok = !label.is_empty()
            && label.len() <= 63
            && label
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || c == b'-')
            && !label.starts_with('-')
            && !label.ends_with('-');
        if !ok {
            return Err(format!(
                "the {what}'s host {h:?} is not a DNS name (letters, digits and inner hyphens in dot-separated labels), an IPv4 address or a bracketed IPv6 address"
            ));
        }
    }
    Ok(Host::Name(h.to_string()))
}

fn port(p: &str, what: &str) -> Result<u16, String> {
    let bad = || format!("the {what}'s port {p:?} is not a number from 1 to 65535");
    if p.is_empty() || p.len() > 5 || !p.bytes().all(|c| c.is_ascii_digit()) {
        return Err(bad());
    }
    match p.parse::<u32>() {
        Ok(n) if (1..=65_535).contains(&n) => Ok(n as u16),
        _ => Err(bad()),
    }
}

/// A path is `/`-separated segments of RFC 3986 path characters, with no
/// trailing `/`.
fn check_path(p: &str) -> Result<(), String> {
    if p.ends_with('/') {
        return Err("the provider URL's path must not end with /".into());
    }
    let b = p.as_bytes();
    let mut i = 0;
    while i < b.len() {
        let c = b[i];
        if c == b'%' {
            if i + 2 < b.len() && b[i + 1].is_ascii_hexdigit() && b[i + 2].is_ascii_hexdigit() {
                i += 3;
                continue;
            }
            return Err("the provider URL's path has a % not followed by two hex digits".into());
        }
        let ok = c.is_ascii_alphanumeric() || b"-._~!$&'()*+,;=:@/".contains(&c);
        if !ok {
            return Err(format!(
                "the provider URL's path has a character not allowed in a URL path at byte {i}"
            ));
        }
        i += 1;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ok(url: &str) -> Endpoint {
        Endpoint::parse(url).unwrap_or_else(|e| panic!("{url}: {e}"))
    }

    fn refused(url: &str) -> String {
        match Endpoint::parse(url) {
            Ok(e) => panic!("{url} was accepted as {e:?}"),
            Err(e) => e,
        }
    }

    #[test]
    fn default_base_is_https_without_port() {
        let e = Endpoint::default_base();
        assert!(e.tls);
        assert_eq!(e.host, Host::Name("api.anthropic.com".into()));
        assert_eq!(e.port, 443);
        assert!(!e.port_given);
        assert_eq!(e.host_header(), "api.anthropic.com");
        assert_eq!(e.target(), "/v1/messages");
        assert_eq!(e.authority(), "api.anthropic.com:443");
        let (e, overridden) = provider_setting(None).unwrap();
        assert_eq!(e.url, DEFAULT_BASE_URL);
        assert!(!overridden);
    }

    #[test]
    fn accepts_the_override_grammar() {
        let e = ok("https://gateway.example.com:8443/anthropic/proxy");
        assert_eq!(e.port, 8443);
        assert!(e.port_given);
        assert_eq!(e.host_header(), "gateway.example.com:8443");
        assert_eq!(e.target(), "/anthropic/proxy/v1/messages");

        let e = ok("http://127.0.0.1:8080");
        assert!(!e.tls);
        assert_eq!(e.host, Host::V4(Ipv4Addr::new(127, 0, 0, 1)));
        assert_eq!(e.host_header(), "127.0.0.1:8080");

        let e = ok("http://127.45.6.7");
        assert_eq!(e.port, 80);
        assert_eq!(e.host_header(), "127.45.6.7");

        let e = ok("http://[::1]:9000/p");
        assert_eq!(e.host, Host::V6(Ipv6Addr::LOCALHOST));
        assert_eq!(e.host_text, "[::1]");
        assert_eq!(e.host_header(), "[::1]:9000");
        assert_eq!(e.target(), "/p/v1/messages");

        let e = ok("http://localhost:3000");
        assert!(e.host.is_loopback());
        assert!(ok("http://LocalHost:3000").host.is_loopback());

        let e = ok("https://[2001:db8::1]");
        assert_eq!(e.authority(), "[2001:db8::1]:443");
        assert!(e.host.is_address());

        let (e, overridden) = provider_setting(Some(OsStr::new("https://localhost:9443"))).unwrap();
        assert!(overridden);
        assert_eq!(e.port, 9443);
    }

    #[test]
    fn refuses_everything_else() {
        assert!(refused("ftp://example.com").contains("https://"));
        assert!(refused("HTTPS://example.com").contains("https://"));
        assert!(refused("example.com").contains("https://"));
        assert!(refused("http://example.com").contains("loopback"));
        assert!(refused("http://10.0.0.1:80").contains("loopback"));
        assert!(refused("http://[::ffff:127.0.0.1]").contains("loopback"));
        assert!(refused("http://localhost.example").contains("loopback"));
        assert!(refused("https://example.com/").contains("end with /"));
        assert!(refused("https://example.com/v1/").contains("end with /"));
        assert!(refused("https://example.com?x=1").contains("query"));
        assert!(refused("https://example.com/p#f").contains("fragment"));
        assert!(refused("https://user:pw@example.com").contains("user information"));
        assert!(refused("https://user@example.com").contains("user information"));
        assert!(refused("https://").contains("no host"));
        assert!(refused("https://:443").contains("no host"));
        assert!(refused("https://example.com:").contains("port"));
        assert!(refused("https://example.com:0").contains("port"));
        assert!(refused("https://example.com:65536").contains("port"));
        assert!(refused("https://example.com:+443").contains("port"));
        assert!(refused("https://example.com:443:1").contains("port"));
        assert!(refused("https://ex ample.com").contains("DNS name"));
        assert!(refused("https://-bad.com").contains("DNS name"));
        assert!(refused("https://example.com.").contains("DNS name"));
        assert!(refused("https://exa_mple.com").contains("DNS name"));
        assert!(refused("https://ex\u{e4}mple.com").contains("DNS name"));
        assert!(refused("https://256.1.1.1").contains("IPv4"));
        assert!(refused("https://1.2.3").contains("IPv4"));
        assert!(refused("https://010.0.0.1").contains("IPv4"));
        assert!(refused("https://[::1").contains("]"));
        assert!(refused("https://[fe80::1%25en0]").contains("IPv6"));
        assert!(refused("https://[::1]x").contains("after"));
        assert!(refused("https://::1").contains("no host"));
        assert!(refused("https://example.com/a b").contains("not allowed"));
        assert!(refused("https://example.com/a%2").contains("hex"));
        assert!(refused("https://example.com/a%zz").contains("hex"));
        assert!(provider_setting(Some(OsStr::new(""))).is_err());
        let long = format!("https://{}.com", "a".repeat(64));
        assert!(refused(&long).contains("DNS name"));
    }

    #[test]
    fn path_characters_and_escapes_are_allowed() {
        let e = ok("https://example.com/a-b_c.d~e/%2F/x:y@z;p=1");
        assert_eq!(e.path, "/a-b_c.d~e/%2F/x:y@z;p=1");
    }

    #[test]
    fn proxy_grammar() {
        let p = Proxy::parse("http://proxy.internal:3128").unwrap();
        assert_eq!(p.port, 3128);
        assert_eq!(p.host_text, "proxy.internal");
        let p = Proxy::parse("http://127.0.0.1:8888/").unwrap();
        assert_eq!(p.value, "http://127.0.0.1:8888/");
        assert_eq!(p.host, Host::V4(Ipv4Addr::new(127, 0, 0, 1)));
        let p = Proxy::parse("http://[::1]:3128").unwrap();
        assert_eq!(p.host_text, "[::1]");
        for bad in [
            "https://proxy:3128",
            "proxy:3128",
            "http://proxy",
            "http://proxy:",
            "http://proxy:3128//",
            "http://proxy:3128/path",
            "http://user:pw@proxy:3128",
            "http://proxy:3128?x",
            "http://proxy:3128#x",
            "socks5://proxy:1080",
            "http://:3128",
        ] {
            assert!(Proxy::parse(bad).is_err(), "{bad} was accepted");
        }
    }

    #[test]
    fn proxy_setting_precedence_and_empty_values() {
        let up = OsStr::new("http://upper:1");
        let low = OsStr::new("http://lower:2");
        assert_eq!(proxy_setting(None, None).unwrap(), None);
        assert_eq!(
            proxy_setting(Some(up), Some(low))
                .unwrap()
                .unwrap()
                .host_text,
            "upper"
        );
        assert_eq!(
            proxy_setting(None, Some(low)).unwrap().unwrap().host_text,
            "lower"
        );
        assert_eq!(
            proxy_setting(Some(OsStr::new("")), Some(low))
                .unwrap()
                .unwrap()
                .host_text,
            "lower"
        );
        assert_eq!(proxy_setting(Some(OsStr::new("")), None).unwrap(), None);
        let e = proxy_setting(Some(OsStr::new("http://u:p@x:1")), Some(low)).unwrap_err();
        assert!(e.starts_with("HTTPS_PROXY"), "{e}");
        let e = proxy_setting(None, Some(OsStr::new("bad"))).unwrap_err();
        assert!(e.starts_with("https_proxy"), "{e}");
    }

    #[test]
    fn the_proxy_is_used_only_for_non_loopback_https() {
        let p = Proxy::parse("http://proxy:3128").unwrap();
        let r = Route::new(Endpoint::default_base(), Some(p.clone()));
        assert_eq!(r.proxy_value(), Some("http://proxy:3128"));
        for base in [
            "https://localhost:9443",
            "https://127.0.0.2",
            "https://[::1]:1",
            "http://127.0.0.1:8080",
        ] {
            let r = Route::new(ok(base), Some(p.clone()));
            assert_eq!(r.proxy, None, "{base} used the proxy");
        }
        let r = Route::new(ok("https://10.1.2.3"), Some(p));
        assert!(r.proxy.is_some());
        assert_eq!(
            Route::new(Endpoint::default_base(), None).proxy_value(),
            None
        );
    }
}
