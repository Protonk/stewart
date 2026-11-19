"""Captured Messages responses, from INTERFACE 4.5, 6.2–6.6 and 7.4–7.5.

Original responses are opaque fixtures; the script, account and charge schedule
are synthetic. Origins and precise projection limits live in testdata/README.md.
"""
from pathlib import Path
from types import SimpleNamespace

import answer_witness as aw
import fake_provider as fp
import rawjson
import run_support as rs
from cases_run import proc, run_submission
from driver_core import CONTINUATION, NEAR_LIMIT, REMINDER, Control, F, case, selftest, sha256_hex


FIXTURES = Path(__file__).parent / "testdata/messages"
ACCOUNT = b"The supplied report claims success; this synthetic auditor did not witness execution."
AUTH_BODY_ID = "req_000000000000000000000000"


def authentication_error_step(body, header_id):
    headers = [("request-id", header_id)] if header_id is not None else []
    return fp.HttpError(401, body=body, request_id_header=False, headers=headers)


@selftest
def captured_authentication_error_selftest():
    body = (FIXTURES / "sanity-authentication-error.json").read_bytes()
    out = [("captured.401.projected-body", len(body) == 130 and sha256_hex(body) ==
            "0366ef8a85e9d5f36b6541f5f64a89a8d785d0242693c9ab256621f6d6c0f380")]
    for name, header_id, line, reported_id in (
        ("original", AUTH_BODY_ID, b"request-id: req_000000000000000000000000\r\n", AUTH_BODY_ID),
        ("different-header", "req_header_test", b"request-id: req_header_test\r\n", "req_header_test"),
        ("absent-header", None, b"", AUTH_BODY_ID),
    ):
        step = authentication_error_step(body, header_id)
        wire = b"".join(step.framed(None))
        expected = (b"HTTP/1.1 401 Unauthorized\r\ncontent-type: application/json\r\n" + line +
                    b"content-length: 130\r\nconnection: close\r\n\r\n" + body)
        facts = fp.provider_facts(SimpleNamespace(response_raw=wire))
        out += [("captured.401." + name + ".wire", wire == expected),
                ("captured.401." + name + ".provider", facts == {
                    "status": 401, "error_type": "authentication_error", "error_message": "invalid x-api-key",
                    "request_id": reported_id})]
    return out


@case("c9.captured-authentication-error", ["C9", "C6"],
      "captured 401 retains its body, uses the header request ID before the body ID and costs nothing",
      needs=("loopback",), controls=[Control("hide_provider_message", [
          r"^captured\.401\.original\.(provider|run_ended\.provider)$"])])
