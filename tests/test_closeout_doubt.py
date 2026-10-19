"""Doubt keeps resources: liveness, placement, creation records and refusals at closeout.

A recorded resource retires only when every use is known to have ended. A
closing record that does not verify, a session or draft record that cannot be
read, and a use recorded between the evaluation and the removal each keep the
resource. Placement stays out of recorded checkout homes; a resumed close
retires only what its first attempt claimed; interrupted and failed creations
are cleared by hand and acknowledged; registration reads only regular files;
a draft-only audit is abandoned once; and discovery lists a supported session
that does not load as unverified. Refusals carry stable reasons.

Each measured guarantee has a firing control (the condition is shown to have
happened), a case differing only in the measured property, and an invariance
case. Measured commands run in a fresh isolated process from the installed
wheel; setup that needs an injected failure or interleaving runs in process.
All repositories, homes and manager storage are disposable fixtures.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import threading
import uuid

import pytest

from stewart import _util, api
import stewart._git as git_module
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
import stewart.close as close_module
import stewart.holdings as holdings
from stewart.workspace import workspace
import stewart_support as support
from stewart_support import assignment_text, read_json, snapshot_tree
import test_discovery as discovery
import test_resources as resources

pytestmark = pytest.mark.system

WS = support.WS
OTHER = resources.OTHER
IDENT = resources.IDENT
SECOND = resources.SECOND
THIRD = resources.THIRD
HOLDER = resources.HOLDER
PARTNER = resources.PARTNER
DRAFT = "draft-question"
REGISTERED = "registered-question"

_common = resources._common
_records = resources._records
_rids = resources._rids
_claim_files = resources._claim_files
_generations = resources._generations
_by_rid = resources._by_rid
_reason = resources._reason


# --- helpers ---------------------------------------------------------------------------------------------


class Stewart(resources.Stewart):
    """The installed wheel in a fresh isolated process, with refusals checked by reason and exit code."""

    def refused(self, *argv, reason: str, code: int = EXIT_REFUSED) -> dict:
        envelope = self(*argv, allowed=(code,))
        assert envelope["error"]["reason"] == reason, envelope["error"]
        return envelope["error"]


def _cli(run_cmd, root: Path) -> Stewart:
    """Commands run from an unrelated directory: nothing may depend on the current directory."""
    elsewhere = root / "elsewhere"
    elsewhere.mkdir(exist_ok=True)
    return Stewart(run_cmd, elsewhere)


def _rewrite(location: Path, data: bytes) -> bytes:
    """Replace a record's bytes in place (a corruption or a restoration); return what was there."""
    original, mode = location.read_bytes(), stat.S_IMODE(location.stat().st_mode)
    location.chmod(mode | stat.S_IWUSR)
    location.write_bytes(data)
    location.chmod(mode)
    return original


def _tree(root: Path) -> dict | None:
    return snapshot_tree(root) if root.exists() else None


def _show(cli: Stewart, repo: Path, rid: str, allowed=(EXIT_OK, EXIT_ATTENTION)) -> dict:
    return cli("--repo", repo, "resource", "show", "--resource", rid, allowed=allowed)["result"]


def _close_resource(rid: str, repo: Path) -> tuple:
    return ("--repo", repo, "close", "--resource", rid, "--actor", "manager")


def _plan(cli: Stewart, repo: Path, rel: str, ident: str, *extra, allowed=(EXIT_OK,)) -> dict[str, dict]:
    plan = cli("--repo", repo, "--workspace", rel, "close", "--audit-id", ident, "--plan", *extra,
               allowed=allowed)["result"]
    assert plan["schema"] == "stewart.closeout/1"
    return _by_rid(plan["resources"])


def _abandon(cli: Stewart, repo: Path, rel: str, ident: str, *extra, allowed=(EXIT_OK,)) -> dict:
    return cli("--repo", repo, "--workspace", rel, "close", "--audit-id", ident, "--actor", "manager", "--abandon",
               "--reason", f"{ident} is finished with its resources", *extra, allowed=allowed)["result"]


def _create_directory(ident: str, path: Path, repo: Path, rel: str = WS) -> tuple:
    return ("--repo", repo, "--workspace", rel, "resource", "create-directory", "--audit-id", ident, "--path", path,
            "--actor", "manager")


def _live(view: dict) -> list[str]:
    return sorted(user["audit"]["audit_id"] for user in view["users"] if user["live"])


def _assigned_prompt(checkout, ident: str) -> None:
    """Write (without committing) a workspace prompt whose assignment block names ``ident``."""
    ws = checkout.ws
    meta = {**checkout.meta, "audit_id": ident, "report_path": ws.report_path(ident)}
    (checkout.repo / ws.prompt).write_text(assignment_text(meta), encoding="utf-8")


# --- 1. liveness doubt keeps resources ----------------------------------------------------------------------


