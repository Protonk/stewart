//! A live placement for driving the auditor's tools in process: a
//! commissioned audit (made by the real binary), a published `run_started`,
//! its run directory and world. Each call is captured and its result
//! recorded the way the run adapter records them, so re-entry reads real
//! result records.

#![allow(dead_code)]

use crate::common::*;
use stewart::answer::{self, Call, Executed, NoticesUsed, Placement};
use stewart::archive::Audit;
use stewart::bodies::{ProviderUse, RunEnded, RunObservations, RunStarted};
use stewart::json::{self, J, Json};
use stewart::log::{self, LogState};
use stewart::runs::{self, RunDir, ToolResult};
use stewart::usage::Usage;
use stewart::util;
use stewart::world::World;

pub struct Live {
    pub e: Env,
    pub r: String,
    pub audit: Audit,
    pub world: World,
    pub placement: Placement,
    pub rd: RunDir,
    pub calls: u64,
}

/// One executed call, its envelope decoded and its content blocks' text.
pub struct Res {
    pub ex: Executed,
    pub env: Json,
    pub blocks: Vec<String>,
}

impl Res {
    pub fn outcome(&self) -> &str {
        s(&self.env, &["outcome"])
    }
    pub fn reason(&self) -> &str {
        s(&self.env, &["reason"])
    }
    pub fn data(&self, path: &[&str]) -> &Json {
        let mut p = vec!["data"];
        p.extend_from_slice(path);
        at(&self.env, &p)
    }
    pub fn str(&self, path: &[&str]) -> &str {
        self.data(path)
            .as_str()
            .unwrap_or_else(|| panic!("{path:?} is not a string: {}", self.text()))
    }
    pub fn num(&self, path: &[&str]) -> u64 {
        self.data(path)
            .as_u64()
            .unwrap_or_else(|| panic!("{path:?} is not an integer: {}", self.text()))
    }
    pub fn effect(&self, k: &str) -> &str {
        s(&self.env, &["effects", k])
    }
    pub fn text(&self) -> String {
        self.blocks[0].clone()
    }
    pub fn ok(&self) -> &Res {
        assert_eq!(self.outcome(), "completed", "{}", self.text());
        self
    }
    pub fn next_tools(&self) -> Vec<String> {
        at(&self.env, &["next"])
            .as_arr()
            .unwrap()
            .iter()
            .map(|n| s(n, &["tool"]).to_string())
            .collect()
    }
    pub fn next_input(&self, i: usize) -> String {
        at(&self.env, &["next", &i.to_string(), "input"])
            .to_j()
            .string()
    }
}

pub fn question_with(e: &Env, family: &str, body: &str) {
    std::fs::write(
        format!("{}/question.md", e.folder),
        e.question(family, body),
    )
    .unwrap();
}

impl Live {
    /// A commissioned audit of `family` with these materials, launched.
    pub fn open(family: &str, body: &str, materials: &[(&str, &[u8])]) -> Live {
        Live::open_env(family, body, materials, &[])
    }

    /// As `open`, with environment variables for the binary's prepare.
    pub fn open_env(
        family: &str,
        body: &str,
        materials: &[(&str, &[u8])],
        env: &[(&str, &str)],
    ) -> Live {
        let e = Env::new();
        let r = e.new_ref();
        e.fill(body, materials);
        question_with(&e, family, body);
        let o = e.run_env(&["prepare", &r, "--json"], env);
        assert_eq!(o.code, Some(0), "{}", o.text());
        let h = s(&o.json(), &["data", "prepared"]).to_string();
        let o = e.commission(&r, &h);
        assert_eq!(o.code, Some(0), "{}", o.text());
        Live::start(e, r)
    }

    /// The default audit: open inquiry over two small materials.
    pub fn new() -> Live {
        Live::open(
            "open-inquiry",
            "Is the retry safe?\n",
            &[
                ("a.py", b"def retry():\r\n    send()\n    send()\n" as &[u8]),
                ("blank.txt", b"  \n"),
                ("notes.txt", b"retry() is called twice.\n"),
                ("u.txt", "h\u{e9}llo\n".as_bytes()),
            ],
        )
    }

    fn start(e: Env, r: String) -> Live {
        let mut audit = Audit::open(&r).unwrap();
        audit.exe = Some(stewart::platform::Exe {
            path: audit.refile.writer_path.clone(),
            sha256: audit.refile.writer_sha256.clone(),
        });
        let state = log::read(&audit);
        let world = stewart::world::load(&audit, &state).unwrap_or_else(|p| panic!("{p:?}"));
        let (placement, rd) = launch(&audit, &state, &world);
        Live {
            e,
            r,
            audit,
            world,
            placement,
            rd,
            calls: 0,
        }
    }

    pub fn state(&self) -> LogState {
        log::read(&self.audit)
    }

    pub fn audit_dir(&self) -> String {
        self.e.audit_dir(&self.r)
    }

