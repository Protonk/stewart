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
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import venv

PHASES = ("setup", "call", "teardown")


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("budget must be finite and greater than zero")
    return seconds


GIT_SHIM = Path("/usr/bin/git")


def git_executable(value):
    """Validate --git-executable: auto, path, or the absolute path of an executable file named git."""
    if value in ("auto", "path"):
        return value
    candidate = Path(value)
    if not (candidate.is_absolute() and candidate.name == "git" and candidate.is_file() and os.access(candidate, os.X_OK)):
        raise argparse.ArgumentTypeError(
            f"expected auto, path or the absolute path of an executable file named git, not {value!r}")
    if os.pathsep in str(candidate.parent):
        raise argparse.ArgumentTypeError(
            f"{candidate.parent} contains {os.pathsep!r}, so PATH would split it; use a git in another directory")
    return value


def run_probe(argv, environment):
    """Return a command's exit status and stripped output, or None and the error if it cannot start.

    The output is stdout, or stderr when a failing command printed nothing else, so a
    fallback reason carries the tool's own message (an unaccepted Xcode licence, missing
    command line tools). Undecodable bytes are replaced rather than aborting the check.
    """
    try:
        completed = subprocess.run(list(map(str, argv)), env=environment, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)
    output = completed.stdout.strip()
    if completed.returncode and not output:
        output = completed.stderr.strip()
    return completed.returncode, output


def direct_git(current, platform, ask, shim):
    """Return the verified binary behind Apple's git shim, or None and why it is not used.

    The developer directory comes from xcode-select -p, which honours DEVELOPER_DIR
    and the system selection as the shim does, so it is evidence independent of the
    candidate's own location. Apple's Git derives its exec path and templates from
    the path it was invoked by, so an existing exec path inside that directory shows
    the candidate runs from its installed place; a link or copy names a missing one.
    """
    if platform != "darwin":
        return None, f"auto selection applies only on darwin, not {platform}"
    if current is None:
        return None, "git does not resolve on PATH"
    try:
        shimmed = os.path.samefile(current, shim)
    except OSError:
        shimmed = False
    if not shimmed:
        return None, f"git resolves to {current}, not the xcrun shim {shim}"
    status, found = ask(shim.parent / "xcrun", "--find", "git")
    if status != 0 or not found:
        return None, f"xcrun --find git failed ({status}): {found}"
    candidate = Path(found)
    try:
        regular = stat.S_ISREG(os.lstat(candidate).st_mode) and os.access(candidate, os.X_OK)
    except OSError:
        regular = False
    if not (candidate.is_absolute() and candidate.name == "git" and regular):
        return None, f"xcrun names {found}, not an absolute executable regular file named git"
    expected, observed = ask(current, "--version"), ask(candidate, "--version")
    if expected[0] != 0 or observed != expected:
        return None, f"{candidate} --version reports {observed[1]!r}, but the shim reports {expected[1]!r}"
    status, developer = ask(shim.parent / "xcode-select", "-p")
    if status != 0 or not Path(developer).is_absolute():
        return None, f"xcode-select -p failed ({status}): {developer}"
    def inside(value):
        return Path(value).is_absolute() and Path(value).resolve().is_relative_to(Path(developer).resolve())
    if not inside(candidate):
        return None, f"{candidate} is outside the developer directory {developer}"
    status, exec_path = ask(candidate, "--exec-path")
    if status != 0 or not inside(exec_path) or not Path(exec_path).is_dir():
        return None, f"{candidate} --exec-path reports {exec_path!r}, not an existing directory under {developer}"
    return candidate, None


