"""Captured citation operands exercised through the common Messages core.

INTERFACE 7.3 owns exact matching and refusal effects. MCP captures are projected
to Messages calls; this case makes no MCP transport or live-replay claim.
"""
from pathlib import Path

import answer_witness as aw
import rawjson
import run_support as rs
from cases_run import proc, run_submission
from driver_core import Control, F, case, selftest, sha256_hex


FIXTURES = Path(__file__).parent / "testdata/citations"
ACCOUNT = b"This synthetic comparison checks citation mechanics, not the captured prose's conclusions."


def source_for(origin):
    return (("materials/control.txt", (FIXTURES / "control.txt").read_bytes()) if origin == "c3"
            else ("materials/src/a.py", (FIXTURES / "a.py.txt").read_bytes()))


def citation_block(origin, which, variant="original"):
    raw = (FIXTURES / (origin + "-" + which + ".json")).read_bytes()
    node = rawjson.parse(raw)
    if origin != "m1":
        params = node.get("params")
        identity = params.value()["_meta"]["claudecode/toolUseId"]
        raw = (b'{"type":"tool_use","id":' + rawjson.compact(identity)
               + b',"name":' + params.get("name").raw + b',"input":' + params.get("arguments").raw + b'}')
    node = rawjson.parse(raw)
    arguments = node.get("input")
    if variant == "quote-fixed":
        citation = arguments.get("citations").items[0]
        source, material = source_for(origin)
        value = citation.value()
        assert value["source"] == source
        target = citation.get("quote")
        replacement = rawjson.compact(material[value["start"]:value["end"]].decode())
    elif variant == "reordered":
        target = arguments
        replacement = rawjson.compact(dict(reversed(list(arguments.value().items()))))
    elif variant == "original":
        return raw
    else:
        raise ValueError("unknown citation variant")
    return raw[:target.start] + replacement + raw[target.end:]


def send_captured(p, raw):
    node = rawjson.parse(raw)
    return p.call(node.get("name").value(), input=node.get("input").value(),
                  raw_input=node.get("input").raw, tid=node.get("id").value(), raw_block=raw)


@case("c14.captured-citations", ["C6", "C7", "C14", "C20"],
      "M1/C2/C3 citation refusals and corrections retain exact calls and independently derived selections",
      needs=("loopback",), controls=[
          Control("drop_refused_capture", [r"^captured\.citation\.m1\.original\.refused-capture$"]),
          Control("grade_support", [r"^captured\.citation\.m1\.original\.corrected-citations$"])])
def c_captured_citations(t):
    origins = ("m1",) if t.sabotage else ("m1", "c2", "c3")
    variants = ("original",) if t.sabotage else ("original", "quote-fixed", "reordered")
    for origin in origins:
        source, material = source_for(origin)
        answers = {}
        for variant in variants:
            pre = "captured.citation." + origin + "." + variant
            valid_probe = variant == "quote-fixed"
            probe = citation_block(origin, "invalid", variant)
            corrected = citation_block(origin, "corrected")
            probe_args = rawjson.parse(probe).get("input").value()
            good_args = rawjson.parse(corrected).get("input").value()
            sources = {source: material}
            good_citations = [aw.record_citation(c, sources) for c in good_args["citations"]]
            entries = [aw.Entry("e1", 1, "record_account", "", ACCOUNT)]
            if valid_probe:
                entries.append(aw.Entry("e2", 1, "record_observation", probe_args.get("label", ""),
                                        probe_args["text"].encode(),
                                        [aw.record_citation(c, sources) for c in probe_args["citations"]]))
            entries.append(aw.Entry("e3" if valid_probe else "e2", 1, "record_observation",
                                    good_args.get("label", ""), good_args["text"].encode(), good_citations))
            expected = aw.answer_json(len(entries), entries)
            sub = run_submission(t, entries=[F(source.removeprefix("materials/"), material)],
                                 body=b"Compare the supplied citation operands mechanically.\n", model="claude-haiku-5-5")
            observed = {}

            def body(p):
                turn = yield p.calls_step(("record_account", {"text": ACCOUNT.decode()}))
                handle = turn.reply().data.get("entry")
                turn = yield p.calls_step(send_captured(p, probe))
                r = turn.reply()
                observed["probe"] = r
                p.eq("probe-outcome", (r.outcome, r.reason),
                     ("completed", None) if valid_probe else ("refused", "citation_invalid"))
                p.eq("probe-effects", r.effects, {"answer": "changed" if valid_probe else "unchanged", "raw_capture": "recorded"})
                if valid_probe:
                    p.eq("probe-citations", r.data.get("citations"), entries[1].citations)
                else:
                    p.eq("probe-index", r.data.get("index"), 0)
                state, current, _ = yield from p.wwaw_all()
                p.eq("probe-revision", state.get("revision"), 2 if valid_probe else 1)
                p.eq("probe-membership", [e.get("id") for e in current], ["e1", "e2"] if valid_probe else ["e1"])
                before, _ = yield from p.read_all(handle)
                p.eq("prior-account-unchanged", before, ACCOUNT)
                turn = yield p.calls_step(send_captured(p, corrected))
                r = turn.reply()
                p.eq("corrected-outcome", (r.outcome, r.data.get("id"), r.data.get("version"), r.data.get("revision")),
                     ("completed", "e3" if valid_probe else "e2", 1, len(entries)))
                p.eq("corrected-citations", r.data.get("citations"), good_citations)
                turn = yield p.calls_step(("prepare", {}))
                prepared = turn.reply().data.get("prepared")
                observed["selection"], _ = yield from p.read_all(prepared + "/selection")
                yield p.calls_step(("submit", {"prepared": prepared, "confirm": True}))

            p = proc(sub, body)
            fx = rs.provider(t, p, label=origin + "-" + variant)
            rep = rs.run(t, sub, fx, name=pre + ".run")
            rs.check_run_reply(t, rep, sub, pre + ".run", ending="sealed", run_number=1, fx=fx,
                               limits=rs.limits_of(sub), seal_actor="auditor", delivery_outcome="verified")
            rs.check_run_ended(t, sub, 1, pre + ".run", ending="sealed", cause=None, requests=8, attempts=8)
            rs.check_procedure(t, p, pre, fx)
            rs.check_requests(t, fx, sub, pre)
            rs.check_history(t, fx, pre)
            rs.check_captures(t, sub, fx, pre + ".run", run_number=1)
            rs.check_run_records(t, sub, pre)
            r = observed.get("probe")
            if not valid_probe and r is not None:
                result = rs.result_for(sub, r.tid)
                t.check(pre + ".refused-capture", result is not None and result[2] == probe
                        and result[3] is not None and result[3].get("is_error") is True
                        and rs.result_envelope(result[3]).get("reason") == "citation_invalid", result)
            t.eq(pre + ".prepared-selection", observed.get("selection"), expected)
            package = rs.package_of(rep)
            answer = rs.read_package_member(package, "answer.json") if package else None
            answers[variant] = answer
            t.eq(pre + ".delivered-answer", answer, expected)
            for entry in entries:
                path = Path(sub.audit_dir) / "payload" / (entry.id + ".v1.bin")
                t.eq(pre + ".retained-" + entry.id, path.read_bytes() if path.is_file() else None, entry.data)
        if not t.sabotage:
            t.eq("captured.citation." + origin + ".order-invariance", answers["reordered"], answers["original"])


