//! Tolerant JSON scanning for provider bodies (INTERFACE 1.2, 6.2).
//!
//! Provider bodies are captured raw and decoded tolerantly: the body must be
//! one JSON text (RFC 8259: UTF-8, no byte-order mark, one value and only
//! whitespace around it), but nothing else of the strict control rules
//! applies. Unknown members may repeat, numbers may be signed or fractional,
//! nesting is unbounded and strings may hold NUL or lone surrogate escapes.
//! Those values are kept as bytes and echoed, never interpreted.
//!
//! The scanner never builds a tree of the whole body. It validates the syntax
//! once with an explicit stack (so a deeply nested `input` cannot exhaust the
//! call stack), then reads the few levels Stewart interprets as byte spans.

/// A byte range `[start, end)` of a body.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Span {
    pub start: usize,
    pub end: usize,
}

impl Span {
    pub fn of<'a>(&self, b: &'a [u8]) -> &'a [u8] {
        &b[self.start..self.end]
    }
    pub fn len(&self) -> usize {
        self.end - self.start
    }
    pub fn is_empty(&self) -> bool {
        self.start == self.end
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Kind {
    Object,
    Array,
    String,
    Number,
    Bool,
    Null,
}

/// The kind of the value starting at `span.start` (the span must be a value).
pub(crate) fn kind(b: &[u8], span: Span) -> Kind {
    match b[span.start] {
        b'{' => Kind::Object,
        b'[' => Kind::Array,
        b'"' => Kind::String,
        b't' | b'f' => Kind::Bool,
        b'n' => Kind::Null,
        _ => Kind::Number,
    }
}

/// Check that `b` is one JSON text and return the span of its value.
pub(crate) fn validate(b: &[u8]) -> Result<Span, String> {
    if let Err(e) = std::str::from_utf8(b) {
        return Err(format!(
            "the body is not valid UTF-8 (byte {})",
            e.valid_up_to()
        ));
    }
    if b.starts_with(b"\xEF\xBB\xBF") {
        return Err("the body begins with a byte-order mark".into());
    }
    let start = ws(b, 0);
    let end = value_end(b, start)?;
    if ws(b, end) != b.len() {
        return Err(format!(
            "the body has bytes after its JSON value (byte {})",
            ws(b, end)
        ));
    }
    Ok(Span { start, end })
}

fn ws(b: &[u8], mut i: usize) -> usize {
    while i < b.len() && matches!(b[i], b' ' | b'\t' | b'\n' | b'\r') {
        i += 1;
    }
    i
}

fn syntax(i: usize, what: &str) -> String {
    format!("the body is not JSON: {what} at byte {i}")
}

/// The end of the value starting at `start` (after whitespace), validating its
/// syntax without recursion.
pub(crate) fn value_end(b: &[u8], start: usize) -> Result<usize, String> {
    let mut stack: Vec<u8> = Vec::new();
    let mut i = start;
    'value: loop {
        i = ws(b, i);
        let Some(&c) = b.get(i) else {
            return Err(syntax(i, "a value is missing"));
        };
        match c {
            b'{' => {
                i = ws(b, i + 1);
                if b.get(i) == Some(&b'}') {
                    i += 1;
                } else {
                    stack.push(b'{');
                    i = key_end(b, i)?;
                    continue 'value;
                }
            }
            b'[' => {
                i = ws(b, i + 1);
                if b.get(i) == Some(&b']') {
                    i += 1;
                } else {
                    stack.push(b'[');
                    continue 'value;
                }
            }
            b'"' => i = string_end(b, i)?,
            b't' => i = literal_end(b, i, b"true")?,
            b'f' => i = literal_end(b, i, b"false")?,
            b'n' => i = literal_end(b, i, b"null")?,
            b'-' | b'0'..=b'9' => i = number_end(b, i)?,
            _ => return Err(syntax(i, "an unexpected character")),
        }
        // After a value: close containers, or move to the next member or element.
        loop {
            let Some(&top) = stack.last() else {
                return Ok(i);
            };
            i = ws(b, i);
            match (top, b.get(i)) {
                (b'{', Some(b',')) => {
                    i = key_end(b, ws(b, i + 1))?;
                    continue 'value;
                }
                (b'[', Some(b',')) => {
                    i += 1;
                    continue 'value;
                }
                (b'{', Some(b'}')) | (b'[', Some(b']')) => {
                    stack.pop();
                    i += 1;
                }
                (b'{', _) => return Err(syntax(i, "expected , or } in an object")),
                _ => return Err(syntax(i, "expected , or ] in an array")),
            }
        }
    }
}