def test_a_closing_record_that_does_not_verify_keeps_its_audits_uses_live(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    shared = root / "shared-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(shared), actor="manager")["rid"]
    (shared / "work.txt").write_text("kept while any use may remain\n", encoding="utf-8")
    api.associate(checkout.ws, PARTNER, rid=rid, actor="manager")
    held = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="the holder is done")
    assert _by_rid(held["closeout"])[rid]["disposition"] == "shared", "the partner's use outlives the holder"
    closing = Path(held["closing"])
    verified = _show(cli, checkout.repo, rid)
    assert [(user["live"], user["state"]) for user in verified["users"]
            if user["audit"]["audit_id"] == HOLDER] == [(False, "closed")]

    original = _rewrite(closing, b"not a closing record\n")
    doubted = _show(cli, checkout.repo, rid)
    # Firing control: the holder's use is live again only because its closing record does not verify.
    assert [(user["live"], user["state"], user["reason"]) for user in doubted["users"]
            if user["audit"]["audit_id"] == HOLDER] == [
        (True, "unverified", "a closing record of this audit does not verify")]
    assert doubted["disposition"] == "shared"

    # The partner's close ends its own use; the holder's doubted use keeps the directory.
    partner = _abandon(cli, checkout.repo, WS, PARTNER)
    evaluation = _by_rid(partner["closeout"])[rid]
    assert evaluation["disposition"] == "shared" and partner["resources"] == []
    assert f"{WS}:{HOLDER}" in " ".join(evaluation["reasons"]) and "unverified" in " ".join(evaluation["reasons"])
    records, contents = _tree(_records(common)), snapshot_tree(shared)
    for _ in range(2):  # Invariance: every later resource close refuses identically and writes nothing.
        refused = cli.refused(*_close_resource(rid, checkout.repo), reason="resource_shared")
        assert f"{WS}:{HOLDER}" in refused["message"] and "unverified" in refused["message"]
    assert _tree(_records(common)) == records and snapshot_tree(shared) == contents
    assert _claim_files(common, rid) == []

    # Differing only in the record's verifiability: restored, the holder's use has ended and it retires.
    _rewrite(closing, original)
    assert _live(_show(cli, checkout.repo, rid)) == []
    retired = cli(*_close_resource(rid, checkout.repo))["result"]
    assert [(item["rid"], item["outcome"]) for item in retired["results"]] == [(rid, "removed")]
    assert not shared.exists() and _claim_files(common, rid) == ["0001.RETIRED.json", "0001.json"]
    assert closing.read_bytes() == original, "the closing record is never rewritten by Stewart"


def test_an_unreadable_session_record_blocks_the_directory_holding_its_checkout_home(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    holding = root / "holding-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(holding), actor="manager")["rid"]
    prepared = api.prepare(checkout.ws, checkout.prompt_commit(), checkout_home_path=holding / "home")
    assert Path(prepared["audit_dir"]).is_relative_to(holding / "home"), "firing control: it pins a path inside"
    held = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="the holder is done")
    assert _by_rid(held["closeout"])[rid]["disposition"] == "shared" and held["resources"] == []
    readable = _show(cli, checkout.repo, rid)
    assert readable["disposition"] == "shared" and _live(readable) == [IDENT]
    assert not any("cannot be read" in reason for reason in readable["reasons"])

    record = Path(prepared["session"]) / "session.json"
    original = _rewrite(record, b"{ not a session record\n")
    unreadable = _show(cli, checkout.repo, rid)
    # The record no longer says what it pins, so no use is derived from it; doubt blocks instead.
    assert _live(unreadable) == [] and unreadable["disposition"] == "blocked"
    doubt = [reason for reason in unreadable["reasons"] if reason.startswith("records that cannot be read may use it")]
    assert len(doubt) == 1 and prepared["session"] in doubt[0], unreadable["reasons"]
    records, contents = _tree(_records(common)), snapshot_tree(holding)
    for _ in range(2):  # Invariance: refused identically, nothing claimed or removed.
        refused = cli.refused(*_close_resource(rid, checkout.repo), reason="resource_blocked")
        assert doubt[0] in refused["message"]
    assert _tree(_records(common)) == records and snapshot_tree(holding) == contents
    assert _claim_files(common, rid) == []

    # Differing only in readability: restored, the session is a live use again (shared, not doubted).
    _rewrite(record, original)
    restored = _show(cli, checkout.repo, rid)
    assert restored["disposition"] == "shared" and _live(restored) == [IDENT]
    assert not any("cannot be read" in reason for reason in restored["reasons"])
    cli.refused(*_close_resource(rid, checkout.repo), reason="resource_shared")

    # The use ends with its audit; then the directory retires (by that close, or explicitly once released).
    api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="done", discard_uncollected=True)
    if api.show_resource(checkout.repo, rid)["disposition"] != "retired":
        retired = cli(*_close_resource(rid, checkout.repo))["result"]
        assert [item["outcome"] for item in retired["results"]] == ["removed"]
    assert not holding.exists()
    endings = _generations(common, rid)
    assert endings and None not in endings.values() and list(endings.values()).count("RETIRED") == 1, endings


def test_a_draft_record_that_does_not_verify_blocks_retirement_until_restored(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    scratch = root / "scratch-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(scratch), actor="manager")["rid"]
    # Another audit is registered in the maintainer checkout; its record pins nothing inside the directory.
    _assigned_prompt(checkout, REGISTERED)
    registration = Path(api.register(checkout.ws, REGISTERED, actor="manager")["path"])
    assert _plan(cli, checkout.repo, WS, HOLDER)[rid]["disposition"] == "remove", "control: nothing doubts it"

    original = _rewrite(registration, b"not a registration record\n")
    # A record that does not verify may name any checkout as its own, wherever it is.
    planned = _plan(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))[rid]
    doubt = f"records that cannot be read may use it: {registration}"
    assert planned["disposition"] == "blocked" and doubt in planned["reasons"]
    closed = _abandon(cli, checkout.repo, WS, HOLDER, allowed=(EXIT_ATTENTION,))
    evaluation = _by_rid(closed["closeout"])[rid]
    assert evaluation["disposition"] == "blocked" and doubt in evaluation["reasons"]
    assert closed["resources"] == [] and closed["closed"] is not None and scratch.is_dir()
    records = _tree(_records(common))
    for _ in range(2):  # Invariance: the doubt refuses every later retirement identically.
        refused = cli.refused(*_close_resource(rid, checkout.repo), reason="resource_blocked")
        assert doubt in refused["message"]
    assert _tree(_records(common)) == records and _claim_files(common, rid) == []

    # Differing only in the record's readability: restored, the left-behind directory retires explicitly.
    _rewrite(registration, original)
    assert _show(cli, checkout.repo, rid)["disposition"] == "remove"
    retired = cli(*_close_resource(rid, checkout.repo))["result"]
    assert [(item["rid"], item["outcome"]) for item in retired["results"]] == [(rid, "removed")]
    assert not scratch.exists() and registration.read_bytes() == original


