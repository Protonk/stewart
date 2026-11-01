# -*- coding: utf-8 -*-
"""Independent credential checks from INTERFACE 4.5/5.7/6.1 and ACCEPTANCE.

Only synthetic, nonfunctional canaries are used. The fake provider retains the
exact request independently of Stewart, outside the archive. Check diagnostics
contain identities and booleans, never the canary value. Raw fake witnesses and
deliberately contaminated archive originals stay private through review.

The Linux case tests a same-user parent observer. Different-user observation and
withholding contaminated exports belong to the launch apparatus, which can run
credential_observer.py under a separately selected UID. No recursive file scan
is treated as proof of process memory erasure.
"""
from __future__ import annotations

import errno
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile

import credential_observer as observer
import fake_provider as fp
import run_support as rs
from driver_core import *  # noqa: F401,F403


REDACTED = "[REDACTED credential]"
REUSE_CONTROL = b"synthetic-archive-bytes-are-not-a-credential"


def descriptor_reuse_witness(path):
    done = subprocess.run([sys.executable, "-I", "-B", observer.__file__,
                           "--descriptor-reuse", path],
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                          env={"PATH": "/usr/bin:/bin"})
    if done.returncode != 0:
        raise RuntimeError("descriptor witness failed: %r" % done.stderr)
    return json.loads(done.stdout)


def descriptor_reuse_control(witness):
    return (witness.get("before_errno") == errno.EBADF
            and witness.get("opened_fd") == witness.get("selected_fd")
            and witness.get("read_bytes") == len(REUSE_CONTROL)
            and witness.get("read_sha256") == sha256_hex(REUSE_CONTROL))


def canary():
    return "sk-ant-NONFUNCTIONAL-CREDENTIAL-CANARY-" + os.urandom(16).hex()


def key_start(t, sub, fx, name, *, stdin=False, env=None):
    """A socket supplies EOF by shutdown while its other half observes closure."""
    writer, reader = socket.socketpair()
    fd = 0 if stdin else reader.fileno()
    environment = {"STEWART_PROVIDER_URL": fx.url, "ANTHROPIC_API_KEY": None}
    environment.update(env or {})
    fx.mark(name)
    try:
        h = t.start(["run", sub.ref, "--key-fd", str(fd)], name=name, env=environment,
                    stdin=reader if stdin else None,
                    pass_fds=() if stdin else (fd,), timeout=15)
    except BaseException:
        writer.close()
        raise
    finally:
        reader.close()
    return h, writer


def key_run(t, sub, fx, name, payload, *, stdin=False, env=None,
            expect="completed", reason=None):
    h, stream = key_start(t, sub, fx, name, stdin=stdin, env=env)
    try:
        try:
            stream.sendall(payload)
            stream.shutdown(socket.SHUT_WR)
        except BrokenPipeError:
            pass  # A source-conflict refusal need not read anything.
        rep = t.finish(h, expect=expect, reason=reason)
    finally:
        stream.close()
    return rep


def receipt_clean(t, sub, secret, name):
    rep = t.cmd(["receipt", sub.ref], name=name, expect="completed")
    needs = rep.data.get("run_needs", [])
    t.check(name + ".credential-routes", any("--key-fd" in s and "ANTHROPIC_API_KEY" in s
                                             for s in needs if isinstance(s, str)), "receipt omitted a credential route")
    t.check(name + ".no-canary", secret.encode() not in rep.stdout + rep.stderr,
            "credential appeared in receipt output")


def check_receipt_of_key(t, fx, secret, name):
    exs = fx.exchanges_of(name)
    t.eq(name + ".provider-requests", len(exs), 1)
    for ex in exs:
        t.check(name + ".exact-authentication", authentication_matches(ex, secret),
                "independent provider did not receive exactly the selected canary")
        t.check(name + ".not-model-visible", secret.encode() not in ex.body,
                "credential appeared in the model-visible body")


def authentication_matches(exchange, secret):
    return exchange.header("x-api-key") == [secret]


