#!/usr/bin/env python3
"""Keep a small tracked record of what the container suites have shown.

The record, apparatus/qualified.json, is a moving front with temporary pins.
For each suite and platform it keeps the latest run, and, when that run did
not qualify, also the latest run that did. Any other record stays only while
it is pinned, with a reason and a condition, stated in words, for releasing
it. An experiment is recorded only by pinning it. Git history keeps the
records that leave. apparatus/qualified.md is rendered from the JSON and must
not be edited by hand.

Every recorded value is read from a run's own evidence under .scratch/ (local
to the machine that ran it; clones do not carry it). A record's evidence path
is always .scratch/ followed by its id, and check reads the evidence there:
in the folder that the listing of .scratch/ names exactly as the id, case
included, so on a case-insensitive volume a folder whose name differs only in
case is not that record's evidence. Every path inside a run folder is matched
the same way, one component at a time against its folder's listing, without
following a link. When .scratch/ exists but a record's folder is absent, check
warns (--require-evidence makes it fail).
The only typed text is a pin's reason and condition and an experiment's
summary. An experiment's result is one file, or a folder ("." for the whole
experiment folder) digested as a sorted listing of every regular file under
it: the digest covers each file's path, size and contents, not mode bits or
empty folders, and skips files named .DS_Store, which Finder writes into a
folder a person opens. If a field cannot be read, extract fails and names it.
Check, render and the other commands fail with a reason, never a traceback,
on a record that is malformed or nested too deeply. A run's outcome is
decided mechanically: "qualified" only when its completion record reports no
failures, every expectation its script makes of the exit records holds, the
driver exited 0 with no failed or skipped case, no broken check and every
control fired, the timing gate passed where it was on, and the end-to-end
case passed.

Run it from the repository root with an isolated interpreter:

    python3 -I -B apparatus/qualified.py extract RUN_DIR --suite acceptance
    python3 -I -B apparatus/qualified.py check [--strict] [--require-evidence]
    python3 -I -B apparatus/qualified.py candidates
    python3 -I -B apparatus/qualified.py --self-test

Drift (reported by check) is measured against the working tree, so
uncommitted and untracked files count, and it excludes the record's own three
files: apparatus/qualified.py, qualified.json and qualified.md.

Standard library only. Git is used read-only, with optional locks, the index
auto-refresh and lazy fetching (GIT_NO_LAZY_FETCH, so a partial clone never
fetches a missing object from its remote) off, and without any GIT_* variable
from the caller's environment, so a hook's GIT_DIR or GIT_INDEX_FILE cannot
redirect it. Every command reads and writes qualified.json and qualified.md
only as regular files with one name in a real folder, refusing a symbolic or
hard link, a FIFO or anything else in their place, or a link in place of their
folder. The script writes those two files and, under --self-test, a new
temporary directory that it leaves in place: it contains no code that deletes
anything. Dot entries in .scratch/ are never records or removal candidates.
"""

import argparse
import ast
import copy
import datetime
import hashlib
import json
import math
import os
import posixpath
import re
import signal
import stat
import subprocess
import sys
import tempfile
import unicodedata

SCHEMA = "stewart.qualified/1"
DRIVER_SCHEMA = "stewart.acceptance-driver/1"
E2E_CASE = "e2e.reacting-audit"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD_REL = "apparatus/qualified.json"
MARKDOWN_REL = "apparatus/qualified.md"
SCRIPT_REL = "apparatus/qualified.py"
# The record's own files are not tested behavior, so they never count as drift.
RECORD_FILES = frozenset((SCRIPT_REL, RECORD_REL, MARKDOWN_REL))
DRIFT_ROOTS = ("service", "apparatus")
DRIFT_SHOWN = 12  # files listed per drift category before summarizing
# (container platform, record key, kernel machine name)
PLATFORMS = (("arm64", "linux-aarch64", "aarch64"), ("amd64", "linux-x86_64", "x86_64"))
SUITES = {
    "acceptance": {"script": "apparatus/acceptance.sh", "start": "acceptance suite start;"},
    "toolchain": {"script": "apparatus/step2.sh", "start": "step2 apparatus check start;",
                  "inner": "apparatus/container/inner-build.sh"},
}
EVIDENCE_WHERE = "local: only on the machine that ran it; clones do not carry it"
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})")
CITATION = re.compile(rb"\.scratch/([A-Za-z0-9._-]+)")
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
# A record's id is its .scratch folder's name: the characters a citation can name, never a dot entry.
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
DATE_KEYS = ("at", "ended_at", "finished_at")  # JSON fields that can date an experiment, in order
DATE_FROM = re.compile(r"(.+) field (%s)" % "|".join(DATE_KEYS))
O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
SELFTEST_LINE = re.compile(r"self-test: (\d+) checks, (\d+) passed, (\d+) failed, (\d+) skipped")
# Fields typed by a person rather than read from evidence; check does not re-derive them.
TYPED_FIELDS = ("pin", "summary")
# Finder writes a file with this name into a folder a person opens; a folder result's digest skips it.
FINDER_FILE = ".DS_Store"
# The deepest nesting of arrays and objects a record may have (stewart.qualified/1 uses 7), checked before any
# field is read, so no rendering or comparison can recurse without bound.
MAX_DEPTH = 32
# A build's name in a toolchain record: one folder name inside the run folder.
BUILD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class Refusal(Exception):
    """A command cannot proceed; the message says why and what to do."""


class ExtractError(Refusal):
    def __init__(self, run_id, problems):
        self.problems = list(dict.fromkeys(problems))  # each once: every read under a refused folder repeats it
        super().__init__("cannot extract %s; these fields could not be read:\n%s"
                         % (run_id, "\n".join("  - " + p for p in self.problems)))


def _no_repeats(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("repeated key %r" % key)
        out[key] = value
    return out


def parse_json(data):
    """Decode JSON bytes, refusing an object that repeats a key. Arrays and objects nested too deeply for the
    decoder raise ValueError, like any other JSON that cannot be decoded, rather than RecursionError."""
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_repeats)
    except RecursionError:
        raise ValueError("arrays and objects are nested too deeply to decode") from None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc(text):
    """Normalize an ISO 8601 time with an offset to YYYY-MM-DDTHH:MM:SSZ, or None."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        when = datetime.datetime.fromisoformat(text)
        if when.tzinfo is None:
            return None
        return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError):  # OverflowError: the UTC time falls outside years 1-9999
        return None


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def read_fd(fd):
    """Everything the open file FD holds from its current offset."""
    chunks = []
    while True:
        chunk = os.read(fd, 1 << 20)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def git_env(extra=None):
    """The environment of every git command this script runs. It drops every GIT_* variable the caller set (a hook
    sets GIT_DIR and GIT_INDEX_FILE; a shell may set GIT_WORK_TREE, GIT_TRACE*, GIT_CONFIG_* and others), so nothing
    outside this script can point a command at another repository or index or make it write a file. It turns
    optional locks off, so a read never takes the index lock, and lazy fetching off, so in a partial clone a missing
    object makes the command fail instead of being fetched from the remote. EXTRA, a context's own settings, comes
    last."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", LC_ALL="C")
    env.update(extra or {})
    return env


class Ctx:
    """The repository, its .scratch evidence and the record's paths."""

    def __init__(self, root, record=None, git_env=None):
        self.root = root
        self.record = record or os.path.join(root, *RECORD_REL.split("/"))
        self.markdown = os.path.splitext(self.record)[0] + ".md"
        self.scratch = os.path.join(root, ".scratch")
        self.git_env = git_env or {}

    def show(self, path):
        rel = os.path.relpath(path, self.root)
        return path if rel.startswith("..") else rel.replace(os.sep, "/")

    def git(self, args, check=True):
        env = git_env(self.git_env)  # see git_env for what is dropped and what is turned off
        proc = subprocess.run(["git", "-C", self.root] + list(args), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if check and proc.returncode != 0:
            raise Refusal("git %s failed with exit %d: %s" % (" ".join(args), proc.returncode,
                                                              proc.stderr.decode("utf-8", "replace").strip()))
        return proc

    def commit_exists(self, commit):
        return self.git(["cat-file", "-e", commit + "^{commit}"], check=False).returncode == 0

    def blob(self, commit, path):
        """The bytes of PATH at COMMIT (git show COMMIT:PATH), or None; why_no_blob says why."""
        proc = self.git(["cat-file", "blob", "%s:%s" % (commit, path)], check=False)
        return proc.stdout if proc.returncode == 0 else None

    def why_no_blob(self, commit, path):
        """Why blob(COMMIT, PATH) gave None. Existence is read from COMMIT's tree, which even a blobless partial
        clone holds; the contents may still be absent there, and are never fetched."""
        if self.git(["rev-parse", "-q", "--verify", "%s:%s" % (commit, path)], check=False).returncode == 0:
            return "%s exists at %s, but its contents are not available locally" % (path, commit)
        return "%s does not exist at %s" % (path, commit)


# ---------------------------------------------------------------- evidence

class Evidence:
    """Reads one run's records under .scratch/<run>; collects what it cannot read."""

    def __init__(self, ctx, run_id):
        self.id = run_id
        self.dir = os.path.join(ctx.scratch, run_id)
        self.problems = []

    def problem(self, text):
        self.problems.append(text)

    def path(self, rel):
        return os.path.join(self.dir, *rel.split("/"))

    def exists(self, rel):
        got = self._reach(rel, need=False)
        if got is not None:
            os.close(got[0])
        return got is not None

    def bytes(self, rel, need=True):
        """REL's bytes, or None. REL is found as _reach finds it and opened without following a link or blocking."""
        got = self._reach(rel, need)
        if got is None:
            return None
        dfd, name, st = got
        try:
            if not stat.S_ISREG(st.st_mode):
                self.problem("%s: not a regular file" % rel)
                return None
            fd = self._open_at(dfd, name, st, rel, os.O_NONBLOCK)
            if fd is None:
                return None
            try:
                return read_fd(fd)
            except OSError as exc:
                self.problem("%s: unreadable (%s)" % (rel, exc.strerror))
                return None
            finally:
                os.close(fd)
        finally:
            os.close(dfd)

    def text(self, rel, need=True):
        data = self.bytes(rel, need)
        if data is None:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            self.problem("%s: not UTF-8 text" % rel)
            return None

    def line(self, rel, need=True):
        text = self.text(rel, need)
        return None if text is None else text.strip()

    def exit(self, rel, need=True):
        text = self.line(rel, need)
        if text is None:
            return None
        if not re.fullmatch(r"-?\d+", text):
            self.problem("%s: not an exit status (%r)" % (rel, text[:40]))
            return None
        return int(text)

    def json(self, rel, need=True):
        data = self.bytes(rel, need)
        if data is None:
            return None
        try:
            return parse_json(data)
        except (ValueError, UnicodeDecodeError) as exc:
            self.problem("%s: not valid JSON (%s)" % (rel, exc))
            return None

    def digest(self, rel, need=True):
        data = self.bytes(rel, need)
        return None if data is None else sha256(data)

    def _entry(self, dfd, name, shown, need=True):
        """The lstat of NAME in the folder DFD, or None with a problem noted (a missing NAME only when NEED). NAME
        must be in the folder's listing exactly, case included: a case-insensitive volume would open a name that
        differs only in case, and that is not the file the record names."""
        try:
            names = os.listdir(dfd)
            st = os.stat(name, dir_fd=dfd, follow_symlinks=False) if name in names else None
        except OSError as exc:
            self.problem("%s: unreadable (%s)" % (shown, exc.strerror))
            return None
        if st is None and need:
            self.problem("%s: missing%s" % (shown, case_hint(names, name, "its folder")))
        return st

    def _reach(self, rel, need=True):
        """(descriptor of REL's folder, REL's name, REL's lstat), the folder opened by _open_folder and REL found by
        _entry; or None. The caller closes the descriptor."""
        folder, _, name = rel.rpartition("/")
        dfd = self._open_folder(folder, need)
        if dfd is None:
            return None
        st = self._entry(dfd, name, rel, need)
        if st is None:
            os.close(dfd)
            return None
        return dfd, name, st

    def _open_at(self, dfd, name, seen, shown, flags):
        """Open NAME in the folder DFD without following a link, as the inode SEEN (an lstat) showed; or None."""
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | O_CLOEXEC | flags, dir_fd=dfd)
        except OSError as exc:
            self.problem("%s: cannot be opened without following a link (%s)" % (shown, exc.strerror))
            return None
        try:
            st = os.fstat(fd)
        except OSError as exc:
            os.close(fd)
            self.problem("%s: unreadable (%s)" % (shown, exc.strerror))
            return None
        if (st.st_dev, st.st_ino, stat.S_IFMT(st.st_mode)) != (seen.st_dev, seen.st_ino, stat.S_IFMT(seen.st_mode)):
            os.close(fd)
            self.problem("%s: changed while it was read" % shown)
            return None
        return fd

    def _open_folder(self, rel, need=True):
        """A descriptor for the folder REL, reached one component at a time from the run folder, each component
        found by _entry and opened without following a link; or None."""
        try:
            fd = os.open(self.dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | O_CLOEXEC)
        except OSError as exc:
            self.problem(".: the run folder cannot be opened without following a link (%s)" % exc.strerror)
            return None
        parts = [p for p in rel.split("/") if p not in ("", ".")]
        for i, part in enumerate(parts):
            shown = "/".join(parts[:i + 1])
            st = self._entry(fd, part, shown, need)
            if st is not None and not stat.S_ISDIR(st.st_mode):
                self.problem("%s: %s" % (shown, "a link (links are refused)" if stat.S_ISLNK(st.st_mode)
                                         else "not a folder"))
                st = None
            sub = None if st is None else self._open_at(fd, part, st, shown, os.O_DIRECTORY)
            os.close(fd)
            if sub is None:
                return None
            fd = sub
        return fd

    def _file_digest(self, fd, shown):
        """(SHA-256, size) of what the open file FD holds, or None."""
        h, size = hashlib.sha256(), 0
        try:
            while True:
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
        except OSError as exc:
            self.problem("%s: unreadable (%s)" % (shown, exc.strerror))
            return None
        return h.hexdigest(), size

    def tree(self, rel):
        """(files, digest) for the folder REL, or None. The digest is the SHA-256 of a listing with one line
        "<SHA-256> <size> <path>\\n" per regular file under REL (path relative to REL, "/"-separated, UTF-8),
        sorted by path bytes. It therefore covers each file's path, size and contents, and not mode bits,
        timestamps or empty folders. A regular file named .DS_Store (FINDER_FILE), which Finder writes into a
        folder a person opens, is skipped and not counted. A link, or anything that is neither a regular file nor
        a folder, is refused. Every folder and file is opened through its parent's descriptor without following a
        link, so a link planted while the walk runs cannot redirect it."""
        top = self._open_folder(rel)
        if top is None:
            return None
        rows, before = [], len(self.problems)

        def walk(dfd, prefix):
            try:
                with os.scandir(dfd) as it:
                    found = sorted(it, key=lambda entry: entry.name)
            except OSError as exc:
                self.problem("%s: unreadable (%s)" % (prefix.rstrip("/") or rel, exc.strerror))
                return
            for entry in found:
                name = prefix + entry.name
                shown = name if rel == "." else rel + "/" + name
                if "\n" in name or "\r" in name:
                    self.problem("%r: a name with a line break cannot be listed" % shown)
                    continue
                try:
                    est = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    self.problem("%s: unreadable (%s)" % (shown, exc.strerror))
                    continue
                if stat.S_ISLNK(est.st_mode):
                    self.problem("%s: a link (links are refused)" % shown)
                elif stat.S_ISDIR(est.st_mode):
                    sub = self._open_at(dfd, entry.name, est, shown, os.O_DIRECTORY)
                    if sub is not None:
                        try:
                            walk(sub, name + "/")
                        finally:
                            os.close(sub)
                elif stat.S_ISREG(est.st_mode) and entry.name == FINDER_FILE:
                    continue  # Finder's folder settings: not part of a result
                elif stat.S_ISREG(est.st_mode):
                    fd = self._open_at(dfd, entry.name, est, shown, os.O_NONBLOCK)
                    if fd is not None:
                        try:
                            got = self._file_digest(fd, shown)
                        finally:
                            os.close(fd)
                        if got is not None:
                            rows.append((name.encode("utf-8", "surrogateescape"), got[0], got[1]))
                else:
                    self.problem("%s: neither a regular file nor a folder" % shown)

        try:
            walk(top, "")
        finally:
            os.close(top)
        if len(self.problems) != before:
            return None
        listing = b"".join(b"%s %d %s\n" % (digest.encode("ascii"), size, name)
                           for name, digest, size in sorted(rows))
        return len(rows), sha256(listing)

    def result(self, rel):
        """An experiment's result record: {path, sha256} for a file, {path, files, sha256} for a folder."""
        got = None if rel == "." else self._reach(rel)
        if got is not None:
            os.close(got[0])
        if rel == "." or (got is not None and stat.S_ISDIR(got[2].st_mode)):
            tree = self.tree(rel)
            return None if tree is None else {"path": rel, "files": tree[0], "sha256": tree[1]}
        digest = None if got is None else self.digest(rel)
        return None if digest is None else {"path": rel, "sha256": digest}

    def field(self, obj, dotted, rel, kind):
        """OBJ's field at a dotted path, which must have KIND (see typed)."""
        cur = obj
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                self.problem("%s: no field %s" % (rel, dotted))
                return None
            cur = cur[part]
        return self.typed(cur, kind, "%s: field %s" % (rel, dotted))

    def typed(self, value, kind, where):
        """VALUE, a value read from evidence, when it has KIND ('int', 'count' (an int, not negative), 'num' (a
        finite number), 'str', 'bool', 'optbool', list, dict); else None, with a problem saying WHERE it was read."""
        ok = {"int": is_int(value), "count": is_int(value) and value >= 0,
              "num": is_int(value) or (isinstance(value, float) and math.isfinite(value)),
              "str": isinstance(value, str), "bool": isinstance(value, bool),
              "optbool": value is None or isinstance(value, bool),
              list: isinstance(value, list), dict: isinstance(value, dict)}[kind]
        if not ok:
            self.problem("%s is %r, not %s" % (where, value, getattr(kind, "__name__", kind)))
            return None
        return value

    def first_token(self, rel, need=True):
        text = self.line(rel, need)
        if text is None:
            return None
        token = text.split()[0] if text.split() else ""
        if not HEX64.fullmatch(token):
            self.problem("%s: no SHA-256 at the start (%r)" % (rel, text[:80]))
            return None
        return token

    def image(self, rel, need=True):
        data = self.json(rel, need)
        if data is None:
            return None
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            self.problem("%s: not a single image inspection" % rel)
            return None
        digest = self.field(data[0], "configuration.descriptor.digest", rel, "str")
        if digest is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            self.problem("%s: image digest %r is not sha256:<hex>" % (rel, digest))
            return None
        return digest

    def binaries(self, need=True):
        """host/binaries.sha256 as {"build-<x>/<file>": digest}."""
        text = self.text("host/binaries.sha256", need)
        if text is None:
            return None
        out = {}
        for line in text.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
                self.problem("host/binaries.sha256: unrecognized line %r" % line[:100])
                return None
            out["/".join(parts[1].strip().split("/")[-2:])] = parts[0]
        return out

    def network(self, rel, need=True):
        """True when a network record shows no route and only the loopback interface."""
        text = self.text(rel, need)
        if text is None:
            return None
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines or not lines[0].startswith("Iface"):
            self.problem("%s: not a route table and interface list" % rel)
            return None
        routes = [l for l in lines[1:] if "\t" in l]
        interfaces = [l.strip() for l in lines[1:] if "\t" not in l]
        return not routes and interfaces == ["lo"]


