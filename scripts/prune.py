"""Remove the artifacts directories of retained check.py runs, keeping each run's record.

A run is what check.py leaves beside NAME.json: NAME.log, NAME.pytest.log,
NAME-dist/ and NAME-artifacts-*/. The receipt, logs, streams and wheel are the
run's record and stay. The artifacts directory is working state: it holds the
test directories and private HOMEs the receipt describes, and it goes once the
run's purpose is served. DEVELOPMENT.md states the policy; this script is its
only mechanism, and it never removes a record.

Without --apply nothing is written or removed: the plan is printed. With it,
the plan is recorded under ROOT/pruned/ before the first removal and each
result after it, and NAME.pruned.json beside each pruned receipt names that
record. Only a receipt binds an artifacts directory: the directory it names
must be a real directory beside it whose name starts with NAME-artifacts-. A
directory nothing binds is an orphan, removed only with --orphans.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ARTIFACTS_MARK = "-artifacts-"
# Directories under the root that hold no runs and are never entered.
UNENTERED = frozenset({"wheelhouse", "pruned"})
# The receipt fields that show a run passed completely; anything else keeps it by default.
CLEAN_OUTCOMES = frozenset({"passed", "skipped"})


def load_check():
    """check.py's removal helper, loaded by path: isolated mode keeps this directory off sys.path.

    remove_tree is the descriptor-based removal the retention pass uses, with
    the same owner-permission retry; sharing it keeps both removals identical.
    """
    script = Path(__file__).resolve().with_name("check.py")
    spec = importlib.util.spec_from_file_location("stewart_check", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, hashlib.sha256(script.read_bytes()).hexdigest()


def unique_keys(pairs):
    """A JSON object with a repeated key is refused rather than letting one value win."""
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"repeated keys {sorted({key for key in keys if keys.count(key) > 1})}")
    return dict(pairs)


def read_receipt(path):
    """A check.py receipt at path, or None: other JSON files, markers and records are not receipts."""
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=unique_keys)
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("artifacts"), str):
        return None
    if not isinstance(value.get("wheel"), str) or not isinstance(value.get("outcomes"), dict):
        return None
    return value


def is_directory(path):
    """Whether path is a directory itself, not a link to one."""
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def discover(root):
    """Receipts and artifacts directories under root, without entering any run's own directories.

    Returns the receipts keyed by their name (the receipt path relative to the
    root without .json), each with the directory its receipt binds or the
    reason it binds none, and every candidate artifacts directory keyed by path.
    """
    runs, candidates = {}, {}
    for dirpath, dirnames, filenames in os.walk(root):
        entered = []
        for name in sorted(dirnames):
            path = os.path.join(dirpath, name)
            if ARTIFACTS_MARK in name:
                candidates[path] = None  # bound later by its receipt, if any
            elif name not in UNENTERED and not name.endswith("-dist") and not os.path.islink(path):
                entered.append(name)
        dirnames[:] = entered
        for name in sorted(filenames):
            if not name.endswith(".json") or name.endswith(".pruned.json"):
                continue
            receipt_path = Path(dirpath) / name
            receipt = read_receipt(receipt_path)
            if receipt is None:
                continue
            stem = name[:-len(".json")]
            named = os.path.normpath(receipt["artifacts"])
            run = {"receipt": str(receipt_path), "stem": stem, "artifacts": named, "bound": False, "unbound": None}
            if os.path.dirname(named) != dirpath or not os.path.basename(named).startswith(stem + ARTIFACTS_MARK):
                run["unbound"] = f"the receipt names {named}, which is not a {stem}{ARTIFACTS_MARK}* entry beside it"
            elif not is_directory(named):
                markers = sorted(Path(dirpath).glob(stem + ".pruned*.json"))
                if markers and not os.path.lexists(named):
                    run["unbound"] = f"its artifacts directory was pruned; {markers[-1]} names the record"
                else:
                    run["unbound"] = f"the receipt names {named}, which is not a directory" + (
                        " (a link)" if os.path.islink(named) else " (missing)" if not os.path.lexists(named) else "")
            elif candidates.get(named) is not None:
                run["unbound"] = f"the receipt names {named}, already bound by {candidates[named]}"
            else:
                run["bound"] = True
                candidates[named] = str(receipt_path)
            runs[str(receipt_path.relative_to(root).with_suffix("")).replace(os.sep, "/")] = run
    return runs, candidates


def measure(top):
    """Allocated bytes and entry count under top, following no links."""
    allocated, entries = 0, 0
    try:
        observed = os.lstat(top)
    except OSError:
        return None, None
    allocated += observed.st_blocks * 512
    for dirpath, dirnames, filenames in os.walk(top):
        for name in dirnames + filenames:
            try:
                observed = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            allocated += observed.st_blocks * 512
            entries += 1
    return allocated, entries


def describe(receipt):
    """What keeps a run by default: outcomes that were not clean, and what makes it an evidence run."""
    problems, evidence = [], []
    outcomes = receipt.get("outcomes") or {}
    if set(outcomes) - CLEAN_OUTCOMES:
        problems.append("outcomes " + ", ".join(f"{count} {name}" for name, count in sorted(outcomes.items())))
    if receipt.get("exit_status") != 0:
        problems.append(f"pytest exit status {receipt.get('exit_status')}")
    if receipt.get("runner_exit_status", 0) != 0:
        problems.append(f"runner exit status {receipt.get('runner_exit_status')}")
    if receipt.get("budget_overruns"):
        problems.append(f"{len(receipt['budget_overruns'])} nodes over the test budget")
    if receipt.get("total_budget_exceeded"):
        problems.append("total budget exceeded")
    retention = receipt.get("retention")
    if isinstance(retention, dict):
        if retention.get("policy") == "all":
            evidence.append("--keep-artifacts all")
        if retention.get("keep_nodes"):
            evidence.append("--keep-node " + " ".join(map(str, retention["keep_nodes"])))
    reduced = isinstance(retention, dict) and retention.get("withheld") is None and "results" in retention
    return problems, evidence, reduced


def git_citations(project, stems, run=subprocess.run):
    """Tracked files of project naming each stem, or None and why Git cannot say.

    The project must be the top of its own work tree, as check.py's receipt
    requires before describing it; a containing repository's files are not the
    project's citations, and a project it does not track would look uncited.
    """
    def git(*arguments):
        try:
            completed = run(["git", "-C", str(project), *arguments], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, errors="replace", timeout=120)
        except (OSError, subprocess.SubprocessError) as error:
            return None, str(error)
        return completed.returncode, completed.stdout if completed.returncode in (0, 1) else completed.stderr.strip()
    status, top = git("rev-parse", "--show-toplevel")
    if status != 0:
        return None, f"git rev-parse --show-toplevel failed in {project}: {top}"
    try:
        if not os.path.samefile(top.strip(), project):
            return None, f"{project} is not the top of its own Git work tree ({top.strip()} is)"
    except OSError as error:
        return None, f"cannot compare {project} with {top.strip()}: {error}"
    citations = {}
    for stem in sorted(set(stems)):
        status, output = git("grep", "-I", "-l", "-z", "--fixed-strings", "-e", stem, "--", ".")
        if status not in (0, 1):
            return None, f"git grep for {stem!r} failed ({status}): {output}"
        citations[stem] = sorted(filter(None, output.split("\0"))) if status == 0 else []
    return citations, None


def running_arguments(run=subprocess.run):
    """The argument strings of every running process, or None and why ps cannot list them."""
    try:
        completed = run(["ps", "-A", "-o", "args="], stdin=subprocess.DEVNULL,
                        capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)
    if completed.returncode:
        return None, f"ps exited {completed.returncode}: {completed.stderr.strip()}"
    return completed.stdout.splitlines(), None


def in_use(path, processes):
    """The first running process whose arguments name path, else None."""
    return next((line.strip() for line in processes if path in line), None)


def resolve_names(names, runs):
    """Map each --run NAME to a discovered run, or return the refusal."""
    chosen, refusals = {}, []
    for name in names:
        key = name[:-len(".json")] if name.endswith(".json") else name
        if key in runs:
            chosen[key] = runs[key]
            continue
        matches = [candidate for candidate, run in runs.items() if run["stem"] == key]
        if len(matches) == 1:
            chosen[matches[0]] = runs[matches[0]]
        elif matches:
            refusals.append(f"--run {name} is ambiguous; name one of {', '.join(matches)}")
        else:
            refusals.append(f"--run {name} names no receipt under the root; the runs are "
                            + (", ".join(sorted(runs)) or "none"))
    return chosen, refusals


def plan_prune(root, runs, candidates, names, include_orphans, citations, processes):
    """Decide each run and orphan, measuring every artifacts directory. Returns the plan and refusals."""
    plan = {"runs": {}, "orphans": {}, "planned": [], "identities": {}, "results": {}, "refusals": []}
    chosen, refusals = resolve_names(names, runs)
    plan["refusals"].extend(refusals)
    for name, run in sorted(runs.items()):
        receipt = read_receipt(Path(run["receipt"]))
        problems, evidence, reduced = describe(receipt)
        entry = {"receipt": run["receipt"], "artifacts": run["artifacts"], "bound": run["bound"],
                 "outcomes": receipt.get("outcomes"), "reduced": reduced, "problems": problems, "evidence": evidence,
                 "cited_by": None if citations is None else citations.get(run["stem"], []),
                 "allocated_bytes": None, "entries": None, "named": name in chosen, "decision": None}
        if run["bound"]:
            entry["allocated_bytes"], entry["entries"] = measure(run["artifacts"])
        plan["runs"][name] = entry
        if not run["bound"]:
            entry["decision"] = "kept: " + run["unbound"]
            if name in chosen:
                plan["refusals"].append(f"--run {name}: {run['unbound']}")
            continue
        user = None if processes is None else in_use(run["artifacts"], processes)
        if user:
            entry["decision"] = f"kept: named by a running process: {user}"
            if name in chosen:
                plan["refusals"].append(f"--run {name}: its artifacts directory is named by a running process: {user}")
            continue
        if name in chosen:
            entry["decision"] = "planned: named by --run"
        else:
            reasons = list(problems) + [f"evidence run ({item})" for item in evidence]
            if citations is None:
                reasons.append("citations unknown")
            elif entry["cited_by"]:
                reasons.append("cited by " + ", ".join(entry["cited_by"]))
            if reasons:
                entry["decision"] = "kept: " + "; ".join(reasons) + " (name it with --run to remove it)"
            else:
                entry["decision"] = "planned: every outcome passed or skipped, no evidence selection, uncited"
        if entry["decision"].startswith("planned"):
            plan["planned"].append(run["artifacts"])
    for path in sorted(candidates):
        if candidates[path] is not None:
            continue
        entry = {"allocated_bytes": None, "entries": None, "decision": None}
        plan["orphans"][path] = entry
        if not is_directory(path):
            entry["decision"] = "kept: not a directory" + (" (a link)" if os.path.islink(path) else "")
            continue
        entry["allocated_bytes"], entry["entries"] = measure(path)
        if not include_orphans:
            entry["decision"] = "kept: no receipt binds it (remove orphans with --orphans)"
        elif processes is None:
            entry["decision"] = "kept: no receipt binds it and the process list is unavailable"
            plan["refusals"].append(f"--orphans needs the process list to show {path} is not in use")
        elif in_use(path, processes):
            entry["decision"] = f"kept: named by a running process: {in_use(path, processes)}"
        else:
            entry["decision"] = "planned: --orphans"
            plan["planned"].append(path)
    for path in plan["planned"]:
        observed = os.lstat(path)
        plan["identities"][path] = [observed.st_dev, observed.st_ino]
    return plan


def gigabytes(value):
    return "unmeasured" if value is None else f"{value / 1e9:.2f} GB"


def print_plan(plan, root):
    for name, entry in plan["runs"].items():
        outcomes = ", ".join(f"{count} {label}" for label, count in sorted((entry["outcomes"] or {}).items())) or "no outcomes"
        size = f"{gigabytes(entry['allocated_bytes'])} in {entry['entries']:,} entries" if entry["bound"] else "unbound"
        shape = "reduced" if entry["reduced"] else "unreduced"
        print(f"[prune] {name}: {size}; {outcomes}; {shape} -> {entry['decision']}")
    for path, entry in plan["orphans"].items():
        size = gigabytes(entry["allocated_bytes"]) + (f" in {entry['entries']:,} entries" if entry["entries"] is not None else "")
        print(f"[prune] orphan {os.path.relpath(path, root)}: {size} -> {entry['decision']}")
    allocated = sum(entry["allocated_bytes"] or 0 for group in (plan["runs"], plan["orphans"])
                    for entry in group.values() if entry["decision"].startswith("planned"))
    kept = sum(1 for group in (plan["runs"], plan["orphans"]) for entry in group.values()
               if entry["decision"].startswith("kept"))
    print(f"[prune] planned {len(plan['planned'])} directories ({gigabytes(allocated)}); kept {kept}")


def exclusive(directory, stem, suffix):
    """Create stem.suffix in directory, or stem.suffix.N, whichever does not exist; an existing name is evidence."""
    for attempt in range(1, 1000):
        candidate = directory / (f"{stem}.{suffix}" if attempt == 1 else f"{stem}.{suffix}.{attempt}")
        try:
            return candidate, os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
    raise OSError(f"no free name for {directory / stem}.{suffix}")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def apply_plan(plan, root, record, remove_tree):
    """Remove the planned directories, recording the plan first and each result after."""
    write_json(record, plan)
    started = time.monotonic()
    try:
        for path in plan["planned"]:
            try:
                observed = os.lstat(path)
                if not stat.S_ISDIR(observed.st_mode) or [observed.st_dev, observed.st_ino] != plan["identities"][path]:
                    raise OSError("replaced after planning")
                remove_tree(path)
                plan["results"][path] = "removed"
            except OSError as error:
                plan["results"][path] = f"failed: {error}"
    finally:
        for path in plan["planned"]:
            plan["results"].setdefault(path, "interrupted before a result was recorded")
        plan["seconds"] = time.monotonic() - started
        write_json(record, plan)
    for name, entry in plan["runs"].items():
        if entry["artifacts"] in plan["results"]:
            receipt = Path(entry["receipt"])
            marker, descriptor = exclusive(receipt.parent, receipt.stem, "pruned.json")
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"record": str(record), "pruned_artifacts": entry["artifacts"],
                                         "result": plan["results"][entry["artifacts"]],
                                         "allocated_bytes": entry["allocated_bytes"], "entries": entry["entries"]},
                                        sort_keys=True, indent=2) + "\n")
            entry["marker"] = str(marker)
    write_json(record, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=(
        "By default a run is planned for removal only when its receipt binds the directory, every recorded "
        "outcome passed or was skipped, pytest and the runner exited 0, no budget was exceeded, the receipt "
        "selected no evidence (--keep-artifacts all or --keep-node), and no tracked file of the project names "
        "the receipt's stem. Everything else is kept and its reason printed; --run NAME removes a named run "
        "regardless of those reasons, but never an unbound run or one a running process names. NAME is the "
        "receipt's path relative to the root without .json (identity/repair-314), or its bare stem when unique. "
        "Records (NAME.json, .log, .pytest.log, .out, NAME-dist/) are never removed here: they leave with the "
        "plan or report that cites them."))
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=project / ".scratch",
                        help="the directory holding retained runs (default <project>/.scratch)")
    parser.add_argument("--project", type=Path, default=project,
                        help="the Git work tree whose tracked files are searched for citations (default: this project)")
    parser.add_argument("--run", action="append", default=[], metavar="NAME",
                        help="remove this run's artifacts directory whatever its outcomes or citations (repeatable)")
    parser.add_argument("--orphans", action="store_true",
                        help="also remove artifacts directories no receipt binds, when no running process names them")
    parser.add_argument("--apply", action="store_true",
                        help="remove the planned directories; without it the plan is printed and nothing is written")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"no directory at {root}")
    runs, candidates = discover(root)
    citations, uncited_reason = git_citations(args.project.resolve(), [run["stem"] for run in runs.values()])
    if uncited_reason:
        print(f"[prune] citations unknown: {uncited_reason}", file=sys.stderr, flush=True)
    processes, no_processes = running_arguments()
    if no_processes:
        print(f"[prune] process list unavailable: {no_processes}", file=sys.stderr, flush=True)
    plan = plan_prune(root, runs, candidates, args.run, args.orphans, citations, processes)
    print_plan(plan, root)
    if plan["refusals"]:
        for refusal in plan["refusals"]:
            print(f"[prune] refused: {refusal}", file=sys.stderr, flush=True)
        print("[prune] nothing was removed", file=sys.stderr, flush=True)
        return 2
    if not args.apply:
        print("[prune] dry run: nothing was written or removed; add --apply to remove the planned directories")
        return 0
    check, check_sha256 = load_check()
    plan.update(root=str(root), project=str(args.project.resolve()), arguments={"run": args.run, "orphans": args.orphans},
                started=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                prune_sha256=hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
                check_sha256=check_sha256, citations_unknown=uncited_reason, processes_unknown=no_processes)
    (root / "pruned").mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record, descriptor = exclusive(root / "pruned", f"{stamp}-{os.getpid()}", "json")
    os.close(descriptor)
    apply_plan(plan, root, record, check.remove_tree)
    removed = sum(value == "removed" for value in plan["results"].values())
    print(f"[prune] removed {removed} of {len(plan['planned'])} planned directories in {plan['seconds']:.1f}s; "
          f"record {record}")
    failures = {path: value for path, value in plan["results"].items() if value != "removed"}
    for path, value in failures.items():
        print(f"[prune] could not remove {path}: {value}", file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
