"""Captured Messages cap/refusal forms, from INTERFACE 6.2–6.5 and 7.4–7.5.

Original responses are opaque fixtures; the script, account and charge schedule
are synthetic. Origins and precise projection limits live in testdata/README.md.
"""
from pathlib import Path

import fake_provider as fp
import rawjson
import run_support as rs
from cases_run import proc, run_submission
from driver_core import CONTINUATION, NEAR_LIMIT, Control, case, selftest, sha256_hex


FIXTURES = Path(__file__).parent / "testdata/messages"
ACCOUNT = b"The supplied report claims success; this synthetic auditor did not witness execution."


class CapturedCap(fp.Message):
    def __init__(self, origin, variant="original"):
        if origin not in ("m2", "m3") or variant not in ("original", "ordinary", "thinking-count"):
            raise ValueError((origin, variant))
        body = (FIXTURES / (origin + "-cap.json")).read_bytes()
        node = rawjson.parse(body)
        if variant == "ordinary":
            target, value = node.get("stop_reason"), b'"end_turn"'
        elif variant == "thinking-count":
            target, value = node.get("usage").get("output_tokens_details").get("thinking_tokens"), b"1"
        if variant != "original":
            body = body[:target.start] + value + body[target.end:]
        self.captured = body
        inputs, outputs = (76034, 16000) if origin == "m2" else (70524, 6170)
        content = rawjson.parse(body).get("content")
        super().__init__([fp.Block(b.raw, "thinking") for b in content.items],
                         stop_reason="end_turn" if variant == "ordinary" else "max_tokens",
                         model="claude-haiku-5-5", label=origin + " captured cap: " + variant,
                         usage=fp.Usage(inputs, outputs, 0, 0, iterations=[
                             {"type": "message", "input_tokens": inputs, "output_tokens": outputs,
                              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}]))
        self.content_raw = content.raw

    def body(self, ex):
        return self.captured


def captured_replacement(handle):
    """Change only the original call's now-unusable audit-specific entry handle."""
    body = (FIXTURES / "m3-replace-missing-citations.json").read_bytes()
    target = rawjson.parse(body).get("input").get("entry")
    return body[:target.start] + rawjson.compact(handle) + body[target.end:]


def check_placement(t, sub, fx, name, number, reply, ending, cause):
    rs.check_run_reply(t, reply, sub, name, ending=ending, cause=cause, run_number=number,
                       fx=fx, limits=rs.limits_of(sub))
    rs.check_run_ended(t, sub, number, name, ending=ending, cause=cause,
                       requests=2 if number == 1 else 6, attempts=2 if number == 1 else 6)
    exs = fx.exchanges_of(name)
    ended = rs.run_ended_of(t, sub, number) or {}
    t.eq(name + ".run-ended-usage", ended.get("usage"), fx.totals(exs))
    rs.check_requests(t, fx, sub, name, exchanges=exs)
    rs.check_history(t, fx, name, exchanges=exs)
    rs.check_captures(t, sub, fx, name, run_number=number, exchanges=exs)


@case("c13.captured-cap", ["C4", "C6", "C7", "C13", "C14"],
      "M2/M3 thinking-only caps preserve work, refuse incomplete replacement and consume cumulative output",
      needs=("loopback",), controls=[
          Control("reset_limits_on_continuation", [r"^captured\.cap\.original\.second\.request-caps$"]),
          Control("fresh_ledger_on_continuation", [r"^captured\.cap\.original\.reentry\.entries$"]),
          Control("omit_effects_on_refusal", [r"^captured\.cap\.original\.refusal\.effects$"])])