/// A member key and its colon; returns the index after the colon.
fn key_end(b: &[u8], i: usize) -> Result<usize, String> {
    if b.get(i) != Some(&b'"') {
        return Err(syntax(i, "expected a string key"));
    }
    let j = ws(b, string_end(b, i)?);
    if b.get(j) != Some(&b':') {
        return Err(syntax(j, "expected : after a key"));
    }
    Ok(j + 1)
}

fn literal_end(b: &[u8], i: usize, word: &[u8]) -> Result<usize, String> {
    if b[i..].starts_with(word) {
        Ok(i + word.len())
    } else {
        Err(syntax(i, "an unknown literal"))
    }
}

fn number_end(b: &[u8], mut i: usize) -> Result<usize, String> {
    let start = i;
    if b.get(i) == Some(&b'-') {
        i += 1;
    }
    match b.get(i) {
        Some(b'0') => i += 1,
        Some(b'1'..=b'9') => {
            while matches!(b.get(i), Some(b'0'..=b'9')) {
                i += 1;
            }
        }
        _ => return Err(syntax(start, "a malformed number")),
    }
    if b.get(i) == Some(&b'.') {
        i += 1;
        let d = i;
        while matches!(b.get(i), Some(b'0'..=b'9')) {
            i += 1;
        }
        if i == d {
            return Err(syntax(start, "a malformed number"));
        }
    }
    if matches!(b.get(i), Some(b'e' | b'E')) {
        i += 1;
        if matches!(b.get(i), Some(b'+' | b'-')) {
            i += 1;
        }
        let d = i;
        while matches!(b.get(i), Some(b'0'..=b'9')) {
            i += 1;
        }
        if i == d {
            return Err(syntax(start, "a malformed number"));
        }
    }
    Ok(i)
}

/// The end of the string starting at `i` (its opening quote), checking escapes
/// and refusing raw control characters. The input is valid UTF-8.
fn string_end(b: &[u8], i: usize) -> Result<usize, String> {
    let mut j = i + 1;
    loop {
        let Some(&c) = b.get(j) else {
            return Err(syntax(i, "an unterminated string"));
        };
        match c {
            b'"' => return Ok(j + 1),
            b'\\' => match b.get(j + 1) {
                Some(b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't') => j += 2,
                Some(b'u') => {
                    let hex = b.get(j + 2..j + 6).unwrap_or(&[]);
                    if hex.len() != 4 || !hex.iter().all(|h| h.is_ascii_hexdigit()) {
                        return Err(syntax(j, "an invalid \\u escape"));
                    }
                    j += 6;
                }
                _ => return Err(syntax(j, "an invalid escape")),
            },
            0x00..=0x1F => return Err(syntax(j, "an unescaped control character in a string")),
            _ => j += 1,
        }
    }
}

/// Decode a string value (its raw bytes, quotes included). `None` when an
/// escape leaves a lone surrogate, which no Unicode string can hold.
pub(crate) fn decode_string(raw: &[u8]) -> Option<String> {
    let inner = &raw[1..raw.len() - 1];
    if !inner.contains(&b'\\') {
        return std::str::from_utf8(inner).ok().map(str::to_string);
    }
    let mut out = String::with_capacity(inner.len());
    let mut i = 0;
    let hex4 = |at: usize| -> u32 {
        let s = std::str::from_utf8(&inner[at..at + 4]).unwrap_or("0000");
        u32::from_str_radix(s, 16).unwrap_or(0)
    };
    while i < inner.len() {
        let c = inner[i];
        if c != b'\\' {
            // Copy one UTF-8 character.
            let len = match c {
                0x00..=0x7F => 1,
                0xC0..=0xDF => 2,
                0xE0..=0xEF => 3,
                _ => 4,
            };
            out.push_str(std::str::from_utf8(&inner[i..i + len]).ok()?);
            i += len;
            continue;
        }
        let e = inner[i + 1];
        i += 2;
        let ch = match e {
            b'"' => '"',
            b'\\' => '\\',
            b'/' => '/',
            b'b' => '\u{8}',
            b'f' => '\u{c}',
            b'n' => '\n',
            b'r' => '\r',
            b't' => '\t',
            _ => {
                let hi = hex4(i);
                i += 4;
                let cp = if (0xD800..0xDC00).contains(&hi) {
                    if inner.get(i..i + 2) != Some(b"\\u") {
                        return None;
                    }
                    let lo = hex4(i + 2);
                    if !(0xDC00..0xE000).contains(&lo) {
                        return None;
                    }
                    i += 6;
                    0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                } else {
                    hi
                };
                char::from_u32(cp)?
            }
        };
        out.push(ch);
    }
    Some(out)
}