@pytest.mark.parametrize("seam", ["after_evaluation", "racing_associate"])
def test_a_use_recorded_at_the_claim_seam_releases_the_claim_and_keeps_the_resource(checkout, tmp_path, run_cmd,
                                                                                   monkeypatch, seam):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    contested, bystander = root / "contested-dir", root / "bystander-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(contested), actor="manager")["rid"]
    other = api.create_directory(checkout.ws, HOLDER, path=str(bystander), actor="manager")["rid"]
    (contested / "work.txt").write_text("the partner's work\n", encoding="utf-8")
    contents = snapshot_tree(contested)
    real_claim, real_record, real_retire = holdings._claim, holdings._record, holdings.retire_for_close
    claimed, checked = threading.Event(), threading.Event()
    seen: dict = {"associations": []}
    box: dict = {}
    order: list[str] = []

    def claim(common_, view, evaluation, claimant):
        if view["rid"] == rid and seam == "after_evaluation":
            # The evaluation that judged it removable is done; a use is recorded before the claim exists.
            seen["associations"].append(api.associate(checkout.ws, PARTNER, rid=rid, actor="partner"))
        made = real_claim(common_, view, evaluation, claimant)
        if view["rid"] == rid and made is not None:
            seen["claim"] = made["path"]
            order.append("claimed")
            claimed.set()
        return made

    def gated_record(directory, name, value):
        # A racing associate passed its retiring check before the claim; its record lands after the claim.
        if directory.name == "associations" and value.get("rid") == rid and value.get("actor") == "partner":
            order.append("checked")
            checked.set()
            assert claimed.wait(60), "the close never claimed the contested directory"
            digest = real_record(directory, name, value)
            order.append("recorded")
            return digest
        return real_record(directory, name, value)

    def retire(common_, closing):
        if seam == "racing_associate":
            racer.join(90)
            assert not racer.is_alive(), "the racing associate did not finish"
            seen["associations"].append(box.get("result", box.get("error")))
        # With the claim active, a use that starts now is refused at its own check.
        with pytest.raises(StewartError) as refused:
            api.associate(checkout.ws, THIRD, rid=rid, actor="third")
        seen["refused"] = refused.value.reason
        return real_retire(common_, closing)

    def race():
        try:
            box["result"] = api.associate(checkout.ws, PARTNER, rid=rid, actor="partner")
        except BaseException as exc:  # noqa: BLE001 - reported on the test thread
            box["error"] = exc

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_claim", claim)
        patch.setattr(holdings, "retire_for_close", retire)
        if seam == "racing_associate":
            patch.setattr(holdings, "_record", gated_record)
            racer = threading.Thread(target=race, name="racing-associate", daemon=True)
            racer.start()
            assert checked.wait(60), "firing control: the associate passed its check before the close began"
        closed = api.close(checkout.ws, HOLDER, actor="manager", abandon=True, reason="the holder is done")

    [association] = seen["associations"]
    assert isinstance(association, dict), association
    location = Path(association["path"])
    # Firing control: the use was recorded after the evaluation that judged the directory removable.
    evaluation = _by_rid(closed["closeout"])[rid]
    assert evaluation["disposition"] == "claimed by this close" and evaluation["claim"] == seen["claim"]
    assert PARTNER not in [user["audit"]["audit_id"] for user in evaluation["users"]]
    assert location.is_file() and read_json(location)["context"]["audit_id"] == PARTNER
    if seam == "racing_associate":
        assert order == ["checked", "claimed", "recorded"], "its check preceded the claim; its record followed it"
    assert seen["refused"] == "resource_retiring"
    assert [path.name for path in location.parent.iterdir()] == [location.name], "the refused use wrote nothing"

    outcomes = _by_rid(closed["resources"])
    assert outcomes[rid]["outcome"] == "kept"
    assert any(reason.startswith("a live use appeared") and PARTNER in reason for reason in outcomes[rid]["reasons"])
    # Differing only in the late use: the bystander claimed by the same close retires.
    assert outcomes[other]["outcome"] == "removed" and not bystander.exists()
    assert closed["exit_code"] == EXIT_ATTENTION
    assert _claim_files(common, rid) == ["0001.RELEASED.json", "0001.json"]
    released = read_json(_records(common, rid) / "claims/0001.RELEASED.json")
    assert any(item.startswith("a live use appeared") for item in released["observation"])
    assert snapshot_tree(contested) == contents

    # Invariance: the use is an ordinary live use from now on, and its own close retires the directory.
    shown = _show(cli, checkout.repo, rid)
    assert shown["disposition"] == "shared" and _live(shown) == [PARTNER]
    partner = _abandon(cli, checkout.repo, WS, PARTNER)
    assert {item["rid"]: item["outcome"] for item in partner["resources"]} == {rid: "removed"}
    assert not contested.exists()
    assert _claim_files(common, rid) == ["0001.RELEASED.json", "0001.json", "0002.RETIRED.json", "0002.json"]
    assert read_json(_records(common, rid) / "claims/0001.RELEASED.json") == released


