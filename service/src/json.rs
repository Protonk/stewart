//! Strict control JSON (INTERFACE 1.2) and the deterministic compact writer.
//!
//! The decoder is used for every JSON value Stewart interprets as control data:
//! archive records read back and auditor tool inputs. It keeps the raw byte
//! span of every value so that digests can be taken over the exact stored
//! bytes, never over a re-serialization.
//!
//! Rules: UTF-8 only, no byte-order mark, one top-level value followed only by
//! JSON whitespace; a key repeated at any depth is refused after escape
//! decoding; lone surrogate escapes and NUL are refused in every string;
//! numbers must be non-negative integers without sign, leading zero, fraction
//! or exponent that fit in 64 bits (each field then applies its own bound);
//! nesting depth is at most 16. A refusal names the JSON pointer of the defect
//! and the rule that was broken.
//!
//! The writer produces compact JSON with keys in the order given. Strings
//! escape `"` and `\`, and exactly U+0000–U+001F (`\b \f \n \r \t` for those
//! five, `\u00xx` in lowercase hex for the rest); every other character,
//! including U+007F and non-ASCII, is written as raw UTF-8. This is the
//! escaping that QUESTION-FORMS pins for the structured answer.

use std::fmt;

/// Maximum nesting depth of arrays and objects.
pub const MAX_DEPTH: usize = 16;

/// A decoded value with the byte span `[start, end)` it occupied in the input.
#[derive(Debug, Clone, PartialEq)]
pub struct Json {
    pub start: usize,
    pub end: usize,
    pub v: V,
}

#[derive(Debug, Clone, PartialEq)]
pub enum V {
    Null,
    Bool(bool),
    Int(u64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

/// A refused input: where (`pointer`, `offset`), which rule, and details.
#[derive(Debug, Clone, PartialEq)]
pub struct JsonError {
    pub pointer: String,
    pub rule: &'static str,
    pub detail: String,
    pub offset: usize,
}

impl fmt::Display for JsonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let at = if self.pointer.is_empty() {
            "the top level"
        } else {
            &self.pointer
        };
        write!(
            f,
            "{} at {} (byte {}): {}",
            self.rule, at, self.offset, self.detail
        )
    }
}

/// Escape one RFC 6901 reference token.
pub fn pointer_token(s: &str) -> String {
    s.replace('~', "~0").replace('/', "~1")
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
    path: Vec<String>,
}

pub fn parse(bytes: &[u8]) -> Result<Json, JsonError> {
    if let Err(e) = std::str::from_utf8(bytes) {
        return Err(JsonError {
            pointer: String::new(),
            rule: "encoding",
            detail: "the input is not valid UTF-8".into(),
            offset: e.valid_up_to(),
        });
    }
    if bytes.starts_with(b"\xEF\xBB\xBF") {
        return Err(JsonError {
            pointer: String::new(),
            rule: "bom",
            detail: "a byte-order mark is not allowed".into(),
            offset: 0,
        });
    }
    let mut p = Parser {
        b: bytes,
        i: 0,
        path: Vec::new(),
    };
    p.ws();
    let v = p.value(1)?;
    p.ws();
    if p.i != p.b.len() {
        return Err(p.err("trailing", "only whitespace may follow the top-level value"));
    }
    Ok(v)
}