/// The members of the object at `obj`: each key (decoded; `None` when it is
/// not a Unicode string) and its value's span, in order, repeats included.
pub(crate) fn members(b: &[u8], obj: Span) -> Result<Vec<(Option<String>, Span)>, String> {
    let mut out = Vec::new();
    let mut i = ws(b, obj.start + 1);
    if b.get(i) == Some(&b'}') {
        return Ok(out);
    }
    loop {
        let key_start = i;
        let key_stop = string_end(b, key_start)?;
        let key = decode_string(&b[key_start..key_stop]);
        i = ws(b, key_stop);
        if b.get(i) != Some(&b':') {
            return Err(syntax(i, "expected : after a key"));
        }
        let v_start = ws(b, i + 1);
        let v_end = value_end(b, v_start)?;
        out.push((
            key,
            Span {
                start: v_start,
                end: v_end,
            },
        ));
        i = ws(b, v_end);
        match b.get(i) {
            Some(b',') => i = ws(b, i + 1),
            Some(b'}') => return Ok(out),
            _ => return Err(syntax(i, "expected , or } in an object")),
        }
    }
}

/// The element spans of the array at `arr`.
pub(crate) fn elements(b: &[u8], arr: Span) -> Result<Vec<Span>, String> {
    let mut out = Vec::new();
    let mut i = ws(b, arr.start + 1);
    if b.get(i) == Some(&b']') {
        return Ok(out);
    }
    loop {
        let start = i;
        let end = value_end(b, start)?;
        out.push(Span { start, end });
        i = ws(b, end);
        match b.get(i) {
            Some(b',') => i = ws(b, i + 1),
            Some(b']') => return Ok(out),
            _ => return Err(syntax(i, "expected , or ] in an array")),
        }
    }
}

/// A member's occurrences in an object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Member<T> {
    Present(T),
    Missing,
    Repeated,
    /// Present once with a value of another type.
    WrongType,
}

impl<T> Member<T> {
    pub fn ok(self) -> Option<T> {
        match self {
            Member::Present(v) => Some(v),
            _ => None,
        }
    }
    pub fn map<U>(self, f: impl FnOnce(T) -> Member<U>) -> Member<U> {
        match self {
            Member::Present(v) => f(v),
            Member::Missing => Member::Missing,
            Member::Repeated => Member::Repeated,
            Member::WrongType => Member::WrongType,
        }
    }
    /// How the member falls short, for prose: `missing`, `repeated` or `of another type`.
    pub fn defect(&self) -> Option<&'static str> {
        match self {
            Member::Present(_) => None,
            Member::Missing => Some("missing"),
            Member::Repeated => Some("repeated"),
            Member::WrongType => Some("of another type"),
        }
    }
}

/// The value of `key` when it appears exactly once, compared after escape decoding.
pub(crate) fn once(ms: &[(Option<String>, Span)], key: &str) -> Member<Span> {
    let mut found = None;
    for (k, v) in ms {
        if k.as_deref() == Some(key) {
            if found.is_some() {
                return Member::Repeated;
            }
            found = Some(*v);
        }
    }
    match found {
        Some(v) => Member::Present(v),
        None => Member::Missing,
    }
}

/// A string value as a Unicode string; `WrongType` for any other value,
/// including a string with a lone surrogate escape.
pub(crate) fn as_string(b: &[u8], m: Member<Span>) -> Member<String> {
    m.map(|s| match kind(b, s) {
        Kind::String => match decode_string(s.of(b)) {
            Some(v) => Member::Present(v),
            None => Member::WrongType,
        },
        _ => Member::WrongType,
    })
}

