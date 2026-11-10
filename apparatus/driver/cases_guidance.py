# -*- coding: utf-8 -*-
"""Selected open-inquiry guidance (INTERFACE 3.2; ACCEPTANCE C1, C15, C19).

Written from the specification without reading service/. The supplied bytes live
in the driver's witness before prepare; arrangement and provider checks compare
against those bytes, never against a value recovered from Stewart.
"""
from __future__ import annotations

import os
import signal

import answer_witness as aw
import fake_provider as fp
import run_support as rs
from cases_foundation import check_arrangement, find_items, item_state, names_bound
from driver_core import *  # noqa: F401,F403
from procedure import Procedure


GUIDANCE_A = b'\xef\xbb\xbf  Start with a direct answer.\r\nThen explain "reach" and limits.\t'
GUIDANCE_B = b'\xef\xbb\xbf  Start with a scoped answer.\r\nThen explain "reach" and limits.\t'
BODY = b"What can these materials establish?\n"
MATERIAL_GUIDANCE = b"This is ordinary evidence, not an instruction selection.\n"


def entries(other=False):
    return [F("evidence.txt", b"changed evidence\n" if other else b"original evidence\n"),
            F("guidance.md", MATERIAL_GUIDANCE)]


def summary(sub):
    return (None if sub.guidance is None else
            {"file": "guidance.md", "size": len(sub.guidance), "sha256": sha256_hex(sub.guidance)})


def after(t, obj, key, previous, name):
    keys = list(obj) if isinstance(obj, dict) else []
    t.check(name, key in keys and previous in keys and keys.index(key) == keys.index(previous) + 1, keys)


def record_body(t, path, schema, name):
    obj = strict_loads(read_bytes(path))
    t.check(name + ".schema", contains_string(obj, schema), "expected " + schema)
    return obj.get("body", obj) if isinstance(obj, dict) else {}


def provenance(t, sub, name, accepted=False):
    """Check public and durable origin/identity against the pre-existing source witness."""
    want = summary(sub)
    prepared = t.log_bodies(sub, "prepared")[-1]
    t.eq(name + ".log-guidance", prepared.get("guidance", "missing"), want)
    after(t, prepared, "guidance", "question", name + ".log-order")
    data = sub.prep[sub.handles[-1]]
    t.eq(name + ".public-guidance", data.get("guidance", "missing"), want)
    after(t, data, "guidance", "question", name + ".public-order")
    t.check_prepared_settings(sub, name)
    manifest = record_body(t, os.path.join(sub.audit_dir, prepared["manifest"]),
                           "stewart.preparation/2", name + ".manifest")
    after(t, manifest, "guidance", "question", name + ".manifest-order")
    mg = manifest.get("guidance", "missing")
    if want is None:
        t.eq(name + ".manifest-guidance", mg, None)
    else:
        t.eq(name + ".manifest-guidance", {k: mg.get(k) for k in want} if isinstance(mg, dict) else mg, want)
        t.eq(name + ".manifest-guidance-keys", list(mg) if isinstance(mg, dict) else None,
             ["file", "size", "sha256", "mtime"])
    arr = sub.arrangement[sub.handles[-1]]["machine"]
    obj = strict_loads(arr)
    t.check(name + ".arrangement-schema", contains_string(obj, "stewart.arrangement/2"), "arrangement schema")
    members = obj.get("body", obj)
    after(t, members, "guidance", "family", name + ".arrangement-order")
    check_arrangement(t, sub, sub.handles[-1], sub.family, name + ".arrangement", sub.limits)
    if not accepted:
        return
    receipt = t.cmd(["receipt", sub.ref], name=name + ".receipt", expect="completed")
    t.eq(name + ".receipt-guidance", receipt.data.get("guidance", "missing"), want)
    after(t, receipt.data, "guidance", "question", name + ".receipt-order")
    accepted_body = t.log_bodies(sub, "accepted")[-1]
    rec = record_body(t, os.path.join(sub.audit_dir, accepted_body["receipt"]),
                      "stewart.receipt/2", name + ".receipt-record")
    after(t, rec, "guidance", "question", name + ".receipt-record-order")
    rg = rec.get("guidance", "missing")
    if want is None:
        t.eq(name + ".receipt-record-guidance", rg, None)
    else:
        t.eq(name + ".receipt-record-guidance", {k: rg.get(k) for k in want} if isinstance(rg, dict) else rg, want)
        t.eq(name + ".receipt-record-guidance-keys", list(rg) if isinstance(rg, dict) else None,
             ["file", "size", "sha256", "capture"])
        t.check(name + ".receipt-capture", isinstance(rg, dict) and isinstance(rg.get("capture"), str)
                and rg["capture"].endswith("/g.bin"), rg)
    caps = t.log_bodies(sub, "intake_planned")[-1].get("captures") or []
    expected_ids = ["question-file"] + [sub.public(k) for k in sorted(sub.files)]
    if want is not None:
        expected_ids.append("guidance-file")
    t.eq(name + ".capture-order", [c.get("item") for c in caps], expected_ids)
    if want is not None:
        t.eq(name + ".capture-name", caps[-1].get("file") if caps else None, "g.bin")
    found = find_items(receipt.data, set(sub.items()))
    t.eq(name + ".receipt-item-ids", sorted(found), sorted(sub.items()))