impl<'a> Parser<'a> {
    fn pointer(&self) -> String {
        let mut s = String::new();
        for t in &self.path {
            s.push('/');
            s.push_str(&pointer_token(t));
        }
        s
    }
    fn err(&self, rule: &'static str, detail: &str) -> JsonError {
        JsonError {
            pointer: self.pointer(),
            rule,
            detail: detail.into(),
            offset: self.i,
        }
    }
    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }
    fn lit(&mut self, word: &[u8], v: V) -> Result<Json, JsonError> {
        let start = self.i;
        if self.b[self.i..].starts_with(word) {
            self.i += word.len();
            // A literal must not run into further identifier characters (`truex`).
            if let Some(c) = self.peek() {
                if c.is_ascii_alphanumeric() {
                    return Err(self.err("syntax", "unexpected characters after a literal"));
                }
            }
            Ok(Json {
                start,
                end: self.i,
                v,
            })
        } else {
            Err(self.err("syntax", "expected a JSON value"))
        }
    }
    fn value(&mut self, depth: usize) -> Result<Json, JsonError> {
        match self.peek() {
            None => Err(self.err("syntax", "unexpected end of input")),
            Some(b'{') => self.object(depth),
            Some(b'[') => self.array(depth),
            Some(b'"') => {
                let start = self.i;
                let s = self.string()?;
                Ok(Json {
                    start,
                    end: self.i,
                    v: V::Str(s),
                })
            }
            Some(b't') => self.lit(b"true", V::Bool(true)),
            Some(b'f') => self.lit(b"false", V::Bool(false)),
            Some(b'n') => self.lit(b"null", V::Null),
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(_) => Err(self.err("syntax", "expected a JSON value")),
        }
    }
    fn number(&mut self) -> Result<Json, JsonError> {
        let start = self.i;
        let mut j = self.i;
        let negative = self.b[j] == b'-';
        if negative {
            j += 1;
        }
        let digits_start = j;
        while j < self.b.len() && self.b[j].is_ascii_digit() {
            j += 1;
        }
        let digits = &self.b[digits_start..j];
        let mut fraction = false;
        if j < self.b.len() && matches!(self.b[j], b'.' | b'e' | b'E') {
            fraction = true;
            j += 1;
            while j < self.b.len()
                && (self.b[j].is_ascii_digit()
                    || matches!(self.b[j], b'.' | b'e' | b'E' | b'+' | b'-'))
            {
                j += 1;
            }
        }
        if digits.is_empty() {
            return Err(self.err("syntax", "a number needs digits"));
        }
        if negative {
            return Err(self.err("integer_sign", "integers are written without a sign"));
        }
        if fraction {
            return Err(self.err(
                "not_integer",
                "only integers are accepted; no fraction or exponent",
            ));
        }
        if digits.len() > 1 && digits[0] == b'0' {
            return Err(self.err("leading_zero", "integers are written without leading zeros"));
        }
        let mut n: u64 = 0;
        for &d in digits {
            n = match n
                .checked_mul(10)
                .and_then(|x| x.checked_add((d - b'0') as u64))
            {
                Some(x) => x,
                None => {
                    return Err(
                        self.err("integer_range", "the integer exceeds 18446744073709551615")
                    );
                }
            };
        }
        self.i = j;
        Ok(Json {
            start,
            end: j,
            v: V::Int(n),
        })
    }
    fn hex4(&mut self) -> Result<u32, JsonError> {
        if self.i + 4 > self.b.len() {
            return Err(self.err("syntax", "incomplete \\u escape"));
        }
        let mut v = 0u32;
        for k in 0..4 {
            let c = self.b[self.i + k];
            let d = match c {
                b'0'..=b'9' => c - b'0',
                b'a'..=b'f' => c - b'a' + 10,
                b'A'..=b'F' => c - b'A' + 10,
                _ => return Err(self.err("syntax", "invalid \\u escape")),
            };
            v = v * 16 + d as u32;
        }
        self.i += 4;
        Ok(v)
    }
    fn string(&mut self) -> Result<String, JsonError> {
        // Caller guarantees the opening quote.
        self.i += 1;
        let mut out = String::new();
        loop {
            let Some(c) = self.peek() else {
                return Err(self.err("syntax", "unterminated string"));
            };
            match c {
                b'"' => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    let esc_at = self.i;
                    self.i += 1;
                    let Some(e) = self.peek() else {
                        return Err(self.err("syntax", "unterminated escape"));
                    };
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let hi = self.hex4()?;
                            let cp = if (0xD800..0xDC00).contains(&hi) {
                                // A high surrogate must be followed by an escaped low surrogate.
                                if self.b[self.i..].starts_with(b"\\u") {
                                    self.i += 2;
                                    let lo = self.hex4()?;
                                    if !(0xDC00..0xE000).contains(&lo) {
                                        self.i = esc_at;
                                        return Err(self.err("lone_surrogate", "a high surrogate escape is not followed by a low surrogate"));
                                    }
                                    0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                                } else {
                                    self.i = esc_at;
                                    return Err(self.err("lone_surrogate", "a high surrogate escape is not followed by a low surrogate"));
                                }
                            } else if (0xDC00..0xE000).contains(&hi) {
                                self.i = esc_at;
                                return Err(self.err(
                                    "lone_surrogate",
                                    "a low surrogate escape appears without a high surrogate",
                                ));
                            } else {
                                hi
                            };
                            if cp == 0 {
                                self.i = esc_at;
                                return Err(self.err(
                                    "nul",
                                    "NUL (\\u0000) is not allowed in control strings",
                                ));
                            }
                            match char::from_u32(cp) {
                                Some(ch) => out.push(ch),
                                None => return Err(self.err("syntax", "invalid escape")),
                            }
                        }
                        _ => {
                            self.i = esc_at;
                            return Err(self.err("syntax", "invalid escape"));
                        }
                    }
                }
                0x00 => return Err(self.err("nul", "NUL is not allowed in control strings")),
                c if c < 0x20 => {
                    return Err(self.err("syntax", "control characters must be escaped in strings"));
                }
                _ => {
                    // Copy one UTF-8 character; the input was validated as UTF-8.
                    let len = utf8_len(c);
                    let s = std::str::from_utf8(&self.b[self.i..self.i + len])
                        .expect("validated UTF-8");
                    out.push_str(s);
                    self.i += len;
                }
            }
        }
    }
    fn array(&mut self, depth: usize) -> Result<Json, JsonError> {
        if depth > MAX_DEPTH {
            return Err(self.err("depth", "nesting is deeper than 16"));
        }
        let start = self.i;
        self.i += 1;
        let mut items = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(Json {
                start,
                end: self.i,
                v: V::Arr(items),
            });
        }
        loop {
            self.path.push(items.len().to_string());
            self.ws();
            let v = self.value(depth + 1)?;
            self.path.pop();
            items.push(v);
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(Json {
                        start,
                        end: self.i,
                        v: V::Arr(items),
                    });
                }
                _ => return Err(self.err("syntax", "expected , or ] in an array")),
            }
        }
    }
    fn object(&mut self, depth: usize) -> Result<Json, JsonError> {
        if depth > MAX_DEPTH {
            return Err(self.err("depth", "nesting is deeper than 16"));
        }
        let start = self.i;
        self.i += 1;
        let mut members: Vec<(String, Json)> = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Json {
                start,
                end: self.i,
                v: V::Obj(members),
            });
        }
        loop {
            self.ws();
            if self.peek() != Some(b'"') {
                return Err(self.err("syntax", "expected a string key"));
            }
            let key_at = self.i;
            let key = self.string()?;
            if members.iter().any(|(k, _)| *k == key) {
                self.path.push(key.clone());
                let mut e = self.err("duplicate_key", "this key appears more than once in its object (compared after escape decoding)");
                e.offset = key_at;
                return Err(e);
            }
            self.ws();
            if self.peek() != Some(b':') {
                return Err(self.err("syntax", "expected : after a key"));
            }
            self.i += 1;
            self.ws();
            self.path.push(key.clone());
            let v = self.value(depth + 1)?;
            self.path.pop();
            members.push((key, v));
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Json {
                        start,
                        end: self.i,
                        v: V::Obj(members),
                    });
                }
                _ => return Err(self.err("syntax", "expected , or } in an object")),
            }
        }
    }
}

