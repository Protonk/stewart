//! Argument parsing and presentation (INTERFACE 5.1). Arguments are exact:
//! no abbreviations and no configuration files. A usage error (exit 2) means
//! no operation began; it prints to stderr only.

use crate::archive::Audit;
use crate::help;
use crate::ids;
use crate::json::J;
use crate::ops;
use crate::reply::{Cause, Outcome, Reply};
use std::io::Write;

const USAGE: &str = "\
usage: stewart new FOLDER [--archive ROOT] [--json]
       stewart prepare REF [--json]
       stewart commission REF HANDLE --i-am-finished [--json]
       stewart receipt REF [--verify] [--json]
       stewart receipt REF --read ITEM
       stewart status REF [--json]
       stewart status --archive ROOT [--json]
       stewart run REF [--json]
       stewart close REF [--confirm TOKEN] [--surrender LOSS]... [--destination DIR] [--json]
       stewart help [commands | forms | limits | reader | close]";

struct Usage(String);

fn usage(msg: impl Into<String>) -> Usage {
    Usage(msg.into())
}

/// Options and positionals of one command line, parsed exactly.
struct Args {
    positionals: Vec<String>,
    flags: Vec<String>,
    values: Vec<(String, String)>,
}

fn parse(
    args: &[String],
    flags: &[&str],
    valued: &[&str],
    repeatable: &[&str],
) -> Result<Args, Usage> {
    let mut out = Args {
        positionals: Vec::new(),
        flags: Vec::new(),
        values: Vec::new(),
    };
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        if a.starts_with("--") {
            if flags.contains(&a.as_str()) {
                if out.flags.contains(a) {
                    return Err(usage(format!("{a} is given twice")));
                }
                out.flags.push(a.clone());
            } else if valued.contains(&a.as_str()) {
                let Some(v) = args.get(i + 1) else {
                    return Err(usage(format!("{a} needs a value")));
                };
                if !repeatable.contains(&a.as_str()) && out.values.iter().any(|(k, _)| k == a) {
                    return Err(usage(format!("{a} is given twice")));
                }
                out.values.push((a.clone(), v.clone()));
                i += 1;
            } else {
                return Err(usage(format!("unknown option {a}")));
            }
        } else {
            out.positionals.push(a.clone());
        }
        i += 1;
    }
    Ok(out)
}

impl Args {
    fn flag(&self, f: &str) -> bool {
        self.flags.iter().any(|x| x == f)
    }
    fn value(&self, k: &str) -> Option<String> {
        self.values
            .iter()
            .find(|(key, _)| key == k)
            .map(|(_, v)| v.clone())
    }
    fn all(&self, k: &str) -> Vec<String> {
        self.values
            .iter()
            .filter(|(key, _)| key == k)
            .map(|(_, v)| v.clone())
            .collect()
    }
    fn exactly(&self, n: usize, what: &str) -> Result<(), Usage> {
        if self.positionals.len() != n {
            return Err(usage(format!(
                "expected {what}, got {} argument(s)",
                self.positionals.len()
            )));
        }
        Ok(())
    }
}

fn absolute(what: &str, p: &str) -> Result<(), Usage> {
    ids::check_absolute(p).map_err(|e| usage(format!("{what} {p:?}: {e}; paths given as arguments are absolute, without . or .. components or a trailing /")))
}

enum Plan {
    Reply {
        reply: Reply,
        json: bool,
        reference: Option<String>,
        mutating: bool,
    },
    Raw {
        bytes: Option<Vec<u8>>,
        line: J,
        exit: i32,
    },
    Text(String),
}

