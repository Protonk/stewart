//! Only fields that affect execution are interpreted. Unknown JSON metadata
//! retains its raw representation, including signed and fractional numbers.
use crate::json::J;
use crate::provider::tolerant::{self as scan, Kind, Member, Span};
use std::collections::HashSet;

pub const FRAME_LIMIT: usize = 8 * 1024 * 1024;
pub const PROTOCOL: &str = "2025-11-25";
#[derive(Clone, Copy)]
pub struct Value<'a> {
    pub raw: &'a [u8],
    pub span: Span,
}
impl<'a> Value<'a> {
    pub fn parse(raw: &'a [u8]) -> Result<Self, String> {
        Ok(Self {
            raw,
            span: scan::validate(raw)?,
        })
    }
    pub fn bytes(self) -> &'a [u8] {
        self.span.of(self.raw)
    }
    pub fn field(self, key: &str) -> Result<Option<Self>, String> {
        if scan::kind(self.raw, self.span) != Kind::Object {
            return Err("expected object".into());
        }
        match scan::once(&scan::members(self.raw, self.span)?, key) {
            Member::Present(span) => Ok(Some(Self {
                raw: self.raw,
                span,
            })),
            Member::Missing => Ok(None),
            _ => Err(format!("repeated interpreted member {key}")),
        }
    }
    pub fn req(self, key: &str) -> Result<Self, String> {
        self.field(key)?.ok_or_else(|| format!("missing {key}"))
    }
    pub fn string(self) -> Result<String, String> {
        if scan::kind(self.raw, self.span) != Kind::String {
            return Err("expected string".into());
        }
        scan::decode_string(self.bytes())
            .filter(|s| !s.contains('\0'))
            .ok_or_else(|| "interpreted strings require Unicode without NUL".into())
    }
    pub fn text(self, key: &str) -> Result<String, String> {
        self.req(key)?.string()
    }
    pub fn number(self) -> Result<u64, String> {
        let s = std::str::from_utf8(self.bytes()).map_err(|e| e.to_string())?;
        let n = s
            .parse::<u64>()
            .map_err(|_| "expected unsigned integer".to_string())?;
        if n > crate::usage::FIGURE_MAX || n.to_string() != s {
            return Err("invalid reported count".into());
        }
        Ok(n)
    }
    pub fn array(self) -> Result<Vec<Self>, String> {
        if scan::kind(self.raw, self.span) != Kind::Array {
            return Err("expected array".into());
        }
        Ok(scan::elements(self.raw, self.span)?
            .into_iter()
            .map(|span| Self {
                raw: self.raw,
                span,
            })
            .collect())
    }
    pub fn null(self) -> bool {
        self.bytes() == b"null"
    }
    pub fn empty(self) -> Result<bool, String> {
        match scan::kind(self.raw, self.span) {
            Kind::Array => Ok(self.array()?.is_empty()),
            Kind::Object => Ok(scan::members(self.raw, self.span)?.is_empty()),
            Kind::Null => Ok(true),
            Kind::Bool => self.boolean().map(|b| !b),
            _ => Ok(false),
        }
    }
    pub fn boolean(self) -> Result<bool, String> {
        match self.bytes() {
            b"true" => Ok(true),
            b"false" => Ok(false),
            _ => Err("expected boolean".into()),
        }
    }
    pub fn id(self) -> Result<String, String> {
        if scan::kind(self.raw, self.span) == Kind::String {
            return Ok(format!("s:{}", self.string()?));
        }
        let raw = self.bytes();
        let digits = raw.strip_prefix(b"-").unwrap_or(raw);
        if digits.is_empty() || !digits.iter().all(u8::is_ascii_digit) {
            return Err("request ID must be a string or integer".into());
        }
        Ok(format!(
            "n:{}",
            if raw == b"-0" {
                "0"
            } else {
                std::str::from_utf8(raw).unwrap()
            }
        ))
    }
}
pub fn result(id: &[u8], value: J) -> J {
    J::obj()
        .with("jsonrpc", "2.0")
        .with("id", J::Raw(id.to_vec()))
        .with("result", value)
}
pub fn error(id: &[u8], code: i32, message: &str) -> J {
    J::obj()
        .with("jsonrpc", "2.0")
        .with("id", J::Raw(id.to_vec()))
        .with(
            "error",
            J::obj()
                .with("code", J::Raw(code.to_string().into_bytes()))
                .with("message", message),
        )
}
/// What the server presents at initialization. The launch surface pins it.
pub fn initialize_result() -> J {
    J::obj()
        .with("protocolVersion", PROTOCOL)
        .with("capabilities", J::obj().with("tools", J::obj()))
        .with(
            "serverInfo",
            J::obj().with("name", "stewart").with("version", "1"),
        )
}
pub enum Action {
    Silent,
    Reply(J),
    Cancel(String),
    Call {
        id: Vec<u8>,
        key: String,
        name: String,
        arguments: Vec<u8>,
    },
}
#[derive(Default)]
pub struct Mcp {
    initialized: bool,
    ready: bool,
    ids: HashSet<String>,
}
impl Mcp {
    pub fn receive(&mut self, raw: &[u8], tools: &[u8]) -> Action {
        let v = match Value::parse(raw) {
            Ok(v) => v,
            Err(e) => return Action::Reply(error(b"null", -32700, &e)),
        };
        let id = match v.field("id") {
            Ok(v) => v,
            Err(e) => return Action::Reply(error(b"null", -32600, &e)),
        };
        let response = (|| -> Result<Action, String> {
            if v.text("jsonrpc")? != "2.0"
                || v.field("result")?.is_some()
                || v.field("error")?.is_some()
            {
                return Err("invalid request envelope".into());
            }
            let method = v.text("method")?;
            if id.is_none() {
                return Ok(match method.as_str() {
                    "notifications/initialized" if self.initialized => {
                        self.ready = true;
                        Action::Silent
                    }
                    "notifications/cancelled" => {
                        Action::Cancel(v.req("params")?.req("requestId")?.id()?)
                    }
                    _ => Action::Silent,
                });
            }
            let id = id.unwrap();
            let key = id.id()?;
            if self.ids.len() >= 65536 {
                return Err("MCP request count exceeded".into());
            }
            if !self.ids.insert(key.clone()) {
                return Err("request ID already used in this placement".into());
            }
            let p = v.field("params")?;
            Ok(match method.as_str() {
                "ping" => Action::Reply(result(id.bytes(), J::obj())),
                "initialize" => {
                    if self.initialized {
                        return Err("repeated initialization".into());
                    }
                    let p = p.ok_or("missing initialization params")?;
                    p.text("protocolVersion")?;
                    p.req("capabilities")?.field("tools")?;
                    let info = p.req("clientInfo")?;
                    info.text("name")?;
                    info.text("version")?;
                    self.initialized = true;
                    Action::Reply(result(id.bytes(), initialize_result()))
                }
                "tools/list" | "tools/call" if !self.ready => {
                    return Err("initialize and notify initialized first".into());
                }
                "tools/list" => {
                    if p.map(|p| p.field("cursor"))
                        .transpose()?
                        .flatten()
                        .is_some()
                    {
                        return Err("fixed tool inventory has no cursor".into());
                    }
                    Action::Reply(result(
                        id.bytes(),
                        J::obj().with("tools", J::Raw(tools.to_vec())),
                    ))
                }
                "tools/call" => {
                    let p = p.ok_or("missing tool parameters")?;
                    let args = p.req("arguments")?;
                    // Core performs strict argument validation, after the exact
                    // tool request has been retained as call-N.json.
                    Action::Call {
                        id: id.bytes().to_vec(),
                        key,
                        name: p.text("name")?,
                        arguments: args.bytes().to_vec(),
                    }
                }
                _ => Action::Reply(error(id.bytes(), -32601, "method not found")),
            })
        })();
        match response {
            Ok(a) => a,
            Err(_)
                if id.is_none()
                    && v.text("jsonrpc").as_deref() == Ok("2.0")
                    && v.text("method").is_ok()
                    && matches!(v.field("result"), Ok(None))
                    && matches!(v.field("error"), Ok(None)) =>
            {
                Action::Silent
            }
            Err(e) => Action::Reply(error(
                id.filter(|v| v.id().is_ok())
                    .map_or(b"null".as_slice(), |v| v.bytes()),
                -32600,
                &e,
            )),
        }
    }
}

