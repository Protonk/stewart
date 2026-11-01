//! Provider credentials: bounded descriptor input, explicit secret access and
//! reflection detection. Raw provider evidence is retained unchanged; detection
//! prevents its use as an auditor response and marks it for private review.

use std::fs::File;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::OsStringExt;
use std::time::{Duration, Instant};

use secrecy::{ExposeSecret, SecretString};
use zeroize::Zeroizing;

use crate::json::{J, JsonError, Obj};
use crate::runs::Headers;

pub const KEY_LIMIT: usize = 4096;
pub const READ_TIMEOUT: Duration = Duration::from_secs(5);
pub const REDACTED: &str = "[REDACTED credential]";

pub struct KeyError {
    pub reason: &'static str,
    pub message: String,
}

fn fail(reason: &'static str, message: impl Into<String>) -> KeyError {
    KeyError {
        reason,
        message: message.into(),
    }
}

/// Capture the input descriptor before opening archive files. An invalid number
/// must never become valid because a later archive open reused it. Ownership is
/// transferred to this invocation; every return drops and closes a valid input.
pub enum Input {
    Environment,
    Descriptor(Result<File, io::Error>),
}

impl Input {
    pub fn capture(fd: Option<i32>) -> Input {
        let Some(fd) = fd else {
            return Input::Environment;
        };
        // SAFETY: fcntl observes an integer descriptor; a successful F_GETFD
        // establishes it is open before ownership is transferred into File.
        let flags = unsafe { libc::fcntl(fd, libc::F_GETFD) };
        if flags < 0 {
            return Input::Descriptor(Err(io::Error::last_os_error()));
        }
        let file = unsafe { File::from_raw_fd(fd) };
        if unsafe { libc::fcntl(fd, libc::F_SETFD, flags | libc::FD_CLOEXEC) } < 0 {
            return Input::Descriptor(Err(io::Error::last_os_error()));
        }
        Input::Descriptor(Ok(file))
    }

    pub fn read(self) -> Result<SecretString, KeyError> {
        // Presence only, without making a secret-bearing environment copy before
        // process protection. This invocation has not started helper threads.
        let env_present = !unsafe { libc::getenv(c"ANTHROPIC_API_KEY".as_ptr()) }.is_null();
        if matches!(self, Input::Descriptor(_)) && env_present {
            return Err(fail(
                "provider_key_source_conflict",
                "--key-fd and ANTHROPIC_API_KEY are both present; select exactly one credential source.",
            ));
        }
        crate::platform::protect_credential().map_err(|e| fail(
            "provider_key_protection_failed",
            format!("The process could not disable credential inspection/core dumps: {}. No credential was read.", crate::util::describe(&e)),
        ))?;
        let bytes = match self {
            Input::Environment => Zeroizing::new(
                std::env::var_os("ANTHROPIC_API_KEY")
                    .unwrap_or_default()
                    .into_vec(),
            ),
            Input::Descriptor(file) => {
                let file = file.map_err(|e| unreadable(&e))?;
                read_descriptor(file)?
            }
        };
        if bytes.is_empty() {
            return Err(fail(
                "provider_key_missing",
                "The selected provider credential is empty or absent.",
            ));
        }
        if bytes.len() > KEY_LIMIT || !bytes.iter().all(|b| (0x21..=0x7e).contains(b)) {
            return Err(fail(
                "provider_key_invalid",
                "The provider credential must contain 1–4096 visible ASCII bytes (0x21–0x7E).",
            ));
        }
        // Validation establishes UTF-8. The temporary input is wiped on drop;
        // SecretString owns the one long-lived copy and redacts Debug output.
        Ok(SecretString::from(
            std::str::from_utf8(&bytes).expect("visible ASCII"),
        ))
    }
}

fn unreadable(e: &io::Error) -> KeyError {
    fail(
        "provider_key_unreadable",
        format!(
            "The credential descriptor could not be read: {}.",
            crate::util::describe(e)
        ),
    )
}

fn read_descriptor(file: File) -> Result<Zeroizing<Vec<u8>>, KeyError> {
    let fd = file.as_raw_fd();
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
    if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
        return Err(unreadable(&io::Error::last_os_error()));
    }
    let deadline = Instant::now() + READ_TIMEOUT;
    let mut bytes = Zeroizing::new(Vec::with_capacity(KEY_LIMIT + 2));
    let mut buf = Zeroizing::new([0u8; KEY_LIMIT + 2]);
    loop {
        let now = Instant::now();
        if now >= deadline {
            return Err(fail(
                "provider_key_unreadable",
                "The credential descriptor did not reach EOF within five seconds.",
            ));
        }
        let mut pfd = libc::pollfd {
            fd,
            events: libc::POLLIN,
            revents: 0,
        };
        let millis = deadline
            .duration_since(now)
            .as_millis()
            .clamp(1, i32::MAX as u128) as i32;
        let ready = unsafe { libc::poll(&mut pfd, 1, millis) };
        if ready < 0 {
            let e = io::Error::last_os_error();
            if e.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(unreadable(&e));
        }
        if ready == 0 {
            continue;
        }
        let n = unsafe { libc::read(fd, buf.as_mut_ptr().cast(), buf.len()) };
        if n < 0 {
            let e = io::Error::last_os_error();
            if matches!(
                e.kind(),
                io::ErrorKind::Interrupted | io::ErrorKind::WouldBlock
            ) {
                continue;
            }
            return Err(unreadable(&e));
        }
        if n == 0 {
            break;
        }
        if bytes.len() + n as usize > KEY_LIMIT + 1 {
            return Err(fail(
                "provider_key_invalid",
                "The provider credential exceeds 4096 bytes plus an optional final LF.",
            ));
        }
        bytes.extend_from_slice(&buf[..n as usize]);
    }
    if bytes.last() == Some(&b'\n') {
        bytes.pop();
    }
    Ok(bytes)
}