def c_captured_authentication_error(t):
    """Serve the projected body with its recorded selected headers. Change only the request-id
    header, then omit it. The attempt keeps the body's ID in all three placements. The run
    reply and ending prefer the different header ID and fall back to the body ID on omission."""
    body = (FIXTURES / "sanity-authentication-error.json").read_bytes()
    for variant, header_id, expected_id in (
        ("original", AUTH_BODY_ID, AUTH_BODY_ID),
        ("different-header", "req_synthetic_header_only", "req_synthetic_header_only"),
        ("absent-header", None, AUTH_BODY_ID),
    ):
        if t.sabotage and variant != "original":
            continue
        name = "captured.401." + variant
        sub = t.submission([])
        t.accept(sub, prefix=name + ".")
        step = authentication_error_step(body, header_id)
        fx = rs.provider(t, fp.Script([step], then=lambda ex: fp.HttpError(400)), label=variant)
        rep = rs.run(t, sub, fx, name=name)
        facts = rs.check_rejection(t, sub, fx, rep, name, run_number=1)
        t.eq(name + ".witness-provider", facts,
             {"status": 401, "error_type": "authentication_error", "error_message": "invalid x-api-key",
              "request_id": expected_id, "request": 1, "attempt": 1})
        expected_headers = {"content-type": ["application/json"],
                            "request-id": [header_id] if header_id is not None else [], "retry-after": []}
        exs = fx.exchanges_of(name)
        if len(exs) == 1:  # check_rejection checks the exchange count.
            _, sent_headers, sent_body, complete, _ = fp.parse_response(exs[0].response_raw)
            selected = {k: [v for n, v in sent_headers if n.lower() == k] for k in expected_headers}
            t.eq(name + ".witness-headers", selected, expected_headers)
            t.eq(name + ".witness-body", (complete, sent_body), (True, body))
        rd = rs.run_dirs(sub).get(1)
        if rd is None:  # check_rejection checks the run directory.
            continue
        t.eq(name + ".archived-attempts", sorted(rd.attempts), [(1, 1)])
        record = (rd.attempts.get((1, 1)) or {}).get("body") or {}
        t.eq(name + ".archived-headers", record.get("headers"), expected_headers)
        t.eq(name + ".archived-error", record.get("error"),
             {"type": "authentication_error", "message": "invalid x-api-key", "request_id": AUTH_BODY_ID})
        t.eq(name + ".request-written", record.get("request_written"), "complete")
        t.eq(name + ".reflection", record.get("credential_reflection"), {"body": False, "headers": []})
        t.eq(name + ".charge", record.get("charged"),
             {"basis": "none", "turns": 0, "input_tokens": 0, "output_tokens": 0})
        t.eq(name + ".ending-usage", (rs.run_ended_of(t, sub, 1) or {}).get("usage"),
             {k: {"reported": 0, "estimated": 0} for k in ("turns", "input_tokens", "output_tokens")})


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


def captured_replacement(handle, filename="m3-replace-missing-citations.json"):
    """Change only the original call's now-unusable audit-specific entry handle."""
    body = (FIXTURES / filename).read_bytes()
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
    variants = ("original",) if t.sabotage else ("original", "ordinary", "thinking-count")
    for variant in variants:
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
    if not t.sabotage:
        t.eq("captured.cap.usage-invariance", list(totals.values()), [totals["original"]] * 3)


class CapturedOrdinary(fp.Message):
    def __init__(self, variant="spent"):
        body = (FIXTURES / "m3-ordinary-ending.json").read_bytes()
        node = rawjson.parse(body)
        if variant == "unused":
            target, value = node.get("stop_reason"), b'"max_tokens"'
        elif variant == "diagnostic":
            target, value = node.get("usage").get("output_tokens_details").get("thinking_tokens"), b"1"
        elif variant != "spent":
            raise ValueError(variant)
        if variant != "spent":
            body = body[:target.start] + value + body[target.end:]
        self.captured = body
        content = rawjson.parse(body).get("content")
        super().__init__([fp.Block(b.raw, "text") for b in content.items],
                         stop_reason="max_tokens" if variant == "unused" else "end_turn",
                         model="claude-haiku-5-5", label="M3 ordinary ending: " + variant,
                         usage=fp.Usage(6660, 248, 0, 0, iterations=[
                             {"type": "message", "input_tokens": 6660, "output_tokens": 248,
                              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}]))
        self.content_raw = content.raw

    def body(self, ex):
        return self.captured


def replacement_call(p, filename, handle):
    raw = captured_replacement(handle, filename)
    call = rawjson.parse(raw)
    return p.call("replace", input=call.get("input").value(), raw_input=call.get("input").raw,
                  tid=call.get("id").value(), raw_block=raw)


@case("c13.captured-reminder", ["C4", "C6", "C7", "C13", "C14"],
      "M3 ordinary ending and citation recovery preserve entries and spend the reminder only once across continuation",
      needs=("loopback",), controls=[
          Control("reset_notice_allowance", [r"^captured\.reminder\.spent\.reminder-once$"]),
          Control("reentry_omit_entry", [r"^captured\.reminder\.spent\.reentry\.entries$"]),
          Control("remove_superseded_payload", [r"^captured\.reminder\.spent\.retained-v1$"])])