# --- 2. placement strictness ------------------------------------------------------------------------------


def test_managed_placement_refuses_a_checkout_home_a_session_records(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    home = root / "homes" / "custom-home"
    home.parent.mkdir()
    prepared = api.prepare(checkout.ws, checkout.prompt_commit(), checkout_home_path=home)
    # Firing control: the session records this non-default checkout home.
    assert read_json(Path(prepared["session"]) / "session.json")["checkout_home"] == str(home)
    assert Path(prepared["audit_dir"]).is_relative_to(home)

    def create(kind: str, path: Path) -> tuple:
        return ("--repo", checkout.repo, "--workspace", WS, "resource", f"create-{kind}", "--audit-id", HOLDER,
                "--path", path, "--actor", "manager")

    inside = [home / "managed", home / Path(prepared["audit_dir"]).parent.name / "managed"]
    for kind in ("directory", "worktree"):
        for path in inside:
            for _ in range(2):  # Invariance: refused identically each time, before any record.
                refused = cli.refused(*create(kind, path), reason="resource_location")
                assert f"a managed {kind} cannot overlap a recorded checkout home: {home}" in refused["message"]
            assert not path.exists()
    assert _rids(common) == [], "a refused placement records no resource"

    # Differing only in containment: siblings that share the home's name as a string prefix are accepted.
    directory = root / "homes" / "custom-home-sibling"
    tree = root / "homes" / "custom-home-tree"
    made = cli(*create("directory", directory))["result"]
    made_tree = cli(*create("worktree", tree))["result"]
    assert directory.is_dir() and tree.is_dir()
    assert sorted(_rids(common)) == sorted([made["rid"], *(item["rid"] for item in made_tree["resources"])])


# --- 3. a resumed close never claims ------------------------------------------------------------------------


def test_a_resumed_close_claims_nothing_and_leaves_eligible_resources_to_close_resource(tmp_path, run_cmd,
                                                                                       monkeypatch):
    checkout = resources._two_workspaces(tmp_path, run_cmd)
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    first_prompt = resources._assign(checkout, WS, IDENT, checkout.base)
    second_prompt = resources._assign(checkout, OTHER, SECOND, first_prompt)
    other_ws = workspace(checkout.repo, OTHER)
    first = api.prepare(checkout.ws, first_prompt)
    api.prepare(other_ws, second_prompt)
    interrupted, uninterrupted = root / "interrupted-dir", root / "uninterrupted-dir"
    rid = api.create_directory(checkout.ws, IDENT, path=str(interrupted), actor="manager")["rid"]
    control = api.create_directory(other_ws, SECOND, path=str(uninterrupted), actor="manager")["rid"]
    assert read_json(_records(common, rid) / "CREATE.json")["context"]["lifetime"] == first["session_uuid"]

    def interrupt(parent, name, **_):
        raise OSError("synthetic interruption before checkout removal")

    with monkeypatch.context() as patch:
        patch.setattr(close_module, "_delete_checkout", interrupt)
        stopped = api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="stop here",
                            discard_uncollected=True)
    # Firing control: the closing record exists and removal stopped at the checkout, before any claim.
    assert stopped["closed"] is None and stopped["failed"][0]["kind"] == "worktree"
    assert Path(stopped["closing"]).is_file() and Path(first["session"]).is_dir()
    assert stopped["closeout"] == [] and stopped["resources"] == [] and _claim_files(common, rid) == []
    # A lifetime that is closing takes no new resource.
    late = root / "late-dir"
    for _ in range(2):
        cli.refused(*_create_directory(IDENT, late, checkout.repo), reason="audit_closed")
    assert not late.exists() and _rids(common) == sorted([rid, control])

    resumed = _abandon(cli, checkout.repo, WS, IDENT, "--discard-uncollected", allowed=(EXIT_OK, EXIT_ATTENTION))
    assert resumed["resumed"] is True and resumed["closed"] is not None and not Path(first["session"]).exists()
    # The resumed close retires only claims its first attempt made: there were none, so it claims nothing.
    assert resumed["closeout"] == [] and resumed["resources"] == []
    assert _claim_files(common, rid) == [] and interrupted.is_dir()
    left = _show(cli, checkout.repo, rid)
    assert left["disposition"] == "remove" and _live(left) == [], "eligible, and left for close --resource"

    # Differing only in the interruption: the other audit's first-attempt close claims and retires its directory.
    done = _abandon(cli, checkout.repo, OTHER, SECOND, "--discard-uncollected", allowed=(EXIT_OK, EXIT_ATTENTION))
    assert _by_rid(done["closeout"])[control]["disposition"] == "claimed by this close"
    assert {item["rid"]: item["outcome"] for item in done["resources"]} == {control: "removed"}
    assert not uninterrupted.exists()
    # Invariance: that close did not reach the resource the resumed close left behind.
    assert _claim_files(common, rid) == [] and interrupted.is_dir()

    retired = cli(*_close_resource(rid, checkout.repo))["result"]
    assert [(item["rid"], item["outcome"], item["resumed"]) for item in retired["results"]] == [
        (rid, "removed", False)]
    assert not interrupted.exists() and _claim_files(common, rid) == ["0001.RETIRED.json", "0001.json"]
    claim = read_json(_records(common, rid) / "claims/0001.json")
    assert claim["claimant"]["kind"] == "resource-close"


# --- 4. manual retirement of interrupted and failed creations -----------------------------------------------


def _interrupted_directory(checkout, monkeypatch, target: Path) -> None:
    """The directory is made, then the creation stops before its outcome record, as a signal would."""
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt("synthetic interruption between the side effect and its outcome")

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_finish", interrupted)
        with pytest.raises(KeyboardInterrupt):
            api.create_directory(checkout.ws, HOLDER, path=str(target), actor="manager")