def guidance_auditor(p, sub):
    """Read the material world, inspect missing sections, then seal an empty answer."""
    turn = yield p.end("I am stopping here.")
    p.eq("reminder", turn.texts, [REMINDER])
    mats, _ = yield from p.list_all()
    p.eq("material-names", [m.get("source") for m in mats] if mats is not None else None,
         [sub.public(k) for k in sorted(sub.files)])
    text, _ = yield from p.read_all("materials/guidance.md")
    p.eq("material-guidance", text, MATERIAL_GUIDANCE)
    turn = yield p.calls_step(("read", {"source": "guidance.md"}),
                              ("search", {"text": "answer", "sources": ["guidance.md"]}))
    for i in range(2):
        r = turn.reply(i)
        p.eq("guidance-not-material-%d" % i, (r.outcome, r.reason) if r else None,
             ("refused", "source_unknown"))

    # 7.6 distinguishes section_unfilled from answer_empty. Exercise both states:
    # the block_incomplete control must be able to refuse the partial preparation.
    turn = yield p.calls_step(("record_account", {"text": "The supplied material does not answer the question."}))
    r = turn.reply(0)
    p.eq("account-recorded", r.outcome if r else None, "completed")
    entry = r.data.get("entry") if r else None
    turn = yield p.calls_step(("prepare", {}))
    r = turn.reply(0)
    p.eq("prepare-partial", r.outcome if r else None, "completed")
    if r is not None and r.outcome == "completed":
        p.eq("partial-counts", r.data.get("counts"),
             {"record_account": 1, "record_observation": 0, "record_limit": 0, "record_artifact": 0})
        p.eq("partial-notices", [(n.get("reason"), n.get("tool")) for n in r.data.get("notices") or []],
             [("section_unfilled", "record_observation"), ("section_unfilled", "record_limit")])
    turn = yield p.calls_step(("delete", {"entry": entry}))
    r = turn.reply(0)
    p.eq("account-deleted", r.outcome if r else None, "completed")
    turn = yield p.calls_step(("prepare", {}))
    r = turn.reply(0)
    p.eq("prepare-empty", r.outcome if r else None, "completed")
    if r is None or r.outcome != "completed":
        yield p.end("Preparation did not return a handle.")
        return
    p.eq("empty-notices", [n.get("reason") for n in r.data.get("notices") or []], ["answer_empty"])
    p.eq("empty-counts", r.data.get("counts"),
         {k: 0 for k in FAMILY_TOOLS["open-inquiry"] + ["record_artifact"]})
    p.eq("empty-selection", (r.data.get("revision"), r.data.get("entry_count")), (2, 0))
    p.eq("base-family", r.data.get("family"), "open-inquiry/1")
    yield p.calls_step(("submit", {"prepared": r.data.get("prepared"), "confirm": True}))


@case("c1.guidance", ["C1", "C7", "C19", "C20"],
      "stock and supplied guidance replace one system block while tools, notices and empty answers stay invariant",
      needs=("loopback",), controls=[
          Control("arrangement_mismatch", [r"^guidance\.(a|b)\.request-\d+\.(system-bytes|system-pinned-bytes)$"]),
          Control("extra_tool", [r"^guidance\.(a|b)\.request-\d+\.tools$"]),
          Control("block_incomplete", [r"^guidance\.(a|b)\.prepare-partial$"])])