@case("credentials.input", ["C1", "C12", "C14", "C20"],
      "descriptor input has strict bounds, EOF deadline and one selected source; environment input still works",
      needs=("loopback",))
def c_input(t):
    sub = t.submission([F("note.txt", b"A credential is not commission material.\n")])
    t.accept(sub, prefix="credential.")
    fx = rs.provider(t, lambda ex: fp.Message(stop_reason="max_tokens"), label="input")

    # Each refusal differs only in credential input; nothing starts or reaches
    # the independent provider. The same commission subsequently runs.
    invalid = [("empty", b"", "provider_key_missing"),
               ("only-lf", b"\n", "provider_key_missing"),
               ("space", b"canary key", "provider_key_invalid"),
               ("tab", b"canary\tkey", "provider_key_invalid"),
               ("crlf", b"canary\r\n", "provider_key_invalid"),
               ("two-lfs", b"canary\n\n", "provider_key_invalid"),
               ("nul", b"canary\x00key", "provider_key_invalid"),
               ("del", b"canary\x7f", "provider_key_invalid"),
               ("non-ascii", b"canary\x80", "provider_key_invalid"),
               ("oversized", b"a" * 4097, "provider_key_invalid")]
    for label, payload, reason in invalid:
        name = "credential.input." + label
        rep = key_run(t, sub, fx, name, payload, expect="refused", reason=reason)
        rs.check_refused_before_request(t, rep, sub, fx, name)
    for label, payload in (("oversized", "K" * 4097), ("lf", canary() + "\n")):
        name = "credential.environment-invalid." + label
        rep = rs.run(t, sub, fx, name=name, env={"ANTHROPIC_API_KEY": payload},
                     expect="refused", reason="provider_key_invalid")
        rs.check_refused_before_request(t, rep, sub, fx, name)
    for label, present in (("present", canary()), ("empty", "")):
        t.protect_check_value(present)
        name = "credential.conflict." + label
        rep = key_run(t, sub, fx, name, b"selected-canary", env={"ANTHROPIC_API_KEY": present},
                      expect="refused", reason="provider_key_source_conflict")
        rs.check_refused_before_request(t, rep, sub, fx, name)
        t.check(name + ".no-value", not present or present.encode() not in rep.stdout + rep.stderr,
                "source conflict disclosed the supplied value")
    # Exercise the lowest closed descriptor, where a delayed credential check
    # could otherwise read an archive file opened at the same number. Rosetta
    # occupies 3 and 4 before guest entry; an independent fresh process witnesses
    # that interpreter and proves both EBADF and subsequent low-number reuse.
    fixture = os.path.join(t.root, "descriptor-reuse-control")
    with open(fixture, "wb") as f:
        f.write(REUSE_CONTROL)
    witness = descriptor_reuse_witness(fixture)
    with open(os.path.join(t.evid, "descriptor-reuse-observer.json"), "w", encoding="utf-8") as f:
        json.dump(witness, f, indent=2)
    t.driver_control("closed-descriptor-reuse", descriptor_reuse_control(witness),
                     "the selected low descriptor is EBADF before a file open, then reads that file after reuse")
    for fd in (witness["selected_fd"], 2147483647):
        name = "credential.closed-fd.%d" % fd
        fx.mark(name)
        rep = t.cmd(["run", sub.ref, "--key-fd", str(fd)], name=name,
                    env={"STEWART_PROVIDER_URL": fx.url}, expect="refused", reason="provider_key_unreadable")
        rs.check_refused_before_request(t, rep, sub, fx, name)
    directory = os.open(t.root, os.O_RDONLY)
    try:
        name = "credential.read-failure"
        fx.mark(name)
        rep = t.cmd(["run", sub.ref, "--key-fd", str(directory)], pass_fds=(directory,),
                    name=name, env={"STEWART_PROVIDER_URL": fx.url},
                    expect="refused", reason="provider_key_unreadable")
        rs.check_refused_before_request(t, rep, sub, fx, name)
    finally:
        os.close(directory)
    name = "credential.deadline"
    h, stream = key_start(t, sub, fx, name)
    try:
        stream.sendall(b"valid-but-without-eof")
        rep = t.finish(h, expect="refused", reason="provider_key_unreadable", timeout=10)
    finally:
        stream.close()
    t.check(name + ".bounded", 4500 <= rep.wall_ms < 10000, {"wall_ms": rep.wall_ms})
    rs.check_refused_before_request(t, rep, sub, fx, name)

    # EOF and one optional LF, descriptor zero, the maximum accepted value,
    # and the existing environment route all deliver the exact selected bytes.
    routes = [("fd", canary(), False, b""), ("lf", canary(), False, b"\n"),
              ("stdin", canary(), True, b""), ("maximum", "K" * 4096, False, b"\n"),
              ("minimum", "!", False, b"")]
    for n, (label, secret, stdin, suffix) in enumerate(routes, 1):
        t.protect_check_value(secret)
        name = "credential.valid." + label
        rep = key_run(t, sub, fx, name, secret.encode() + suffix, stdin=stdin)
        rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="max_tokens", run_number=n,
                           fx=fx, limits=rs.limits_of(sub))
        check_receipt_of_key(t, fx, secret, name)
        t.check(name + ".no-value", secret.encode() not in rep.stdout + rep.stderr, "run output disclosed the canary")
        receipt_clean(t, sub, secret, name + ".receipt")
    fx.key = canary()
    t.protect_check_value(fx.key)
    name = "credential.valid.environment"
    rep = rs.run(t, sub, fx, name=name)
    rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="max_tokens", run_number=6,
                       fx=fx, limits=rs.limits_of(sub))
    check_receipt_of_key(t, fx, fx.key, name)
    rs.check_run_records(t, sub, "credential.input")
    t.driver_control("authentication-mismatch", bool(fx.exchanges) and
                     not authentication_matches(fx.exchanges[-1], "different-nonfunctional-key"),
                     "the exact-authentication witness rejects a different selected key")


