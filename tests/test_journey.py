"""The continuation journey through the installed wheel's public interfaces.

A fresh process per command, started from the original checkout with only the
repository and the shipped guidance, discovers the recorded audits, selects one
by a kept reference, continues it through review, retention, export and close,
recovers an interrupted keyed close from its saved key, and retires the shared
managed worktree, branch and temporary directory only once the last audit that
uses them has closed. Another audit, the shared runtime, unrelated branches and
files, retained bytes, enrolled external resources and closed history survive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, StewartError
import stewart_support as support
from stewart_support import assignment_text, snapshot_tree

pytestmark = [pytest.mark.system, pytest.mark.heavy]

OUTER = "audits/ws"
NESTED = "audits/ws/nested"
OTHER = "audits/other"
IDENT = "review-one"


class Stewart:
    """One fresh isolated process per call, from the installed wheel; each returns its JSON envelope."""

    def __init__(self, run_cmd, cwd: Path):
        self.run_cmd, self.cwd = run_cmd, cwd

    def __call__(self, *argv: str, cwd: Path | None = None, allowed=(EXIT_OK,), prose: bool = False):
        command = [sys.executable, "-I", "-B", "-m", "stewart", *([] if prose else ["--json"]), *map(str, argv)]
        result = self.run_cmd(command, cwd=cwd or self.cwd)
        assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
        if prose:
            return result
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "stewart.result/3" and envelope["exit_code"] == result.returncode
        return envelope


def _git(run_cmd, cwd: Path, *argv: str) -> str:
    return run_cmd(["git", *argv], cwd=cwd, check=True).stdout.strip()


def _workspace_files(root: Path, rel: str) -> None:
    folder = root / rel
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "AUDITOR.md").write_text("Auditor instructions\n")
    (folder / "MAINTAINER.md").write_text("Maintainer instructions\n")
    (folder / "PROMPT.md").write_text("**UNASSIGNED**\n")


def _assign(run_cmd, checkout: Path, rel: str, meta: dict) -> str:
    """Author the drafted prompt's sections and commit it alone."""
    (checkout / rel / "PROMPT.md").write_text(assignment_text(meta))
    _git(run_cmd, checkout, "add", "--", f"{rel}/PROMPT.md")
    _git(run_cmd, checkout, "commit", "-qm", f"Assign {rel}")
    return _git(run_cmd, checkout, "rev-parse", "HEAD")


