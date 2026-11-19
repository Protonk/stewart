"""Manager-declared material roles, from INTERFACE 3.2, 5.3–5.5 and QUESTION-FORMS."""
import json
import os
import shutil

from cases_foundation import check_arrangement, no_diag
from driver_core import D, F, case, check_advice, check_defects, question_md, read_bytes, strict_loads
from rawjson import compact


def roles_field(declarations):
    return (b"material-roles: " + compact(declarations),)


def prepare_selection(t, sub, name, declarations, advice):
    t.new_ref(sub, name=name + ".new")
    prepared = t.prepare(sub, name=name + ".prepare")
    t.check_prepare_witness(prepared, sub, name)
    t.check_prepared_settings(sub, name)
    handle = sub.handles[-1]
    got = check_arrangement(t, sub, handle, sub.family, name, sub.limits, declarations)
    check_advice(t, name, prepared.data, got["descriptor"], advice)
    return handle


@case("c21.role-capture", ["C21", "C7", "C11", "C15"],
      "many-to-many declarations preserve manager order, literal evidence and the accepted interpretation")
def c_role_capture(t):
    for label, subject, prose in (("original", "result.txt", b"Some measurements.\n"),
                                  ("renamed", "unrelated-name.txt", b"Some measurements.\n"),
                                  ("other-prose", "result.txt", b"Different observations.\n")):
        source = "materials/" + subject
        # Deliberately supply keys and roles out of presentation order.
        declarations = [
            {"source": "materials/reported.txt", "role": "report"},
            {"label": "South specimen", "source": source, "role": "alternative"},
            {"source": "materials/basis.txt", "role": "criterion"},
            {"source": source, "label": "North specimen", "role": "alternative"},
            {"role": "context", "source": source},
        ]
        sub = t.submission([F(subject, prose), F("reported.txt", b"A third-party report.\n"),
                            F("basis.txt", b"Compare the reported quantities.\n"), F("extra.txt", b"\n")],
                           family="comparison", q={"extra": roles_field(declarations)})
        name = "role-capture." + label
        handle = prepare_selection(t, sub, name, declarations, [])
        readable = sub.arrangement[handle]["readable"].decode("utf-8")
        t.check(name + ".readable-attribution",
                any("manager" in line and any(word in line for word in ("role", "mapping", "declar"))
                    for line in readable.lower().splitlines()), readable)
        position = 0
        for text in ("South specimen", "North specimen", "materials/basis.txt", source, "materials/reported.txt"):
            found = readable.find(text, position)
            if t.check(name + ".readable-order." + text, found >= 0, readable):
                position = found + len(text)
        t.commission(sub, handle, name=name + ".commission")
        t.driver_change("remove the accepted source folder", lambda: shutil.rmtree(sub.folder))
        for item, expected in sub.items().items():
            t.check_readback_ok(sub, item, expected, name)


@case("c21.role-advice", ["C21", "C7", "C11"],
      "missing mappings give family advice while empty, broad, undeveloped and one-sided inquiries commission")
def c_role_advice(t):
    subject = [("subject", "suggestion")]
    context = [("context", "suggestion")]
    comparison = [("alternative", "warning"), ("criterion", "suggestion")]
    one_side = [{"role": "alternative", "source": "materials/a.txt", "label": "One"},
                {"role": "alternative", "source": "materials/b.txt", "label": "One"},
                {"role": "criterion", "source": "materials/a.txt"}]
    for label, family, entries, declarations, advice, guidance in (
            ("open-omitted", "open-inquiry", [F("subject.txt", b"Subject.\n")], None, subject, b"Investigate.\n"),
            ("open-explicit-empty", "open-inquiry", [F("subject.txt", b"Subject.\n")], [], subject, b"Investigate.\n"),
            ("framing", "inquiry-framing", [], [], context, None),
            ("comparison-empty", "comparison", [], None, comparison, None),
            ("one-sided", "comparison", [F("a.txt", b"One observation."), F("b.txt", b"More on the same case.")],
             one_side, [("alternative", "warning")], None)):
        sub = t.submission(entries, family=family, body=b"What can we learn?\n", guidance=guidance,
                           q={"extra": () if declarations is None else roles_field(declarations)})
        name = "role-advice." + label
        handle = prepare_selection(t, sub, name, declarations or [], advice)
        t.commission(sub, handle, name=name + ".commission")
        status = t.status(sub, name=name + ".status")
        t.eq(name + ".accepted", status.data["headline"]["accepted"], "yes")
        t.eq(name + ".no-advice-diagnostic", status.data.get("diagnostics"), [])


@case("c21.role-refusals", ["C21", "C11", "C15", "C20"],
      "invalid declarations refuse, corrected files commission and changing a prepared proposal requires fresh preparation")
