"""Archive writes that fail partway and the retained-payload limits, from INTERFACE 1.3, 1.4,
4.3, 4.8, 5.4, 5.7, 6.3, 7.1, 7.4, 8.3 and Appendix C. Written without reading service/.

Each failure is injected with an Appendix C.1 point on the test build. The cases judge what the
reply says was established against what the archive then holds, and what the next ordinary
command does with the unfinished record.
"""
from __future__ import annotations

import os

import fake_provider as fp
import run_support as rs
from cases_run import prepare_and_submit, proc, run_submission
from driver_core import F, case

MiB = 1 << 20


def no_diag_effects(effects):
    return {k: v for k, v in (effects or {}).items() if k != "diagnostic"}


def _one(p, tool, inp):
    """One call in a response of its own; its reply (None when the placement ended instead)."""
    turn = yield p.calls_step((tool, inp))
    return turn.reply(0) if turn is not None else None


def _state(r):
    return (r.outcome, r.reason) if r is not None else None


# ---------------------------------------------------------------------------
# 7.4: the retained-payload cap and reserve, with STEWART_TEST_RETAINED_LIMITS.
# ---------------------------------------------------------------------------

CAP, RESERVE = 2000, MiB + 500


def _retained_body(p):
    """7.4 at CAP=2000 and RESERVE=1 MiB + 500, in one conversation (the payload is the text's
    UTF-8 bytes): a 1 MiB + 1 byte addition before the cap is reached is admitted; two 1000-byte
    replacements of e1 retain 1000 and then 2000 bytes, the second reaching the cap with no
    reserve; then a 1 MiB + 1 byte addition is retained_payload_cap, an addition of exactly
    1 MiB draws on the reserve, a 500-byte replacement uses the reserve exactly, and a 1-byte
    addition and a 1-byte replacement are retained_payload_reserve_exhausted. A delete still
    completes, and prepare and submit seal."""
    r = yield from _one(p, "record_observation", {"text": "a" * 1000})
    p.eq("e1.add", _state(r), ("completed", None))
    h1 = r.data.get("entry") if r else None
    r = yield from _one(p, "record_observation", {"text": "b" * (MiB + 1)})
    p.eq("large-before-cap", _state(r), ("completed", None))
    h2 = r.data.get("entry") if r else None
    r = yield from _one(p, "replace", {"entry": h1, "text": "c" * 1000, "citations": [], "label": ""})
    p.eq("replace-retains-1000", _state(r), ("completed", None))
    h1 = r.data.get("entry") if r else h1
    r = yield from _one(p, "replace", {"entry": h1, "text": "d" * 1000, "citations": [], "label": ""})
    p.eq("replace-reaches-cap", _state(r), ("completed", None))
    h1 = r.data.get("entry") if r else h1
    r = yield from _one(p, "record_observation", {"text": "e" * (MiB + 1)})
    p.eq("over-1mib-after-cap", _state(r), ("refused", "retained_payload_cap"))
    r = yield from _one(p, "record_observation", {"text": "f" * MiB})
    p.eq("1mib-draws-reserve", _state(r), ("completed", None))
    r = yield from _one(p, "replace", {"entry": h1, "text": "g" * 500, "citations": [], "label": ""})
    p.eq("reserve-used-exactly", _state(r), ("completed", None))
    h1 = r.data.get("entry") if r else h1
    r = yield from _one(p, "record_observation", {"text": "h"})
    p.eq("add-after-reserve", _state(r), ("refused", "retained_payload_reserve_exhausted"))
    r = yield from _one(p, "replace", {"entry": h1, "text": "i", "citations": [], "label": ""})
    p.eq("replace-after-reserve", _state(r), ("refused", "retained_payload_reserve_exhausted"))
    r = yield from _one(p, "delete", {"entry": h2})
    p.eq("delete-after-reserve", _state(r), ("completed", None))
    yield from prepare_and_submit(p, "retained.seal")


def _overdraw_body(p):
    """7.4 at CAP=1000 and RESERVE=300: after the cap is reached, an addition is admitted only
    when its whole charge fits in the reserve left. 200 bytes fit with 300 left; another 200 do
    not with 100 left, so it is refused rather than overdrawing the reserve."""
    r = yield from _one(p, "record_observation", {"text": "a" * 600})
    h = r.data.get("entry") if r else None
    for text in ("b" * 600, "c" * 600):
        r = yield from _one(p, "replace", {"entry": h, "text": text, "citations": [], "label": ""})
        h = r.data.get("entry") if r else h
    p.eq("overdraw.cap-reached", _state(r), ("completed", None))
    r = yield from _one(p, "record_observation", {"text": "x" * 200})
    p.eq("overdraw.fits", _state(r), ("completed", None))
    r = yield from _one(p, "record_observation", {"text": "y" * 200})
    p.eq("overdraw.does-not-fit", _state(r), ("refused", "retained_payload_reserve_exhausted"))
    yield p.end("Stopping.")


