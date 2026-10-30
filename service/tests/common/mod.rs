//! Shared harness for the end-to-end tests: each test gets its own disjoint
//! folder, archive and destination under a fresh temporary directory, and
//! runs the real `stewart` binary from an unrelated working directory.

#![allow(dead_code)]

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use stewart::json::{self, Json};

pub struct Env {
    pub base: PathBuf,
    pub folder: String,
    pub archive: String,
    pub dest: String,
    pub cwd: String,
    pub extra_env: Vec<(String, String)>,
}

impl Drop for Env {
    fn drop(&mut self) {
        // Restore permissions a test may have narrowed, then remove the scratch tree.
        let _ = Command::new("chmod")
            .args(["-R", "u+rwx"])
            .arg(&self.base)
            .status();
        let _ = std::fs::remove_dir_all(&self.base);
    }
}

pub struct Out {
    pub code: Option<i32>,
    pub stdout: Vec<u8>,
    pub stderr: String,
}

impl Out {
    pub fn json(&self) -> Json {
        assert!(
            !self.stdout.is_empty(),
            "no stdout; stderr: {}",
            self.stderr
        );
        json::parse(&self.stdout).unwrap_or_else(|e| {
            panic!(
                "reply is not strict JSON ({e}): {}",
                String::from_utf8_lossy(&self.stdout)
            )
        })
    }
    pub fn text(&self) -> String {
        String::from_utf8_lossy(&self.stdout).into_owned()
    }
}

/// A path inside a decoded reply, by keys and array indexes.
pub fn at<'a>(v: &'a Json, path: &[&str]) -> &'a Json {
    let mut cur = v;
    for p in path {
        cur = match &cur.v {
            json::V::Obj(m) => {
                &m.iter()
                    .find(|(k, _)| k == p)
                    .unwrap_or_else(|| panic!("no key {p}"))
                    .1
            }
            json::V::Arr(a) => &a[p.parse::<usize>().expect("index")],
            _ => panic!("cannot descend into {p}"),
        };
    }
    cur
}

pub fn s<'a>(v: &'a Json, path: &[&str]) -> &'a str {
    at(v, path)
        .as_str()
        .unwrap_or_else(|| panic!("{path:?} is not a string"))
}

pub fn has(v: &Json, key: &str) -> bool {
    matches!(&v.v, json::V::Obj(m) if m.iter().any(|(k, _)| k == key))
}

pub fn strs(v: &Json, path: &[&str]) -> Vec<String> {
    at(v, path)
        .as_arr()
        .expect("array")
        .iter()
        .map(|x| x.as_str().expect("string").to_string())
        .collect()
}

pub fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_stewart")
}

