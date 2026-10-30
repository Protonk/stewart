# -*- coding: utf-8 -*-
"""After-launch cases: delivery, close and status once an auditor has been placed
(ACCEPTANCE C5, C8, C16 and the after-launch parts of C17 and C18; traces T8 from
the run's ending on, T9, T10, T13's close behaviour and T14).

Written from docs/INTERFACE.md, docs/QUESTION-FORMS.md, CONTRACTS.md and
ACCEPTANCE.md without reading service/. Each case drives `stewart run` against
the fake Messages API on loopback (run_support.provider) with the reacting
auditor or a fixed script, then `status` and `close`, and judges the result
against the driver's own witnesses:

- the expected return package (manifest.json, answer.json, answer.md and every
  artifact member) computed by answer_witness from what the auditor recorded,
  never from Stewart's records. Only the seal's time (`sealed_at`) and, after a
  kill, the answer revision come from Stewart's replies, because nothing else
  can witness them; both are checked against what can be witnessed;
- an independent verification of every delivered package from its own manifest
  alone, and a re-rendering of answer.md from the delivered answer.json and
  artifact members under the pinned rendering rules;
- confirmation tokens, loss IDs and seal handles recomputed from the witness
  manifest and the record they bind (INTERFACE 2.3);
- archive and destination inventories around every command (driver_core):
  earlier entries never change or disappear;
- status at each lifecycle point as distinct facts, with the human presentation
  carrying the same actionable facts as the JSON one.

Where the specification leaves a value open, the most literal reading is taken
and the expectation names the section it rests on.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import tempfile
import time
import traceback

import answer_witness as aw
import fake_provider as fp
import run_support as rs
from driver_core import *  # noqa: F401,F403  (case registry, T, helpers, pinned facts)
from reacting_auditor import Goal, ReactingAuditor

# ---------------------------------------------------------------------------
# Pinned shapes (INTERFACE 5.6-5.8, 8.2-8.4).
# ---------------------------------------------------------------------------

PACKAGE_FMT = "stewart-return-%s-%03d"
RUN_DELIVERY_KEYS = ("attempt", "outcome", "location", "verified_members", "unverified_members", "losses", "cause")
STATUS_DELIVERY_KEYS = ("attempt", "by", "destination", "destination_source", "package", "replaces", "outcome",
                        "cause", "verified_members", "unverified_members", "losses", "confirmation")
SEAL_VIEW_KEYS = ("handle", "actor", "sealed_at", "revision", "manifest_sha256", "unproduced")
LOSS_KEYS = ("loss", "member", "role", "failure", "stage")
RUN_LAST_KEYS = ("number", "started_at", "ending", "cause", "ended_at", "recorded_by")
# 5.8 "data of a completed reply, by path", after launch.
CLOSE_UNFINISHED_KEYS = ("closure", "unfinished_reason", "headline", "runs", "seal", "delivery", "confirmation",
                         "holder")
CLOSE_CLOSED_KEYS = ("closure", "already_closed", "before_launch", "accepted", "closed_at", "headline", "outcome",
                     "runs", "seal", "delivery", "placement", "surrendered")
# 4.2: the names an audit directory may hold.
AUDIT_LAYOUT = ("REFERENCE.json", "active.lock", "log", "stage", "prep", "intake", "payload", "prepared", "seal",
                "runs", "delivery", "diag")
UNVERIFIED = {"verified": False, "confirmed": False}

# ---------------------------------------------------------------------------
# Scenario material: a short question and two small materials, so that every
# run is a handful of turns. The goals cite both by range and by quote, carry a
# draft that is replaced (a superseded payload stays in the archive), and two
# artifacts, one text and one binary.
# ---------------------------------------------------------------------------

QUESTION = b"Can one reminder be sent twice when the worker restarts?\n"


def materials():
    return [F("a.py", b"def send(r):\n    deliver(r)\n    mark_sent(r)\n"),
            F("notes/R1.txt", "R1. A reminder ID is sent at most once.\r\nrésumé line\r\n".encode("utf-8"))]


ORDERING = "deliver(r) runs before mark_sent(r)."
DRAFT = "Draft account."


def goals(sub, *, artifacts=True, ordering=ORDERING):
    a = sub.files[b"a.py"]["data"]
    s = a.find(b"deliver(r)")
    out = [Goal("account", "A restart between the two calls can repeat a send; the materials show no recovery.",
                kind="record_account", draft=DRAFT,
                citations=[{"source": "materials/notes/R1.txt", "quote": "at most once"}]),
           Goal("ordering", ordering, citations=[{"source": "materials/a.py", "start": s, "end": s + 10}]),
           Goal("scope", "Only two files were supplied.\n", kind="record_limit")]
    if artifacts:
        out += [Goal("trace", "send -> deliver -> mark_sent\n", kind="record_artifact", artifact="text"),
                Goal("blob", kind="record_artifact", artifact="base64", data=b"\x00\x01\xfe\xff stewart\n")]
    return out


def record_step(tid, label, text):
    """A fixed response holding one record_observation call (QUESTION-FORMS input schema)."""
    return fp.Message([fp.tool_use(tid, "record_observation", input={"text": text, "label": label})],
                      stop_reason="tool_use")


def end_step(words):
    return fp.Message([fp.text(words)], stop_reason="end_turn")


def observation(eid, label, text):
    """The witness entry a record_step creates as the eid-th addition."""
    return aw.Entry(eid, 1, "record_observation", label, text.encode("utf-8"), citations=[])


# ---------------------------------------------------------------------------
# An audit and its witness.
# ---------------------------------------------------------------------------

class Audit:
    """One audit of a case: its submission, provider fixture, auditor, and the return the
    driver expects once a seal exists (entries, revision, actor and Stewart's seal time)."""

    def __init__(self, t, label, sub):
        self.t, self.label, self.sub = t, label, sub
        self.fx = self.aud = None
        self.entries = self.revision = self.actor = self.sealed_at = None
        self.files = None
        # Set when a case has made the archived seal manifest unreadable (5.6: the seal's
        # sealed_at and unproduced are the manifest's, so they can no longer be established).
        self.manifest_unreadable = False

    @property
    def manifest(self):
        return self.files["manifest.json"] if self.files else None


def audit(t, label, *, dest_watch="additions", accept=True, q=None, dest=None, archive=None, body=QUESTION):
    sub = t.submission(materials(), body=body, dest_watch=dest_watch, q=q, dest=dest, archive=archive)
    a = Audit(t, label, sub)
    if accept:
        t.accept(sub, prefix=label + ".")
    return a


def with_auditor(t, a, goal_list, **kw):
    sub = a.sub
    sources = {sub.public(rel): w["data"] for rel, w in sub.files.items() if "data" in w}
    forbidden = [sub.archive, sub.folder, sub.ref, sub.store, sub.family, sub.dest]
    kw.setdefault("calls_per_turn", 2)
    a.aud = ReactingAuditor(goal_list, question=sub.body, materials=sources, family=sub.family,
                            limits=rs.limits_of(sub), forbidden=forbidden, model=sub.model, **kw)
    a.fx = rs.provider(t, a.aud, label=a.label)
    a.aud.provider = a.fx.provider     # allowance and near-limit expectations from the fake's charges
    return a


def with_script(t, a, steps):
    a.fx = rs.provider(t, fp.Script(steps), label=a.label)
    return a


def pkg_name(sub, attempt):
    return PACKAGE_FMT % (sub.audit, attempt)


def pkg_path(sub, attempt, dest=None):
    return os.path.join(dest or sub.dest, pkg_name(sub, attempt))


def expected_package(entries, revision, *, audit_id, store, family_id, writer, actor, sealed_at):
    """member name -> expected bytes of a return package (INTERFACE 8.2, QUESTION-FORMS)."""
    aj = aw.answer_json(revision, entries)
    md = aw.render(entries)
    files = {"answer.json": aj}
    if md is not None:
        files["answer.md"] = md
    for e in entries:
        if e.kind == "record_artifact" and not e.unproduced:
            files[e.member] = e.data
    files["manifest.json"] = aw.manifest(audit_id, store, family_id, writer, actor, sealed_at, revision,
                                         aw.members(entries, aj, md), aw.unproduced(entries))
    return files


def set_expected(t, a, entries, revision, actor, sealed_at, name):
    """Fix the return the driver expects for a's seal. sealed_at is Stewart's (8.2: when it
    wrote the manifest); nothing else in the expectation comes from Stewart."""
    a.entries, a.revision, a.actor, a.sealed_at = list(entries), revision, actor, sealed_at
    ok = isinstance(sealed_at, str) and bool(AT_RE.match(sealed_at)) and isinstance(revision, int)
    if not t.check(name + ".witness-inputs", ok, {"sealed_at": sealed_at, "revision": revision}):
        a.files = None
        return
    a.files = expected_package(a.entries, revision, audit_id=a.sub.audit, store=a.sub.store,
                               family_id=a.sub.family + "/1", writer=t.bin["sha256"], actor=actor,
                               sealed_at=sealed_at)


def damaged(entries, ids, failure="damaged"):
    """The same selection with the entries in ids unproduced (8.1, QUESTION-FORMS)."""
    return [aw.Entry(e.id, e.version, e.kind, e.label, e.data, citations=e.citations, encoding=e.encoding,
                     unproduced=failure) if e.id in ids else e for e in entries]


def member_names(a):
    """verified_members of a complete attempt: manifest.json, then the manifest's members (8.3)."""
    if not a.files:
        return None
    return ["manifest.json"] + [m[0] for m in aw.members(a.entries, a.files["answer.json"], a.files.get("answer.md"))]


def unproduced_names(a):
    bad = [e.id for e in a.entries if e.unproduced]
    return bad + (["answer.md"] if bad else [])


def witness_revision(aud):
    """The answer revision (the number of entry records, 4.4) from the auditor's own account:
    every add or replace whose completed reply it saw, plus every add or replace it issued whose
    reply it never saw. Use only where every issued call was executed (an ordinary ending, a
    confirmed submit, or a kill after a response's blocks were all executed)."""
    seen = {r[0] for r in aud.replies}
    unseen = [c for c in aud.issued.values() if c["purpose"] in ("record", "replace") and c["id"] not in seen]
    return aud.mutations_done + len(unseen)


def witness_entry_count(aud):
    seen = {r[0]: r for r in aud.replies}
    n = 0
    for c in aud.issued.values():
        if c["purpose"] != "record":
            continue
        r = seen.get(c["id"])
        if r is None or r[2] == "completed":
            n += 1
    return n


def payload_path(sub, entry):
    """payload/<id>.v<version>.bin (INTERFACE 7.4)."""
    return os.path.join(sub.audit_dir, "payload", "%s.v%d.bin" % (entry.id, entry.version))


# ---------------------------------------------------------------------------
# Handles recomputed from the witness (INTERFACE 2.3).
# ---------------------------------------------------------------------------

def token_of(store, audit_id, kind, obj, manifest, record):
    return "%s.%s" % (obj, handle_check(store, audit_id, kind, obj, [sha256_hex(manifest), sha256_hex(record)]))


def seal_handle(store, audit_id, manifest):
    return "seal." + handle_check(store, audit_id, "seal", "seal", [sha256_hex(manifest)])


def log_record(t, sub, kind, pred=lambda b: True, last=False):
    """(name, raw, body) of the first (or last) log record of kind whose body satisfies pred."""
    found = None
    for r in t.read_log(sub):
        o = r["obj"]
        if isinstance(o, dict) and o.get("kind") == kind and isinstance(o.get("body"), dict) and pred(o["body"]):
            found = ("log/" + r["name"], r["raw"], o["body"])
            if not last:
                return found
    return found


def cf_token(t, a, attempt):
    """cf<n>.<check>: binds the witness manifest and the attempt's delivery_ended record (2.3, 8.4)."""
    rec = log_record(t, a.sub, "delivery_ended", lambda b: b.get("attempt") == attempt)
    if rec is None or not a.files:
        return None
    return token_of(a.sub.store, a.sub.audit, "cf", "cf%d" % attempt, a.manifest, rec[1])


def expected_losses(t, a, attempt):
    """Each loss of a verified_with_losses attempt whose members were unproduced at seal (8.4):
    the entry ID of each unproduced entry, then answer.md; loss IDs bind the witness manifest and
    the attempt's delivery_ended record."""
    rec = log_record(t, a.sub, "delivery_ended", lambda b: b.get("attempt") == attempt)
    out = []
    for e in a.entries or []:
        if e.unproduced:
            out.append((e.id, "entry", e.unproduced, e.id))
    if out:
        out.append(("answer.md", "rendering", "not_rendered", "answer-md"))
    res = []
    for member, role, failure, tok in out:
        loss = token_of(a.sub.store, a.sub.audit, "loss", "loss." + tok, a.manifest, rec[1]) \
            if (rec is not None and a.files) else None
        res.append({"loss": loss, "member": member, "role": role, "failure": failure, "stage": "seal"})
    return res


# ---------------------------------------------------------------------------
# Delivered packages.
# ---------------------------------------------------------------------------

def tree_digest(path):
    """[(name, sha256)] of a package directory's files, or None when it is gone."""
    try:
        names = sorted(os.listdir(path))
    except OSError:
        return None
    out = []
    for n in names:
        p = os.path.join(path, n)
        try:
            out.append((n, sha256_hex(read_bytes(p))))
        except OSError as exc:
            out.append((n, "unreadable: %s" % exc))
    return out


def check_self_verifying(t, name, path):
    """INTERFACE 8.2: the manifest verifies the package without the archive. The package holds
    exactly manifest.json and the manifest's members, each of the stated size and SHA-256."""
    try:
        raw = read_bytes(os.path.join(path, "manifest.json"))
        man = strict_loads(raw[:-1] if raw.endswith(b"\n") else raw)
    except (OSError, StrictJSONError) as exc:
        t.check(name + ".manifest", False, str(exc))
        return
    t.check(name + ".manifest-one-line", raw.endswith(b"\n") and raw.count(b"\n") == 1, raw[-40:])
    mem = man.get("members") if isinstance(man, dict) else None
    if not t.check(name + ".members-list", isinstance(mem, list) and all(isinstance(m, dict) for m in mem), mem):
        return
    names = [m.get("name") for m in mem]
    safe = all(isinstance(n, str) and n and "/" not in n and n not in (".", "..") for n in names)
    if not t.check(name + ".member-names", safe, names):
        return
    try:
        listing = sorted(os.listdir(path))
    except OSError as exc:
        t.check(name + ".listing", False, str(exc))
        return
    t.eq(name + ".exactly-listed", listing, sorted(["manifest.json"] + names))
    for m in mem:
        try:
            data = read_bytes(os.path.join(path, m["name"]))
        except OSError:
            data = None
        t.check(name + ".member." + m["name"], data is not None and len(data) == m.get("size")
                and sha256_hex(data) == m.get("sha256"),
                {"member": m, "got_size": None if data is None else len(data),
                 "got_sha256": None if data is None else sha256_hex(data)})


def rerender(path):
    """(answer.json re-serialized, answer.md re-rendered, error) from a delivered package's own
    answer.json and artifact members under the pinned rules (QUESTION-FORMS)."""
    try:
        raw = read_bytes(os.path.join(path, "answer.json"))
        obj = strict_loads(raw[:-1] if raw.endswith(b"\n") else raw)
        ents = []
        for e in obj["entries"]:
            if "unproduced" in e:
                u = e["unproduced"]
                ents.append(aw.Entry(e["id"], e["version"], e["kind"], e["label"], b"", unproduced=u["failure"],
                                     sha256=u["sha256"], size=u["size"]))
            elif e["kind"] == "record_artifact":
                data = read_bytes(os.path.join(path, e["member"]))
                ents.append(aw.Entry(e["id"], e["version"], e["kind"], e["label"], data, encoding=e["encoding"]))
            else:
                ents.append(aw.Entry(e["id"], e["version"], e["kind"], e["label"], e["text"].encode("utf-8"),
                                     citations=e.get("citations") or []))
        return raw, aw.answer_json(obj["revision"], ents), aw.render(ents), None
    except (OSError, StrictJSONError, KeyError, TypeError, AttributeError) as exc:
        return None, None, None, "%s: %s" % (type(exc).__name__, exc)


def check_rendering(t, name, path):
    """C5: the rendering is reproducible from the exact structured answer and elements; the
    structured answer follows its pinned serialization; an unproduced entry means no answer.md."""
    raw, again, md, err = rerender(path)
    if not t.check(name + ".decodable", err is None, err):
        return
    t.check(name + ".answer-canonical", raw == again, {"delivered": raw[:300], "reserialized": again[:300]})
    have = os.path.join(path, "answer.md")
    if md is None:
        t.check(name + ".not-rendered", not os.path.lexists(have), "answer.md delivered beside an unproduced entry")
    else:
        try:
            got = read_bytes(have)
        except OSError as exc:
            got = None
            t.check(name + ".reproduced", False, str(exc))
        if got is not None:
            t.check(name + ".reproduced", got == md, {"delivered": got[:300], "rendered": md[:300]})


def check_package_at(t, a, name, attempt, dest=None):
    """The package of this attempt equals the witness, verifies by its manifest alone and
    reproduces its rendering."""
    path = pkg_path(a.sub, attempt, dest)
    if not t.check(name + ".witness", a.files is not None, "no expected return (the seal was not observed)"):
        return path
    rs.check_package(t, path, a.files, name + ".package")
    check_self_verifying(t, name + ".manifest-verify", path)
    check_rendering(t, name + ".rendering", path)
    return path


# ---------------------------------------------------------------------------
# Commands.
# ---------------------------------------------------------------------------

def run_cmd(t, a, name, *, expect="completed", reason=None, fault=None, cwd=None, env=None, killed=False,
            mark=True, timeout=300):
    """stewart run REF against a's fake. killed: a fault kills it, so no reply is judged (1.6)."""
    fx = a.fx
    if fx is not None and mark:
        fx.mark(name)
    pre = locations_before(t, a)
    rep = t.cmd(["run", a.sub.ref], name=name, env=rs.run_env(t, fx, env), fault=fault, cwd=cwd,
                timeout=timeout, writer=a.sub.writer, envelope=not killed,
                expect=None if killed else expect, reason=None if killed else reason)
    if fx is not None and mark:
        rs.collect_protocol_timings(t, fx, name)
    if killed:
        t.eq(name + ".killed", rep.rc, -signal.SIGKILL)
        t.eq(name + ".no-reply", rep.stdout, b"")
    else:
        check_retained(t, a, name, rep, pre)
    return rep


def close_cmd(t, a, name, opts=(), *, expect="completed", reason=None, fault=None, cwd=None, env=None,
              killed=False, timeout=180):
    pre = locations_before(t, a)
    rep = t.cmd(["close", a.sub.ref] + list(opts), name=name, fault=fault, cwd=cwd, env=env, timeout=timeout,
                writer=a.sub.writer, envelope=not killed, expect=None if killed else expect,
                reason=None if killed else reason)
    if killed:
        t.eq(name + ".killed", rep.rc, -signal.SIGKILL)
        t.eq(name + ".no-reply", rep.stdout, b"")
    else:
        check_retained(t, a, name, rep, pre)
    return rep


# ---------------------------------------------------------------------------
# Retained locations (INTERFACE 1.3 as amended): a failed or refused manager reply lists every
# location the invocation created and kept. Judged by driver_core's T.check_retained against the
# driver's own listings taken around the command; packages new at a destination are passed as
# `outside`.
# ---------------------------------------------------------------------------

def locations_before(t, a):
    """The audit's location folders and every watched destination's entries, before a command."""
    dests = {}
    for p, w in t.watches.items():
        if w.get("mode") == "additions":
            try:
                dests[p] = set(os.listdir(p))
            except OSError:
                dests[p] = set()
    return {"audit": t.audit_locations(a.sub) if a.sub.audit else set(), "dests": dests, "live": t.writer_live()}


def new_packages(pre):
    """Entries that appeared at a watched destination since `pre` (packages, 8.2)."""
    out = []
    for d, names in pre["dests"].items():
        try:
            now = set(os.listdir(d))
        except OSError:
            continue
        out += [os.path.join(d, n) for n in sorted(now - names)]
    return out


def check_retained(t, a, name, rep, pre):
    if rep.outcome not in ("refused", "failed"):
        return
    if pre["live"] or t.writer_live():
        # Another Stewart process of this case was writing, so what this invocation created
        # cannot be told from the listings.
        t.skip_part(name + ".retained", "a background Stewart process was writing during the command")
        return
    t.check_retained(rep, a.sub, name, pre["audit"], outside=new_packages(pre))


def scenario(t, label, fn, *args, **kw):
    """Run one scenario of a case; a failed requirement or an unexpected exception ends only it."""
    try:
        return fn(t, *args, **kw)
    except Abort:
        return None
    except Skip:
        raise
    except Exception:
        t.check("driver.exception.%s" % label, False, traceback.format_exc()[-3000:])
        return None


def no_diag(effects):
    return {k: v for k, v in (effects or {}).items() if k != "diagnostic"}


def log_len(t, sub):
    return len(t.read_log(sub))


# ---------------------------------------------------------------------------
# Views: seal, delivery, close reply and status (pure checks over decoded replies).
# ---------------------------------------------------------------------------

def check_seal_view(t, name, view, a):
    """A seal as status, run and close show it (5.6): its handle binds the witness manifest."""
    if not t.check(name + ".present", isinstance(view, dict), view):
        return
    t.eq(name + ".keys", sorted(view), sorted(SEAL_VIEW_KEYS))
    sa = view.get("sealed_at")
    if getattr(a, "manifest_unreadable", False):
        # 5.6: "sealed_at (the manifest's)" and "unproduced, the names of the manifest's
        # unproduced members"; a fact that cannot be established is unknown, never a guess.
        t.eq(name + ".sealed_at", sa, "unknown")
    else:
        t.check(name + ".sealed_at", isinstance(sa, str) and bool(AT_RE.match(sa)), sa)
    if not a.files:
        return
    ms = sha256_hex(a.manifest)
    t.eq(name + ".actor", view.get("actor"), a.actor)
    t.eq(name + ".revision", view.get("revision"), a.revision)
    t.eq(name + ".manifest_sha256", view.get("manifest_sha256"), ms)
    t.eq(name + ".handle", view.get("handle"), seal_handle(a.sub.store, a.sub.audit, a.manifest))
    t.eq(name + ".unproduced", view.get("unproduced"),
         "unknown" if getattr(a, "manifest_unreadable", False) else unproduced_names(a))


def check_delivery_view(t, name, v, a, *, attempt, outcome, in_status=False, dest=None, by=None, source=None,
                        replaces="skip", token=None, verified="default", unverified=(), losses=(), cause="default",
                        location="default"):
    """One delivery attempt as run and close replies give it (5.7, 5.8), or as status lists it
    (5.6, in_status). cause: True (a cause with an error), False (null), or the error name."""
    if not t.check(name + ".present", isinstance(v, dict), v):
        return
    t.eq(name + ".keys", sorted(v), sorted(STATUS_DELIVERY_KEYS if in_status else RUN_DELIVERY_KEYS))
    t.eq(name + ".attempt", v.get("attempt"), attempt)
    t.eq(name + ".outcome", v.get("outcome"), outcome)
    if verified == "default":
        if outcome in ("verified", "verified_with_losses"):
            verified = member_names(a)
        elif outcome in ("failed", "name_taken"):
            verified = []
        else:
            verified = None
    if verified is not None:
        t.eq(name + ".verified_members", v.get("verified_members"), list(verified))
    if unverified is not None:
        t.eq(name + ".unverified_members", v.get("unverified_members"), list(unverified))
    if losses is not None:
        t.eq(name + ".losses", v.get("losses"), list(losses))
    if cause == "default":
        cause = outcome in ("partial", "failed", "name_taken")
    c = v.get("cause")
    if cause is True:
        t.check(name + ".cause", isinstance(c, dict) and isinstance(c.get("error"), str), c)
    elif cause is False:
        t.eq(name + ".cause", c, None)
    elif isinstance(cause, str):
        t.eq(name + ".cause.error", c.get("error") if isinstance(c, dict) else None, cause)
    if in_status:
        t.eq(name + ".package", v.get("package"), pkg_name(a.sub, attempt))
        t.eq(name + ".destination", v.get("destination"), dest or a.sub.dest)
        if by is not None:
            t.eq(name + ".by", v.get("by"), by)
        if source is not None:
            t.eq(name + ".destination_source", v.get("destination_source"), source)
        if replaces != "skip":
            t.eq(name + ".replaces", v.get("replaces"), replaces)
        t.eq(name + ".confirmation", v.get("confirmation"), token)
    else:
        if location == "default":
            # 4.4 delivery_ended.package: the package path, or null when none was created.
            location = pkg_path(a.sub, attempt, dest) if outcome in ("verified", "verified_with_losses", "partial") \
                else None
        t.eq(name + ".location", v.get("location"), location)


def argvs_of(obj):
    nxt = obj.get("next") if isinstance(obj, dict) else None
    return [n.get("argv") for n in nxt or [] if isinstance(n, dict) and isinstance(n.get("argv"), list)]


def commands_of(obj):
    return sorted({a[1] for a in argvs_of(obj) if len(a) > 1})


def has_confirm(obj, writer, ref, token, losses):
    """A next call `close REF --confirm TOKEN` naming each loss with --surrender (5.8)."""
    for a in argvs_of(obj):
        if a[:5] != [writer, "close", ref, "--confirm", token]:
            continue
        rest = a[5:]
        if len(rest) % 2:
            continue
        pairs = [(rest[i], rest[i + 1]) for i in range(0, len(rest), 2)]
        if all(p[0] == "--surrender" for p in pairs) and sorted(p[1] for p in pairs) == sorted(losses):
            return True
    return False


def offers_destination(obj):
    """The close call's explanation offers --destination DIR (5.7, 5.8, 8.3)."""
    nxt = obj.get("next") if isinstance(obj, dict) else None
    return any(isinstance(n, dict) and isinstance(n.get("argv"), list) and n["argv"][1:2] == ["close"]
               and "--destination" in str(n.get("why")) for n in nxt or [])


def check_close_obj(t, a, name, obj, *, closure, reason=None, effects=None, token=None, losses=(), outcome=None,
                    placement=None, already=False, actor=None, attempt=None, delivery=None, runs=None, holder=False,
                    surrendered=(), destination_offered=False):
    """A completed close reply after launch (5.8): effects, the data of its path, and next calls."""
    obj = obj if isinstance(obj, dict) else {}
    d = obj.get("data") if isinstance(obj.get("data"), dict) else {}
    if effects is not None:
        t.eq(name + ".effects", no_diag(obj.get("effects")), effects)
    t.eq(name + ".closure", d.get("closure"), closure)
    hl = d.get("headline") if isinstance(d.get("headline"), dict) else {}
    t.eq(name + ".headline.closed", hl.get("closed"), "yes" if closure == "complete" else "unfinished")
    if closure == "unfinished":
        t.eq(name + ".data-keys", sorted(d), sorted(CLOSE_UNFINISHED_KEYS))
        t.eq(name + ".unfinished_reason", d.get("unfinished_reason"), reason)
        t.eq(name + ".confirmation", d.get("confirmation"), token if reason == "awaiting_confirmation" else None)
        h = d.get("holder")
        if holder:
            t.check(name + ".holder", isinstance(h, dict) and isinstance(h.get("pid"), int), h)
        else:
            t.eq(name + ".holder", h, None)
    else:
        t.eq(name + ".data-keys", sorted(d), sorted(CLOSE_CLOSED_KEYS))
        t.eq(name + ".already_closed", d.get("already_closed"), already)
        t.eq(name + ".before_launch", d.get("before_launch"), False)
        t.eq(name + ".accepted", d.get("accepted"), True)
        ca = d.get("closed_at")
        t.check(name + ".closed_at", isinstance(ca, str) and bool(AT_RE.match(ca)), ca)
        t.eq(name + ".outcome", d.get("outcome"), outcome)
        t.eq(name + ".placement", d.get("placement"), placement)
        sur = d.get("surrendered")
        t.eq(name + ".surrendered", sorted(x.get("loss") for x in sur if isinstance(x, dict))
             if isinstance(sur, list) else sur, sorted(surrendered))
    if runs is not None:
        t.eq(name + ".runs", d.get("runs"), runs)
    seal = d.get("seal")
    if actor is not None:
        t.eq(name + ".seal.actor", seal.get("actor") if isinstance(seal, dict) else None, actor)
    if a is not None and a.files and isinstance(seal, dict):
        check_seal_view(t, name + ".seal", seal, a)
    dv = d.get("delivery") if isinstance(d.get("delivery"), dict) else {}
    if attempt is not None:
        t.eq(name + ".delivery.attempt", dv.get("attempt"), attempt)
    if delivery is not None:
        t.eq(name + ".delivery.outcome", dv.get("outcome"), delivery)
    if closure == "complete":
        t.eq(name + ".next", obj.get("next"), [])
    elif reason == "awaiting_confirmation":
        t.check(name + ".next.confirm", a is not None and has_confirm(obj, a.sub.writer, a.sub.ref, token, losses),
                {"next": obj.get("next"), "token": token, "losses": list(losses)})
        t.eq(name + ".next.commands", commands_of(obj), ["close", "status"])
    elif reason == "delivery_incomplete":
        t.eq(name + ".next.commands", commands_of(obj), ["close"])
        if destination_offered:
            t.check(name + ".next.offers-destination", offers_destination(obj), obj.get("next"))
    elif reason in ("run_still_held", "close_in_progress", "intake_still_running"):
        t.eq(name + ".next.commands", commands_of(obj), ["close", "status"])
    elif reason == "log_damaged":
        t.eq(name + ".next.commands", commands_of(obj), ["status"])


def check_status_obj(t, a, name, obj, *, condition, sealed="none", delivered=None, closed="no", runs_count=1,
                     held=False, last=None, answer=None, seal="skip", deliveries=None, closure=None, next_cmds=(),
                     confirm=None, allowances=True, destination_offered=False):
    """Status data (5.6) at one lifecycle point after launch, as distinct facts.

    last: None when the latest placement has no run_ended, else {ending, cause, recorded_by}.
    seal: None (no seal), 'skip', or the expected actor (checked against a's witness).
    deliveries: None for [], 'skip', or a list of check_delivery_view keyword dicts.
    closure: None (no close request), 'skip', or {unfinished_reason, outcome, placement,
    surrendered (loss IDs or None), closed (bool)}.
    allowances: True (from the fake's charges), False (skip) or the expected value."""
    obj = obj if isinstance(obj, dict) else {}
    d = obj.get("data") if isinstance(obj.get("data"), dict) else {}
    sub = a.sub
    t.eq(name + ".data-keys", list(d), list(STATUS_DATA_KEYS))
    t.eq(name + ".condition", d.get("condition"), condition)
    hl = d.get("headline") if isinstance(d.get("headline"), dict) else {}
    t.eq(name + ".headline.accepted", hl.get("accepted"), "yes")
    t.eq(name + ".headline.launched", hl.get("launched"), "yes")
    t.eq(name + ".headline.sealed", hl.get("sealed"), {"by": sealed})
    t.eq(name + ".headline.delivered", hl.get("delivered"), delivered if delivered is not None else UNVERIFIED)
    t.eq(name + ".headline.closed", hl.get("closed"), closed)
    t.check(name + ".summary", isinstance(d.get("summary"), str) and d["summary"].strip() != "", d.get("summary"))
    ev = d.get("evidence")
    t.check(name + ".evidence", isinstance(ev, list) and len(ev) > 0 and all(
        isinstance(e, dict) and set(e) == {"fact", "evidence"} and all(isinstance(x, str) and x for x in e.values())
        for e in ev), ev)
    runs = d.get("runs") if isinstance(d.get("runs"), dict) else {}
    t.eq(name + ".runs.keys", list(runs), ["count", "held", "holder", "last"])
    t.eq(name + ".runs.count", runs.get("count"), runs_count)
    t.eq(name + ".runs.held", runs.get("held"), held)
    if held:
        h = runs.get("holder")
        t.check(name + ".runs.holder", isinstance(h, dict) and isinstance(h.get("pid"), int), h)
    else:
        t.eq(name + ".runs.holder", runs.get("holder"), None)
    lst = runs.get("last") if isinstance(runs.get("last"), dict) else {}
    t.eq(name + ".runs.last.keys", list(lst), list(RUN_LAST_KEYS))
    t.eq(name + ".runs.last.number", lst.get("number"), runs_count)
    t.check(name + ".runs.last.started_at", isinstance(lst.get("started_at"), str)
            and bool(AT_RE.match(lst["started_at"])), lst.get("started_at"))
    if last is None:
        t.eq(name + ".runs.last.no-ending", [lst.get(k) for k in ("ending", "cause", "ended_at", "recorded_by")],
             [None] * 4)
    else:
        t.eq(name + ".runs.last.ending", [lst.get("ending"), lst.get("cause"), lst.get("recorded_by")],
             [last.get("ending"), last.get("cause"), last.get("recorded_by")])
        t.check(name + ".runs.last.ended_at", isinstance(lst.get("ended_at"), str)
                and bool(AT_RE.match(lst["ended_at"])), lst.get("ended_at"))
    if allowances is True and a.fx is not None:
        t.eq(name + ".allowances", d.get("allowances"), fp.allowances(a.fx.totals(), rs.limits_of(sub)))
    elif isinstance(allowances, dict):
        t.eq(name + ".allowances", d.get("allowances"), allowances)
    if answer is not None:
        t.eq(name + ".answer", d.get("answer"), answer)
    if seal is None:
        t.eq(name + ".seal", d.get("seal"), None)
    elif seal != "skip":
        sv = d.get("seal")
        t.eq(name + ".seal.actor", sv.get("actor") if isinstance(sv, dict) else None, seal)
        if a.files:
            check_seal_view(t, name + ".seal", sv, a)
    dl = d.get("deliveries")
    if deliveries is None:
        t.eq(name + ".deliveries", dl, [])
    elif deliveries != "skip":
        if t.eq(name + ".deliveries.count", len(dl) if isinstance(dl, list) else dl, len(deliveries)):
            for i, exp in enumerate(deliveries):
                check_delivery_view(t, "%s.deliveries.%d" % (name, i + 1), dl[i], a, in_status=True, **exp)
    cl = d.get("closure")
    if closure is None:
        t.eq(name + ".closure", cl, None)
    elif closure != "skip":
        if t.check(name + ".closure-keys", isinstance(cl, dict) and list(cl) == list(STATUS_CLOSURE_KEYS), cl):
            ra = cl["requested_at"]
            t.check(name + ".closure.requested_at", isinstance(ra, str) and bool(AT_RE.match(ra)), ra)
            t.eq(name + ".closure.before_launch", cl["before_launch"], False)
            t.eq(name + ".closure.accepted", cl["accepted"], True)
            t.eq(name + ".closure.unfinished_reason", cl["unfinished_reason"], closure.get("unfinished_reason"))
            if closure.get("closed"):
                ca = cl["closed_at"]
                t.check(name + ".closure.closed_at", isinstance(ca, str) and bool(AT_RE.match(ca)), ca)
            else:
                t.eq(name + ".closure.closed_at", cl["closed_at"], None)
            t.eq(name + ".closure.outcome", cl["outcome"], closure.get("outcome"))
            t.eq(name + ".closure.placement", cl["placement"], closure.get("placement"))
            sur = cl["surrendered"]
            want = closure.get("surrendered")
            t.eq(name + ".closure.surrendered",
                 sorted(x.get("loss") for x in sur if isinstance(x, dict)) if isinstance(sur, list) else sur,
                 sorted(want) if isinstance(want, (list, tuple)) else want)
    t.check(name + ".diagnostics", isinstance(d.get("diagnostics"), list), d.get("diagnostics"))
    t.eq(name + ".provider", [d.get("provider_url_override"), d.get("provider_proxy")],
         [a.fx.url if a.fx is not None else None, None])
    t.eq(name + ".receipt_line", d.get("receipt_line"), [sub.writer, "receipt", sub.ref])
    t.eq(name + ".next.commands", commands_of(obj), sorted(next_cmds))
    if confirm is not None:
        t.check(name + ".next.confirm", has_confirm(obj, sub.writer, sub.ref, confirm[0], confirm[1]),
                {"next": obj.get("next"), "token": confirm[0], "losses": confirm[1]})
    if destination_offered:
        t.check(name + ".next.offers-destination", offers_destination(obj), obj.get("next"))


def human_facts(data):
    """Actionable facts of status JSON that its human presentation must also carry: the seal's
    actor, the delivered package, every outstanding confirmation token, every loss ID and the
    readback route (5.6, C16 "Human and JSON presentations agree")."""
    facts = []
    hl = data.get("headline") if isinstance(data.get("headline"), dict) else {}
    by = (hl.get("sealed") or {}).get("by") if isinstance(hl.get("sealed"), dict) else None
    if by in ("auditor", "manager"):
        facts.append(by)
    dv = hl.get("delivered") if isinstance(hl.get("delivered"), dict) else {}
    if isinstance(dv.get("location"), str):
        facts.append(os.path.basename(dv["location"]))
    for x in dv.get("losses") or []:
        if isinstance(x, str):
            facts.append(x)
    for x in data.get("deliveries") or []:
        if isinstance(x, dict) and isinstance(x.get("confirmation"), str):
            facts.append(x["confirmation"])
    if data.get("receipt_line"):
        facts.append("receipt")
    return facts


def check_human_agrees(t, name, json_rc, data, human_rc, human_out):
    t.eq(name + ".human.exit", human_rc, json_rc)
    text = human_out.decode("utf-8", "replace")
    t.check(name + ".human.text", text.strip() != "" and not text.lstrip().startswith("{"), text[:200])
    low = text.lower()
    missing = [f for f in human_facts(data) if (f.lower() if f in ("auditor", "manager", "receipt") else f)
               not in (low if f in ("auditor", "manager", "receipt") else text)]
    t.check(name + ".human.agrees", not missing, {"missing": missing, "human": text[:1200]})


def status_point(t, a, name, *, human=True, again=False, cwd=None, **exp):
    """status REF (JSON, then human) at one lifecycle point; with again, a second status after
    time has passed must report the same facts (C16: elapsed time establishes nothing)."""
    rep = t.status(a.sub, name=name, cwd=cwd)
    check_status_obj(t, a, name, rep.obj, **exp)
    if human:
        hum = t.cmd(["status", a.sub.ref], json_reply=False, envelope=False, name=name + ".human", cwd=cwd)
        check_human_agrees(t, name, rep.rc, rep.data, hum.rc, hum.stdout)
    if again:
        time.sleep(1.2)
        rep2 = t.status(a.sub, name=name + ".later")
        t.eq(name + ".elapsed-time-invariant", rep2.data, rep.data)
    return rep


def status_seal(t, a, name):
    """Status's seal view, for a seal whose reply was lost (only its time is taken from it)."""
    rep = t.status(a.sub, name=name)
    sv = rep.data.get("seal")
    return sv if isinstance(sv, dict) else {}


# ---------------------------------------------------------------------------
# Common steps.
# ---------------------------------------------------------------------------

def run_ordinary(t, a, name, *, run_number=1):
    """A run whose auditor records its goals and ends its turn twice without submitting (T8)."""
    rep = run_cmd(t, a, name)
    t.require(name + ".completed", rep.outcome == "completed", rep.obj)
    rs.check_run_reply(t, rep, a.sub, name, ending="ended_unsubmitted", run_number=run_number, fx=a.fx,
                       limits=rs.limits_of(a.sub))
    t.eq(name + ".exit", rep.rc, 0)
    t.eq(name + ".effects.seal", rep.effects.get("seal"), "none")
    t.eq(name + ".delivery", rep.data.get("delivery"), None)
    if a.aud is not None:
        rs.check_auditor(t, a.aud, name)
        t.eq(name + ".reminder-once", a.aud.reminders_seen, 1)
    rs.check_fake(t, a.fx, name)
    return rep


def run_scripted_ending(t, a, name):
    """A fixed script that ends its turn until the run ends ended_unsubmitted (6.4, T8)."""
    rep = run_cmd(t, a, name)
    t.require(name + ".completed", rep.outcome == "completed", rep.obj)
    rs.check_run_reply(t, rep, a.sub, name, ending="ended_unsubmitted", run_number=1, fx=a.fx,
                       limits=rs.limits_of(a.sub))
    rs.check_fake(t, a.fx, name)
    return rep


def run_sealed(t, a, name, *, delivery="verified", run_number=1, cwd=None, env=None, fault=None):
    """A run whose auditor prepares, inspects both views and submits; the run delivers (6.3)."""
    rep = run_cmd(t, a, name, cwd=cwd, env=env, fault=fault)
    t.require(name + ".completed", rep.outcome == "completed", rep.obj)
    rs.check_run_reply(t, rep, a.sub, name, ending="sealed", run_number=run_number, fx=a.fx,
                       limits=rs.limits_of(a.sub), seal_actor="auditor", delivery_outcome=delivery)
    t.eq(name + ".exit", rep.rc, 0)
    rs.check_auditor(t, a.aud, name)
    rs.check_fake(t, a.fx, name)
    seal = rep.data.get("seal") if isinstance(rep.data.get("seal"), dict) else {}
    rev = witness_revision(a.aud)
    t.eq(name + ".seal.revision-witness", seal.get("revision"), rev)
    set_expected(t, a, a.aud.expected_selection(rev), rev, "auditor", seal.get("sealed_at"), name)
    check_seal_view(t, name + ".seal", seal, a)
    if a.files:
        fs = a.aud.final_selection or {}
        # C5: the auditor inspected exactly these bytes before confirming its submission.
        t.eq(name + ".inspected-before-submit", [fs.get("answer_json_sha256"), fs.get("answer_md_sha256")],
             [sha256_hex(a.files["answer.json"]), sha256_hex(a.files.get("answer.md", b""))])
    return rep


def manager_sealed(t, a, seal_view, name, entries, revision):
    """Close sealed the recorded selection with manager attribution (5.8, 8.1)."""
    sv = seal_view if isinstance(seal_view, dict) else {}
    t.eq(name + ".actor", sv.get("actor"), "manager")
    t.eq(name + ".revision", sv.get("revision"), revision)
    set_expected(t, a, entries, revision, "manager", sv.get("sealed_at"), name)
    check_seal_view(t, name, sv, a)


def confirm_and_close(t, a, name, token, *, losses=(), attempt=1, actor=None, placement="confirmed",
                      outcome="closed_delivered", delivery="verified"):
    opts = ["--confirm", token or "cf0.aaaaaa"]
    for x in losses:
        opts += ["--surrender", x]
    rep = close_cmd(t, a, name, opts)
    check_close_obj(t, a, name, rep.obj, closure="complete", outcome=outcome, placement=placement,
                    effects={"run": "ended", "seal": "existing", "delivery": delivery, "closure": "complete"},
                    actor=actor or a.actor, attempt=attempt, delivery=delivery, surrendered=losses)
    closed = log_record(t, a.sub, "closed", last=True)
    body = closed[2] if closed else {}
    t.eq(name + ".closed-record", [body.get("before_launch"), body.get("placement"), body.get("confirmation"),
                                   (body.get("seal") or {}).get("actor"), body.get("outcome")],
         [False, placement, token if placement == "confirmed" else None, actor or a.actor, outcome])
    return rep


def ended_record_name(t, sub):
    rec = log_record(t, sub, "run_ended", last=True)
    return rec[0] if rec else None


# ---------------------------------------------------------------------------
# C5: the delivered return.
# ---------------------------------------------------------------------------

@case("c5.package", ["C5", "C6", "C12", "C20"],
      "the delivered return equals the witness; differing answers differ only there; paths change nothing",
      needs=("loopback",),
      controls=[Control("drop_last_entry", [r"^c5\.pass\.package\.", r"^auditor\.view\."]),
                Control("deliver_conversation", [r"^c5\.pass\.package\.package-members",
                                                 r"^c5\.pass\.manifest-verify\.exactly-listed"]),
                Control("regenerate_rendering", [r"^c5\.pass\.package\.member-bytes\.answer\.md",
                                                 r"^c5\.pass\.manifest-verify\.member\.answer\.md",
                                                 r"^c5\.pass\.rendering\."]),
                Control("render_conclusion", [r"^c5\.pass\.package\.member-bytes\.answer\.md",
                                              r"^auditor\.view\.rendering"])])
def c_package(t):
    """Pass: the reacting auditor records five goals (a quoted and a ranged citation, a draft
    replaced, a text and a binary artifact), inspects both prepared views and submits; the run
    delivers attempt 1. The package holds exactly manifest.json, answer.json, answer.md and the
    two artifact members, each equal to the witness bytes, mode 0700/0600; it verifies from its
    own manifest; answer.md re-renders from the delivered answer.json and artifacts; the bytes
    are the ones the auditor read before confirming; the manifest digest the run printed at seal
    and status shows equals the delivered manifest's, and the seal handle binds it. Status says
    delivered_open; an ordinary close confirms placement (delivered_before_close) without a
    provider request or another copy. Differing: one byte changed in one entry's text changes
    answer.json and answer.md in exactly that entry. Invariance: the same goals with another
    archive, destination, working directory and HOME seal byte-identical answer.json, answer.md
    and artifacts; only the manifest's audit, store and seal time differ."""
    out = {}
    a = audit(t, "c5.pass")
    with_auditor(t, a, goals(a.sub))
    out["pass"] = scenario(t, "pass", deliver_and_close, a, "c5.pass")
    b = audit(t, "c5.differ")
    changed = ORDERING[:-1] + "!"
    with_auditor(t, b, goals(b.sub, ordering=changed))
    out["differ"] = scenario(t, "differ", deliver_and_close, b, "c5.differ")
    c = audit(t, "c5.same")
    with_auditor(t, c, goals(c.sub))
    out["same"] = scenario(t, "same", deliver_and_close, c, "c5.same", cwd=t.fresh_dir("c5 other cwd"),
                           env={"HOME": t.fresh_dir("c5 other home")})
    if out.get("pass") and out.get("differ"):
        pa, pb = out["pass"], out["differ"]
        old, new = aw.pinned_json_string(ORDERING).encode(), aw.pinned_json_string(changed).encode()
        aj_a, aj_b = rs.read_package_member(pa, "answer.json"), rs.read_package_member(pb, "answer.json")
        t.check("c5.differ.answer-differs-only-there", aj_a is not None and aj_a.count(old) == 1
                and aj_a.replace(old, new) == aj_b, {"pass": (aj_a or b"")[:400], "differ": (aj_b or b"")[:400]})
        md_a, md_b = rs.read_package_member(pa, "answer.md"), rs.read_package_member(pb, "answer.md")
        t.check("c5.differ.rendering-differs-only-there", md_a is not None and md_a.count(b"> " + ORDERING.encode()) == 1
                and md_a.replace(b"> " + ORDERING.encode(), b"> " + changed.encode()) == md_b,
                {"pass": (md_a or b"")[:400], "differ": (md_b or b"")[:400]})
    if out.get("pass") and out.get("same"):
        pa, pc = out["pass"], out["same"]
        names = sorted(n for n in (os.listdir(pa) if os.path.isdir(pa) else []) if n != "manifest.json")
        t.check("c5.same.members", names and names == sorted(n for n in os.listdir(pc) if n != "manifest.json")
                if os.path.isdir(pc) else False, names)
        for n in names:
            t.check("c5.same.bytes." + n, rs.read_package_member(pa, n) == rs.read_package_member(pc, n), n)


def deliver_and_close(t, a, name, cwd=None, env=None):
    """A sealed, delivered audit: package checks, status delivered_open, ordinary close."""
    rep = run_sealed(t, a, name + ".run", cwd=cwd, env=env)
    check_delivery_view(t, name + ".run.delivery", rep.data.get("delivery"), a, attempt=1, outcome="verified")
    path = check_package_at(t, a, name, 1)
    t.eq(name + ".destination", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    man = rs.read_package_member(path, "manifest.json")
    t.eq(name + ".printed-digest-is-delivered",
         (rep.data.get("seal") or {}).get("manifest_sha256"), sha256_hex(man) if man is not None else None)
    archived = rs.read_package_member(os.path.join(a.sub.audit_dir, "seal"), "manifest-1.json")
    t.eq(name + ".manifest-is-the-seal-manifest", man, archived)
    n_ex = len(a.fx.exchanges)
    loc = path
    status_point(t, a, name + ".status", condition="delivered_open", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": loc},
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"},
                 answer={"revision": a.revision, "entries": len(a.entries or [])}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="verified", by="run", source="commissioned", replaces=None)],
                 next_cmds=("close",))
    rep = close_cmd(t, a, name + ".close")
    check_close_obj(t, a, name + ".close", rep.obj, closure="complete", outcome="closed_delivered",
                    placement="delivered_before_close", attempt=1, delivery="verified", actor="auditor",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"},
                    runs={"count": 1, "held": False, "last_ending": "sealed"})
    t.eq(name + ".close.no-provider-request", len(a.fx.exchanges), n_ex)
    t.eq(name + ".close.no-second-copy", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    status_point(t, a, name + ".status-closed", condition="closed", sealed="auditor",
                 delivered={"verified": True, "confirmed": True, "location": loc}, closed="yes",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="verified", by="run", source="commissioned", replaces=None)],
                 closure={"unfinished_reason": None, "outcome": "closed_delivered",
                          "placement": "delivered_before_close", "surrendered": [], "closed": True},
                 next_cmds=())
    return path