def _failed_directory(checkout, monkeypatch, target: Path) -> StewartError:
    """An entry appears at the path after the start record, so the creation's own mkdir fails."""
    real = holdings._start

    def start_then_plant(common, directory, rid, kind, context, intended, actor):
        digest = real(common, directory, rid, kind, context, intended, actor)
        Path(intended["path"]).mkdir()
        (Path(intended["path"]) / "planted.txt").write_text("an entry that won the race\n", encoding="utf-8")
        return digest

    with monkeypatch.context() as patch:
        patch.setattr(holdings, "_start", start_then_plant)
        return _reason(api.create_directory, checkout.ws, HOLDER, path=str(target), actor="manager")


def _failed_worktree(checkout, monkeypatch, target: Path) -> StewartError:
    """Git adds and locks the worktree, then the creation fails before its marker and outcome identity."""
    real = git_module.git

    def fail_after_add(repo, *args, **kwargs):
        done = real(repo, *args, **kwargs)
        if args[:2] == ("worktree", "add"):
            raise StewartError("synthetic failure after Git added the worktree", reason="git_failed")
        return done

    with monkeypatch.context() as patch:
        patch.setattr(git_module, "git", fail_after_add)
        return _reason(api.create_worktree, checkout.ws, HOLDER, path=str(target), actor="manager")


@pytest.mark.parametrize("kind,how", [("directory", "interrupted"), ("directory", "failed"), ("worktree", "failed")])
def test_an_interrupted_or_failed_creation_is_cleared_by_hand_and_acknowledged(checkout, tmp_path, run_cmd,
                                                                              monkeypatch, kind, how):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    target = root / f"{how}-{kind}"
    if how == "interrupted":
        _interrupted_directory(checkout, monkeypatch, target)
    else:
        failure = (_failed_directory if kind == "directory" else _failed_worktree)(checkout, monkeypatch, target)
    [rid] = _rids(common)
    created = _records(common, rid)
    if how == "failed":
        assert failure.reason == "resource_creation" and str(created) in failure.retained, failure.to_json()
    # Firing control: the creation's records say what happened, and something is at its intended location.
    assert sorted(os.listdir(created)) == (["CREATE.json"] if how == "interrupted" else ["CREATE.json", "CREATED.json"])
    if how == "failed":
        outcome = read_json(created / "CREATED.json")
        assert (outcome["status"], outcome["identity"]) == ("failed", None) and outcome["error"]
    assert target.is_dir()
    if kind == "worktree":
        assert str(target) in resources._worktrees(checkout.repo), "control: Git registered the worktree"
    start_bytes = (created / "CREATE.json").read_bytes()
    found = snapshot_tree(target)

    present = _show(cli, checkout.repo, rid)
    assert present["creation"] == ("unresolved" if how == "interrupted" else "failed")
    assert present["disposition"] == "blocked" and present["observation"]["state"] == "present"
    reasons = " ".join(present["reasons"])
    assert ("creation was interrupted" if how == "interrupted" else "its recorded creation failed") in reasons
    assert "remove what is there by hand" in reasons
    acknowledge = ("--repo", checkout.repo, "resource", "acknowledge", "--resource", rid, "--actor", "manager",
                   "--note", "cleared by hand after review")
    for _ in range(2):  # Invariance: nothing Stewart did not create is removed or acknowledged while present.
        cli.refused(*acknowledge, reason="resource_present")
        refused = cli.refused(*_close_resource(rid, checkout.repo), reason="resource_blocked")
        assert ("creation was interrupted" if how == "interrupted" else "creation failed") in refused["message"]
    assert snapshot_tree(target) == found and sorted(os.listdir(created)) == sorted(
        ["CREATE.json"] + (["CREATED.json"] if how == "failed" else []))

    # Differing only in what is at the location: cleared by hand, it is missing and can be acknowledged.
    if kind == "worktree":
        checkout.git("worktree", "remove", "-f", "-f", str(target))
    else:
        shutil.rmtree(target)
    missing = _show(cli, checkout.repo, rid)
    assert missing["disposition"] == "missing" and missing["observation"]["state"] == "absent"
    assert "acknowledge it if that is final" in " ".join(missing["reasons"])
    cli(*acknowledge)
    acknowledged = _show(cli, checkout.repo, rid)
    assert acknowledged["disposition"] == "acknowledged"
    assert acknowledged["acknowledged"]["observed_at_acknowledgment"]["state"] == "absent"
    assert acknowledged["acknowledged"]["acknowledged"]["actor"] == "manager"
    if how == "failed":
        assert acknowledged["exit_code"] == EXIT_OK
    record = read_json(created / "ACKNOWLEDGED.json")
    assert record["resource_record_sha256"] == _util.sha256_bytes(start_bytes)
    assert (created / "CREATE.json").read_bytes() == start_bytes, "the creation record is never edited"
    cli.refused(*acknowledge, reason="destination_exists")
    cli.refused(*_close_resource(rid, checkout.repo), reason="resource_retired")
    assert _claim_files(common, rid) == []


