//! Identifiers, handles and the manager reference (INTERFACE 2).

use crate::util;
use std::io;

const B32: &[u8; 32] = b"abcdefghijklmnopqrstuvwxyz234567";

/// Lowercase RFC 4648 base32 without padding.
pub fn base32(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().div_ceil(5) * 8);
    let mut acc: u32 = 0;
    let mut bits = 0u32;
    for &b in bytes {
        acc = (acc << 8) | b as u32;
        bits += 8;
        while bits >= 5 {
            bits -= 5;
            out.push(B32[((acc >> bits) & 31) as usize] as char);
        }
    }
    if bits > 0 {
        out.push(B32[((acc << (5 - bits)) & 31) as usize] as char);
    }
    out
}

fn is_b32(s: &str) -> bool {
    s.bytes()
        .all(|b| b.is_ascii_lowercase() || (b'2'..=b'7').contains(&b))
}

/// A store (`s`) or audit (`a`) identifier: the prefix and 16 base32
/// characters encoding 80 random bits.
pub fn new_id(prefix: char) -> io::Result<String> {
    let mut buf = [0u8; 10];
    crate::platform::random_fill(&mut buf)?;
    Ok(format!("{prefix}{}", base32(&buf)))
}

pub fn is_id(s: &str, prefix: char) -> bool {
    s.len() == 17 && s.starts_with(prefix) && is_b32(&s[1..])
}

/// A random name for a stage file (not an identifier anyone holds).
pub fn random_token() -> io::Result<String> {
    let mut buf = [0u8; 10];
    crate::platform::random_fill(&mut buf)?;
    Ok(base32(&buf))
}

/// The 6-character check of a handle:
/// base32(SHA-256("stewart.handle/1\0store\0audit\0kind\0object\0binding")).
pub fn check(store: &str, audit: &str, kind: &str, object: &str, binding: &[&str]) -> String {
    let mut msg = Vec::new();
    msg.extend_from_slice(b"stewart.handle/1");
    for part in [store, audit, kind, object] {
        msg.push(0);
        msg.extend_from_slice(part.as_bytes());
    }
    msg.push(0);
    msg.extend_from_slice(binding.join("\0").as_bytes());
    let digest = util::sha256_raw(&msg);
    base32(&digest)[..6].to_string()
}

pub fn handle(store: &str, audit: &str, kind: &str, object: &str, binding: &[&str]) -> String {
    format!("{object}.{}", check(store, audit, kind, object, binding))
}

/// Split a manager preparation handle `mp<n>.<check>` into its number and check.
/// Anything not of that exact shape is `None`.
pub fn parse_mp(h: &str) -> Option<(u64, &str)> {
    let rest = h.strip_prefix("mp")?;
    let (num, chk) = rest.split_once('.')?;
    if num.is_empty()
        || num.len() > 9
        || !num.bytes().all(|b| b.is_ascii_digit())
        || num.starts_with('0')
    {
        return None;
    }
    if chk.len() != 6 || !is_b32(chk) {
        return None;
    }
    Some((num.parse().ok()?, chk))
}

// ---------------------------------------------------------------------------
// The manager reference: stw1:<audit-id>:<store-id>:<encoded archive root>.

#[derive(Debug, Clone, PartialEq)]
pub struct Reference {
    pub audit: String,
    pub store: String,
    pub root: String,
}

fn unreserved(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'/' | b'.' | b'_' | b'-')
}

pub fn encode_root(root: &str) -> String {
    let mut s = String::new();
    for &b in root.as_bytes() {
        if unreserved(b) {
            s.push(b as char);
        } else {
            s.push_str(&format!("%{b:02X}"));
        }
    }
    s
}

pub fn encode_reference(audit: &str, store: &str, root: &str) -> String {
    format!("stw1:{audit}:{store}:{}", encode_root(root))
}

/// Check the shape required of an archive root (and other absolute paths
/// Stewart records): UTF-8, absolute, no `.`, `..` or empty components and no
/// trailing `/` (the root directory `/` itself is allowed).
pub fn check_absolute(path: &str) -> Result<(), &'static str> {
    if !path.starts_with('/') {
        return Err("the path must be absolute");
    }
    if path.contains('\0') {
        return Err("the path contains NUL");
    }
    if path == "/" {
        return Ok(());
    }
    if path.ends_with('/') {
        return Err("the path must not end with /");
    }
    for c in path[1..].split('/') {
        match c {
            "" => return Err("the path has an empty component (//)"),
            "." | ".." => return Err("the path has a . or .. component"),
            _ => {}
        }
    }
    Ok(())
}