def c_guidance(t):
    """The same binary receives stock, A, B and A with changed materials. Every fake request
    has exactly the selected second block; BOM, CRLF, quotes and edge whitespace survive.
    Whole-block replacement excludes the stock text. Orientation, tools, notices, limits and
    base family remain fixed. materials/guidance.md is ordinary readable material; the root
    guidance is not listed or accepted as a read/search source. Each audit observes the
    ordinary reminder, prepares an account with two missing sections, deletes the account,
    then prepares and submits an empty answer without acknowledgment."""
    pinned = {}
    for label, guidance, other in (("stock", None, False), ("a", GUIDANCE_A, False),
                                    ("b", GUIDANCE_B, False), ("other-material", GUIDANCE_A, True)):
        pre = "guidance." + label
        sub = t.submission(entries(other), body=BODY, guidance=guidance, dest_watch="additions")
        t.accept(sub, prefix=pre + ".", check_witness=True)
        provenance(t, sub, pre, accepted=True)
        raw = strict_loads(sub.arrangement[sub.accepted_handle]["machine"])
        pinned[label] = raw.get("body", raw)

        p = Procedure(lambda p, sub=sub: guidance_auditor(p, sub), model=sub.model)
        fx = rs.provider(t, p, label=label)
        rep = rs.run(t, sub, fx, name=pre + ".run")
        rs.check_run_reply(t, rep, sub, pre + ".run", ending="sealed", run_number=1, fx=fx,
                           limits=rs.limits_of(sub), seal_actor="auditor", delivery_outcome="verified")
        rs.check_procedure(t, p, pre, fx)
        rs.check_requests(t, fx, sub, pre)
        rs.check_history(t, fx, pre)
        if fx.exchanges:
            rs.check_first_message(t, fx.exchanges[0], sub.body, False, pre)
        package = rs.package_of(rep)
        t.eq(pre + ".empty-rendering", rs.read_package_member(package, "answer.md") if package else None,
             aw.EMPTY_RENDERING)
        t.eq(pre + ".empty-answer", rs.read_package_member(package, "answer.json") if package else None,
             aw.answer_json(2, []))
    if len(pinned) == 4:
        for key in ARRANGEMENT_MEMBERS:
            if key in ("system", "guidance", "bindings"):
                continue
            for label in ("a", "b", "other-material"):
                t.eq("guidance.invariance.%s.%s" % (label, key), pinned[label][key], pinned["stock"][key])
        for label in ("a", "b"):
            t.eq("guidance.differing.%s.bindings" % label, pinned[label]["bindings"], pinned["stock"]["bindings"])
        for key in ("system", "guidance"):
            t.eq("guidance.invariance.other-material." + key, pinned["other-material"][key], pinned["a"][key])


@case("c19.guidance", ["C1", "C19", "C20"],
      "guidance is explicitly selected, regular nonblank UTF-8, and bounded separately from materials")