def test_an_acknowledged_interrupted_creation_needs_no_further_attention(checkout, tmp_path, run_cmd, monkeypatch):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    interrupted, failed = root / "interrupted-directory", root / "failed-directory"
    _interrupted_directory(checkout, monkeypatch, interrupted)
    [interrupted_rid] = _rids(common)
    assert _failed_directory(checkout, monkeypatch, failed).reason == "resource_creation"
    [failed_rid] = sorted(set(_rids(common)) - {interrupted_rid})
    for path, rid in ((interrupted, interrupted_rid), (failed, failed_rid)):
        shutil.rmtree(path)
        assert _show(cli, checkout.repo, rid)["exit_code"] == EXIT_ATTENTION, "control: the absence needs attention"
        cli("--repo", checkout.repo, "resource", "acknowledge", "--resource", rid, "--actor", "manager")
    # Control, differing only in how the creation ended: the acknowledged failed creation needs nothing more.
    assert _show(cli, checkout.repo, failed_rid)["exit_code"] == EXIT_OK
    # Measured: the acknowledged interrupted creation has the same final state and needs nothing more either.
    shown = _show(cli, checkout.repo, interrupted_rid)
    assert shown["disposition"] == "acknowledged" and shown["exit_code"] == EXIT_OK
    found = cli("--repo", checkout.repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))
    assert {item["rid"]: item["exit_code"] for item in found["result"]["resources"]} == {
        interrupted_rid: EXIT_OK, failed_rid: EXIT_OK}


# --- 5. registration reads only regular guidance files -------------------------------------------------------


@pytest.mark.parametrize("role", ["prompt", "auditor_guidance", "maintainer_guidance"])
def test_register_refuses_a_guidance_file_that_is_a_link(checkout, tmp_path, run_cmd, role):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    ws = checkout.ws
    _assigned_prompt(checkout, REGISTERED)
    location = checkout.repo / getattr(ws, role)
    data = location.read_bytes()
    target = root / f"outside-{location.name}"
    target.write_bytes(data)
    location.unlink()
    location.symlink_to(target)
    assert location.is_symlink() and location.read_bytes() == data, "firing control: same bytes, through a link"
    records = common / "stewart/audits" / ws.slug / REGISTERED
    register = ("--repo", checkout.repo, "--workspace", WS, "register", "--audit-id", REGISTERED, "--actor", "manager")
    for _ in range(2):  # Invariance: refused identically; no registration record is written.
        refused = cli.refused(*register, reason="path_symlink")
        assert getattr(ws, role) in refused["message"]
        assert not records.exists()
    assert target.read_bytes() == data and location.is_symlink()

    # Differing only in the file kind: the same bytes as a regular file register.
    location.unlink()
    location.write_bytes(data)
    registered = cli(*register)["result"]
    observed = read_json(Path(registered["path"]))["observed"][role]
    assert (observed["kind"], observed["sha256"]) == ("file", _util.sha256_bytes(data))
    assert [path.name for path in (records / "registrations").iterdir()] == [Path(registered["path"]).name]


# --- 6. refusal reasons with controls --------------------------------------------------------------------------


