"""Characterize Git trust boundaries; baseline behavior is not the desired contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import sys

import pytest

from stewart._git import git
from stewart.assignment import expected_inputs
from stewart.coverage import prompt_identities
from stewart.prepare import prepare
import stewart_support as support

pytestmark = pytest.mark.system


def _save(directory, name, value):
    (directory / f"{name}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


@pytest.mark.parametrize("selection", ["matched", "unmatched", "unset"])
def test_custody_git_prepare_filter_execution(tmp_path, run_cmd, selection):
    """A harmless configured smudge writes only a fixture marker and preserves bytes."""
    checkout = support.make_checkout(tmp_path, run_cmd, ws_rel="nested/audit/work", name="subject")
    pattern = "input.txt"
    # Only input.txt is assigned, but Git checks out the complete tree. For the
    # invariance case use a path absent from that tree, not another tracked file.
    if selection == "unmatched":
        pattern = "absent.txt"
    (checkout.repo / ".gitattributes").write_text(f"{pattern} filter=custody-probe\n")
    checkout.git("add", ".gitattributes")
    checkout.git("commit", "-qm", "Filter attribute fixture")
    checkout.meta["target_commit"] = checkout.git("rev-parse", "HEAD")
    revision = checkout.prompt_commit()
    marker = tmp_path / "filter-invoked.txt"
    probe = tmp_path / "filter_probe.py"
    probe.write_text("from pathlib import Path\nimport sys\n"
                     "Path(sys.argv[1]).write_text('configured filter invoked\\n')\n"
                     "sys.stdout.buffer.write(sys.stdin.buffer.read())\n")
    if selection != "unset":
        checkout.git("config", "filter.custody-probe.clean", "cat")
        checkout.git("config", "filter.custody-probe.smudge",
                     shlex.join([sys.executable, "-I", "-B", str(probe), str(marker)]))
        checkout.git("config", "filter.custody-probe.required", "true")
    assert not marker.exists()
    prepared = prepare(checkout.ws, revision, mode="snapshot",
                       checkout_home_path=tmp_path / "audit checkouts")
    worktree = Path(prepared["worktree"])
    observed = {"selection": selection, "filter_invoked": marker.exists(),
                "prepared": prepared, "input_bytes_unchanged":
                (worktree / "input.txt").read_bytes() == (checkout.repo / "input.txt").read_bytes()}
    _save(tmp_path, "git-filter-observation", observed)
    assert observed["filter_invoked"] == (selection == "matched")
    assert observed["input_bytes_unchanged"]


def test_custody_git_replacement_views(checkout, tmp_path):
    """Input pin construction and capture coverage currently use different Git views."""
    revision = checkout.prompt_commit()
    from stewart.assignment import assignment_metadata
    meta = assignment_metadata(checkout.meta, checkout.ws)
    original = expected_inputs(checkout.repo, meta, revision)
    unchanged = expected_inputs(checkout.repo, meta, revision)
    assert original == unchanged
    raw = (checkout.repo / "input.txt").read_bytes()
    original_oid = checkout.git("rev-parse", f"{revision}:input.txt")
    replacement = b"replacement object bytes\n"
    replacement_oid = git(checkout.repo, "hash-object", "-w", "--stdin", input=replacement).stdout.decode().strip()
    checkout.git("replace", original_oid, replacement_oid)
    replaced = expected_inputs(checkout.repo, meta, revision)
    coverage = prompt_identities(checkout.repo, revision, {"input.txt"})
    _save(tmp_path, "git-replacement-observation", {
        "revision": revision, "before": original, "with_replacement": replaced,
        "coverage": coverage, "live_input_sha256": hashlib.sha256(raw).hexdigest(),
        "replacement_sha256": hashlib.sha256(replacement).hexdigest(),
    })
    assert original[0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert replaced[0]["sha256"] == hashlib.sha256(replacement).hexdigest()
    assert coverage["input.txt"] == ("file", original[0]["sha256"])
    checkout.git("replace", "-d", original_oid)
    assert expected_inputs(checkout.repo, meta, revision) == original