@case("c3.retained-limits", ["C3", "C6", "C20"],
      "the retained-payload cap and reserve admit and refuse edits at their boundaries (7.4)",
      mode="test", needs=("loopback",))
def c_retained_limits(t):
    """With STEWART_TEST_RETAINED_LIMITS=2000,1049076 (Appendix C): admission uses the retained
    total before the edit; the edit that reaches the cap uses no reserve; after it an edit over
    1 MiB is retained_payload_cap and smaller ones charge their full size to the reserve, an exact
    fit is admitted and any later addition or replacement is retained_payload_reserve_exhausted;
    deletion, prepare and submit never refuse. The run seals and delivers. A second audit at
    1000,300: once the cap is reached a 200-byte addition fits the 300 left and is admitted, and
    the next 200-byte addition, with 100 left, is retained_payload_reserve_exhausted (an edit is
    admitted only when its whole charge fits)."""
    sub = run_submission(t)
    p = proc(sub, _retained_body)
    fx = rs.provider(t, p, label="retained")
    env = {"STEWART_TEST_RETAINED_LIMITS": "%d,%d" % (CAP, RESERVE)}
    rep = rs.run(t, sub, fx, name="retained.run", env=env, timeout=600)
    rs.check_run_reply(t, rep, sub, "retained.run", ending="sealed", run_number=1, fx=fx, limits=rs.limits_of(sub),
                       seal_actor="auditor", delivery_outcome="verified")
    rs.check_procedure(t, p, "retained", fx)
    sub2 = run_submission(t)
    p2 = proc(sub2, _overdraw_body)
    fx2 = rs.provider(t, p2, label="overdraw")
    rep = rs.run(t, sub2, fx2, name="retained.overdraw", env={"STEWART_TEST_RETAINED_LIMITS": "1000,300"})
    rs.check_run_reply(t, rep, sub2, "retained.overdraw", ending="ended_unsubmitted", run_number=1, fx=fx2,
                       limits=rs.limits_of(sub2))
    rs.check_procedure(t, p2, "retained", fx2)


# ---------------------------------------------------------------------------
# 7.1: an auditor call whose log record or result record cannot be linked.
# ---------------------------------------------------------------------------

def _record_then_account(p):
    yield p.calls_step(("record_observation", {"text": "First, recorded before the failure."}),
                       ("record_account", {"text": "Second, in the same response."}))


@case("c17.auditor-record-failures", ["C17", "C3", "C6", "C20"],
      "an auditor call whose entry or result record cannot be linked fails record_failed with what is known, "
      "and the placement ends archive_write_failed",
      mode="test", needs=("loopback",), faults=("log.publish:entry=eio", "runs.publish:tool_result=eio"))
def c_auditor_record_failures(t):
    """7.1 and 6.5. A response carries record_observation then record_account. With the entry
    record's link failing (log.publish:entry=eio) the first call's result record is failed
    record_failed with effects answer unchanged, raw_capture recorded and a diagnostic, no entry
    is recorded, the second call is neither captured nor executed, no further request is sent,
    and the run ends interrupted archive_write_failed (exit 5) with answer unchanged. With the
    entry linked but its result record failing (runs.publish:tool_result=eio) the entry stands,
    no result record exists, the second call is not captured, and the run reports answer
    changed. Status counts the entries the log holds."""
    for label, fault, linked in (("entry-link", "log.publish:entry=eio", False),
                                 ("result-link", "runs.publish:tool_result=eio", True)):
        pre = "auditor-fail." + label
        sub = run_submission(t)
        p = proc(sub, _record_then_account)
        fx = rs.provider(t, p, label=label)
        rep = rs.run(t, sub, fx, name=pre + ".run", fault=fault)
        rs.check_run_reply(t, rep, sub, pre + ".run", ending="interrupted", cause="archive_write_failed",
                           run_number=1, fx=fx, limits=rs.limits_of(sub))
        t.eq(pre + ".run.exit", rep.rc, 5)
        t.eq(pre + ".run.effects", no_diag_effects(rep.effects),
             {"run": "ended", "answer": "changed" if linked else "unchanged", "seal": "none", "delivery": "none"})
        t.eq(pre + ".one-request", len(fx.exchanges), 1)
        t.eq(pre + ".entry-records", len(rs.entry_bodies(t, sub)), 1 if linked else 0)
        rd = rs.run_dirs(sub).get(1)
        t.require(pre + ".run-dir", rd is not None, sorted(rs.run_dirs(sub)))
        t.eq(pre + ".one-call-captured", sorted(rd.calls), [1])
        if linked:
            t.eq(pre + ".no-result-record", sorted(rd.results), [])
        else:
            t.eq(pre + ".result-record", sorted(rd.results), [1])
            env = rs.result_envelope((rd.results.get(1) or {}).get("body") or {}) or {}
            t.eq(pre + ".result", (env.get("outcome"), env.get("reason")), ("failed", "record_failed"))
            t.eq(pre + ".result.effects", env.get("effects"),
                 {"answer": "unchanged", "raw_capture": "recorded", "diagnostic": "durable"})
        st = t.status(sub, name=pre + ".status")
        t.eq(pre + ".status.condition", st.data.get("condition"), "interrupted")
        t.eq(pre + ".status.entries", (st.data.get("answer") or {}).get("entries"), 1 if linked else 0)
        rs.check_procedure(t, p, pre, fx)