def select_git(requested, path_value, platform, probe, wrapper_dir, shell, shim=GIT_SHIM):
    """Choose the tests' PATH for a validated --git-executable and record how git resolves under it.

    probe(argv, path) runs argv with PATH set to path and returns (exit status, output),
    or None and the error for a command that cannot start; tests substitute it. auto
    verifies the binary behind Apple's shim on darwin and writes wrapper_dir/git, a
    script for shell that execs that binary by absolute path: Apple's Git derives its
    exec path and templates from the path it was invoked by, so a link or copy would
    break them, and inserting the binary's own directory would also expose every other
    developer tool there (python3.9 among them). path changes nothing, and an explicit
    executable is used as given. Only the chosen executable's directory is inserted,
    immediately before the PATH entry that supplied the current git so earlier entries
    keep precedence; when no git resolves it is appended, which leaves every name that
    already resolved alone. git counts as already selected only when PATH reaches that
    same path, not another path to the same file. auto falls back to the unchanged
    PATH and records why; an explicit executable that the insertion does not reach is
    refused. Every name whose resolution changed is recorded with its old and new
    executable, and the version and exec path come from the git the tests reach, run
    under their PATH.
    """
    results = {}
    def ask(*argv, path=path_value):
        key = (path, *map(str, argv))
        if key not in results:
            results[key] = probe(list(key[1:]), path)
        return results[key]
    current = shutil.which("git", path=path_value)
    candidate = fallback = wrapper = None
    if requested == "auto":
        target, fallback = direct_git(current, platform, ask, shim)
        if target is not None:
            candidate = Path(wrapper_dir) / "git"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(f"#!{shell}\nexec {shlex.quote(str(target))} \"$@\"\n")
            candidate.chmod(0o755)
            wrapper = {"path": str(candidate), "shell": shell, "target": str(target)}
    elif requested != "path":
        candidate = Path(requested)
    entries = path_value.split(os.pathsep) if path_value else []
    selected_path, inserted, before = path_value, None, None
    if candidate is not None and current == str(candidate):
        fallback = f"git already resolves to {candidate}"
    elif candidate is not None:
        # shutil.which returns the first entry joined with the name, which identifies the supplier.
        suppliers = [index for index, entry in enumerate(entries) if os.path.join(entry, "git") == current]
        index = suppliers[0] if suppliers else len(entries)
        trial = os.pathsep.join([*entries[:index], str(candidate.parent), *entries[index:]])
        reached = shutil.which("git", path=trial)
        if reached != str(candidate):
            fallback = f"inserting {candidate.parent} would resolve git to {reached}, not {candidate}"
            if requested != "auto":
                raise RuntimeError(f"--git-executable {requested}: {fallback}; refused before provisioning")
            wrapper = None
        else:
            selected_path, inserted, before = trial, str(candidate.parent), entries[index] if suppliers else None
    changed = {}
    for name in sorted(os.listdir(inserted)) if inserted else ():
        old, new = shutil.which(name, path=path_value), shutil.which(name, path=selected_path)
        if old != new:
            changed[name] = {"old": old, "new": new}
    executable = shutil.which("git", path=selected_path)
    def reported(option):
        # Under the tests' PATH: a wrapper that execs git by name finds itself there.
        status, output = ask(executable, option, path=selected_path) if executable else (None, None)
        return output if status == 0 else None
    return selected_path, {"requested": requested, "inserted": inserted, "before": before, "wrapper": wrapper,
                           "executable": executable, "realpath": executable and os.path.realpath(executable),
                           "version": reported("--version"), "exec_path": reported("--exec-path"),
                           "fallback": fallback, "changed": changed}


