//! Manager preparation over MCP stdio (INTERFACE 5.11).
//! The session keeps only the initialization handshake and the workspace the
//! launcher designated. Tools receive input values and that workspace, never
//! an audit, a credential or a provider capability; only `assemble` touches
//! the workspace.

mod assembly;
mod assessment;
mod tools;
mod workspace;

pub(crate) use workspace::Workspace;

use crate::json::J;
use crate::rpc::{self, Value};
use std::io::{self, BufRead, Write};

const LINE_LIMIT: usize = 4 * 1024 * 1024;

#[derive(Default, PartialEq)]
enum Stage {
    #[default]
    New,
    Initialized,
    Ready,
}

struct Session {
    stage: Stage,
    workspace: Option<Workspace>,
}

impl Session {
    fn receive(&mut self, bytes: &[u8]) -> Option<J> {
        let request = match Value::parse(bytes) {
            Ok(v) => v,
            Err(e) => return Some(rpc::error(b"null", -32700, &e)),
        };
        let id = match request.field("id") {
            Ok(id) if id.is_none_or(|v| v.id().is_ok()) => id,
            _ => {
                return Some(rpc::error(
                    b"null",
                    -32600,
                    "Expected a request with a string or integer ID.",
                ));
            }
        };
        let envelope = || -> Result<String, String> {
            if request.text("jsonrpc")? != "2.0"
                || request.field("result")?.is_some()
                || request.field("error")?.is_some()
            {
                return Err("Invalid request envelope.".into());
            }
            request.text("method")
        };
        let method = match envelope() {
            Ok(m) => m,
            Err(e) => {
                return Some(rpc::error(
                    id.map_or(b"null".as_slice(), Value::bytes),
                    -32600,
                    &e,
                ));
            }
        };
        let Some(id) = id else {
            if method == "notifications/initialized"
                && self.stage == Stage::Initialized
                && request
                    .field("params")
                    .is_ok_and(|p| p.is_none_or(|v| v.field("_meta").is_ok()))
            {
                self.stage = Stage::Ready;
            }
            return None;
        };
        let id = id.bytes();
        Some(match method.as_str() {
            "initialize" if self.stage != Stage::New => {
                rpc::error(id, -32600, "Already initialized.")
            }
            "tools/call" | "tools/list" if self.stage != Stage::Ready => rpc::error(
                id,
                -32600,
                "Initialize and send notifications/initialized first.",
            ),
            "initialize" | "ping" | "tools/call" | "tools/list" => {
                match self.dispatch(&method, request) {
                    Ok(data) => rpc::result(id, data),
                    Err(e) => rpc::error(id, -32602, &e),
                }
            }
            _ => rpc::error(id, -32601, "Method not found."),
        })
    }
    fn dispatch(&mut self, method: &str, request: Value) -> Result<J, String> {
        let params = request.field("params")?;
        if let Some(params) = params {
            params.field("_meta")?; // Parameters are an object. Metadata stays opaque.
        }
        match method {
            "ping" => Ok(J::obj()),
            "initialize" => {
                let p = params.ok_or("Missing initialization parameters.")?;
                p.text("protocolVersion")?;
                p.req("capabilities")?.field("tools")?;
                let client = p.req("clientInfo")?;
                client.text("name")?;
                client.text("version")?;
                self.stage = Stage::Initialized;
                Ok(rpc::initialize_result("stewart-manager"))
            }
            "tools/list" => {
                if let Some(p) = params
                    && p.field("cursor")?.is_some()
                {
                    return Err("The tool list has one page and takes no cursor.".into());
                }
                Ok(J::obj().with("tools", tools::list()))
            }
            "tools/call" => {
                let p = params.ok_or("Missing tool parameters.")?;
                let name = p.text("name")?;
                let args = p.field("arguments")?;
                let tool = tools::Tool::named(&name).ok_or("Unknown manager preparation tool.")?;
                Ok(tool.call(
                    args.map_or(b"{}".as_slice(), Value::bytes),
                    self.workspace.as_ref(),
                ))
            }
            _ => unreachable!(),
        }
    }
}

/// Consume a frame without ever retaining more than its limit. A discarded
/// frame gets one error, even when its delimiter arrives in a later buffer.
pub(crate) fn serve(
    mut input: impl BufRead,
    mut output: impl Write,
    workspace: Option<Workspace>,
) -> io::Result<()> {
    let mut session = Session {
        stage: Stage::default(),
        workspace,
    };
    let mut frame = Vec::new();
    let mut overlong = false;
    loop {
        let chunk = input.fill_buf()?;
        if chunk.is_empty() {
            return Ok(());
        }
        let newline = chunk.iter().position(|b| *b == b'\n');
        let end = newline.unwrap_or(chunk.len());
        if !overlong {
            overlong = end > LINE_LIMIT - frame.len();
            if !overlong {
                frame.extend_from_slice(&chunk[..end]);
            }
        }
        input.consume(end + usize::from(newline.is_some()));
        if newline.is_none() {
            continue;
        }
        let response = if overlong {
            Some(rpc::error(b"null", -32600, "Input line exceeds 4 MiB."))
        } else {
            session.receive(&frame)
        };
        if let Some(response) = response {
            output.write_all(&response.bytes())?;
            output.write_all(b"\n")?;
            output.flush()?;
        }
        frame.clear();
        overlong = false;
    }
}