def c_role_refusals(t):
    source = "materials/a.txt"
    valid = {"role": "subject", "source": source}
    sub = t.submission([F("a.txt", b"The supplied text.\n"), D("empty-dir")],
                       q={"extra": roles_field([valid])})
    t.new_ref(sub)
    qpath = os.path.join(sub.folder, "question.md")
    original = sub.question
    line = next(i for i, text in enumerate(original.splitlines(), 1) if text.startswith(b"material-roles:"))
    handle = t.prepare(sub, name="refusals.initial").data["prepared"]
    history = []

    def remember_diagnostic(reply):
        paths = [p for p in reply.obj.get("retained", []) if os.path.dirname(p) == os.path.join(sub.audit_dir, "diag")]
        t.require(reply.name + ".one-retained-diagnostic", len(paths) == 1, paths)
        path = paths[0]
        date = strict_loads(read_bytes(path))["at"][:10]
        history.append((os.path.relpath(path, sub.audit_dir), date, reply.reason, reply.op))

    def refused(name, raw, errors):
        q = question_md(dest=sub.dest, extra=(b"material-roles: " + raw,))
        t.edit(qpath, q, name + " declaration")
        reply = t.prepare(sub, name=name, expect="refused", reason=errors[0]["reason"])
        check_defects(t, name, reply.data, [dict(error, line=line, key="material-roles", severity="error") for error in errors])
        t.eq(name + ".preparation", reply.effects.get("preparation"), "none")
        remember_diagnostic(reply)
        return reply

    for name, bad in (("case", "materials/A.txt"), ("path", "materials/./a.txt"),
                      ("directory", "materials/empty-dir"), ("question", "question"), ("root-guidance", "guidance.md")):
        refused("refusals." + name, compact([dict(valid, source=bad)]),
                [{"reason": "role_source_unknown", "pointer": "/0/source", "source": bad, "role": "subject"}])
    refused("refusals.unsupported", compact([dict(valid, role="criterion")]),
            [{"reason": "role_unsupported", "pointer": "/0/role", "role": "criterion"}])
    # Decoding JSON escapes precedes duplicate detection.
    duplicate = b'[{"role":"subject","source":"materials/a.txt"},{"source":"materials/\\u0061.txt","role":"subject"}]'
    rep = refused("refusals.duplicate", duplicate, [{"reason": "role_duplicate", "pointer": "/1", "source": source,
                                                      "role": "subject"}])
    detail = rep.data["defects"][0]
    t.check("refusals.duplicate.first-index", "0" in detail["message"] + detail["remedy"], detail)
    bad = "materials/absent"
    # The same error at indices 2 and 10 must follow numeric declaration order.
    mappings = [{"role": "report", "source": "materials/%d" % i} for i in range(11)]
    refused("refusals.ordered", compact(mappings),
            [{"reason": "role_source_unknown", "pointer": "/%d/source" % i, "source": row["source"], "role": "report"}
             for i, row in enumerate(mappings)])
    for name, raw in (("not-array", b"{}"), ("bad-json", b'[{"role":'),
                      ("duplicate-member", b'[{"role":"subject","role":"report","source":"materials/a.txt"}]'),
                      ("extra-label", compact([dict(valid, label="unused")]))):
        refused("refusals." + name, raw, [{"reason": "role_declaration_invalid"}])
    t.edit(qpath, question_md(dest=sub.dest, extra=roles_field([dict(valid, source=bad)])))
    changed = t.commission(sub, handle, name="refusals.changed", expect="refused", reason="selection_changed")
    remember_diagnostic(changed)
    t.eq("refusals.changed.effects", no_diag(changed.effects), {"acceptance": "absent", "attempt": "partial"})
    t.eq("refusals.no-extra-preparation", t.log_kinds(sub).count("prepared"), 1)
    t.edit(qpath, original)
    prepared = t.prepare(sub, name="refusals.corrected")
    check_defects(t, "refusals.corrected", prepared.data, [])
    t.commission(sub, sub.handles[-1], name="refusals.commission")
    status = t.status(sub, name="refusals.status")
    t.check_status(status, sub, "refusals.status", condition="not_started", accepted="yes", next_cmds=("run", "close"))
    diagnostics = [json.dumps(row, ensure_ascii=False) for row in status.data.get("diagnostics", [])]
    for path, date, reason, operation in history:
        t.check("refusals.status." + path, any(all(word in row for word in (path, date, reason, operation))
                                               for row in diagnostics), diagnostics)
    t.check_readback_ok(sub, "question-file", original, "refusals.corrected")


@case("c21.role-bounds", ["C21", "C19", "C20"], "alternative labels and declaration counts at and beyond their bounds")
def c_role_bounds(t):
    longest = "é" * 64
    source = "materials/a.txt"
    rows = [{"role": "criterion", "source": source}] + [
        {"role": "alternative", "source": source, "label": label}
        for label in [longest] + [str(i) for i in range(510)]]
    sub = t.submission([F("a.txt", b"One document discusses many alternatives.\n")],
                       family="comparison", q={"extra": roles_field(rows)})
    t.new_ref(sub)
    prepared = t.prepare(sub, name="bounds.exact")
    check_defects(t, "bounds.exact", prepared.data, [])
    machine = strict_loads(sub.arrangement[sub.handles[-1]]["machine"])
    t.eq("bounds.all-declarations", machine["body"]["commissioning"]["material_roles"], rows)
    for name, invalid in (("count-513", rows + [dict(rows[-1], label="more")]),
                          ("label-129-bytes", [dict(rows[1], label=longest + "a")]),
                          ("label-blank", [dict(rows[1], label="  ")]),
                          ("label-control", [dict(rows[1], label="x\u0081")]),
                          ("label-missing", [{"role": "alternative", "source": source}])):
        t.edit(os.path.join(sub.folder, "question.md"), question_md(dest=sub.dest, family=sub.family, extra=roles_field(invalid)))
        reply = t.prepare(sub, name="bounds." + name, expect="refused", reason="role_declaration_invalid")
        check_defects(t, "bounds." + name, reply.data, [{"reason": "role_declaration_invalid", "key": "material-roles",
                                                       "severity": "error"}])
    t.eq("bounds.only-one-preparation", t.log_kinds(sub).count("prepared"), 1)