fn utf8_len(first: u8) -> usize {
    match first {
        0x00..=0x7F => 1,
        0xC0..=0xDF => 2,
        0xE0..=0xEF => 3,
        _ => 4,
    }
}

// ---------------------------------------------------------------------------
// Schema helpers: typed access that refuses unknown keys and wrong types.

/// A view of a decoded object at a JSON pointer.
pub struct Obj<'a> {
    pub members: &'a [(String, Json)],
    pub pointer: String,
    pub at: usize,
}

fn type_name(v: &V) -> &'static str {
    match v {
        V::Null => "null",
        V::Bool(_) => "boolean",
        V::Int(_) => "integer",
        V::Str(_) => "string",
        V::Arr(_) => "array",
        V::Obj(_) => "object",
    }
}

fn type_err(ptr: &str, at: usize, want: &str, got: &V) -> JsonError {
    JsonError {
        pointer: ptr.into(),
        rule: "type",
        detail: format!("expected {want}, found {}", type_name(got)),
        offset: at,
    }
}

impl Json {
    pub fn obj(&self, pointer: &str) -> Result<Obj<'_>, JsonError> {
        match &self.v {
            V::Obj(m) => Ok(Obj {
                members: m,
                pointer: pointer.into(),
                at: self.start,
            }),
            other => Err(type_err(pointer, self.start, "object", other)),
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        if let V::Str(s) = &self.v {
            Some(s)
        } else {
            None
        }
    }
    pub fn as_u64(&self) -> Option<u64> {
        if let V::Int(n) = &self.v {
            Some(*n)
        } else {
            None
        }
    }
    pub fn as_arr(&self) -> Option<&[Json]> {
        if let V::Arr(a) = &self.v {
            Some(a)
        } else {
            None
        }
    }
    pub fn is_null(&self) -> bool {
        matches!(self.v, V::Null)
    }
    /// Convert to an output value (for embedding decoded data in replies).
    pub fn to_j(&self) -> J {
        match &self.v {
            V::Null => J::Null,
            V::Bool(b) => J::Bool(*b),
            V::Int(n) => J::Int(*n),
            V::Str(s) => J::Str(s.clone()),
            V::Arr(a) => J::Arr(a.iter().map(|x| x.to_j()).collect()),
            V::Obj(m) => J::Obj(m.iter().map(|(k, v)| (k.clone(), v.to_j())).collect()),
        }
    }
}