def c_captured_reminder(t):
    material = (FIXTURES / "m3-supplied-report.txt").read_bytes()
    corrected = rawjson.parse((FIXTURES / "m3-citation-corrected.json").read_bytes()).get("input").value()
    citations = [aw.record_citation(c, {"materials/context/supplied-report.txt": material})
                 for c in corrected["citations"]]
    observation = b"The supplied report is an illustrative fixture."
    limit = b"This comparison witnesses no execution of the report's subject."
    expected_selection = aw.answer_json(4, [
        aw.Entry("e1", 2, "record_account", corrected["label"], corrected["text"].encode(), citations=citations),
        aw.Entry("e2", 1, "record_observation", "", observation),
        aw.Entry("e3", 1, "record_limit", "", limit)])
    selections, totals = {}, {}
    variants = ("spent",) if t.sabotage else ("spent", "unused", "diagnostic")
    for variant in variants:
        pre = "captured.reminder." + variant
        spent = variant != "unused"
        sub = run_submission(t, entries=[F("context/supplied-report.txt", material)],
                             body=b"What does the supplied report establish?\n", model="claude-haiku-5-5")
        observed = {}

        def body(p):
            p.usage = lambda: fp.Usage(1000, 50)
            turn = yield p.calls_step(("record_account", {"text": ACCOUNT.decode()}),
                                      ("record_observation", {"text": observation.decode()}),
                                      ("record_limit", {"text": limit.decode()}))
            p.eq("recorded", [r.outcome for r in turn.replies], ["completed"] * 3)
            handles = [r.data.get("entry") for r in turn.replies]
            turn = yield CapturedOrdinary(variant)
            if spent:
                p.eq("first-reminder", turn.texts, [REMINDER])
                # The original interruption was a signal before transmission.
                # Here an observed HTTP retry exhaustion makes transmission
                # and the continuation boundary deterministic.
                turn = yield fp.HttpError(529, retry_after="0")
            p.eq("fresh-conversation", turn.new_conversation, True)
            p.eq("continuation-input", turn.first_message.value() if turn.first_message else None,
                 {"role": "user", "content": [{"type": "text", "text": sub.body.decode()},
                                               {"type": "text", "text": CONTINUATION}]})
            state, entries, _ = yield from p.wwaw_all()
            p.eq("reentry.entries", [(e.get("id"), e.get("entry")) for e in entries],
                 list(zip(("e1", "e2", "e3"), handles)))
            p.eq("reentry.revision", (state or {}).get("revision"), 3)
            p.eq("reentry.reminder-spent", (state or {}).get("notices_used", {}).get("reminder"), spent)
            handle = entries[0].get("entry") if entries else handles[0]
            old, _ = yield from p.read_all(handle)
            p.eq("account-before-refusal", old, ACCOUNT)
            turn = yield p.calls_step(replacement_call(p, "m3-citation-invalid.json", handle))
            r = turn.reply()
            p.eq("citation-refusal", (r.outcome, r.reason), ("refused", "citation_invalid"))
            p.eq("citation-refusal-index", r.data.get("index"), 0)
            p.eq("citation-refusal-effects", r.effects, {"answer": "unchanged", "raw_capture": "recorded"})
            state, entries, _ = yield from p.wwaw_all()
            p.eq("refusal-preserves-revision", (state or {}).get("revision"), 3)
            p.eq("refusal-preserves-entries", [(e.get("id"), e.get("entry")) for e in entries],
                 list(zip(("e1", "e2", "e3"), handles)))
            old, _ = yield from p.read_all(handle)
            p.eq("account-after-refusal", old, ACCOUNT)
            turn = yield p.calls_step(replacement_call(p, "m3-citation-corrected.json", handle))
            r = turn.reply()
            p.eq("corrected-replacement", (r.outcome, r.data.get("id"), r.data.get("version"), r.data.get("revision")),
                 ("completed", "e1", 2, 4))
            p.eq("corrected-citations", r.data.get("citations"), citations)
            turn = yield p.calls_step(("prepare", {}))
            prepared = turn.reply().data.get("prepared")
            observed["selection"], _ = yield from p.read_all(prepared + "/selection")
            turn = yield p.end("Synthetic continuation ends without submitting.")
            if not spent:
                p.eq("continuation-reminder", turn.texts, [REMINDER])
                yield p.end("Synthetic ending after the reminder.")

        p = proc(sub, body)
        fx = rs.provider(t, p, label=variant, accepts=fp.MESSAGES_API)
        first_name, second_name = pre + ".first", pre + ".second"
        first = rs.run(t, sub, fx, name=first_name)
        cause = "provider_unavailable" if spent else "max_tokens"
        rs.check_run_reply(t, first, sub, first_name, ending="interrupted", cause=cause, run_number=1,
                           fx=fx, limits=rs.limits_of(sub))
        rs.check_run_ended(t, sub, 1, first_name, ending="interrupted", cause=cause,
                           requests=3 if spent else 2, attempts=6 if spent else 2)
        t.eq(pre + ".first-notice", first.data.get("notices"), [{"type": "reminder", "sent": "sent"}] if spent else [])
        second = rs.run(t, sub, fx, name=second_name)
        rs.check_run_reply(t, second, sub, second_name, ending="ended_unsubmitted", run_number=2,
                           fx=fx, limits=rs.limits_of(sub))
        rs.check_run_ended(t, sub, 2, second_name, ending="ended_unsubmitted", cause=None,
                           requests=9 if spent else 10, attempts=9 if spent else 10)
        rs.check_procedure(t, p, pre, fx)
        rs.check_requests(t, fx, sub, pre)
        rs.check_history(t, fx, pre)
        rs.check_run_records(t, sub, pre)
        for number, name in enumerate((first_name, second_name), 1):
            exs = fx.exchanges_of(name)
            rs.check_captures(t, sub, fx, name, run_number=number, exchanges=exs)
            t.eq(name + ".run-ended-usage", (rs.run_ended_of(t, sub, number) or {}).get("usage"), fx.totals(exs))
        t.eq(pre + ".reminder-once", p.texts, [REMINDER])
        notices = t.log_bodies(sub, "notice")
        t.eq(pre + ".notice-record", [(n.get("type"), n.get("run"), n.get("request"), n.get("text")) for n in notices],
             [("reminder", 1 if spent else 2, 3 if spent else 10, REMINDER)])
        t.eq(pre + ".second-notice", second.data.get("notices"), [] if spent else [{"type": "reminder", "sent": "sent"}])
        t.eq(pre + ".entry-actions", [b.get("action") for b in rs.entry_bodies(t, sub)], ["add"] * 3 + ["replace"])
        for version, expected in ((1, ACCOUNT), (2, corrected["text"].encode())):
            path = Path(sub.audit_dir) / "payload" / ("e1.v%d.bin" % version)
            t.eq(pre + ".retained-v%d" % version, path.read_bytes() if path.is_file() else None, expected)
        selections[variant] = observed.get("selection")
        t.eq(pre + ".prepared-selection", selections[variant], expected_selection)
        t.eq(pre + ".no-seal", t.log_bodies(sub, "seal"), [])
        refused = rs.run(t, sub, fx, name=pre + ".after-ending", expect="refused", reason="authoring_ended")
        t.eq(pre + ".ended-by", refused.data.get("ended_by"), "ordinary_ending")
        t.eq(pre + ".no-request-after-ending", fx.exchanges_of(pre + ".after-ending"), [])
        totals[variant] = fx.totals()
        t.eq(pre + ".literal-total", totals[variant], {
            "turns": {"reported": 11 if spent else 12, "estimated": 0},
            "input_tokens": {"reported": 16660 if spent else 17660, "estimated": 0},
            "output_tokens": {"reported": 748 if spent else 798, "estimated": 0}})
    if not t.sabotage:
        t.eq("captured.reminder.selection-invariance", list(selections.values()), [expected_selection] * 3)
        t.eq("captured.reminder.diagnostic-invariance", totals["diagnostic"], totals["spent"])