def evidence_path(run_id):
    """The only evidence path a record with this id may carry."""
    return ".scratch/" + run_id


def evidence_field(run_id):
    return {"path": evidence_path(run_id), "where": EVIDENCE_WHERE}


def scratch_listing(ctx):
    """(whether .scratch exists, the set of names its listing gives). Evidence is found by a name that appears in
    this listing exactly, case included: a case-insensitive volume would open .scratch/Run-1 for a folder listed as
    run-1, and that folder is not the evidence of a record named Run-1. An unreadable .scratch lists nothing."""
    exists = os.path.lexists(ctx.scratch)
    try:
        names = set(os.listdir(ctx.scratch)) if os.path.isdir(ctx.scratch) else set()
    except OSError:
        names = set()
    return exists, names


def case_hint(names, name, where=".scratch"):
    """A note naming the entries of WHERE (whose listing is NAMES) that differ from NAME only in case or Unicode
    normalization, or ""."""
    fold = lambda n: unicodedata.normalize("NFC", n).casefold()
    near = sorted(n for n in names if n != name and fold(n) == fold(name))
    if not near:
        return ""
    return "; %s has %s, whose name differs only in case or Unicode normalization (names are matched exactly)" % (
        where, ", ".join(near))


def require_run_folder(ctx, run_id, what):
    """Refuse unless the listing of .scratch names RUN_ID exactly and it is a folder, not a link."""
    names = scratch_listing(ctx)[1]
    path = os.path.join(ctx.scratch, run_id)
    if run_id not in names or os.path.islink(path) or not os.path.isdir(path):
        raise Refusal("%s is not %s%s" % (ctx.show(path), what, case_hint(names, run_id)))


def read_header(ctx, ev, suite):
    """What both suites record alike: source, script, date and run-level failures."""
    info = SUITES[suite]
    head = {"failures": [], "finished": False, "stopped": False, "lines": [], "script_text": None,
            "source_commit": None, "script": None, "date": None}
    log = ev.text("host/driver.log")
    head["lines"] = log.splitlines() if log else []
    if head["lines"] and info["start"] not in head["lines"][0]:
        ev.problem("host/driver.log: the first line is not the start of a %s run: %r"
                   % (suite, head["lines"][0][:100]))
    commit = ev.line("host/commit.stdout")
    if commit is not None:
        if not HEX40.fullmatch(commit):
            ev.problem("host/commit.stdout: not a full commit hash (%r)" % commit[:60])
            commit = None
        else:
            staged = ev.line("staging/COMMIT", need=False)
            if staged is not None and staged != commit:
                ev.problem("staging/COMMIT names %s but host/commit.stdout names %s" % (staged, commit))
    if commit is not None:
        if not ctx.commit_exists(commit):
            ev.problem("source commit %s is not in this repository" % commit)
        else:
            head["source_commit"] = commit
            blob = ctx.blob(commit, info["script"])
            if blob is None:
                ev.problem(ctx.why_no_blob(commit, info["script"]))
            else:
                head["script"] = {"path": info["script"], "sha256": sha256(blob)}
                head["script_text"] = blob.decode("utf-8", "replace")
    done = ev.line("host/DONE", need=False)
    if done is None:
        head["failures"].append("host/DONE is missing: the run did not finish")
        stamps = [m.group(0) for l in head["lines"] for m in [TIMESTAMP.match(l)] if m]
        if stamps:
            head["date"] = utc(stamps[-1])
        else:
            ev.problem("date: host/DONE is missing and host/driver.log has no timestamp")
    else:
        m = re.fullmatch(r"(done|stopped) (\S+) failures=(\d+)(?:: (.*))?", done)
        if not m:
            ev.problem("host/DONE: unrecognized %r" % done[:100])
        else:
            head["date"] = utc(m.group(2))
            if head["date"] is None:
                ev.problem("host/DONE: %r is not a UTC time" % m.group(2))
            head["finished"] = m.group(1) == "done"
            head["stopped"] = m.group(1) == "stopped"
            if head["stopped"]:
                head["failures"].append("stopped: %s" % (m.group(4) or "no reason recorded"))
            if int(m.group(3)):
                head["failures"].append("host/DONE reports failures=%s" % m.group(3))
    for line in head["lines"]:
        rest = line.split(" ", 1)[1] if " " in line else line
        if rest.startswith(("FAILED: ", "STOP: ")):
            head["failures"].append("host/driver.log: " + rest)
    head["source_archive_sha256"] = ev.first_token("host/source.sha256", need=head["finished"])
    return head


def acceptance_expectations(ev, script_text):
    """The exit-record expectations acceptance.sh states, as (folder, name, value, label)."""
    m = re.search(r'^TEST_VARS="([^"]*)"', script_text, re.M)
    names = m.group(1).split() if m else []
    out = []
    pattern = r'expect "\$OUT/\$(b|d)/([A-Za-z0-9_.$-]+)\.exit" (\d+) "([^"]*)"'
    for m in re.finditer(pattern, script_text):
        folder = "build" if m.group(1) == "b" else "driver"
        values = names if "$var" in m.group(2) else [None]
        for var in values:
            sub = (lambda s: s.replace("$var", var)) if var else (lambda s: s)
            out.append((folder, sub(m.group(2)), int(m.group(3)), sub(m.group(4))))
    if not out or any("$" in name for _, name, _, _ in out):
        ev.problem("%s at the source commit: its expect lines could not be read"
                   % SUITES["acceptance"]["script"])
        return []
    return out


def explain_not_run(ev, head, p, steps):
    """The run's own reasons a platform's results are absent, or [] when it gives none."""
    why = []
    if head["stopped"] or not ev.exists("host/DONE"):
        why.append("the run did not finish")
    for step in steps:
        rc = ev.exit("host/%s.exit" % step, need=False)
        if rc not in (None, 0):
            why.append("host/%s.exit is %d" % (step, rc))
    for line in head["lines"]:
        if "FAILED: " in line and (p + ":" in line or "-" + p in line):
            why.append(line.split("FAILED: ", 1)[1])
    return why


def acceptance_platform(ctx, ev, head, p, machine, native, expectations, bins):
    fails = []
    result_rel = "driver-%s/evidence/RESULT.json" % p
    if not ev.exists(result_rel):
        why = explain_not_run(ev, head, p, ("build-" + p, "driver-" + p))
        if not why:
            ev.problem("%s: missing, and the run's records give no reason" % result_rel)
        return {"execution": None, "outcome": "failed", "failures": ["not run: " + "; ".join(why)]}
    res = ev.json(result_rel)
    if res is None:
        return {}
    if not isinstance(res, dict) or res.get("schema") != DRIVER_SCHEMA:
        ev.problem("%s: schema is not %s" % (result_rel, DRIVER_SCHEMA))
        return {}

    def get(dotted, kind):
        return ev.field(res, dotted, result_rel, kind)

    emulation = ev.line("driver-%s/emulation.txt" % p)
    got_machine = get("platform.machine", "str")
    if got_machine is not None and got_machine != machine:
        fails.append("%s: platform.machine is %s, not %s" % (result_rel, got_machine, machine))
    if emulation is None:
        execution = None
    elif "rosetta" in emulation.lower():
        execution = "emulated (Rosetta)"
    elif emulation == "none" and native == p:
        execution = "native"
    else:
        execution = "emulated"

    for rel in ("host/build-%s.exit" % p, "host/driver-%s.exit" % p,
                "driver-%s/driver.exit" % p, "driver-%s/driver-final.exit" % p):
        rc = ev.exit(rel)
        if rc not in (None, 0):
            fails.append("%s is %d" % (rel, rc))

    checks = {"passed": 0, "total": 0, "controls_fired": 0, "controls_total": 0}
    for folder, name, want, label in expectations:
        rel = "%s-%s/%s.exit" % (folder, p, name)
        got = ev.exit(rel)
        control = "control fired" in label
        checks["total"] += 1
        checks["controls_total"] += control
        if got == want:
            checks["passed"] += 1
            checks["controls_fired"] += control
        elif got is not None:
            fails.append("%s is %d, expected %d (%s)" % (rel, got, want, label.replace("$p", p)))

    selftest_text = ev.text("driver-%s/selftest.stdout" % p)
    self_test = None
    if selftest_text is not None:
        found = SELFTEST_LINE.findall(selftest_text)
        if not found:
            ev.problem("driver-%s/selftest.stdout: no self-test summary line" % p)
        else:
            n, passed, failed, skipped = (int(x) for x in found[-1])
            self_test = {"checks": n, "passed": passed, "failed": failed, "skipped": skipped}
            if failed or passed != n:
                fails.append("driver self-test: %d of %d passed" % (passed, n))

    cases = {k: get("counts.cases." + k, "int") for k in ("selected", "ran", "passed", "failed", "skipped")}
    variants = {k: get("counts.variants." + k, "int") for k in ("ran", "passed", "failed", "skipped")}
    check_counts = {k: get("counts.checks." + k, "int")
                    for k in ("passed", "failed_outside_controls", "failed_inside_controls")}
    controls = {"fired": get("counts.controls.fired", "int"), "total": get("counts.controls.total", "int")}
    driver_controls = {"fired": get("counts.driver_controls.fired", "int"),
                       "total": get("counts.driver_controls.total", "int")}
    if None not in cases.values():
        if cases["passed"] != cases["selected"] or cases["failed"] or cases["skipped"]:
            fails.append("cases: %d selected, %d passed, %d failed, %d skipped" % (
                cases["selected"], cases["passed"], cases["failed"], cases["skipped"]))
    if check_counts["failed_outside_controls"]:
        fails.append("%d checks failed outside control variants" % check_counts["failed_outside_controls"])
    if None not in controls.values() and controls["fired"] != controls["total"]:
        fails.append("sabotage controls: %d of %d fired" % (controls["fired"], controls["total"]))
    if None not in driver_controls.values() and driver_controls["fired"] != driver_controls["total"]:
        fails.append("driver controls: %d of %d fired" % (driver_controls["fired"], driver_controls["total"]))
    for name in ("failed_cases", "broken_checks", "controls_unassigned", "controls_never_fired"):
        items = get(name, list)
        if items:
            shown = [i if isinstance(i, str) else "%s %s/%s" % (i.get("status"), i.get("case") or "(any case)",
                                                                  i.get("sabotage") or i.get("name"))
                     for i in items if isinstance(i, str)
                     or ev.typed(i, dict, "%s: an item of %s" % (result_rel, name)) is not None]
            fails.append("%s: %s" % (name, ", ".join(str(s) for s in shown)))
    if get("exit", "int") not in (0, None):
        fails.append("%s: driver exit %d" % (result_rel, res["exit"]))
    if get("interrupted", "bool"):
        fails.append("%s: the driver was interrupted" % result_rel)

    gate = {"enabled": get("timing_gate.enabled", "bool"), "passed": get("timing_gate.passed", "optbool"),
            "threshold_ms": get("timing_gate.threshold_ms", "num"), "worst_ms": get("timing_gate.worst_ms", "num"),
            "protocol_passed": get("timing_gate.protocol.passed", "optbool"),
            "protocol_worst_ms": get("timing_gate.protocol.worst_ms", "num")}
    if gate["enabled"]:
        if gate["passed"] is not True or gate["protocol_passed"] is not True:
            fails.append("timing gate on and not passed (commands %s, protocol %s)"
                         % (gate["passed"], gate["protocol_passed"]))
    elif execution == "native":
        fails.append("timing gate off on a native run")

    e2e = {"case": E2E_CASE, "outcome": "absent", "checks_passed": 0, "checks_failed": 0}
    for case in get("cases", list) or []:
        if isinstance(case, dict) and case.get("id") == E2E_CASE:
            where = "%s: case %s" % (result_rel, E2E_CASE)
            release = [v for v in ev.typed(case.get("variants") or [], list, where + " variants") or []
                       if isinstance(v, dict) and v.get("binary") == "release"]
            count = lambda key: sum(ev.typed(v.get(key) or 0, "count", "%s %s" % (where, key)) or 0 for v in release)
            e2e = {"case": E2E_CASE, "outcome": case.get("outcome"),
                   "checks_passed": count("checks_passed"), "checks_failed": count("checks_failed")}
    if e2e["outcome"] != "pass" or e2e["checks_failed"] or not e2e["checks_passed"]:
        fails.append("%s: %s, %d checks passed and %d failed on the release binary"
                     % (E2E_CASE, e2e["outcome"], e2e["checks_passed"], e2e["checks_failed"]))

    digests = {}
    for kind, built in (("release", "stewart"), ("test", "stewart-test")):
        ran = get("binaries.%s.sha256" % kind, "str")
        given = get("binaries.%s.source_sha256" % kind, "str")
        digests[kind] = ran
        if ran is not None and given is not None and ran != given:
            fails.append("%s binary: the driver installed %s from a source with %s" % (kind, ran, given))
        if bins is not None and ran is not None:
            recorded = bins.get("build-%s/%s" % (p, built))
            if recorded != ran:
                fails.append("host/binaries.sha256 gives %s for build-%s/%s; the driver ran %s"
                             % (recorded, p, built, ran))

    rustc = ev.line("build-%s/toolchain.stdout" % p)
    return {
        "execution": execution,
        "outcome": "failed" if fails else "qualified",
        "failures": fails,
        "toolchain_image": ev.image("host/toolchain-inspect-%s.stdout" % p),
        "rustc": rustc.splitlines()[0] if rustc else None,
        "script_checks": checks,
        "self_test": self_test,
        "cases": cases,
        "variants": variants,
        "checks": check_counts,
        "controls": controls,
        "driver_controls": driver_controls,
        "timing_gate": gate,
        "e2e": e2e,
        "release_sha256": digests["release"],
        "test_sha256": digests["test"],
        "result_sha256": ev.digest(result_rel),
    }


def extract_acceptance(ctx, ev):
    head = read_header(ctx, ev, "acceptance")
    native = None
    if head["lines"]:
        m = re.search(r"native architecture (\S+)", head["lines"][0])
        if m:
            native = m.group(1)
        else:
            ev.problem("host/driver.log: the start line names no native architecture")
    expectations = acceptance_expectations(ev, head["script_text"]) if head["script_text"] else []
    bins = ev.binaries(need=head["finished"])
    platforms = {}
    for p, key, machine in PLATFORMS:
        platforms[key] = acceptance_platform(ctx, ev, head, p, machine, native, expectations, bins)
    extra = {"python_image": ev.image("host/python-inspect.stdout", need=head["finished"])}
    return suite_entry(ev, head, "acceptance", platforms, extra)


def toolchain_platform(ctx, ev, head, p, steps, bins):
    fails = []
    rc = ev.exit("host/toolchain-%s.exit" % p, need=head["finished"])
    if rc not in (None, 0):
        fails.append("host/toolchain-%s.exit is %d" % (p, rc))
    builds = []
    for i in (1, 2):
        name = "build-%s-%d" % (p, i)
        if not ev.exists(name):
            why = explain_not_run(ev, head, p, (name,))
            if not why:
                ev.problem("%s: missing, and the run's records give no reason" % name)
            fails.append("%s not run: %s" % (name, "; ".join(why)))
            builds.append({"name": name, "steps_passed": 0, "steps_total": len(steps), "static": None,
                           "run_exit": None, "offline": None, "sha256": None})
            continue
        host_rc = ev.exit("host/%s.exit" % name)
        if host_rc not in (None, 0):
            fails.append("host/%s.exit is %d" % (name, host_rc))
        complete = host_rc == 0
        passed = 0
        for step in steps:
            src = ev.exit("%s/%s.exit" % (name, step), need=complete)
            if src == 0:
                passed += 1
            elif src is not None:
                fails.append("%s/%s.exit is %d" % (name, step, src))
                break
        if passed != len(steps):
            fails.append("%s: %d of %d steps passed" % (name, passed, len(steps)))
        offline = ev.network("%s/network.stdout" % name, need=complete)
        if offline is False:
            fails.append("%s/network.stdout shows a route or an interface besides lo" % name)
        static = ev.exit("%s/static.exit" % name, need=complete)
        builds.append({"name": name, "steps_passed": passed, "steps_total": len(steps),
                       "static": None if static is None else static == 0,
                       "run_exit": ev.exit("%s/run.exit" % name, need=complete), "offline": offline,
                       "sha256": ev.first_token("%s/sha256.stdout" % name, need=complete)})
        if bins is not None and builds[-1]["sha256"] is not None:
            recorded = bins.get("%s/stewart" % name)
            if recorded != builds[-1]["sha256"]:
                fails.append("host/binaries.sha256 gives %s for %s/stewart; its own record gives %s"
                             % (recorded, name, builds[-1]["sha256"]))
    digests = {b["sha256"] for b in builds}
    marker = ev.line("host/reproducible-%s" % p, need=head["finished"])
    reproducible = marker == "same" and len(digests) == 1 and None not in digests
    if not reproducible:
        fails.append("reproducible-%s: marker %r, build digests %s" % (p, marker, sorted(map(str, digests))))
    alpine = ev.exit("host/alpine-run-%s.exit" % p, need=head["finished"])
    if alpine not in (None, 0):
        fails.append("host/alpine-run-%s.exit is %d" % (p, alpine))
    versions = set()
    for b in builds:
        if ev.exists(b["name"]):
            text = ev.line("%s/toolchain.stdout" % b["name"], need=b["steps_passed"] > 0)
            if text:
                versions.add(text.splitlines()[0])
    if len(versions) > 1:
        fails.append("the two builds report different toolchains: %s" % sorted(versions))
    return {
        "execution": None,
        "outcome": "failed" if fails else "qualified",
        "failures": fails,
        "toolchain_image": ev.image("host/toolchain-inspect-%s.stdout" % p, need=head["finished"]),
        "rustc": sorted(versions)[0] if versions else None,
        "builds": builds,
        "reproducible": reproducible,
        "release_sha256": next(iter(digests)) if reproducible else None,
        "alpine_run_exit": alpine,
    }


def extract_toolchain(ctx, ev):
    head = read_header(ctx, ev, "toolchain")
    steps = []
    if head["source_commit"]:
        inner = ctx.blob(head["source_commit"], SUITES["toolchain"]["inner"])
        if inner is None:
            ev.problem(ctx.why_no_blob(head["source_commit"], SUITES["toolchain"]["inner"]))
        else:
            steps = re.findall(r"^step ([A-Za-z0-9_-]+) ", inner.decode("utf-8", "replace"), re.M)
            if not steps:
                ev.problem("%s at %s: no step lines" % (SUITES["toolchain"]["inner"], head["source_commit"]))
    bins = ev.binaries(need=head["finished"])
    platforms = {}
    for p, key, _machine in PLATFORMS:
        platforms[key] = toolchain_platform(ctx, ev, head, p, steps, bins)
    listing = ev.bytes("host/vendor.sha256", need=head["finished"])
    vendor_rc = ev.exit("host/vendor.exit", need=head["finished"])
    if vendor_rc not in (None, 0):
        head["failures"].append("host/vendor.exit is %d" % vendor_rc)
    extra = {"vendor": None if listing is None else {
        "files": sum(1 for l in listing.decode("utf-8", "replace").splitlines() if l.strip()),
        "listing_sha256": sha256(listing)}}
    return suite_entry(ev, head, "toolchain", platforms, extra)