impl<'a> Obj<'a> {
    fn child_ptr(&self, k: &str) -> String {
        format!("{}/{}", self.pointer, pointer_token(k))
    }
    /// Refuse any key outside `allowed`, naming the expected keys.
    pub fn only(&self, allowed: &[&str]) -> Result<(), JsonError> {
        for (k, v) in self.members {
            if !allowed.contains(&k.as_str()) {
                return Err(JsonError {
                    pointer: self.child_ptr(k),
                    rule: "unknown_key",
                    detail: format!("unknown key; expected keys: {}", allowed.join(", ")),
                    offset: v.start,
                });
            }
        }
        Ok(())
    }
    pub fn get(&self, k: &str) -> Option<&'a Json> {
        self.members
            .iter()
            .find(|(key, _)| key == k)
            .map(|(_, v)| v)
    }
    pub fn req(&self, k: &str) -> Result<&'a Json, JsonError> {
        self.get(k).ok_or_else(|| JsonError {
            pointer: self.child_ptr(k),
            rule: "missing_key",
            detail: "a required key is missing".into(),
            offset: self.at,
        })
    }
    pub fn str(&self, k: &str) -> Result<&'a str, JsonError> {
        let v = self.req(k)?;
        v.as_str()
            .ok_or_else(|| type_err(&self.child_ptr(k), v.start, "string", &v.v))
    }
    /// A string, or `null`; the key itself must be present.
    pub fn str_or_null(&self, k: &str) -> Result<Option<&'a str>, JsonError> {
        let v = self.req(k)?;
        match &v.v {
            V::Null => Ok(None),
            V::Str(s) => Ok(Some(s)),
            other => Err(type_err(
                &self.child_ptr(k),
                v.start,
                "string or null",
                other,
            )),
        }
    }
    pub fn opt_str(&self, k: &str) -> Result<Option<&'a str>, JsonError> {
        match self.get(k) {
            None => Ok(None),
            Some(v) => v
                .as_str()
                .map(Some)
                .ok_or_else(|| type_err(&self.child_ptr(k), v.start, "string", &v.v)),
        }
    }
    pub fn u64(&self, k: &str, max: u64) -> Result<u64, JsonError> {
        let v = self.req(k)?;
        let n = v
            .as_u64()
            .ok_or_else(|| type_err(&self.child_ptr(k), v.start, "integer", &v.v))?;
        if n > max {
            return Err(JsonError {
                pointer: self.child_ptr(k),
                rule: "integer_range",
                detail: format!("the integer exceeds this field's bound {max}"),
                offset: v.start,
            });
        }
        Ok(n)
    }
    pub fn bool(&self, k: &str) -> Result<bool, JsonError> {
        let v = self.req(k)?;
        match v.v {
            V::Bool(b) => Ok(b),
            ref other => Err(type_err(&self.child_ptr(k), v.start, "boolean", other)),
        }
    }
    pub fn obj(&self, k: &str) -> Result<Obj<'a>, JsonError> {
        let v = self.req(k)?;
        v.obj(&self.child_ptr(k))
    }
    pub fn obj_or_null(&self, k: &str) -> Result<Option<Obj<'a>>, JsonError> {
        let v = self.req(k)?;
        if v.is_null() {
            Ok(None)
        } else {
            v.obj(&self.child_ptr(k)).map(Some)
        }
    }
    pub fn arr(&self, k: &str) -> Result<&'a [Json], JsonError> {
        let v = self.req(k)?;
        v.as_arr()
            .ok_or_else(|| type_err(&self.child_ptr(k), v.start, "array", &v.v))
    }
    /// An array of strings.
    pub fn strs(&self, k: &str) -> Result<Vec<&'a str>, JsonError> {
        let arr = self.arr(k)?;
        let mut out = Vec::with_capacity(arr.len());
        for (i, v) in arr.iter().enumerate() {
            match v.as_str() {
                Some(s) => out.push(s),
                None => {
                    return Err(type_err(
                        &format!("{}/{i}", self.child_ptr(k)),
                        v.start,
                        "string",
                        &v.v,
                    ));
                }
            }
        }
        Ok(out)
    }
    /// Pointer of a child, for building nested errors.
    pub fn ptr(&self, k: &str) -> String {
        self.child_ptr(k)
    }
    /// Require exactly these keys: an unknown key is refused (naming the
    /// expected keys) and every listed key must be present, including those
    /// whose value may be `null`. Order is not checked here; writers emit the
    /// listed order.
    pub fn exactly(&self, keys: &[&str]) -> Result<(), JsonError> {
        self.only(keys)?;
        for k in keys {
            self.req(k)?;
        }
        Ok(())
    }
    /// An integer or `null`; the key itself must be present.
    pub fn u64_or_null(&self, k: &str, max: u64) -> Result<Option<u64>, JsonError> {
        if self.req(k)?.is_null() {
            Ok(None)
        } else {
            self.u64(k, max).map(Some)
        }
    }
    /// An array or `null`; the key itself must be present.
    pub fn arr_or_null(&self, k: &str) -> Result<Option<&'a [Json]>, JsonError> {
        if self.req(k)?.is_null() {
            Ok(None)
        } else {
            self.arr(k).map(Some)
        }
    }
    /// A string from a closed set of values.
    pub fn one_of(&self, k: &str, values: &[&str]) -> Result<&'a str, JsonError> {
        let s = self.str(k)?;
        if values.contains(&s) {
            Ok(s)
        } else {
            Err(value_err(
                &self.child_ptr(k),
                self.req(k)?.start,
                format!("{s:?} is not one of: {}", values.join(", ")),
            ))
        }
    }
    /// A lowercase hexadecimal SHA-256 digest.
    pub fn sha256(&self, k: &str) -> Result<&'a str, JsonError> {
        let s = self.str(k)?;
        if crate::util::is_hex64(s) {
            Ok(s)
        } else {
            Err(value_err(
                &self.child_ptr(k),
                self.req(k)?.start,
                "expected a lowercase hexadecimal SHA-256 digest",
            ))
        }
    }
    /// A digest or `null`.
    pub fn sha256_or_null(&self, k: &str) -> Result<Option<&'a str>, JsonError> {
        if self.req(k)?.is_null() {
            Ok(None)
        } else {
            self.sha256(k).map(Some)
        }
    }
    /// A rule about a member's value that its type does not express.
    pub fn invalid(&self, k: &str, detail: impl Into<String>) -> JsonError {
        let at = self.get(k).map(|v| v.start).unwrap_or(self.at);
        value_err(&self.child_ptr(k), at, detail)
    }
}