@case("credentials.arguments", ["C12", "C20"],
      "key-fd is a run-only canonical descriptor option and input failures preserve refusal order")
def c_arguments(t):
    sub = t.submission([])
    t.new_ref(sub)
    before = t.log_kinds(sub)
    invalid_results = []
    for value in ("1", "2", "00", "03", "+3", "-3", "2147483648", "x", ""):
        rep = t.cmd(["run", sub.ref, "--key-fd", value], name="credential.usage.%r" % value,
                    envelope=False)
        t.eq("credential.usage.exit", rep.rc, 2)
        invalid_results.append(rep.rc)
    for args in (["run", sub.ref, "--key-fd"], ["status", sub.ref, "--key-fd", "0"]):
        rep = t.cmd(args, name="credential.usage.shape", envelope=False)
        t.eq("credential.usage.shape.exit", rep.rc, 2)
    t.eq("credential.usage.no-effects", t.log_kinds(sub), before)
    t.cmd(["run", "bad-reference", "--key-fd", "2147483647"],
          name="credential.order.reference", expect="refused", reason="reference_invalid")
    t.cmd(["run", sub.ref, "--key-fd", "2147483647"], name="credential.order.not-accepted",
          expect="refused", reason="not_accepted")
    t.driver_control("invalid-descriptor-input", len(invalid_results) == 9 and all(rc == 2 for rc in invalid_results),
                     "nine deliberately malformed or reserved descriptors produced usage refusals")


def escape_canary(secret):
    """A fully escaped ASCII canary; no literal key exists in these response bytes."""
    return b"".join(("\\u%04x" % ord(c)).encode() for c in secret)