/// Which exact retained surfaces contain the current credential. This marker is
/// always present, including clean attempts, so export tooling need not infer a
/// negative result from missing data.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Reflection {
    pub body: bool,
    pub headers: Vec<String>,
}

impl Reflection {
    pub fn found(&self) -> bool {
        self.body || !self.headers.is_empty()
    }
    pub fn to_j(&self) -> J {
        J::obj()
            .with("body", self.body)
            .with("headers", crate::json::strs(&self.headers))
    }
    pub fn decode(o: &Obj) -> Result<Reflection, JsonError> {
        o.exactly(&["body", "headers"])?;
        let headers: Vec<String> = o.strs("headers")?.into_iter().map(str::to_string).collect();
        let expected: Vec<String> = crate::runs::RECORDED_HEADERS
            .iter()
            .filter(|n| headers.iter().any(|h| h == **n))
            .map(|n| n.to_string())
            .collect();
        if headers != expected {
            return Err(o.invalid("headers", "expected unique recorded header names in content-type, request-id, retry-after order"));
        }
        Ok(Reflection {
            body: o.bool("body")?,
            headers,
        })
    }
}

/// Linear-time matching, also over JSON escapes, without allocating a decoded
/// copy of a response or the secret. Escapes are recognized even in incomplete
/// JSON, because a truncated/error response still requires detection.
pub fn reflects(bytes: &[u8], key: &SecretString) -> bool {
    let needle = key.expose_secret().as_bytes();
    if needle.is_empty() {
        return false;
    }
    let mut prefix = vec![0usize; needle.len()];
    for i in 1..needle.len() {
        let mut j = prefix[i - 1];
        while j > 0 && needle[i] != needle[j] {
            j = prefix[j - 1];
        }
        if needle[i] == needle[j] {
            j += 1;
        }
        prefix[i] = j;
    }
    let matches = |iter: &mut dyn Iterator<Item = u8>| {
        let mut j = 0;
        for b in iter {
            while j > 0 && b != needle[j] {
                j = prefix[j - 1];
            }
            if b == needle[j] {
                j += 1;
            }
            if j == needle.len() {
                return true;
            }
        }
        false
    };
    if matches(&mut bytes.iter().copied()) {
        return true;
    }
    let mut i = 0;
    matches(&mut std::iter::from_fn(|| {
        let b = *bytes.get(i)?;
        i += 1;
        if b != b'\\' {
            return Some(b);
        }
        let Some(&escaped) = bytes.get(i) else {
            return Some(b);
        };
        match escaped {
            b'"' | b'\\' | b'/' => {
                i += 1;
                Some(escaped)
            }
            b'b' | b'f' | b'n' | b'r' | b't' => {
                i += 1;
                Some(match escaped {
                    b'b' => 8,
                    b'f' => 12,
                    b'n' => 10,
                    b'r' => 13,
                    _ => 9,
                })
            }
            b'u' if bytes.len() >= i + 5 => {
                let code = bytes[i + 1..i + 5]
                    .iter()
                    .try_fold(0u32, |n, c| (*c as char).to_digit(16).map(|v| n * 16 + v));
                if let Some(code) = code {
                    i += 5;
                    Some(if code <= 127 { code as u8 } else { 0 })
                } else {
                    Some(b)
                }
            }
            _ => Some(b),
        }
    }))
}

pub fn reflection(body: &[u8], headers: &Headers, key: &SecretString) -> Reflection {
    let mut found = Reflection {
        body: reflects(body, key),
        headers: Vec::new(),
    };
    for (name, values) in [
        ("content-type", &headers.content_type),
        ("request-id", &headers.request_id),
        ("retry-after", &headers.retry_after),
    ] {
        if values.iter().any(|v| reflects(v.as_bytes(), key)) {
            found.headers.push(name.into());
        }
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reflection_matches_literal_and_mixed_escapes_in_partial_json() {
        let key = SecretString::from("sk-a/b\\c\"");
        for b in [
            br#"prefix sk-a/b\c" suffix"#.as_slice(),
            br#"{"x":"\u0073k-a\/b\\c\""#.as_slice(),
        ] {
            assert!(reflects(b, &key));
        }
        assert!(!reflects(br#"{"x":"sk-a/b-other"}"#, &key));
        assert!(!reflects(br#"\\u0073k-a\/b\\c\""#, &key));
    }
    #[test]
    fn reflection_reports_retained_surfaces_without_changing_them() {
        let key = SecretString::from("test-secret");
        let headers = Headers {
            content_type: vec!["application/json".into()],
            request_id: vec!["test-secret".into()],
            retry_after: Vec::new(),
        };
        let found = reflection(b"{\"error\":\"test-\\u0073ecret\"", &headers, &key);
        assert_eq!(
            found,
            Reflection {
                body: true,
                headers: vec!["request-id".into()]
            }
        );
        let clean = reflection(b"ordinary provider failure", &Headers::default(), &key);
        assert_eq!(clean, Reflection::default());
        assert!(headers.request_id[0].contains("test-secret"));
    }
}