pub fn line(value: J) -> Vec<u8> {
    let mut b = value.bytes();
    b.push(b'\n');
    b
}
/// One supplied input message. The launch surface pins this shape.
pub fn user_message(text: &str) -> J {
    J::obj()
        .with("type", "user")
        .with("session_id", "")
        .with("parent_tool_use_id", J::Null)
        .with(
            "message",
            J::obj().with("role", "user").with("content", text),
        )
}
pub fn user(text: &str) -> Vec<u8> {
    line(user_message(text))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn metadata_is_tolerant_and_interpreted_duplicates_fail() {
        let v = Value::parse(br#"{"x":-1.5e4,"x":{},"model":"m"}"#).unwrap();
        assert_eq!(v.text("model").unwrap(), "m");
        assert!(v.field("x").is_err());
    }
    #[test]
    fn undetermined_request_ids_have_null_error_ids() {
        for (raw, code) in [
            ("{", "-32700"),
            (
                r#"{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}"#,
                "-32600",
            ),
            (r#"{"jsonrpc":"2.0","id":{},"method":"ping"}"#, "-32600"),
            (r#"{"jsonrpc":"1.0","method":"ping"}"#, "-32600"),
            ("[]", "-32600"),
        ] {
            let Action::Reply(reply) = Mcp::default().receive(raw.as_bytes(), b"[]") else {
                panic!("invalid request received no error: {raw}");
            };
            let bytes = reply.bytes();
            let value = Value::parse(&bytes).unwrap();
            assert_eq!(value.req("id").unwrap().bytes(), b"null");
            assert_eq!(
                value.req("error").unwrap().req("code").unwrap().bytes(),
                code.as_bytes()
            );
        }
    }

    #[test]
    fn notification_never_becomes_a_call() {
        let mut m = Mcp::default();
        assert!(matches!(m.receive(br#"{"jsonrpc":"2.0","method":"tools/call","params":{"name":"submit","arguments":{}}}"#, b"[]"), Action::Silent));
        assert!(matches!(m.receive(br#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"submit","arguments":{}}}"#, b"[]"), Action::Reply(_)));
    }
}