def test_close_resource_refuses_a_resource_another_live_audit_uses(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    shared, lone = root / "shared-dir", root / "lone-dir"
    rid = api.create_directory(checkout.ws, HOLDER, path=str(shared), actor="manager")["rid"]
    lone_rid = api.create_directory(checkout.ws, HOLDER, path=str(lone), actor="manager")["rid"]
    api.associate(checkout.ws, PARTNER, rid=rid, actor="manager")
    closed = _abandon(cli, checkout.repo, WS, HOLDER)
    # Control, differing only in the other use: the holder's single-use directory retired with its close.
    assert {item["rid"]: item["outcome"] for item in closed["resources"]} == {lone_rid: "removed"}
    assert _by_rid(closed["closeout"])[rid]["disposition"] == "shared" and shared.is_dir()
    records = _tree(_records(common))
    for _ in range(2):
        refused = cli.refused(*_close_resource(rid, checkout.repo), reason="resource_shared")
        assert f"{WS}:{PARTNER}" in refused["message"] and f"{WS}:{HOLDER}" not in refused["message"]
    assert _tree(_records(common)) == records and _claim_files(common, rid) == []
    # Invariance: the last use's own close retires it; then a resource close finds it retired.
    partner = _abandon(cli, checkout.repo, WS, PARTNER)
    assert {item["rid"]: item["outcome"] for item in partner["resources"]} == {rid: "removed"}
    cli.refused(*_close_resource(rid, checkout.repo), reason="resource_retired")


def test_a_session_without_a_writer_stamp_refuses_mutations_but_can_be_abandoned(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    prepared = support.prepared_session(checkout, report=None)
    status = ("--repo", checkout.repo, "--workspace", WS, "status", "--audit-id", IDENT)

    def mutations(view: dict) -> list[dict]:
        return [action for action in view["next_actions"] if action["action"] not in ("handoff", "triage-draft")]

    stamped = cli(*status, allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    # Control, differing only in the stamp: the writer is recorded and mutations are offered.
    assert stamped["implementation"]["same"] is True and "collect" in [a["action"] for a in mutations(stamped)]
    assert not any("is withheld" in note for note in stamped["outstanding"])

    record = prepared.session / "session.json"
    document = json.loads(record.read_bytes())
    assert isinstance(document.get("stewart"), dict), "firing control: the record carried a stamp"
    stripped = json.dumps({key: value for key, value in document.items() if key != "stewart"}).encode()
    _rewrite(record, stripped)
    held = snapshot_tree(prepared.session)
    collect = ("--repo", checkout.repo, "--workspace", WS, "collect", "--audit-id", IDENT, "--auditor-stopped",
               "finished")
    concluded = ("--repo", checkout.repo, "--workspace", WS, "close", "--audit-id", IDENT, "--actor", "manager")
    for argv in (collect, collect, concluded):  # Invariance: each mutation refuses identically and writes nothing.
        refused = cli.refused(*argv, reason="implementation_unrecorded", code=EXIT_UNVERIFIED)
        assert refused["retained"] == [str(record)]
    assert snapshot_tree(prepared.session) == held and not (common / "stewart/closed").exists()

    view = cli(*status, allowed=(EXIT_OK, EXIT_ATTENTION, EXIT_UNVERIFIED))["result"]
    assert view["implementation"]["same"] is None and view["implementation"]["recorded"] is None
    offered = mutations(view)
    assert [action["action"] for action in offered] == ["close"] and "--abandon" in offered[0]["argv"]
    withheld = [note for note in view["outstanding"] if "is withheld" in note]
    assert any(note.startswith("collect is withheld") for note in withheld), view["outstanding"]
    assert snapshot_tree(prepared.session) == held, "status reads only"

    # The one mutation that accepts an unrecorded writer: an abandon, which keeps the stripped bytes as evidence.
    closed = cli(*concluded, "--abandon", "--reason", "the writer is unrecorded",
                 allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert closed["closed"] is not None and not prepared.session.exists()
    closing = read_json(Path(closed["closing"]))
    assert closing["identity"]["session_sha256"] == _util.sha256_bytes(stripped)


def test_a_closed_audit_takes_no_new_resource_or_use(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    used = root / "holder-dir"
    api.create_directory(checkout.ws, HOLDER, path=str(used), actor="manager")
    partner_rid = api.create_directory(checkout.ws, PARTNER, path=str(root / "partner-dir"), actor="manager")["rid"]
    _abandon(cli, checkout.repo, WS, HOLDER)
    view = cli("--repo", checkout.repo, "--workspace", WS, "status", "--audit-id", HOLDER,
               allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert view["audit_id_state"] == "reserved", "firing control: a closing record reserves the closed audit's ID"
    external = root / "external-dir"
    external.mkdir()
    late = root / "late-dir"

    def attempts(ident: str) -> list[tuple]:
        prefix = ("--repo", checkout.repo, "--workspace", WS, "resource")
        return [_create_directory(ident, late, checkout.repo),
                (*prefix, "create-branch", "--audit-id", ident, "--branch", "audit/late", "--actor", "manager"),
                (*prefix, "enroll", "--audit-id", ident, "--kind", "directory", "--path", external, "--actor",
                 "manager"),
                (*prefix, "associate", "--audit-id", ident, "--resource", partner_rid, "--actor", "manager")]

    records, closed = _tree(_records(common)), _tree(common / "stewart/closed")
    for argv in attempts(HOLDER) * 2:  # Invariance: refused identically; nothing is recorded or created.
        refused = cli.refused(*argv, reason="audit_closed")
        assert "closed" in refused["message"]
    assert _tree(_records(common)) == records and _tree(common / "stewart/closed") == closed
    assert not late.exists() and not resources._ref(checkout.repo, "refs/heads/audit/late")

    # Differing only in the audit: the same commands for an audit with no closing record are accepted.
    for argv in attempts(THIRD):
        cli(*argv)
    assert late.is_dir() and resources._ref(checkout.repo, "refs/heads/audit/late")
    shown = _show(cli, checkout.repo, partner_rid)
    assert _live(shown) == [PARTNER, THIRD]


def test_unknown_resources_and_absent_paths_are_resource_missing(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    present = root / "present-dir"
    present.mkdir()
    known = api.create_directory(checkout.ws, HOLDER, path=str(root / "known-dir"), actor="manager")["rid"]
    unknown = str(uuid.uuid4())
    assert not (_records(common) / unknown).exists(), "firing control: a well-formed identifier nothing records"
    prefix = ("--repo", checkout.repo, "--workspace", WS, "resource")
    enroll = (*prefix, "enroll", "--audit-id", PARTNER, "--actor", "manager", "--kind")
    refusals = [
        _close_resource(unknown, checkout.repo),
        _close_resource("not-a-resource-id", checkout.repo),
        ("--repo", checkout.repo, "resource", "show", "--resource", unknown),
        ("--repo", checkout.repo, "resource", "acknowledge", "--resource", unknown, "--actor", "manager"),
        (*prefix, "associate", "--audit-id", PARTNER, "--resource", unknown, "--actor", "manager"),
        (*enroll, "directory", "--path", root / "absent-dir"),
        (*enroll, "worktree", "--path", present),
        (*enroll, "branch", "--branch", "absent/branch"),
    ]
    records = _tree(_records(common))
    for argv in refusals * 2:  # Invariance: refused identically; nothing is recorded.
        cli.refused(*argv, reason="resource_missing")
    assert _tree(_records(common)) == records and _rids(common) == [known]
    assert not (root / "absent-dir").exists()

    # Differing only in existence: a recorded identifier and an existing directory are accepted.
    assert _show(cli, checkout.repo, known)["rid"] == known
    enrolled = cli(*enroll, "directory", "--path", present)["result"]
    assert sorted(_rids(common)) == sorted([known, enrolled["rid"]])


def test_noncanonical_reference_and_workspace_paths_are_refused(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    discovery._init(cli, checkout.repo, WS, DRAFT)
    reference = cli("--repo", checkout.repo, "--workspace", WS, "select", "--audit-id", DRAFT)["result"]["reference"]
    good = root / "good-ref.json"
    good.write_text(json.dumps(reference), encoding="utf-8")
    assert cli("--ref", good, "status")["result"]["workspace"]["rel"] == WS, "control: the canonical reference binds"
    late = root / "late-dir"
    records = _tree(_records(common))
    for spelling in (f"{WS}/", f"{WS.split('/')[0]}/./{WS.split('/')[1]}", WS.replace("/", "//")):
        bad = root / "bad-ref.json"
        bad.write_text(json.dumps({**reference, "workspace": spelling}), encoding="utf-8")
        cli.refused("--ref", bad, "status", reason="path_noncanonical")
        cli.refused("--ref", bad, "resource", "create-directory", "--path", late, "--actor", "manager",
                    reason="path_noncanonical")
        cli.refused(*_create_directory(DRAFT, late, checkout.repo, rel=spelling), reason="path_noncanonical")
    # Invariance: none of the refusals recorded or created anything.
    assert _tree(_records(common)) == records and not late.exists()
    # Differing only in the spelling: the canonical workspace creates the directory.
    made = cli("--ref", good, "resource", "create-directory", "--path", late, "--actor", "manager")["result"]
    assert late.is_dir() and _rids(common) == [made["rid"]]


# --- 7. a draft-only audit is abandoned once ------------------------------------------------------------------


def test_a_draft_only_audit_is_abandoned_once_and_then_takes_nothing(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    common = _common(checkout.repo)
    repo, ws = checkout.repo, checkout.ws
    drafted = discovery._init(cli, repo, WS, DRAFT)
    entry = discovery._entries(cli("--repo", repo, "discover")["result"])[(WS, DRAFT)]
    assert entry["stage"] == "draft" and entry["lifetime"] is None, "firing control: recorded only as a draft"
    abandon = ("--repo", repo, "--workspace", WS, "close", "--audit-id", DRAFT, "--actor", "manager", "--abandon",
               "--reason", "drafted in error")

    first = cli(*abandon, allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    closing = read_json(Path(first["closing"]))
    assert first["closed"] is not None and first["released"] is False and first["session_uuid"] is None
    assert closing["observed"]["drafts"] == [drafted["draft_record"]]
    view = cli("--repo", repo, "--workspace", WS, "status", "--audit-id", DRAFT,
               allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert view["audit_id_state"] == "reserved"
    assert discovery._entries(cli("--repo", repo, "discover")["result"])[(WS, DRAFT)]["stage"] == "closed"

    # Differing only in what the draft knew: it predates the close now, so it leaves nothing to abandon.
    closed, prompt = _tree(common / "stewart/closed"), (repo / ws.prompt).read_bytes()
    audits = _tree(common / "stewart/audits")
    late = root / "late-dir"
    for _ in range(2):  # Invariance: every later attempt refuses identically and writes nothing.
        cli.refused(*abandon, reason="session_missing")
        cli.refused(*_create_directory(DRAFT, late, repo), reason="audit_closed")
        cli.refused("--repo", repo, "--workspace", WS, "init", "--audit-id", DRAFT, "--input", "input.txt",
                    "--replace-prompt", reason="audit_id_reserved")
    assert _tree(common / "stewart/closed") == closed and _tree(common / "stewart/audits") == audits
    assert (repo / ws.prompt).read_bytes() == prompt and not late.exists() and _rids(common) == []


# --- 8. discovery lists a supported session that does not load as unverified ------------------------------------


def test_a_supported_session_that_does_not_load_is_unverified_and_cannot_be_selected(checkout, tmp_path, run_cmd):
    root = tmp_path.resolve()
    cli = _cli(run_cmd, root)
    repo = checkout.repo
    look = discovery.ReadOnly(cli, repo)
    prepared = api.prepare(checkout.ws, checkout.prompt_commit())
    _assigned_prompt(checkout, REGISTERED)
    api.register(checkout.ws, REGISTERED, actor="manager")
    healthy = look("--repo", repo, "discover")["result"]
    entry = discovery._entries(healthy)[(WS, IDENT)]
    assert (entry["stage"], entry["lifetime"], entry["problems"]) == ("prepared", prepared["session_uuid"], [])
    selected = look("--repo", repo, "--workspace", WS, "select", "--audit-id", IDENT)["result"]
    assert selected["reference"]["lifetime"] == prepared["session_uuid"]

    record = Path(prepared["session"]) / "session.json"
    document = json.loads(record.read_bytes())
    original = _rewrite(record, json.dumps({**document, "launch_token": "not-the-issued-token"}).encode())
    # Firing control: the envelope still parses as a supported session; only the loader rejects it.
    collect = cli.refused("--repo", repo, "--workspace", WS, "collect", "--audit-id", IDENT, "--auditor-stopped",
                          "finished", reason="session_identity", code=EXIT_UNVERIFIED)
    broken = look("--repo", repo, "discover", allowed=(EXIT_UNVERIFIED,))["result"]
    entry = discovery._entries(broken)[(WS, IDENT)]
    assert entry["session"]["supported"] is True and entry["session"]["stage"] == "prepared"
    assert (entry["stage"], entry["lifetime"]) == ("unverified", prepared["session_uuid"])
    assert [problem["reason"] for problem in entry["problems"]] == ["session_identity"]
    assert entry["problems"][0]["message"] == collect["message"], "discovery reports the loader's own refusal"
    unresolved = look.refused("--repo", repo, "--workspace", WS, "select", "--audit-id", IDENT,
                              reason="selection_unresolved", code=EXIT_UNVERIFIED)
    assert unresolved["retained"] == [prepared["session"]]
    # Invariance: the other audit's entry is listed exactly as before.
    assert discovery._entries(broken)[(WS, REGISTERED)] == discovery._entries(healthy)[(WS, REGISTERED)]

    # Differing only in the loaded field: restored, the session lists as prepared and selects again.
    _rewrite(record, original)
    assert look("--repo", repo, "discover")["result"] == healthy
    assert look("--repo", repo, "--workspace", WS, "select", "--audit-id", IDENT)["result"] == selected