@case("c5.partial-delivery", ["C5", "C6", "C8", "C16"],
      "a partial delivery keeps its package and names its missing member; close copies afresh; verification catches "
      "a corrupted member", mode="test", needs=("loopback",),
      controls=[Control("skip_delivery_verification", [r"^c5\.partial\.corrupt\."]),
                Control("remove_partial_package", [r"^c5\.partial\.kept\.", r"^inventory\."])])
def c_partial(t):
    """The run seals as the auditor; delivery.member_write:answer.md=eio makes attempt 1
    partial: manifest.json and answer.json written and verified (the witness bytes), answer.md
    named write_failed, cause given; the run still ends sealed. Status: sealed_undelivered, next
    close offering --destination. Close with delivery.member_corrupt:answer.json=corrupt makes
    attempt 2 (replaces 1) partial with answer.json not_verified: verification reads members
    back. Close again makes attempt 3 (replaces 2) verified, a complete copy equal to the
    witness, presented for confirmation (cf3): it was made after the close request. Packages 1
    and 2 keep their bytes throughout. Confirming closes with placement confirmed."""
    scenario(t, "partial", _partial, audit(t, "c5.partial"))


def _partial(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    rep = run_sealed(t, a, "c5.partial.run", delivery="partial", fault="delivery.member_write:answer.md=eio")
    check_delivery_view(t, "c5.partial.run.delivery", rep.data.get("delivery"), a, attempt=1, outcome="partial",
                        verified=["manifest.json", "answer.json"],
                        unverified=[{"name": "answer.md", "failure": "write_failed"}])
    t.check("c5.partial.run.offers-destination", offers_destination(rep.obj), rep.next)
    p1 = pkg_path(a.sub, 1)
    for n in ("manifest.json", "answer.json"):
        t.check("c5.partial.package-1." + n, a.files is not None and rs.read_package_member(p1, n) == a.files[n], n)
    kept1 = tree_digest(p1)
    t.check("c5.partial.package-1.kept", kept1 is not None, p1)
    status_point(t, a, "c5.partial.status", condition="sealed_undelivered", sealed="auditor",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="partial", by="run", source="commissioned", replaces=None,
                                  verified=["manifest.json", "answer.json"],
                                  unverified=[{"name": "answer.md", "failure": "write_failed"}])],
                 next_cmds=("close",), destination_offered=True)
    n_ex = len(a.fx.exchanges)
    rep = close_cmd(t, a, "c5.partial.corrupt.close", fault="delivery.member_corrupt:answer.json=corrupt")
    check_close_obj(t, a, "c5.partial.corrupt.close", rep.obj, closure="unfinished", reason="delivery_incomplete",
                    effects={"run": "ended", "seal": "existing", "delivery": "partial", "closure": "unfinished"},
                    actor="auditor", attempt=2, delivery="partial", destination_offered=True,
                    runs={"count": 1, "held": False, "last_ending": "sealed"})
    check_delivery_view(t, "c5.partial.corrupt.close.delivery", rep.data.get("delivery"), a, attempt=2,
                        outcome="partial", verified=["manifest.json", "answer.md"],
                        unverified=[{"name": "answer.json", "failure": "not_verified"}])
    t.eq("c5.partial.kept.001-after-2", tree_digest(p1), kept1)
    p2 = pkg_path(a.sub, 2)
    kept2 = tree_digest(p2)
    rep = close_cmd(t, a, "c5.partial.close")
    tok = cf_token(t, a, 3)
    check_close_obj(t, a, "c5.partial.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="auditor", attempt=3, delivery="verified")
    check_delivery_view(t, "c5.partial.close.delivery", rep.data.get("delivery"), a, attempt=3, outcome="verified")
    check_package_at(t, a, "c5.partial.copy-3", 3)
    t.eq("c5.partial.kept.001-after-3", tree_digest(p1), kept1)
    t.eq("c5.partial.kept.002-after-3", tree_digest(p2), kept2)
    t.eq("c5.partial.no-provider-request", len(a.fx.exchanges), n_ex)
    status_point(t, a, "c5.partial.status-awaiting", condition="awaiting_confirmation", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": pkg_path(a.sub, 3)}, closed="unfinished",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="partial", by="run", source="commissioned", replaces=None,
                                  verified=["manifest.json", "answer.json"],
                                  unverified=[{"name": "answer.md", "failure": "write_failed"}]),
                             dict(attempt=2, outcome="partial", by="close", source="commissioned", replaces=1,
                                  verified=["manifest.json", "answer.md"],
                                  unverified=[{"name": "answer.json", "failure": "not_verified"}]),
                             dict(attempt=3, outcome="verified", by="close", source="commissioned", replaces=2,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []))
    confirm_and_close(t, a, "c5.partial.confirm", tok, attempt=3)
    t.eq("c5.partial.kept.001-at-end", tree_digest(p1), kept1)
    t.eq("c5.partial.kept.002-at-end", tree_digest(p2), kept2)