def c_captured_cap(t):
    totals = {}
    for variant in ("original", "ordinary", "thinking-count"):
        pre = "captured.cap." + variant
        sub = run_submission(t, entries=[], body=b"Explain the supplied report's limits.\n",
                             model="claude-haiku-5-5",
                             q={"turns": "20", "input_tokens": "1000000", "output_tokens": "40170"})
        near = NEAR_LIMIT.format(turns=17, input_tokens=921966, output_tokens=6170)

        def body(p):
            turn = yield p.calls_step(("record_account", {"text": ACCOUNT.decode()}), usage=fp.Usage(1000, 12000))
            r = turn.reply()
            p.eq("recorded", (r.outcome, r.data.get("id"), r.data.get("revision")), ("completed", "e1", 1))
            original_handle = r.data.get("entry")
            turn = yield CapturedCap("m2")
            p.eq("fresh-conversation", turn.new_conversation, True)
            p.eq("continuation-input", turn.first_message.value() if turn.first_message else None,
                 {"role": "user", "content": [{"type": "text", "text": sub.body.decode()},
                                               {"type": "text", "text": CONTINUATION}]})
            p.usage = lambda: fp.Usage(1000, 0)
            turn = yield p.calls_step(("what_am_i_working_with", {}), usage=fp.Usage(1000, 6000))
            state = turn.reply().data
            entries = state.get("entries") or []
            p.eq("reentry.entries", [(e.get("id"), e.get("entry")) for e in entries], [("e1", original_handle)])
            p.eq("reentry.revision", state.get("revision"), 1)
            p.eq("reentry.used-output", state.get("allowances", {}).get("output_tokens", {}).get("used"), 34000)
            p.eq("reentry.notice", turn.texts, [near])
            # A missing entry must fail the re-entry check without crashing the
            # fixture; the old handle lets the remaining refusal checks run.
            handle = entries[0].get("entry") if entries else original_handle
            text, _ = yield from p.read_all(handle)
            p.eq("read-before-refusal", text, ACCOUNT)
            raw = captured_replacement(handle)
            call = rawjson.parse(raw)
            turn = yield p.step([p.call("replace", input=call.get("input").value(),
                                       raw_input=call.get("input").raw, tid=call.get("id").value(), raw_block=raw)])
            refused = turn.reply()
            p.eq("refusal.reason", (refused.outcome, refused.reason), ("refused", "fields_invalid"))
            p.eq("refusal.fields", refused.data,
                 {"entry_kind": "record_account", "missing": ["citations"], "not_allowed": []})
            p.eq("refusal.effects", refused.effects, {"answer": "unchanged", "raw_capture": "recorded"})
            turn = yield p.calls_step(("what_am_i_working_with", {}))
            state = turn.reply().data
            p.eq("refusal.revision", state.get("revision"), 1)
            p.eq("refusal.entries", [(e.get("id"), e.get("entry")) for e in state.get("entries", [])],
                 [("e1", original_handle)])
            text, _ = yield from p.read_all(handle)
            p.eq("read-after-refusal", text, ACCOUNT)
            yield CapturedCap("m3", variant)

        p = proc(sub, body)
        fx = rs.provider(t, p, label=variant, accepts=fp.MESSAGES_API)
        first = rs.run(t, sub, fx, name=pre + ".first")
        check_placement(t, sub, fx, pre + ".first", 1, first, "interrupted", "max_tokens")
        t.eq(pre + ".first.request-caps", [e.max_tokens() for e in fx.exchanges], [16000, 16000])
        t.eq(pre + ".first.no-notices", first.data.get("notices"), [])
        status = t.status(sub, name=pre + ".between")
        t.eq(pre + ".between.next", sorted({a[1] for a in status.next_argvs()}), ["close", "run"])
        second = rs.run(t, sub, fx, name=pre + ".second")
        ending = "limit_reached" if variant == "ordinary" else "interrupted"
        cause = None if variant == "ordinary" else "max_tokens"
        check_placement(t, sub, fx, pre + ".second", 2, second, ending, cause)
        rs.check_procedure(t, p, pre, fx)
        rs.check_run_records(t, sub, pre)
        t.eq(pre + ".second.request-caps", [e.max_tokens() for e in fx.exchanges_of(pre + ".second")],
             [12170, 6170, 6170, 6170, 6170, 6170])
        t.eq(pre + ".notices", p.texts, [near])
        notices = t.log_bodies(sub, "notice")
        t.eq(pre + ".notice-record", [(n.get("type"), n.get("run"), n.get("request"), n.get("text")) for n in notices],
             [("near_limit", 2, 2, near)])
        t.eq(pre + ".notice-transmitted", second.data.get("notices"), [{"type": "near_limit", "sent": "sent"}])
        t.eq(pre + ".entry-actions", [b.get("action") for b in rs.entry_bodies(t, sub)], ["add"])
        payload = Path(sub.audit_dir) / "payload/e1.v1.bin"
        t.eq(pre + ".retained-account", payload.read_bytes() if payload.is_file() else None, ACCOUNT)
        t.eq(pre + ".payload-members", sorted(p.name for p in payload.parent.iterdir()) if payload.parent.is_dir() else None,
             ["e1.v1.bin"])
        t.eq(pre + ".no-seal", t.log_bodies(sub, "seal"), [])
        status = t.status(sub, name=pre + ".status")
        t.eq(pre + ".last-ending", (status.data.get("runs", {}).get("last") or {}).get("ending"), ending)
        t.eq(pre + ".only-close", sorted({a[1] for a in status.next_argvs()}), ["close"])
        totals[variant] = status.data.get("allowances")
        expected = {"turns": {"reported": 8, "estimated": 0},
                    "input_tokens": {"reported": 152558, "estimated": 0},
                    "output_tokens": {"reported": 40170, "estimated": 0}}
        t.eq(pre + ".literal-total", fx.totals(), expected)
        t.eq(pre + ".cumulative-allowances", totals[variant], fp.allowances(expected, rs.limits_of(sub)))
    t.eq("captured.cap.usage-invariance", list(totals.values()), [totals["original"]] * 3)