fn plan(argv: &[String]) -> Result<Plan, Usage> {
    let Some(cmd) = argv.first() else {
        return Err(usage("a command is required"));
    };
    let rest = &argv[1..];
    match cmd.as_str() {
        "help" => {
            let a = parse(rest, &[], &[], &[])?;
            match a.positionals.as_slice() {
                [] => Ok(Plan::Text(help::overview())),
                [t] => help::topic(t).map(Plan::Text).ok_or_else(|| {
                    usage(format!(
                        "unknown help topic {t:?}; topics: {}",
                        help::TOPICS.join(", ")
                    ))
                }),
                _ => Err(usage("help takes at most one topic")),
            }
        }
        "new" => {
            let a = parse(rest, &["--json"], &["--archive"], &[])?;
            a.exactly(1, "FOLDER")?;
            let folder = &a.positionals[0];
            absolute("FOLDER", folder)?;
            let root = match a.value("--archive") {
                Some(r) => Some(r),
                None => match std::env::var_os("STEWART_ARCHIVE") {
                    None => None,
                    Some(v) if v.is_empty() => None,
                    Some(v) => Some(
                        v.into_string()
                            .map_err(|_| usage("STEWART_ARCHIVE is not valid UTF-8"))?,
                    ),
                },
            };
            if let Some(r) = &root {
                absolute("the archive root", r)?;
            }
            Ok(Plan::Reply {
                reply: ops::new::run(folder, root.as_deref()),
                json: a.flag("--json"),
                reference: None,
                mutating: true,
            })
        }
        "prepare" => {
            let a = parse(rest, &["--json"], &[], &[])?;
            a.exactly(1, "REF")?;
            let r = a.positionals[0].clone();
            Ok(Plan::Reply {
                reply: ops::prepare::run(&r),
                json: a.flag("--json"),
                reference: Some(r),
                mutating: true,
            })
        }
        "commission" => {
            let a = parse(rest, &["--json", "--i-am-finished"], &[], &[])?;
            a.exactly(2, "REF HANDLE")?;
            let r = a.positionals[0].clone();
            let reply = ops::commission::run(&r, &a.positionals[1], a.flag("--i-am-finished"));
            Ok(Plan::Reply {
                reply,
                json: a.flag("--json"),
                reference: Some(r),
                mutating: true,
            })
        }
        "receipt" => {
            let a = parse(rest, &["--json", "--verify"], &["--read"], &[])?;
            a.exactly(1, "REF")?;
            let r = a.positionals[0].clone();
            if let Some(item) = a.value("--read") {
                if a.flag("--json") || a.flag("--verify") {
                    return Err(usage(
                        "--read writes raw bytes; it takes neither --json nor --verify",
                    ));
                }
                let res = ops::receipt::read(&r, &item);
                return Ok(Plan::Raw {
                    bytes: res.bytes,
                    line: res.line,
                    exit: res.exit,
                });
            }
            Ok(Plan::Reply {
                reply: ops::receipt::run(&r, a.flag("--verify")),
                json: a.flag("--json"),
                reference: Some(r),
                mutating: false,
            })
        }
        "status" => {
            let a = parse(rest, &["--json"], &["--archive"], &[])?;
            if let Some(root) = a.value("--archive") {
                a.exactly(0, "no REF with --archive")?;
                absolute("the archive root", &root)?;
                return Ok(Plan::Reply {
                    reply: ops::status::run_archive(&root),
                    json: a.flag("--json"),
                    reference: None,
                    mutating: false,
                });
            }
            a.exactly(1, "REF")?;
            let r = a.positionals[0].clone();
            Ok(Plan::Reply {
                reply: ops::status::run(&r),
                json: a.flag("--json"),
                reference: Some(r),
                mutating: false,
            })
        }
        "run" => {
            let a = parse(rest, &["--json"], &[], &[])?;
            a.exactly(1, "REF")?;
            let r = a.positionals[0].clone();
            Ok(Plan::Reply {
                reply: ops::run::run(&r),
                json: a.flag("--json"),
                reference: Some(r),
                mutating: true,
            })
        }
        "close" => {
            let a = parse(
                rest,
                &["--json"],
                &["--confirm", "--surrender", "--destination"],
                &["--surrender"],
            )?;
            a.exactly(1, "REF")?;
            let r = a.positionals[0].clone();
            let confirm = a.value("--confirm");
            let surrender = a.all("--surrender");
            let destination = a.value("--destination");
            // A surrender is part of a confirmation, and a replacement
            // destination serves only a delivery still owed. Whether DIR is an
            // existing absolute directory is close's refusal
            // (destination_invalid), checked against the records.
            if !surrender.is_empty() && confirm.is_none() {
                return Err(usage("--surrender is accepted only with --confirm"));
            }
            if destination.is_some() && confirm.is_some() {
                return Err(usage("--destination is accepted only without --confirm"));
            }
            let flags = ops::close::Flags {
                confirm,
                surrender,
                destination,
            };
            Ok(Plan::Reply {
                reply: ops::close::run(&r, &flags),
                json: a.flag("--json"),
                reference: Some(r),
                mutating: true,
            })
        }
        other => Err(usage(format!("unknown command {other:?}"))),
    }
}

