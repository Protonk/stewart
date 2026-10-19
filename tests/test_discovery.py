"""Discovery, drafts, registration and selection references through the installed wheel.

An audit exists for Stewart only once a record names it: a mutating ``init``
(start record before its writes, outcome after), an explicit registration of a
named workspace, a session, a closing record, a role row or a resource context.
Discovery and selection read those records and write nothing; a selection is a
reference the caller keeps, and every use revalidates it against the records
as they are now. Each guarantee below has a firing control (the condition
happened), a case differing only in the measured property, and an invariance
case. Measured commands run in a fresh isolated process from the installed
wheel; setup that needs an injected failure runs in process.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pathlib
import stat
import sys
import uuid

import pytest

from stewart import _util
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart.api import close, initialize, prepare, workspace
import stewart_support as support
from stewart_support import assignment_text, read_json, snapshot_tree

pytestmark = pytest.mark.system

OUTER = support.WS
NESTED = f"{support.WS}/nested"
OTHER = "reviews/other"
IDENT = "draft-question"
SHARED = "shared-question"


class Stewart:
    """One fresh isolated process per call, from the installed wheel; each returns its JSON envelope."""

    def __init__(self, run_cmd, cwd: Path):
        self.run_cmd, self.cwd = run_cmd, cwd

    def __call__(self, *argv, allowed=(EXIT_OK,), cwd: Path | None = None) -> dict:
        command = [sys.executable, "-I", "-B", "-m", "stewart", "--json", *map(str, argv)]
        result = self.run_cmd(command, cwd=cwd or self.cwd)
        assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "stewart.result/3" and envelope["exit_code"] == result.returncode
        return envelope

    def refused(self, *argv, reason: str, code: int = EXIT_REFUSED) -> dict:
        envelope = self(*argv, allowed=(code,))
        assert envelope["error"]["reason"] == reason, envelope["error"]
        return envelope["error"]


def _sha(data: bytes) -> str:
    return _util.sha256_bytes(data)


def _common(checkout) -> Path:
    return Path(checkout.git("rev-parse", "--path-format=absolute", "--git-common-dir"))


def _storage(common: Path) -> dict | None:
    root = common / "stewart"
    return snapshot_tree(root) if root.exists() else None


def _add_workspaces(checkout, *rels: str) -> None:
    """More committed workspaces beside the fixture's; none of them is recorded by being created."""
    for rel in rels:
        folder = checkout.repo / rel
        folder.mkdir(parents=True)
        (folder / "AUDITOR.md").write_text("Auditor instructions\n", encoding="utf-8")
        (folder / "MAINTAINER.md").write_text("Maintainer instructions\n", encoding="utf-8")
        (folder / "PROMPT.md").write_text("**UNASSIGNED**\n", encoding="utf-8")
    checkout.git("add", "--", *rels)
    checkout.git("commit", "-qm", "More workspaces")


def _linked(checkout, name: str) -> Path:
    """A linked maintainer worktree of the fixture repository, outside it."""
    path = (checkout.tmp / name).resolve()
    checkout.git("worktree", "add", "-q", "-b", f"maintainer/{name}", str(path))
    return path


def _remove_linked(checkout, path: Path) -> None:
    checkout.git("worktree", "remove", "--force", str(path))
    assert not path.exists(), "firing control: the maintainer checkout is gone"


def _meta(root: Path, rel: str, ident: str, target: str) -> dict:
    ws = workspace(root, rel)
    return {"audit_id": ident, "target_commit": target, "report_path": ws.report_path(ident),
            "input_files": ["input.txt"], "external_sources": []}


def _assign(checkout, root: Path, rel: str, ident: str) -> str:
    """Author a complete prompt naming ``ident`` in ``root`` and commit it alone; return the prompt commit."""
    target = checkout.git("rev-parse", "HEAD", cwd=root)
    ws = workspace(root, rel)
    (root / ws.prompt).write_text(assignment_text(_meta(root, rel, ident, target)), encoding="utf-8")
    checkout.git("add", "--", ws.prompt, cwd=root)
    checkout.git("commit", "-qm", f"Assign {ident}", cwd=root)
    return checkout.git("rev-parse", "HEAD", cwd=root)


def _init(cli: Stewart, root: Path, rel: str, ident: str, *extra) -> dict:
    return cli("--repo", root, "--workspace", rel, "init", "--audit-id", ident, "--input", "input.txt",
               "--replace-prompt", *extra)["result"]