/// Build a schema error at a pointer (used by record decoders for value rules).
pub fn value_err(pointer: &str, at: usize, detail: impl Into<String>) -> JsonError {
    JsonError {
        pointer: pointer.into(),
        rule: "value",
        detail: detail.into(),
        offset: at,
    }
}

// ---------------------------------------------------------------------------
// Output.

/// An output value. Objects keep their keys in insertion order. `Raw` splices
/// bytes that are already compact JSON (pinned arrangement members).
#[derive(Debug, Clone, PartialEq)]
pub enum J {
    Null,
    Bool(bool),
    Int(u64),
    Str(String),
    Raw(Vec<u8>),
    Arr(Vec<J>),
    Obj(Vec<(String, J)>),
}

impl J {
    pub fn obj() -> J {
        J::Obj(Vec::new())
    }
    /// Append a member (builder style).
    pub fn with(mut self, k: &str, v: impl Into<J>) -> J {
        if let J::Obj(m) = &mut self {
            m.push((k.to_string(), v.into()));
        }
        self
    }
    pub fn push(&mut self, k: &str, v: impl Into<J>) {
        if let J::Obj(m) = self {
            m.push((k.to_string(), v.into()));
        }
    }
    pub fn get(&self, k: &str) -> Option<&J> {
        if let J::Obj(m) = self {
            m.iter().find(|(key, _)| key == k).map(|(_, v)| v)
        } else {
            None
        }
    }
    pub fn is_empty_obj(&self) -> bool {
        matches!(self, J::Obj(m) if m.is_empty())
    }
    pub fn write(&self, out: &mut Vec<u8>) {
        match self {
            J::Null => out.extend_from_slice(b"null"),
            J::Bool(true) => out.extend_from_slice(b"true"),
            J::Bool(false) => out.extend_from_slice(b"false"),
            J::Int(n) => out.extend_from_slice(n.to_string().as_bytes()),
            J::Str(s) => escape_into(s, out),
            J::Raw(r) => out.extend_from_slice(r),
            J::Arr(a) => {
                out.push(b'[');
                for (i, v) in a.iter().enumerate() {
                    if i > 0 {
                        out.push(b',');
                    }
                    v.write(out);
                }
                out.push(b']');
            }
            J::Obj(m) => {
                out.push(b'{');
                for (i, (k, v)) in m.iter().enumerate() {
                    if i > 0 {
                        out.push(b',');
                    }
                    escape_into(k, out);
                    out.push(b':');
                    v.write(out);
                }
                out.push(b'}');
            }
        }
    }
    pub fn bytes(&self) -> Vec<u8> {
        let mut out = Vec::new();
        self.write(&mut out);
        out
    }
    pub fn string(&self) -> String {
        String::from_utf8(self.bytes()).expect("the writer emits UTF-8")
    }
}