@selftest
def captured_cap_selftests():
    import copy
    import json
    out = []
    for origin, size, digest, inputs, outputs in (
        ("m2", 54949, "f2dc69b90bd373506e4029d09df7490e67f3f801a69863e59915fd6f8da1d562", 76034, 16000),
        ("m3", 21530, "7d6e531186186ba37cc42388d2d6f5680115dc3d56d23387ee3ccae76082a7b1", 70524, 6170),
    ):
        step = CapturedCap(origin)
        value = json.loads(step.captured)
        out += [(origin + ".cap.size", len(step.captured) == size),
                (origin + ".cap.digest", sha256_hex(step.captured) == digest),
                (origin + ".cap.thinking-only", [b["type"] for b in value["content"]] == ["thinking"]),
                (origin + ".cap.stop", value["stop_reason"] == "max_tokens"),
                (origin + ".cap.charge", step.charge(None) ==
                 {"basis": "reported", "turns": 1, "input_tokens": inputs, "output_tokens": outputs})]
    original = CapturedCap("m3")
    for variant in ("ordinary", "thinking-count"):
        step = CapturedCap("m3", variant)
        expected = copy.deepcopy(json.loads(original.captured))
        if variant == "ordinary":
            expected["stop_reason"] = "end_turn"
            raw = original.captured.replace(b'"stop_reason":"max_tokens"', b'"stop_reason":"end_turn"', 1)
        else:
            expected["usage"]["output_tokens_details"]["thinking_tokens"] = 1
            raw = original.captured.replace(b'"thinking_tokens":6170', b'"thinking_tokens":1', 1)
        out += [("m3.cap." + variant + ".one-field", json.loads(step.captured) == expected),
                ("m3.cap." + variant + ".one-span", step.captured == raw),
                ("m3.cap." + variant + ".content-invariant", step.content_raw == original.content_raw),
                ("m3.cap." + variant + ".charge-invariant", step.charge(None) == original.charge(None))]
    raw = (FIXTURES / "m3-replace-missing-citations.json").read_bytes()
    changed = captured_replacement("e1.v1.synthetic")
    value = json.loads(raw)
    original_handle = value["input"]["entry"]
    value["input"]["entry"] = "e1.v1.synthetic"
    out += [("m3.replace.digest", len(raw) == 1030 and sha256_hex(raw) ==
             "e480c004bea835f76e0deaea7b2a56a6c2d3a43a0051e8ebfaf0d90765f7254c"),
            ("m3.replace.handle-only", json.loads(changed) == value),
            ("m3.replace.handle-span", changed == raw.replace(original_handle.encode(), b"e1.v1.synthetic", 1)),
            ("m3.replace.missing-citations", set(value["input"]) == {"entry", "label", "text"})]
    notice = (FIXTURES / "m3-near-limit.txt").read_bytes()
    out += [("m3.near-limit.digest", len(notice) == 182 and sha256_hex(notice) ==
             "e2c5ac7ed5659d93d7150e7ba1a85703bf7a016efdf95f8451843a5ed2eb3a95"),
            ("m3.near-limit.form", notice == NEAR_LIMIT.format(
                turns=35, input_tokens=9145049, output_tokens=12271).encode())]
    return out