def c_guidance_intake(t):
    """Selection is exact: stray/missing files, other paths/families, duplicate or unsupported
    fields, malformed/blank text, links and directories refuse without a prepared record.
    Exactly guidance_bytes and 128 material files are admitted together; one additional
    guidance byte refuses. The existing total-byte case includes selected guidance too."""
    bad = [
        ("unselected", {"root_entries": [F("guidance.md", GUIDANCE_A)]}, "unexpected_root_entry", "guidance.md"),
        ("missing", {"q": {"guidance": "guidance.md"}}, "folder_incomplete", "guidance.md"),
        ("other-name", {"guidance": GUIDANCE_A, "q": {"guidance": "other.md"}}, "setting_invalid", "guidance"),
        ("relative-path", {"guidance": GUIDANCE_A, "q": {"guidance": "../guidance.md"}}, "setting_invalid", "guidance"),
        ("absolute-path", {"guidance": GUIDANCE_A, "q": {"guidance": "/guidance.md"}}, "setting_invalid", "guidance"),
        ("framing", {"guidance": GUIDANCE_A, "family": "inquiry-framing"}, "setting_invalid", "guidance"),
        ("comparison", {"guidance": GUIDANCE_A, "family": "comparison"}, "setting_invalid", "guidance"),
        ("duplicate", {"guidance": GUIDANCE_A, "q": {"extra": (b"guidance: guidance.md",)}},
         "front_matter_invalid", "guidance"),
        ("override", {"guidance": GUIDANCE_A, "q": {"extra": (b"orientation: guidance.md",)}},
         "front_matter_invalid", "orientation"),
        ("invalid-utf8", {"guidance": b"valid\xff"}, "material_not_text", "guidance.md"),
        ("nul", {"guidance": b"valid\x00"}, "material_not_text", "guidance.md"),
        ("empty", {"guidance": b""}, "guidance_empty", "guidance.md"),
        ("whitespace", {"guidance": " \t\r\n\u2003".encode("utf-8")}, "guidance_empty", "guidance.md"),
        ("link", {"q": {"guidance": "guidance.md"}, "root_entries": [L("guidance.md", "materials/guidance.md")]},
         "unsupported_entry", "guidance.md"),
        ("directory", {"q": {"guidance": "guidance.md"}, "root_entries": [D("guidance.md")]},
         "unsupported_entry", "guidance.md"),
        ("fifo", {"q": {"guidance": "guidance.md"}, "root_entries": [FIFO("guidance.md")]},
         "unsupported_entry", "guidance.md"),
    ]
    for label, kw, reason, mentioned in bad:
        pre = "guidance.intake." + label
        sub = t.submission(entries(), body=BODY, **kw)
        t.new_ref(sub, name=pre + ".new")
        rep = t.prepare(sub, name=pre, expect="refused", reason=reason, timeout=15)
        t.eq(pre + ".no-preparation", t.log_kinds(sub).count("prepared"), 0)
        t.check(pre + ".names-entry", mentioned in str(rep.obj), mentioned)
    exact = t.submission([F("m%03d" % i, b"") for i in range(BOUNDS["files"])],
                         body=BODY, guidance=b"G" * BOUNDS["guidance_bytes"])
    t.accept(exact, prefix="guidance.intake.exact.", check_witness=True)
    provenance(t, exact, "guidance.intake.exact", accepted=True)
    t.check_readback_ok(exact, "guidance-file", exact.guidance, "guidance.intake.exact.readback")
    over = t.submission([], body=BODY, guidance=b"G" * (BOUNDS["guidance_bytes"] + 1))
    t.new_ref(over, name="guidance.intake.over.new")
    rep = t.prepare(over, name="guidance.intake.over", expect="refused", reason="bound_exceeded")
    t.check("guidance.intake.over.names-bound",
            all(names_bound(rep, "guidance_bytes", BOUNDS["guidance_bytes"], "guidance.md")), rep.obj)
    t.eq("guidance.intake.over.no-preparation", t.log_kinds(over).count("prepared"), 0)


@case("c15.guidance-capture", ["C1", "C15", "C17", "C19"],
      "guidance capture survives source edits, lost replies and continuation; damaged or missing capture stops readback and run",
      controls=[
          Control("accept_changed_source", [r"^guidance\.capture\.changed\.(outcome|reason)$"]),
          Control("readback_live_source", [r"^guidance\.capture\.edited-readback\.bytes$"])])