@selftest
def captured_reminder_selftests():
    import copy
    import json
    out = []
    for filename, size, digest in (
        ("m3-ordinary-ending.json", 1555, "ee1df6b283c322424e116e2e9a692a44ebd27e07546d5bd1928f27f407753728"),
        ("m3-citation-invalid.json", 1187, "bff4227f27d85e7991fa9e05d33dd35904c2d9b2a723eeeeb4fa842dc53291ff"),
        ("m3-citation-corrected.json", 1167, "1a6ea9ccc7d0936579e1734a30300f972e088e6e6f5fb6ad5fb816a8fd260b88"),
        ("m3-supplied-report.txt", 591, "86b5be5c14dad39f2facfb70607658bdc637f2df5a678e78e70972c459b9296d"),
    ):
        raw = (FIXTURES / filename).read_bytes()
        out.append(("m3.reminder." + filename + ".origin", len(raw) == size and sha256_hex(raw) == digest))
    original = CapturedOrdinary()
    for variant in ("unused", "diagnostic"):
        step = CapturedOrdinary(variant)
        expected = json.loads(original.captured)
        if variant == "unused":
            expected["stop_reason"] = "max_tokens"
            raw = original.captured.replace(b'"stop_reason":"end_turn"', b'"stop_reason":"max_tokens"', 1)
        else:
            expected["usage"]["output_tokens_details"]["thinking_tokens"] = 1
            raw = original.captured.replace(b'"thinking_tokens":0', b'"thinking_tokens":1', 1)
        out += [("m3.reminder." + variant + ".one-field", json.loads(step.captured) == expected),
                ("m3.reminder." + variant + ".one-span", step.captured == raw),
                ("m3.reminder." + variant + ".content", step.content_raw == original.content_raw),
                ("m3.reminder." + variant + ".charge", step.charge(None) ==
                 {"basis": "reported", "turns": 1, "input_tokens": 6660, "output_tokens": 248})]
    bad = json.loads((FIXTURES / "m3-citation-invalid.json").read_bytes())
    good = json.loads((FIXTURES / "m3-citation-corrected.json").read_bytes())
    expected = copy.deepcopy(bad)
    expected["id"] = good["id"]
    expected["input"]["citations"][0].pop("start")
    expected["input"]["citations"][0].pop("end")
    out.append(("m3.citation.range-correction", expected == good))
    sources = {"materials/context/supplied-report.txt": (FIXTURES / "m3-supplied-report.txt").read_bytes()}
    try:
        aw.record_citation(bad["input"]["citations"][0], sources)
        refused = False
    except aw.CitationDefect as exc:
        refused = exc.reason == "citation_invalid"
    out.append(("m3.citation.invalid-control", refused))
    out.append(("m3.citation.corrected-ranges", [aw.record_citation(c, sources)["stewart"]["range"]
                                               for c in good["input"]["citations"]] ==
                [[347, 428], [431, 507], [98, 125]]))
    for filename in ("m3-citation-invalid.json", "m3-citation-corrected.json"):
        raw = (FIXTURES / filename).read_bytes()
        expected = json.loads(raw)
        old = expected["input"]["entry"]
        expected["input"]["entry"] = "e1.v1.synthetic"
        projected = captured_replacement("e1.v1.synthetic", filename)
        out += [("m3.citation." + filename + ".handle-only", json.loads(projected) == expected),
                ("m3.citation." + filename + ".handle-span",
                 projected == raw.replace(old.encode(), b"e1.v1.synthetic", 1))]
    return out


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
