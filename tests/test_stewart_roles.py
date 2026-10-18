"""Audit roles select guidance independently of harness entry files and profiles.

The controls vary role-file presence while keeping harness files, then vary
harness/model choices while keeping the role policy. They establish the files
required and handed off, not that a real agent read or followed instructions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stewart.assignment import initialize
from stewart._bootstrap import StewartError
from stewart.prepare import prepare
from stewart.status import status

pytestmark = pytest.mark.system


@pytest.mark.parametrize("harness,model,entry_files", [
    ("first-harness", "first-model", ()),
    ("second-harness", "first-model", ()),
    ("first-harness", "second-model", ()),
    ("first-harness", "first-model", ("AGENTS.md", "CLAUDE.md")),
])
def test_role_guidance_is_explicit_and_independent_of_launch_choices(checkout, harness, model, entry_files):
    repo, ws, git = checkout.repo, checkout.ws, checkout.git
    assert ws.auditor_guidance == f"{ws.rel}/AUDITOR.md", "auditor policy is selected by role"
    assert ws.maintainer_guidance == f"{ws.rel}/MAINTAINER.md", "the same harness can serve the maintainer role"
    role_bytes = {"AUDITOR.md": b"Only inspect and report within the assignment.\n",
                  "MAINTAINER.md": b"Prepare the assignment and disposition captured evidence.\n"}
    for name, data in role_bytes.items():
        (repo / ws.rel / name).write_bytes(data)
    for name in entry_files:
        (repo / ws.rel / name).write_text("Harness entry text cannot select a Stewart role.\n")
    profile = {"schema": "stewart.launch-profile/2", "scope_adapter": "claude-code-restricted/1", "harness": harness, "model": model,
               "effort": "test", "actor": "manager", "command": [harness, "--model", "{model}", "{prompt}"]}
    (repo / ws.rel / "LAUNCH-PROFILE.json").write_text(json.dumps(profile))
    git("add", "--", ws.rel)
    git("commit", "-qm", "Role policy and launch choices")
    checkout.meta["target_commit"] = git("rev-parse", "HEAD")
    preview = initialize(ws, "preview-question", "HEAD", inputs=["input.txt"])
    assert preview["written"] is None, "explicit role files suffice even without either harness entry file"
    revision = checkout.prompt_commit()
    # The pinned role policy must survive unrelated edits in the manager checkout.
    for name in role_bytes:
        (repo / ws.rel / name).write_text("Uncommitted replacement policy.\n")
    prepared = prepare(ws, revision)
    worktree = Path(prepared["worktree"])
    for name, data in role_bytes.items():
        assert (worktree / ws.rel / name).read_bytes() == data, "guidance comes from the prompt commit"
    launch = Path(prepared["launch"]).read_text()
    assert "You are the auditor for this assignment." in launch, "the handoff assigns the role explicitly"
    assert f"Read `{ws.rel}/AUDITOR.md` first, then `{ws.prompt}`." in launch
    assert "MAINTAINER.md" not in launch and "CLAUDE.md" not in launch and "AGENTS.md" not in launch, (
        "an auditor handoff must select auditor policy, independently of harness filenames")
    view = status(ws, checkout.meta["audit_id"])
    handoff = next(action for action in view["next_actions"] if action["action"] == "handoff")
    assert handoff["launch"] == prepared["launch"] and handoff["command"] == prepared["launch_command"]
    assert view["launch_profile"]["harness"] == harness and view["launch_profile"]["model"] == model


@pytest.mark.parametrize("role_file", ["AUDITOR.md", "MAINTAINER.md"])
def test_harness_entry_files_cannot_substitute_for_missing_role_policy(checkout, role_file):
    repo, ws, git = checkout.repo, checkout.ws, checkout.git
    role = repo / ws.rel / role_file
    original = role.read_bytes()
    role.unlink()
    # Both legacy filenames exist. Neither can satisfy either missing role.
    for name in ("AGENTS.md", "CLAUDE.md"):
        (repo / ws.rel / name).write_text("Legacy instructions.\n")
    git("add", "-A", "--", ws.rel)
    git("commit", "-qm", "Missing role policy with both harness entries present")
    checkout.meta["target_commit"] = git("rev-parse", "HEAD")
    revision = checkout.prompt_commit()
    with pytest.raises(StewartError) as init_error:
        initialize(ws, "preview-question", "HEAD", inputs=["input.txt"])
    assert init_error.value.reason == "workspace_guidance" and role_file in str(init_error.value)
    # Restoring only the working copy cannot repair the committed launch contract.
    role.write_bytes(original)
    initialize(ws, "preview-question", "HEAD", inputs=["input.txt"])
    with pytest.raises(StewartError) as prepare_error:
        prepare(ws, revision)
    assert prepare_error.value.reason == "workspace_guidance" and role_file in str(prepare_error.value)
    assert not (repo / ".git/stewart").exists(), "missing committed guidance refuses before allocating a session"
    git("add", "--", f"{ws.rel}/{role_file}")
    git("commit", "-qm", "Restore explicit role policy")
    checkout.meta["audit_id"] = "restored-question"
    checkout.meta["report_path"] = ws.report_path("restored-question")
    assert Path(prepare(ws, checkout.prompt_commit())["launch"]).is_file(), (
        "restoring only the missing role file makes preparation possible")