# ---------------------------------------------------------------------------
# 6.3 and 8.3: the run's delivery records failing to publish.
# ---------------------------------------------------------------------------

def _record_and_seal(p):
    yield p.calls_step(("record_observation", {"text": "Recorded, then sealed."}))
    yield from prepare_and_submit(p, "delivery-records.seal")


def _package_names(sub):
    return sorted(n for n in os.listdir(sub.dest) if n.startswith("stewart-return-")) if os.path.isdir(sub.dest) else []


@case("c5.run-delivery-records", ["C5", "C17", "C20", "C8"],
      "a run whose delivery_planned or delivery_ended cannot be published reports delivery unknown; close then "
      "reconciles and delivers",
      mode="test", needs=("loopback",),
      faults=("log.publish:delivery_planned=eio", "log.publish:delivery_ended=eio"))
def c_run_delivery_records(t):
    """After the auditor's seal the run delivers (6.3, 8.3). When delivery_planned cannot be
    linked, nothing is written at the destination; when delivery_ended cannot be linked the
    package of attempt 1 is. Either way the run's effects say seal recorded and delivery unknown
    (1.4), and its outcome follows 5.7: completed with ending sealed if run_ended was published,
    else failed record_failed with run started. Close then delivers: after the planned failure
    as attempt 2 (attempt 1's plan file stays claimed, 4.3) replacing nothing; after the ended
    failure it first reconciles attempt 1 as failed with cause deliver/process_gone and makes
    attempt 2, which replaces it; attempt 1's package stays. Both await confirmation."""
    for label, fault in (("planned", "log.publish:delivery_planned=eio"), ("ended", "log.publish:delivery_ended=eio")):
        pre = "delivery-records." + label
        sub = run_submission(t)
        p = proc(sub, _record_and_seal)
        fx = rs.provider(t, p, label=label)
        rep = rs.run(t, sub, fx, name=pre + ".run", fault=fault, expect=None)
        kinds = t.log_kinds(sub)
        if "run_ended" in kinds:
            t.eq(pre + ".run.outcome", rep.outcome, "completed")
            t.eq(pre + ".run.ending", rep.data.get("ending"), "sealed")
        else:
            t.eq(pre + ".run.outcome", (rep.outcome, rep.reason), ("failed", "record_failed"))
            t.eq(pre + ".run.started", rep.effects.get("run"), "started")
        t.eq(pre + ".run.effects", {k: rep.effects.get(k) for k in ("answer", "seal", "delivery")},
             {"answer": "changed", "seal": "recorded", "delivery": "unknown"})
        t.eq(pre + ".packages-after-run", _package_names(sub),
             [] if label == "planned" else ["stewart-return-%s-001" % sub.audit])
        close = t.cmd(["close", sub.ref], name=pre + ".close", expect="completed")
        d = close.data
        t.eq(pre + ".close.effects", no_diag_effects(close.effects),
             {"run": "ended", "seal": "existing", "delivery": "verified", "closure": "unfinished"})
        t.eq(pre + ".close.unfinished", d.get("unfinished_reason"), "awaiting_confirmation")
        t.eq(pre + ".close.attempt", (d.get("delivery") or {}).get("attempt"), 2)
        planned = [b for b in t.log_bodies(sub, "delivery_planned") if isinstance(b, dict)]
        t.eq(pre + ".planned", [(b.get("attempt"), b.get("by"), b.get("replaces")) for b in planned],
             [(2, "close", None)] if label == "planned" else [(1, "run", None), (2, "close", 1)])
        ended = [b for b in t.log_bodies(sub, "delivery_ended") if isinstance(b, dict)]
        if label == "ended":
            first = [b for b in ended if b.get("attempt") == 1]
            t.eq(pre + ".reconciled", [(b.get("outcome"), b.get("cause"), b.get("recorded_by")) for b in first],
                 [("failed", {"operation": "deliver", "error": "process_gone"}, "close")])
        t.eq(pre + ".packages-after-close", _package_names(sub),
             ["stewart-return-%s-%03d" % (sub.audit, n) for n in ((2,) if label == "planned" else (1, 2))])
        rs.check_procedure(t, p, pre, fx)