@case("c5.t9-destination", ["C5", "C8", "C16", "C18"],
      "T9: an unavailable destination; close retries it, then copies to a replacement under --destination",
      mode="both", needs=("loopback",))
def c_t9(t):
    """T9. The commissioned destination is removed after commission. The auditor seals; the
    run's delivery attempt 1 fails (no package, a cause) and the run ends sealed. Status:
    sealed_undelivered, next close offering --destination. close: attempt 2 at the commissioned
    destination, replaces 1, fails; closure unfinished delivery_incomplete, no token, next close
    whose explanation offers --destination. --destination naming a missing path or a file is
    refused destination_invalid, publishing nothing. close --destination DIR: attempt 3, replaces
    2, destination_source replacement, verified in DIR/stewart-return-<audit>-003 with the
    witness bytes, token cf3. A further --destination is refused delivery_already_verified.
    Confirming closes. All three attempts stay recorded, the commissioned path is not
    recreated, and no close sends a provider request."""
    scenario(t, "t9", _t9, audit(t, "c5.t9"))


def _t9(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    t.driver_change("remove the commissioned destination after commission", lambda: os.rmdir(a.sub.dest))
    rep = run_sealed(t, a, "c5.t9.run", delivery="failed")
    check_delivery_view(t, "c5.t9.run.delivery", rep.data.get("delivery"), a, attempt=1, outcome="failed")
    fail1 = dict(attempt=1, outcome="failed", by="run", source="commissioned", replaces=None)
    status_point(t, a, "c5.t9.status", condition="sealed_undelivered", sealed="auditor",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor", deliveries=[fail1],
                 next_cmds=("close",), destination_offered=True)
    n_ex = len(a.fx.exchanges)
    rep = close_cmd(t, a, "c5.t9.close")
    check_close_obj(t, a, "c5.t9.close", rep.obj, closure="unfinished", reason="delivery_incomplete",
                    effects={"run": "ended", "seal": "existing", "delivery": "failed", "closure": "unfinished"},
                    actor="auditor", attempt=2, delivery="failed", destination_offered=True)
    check_delivery_view(t, "c5.t9.close.delivery", rep.data.get("delivery"), a, attempt=2, outcome="failed")
    fail2 = dict(attempt=2, outcome="failed", by="close", source="commissioned", replaces=1)
    n_log = log_len(t, a.sub)
    spec = t.mkdir("t9 specimens")
    a_file = os.path.join(spec, "not-a-directory")
    with open(a_file, "wb") as f:
        f.write(b"x\n")
    for label, d in (("missing", os.path.join(spec, "absent")), ("file", a_file)):
        close_cmd(t, a, "c5.t9.destination-" + label, ["--destination", d], expect="refused",
                  reason="destination_invalid")
    t.eq("c5.t9.refusals-published-nothing", log_len(t, a.sub), n_log)
    d2 = t.dest_path()
    t.watch(d2, "additions", "replacement destination")
    rep = close_cmd(t, a, "c5.t9.replace", ["--destination", d2])
    tok = cf_token(t, a, 3)
    check_close_obj(t, a, "c5.t9.replace", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="auditor", attempt=3, delivery="verified")
    check_delivery_view(t, "c5.t9.replace.delivery", rep.data.get("delivery"), a, attempt=3, outcome="verified",
                        dest=d2)
    check_package_at(t, a, "c5.t9.copy-3", 3, dest=d2)
    t.eq("c5.t9.replacement-holds-one-package", sorted(os.listdir(d2)), [pkg_name(a.sub, 3)])
    d3 = t.dest_path()
    t.watch(d3, "additions", "second replacement destination")
    close_cmd(t, a, "c5.t9.second-replacement", ["--destination", d3], expect="refused",
              reason="delivery_already_verified")
    t.eq("c5.t9.second-replacement-empty", os.listdir(d3), [])
    verified3 = dict(attempt=3, outcome="verified", by="close", source="replacement", replaces=2, dest=d2, token=tok)
    status_point(t, a, "c5.t9.status-awaiting", condition="awaiting_confirmation", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": pkg_path(a.sub, 3, d2)},
                 closed="unfinished", last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[fail1, fail2, verified3], closure={"unfinished_reason": "awaiting_confirmation"},
                 next_cmds=("close", "status"), confirm=(tok, []))
    confirm_and_close(t, a, "c5.t9.confirm", tok, attempt=3)
    t.eq("c5.t9.no-provider-request", len(a.fx.exchanges), n_ex)
    t.check("c5.t9.commissioned-not-recreated", not os.path.lexists(a.sub.dest), a.sub.dest)
    verified3["token"] = None
    status_point(t, a, "c5.t9.status-closed", condition="closed", sealed="auditor",
                 delivered={"verified": True, "confirmed": True, "location": pkg_path(a.sub, 3, d2)}, closed="yes",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[fail1, fail2, verified3],
                 closure={"unfinished_reason": None, "outcome": "closed_delivered", "placement": "confirmed",
                          "surrendered": [], "closed": True})


@case("c5.conflicting-package", ["C5", "C6", "C18"],
      "an existing path with the package's name is neither adopted, emptied nor overwritten",
      mode="both", needs=("loopback",))
def c_conflict(t):
    """A directory named stewart-return-<audit>-001 holding a file the driver planted already
    exists in the destination. The run's attempt 1 ends name_taken; attempt 2 (replaces 1)
    delivers verified to ...-002 with the witness bytes. The planted directory keeps exactly its
    file and bytes. An ordinary close then confirms the copy that existed before close."""
    scenario(t, "conflict", _conflict, audit(t, "c5.conflict"))


def _conflict(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    planted = pkg_path(a.sub, 1)

    def plant():
        os.mkdir(planted, 0o755)
        with open(os.path.join(planted, "planted.txt"), "wb") as f:
            f.write(b"Not Stewart's package.\n")
    t.driver_change("plant a directory with the first package's name", plant)
    before = tree_digest(planted)
    rep = run_sealed(t, a, "c5.conflict.run")
    # 5.7 "delivery, the attempt this run made": with two attempts, the newest.
    check_delivery_view(t, "c5.conflict.run.delivery", rep.data.get("delivery"), a, attempt=2, outcome="verified")
    check_package_at(t, a, "c5.conflict.copy-2", 2)
    t.eq("c5.conflict.planted-untouched", tree_digest(planted), before)
    loc = pkg_path(a.sub, 2)
    status_point(t, a, "c5.conflict.status", condition="delivered_open", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": loc},
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="name_taken", by="run", source="commissioned", replaces=None),
                             dict(attempt=2, outcome="verified", by="run", source="commissioned", replaces=1)],
                 next_cmds=("close",))
    rep = close_cmd(t, a, "c5.conflict.close")
    check_close_obj(t, a, "c5.conflict.close", rep.obj, closure="complete", outcome="closed_delivered",
                    placement="delivered_before_close", attempt=2, delivery="verified", actor="auditor",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
    t.eq("c5.conflict.planted-untouched-at-end", tree_digest(planted), before)


@case("c5.lost-run-reply", ["C5", "C8", "C16", "C17"],
      "a run killed after its verified delivery: status shows it; close confirms it without a second copy",
      mode="test", needs=("loopback",))
def c_lost_run_reply(t):
    """delivery.after_ended=kill kills the run after its delivery_ended (verified) and before
    run_ended and its reply. Status, from the records alone: delivered_open with the delivered
    location, the auditor's seal, no ending recorded for the run. close from another directory
    and HOME reconciles the run (interrupted, process_gone, by close) and closes on the copy
    that existed before the close request (delivered_before_close): no new attempt, no second
    package, the package equal to the witness."""
    scenario(t, "lost", _lost_run_reply, audit(t, "c5.lost"))


def _lost_run_reply(t, a):
    with_auditor(t, a, goals(a.sub))
    run_cmd(t, a, "c5.lost.run", fault="delivery.after_ended=kill", killed=True)
    rs.check_auditor(t, a.aud, "c5.lost.run")
    sv = status_seal(t, a, "c5.lost.seal")
    rev = witness_revision(a.aud)
    set_expected(t, a, a.aud.expected_selection(rev), rev, "auditor", sv.get("sealed_at"), "c5.lost.seal")
    loc = check_package_at(t, a, "c5.lost.copy-1", 1)
    status_point(t, a, "c5.lost.status", condition="delivered_open", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": loc}, last=None, seal="auditor",
                 answer={"revision": rev, "entries": witness_entry_count(a.aud)},
                 deliveries=[dict(attempt=1, outcome="verified", by="run", source="commissioned", replaces=None)],
                 next_cmds=("close",), again=True)
    rep = close_cmd(t, a, "c5.lost.close", cwd=t.fresh_dir("lost close cwd"),
                    env={"HOME": t.fresh_dir("lost close home")})
    check_close_obj(t, a, "c5.lost.close", rep.obj, closure="complete", outcome="closed_delivered",
                    placement="delivered_before_close", attempt=1, delivery="verified", actor="auditor",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"},
                    runs={"count": 1, "held": False, "last_ending": "interrupted"})
    t.eq("c5.lost.no-second-copy", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    t.eq("c5.lost.one-attempt", len(t.log_bodies(a.sub, "delivery_planned")), 1)
    ended = log_record(t, a.sub, "run_ended", last=True)
    body = ended[2] if ended else {}
    t.eq("c5.lost.reconciled", [body.get("ending"), body.get("cause"), body.get("recorded_by")],
         ["interrupted", "process_gone", "close"])
    t.eq("c5.lost.reconciled-usage", body.get("usage"), a.fx.totals())


@case("c5.t10-damaged-payload", ["C5", "C8", "C14", "C16"],
      "T10: a payload damaged after it was recorded is a named, surrendered loss, never delivered as good",
      mode="both", needs=("loopback",))
def c_t10(t):
    """T10. The auditor records five goals and ends ordinarily; the driver flips one bit of the
    observation's payload in the archive. close seals as manager: answer.json writes that entry
    unproduced {sha256, size, failure: damaged} with the recorded digest and size, no answer.md
    is produced and the manifest lists the entry and answer.md as unproduced; the delivery is
    verified_with_losses with token cf1 and loss IDs loss.<id>... and loss.answer-md...; the
    package equals the witness. --destination is refused delivery_already_verified (a new place
    repairs no missing bytes); --confirm alone, or naming one loss, is surrender_required; an
    unknown loss ID is handle_invalid; --surrender without --confirm is a usage error. Naming
    both closes with closed_with_surrendered_losses. Status then shows delivered.verified false
    with the loss IDs: never a complete delivery."""
    scenario(t, "t10", _t10, audit(t, "c5.t10"))


def _t10(t, a):
    with_auditor(t, a, goals(a.sub), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c5.t10.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    target = next((e for e in entries if e.label == "ordering"), None)
    t.require("c5.t10.target", target is not None, [e.label for e in entries])
    path = payload_path(a.sub, target)
    t.require("c5.t10.payload-recorded", rs.read_package_member(os.path.dirname(path), os.path.basename(path))
              == target.data, path)
    t.flip_bit(path, 0)
    close_damaged(t, a, "c5.t10", entries, rev, [target.id])


def close_damaged(t, a, name, entries, rev, bad_ids, confirm_status=True):
    """Close an audit whose selection has damaged payloads, then surrender the losses (T10)."""
    rep = close_cmd(t, a, name + ".close")
    manager_sealed(t, a, rep.data.get("seal"), name + ".close.seal", damaged(entries, bad_ids), rev)
    tok = cf_token(t, a, 1)
    losses = expected_losses(t, a, 1)
    ids = [x["loss"] for x in losses]
    check_close_obj(t, a, name + ".close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified_with_losses",
                             "closure": "unfinished"},
                    token=tok, losses=ids, actor="manager", attempt=1, delivery="verified_with_losses")
    check_delivery_view(t, name + ".close.delivery", rep.data.get("delivery"), a, attempt=1,
                        outcome="verified_with_losses", losses=losses)
    loc = check_package_at(t, a, name + ".copy-1", 1)
    t.check(name + ".no-answer-md", not os.path.lexists(os.path.join(loc, "answer.md")), loc)
    # The steps below confirm and surrender by these handles; without them they cannot be judged.
    t.require(name + ".handles-known", bool(tok) and bool(ids) and all(ids), {"token": tok, "losses": ids})
    with_losses = {"verified": False, "confirmed": False, "location": loc, "losses": ids}
    if confirm_status:
        status_point(t, a, name + ".status-awaiting", condition="awaiting_confirmation", sealed="manager",
                     delivered=with_losses, closed="unfinished", last=log_last(t, a.sub), seal="manager",
                     runs_count=runs_count(t, a.sub),
                     deliveries=[dict(attempt=1, outcome="verified_with_losses", by="close", source="commissioned",
                                      replaces=None, losses=losses, token=tok)],
                     closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                     confirm=(tok, ids))
    n_log = log_len(t, a.sub)
    d2 = t.dest_path()
    t.watch(d2, "additions", "replacement destination")
    close_cmd(t, a, name + ".replace-destination", ["--destination", d2], expect="refused",
              reason="delivery_already_verified")
    t.eq(name + ".replace-destination.nothing-copied", os.listdir(d2), [])
    rep = close_cmd(t, a, name + ".confirm-only", ["--confirm", tok or "cf1.aaaaaa"], expect="refused",
                    reason="surrender_required")
    t.check(name + ".confirm-only.losses", all(x and mentions(rep.data.get("losses"), x) for x in ids),
            rep.data.get("losses"))
    t.check(name + ".confirm-only.offers-every-loss", has_confirm(rep.obj, a.sub.writer, a.sub.ref, tok, ids),
            rep.next)
    if ids:
        close_cmd(t, a, name + ".surrender-one", ["--confirm", tok or "cf1.aaaaaa", "--surrender", ids[0] or "x"],
                  expect="refused", reason="surrender_required")
        close_cmd(t, a, name + ".surrender-unknown",
                  ["--confirm", tok or "cf1.aaaaaa", "--surrender", ids[0] or "x", "--surrender", "loss.e99.aaaaaa"],
                  expect="refused", reason="handle_invalid")
        r = t.cmd(["close", a.sub.ref, "--surrender", ids[0] or "x"], name=name + ".surrender-without-confirm",
                  envelope=False)
        t.eq(name + ".surrender-without-confirm.exit", r.rc, 2)
    t.eq(name + ".refusals-published-nothing", log_len(t, a.sub), n_log)
    confirm_and_close(t, a, name + ".confirm", tok, losses=ids, actor="manager",
                      outcome="closed_with_surrendered_losses", delivery="verified_with_losses")
    closed = log_record(t, a.sub, "closed", last=True)
    t.eq(name + ".closed-record.surrendered", (closed[2] if closed else {}).get("surrendered"), losses)
    st = t.status(a.sub, name=name + ".status-closed")
    check_status_obj(t, a, name + ".status-closed", st.obj, condition="closed", sealed="manager",
                     delivered=dict(with_losses, confirmed=True), closed="yes",
                     last=log_last(t, a.sub), seal="manager", runs_count=runs_count(t, a.sub),
                     deliveries=[dict(attempt=1, outcome="verified_with_losses", by="close", source="commissioned",
                                      replaces=None, losses=losses)],
                     closure={"unfinished_reason": None, "outcome": "closed_with_surrendered_losses",
                              "placement": "confirmed", "surrendered": ids, "closed": True})
    return ids


def log_last(t, sub):
    rec = log_record(t, sub, "run_ended", last=True)
    if rec is None:
        return None
    b = rec[2]
    return {"ending": b.get("ending"), "cause": b.get("cause"), "recorded_by": b.get("recorded_by")}


def runs_count(t, sub):
    return len(t.log_bodies(sub, "run_started"))


@case("c5.payload-corrupt-fault", ["C5", "C14"],
      "entry.payload_corrupt: payloads damaged as they were written are unproduced members, never good ones",
      mode="test", needs=("loopback",))
def c_payload_fault(t):
    """With entry.payload_corrupt=corrupt the run's payload files differ from the bytes the
    entries record. The auditor ends ordinarily (it never reads its entries). close seals as
    manager with exactly the entries whose payload file differs from the witness unproduced
    (damaged), delivers verified_with_losses and closes only when every loss is named."""
    scenario(t, "payload-fault", _payload_fault, audit(t, "c5.corrupt"))


def _payload_fault(t, a):
    with_auditor(t, a, goals(a.sub), finish="ordinary", after_reminder="end")
    rep = run_cmd(t, a, "c5.corrupt.run", fault="entry.payload_corrupt=corrupt")
    t.require("c5.corrupt.run.completed", rep.outcome == "completed", rep.obj)
    t.eq("c5.corrupt.run.ending", rep.data.get("ending"), "ended_unsubmitted")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    bad = []
    for e in entries:
        p = payload_path(a.sub, e)
        data = rs.read_package_member(os.path.dirname(p), os.path.basename(p))
        if data != e.data:
            bad.append(e.id)
    t.require("c5.corrupt.payloads-damaged", bool(bad), "no payload file differs from the witness")
    close_damaged(t, a, "c5.corrupt", entries, rev, bad)


@case("c5.unknown-membership", ["C5", "C8", "C16", "C20"],
      "a seal manifest that cannot be verified: membership unknown, delivery failed, never an empty return",
      mode="test", needs=("loopback",),
      controls=[Control("unknown_membership_empty", [r"^c5\.unknown\."])])
def c_unknown(t):
    """The auditor ends ordinarily; close is killed after its manager seal (close.after_seal),
    before delivery. Status: close_unfinished, sealed by the manager, no delivery,
    unfinished_reason delivery_incomplete; the archived seal manifest equals the witness. The
    driver flips one bit of seal/manifest-1.json. close: attempt 1 fails with membership unknown
    (cause manifest_unavailable), no package, no token, no loss IDs; closure unfinished
    delivery_incomplete. close --destination DIR fails the same way and DIR stays empty: a new
    place repairs no missing bytes. --confirm is refused. No closed record, no empty return."""
    scenario(t, "unknown", _unknown, audit(t, "c5.unknown"))


def _unknown(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c5.unknown.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    close_cmd(t, a, "c5.unknown.close-killed", fault="close.after_seal=kill", killed=True)
    sv = status_seal(t, a, "c5.unknown.seal")
    manager_sealed(t, a, sv, "c5.unknown.seal", entries, rev)
    status_point(t, a, "c5.unknown.status-sealed", condition="close_unfinished", sealed="manager",
                 closed="unfinished", last=log_last(t, a.sub), seal="manager",
                 closure={"unfinished_reason": "delivery_incomplete"}, next_cmds=("close", "status"))
    mpath = os.path.join(a.sub.audit_dir, "seal", "manifest-1.json")
    t.require("c5.unknown.archived-manifest", a.manifest is not None and
              rs.read_package_member(os.path.dirname(mpath), "manifest-1.json") == a.manifest, mpath)
    t.flip_bit(mpath, 20)
    a.manifest_unreadable = True
    rep = close_cmd(t, a, "c5.unknown.close")
    check_close_obj(t, a, "c5.unknown.close", rep.obj, closure="unfinished", reason="delivery_incomplete",
                    effects={"run": "ended", "seal": "existing", "delivery": "failed", "closure": "unfinished"},
                    actor="manager", attempt=1, delivery="failed")
    check_delivery_view(t, "c5.unknown.close.delivery", rep.data.get("delivery"), a, attempt=1, outcome="failed",
                        verified=[], cause="manifest_unavailable")
    t.eq("c5.unknown.no-package", os.listdir(a.sub.dest), [])
    fail1 = dict(attempt=1, outcome="failed", by="close", source="commissioned", replaces=None,
                 cause="manifest_unavailable", verified=[])
    status_point(t, a, "c5.unknown.status", condition="close_unfinished", sealed="manager", closed="unfinished",
                 last=log_last(t, a.sub), seal="manager", deliveries=[fail1],
                 closure={"unfinished_reason": "delivery_incomplete"}, next_cmds=("close", "status"),
                 destination_offered=True)
    d2 = t.dest_path()
    t.watch(d2, "additions", "replacement destination")
    rep = close_cmd(t, a, "c5.unknown.replace", ["--destination", d2])
    check_close_obj(t, a, "c5.unknown.replace", rep.obj, closure="unfinished", reason="delivery_incomplete",
                    effects={"run": "ended", "seal": "existing", "delivery": "failed", "closure": "unfinished"},
                    actor="manager", attempt=2, delivery="failed")
    t.eq("c5.unknown.replacement-empty", os.listdir(d2), [])
    n_log = log_len(t, a.sub)
    close_cmd(t, a, "c5.unknown.confirm", ["--confirm", "cf2.aaaaaa"], expect="refused",
              reason=("confirmation_mismatch", "handle_invalid"))
    t.eq("c5.unknown.confirm-published-nothing", log_len(t, a.sub), n_log)
    t.check("c5.unknown.not-closed", "closed" not in t.log_kinds(a.sub), t.log_kinds(a.sub))
    t.check("c5.unknown.no-verified-attempt", all(b.get("outcome") == "failed" for b in
                                                  t.log_bodies(a.sub, "delivery_ended")),
            t.log_bodies(a.sub, "delivery_ended"))


# ---------------------------------------------------------------------------
# C17 after launch: close's own write failures.
# ---------------------------------------------------------------------------

@case("c17.close-failures", ["C17", "C6", "C8", "C20"],
      "close's write failures and a lost close reply keep their causes, effects and retained partials",
      mode="test", needs=("loopback",))
def c_close_failures(t):
    """After an ordinary ending: close with prepared.write=eio fails (record_failed) with the
    original cause first, effects closure requested and no seal, retained archive locations, a
    durable diagnostic and next close. Close with seal.manifest_write=eio and diag.write=eio
    fails again with both causes, the original first, and diagnostic reported_only. Status
    between them: close_unfinished, nothing sealed, diagnostics listed. Close with
    reply.write=epipe does its work without a usable reply; status recovers the outstanding token
    and a repeat re-presents the same attempt without another. Confirming closes. Every retained
    path still exists at the end."""
    scenario(t, "close-failures", _close_failures, audit(t, "c17.close"))


def _close_failures(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c17.close.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    retained = []
    for label, fault, closure, diag in (("prepared-write", "prepared.write=eio", "requested", "durable"),
                                        ("manifest-write", "seal.manifest_write=eio,diag.write=eio", "unfinished",
                                         "reported_only")):
        name = "c17.close." + label
        # Appendix A: record_failed, "An archive write failed; effects state what is known" (5.8 names
        # no reason of its own for close's write failures).
        rep = close_cmd(t, a, name, fault=fault, expect="failed", reason="record_failed")
        eff = rep.effects
        t.eq(name + ".effects.run", eff.get("run"), "ended")
        t.check(name + ".effects.seal", eff.get("seal") in ("none", "unknown"), eff)
        t.eq(name + ".effects.delivery", eff.get("delivery"), "none")
        # 1.4 as amended: requested when this invocation published close_requested and its reply is
        # failed, whatever else it established; a later failing close reports unfinished.
        t.eq(name + ".effects.closure", eff.get("closure"), closure)
        t.eq(name + ".effects.diagnostic", eff.get("diagnostic"), diag)
        causes = rep.obj.get("causes") if isinstance(rep.obj, dict) else None
        t.check(name + ".causes.original-first", isinstance(causes, list) and causes and isinstance(causes[0], dict)
                and causes[0].get("error") == "EIO", causes)
        if diag == "reported_only":
            t.check(name + ".causes.diagnostic-second", isinstance(causes, list) and len(causes) >= 2, causes)
        # retained (1.3 as amended) is checked exactly by close_cmd against the locations the
        # inventories show this close created: its claimed preparation, any seal manifest it
        # claimed and its diagnostic when that was written.
        ret = rep.obj.get("retained") if isinstance(rep.obj, dict) else None
        retained += [p for p in ret or [] if isinstance(p, str)]
        t.check(name + ".next-close", [a.sub.writer, "close", a.sub.ref] in rep.next_argvs(), rep.next)
        st = status_point(t, a, name + ".status", condition="close_unfinished", sealed="none", closed="unfinished",
                          last=log_last(t, a.sub), seal=None, closure={"unfinished_reason": None},
                          next_cmds=("close", "status"))
        t.check(name + ".status.diagnostics", mentions(st.data.get("diagnostics"), "diag/"), st.data.get("diagnostics"))
    # 1.6: a missing reply is unknown, not a code; only the absence of the reply is judged here.
    rep = t.cmd(["close", a.sub.ref], name="c17.close.reply-lost", fault="reply.write=epipe", envelope=False,
                writer=a.sub.writer)
    t.eq("c17.close.reply-lost.no-reply", rep.stdout, b"")
    sv = status_seal(t, a, "c17.close.seal")
    manager_sealed(t, a, sv, "c17.close.seal", entries, rev)
    tok = cf_token(t, a, 1)
    loc = check_package_at(t, a, "c17.close.copy-1", 1)
    status_point(t, a, "c17.close.status-awaiting", condition="awaiting_confirmation", sealed="manager",
                 delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished",
                 last=log_last(t, a.sub), seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []))
    n_log = log_len(t, a.sub)
    rep = close_cmd(t, a, "c17.close.repeat")
    check_close_obj(t, a, "c17.close.repeat", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    t.eq("c17.close.repeat.published-nothing", log_len(t, a.sub), n_log)
    confirm_and_close(t, a, "c17.close.confirm", tok)
    t.check("c17.close.retained-kept", retained and all(os.path.lexists(p) for p in retained),
            [p for p in retained if not os.path.lexists(p)])


# ---------------------------------------------------------------------------
# C18 after launch: custody through close.
# ---------------------------------------------------------------------------

@case("c18.after-launch-custody", ["C18", "C5", "C6", "C15", "C16"],
      "originals read back after the sources are gone and after close; the delivered return verifies without the "
      "archive", needs=("loopback",))
def c_custody(t):
    """Disjoint folder, archive and destination. After acceptance the driver removes the
    original question and materials; every receipt item reads back the witness bytes. The
    reacting auditor drafts and replaces its account and submits; the run delivers. The archive
    holds only the 4.2 layout, the superseded draft payload stays with its bytes, and the
    archived seal manifest is the delivered manifest byte for byte. An ordinary close leaves the
    folder untouched; readback still verifies. With the archive moved away, status and receipt
    refuse archive_unavailable without recreating it, and the delivered package still verifies
    from its own manifest and equals the witness. Restored, status reports the same closed
    audit. An externally removed delivered member changes nothing status reports and causes no
    new copy."""
    scenario(t, "custody", _custody, audit(t, "c18"))


def _custody(t, a):
    sub = a.sub

    def lose():
        for rel in sorted(sub.files, reverse=True):
            os.unlink(os.path.join(sub.folder, "materials", rel.decode("utf-8")))
        os.unlink(os.path.join(sub.folder, "question.md"))
    t.driver_change("remove the original sources after acceptance", lose)
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "c18.readback-before")
    with_auditor(t, a, goals(sub))
    run_sealed(t, a, "c18.run")
    loc = check_package_at(t, a, "c18.copy-1", 1)
    acc = (a.aud.mem.entries or {}).get("account") or {}
    eid = acc.get("id")
    draft = os.path.join(sub.audit_dir, "payload", "%s.v1.bin" % eid)
    t.eq("c18.superseded-payload-kept", rs.read_package_member(os.path.dirname(draft), os.path.basename(draft)),
         DRAFT.encode("utf-8"))
    t.eq("c18.archived-manifest-is-delivered", rs.read_package_member(os.path.join(sub.audit_dir, "seal"),
                                                                      "manifest-1.json"),
         rs.read_package_member(loc, "manifest.json"))
    check_population(t, "c18.population", sub)
    rep = close_cmd(t, a, "c18.close")
    check_close_obj(t, a, "c18.close", rep.obj, closure="complete", outcome="closed_delivered",
                    placement="delivered_before_close", attempt=1, delivery="verified", actor="auditor",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
    for item, exp in sub.items().items():
        t.check_readback_ok(sub, item, exp, "c18.readback-after-close")
    check_population(t, "c18.population-after-close", sub)
    before = t.status(sub, name="c18.status-closed")
    t.eq("c18.status-closed.condition", before.data.get("condition"), "closed")
    moved = sub.archive + " (moved away)"
    t.driver_change("move the archive away", lambda: os.rename(sub.archive, moved))
    try:
        t.status(sub, name="c18.unavailable.status", expect="refused", reason="archive_unavailable")
        t.cmd(["receipt", sub.ref], name="c18.unavailable.receipt", expect="refused", reason="archive_unavailable")
        t.check("c18.unavailable.not-recreated", not os.path.lexists(sub.archive), sub.archive)
        check_self_verifying(t, "c18.unavailable.package-verifies", loc)
        rs.check_package(t, loc, a.files or {}, "c18.unavailable.package")
    finally:
        t.driver_change("restore the archive", lambda: os.rename(moved, sub.archive))
    again = t.status(sub, name="c18.restored.status")
    t.eq("c18.restored.same-facts", again.data, before.data)
    t.driver_change("remove a delivered member externally", lambda: os.unlink(os.path.join(loc, "answer.md")))
    after = t.status(sub, name="c18.external-removal.status")
    t.eq("c18.external-removal.same-facts", after.data, before.data)
    rep = close_cmd(t, a, "c18.external-removal.close")
    t.eq("c18.external-removal.close.already_closed", rep.data.get("already_closed"), True)
    t.eq("c18.external-removal.no-new-copy", sorted(os.listdir(sub.dest)), [pkg_name(sub, 1)])
    t.check("c18.folder-kept", os.path.isdir(os.path.join(sub.folder, "materials")), sub.folder)


def check_population(t, name, sub):
    """The archive holds the 4.2 layout and nothing else: STORE.json and audits/<id>/ with only
    the documented names; payloads, seal manifests, delivery plans and log records named as 4.2,
    4.4 and 7.4 state."""
    import re as _re
    try:
        t.eq(name + ".root", sorted(os.listdir(sub.archive)), ["STORE.json", "audits"])
        t.eq(name + ".audits", sorted(os.listdir(os.path.join(sub.archive, "audits"))), [sub.audit])
        names = sorted(os.listdir(sub.audit_dir))
    except OSError as exc:
        t.check(name + ".readable", False, str(exc))
        return
    t.check(name + ".audit-layout", set(names) <= set(AUDIT_LAYOUT), sorted(set(names) - set(AUDIT_LAYOUT)))
    pats = {"payload": r"e[1-9][0-9]*\.v[1-9][0-9]*(-[2-9]|-[1-9][0-9]+)?\.bin",
            "seal": r"manifest-[1-9][0-9]*\.json", "delivery": r"[1-9][0-9]*\.json", "log": r"[1-9][0-9]*\.json",
            "prepared": r"[1-9][0-9]*", "runs": r"[1-9][0-9]*"}
    for d, pat in pats.items():
        p = os.path.join(sub.audit_dir, d)
        listing = sorted(os.listdir(p)) if os.path.isdir(p) else []
        bad = [n for n in listing if not _re.fullmatch(pat, n)]
        t.check("%s.%s-names" % (name, d), not bad, bad)


# ---------------------------------------------------------------------------
# C8: close from every state.
# ---------------------------------------------------------------------------

@case("c8.close-every-state", ["C8", "C3", "C5", "C16", "C20"],
      "close before launch, after an ordinary ending (T8), after delivery, an interruption, an empty answer and "
      "a damaged log", needs=("loopback",),
      controls=[Control("skip_confirmation", [r"^c8\.t8\.close\."]),
                Control("empty_return_before_launch", [r"^c8\.before-launch\."])])
def c_close_every_state(t):
    """Before launch (accepted, never run): closed_before_launch, no seal, no delivery, nothing
    at the destination. Failed intake: closed without acceptance. T8: an ordinary ending, the
    reminder once, run refused authoring_ended (ordinary_ending, naming the run_ended record);
    before any copy, --destination is destination_not_replaceable and --confirm is refused; close
    seals as manager, delivers, and stays unfinished awaiting_confirmation with cf1 (a copy made
    by close needs confirmation); a repeat re-presents the same attempt and token publishing
    nothing; --destination is then delivery_already_verified and a wrong token refused;
    --confirm closes (placement confirmed); a repeat is already_closed; run is reference_closed.
    Differing: a copy delivered before the close request is confirmed by an ordinary close
    (delivered_before_close). An interruption (retry-after 61) is sealed by the manager with the
    entry it recorded. An empty answer gives an honest empty return. A damaged log after launch:
    status log_damaged, close unfinished log_damaged publishing nothing, run refused."""
    scenario(t, "before-launch", _before_launch)
    scenario(t, "failed-intake", _failed_intake)
    scenario(t, "t8", _t8, audit(t, "c8.t8"))
    scenario(t, "delivered", _delivered_before_close, audit(t, "c8.delivered"))
    scenario(t, "interrupted", _interrupted_close, audit(t, "c8.interrupted"))
    scenario(t, "empty", _empty_answer, audit(t, "c8.empty"))
    scenario(t, "damaged-log", _damaged_log, audit(t, "c8.damaged-log"))


def _before_launch(t):
    a = audit(t, "c8.before-launch", dest_watch="frozen")
    rep = close_cmd(t, a, "c8.before-launch.close")
    t.eq("c8.before-launch.effects", no_diag(rep.effects),
         {"run": "not_started", "seal": "none", "delivery": "none", "closure": "complete"})
    t.eq("c8.before-launch.data", [rep.data.get("closure"), rep.data.get("before_launch"), rep.data.get("accepted")],
         ["complete", True, True])
    kinds = t.log_kinds(a.sub)
    t.eq("c8.before-launch.log-tail", kinds[-2:], ["close_requested", "closed"])
    t.check("c8.before-launch.no-seal-or-delivery", not ({"seal", "delivery_planned", "delivery_ended"} & set(kinds)),
            kinds)
    t.eq("c8.before-launch.destination-empty", os.listdir(a.sub.dest), [])
    for d in ("seal", "prepared", "delivery", "payload", "runs"):
        p = os.path.join(a.sub.audit_dir, d)
        t.check("c8.before-launch.no-%s" % d, not os.path.exists(p) or not os.listdir(p), d)
    st = t.status(a.sub, name="c8.before-launch.status")
    t.check_status(st, a.sub, "c8.before-launch.status", condition="closed_before_launch", accepted="yes",
                   closed="yes")
    t.eq("c8.before-launch.status.next", st.next, [])


def _failed_intake(t):
    sub = t.submission(materials(), dest_watch="frozen")
    t.new_ref(sub, name="c8.failed-intake.new")
    t.prepare(sub, name="c8.failed-intake.prepare")
    t.edit(os.path.join(sub.folder, "materials", "a.py"), b"def send(r):\n    pass\n", note="change a.py")
    t.commission(sub, sub.handles[-1], name="c8.failed-intake.commission", expect="refused",
                 reason="selection_changed")
    rep = t.cmd(["close", sub.ref], name="c8.failed-intake.close", expect="completed", writer=sub.writer)
    t.eq("c8.failed-intake.data", [rep.data.get("closure"), rep.data.get("before_launch"), rep.data.get("accepted")],
         ["complete", True, False])
    closed = t.log_bodies(sub, "closed")
    t.eq("c8.failed-intake.outcome", (closed[-1] if closed else {}).get("outcome"), "closed_without_acceptance")
    st = t.status(sub, name="c8.failed-intake.status")
    t.check_status(st, sub, "c8.failed-intake.status", condition="closed_before_launch", accepted="no", closed="yes")
    t.eq("c8.failed-intake.destination-empty", os.listdir(sub.dest), [])


def _t8(t, a):
    with_auditor(t, a, goals(a.sub), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c8.t8.run")
    notices = t.log_bodies(a.sub, "notice")
    t.eq("c8.t8.reminder-record", [n.get("type") for n in notices if isinstance(n, dict)], ["reminder"])
    ended = log_record(t, a.sub, "run_ended", last=True)
    t.eq("c8.t8.run_ended", [(ended[2] if ended else {}).get(k) for k in ("ending", "cause", "recorded_by", "seal")],
         ["ended_unsubmitted", None, "run", None])
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    rep = run_cmd(t, a, "c8.t8.run-again", expect="refused", reason="authoring_ended", mark=False)
    t.eq("c8.t8.run-again.ended_by", [rep.data.get("ended_by"), rep.data.get("record")],
         ["ordinary_ending", ended[0] if ended else None])
    t.eq("c8.t8.run-again.effects", no_diag(rep.effects),
         {"run": "ended", "answer": "unchanged", "seal": "none", "delivery": "none"})
    t.check("c8.t8.run-again.next-close", [a.sub.writer, "close", a.sub.ref] in rep.next_argvs(), rep.next)
    status_point(t, a, "c8.t8.status", condition="ended_unsubmitted",
                 last={"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"},
                 answer={"revision": rev, "entries": len(entries)}, seal=None, next_cmds=("close",), again=True)
    n_log = log_len(t, a.sub)
    other = t.dest_path()
    t.watch(other, "frozen", "unused destination")
    close_cmd(t, a, "c8.t8.destination-before-copy", ["--destination", other], expect="refused",
              reason="destination_not_replaceable")
    close_cmd(t, a, "c8.t8.confirm-before-copy", ["--confirm", "cf1.aaaaaa"], expect="refused",
              reason=("confirmation_mismatch", "handle_invalid"))
    r = t.cmd(["close", a.sub.ref, "--surrender", "loss.e1.aaaaaa"], name="c8.t8.surrender-alone", envelope=False)
    t.eq("c8.t8.surrender-alone.exit", r.rc, 2)
    r = t.cmd(["close", a.sub.ref, "--confirm", "cf1.aaaaaa", "--destination", other],
              name="c8.t8.confirm-with-destination", envelope=False)
    t.eq("c8.t8.confirm-with-destination.exit", r.rc, 2)
    t.eq("c8.t8.options-published-nothing", log_len(t, a.sub), n_log)
    n_ex = len(a.fx.exchanges)
    rep = close_cmd(t, a, "c8.t8.close")
    manager_sealed(t, a, rep.data.get("seal"), "c8.t8.close.seal", entries, rev)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.t8.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified",
                    runs={"count": 1, "held": False, "last_ending": "ended_unsubmitted"})
    check_delivery_view(t, "c8.t8.close.delivery", rep.data.get("delivery"), a, attempt=1, outcome="verified")
    t.check("c8.t8.close.not-closed", "closed" not in t.log_kinds(a.sub), t.log_kinds(a.sub)[-4:])
    req = log_record(t, a.sub, "close_requested")
    t.eq("c8.t8.close.close_requested-flags", (req[2] if req else {}).get("flags"),
         {"confirm": None, "surrender": [], "destination": None})
    loc = check_package_at(t, a, "c8.t8.copy-1", 1)
    n_log = log_len(t, a.sub)
    rep = close_cmd(t, a, "c8.t8.repeat", cwd=t.fresh_dir("t8 repeat cwd"))
    check_close_obj(t, a, "c8.t8.repeat", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    t.eq("c8.t8.repeat.published-nothing", log_len(t, a.sub), n_log)
    t.eq("c8.t8.repeat.no-second-copy", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    close_cmd(t, a, "c8.t8.destination-after-copy", ["--destination", other], expect="refused",
              reason="delivery_already_verified")
    wrong = "cf1." + ("aaaaaa" if not tok or not tok.endswith("aaaaaa") else "bbbbbb")
    close_cmd(t, a, "c8.t8.wrong-token", ["--confirm", wrong], expect="refused",
              reason=("confirmation_mismatch", "handle_invalid"))
    close_cmd(t, a, "c8.t8.other-attempt-token", ["--confirm", "cf2" + (tok or "cf1.aaaaaa")[3:]], expect="refused",
              reason=("confirmation_mismatch", "handle_invalid"))
    t.eq("c8.t8.refusals-published-nothing", log_len(t, a.sub), n_log)
    status_point(t, a, "c8.t8.status-awaiting", condition="awaiting_confirmation", sealed="manager",
                 delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished",
                 last={"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}, seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []))
    confirm_and_close(t, a, "c8.t8.confirm", tok, actor="manager")
    t.eq("c8.t8.no-provider-request", len(a.fx.exchanges), n_ex)
    status_point(t, a, "c8.t8.status-closed", condition="closed", sealed="manager",
                 delivered={"verified": True, "confirmed": True, "location": loc}, closed="yes",
                 last={"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}, seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None)],
                 closure={"unfinished_reason": None, "outcome": "closed_delivered", "placement": "confirmed",
                          "surrendered": [], "closed": True})
    n_log = log_len(t, a.sub)
    rep = close_cmd(t, a, "c8.t8.again", ["--destination", other])
    check_close_obj(t, a, "c8.t8.again", rep.obj, closure="complete", already=True, outcome="closed_delivered",
                    placement="confirmed", actor="manager", attempt=1, delivery="verified")
    t.eq("c8.t8.again.published-nothing", log_len(t, a.sub), n_log)
    rep = run_cmd(t, a, "c8.t8.run-closed", expect="refused", reason="reference_closed", mark=False)
    t.check("c8.t8.run-closed.next", "close" in commands_of(rep.obj), rep.next)


def _delivered_before_close(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    rep = run_sealed(t, a, "c8.delivered.run")
    check_delivery_view(t, "c8.delivered.run.delivery", rep.data.get("delivery"), a, attempt=1, outcome="verified")
    check_package_at(t, a, "c8.delivered.copy-1", 1)
    rep = close_cmd(t, a, "c8.delivered.close")
    check_close_obj(t, a, "c8.delivered.close", rep.obj, closure="complete", outcome="closed_delivered",
                    placement="delivered_before_close", attempt=1, delivery="verified", actor="auditor",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
    closed = log_record(t, a.sub, "closed", last=True)
    t.eq("c8.delivered.closed-record", [(closed[2] if closed else {}).get(k) for k in ("placement", "confirmation")],
         ["delivered_before_close", None])
    t.eq("c8.delivered.one-package", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])


def _interrupted_close(t, a):
    text = "The materials show deliver before mark_sent."
    with_script(t, a, [record_step("toolu_i1", "first", text), fp.HttpError(529, retry_after="61")])
    rep = run_cmd(t, a, "c8.interrupted.run")
    rs.check_run_reply(t, rep, a.sub, "c8.interrupted.run", ending="interrupted", cause="provider_unavailable",
                       run_number=1, fx=a.fx, limits=rs.limits_of(a.sub))
    t.eq("c8.interrupted.run.exit", rep.rc, 5)
    rs.check_fake(t, a.fx, "c8.interrupted.run")
    status_point(t, a, "c8.interrupted.status", condition="interrupted",
                 last={"ending": "interrupted", "cause": "provider_unavailable", "recorded_by": "run"},
                 answer={"revision": 1, "entries": 1}, seal=None, next_cmds=("run", "close"))
    rep = close_cmd(t, a, "c8.interrupted.close")
    manager_sealed(t, a, rep.data.get("seal"), "c8.interrupted.close.seal", [observation("e1", "first", text)], 1)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.interrupted.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified",
                    runs={"count": 1, "held": False, "last_ending": "interrupted"})
    check_package_at(t, a, "c8.interrupted.copy-1", 1)
    confirm_and_close(t, a, "c8.interrupted.confirm", tok, actor="manager")
    run_cmd(t, a, "c8.interrupted.run-closed", expect="refused", reason="reference_closed", mark=False)


def _empty_answer(t, a):
    with_script(t, a, [end_step("Nothing to record yet."), end_step("Stopping.")])
    run_scripted_ending(t, a, "c8.empty.run")
    rep = close_cmd(t, a, "c8.empty.close")
    manager_sealed(t, a, rep.data.get("seal"), "c8.empty.close.seal", [], 0)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.empty.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    loc = check_package_at(t, a, "c8.empty.copy-1", 1)
    t.eq("c8.empty.answer", rs.read_package_member(loc, "answer.json"),
         b'{"schema":"stewart.answer/1","revision":0,"entries":[]}\n')
    t.eq("c8.empty.rendering", rs.read_package_member(loc, "answer.md"), b"No answer entries recorded.\n")
    confirm_and_close(t, a, "c8.empty.confirm", tok, actor="manager")


def _damaged_log(t, a):
    with_script(t, a, [end_step("Nothing to record."), end_step("Stopping.")])
    run_scripted_ending(t, a, "c8.damaged-log.run")
    n = log_len(t, a.sub)
    bad = os.path.join(a.sub.audit_dir, "log", "%d.json" % (n + 1))
    t.tampered_logs.add(a.sub.audit)

    def torn():
        with open(bad, "wb") as f:
            f.write(b'{"record":"stewart.record/1","kind":"clo')
    t.driver_change("write a torn log record after launch", torn)
    t.mode_exempt.add(bad)
    st = t.status(a.sub, name="c8.damaged-log.status")
    d = st.data
    hl = d.get("headline") if isinstance(d.get("headline"), dict) else {}
    t.eq("c8.damaged-log.status.condition", d.get("condition"), "log_damaged")
    t.eq("c8.damaged-log.status.accepted", hl.get("accepted"), "yes")
    t.check("c8.damaged-log.status.launched", hl.get("launched") in ("yes", "unknown"), hl.get("launched"))
    # 5.6: a headline value depending on the unreadable part is unknown; verified and confirmed are
    # the string unknown on a damaged log. A seal or a close record could be in the damaged part.
    t.eq("c8.damaged-log.status.sealed", hl.get("sealed"), {"by": "unknown"})
    t.eq("c8.damaged-log.status.delivered", hl.get("delivered"), {"verified": "unknown", "confirmed": "unknown"})
    t.eq("c8.damaged-log.status.closed", hl.get("closed"), "unknown")
    t.check("c8.damaged-log.status.names-record", mentions(d.get("diagnostics"), "%d.json" % (n + 1)),
            d.get("diagnostics"))
    t.check("c8.damaged-log.status.next-receipt", "receipt" in commands_of(st.obj), st.next)
    names = sorted(os.listdir(os.path.join(a.sub.audit_dir, "log")))
    rep = close_cmd(t, a, "c8.damaged-log.close")
    t.eq("c8.damaged-log.close.reason", [rep.data.get("closure"), rep.data.get("unfinished_reason")],
         ["unfinished", "log_damaged"])
    t.eq("c8.damaged-log.close.effects", no_diag(rep.effects),
         {"run": "unknown", "seal": "unknown", "delivery": "unknown", "closure": "unknown"})
    t.check("c8.damaged-log.close.bad_records", mentions(rep.data.get("bad_records"), "%d.json" % (n + 1)),
            rep.data.get("bad_records"))
    t.eq("c8.damaged-log.close.next", commands_of(rep.obj), ["status"])
    t.eq("c8.damaged-log.close.published-nothing", sorted(os.listdir(os.path.join(a.sub.audit_dir, "log"))), names)
    t.eq("c8.damaged-log.close.nothing-delivered", os.listdir(a.sub.dest), [])
    run_cmd(t, a, "c8.damaged-log.run-again", expect="refused", reason="log_damaged", mark=False)


@case("c8.close-faults", ["C8", "C16", "C17", "C3"],
      "close killed after its request, after its seal, after delivery (T14) and after closed; a run killed after "
      "its seal or before its first request", mode="test", needs=("loopback",))
def c_close_faults(t):
    """close.after_requested: status close_unfinished with no reason (the last close stopped
    before recording more); run refuses reference_closed; close continues to a manager seal and
    a copy for confirmation. close.after_seal: status shows the manager seal and
    delivery_incomplete; close delivers without sealing again. T14: delivery.after_ended kills
    close after its verified delivery; status shows awaiting_confirmation and cf1; close from
    another directory and HOME re-presents the same attempt and token without another attempt;
    --confirm with close.after_closed_link kills after closed; status says closed; close returns
    already_closed with the recorded outcome. seal.after_link kills the run after the auditor's
    seal: status sealed_undelivered; run refuses authoring_ended (seal); close reconciles the run,
    keeps the auditor's seal and delivers for confirmation. run.after_started kills before the
    first request: still launched, and close seals an empty selection as manager: an honest
    empty return."""
    scenario(t, "after-requested", _after_requested, audit(t, "c8.after-requested"))
    scenario(t, "after-seal", _after_seal, audit(t, "c8.after-seal"))
    scenario(t, "t14", _t14, audit(t, "c8.t14"))
    scenario(t, "sealed-killed", _sealed_killed, audit(t, "c8.sealed-killed"))
    scenario(t, "after-started", _after_started, audit(t, "c8.after-started"))


def _after_requested(t, a):
    with_script(t, a, [end_step("Nothing yet."), end_step("Stopping.")])
    run_scripted_ending(t, a, "c8.after-requested.run")
    close_cmd(t, a, "c8.after-requested.close", fault="close.after_requested=kill", killed=True)
    t.eq("c8.after-requested.log-tail", t.log_kinds(a.sub)[-1:], ["close_requested"])
    status_point(t, a, "c8.after-requested.status", condition="close_unfinished", closed="unfinished",
                 last={"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}, seal=None,
                 closure={"unfinished_reason": None}, next_cmds=("close", "status"))
    run_cmd(t, a, "c8.after-requested.run-again", expect="refused", reason="reference_closed", mark=False)
    rep = close_cmd(t, a, "c8.after-requested.continue")
    manager_sealed(t, a, rep.data.get("seal"), "c8.after-requested.continue.seal", [], 0)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.after-requested.continue", rep.obj, closure="unfinished",
                    reason="awaiting_confirmation", token=tok, actor="manager", attempt=1, delivery="verified",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"})
    t.eq("c8.after-requested.one-request", t.log_kinds(a.sub).count("close_requested"), 1)
    check_package_at(t, a, "c8.after-requested.copy-1", 1)
    confirm_and_close(t, a, "c8.after-requested.confirm", tok)


def _after_seal(t, a):
    text = "Recorded before the run stopped."
    with_script(t, a, [record_step("toolu_a1", "kept", text), end_step("Done."), end_step("Stopping.")])
    run_scripted_ending(t, a, "c8.after-seal.run")
    close_cmd(t, a, "c8.after-seal.close", fault="close.after_seal=kill", killed=True)
    sv = status_seal(t, a, "c8.after-seal.seal")
    manager_sealed(t, a, sv, "c8.after-seal.seal", [observation("e1", "kept", text)], 1)
    t.eq("c8.after-seal.archived-manifest", rs.read_package_member(os.path.join(a.sub.audit_dir, "seal"),
                                                                   "manifest-1.json"), a.manifest)
    status_point(t, a, "c8.after-seal.status", condition="close_unfinished", sealed="manager", closed="unfinished",
                 last={"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}, seal="manager",
                 closure={"unfinished_reason": "delivery_incomplete"}, next_cmds=("close", "status"))
    rep = close_cmd(t, a, "c8.after-seal.continue")
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.after-seal.continue", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    token=tok, actor="manager", attempt=1, delivery="verified",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"})
    t.eq("c8.after-seal.one-seal", t.log_kinds(a.sub).count("seal"), 1)
    check_package_at(t, a, "c8.after-seal.copy-1", 1)
    confirm_and_close(t, a, "c8.after-seal.confirm", tok)


def _t14(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c8.t14.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    n0 = log_len(t, a.sub)
    close_cmd(t, a, "c8.t14.close", fault="delivery.after_ended=kill", killed=True)
    t.eq("c8.t14.published", t.log_kinds(a.sub)[n0:], ["close_requested", "seal", "delivery_planned",
                                                       "delivery_ended"])
    sv = status_seal(t, a, "c8.t14.seal")
    manager_sealed(t, a, sv, "c8.t14.seal", entries, rev)
    tok = cf_token(t, a, 1)
    loc = check_package_at(t, a, "c8.t14.copy-1", 1)
    last = {"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}
    status_point(t, a, "c8.t14.status", condition="awaiting_confirmation", sealed="manager",
                 delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished", last=last,
                 seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []), again=True)
    n_log = log_len(t, a.sub)
    rep = close_cmd(t, a, "c8.t14.repeat", cwd=t.fresh_dir("t14 cwd"), env={"HOME": t.fresh_dir("t14 home")})
    check_close_obj(t, a, "c8.t14.repeat", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    t.eq("c8.t14.repeat.published-nothing", log_len(t, a.sub), n_log)
    t.eq("c8.t14.repeat.no-second-copy", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    close_cmd(t, a, "c8.t14.confirm", ["--confirm", tok or "cf1.aaaaaa"], fault="close.after_closed_link=kill",
              killed=True)
    t.eq("c8.t14.closed-linked", t.log_kinds(a.sub)[-1:], ["closed"])
    status_point(t, a, "c8.t14.status-closed", condition="closed", sealed="manager",
                 delivered={"verified": True, "confirmed": True, "location": loc}, closed="yes", last=last,
                 seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None)],
                 closure={"unfinished_reason": None, "outcome": "closed_delivered", "placement": "confirmed",
                          "surrendered": [], "closed": True})
    n_log = log_len(t, a.sub)
    rep = close_cmd(t, a, "c8.t14.after", cwd=t.fresh_dir("t14 after cwd"))
    check_close_obj(t, a, "c8.t14.after", rep.obj, closure="complete", already=True, outcome="closed_delivered",
                    placement="confirmed", actor="manager", attempt=1, delivery="verified",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "complete"})
    t.eq("c8.t14.after.published-nothing", log_len(t, a.sub), n_log)


def _sealed_killed(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    run_cmd(t, a, "c8.sealed-killed.run", fault="seal.after_link=kill", killed=True)
    rs.check_auditor(t, a.aud, "c8.sealed-killed.run")
    sv = status_seal(t, a, "c8.sealed-killed.seal")
    rev = witness_revision(a.aud)
    set_expected(t, a, a.aud.expected_selection(rev), rev, "auditor", sv.get("sealed_at"), "c8.sealed-killed.seal")
    status_point(t, a, "c8.sealed-killed.status", condition="sealed_undelivered", sealed="auditor", last=None,
                 seal="auditor", next_cmds=("close",))
    seal_rec = log_record(t, a.sub, "seal")
    rep = run_cmd(t, a, "c8.sealed-killed.run-again", expect="refused", reason="authoring_ended", mark=False)
    t.eq("c8.sealed-killed.run-again.ended_by", [rep.data.get("ended_by"), rep.data.get("record")],
         ["seal", seal_rec[0] if seal_rec else None])
    n_ex = len(a.fx.exchanges)
    rep = close_cmd(t, a, "c8.sealed-killed.close")
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.sealed-killed.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="auditor", attempt=1, delivery="verified",
                    runs={"count": 1, "held": False, "last_ending": "interrupted"})
    t.eq("c8.sealed-killed.no-provider-request", len(a.fx.exchanges), n_ex)
    ended = log_record(t, a.sub, "run_ended", last=True)
    t.eq("c8.sealed-killed.reconciled", [(ended[2] if ended else {}).get(k) for k in ("ending", "cause", "recorded_by")],
         ["interrupted", "process_gone", "close"])
    check_package_at(t, a, "c8.sealed-killed.copy-1", 1)
    confirm_and_close(t, a, "c8.sealed-killed.confirm", tok, actor="auditor")


def _after_started(t, a):
    with_script(t, a, [])
    run_cmd(t, a, "c8.after-started.run", fault="run.after_started=kill", killed=True)
    t.eq("c8.after-started.no-request", len(a.fx.exchanges), 0)
    status_point(t, a, "c8.after-started.status", condition="interrupted", last=None,
                 answer={"revision": 0, "entries": 0}, seal=None, next_cmds=("run", "close"))
    rep = close_cmd(t, a, "c8.after-started.close")
    manager_sealed(t, a, rep.data.get("seal"), "c8.after-started.close.seal", [], 0)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.after-started.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    ended = log_record(t, a.sub, "run_ended", last=True)
    body = ended[2] if ended else {}
    t.eq("c8.after-started.reconciled", [body.get(k) for k in ("ending", "cause", "recorded_by")],
         ["interrupted", "process_gone", "close"])
    zero = {k: {"reported": 0, "estimated": 0} for k in ("turns", "input_tokens", "output_tokens")}
    t.eq("c8.after-started.reconciled-usage", body.get("usage"), zero)
    check_package_at(t, a, "c8.after-started.copy-1", 1)
    confirm_and_close(t, a, "c8.after-started.confirm", tok)


@case("c8.close-running", ["C8", "C12", "C16", "C3"],
      "T13: close stops a held run; a stopped holder leaves close run_still_held; a seal alone is not a stop",
      mode="test", needs=("loopback", "lock"),
      linux_reason="a live run is observed through its OFD lock and close waits on it, a Linux-only expectation",
      controls=[Control("seal_as_stopped", [r"^c8\.held-sealed\.close\."])])
def c_close_running(t):
    """T13. Run A records an entry and stalls in its second provider request. Status: run_active
    with the holder's run_started observations; a second run refuses run_held naming the holder.
    close publishes close_requested; run A observes it, aborts the request (aborted_by_close,
    charged an estimate), ends stopped_by_close and exits 0; close then seals the recorded entry
    as manager, delivers and awaits confirmation. With run A SIGSTOPped in a stalled request,
    close waits about 30 s and replies unfinished run_still_held with the holder; status shows the
    held run and that reason; after SIGCONT the run stops by close and a later close resumes. A
    run that has sealed and is paused in delivery still holds the lock: close waits and replies
    run_still_held (effects.run still_held, the auditor's seal existing), never treating the seal
    as stopped execution; released, the run delivers and ends sealed, and close presents that
    copy for confirmation because it was made after the close request."""
    scenario(t, "t13", _t13, audit(t, "c8.t13"))
    scenario(t, "t13-stopped", _t13_stopped, audit(t, "c8.t13-stopped"))
    scenario(t, "held-sealed", _held_sealed, audit(t, "c8.held-sealed"))


def _started_observations(t, sub):
    rec = log_record(t, sub, "run_started", last=True)
    return (rec[2] if rec else {}).get("observations")


def _attempt_body(sub, run, request, attempt=1):
    rd = rs.run_dirs(sub).get(run)
    rec = rd.attempts.get((request, attempt)) if rd is not None else None
    return rec.get("body") if isinstance(rec, dict) and isinstance(rec.get("body"), dict) else {}


def attempt_unrecorded(sub, run, request, attempt=1):
    """The request's capture exists and the attempt has no record yet (4.5)."""
    d = os.path.join(sub.audit_dir, "runs", str(run))
    return (os.path.isfile(os.path.join(d, "request-%d.json" % request))
            and not os.path.lexists(os.path.join(d, "attempt-%d-%d.json" % (request, attempt))))


def _t13(t, a):
    text = "Recorded before close."
    with_script(t, a, [record_step("toolu_t1", "first", text), fp.Stall(120)])
    h = rs.start_run(t, a.sub, a.fx, name="c8.t13.run", timeout=300)
    stalled = rs.wait_for(lambda: len(a.fx.exchanges) >= 2 and a.fx.exchanges[1].outcome == "stalled", 60)
    t.require("c8.t13.stalled", stalled, [e.outcome for e in a.fx.exchanges])
    obs = _started_observations(t, a.sub)
    t.check("c8.t13.observations-pid", isinstance(obs, dict) and obs.get("pid") == h["proc"].p.pid, obs)
    st = status_point(t, a, "c8.t13.status-held", condition="run_active", held=True, last=None, seal=None,
                      allowances=fp.allowances(a.fx.totals(upto=1), rs.limits_of(a.sub)),
                      next_cmds=("close", "status"))
    t.eq("c8.t13.status-held.holder", (st.data.get("runs") or {}).get("holder"), obs)
    # 5.6, 6.4 (a1515e7): a live placement counts only its attempt records; the request still in
    # flight has none yet, so the expected allowances above leave it out. Witness that it has none.
    t.check("c8.t13.status-held.in-flight-unrecorded", attempt_unrecorded(a.sub, 1, 2), sorted(
        os.listdir(os.path.join(a.sub.audit_dir, "runs", "1"))))
    rep = t.cmd(["run", a.sub.ref], name="c8.t13.second-run", env=rs.run_env(t, a.fx), expect="refused",
                reason="run_held", writer=a.sub.writer)
    t.eq("c8.t13.second-run.holder", [rep.data.get("run"), rep.data.get("holder")], [1, obs])
    # 1.4: still_held, "a placement still holds the active lock"; a refusal changes nothing (5.7).
    t.eq("c8.t13.second-run.effects", no_diag(rep.effects),
         {"run": "still_held", "answer": "unchanged", "seal": "none", "delivery": "none"})
    t.check("c8.t13.second-run.next", commands_of(rep.obj) == ["close", "status"], rep.next)
    rep = close_cmd(t, a, "c8.t13.close", timeout=120)
    manager_sealed(t, a, rep.data.get("seal"), "c8.t13.close.seal", [observation("e1", "first", text)], 1)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.t13.close", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified",
                    runs={"count": 1, "held": False, "last_ending": "stopped_by_close"})
    rr = rs.finish_run(t, h, expect="completed")
    rs.check_run_reply(t, rr, a.sub, "c8.t13.run", ending="stopped_by_close", run_number=1, fx=a.fx,
                       limits=rs.limits_of(a.sub))
    t.eq("c8.t13.run.exit", rr.rc, 0)
    att = _attempt_body(a.sub, 1, 2)
    t.eq("c8.t13.aborted-attempt", [att.get("outcome"), (att.get("charged") or {}).get("basis")],
         ["aborted_by_close", "estimated"])
    check_package_at(t, a, "c8.t13.copy-1", 1)
    confirm_and_close(t, a, "c8.t13.confirm", tok)


def _t13_stopped(t, a):
    with_script(t, a, [fp.Stall(180)])
    h = rs.start_run(t, a.sub, a.fx, name="c8.t13-stopped.run", timeout=400)
    stalled = rs.wait_for(lambda: len(a.fx.exchanges) >= 1 and a.fx.exchanges[0].outcome == "stalled", 60)
    t.require("c8.t13-stopped.stalled", stalled, [e.outcome for e in a.fx.exchanges])
    t.require("c8.t13-stopped.sigstop", t.signal(h, signal.SIGSTOP), "SIGSTOP")
    try:
        rep = close_cmd(t, a, "c8.t13-stopped.close", timeout=180)
        check_close_obj(t, a, "c8.t13-stopped.close", rep.obj, closure="unfinished", reason="run_still_held",
                        effects={"run": "still_held", "seal": "none", "delivery": "none", "closure": "unfinished"},
                        holder=True, runs={"count": 1, "held": True, "last_ending": None})
        t.check("c8.t13-stopped.close.waited", 25000 <= rep.wall_ms <= 120000, rep.wall_ms)
        st = status_point(t, a, "c8.t13-stopped.status", condition="close_unfinished", held=True, closed="unfinished",
                          last=None, seal=None, closure={"unfinished_reason": "run_still_held"},
                          allowances=fp.allowances(a.fx.totals(upto=0), rs.limits_of(a.sub)),
                          next_cmds=("close", "status"))
        t.eq("c8.t13-stopped.status.holder", (st.data.get("runs") or {}).get("holder"),
             _started_observations(t, a.sub))
        # The stopped run still holds the lock (status: held, run_still_held), so its placement is
        # live and its in-flight request has no attempt record yet (5.6, 6.4 as amended in a1515e7):
        # the expected allowances are zero. The aborted_by_close estimate is charged only when the
        # attempt ends, after SIGCONT. Witness the missing record at the time of the status.
        t.check("c8.t13-stopped.status.in-flight-unrecorded", attempt_unrecorded(a.sub, 1, 1), sorted(
            os.listdir(os.path.join(a.sub.audit_dir, "runs", "1"))))
    finally:
        t.signal(h, signal.SIGCONT)
    rr = rs.finish_run(t, h, expect="completed")
    rs.check_run_reply(t, rr, a.sub, "c8.t13-stopped.run", ending="stopped_by_close", run_number=1, fx=a.fx,
                       limits=rs.limits_of(a.sub))
    rep = close_cmd(t, a, "c8.t13-stopped.resume")
    manager_sealed(t, a, rep.data.get("seal"), "c8.t13-stopped.resume.seal", [], 0)
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.t13-stopped.resume", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="manager", attempt=1, delivery="verified")
    check_package_at(t, a, "c8.t13-stopped.copy-1", 1)
    confirm_and_close(t, a, "c8.t13-stopped.confirm", tok)


def _held_sealed(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    h = rs.start_run(t, a.sub, a.fx, name="c8.held-sealed.run", fault="delivery.after_member:1=pause", timeout=300)
    stem = t.wait_paused("delivery.after_member", h, timeout=120)
    t.require("c8.held-sealed.paused", stem is not None, "the run did not pause in delivery")
    try:
        st = t.status(a.sub, name="c8.held-sealed.status")
        hl = st.data.get("headline") if isinstance(st.data.get("headline"), dict) else {}
        t.eq("c8.held-sealed.status.facts", [st.data.get("condition"), hl.get("sealed"),
                                             (st.data.get("runs") or {}).get("held")],
             ["run_active", {"by": "auditor"}, True])
        rep = close_cmd(t, a, "c8.held-sealed.close", timeout=180)
        d = rep.data
        eff = no_diag(rep.effects)
        t.eq("c8.held-sealed.close.closure", [d.get("closure"), d.get("unfinished_reason")],
             ["unfinished", "run_still_held"])
        t.eq("c8.held-sealed.close.effects.run", eff.get("run"), "still_held")
        t.eq("c8.held-sealed.close.effects.seal", eff.get("seal"), "existing")
        # 5.8 table, run_still_held: "newest attempt's outcome, or none"; the attempt is still open.
        t.check("c8.held-sealed.close.effects.delivery", eff.get("delivery") in ("none", "unknown"), eff)
        t.check("c8.held-sealed.close.holder", isinstance(d.get("holder"), dict), d.get("holder"))
        t.check("c8.held-sealed.close.waited", 25000 <= rep.wall_ms <= 120000, rep.wall_ms)
        t.eq("c8.held-sealed.close.seal-actor", (d.get("seal") or {}).get("actor"), "auditor")
    finally:
        t.release(stem)
    rr = rs.finish_run(t, h, expect="completed")
    t.require("c8.held-sealed.run.completed", rr.outcome == "completed", rr.obj)
    rs.check_run_reply(t, rr, a.sub, "c8.held-sealed.run", ending="sealed", run_number=1, fx=a.fx,
                       limits=rs.limits_of(a.sub), seal_actor="auditor", delivery_outcome="verified")
    rev = witness_revision(a.aud)
    seal = rr.data.get("seal") if isinstance(rr.data.get("seal"), dict) else {}
    set_expected(t, a, a.aud.expected_selection(rev), rev, "auditor", seal.get("sealed_at"), "c8.held-sealed.run")
    check_package_at(t, a, "c8.held-sealed.copy-1", 1)
    rep = close_cmd(t, a, "c8.held-sealed.after")
    tok = cf_token(t, a, 1)
    check_close_obj(t, a, "c8.held-sealed.after", rep.obj, closure="unfinished", reason="awaiting_confirmation",
                    effects={"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"},
                    token=tok, actor="auditor", attempt=1, delivery="verified")
    confirm_and_close(t, a, "c8.held-sealed.confirm", tok, actor="auditor")


# ---------------------------------------------------------------------------
# C16: status after launch.
# ---------------------------------------------------------------------------

@case("c16.status-after-launch", ["C16", "C8", "C13", "C20"],
      "status at every lifecycle point after launch: distinct facts, human and JSON agree, time changes nothing",
      mode="test", needs=("loopback",),
      controls=[Control("ended_as_submitted", [r"^c16\.ordinary\.status\.", r"^c16\.limit\.status\."]),
                Control("seal_as_delivered", [r"^c16\.sealed-undelivered\.status\.", r"^c16\.partial\.status\."])])
def c_status_after_launch(t):
    """Interrupted (killed between turns): runs 1, no ending recorded, nothing sealed, next run
    and close, allowances from the attempt records; run continues to an auditor seal and a
    verified delivery (delivered_open, location); a later status and a changed delivered copy
    change nothing status reports; close, then closed. Ordinary unsubmitted stop: sealed none,
    next close; close killed after its request: close_unfinished with no reason; continued:
    awaiting_confirmation with the token; confirmed: closed. Limit stop: limit_reached, sealed
    none. Differing, kill after sealing: sealed_undelivered by the auditor, not delivered; run
    refuses; close delivers without a provider request. Partial delivery: sealed_undelivered,
    not delivered. Close with a surrendered loss: closed, delivered.verified false with the loss
    IDs. Each status in JSON and for people, carrying the same facts."""
    scenario(t, "interrupted", _st_interrupted, audit(t, "c16.interrupted"))
    scenario(t, "ordinary", _st_ordinary, audit(t, "c16.ordinary"))
    scenario(t, "limit", _st_limit, audit(t, "c16.limit", q={"turns": "6"}))
    scenario(t, "sealed-undelivered", _st_sealed_undelivered, audit(t, "c16.sealed-undelivered"))
    scenario(t, "partial", _st_partial, audit(t, "c16.partial"))
    scenario(t, "surrendered", _st_surrendered, audit(t, "c16.surrendered"))


def _st_interrupted(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), calls_per_turn=1)
    # Responses 1-5 read the question, list, read both materials and re-enter; 6 and 7 record the
    # draft account and the observation. The kill comes after response 7's call was executed.
    run_cmd(t, a, "c16.interrupted.run-1", fault="run.between_turns:7=kill", killed=True)
    rev = witness_revision(a.aud)
    status_point(t, a, "c16.interrupted.status", condition="interrupted", last=None,
                 answer={"revision": rev, "entries": witness_entry_count(a.aud)}, seal=None,
                 next_cmds=("run", "close"), again=True)
    rep = run_sealed(t, a, "c16.interrupted.run-2", run_number=2)
    loc = check_package_at(t, a, "c16.interrupted.copy-1", 1)
    t.eq("c16.interrupted.two-conversations", a.aud.conversations, 2)
    ended = t.log_bodies(a.sub, "run_ended")
    t.eq("c16.interrupted.run-1-reconciled", [(ended[0] if ended else {}).get(k) for k in
                                              ("ending", "cause", "recorded_by")],
         ["interrupted", "process_gone", "run"])
    deliveries = [dict(attempt=1, outcome="verified", by="run", source="commissioned", replaces=None)]
    st = status_point(t, a, "c16.interrupted.status-delivered", condition="delivered_open", sealed="auditor",
                      delivered={"verified": True, "confirmed": False, "location": loc}, runs_count=2,
                      last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                      answer={"revision": a.revision, "entries": len(a.entries or [])}, deliveries=deliveries,
                      next_cmds=("close",), again=True)

    def tamper():
        with open(os.path.join(loc, "answer.md"), "ab") as f:
            f.write(b"\nChanged after delivery.\n")
    t.driver_change("change the delivered copy", tamper)
    st2 = t.status(a.sub, name="c16.interrupted.status-after-change")
    t.eq("c16.interrupted.copy-change-invariant", st2.data, st.data)
    t.eq("c16.interrupted.no-new-copy", sorted(os.listdir(a.sub.dest)), [pkg_name(a.sub, 1)])
    close_cmd(t, a, "c16.interrupted.close")
    status_point(t, a, "c16.interrupted.status-closed", condition="closed", sealed="auditor",
                 delivered={"verified": True, "confirmed": True, "location": loc}, closed="yes", runs_count=2,
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor", deliveries=deliveries,
                 closure={"unfinished_reason": None, "outcome": "closed_delivered",
                          "placement": "delivered_before_close", "surrendered": [], "closed": True})


def _st_ordinary(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c16.ordinary.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    last = {"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}
    status_point(t, a, "c16.ordinary.status", condition="ended_unsubmitted", last=last,
                 answer={"revision": rev, "entries": len(entries)}, seal=None, next_cmds=("close",), again=True)
    close_cmd(t, a, "c16.ordinary.close-killed", fault="close.after_requested=kill", killed=True)
    status_point(t, a, "c16.ordinary.status-requested", condition="close_unfinished", closed="unfinished", last=last,
                 seal=None, closure={"unfinished_reason": None}, next_cmds=("close", "status"))
    rep = close_cmd(t, a, "c16.ordinary.close")
    manager_sealed(t, a, rep.data.get("seal"), "c16.ordinary.close.seal", entries, rev)
    tok = cf_token(t, a, 1)
    loc = pkg_path(a.sub, 1)
    status_point(t, a, "c16.ordinary.status-awaiting", condition="awaiting_confirmation", sealed="manager",
                 delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished", last=last,
                 seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []), again=True)
    confirm_and_close(t, a, "c16.ordinary.confirm", tok, actor="manager")
    status_point(t, a, "c16.ordinary.status-closed", condition="closed", sealed="manager",
                 delivered={"verified": True, "confirmed": True, "location": loc}, closed="yes", last=last,
                 seal="manager",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None)],
                 closure={"unfinished_reason": None, "outcome": "closed_delivered", "placement": "confirmed",
                          "surrendered": [], "closed": True})


def _st_limit(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False), calls_per_turn=1)
    rep = run_cmd(t, a, "c16.limit.run")
    t.require("c16.limit.run.completed", rep.outcome == "completed", rep.obj)
    rs.check_run_reply(t, rep, a.sub, "c16.limit.run", ending="limit_reached", run_number=1, fx=a.fx,
                       limits=rs.limits_of(a.sub))
    t.eq("c16.limit.run.exit", rep.rc, 0)
    # 6.4: the last response's calls run before the placement ends, so their entries count.
    status_point(t, a, "c16.limit.status", condition="limit_reached",
                 last={"ending": "limit_reached", "cause": None, "recorded_by": "run"}, seal=None,
                 answer={"revision": witness_revision(a.aud), "entries": witness_entry_count(a.aud)},
                 next_cmds=("close",), again=True)
    rep = run_cmd(t, a, "c16.limit.run-again", expect="refused", reason="authoring_ended", mark=False)
    t.eq("c16.limit.run-again.ended_by", rep.data.get("ended_by"), "limit")


def _st_sealed_undelivered(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    run_cmd(t, a, "c16.sealed-undelivered.run", fault="seal.after_link=kill", killed=True)
    sv = status_seal(t, a, "c16.sealed-undelivered.seal")
    rev = witness_revision(a.aud)
    set_expected(t, a, a.aud.expected_selection(rev), rev, "auditor", sv.get("sealed_at"),
                 "c16.sealed-undelivered.seal")
    status_point(t, a, "c16.sealed-undelivered.status", condition="sealed_undelivered", sealed="auditor", last=None,
                 seal="auditor", answer={"revision": rev, "entries": len(a.entries or [])}, next_cmds=("close",),
                 again=True)
    run_cmd(t, a, "c16.sealed-undelivered.run-again", expect="refused", reason="authoring_ended", mark=False)
    n_ex = len(a.fx.exchanges)
    rep = close_cmd(t, a, "c16.sealed-undelivered.close")
    t.eq("c16.sealed-undelivered.close.delivery", (rep.data.get("delivery") or {}).get("outcome"), "verified")
    t.eq("c16.sealed-undelivered.no-provider-request", len(a.fx.exchanges), n_ex)
    tok = cf_token(t, a, 1)
    status_point(t, a, "c16.sealed-undelivered.status-awaiting", condition="awaiting_confirmation", sealed="auditor",
                 delivered={"verified": True, "confirmed": False, "location": pkg_path(a.sub, 1)},
                 closed="unfinished", last={"ending": "interrupted", "cause": "process_gone", "recorded_by": "close"},
                 seal="auditor",
                 deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                  token=tok)],
                 closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                 confirm=(tok, []))


def _st_partial(t, a):
    with_auditor(t, a, goals(a.sub, artifacts=False))
    run_sealed(t, a, "c16.partial.run", delivery="partial", fault="delivery.member_write:answer.md=eio")
    status_point(t, a, "c16.partial.status", condition="sealed_undelivered", sealed="auditor",
                 last={"ending": "sealed", "cause": None, "recorded_by": "run"}, seal="auditor",
                 deliveries=[dict(attempt=1, outcome="partial", by="run", source="commissioned", replaces=None,
                                  verified=["manifest.json", "answer.json"],
                                  unverified=[{"name": "answer.md", "failure": "write_failed"}])],
                 next_cmds=("close",), destination_offered=True, again=True)


def _st_surrendered(t, a):
    with_auditor(t, a, goals(a.sub), finish="ordinary", after_reminder="end")
    run_ordinary(t, a, "c16.surrendered.run")
    entries = a.aud.expected_selection(None)
    rev = witness_revision(a.aud)
    target = next((e for e in entries if e.kind == "record_artifact" and e.encoding == "binary"), None)
    t.require("c16.surrendered.target", target is not None, [e.label for e in entries])
    path = payload_path(a.sub, target)
    t.require("c16.surrendered.payload-recorded", rs.read_package_member(os.path.dirname(path),
                                                                        os.path.basename(path)) == target.data, path)
    t.flip_bit(path, 0)
    ids = close_damaged(t, a, "c16.surrendered", entries, rev, [target.id])
    loc = pkg_path(a.sub, 1)
    hum = t.cmd(["status", a.sub.ref], json_reply=False, envelope=False, name="c16.surrendered.status-human")
    st = t.status(a.sub, name="c16.surrendered.status-json")
    check_human_agrees(t, "c16.surrendered.status", st.rc, st.data, hum.rc, hum.stdout)
    t.check("c16.surrendered.not-a-complete-delivery",
            ((st.data.get("headline") or {}).get("delivered") or {}).get("verified") is False
            and ((st.data.get("headline") or {}).get("delivered") or {}).get("losses") == ids,
            st.data.get("headline"))
    t.check("c16.surrendered.artifact-not-delivered", not os.path.lexists(os.path.join(loc, target.member)), loc)


# ---------------------------------------------------------------------------
# Self-tests (no binary): the witness, the package checks and the status and close
# expectations, each passing on a correct specimen and failing on a broken one.
# ---------------------------------------------------------------------------

class _ST:
    """Just enough of T for the pure checks."""

    def __init__(self):
        self.checks = []
        self.bin = {"sha256": "ab" * 32, "kind": "test", "path": "/opt/stewart/bin/stewart"}

    def check(self, name, cond, detail=None):
        self.checks.append((name, bool(cond), detail))
        return bool(cond)

    def eq(self, name, actual, expected):
        return self.check(name, actual == expected, {"actual": actual, "expected": expected})

    def require(self, name, cond, detail=None):
        if not self.check(name, cond, detail):
            raise Abort(name)

    def failed(self):
        return [c[0] for c in self.checks if not c[1]]


class _Sub:
    def __init__(self, root):
        self.audit, self.store = "a" + "b" * 16, "s" + "c" * 16
        self.archive = os.path.join(root, "archive")
        self.dest = os.path.join(root, "returns")
        self.writer = "/opt/stewart/bin/stewart"
        self.ref = "stw1:%s:%s:%s" % (self.audit, self.store, self.archive)
        self.family, self.limits = "open-inquiry", (200, 20000000, 400000)

    @property
    def audit_dir(self):
        return os.path.join(self.archive, "audits", self.audit)


def _specimen_entries():
    src = {"materials/a.py": b"def send(r):\n    deliver(r)\n", "question": QUESTION}
    s = src["materials/a.py"].find(b"deliver(r)")
    return [aw.Entry("e1", 2, "record_account", "", "Account.\nSecond line.".encode("utf-8"),
                     citations=[aw.record_citation({"source": "question", "quote": "restarts"}, src)]),
            aw.Entry("e2", 1, "record_observation", "ordering", ORDERING.encode("utf-8"),
                     citations=[aw.record_citation({"source": "materials/a.py", "start": s, "end": s + 10}, src)]),
            aw.Entry("e4", 1, "record_artifact", "trace", b"send -> deliver\n", encoding="utf-8"),
            aw.Entry("e5", 1, "record_artifact", "blob", b"\x00\x01\xfe\xff", encoding="binary")]


def _write_package(path, files):
    os.makedirs(path, mode=0o700)
    os.chmod(path, 0o700)
    for n, data in files.items():
        p = os.path.join(path, n)
        with open(p, "wb") as f:
            f.write(data)
        os.chmod(p, 0o600)


def _package_round(root, label, files, a):
    st = _ST()
    path = os.path.join(root, label)
    _write_package(path, files)
    rs.check_package(st, path, a.files, "p.package")
    check_self_verifying(st, "p.manifest-verify", path)
    check_rendering(st, "p.rendering", path)
    return st.failed()


def _selftest_packages():
    out = []
    root = tempfile.mkdtemp(prefix="stewart-after-launch-")
    try:
        sub = _Sub(root)
        a = Audit(_ST(), "s", sub)
        st = _ST()
        set_expected(st, a, _specimen_entries(), 7, "auditor", "2026-11-02T15:20:04.118Z", "s")
        good = dict(a.files)
        out.append(("after-launch.package.members", sorted(good) == ["answer.json", "answer.md", "artifact-e4.bin",
                                                                    "artifact-e5.bin", "manifest.json"], sorted(good)))
        fails = _package_round(root, "good", good, a)
        out.append(("after-launch.package.pass", not fails, fails))
        # The sabotage controls of C5, simulated on the package itself: each must fail its target.
        variants = {
            "deliver_conversation": (dict(good, **{"conversation.json": b"[]\n"}), r"\.package-members$|\.exactly-listed$"),
            "regenerate_rendering": (dict(good, **{"answer.md": b"Rendered again.\n" + good["answer.md"].split(b"\n", 1)[1]}),
                                     r"member-bytes\.answer\.md$|\.member\.answer\.md$"),
            "render_conclusion": (dict(good, **{"answer.md": good["answer.md"] + b"No issues found.\n"}),
                                  r"member-bytes\.answer\.md$"),
        }
        dropped = _specimen_entries()[:-1]
        b = Audit(_ST(), "d", sub)
        set_expected(_ST(), b, dropped, 7, "auditor", "2026-11-02T15:20:04.118Z", "d")
        variants["drop_last_entry"] = (dict(b.files), r"\.package-members$|member-bytes\.answer\.json$")
        variants["skip_delivery_verification"] = (
            dict(good, **{"answer.json": good["answer.json"][:-2] + b"X\n"}), r"\.member\.answer\.json$")
        import re as _re
        for label, (files, pat) in sorted(variants.items()):
            fails = _package_round(root, label, files, a)
            out.append(("after-launch.package.control.%s" % label, any(_re.search(pat, f) for f in fails), fails[:6]))
        # An unproduced entry: no answer.md, the manifest lists both unproduced members.
        c = Audit(_ST(), "u", sub)
        set_expected(_ST(), c, damaged(_specimen_entries(), ["e2"]), 7, "manager", "2026-11-02T15:31:40.020Z", "u")
        man = strict_loads(c.files["manifest.json"][:-1])
        out.append(("after-launch.package.unproduced-manifest",
                    man["unproduced"] == [{"name": "e2", "role": "entry", "failure": "damaged", "dependency": None},
                                          {"name": "answer.md", "role": "rendering", "failure": "not_rendered",
                                           "dependency": ["e2"]}] and "answer.md" not in c.files, man["unproduced"]))
        fails = _package_round(root, "unproduced", dict(c.files), c)
        out.append(("after-launch.package.unproduced-pass", not fails, fails))
        fails = _package_round(root, "unproduced-rendered", dict(c.files, **{"answer.md": b"x\n"}), c)
        out.append(("after-launch.package.unproduced-rendered-fails", any(f.endswith(".not-rendered") for f in fails),
                    fails))
        out.append(("after-launch.package.unproduced-names", unproduced_names(c) == ["e2", "answer.md"]
                    and member_names(c) == ["manifest.json", "answer.json", "artifact-e4.bin", "artifact-e5.bin"],
                    (unproduced_names(c), member_names(c))))
        # An empty selection: the honest empty return.
        e = Audit(_ST(), "e", sub)
        set_expected(_ST(), e, [], 0, "manager", "2026-11-02T15:31:40.020Z", "e")
        out.append(("after-launch.package.empty", e.files["answer.json"] ==
                    b'{"schema":"stewart.answer/1","revision":0,"entries":[]}\n'
                    and e.files["answer.md"] == b"No answer entries recorded.\n", sorted(e.files)))
        out.append(("after-launch.package.empty-pass", not _package_round(root, "empty", dict(e.files), e)))
        # Handles bind what they claim (2.3): a different record or manifest changes them.
        rec = b'{"record":"stewart.record/1","kind":"delivery_ended"}\n'
        t1 = token_of(sub.store, sub.audit, "cf", "cf1", a.manifest, rec)
        out.append(("after-launch.token.form", re.fullmatch(r"cf1\.[a-z2-7]{6}", t1) is not None, t1))
        out.append(("after-launch.token.binds", t1 != token_of(sub.store, sub.audit, "cf", "cf1", a.manifest, rec + b" ")
                    and t1 != token_of(sub.store, sub.audit, "cf", "cf1", b.manifest, rec)))
        out.append(("after-launch.seal-handle", re.fullmatch(r"seal\.[a-z2-7]{6}",
                                                             seal_handle(sub.store, sub.audit, a.manifest)) is not None))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return out


def _status_specimen(a, *, condition, sealed, delivered, closed, last, seal=None, deliveries=(), closure=None,
                     nxt=()):
    at = "2026-11-02T15:20:04.118Z"
    return {"schema": "stewart.reply/1", "operation": "status", "outcome": "completed", "effects": {},
            "next": [{"argv": list(x), "why": "Next."} for x in nxt],
            "data": {"headline": {"accepted": "yes", "launched": "yes", "sealed": {"by": sealed},
                                  "delivered": delivered, "closed": closed},
                     "condition": condition, "summary": "Facts.",
                     "evidence": [{"fact": "launched", "evidence": "run_started log/5.json"}],
                     "runs": {"count": 1, "held": False, "holder": None,
                              "last": {"number": 1, "started_at": at, "ending": last, "cause": None,
                                       "ended_at": at if last else None, "recorded_by": "run" if last else None}},
                     "allowances": None, "answer": {"revision": 7, "entries": 4}, "seal": seal,
                     "deliveries": list(deliveries), "closure": closure, "diagnostics": [],
                     "provider_url_override": None, "provider_proxy": None,
                     "receipt_line": [a.sub.writer, "receipt", a.sub.ref]}}


def _selftest_views():
    import re as _re
    out = []
    root = tempfile.mkdtemp(prefix="stewart-after-launch-views-")
    try:
        sub = _Sub(root)
        a = Audit(_ST(), "v", sub)
        set_expected(_ST(), a, _specimen_entries(), 7, "auditor", "2026-11-02T15:20:04.118Z", "v")
        w, ref = sub.writer, sub.ref
        sv = {"handle": seal_handle(sub.store, sub.audit, a.manifest), "actor": "auditor",
              "sealed_at": a.sealed_at, "revision": 7, "manifest_sha256": sha256_hex(a.manifest), "unproduced": []}
        last = {"ending": "ended_unsubmitted", "cause": None, "recorded_by": "run"}

        def status_round(spec, **exp):
            st = _ST()
            check_status_obj(st, a, "s", spec, allowances=False, **exp)
            return st.failed()
        # ended_unsubmitted: passes; the ended_as_submitted control (sealed.by auditor) fails it.
        spec = _status_specimen(a, condition="ended_unsubmitted", sealed="none", delivered=dict(UNVERIFIED),
                                closed="no", last="ended_unsubmitted", nxt=[(w, "close", ref)])
        exp = dict(condition="ended_unsubmitted", last=last, seal=None, next_cmds=("close",),
                   answer={"revision": 7, "entries": 4})
        f = status_round(spec, **exp)
        out.append(("after-launch.status.ended-unsubmitted", not f, f))
        bad = json.loads(json.dumps(spec))
        bad["data"]["headline"]["sealed"] = {"by": "auditor"}
        f = status_round(bad, **exp)
        out.append(("after-launch.status.control.ended_as_submitted", "s.headline.sealed" in f, f))
        # sealed_undelivered: passes; seal_as_delivered (verified true with a seal) fails it.
        spec = _status_specimen(a, condition="sealed_undelivered", sealed="auditor", delivered=dict(UNVERIFIED),
                                closed="no", last="sealed", seal=sv, nxt=[(w, "close", ref)])
        exp = dict(condition="sealed_undelivered", sealed="auditor", last=dict(last, ending="sealed"), seal="auditor",
                   next_cmds=("close",))
        f = status_round(spec, **exp)
        out.append(("after-launch.status.sealed-undelivered", not f, f))
        bad = json.loads(json.dumps(spec))
        bad["data"]["headline"]["delivered"] = {"verified": True, "confirmed": False}
        f = status_round(bad, **exp)
        out.append(("after-launch.status.control.seal_as_delivered", "s.headline.delivered" in f, f))
        bad = json.loads(json.dumps(spec))
        bad["data"]["seal"]["manifest_sha256"] = "0" * 64
        f = status_round(bad, **exp)
        out.append(("after-launch.status.seal-binding", "s.seal.manifest_sha256" in f, f))
        # A seal whose manifest cannot be read: its time and unproduced list are unknown, never kept.
        a.manifest_unreadable = True
        st = _ST()
        check_seal_view(st, "u", dict(sv, sealed_at="unknown", unproduced="unknown"), a)
        out.append(("after-launch.seal.manifest-unreadable", not st.failed(), st.failed()))
        st = _ST()
        check_seal_view(st, "u", sv, a)
        out.append(("after-launch.seal.manifest-unreadable-no-guess",
                    "u.sealed_at" in st.failed() and "u.unproduced" in st.failed(), st.failed()))
        a.manifest_unreadable = False
        # awaiting_confirmation with a token: the confirm next call must name it.
        tok = "cf1.abcdef"
        dl = {"attempt": 1, "by": "close", "destination": sub.dest, "destination_source": "commissioned",
              "package": pkg_name(sub, 1), "replaces": None, "outcome": "verified", "cause": None,
              "verified_members": member_names(a), "unverified_members": [], "losses": [], "confirmation": tok}
        loc = pkg_path(sub, 1)
        closure = {"requested_at": a.sealed_at, "before_launch": False, "accepted": True,
                   "unfinished_reason": "awaiting_confirmation", "closed_at": None, "outcome": None,
                   "placement": None, "surrendered": None}
        spec = _status_specimen(a, condition="awaiting_confirmation", sealed="auditor",
                                delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished",
                                last="sealed", seal=sv, deliveries=[dl], closure=closure,
                                nxt=[(w, "close", ref, "--confirm", tok), (w, "status", ref)])
        exp = dict(condition="awaiting_confirmation", sealed="auditor",
                   delivered={"verified": True, "confirmed": False, "location": loc}, closed="unfinished",
                   last=dict(last, ending="sealed"), seal="auditor",
                   deliveries=[dict(attempt=1, outcome="verified", by="close", source="commissioned", replaces=None,
                                    token=tok)],
                   closure={"unfinished_reason": "awaiting_confirmation"}, next_cmds=("close", "status"),
                   confirm=(tok, []))
        f = status_round(spec, **exp)
        out.append(("after-launch.status.awaiting", not f, f))
        bad = json.loads(json.dumps(spec))
        bad["next"] = [{"argv": [w, "close", ref], "why": "x"}, {"argv": [w, "status", ref], "why": "x"}]
        f = status_round(bad, **exp)
        out.append(("after-launch.status.confirm-next-required", "s.next.confirm" in f, f))
        # Human agreement: the same facts, or a failure naming what is missing.
        data = spec["data"]
        human = ("Sealed by the auditor. Delivered to %s and verified; confirm with close --confirm %s. "
                 "Receipt: stewart receipt REF\n" % (loc, tok)).encode("utf-8")
        st = _ST()
        check_human_agrees(st, "h", 0, data, 0, human)
        out.append(("after-launch.human.agrees", not st.failed(), st.failed()))
        st = _ST()
        check_human_agrees(st, "h", 0, data, 0, human.replace(tok.encode(), b"the token"))
        out.append(("after-launch.human.missing-token-fails", "h.human.agrees" in st.failed(), st.failed()))
        st = _ST()
        check_human_agrees(st, "h", 0, data, 0, json.dumps(spec).encode())
        out.append(("after-launch.human.json-is-not-human", "h.human.text" in st.failed(), st.failed()))
        # Close replies (5.8): the T8 example passes; skip_confirmation (closed right after a copy
        # close made) fails; a closed reply has no next calls.
        cobj = {"schema": "stewart.reply/1", "operation": "close", "outcome": "completed",
                "effects": {"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                "next": [{"argv": [w, "close", ref, "--confirm", tok], "why": "Confirm."},
                         {"argv": [w, "status", ref], "why": "Status."}],
                "data": {"closure": "unfinished", "unfinished_reason": "awaiting_confirmation",
                         "headline": {"closed": "unfinished"},
                         "runs": {"count": 1, "held": False, "last_ending": "ended_unsubmitted"}, "seal": sv,
                         "delivery": {"attempt": 1, "outcome": "verified"}, "confirmation": tok, "holder": None}}
        cexp = dict(closure="unfinished", reason="awaiting_confirmation", token=tok, attempt=1, delivery="verified",
                    effects={"run": "ended", "seal": "recorded", "delivery": "verified", "closure": "unfinished"},
                    runs={"count": 1, "held": False, "last_ending": "ended_unsubmitted"})
        st = _ST()
        check_close_obj(st, a, "c", cobj, **cexp)
        out.append(("after-launch.close.awaiting", not st.failed(), st.failed()))
        bad = json.loads(json.dumps(cobj))
        bad["effects"]["closure"] = "complete"
        bad["data"] = {"closure": "complete", "already_closed": False, "before_launch": False, "accepted": True,
                       "closed_at": a.sealed_at, "headline": {"closed": "yes"}, "outcome": "closed_delivered",
                       "runs": cobj["data"]["runs"], "seal": sv, "delivery": cobj["data"]["delivery"],
                       "placement": "delivered_before_close", "surrendered": []}
        bad["next"] = []
        st = _ST()
        check_close_obj(st, a, "c8.t8.close", bad, **cexp)
        out.append(("after-launch.close.control.skip_confirmation",
                    any(_re.match(r"^c8\.t8\.close\.", x) for x in st.failed()), st.failed()))
        out.append(("after-launch.has-confirm.surrender-pairs",
                    has_confirm({"next": [{"argv": [w, "close", ref, "--confirm", tok, "--surrender", "l2",
                                                    "--surrender", "l1"], "why": "x"}]}, w, ref, tok, ["l1", "l2"])
                    and not has_confirm({"next": [{"argv": [w, "close", ref, "--confirm", tok, "--surrender", "l1"],
                                                   "why": "x"}]}, w, ref, tok, ["l1", "l2"])))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return out


def _selftest_witness_with_stand_in():
    """The manager seal's expected selection and revision, from the reacting auditor's own
    account, against mini_stewart's ledger (a stand-in, not Stewart): an ordinary ending, and a
    kill after an executed call followed by a continuation."""
    import mini_stewart
    import reacting_auditor as ra
    out = []
    for label, kill in (("ordinary", None), ("killed-then-continued", 3)):
        q, mats = ra._scenario_material()
        aud = ReactingAuditor(ra._goals(mats), question=q, materials=mats, finish="ordinary", after_reminder="end",
                              calls_per_turn=1)
        sim = mini_stewart.MiniStewart(aud, q, mats)
        endings = [sim.run(kill_after_mutations=kill)]
        if endings[-1] == "killed":
            endings.append(sim.run())
        want = [aw.Entry(e["id"], e["version"], e["kind"], e["label"], e["data"], citations=e["citations"],
                         encoding=e["encoding"]) for e in sim.current()]
        rev = witness_revision(aud)
        got = aud.expected_selection(rev)
        out.append(("after-launch.witness.%s.ending" % label, endings[-1] == "ended_unsubmitted", endings))
        out.append(("after-launch.witness.%s.revision" % label, rev == sim.revision, (rev, sim.revision)))
        out.append(("after-launch.witness.%s.entries" % label, witness_entry_count(aud) == len(sim.entries),
                    (witness_entry_count(aud), len(sim.entries))))
        out.append(("after-launch.witness.%s.selection" % label,
                    aw.answer_json(rev, got) == aw.answer_json(sim.revision, want),
                    {"witness": aw.answer_json(rev, got)[:300], "stand-in": aw.answer_json(sim.revision, want)[:300]}))
    return out


@selftest
def after_launch_selftests():
    return _selftest_packages() + _selftest_views() + _selftest_witness_with_stand_in()