/// Run the command line; returns the exit status.
pub fn main() -> i32 {
    let mut argv = Vec::new();
    for a in std::env::args_os().skip(1) {
        match a.into_string() {
            Ok(s) => argv.push(s),
            Err(_) => {
                eprintln!("stewart: arguments must be valid UTF-8\n{USAGE}");
                return 2;
            }
        }
    }
    match plan(&argv) {
        Err(Usage(msg)) => {
            eprintln!(
                "stewart: {msg}\n{USAGE}\nRun `stewart help` for the manager's path and topics."
            );
            2
        }
        Ok(Plan::Text(t)) => {
            let mut out = std::io::stdout().lock();
            if out
                .write_all(t.as_bytes())
                .and_then(|_| out.flush())
                .is_err()
            {
                return 4;
            }
            0
        }
        Ok(Plan::Raw { bytes, line, exit }) => {
            if let Some(b) = bytes {
                let mut out = std::io::stdout().lock();
                if let Err(e) = out.write_all(&b).and_then(|_| out.flush()) {
                    let l = J::obj()
                        .with("item", line.get("item").cloned().unwrap_or(J::Null))
                        .with("verified", true)
                        .with("written", false)
                        .with("error", crate::util::errno_name(&e));
                    eprintln!("{}", l.string());
                    return 4;
                }
            }
            eprintln!("{}", line.string());
            exit
        }
        Ok(Plan::Reply {
            reply,
            json,
            reference,
            mutating,
        }) => emit(&reply, json, reference.as_deref(), mutating),
    }
}

fn emit(reply: &Reply, json: bool, reference: Option<&str>, mutating: bool) -> i32 {
    let bytes = if json {
        reply.json_line()
    } else {
        reply.human().into_bytes()
    };
    let written = crate::fault!("reply.write").and_then(|_| {
        let mut out = std::io::stdout().lock();
        out.write_all(&bytes).and_then(|_| out.flush())
    });
    match written {
        Ok(()) => reply.exit_code(),
        Err(e) => {
            // The reply could not be written: keep a durable account if this
            // operation may have changed the audit, then say so on stderr.
            let mut recorded = false;
            if mutating {
                if let Some(r) = reference {
                    if let Ok(mut audit) = Audit::open(r) {
                        if audit.require_mutation().is_ok() {
                            let body = J::obj()
                                .with("operation", reply.operation)
                                .with("outcome", "reply_not_written")
                                .with("reason", J::Null)
                                .with("message", "The reply could not be written; this record is the account of the invocation's result.")
                                .with("reply", reply.to_j())
                                .with("causes", J::Arr(vec![Cause::io("write reply", &e).to_j()]));
                            recorded = audit.write_diag(body).is_ok();
                        }
                    }
                }
            }
            eprintln!(
                "stewart {}: the reply could not be written ({}); outcome was {}. {}",
                reply.operation,
                crate::util::errno_name(&e),
                reply.outcome.name(),
                if recorded {
                    "A diagnostic records the result; status reads it."
                } else {
                    "Run status to learn what was recorded."
                }
            );
            if reply.outcome == Outcome::Completed {
                4
            } else {
                reply.exit_code().max(4)
            }
        }
    }
}
