//! JSON-RPC envelopes for the two independent MCP servers (INTERFACE 5.11).
//! Interpret protocol fields without applying application limits to opaque metadata.
use crate::json::{
    J,
    tolerant::{self as scan, Kind, Member, Span},
};

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
pub fn initialize_result(name: &str) -> J {
    J::obj()
        .with("protocolVersion", PROTOCOL)
        .with("capabilities", J::obj().with("tools", J::obj()))
        .with(
            "serverInfo",
            J::obj().with("name", name).with("version", "1"),
        )
}