def reflected_steps(secret):
    mutation = fp.tool_use("credential-tool", "record_account", {"text": "This tool must not execute on reflection."})
    usage = fp.Usage(123, 17, cache_creation=3, cache_read=5)
    literal = fp.Message([fp.text(secret), mutation], stop_reason="refusal", usage=usage)
    escaped = fp.Message([fp.text("placeholder"), mutation], stop_reason="refusal", usage=usage,
                         body=literal.body(type("Ex", (), {"n": 1})()).replace(secret.encode(), escape_canary(secret)),
                         charge={"basis": "reported", "turns": 1, "input_tokens": 131, "output_tokens": 17})
    out = [("success-literal", literal, True, [], "response", True),
           ("success-escaped", escaped, True, [], "response", True)]
    for header in ("content-type", "request-id", "retry-after"):
        out.append(("header-" + header, fp.Message([mutation], stop_reason="tool_use", usage=usage,
                                                  headers=[(header, "prefix-" + secret + "-suffix")]),
                    False, [header], "response", True))
    out.append(("headers-escaped", fp.Message([mutation], stop_reason="tool_use", usage=usage,
                  headers=[(h, escape_canary(secret).decode()) for h in ("retry-after", "request-id", "content-type")]),
                False, ["content-type", "request-id", "retry-after"], "response", True))
    out.append(("rejection", fp.HttpError(401, error_type="echo-" + secret, message="Rejected " + secret),
                True, [], "http_error", True))
    out.append(("retryable-error", fp.HttpError(529, message="Overloaded " + secret, retry_after="0"),
                True, [], "http_error", True))
    out.append(("malformed", fp.Message(body=b'{broken "' + escape_canary(secret) + b'"'),
                True, [], "response_undecodable", True))
    partial = b'{"partial":"' + escape_canary(secret) + b'"'
    raw = (b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\ncontent-length: "
           + str(len(partial) + 100).encode() + b"\r\nconnection: close\r\n\r\n" + partial)
    out.append(("truncated", fp.Raw(raw, charge="estimated"), True, [], "connection_lost", False))
    return out


def response_headers(ex):
    head = ex.response_raw.split(b"\r\n\r\n", 1)[0]
    result = {h: [] for h in ("content-type", "request-id", "retry-after")}
    for line in head.split(b"\r\n")[1:]:
        name, sep, value = line.partition(b":")
        name = name.decode("ascii").lower()
        if sep and name in result:
            result[name].append(value.strip(b" \t").decode("ascii"))
    return result


def safe_diagnostics(record, secret):
    selected = {k: record.get(k) for k in ("error", "model", "stop_reason", "problem")}
    return secret not in json.dumps(selected, ensure_ascii=False)


@case("credentials.reflection", ["C1", "C6", "C9", "C12", "C14"],
      "reflected keys stay exact in marked private evidence; derived output is safe and tools/retries stop",
      needs=("loopback",))
