"""Build and test a wheel in a private environment using provisioned wheels only.

The selected suite runs outside the source tree and any parent pytest configuration.
No editable install, inherited plugin or project import path supplies Stewart.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import venv


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("budget must be finite and greater than zero")
    return seconds


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--wheelhouse", type=Path, default=os.environ.get("STEWART_WHEELHOUSE"))
    parser.add_argument("--parity-output", type=Path, help="write byte-contract vectors from the installed wheel")
    parser.add_argument("--result", type=Path, default=project / ".scratch/check-result.json")
    parser.add_argument("--fast", action="store_true", help="select smoke checks only; full coverage requires an unfiltered run")
    parser.add_argument("--test-budget-seconds", type=positive_seconds,
                        help="fail when any test's setup, call and teardown exceed this wall time")
    parser.add_argument("--total-budget-seconds", type=positive_seconds,
                        help="fail when provisioning, build and tests together exceed this wall time")
    args, tests = parser.parse_known_args()
    if args.fast:
        if any(arg.startswith("-m") for arg in tests):
            parser.error("--fast owns the marker selection; do not combine it with -m")
        tests = ["-m", "smoke and not heavy", *tests]
    result = args.result.resolve()
    wheels = (args.wheelhouse or project / ".scratch/wheelhouse").resolve()
    if not wheels.is_dir():
        parser.error("provision the hash-locked wheelhouse before running tests; no downloads are attempted")
    result.parent.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTEST_", "STEWART_TEST_", "PYTHON"))}
    environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                       PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INDEX="1", PIP_NO_CACHE_DIR="1",
                       STEWART_WHEELHOUSE=str(wheels))
    transcript = result.with_suffix(".log")
    with tempfile.TemporaryDirectory(prefix="stewart-wheel-check-") as temporary, transcript.open("w") as log:
        root = Path(temporary).resolve()
        prefix = root / "environment"
        venv.EnvBuilder(with_pip=True).create(prefix)
        python = prefix / "bin/python"
        def run(arguments, *, cwd=root):
            command = [str(python), "-I", "-B", *map(str, arguments)]
            log.write(json.dumps({"argv": command, "cwd": str(cwd)}) + "\n"); log.flush()
            completed = subprocess.run(command, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError(f"command failed ({completed.returncode}); see {transcript}")
        run(["-m", "pip", "install", "--no-index", "--no-compile", "--find-links", wheels,
             "--require-hashes", "-r", project / "requirements.lock"])
        run(["-m", "build", "--no-isolation", "--wheel", "--outdir", root / "dist", project])
        distributions = list((root / "dist").glob("*.whl"))
        if len(distributions) != 1:
            raise RuntimeError(f"expected one built wheel, found {len(distributions)}")
        wheel = distributions[0]
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        retained = result.parent / (result.stem + "-dist") / wheel.name
        retained.parent.mkdir(exist_ok=True)
        shutil.copyfile(wheel, retained)
        run(["-m", "pip", "install", "--no-index", "--no-deps", "--no-compile", wheel])
        runtime = subprocess.check_output([str(python), "-I", "-B", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                                          env=environment, text=True).strip()
        suite = root / "suite"
        shutil.copytree(project / "tests", suite / "tests", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        shutil.copyfile(project / "pyproject.toml", suite / "pyproject.toml")
        if args.parity_output:
            run([suite / "tests/parity_vectors.py", args.parity_output.resolve(), digest])
        environment.update(STEWART_TEST_RUNTIME=runtime, STEWART_TEST_PROJECT=str(project),
                           STEWART_TEST_SUITE=str(suite), STEWART_TEST_RESULT=str(result),
                           STEWART_TEST_WHEEL_SHA256=digest, STEWART_TEST_WHEEL=str(retained))
        if args.test_budget_seconds is not None:
            environment["STEWART_TEST_BUDGET_SECONDS"] = str(args.test_budget_seconds)
        artifacts = Path(tempfile.mkdtemp(prefix=result.stem + "-artifacts-", dir=result.parent))
        environment["STEWART_TEST_ARTIFACTS"] = str(artifacts)
        command = [str(python), "-I", "-B", "-m", "pytest", "-c", str(suite / "pyproject.toml"),
                   f"--confcutdir={suite}", f"--basetemp={artifacts}", str(suite / "tests"), *tests]
        print(f"[stewart] wheel {wheel.name} sha256={digest}; Python {sys.version.split()[0]}", flush=True)
        outcome = subprocess.run(command, cwd=suite, env=environment)
        elapsed = time.monotonic() - started
        over_budget = args.total_budget_seconds is not None and elapsed > args.total_budget_seconds
        # Only augment this invocation's receipt; a failed startup must not
        # relabel a result left by a previous invocation at the same path.
        if result.is_file():
            observed = json.loads(result.read_text())
            if observed.get("artifacts") == str(artifacts):
                observed.update(total_seconds=elapsed, total_budget_seconds=args.total_budget_seconds,
                                total_budget_exceeded=over_budget, fast=args.fast,
                                runner_exit_status=outcome.returncode or int(over_budget))
                result.write_text(json.dumps(observed, sort_keys=True, indent=2) + "\n")
        print(f"[stewart] total wall time {elapsed:.3f}s (including provisioning and build)", flush=True)
        if over_budget:
            print(f"[stewart] total budget exceeded: {elapsed:.3f}s > {args.total_budget_seconds}s", file=sys.stderr)
        return outcome.returncode or int(over_budget)


if __name__ == "__main__":
    raise SystemExit(main())
