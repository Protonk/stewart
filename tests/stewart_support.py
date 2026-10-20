"""Helpers shared by the stewart custody tests.

The disposable repository places the assignment workspace at ``audits/ws``, a
path with no relation to any real workspace, so every test that passes through
these helpers is evidence that the tool derives its paths from the workspace it
is given rather than from a baked-in coordinate.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace

from stewart.collect import collect
from stewart.prepare import prepare
from stewart.workspace import workspace as _workspace

WS = "audits/ws"
SECTION_BODIES = {
    "Question": "Does the implementation preserve the documented value?",
    "Decision": "Whether to investigate a conversion loss.",
    "Scope and exclusions": "Read input.txt; do not broaden the task.",
    "Evidence": "The input is an authored positive example.",
    "Stop condition": "Report the comparison or the missing evidence.",
}


def assignment_text(meta: dict, *, extra_sections: dict | None = None) -> str:
    """A complete, assigned prompt around one metadata block."""
    sections = dict(SECTION_BODIES)
    if extra_sections:
        sections.update(extra_sections)
    body = "".join(f"## {title}\n{text}\n\n" for title, text in sections.items())
    return "# Audit assignment\n\n```audit-assignment\n" + json.dumps(meta, indent=2) + "\n```\n\n" + body


def session_path(checkout, ident: str = "one-question") -> Path:
    """The session's repo-wide private directory under the Git common directory."""
    from stewart.session import session_dir
    return session_dir(checkout.ws, ident)


def git_working_directories(monkeypatch, function, *args, **kwargs):
    """``function(*args, **kwargs)``'s result and the working directory of each Git process it started.

    Every process goes through ``subprocess.Popen`` (``subprocess.run`` uses it), which is
    replaced process-wide while ``function`` runs.
    """
    import os
    import subprocess
    real, places = subprocess.Popen, []

    class Started(real):
        def __init__(self, *args, **options):
            argv = args[0] if args else options["args"]  # Stewart's git() passes args= by keyword
            program = argv[0] if isinstance(argv, (list, tuple)) else argv
            if os.path.basename(os.fsdecode(program)) == "git":
                places.append(Path(options.get("cwd") or os.getcwd()))
            super().__init__(*args, **options)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", Started)
        return function(*args, **kwargs), places


def read_json(location: Path) -> dict:
    return json.loads(location.read_text(encoding="utf-8"))


def make_checkout(tmp_path: Path, run_cmd, *, ws_rel: str = WS, name: str = "main") -> SimpleNamespace:
    """Build a disposable main checkout with one assignment workspace."""
    repo = (tmp_path / name).resolve()
    repo.mkdir(parents=True)

    def git(*args, cwd=repo):
        return run_cmd(["git", *args], cwd=cwd, check=True).stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Stewart test")
    git("config", "user.email", "stewart-test@example.invalid")
    # The fixture's own areas: ``ignored/`` for supplemental inputs and
    # ``.scratch/`` for manager-chosen evidence packages. Stewart's storage needs
    # no ignore rule and writes nothing in either.
    (repo / ".gitignore").write_text(".scratch/\nignored/\n", encoding="utf-8")
    (repo / ".scratch").mkdir()
    (repo / "input.txt").write_text("committed input\n", encoding="utf-8")
    (repo / "other.txt").write_text("unrelated input\n", encoding="utf-8")
    tasks = repo / ws_rel
    tasks.mkdir(parents=True)
    # Role files are sufficient; no harness-specific entry file is required.
    (tasks / "MAINTAINER.md").write_text("Maintainer instructions\n", encoding="utf-8")
    (tasks / "AUDITOR.md").write_text("Auditor instructions\n", encoding="utf-8")
    (tasks / "PROMPT.md").write_text("**UNASSIGNED**\n", encoding="utf-8")
    # The audited project has no Stewart source; helpers come from the supplied runtime.
    git("add", "--", ".")
    git("commit", "-qm", "Target fixture")
    ws = _workspace(repo, ws_rel)
    meta = {
        "audit_id": "one-question", "target_commit": git("rev-parse", "HEAD"),
        "report_path": ws.report_path("one-question"),
        "input_files": ["input.txt"], "external_sources": [],
    }

    def prompt_commit(extra_paths=(), *, text: str | None = None):
        (repo / ws.prompt).write_text(text if text is not None else assignment_text(meta), encoding="utf-8")
        git("add", "--", ws.prompt, *extra_paths)
        git("commit", "-qm", "Prompt fixture")
        return git("rev-parse", "HEAD")

    return SimpleNamespace(repo=repo, ws=ws, meta=meta, git=git, prompt_commit=prompt_commit, tmp=tmp_path)


