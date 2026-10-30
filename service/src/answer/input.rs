//! Tool inputs, decoded strictly (INTERFACE 1.2, 7.1): at most 4 MiB, one
//! JSON object, unknown keys refused with the expected keys, every value of
//! its type. A refusal names the JSON pointer of the defect and the rule, and
//! says that the raw input was captured before decoding.

use super::common::refused;
use crate::archive::Fail;
use crate::json::{self, J, Json, JsonError, Obj};

const CAPTURED: &str = "The raw input was captured before decoding.";

/// `input_invalid` for a decoding or schema defect.
pub fn invalid(e: &JsonError, expected: Option<&[&str]>) -> Fail {
    let at = if e.pointer.is_empty() {
        "the input".to_string()
    } else {
        format!("the input at {}", e.pointer)
    };
    let mut data = J::obj()
        .with("pointer", e.pointer.as_str())
        .with("rule", e.rule)
        .with("detail", e.detail.as_str());
    if let Some(keys) = expected {
        data.push("expected", json::strs(keys));
    }
    refused(
        "input_invalid",
        format!("{at} breaks the rule {}: {}. {CAPTURED}", e.rule, e.detail),
    )
    .data(data)
}

/// A rule about a value that its type does not express.
pub fn invalid_value(pointer: &str, detail: impl Into<String>) -> Fail {
    invalid(&json::value_err(pointer, 0, detail), None)
}

/// Decode the raw `input` bytes: bounded, strict, an object.
pub fn decode(raw: Option<&[u8]>) -> Result<Json, Fail> {
    let Some(raw) = raw else {
        return Err(refused(
            "input_invalid",
            format!("The tool_use block has no single input value. {CAPTURED}"),
        )
        .data(
            J::obj()
                .with("pointer", "")
                .with("rule", "missing_input")
                .with("detail", "input is missing or repeated"),
        ));
    };
    let limit = crate::forms::TOOL_INPUT_BYTES;
    if raw.len() as u64 > limit {
        return Err(refused(
            "input_too_large",
            format!(
                "The input is {} bytes; one call carries at most {limit} bytes. {CAPTURED}",
                raw.len()
            ),
        )
        .data(J::obj().with("size", raw.len()).with("limit", limit)));
    }
    let v = json::parse(raw).map_err(|e| invalid(&e, None))?;
    v.obj("").map_err(|e| invalid(&e, None))?;
    Ok(v)
}

/// The input object, with only `allowed` keys and every `required` one.
pub fn object<'a>(v: &'a Json, allowed: &[&str], required: &[&str]) -> Result<Obj<'a>, Fail> {
    let o = v.obj("").map_err(|e| invalid(&e, None))?;
    keys(&o, allowed, required)?;
    Ok(o)
}

/// Check an object's keys: unknown ones are refused with the expected keys
/// (ignored under the `accept_unknown_tool_field` sabotage control).
pub fn keys(o: &Obj, allowed: &[&str], required: &[&str]) -> Result<(), Fail> {
    if !crate::sabotage!("accept_unknown_tool_field") {
        if let Err(e) = o.only(allowed) {
            return Err(invalid(&e, Some(allowed)));
        }
    }
    for k in required {
        o.req(k).map_err(|e| invalid(&e, Some(allowed)))?;
    }
    Ok(())
}

pub fn opt_str<'a>(o: &Obj<'a>, k: &str) -> Result<Option<&'a str>, Fail> {
    o.opt_str(k).map_err(|e| invalid(&e, None))
}

pub fn req_str<'a>(o: &Obj<'a>, k: &str) -> Result<&'a str, Fail> {
    o.str(k).map_err(|e| invalid(&e, None))
}

pub fn opt_u64(o: &Obj, k: &str) -> Result<Option<u64>, Fail> {
    match o.get(k) {
        None => Ok(None),
        Some(_) => o.u64(k, u64::MAX).map(Some).map_err(|e| invalid(&e, None)),
    }
}

pub fn opt_bool(o: &Obj, k: &str) -> Result<Option<bool>, Fail> {
    match o.get(k) {
        None => Ok(None),
        Some(_) => o.bool(k).map(Some).map_err(|e| invalid(&e, None)),
    }
}

pub fn opt_arr<'a>(o: &Obj<'a>, k: &str) -> Result<Option<&'a [Json]>, Fail> {
    match o.get(k) {
        None => Ok(None),
        Some(_) => o.arr(k).map(Some).map_err(|e| invalid(&e, None)),
    }
}