def _failed_prepare(monkeypatch, ws, revision: str) -> None:
    """A preparation that fails at Git worktree administration, preserving its session as prepare does."""
    import stewart.prepare as prepare_module
    real = prepare_module.git

    def denied(repo, *args, **kwargs):
        if args[:2] == ("worktree", "add"):
            raise StewartError("synthetic Git administration denial", reason="git_failed")
        return real(repo, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(prepare_module, "git", denied)
        with pytest.raises(StewartError) as refused:
            prepare_module.prepare(ws, revision)
    assert refused.value.reason == "prepare_failed", "firing control: the preparation failed"


def _interrupted_init(monkeypatch, ws, ident: str) -> None:
    """Stop a mutating init after its start record and before its prompt write, as a signal would."""
    prompt = ws.repo / ws.prompt
    before = prompt.read_bytes()
    real = pathlib.Path.write_text

    def interrupted(self, *args, **kwargs):
        if self == prompt:
            raise KeyboardInterrupt("synthetic interruption between the start record and the prompt write")
        return real(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "write_text", interrupted)
        with pytest.raises(KeyboardInterrupt):
            initialize(ws, ident, "HEAD", inputs=["input.txt"], replace_prompt=True)
    assert prompt.read_bytes() == before, "firing control: the interruption came before the prompt write"


def _entries(found: dict) -> dict:
    return {(entry["workspace"], entry["audit_id"]): entry for entry in found["audits"]}


def _located(found: dict) -> dict:
    """Entries by storage location; a record that cannot establish its workspace is still located."""
    return {(entry["slug"], entry["audit_id"]): entry for entry in found["audits"]}


class ReadOnly:
    """Run read-only commands and prove each one left the observed trees byte-identical."""

    def __init__(self, cli: Stewart, *roots: Path):
        self.cli = cli
        self.roots = [*roots, Path(os.environ["HOME"]), Path(os.environ["STEWART_MANAGER_HOME"])]
        # The source launcher deploys the installed package into the manager home at its first
        # startup, whatever the command; that code cache is not a record of any audit. Warm it with
        # a command that needs no repository, so every measured command starts from it.
        cli("docs", "agents")

    def _snapshot(self) -> dict:
        return {root: snapshot_tree(root) if root.exists() else None for root in self.roots}

    def __call__(self, *argv, **kwargs) -> dict:
        before = self._snapshot()
        envelope = self.cli(*argv, **kwargs)
        assert self._snapshot() == before, f"{argv} wrote something"
        return envelope

    def refused(self, *argv, **kwargs) -> dict:
        before = self._snapshot()
        error = self.cli.refused(*argv, **kwargs)
        assert self._snapshot() == before, f"{argv} wrote something"
        return error


# --- 1. drafts: preview, start/outcome records, interruption, absence ---------------------------------


def test_preview_writes_nothing_and_an_unrecorded_workspace_is_absent(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    _add_workspaces(checkout, OTHER)
    repo, common = checkout.repo, _common(checkout)
    look = ReadOnly(cli, repo)
    # Firing control: both workspaces exist with every guidance file, yet no record names either one.
    for rel in (OUTER, OTHER):
        assert all((repo / name).is_file() for name in workspace(repo, rel).guidance_files())
    found = look("--repo", repo, "discover")["result"]
    assert found["audits"] == [] and found["exit_code"] == EXIT_OK
    look.refused("--repo", repo, "--workspace", OUTER, "select", "--audit-id", IDENT, reason="selection_missing")
    assert _storage(common) is None, "nothing has created Stewart's repository storage yet"

    tree = snapshot_tree(repo)
    preview = cli("--repo", repo, "--workspace", OUTER, "init", "--audit-id", IDENT, "--input", "input.txt")["result"]
    assert preview["written"] is None and preview["draft_record"] is None and IDENT in preview["draft"]
    assert snapshot_tree(repo) == tree and _storage(common) is None, "a preview writes nothing"
    assert look("--repo", repo, "discover")["result"]["audits"] == [], "a preview records no draft"

    # Changed property: the same init with --replace-prompt records the audit.
    _init(cli, repo, OUTER, IDENT)
    assert snapshot_tree(repo) != tree and _storage(common), "firing control: the snapshots see a mutation"
    found = look("--repo", repo, "discover")["result"]
    assert [(entry["workspace"], entry["audit_id"], entry["stage"]) for entry in found["audits"]] == [
        (OUTER, IDENT, "draft")]
    # Invariance: the other workspace, never recorded, stays absent from discovery and status.
    assert all(entry["slug"] != workspace(repo, OTHER).slug for entry in found["audits"])
    cli.refused("--repo", repo, "--workspace", OTHER, "status", "--audit-id", IDENT, reason="session_missing")
    look.refused("--repo", repo, "--workspace", OTHER, "select", "--audit-id", IDENT, reason="selection_missing")


def test_replace_prompt_records_its_intended_writes_then_their_outcome(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws, common = checkout.repo, checkout.ws, _common(checkout)
    before = (repo / ws.prompt).read_bytes()
    manifest_rel = "inventory/inputs.json"
    result = _init(cli, repo, ws.rel, IDENT, "--input-manifest", manifest_rel)

    record = Path(result["draft_record"])
    assert record.parent == common / "stewart/audits" / ws.slug / IDENT / "init"
    started_bytes = (record / "STARTED.json").read_bytes()
    started, outcome = json.loads(started_bytes), read_json(record / "OUTCOME.json")
    prompt, manifest = (repo / ws.prompt).read_bytes(), (repo / manifest_rel).read_bytes()
    assert prompt.decode() == result["draft"]
    assert (started["schema"], started["kind"], started["phase"]) == ("stewart.draft/1", "init", "started")
    assert {item["role"]: (item["path"], item["sha256"]) for item in started["intended"]} == {
        "prompt": (ws.prompt, _sha(prompt)), "input_manifest": (manifest_rel, _sha(manifest))}
    assert started["prompt_before"] == {"kind": "file", "sha256": _sha(before)}
    assert started["context"] == {"workspace": ws.rel, "slug": ws.slug, "audit_id": IDENT, "lifetime": None,
                                  "closed_before": []}
    assert started["checkout"] == str(repo)
    assert (outcome["phase"], outcome["status"], outcome["error"]) == ("outcome", "completed", None)
    assert outcome["started_sha256"] == _sha(started_bytes), "the outcome binds the start record it follows"
    assert {item["role"]: item["sha256"] for item in outcome["written"]} == {
        "prompt": _sha(prompt), "input_manifest": _sha(manifest)}
    assert started["recorded_at"] <= outcome["recorded_at"]

    view = cli("--repo", repo, "--workspace", ws.rel, "status", "--audit-id", IDENT)["result"]
    assert view["schema"] == "stewart.status-draft/1" and view["attention"] == [] and view["exit_code"] == EXIT_OK
    assert {item["path"]: item["state"] for item in view["drafts"][0]["files"]} == {
        ws.prompt: "unchanged", manifest_rel: "unchanged"}
    # Changed property: authoring the prompt changes its observation now, never the record.
    record_bytes = {name: (record / name).read_bytes() for name in ("STARTED.json", "OUTCOME.json")}
    (repo / ws.prompt).write_text(assignment_text(_meta(repo, ws.rel, IDENT, started["target_commit"])))
    view = cli("--repo", repo, "--workspace", ws.rel, "status", "--audit-id", IDENT)["result"]
    assert {item["path"]: item["state"] for item in view["drafts"][0]["files"]} == {
        ws.prompt: "changed", manifest_rel: "unchanged"}
    assert {name: (record / name).read_bytes() for name in record_bytes} == record_bytes


def test_an_interrupted_init_keeps_its_start_record_and_reports_draft_incomplete(checkout, run_cmd, monkeypatch):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws, common = checkout.repo, checkout.ws, _common(checkout)
    base = ["--repo", repo, "--workspace", ws.rel]
    _interrupted_init(monkeypatch, ws, IDENT)
    records = common / "stewart/audits" / ws.slug / IDENT / "init"
    [held] = list(records.iterdir())
    assert (held / "STARTED.json").is_file() and not (held / "OUTCOME.json").exists()
    started = (held / "STARTED.json").read_bytes()

    view = cli(*base, "status", "--audit-id", IDENT, allowed=(EXIT_ATTENTION,))["result"]
    assert view["schema"] == "stewart.status-draft/1"
    assert [(item["reason"], item["source"]) for item in view["attention"]] == [("draft_incomplete",
                                                                               f"draft {held.name}")]
    assert [(item["state"], item["written"]) for item in view["drafts"]] == [("partial", [])]
    found = cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    entry = _entries(found)[(ws.rel, IDENT)]
    assert entry["stage"] == "draft" and [item["state"] for item in entry["drafts"]] == ["partial"]

    # Changed property: a completed init of another audit has no incomplete draft.
    initialize(ws, "complete-question", "HEAD", inputs=["input.txt"], replace_prompt=True)
    complete = cli(*base, "status", "--audit-id", "complete-question")["result"]
    assert complete["attention"] == [] and [item["state"] for item in complete["drafts"]] == ["completed"]

    # A retry gets a new record; the interrupted one keeps its bytes and still has no outcome.
    retried = initialize(ws, IDENT, "HEAD", inputs=["input.txt"], replace_prompt=True)
    assert Path(retried["draft_record"]).name != held.name
    assert (held / "STARTED.json").read_bytes() == started and not (held / "OUTCOME.json").exists()
    view = cli(*base, "status", "--audit-id", IDENT, allowed=(EXIT_ATTENTION,))["result"]
    assert sorted(item["state"] for item in view["drafts"]) == ["completed", "partial"]
    assert [item["source"] for item in view["attention"]] == [f"draft {held.name}"]
    # Discovery's exit code agrees with status: an interrupted init is unfinished work (1), not "no news".
    assert cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))["exit_code"] == EXIT_ATTENTION


def test_an_interrupted_redraft_of_a_released_id_is_reported_draft_incomplete(checkout, run_cmd, monkeypatch):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws = checkout.repo, checkout.ws
    base = ["--repo", repo, "--workspace", ws.rel]
    _failed_prepare(monkeypatch, ws, _assign(checkout, repo, ws.rel, IDENT))
    assert close(ws, IDENT, actor="manager", abandon=True, reason="Git administration was denied")["released"]
    released = cli(*base, "status", "--audit-id", IDENT)["result"]
    assert released["audit_id_state"] == "released" and released["attention"] == [], "control: nothing is pending"

    _interrupted_init(monkeypatch, ws, IDENT)
    entry = _entries(cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))["result"])[(ws.rel, IDENT)]
    assert entry["stage"] == "draft" and [item["state"] for item in entry["drafts"]] == ["partial"]
    # Measured: status on a recorded audit with no session reports the interrupted init, as it does
    # for an audit that was never closed (test above), and agrees with discovery's stage.
    view = cli(*base, "status", "--audit-id", IDENT, allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert [item["reason"] for item in view["attention"]] == ["draft_incomplete"], view.get("schema")
    assert view["exit_code"] == EXIT_ATTENTION


# --- 2. registration ----------------------------------------------------------------------------------


def test_register_records_present_observations_of_a_named_workspace(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws, common = checkout.repo, checkout.ws, _common(checkout)
    (repo / ws.prompt).write_text(assignment_text(_meta(repo, ws.rel, IDENT, checkout.meta["target_commit"])))
    assert cli("--repo", repo, "discover")["result"]["audits"] == [], "control: an existing workspace alone is absent"

    result = cli("--repo", repo, "--workspace", ws.rel, "register", "--audit-id", IDENT, "--actor", "manager")["result"]
    location = Path(result["path"])
    assert location.parent == common / "stewart/audits" / ws.slug / IDENT / "registrations"
    data = location.read_bytes()
    record = json.loads(data)
    assert result["sha256"] == _sha(data) and record["schema"] == "stewart.registration/1"
    assert record["actor"] == "manager" and record["checkout"] == str(repo)
    assert record["context"] == {"workspace": ws.rel, "slug": ws.slug, "audit_id": IDENT, "lifetime": None,
                                 "closed_before": []}
    observed = {role: (item["path"], item["sha256"]) for role, item in record["observed"].items() if role != "head"}
    assert observed == {"auditor_guidance": (ws.auditor_guidance, _sha((repo / ws.auditor_guidance).read_bytes())),
                        "maintainer_guidance": (ws.maintainer_guidance,
                                                _sha((repo / ws.maintainer_guidance).read_bytes())),
                        "prompt": (ws.prompt, _sha((repo / ws.prompt).read_bytes()))}
    assert record["observed"]["head"] == checkout.git("rev-parse", "HEAD")
    assert "no earlier custody" in record["note"]

    entry = _entries(cli("--repo", repo, "discover")["result"])[(ws.rel, IDENT)]
    assert entry["stage"] == "draft" and entry["lifetime"] is None and entry["checkout"] == str(repo)
    [draft] = entry["drafts"]
    assert (draft["kind"], draft["state"], draft["actor"]) == ("registration", "completed", "manager")
    assert {item["path"]: item["state"] for item in draft["files"]} == dict.fromkeys(ws.guidance_files(), "unchanged")
    # Changed property: a later edit is observed as a change; the record keeps what was observed then.
    with (repo / ws.prompt).open("a", encoding="utf-8") as handle:
        handle.write("\nEdited after registration.\n")
    [draft] = _entries(cli("--repo", repo, "discover")["result"])[(ws.rel, IDENT)]["drafts"]
    assert {item["path"]: item["state"] for item in draft["files"]} == {
        ws.auditor_guidance: "unchanged", ws.maintainer_guidance: "unchanged", ws.prompt: "changed"}
    assert location.read_bytes() == data


def test_register_refuses_another_id_a_reserved_id_and_an_existing_session(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws, common = checkout.repo, checkout.ws, _common(checkout)
    base = ["--repo", repo, "--workspace", ws.rel]
    records = common / "stewart/audits" / ws.slug

    def register(ident: str, **kwargs):
        return cli(*base, "register", "--audit-id", ident, "--actor", "manager", **kwargs)

    # The unassigned fixture prompt has no block naming any ID.
    cli.refused(*base, "register", "--audit-id", IDENT, "--actor", "manager", reason="assignment_schema")
    # A block naming another ID is refused the same way and records nothing.
    (repo / ws.prompt).write_text(assignment_text(_meta(repo, ws.rel, "other-question",
                                                        checkout.meta["target_commit"])))
    cli.refused(*base, "register", "--audit-id", IDENT, "--actor", "manager", reason="assignment_schema")
    assert not (records / IDENT).exists()
    # Control: the same prompt registers the ID its block names.
    register("other-question")

    # A draft-only abandon keeps the ID reserved; registering it again is refused.
    cli(*base, "close", "--audit-id", "other-question", "--actor", "manager", "--abandon", "--reason",
        "drafted in error", allowed=(EXIT_OK, EXIT_ATTENTION))
    closed = cli(*base, "status", "--audit-id", "other-question")["result"]
    assert closed["audit_id_state"] == "reserved", "firing control: a closing record reserves the ID"
    registrations = sorted((records / "other-question/registrations").iterdir())
    cli.refused(*base, "register", "--audit-id", "other-question", "--actor", "manager", reason="audit_id_reserved")
    assert sorted((records / "other-question/registrations").iterdir()) == registrations

    # An existing session is refused (audit_recorded); before preparation the same ID registered.
    revision = _assign(checkout, repo, ws.rel, "prepared-question")
    register("prepared-question")
    prepared = prepare(ws, revision)
    assert Path(prepared["session"]).is_dir(), "firing control: the session exists"
    error = cli.refused(*base, "register", "--audit-id", "prepared-question", "--actor", "manager",
                        reason="audit_recorded")
    assert error["retained"] == [prepared["session"]]
    assert len(list((records / "prepared-question/registrations").iterdir())) == 1


# --- 3. discovery -------------------------------------------------------------------------------------


@pytest.mark.heavy
def test_discovery_lists_recorded_audits_everywhere_and_keeps_going_past_broken_entries(checkout, run_cmd,
                                                                                        monkeypatch):
    cli = Stewart(run_cmd, checkout.tmp)
    _add_workspaces(checkout, NESTED, OTHER)
    repo, common = checkout.repo, _common(checkout)
    linked = _linked(checkout, "linked")
    look = ReadOnly(cli, repo, linked)
    _init(cli, repo, OUTER, SHARED)
    nested = prepare(workspace(repo, NESTED), _assign(checkout, repo, NESTED, SHARED))
    _init(cli, linked, OTHER, "linked-question")

    def discover(root: Path = repo, code: int = EXIT_OK) -> dict:
        return look("--repo", root, "discover", allowed=(code,))["result"]

    found = discover()
    entries = _entries(found)
    assert set(entries) == {(OUTER, SHARED), (NESTED, SHARED), (OTHER, "linked-question")}
    assert (entries[(OUTER, SHARED)]["stage"], entries[(OUTER, SHARED)]["checkout"]) == ("draft", str(repo))
    prepared_entry = entries[(NESTED, SHARED)]
    assert (prepared_entry["stage"], prepared_entry["lifetime"]) == ("prepared", nested["session_uuid"])
    assert prepared_entry["checkout"] == str(repo) and prepared_entry["checkout_available"] is True
    assert entries[(OTHER, "linked-question")]["draft_checkouts"] == [str(linked)]
    assert entries[(OTHER, "linked-question")]["checkout"] == str(linked)
    assert entries[(OUTER, SHARED)]["shares_audit_id_with"] == [NESTED]
    assert entries[(NESTED, SHARED)]["shares_audit_id_with"] == [OUTER]
    assert entries[(OTHER, "linked-question")]["shares_audit_id_with"] == []
    assert found["problems"] == [] and found["exit_code"] == EXIT_OK
    # Invariance: another maintainer checkout of the repository discovers the same audits.
    assert discover(linked)["audits"] == found["audits"]

    # A failed preparation is unfinished work (1); its released abandon is history (0).
    failing = workspace(repo, OTHER)
    _failed_prepare(monkeypatch, failing, _assign(checkout, repo, OTHER, "failing-question"))
    assert _entries(discover(code=EXIT_ATTENTION))[(OTHER, "failing-question")]["stage"] == "preparation_failed"
    assert close(failing, "failing-question", actor="manager", abandon=True, reason="synthetic denial")["released"]
    healthy = discover()
    assert _entries(healthy)[(OTHER, "failing-question")]["stage"] == "closed"

    def others(result: dict, key: tuple) -> list:
        return [entry for entry in result["audits"] if (entry["workspace"], entry["audit_id"]) != key]

    def rewrite(location: Path, data: bytes) -> bytes:
        original, mode = location.read_bytes(), stat.S_IMODE(location.stat().st_mode)
        location.chmod(mode | stat.S_IWUSR)
        location.write_bytes(data)
        location.chmod(mode)
        return original

    # An unsupported session schema is listed by location and envelope; nothing else is inferred.
    session_record = Path(nested["session"]) / "session.json"
    document = json.loads(session_record.read_bytes())
    original_session = rewrite(session_record, json.dumps({**document, "schema_version": 99}).encode())
    broken = discover(code=EXIT_UNVERIFIED)
    entry = _entries(broken)[(NESTED, SHARED)]
    assert (entry["stage"], entry["lifetime"]) == ("unsupported", None)
    assert entry["session"]["path"] == nested["session"] and entry["session"]["supported"] is False
    assert entry["session"]["envelope"] == {"schema": 99, "workspace": NESTED,
                                            "writer": prepared_entry["implementation"]["recorded"]}
    assert (entry["session"]["uuid"], entry["session"]["stage"], entry["session"]["collections"]) == (None, None, None)
    assert [problem["reason"] for problem in entry["problems"]] == ["session_schema_unsupported"]
    assert others(broken, (NESTED, SHARED)) == others(healthy, (NESTED, SHARED))
    unresolved = look.refused("--repo", repo, "--workspace", NESTED, "select", "--audit-id", SHARED,
                              reason="selection_unresolved", code=EXIT_UNVERIFIED)
    assert unresolved["retained"] == [nested["session"]]
    look("--repo", repo, "--workspace", OUTER, "select", "--audit-id", SHARED)
    # Changed property: an envelope naming a workspace that does not match its location is not accepted.
    rewrite(session_record, json.dumps({**document, "schema_version": 99, "workspace": OTHER}).encode())
    entry = _located(discover(code=EXIT_UNVERIFIED))[(workspace(repo, NESTED).slug, SHARED)]
    assert entry["session"]["envelope"]["workspace"] is None and entry["workspace"] is None
    assert entry["session"]["envelope"]["schema"] == 99 and entry["stage"] == "unsupported"
    rewrite(session_record, original_session)
    assert discover() == healthy, "the restored session lists as before"

    # An invalid closing record keeps its diagnostic.
    closing_record = Path(_entries(healthy)[(OTHER, "failing-question")]["closes"][0]["path"]) / "CLOSING.json"
    original_closing = rewrite(closing_record, b"not json")
    broken = discover(code=EXIT_UNVERIFIED)
    closed_at = (workspace(repo, OTHER).slug, "failing-question")
    entry = _located(broken)[closed_at]
    assert entry["closes"][0]["problem"]["reason"] == "closing_record_invalid"
    assert "closing_record_invalid" in [problem["reason"] for problem in entry["problems"]]
    # The closing record was the only one naming the workspace; the entry stays listed by its location.
    assert (entry["workspace"], entry["stage"]) == (None, "closed")
    assert others(broken, (None, "failing-question")) == others(healthy, (OTHER, "failing-question"))
    rewrite(closing_record, original_closing)
    assert discover() == healthy

    # An invalid role row is a located problem; discovery lists everything else, a mutation still refuses.
    planted = common / "stewart/worktree-roles" / f"{uuid.uuid4()}.json"
    planted.write_text("{}")
    broken = discover(code=EXIT_UNVERIFIED)
    assert [(problem["reason"], problem["location"]) for problem in broken["problems"]] == [
        ("worktree_role_registry", str(planted))]
    assert broken["audits"] == healthy["audits"]
    look("--repo", repo, "--workspace", OUTER, "select", "--audit-id", SHARED)
    prompt = (repo / OUTER / "PROMPT.md").read_bytes()
    cli.refused("--repo", repo, "--workspace", OUTER, "init", "--audit-id", "fresh-question", "--input", "input.txt",
                "--replace-prompt", reason="worktree_role_registry", code=EXIT_UNVERIFIED)
    assert (repo / OUTER / "PROMPT.md").read_bytes() == prompt
    assert not (common / "stewart/audits" / workspace(repo, OUTER).slug / "fresh-question").exists()

    # All three at once: discovery still lists every audit, each with its own diagnostic.
    rewrite(session_record, json.dumps({**document, "schema_version": 99}).encode())
    rewrite(closing_record, b"not json")
    broken = discover(code=EXIT_UNVERIFIED)
    assert set(_located(broken)) == set(_located(healthy))
    assert _entries(broken)[(NESTED, SHARED)]["stage"] == "unsupported"
    assert _located(broken)[closed_at]["closes"][0]["problem"]["reason"] == "closing_record_invalid"
    assert [problem["reason"] for problem in broken["problems"]] == ["worktree_role_registry"]
    assert _entries(broken)[(OUTER, SHARED)] == _entries(healthy)[(OUTER, SHARED)]
    planted.unlink()
    rewrite(session_record, original_session)
    rewrite(closing_record, original_closing)
    assert discover() == healthy


# --- 4. selection ---------------------------------------------------------------------------------------


@pytest.mark.heavy
def test_select_refuses_an_ambiguous_alias_and_kept_references_stay_independent(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    _add_workspaces(checkout, NESTED)
    repo, common = checkout.repo, _common(checkout)
    look = ReadOnly(cli, repo)
    _init(cli, repo, OUTER, SHARED)
    _init(cli, repo, NESTED, SHARED)

    ambiguous = look.refused("--repo", repo, "select", "--audit-id", SHARED, reason="selection_ambiguous")
    assert sorted(ambiguous["retained"]) == sorted([OUTER, NESTED])
    outer = look("--repo", repo, "--workspace", OUTER, "select", "--audit-id", SHARED)["result"]
    assert outer["stage"] == "draft" and outer["reference"] == {
        "schema": "stewart.audit-ref/1", "repository": str(common), "checkout": str(repo), "owner": str(repo),
        "workspace": OUTER, "audit_id": SHARED, "lifetime": None, "closes": [], "implementation": None}
    nested = look("--repo", repo, "--workspace", NESTED, "select", "--audit-id", SHARED)["result"]
    assert nested["reference"] == {**outer["reference"], "workspace": NESTED}
    # Invariance: a second caller selecting the same audit gets the same reference, and nothing changes.
    assert look("--repo", repo, "--workspace", OUTER, "select", "--audit-id", SHARED)["result"]["reference"] == \
        outer["reference"]

    caller_a, caller_b = tmp_path / "caller-a.json", tmp_path / "caller-b.json"
    caller_a.write_text(json.dumps(outer["reference"]))
    caller_b.write_text(json.dumps(nested["reference"]))
    held_b = caller_b.read_bytes()
    before = look("--ref", caller_b, "status")["result"]
    assert (before["schema"], before["workspace"]["rel"]) == ("stewart.status-draft/1", NESTED)
    # Caller A acts through its own reference; caller B's reference and view are unaffected.
    cli("--ref", caller_a, "close", "--actor", "manager", "--abandon", "--reason", "caller A stops",
        allowed=(EXIT_OK, EXIT_ATTENTION))
    stages = {entry["workspace"]: entry["stage"] for entry in look("--repo", repo, "discover")["result"]["audits"]}
    assert stages == {OUTER: "closed", NESTED: "draft"}, "firing control: caller A's close happened"
    assert caller_b.read_bytes() == held_b and look("--ref", caller_b, "status")["result"] == before


def test_drafts_in_two_maintainer_checkouts_select_only_from_one_of_them(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    repo = checkout.repo
    first, spare = _linked(checkout, "first"), _linked(checkout, "spare")
    look = ReadOnly(cli, repo, first, spare)
    _init(cli, repo, OUTER, IDENT)
    _init(cli, first, OUTER, IDENT)

    entry = _entries(look("--repo", spare, "discover")["result"])[(OUTER, IDENT)]
    assert entry["draft_checkouts"] == sorted([str(repo), str(first)]) and entry["checkout"] is None
    refused = look.refused("--repo", spare, "--workspace", OUTER, "select", "--audit-id", IDENT,
                           reason="selection_ambiguous")
    assert sorted(refused["retained"]) == sorted([str(repo), str(first)])
    for root in (repo, first):
        reference = look("--repo", root, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]["reference"]
        assert (reference["owner"], reference["checkout"], reference["lifetime"]) == (str(root), str(root), None)

    # Changed property: a draft recorded in one checkout selects from any checkout, bound to that one.
    _init(cli, first, OUTER, "single-question")
    reference = look("--repo", spare, "--workspace", OUTER, "select", "--audit-id",
                     "single-question")["result"]["reference"]
    assert (reference["owner"], reference["checkout"]) == (str(first), str(first))


# --- 5. reference revalidation ----------------------------------------------------------------------------


@pytest.mark.heavy
def test_a_draft_reference_never_reaches_the_session_prepared_since(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    repo = checkout.repo
    _init(cli, repo, OUTER, IDENT)
    draft_ref = tmp_path / "draft-ref.json"
    draft_ref.write_text(json.dumps(cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id",
                                        IDENT)["result"]["reference"]))
    assert cli("--ref", draft_ref, "status")["result"]["schema"] == "stewart.status-draft/1", "control"

    revision = _assign(checkout, repo, OUTER, IDENT)
    prepared = cli("--ref", draft_ref, "prepare", "--prompt-commit", revision,
                   allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    bound = prepared["reference"]
    assert (bound["lifetime"], bound["workspace"], bound["audit_id"]) == (prepared["session_uuid"], OUTER, IDENT)
    assert bound["closes"] == [] and bound["checkout"] == str(repo) and bound["implementation"]
    collections = Path(prepared["session"]) / "collections"

    def count() -> int:
        return len(list(collections.iterdir())) if collections.exists() else 0

    cli.refused("--ref", draft_ref, "status", reason="reference_stale")
    cli.refused("--ref", draft_ref, "collect", "--auditor-stopped", "finished", reason="reference_stale")
    assert count() == 0, "a stale reference collects nothing"

    # Changed property: prepare's own reference binds the new lifetime.
    bound_ref = tmp_path / "bound-ref.json"
    bound_ref.write_text(json.dumps(bound))
    assert cli("--ref", bound_ref, "status")["result"]["reference"] == bound
    cli("--ref", bound_ref, "collect", "--auditor-stopped", "finished", allowed=(EXIT_OK, EXIT_ATTENTION))
    assert count() == 1
    # Invariance: selecting again yields the same bound reference.
    assert cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]["reference"] == bound


def test_a_draft_reference_cannot_prepare_a_prompt_naming_another_audit(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, common = checkout.repo, _common(checkout)
    _init(cli, repo, OUTER, IDENT)
    held = tmp_path / "draft-ref.json"
    held.write_text(json.dumps(cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id",
                                   IDENT)["result"]["reference"]))
    revision = _assign(checkout, repo, OUTER, "other-question")
    cli.refused("--ref", held, "prepare", "--prompt-commit", revision, reason="reference_mismatch")
    assert not (common / "stewart/sessions" / workspace(repo, OUTER).slug / "other-question").exists()


@pytest.mark.heavy
def test_a_draft_reference_taken_before_a_close_never_reaches_a_later_draft(checkout, run_cmd, monkeypatch,
                                                                            tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    repo, ws = checkout.repo, checkout.ws
    _init(cli, repo, ws.rel, IDENT)
    old_ref = tmp_path / "old-ref.json"
    old_ref.write_text(json.dumps(cli("--repo", repo, "--workspace", ws.rel, "select", "--audit-id",
                                      IDENT)["result"]["reference"]))
    assert json.loads(old_ref.read_text())["closes"] == []
    cli("--ref", old_ref, "status")

    _failed_prepare(monkeypatch, ws, _assign(checkout, repo, ws.rel, IDENT))
    failed_uuid = read_json(support.session_path(checkout, IDENT) / "session.json")["session_uuid"]
    cli.refused("--ref", old_ref, "status", reason="reference_stale")
    assert close(ws, IDENT, actor="manager", abandon=True, reason="Git administration was denied")["released"]
    _init(cli, repo, ws.rel, IDENT)

    entry = _entries(cli("--repo", repo, "discover")["result"])[(ws.rel, IDENT)]
    assert entry["stage"] == "draft" and [item["session_uuid"] for item in entry["closes"]] == [failed_uuid]
    assert sorted(item["closed_before"] for item in entry["drafts"]) == [[], [failed_uuid]]
    # The older reference's closes no longer cover the records: refused, never rebound to the new draft.
    cli.refused("--ref", old_ref, "status", reason="reference_stale")
    cli.refused("--ref", old_ref, "close", "--actor", "manager", "--abandon", "--reason", "stale caller",
                reason="reference_stale")
    # Changed property: a reference selected now covers the close and binds.
    new = cli("--repo", repo, "--workspace", ws.rel, "select", "--audit-id", IDENT)["result"]["reference"]
    assert (new["closes"], new["lifetime"]) == ([failed_uuid], None)
    new_ref = tmp_path / "new-ref.json"
    new_ref.write_text(json.dumps(new))
    first = cli("--ref", new_ref, "status")["result"]
    assert first["reference"]["closes"] == [failed_uuid]
    assert cli("--ref", new_ref, "status")["result"] == first, "invariance: the bound view repeats"


def test_a_mismatched_lifetime_refuses_status_and_collect(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    prepared = support.prepared_session(checkout)
    ident, lifetime = checkout.meta["audit_id"], prepared.prepared["session_uuid"]
    base = ["--repo", checkout.repo, "--workspace", checkout.ws.rel]
    other = str(uuid.uuid4())
    collections = prepared.session / "collections"

    def count() -> int:
        return len(list(collections.iterdir())) if collections.exists() else 0

    cli.refused(*base, "--lifetime", other, "status", "--audit-id", ident, reason="reference_stale")
    cli.refused(*base, "--lifetime", other, "collect", "--audit-id", ident, "--auditor-stopped", "finished",
                reason="reference_stale")
    assert count() == 0 and prepared.report.is_file(), "a refused collect captured nothing"
    # Control: the bound lifetime is accepted; invariance: binding it does not change the view.
    bound = cli(*base, "--lifetime", lifetime, "status", "--audit-id", ident)["result"]
    assert bound == cli(*base, "status", "--audit-id", ident)["result"]
    cli(*base, "--lifetime", lifetime, "collect", "--audit-id", ident, "--auditor-stopped", "finished",
        allowed=(EXIT_OK, EXIT_ATTENTION))
    assert count() == 1


def test_a_reference_whose_checkout_is_gone_is_refused(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    repo = checkout.repo
    linked = _linked(checkout, "linked")
    _init(cli, linked, OUTER, IDENT)
    held = tmp_path / "linked-ref.json"
    reference = cli("--repo", linked, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]["reference"]
    assert (reference["checkout"], reference["owner"]) == (str(linked), str(linked))
    held.write_text(json.dumps(reference))
    assert cli("--ref", held, "status")["result"]["workspace"]["repo"] == str(linked), "control: it binds"

    _remove_linked(checkout, linked)
    cli.refused("--ref", held, "status", reason="reference_checkout_missing")
    cli.refused("--repo", repo, "--ref", held, "status", reason="reference_checkout_missing")
    # Invariance: selecting again from an existing checkout binds there and still names the draft's owner.
    again = cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]["reference"]
    assert (again["checkout"], again["owner"]) == (str(repo), str(linked))
    held.write_text(json.dumps(again))
    assert cli("--ref", held, "status")["result"]["workspace"]["repo"] == str(repo)


def test_explicit_coordinates_that_disagree_with_a_reference_are_refused(checkout, run_cmd, tmp_path):
    cli = Stewart(run_cmd, checkout.tmp)
    _add_workspaces(checkout, OTHER)
    repo, common = checkout.repo, _common(checkout)
    _init(cli, repo, OUTER, IDENT)
    held = tmp_path / "ref.json"
    held.write_text(json.dumps(cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id",
                                   IDENT)["result"]["reference"]))
    cli.refused("--ref", held, "--workspace", OTHER, "status", reason="reference_mismatch")
    cli.refused("--ref", held, "status", "--audit-id", "other-question", reason="reference_mismatch")
    cli.refused("--ref", held, "--lifetime", str(uuid.uuid4()), "status", reason="reference_mismatch")
    cli.refused("--ref", held, "close", "--audit-id", "other-question", "--actor", "manager", "--abandon",
                "--reason", "mismatched", reason="reference_mismatch")
    assert not (common / "stewart/closed").exists(), "a refused close recorded nothing"
    # Control: agreeing explicit values are accepted; invariance: they change nothing in the view.
    agreeing = cli("--ref", held, "--workspace", OUTER, "status", "--audit-id", IDENT)["result"]
    assert agreeing == cli("--ref", held, "status")["result"]


# --- 6. removed maintainer checkouts --------------------------------------------------------------------


def test_a_session_whose_owner_checkout_was_removed_stays_discoverable(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    _add_workspaces(checkout, OTHER)
    repo = checkout.repo
    owner = _linked(checkout, "owner")
    prepared = prepare(workspace(owner, OUTER), _assign(checkout, owner, OUTER, IDENT))
    _init(cli, repo, OTHER, "main-question")

    entries = _entries(cli("--repo", repo, "discover")["result"])
    live = entries[(OUTER, IDENT)]
    assert (live["stage"], live["checkout"], live["checkout_available"]) == ("prepared", str(owner), True)
    assert "session_owner_missing" not in [problem["reason"] for problem in live["problems"]]

    _remove_linked(checkout, owner)
    found = cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_UNVERIFIED))["result"]
    entries = _entries(found)
    gone = entries[(OUTER, IDENT)]
    assert (gone["stage"], gone["lifetime"]) == ("prepared", prepared["session_uuid"])
    assert (gone["checkout"], gone["checkout_available"]) == (str(owner), False)
    assert gone["session"]["path"] == prepared["session"]
    assert "session_owner_missing" in [problem["reason"] for problem in gone["problems"]]
    # Invariance: an audit drafted in the surviving checkout is unaffected.
    assert (entries[(OTHER, "main-question")]["checkout"], entries[(OTHER, "main-question")]["checkout_available"]) \
        == (str(repo), True)
    reference = cli("--repo", repo, "--workspace", OUTER, "select", "--audit-id", IDENT)["result"]["reference"]
    assert (reference["owner"], reference["checkout"], reference["lifetime"]) == (
        str(owner), str(repo), prepared["session_uuid"])


def test_draft_files_of_a_removed_draft_checkout_are_unavailable(checkout, run_cmd):
    cli = Stewart(run_cmd, checkout.tmp)
    repo = checkout.repo
    drafts = _linked(checkout, "drafts")
    result = _init(cli, drafts, OUTER, IDENT)
    recorded = _sha((drafts / OUTER / "PROMPT.md").read_bytes())
    assert [item["sha256"] for item in result["written_files"]] == [recorded]

    def files() -> list[dict]:
        found = cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_UNVERIFIED))["result"]
        [draft] = _entries(found)[(OUTER, IDENT)]["drafts"]
        return draft["files"]

    prompt = workspace(repo, OUTER).prompt
    assert files() == [{"path": prompt, "recorded_sha256": recorded, "observed_sha256": recorded,
                        "state": "unchanged"}]
    # Changed property (present checkout): an edited prompt is "changed", observed with its new digest.
    (drafts / prompt).write_text("edited by hand\n")
    assert [(item["state"], item["observed_sha256"]) for item in files()] == [
        ("changed", _sha(b"edited by hand\n"))]

    _remove_linked(checkout, drafts)
    assert files() == [{"path": prompt, "recorded_sha256": recorded, "state": "unavailable"}]
    found = cli("--repo", repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_UNVERIFIED))["result"]
    entry = _entries(found)[(OUTER, IDENT)]
    assert (entry["checkout"], entry["checkout_available"]) == (str(drafts), False)
    view = cli("--repo", repo, "--workspace", OUTER, "status", "--audit-id", IDENT,
               allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert view["schema"] == "stewart.status-draft/1"
    assert [(item["path"], item["state"]) for item in view["drafts"][0]["files"]] == [(prompt, "unavailable")]
    assert view["next_actions"] == [] and view["outstanding"], "the gone checkout's draft is not continued here"