def response_for(collected: dict, *, decision: str = "No action; retain the report.", **overrides) -> dict:
    """A structurally valid maintainer response bound to one collection result."""
    receipt = collected["receipt"]
    response = {
        "collection": collected["collection"],
        "collection_sha256": _hash.sha256_bytes((Path(collected["path"]) / "collection.json").read_bytes()),
        "accepted": [], "rejected": [], "unresolved": [],
        "custody_gaps": {gap["id"]: "reviewed; no bearing on the question" for gap in collected["gaps"]},
        "decision": decision,
    }
    if receipt["report_status"] == "present":
        response["report_sha256"] = receipt["report_sha256"]
    else:
        response["report_gap"] = f"no report captured (status {receipt['report_status']})"
    response.update(overrides)
    return response


PAUSE_NOTE = "the fixture's only writer (this test) holds its writes; no other writer exists"


def prepared_session(checkout, *, mode: str = "snapshot", report: str | None = "A partial report.\n") -> SimpleNamespace:
    """Commit the fixture prompt, prepare, and optionally write a report in the worktree."""
    revision = checkout.prompt_commit()
    paused = mode == "paused"
    prepared = prepare(checkout.ws, revision, mode=mode, writers_paused=paused,
                       pause_note=PAUSE_NOTE if paused else None)
    session = Path(prepared["session"])
    worktree = Path(prepared["worktree"])
    report_path = worktree / checkout.meta["report_path"]
    if report is not None:
        report_path.write_text(report, encoding="utf-8")
    return SimpleNamespace(prepared=prepared, session=session, worktree=worktree, report=report_path,
                           revision=revision)


def collect_with_deadline(checkout, *, seconds: float = 60.0) -> dict:
    """Collect on a worker thread so a collector that blocks on a special entry fails instead of hanging."""
    box: dict = {}

    def work():
        try:
            box["result"] = collect(checkout.ws, checkout.meta["audit_id"], auditor_stopped="finished")
        except BaseException as exc:  # noqa: BLE001 - surfaced on the test thread below
            box["error"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), f"collection did not finish within {seconds}s: a special entry blocked it"
    if "error" in box:
        raise box["error"]
    return box["result"]


def snapshot_tree(root: Path) -> dict[str, str]:
    """Path -> digest or link/kind marker for everything below root, for read-only proofs."""
    from stewart import _util as _hash

    out: dict[str, str] = {}
    for entry in sorted(root.rglob("*")):
        rel = str(entry.relative_to(root))
        if entry.is_symlink():
            out[rel] = "link:" + str(entry.readlink())
        elif entry.is_dir():
            out[rel] = "dir"
        elif entry.is_file():
            out[rel] = _hash.sha256_bytes((entry).read_bytes())
        else:
            out[rel] = "special"
    return out


# --- experiment fixtures ---------------------------------------------------------

import sys  # noqa: E402

from stewart import _util as _hash  # noqa: E402
import stewart  # noqa: E402

INSTALLED_LIB = Path(stewart.__file__).parent.parent
SCRIPT = f"{WS}/scratch/one-question/artifacts/experiment.py"
PREDICTION = f"{WS}/scratch/one-question/artifacts/prediction.md"
OUTPUT = f"{WS}/scratch/one-question/run"
MANIFEST = "evidence/protected.json"

AUTHORIZATION = {
    "Experiment authorization": (
        "Permission: construction plus execution of the released script, once.\n"
        "Target and variation: synthetic comparisons only.\n"
        "Protected state: input.txt and other.txt byte-identical at both endpoints.\n"
        "Construction area: the declared scratch path.\n"
        "Execution allowance: the single command template in the grant object.\n"
        "Action bounds and stops: one invocation; stop on any failure.\n"
        "Preservation evidence: the protected manifest, hashed by the wrapper at both endpoints."
    ),
}

REVIEW = {
    "cases": [
        {"id": "o1", "population": "ordinary", "role": "measured property varies", "expected_admission": True,
         "prediction": "agree", "measurements": ["value"]},
        {"id": "o2", "population": "ordinary", "role": "ignored metadata varies", "expected_admission": True,
         "prediction": "agree", "measurements": ["value"]},
        {"id": "c1", "population": "control", "role": "planted disagreement", "expected_admission": True,
         "prediction": "mismatch", "measurements": ["value"]},
        {"id": "r1", "population": "ordinary", "role": "planned refusal", "expected_admission": False,
         "prediction": "refused", "measurements": []},
    ],
    "admissibility_reasoning": "synthetic cases whose admission is declared by construction",
    "static_review": ["the script uses the pinned initial-process ledger and writes one receipt"],
    "limits": ["synthetic child; no project semantics are measured"],
}