def c_reflection(t):
    secret = canary()
    t.protect_check_value(secret)
    for label, step, body_match, header_matches, outcome, complete in reflected_steps(secret):
        name = "credential.reflect." + label
        sub = t.submission([])
        t.accept(sub, prefix=name + ".")
        # Unexpected retries receive a harmless hard rejection quickly. The
        # attempt count, not fake script exhaustion, detects a retry defect.
        fx = rs.provider(t, fp.Script([step], then=lambda ex: fp.HttpError(400)), label=label, key=secret)
        rep = key_run(t, sub, fx, name, secret.encode())
        rs.check_run_reply(t, rep, sub, name, ending="interrupted", cause="credential_reflected",
                           run_number=1, fx=fx, limits=rs.limits_of(sub), provider=None)
        check_receipt_of_key(t, fx, secret, name)
        rd = rs.run_dirs(sub).get(1)
        t.require(name + ".captures", rd is not None, "missing run directory")
        t.eq(name + ".one-attempt", sorted(rd.attempts), [(1, 1)])
        record = (rd.attempts.get((1, 1)) or {}).get("body") or {}
        t.eq(name + ".marker", record.get("credential_reflection"), {"body": body_match, "headers": header_matches})
        t.eq(name + ".outcome", record.get("outcome"), outcome)
        t.eq(name + ".decision", [record.get("then"), record.get("delay_ms")], ["end", None])
        t.eq(name + ".complete", (record.get("response") or {}).get("complete"), complete)
        if fx.exchanges:
            ex = fx.exchanges[0]
            raw = ex.response_raw.split(b"\r\n\r\n", 1)[1]
            t.check(name + ".exact-private-body", rd.responses.get((1, 1)) == raw,
                    "response capture differs from independent provider bytes")
            t.check(name + ".exact-private-headers", record.get("headers") == response_headers(ex),
                    "retained headers differ from independent provider values")
            t.eq(name + ".charge", record.get("charged"), ex.charge)
        t.check(name + ".safe-derived", safe_diagnostics(record, secret), "derived record disclosed a credential")
        for field in ("model", "stop_reason"):
            if outcome == "response":
                t.eq(name + ".redacted." + field, record.get(field), REDACTED)
        if outcome == "http_error":
            t.eq(name + ".redacted.error", record.get("error"),
                 {"type": REDACTED, "message": REDACTED, "request_id": REDACTED})
        problem = record.get("problem")
        t.check(name + ".explicit-redaction", isinstance(problem, str) and
                "redact" in problem.lower() and "credential" in problem.lower(), "problem omitted reflection/redaction explanation")
        t.eq(name + ".no-calls", list(rd.calls), [])
        t.eq(name + ".no-results", list(rd.results), [])
        t.eq(name + ".no-entries", rs.entry_bodies(t, sub), [])
        t.check(name + ".safe-manager", secret.encode() not in rep.stdout + rep.stderr,
                "run output disclosed credential")
        ended = rs.run_ended_of(t, sub, 1) or {}
        t.eq(name + ".run-ended-cause", ended.get("cause"), "credential_reflected")
        t.eq(name + ".run-ended-provider", ended.get("provider"), None)
        t.check(name + ".safe-ending", secret not in json.dumps(ended), "run ending disclosed credential")
        status = t.status(sub, name=name + ".status")
        t.check(name + ".safe-status", secret.encode() not in status.stdout + status.stderr,
                "status without a key disclosed credential")
        t.eq(name + ".status-condition", status.data.get("condition"), "interrupted")
        rs.check_run_records(t, sub, name)
    # A clean differing response executes the same tool; a non-secret provider
    # diagnostic is preserved exactly. These are actual binary comparisons.
    for label, step in (("clean-tool", fp.Message([fp.text("unrelated-text"), fp.tool_use("credential-tool", "record_account",
                           {"text": "This tool must not execute on reflection."})], stop_reason="refusal",
                           usage=fp.Usage(123, 17, cache_creation=3, cache_read=5))),
                        ("unrelated-diagnostic", fp.HttpError(401, message="An unrelated diagnosis stays intact."))):
        name = "credential.invariance." + label
        sub = t.submission([])
        t.accept(sub, prefix=name + ".")
        fx = rs.provider(t, fp.Script([step]), label=label, key=secret)
        rep = key_run(t, sub, fx, name, secret.encode())
        record = (rs.run_dirs(sub)[1].attempts[(1, 1)] or {}).get("body", {})
        t.eq(name + ".clean-marker", record.get("credential_reflection"), {"body": False, "headers": []})
        t.eq(name + ".problem", record.get("problem"), None)
        if label == "clean-tool":
            t.eq(name + ".tool-executed", len(rs.entry_bodies(t, sub)), 1)
            t.eq(name + ".stop-reason", record.get("stop_reason"), "refusal")
        else:
            t.eq(name + ".unchanged-diagnostic", (record.get("error") or {}).get("message"), step.message)
            t.eq(name + ".manager-diagnostic", (rep.data.get("provider") or {}).get("error_message"), step.message)
    t.driver_control("credential-display-leak", not safe_diagnostics({"problem": secret}, secret),
                     "the derived-diagnostic detector catches a deliberate leak")


@case("credentials.process", ["C1", "C12"],
      "Linux blocks actual same-user process inspection before credential read and closes its input",
      needs=("linux", "loopback", "nonroot"),
      linux_reason="Linux procfs permissions and core-dump wait status")
