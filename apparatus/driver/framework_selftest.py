"""Firing controls for selection, partial observations and runner accounting.

These cases exercise the real runner with synthetic checks, without launching a
Stewart binary. Expected failures stay inside this self-test's comparisons.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import driver_core as core


@core.selftest
def runner_selftest():
    results = []
    def check(name, actual, expected):
        results.append(("runner." + name, actual == expected,
                        {"actual": actual, "expected": expected}))

    def specimen(label, fn, mode="driver", controls=()):
        return core.CaseSpec(label, [], label, fn, mode, set(), list(controls), False, set(), None)

    def passed(t):
        t.check("measured", True)
    def failed(t):
        t.check("measured", False, "deliberate failure")
    def partial(t):
        passed(t)
        t.skip_part("not-observed", "deliberate partial observation")
    def failed_then_skip(t):
        failed(t)
        t.skip("deliberate skip after failure")
    def mixed(t):
        if t.variant == "release":
            failed(t)
        else:
            t.skip("deliberate skipped second variant")
    def controlled(t):
        t.check("measured", not t.sabotage, "deliberate control")
    def exception(t):
        raise RuntimeError("deliberate case exception")

    original = core.CASES[:]
    with tempfile.TemporaryDirectory(prefix="stewart-runner-selftest-") as root:
        fake = os.path.join(root, "unused-binary")
        with open(fake, "wb") as stream:
            stream.write(b"synthetic identity only; never executed\n")
        specs = [specimen("pass", passed), specimen("partial", partial),
                 specimen("failed-then-skip", failed_then_skip), specimen("mixed", mixed, mode="both"),
                 specimen("control", controlled, mode="release",
                          controls=[core.Control(core.SABOTAGES[0], [r"^measured$"])]),
                 specimen("exception", exception)]
        core.CASES[:] = specs
        try:
            def driver(label, patterns, exclude=(), timing="off", require=False):
                args = SimpleNamespace(evidence=os.path.join(root, label), work=root,
                                       binary=fake, test_binary=fake, timing_gate=timing,
                                       case=list(patterns), exclude=list(exclude), skip_heavy=False,
                                       network_isolated=True, require_all_controls=require, keep_work="all")
                return core.Driver(args)

            drv = driver("selection", ["p*", "mixed"], ["partial"])
            check("selection-includes-excludes", [s.id for s in drv.select()], ["pass", "mixed"])
            drv = driver("results", ["*"])
            with contextlib.redirect_stderr(io.StringIO()):
                code = drv.run()
            result = json.load(open(os.path.join(drv.evidence, "RESULT.json"), encoding="utf-8"))
            check("outcomes", [r["outcome"] for r in result["cases"]],
                  ["pass", "skipped", "fail", "fail", "pass", "fail"])
            check("case-counts", result["counts"]["cases"],
                  {"selected": 6, "ran": 5, "passed": 2, "failed": 3, "skipped": 1})
            check("exception-is-named", result["cases"][-1]["variants"][0]["failed_names"],
                  ["driver.exception"])
            check("control-fired", result["controls"][0]["status"], "fired")
            check("failure-exit", code, 1)
            for label, patterns, timing, expected in (
                    ("positive", ["pass", "control"], "off", 0),
                    ("empty", ["absent-case"], "off", 1),
                    ("empty-with-timing", ["absent-case"], "on", 1)):
                drv = driver(label, patterns, timing=timing)
                with contextlib.redirect_stderr(io.StringIO()):
                    check(label + ".exit", drv.run(), expected)
            drv = driver("unfired", ["pass"], require=True)
            with contextlib.redirect_stderr(io.StringIO()):
                check("unfired-required-controls.exit", drv.run(), 1)
            specs[0] = specimen("pass", lambda t: (_ for _ in ()).throw(KeyboardInterrupt()))
            core.CASES[:] = specs
            drv = driver("interrupted", ["pass", "partial"])
            with contextlib.redirect_stderr(io.StringIO()):
                check("interrupted.exit", drv.run(), 1)
            result = json.load(open(os.path.join(drv.evidence, "RESULT.json"), encoding="utf-8"))
            check("interrupted.selected", result["counts"]["cases"]["selected"], 2)
            check("interrupted.skipped", result["counts"]["cases"]["skipped"], 2)
        finally:
            core.CASES[:] = original
    # Run the real self-test command accounting in fresh interpreters. Importing
    # only core avoids recursively invoking this registered control. Missing
    # specification files must remain skipped, and a registered failure or
    # exception must reach the process exit status.
    bootstrap = """import os, sys
sys.path.insert(0, %r)
import driver_core as core
isfile = os.path.isfile
os.path.isfile = lambda path: False if str(path).endswith(('QUESTION-FORMS.md', 'INTERFACE.md')) else isfile(path)
def raised():
    raise RuntimeError('deliberate self-test exception')
core.SELF_TESTS[:] = [%s]
sys.exit(core.self_test())
"""
    for label, callback, expected_exit, expected_failures in (
            ("skip", "lambda: [('control.skipped', None, 'deliberately absent')]", 0, 0),
            ("false", "lambda: [('control.false', False)]", 1, 1),
            ("exception", "raised", 1, 1)):
        child = subprocess.run([sys.executable, "-I", "-B", "-c",
                                bootstrap % (os.path.dirname(core.__file__), callback)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = child.stdout.decode("utf-8", "replace")
        check("self-test." + label + ".exit", child.returncode, expected_exit)
        summary = re.search(r"self-test: (\d+) checks, (\d+) passed, (\d+) failed, (\d+) skipped", output)
        counts = tuple(map(int, summary.groups())) if summary else None
        check("self-test." + label + ".accounting",
              bool(counts and counts[0] == sum(counts[1:]) and counts[2] == expected_failures
                   and counts[3] == (3 if label == "skip" else 2)), True)
        check("self-test." + label + ".missing-specifications-skipped",
              "skip docs.available" in output and "skip docs.interface-available" in output, True)
    return results