DEFAULT_CASES = '''ledger.declare("o1", population="ordinary", role="measured property varies", expected_admission=True, prediction="agree", measurements=["value"])
ledger.declare("o2", population="ordinary", role="ignored metadata varies", expected_admission=True, prediction="agree", measurements=["value"])
ledger.declare("c1", population="control", role="planted disagreement", expected_admission=True, prediction="mismatch", measurements=["value"])
ledger.declare("r1", population="ordinary", role="planned refusal", expected_admission=False, prediction="refused", measurements=[])
for case in ("o1", "o2", "c1", "r1"):
    ledger.reach(case)
ledger.admit("o1", True)
ledger.admit("o2", True)
ledger.admit("c1", True)
ledger.admit("r1", False, reason="declared inadmissible")
ledger.compare("o1", "value", 1, 1)
ledger.compare("o2", "value", 1, 1, note="metadata differs; value identical")
control = ledger.compare("c1", "value", 1, 2, note="planted")
'''

CHILD = '''"""Synthetic experiment child for the stewart tests; harmless."""
import argparse
import json
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
parser.add_argument("--manifest", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(args.root)
assert Path.cwd() == root, "the wrapper runs the child with cwd at the explicit root"
##BEFORE##
from _stewart_ledger_v1 import Ledger

output = root / args.output
ledger = Ledger(output / "ledger.jsonl")
control = None
##CASES##
##BODY##
(output / "receipt.json").write_text(json.dumps({
    "root": str(root), "script": __file__, "control_mismatch": control, "self_reported_mismatches": 0,
    "modules": sorted(name for name in sys.modules if name.startswith(("tools.", "stewart", "_stewart"))),
    "ledger_file": sys.modules["_stewart_ledger_v1"].__file__,
}) + "\\n")
print("done")
'''


def grant(**overrides) -> dict:
    base = {
        "schema": "stewart.experiment-grant/2", "permission": "construction+execution", "script": SCRIPT, "freeze": [PREDICTION], "output_area": OUTPUT,
        "protected_manifest": MANIFEST, "interpreter": "tool-interpreter", "environment": "minimal",
        "cwd": "worktree",
        "argv_template": ["{interpreter}", "-B", "{script}", "--root", "{root}", "--manifest", "{manifest}",
                          "--output", "{output}"],
        "invocations": 1,
    }
    base.update(overrides)
    return base


def child_source(*, cases: str = DEFAULT_CASES, body: str = "", before: str = "") -> str:
    return CHILD.replace("##CASES##", cases).replace("##BODY##", body).replace("##BEFORE##", before)


SCRATCH = [f"{WS}/scratch/one-question/artifacts", f"{WS}/scratch/one-question/run"]


def experiment_checkout(tmp_path: Path, run_cmd, *, scratch: list[str] | None = None,
                        **grant_overrides) -> SimpleNamespace:
    """A source-free project with a protected manifest and a granted script."""
    checkout = make_checkout(tmp_path, run_cmd)
    repo, git = checkout.repo, checkout.git
    manifest = {"schema": 1, "files": {"input.txt": _hash.sha256_bytes((repo / "input.txt").read_bytes()),
                                       "other.txt": _hash.sha256_bytes((repo / "other.txt").read_bytes())}}
    (repo / "evidence").mkdir()
    (repo / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    git("add", "--", ".")
    git("commit", "-qm", "Protected manifest at target")
    checkout.meta.update(
        target_commit=git("rev-parse", "HEAD"), input_files=["input.txt", MANIFEST],
        scratch_paths=list(scratch or SCRATCH), experiment=grant(**grant_overrides),
    )
    checkout.grant = checkout.meta["experiment"]
    checkout.prompt_text = assignment_text(checkout.meta, extra_sections=AUTHORIZATION)
    return checkout


def prepared_experiment(checkout, **child_kwargs) -> SimpleNamespace:
    """Commit the granted prompt, prepare, and construct the child in the worktree as an auditor would."""
    revision = checkout.prompt_commit(text=checkout.prompt_text)
    prepared = prepare(checkout.ws, revision)
    session = Path(prepared["session"])
    worktree = Path(prepared["worktree"])
    script = worktree / checkout.grant["script"]
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(child_source(**child_kwargs), encoding="utf-8")
    for frozen in checkout.grant["freeze"]:
        (worktree / frozen).parent.mkdir(parents=True, exist_ok=True)
        (worktree / frozen).write_text("Ordinary agree; the planted control disagrees; r1 is refused.\n")
    return SimpleNamespace(prepared=prepared, session=session, worktree=worktree, script=script, revision=revision)