def c_process(t):
    secret = canary()
    t.protect_check_value(secret)
    control = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import time; time.sleep(30)"],
                               env={"PATH": "/usr/bin:/bin", "CREDENTIAL_CONTROL": secret},
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        observed_control = observer.observe(control.pid)
        readable = (all(observed_control["access"][n]["allowed"] for n in ("environ", "maps", "mem", "fd"))
                    and observed_control["access"]["mem"].get("read_bytes") == 1)
        t.driver_control("readable-process", readable and not observer.inspection_denied(observed_control),
                         "same-user control permits actual environment/maps/fd and one-byte memory reads")
    finally:
        control.kill()
        control.wait()
    sub = t.submission([])
    t.accept(sub, prefix="credential.process.")
    fx = rs.provider(t, fp.Script([fp.Stall(seconds=30)]), label="process", key=secret)
    name = "credential.process.run"
    h, stream = key_start(t, sub, fx, name)
    observations, during = [], None
    try:
        # The child cannot receive any key byte until the observer has tested
        # its actual access, so timing cannot hide an early-read exposure.
        def protected():
            observation = observer.observe(h["proc"].p.pid)
            observations.append(observation)
            return observer.inspection_denied(observation)
        t.check("credential.process.before-input", rs.wait_for(protected, timeout=3),
                "same-user process inspection was not denied before key delivery")
        stream.sendall(secret.encode())
        stream.shutdown(socket.SHUT_WR)
        t.check("credential.process.provider-received", rs.wait_for(lambda: bool(fx.exchanges), timeout=5),
                "independent fake did not receive a request")
        during = observer.observe(h["proc"].p.pid)
        t.check("credential.process.during-request", observer.inspection_denied(during), during)
        t.eq("credential.process.core-limits", during.get("core_limits"), ["0", "0"])
        stream.settimeout(2)
        try:
            closed = stream.recv(1) == b""
        except socket.timeout:
            closed = False
        t.check("credential.process.descriptor-closed", closed, "credential descriptor remains open while request waits")
        t.check("credential.process.argv-clean", secret not in json.dumps(h["argv"]), "canary appeared in process argv")
        during["cmdline_form"] = observer.match_cmdline(during, h["argv"])
        t.check("credential.process.actual-argv", during["cmdline_form"] is not None,
                {"actual_sha256": during.get("cmdline_sha256"),
                 "actual_bytes": during.get("cmdline_bytes"),
                 "expected_forms": observer.cmdline_forms(h["argv"])})
        t.check("credential.process.environment-clean", secret not in json.dumps(h["env"]), "canary appeared in process environment")
        check_receipt_of_key(t, fx, secret, name)
        # An actual abort must not produce a core, not merely request that it
        # should not. The frozen cwd/home watches also detect surviving files.
        t.signal(h, signal.SIGABRT)
        rep = t.finish(h, envelope=False)
        t.eq("credential.process.aborted", rep.rc, -signal.SIGABRT)
        status = h["proc"].status
        t.check("credential.process.no-core", status is not None and not os.WCOREDUMP(status),
                "kernel reported a core dump after the deliberate abort")
    finally:
        stream.close()
        if h["proc"].running():
            h["proc"].kill()
            t.finish(h, envelope=False)
    with open(os.path.join(t.evid, "process-observers.json"), "w", encoding="utf-8") as f:
        json.dump({"control": observed_control, "before_input": observations, "during_request": during,
                   "boundary": "same-user parent procfs observer; different-user and export checks are launch-apparatus work"}, f, indent=2)