    /// Execute a block as the run would: capture it, execute it, record
    /// its result.
    pub fn call_raw(&mut self, name: Option<&str>, input: Option<&[u8]>) -> Res {
        self.calls += 1;
        let c = self.calls;
        let id = format!("toolu_{:02}_{c}", self.placement.run);
        let mut block = format!("{{\"type\":\"tool_use\",\"id\":\"{id}\",\"name\":").into_bytes();
        match name {
            Some(n) => json::escape_into(n, &mut block),
            None => block.extend_from_slice(b"null"),
        }
        block.extend_from_slice(b",\"input\":");
        block.extend_from_slice(input.unwrap_or(b"null"));
        block.push(b'}');
        self.rd.write_call(c, &block).unwrap();
        let call = Call {
            call: c,
            tool_use_id: &id,
            name,
            input,
        };
        let ex = answer::execute(&self.audit, &self.world, &self.placement, &call);
        self.record(c, &id, name, input, &block, &ex);
        decode(ex)
    }

    pub fn record(
        &self,
        c: u64,
        id: &str,
        name: Option<&str>,
        input: Option<&[u8]>,
        block: &[u8],
        ex: &Executed,
    ) {
        let t = ToolResult {
            call: c,
            request: 1,
            attempt: 1,
            block: 0,
            call_bytes: block.len() as u64,
            call_sha256: util::sha256_hex(block),
            tool_use_id: id.to_string(),
            tool: name.map(str::to_string),
            input_sha256: input.map(util::sha256_hex),
            replay_of: None,
            outcome: ex.outcome.name().to_string(),
            reason: ex.reason.clone(),
            revision: ex.revision,
            log_record: ex.log_record.clone(),
            is_error: ex.is_error,
            content: ex.content.clone(),
        };
        self.rd
            .publish(&self.audit, "tool_result", &runs::result_name(c), t.to_j())
            .unwrap();
    }

    pub fn call(&mut self, tool: &str, input: &str) -> Res {
        self.call_raw(Some(tool), Some(input.as_bytes()))
    }

    /// End this placement (interrupted) and start the next one.
    pub fn continue_run(&mut self) {
        self.continue_run_with(Usage::default());
    }

    /// As `continue_run`, recording `usage` as the ended placement's charge.
    pub fn continue_run_with(&mut self, usage: Usage) {
        let run = self.placement.run;
        let body = RunEnded {
            run,
            ending: "interrupted".into(),
            cause: Some("signal".into()),
            recorded_by: "run".into(),
            provider: None,
            requests: 0,
            attempts: 0,
            usage,
            notices: vec![],
            seal: None,
            message: "test".into(),
        };
        log::publish(&self.audit, "run_ended", |_| Ok(body.to_j()))
            .ok()
            .unwrap();
        let state = self.state();
        let (placement, rd) = launch(&self.audit, &state, &self.world);
        self.placement = placement;
        self.rd = rd;
        self.calls = 0;
    }

    /// Publish `close_requested` as close's step 4 does.
    pub fn request_close(&self) -> u64 {
        let body = stewart::bodies::CloseRequested {
            flags: Default::default(),
        };
        log::publish(&self.audit, "close_requested", |_| Ok(body.to_j()))
            .ok()
            .unwrap()
            .n
    }

    /// Record an entry and return its handle.
    pub fn add(&mut self, tool: &str, text: &str, label: &str) -> String {
        let input = J::obj().with("text", text).with("label", label).string();
        let r = self.call(tool, &input);
        r.ok();
        r.str(&["entry"]).to_string()
    }

    pub fn file(&self, rel: &str) -> Vec<u8> {
        std::fs::read(format!("{}/{rel}", self.audit_dir())).unwrap()
    }
}

fn launch(audit: &Audit, state: &LogState, world: &World) -> (Placement, RunDir) {
    let run = state.next_run();
    let body = RunStarted {
        run,
        arrangement_sha256: world.arrangement_sha256.clone(),
        provider: ProviderUse {
            base_url: "https://api.anthropic.com".into(),
            overridden: false,
            proxy: None,
            anthropic_version: stewart::forms::ANTHROPIC_VERSION.into(),
        },
        observations: RunObservations::current(),
    };
    log::publish(audit, "run_started", |_| Ok(body.to_j()))
        .ok()
        .unwrap();
    let rd = RunDir::create(audit, run).unwrap();
    let state = log::read(audit);
    let placement = Placement {
        run,
        continuing: run > 1,
        used: state.recorded_usage(),
        limits: state.limits().unwrap(),
        notices_used: NoticesUsed {
            reminder: state.notice_used("reminder"),
            near_limit: state.notice_used("near_limit"),
        },
    };
    (placement, rd)
}

/// Decode an account's content: the envelope and every block's text.
pub fn decode(ex: Executed) -> Res {
    let content = json::parse(&ex.content).expect("content is strict JSON");
    let blocks: Vec<String> = content
        .as_arr()
        .expect("content is an array")
        .iter()
        .map(|b| {
            assert_eq!(s(b, &["type"]), "text");
            s(b, &["text"]).to_string()
        })
        .collect();
    let env = json::parse(blocks[0].as_bytes()).expect("the envelope is strict JSON");
    assert_eq!(s(&env, &["schema"]), "stewart.reply/1");
    assert_eq!(ex.is_error, s(&env, &["outcome"]) != "completed");
    Res { ex, env, blocks }
}