def c_guidance_capture(t):
    """A same-size edit with restored mtime refuses the old handle. Fresh preparation accepts
    B; on the test binary its reply is killed after the accepted link. Repeating the handle
    after a source edit returns the same receipt and makes no intake. Two interrupted fake
    placements, before and after source removal, send the independently witnessed B bytes.
    Changed HOME/cwd do not affect readback. Corrupting, then removing g.bin makes readback
    and run refuse while another material still reads; neither refused run reaches the fake."""
    sub = t.submission(entries(), body=BODY, guidance=GUIDANCE_A)
    t.new_ref(sub, name="guidance.capture.new")
    t.prepare(sub, name="guidance.capture.prepare-a")
    old = sub.handles[-1]
    path = os.path.join(sub.folder, "guidance.md")
    st = os.stat(path)
    t.require("guidance.capture.same-size", len(GUIDANCE_A) == len(GUIDANCE_B), "fixture sizes")

    def change():
        with open(path, "r+b") as f:
            f.write(GUIDANCE_B)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    t.driver_change("edit only guidance bytes, preserving size and mtime", change)
    sub.guidance = GUIDANCE_B
    t.save_witness(sub, label="guidance-b-before-prepare")
    changed = t.commission(sub, old, name="guidance.capture.changed", expect="refused", reason="selection_changed")
    t.eq("guidance.capture.changed.names", changed.data.get("changed"), ["guidance.md"])
    if changed.outcome == "completed":
        return  # The control's target fired; acceptance prevents a second prepare.
    t.prepare(sub, name="guidance.capture.prepare-b")
    handle = sub.handles[-1]
    if t.bin["kind"] == "test":
        rep = t.cmd(["commission", sub.ref, handle, "--i-am-finished"], name="guidance.capture.lost-reply",
                    envelope=False, fault="commission.after_accepted_link=kill")
        t.eq("guidance.capture.lost-reply.signal", rep.rc, -signal.SIGKILL)
        t.eq("guidance.capture.lost-reply.empty", rep.stdout, b"")
    else:
        t.commission(sub, handle, name="guidance.capture.accept")
    accepted = t.log_bodies(sub, "accepted")[-1]
    logs, intakes = t.log_kinds(sub), t.intake_dirs(sub)
    t.edit(path, b"Later source text cannot replace the accepted guidance.\n")
    rep = t.commission(sub, handle, name="guidance.capture.repeat", already=True)
    t.eq("guidance.capture.repeat.receipt", rep.data.get("receipt_sha256"), accepted.get("receipt_sha256"))
    t.eq("guidance.capture.repeat.no-new-log", t.log_kinds(sub), logs)
    t.eq("guidance.capture.repeat.no-new-intake", t.intake_dirs(sub), intakes)
    provenance(t, sub, "guidance.capture.accepted", accepted=True)
    t.check_readback_ok(sub, "guidance-file", GUIDANCE_B, "guidance.capture.edited-readback")
    home, cwd = t.fresh_dir("other-home"), t.fresh_dir("other-cwd")
    fx = None
    if t.drv.loopback_problem:
        t.skip_part("guidance requests, continuation and damaged/missing-capture run preflight", t.drv.loopback_problem)
        t.driver_change("remove the accepted guidance's live source", lambda: os.unlink(path))
        t.check_readback_ok(sub, "guidance-file", GUIDANCE_B, "guidance.capture.removed-readback",
                            env={"HOME": home}, cwd=cwd)
    else:
        fx = rs.provider(t, fp.Script([fp.HttpError(529, retry_after="61"), fp.HttpError(529, retry_after="61")]),
                         label="guidance-capture")
        for number in (1, 2):
            pre = "guidance.capture.run-%d" % number
            if number == 2:
                t.driver_change("remove the accepted guidance's live source", lambda: os.unlink(path))
            t.check_readback_ok(sub, "guidance-file", GUIDANCE_B, pre + ".readback", env={"HOME": home}, cwd=cwd)
            rep = rs.run(t, sub, fx, name=pre, env={"HOME": home}, cwd=cwd)
            ex = fx.exchanges_of(pre)
            rs.check_run_reply(t, rep, sub, pre, ending="interrupted", cause="provider_unavailable", run_number=number,
                               fx=fx, limits=rs.limits_of(sub),
                               provider=rs.provider_expected(ex[-1] if ex else None, 1, 1))
            if ex:
                rs.check_first_message(t, ex[0], sub.body, number > 1, pre)
        rs.check_requests(t, fx, sub, "guidance.capture")
    caps = t.capture_paths(sub)
    t.require("guidance.capture.located", len(caps.get("guidance-file", [])) == 1, caps)
    capture = caps["guidance-file"][0]
    t.flip_bit(capture)
    for label, diagnostic, state in (("damaged", "item_damaged", "damaged"), ("missing", "item_missing", "missing")):
        if label == "missing":
            quarantine = os.path.join(t.mkdir("quarantine"), "g.bin")
            t.driver_change("move damaged guidance capture outside Stewart", lambda: os.rename(capture, quarantine))
        pre = "guidance.capture." + label
        t.check_readback_refused(sub, "guidance-file", diagnostic, pre + ".readback")
        t.check_readback_ok(sub, "materials/evidence.txt", sub.files[b"evidence.txt"]["data"], pre + ".other-readback")
        verify = t.cmd(["receipt", sub.ref, "--verify"], name=pre + ".verify", expect="completed")
        items = find_items(verify.data, set(sub.items()))
        t.eq(pre + ".own-state", item_state(items.get("guidance-file", {})), state)
        t.eq(pre + ".other-state", item_state(items.get("materials/evidence.txt", {})), "verified")
        if fx is not None:
            count = len(fx.exchanges)
            rep = rs.run(t, sub, fx, name=pre + ".run", expect="refused", reason="commission_damaged")
            t.check(pre + ".named-item", contains_string(rep.data.get("items"), "guidance-file"), rep.data)
            t.eq(pre + ".no-provider-request", len(fx.exchanges), count)
            t.eq(pre + ".no-run-start", len(t.log_bodies(sub, "run_started")), 2)
