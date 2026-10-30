//! Small shared helpers: digests, UTC timestamps and errno names.

use sha2::{Digest, Sha256};
use std::io;

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex(&Sha256::digest(bytes))
}

pub fn sha256_raw(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

pub fn hex(bytes: &[u8]) -> String {
    const H: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(H[(b >> 4) as usize] as char);
        s.push(H[(b & 15) as usize] as char);
    }
    s
}

pub fn is_hex64(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// Current UTC time as `YYYY-MM-DDTHH:MM:SS.mmmZ`. An observation, never a deadline.
pub fn now_utc() -> String {
    let d = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format_utc(d.as_secs() as i64, d.subsec_millis())
}

pub fn format_utc(secs: i64, millis: u32) -> String {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    let (y, m, d) = civil_from_days(days);
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}.{millis:03}Z",
        rem / 3600,
        (rem % 3600) / 60,
        rem % 60
    )
}

/// Whether `s` has the `at` shape written by `now_utc`.
pub fn is_utc_ms(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 24
        && b.iter().enumerate().all(|(i, c)| match i {
            4 | 7 => *c == b'-',
            10 => *c == b'T',
            13 | 16 => *c == b':',
            19 => *c == b'.',
            23 => *c == b'Z',
            _ => c.is_ascii_digit(),
        })
}

// Howard Hinnant's days-to-civil algorithm.
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// The symbolic name of an OS error (`EIO`), or `errno <n>`, or the error text.
pub fn errno_name(e: &io::Error) -> String {
    let Some(n) = e.raw_os_error() else {
        return e.to_string();
    };
    let name = match n {
        libc::EPERM => "EPERM",
        libc::ENOENT => "ENOENT",
        libc::EINTR => "EINTR",
        libc::EIO => "EIO",
        libc::ENXIO => "ENXIO",
        libc::EBADF => "EBADF",
        libc::EAGAIN => "EAGAIN",
        libc::ENOMEM => "ENOMEM",
        libc::EACCES => "EACCES",
        libc::EBUSY => "EBUSY",
        libc::EEXIST => "EEXIST",
        libc::EXDEV => "EXDEV",
        libc::ENODEV => "ENODEV",
        libc::ENOTDIR => "ENOTDIR",
        libc::EISDIR => "EISDIR",
        libc::EINVAL => "EINVAL",
        libc::ENFILE => "ENFILE",
        libc::EMFILE => "EMFILE",
        libc::EFBIG => "EFBIG",
        libc::ENOSPC => "ENOSPC",
        libc::EROFS => "EROFS",
        libc::EMLINK => "EMLINK",
        libc::EPIPE => "EPIPE",
        libc::ENAMETOOLONG => "ENAMETOOLONG",
        libc::ENOTEMPTY => "ENOTEMPTY",
        libc::ELOOP => "ELOOP",
        libc::EDQUOT => "EDQUOT",
        libc::ETIMEDOUT => "ETIMEDOUT",
        libc::ENOSYS => "ENOSYS",
        libc::EOPNOTSUPP => "EOPNOTSUPP",
        _ => return format!("errno {n}"),
    };
    name.to_string()
}

/// A short "EIO (Input/output error)" description.
pub fn describe(e: &io::Error) -> String {
    match e.raw_os_error() {
        Some(_) => {
            let name = errno_name(e);
            let text = e.to_string();
            let text = text.split(" (os error").next().unwrap_or(&text).to_string();
            format!("{name} ({text})")
        }
        None => e.to_string(),
    }
}

/// Levenshtein distance, for "did you mean" hints on exact names.
pub fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    for i in 1..=a.len() {
        let mut cur = vec![i; b.len() + 1];
        for j in 1..=b.len() {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        prev = cur;
    }
    prev[b.len()]
}

pub fn nearest<'a>(word: &str, choices: &[&'a str]) -> &'a str {
    choices
        .iter()
        .min_by_key(|c| edit_distance(word, c))
        .copied()
        .unwrap_or("")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utc_formatting() {
        assert_eq!(format_utc(0, 0), "1970-01-01T00:00:00.000Z");
        assert_eq!(format_utc(1_793_628_191, 402), "2026-11-02T14:03:11.402Z");
        assert_eq!(format_utc(951_782_400, 7), "2000-02-29T00:00:00.007Z");
        assert!(is_utc_ms(&now_utc()));
        assert!(!is_utc_ms("2026-11-02 13:23:11.402Z"));
    }

    #[test]
    fn digests_and_names() {
        assert_eq!(sha256_hex(b"stewart").len(), 64);
        assert!(is_hex64(&sha256_hex(b"")));
        assert_eq!(errno_name(&io::Error::from_raw_os_error(libc::EIO)), "EIO");
        assert_eq!(
            nearest("limit-turn", &["limit-turns", "model"]),
            "limit-turns"
        );
    }
}
