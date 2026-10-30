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

/// Split `<prefix><n>.<check>` into its number and check. Anything not of
/// that exact shape is `None`.
fn parse_numbered<'a>(h: &'a str, prefix: &str) -> Option<(u64, &'a str)> {
    let rest = h.strip_prefix(prefix)?;
    let (num, chk) = rest.split_once('.')?;
    if num.is_empty()
        || num.len() > 9
        || !num.bytes().all(|b| b.is_ascii_digit())
        || num.starts_with('0')
    {
        return None;
    }
    is_check(chk).then_some(())?;
    Some((num.parse().ok()?, chk))
}

fn is_check(chk: &str) -> bool {
    chk.len() == 6 && is_b32(chk)
}

/// Split a manager preparation handle `mp<n>.<check>` into its number and check.
/// Anything not of that exact shape is `None`.
pub fn parse_mp(h: &str) -> Option<(u64, &str)> {
    parse_numbered(h, "mp")
}

// Handles after launch (2.3). Each `*_handle` builds the one valid handle
// for an object and its binding; a presented handle is valid exactly when it
// equals the handle rebuilt from the records it names. The `parse_*`
// functions only split a handle's shape, so a caller can find the records to
// rebuild it from; they establish nothing.

/// An entry version's handle `<id>.v<version>.<check>`, binding the SHA-256
/// of the `entry` record that created the version.
pub fn entry_handle(
    store: &str,
    audit: &str,
    id: &str,
    version: u64,
    record_sha256: &str,
) -> String {
    handle(
        store,
        audit,
        "entry",
        &format!("{id}.v{version}"),
        &[record_sha256],
    )
}

/// Split `e<n>.v<version>.<check>` into the entry ID and version.
pub fn parse_entry_handle(h: &str) -> Option<(&str, u64)> {
    let (object, chk) = h.rsplit_once('.')?;
    let (id, version) = object.split_once(".v")?;
    crate::names::parse_entry_id(id)?;
    let version = crate::names::parse_num(version)?;
    is_check(chk).then_some((id, version))
}

/// An auditor preparation handle `ap<n>.<check>`, binding the SHA-256 of
/// `prepared/<n>/answer.json`, of `prepared/<n>/answer.md` and the answer
/// revision.
pub fn ap_handle(
    store: &str,
    audit: &str,
    n: u64,
    answer_sha256: &str,
    rendering_sha256: &str,
    revision: u64,
) -> String {
    handle(
        store,
        audit,
        "ap",
        &format!("ap{n}"),
        &[answer_sha256, rendering_sha256, &revision.to_string()],
    )
}

pub fn parse_ap(h: &str) -> Option<u64> {
    parse_numbered(h, "ap").map(|(n, _)| n)
}

/// A prepared view: `<auditor preparation>/rendering` or `/selection`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum View {
    /// `answer.md`.
    Rendering,
    /// `answer.json`.
    Selection,
}

/// Split a prepared view source into the preparation handle and the view.
pub fn parse_view(source: &str) -> Option<(&str, View)> {
    let (ap, view) = source.split_once('/')?;
    parse_ap(ap)?;
    match view {
        "rendering" => Some((ap, View::Rendering)),
        "selection" => Some((ap, View::Selection)),
        _ => None,
    }
}

/// The seal handle `seal.<check>`, binding the SHA-256 of the return manifest.
pub fn seal_handle(store: &str, audit: &str, manifest_sha256: &str) -> String {
    handle(store, audit, "seal", "seal", &[manifest_sha256])
}

/// A confirmation token `cf<n>.<check>` for delivery attempt `n`, binding
/// the manifest's SHA-256 and that of the attempt's `delivery_ended` record.
pub fn cf_handle(
    store: &str,
    audit: &str,
    attempt: u64,
    manifest_sha256: &str,
    ended_sha256: &str,
) -> String {
    handle(
        store,
        audit,
        "cf",
        &format!("cf{attempt}"),
        &[manifest_sha256, ended_sha256],
    )
}

pub fn parse_cf(h: &str) -> Option<u64> {
    parse_numbered(h, "cf").map(|(n, _)| n)
}

/// A loss ID `loss.<member token>.<check>`, binding the manifest's SHA-256
/// and that of the failure record, the attempt's `delivery_ended` (8.4). The
/// token is `names::member_token` of the member.
pub fn loss_handle(
    store: &str,
    audit: &str,
    token: &str,
    manifest_sha256: &str,
    failure_sha256: &str,
) -> String {
    handle(
        store,
        audit,
        "loss",
        &format!("loss.{token}"),
        &[manifest_sha256, failure_sha256],
    )
}

/// The member token of a loss ID.
pub fn parse_loss(h: &str) -> Option<&str> {
    let (object, chk) = h.rsplit_once('.')?;
    let token = object.strip_prefix("loss.")?;
    (!token.is_empty() && is_check(chk)).then_some(token)
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
    fn handles_after_launch_bind_their_objects() {
        let sha = "a".repeat(64);
        let e = entry_handle("s", "a", "e3", 2, &sha);
        assert!(e.starts_with("e3.v2."));
        assert_eq!(&e[6..], check("s", "a", "entry", "e3.v2", &[&sha]));
        assert_eq!(parse_entry_handle(&e), Some(("e3", 2)));
        assert_ne!(e, entry_handle("s", "a", "e3", 2, &"b".repeat(64)));
        for bad in [
            "e3.v2",
            "e3.v02.abcdef",
            "e03.v2.abcdef",
            "x3.v2.abcdef",
            "e3v2.abcdef",
        ] {
            assert_eq!(parse_entry_handle(bad), None, "{bad}");
        }
        let ap = ap_handle("s", "a", 4, &sha, &sha, 7);
        assert_eq!(&ap[4..], check("s", "a", "ap", "ap4", &[&sha, &sha, "7"]));
        assert_ne!(ap, ap_handle("s", "a", 4, &sha, &sha, 8));
        assert_eq!(parse_ap(&ap), Some(4));
        let view = format!("{ap}/rendering");
        assert_eq!(parse_view(&view), Some((ap.as_str(), View::Rendering)));
        assert_eq!(parse_view(&format!("{ap}/other")), None);
        let seal = seal_handle("s", "a", &sha);
        assert_eq!(
            seal,
            format!("seal.{}", check("s", "a", "seal", "seal", &[&sha]))
        );
        let cf = cf_handle("s", "a", 1, &sha, &"c".repeat(64));
        assert_eq!(parse_cf(&cf), Some(1));
        let loss = loss_handle("s", "a", "answer-md", &sha, &sha);
        assert!(loss.starts_with("loss.answer-md."));
        assert_eq!(parse_loss(&loss), Some("answer-md"));
        assert_eq!(parse_loss("loss..abcdef"), None);
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