/// A non-negative integer written with digits only (no sign, fraction or
/// exponent) that fits in 64 bits.
pub(crate) fn integer(b: &[u8], s: Span) -> Option<u64> {
    let raw = s.of(b);
    if raw.is_empty() || !raw.iter().all(|c| c.is_ascii_digit()) {
        return None;
    }
    std::str::from_utf8(raw).ok()?.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A JSON escape (backslash, u, four hex digits) built at run time.
    fn u(hex: &str) -> String {
        format!("{}u{hex}", '\\')
    }

    #[test]
    fn validates_ordinary_json_texts() {
        for ok in [
            r#"{}"#,
            r#" [] "#,
            r#"{"a":[1,-2.5e+3,0.0,true,false,null,"x"],"a":{}}"#,
            "\"tab\\tnew\\nline\"",
            "0",
            "-0",
            "1E9",
            "\n{\"k\" : [ 1 , 2 ] }\r\n",
        ] {
            assert!(validate(ok.as_bytes()).is_ok(), "{ok}");
        }
    }

    #[test]
    fn refuses_what_is_not_one_json_text() {
        for (bad, why) in [
            ("", "missing"),
            ("{", "key"),
            ("{\"a\":1,}", "key"),
            ("[1,]", "unexpected"),
            ("[1 2]", "expected , or ]"),
            ("{\"a\" 1}", ":"),
            ("01", "bytes after"),
            ("1.", "malformed number"),
            ("-", "malformed number"),
            ("1e", "malformed number"),
            ("+1", "unexpected"),
            ("tru", "literal"),
            ("nul", "literal"),
            ("{} {}", "bytes after"),
            ("\"a\u{1}b\"", "control character"),
            ("\"\\x\"", "invalid escape"),
            ("\"\\u12\"", "\\u escape"),
            ("\"open", "unterminated"),
        ] {
            let e = validate(bad.as_bytes()).unwrap_err();
            assert!(e.contains(why), "{bad:?}: {e}");
        }
        assert!(
            validate(b"\xEF\xBB\xBF{}")
                .unwrap_err()
                .contains("byte-order")
        );
        assert!(validate(b"{\"a\":\"\xff\"}").unwrap_err().contains("UTF-8"));
    }

    #[test]
    fn deep_nesting_does_not_recurse() {
        let deep = format!("{}{}", "[".repeat(200_000), "]".repeat(200_000));
        assert_eq!(validate(deep.as_bytes()).unwrap().end, deep.len());
        let bad = format!("{}{}", "[".repeat(200_000), "]".repeat(199_999));
        assert!(validate(bad.as_bytes()).is_err());
    }

    #[test]
    fn decodes_strings_tolerantly() {
        let s = format!("\"a{}b{}{}{}\"", u("0041"), u("d83d"), u("de00"), u("0000"));
        assert_eq!(
            decode_string(s.as_bytes()).as_deref(),
            Some("aAb\u{1F600}\u{0}")
        );
        let lone = format!("\"x{}y\"", u("d800"));
        assert!(validate(lone.as_bytes()).is_ok());
        assert_eq!(decode_string(lone.as_bytes()), None);
        let lone_low = format!("\"{}\"", u("dc00"));
        assert_eq!(decode_string(lone_low.as_bytes()), None);
        let bad_pair = format!("\"{}{}\"", u("d800"), u("0041"));
        assert_eq!(decode_string(bad_pair.as_bytes()), None);
        assert_eq!(
            decode_string("\"é\\\"\\\\\\/\"".as_bytes()).as_deref(),
            Some("é\"\\/")
        );
    }

    #[test]
    fn members_keep_repeats_and_compare_decoded_keys() {
        let body = format!(r#"{{"a":1,"{}":[2],"b":"x","c":{{"d":null}}}}"#, u("0061"));
        let b = body.as_bytes();
        let top = validate(b).unwrap();
        let ms = members(b, top).unwrap();
        assert_eq!(ms.len(), 4);
        assert_eq!(once(&ms, "a"), Member::Repeated);
        assert_eq!(once(&ms, "z"), Member::Missing);
        let c = once(&ms, "c").ok().unwrap();
        assert_eq!(c.of(b), br#"{"d":null}"#);
        assert_eq!(as_string(b, once(&ms, "b")), Member::Present("x".into()));
        assert_eq!(as_string(b, once(&ms, "c")), Member::WrongType);
        let arr = validate(b" [ 1 , {\"k\":[]} , \"s\" ] ").unwrap();
        let els = elements(b" [ 1 , {\"k\":[]} , \"s\" ] ", arr).unwrap();
        assert_eq!(els.len(), 3);
        assert_eq!(els[1].of(b" [ 1 , {\"k\":[]} , \"s\" ] "), b"{\"k\":[]}");
    }

    #[test]
    fn integers_are_digits_only() {
        let b = br#"[12,0,-1,1.0,1e2,18446744073709551615,18446744073709551616]"#;
        let els = elements(b, validate(b).unwrap()).unwrap();
        let got: Vec<Option<u64>> = els.iter().map(|s| integer(b, *s)).collect();
        assert_eq!(
            got,
            [Some(12), Some(0), None, None, None, Some(u64::MAX), None]
        );
    }
}