impl Env {
    /// Scratch space comes from `STEWART_IT_TMP` when set, else the system
    /// temporary directory. On Linux the archive must be on ext4, xfs or
    /// btrfs, so point `STEWART_IT_TMP` at such a directory when `/tmp` is
    /// tmpfs or overlayfs.
    pub fn new() -> Env {
        let base_dir = std::env::var_os("STEWART_IT_TMP")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir);
        let root = std::fs::canonicalize(base_dir).unwrap();
        let mut buf = [0u8; 8];
        stewart::platform::random_fill(&mut buf).unwrap();
        let base = root.join(format!("stewart-it-{}", stewart::ids::base32(&buf)));
        std::fs::create_dir_all(&base).unwrap();
        let p = |n: &str| base.join(n).to_str().unwrap().to_string();
        std::fs::create_dir_all(base.join("returns")).unwrap();
        std::fs::create_dir_all(base.join("elsewhere")).unwrap();
        Env {
            folder: p("q"),
            archive: p("archive"),
            dest: p("returns"),
            cwd: p("elsewhere"),
            base,
            extra_env: Vec::new(),
        }
    }

    pub fn path(&self, rel: &str) -> String {
        self.base.join(rel).to_str().unwrap().to_string()
    }

    pub fn run(&self, args: &[&str]) -> Out {
        self.run_env(args, &[])
    }

    pub fn run_env(&self, args: &[&str], env: &[(&str, &str)]) -> Out {
        let mut c = Command::new(bin());
        c.args(args)
            .current_dir(&self.cwd)
            .env_remove("STEWART_ARCHIVE")
            .env_remove("STEWART_TEST_FAULT")
            .env_remove("STEWART_TEST_SABOTAGE");
        for (k, v) in &self.extra_env {
            c.env(k, v);
        }
        for (k, v) in env {
            c.env(k, v);
        }
        c.stdin(Stdio::null());
        let o = c.output().expect("run stewart");
        Out {
            code: o.status.code(),
            stdout: o.stdout,
            stderr: String::from_utf8_lossy(&o.stderr).into_owned(),
        }
    }

    /// `new` with the scaffold, returning the reference.
    pub fn new_ref(&self) -> String {
        let o = self.run(&["new", &self.folder, "--archive", &self.archive, "--json"]);
        assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
        s(&o.json(), &["data", "reference"]).to_string()
    }

    pub fn question(&self, family: &str, body: &str) -> String {
        format!(
            "---\nstewart: question/1\nfamily: {family}\nmodel: claude-opus-5-5\ndestination: {}\nlimit-turns: 200\nlimit-input-tokens: 20000000\nlimit-output-tokens: 400000\n---\n{body}",
            self.dest
        )
    }

    /// Write a valid question and the given materials.
    pub fn fill(&self, body: &str, materials: &[(&str, &[u8])]) {
        std::fs::write(
            format!("{}/question.md", self.folder),
            self.question("open-inquiry", body),
        )
        .unwrap();
        for (name, bytes) in materials {
            let p = format!("{}/materials/{name}", self.folder);
            std::fs::create_dir_all(Path::new(&p).parent().unwrap()).unwrap();
            std::fs::write(&p, bytes).unwrap();
        }
    }

    /// new + fill + prepare; returns (reference, handle).
    pub fn prepared(&self, materials: &[(&str, &[u8])]) -> (String, String) {
        let r = self.new_ref();
        self.fill("Audit our app to make sure there are no bugs.\n", materials);
        let o = self.run(&["prepare", &r, "--json"]);
        assert_eq!(o.code, Some(0), "{}{}", o.text(), o.stderr);
        (r, s(&o.json(), &["data", "prepared"]).to_string())
    }

    pub fn commission(&self, r: &str, h: &str) -> Out {
        self.run(&["commission", r, h, "--i-am-finished", "--json"])
    }

    pub fn audit_dir(&self, r: &str) -> String {
        let id = r.split(':').nth(1).unwrap();
        format!("{}/audits/{id}", self.archive)
    }

    /// Kinds of the audit's log records, in order (read independently).
    pub fn log_kinds(&self, r: &str) -> Vec<String> {
        let dir = format!("{}/log", self.audit_dir(r));
        let mut n = 1;
        let mut out = Vec::new();
        while let Ok(b) = std::fs::read(format!("{dir}/{n}.json")) {
            let j = json::parse(&b).unwrap();
            out.push(s(&j, &["kind"]).to_string());
            n += 1;
        }
        out
    }

    pub fn log_record(&self, r: &str, n: usize) -> Json {
        json::parse(&std::fs::read(format!("{}/log/{n}.json", self.audit_dir(r))).unwrap()).unwrap()
    }

    /// An independent inventory of the archive: path -> (inode, size, digest).
    pub fn inventory(&self) -> BTreeMap<String, (u64, u64, String)> {
        let mut out = BTreeMap::new();
        walk(Path::new(&self.archive), &mut out);
        out
    }
}

fn walk(p: &Path, out: &mut BTreeMap<String, (u64, u64, String)>) {
    use std::os::unix::fs::MetadataExt;
    let Ok(rd) = std::fs::read_dir(p) else { return };
    for e in rd.flatten() {
        let path = e.path();
        let md = std::fs::symlink_metadata(&path).unwrap();
        if md.is_dir() {
            out.insert(format!("{}/", path.display()), (md.ino(), 0, String::new()));
            walk(&path, out);
        } else {
            let bytes = std::fs::read(&path).unwrap_or_default();
            out.insert(
                path.display().to_string(),
                (md.ino(), md.len(), stewart::util::sha256_hex(&bytes)),
            );
        }
    }
}

/// Every entry of `before` is still present and unchanged in `after`.
pub fn only_additions(
    before: &BTreeMap<String, (u64, u64, String)>,
    after: &BTreeMap<String, (u64, u64, String)>,
) -> Result<(), String> {
    for (k, v) in before {
        match after.get(k) {
            None => return Err(format!("{k} was removed")),
            Some(a) if a != v => return Err(format!("{k} was rewritten")),
            _ => {}
        }
    }
    Ok(())
}
