//! One duplicate-safe JSON parser for every control surface.
use crate::{Error, Result};
use serde::de::{self, DeserializeOwned, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer};
use serde_json::{Map, Number, Value};
use std::fmt;

struct Unique(Value);
impl<'de> Deserialize<'de> for Unique {
    fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = Unique;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("JSON without repeated keys")
            }
            fn visit_bool<E: de::Error>(self, v: bool) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Bool(v)))
            }
            fn visit_i64<E: de::Error>(self, v: i64) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Number(v.into())))
            }
            fn visit_u64<E: de::Error>(self, v: u64) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Number(v.into())))
            }
            fn visit_f64<E: de::Error>(self, v: f64) -> std::result::Result<Unique, E> {
                Number::from_f64(v)
                    .map(|n| Unique(Value::Number(n)))
                    .ok_or_else(|| E::custom("nonfinite number"))
            }
            fn visit_str<E: de::Error>(self, v: &str) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::String(v.into())))
            }
            fn visit_string<E: de::Error>(self, v: String) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::String(v)))
            }
            fn visit_none<E: de::Error>(self) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Null))
            }
            fn visit_unit<E: de::Error>(self) -> std::result::Result<Unique, E> {
                Ok(Unique(Value::Null))
            }
            fn visit_seq<A: SeqAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                let mut out = Vec::new();
                while let Some(Unique(v)) = a.next_element()? {
                    out.push(v);
                }
                Ok(Unique(Value::Array(out)))
            }
            fn visit_map<A: MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Unique, A::Error> {
                let mut out = Map::new();
                while let Some(k) = a.next_key::<String>()? {
                    if out.contains_key(&k) {
                        return Err(de::Error::custom(format!("duplicate key: {k}")));
                    }
                    let Unique(v) = a.next_value()?;
                    out.insert(k, v);
                }
                Ok(Unique(Value::Object(out)))
            }
        }
        d.deserialize_any(V)
    }
}
pub fn value(raw: &[u8], path: &str) -> Result<Value> {
    let mut d = serde_json::Deserializer::from_slice(raw);
    let Unique(v)=Unique::deserialize(&mut d).map_err(|e| Error::new(if e.to_string().contains("duplicate key:") {"duplicate_key"} else {"invalid_json"},e.to_string(),path,"Keep the original bytes; supply a new valid request or inspect the retained diagnostic."))?;
    d.end().map_err(|e| {
        Error::new(
            "invalid_json",
            e.to_string(),
            path,
            "Keep the original bytes; trailing JSON is not accepted.",
        )
    })?;
    Ok(v)
}
pub fn parse<T: DeserializeOwned>(raw: &[u8], schema: &str, path: &str) -> Result<T> {
    let v = value(raw, path)?;
    match v.get("schema").and_then(Value::as_str) {
        Some(s) if s == schema => (),
        Some(s) => {
            return Err(Error::new(
                "unsupported_schema",
                format!("Schema {s} is unsupported; expected {schema}"),
                path,
                "Use a reader for this exact schema; do not rewrite historical records.",
            ));
        }
        None => {
            return Err(Error::new(
                "invalid_record",
                "Missing string schema",
                path,
                "Preserve the record and inspect its origin.",
            ));
        }
    }
    serde_json::from_value(v).map_err(|e| {
        Error::new(
            "invalid_record",
            e.to_string(),
            path,
            "Preserve the record; correct a new request rather than editing retained receipts.",
        )
    })
}