/// Write `s` as a JSON string with the pinned escaping rules.
pub fn escape_into(s: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for ch in s.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{8}' => out.extend_from_slice(b"\\b"),
            '\u{c}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => {
                out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes())
            }
            c => {
                let mut buf = [0u8; 4];
                out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
            }
        }
    }
    out.push(b'"');
}

pub fn quote(s: &str) -> String {
    let mut v = Vec::new();
    escape_into(s, &mut v);
    String::from_utf8(v).expect("UTF-8")
}

impl From<&str> for J {
    fn from(s: &str) -> J {
        J::Str(s.to_string())
    }
}
impl From<String> for J {
    fn from(s: String) -> J {
        J::Str(s)
    }
}
impl From<&String> for J {
    fn from(s: &String) -> J {
        J::Str(s.clone())
    }
}
impl From<u64> for J {
    fn from(n: u64) -> J {
        J::Int(n)
    }
}
impl From<usize> for J {
    fn from(n: usize) -> J {
        J::Int(n as u64)
    }
}
impl From<u32> for J {
    fn from(n: u32) -> J {
        J::Int(n as u64)
    }
}
impl From<bool> for J {
    fn from(b: bool) -> J {
        J::Bool(b)
    }
}
impl From<Vec<J>> for J {
    fn from(v: Vec<J>) -> J {
        J::Arr(v)
    }
}
impl<T: Into<J>> From<Option<T>> for J {
    fn from(v: Option<T>) -> J {
        match v {
            Some(x) => x.into(),
            None => J::Null,
        }
    }
}