def suite_entry(ev, head, suite, platforms, extra):
    failed = head["failures"] or any(pl.get("outcome") != "qualified" for pl in platforms.values())
    entry = {
        "id": ev.id,
        "kind": "suite",
        "suite": suite,
        "script": head["script"],
        "source_commit": head["source_commit"],
        "source_archive_sha256": head["source_archive_sha256"],
        "date": head["date"],
        "outcome": "failed" if failed else "qualified",
        "failures": list(head["failures"]),
    }
    entry.update(extra)
    entry.update({"platforms": platforms, "evidence": evidence_field(ev.id), "pin": None})
    return entry


def extract_suite(ctx, run_id, suite):
    require_run_folder(ctx, run_id, "a run folder")
    ev = Evidence(ctx, run_id)
    entry = (extract_acceptance if suite == "acceptance" else extract_toolchain)(ctx, ev)
    if ev.problems:
        raise ExtractError(run_id, ev.problems)
    return entry


def clean_rel(rel):
    """REL as a normalized "/"-separated path inside a folder ("." for the folder itself), or None if it leaves."""
    if not isinstance(rel, str) or not rel or "\0" in rel:
        return None
    rel = posixpath.normpath(rel)
    if rel.startswith("/") or ".." in rel.split("/"):
        return None
    return rel


def date_file(date_from):
    """The file a recorded date_from names ("<file> field <key>"), or None for DONE or anything else."""
    m = DATE_FROM.fullmatch(date_from) if isinstance(date_from, str) else None
    return m.group(1) if m else None


def experiment_entry(ctx, run_id, result_rel, summary, date_rel=None):
    """An experiment's record. Its date comes from DONE when that holds a time, else from the at, ended_at or
    finished_at field of DATE_REL, a JSON file in the folder (by default the result, when it is a JSON file)."""
    require_run_folder(ctx, run_id, "an experiment folder")
    ev = Evidence(ctx, run_id)
    for what, rel in (("result", result_rel), ("date file", date_rel)):
        if rel is not None and clean_rel(rel) != rel:
            raise Refusal("%s %r is not a normalized path inside %s" % (what, rel, ctx.show(ev.dir)))
    result = ev.result(result_rel)
    date, source = None, None
    done = ev.text("DONE", need=False)
    if done:
        m = TIMESTAMP.search(done)
        if m:
            date, source = utc(m.group(0)), "DONE"
    if date_rel is None and result is not None and "files" not in result and result_rel.endswith(".json"):
        date_rel = result_rel
    if date is None and date_rel is not None:
        data = ev.json(date_rel)
        if isinstance(data, dict):
            for key in DATE_KEYS:
                if isinstance(data.get(key), str) and utc(data[key]):
                    date, source = utc(data[key]), "%s field %s" % (date_rel, key)
                    break
    if date is None:
        if date_rel is None:
            ev.problem("date: DONE records no UTC time and no JSON file names one; name one with --date-from")
        else:
            ev.problem("date: neither DONE nor %s (field %s) records a UTC time" % (date_rel, ", ".join(DATE_KEYS)))
    if ev.problems:
        raise ExtractError(run_id, ev.problems)
    return {"id": run_id, "kind": "experiment", "date": date, "date_from": source, "summary": summary,
            "result": result, "evidence": evidence_field(run_id), "pin": None}


# ---------------------------------------------------------------- the record

def empty_record():
    return {"schema": SCHEMA, "entries": []}


def nesting_depth(value):
    """How deeply VALUE nests arrays and objects (0 for a scalar), counted without recursion and only until it
    passes MAX_DEPTH."""
    deepest, stack = 0, [(value, 1)]
    while stack and deepest <= MAX_DEPTH:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            deepest = max(deepest, depth)
            stack.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
    return deepest


def _what(value):
    """The kind of a decoded JSON value, for a message."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true or false"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    return "an array" if isinstance(value, list) else "an object"


# Field checks: each is called as check(value, where, probs) and appends a problem for each way VALUE is wrong.
# Together they cover every field that render, check, candidates and the commands read, with the kind of value
# they need, so a record that passes record_problems cannot make them fail with a traceback.

def _want(test, what):
    """A check that TEST(value) holds; WHAT says what the value must be."""
    def check(value, where, probs):
        if not test(value):
            probs.append("%s must be %s (it is %s)" % (where, what, _what(value)))
    return check


def _fields(value, spec, where, probs, checked_elsewhere=()):
    """Check that VALUE is an object with exactly SPEC's fields, each passing SPEC's check for it (None: checked by
    the caller). A field in CHECKED_ELSEWHERE is not reported here when it is missing."""
    if not isinstance(value, dict):
        probs.append("%s must be an object (it is %s)" % (where, _what(value)))
        return
    missing = [k for k in spec if k not in value and k not in checked_elsewhere]
    extra = sorted(k for k in value if k not in spec)
    if missing:
        probs.append("%s lacks %s" % (where, ", ".join(missing)))
    if extra:
        probs.append("%s has %s, which %s does not define" % (where, ", ".join(json.dumps(k) for k in extra), SCHEMA))
    for key, check in spec.items():
        if key in value and check is not None:
            check(value[key], "%s.%s" % (where, key), probs)


def _object(spec, nullable=False):
    def check(value, where, probs):
        if value is None and nullable:
            return
        _fields(value, spec, where, probs)
    return check


def _array(item_check):
    def check(value, where, probs):
        if not isinstance(value, list):
            probs.append("%s must be an array (it is %s)" % (where, _what(value)))
            return
        for i, item in enumerate(value):
            item_check(item, "%s[%d]" % (where, i), probs)
    return check


def _is_sha(value):
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


_STR = _want(lambda v: isinstance(v, str), "a string")
_OPT_STR = _want(lambda v: v is None or isinstance(v, str), "a string or null")
_OPT_SHA = _want(lambda v: v is None or _is_sha(v), "a SHA-256 in hex, or null")
_SHA = _want(_is_sha, "a SHA-256 in hex")
_INT = _want(is_int, "an integer")
_OPT_INT = _want(lambda v: v is None or is_int(v), "an integer or null")
_NUM = _want(lambda v: is_int(v) or isinstance(v, float), "a number")
_OPT_NUM = _want(lambda v: v is None or is_int(v) or isinstance(v, float), "a number or null")
_BOOL = _want(lambda v: isinstance(v, bool), "true or false")
_OPT_BOOL = _want(lambda v: v is None or isinstance(v, bool), "true, false or null")
_SCALAR = _want(lambda v: v is None or isinstance(v, (str, int, float)), "a string, number, true, false or null")
_OUTCOME = _want(lambda v: v in ("qualified", "failed"), '"qualified" or "failed"')
_FAILURES = _array(_STR)


def _counts(*keys):
    return _object({k: _OPT_INT for k in keys})


# A platform of an acceptance run whose results are absent records only why; otherwise it records everything.
ACCEPTANCE_NOT_RUN = {"execution": _OPT_STR, "outcome": _OUTCOME, "failures": _FAILURES}
ACCEPTANCE_PLATFORM = dict(ACCEPTANCE_NOT_RUN, **{
    "toolchain_image": _OPT_STR, "rustc": _OPT_STR,
    "script_checks": _counts("passed", "total", "controls_fired", "controls_total"),
    "self_test": _object({k: _OPT_INT for k in ("checks", "passed", "failed", "skipped")}, nullable=True),
    "cases": _counts("selected", "ran", "passed", "failed", "skipped"),
    "variants": _counts("ran", "passed", "failed", "skipped"),
    "checks": _counts("passed", "failed_outside_controls", "failed_inside_controls"),
    "controls": _counts("fired", "total"),
    "driver_controls": _counts("fired", "total"),
    "timing_gate": _object({"enabled": _OPT_BOOL, "passed": _OPT_BOOL, "threshold_ms": _OPT_NUM,
                            "worst_ms": _OPT_NUM, "protocol_passed": _OPT_BOOL, "protocol_worst_ms": _OPT_NUM}),
    "e2e": _object({"case": _STR, "outcome": _SCALAR, "checks_passed": _NUM, "checks_failed": _NUM}),
    "release_sha256": _OPT_STR, "test_sha256": _OPT_STR, "result_sha256": _OPT_SHA,
})
TOOLCHAIN_PLATFORM = dict(ACCEPTANCE_NOT_RUN, **{
    "toolchain_image": _OPT_STR, "rustc": _OPT_STR,
    "builds": _array(_object({
        "name": _want(lambda v: isinstance(v, str) and BUILD_NAME.fullmatch(v) is not None,
                      "a folder name (letters, digits, '.', '_' and '-')"),
        "steps_passed": _INT, "steps_total": _INT, "static": _OPT_BOOL, "run_exit": _OPT_INT,
        "offline": _OPT_BOOL, "sha256": _OPT_SHA})),
    "reproducible": _BOOL, "release_sha256": _OPT_SHA, "alpine_run_exit": _OPT_INT,
})


def _platforms(suite):
    def check(value, where, probs):
        if not isinstance(value, dict) or not value:
            probs.append("%s must be an object with at least one platform (it is %s)"
                         % (where, "empty" if value == {} else _what(value)))
            return
        for key, pl in value.items():
            if key not in [p[1] for p in PLATFORMS]:
                probs.append("%s has %s, which is not a platform (%s)" % (where, json.dumps(key),
                                                                          ", ".join(p[1] for p in PLATFORMS)))
                continue
            if suite == "toolchain":
                spec = TOOLCHAIN_PLATFORM
            elif isinstance(pl, dict) and set(pl) <= set(ACCEPTANCE_NOT_RUN):
                spec = ACCEPTANCE_NOT_RUN
            else:
                spec = ACCEPTANCE_PLATFORM
            _fields(pl, spec, "%s.%s" % (where, key), probs)
    return check


def suite_fields(suite):
    """The fields of a suite record (None: checked by record_problems itself)."""
    spec = {"id": None, "kind": None, "suite": None, "date": None, "evidence": None, "pin": None,
            "script": _object({"path": _want(lambda v: v == SUITES[suite]["script"],
                                             json.dumps(SUITES[suite]["script"])),
                               "sha256": _SHA}),
            "source_commit": _want(lambda v: isinstance(v, str) and HEX40.fullmatch(v) is not None,
                                   "a full commit hash"),
            "source_archive_sha256": _OPT_SHA, "outcome": _OUTCOME, "failures": _FAILURES,
            "platforms": _platforms(suite)}
    if suite == "acceptance":
        spec["python_image"] = _OPT_STR
    else:
        spec["vendor"] = _object({"files": _want(lambda v: is_int(v) and v >= 0, "a count"), "listing_sha256": _SHA},
                                 nullable=True)
    return spec


EXPERIMENT_FIELDS = dict.fromkeys(("id", "kind", "date", "date_from", "summary", "result", "evidence", "pin"))


def record_problems(record):
    """Ways RECORD does not follow stewart.qualified/1. Every field that render, check, candidates and the commands
    read must be present with the kind of value they need, and an entry, platform or nested object has exactly its
    schema's fields, so a malformed record gets a reason here rather than a traceback later."""
    if nesting_depth(record) > MAX_DEPTH:
        return ["the record nests arrays and objects more than %d deep" % MAX_DEPTH]
    try:
        dump_json(record).encode("utf-8")
    except UnicodeEncodeError:
        return ["a string in the record is not Unicode text (it has a lone surrogate), so it cannot be "
                "printed or written as UTF-8"]
    probs = []
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return ["the record is not %s" % SCHEMA]
    entries = record.get("entries")
    if not isinstance(entries, list):
        return ["entries is not a list"]
    seen = set()
    for i, e in enumerate(entries):
        where = "entries[%d]" % i
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            probs.append("%s: no id" % where)
            continue
        where = e["id"]
        if e["id"] in seen:
            probs.append("%s: repeated id" % where)
        seen.add(e["id"])
        if not RUN_ID.fullmatch(e["id"]):
            probs.append("%s: id is not a .scratch folder name (letters, digits, '.', '_' and '-', not starting "
                         "with a dot)" % where)
        # check finds the evidence at this path, so it must be the id's own folder and nothing else.
        evidence = e.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"path", "where"} \
                or not isinstance(evidence.get("where"), str):
            probs.append("%s: evidence is not {path, where}" % where)
        elif evidence.get("path") != evidence_path(e["id"]):
            probs.append("%s: evidence.path is %s, not %s; the record's id and its evidence must agree"
                         % (where, json.dumps(evidence.get("path")), json.dumps(evidence_path(e["id"]))))
        if not isinstance(e.get("date"), str) or utc(e["date"]) != e["date"]:
            probs.append("%s: date is not YYYY-MM-DDTHH:MM:SSZ" % where)
        pin = e.get("pin")
        if pin is not None and not (isinstance(pin, dict) and set(pin) == {"reason", "until"}
                                    and all(isinstance(v, str) and v.strip() for v in pin.values())):
            probs.append("%s: pin is not {reason, until}" % where)
        if e.get("kind") == "suite":
            if not isinstance(e.get("suite"), str) or e["suite"] not in SUITES:
                probs.append("%s: suite must be one of %s (it is %s)" % (where, ", ".join(sorted(SUITES)),
                                                                         json.dumps(e.get("suite"))))
            else:
                _fields(e, suite_fields(e["suite"]), where, probs,
                        checked_elsewhere=("id", "kind", "suite", "date", "evidence"))
        elif e.get("kind") == "experiment":
            _fields(e, EXPERIMENT_FIELDS, where, probs,
                    checked_elsewhere=tuple(k for k in EXPERIMENT_FIELDS if k != "pin"))
            if pin is None:
                probs.append("%s: an experiment record must be pinned" % where)
            result = e.get("result")
            if not isinstance(result, dict):
                probs.append("%s: no result" % where)
            elif set(result) not in ({"path", "sha256"}, {"path", "files", "sha256"}) \
                    or not isinstance(result.get("path"), str) or clean_rel(result["path"]) != result["path"] \
                    or not isinstance(result.get("sha256"), str) or not HEX64.fullmatch(result["sha256"]) \
                    or ("files" in result and not (is_int(result["files"]) and result["files"] >= 0)):
                probs.append("%s: result is not {path, sha256} or {path, files, sha256} with a normalized path "
                             "inside the folder" % where)
            if not isinstance(e.get("summary"), str):
                probs.append("%s: no summary" % where)
            date_from = e.get("date_from")
            if date_from != "DONE" and clean_rel(date_file(date_from)) in (None, "."):
                probs.append("%s: date_from is not DONE or \"<file> field <%s>\"" % (where, "|".join(DATE_KEYS)))
            elif date_from != "DONE" and clean_rel(date_file(date_from)) != date_file(date_from):
                probs.append("%s: date_from names a path that is not normalized" % where)
        else:
            probs.append("%s: kind is not suite or experiment" % where)
    return probs