@selftest
def credential_selftests():
    secret = "synthetic-A/z+9"
    out = [("credentials.escape-equivalence", json.loads(b'"' + escape_canary(secret) + b'"') == secret),
           ("credentials.escape-no-literal", secret.encode() not in escape_canary(secret)),
           ("credentials.display-clean", safe_diagnostics({"problem": "unrelated"}, secret)),
           ("credentials.display-control", not safe_diagnostics({"error": {"message": secret}}, secret))]
    denied = {"access": {n: {"allowed": False, "errno": 13} for n in ("environ", "maps", "mem", "fd")}}
    missing = {"access": {n: {"allowed": False, "errno": 2} for n in ("environ", "maps", "mem", "fd")}}
    out += [("credentials.observer-denial", observer.inspection_denied(denied)),
            ("credentials.observer-disappearance-control", not observer.inspection_denied(missing))]
    argv = ["/synthetic/stewart", "run", "synthetic-reference", "--key-fd", "7", "--json"]
    def observed_argv(args):
        data = b"\0".join(os.fsencode(arg) for arg in args) + b"\0"
        return {"access": {"cmdline": {"allowed": True}},
                "cmdline_sha256": sha256_hex(data), "cmdline_bytes": len(data)}
    out += [("credentials.argv-direct", observer.match_cmdline(observed_argv(argv), argv) == "direct"),
            ("credentials.argv-rosetta", observer.match_cmdline(
                observed_argv(["/run/rosetta/rosetta"] + argv), argv) == "rosetta")]
    for label, actual in (("changed-argument", argv[:-1] + ["--other"]),
                          ("arbitrary-prefix", ["/arbitrary/interpreter"] + argv),
                          ("repeated-prefix", ["/run/rosetta/rosetta"] * 2 + argv),
                          ("extra-value", ["/run/rosetta/rosetta"] + argv + [secret])):
        out.append(("credentials.argv-" + label + "-control",
                    observer.match_cmdline(observed_argv(actual), argv) is None))
    unreadable_argv = observed_argv(argv)
    unreadable_argv["access"]["cmdline"] = {"allowed": False, "errno": 13}
    out.append(("credentials.argv-unreadable-control", observer.match_cmdline(unreadable_argv, argv) is None))
    with tempfile.TemporaryDirectory(prefix="stewart-credential-selftest-") as temp:
        fixture = os.path.join(temp, "descriptor-reuse-control")
        with open(fixture, "wb") as f:
            f.write(REUSE_CONTROL)
        witness = descriptor_reuse_witness(fixture)
        out.append(("credentials.closed-descriptor-reuse", descriptor_reuse_control(witness)))
        out.append(("credentials.open-descriptor-control",
                    not descriptor_reuse_control(dict(witness, before_errno=None))))
        out.append(("credentials.unrelated-descriptor-control",
                    not descriptor_reuse_control(dict(witness, opened_fd=witness["selected_fd"] + 1))))
    summaries = T.__new__(T)
    summaries.checks, summaries.private_check_values = [], []
    summaries.protect_check_value("Q" * 4096)
    summaries.check("synthetic-leak-control", False, {"actual": "Q" * 4096})
    out.append(("credentials.private-summary-before-truncation",
                "Q" not in summaries.checks[0]["detail"] and "PRIVATE" in summaries.checks[0]["detail"]))
    specimens = reflected_steps(secret)
    out.append(("credentials.reflection-fixtures", len(specimens) == 10))
    ex = fp.Exchange(1, "http", None, None, fp.now())
    ex.n, ex.body = 1, b'{"max_tokens":4096}'
    escaped = next(step for label, step, *_ in specimens if label == "success-escaped")
    parsed = json.loads(escaped.body(ex))
    out.append(("credentials.escaped-fixture-usage",
                parsed["content"][0]["text"] == secret and escaped.charge(ex)["input_tokens"] == 131))
    for use_stdin in (False, True):
        r, w = os.pipe()
        os.write(w, secret.encode())
        os.close(w)
        fd = 0 if use_stdin else r
        try:
            proc = Proc([sys.executable, "-I", "-B", "-c",
                         "import os; os.write(1, os.read(%d, 4096))" % fd],
                        {"PATH": "/usr/bin:/bin"}, os.getcwd(), 5,
                        stdin=r if use_stdin else None, pass_fds=() if use_stdin else (r,))
            result = proc.wait()
            out.append(("credentials.harness-" + ("stdin" if use_stdin else "descriptor"),
                        result["rc"] == 0 and result["stdout"] == secret.encode()))
        finally:
            os.close(r)
    return out