@selftest
def citation_capture_selftests():
    import copy
    out = []
    for name, size, digest in (
        ('m1-invalid.json', 553, '7921ec111192371e6b680bc8a455ae684c2bb47a94b519fb53d65e65b3ef237d'),
        ('m1-corrected.json', 407, 'a46aaa88d900600cd71c080ffbfb58b2f84954c74c47f4702ffb13d15c68e221'),
        ('c2-invalid.json', 801, '59c95bcf98e1cdb247e10d98267b9997cfbf19a8d024224eae809fd5dd99af68'),
        ('c2-corrected.json', 711, '7a9977e1c379e2071242d58d84f9c982ccf9f6013d0d9c60685709de6b2346ca'),
        ('c3-invalid.json', 607, '847bc04962038544049e39a208c48f348076af37ed067f4d984af53e499b282f'),
        ('c3-corrected.json', 587, '276dd05080de15a031453a0dd27370bf530302daccdba00359397ec647105d97'),
        ('a.py.txt', 175, '3fed093a5696428b7440ae3a0f93d2bd3bc93084b495fc3ec6297ab78c23afce'),
        ('control.txt', 49152, '947ae167c6e71f036d5c603c3f273706c2252b1b18d381bbf7da3045da49e0d2'),
    ):
        raw = (FIXTURES / name).read_bytes()
        out.append(("citation-capture." + name, len(raw) == size and sha256_hex(raw) == digest))
    for origin in ("m1", "c2", "c3"):
        name, data = source_for(origin)
        original_raw = citation_block(origin, "invalid")
        original = rawjson.parse(original_raw).value()
        fixed = rawjson.parse(citation_block(origin, "invalid", "quote-fixed")).value()
        expected = copy.deepcopy(original)
        citation = expected["input"]["citations"][0]
        citation["quote"] = data[citation["start"]:citation["end"]].decode()
        out.append((origin + ".quote-only-change", fixed == expected))
        out.append((origin + ".order-invariance", rawjson.parse(citation_block(origin, "invalid", "reordered")).value() == original))
        for which, arguments, refused in (("invalid", original["input"], True), ("fixed", fixed["input"], False),
                ("corrected", rawjson.parse(citation_block(origin, "corrected")).get("input").value(), False)):
            try:
                annotations = [aw.record_citation(c, {name: data}) for c in arguments["citations"]]
            except aw.CitationDefect as defect:
                out.append((origin + "." + which + ".citation", refused and defect.reason == "citation_invalid"))
            else:
                out.append((origin + "." + which + ".citation", not refused and len(annotations) == 1))
        for which in ("invalid", "corrected"):
            captured = (FIXTURES / (origin + "-" + which + ".json")).read_bytes()
            projected = citation_block(origin, which)
            if origin == "m1":
                out.append((origin + "." + which + ".unchanged-block", captured == projected))
            else:
                params = rawjson.parse(captured).get("params")
                out.append((origin + "." + which + ".unchanged-arguments", params.get("arguments").raw ==
                            rawjson.parse(projected).get("input").raw))
    return out