def load_record(ctx, missing_ok=False):
    data = read_regular(ctx.record, ctx.show(ctx.record))
    if data is None:
        if missing_ok:
            return empty_record()
        raise Refusal("%s does not exist; create it with extract or pin --experiment" % ctx.show(ctx.record))
    try:
        record = parse_json(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Refusal("%s is not valid JSON: %s" % (ctx.show(ctx.record), exc))
    probs = record_problems(record)
    if probs:
        raise Refusal("%s does not follow %s:\n%s" % (ctx.show(ctx.record), SCHEMA,
                                                      "\n".join("  - " + p for p in probs)))
    return record


def sort_entries(entries):
    return sorted(entries, key=lambda e: (e["kind"] != "suite", e.get("suite") or "", e["date"], e["id"]))


def dump_json(record):
    return json.dumps(record, indent=2, ensure_ascii=False) + "\n"


def _kind(mode):
    if stat.S_ISLNK(mode):
        return "a link"
    if stat.S_ISDIR(mode):
        return "a folder"
    if stat.S_ISFIFO(mode):
        return "a FIFO"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "a device"
    return "not a regular file"


def open_target(path, shown=None, verb="write"):
    """(folder descriptor, lstat of PATH or None) for writing PATH, or for reading it when VERB is "read". Refuses
    when PATH's folder is a link or not a folder, or PATH exists and is anything but a regular file with one name:
    a symbolic or hard link could point the write at a file elsewhere, or make a read take another file's bytes as
    the record's, and a FIFO or device could block. The caller closes the descriptor."""
    shown = shown or path
    parent = os.path.dirname(path) or "."
    try:
        pst = os.lstat(parent)
    except OSError as exc:
        raise Refusal("refusing to %s %s: its folder cannot be read (%s)" % (verb, shown, exc.strerror))
    if not stat.S_ISDIR(pst.st_mode):
        raise Refusal("refusing to %s %s: its folder %s is %s; links are not followed"
                      % (verb, shown, parent, _kind(pst.st_mode)))
    try:
        dfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | O_CLOEXEC)
    except OSError as exc:
        raise Refusal("refusing to %s %s: its folder cannot be opened without following a link (%s)"
                      % (verb, shown, exc.strerror))
    try:
        fst = os.fstat(dfd)
        if (fst.st_dev, fst.st_ino) != (pst.st_dev, pst.st_ino):
            raise Refusal("refusing to %s %s: its folder changed while it was opened" % (verb, shown))
        try:
            st = os.stat(os.path.basename(path), dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            st = None
        except OSError as exc:
            raise Refusal("refusing to %s %s: it cannot be examined (%s)" % (verb, shown, exc.strerror))
        if st is not None and not stat.S_ISREG(st.st_mode):
            raise Refusal("refusing to %s %s: it is %s; only a regular file or an absent one is %s, and links are "
                          "not followed" % (verb, shown, _kind(st.st_mode), "read" if verb == "read" else "written"))
        if st is not None and st.st_nlink != 1:
            raise Refusal("refusing to %s %s: it has %d names (a hard link); %s" % (
                verb, shown, st.st_nlink, "its bytes may be another file's" if verb == "read"
                else "writing it would change the file under its other names too"))
    except BaseException:
        os.close(dfd)
        raise
    return dfd, st


def read_regular(path, shown=None):
    """PATH's bytes, or None when it is absent. PATH is read under the rules it is written under (open_target):
    its folder must be a real folder and PATH a regular file with one name, opened through the folder's descriptor
    without following a link and without blocking, and still the file that was examined."""
    shown = shown or path
    if not os.path.lexists(os.path.dirname(path) or "."):
        return None  # no folder, so no file; a link in the folder's place is refused by open_target
    dfd, st = open_target(path, shown, "read")
    try:
        if st is None:
            return None
        try:
            fd = os.open(os.path.basename(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | O_CLOEXEC, dir_fd=dfd)
        except OSError as exc:
            raise Refusal("refusing to read %s: %s (it may have changed since it was examined)" % (shown, exc.strerror))
        try:
            fst = os.fstat(fd)
            if not stat.S_ISREG(fst.st_mode) or fst.st_nlink != 1 or \
                    (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
                raise Refusal("refusing to read %s: it changed while it was opened" % shown)
            return read_fd(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise Refusal("refusing to read %s: %s" % (shown, exc.strerror))
    finally:
        os.close(dfd)


def write_if_changed(path, text, shown=None):
    """Write TEXT to PATH unless PATH already holds it; return whether it wrote. Never follows a link: see
    open_target for what is refused. The file is opened through its folder's descriptor with O_NOFOLLOW, and
    without O_TRUNC: it is truncated only once it is shown to be still the one regular file with one name."""
    shown = shown or path
    data = text.encode("utf-8")
    name = os.path.basename(path)
    dfd, st = open_target(path, shown)
    try:
        flags = os.O_NOFOLLOW | os.O_NONBLOCK | O_CLOEXEC
        if st is not None:
            fd = os.open(name, os.O_RDONLY | flags, dir_fd=dfd)
            try:
                fst = os.fstat(fd)
                if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
                    raise Refusal("refusing to write %s: it changed while it was read" % shown)
                if read_fd(fd) == data:
                    return False
            finally:
                os.close(fd)
            flags |= os.O_WRONLY
        else:
            flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(name, flags, 0o666, dir_fd=dfd)
        try:
            fst = os.fstat(fd)
            if not stat.S_ISREG(fst.st_mode) or fst.st_nlink != 1 or \
                    (st is not None and (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino)):
                raise Refusal("refusing to write %s: it changed while it was opened" % shown)
            os.ftruncate(fd, 0)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
    except OSError as exc:
        # O_NOFOLLOW turns a link that appeared since open_target looked into an error here, never a write.
        raise Refusal("refusing to write %s: %s (it may have changed since it was examined)"
                      % (shown, exc.strerror))
    finally:
        os.close(dfd)
    return True


def save(ctx, record, out):
    record["entries"] = sort_entries(record["entries"])
    probs = record_problems(record)
    if probs:
        raise Refusal("refusing to write a record that does not follow %s:\n%s"
                      % (SCHEMA, "\n".join("  - " + p for p in probs)))
    # Refuse before writing either file, so a refused Markdown target cannot leave a JSON without its render.
    for path in (ctx.record, ctx.markdown):
        os.close(open_target(path, ctx.show(path))[0])
    for path, text in ((ctx.record, dump_json(record)), (ctx.markdown, render(record))):
        out("%s %s" % ("wrote" if write_if_changed(path, text, ctx.show(path)) else "unchanged:", ctx.show(path)))


def front(entries):
    """{id: [why]}: per (suite, platform), the latest run, and the latest qualified run behind a failed one."""
    groups = {}
    for e in entries:
        if e["kind"] == "suite":
            for platform in e["platforms"]:
                groups.setdefault((e["suite"], platform), []).append(e)
    keep = {}
    for (suite, platform), runs in sorted(groups.items()):
        runs.sort(key=lambda e: (e["date"], e["id"]))
        latest = runs[-1]
        keep.setdefault(latest["id"], []).append("%s %s: latest" % (suite, platform))
        if latest["outcome"] != "qualified":
            good = [e for e in runs if e["outcome"] == "qualified"]
            if good:
                keep.setdefault(good[-1]["id"], []).append("%s %s: latest qualified" % (suite, platform))
    return keep


def apply_front(record, out):
    """Drop every entry that is neither on the front nor pinned; report what leaves."""
    keep = front(record["entries"])
    kept, dropped = [], []
    for e in record["entries"]:
        (kept if e["id"] in keep or e.get("pin") else dropped).append(e)
    record["entries"] = kept
    for e in dropped:
        out("dropped %s (%s, %s, %s): neither on the front nor pinned; Git history keeps its earlier record"
            % (e["id"], e.get("suite") or e["kind"], e["date"], e.get("outcome", "experiment")))
    if not dropped:
        out("dropped: none")
    return [e["id"] for e in dropped]


def print_pins(record, out):
    pins = [e for e in record["entries"] if e.get("pin")]
    if not pins:
        out("pins: none")
        return
    out("pins (reconsider each; release one with `unpin ID` once its condition holds):")
    for e in pins:
        out("  %s (%s, %s): %s; until %s" % (e["id"], e.get("suite") or e["kind"], e["date"][:10],
                                             e["pin"]["reason"], e["pin"]["until"]))


def print_front(record, out):
    keep = front(record["entries"])
    if not keep:
        out("front: empty")
    for run_id in sorted(keep):
        out("front: %s (%s)" % (run_id, "; ".join(keep[run_id])))


# ---------------------------------------------------------------- rendering

def cell(value):
    if value is None:
        return "not recorded"
    return str(value).replace("|", "\\|")


def ratio(d, a, b):
    if not d or d.get(a) is None or d.get(b) is None:
        return "not recorded"
    return "%s/%s" % (d[a], d[b])


def code(value):
    return "not recorded" if value is None else "`%s`" % value


def yes_no(value):
    return "not recorded" if value is None else ("yes" if value else "no")


def render_platform_rows(e):
    keys = [p[1] for p in PLATFORMS if p[1] in e["platforms"]]
    pls = [e["platforms"][k] for k in keys]
    rows = [("Execution", [cell(pl.get("execution")) if pl.get("execution") or e["suite"] == "acceptance"
                           else "not recorded by the suite" for pl in pls]),
            ("Outcome", ["**%s**" % pl.get("outcome") for pl in pls]),
            ("Failures", ["; ".join(cell(f) for f in pl.get("failures") or []) or "none" for pl in pls]),
            ("Toolchain image", [code(pl.get("toolchain_image")) for pl in pls]),
            ("rustc", [cell(pl.get("rustc")) for pl in pls])]
    if e["suite"] == "acceptance":
        def gate(pl):
            g = pl.get("timing_gate") or {}
            if g.get("enabled"):
                head = "on, %s" % ("passed" if g.get("passed") and g.get("protocol_passed") else "not passed")
            else:
                head = "off (reported, not gated)"
            return "%s: worst %s ms; protocol worst %s ms; threshold %s ms" % (
                head, cell(g.get("worst_ms")), cell(g.get("protocol_worst_ms")), cell(g.get("threshold_ms")))

        def counts(pl, key, order):
            d = pl.get(key) or {}
            return ", ".join("%s %s" % (k.replace("_", " "), cell(d.get(k))) for k in order) if d else "not recorded"

        def e2e(pl):
            x = pl.get("e2e")
            if not x:
                return "not recorded"
            return "%s, %s/%s checks" % (x["outcome"], x["checks_passed"], x["checks_passed"] + x["checks_failed"])

        rows += [
            ("Script checks (exit records)", ["%s, controls %s" % (ratio(pl.get("script_checks"), "passed", "total"),
                                                                   ratio(pl.get("script_checks"), "controls_fired",
                                                                         "controls_total")) for pl in pls]),
            ("Driver self-test", [ratio(pl.get("self_test"), "passed", "checks") for pl in pls]),
            ("Cases passed", [ratio(pl.get("cases"), "passed", "selected") for pl in pls]),
            ("Cases", [counts(pl, "cases", ("selected", "ran", "passed", "failed", "skipped")) for pl in pls]),
            ("Variants (a fired control's variant fails)",
             [counts(pl, "variants", ("ran", "passed", "failed", "skipped")) for pl in pls]),
            ("Checks", [counts(pl, "checks", ("passed", "failed_outside_controls", "failed_inside_controls"))
                        for pl in pls]),
            ("Sabotage controls fired", [ratio(pl.get("controls"), "fired", "total") for pl in pls]),
            ("Driver controls fired", [ratio(pl.get("driver_controls"), "fired", "total") for pl in pls]),
            ("Timing gate", [gate(pl) for pl in pls]),
            ("End to end (`%s`)" % E2E_CASE, [e2e(pl) for pl in pls]),
            ("Release binary SHA-256", [code(pl.get("release_sha256")) for pl in pls]),
            ("Test binary SHA-256", [code(pl.get("test_sha256")) for pl in pls]),
            ("RESULT.json SHA-256", [code(pl.get("result_sha256")) for pl in pls]),
        ]
    else:
        def build(pl, i):
            bs = pl.get("builds") or []
            if i >= len(bs):
                return "not recorded"
            b = bs[i]
            return "`%s`: %s/%s steps; static %s; offline %s; run exit %s; %s" % (
                b["name"], b["steps_passed"], b["steps_total"], yes_no(b["static"]),
                yes_no(b["offline"]), cell(b["run_exit"]), code(b["sha256"]))

        rows += [
            ("Build 1", [build(pl, 0) for pl in pls]),
            ("Build 2", [build(pl, 1) for pl in pls]),
            ("Reproducible", ["yes" if pl.get("reproducible") else "no" for pl in pls]),
            ("Binary SHA-256 (both builds)", [code(pl.get("release_sha256")) for pl in pls]),
            ("Alpine run exit", [cell(pl.get("alpine_run_exit")) for pl in pls]),
        ]
    lines = ["| | %s |" % " | ".join(keys), "| --- |%s" % (" --- |" * len(keys))]
    lines += ["| %s | %s |" % (label, " | ".join(vals)) for label, vals in rows]
    return lines


def render(record):
    entries = record["entries"]
    keep = front(entries)
    L = ["<!-- Generated by apparatus/qualified.py from qualified.json. Do not edit by hand: "
         "run `python3 -I -B apparatus/qualified.py render`. -->",
         "",
         "# Qualified behavior",
         "",
         "Generated from [qualified.json](qualified.json) by [qualified.py](qualified.py);",
         "`python3 -I -B apparatus/qualified.py check` fails when this file differs from",
         "a fresh render or a record no longer matches its local evidence.",
         "",
         "For each suite and platform the record keeps the latest run and, when that",
         "run did not qualify, the latest run that did (the front). Any other record",
         "stays only while pinned, with a reason and a condition for its release; Git",
         "history keeps the records that left. Every value is read from the run's own",
         "evidence, and the outcome is decided mechanically from it. A run qualifies the",
         "source commit it archived and the binaries whose digests it recorded; it says",
         "nothing about later source, which `check` reports as drift. Evidence paths name",
         "`.scratch/` folders that exist only on the machine that made them; clones do",
         "not carry them.",
         "",
         "## Front",
         ""]
    rows = []
    for e in entries:
        for why in keep.get(e["id"], []):
            suite_platform, reason = why.split(": ", 1)
            suite, platform = suite_platform.split(" ", 1)
            rows.append((suite, platform, reason != "latest", e, reason))
    if rows:
        L += ["| Suite | Platform | Run | Finished (UTC) | Source | Outcome | On the front as |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for suite, platform, _, e, reason in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
            here = e["platforms"][platform].get("outcome")
            outcome = e["outcome"] if here == e["outcome"] else "%s (this platform: %s)" % (e["outcome"], here)
            L.append("| %s | %s | [%s](#%s) | %s | `%s` | %s | %s |" % (
                suite, platform, e["id"], e["id"], e["date"], e["source_commit"][:7], outcome, reason))
    else:
        L.append("Empty.")
    L += ["", "## Pins", ""]
    pins = [e for e in entries if e.get("pin")]
    if pins:
        L += ["| Record | Kind | Reason | Until |", "| --- | --- | --- | --- |"]
        for e in pins:
            L.append("| [%s](#%s) | %s | %s | %s |" % (e["id"], e["id"], e.get("suite") or e["kind"],
                                                         cell(e["pin"]["reason"]), cell(e["pin"]["until"])))
    else:
        L.append("None.")
    L += ["", "## Records"]
    for e in entries:
        L += ["", "### %s" % e["id"], ""]
        pin = e.get("pin")
        pin_text = "%s; until %s" % (pin["reason"], pin["until"]) if pin else "none"
        if e["kind"] == "suite":
            L += ["- Suite: %s, `%s` (SHA-256 %s at the source commit)" % (
                      e["suite"], e["script"]["path"], code(e["script"]["sha256"])),
                  "- Source commit: `%s`; archive SHA-256 %s" % (e["source_commit"],
                                                                 code(e.get("source_archive_sha256"))),
                  "- Finished: %s" % e["date"],
                  "- Outcome: **%s**" % e["outcome"],
                  "- Run-level failures: %s" % ("; ".join(cell(f) for f in e["failures"]) or "none")]
            if e["suite"] == "acceptance":
                L.append("- Python image: %s" % code(e.get("python_image")))
            if e["suite"] == "toolchain":
                v = e.get("vendor")
                L.append("- Vendored crates: %s" % ("%d files, listing SHA-256 `%s`" % (v["files"], v["listing_sha256"])
                                                    if v else "not recorded"))
            L += ["- Evidence: `%s` (%s)" % (e["evidence"]["path"], e["evidence"]["where"]),
                  "- Pin: %s" % pin_text, ""]
            L += render_platform_rows(e)
        else:
            r = e["result"]
            if "files" in r:
                result_text = ("- Result: `%s`, every regular file under it (%d files); SHA-256 of their sorted "
                               "listing (SHA-256, size and path of each) `%s`" % (r["path"], r["files"], r["sha256"]))
            else:
                result_text = "- Result: `%s`, SHA-256 `%s`" % (r["path"], r["sha256"])
            L += ["- Experiment: %s" % cell(e["summary"]),
                  "- Date: %s (from %s)" % (e["date"], e["date_from"]),
                  result_text,
                  "- Evidence: `%s` (%s)" % (e["evidence"]["path"], e["evidence"]["where"]),
                  "- Pin: %s" % pin_text]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- drift

def _strip_lines(text, marker):
    return [l.rstrip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith(marker)]


def _python_shape(text):
    """The AST without docstrings (comments never reach the AST), or None when it does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return ast.dump(tree, include_attributes=False)


def file_kind(path, data):
    name = os.path.basename(path)
    first = data.split(b"\n", 1)[0] if data else b""
    if name.endswith(".rs"):
        return "rust"
    if name.endswith(".py") or (first.startswith(b"#!") and b"python" in first):
        return "python"
    if name.endswith(".sh") or name in ("Containerfile", "Dockerfile") or (first.startswith(b"#!") and b"sh" in first):
        return "shell"
    return "other"


def code_changed(path, old, new):
    """Whether OLD and NEW (bytes; None for absent) differ outside comments and docstrings."""
    if old == new:
        return False
    kind = file_kind(path, new if new is not None else old)
    if kind == "other":
        return True
    texts = [(b or b"").decode("utf-8", "surrogateescape") for b in (old, new)]
    if kind == "rust":
        return _strip_lines(texts[0], "//") != _strip_lines(texts[1], "//")
    if kind == "python":
        shapes = [_python_shape(t) for t in texts]
        if None not in shapes:
            return shapes[0] != shapes[1]
    return _strip_lines(texts[0], "#") != _strip_lines(texts[1], "#")


def drift(ctx, commit):
    """Files under service/ and apparatus/ changed since COMMIT, measured against the working tree (uncommitted and
    untracked-but-not-ignored files included); the record's own three files (RECORD_FILES) are left out, and so is a
    file whose bytes equal COMMIT's (git lists it when only the index's stat cache is stale). A file that existed at
    COMMIT but whose contents there are not available locally (a partial clone) counts as code."""
    status = {}
    # diff.autoRefreshIndex=false: git diff would otherwise rewrite the index's stat cache; this stays read-only.
    raw = ctx.git(["-c", "diff.autoRefreshIndex=false", "diff", "--no-renames", "--name-status", "-z", commit,
                   "--"] + list(DRIFT_ROOTS)).stdout
    parts = raw.decode("utf-8", "surrogateescape").split("\0")
    for i in range(0, len(parts) - 1, 2):
        status[parts[i + 1]] = parts[i]
    raw = ctx.git(["ls-files", "-z", "--others", "--exclude-standard", "--"] + list(DRIFT_ROOTS)).stdout
    for path in raw.decode("utf-8", "surrogateescape").split("\0"):
        if path:
            status[path] = "?"
    changed, comments, docs = [], [], []
    for path in sorted(status):
        if path in RECORD_FILES:
            continue
        label = "%s %s" % (status[path], path)
        old = None if status[path] in ("A", "?") else ctx.blob(commit, path)
        full = os.path.join(ctx.root, *path.split("/"))
        new = None
        if os.path.isfile(full) and not os.path.islink(full):
            with open(full, "rb") as handle:
                new = handle.read()
        if old is not None and old == new:
            continue
        if path.endswith(".md"):
            docs.append(label)
        elif old is None and status[path] not in ("A", "?"):
            changed.append(label + " (contents at %s not available locally; counted as code)" % commit[:7])
        else:
            (changed if code_changed(path, old, new) else comments).append(label)
    return changed, comments, docs


# ---------------------------------------------------------------- check

def diff_fields(stored, fresh, prefix=""):
    if isinstance(stored, dict) and isinstance(fresh, dict):
        out = []
        for key in sorted(set(stored) | set(fresh)):
            if not prefix and key in TYPED_FIELDS:
                continue
            path = "%s.%s" % (prefix, key) if prefix else key
            if key not in stored or key not in fresh:
                out.append("%s: %s in the record, %s in the evidence" % (
                    path, "present" if key in stored else "absent", "present" if key in fresh else "absent"))
            else:
                out += diff_fields(stored[key], fresh[key], path)
        return out
    if isinstance(stored, list) and isinstance(fresh, list) and len(stored) == len(fresh):
        out = []
        for i, (a, b) in enumerate(zip(stored, fresh)):
            out += diff_fields(a, b, "%s[%d]" % (prefix, i))
        return out
    if stored != fresh or type(stored) is not type(fresh):
        return ["%s: record %s, evidence %s" % (prefix, json.dumps(stored), json.dumps(fresh))]
    return []


def run_check(ctx, strict=False, out=print, with_drift=True, require_evidence=False):
    """Return [(tag, message)] failures; print a report."""
    fails = []
    record = None
    try:
        data = read_regular(ctx.record, ctx.show(ctx.record))
        if data is None:
            fails.append(("record", "%s does not exist; create it with extract or pin --experiment"
                          % ctx.show(ctx.record)))
        else:
            record = parse_json(data)
    except Refusal as exc:
        fails.append(("record", str(exc)))
    except (ValueError, UnicodeDecodeError) as exc:
        fails.append(("record", "%s is not valid JSON: %s" % (ctx.show(ctx.record), exc)))
    if not fails:
        fails += [("schema", p) for p in record_problems(record)]
    if fails:
        for tag, msg in fails:
            out("FAIL %s: %s" % (tag, msg))
        out("check: FAILED (%d); nothing else was checked" % len(fails))
        return fails
    entries = record["entries"]
    out("check %s (%s, %d records)" % (ctx.show(ctx.record), SCHEMA, len(entries)))
    expected = render(record)
    try:
        raw = read_regular(ctx.markdown, ctx.show(ctx.markdown))
    except Refusal as exc:
        fails.append(("render", str(exc)))
    else:
        actual = None if raw is None else raw.decode("utf-8", "replace")
        if actual != expected:
            fails.append(("render", "%s %s a fresh render; run render, never edit it by hand" % (
                ctx.show(ctx.markdown), "is missing, not" if actual is None else "differs from")))
        else:
            out("ok   %s matches a fresh render" % ctx.show(ctx.markdown))
    keep = front(entries)
    scratch_exists, scratch_names = scratch_listing(ctx)
    for e in entries:
        if e["kind"] == "suite":
            if not ctx.commit_exists(e["source_commit"]):
                fails.append(("commit", "%s: source commit %s is not in this repository" % (e["id"], e["source_commit"])))
            else:
                out("ok   %s: source commit %s is in the repository" % (e["id"], e["source_commit"][:12]))
        if e["id"] not in keep and not e.get("pin"):
            out("note %s is neither on the front nor pinned; the next extract drops it" % e["id"])
        # The evidence is the .scratch folder listed under exactly the record's id (record_problems has made its
        # evidence.path .scratch/<id>); on a case-insensitive volume a name differing in case is another folder.
        if e["id"] not in scratch_names:
            where = e["evidence"]["path"]
            hint = case_hint(scratch_names, e["id"])
            if scratch_exists:
                matched = ["%s/%s (%s)" % (ctx.show(ctx.scratch), name, ", ".join(rels))
                           for name in sorted(scratch_names) if not name.startswith(".")
                           for rels in [folder_matches(ctx, name, e)] if rels]
                if matched:
                    hint += "; its recorded digests match %s" % "; ".join(matched)
            if require_evidence:
                fails.append(("absent", "%s: evidence %s is not present here, and --require-evidence needs it%s"
                              % (e["id"], where, hint)))
            elif scratch_exists:
                out("WARN %s: evidence %s is absent although %s exists; not re-verified%s (--require-evidence "
                    "makes this fail)" % (e["id"], where, ctx.show(ctx.scratch), hint))
            else:
                out("skip %s: evidence %s is not present here; not re-verified" % (e["id"], where))
            if e["kind"] == "suite" and ctx.commit_exists(e["source_commit"]):
                blob = ctx.blob(e["source_commit"], e["script"]["path"])
                if blob is None:
                    fails.append(("script", "%s: %s" % (e["id"], ctx.why_no_blob(e["source_commit"],
                                                                                  e["script"]["path"]))))
                elif sha256(blob) != e["script"]["sha256"]:
                    fails.append(("script", "%s: %s at %s does not have the recorded SHA-256"
                                  % (e["id"], e["script"]["path"], e["source_commit"][:12])))
            continue
        try:
            if e["kind"] == "suite":
                fresh = extract_suite(ctx, e["id"], e["suite"])
            else:
                fresh = experiment_entry(ctx, e["id"], e["result"]["path"], e["summary"], date_file(e["date_from"]))
        except Refusal as exc:
            fails.append(("evidence", "%s: re-extracting the local evidence failed: %s" % (e["id"], exc)))
            continue
        diffs = diff_fields(e, fresh)
        if diffs:
            fails.append(("evidence", "%s no longer matches its local evidence:\n%s" % (
                e["id"], "\n".join("       " + d for d in diffs))))
        else:
            out("ok   %s matches its local evidence (re-extracted: %s)" % (
                e["id"], "digests, counts and outcome" if e["kind"] == "suite" else
                "result digest and date" if "files" not in e["result"] else
                "listing digest of %d files, and date" % e["result"]["files"]))
    for tag, msg in fails:
        out("FAIL %s: %s" % (tag, msg))
    print_pins(record, out)
    if with_drift:
        out("drift since each front run's source commit, in %s (working tree, including uncommitted and "
            "untracked files; the record's own %s are left out; comment-only changes are not code; A added, "
            "M modified, D deleted, ? untracked)%s:" % (
                " and ".join(r + "/" for r in DRIFT_ROOTS), ", ".join(sorted(RECORD_FILES)),
                "; --strict fails on code drift" if not strict else ""))
        for e in entries:
            if e["id"] not in keep or e["kind"] != "suite" or not ctx.commit_exists(e["source_commit"]):
                continue
            changed, comments, docs = drift(ctx, e["source_commit"])
            out("  %s (%s, source %s, %s):" % (e["id"], e["suite"], e["source_commit"][:7], e["date"]))
            for title, labels in (("code changes", changed), ("comment-only changes", comments),
                                  ("documentation (Markdown)", docs)):
                out("    %s: %s" % (title, len(labels) or "none"))
                for label in labels[:DRIFT_SHOWN]:
                    out("      " + label)
                if len(labels) > DRIFT_SHOWN:
                    out("      and %d more (all: git diff --name-status %s -- %s)" % (
                        len(labels) - DRIFT_SHOWN, e["source_commit"][:7], " ".join(DRIFT_ROOTS)))
            if strict and changed:
                fails.append(("drift", "%s: %d files under %s have code changes since %s" % (
                    e["id"], len(changed), "/".join(DRIFT_ROOTS), e["source_commit"][:7])))
                out("FAIL drift: %s has code drift" % e["id"])
    out("check: %s" % ("passed" if not fails else "FAILED (%d)" % len(fails)))
    return fails


# ---------------------------------------------------------------- candidates

def citations(ctx):
    """{name in lower case: [file]} for every ".scratch/<name>" in a tracked or untracked-but-not-ignored file, other
    than the record's own three files (RECORD_FILES): the record keeps folders through its front and pins, not
    through its rendering. A name is kept in lower case because a citation that differs from a folder's name only
    in case still keeps that folder. Each file is opened without following a link or blocking; only a regular file
    is read."""
    raw = ctx.git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"]).stdout
    found = {}
    for path in sorted(set(raw.decode("utf-8", "surrogateescape").split("\0"))):
        if not path or path.startswith(".scratch/") or path in RECORD_FILES:
            continue
        try:
            fd = os.open(os.path.join(ctx.root, *path.split("/")),
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | O_CLOEXEC)
        except OSError:
            continue
        try:
            data = read_fd(fd) if stat.S_ISREG(os.fstat(fd).st_mode) else b""
        except OSError:
            data = b""
        finally:
            os.close(fd)
        for m in CITATION.finditer(data):
            name = m.group(1).decode("ascii").lower()
            for form in {name, name.rstrip(".")}:
                found.setdefault(form, set()).add(path)
    return {k: sorted(v) for k, v in found.items()}


def disk_usage(path):
    """Bytes allocated under PATH (each inode once; links not followed), and the count of unreadable items."""
    seen, total, errors = set(), 0, [0]

    def add(st):
        key = (st.st_dev, st.st_ino)
        if key not in seen:
            seen.add(key)
            return st.st_blocks * 512
        return 0

    try:
        st = os.lstat(path)
    except OSError:
        return 0, 1
    total += add(st)
    if stat.S_ISDIR(st.st_mode):
        def onerror(_exc):
            errors[0] += 1
        for base, dirs, files in os.walk(path, onerror=onerror, followlinks=False):
            for name in dirs + files:
                try:
                    total += add(os.lstat(os.path.join(base, name)))
                except OSError:
                    errors[0] += 1
    return total, errors[0]


def _count_files(path, limit):
    """Entries other than folders under PATH, links not followed and Finder's .DS_Store files not counted, stopping
    once the count passes LIMIT. A folder result's listing digest can match only when this equals its count."""
    count = 0
    for _base, _dirs, files in os.walk(path, followlinks=False):
        count += sum(1 for name in files if name != FINDER_FILE)
        if count > limit:
            break
    return count


def folder_matches(ctx, name, entry):
    """The files in the .scratch entry NAME that hold ENTRY's recorded digests, or [] when NAME does not match
    ENTRY. NAME matches an acceptance run when any driver-*/evidence/RESULT.json in it has a RESULT.json SHA-256
    the run records; a toolchain run when its source archive, vendor listing and build digests are all the ones
    recorded (runs of the same source share these, so they all match); an experiment when its result has the
    recorded SHA-256 (a file) or file count and listing digest (a folder). Reads only, never following a link."""
    try:
        if not stat.S_ISDIR(os.lstat(os.path.join(ctx.scratch, name)).st_mode):
            return []
    except OSError:
        return []
    ev = Evidence(ctx, name)
    digest = lambda rel, token=False: ev.first_token(rel, need=False) if token else ev.digest(rel, need=False)
    if entry["kind"] == "suite" and entry["suite"] == "acceptance":
        wanted = {pl.get("result_sha256") for pl in entry["platforms"].values()} - {None}
        try:
            subs = sorted(n for n in os.listdir(ev.dir) if n.startswith("driver-"))
        except OSError:
            return []
        rels = ["%s/evidence/RESULT.json" % sub for sub in subs]
        return [rel for rel in rels if wanted and digest(rel) in wanted]
    if entry["kind"] == "suite":
        wants = []
        if entry["source_archive_sha256"]:
            wants.append(("host/source.sha256", True, entry["source_archive_sha256"]))
        if entry["vendor"]:
            wants.append(("host/vendor.sha256", False, entry["vendor"]["listing_sha256"]))
        for pl in entry["platforms"].values():
            for build in pl.get("builds") or []:
                if build["sha256"]:
                    wants.append(("%s/sha256.stdout" % build["name"], True, build["sha256"]))
        if wants and all(digest(rel, token) == want for rel, token, want in wants):
            return [rel for rel, _token, _want in wants]
        return []
    result = entry["result"]
    rel = result["path"]
    if "files" in result:  # counting first is cheap; only the listing digest, read without links, decides
        if _count_files(ev.path(rel), result["files"]) != result["files"]:
            return []
        return [rel] if ev.tree(rel) == (result["files"], result["sha256"]) else []
    return [rel] if digest(rel) == result["sha256"] else []


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def run_candidates(ctx, out=print):
    """List .scratch entries with sizes and why each is kept, then warn about each record that nothing here accounts
    for: its folder is not listed and no folder holds its recorded digests. Returns one row per entry, then one with
    status "absent" per such record. Reads only; never changes anything."""
    record = load_record(ctx, missing_ok=True)
    keep = front(record["entries"])
    pins = {e["id"]: e["pin"] for e in record["entries"] if e.get("pin")}
    cites = citations(ctx)
    names = sorted(os.listdir(ctx.scratch)) if os.path.isdir(ctx.scratch) else []
    rows, totals = [], {"keep": [0, 0], "candidate": [0, 0], "ignored": [0, 0]}
    for name in names:
        size, errors = disk_usage(os.path.join(ctx.scratch, name))
        if name.startswith("."):
            # A dot entry (a harness's or tool's own folder) is not a run: never a record, never a candidate.
            totals["ignored"][0] += 1
            totals["ignored"][1] += size
            rows.append({"name": name, "size": size, "unreadable": errors, "status": "ignored",
                         "why": ["dot entry"]})
            out("%-9s %10s  %s  (dot entry)%s" % ("ignored", human(size), name,
                                                  "  (%d items unreadable; size is a lower bound)" % errors
                                                  if errors else ""))
            continue
        why = []
        if name in keep:
            why.append("front (%s)" % "; ".join(keep[name]))
        if name in pins:
            why.append("pinned until %s" % pins[name]["until"])
        if name.lower() in cites:
            files = cites[name.lower()]
            why.append("cited by %s%s" % (", ".join(files[:4]), " and %d more" % (len(files) - 4)
                                          if len(files) > 4 else ""))
        if not why:
            # Records find their folders by exact name. A folder no name keeps is still kept when it holds a
            # record's recorded digests; a record that has none to find gets a WARN line below.
            for e in record["entries"]:
                rels = folder_matches(ctx, name, e)
                if rels:
                    why.append("holds the digests recorded for %s (%s)" % (e["id"], ", ".join(rels[:3]) + (
                        " and %d more" % (len(rels) - 3) if len(rels) > 3 else "")))
        status = "keep" if why else "candidate"
        totals[status][0] += 1
        totals[status][1] += size
        rows.append({"name": name, "size": size, "unreadable": errors, "status": status, "why": why})
        out("%-9s %10s  %s%s%s" % (status, human(size), name, "  " + "; ".join(why) if why else "",
                                   "  (%d items unreadable; size is a lower bound)" % errors if errors else ""))
    out("kept: %d entries, %s; ignored (dot entries): %d, %s; removal candidates: %d entries, %s. This command "
        "never deletes or changes anything; removal is a decision for the user." % (
            totals["keep"][0], human(totals["keep"][1]), totals["ignored"][0], human(totals["ignored"][1]),
            totals["candidate"][0], human(totals["candidate"][1])))
    for e in record["entries"]:
        if e["id"] not in names and not any(folder_matches(ctx, n, e) for n in names if not n.startswith(".")):
            rows.append({"name": e["id"], "status": "absent", "why": []})
            out("WARN %s: its evidence folder %s is absent and no folder here holds its digests, so a renamed copy "
                "may be listed as a candidate; remove nothing until the record and the folders agree"
                % (e["id"], e["evidence"]["path"]))
    return rows


# ---------------------------------------------------------------- commands

def run_folder(ctx, arg):
    """Resolve RUN_DIR to a name directly under .scratch."""
    candidates = [os.path.abspath(arg), os.path.join(ctx.root, arg), os.path.join(ctx.scratch, arg)]
    for path in candidates:
        if os.path.lexists(path):
            break
    else:
        raise Refusal("%s does not exist (looked relative to the current folder, the repository and .scratch)" % arg)
    path = os.path.abspath(path)
    if os.path.islink(path) or not os.path.isdir(path):
        raise Refusal("%s is not a folder (links are not followed)" % arg)
    if os.path.realpath(os.path.dirname(path)) != os.path.realpath(ctx.scratch):
        raise Refusal("%s is not directly under %s; the record names runs by their .scratch folder" % (
            arg, ctx.show(ctx.scratch)))
    name = os.path.basename(path)
    if not RUN_ID.fullmatch(name):
        raise Refusal("%s cannot be a record id: a run folder's name uses letters, digits, '.', '_' and '-' and "
                      "does not start with a dot" % name)
    names = scratch_listing(ctx)[1]
    if name not in names:
        raise Refusal("%s is not the name %s lists; give the folder's name exactly, case included%s"
                      % (arg, ctx.show(ctx.scratch), case_hint(names, name)))
    return name


def inside_folder(ctx, folder, arg, what):
    """ARG, given relative to FOLDER or as a path inside it, as a normalized path relative to FOLDER."""
    rel = arg
    if not os.path.lexists(os.path.join(folder, arg)):
        full = os.path.abspath(arg)
        for base in (folder, os.path.realpath(folder)):
            if full == base or full.startswith(base + os.sep):
                rel = os.path.relpath(full, base)
                break
        else:
            raise Refusal("%s %s is neither a path in %s nor a path inside it" % (what, arg, ctx.show(folder)))
    rel = clean_rel(rel.replace(os.sep, "/"))
    if rel is None:
        raise Refusal("%s %s is not inside %s" % (what, arg, ctx.show(folder)))
    return rel


def one_line(text, what):
    text = (text or "").strip()
    if not text or "\n" in text:
        raise Refusal("%s must be one non-empty line" % what)
    return text


def cmd_extract(ctx, run_arg, suite, out=print):
    run_id = run_folder(ctx, run_arg)
    record = load_record(ctx, missing_ok=True)
    entry = extract_suite(ctx, run_id, suite)
    old = next((e for e in record["entries"] if e["id"] == run_id), None)
    if old is not None and old["kind"] != "suite":
        raise Refusal("%s is recorded as an experiment; unpin it first" % run_id)
    if old is not None:
        entry["pin"] = old.get("pin")
        diffs = diff_fields(old, entry)
        out("replaced %s: %s" % (run_id, "unchanged" if not diffs else "%d fields changed" % len(diffs)))
        for d in diffs:
            out("  " + d)
        record["entries"] = [entry if e["id"] == run_id else e for e in record["entries"]]
    else:
        out("added %s" % run_id)
        record["entries"].append(entry)
    out("%s (%s, source %s, finished %s): %s" % (run_id, suite, entry["source_commit"][:12], entry["date"],
                                                 entry["outcome"]))
    for f in entry["failures"]:
        out("  run failure: %s" % f)
    for key, pl in entry["platforms"].items():
        out("  %s: %s" % (key, summarize_platform(suite, pl)))
        for f in pl.get("failures") or []:
            out("    failure: %s" % f)
    apply_front(record, out)
    print_front(record, out)
    save(ctx, record, out)
    print_pins(record, out)
    return entry


def summarize_platform(suite, pl):
    if "cases" not in pl and "builds" not in pl:
        return pl.get("outcome", "?")
    if suite == "acceptance":
        g = pl["timing_gate"]
        return ("%s, %s; cases %s; sabotage controls %s; driver controls %s; timing gate %s (worst %s ms); "
                "%s %s %s checks; release %s" % (
                    pl["outcome"], pl["execution"], ratio(pl["cases"], "passed", "selected"),
                    ratio(pl["controls"], "fired", "total"), ratio(pl["driver_controls"], "fired", "total"),
                    "on" if g["enabled"] else "off", g["worst_ms"], E2E_CASE, pl["e2e"]["outcome"],
                    pl["e2e"]["checks_passed"], (pl["release_sha256"] or "?")[:16]))
    return "%s; image %s; builds %s; reproducible %s; release %s" % (
        pl["outcome"], (pl["toolchain_image"] or "?")[:19],
        ", ".join("%s %s/%s steps" % (b["name"], b["steps_passed"], b["steps_total"]) for b in pl["builds"]),
        "yes" if pl["reproducible"] else "no", (pl["release_sha256"] or "?")[:16])


def cmd_pin(ctx, args, out=print):
    reason = one_line(args.reason, "--reason")
    until = one_line(args.until, "--until")
    record = load_record(ctx, missing_ok=args.experiment is not None)
    if args.experiment is not None:
        if args.id:
            raise Refusal("give either ID or --experiment, not both")
        if not args.summary or not args.result:
            raise Refusal("pin --experiment needs --summary and --result")
        run_id = run_folder(ctx, args.experiment)
        folder = os.path.join(ctx.scratch, run_id)
        result = inside_folder(ctx, folder, args.result, "--result")
        date_rel = None if args.date_from is None else inside_folder(ctx, folder, args.date_from, "--date-from")
        entry = experiment_entry(ctx, run_id, result, one_line(args.summary, "--summary"), date_rel)
        old = next((e for e in record["entries"] if e["id"] == run_id), None)
        if old is not None and old["kind"] != "experiment":
            raise Refusal("%s is recorded as a %s run; pin it with `pin %s`" % (run_id, old.get("suite"), run_id))
        entry["pin"] = {"reason": reason, "until": until}
        record["entries"] = [e for e in record["entries"] if e["id"] != run_id] + [entry]
        out("pinned experiment %s (%s, from %s; %s%s SHA-256 %s)" % (
            run_id, entry["date"], entry["date_from"], result,
            " (%d files, listing)" % entry["result"]["files"] if "files" in entry["result"] else "",
            entry["result"]["sha256"]))
    else:
        if not args.id or args.summary or args.result or args.date_from:
            raise Refusal("pin ID takes only --reason and --until; an experiment needs --experiment")
        entry = next((e for e in record["entries"] if e["id"] == args.id), None)
        if entry is None:
            raise Refusal("%s is not in the record; extract it first, or pin it with --experiment" % args.id)
        entry["pin"] = {"reason": reason, "until": until}
        out("pinned %s" % args.id)
    apply_front(record, out)
    save(ctx, record, out)
    print_pins(record, out)


def cmd_unpin(ctx, run_id, out=print):
    record = load_record(ctx)
    entry = next((e for e in record["entries"] if e["id"] == run_id), None)
    if entry is None:
        raise Refusal("%s is not in the record" % run_id)
    if not entry.get("pin"):
        raise Refusal("%s is not pinned" % run_id)
    entry["pin"] = None
    out("unpinned %s%s" % (run_id, "; an experiment record exists only while pinned"
                           if entry["kind"] == "experiment" else ""))
    apply_front(record, out)
    save(ctx, record, out)
    print_pins(record, out)


def cmd_render(ctx, out=print):
    record = load_record(ctx)
    changed = write_if_changed(ctx.markdown, render(record), ctx.show(ctx.markdown))
    out("%s %s" % ("wrote" if changed else "unchanged:", ctx.show(ctx.markdown)))


# ---------------------------------------------------------------- self-test

FIXTURE_SCRIPT = """#!/bin/sh
TEST_VARS="STEWART_TEST_A STEWART_TEST_B"
note "acceptance suite start; repository $REPO; native architecture $NATIVE"
    expect "$OUT/$b/build-release.exit" 0 "$p: release build"
    expect "$OUT/$b/static-stewart-glibc.exit" 1 "$p: control fired: the static check rejects the glibc build"
    for var in $TEST_VARS; do
        expect "$OUT/$b/strings-stewart-$var.exit" 1 "$p: release binary lacks $var"
        expect "$OUT/$b/strings-stewart-test-$var.exit" 0 "$p: control fired: the test binary contains $var"
    done
    expect "$OUT/$d/selftest.exit" 0 "$p: driver self-test"
"""
FIXTURE_TOOLCHAIN_SCRIPT = """#!/bin/sh
note "step2 apparatus check start; repository $REPO"
"""


def _write(base, rel, text):
    path = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _fixture_run(ctx, run_id, commit, date, failing):
    """A small acceptance run in the layout acceptance.sh writes; FAILING breaks one case on aarch64."""
    d = os.path.join(ctx.scratch, run_id)
    w = lambda rel, text: _write(d, rel, text)
    w("host/commit.stdout", commit + "\n")
    w("staging/COMMIT", commit + "\n")
    w("host/DONE", "done %s failures=%d\n" % (date, 1 if failing else 0))
    log = "%s acceptance suite start; repository /r; native architecture arm64\n" % date
    if failing:
        log += "%s FAILED: driver-arm64: the driver reported failures\n" % date
    w("host/driver.log", log)
    w("host/source.sha256", "%s  /r/staging/source.tar\n" % sha256(run_id.encode()))
    image = lambda tag: json.dumps([{"configuration": {"descriptor": {"digest": "sha256:" + sha256(tag.encode())}}}])
    w("host/python-inspect.stdout", image("python"))
    bins = []
    for p, _key, machine in PLATFORMS:
        broken = failing and p == "arm64"
        w("host/toolchain-inspect-%s.stdout" % p, image("toolchain-" + p))
        w("host/build-%s.exit" % p, "0\n")
        w("host/driver-%s.exit" % p, "%d\n" % broken)
        for rel, value in (("build-release", 0), ("static-stewart-glibc", 1), ("strings-stewart-STEWART_TEST_A", 1),
                           ("strings-stewart-STEWART_TEST_B", 1), ("strings-stewart-test-STEWART_TEST_A", 0),
                           ("strings-stewart-test-STEWART_TEST_B", 0)):
            w("build-%s/%s.exit" % (p, rel), "%d\n" % value)
        w("build-%s/toolchain.stdout" % p, "rustc 0.0.0 (fixture)\n")
        release, test = sha256(("%s-%s-r" % (run_id, p)).encode()), sha256(("%s-%s-t" % (run_id, p)).encode())
        bins += ["%s  /r/build-%s/stewart" % (release, p), "%s  /r/build-%s/stewart-test" % (test, p)]
        w("driver-%s/emulation.txt" % p, "none\n" if p == "arm64" else "--emulator-home-artifact .cache/rosetta\n")
        for rel, value in (("selftest", 0), ("driver", broken), ("driver-final", broken)):
            w("driver-%s/%s.exit" % (p, rel), "%d\n" % value)
        w("driver-%s/selftest.stdout" % p, "ok   x\nself-test: 3 checks, 3 passed, 0 failed, 0 skipped\n")
        gated = p == "arm64"
        result = {
            "schema": DRIVER_SCHEMA, "interrupted": False, "platform": {"machine": machine},
            "binaries": {"release": {"sha256": release, "source_sha256": release},
                         "test": {"sha256": test, "source_sha256": test}},
            "counts": {"cases": {"selected": 3, "ran": 3, "passed": 3 - broken, "failed": int(broken), "skipped": 0},
                       "variants": {"ran": 5, "passed": 4, "failed": 1, "skipped": 0},
                       "checks": {"passed": 40, "failed_outside_controls": int(broken), "failed_inside_controls": 2},
                       "controls": {"total": 1, "fired": 1, "not_fired": 0, "baseline_failed": 0, "skipped": 0},
                       "driver_controls": {"total": 1, "fired": 1}},
            "failed_cases": ["c1.fixture"] if broken else [], "broken_checks": [],
            "controls_unassigned": [], "controls_never_fired": [],
            "timing_gate": {"enabled": gated, "threshold_ms": 100.0, "worst_ms": 1.5, "passed": True if gated else None,
                            "protocol": {"worst_ms": 3.0, "passed": True if gated else None}},
            "cases": [{"id": E2E_CASE, "outcome": "pass",
                       "variants": [{"binary": "release", "checks_passed": 10, "checks_failed": 0}]}],
            "exit": int(broken),
        }
        w("driver-%s/evidence/RESULT.json" % p, json.dumps(result, indent=1))
    w("host/binaries.sha256", "\n".join(bins) + "\n")


def _tree_state(path):
    """{relative path: what is there} for everything under PATH, links not followed: a witness of any change."""
    state = {}
    for base, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            full = os.path.join(base, name)
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                what = ("link", os.readlink(full))
            elif stat.S_ISREG(st.st_mode):
                with open(full, "rb") as handle:
                    what = ("file", sha256(handle.read()))
            else:
                what = ("folder" if stat.S_ISDIR(st.st_mode) else "other", None)
            state[os.path.relpath(full, path)] = what
    return state


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


class _Deadline(Exception):
    """Raised by with_deadline's alarm."""


def with_deadline(seconds, action):
    """ACTION's result, or _Deadline raised once SECONDS pass; the alarm interrupts an open or read that blocks.
    The self-test runs in the main thread, where signals are delivered."""
    def expire(_signum, _frame):
        raise _Deadline("no result within %d seconds" % seconds)
    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return action()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class _MemoCtx(Ctx):
    """A context that remembers each git command's result by its arguments, for the sweep of altered records, which
    runs the same read-only commands many times."""

    def __init__(self, *args, **kwargs):
        Ctx.__init__(self, *args, **kwargs)
        self.answers = {}

    def git(self, args, check=True):
        key = (tuple(args), check)
        if key not in self.answers:
            self.answers[key] = Ctx.git(self, args, check)
        return self.answers[key]


def _toolchain_entry(commit):
    """A valid toolchain record whose evidence is absent, so the sweep covers every field a toolchain record has."""
    platforms = {}
    for p, key, _machine in PLATFORMS:
        digest = sha256(("tool-1-" + p).encode())
        platforms[key] = {
            "execution": None, "outcome": "qualified", "failures": [],
            "toolchain_image": "sha256:" + sha256(("toolchain-" + p).encode()), "rustc": "rustc 0.0.0 (fixture)",
            "builds": [{"name": "build-%s-%d" % (p, i), "steps_passed": 9, "steps_total": 9, "static": True,
                        "run_exit": 0, "offline": True, "sha256": digest} for i in (1, 2)],
            "reproducible": True, "release_sha256": digest, "alpine_run_exit": 0}
    return {"id": "tool-1", "kind": "suite", "suite": "toolchain",
            "script": {"path": SUITES["toolchain"]["script"], "sha256": sha256(FIXTURE_TOOLCHAIN_SCRIPT.encode())},
            "source_commit": commit, "source_archive_sha256": sha256(b"tool-1"), "date": "2026-01-08T00:00:00Z",
            "outcome": "qualified", "failures": [], "vendor": {"files": 2, "listing_sha256": sha256(b"vendor")},
            "platforms": platforms, "evidence": evidence_field("tool-1"), "pin": None}


def _altered_records(record, ids):
    """(label, altered copy, whether a field was removed) for each field of the entries named IDS, descending into
    the first platform of each and the first item of each array: the field removed, then set to each other kind of
    value, one nested too deeply included. Removing a platform or an array item is not counted as removing a field:
    it leaves a record of the same shape that only the evidence can contradict."""
    deep = "x"
    for _ in range(MAX_DEPTH + 4):
        deep = [deep]
    values = (None, True, 7, 1.5, "x", [], ["x"], {}, {"x": 1}, deep)
    paths = []

    def walk(value, path):
        if isinstance(value, dict):
            for key in (list(value)[:1] if path[-1] == "platforms" else list(value)):
                paths.append(path + (key,))
                walk(value[key], path + (key,))
        elif isinstance(value, list) and value:
            paths.append(path + (0,))
            walk(value[0], path + (0,))

    for i, e in enumerate(record["entries"]):
        if e["id"] in ids:
            walk(e, ("entries", i))

    def at(value, path):
        for key in path:
            value = value[key]
        return value

    for path in paths:
        label = ".".join([at(record, path[:2])["id"]] + [str(k) for k in path[2:]])
        current = at(record, path)
        removed = copy.deepcopy(record)
        del at(removed, path[:-1])[path[-1]]
        yield "remove " + label, removed, isinstance(path[-1], str) and path[-2] != "platforms"
        for value in values:
            if type(value) is type(current) and value == current:
                continue
            changed = copy.deepcopy(record)
            at(changed, path[:-1])[path[-1]] = copy.deepcopy(value)
            yield "set %s to %s" % (label, json.dumps(value)[:24]), changed, False


def _run_every_command(ctx, record):
    """Write RECORD where CTX keeps the record (with its render when it is valid), then run check (with drift),
    render, candidates, extract of run-b and unpin of exp-3 on it. Returns (check's failures, None), or (None, what
    was raised) when any command raised anything but a refusal."""
    quiet = lambda *_: None
    folder = os.path.dirname(ctx.record)
    try:
        _write(folder, "qualified.json", json.dumps(record, indent=2) + "\n")  # escaped, so any string can be written
        _write(folder, "qualified.md", "not a render\n" if record_problems(record) else render(record))
        fails = run_check(ctx, out=quiet)
        for command in (lambda: cmd_render(ctx, out=quiet), lambda: run_candidates(ctx, out=quiet),
                        lambda: cmd_extract(ctx, "run-b", "acceptance", out=quiet),
                        lambda: cmd_unpin(ctx, "exp-3", out=quiet)):
            try:
                command()
            except Refusal:
                pass
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, str(exc)[:120])
    return fails, None


# Set for the whole self-test, as a git hook's environment sets them, to point at a throwaway victim repository.
POISONED = ("GIT_DIR", "GIT_INDEX_FILE")
# Set for the whole self-test as a caller's shell might set it, naming a file inside the victim: any git command
# that receives it appends a trace there. No git command the script or its self-test runs may pass it on.
CALLER_TRACE = "GIT_TRACE"


def run_self_test(out=print):
    base = tempfile.mkdtemp(prefix="qualified-self-test-")
    out("self-test in %s (left in place: this script deletes nothing)" % base)
    isolated = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "HOME": base,
                "GIT_AUTHOR_NAME": "self-test", "GIT_AUTHOR_EMAIL": "self-test@invalid",
                "GIT_COMMITTER_NAME": "self-test", "GIT_COMMITTER_EMAIL": "self-test@invalid"}
    results = []

    def control(name, ok, detail):
        """Report one control; OK is True (passed), False (failed) or None (skipped: it cannot fire here)."""
        results.append(ok)
        out("%s %s: %s" % ({True: "PASS", False: "FAIL", None: "SKIP"}[ok], name, detail))

    # The victim: a repository with one commit, made before the environment points at it. Every git command
    # below runs while GIT_DIR and GIT_INDEX_FILE name the victim, as they would under a git hook, and while the
    # caller's GIT_TRACE names a file inside it.
    victim = os.path.join(base, "victim")
    _write(victim, "victim.txt", "the victim's own file\n")
    vctx = Ctx(victim, git_env=isolated)
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-verify", "-m", "victim"]):
        vctx.git(args)
    victim_before = _tree_state(victim)
    caller_trace = os.path.join(victim, "caller-trace.log")
    saved = {key: os.environ.get(key) for key in POISONED + (CALLER_TRACE,)}
    os.environ["GIT_DIR"] = os.path.join(victim, ".git")
    os.environ["GIT_INDEX_FILE"] = os.path.join(victim, ".git", "index")
    os.environ[CALLER_TRACE] = caller_trace
    try:
        _self_test_controls(base, isolated, control)
    except Exception as exc:  # a control that raises is a failure to report, not a reason to stop reporting
        control("self-test: the controls ran to the end", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    victim_after = _tree_state(victim)
    differ = sorted(k for k in set(victim_before) | set(victim_after) if victim_before.get(k) != victim_after.get(k))
    control("git: the victim repository named by GIT_DIR and GIT_INDEX_FILE throughout is unchanged afterwards",
            bool(victim_before) and not differ, "%d paths under the victim (its .git included) compared; changed: %s"
            % (len(victim_before), differ[:8] or "none"))
    control("git: no git command passed on the caller's %s (its trace file in the victim is absent)" % CALLER_TRACE,
            not os.path.lexists(caller_trace), "%s %s" % (caller_trace, "exists" if os.path.lexists(caller_trace)
                                                          else "is absent"))

    passed, failed = results.count(True), results.count(False)
    out("self-test: %d controls, %d passed, %d failed, %d skipped" % (len(results), passed, failed,
                                                                      len(results) - passed - failed))
    return failed == 0


def _self_test_controls(base, isolated, control):
    root = os.path.join(base, "repo")
    os.makedirs(root)
    ctx = Ctx(root, git_env=isolated)
    _write(root, ".gitignore", ".scratch/\nignored.txt\n")
    _write(root, "apparatus/acceptance.sh", FIXTURE_SCRIPT)
    _write(root, "apparatus/step2.sh", FIXTURE_TOOLCHAIN_SCRIPT)
    _write(root, "service/src/lib.rs", "//! The crate.\n\npub fn f() -> u32 {\n    // one\n    1\n}\n")
    _write(root, "apparatus/tool.py", '"""A tool."""\n\n\ndef g():\n    """Say two."""\n    return 2  # two\n')
    _write(root, "apparatus/README.md", "# Apparatus\n")
    _write(root, "service/README.md", "# Service\n")
    ctx.git(["init", "-q"])
    ctx.git(["add", "-A"])
    ctx.git(["commit", "-q", "--no-verify", "-m", "fixture"])
    commit = ctx.git(["rev-parse", "HEAD"]).stdout.decode().strip()
    quiet = lambda *_: None

    # Git: the inherited GIT_DIR is live (an unfiltered command follows it), and this script's commands ignore it.
    # The firing control passes on GIT_DIR and GIT_INDEX_FILE, the variables it tests, and nothing else of the
    # caller's: its environment is the filtered one every git command gets, so the caller's GIT_TRACE stays out.
    fire_env = git_env(isolated)
    fire_env.update({key: os.environ[key] for key in POISONED})
    unfiltered = subprocess.run(["git", "-C", root, "rev-parse", "--absolute-git-dir"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=fire_env)
    raw_dir = unfiltered.stdout.decode("utf-8", "replace").strip()
    here = ctx.git(["rev-parse", "--absolute-git-dir"]).stdout.decode("utf-8", "replace").strip()
    control("git: an unfiltered git command in the fixture follows the inherited GIT_DIR (firing control)",
            unfiltered.returncode == 0 and os.path.realpath(raw_dir) == os.path.realpath(os.environ["GIT_DIR"]),
            "it resolves %s" % (raw_dir or unfiltered.stderr.decode("utf-8", "replace").strip()))
    control("git: this script's git commands use the fixture's own repository and its fixture commit",
            os.path.realpath(here) == os.path.realpath(os.path.join(root, ".git"))
            and HEX40.fullmatch(commit) is not None,
            "they resolve %s; HEAD %s" % (here, commit[:12]))
    # The caller's GIT_TRACE (set by run_self_test) is live: git given a GIT_TRACE appends its trace to that file.
    probe = os.path.join(base, "trace-probe.log")
    traced = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(git_env(isolated),
                                                                                     **{CALLER_TRACE: probe}))
    control("git: a git command given %s writes its trace file (firing control for the caller's %s)"
            % (CALLER_TRACE, CALLER_TRACE), traced.returncode == 0 and os.path.isfile(probe)
            and os.path.getsize(probe) > 0, "%s %s" % (probe, "written" if os.path.isfile(probe) else "absent"))

    # Git: in a partial clone a missing object is never fetched; a command given lazy fetching would fetch it.
    ctx.git(["config", "uploadpack.allowFilter", "true"])
    partial = os.path.join(base, "partial")
    ctx.git(["clone", "-q", "--no-checkout", "--filter=blob:none", "file://" + root, partial])
    pctx = Ctx(partial, git_env=isolated)
    wanted = "apparatus/acceptance.sh"
    oid = pctx.git(["rev-parse", "%s:%s" % (commit, wanted)]).stdout.decode().strip()
    missing = lambda: pctx.git(["cat-file", "-e", oid], check=False).returncode != 0
    was_missing = missing()
    got = pctx.blob(commit, wanted)
    still_missing = missing()
    control("git: this script's commands never fetch an object missing from a partial clone",
            was_missing and got is None and still_missing,
            "%s:%s missing before %s; read back %s; missing after %s" % (
                commit[:12], wanted, was_missing, "nothing" if got is None else "%d bytes" % len(got), still_missing))
    lazy_env = git_env(isolated)
    lazy_env.pop("GIT_NO_LAZY_FETCH", None)
    lazy = subprocess.run(["git", "-C", partial, "cat-file", "blob", "%s:%s" % (commit, wanted)],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=lazy_env)
    control("git: without GIT_NO_LAZY_FETCH the same read fetches the object from the clone's remote (firing "
            "control; the remote is the fixture repository)",
            lazy.returncode == 0 and lazy.stdout == FIXTURE_SCRIPT.encode(),
            "exit %d, %d bytes" % (lazy.returncode, len(lazy.stdout)))
    # The clone has no checkout, so every file reads as deleted; of their contents only acceptance.sh's is now local.
    p_code, p_comments, _docs = drift(pctx, commit)
    control("drift: in a partial clone, a deleted file whose contents at the source commit are not local counts as "
            "code, said as such", not p_comments and "D service/src/lib.rs (contents at %s not available locally; "
            "counted as code)" % commit[:7] in p_code, "code %s; comment-only %s" % (p_code, p_comments))
    _write(partial, "apparatus/qualified.json", dump_json({"schema": SCHEMA, "entries": [_toolchain_entry(commit)]}))
    p_fails = run_check(pctx, out=quiet, with_drift=False)
    control("check: in a partial clone, a script that exists at the source commit but is not local is said to be "
            "so", any(t == "script" and "step2.sh exists at %s, but its contents are not available" % commit in m
                      for t, m in p_fails), "failures %s" % p_fails)

    _fixture_run(ctx, "run-0", commit, "2025-12-31T00:00:00Z", False)
    _fixture_run(ctx, "run-a", commit, "2026-01-01T00:00:00Z", False)
    _fixture_run(ctx, "run-b", commit, "2026-01-02T00:00:00Z", False)
    _fixture_run(ctx, "run-c", commit, "2026-01-03T00:00:00Z", True)
    ids = lambda: [e["id"] for e in load_record(ctx)["entries"]]

    # Front rule.
    cmd_extract(ctx, "run-0", "acceptance", out=quiet)
    cmd_extract(ctx, "run-a", "acceptance", out=quiet)
    step1 = ids()
    control("front: a newer qualified run replaces an older unpinned one", step1 == ["run-a"],
            "record after extracting run-0 then run-a: %s" % step1)
    cmd_pin(ctx, argparse.Namespace(id="run-a", experiment=None, summary=None, result=None, date_from=None,
                                    reason="fixture", until="the self-test ends"), out=quiet)
    cmd_extract(ctx, "run-b", "acceptance", out=quiet)
    step2 = ids()
    control("front: a pin keeps an older run", step2 == ["run-a", "run-b"],
            "record after pinning run-a and extracting run-b: %s" % step2)
    c_entry = cmd_extract(ctx, "run-c", "acceptance", out=quiet)
    step3 = ids()
    control("outcome: a failed case makes the run failed, mechanically",
            c_entry["outcome"] == "failed" and c_entry["platforms"]["linux-aarch64"]["outcome"] == "failed"
            and c_entry["platforms"]["linux-x86_64"]["outcome"] == "qualified",
            "run-c %s; aarch64 %s; x86_64 %s" % (c_entry["outcome"], c_entry["platforms"]["linux-aarch64"]["outcome"],
                                                   c_entry["platforms"]["linux-x86_64"]["outcome"]))
    control("front: keeps the last qualified run behind a failed latest one",
            step3 == ["run-a", "run-b", "run-c"], "record after extracting the failed run-c: %s" % step3)
    cmd_unpin(ctx, "run-a", out=quiet)
    step4 = ids()
    control("front: an older unpinned run leaves", step4 == ["run-b", "run-c"],
            "record after unpinning run-a: %s" % step4)

    # Check: a clean record passes; each tampering fires its own failure.
    clean = run_check(ctx, out=quiet, with_drift=False)
    control("check: the untouched record passes (invariance)", clean == [], "failures %s" % clean)
    # The copy sits outside the fixture repository, so it is neither drift nor a citation.
    copy = os.path.join(base, "trial", "qualified.json")
    variant = Ctx(root, record=copy, git_env=isolated)

    def tampered(change, edit_markdown=None):
        record = load_record(ctx)
        change(record)
        _write(os.path.dirname(copy), "qualified.json", dump_json(record))
        _write(os.path.dirname(copy), "qualified.md", render(record) + (edit_markdown or ""))
        return run_check(variant, out=quiet, with_drift=False)

    def bump(record):
        record["entries"][0]["platforms"]["linux-aarch64"]["cases"]["passed"] += 1

    def repin(record):
        record["entries"][0]["pin"] = {"reason": "typed text", "until": "never"}

    def no_commit(record):
        record["entries"][0]["source_commit"] = "0" * 40

    for name, change, md, tag in (("a tampered count in a copy of the JSON", bump, None, "evidence"),
                                  ("a hand edit to the Markdown", lambda r: None, "\nedited by hand\n", "render"),
                                  ("a nonexistent source commit", no_commit, None, "commit")):
        fails = tampered(change, md)
        control("check fails on %s" % name, tag in [t for t, _ in fails],
                "failure tags %s" % sorted(set(t for t, _ in fails)))
    fails = tampered(repin)
    control("check: a typed field (pin text) is not evidence (invariance)", fails == [], "failures %s" % fails)

    # Check finds evidence only at evidence.path, which must be the id's own folder.
    def rename(record):
        record["entries"][0]["id"] = "run-z"
        bump(record)

    def rename_both(record):
        record["entries"][0]["id"] = "run-0"
        record["entries"][0]["evidence"]["path"] = evidence_path("run-0")

    fails = tampered(rename)
    control("check fails on a renamed id (with a tampered count) whose evidence.path still names the old folder",
            any(t == "schema" and "evidence.path" in m for t, m in fails),
            "failures %s" % [m for _, m in fails])
    fails = tampered(rename_both)
    control("check re-verifies at the renamed evidence.path: another run's folder there does not match",
            any(t == "evidence" and m.startswith("run-0 no longer matches") for t, m in fails),
            "failure tags %s" % sorted(set(t for t, _ in fails)))

    # Check says what is wrong when the record is missing or cannot be decoded.
    _write(base, "repeated/qualified.json", '{"schema": "%s", "entries": [], "entries": []}\n' % SCHEMA)
    for name, where, expect in (("a missing record", "absent", "does not exist"),
                                ("a record with a repeated key", "repeated", "repeated key")):
        lines = []
        fails = run_check(Ctx(root, record=os.path.join(base, where, "qualified.json"), git_env=isolated),
                          out=lines.append, with_drift=False)
        control("check fails on %s and says why" % name,
                [t for t, _ in fails] == ["record"] and any(expect in l for l in lines)
                and any(l.startswith("check: FAILED") for l in lines), "output %s" % lines)

    # Experiments: a folder result is the SHA-256 of a sorted listing of every regular file under it.
    exp = os.path.join(ctx.scratch, "exp-1")
    files = {"times.json": '{"at": "2026-01-04T01:02:03+01:00"}\n', "copies/a.txt": "a\n",
             "copies/deep/b.txt": "b\n", "copies/Z.txt": "z\n"}
    for rel, text in files.items():
        _write(exp, rel, text)
    listing = "".join("%s %d %s\n" % (sha256(files[rel].encode()), len(files[rel].encode()), rel)
                      for rel in sorted(files, key=lambda r: r.encode()))
    pin = lambda **kw: argparse.Namespace(**dict(dict(
        id=None, experiment="exp-1", summary="fixture experiment", result=".", date_from="times.json",
        reason="fixture", until="the self-test ends"), **kw))
    cmd_pin(ctx, pin(), out=quiet)
    entry = next(e for e in load_record(ctx)["entries"] if e["id"] == "exp-1")
    want = {"path": ".", "files": 4, "sha256": sha256(listing.encode())}
    control("experiment: --result . records the digest of the sorted listing of every regular file, and the date",
            entry["result"] == want and entry["date"] == "2026-01-04T00:02:03Z"
            and entry["date_from"] == "times.json field at",
            "result %s (want %s); date %s from %s" % (entry["result"], want, entry["date"], entry["date_from"]))
    cmd_pin(ctx, pin(experiment="exp-1", result="copies"), out=quiet)
    entry = next(e for e in load_record(ctx)["entries"] if e["id"] == "exp-1")
    control("experiment: --result FOLDER lists only that folder, paths relative to it",
            entry["result"]["path"] == "copies" and entry["result"]["files"] == 3,
            "result %s" % entry["result"])
    cmd_pin(ctx, pin(), out=quiet)
    clean = run_check(ctx, out=quiet, with_drift=False)
    control("check: a pinned folder result re-verifies (invariance)", clean == [], "failures %s" % clean)
    _write(exp, "copies/deep/b.txt", "B\n")
    edited = run_check(ctx, out=quiet, with_drift=False)
    control("check fails when a file under a folder result changes",
            any(t == "evidence" and "result.sha256" in m for t, m in edited),
            "failures %s" % [m.splitlines()[0] for _, m in edited])
    _write(exp, "copies/deep/b.txt", "b\n")
    restored = run_check(ctx, out=quiet, with_drift=False)
    control("check passes again once that file's bytes are restored (invariance)", restored == [],
            "failures %s" % restored)
    # A Finder .DS_Store is not part of a folder result; any other new file is.
    loose = os.path.join(ctx.scratch, "exp-ds")
    _write(loose, "a.txt", "a\n")
    ds_tree = lambda: Evidence(ctx, "exp-ds").tree(".")
    plain = ds_tree()
    _write(loose, "sub/" + FINDER_FILE, "Finder\n")
    finder = ds_tree()
    _write(loose, "sub/DS_Store", "Finder\n")
    other = ds_tree()
    control("experiment: a new file under a folder result changes its count and digest (firing control)",
            other is not None and finder is not None and other[0] == finder[0] + 1 and other[1] != finder[1],
            "files and digest: %s, then with sub/DS_Store %s" % (finder, other))
    control("experiment: a %s under a folder result is skipped: count and digest unchanged" % FINDER_FILE,
            plain is not None and finder == plain, "files and digest: %s, then with sub/%s %s"
            % (plain, FINDER_FILE, finder))
    _write(exp, FINDER_FILE, "Finder\n")
    _write(exp, "copies/" + FINDER_FILE, "Finder\n")
    finder_check = run_check(ctx, out=quiet, with_drift=False)
    control("check: a pinned folder result re-verifies after Finder writes %s files into it (invariance)"
            % FINDER_FILE, finder_check == [], "failures %s" % [m.splitlines()[0] for _, m in finder_check])
    linked = os.path.join(ctx.scratch, "exp-2")
    _write(linked, "result.json", '{"at": "2026-01-05T00:00:00Z"}\n')
    os.symlink(os.path.join(exp, "copies", "a.txt"), os.path.join(linked, "planted"))
    try:
        cmd_pin(ctx, pin(experiment="exp-2", date_from=None), out=quiet)
        refused = "pinned"
    except Refusal as exc:
        refused = str(exc)
    control("experiment: a link under a folder result is refused", "planted: a link" in refused,
            "pin --experiment with a link inside: %s" % refused.replace("\n", " "))
    os.symlink(os.path.join(exp, "copies"), os.path.join(linked, "sub"))
    ev = Evidence(ctx, "exp-2")
    got = ev.bytes("sub/a.txt")
    control("evidence: a file read through a link in place of a folder in a run folder is refused, not read",
            _read(os.path.join(linked, "sub", "a.txt")) == b"a\n" and got is None
            and "sub: a link (links are refused)" in ev.problems, "read %r; problems %s" % (got, ev.problems))
    os.symlink(os.path.join(exp, "times.json"), os.path.join(exp, "copies", "late-link"))
    late = run_check(ctx, out=quiet, with_drift=False)
    control("check fails when a link appears under a pinned folder result",
            any(t == "evidence" and "late-link: a link" in m for t, m in late),
            "failures %s" % [m.replace("\n", " ") for _, m in late])

    # Writes: a link in place of qualified.json, qualified.md or their folder is refused and never followed.
    record_text = dump_json(load_record(ctx))
    victim_file = os.path.join(base, "victim-file.txt")
    _write(base, "victim-file.txt", "not the record\n")
    _write(base, "victim-record.json", record_text)
    victim_record = os.path.join(base, "victim-record.json")
    for folder in ("link-md", "link-json", "hard-md", "real-dir"):
        os.makedirs(os.path.join(base, folder))
    _write(base, "link-md/qualified.json", record_text)
    os.symlink(victim_file, os.path.join(base, "link-md", "qualified.md"))
    os.symlink(victim_record, os.path.join(base, "link-json", "qualified.json"))
    _write(base, "hard-md/qualified.json", record_text)
    os.link(victim_file, os.path.join(base, "hard-md", "qualified.md"))
    _write(base, "real-dir/qualified.json", record_text)
    os.symlink(os.path.join(base, "real-dir"), os.path.join(base, "link-dir"))

    def attempt(folder, action):
        trial = Ctx(root, record=os.path.join(base, folder, "qualified.json"), git_env=isolated)
        try:
            if action == "render":
                cmd_render(trial, out=quiet)
            else:
                save(trial, load_record(trial), quiet)
            return "wrote"
        except Refusal as exc:
            return str(exc)

    victims = lambda: (_read(victim_file), _read(victim_record))
    before = victims()
    reach = _read(os.path.join(base, "link-md", "qualified.md")) == before[0] and \
        _read(os.path.join(base, "link-json", "qualified.json")) == before[1]
    control("write: each planted link reaches its victim when followed (firing control)", reach,
            "reading through the links gives the victims' bytes: %s" % reach)
    for name, folder, action, expect in (
            ("qualified.md is a symbolic link", "link-md", "render", "it is a link"),
            ("qualified.json is a symbolic link", "link-json", "save", "it is a link"),
            ("qualified.md is a hard link", "hard-md", "render", "a hard link"),
            ("their folder is a symbolic link", "link-dir", "render", "is a link; links are not followed")):
        got = attempt(folder, action)
        control("write: refused when %s, and the victim is unchanged" % name,
                expect in got and victims() == before, "%s: %s" % (action, got))
    got = attempt("real-dir", "render")
    written = os.path.join(base, "real-dir", "qualified.md")
    control("write: a regular file in a real folder is written (invariance)",
            got == "wrote" and _read(written) == render(load_record(ctx)).encode("utf-8")
            and not os.path.islink(written), "render: %s" % got)
    # A second name made between the read and the write (raced deterministically: made just before the write open).
    target, other = os.path.join(base, "race", "qualified.md"), os.path.join(base, "race", "other-name")
    _write(base, "race/qualified.md", "old render\n")
    real_open = os.open

    def racing_open(path, flags, *rest, **kw):
        if flags & (os.O_WRONLY | os.O_RDWR) and not os.path.lexists(other):
            os.link(target, other)
        return real_open(path, flags, *rest, **kw)

    os.open = racing_open
    try:
        got = "wrote" if write_if_changed(target, "new render\n") else "unchanged"
    except Refusal as exc:
        got = str(exc)
    finally:
        os.open = real_open
    control("write: a hard link made between the read and the write is refused before anything is truncated",
            "changed while it was opened" in got and _read(other) == b"old render\n",
            "%s; the other name holds %r" % (got, _read(other) if os.path.lexists(other) else None))

    # Reads: every command reads qualified.json and qualified.md under the rules they are written under, so a
    # link to identical bytes, a hard link or a FIFO in their place is refused, never read through or waited on.
    md_text = render(load_record(ctx))
    _write(base, "read-target/qualified.json", record_text)
    _write(base, "read-target/qualified.md", md_text)
    target_json = os.path.join(base, "read-target", "qualified.json")
    target_md = os.path.join(base, "read-target", "qualified.md")
    for folder in ("render-json-sym", "render-json-hard", "check-json-sym", "check-json-hard", "check-md-sym",
                   "check-md-hard", "check-fifo"):
        os.makedirs(os.path.join(base, folder))
    os.symlink(target_json, os.path.join(base, "render-json-sym", "qualified.json"))
    os.link(target_json, os.path.join(base, "render-json-hard", "qualified.json"))
    os.symlink(target_json, os.path.join(base, "check-json-sym", "qualified.json"))
    _write(base, "check-json-sym/qualified.md", md_text)
    os.link(target_json, os.path.join(base, "check-json-hard", "qualified.json"))
    _write(base, "check-json-hard/qualified.md", md_text)
    _write(base, "check-md-sym/qualified.json", record_text)
    os.symlink(target_md, os.path.join(base, "check-md-sym", "qualified.md"))
    _write(base, "check-md-hard/qualified.json", record_text)
    os.link(target_md, os.path.join(base, "check-md-hard", "qualified.md"))
    os.mkfifo(os.path.join(base, "check-fifo", "qualified.json"))
    trial_ctx = lambda folder: Ctx(root, record=os.path.join(base, folder, "qualified.json"), git_env=isolated)

    for name, folder, expect in (("a symbolic link", "render-json-sym", "it is a link"),
                                 ("a hard link", "render-json-hard", "a hard link")):
        got = []
        for command in (lambda c: cmd_render(c, out=quiet), lambda c: run_candidates(c, out=quiet)):
            try:
                command(trial_ctx(folder))
                got.append("proceeded")
            except Refusal as exc:
                got.append(str(exc))
        beside = os.path.lexists(os.path.join(base, folder, "qualified.md"))
        control("read: render and candidates refuse a qualified.json that is %s, and nothing is written beside it"
                % name, all(g.startswith("refusing to read") and expect in g for g in got) and not beside,
                "render: %s; candidates: %s; qualified.md written: %s" % (got[0], got[1], beside))

    for name, folder, tag, expect in (
            ("qualified.json is a symbolic link to identical bytes", "check-json-sym", "record", "it is a link"),
            ("qualified.json is a hard link to identical bytes", "check-json-hard", "record", "a hard link"),
            ("qualified.md is a symbolic link to identical bytes", "check-md-sym", "render", "it is a link"),
            ("qualified.md is a hard link to identical bytes", "check-md-hard", "render", "a hard link"),
            ("qualified.json is a FIFO, without waiting for a writer", "check-fifo", "record", "a FIFO")):
        try:
            # A deadline, so a check that waits on the FIFO for a writer fails this control instead of hanging.
            fails = with_deadline(10, lambda: run_check(trial_ctx(folder), out=quiet, with_drift=False))
        except Exception as exc:
            fails = [("raised", "%s: %s" % (type(exc).__name__, exc))]
        control("read: check fails when %s" % name,
                any(t == tag and m.startswith("refusing to read") and expect in m for t, m in fails),
                "failures %s" % [(t, m.splitlines()[0]) for t, m in fails])

    # Candidates: only a citation from a tracked or untracked-but-not-ignored file keeps an entry.
    _write(ctx.scratch, "orphan-01/x", "x\n")
    status = lambda: {r["name"]: r["status"] for r in run_candidates(ctx, out=quiet)}
    before = status()
    _write(root, "ignored.txt", "see .scratch/orphan-01\n")
    ignored = status()
    _write(root, "NOTES.md", "see .scratch/orphan-01.\n")
    cited = status()
    control("candidates: an uncited entry is a candidate; an ignored file's citation does not keep it",
            before.get("orphan-01") == "candidate" and ignored.get("orphan-01") == "candidate",
            "uncited %s; cited only by an ignored file %s" % (before.get("orphan-01"), ignored.get("orphan-01")))
    control("candidates: a citation keeps a candidate", cited.get("orphan-01") == "keep",
            "cited by an untracked NOTES.md: %s; front runs %s" % (
                cited.get("orphan-01"), {k: cited.get(k) for k in ("run-b", "run-c")}))
    _write(ctx.scratch, "orphan-02/x", "x\n")
    _write(ctx.scratch, "orphan-03/x", "x\n")
    _write(root, "CASE.md", "see .scratch/ORPHAN-02\n")
    md = _read(ctx.markdown)
    _write(os.path.dirname(ctx.markdown), "qualified.md", md.decode("utf-8") + "see .scratch/orphan-03\n")
    cited = status()
    with open(ctx.markdown, "wb") as handle:
        handle.write(md)
    control("candidates: a citation differing from a folder's name only in case keeps it",
            cited.get("orphan-02") == "keep", "cited as .scratch/ORPHAN-02: %s" % cited.get("orphan-02"))
    control("candidates: a citation in the record's own qualified.md does not keep a folder",
            cited.get("orphan-03") == "candidate", "cited only by qualified.md: %s" % cited.get("orphan-03"))
    os.makedirs(os.path.join(ctx.scratch, ".harness", ".cc-writes"))
    os.makedirs(os.path.join(ctx.scratch, "empty-01"))
    dots = status()
    control("candidates: a dot entry is ignored, never a candidate; an empty ordinary entry is a candidate",
            dots.get(".harness") == "ignored" and dots.get("empty-01") == "candidate",
            "dot entry %s; empty ordinary entry %s" % (dots.get(".harness"), dots.get("empty-01")))

    # Evidence is the folder listed under exactly the record's id. Two more experiments, with a folder result and a
    # file result, to rename alongside run-b (exp-1 now holds a link, so no listing digest covers it).
    for name, files in (("exp-3", {"result.json": '{"at": "2026-01-06T00:00:00Z"}\n', "data/x.txt": "x\n"}),
                        ("exp-4", {"result.json": '{"at": "2026-01-07T00:00:00Z"}\n', "notes.txt": "n\n"})):
        for rel, text in files.items():
            _write(os.path.join(ctx.scratch, name), rel, text)
    cmd_pin(ctx, pin(experiment="exp-3", result=".", date_from="result.json"), out=quiet)
    cmd_pin(ctx, pin(experiment="exp-4", result="result.json", date_from=None), out=quiet)

    saved_record = (_read(ctx.record), _read(ctx.markdown))

    def variant_run(change, also=None, **check_options):
        """Check and candidates with the repository's own record changed by CHANGE, as a hand edit would leave it;
        then ALSO, and the record is restored. Returns (failures, check's lines, candidates rows by name, ALSO's
        result)."""
        record = load_record(ctx)
        change(record)
        _write(os.path.dirname(ctx.record), os.path.basename(ctx.record), dump_json(record))
        _write(os.path.dirname(ctx.markdown), os.path.basename(ctx.markdown), render(record))
        lines = []
        try:
            fails = run_check(ctx, out=lines.append, with_drift=False, **check_options)
        except Exception as exc:  # report a command that cannot take these options, or crashes, as a failure
            fails = [("raised", "%s: %s" % (type(exc).__name__, exc))]
        rows = {r["name"]: r for r in run_candidates(ctx, out=quiet)}
        result = also() if also else None
        for path, data in zip((ctx.record, ctx.markdown), saved_record):
            with open(path, "wb") as handle:
                handle.write(data)
        return fails, lines, rows, result

    def extract_recased():
        try:
            cmd_extract(ctx, "Run-b", "acceptance", out=quiet)
            return "extracted"
        except Refusal as exc:
            return str(exc)

    def rename(pairs):
        def change(record):
            for old, new in pairs:
                e = next(x for x in record["entries"] if x["id"] == old)
                e["id"], e["evidence"]["path"] = new, evidence_path(new)
        return change

    conflates = os.path.isdir(os.path.join(ctx.scratch, "Run-b"))
    control("evidence: this volume opens .scratch/Run-b for the folder listed as run-b (firing control: the "
            "volume is case-insensitive)", True if conflates else None,
            "it does" if conflates else "this volume is case-sensitive, so the case controls cannot fire here")
    fails, lines, rows, refused = variant_run(rename([("run-b", "Run-b")]), also=extract_recased)
    shown = [l for l in lines if "Run-b" in l]
    control("evidence: check does not re-verify a record whose id differs from its folder's name only in case; it "
            "warns, naming that folder",
            not any(l.startswith("ok   Run-b matches") for l in lines)
            and any(l.startswith("WARN Run-b:") and ".scratch has run-b" in l for l in lines), "lines %s" % shown)
    row = rows.get("run-b", {})
    control("candidates: the folder of a record whose id differs from its name only in case is kept, as holding "
            "that record's digests", row.get("status") == "keep" and any("Run-b" in w for w in row.get("why", ())),
            "run-b: %s; %s" % (row.get("status"), row.get("why")))
    control("evidence: extract refuses a run folder named in another case than .scratch lists it",
            ("exactly, case included" in refused) if conflates else refused != "extracted",
            "extract Run-b: %s" % refused)

    gone = (("run-b", "run-gone"), ("exp-3", "exp3-gone"), ("exp-4", "exp4-gone"))
    fails, lines, rows, _ = variant_run(rename(gone))
    warned = {new: [l for l in lines if l.startswith("WARN %s:" % new)] for _old, new in gone}
    control("evidence: check warns, without failing, for each record whose evidence is absent while .scratch "
            "exists, naming the folder that holds its digests",
            all(any("its recorded digests match .scratch/%s " % old in l for l in warned[new]) for old, new in gone)
            and not any(new in m for _t, m in fails for _old, new in gone),
            "WARN lines %s; failures naming them %s" % (
                [l[:110] for ls in warned.values() for l in ls],
                [m.splitlines()[0] for _t, m in fails if any(new in m for _old, new in gone)]))
    fails, lines, rows, _ = variant_run(rename(gone), require_evidence=True)
    absent = sorted(m.split(":")[0] for t, m in fails if t == "absent")
    control("evidence: check --require-evidence fails for each record whose evidence is absent",
            absent == sorted(new for _old, new in gone), "absent failures for %s; failures %s" % (
                absent, [(t, m.splitlines()[0]) for t, m in fails]))
    control("candidates: a folder whose record's id was changed to an absent name is kept, as holding that "
            "record's digests (an acceptance run, a folder result and a file result)",
            all(rows.get(old, {}).get("status") == "keep" and any(new in w for w in rows[old]["why"])
                for old, new in gone), "; ".join("%s: %s %s" % (old, rows.get(old, {}).get("status"),
                                                                rows.get(old, {}).get("why")) for old, _new in gone))
    control("candidates: other runs' folders, whose RESULT.json digests differ, stay candidates (invariance)",
            rows.get("run-0", {}).get("status") == "candidate" and rows.get("run-a", {}).get("status") == "candidate",
            "run-0 %s; run-a %s" % (rows.get("run-0", {}).get("status"), rows.get("run-a", {}).get("status")))

    def no_digests(record):  # run-b renamed as if it had stopped before recording any RESULT.json
        rename([("run-b", "run-gone")])(record)
        for pl in next(e for e in record["entries"] if e["id"] == "run-gone")["platforms"].values():
            pl["result_sha256"] = None

    _fails, _lines, bare, _ = variant_run(no_digests)
    control("candidates: a record whose folder is absent and whose digests no folder holds gets a WARN line (exit "
            "1); records accounted for by their digests get none",
            bare.get("run-gone", {}).get("status") == "absent" and not any(r["status"] == "absent" for r in rows.values()),
            "run-gone %s, its renamed folder run-b %s; absent rows with digests held: %s" % (
                bare.get("run-gone", {}).get("status"), bare.get("run-b", {}).get("status"),
                [n for n, r in rows.items() if r["status"] == "absent"]))

    def recase(record):  # paths inside a run folder named in another case than the folder lists them
        for e in record["entries"]:
            if e["id"] == "exp-3":
                e["date_from"] = "RESULT.json field at"
            elif e["id"] == "exp-4":
                e["result"]["path"] = "RESULT.json"

    def pin_recased():
        try:
            cmd_pin(ctx, pin(experiment="exp-4", result="RESULT.json", date_from=None), out=quiet)
            return "pinned"
        except Refusal as exc:
            return str(exc)

    fails, _lines, _rows, refused = variant_run(recase, also=pin_recased)
    hint = "its folder has result.json, whose name differs only in case"
    control("evidence: a result path or date file in another case than its folder lists it fails check, and pin "
            "refuses it, each with a hint", sum(t == "evidence" and hint in m for t, m in fails) == 2 and hint in refused,
            "failures %s; pin: %s" % ([m.replace("\n", " ")[:140] for _t, m in fails], refused.replace("\n", " ")))

    # Malformed records: a reason from check, never a traceback from any command.
    deep_ctx = Ctx(root, record=os.path.join(base, "deep", "qualified.json"), git_env=isolated)
    _write(base, "deep/qualified.json", '{"schema": "%s", "entries": %s%s}\n' % (SCHEMA, "[" * 100000, "]" * 100000))
    said = []
    for command in (lambda: run_check(deep_ctx, out=said.append, with_drift=False),
                    lambda: cmd_render(deep_ctx, out=quiet), lambda: run_candidates(deep_ctx, out=quiet)):
        try:
            command()
        except Refusal as exc:
            said.append(str(exc))
        except Exception as exc:
            said.append("raised %s" % type(exc).__name__)
    control("record: a record nested too deeply to decode fails check with a reason, and render and candidates "
            "refuse it", any(l.startswith("FAIL record:") and "too deeply" in l for l in said)
            and sum("too deeply" in l for l in said) == 3 and not any(l.startswith("raised") for l in said),
            "%s" % [l[-90:] for l in said])

    sweep_ctx = _MemoCtx(root, record=os.path.join(base, "sweep", "qualified.json"), git_env=isolated)
    good = load_record(ctx)
    good["entries"] = [e for e in good["entries"] if e["id"] != "exp-1"] + [_toolchain_entry(commit)]
    base_fails, base_raised = _run_every_command(sweep_ctx, good)
    control("record: the sweep's starting record (two acceptance runs, two experiments, a toolchain run whose "
            "evidence is absent) passes check (invariance)", base_fails == [] and base_raised is None,
            "failures %s; raised %s" % ([m.splitlines()[0] for _t, m in base_fails or []], base_raised))
    raised, passed_removals, count = [], [], 0
    for label, changed, removal in _altered_records(good, ("run-c", "exp-3", "exp-4", "tool-1")):
        count += 1
        fails, problem = _run_every_command(sweep_ctx, changed)
        if problem:
            raised.append("%s: %s" % (label, problem))
        elif removal and not fails:
            passed_removals.append(label)
    control("record: %d altered copies of a valid record (each field of an entry of each kind removed, or set to "
            "another kind of value): check, render, candidates, extract and unpin never raise, and check fails on "
            "every removed field" % count, count > 0 and not raised and not passed_removals,
            "raised %d %s; removals check passed %d %s" % (len(raised), raised[:3], len(passed_removals),
                                                            passed_removals[:3]))
    for name, change in (
            ("a platform key that is not a platform", lambda e: e["platforms"].update(
                {"linux: odd": e["platforms"].pop("linux-x86_64")})),
            ("a string with a lone surrogate", lambda e: e["failures"].append("\ud800")),
            ("a date whose UTC conversion leaves years 1-9999", lambda e: e.update(date="9999-12-31T23:59:59-01:00"))):
        changed = json.loads(json.dumps(good))
        change(changed["entries"][0])
        fails, problem = _run_every_command(sweep_ctx, changed)
        control("record: %s fails check with a reason, and no command raises" % name,
                problem is None and any(t == "schema" for t, _m in fails), "raised %s; failures %s"
                % (problem, [m for _t, m in fails or []][:2]))
    _fixture_run(ctx, "run-m", commit, "2026-01-09T00:00:00Z", False)
    bad = json.loads(_read(os.path.join(ctx.scratch, "run-m", "driver-arm64", "evidence", "RESULT.json")))
    bad["cases"][0]["variants"][0]["checks_passed"] = "many"
    _write(ctx.scratch, "run-m/driver-arm64/evidence/RESULT.json", json.dumps(bad))
    try:
        got = "extracted %s" % extract_suite(ctx, "run-m", "acceptance")["outcome"]
    except Refusal as exc:
        got = str(exc)
    except Exception as exc:
        got = "raised %s: %s" % (type(exc).__name__, exc)
    control("extract: a malformed evidence value (a checks_passed that is not a number) is named as a field that "
            "cannot be read", got.startswith("cannot extract run-m") and "checks_passed is 'many'" in got,
            got.replace("\n", " "))
    for value in (1.5, -5, float("inf"), float("nan")):
        bad["cases"][0]["variants"][0]["checks_passed"] = value
        _write(ctx.scratch, "run-m/driver-arm64/evidence/RESULT.json", json.dumps(bad))
        try:
            got = "extracted %s" % extract_suite(ctx, "run-m", "acceptance")["outcome"]
        except Refusal as exc:
            got = str(exc)
        except Exception as exc:
            got = "raised %s: %s" % (type(exc).__name__, exc)
        control("extract: a checks_passed of %r is refused as not a count" % value,
                got.startswith("cannot extract run-m") and "checks_passed is" in got and "not count" in got,
                got.replace("\n", " ")[:300])

    heading = "\n# Qualified behavior\n"
    control("render: the heading uses US spelling, %r" % heading.strip(), heading in render(load_record(ctx)),
            "heading %s" % [l for l in render(load_record(ctx)).splitlines() if l.startswith("# ")])

    # Drift: comment and docstring edits are not code; a code edit is.
    _write(root, "service/src/lib.rs", "//! The crate, documented.\n\npub fn f() -> u32 {\n    // one!\n    1\n}\n")
    _write(root, "apparatus/tool.py", '"""A tool, documented."""\n\n\ndef g():\n    """Say two!"""\n'
                                      '    return 2  # still two\n')
    _write(root, "apparatus/README.md", "# Apparatus, documented\n")
    for same in ("apparatus/step2.sh", "service/README.md"):  # same bytes; the index's stat cache is stale
        os.utime(os.path.join(root, *same.split("/")), (1e9, 1e9))
    listed = ctx.git(["-c", "diff.autoRefreshIndex=false", "diff", "--name-only", commit, "--", "apparatus/step2.sh",
                      "service/README.md"])
    code1, comments1, docs1 = drift(ctx, commit)
    control("drift: a file whose bytes equal the source commit's, Markdown included, is left out, though git lists it "
            "for its stale stat cache", None if len(listed.stdout.split()) < 2 else not any(
                "step2.sh" in l or "service/README.md" in l for l in code1 + comments1 + docs1),
            "git lists %r; drift lists %s" % (listed.stdout.strip(), code1 + comments1 + docs1))
    _write(root, "service/src/lib.rs", "//! The crate.\n\npub fn f() -> u32 {\n    2\n}\n")
    code2, _c2, _d2 = drift(ctx, commit)
    control("drift: comment and docstring edits are not code; Markdown is documentation",
            code1 == [] and len(comments1) == 2 and docs1 == ["M apparatus/README.md"],
            "code %s; comment-only %s; documentation %s" % (code1, comments1, docs1))
    control("drift: a code edit is code drift", code2 == ["M service/src/lib.rs"], "code %s" % code2)


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="qualified.py",
        description="Keep apparatus/qualified.json, the record of what the container suites have shown, and "
                    "render apparatus/qualified.md from it. The record keeps a front (per suite and platform, the "
                    "latest run, plus the latest qualified run behind a failed one) and pinned records; every "
                    "value is read from the run's own evidence under .scratch, in the folder whose listed name is "
                    "exactly the record's id, case included. Every command reads and writes qualified.json and "
                    "qualified.md only as regular files with one name, refusing a symbolic or hard link, a FIFO or "
                    "anything else in their place.",
        epilog="Run from the repository root as python3 -I -B apparatus/qualified.py COMMAND. Exit status: 0 "
               "success, 1 check or self-test failed or candidates warned, 2 refused (the message says why).")
    parser.add_argument("--self-test", action="store_true",
                        help="run firing controls in a new temporary directory (left in place) and report each")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    p = sub.add_parser("extract", help="read a run's evidence, add or replace its record, apply the front",
                       description="Read a suite run's evidence, add or replace its record (keeping any pin), "
                                   "drop records neither on the front nor pinned, rewrite the JSON and render the "
                                   "Markdown. Fails, naming each field, when the evidence cannot be read.")
    p.add_argument("run_dir", metavar="RUN_DIR", help="the run's folder, directly under .scratch")
    p.add_argument("--suite", required=True, choices=sorted(SUITES),
                   help="acceptance (apparatus/acceptance.sh) or toolchain (apparatus/step2.sh)")
    p = sub.add_parser("pin", help="keep a record off the front, with a reason and a release condition",
                       description="Pin a recorded run: pin ID --reason TEXT --until TEXT. Pin an experiment: "
                                   "pin --experiment RUN_DIR --summary TEXT --result PATH [--date-from FILE] "
                                   "--reason TEXT --until TEXT, where PATH is the experiment's result relative to "
                                   "its folder: a file, whose SHA-256 is recorded, or a folder (\".\" for the whole "
                                   "experiment folder), whose digest is the SHA-256 of a listing with one line "
                                   "\"<SHA-256> <size> <path>\" per regular file under it (path relative to it, "
                                   "sorted by its bytes), so it covers each file's path, size and contents, not mode "
                                   "bits, timestamps or empty folders; files named .DS_Store, which Finder writes "
                                   "into a folder a person opens, are skipped and not counted; a link or other "
                                   "special entry anywhere under it is "
                                   "refused. check re-computes the digest. The date comes from a DONE file with a "
                                   "UTC time, else from the at, ended_at or finished_at field of --date-from FILE "
                                   "(by default the result, when it is a JSON file).")
    p.add_argument("id", nargs="?", metavar="ID", help="a record's id (its .scratch folder name)")
    p.add_argument("--experiment", metavar="RUN_DIR", help="an experiment folder directly under .scratch")
    p.add_argument("--summary", help="one line saying what the experiment holds")
    p.add_argument("--result", metavar="PATH",
                   help="the experiment's result: a file, or a folder (\".\" for the whole experiment folder) "
                        "digested as a sorted listing of the path, size and SHA-256 of every regular file under it "
                        "(not mode bits or empty folders; .DS_Store files skipped); links are refused")
    p.add_argument("--date-from", metavar="FILE",
                   help="a JSON file in the experiment folder whose at, ended_at or finished_at field dates it, "
                        "when the folder has no DONE with a time (default: the result, if a JSON file)")
    p.add_argument("--reason", required=True, help="why the record is kept")
    p.add_argument("--until", required=True, help="the condition, in words, under which it can be released")
    p = sub.add_parser("unpin", help="release a pin; the record leaves unless it is on the front",
                       description="Remove a pin and apply the front. An experiment record leaves at once.")
    p.add_argument("id", metavar="ID")
    sub.add_parser("render", help="rewrite qualified.md from qualified.json",
                   description="Rewrite qualified.md from qualified.json, deterministically.")
    p = sub.add_parser("check", help="verify the record; report drift since each front run, measured against the "
                                     "working tree and excluding the record's own three files",
                       description="Fail when the record is missing, is not valid JSON (a repeated key included) or "
                                   "does not follow the schema (a record's evidence.path must be .scratch/ followed "
                                   "by its id), when qualified.md differs from a fresh render, a source commit is "
                                   "missing from the repository, or a record whose evidence is here no longer "
                                   "matches it. A record's evidence is the .scratch folder listed under exactly its "
                                   "id, case included; when it is absent, check prints a WARN line if .scratch "
                                   "exists (naming any folder that holds the record's digests) and a skip line if "
                                   "not, as in a clone, and --require-evidence makes either fail. Then report, "
                                   "without failing, code and documentation changes under "
                                   "service/ and apparatus/ since each front run's source commit. Drift is measured "
                                   "against the working tree, so uncommitted and untracked (not ignored) files "
                                   "count, and it excludes the record's own three files: apparatus/qualified.py, "
                                   "apparatus/qualified.json and apparatus/qualified.md.")
    p.add_argument("--strict", action="store_true",
                   help="also fail when a front run has code drift (working tree; the record's own files excluded)")
    p.add_argument("--require-evidence", action="store_true",
                   help="also fail when a record's evidence folder is not in .scratch here")
    sub.add_parser("candidates", help="list .scratch entries, their sizes and why each is kept; deletes nothing",
                   description="List each top-level .scratch entry with its size and whether it is kept: on the "
                               "front, pinned, cited as .scratch/<name> (case ignored) by a tracked or untracked-"
                               "but-not-ignored file outside .scratch other than the record's own three files, or "
                               "holding a record's recorded digests. Records name their folders exactly, case "
                               "included; a folder no record names is still kept when it holds an acceptance run's "
                               "RESULT.json digest, a toolchain run's source archive, vendor listing and build "
                               "digests (shared by runs of the same source, so all such runs are kept) or an "
                               "experiment's result digest. A dot entry (a name starting with a dot, such as a "
                               "harness's own folder) is listed as ignored and is never a candidate. Everything "
                               "else is a removal candidate. This command never deletes or changes anything. Exit "
                               "status: 0 only when every record is accounted for, its folder listed or a folder "
                               "here holding its recorded digests; otherwise 1, after a WARN line per record that "
                               "is not, since a renamed copy of its folder may be listed as a candidate. On a "
                               "machine without the evidence every record is unaccounted for, so it exits 1.")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            if args.command:
                parser.error("--self-test takes no command")
            return 0 if run_self_test() else 1
        ctx = Ctx(ROOT)
        if args.command == "extract":
            cmd_extract(ctx, args.run_dir, args.suite)
        elif args.command == "pin":
            cmd_pin(ctx, args)
        elif args.command == "unpin":
            cmd_unpin(ctx, args.id)
        elif args.command == "render":
            cmd_render(ctx)
        elif args.command == "check":
            return 1 if run_check(ctx, strict=args.strict, require_evidence=args.require_evidence) else 0
        elif args.command == "candidates":
            return 1 if any(r["status"] == "absent" for r in run_candidates(ctx)) else 0
        else:
            parser.print_help()
            return 2
    except Refusal as exc:
        print("qualified.py: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