def file_digests(root):
    """SHA-256 of every file under root, keyed by its relative POSIX path."""
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def project_git(project, environment):
    """The project's commit and status, or why Git could not report them.

    Only a project at the top of its own work tree is described: a copy inside
    another checkout would otherwise report the containing checkout's commit.
    """
    git = shutil.which("git", path=environment.get("PATH", os.defpath))
    record = {"git": git, "commit": None, "status": None, "dirty": None, "absent": None}
    if git is None:
        record["absent"] = "no git executable on PATH"
        return record
    # Discover the project itself, and never refresh its index while observing it.
    env = {key: value for key, value in environment.items() if not key.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    def ask(*arguments):
        # Observation must not stall the run: no terminal input, and a bounded wait.
        completed = subprocess.run([git, "-C", str(project), *arguments], env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, errors="replace", timeout=60)
        if completed.returncode:
            raise RuntimeError(f"git {' '.join(arguments)} exited {completed.returncode}: {completed.stderr.strip()}")
        return completed.stdout
    try:
        top = Path(ask("rev-parse", "--show-toplevel").strip()).resolve()
        if top != project:
            record["absent"] = f"the project is inside the Git work tree {top}, not at its top"
            return record
        commit = ask("rev-parse", "--verify", "HEAD").strip()
        status = ask("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        record["absent"] = str(error)
        return record
    record.update(commit=commit, status=status, dirty=bool(status))
    return record


def run_logged(command, log, **options):
    """Run a command whose stdout and stderr reach both the console and log.

    Each log line carries the stream it was written to; lines of the two
    streams interleave in the order the relays read them. The relays keep
    draining when a write fails, because a full pipe would stall pytest.
    """
    lock = threading.Lock()
    def record(data):
        with lock:
            try:
                log.write(data)
                log.flush()
            except (OSError, ValueError):
                pass
    def relay(source, console, label):
        pending = b""
        with open(source, "rb", buffering=0) as stream:
            while chunk := stream.read(65536):
                try:
                    console.write(chunk)
                    console.flush()
                except (OSError, ValueError):
                    pass
                *lines, pending = (pending + chunk).split(b"\n")
                record(b"".join(label + line + b"\n" for line in lines))
        if pending:
            record(label + pending + b"\n")
    ends, relays = [], []
    for console, label in ((sys.stdout.buffer, b"stdout: "), (sys.stderr.buffer, b"stderr: ")):
        read, write = os.pipe()
        ends.append(write)
        relays.append(threading.Thread(target=relay, args=(read, console, label), daemon=True))
        relays[-1].start()
    try:
        return subprocess.run(command, stdout=ends[0], stderr=ends[1], **options)
    finally:
        for end in ends:
            os.close(end)
        for thread in relays:
            thread.join(timeout=10)
        if any(thread.is_alive() for thread in relays):
            print("[stewart] a process pytest started still holds its output streams; "
                  "the pytest log may be incomplete", file=sys.stderr, flush=True)


def unique_keys(pairs):
    """Refuse a JSON object that repeats a key rather than let the last one decide."""
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"repeated keys {sorted({key for key in keys if keys.count(key) > 1})}")
    return dict(pairs)


def this_receipt(result, artifacts):
    """This invocation's receipt, or None and the reason it cannot be used."""
    if not result.is_file():
        return None, f"pytest wrote no receipt at {result}"
    try:
        observed = json.loads(result.read_bytes(), object_pairs_hook=unique_keys)
    except (OSError, ValueError) as error:
        return None, f"the receipt at {result} cannot be read: {error}"
    # A failed startup must not relabel a result left by a previous invocation.
    if not isinstance(observed, dict) or observed.get("artifacts") != str(artifacts):
        return None, f"{result} was not written by this invocation"
    return observed, None


def write_result(result, value):
    result.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def plan_retention(receipt, artifacts, policy, keep_nodes):
    """Plan removal of the owned paths of unselected nodes that passed every phase.

    Returns the plan recorded in the receipt and, for each planned path, the
    device and inode it had when planned. Entries no node owns, nodes with a
    phase that did not pass or was never recorded, nodes over the test budget,
    and anything that is not a directory stay. A pytest ``<prefix>current``
    link goes only with its target.
    """
    plan = {"policy": policy, "keep_nodes": keep_nodes, "missing_keep_nodes": {}, "withheld": None,
            "planned": [], "links": {}, "kept": {}, "results": {}, "seconds": None}
    phases, owners, overruns = (receipt.get(key) for key in ("phase_outcomes", "owned_paths", "budget_overruns"))
    if not all(isinstance(value, dict) for value in (phases, owners, overruns)):
        # Nothing shows what any node owns or that a requested node executed.
        plan["missing_keep_nodes"] = dict.fromkeys(keep_nodes)
        plan["withheld"] = "the receipt records no phase outcomes, owned paths or budget overruns"
        return plan, {}
    # A node executed only if its call ran: a skip mark ends it in setup, a
    # failed setup leaves no call, and pytest reports skips and xfails in the
    # call as "skipped". Each refused node keeps the phases that were observed.
    plan["missing_keep_nodes"] = {node: phases.get(node, {}) for node in keep_nodes
                                  if phases.get(node, {}).get("call") in (None, "skipped")}
    if plan["missing_keep_nodes"]:
        # An evidence run that lost its control is not evidence; a mistyped
        # node ID must not cost the evidence the caller meant to keep.
        plan["withheld"] = "--keep-node named nodes with no executed call on record"
        return plan, {}
    if policy == "all":
        plan["withheld"] = "--keep-artifacts all keeps every artifact"
        return plan, {}
    claims = {}
    for node, paths in owners.items():
        for path in paths:
            claims.setdefault(path, []).append(node)
    try:
        with os.scandir(artifacts) as entries:
            children = sorted(entry.path for entry in entries)
    except OSError as error:
        plan["withheld"] = f"the artifacts directory cannot be listed: {error}"
        return plan, {}
    identities, links = {}, []
    for path in children:
        try:
            observed = os.lstat(path)
        except OSError as error:
            plan["kept"][path] = f"cannot be inspected: {error}"
            continue
        nodes = claims.get(path, [])
        if not nodes and stat.S_ISLNK(observed.st_mode):
            links.append(path)
            continue
        if len(nodes) != 1:
            plan["kept"][path] = f"claimed by several nodes: {nodes}" if nodes else "no node owns this entry"
            continue
        node, = nodes
        outcomes = phases.get(node, {})
        if node in keep_nodes:
            plan["kept"][path] = f"--keep-node {node}"
        elif any(outcomes.get(phase) != "passed" for phase in PHASES):
            plan["kept"][path] = f"{node}: " + ", ".join(
                f"{phase} {outcomes.get(phase, 'not recorded')}" for phase in PHASES)
        elif node in overruns:
            # The run fails on this node; its command records show what the slow node ran.
            plan["kept"][path] = f"{node}: over --test-budget-seconds ({overruns[node]}s for setup, call and teardown)"
        elif not stat.S_ISDIR(observed.st_mode):
            plan["kept"][path] = "not a directory"
        else:
            plan["planned"].append(path)
            identities[path] = (observed.st_dev, observed.st_ino)
    for path in links:
        try:
            target = os.path.normpath(os.path.join(artifacts, os.readlink(path)))
        except OSError as error:
            plan["kept"][path] = f"cannot be inspected: {error}"
            continue
        if path.endswith("current") and target in identities:
            plan["links"][path] = target
        else:
            plan["kept"][path] = f"link to {target}, which this pass does not remove"
    return plan, identities


def remove_tree(top):
    """Remove one artifact directory, restoring owner access a test took away.

    shutil.rmtree's descriptor-based walk does not follow links inside the
    tree. A path refused for permission gets one retry after it and its parent
    regain owner read, write and search permission; what still fails is raised.
    """
    failures, retried = [], set()
    def handle(function, path, error):
        if isinstance(error, PermissionError) and path not in retried:
            retried.add(path)
            try:
                for directory in (os.path.dirname(path), path):
                    if directory == top or directory.startswith(top + os.sep):
                        mode = os.lstat(directory).st_mode
                        if stat.S_ISDIR(mode):
                            os.chmod(directory, stat.S_IMODE(mode) | stat.S_IRWXU)
                if function in (os.unlink, os.rmdir):
                    function(path)
                else:
                    rmtree(path)
                return
            except OSError as retry:
                error = retry
        if not isinstance(error, FileNotFoundError):
            failures.append(f"{path}: {error}")
    def rmtree(path):
        shutil.rmtree(path, onexc=handle)
    rmtree(top)
    if failures:
        raise OSError(f"{len(failures)} entries remain; first {failures[0]}")


def remove_planned(plan, identities, artifacts):
    """Remove the planned directories, then links whose target went, recording each result."""
    for path in plan["planned"]:
        try:
            observed = os.lstat(path)
            if not stat.S_ISDIR(observed.st_mode) or (observed.st_dev, observed.st_ino) != identities[path]:
                raise OSError("replaced after planning")
            remove_tree(path)
            plan["results"][path] = "removed"
        except OSError as error:
            plan["results"][path] = f"failed: {error}"
    for link, target in plan["links"].items():
        if plan["results"].get(target) != "removed":
            plan["results"][link] = f"kept: {target} was not removed"
            continue
        try:
            if os.path.normpath(os.path.join(artifacts, os.readlink(link))) != target:
                raise OSError("changed after planning")
            os.unlink(link)
            plan["results"][link] = "removed"
        except OSError as error:
            plan["results"][link] = f"failed: {error}"


def describe_phases(phases):
    """Name the phase outcomes a result recorded for a node, for a refusal message."""
    if phases is None:
        return "no usable result records its phases"
    return ", ".join(f"{phase} {outcome}" for phase, outcome in phases.items()) or "no phase recorded"


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Arguments check.py does not recognize go to pytest unchanged. Name tests relative to the "
        "staged suite root, which mirrors the project root: tests/test_runner.py or "
        "tests/test_runner.py::test_budget_charges_all_phases_and_ignores_node_names. Without a "
        "positional argument pytest collects the configured testpaths. A selection that collects a "
        "node more than once is refused, and so is a test outside the staged tests directory named beside "
        "a staged path. pytest loads the staged conftest only for staged paths, so a selection naming only "
        "outside paths runs them without the suite's checks and then fails for want of a receipt, as do "
        "options that end pytest before a session (--version, --markers). NAME is the --result stem. "
        "Beside the result a run keeps NAME.log (provisioning, build and the Git selection), NAME.pytest.log "
        "(pytest's argv, then its stdout and stderr, each line labelled with its stream), "
        "NAME-dist/ (the tested wheel) and NAME-artifacts-*/ (pytest's base temporary directory, reduced "
        "as --keep-artifacts says once this invocation's receipt is written; without that receipt nothing "
        "is removed)."))
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--wheelhouse", type=Path, default=os.environ.get("STEWART_WHEELHOUSE"),
                        help="the hash-locked wheelhouse (default: $STEWART_WHEELHOUSE, else <project>/.scratch/wheelhouse)")
    parser.add_argument("--parity-output", type=Path, help="write byte-contract vectors from the installed wheel")
    parser.add_argument("--result", type=Path, default=project / ".scratch/check-result.json",
                        help="the receipt path (default <project>/.scratch/check-result.json); use a fresh name per run")
    parser.add_argument("--fast", action="store_true",
                        help="select only `smoke and not heavy`; full coverage requires an unfiltered run")
    parser.add_argument("--test-budget-seconds", type=positive_seconds,
                        help="fail when any test's setup, call and teardown exceed this wall time")
    parser.add_argument("--total-budget-seconds", type=positive_seconds,
                        help="fail when provisioning, build and tests together exceed this wall time")
    parser.add_argument("--git-executable", type=git_executable, default="auto", metavar="{auto,path,/ABSOLUTE/git}", help=(
        "the git the tests reach through PATH. auto (default): on macOS, when git resolves to Apple's "
        "/usr/bin/git shim, verify the binary `xcrun --find git` names (the shim's version, an existing "
        "exec path, both inside the `xcode-select -p` developer directory), write a private git script "
        "that execs it by absolute path (/bin/dash, else /bin/sh), and insert that script's directory "
        "immediately before the PATH entry that supplied the shim, so only git changes; otherwise leave "
        "PATH unchanged and record why. path: leave PATH unchanged. An absolute path to an executable "
        "named git: insert its whole directory at the same place (so use a directory holding only git, and "
        "have a wrapper exec the real git by absolute path), appending it when no git resolves, unless PATH "
        "already reaches that exact path; refused when the inserted directory would not reach it. The "
        "choice, the resolved git, its version and exec path under the tests' PATH, and every name whose "
        "resolution changed go to the .log and the result"))
    parser.add_argument("--keep-artifacts", choices=("failed", "all"), default="failed",
                        help="failed (default): after the run, remove the test directory and private HOME of each "
                             "node whose setup, call and teardown all passed within any --test-budget-seconds, "
                             "keeping failed, skipped, interrupted and over-budget nodes and entries no node owns; "
                             "all: remove nothing")
    parser.add_argument("--keep-node", action="append", default=[], metavar="NODEID",
                        help="also keep this passing node's directories, named as the result names nodes "
                             "(repeatable); a named node with no executed call on record (no call phase, or a "
                             "skipped one, as pytest reports skips and xfails) fails the invocation and nothing "
                             "is removed")
    args, tests = parser.parse_known_args()
    if args.fast:
        if any(arg.startswith("-m") for arg in tests):
            parser.error("--fast owns the marker selection; do not combine it with -m")
        tests = ["-m", "smoke and not heavy", *tests]
    result = args.result.resolve()
    wheels = (args.wheelhouse or project / ".scratch/wheelhouse").resolve()
    if not wheels.is_dir():
        source = "--wheelhouse" if args.wheelhouse else ("$STEWART_WHEELHOUSE" if os.environ.get("STEWART_WHEELHOUSE")
                                                          else "the default")
        parser.error(f"no wheelhouse at {wheels} (from {source}); provision the hash-locked wheelhouse "
                     "before running tests; no downloads are attempted")
    result.parent.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTEST_", "STEWART_TEST_", "PYTHON"))}
    environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                       PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INDEX="1", PIP_NO_CACHE_DIR="1",
                       STEWART_WHEELHOUSE=str(wheels))
    transcript = result.with_suffix(".log")
    with tempfile.TemporaryDirectory(prefix="stewart-wheel-check-") as temporary, transcript.open("w") as log:
        root = Path(temporary).resolve()
        # Decided once, before provisioning; only the tests' environment receives the PATH.
        shell = "/bin/dash" if os.access("/bin/dash", os.X_OK) else "/bin/sh"
        tests_path, git_selection = select_git(args.git_executable, environment.get("PATH", os.defpath), sys.platform,
                                               lambda argv, path: run_probe(argv, {**environment, "PATH": path}),
                                               root / "git-selection", shell)
        log.write(json.dumps({"git_selection": git_selection}) + "\n"); log.flush()
        if git_selection["inserted"]:
            placed = (f"inserted {git_selection['inserted']} before {git_selection['before']}" if git_selection["before"]
                      else f"appended {git_selection['inserted']}")
            detail = f"{placed}; changed names: {', '.join(git_selection['changed']) or 'none'}"
        else:
            detail = f"PATH unchanged ({git_selection['fallback'] or '--git-executable ' + args.git_executable})"
        found = (f"git {git_selection['executable']} ({git_selection['version']})" if git_selection["executable"]
                 else "no git on PATH")
        print(f"[stewart] {found}: {detail}", flush=True)
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
        if git_selection["inserted"]:
            environment["PATH"] = tests_path
        if args.test_budget_seconds is not None:
            environment["STEWART_TEST_BUDGET_SECONDS"] = str(args.test_budget_seconds)
        artifacts = Path(tempfile.mkdtemp(prefix=result.stem + "-artifacts-", dir=result.parent))
        environment["STEWART_TEST_ARTIFACTS"] = str(artifacts)
        # No suite directory argument: pytest falls back to testpaths, and naming
        # it beside a caller's path would collect that path's tests twice.
        command = [str(python), "-I", "-B", "-m", "pytest", "-c", str(suite / "pyproject.toml"),
                   f"--confcutdir={suite}", f"--basetemp={artifacts}", *tests]
        # The wheel does not identify the tests: record the staged suite, this script and
        # the project's Git state as pytest is about to see them, with the tests' environment.
        identity = {"suite_sha256": file_digests(suite),
                    "check_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
                    "project_git": project_git(project, environment)}
        print(f"[stewart] wheel {wheel.name} sha256={digest}; Python {sys.version.split()[0]}", flush=True)
        # A pytest that stops before its session starts writes no receipt; its streams stay here regardless.
        with (result.parent / (result.stem + ".pytest.log")).open("wb") as streams:
            streams.write(json.dumps({"argv": command, "cwd": str(suite)}).encode() + b"\n")
            outcome = run_logged(command, streams, cwd=suite, env=environment)
        elapsed = time.monotonic() - started
        over_budget = args.total_budget_seconds is not None and elapsed > args.total_budget_seconds
        # Only augment this invocation's receipt; a failed startup must not
        # relabel a result left by a previous invocation at the same path.
        observed, unusable = this_receipt(result, artifacts)
        receipted = observed is not None
        keep_nodes = list(dict.fromkeys(args.keep_node))
        if receipted:
            plan, identities = plan_retention(observed, artifacts, args.keep_artifacts, keep_nodes)
            missing = plan["missing_keep_nodes"]
        else:
            # Nothing attributes any directory to a node, and nothing shows a requested node executed.
            plan, identities, missing = None, {}, dict.fromkeys(keep_nodes)
        status = outcome.returncode or int(over_budget) or int(bool(missing))
        if receipted:
            observed.update(total_seconds=elapsed, total_budget_seconds=args.total_budget_seconds,
                            total_budget_exceeded=over_budget, fast=args.fast, git_selection=git_selection,
                            runner_exit_status=status)
            observed.update(identity, retention=plan)
            # The plan is on record before the first removal; each result follows.
            write_result(result, observed)
            removal_started = time.monotonic()
            try:
                remove_planned(plan, identities, artifacts)
            finally:
                # An interrupted pass keeps what it recorded and marks the rest rather than guess.
                for path in [*plan["planned"], *plan["links"]]:
                    plan["results"].setdefault(path, "interrupted before a result was recorded")
                plan["seconds"] = time.monotonic() - removal_started
                write_result(result, observed)
        print(f"[stewart] total wall time {elapsed:.3f}s (including provisioning and build)", flush=True)
        if not receipted:
            print(f"[stewart] retention: removed nothing; {unusable}", flush=True)
        elif plan["withheld"]:
            print(f"[stewart] retention ({args.keep_artifacts}): removed nothing; {plan['withheld']}", flush=True)
        else:
            removed = sum(value == "removed" for value in plan["results"].values())
            print(f"[stewart] retention ({args.keep_artifacts}): removed {removed} of "
                  f"{len(plan['planned']) + len(plan['links'])} planned paths, kept {len(plan['kept'])} "
                  f"entries; the result's retention field lists each", flush=True)
            for path, value in plan["results"].items():
                if value.startswith("failed"):
                    print(f"[stewart] could not remove {path}: {value}", file=sys.stderr, flush=True)
        if missing:
            refused = "; ".join(f"{node} ({describe_phases(phases)})" for node, phases in missing.items())
            print(f"[stewart] --keep-node targets with no executed call on record: {refused}; nothing was removed",
                  file=sys.stderr, flush=True)
        if over_budget:
            print(f"[stewart] total budget exceeded: {elapsed:.3f}s > {args.total_budget_seconds}s", file=sys.stderr)
        if not receipted and not outcome.returncode:
            # Pytest loads the staged conftest only for paths under the suite: a
            # selection naming only tests elsewhere runs them without its boundary
            # checks and refusals, and writes no receipt.
            print(f"[stewart] pytest exited 0 without writing this invocation's receipt to {result}: either the "
                  "selection named only paths outside the staged suite, so its conftest and checks never ran (name "
                  "tests as tests/<file>.py or tests/<file>.py::<test>), or an option ended pytest before a session "
                  "(--version, --markers)", file=sys.stderr)
            return 1
        return status


if __name__ == "__main__":
    raise SystemExit(main())