pub fn decode_reference(s: &str) -> Result<Reference, String> {
    let rest = s
        .strip_prefix("stw1:")
        .ok_or("a reference begins with stw1:")?;
    let mut parts = rest.splitn(3, ':');
    let audit = parts.next().unwrap_or("");
    let store = parts
        .next()
        .ok_or("the reference has no store identifier")?;
    let enc = parts.next().ok_or("the reference has no archive root")?;
    if !is_id(audit, 'a') {
        return Err("the audit identifier is not a- followed by 16 base32 characters".into());
    }
    if !is_id(store, 's') {
        return Err("the store identifier is not s followed by 16 base32 characters".into());
    }
    let b = enc.as_bytes();
    let mut raw = Vec::new();
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' {
            let hex = b.get(i + 1..i + 3).ok_or("an incomplete %XX escape")?;
            let ok = hex
                .iter()
                .all(|c| c.is_ascii_digit() || (b'A'..=b'F').contains(c));
            if !ok {
                return Err("a %XX escape must use uppercase hexadecimal".into());
            }
            let v = u8::from_str_radix(std::str::from_utf8(hex).unwrap_or("zz"), 16)
                .map_err(|_| "a bad %XX escape")?;
            if unreserved(v) {
                return Err("a %XX escape encodes a character that is written plainly".into());
            }
            raw.push(v);
            i += 3;
        } else if unreserved(b[i]) {
            raw.push(b[i]);
            i += 1;
        } else {
            return Err(format!(
                "the byte {:?} must be written as %XX",
                b[i] as char
            ));
        }
    }
    let root = String::from_utf8(raw).map_err(|_| "the archive root is not valid UTF-8")?;
    check_absolute(&root).map_err(|e| format!("archive root: {e}"))?;
    Ok(Reference {
        audit: audit.into(),
        store: store.into(),
        root,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base32_matches_rfc4648_vectors_in_lowercase() {
        assert_eq!(base32(b""), "");
        assert_eq!(base32(b"f"), "my");
        assert_eq!(base32(b"fo"), "mzxq");
        assert_eq!(base32(b"foo"), "mzxw6");
        assert_eq!(base32(b"foob"), "mzxw6yq");
        assert_eq!(base32(b"fooba"), "mzxw6ytb");
        assert_eq!(base32(b"foobar"), "mzxw6ytboi");
    }

    #[test]
    fn ids_have_the_specified_shape() {
        let s = new_id('s').unwrap();
        let a = new_id('a').unwrap();
        assert!(is_id(&s, 's') && is_id(&a, 'a'));
        assert!(!is_id(&s, 'a'));
        assert_ne!(new_id('a').unwrap(), a);
        assert!(!is_id("aQM3X7KD2HZ5VW4NY", 'a'));
        assert!(!is_id("aqm3x7kd2hz5vw4n1", 'a'));
    }

    #[test]
    fn checks_bind_every_part() {
        let base = check("s1", "a1", "mp", "mp1", &["ab"]);
        assert_eq!(base.len(), 6);
        assert!(is_b32(&base));
        assert_eq!(base, check("s1", "a1", "mp", "mp1", &["ab"]));
        for other in [
            check("s2", "a1", "mp", "mp1", &["ab"]),
            check("s1", "a2", "mp", "mp1", &["ab"]),
            check("s1", "a1", "ap", "mp1", &["ab"]),
            check("s1", "a1", "mp", "mp2", &["ab"]),
            check("s1", "a1", "mp", "mp1", &["ac"]),
            check("s1", "a1", "mp", "mp1", &["a", "b"]),
        ] {
            assert_ne!(base, other);
        }
        // The message layout is exactly the specified one.
        let msg = b"stewart.handle/1\0s1\0a1\0mp\0mp1\0ab";
        assert_eq!(base, base32(&util::sha256_raw(msg))[..6]);
    }

    #[test]
    fn manager_preparation_handles_parse_strictly() {
        assert_eq!(parse_mp("mp2.k4q7xa"), Some((2, "k4q7xa")));
        for bad in [
            "mp0.k4q7xa",
            "mp02.k4q7xa",
            "mp2.k4q7x",
            "mp2.K4Q7XA",
            "ap2.k4q7xa",
            "mp.k4q7xa",
            "mp2k4q7xa",
            "mp2.k4q7xa1",
        ] {
            assert_eq!(parse_mp(bad), None, "{bad}");
        }
    }

    #[test]
    fn references_round_trip_and_refuse_noncanonical_forms() {
        let r = encode_reference(
            "aqm3x7kd2hz5vw4ny",
            "s7tq2bk6xm3ra4pfe",
            "/home/ana/stewart-archive",
        );
        assert_eq!(
            r,
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/home/ana/stewart-archive"
        );
        let d = decode_reference(&r).unwrap();
        assert_eq!(d.root, "/home/ana/stewart-archive");
        let odd = "/home/ana/my archive:é%";
        let r = encode_reference("aqm3x7kd2hz5vw4ny", "s7tq2bk6xm3ra4pfe", odd);
        assert!(r.ends_with("/home/ana/my%20archive%3A%C3%A9%25"));
        assert_eq!(decode_reference(&r).unwrap().root, odd);
        for bad in [
            "stw2:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:x",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x/",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x/../y",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x//y",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x%2fy",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x%41",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/a b",
            "stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/%FF",
            "stw1:sqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/x",
            "stw1:aqm3x7kd2hz5vw4ny:/x",
        ] {
            assert!(decode_reference(bad).is_err(), "{bad}");
        }
        assert!(decode_reference("stw1:aqm3x7kd2hz5vw4ny:s7tq2bk6xm3ra4pfe:/").is_ok());
    }
}