/// An array of strings.
pub fn strs<S: AsRef<str>>(items: &[S]) -> J {
    J::Arr(
        items
            .iter()
            .map(|s| J::Str(s.as_ref().to_string()))
            .collect(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rule(input: &str) -> &'static str {
        parse(input.as_bytes()).unwrap_err().rule
    }

    /// A JSON escape (backslash, u, four hex digits) built at run time.
    fn u(hex: &str) -> String {
        format!("{}u{hex}", '\\')
    }

    #[test]
    fn accepts_ordinary_values_with_spans() {
        let input = format!(
            r#" {{"a": [1, true, null, "x{}"], "b": {{"c": 0}}}} "#,
            u("00e9")
        );
        let v = parse(input.as_bytes()).unwrap();
        let o = v.obj("").unwrap();
        let a = o.arr("a").unwrap();
        assert_eq!(a[0].v, V::Int(1));
        assert_eq!(a[3].as_str(), Some("x\u{e9}"));
        let raw = input.as_bytes();
        let b = o.req("b").unwrap();
        assert_eq!(&raw[b.start..b.end], br#"{"c": 0}"#);
    }

    #[test]
    fn refuses_duplicates_at_any_depth_after_escape_decoding() {
        let e = parse(format!(r#"{{"a":1,"{}":2}}"#, u("0061")).as_bytes()).unwrap_err();
        assert_eq!(e.rule, "duplicate_key");
        assert_eq!(e.pointer, "/a");
        let e = parse(br#"{"x":[{"k":1,"k":2}]}"#).unwrap_err();
        assert_eq!(e.rule, "duplicate_key");
        assert_eq!(e.pointer, "/x/0/k");
        // Same key in different objects is fine.
        assert!(parse(br#"{"a":{"a":1},"b":{"a":2}}"#).is_ok());
    }

    #[test]
    fn refuses_bad_strings() {
        assert_eq!(rule(r#"["\ud800"]"#), "lone_surrogate");
        assert_eq!(rule(r#"["\udc00"]"#), "lone_surrogate");
        assert_eq!(
            rule(&format!(r#"["{}{}"]"#, u("d800"), u("0041"))),
            "lone_surrogate"
        );
        let pair = format!(r#"["{}{}"]"#, u("d83d"), u("de00"));
        assert_eq!(
            parse(pair.as_bytes()).unwrap().v,
            V::Arr(vec![Json {
                start: 1,
                end: 15,
                v: V::Str("\u{1F600}".into())
            }])
        );
        assert_eq!(rule(r#"{"a":"\u0000"}"#), "nul");
        assert_eq!(rule("[\"a\u{0}\"]"), "nul");
        assert_eq!(rule("[\"a\nb\"]"), "syntax");
        assert_eq!(rule(r#"["\x"]"#), "syntax");
    }

    #[test]
    fn refuses_non_integers_and_signs() {
        assert_eq!(rule("[1.0]"), "not_integer");
        assert_eq!(rule("[1e3]"), "not_integer");
        assert_eq!(rule("[-1]"), "integer_sign");
        assert_eq!(rule("[-0]"), "integer_sign");
        assert_eq!(rule("[01]"), "leading_zero");
        assert_eq!(rule("[18446744073709551616]"), "integer_range");
        assert_eq!(parse(b"18446744073709551615").unwrap().v, V::Int(u64::MAX));
        assert_eq!(parse(b"0").unwrap().v, V::Int(0));
    }

    #[test]
    fn booleans_are_literals_only() {
        let v = parse(br#"{"b":"true"}"#).unwrap();
        let e = v.obj("").unwrap().bool("b").unwrap_err();
        assert_eq!(e.rule, "type");
        assert_eq!(e.pointer, "/b");
        assert_eq!(rule("[True]"), "syntax");
        assert_eq!(rule("[truex]"), "syntax");
    }

    #[test]
    fn framing_rules() {
        assert_eq!(rule("\u{feff}{}"), "bom");
        assert_eq!(rule("{} {}"), "trailing");
        assert_eq!(rule("{} x"), "trailing");
        assert_eq!(rule(""), "syntax");
        assert_eq!(parse(b"\xff").unwrap_err().rule, "encoding");
        assert!(parse(b" {} \n").is_ok());
    }

    #[test]
    fn depth_is_bounded_at_sixteen() {
        let ok = format!("{}{}", "[".repeat(16), "]".repeat(16));
        assert!(parse(ok.as_bytes()).is_ok());
        let deep = format!("{}{}", "[".repeat(17), "]".repeat(17));
        assert_eq!(parse(deep.as_bytes()).unwrap_err().rule, "depth");
        let mixed = format!("{}{}", r#"{"a":"#.repeat(17), "}".repeat(17));
        assert_eq!(
            parse(format!("{}1{}", &mixed[..mixed.len() - 17], "}".repeat(17)).as_bytes())
                .unwrap_err()
                .rule,
            "depth"
        );
    }

    #[test]
    fn unknown_keys_are_named_with_expected_keys() {
        let v = parse(br#"{"a":1,"b~/":2}"#).unwrap();
        let e = v.obj("").unwrap().only(&["a"]).unwrap_err();
        assert_eq!(e.rule, "unknown_key");
        assert_eq!(e.pointer, "/b~0~1");
        assert!(e.detail.contains("expected keys: a"));
        let e = v.obj("").unwrap().req("z").unwrap_err();
        assert_eq!(e.rule, "missing_key");
    }

    #[test]
    fn writer_escapes_exactly_the_pinned_set() {
        let s = "q\"\\\u{8}\u{c}\n\r\t\u{1}\u{1f}\u{7f}é/";
        assert_eq!(
            quote(s),
            "\"q\\\"\\\\\\b\\f\\n\\r\\t\\u0001\\u001f\u{7f}é/\""
        );
        let j = J::obj()
            .with("b", 1u64)
            .with("a", J::Arr(vec![J::Null, true.into(), "x".into()]))
            .with("r", J::Raw(b"{\"k\":2}".to_vec()));
        assert_eq!(j.string(), r#"{"b":1,"a":[null,true,"x"],"r":{"k":2}}"#);
        // Round trip through the strict decoder.
        let back = parse(&J::Str(s.into()).bytes()).unwrap();
        assert_eq!(back.as_str(), Some(s));
    }
}