# ---------------------------------------------------------------------------
# 5.4: an intake whose ending cannot be published.
# ---------------------------------------------------------------------------

@case("c17.intake-ending-unrecorded", ["C17", "C6", "C16"],
      "a receipt failure whose intake_ended cannot be published reports it separately; the next commission "
      "reconciles the attempt",
      mode="test", faults=("commission.receipt_write=eio", "log.publish:intake_ended=eio"))
def c_intake_ending_unrecorded(t):
    """5.4: a receipt that cannot be written fails receipt_record_failed with acceptance absent
    and the attempt partial; it records that intake ending when possible, and failure to record
    it is reported separately, as a second entry in causes: with intake_ended's link failing too,
    the reply keeps its reason and effects, no intake_ended exists, and its two causes are the
    receipt write failure, exactly as that failure alone reports it, then a second EIO. A refused
    intake (a changed selection) whose ending cannot be linked stays selection_changed with two
    causes, the refusal and then the ending-link EIO (1.3). Status then sees an intake without an outcome (intake_failed);
    the next commission publishes intake_ended process_gone for attempt 1 and accepts attempt 2."""
    # The original cause, as the same receipt failure alone reports it (its ending recorded).
    base = t.submission([F("a.txt", b"alpha\n"), F("b.txt", b"bravo\n")])
    t.new_ref(base, name="intake-ending.base.new")
    t.prepare(base, name="intake-ending.base.prepare")
    r0 = t.commission(base, base.handles[-1], name="intake-ending.base", expect="failed",
                      reason="receipt_record_failed", fault="commission.receipt_write=eio")
    original = (r0.obj or {}).get("causes") or []
    t.eq("intake-ending.base.one-cause", len(original), 1)
    sub = t.submission([F("a.txt", b"alpha\n"), F("b.txt", b"bravo\n")])
    t.new_ref(sub)
    t.prepare(sub)
    h = sub.handles[-1]
    rep = t.commission(sub, h, name="intake-ending.commission", expect="failed", reason="receipt_record_failed",
                       fault="commission.receipt_write=eio,log.publish:intake_ended=eio")
    t.eq("intake-ending.effects", no_diag_effects(rep.effects), {"acceptance": "absent", "attempt": "partial"})
    t.eq("intake-ending.log-tail", t.log_kinds(sub)[-1:], ["intake_planned"])
    # 5.4: the unrecorded ending is a second entry in causes, the original (the receipt write) first.
    causes = (rep.obj or {}).get("causes") or []
    t.eq("intake-ending.two-causes", len(causes), 2)
    t.check("intake-ending.original-first", bool(causes) and bool(original) and causes[0] == original[0],
            {"causes": causes, "original": original})
    t.check("intake-ending.ending-second", len(causes) == 2 and isinstance(causes[1], dict)
            and causes[1].get("error") == "EIO" and causes[1] != causes[0], causes)
    # A refused intake (changed selection) whose ending cannot be linked: still selection_changed,
    # with causes [the refusal, the ending-link failure] (1.3, 5.4).
    ref = t.submission([F("a.txt", b"alpha\n"), F("b.txt", b"bravo\n")])
    t.new_ref(ref, name="intake-ending.refused.new")
    t.prepare(ref, name="intake-ending.refused.prepare")
    t.edit(os.path.join(ref.folder, "materials", "a.txt"), b"alpha changed after prepare\n")
    r2 = t.commission(ref, ref.handles[-1], name="intake-ending.refused", expect="refused", reason="selection_changed",
                      fault="log.publish:intake_ended=eio")
    t.eq("intake-ending.refused.effects", no_diag_effects(r2.effects), {"acceptance": "absent", "attempt": "partial"})
    t.check("intake-ending.refused.no-ending", "intake_ended" not in t.log_kinds(ref), t.log_kinds(ref))
    c2 = (r2.obj or {}).get("causes") or []
    t.eq("intake-ending.refused.two-causes", len(c2), 2)
    t.check("intake-ending.refused.ending-second", len(c2) == 2 and isinstance(c2[1], dict)
            and c2[1].get("error") == "EIO" and c2[0] != c2[1], c2)
    st = t.status(sub, name="intake-ending.status")
    t.eq("intake-ending.status.condition", st.data.get("condition"), "intake_failed")
    t.commission(sub, h, name="intake-ending.retry")
    ended = [b for b in t.log_bodies(sub, "intake_ended") if isinstance(b, dict)]
    t.eq("intake-ending.reconciled", [(b.get("attempt"), b.get("outcome"), b.get("recorded_by")) for b in ended],
         [(1, "process_gone", "commission")])
    t.eq("intake-ending.attempts", len(t.intake_dirs(sub)), 2)