def test_continue_select_recover_and_retire_from_the_original_checkout(tmp_path, run_cmd, monkeypatch):
    origin = (tmp_path / "original").resolve()
    origin.mkdir()
    git = lambda *argv, cwd=origin: _git(run_cmd, cwd, *argv)  # noqa: E731
    git("init", "-q", "-b", "main")
    (origin / ".gitignore").write_text(".scratch/\n")
    (origin / "input.txt").write_text("committed input\n")
    (origin / "unrelated.txt").write_text("unrelated work\n")
    _workspace_files(origin, OUTER)
    _workspace_files(origin, NESTED)
    _workspace_files(origin, OTHER)
    git("add", "--", ".")
    git("commit", "-qm", "Two workspaces, one nested in the other")
    git("branch", "topic")
    target = git("rev-parse", "HEAD")
    stewart = Stewart(run_cmd, origin)
    outer = ["--repo", origin, "--workspace", OUTER]
    nested = ["--repo", origin, "--workspace", NESTED]
    manager_tree, borrowed_tree = tmp_path / "manager-tree", tmp_path / "borrowed-tree"
    scratch_dir, external = tmp_path / "scratch-dir", tmp_path / "external-dir"
    external.mkdir()
    (external / "kept.txt").write_text("created outside Stewart\n")

    # Never-recorded workspaces are absent; init's preview writes nothing.
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    assert stewart("--repo", origin, "discover")["result"]["audits"] == []
    before = snapshot_tree(origin)
    stewart(*outer, "init", "--audit-id", IDENT, "--input", "input.txt")
    assert snapshot_tree(origin) == before and not (common / "stewart/audits").exists()

    # Managed resources are created in a recorded audit context before their side effects.
    created = stewart(*outer, "resource", "create-worktree", "--audit-id", IDENT, "--path", manager_tree,
                      "--branch", "audit/shared", "--actor", "manager")["result"]
    worktree_rid = next(item["rid"] for item in created["resources"] if item["kind"] == "worktree")
    branch_rid = next(item["rid"] for item in created["resources"] if item["kind"] == "branch")
    borrowed_rid = stewart(*nested, "resource", "create-worktree", "--audit-id", IDENT, "--path", borrowed_tree,
                           "--existing-branch", "topic", "--actor", "manager")["result"]["resources"][0]["rid"]
    directory_rid = stewart(*outer, "resource", "create-directory", "--audit-id", IDENT, "--path", scratch_dir,
                            "--actor", "manager")["result"]["rid"]
    stewart(*nested, "resource", "associate", "--audit-id", IDENT, "--resource", directory_rid, "--actor", "manager")
    enrolled_rid = stewart(*outer, "resource", "enroll", "--audit-id", IDENT, "--kind", "directory", "--path",
                           external, "--actor", "manager")["result"]["rid"]

    # Both audits are drafted in the managed worktree and prepared from it; they share an audit ID.
    tree = ["--repo", manager_tree, "--workspace"]
    stewart(*tree, OUTER, "init", "--audit-id", IDENT, "--input", "input.txt", "--replace-prompt")
    outer_meta = {"audit_id": IDENT, "target_commit": target, "report_path": f"{OUTER}/reports/{IDENT}.md",
                  "input_files": ["input.txt"], "external_sources": []}
    outer_prompt = _assign(run_cmd, manager_tree, OUTER, outer_meta)
    stewart(*tree, NESTED, "init", "--audit-id", IDENT, "--target-commit", outer_prompt, "--input", "input.txt",
            "--replace-prompt")
    nested_meta = {**outer_meta, "target_commit": outer_prompt, "report_path": f"{NESTED}/reports/{IDENT}.md"}
    nested_prompt = _assign(run_cmd, manager_tree, NESTED, nested_meta)
    prepared_outer = stewart(*tree, OUTER, "prepare", "--prompt-commit", outer_prompt)["result"]
    prepared_nested = stewart(*tree, NESTED, "prepare", "--prompt-commit", nested_prompt)["result"]
    for prepared, meta in ((prepared_outer, outer_meta), (prepared_nested, nested_meta)):
        Path(prepared["worktree"], meta["report_path"]).write_text("Identical report bytes.\n")

    # A failed preparation of another audit stays recorded and live throughout.
    import stewart.prepare as prepare_module
    from stewart.workspace import workspace
    failed_meta = {**outer_meta, "audit_id": "other-question", "report_path": f"{OTHER}/reports/other-question.md"}
    failed_prompt = _assign(run_cmd, origin, OTHER, failed_meta)
    real_git = prepare_module.git

    def denied(repo, *args, **kwargs):
        if args[:2] == ("worktree", "add"):
            raise StewartError("synthetic Git administration denial", reason="git_failed")
        return real_git(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(prepare_module, "git", denied)
        with pytest.raises(StewartError):
            prepare_module.prepare(workspace(origin, OTHER), failed_prompt)

    # Two keys produce two collections of identical report bytes; the same key returns the same one.
    first = stewart(*tree, OUTER, "--request-key", "collect-a1", "collect", "--audit-id", IDENT,
                    "--auditor-stopped", "finished", allowed=(1,))["result"]
    second = stewart(*tree, OUTER, "--request-key", "collect-a2", "collect", "--audit-id", IDENT,
                     "--auditor-stopped", "finished", allowed=(1,))["result"]
    assert first["collection"] != second["collection"]
    assert first["receipt"]["report_sha256"] == second["receipt"]["report_sha256"]
    assert first["collection_sha256"] != second["collection_sha256"]
    collections = Path(prepared_outer["session"]) / "collections"
    count = len(list(collections.iterdir()))
    replay = stewart(*tree, OUTER, "--request-key", "collect-a1", "collect", "--audit-id", IDENT,
                     "--auditor-stopped", "finished", allowed=(1,))["result"]
    assert replay["schema"] == "stewart.request/1" and replay["state"] == "completed" and replay["replayed"]
    assert replay["outputs"][0]["name"] == first["collection"] and len(list(collections.iterdir())) == count
    conflict = stewart(*tree, OUTER, "--request-key", "collect-a1", "collect", "--audit-id", IDENT,
                       "--auditor-stopped", "interrupted", allowed=(EXIT_REFUSED,))
    assert conflict["error"]["reason"] == "request_key_conflict"
    stewart(*tree, NESTED, "collect", "--audit-id", IDENT, "--auditor-stopped", "finished", allowed=(1,))

    # A fresh process from the original checkout discovers and selects; doing so writes nothing.
    private = snapshot_tree(common / "stewart")
    trees = {path: snapshot_tree(path) for path in (origin, manager_tree)}
    found = stewart("--repo", origin, "discover", allowed=(EXIT_OK, 1))["result"]
    keys = {(entry["workspace"], entry["audit_id"]): entry for entry in found["audits"]}
    assert keys[(OUTER, IDENT)]["stage"] == "prepared" and keys[(NESTED, IDENT)]["stage"] == "prepared"
    assert keys[(OTHER, "other-question")]["stage"] == "preparation_failed"
    assert keys[(OUTER, IDENT)]["shares_audit_id_with"] == [NESTED]
    assert keys[(OUTER, IDENT)]["checkout"] == str(manager_tree)
    ambiguous = stewart("--repo", origin, "select", "--audit-id", IDENT, allowed=(EXIT_REFUSED,))
    assert ambiguous["error"]["reason"] == "selection_ambiguous"
    reference_outer = tmp_path / "outer-ref.json"
    reference_outer.write_text(stewart("--repo", origin, "--workspace", OUTER, "select", "--audit-id", IDENT,
                                       prose=True).stdout)
    reference_nested = tmp_path / "nested-ref.json"
    reference_nested.write_text(stewart("--repo", origin, "--workspace", NESTED, "select", "--audit-id", IDENT,
                                        prose=True).stdout)
    assert snapshot_tree(common / "stewart") == private, "discovery and selection write no record"
    assert {path: snapshot_tree(path) for path in trees} == trees
    held_outer = json.loads(reference_outer.read_text())
    assert held_outer["lifetime"] == prepared_outer["session_uuid"] and held_outer["checkout"] == str(manager_tree)
    assert json.loads(reference_nested.read_text())["lifetime"] == prepared_nested["session_uuid"]

    # Continue with an explicitly supplied review, consuming status's own action argv.
    ref = ["--ref", reference_outer]
    view = stewart(*ref, "status", allowed=(1,))["result"]
    assert view["stage"] == "collected" and view["reference"]["lifetime"] == held_outer["lifetime"]
    drafted = next(action for action in view["next_actions"] if action["action"] == "triage-draft"
                   and action["operands"]["collection"] == second["collection"])
    assert drafted["operands"]["collection_sha256"] == second["collection_sha256"]
    assert "--lifetime" in drafted["argv"]
    response = json.loads(run_cmd(drafted["argv"], cwd=origin, check=True).stdout)
    response.update(decision="Retain the report.", custody_gaps={key: "reviewed" for key in response["custody_gaps"]})
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(response))
    triaged = stewart(*ref, "--request-key", "triage-a", "triage", "--collection", second["collection"],
                      "--response", response_file, "--actor", "manager")["result"]
    stewart(*ref, "retain", "--triage", triaged["triage"], "--report")
    durable = tmp_path / "durable-package"
    exported = stewart(*ref, "export", "--collection", second["collection"], "--select", "REPORT.md", "--output",
                       durable, "--actor", "manager")["result"]
    assert Path(exported["manifest"]).is_file() and not exported["package"].startswith(str(manager_tree))
    # The retained report becomes history on the shared branch, which is merged into main.
    _git(run_cmd, manager_tree, "add", "--", outer_meta["report_path"])
    _git(run_cmd, manager_tree, "commit", "-qm", "Retain the reviewed report")
    git("merge", "-q", "--no-edit", "audit/shared")

    # The plan explains every resource and writes nothing.
    private = snapshot_tree(common / "stewart")
    plan = stewart(*ref, "close", "--plan")["result"]
    assert snapshot_tree(common / "stewart") == private
    dispositions = {item["rid"]: item["disposition"] for item in plan["resources"]}
    assert dispositions[worktree_rid] == dispositions[branch_rid] == dispositions[directory_rid] == "shared"
    assert dispositions[enrolled_rid] == "manual" and plan["audit"]["refusal"] is None

    # Interrupt a keyed close after its record and before removal; lose the response; recover by the key.
    import stewart.close as close_module
    from stewart.audits import bind, load_reference
    bound = bind(load_reference(reference_outer))
    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", lambda parent, name: (_ for _ in ()).throw(
            KeyboardInterrupt("synthetic interruption")))
        with pytest.raises(KeyboardInterrupt):
            close_module.close(bound.ws, IDENT, actor="manager", lifetime=bound.lifetime, request_key="close-a")
    pending = stewart(*ref, "--request-key", "close-a", "close", "--actor", "manager", allowed=(1,))["result"]
    assert pending["state"] == "partial" and pending["replayed"], "an uncertain close is not silently replayed"
    assert Path(prepared_outer["worktree"]).is_dir()
    resumed = stewart(*ref, "--request-key", "close-a", "--resume-request", "close", "--actor", "manager")["result"]
    assert resumed["closed"] and not Path(prepared_outer["worktree"]).exists()
    left = {item["rid"]: item["disposition"] for item in stewart(*ref, "close", "--plan")["result"]["resources"]}
    assert left[worktree_rid] == "shared" and manager_tree.is_dir() and scratch_dir.is_dir()

    # Observation from another directory stays bound to its reference.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    closed_view = stewart(*ref, "status", cwd=elsewhere)["result"]
    assert closed_view["schema"] == "stewart.status-closed/2"
    assert {item["rid"]: item["disposition"] for item in closed_view["resources"]}[worktree_rid] == "shared"
    nested_view = stewart("--ref", reference_nested, "status", cwd=elsewhere, allowed=(1,))["result"]
    assert nested_view["reference"]["lifetime"] == prepared_nested["session_uuid"]

    # The last user closes: the shared worktree, its branch and the directory retire; the rest survives.
    nested_collection = nested_view["collections"][-1]["name"]
    drafted = stewart("--ref", reference_nested, "triage-draft", "--collection", nested_collection)["result"]
    nested_response = drafted["response"]
    nested_response.update(decision="No action.", custody_gaps={key: "reviewed" for key in
                                                                 nested_response["custody_gaps"]})
    response_file.write_text(json.dumps(nested_response))
    stewart("--ref", reference_nested, "triage", "--collection", nested_collection, "--response", response_file,
            "--actor", "manager")
    runtime = Path(os.environ["STEWART_MANAGER_HOME"])
    runtime_before = snapshot_tree(runtime / "deployments")
    closed = stewart("--ref", reference_nested, "--request-key", "close-b", "close", "--actor", "manager")["result"]
    outcomes = {item["rid"]: item["outcome"] for item in closed["resources"]}
    assert outcomes == {worktree_rid: "removed", branch_rid: "removed", directory_rid: "removed",
                        borrowed_rid: "removed"}
    assert not manager_tree.exists() and not borrowed_tree.exists() and not scratch_dir.exists()
    assert git("for-each-ref", "--format=%(refname)", "refs/heads/") == "refs/heads/main\nrefs/heads/topic"
    assert (external / "kept.txt").read_text() == "created outside Stewart\n"
    assert (origin / "unrelated.txt").read_text() == "unrelated work\n"
    assert (origin / outer_meta["report_path"]).read_text() == "Identical report bytes.\n"
    assert Path(exported["manifest"]).is_file()
    assert snapshot_tree(runtime / "deployments") == runtime_before, "the shared runtime survives"
    survivor = stewart("--repo", origin, "--workspace", OTHER, "status", "--audit-id", "other-question",
                       allowed=(1,))["result"]
    assert survivor["preparation"]["state"] == "failed"
    history = stewart("--repo", origin, "discover", allowed=(EXIT_OK, 1))["result"]
    remaining = {item["rid"]: item for item in history["resources"]}
    assert remaining[enrolled_rid]["disposition"] == "manual"
    assert remaining[worktree_rid]["disposition"] == "retired"
    assert any(item["disposition"] == "retained" for item in history["resources"]), "the export is deliberate retention"
    assert {item["key"] for item in history["requests"]} >= {"collect-a1", "collect-a2", "triage-a", "close-a",
                                                             "close-b"}

    # Manual retirement is acknowledged, never inferred.
    refused = stewart("--repo", origin, "resource", "acknowledge", "--resource", enrolled_rid, "--actor", "manager",
                      allowed=(EXIT_REFUSED,))
    assert refused["error"]["reason"] == "resource_present"
    shutil.rmtree(external)
    missing = stewart("--repo", origin, "resource", "show", "--resource", enrolled_rid, allowed=(1,))["result"]
    assert missing["disposition"] == "missing"
    stewart("--repo", origin, "resource", "acknowledge", "--resource", enrolled_rid, "--actor", "manager",
            "--note", "removed by hand")
    shown = stewart("--repo", origin, "resource", "show", "--resource", enrolled_rid)["result"]
    assert shown["disposition"] == "acknowledged"
    assert shown["acknowledged"]["observed_at_acknowledgment"]["state"] == "absent"
    assert shown["acknowledged"]["acknowledged"]["actor"] == "manager"

    # A retry after closeout reports the historical request and recreates nothing. The checkout the
    # key was submitted from was retired with the managed worktree; the key resolves from any checkout.
    gone = stewart(*ref, "status", allowed=(EXIT_REFUSED,))
    assert gone["error"]["reason"] == "reference_checkout_missing"
    after = stewart(*outer, "--request-key", "collect-a1", "collect", "--audit-id", IDENT, "--auditor-stopped",
                    "finished", allowed=(1,))["result"]
    rebound = stewart("--repo", origin, *ref, "--request-key", "collect-a1", "collect", "--auditor-stopped",
                      "finished", allowed=(EXIT_REFUSED,))
    assert rebound["error"]["reason"] == "request_key_conflict", "a lifetime-bound retry is different work"
    assert after["state"] == "completed" and [item["availability"] for item in after["outputs"]] == ["retired"]
    assert not Path(prepared_outer["session"]).exists()

    # Losing the reference too: rediscover and select again.
    reselected = stewart("--repo", origin, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]
    assert reselected["stage"] == "closed" and reselected["reference"]["lifetime"] is None
