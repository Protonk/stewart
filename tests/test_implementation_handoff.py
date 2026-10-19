"""Implementation identity and explicit runtime handoff, through the installed wheel.

A record's ``stewart`` stamp names the writing package by the digest of its
member bytes, not by where it is installed. These tests stage copies of the
installed package and run each copy only through its own source bootstrap with
a private manager home, so its records carry a recorded isolated-manager
invocation. The installed wheel (in process and through its CLI) then inspects,
renders and refuses those records. A distinguishable copy carries an import-time
sentinel that appends a line to a file whenever its code is imported or run; the
copy's own runs fire it, and its line count proves the wheel never imported or
executed the copy while inspecting, rendering or refusing.

Controls: a byte-identical copy at another location is the same implementation
and is mutated normally; a copy differing in one resource byte is refused. An
in-process writer records no invocation; a damaged launcher or deployment
leaves the handoff unresolved and nothing falls back to the current
installation. Unit-level stamps with untrusted fields are rejected without any
observation outside the recorded layout, and an unsupported session schema is
listed only through its discovery envelope.
"""
from __future__ import annotations

import copy as _copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
from types import SimpleNamespace

import pytest

import stewart
from stewart import api
from stewart._bootstrap import EXIT_ATTENTION, EXIT_OK, EXIT_REFUSED, EXIT_UNVERIFIED, StewartError
from stewart._git import git_text
from stewart.session import SESSION_SCHEMA
import stewart_support as support
from stewart_support import WS, snapshot_tree
from support import stage_runtime

pytestmark = pytest.mark.system

IDENT = "one-question"
COPY_KEY = "copy-collect"
#: Status actions that only read; every other generated action is a mutation bound to the session's writer.
READ_ONLY_ACTIONS = {"triage-draft", "handoff"}
#: Appended to a copy's ``__init__.py``: every import of that package appends "<pid> <file>".
SENTINEL_SOURCE = '''

# Test sentinel: any import or execution of this copy appends one line.
import os as _sentinel_os
try:
    _sentinel_fd = _sentinel_os.open({path!r}, _sentinel_os.O_WRONLY | _sentinel_os.O_APPEND | _sentinel_os.O_CREAT,
                                     0o600)
    _sentinel_os.write(_sentinel_fd, ("%d %s\\n" % (_sentinel_os.getpid(), __file__)).encode())
    _sentinel_os.close(_sentinel_fd)
except OSError:
    pass
del _sentinel_os
'''
#: Runs a copy's CLI in process from its own source directory, never through a launcher.
IN_PROCESS = ("import sys; sys.path.insert(0, sys.argv[1]); from stewart.cli import main; "
              "raise SystemExit(main(sys.argv[2:]))")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _envelope(result, argv, allowed) -> dict:
    assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
    envelope = json.loads(result.stdout)
    assert envelope["schema"] == "stewart.result/3" and envelope["exit_code"] == result.returncode, envelope
    return envelope


class Wheel:
    """The installed wheel's CLI, one fresh isolated process per call, returning its JSON envelope."""

    def __init__(self, run_cmd, cwd: Path):
        self.run_cmd, self.cwd = run_cmd, cwd

    def __call__(self, *argv, allowed=(EXIT_OK,)) -> dict:
        command = [sys.executable, "-I", "-B", "-m", "stewart", "--json", *map(str, argv)]
        return _envelope(self.run_cmd(command, cwd=self.cwd), argv, allowed)

    def prose(self, *argv, allowed=(EXIT_OK,)) -> str:
        result = self.run_cmd([sys.executable, "-I", "-B", "-m", "stewart", *map(str, argv)], cwd=self.cwd)
        assert result.returncode in allowed, f"{argv}: {result.returncode}\n{result.stdout}\n{result.stderr}"
        return result.stdout


class Copy:
    """A staged copy of the installed package, run only through its own source bootstrap.

    ``extra`` is appended to its bundled manual, so its package digest differs
    from the wheel's; ``sentinel`` names a file its ``__init__`` appends to.
    """

    def __init__(self, tmp_path: Path, run_cmd, name: str = "copy", *, extra: bytes | None = b"",
                 sentinel: Path | None = None):
        self.run_cmd = run_cmd
        self.root = stage_runtime(tmp_path / name)
        self.package = self.root / "stewart"
        if extra:
            manual = self.package / "resources/README.md"
            manual.write_bytes(manual.read_bytes() + extra)
        if sentinel is not None:
            init = self.package / "__init__.py"
            init.write_bytes(init.read_bytes() + SENTINEL_SOURCE.format(path=str(sentinel)).encode())
        self.home = tmp_path / f"{name}-manager-home"
        self.digest = api.package_identity(self.package, source_git=False)["package_sha256"]
        self.runs = 0

    def __call__(self, *argv, cwd: Path, allowed=(EXIT_OK,)) -> dict:
        self.runs += 1
        command = [sys.executable, "-I", "-B", self.package / "_bootstrap.py", "source", "--manager-home", self.home,
                   "--", "--json", *argv]
        return _envelope(self.run_cmd(command, cwd=cwd), argv, allowed)

    def deployment(self) -> tuple[Path, str]:
        found = sorted((self.home / "deployments").iterdir())
        assert len(found) == 1, f"one retained deployment expected: {found}"
        return found[0] / "runtime", found[0].name

    @property
    def launcher(self) -> Path:
        return self.home / "launchers" / f"{_sha256(self.package / '_bootstrap.py')}.py"

    def prefix(self) -> list[str]:
        """The supported isolated-manager form for this copy's retained deployment."""
        code_root, digest = self.deployment()
        return [sys.executable, "-I", "-B", str(self.launcher), "manager", "--code-root", str(code_root),
                "--runtime-sha256", digest, "--"]


class Sentinel:
    def __init__(self, path: Path):
        self.path = path

    def lines(self) -> list[str]:
        return self.path.read_text().splitlines() if self.path.exists() else []


def _wheel_digest() -> str:
    return api.package_identity(Path(stewart.__file__).parent, source_git=False)["package_sha256"]


def _common(repo: Path) -> Path:
    return Path(git_text(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _ws_args(checkout) -> list:
    return ["--repo", checkout.repo, "--workspace", WS]


def _status_arguments(checkout) -> list[str]:
    return ["--repo", str(checkout.repo), "--workspace", WS, "status", "--audit-id", IDENT]


def _audit_by(run, checkout, *, key: str | None = COPY_KEY) -> SimpleNamespace:
    """Initialize, prepare and collect the fixture audit with ``run`` (a copy's CLI), keyed when asked."""
    ws = _ws_args(checkout)
    run(*ws, "init", "--audit-id", IDENT, "--input", "input.txt", "--replace-prompt", cwd=checkout.repo)
    revision = checkout.prompt_commit()
    prepared = run(*ws, "prepare", "--prompt-commit", revision, cwd=checkout.repo,
                   allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    Path(prepared["worktree"], checkout.meta["report_path"]).write_text("A report written under the copy.\n")
    keyed = ["--request-key", key] if key else []
    collected = run(*ws, *keyed, "collect", "--audit-id", IDENT, "--auditor-stopped", "finished", cwd=checkout.repo,
                    allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    session = Path(prepared["session"])
    return SimpleNamespace(prepared=prepared, collected=collected, session=session,
                           record=json.loads((session / "session.json").read_text()),
                           common=_common(checkout.repo))


def _entry(found: dict, ident: str = IDENT) -> dict:
    entries = [item for item in found["audits"] if item["audit_id"] == ident]
    assert len(entries) == 1, found["audits"]
    return entries[0]


def _foreign_modules(*roots: Path) -> list[str]:
    """Modules loaded in this process from any of ``roots``."""
    found = []
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and any(Path(filename).resolve().is_relative_to(root.resolve()) for root in roots):
            found.append(filename)
    return found


def _mutation_actions(view: dict) -> list[dict]:
    return [action for action in view["next_actions"]
            if action.get("argv") and action["action"] not in READ_ONLY_ACTIONS]


def _assert_rendered_with(view: dict, prefix: list[str], lifetime: str) -> None:
    """Mutation actions carry ``prefix``; read-only ones stay with the viewer's own deployment."""
    mutations = _mutation_actions(view)
    assert mutations, f"firing control: status offers at least one mutation action: {view['next_actions']}"
    for action in mutations:
        argv = action["argv"]
        assert argv[:len(prefix)] == prefix, action
        assert action["runtime"] == view["implementation"]["handoff"]["runtime"], action
        assert action["env"] == {} and action["handoff"] == "the recorded implementation; run it explicitly"
        assert argv[argv.index("--lifetime") + 1] == lifetime, action
    own = Path(os.environ["STEWART_MANAGER_HOME"])
    for action in view["next_actions"]:
        if action.get("argv") and action["action"] in READ_ONLY_ACTIONS:
            assert Path(action["argv"][3]).is_relative_to(own), f"a read stays with the viewer: {action}"


# --- 1. a distinguishable implementation: inspected and handed off, never imported or run -----------------


@pytest.mark.heavy
def test_distinguishable_copy_is_inspected_with_a_verified_handoff_and_never_imported(tmp_path, run_cmd, checkout):
    sentinel = Sentinel(tmp_path / "sentinel.log")
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n", sentinel=sentinel.path)
    wheel_digest = _wheel_digest()
    assert copy.digest != wheel_digest
    audit = _audit_by(copy, checkout)
    code_root, runtime_sha256 = copy.deployment()

    # Firing control: the copy's own runs import its code, from its retained deployment.
    fired = sentinel.lines()
    assert copy.runs == 3 and len({line.split()[0] for line in fired}) >= copy.runs, fired
    assert all(line.endswith(str(code_root / "stewart/__init__.py")) for line in fired), fired
    stamp = audit.record["stewart"]
    assert stamp["package_sha256"] == copy.digest
    assert stamp["invocation"] == {**stamp["invocation"], "route": "isolated-manager/1", "code_root": str(code_root),
                                   "launcher": str(copy.launcher), "runtime_sha256": runtime_sha256,
                                   "launcher_sha256": _sha256(copy.package / "_bootstrap.py")}
    assert stamp["invocation"]["interpreter"] == sys.executable

    expected = [*copy.prefix(), *_status_arguments(checkout)]
    wheel = Wheel(run_cmd, tmp_path)
    private = snapshot_tree(audit.common / "stewart")
    before = len(sentinel.lines())

    # In process: discovery reports a different implementation and its verified, unexecuted handoff.
    found = api.discover(checkout.repo)
    entry = _entry(found)
    assert entry["stage"] == "prepared" and entry["session"]["collections"] == 1, "a supported schema is read"
    implementation = entry["implementation"]
    assert implementation["same"] is False
    assert implementation["recorded"] == copy.digest and implementation["viewer"] == wheel_digest
    assert found["viewer"]["package_sha256"] == wheel_digest
    handoff = implementation["handoff"]
    assert handoff["state"] == "verified" and handoff["env"] == {}
    assert handoff["argv"] == expected
    assert handoff["runtime"] == {"code_root": str(code_root), "runtime_sha256": runtime_sha256,
                                  "launcher": str(copy.launcher), "launcher_sha256": copy.launcher.name[:-3],
                                  "interpreter": sys.executable, "route": "isolated-manager/1"}
    assert "authenticity" in handoff["limit"]

    # Selection binds the writer's identity; it is a reference, not permission.
    selected = api.select(checkout.repo, audit_id=IDENT, workspace=WS)["reference"]
    assert selected["implementation"] == copy.digest and selected["lifetime"] == audit.prepared["session_uuid"]

    # Status renders every mutation action with the handoff's argv; reads stay with the viewer.
    view = api.status(checkout.ws, IDENT)
    assert view["stage"] == "collected" and view["reference"]["implementation"] == copy.digest
    assert view["implementation"]["same"] is False and view["implementation"]["handoff"] == handoff
    _assert_rendered_with(view, expected[:expected.index("--") + 1], audit.prepared["session_uuid"])

    # The copy's request key is inspectable under the viewer; inspection executes nothing.
    request = api.inspect_request(checkout.repo, COPY_KEY)
    assert request["state"] == "completed" and request["outputs"][0]["name"] == audit.collected["collection"]
    shown = wheel("--repo", checkout.repo, "request", "--key", COPY_KEY, allowed=(EXIT_OK, EXIT_ATTENTION))
    assert shown["result"]["state"] == "completed" and shown["exit_code"] == request["outcome"]["exit_code"]

    # The installed CLI agrees, in JSON and in prose.
    cli_found = wheel("--repo", checkout.repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert _entry(cli_found)["implementation"]["handoff"]["argv"] == expected
    assert shlex.join(expected) in wheel.prose("--repo", checkout.repo, "discover", allowed=(EXIT_OK, EXIT_ATTENTION))
    cli_view = wheel(*_ws_args(checkout), "status", "--audit-id", IDENT, allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    assert cli_view["implementation"]["handoff"]["argv"] == expected
    _assert_rendered_with(cli_view, expected[:expected.index("--") + 1], audit.prepared["session_uuid"])

    # Inspection wrote nothing and never imported or ran the copy, in process or in the CLI's processes.
    assert snapshot_tree(audit.common / "stewart") == private
    assert len(sentinel.lines()) == before, sentinel.lines()[before:]
    assert _foreign_modules(copy.root, copy.home, Path(audit.prepared["audit_dir"])) == []


@pytest.mark.heavy
def test_mutations_under_another_implementation_are_refused_with_the_handoff_which_the_caller_runs(
        tmp_path, run_cmd, checkout):
    sentinel = Sentinel(tmp_path / "sentinel.log")
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n", sentinel=sentinel.path)
    audit = _audit_by(copy, checkout)
    expected = [*copy.prefix(), *_status_arguments(checkout)]
    prefix = expected[:expected.index("--") + 1]
    wheel = Wheel(run_cmd, tmp_path)
    private = snapshot_tree(audit.common / "stewart")
    checkout_dir = snapshot_tree(Path(audit.prepared["audit_dir"]))
    before = len(sentinel.lines())
    assert before >= copy.runs == 3, "firing control: each of the copy's own runs imports it"

    def refused_in_process(call) -> StewartError:
        with pytest.raises(StewartError) as caught:
            call()
        assert caught.value.reason == "implementation_mismatch", caught.value.to_json()
        assert caught.value.exit_code == EXIT_REFUSED
        return caught.value

    # Collect and close, in process: refused with the verified handoff, never continued here.
    for call in (lambda: api.collect(checkout.ws, IDENT, auditor_stopped="finished"),
                 lambda: api.close(checkout.ws, IDENT, actor="manager"),
                 lambda: api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="unit refusal")):
        error = refused_in_process(call)
        assert error.handoff["state"] == "verified" and error.handoff["argv"] == expected
        assert error.retained == [str(audit.session / "session.json")]
        assert any(shlex.join(expected) in step for step in error.next_steps), error.next_steps

    # The same refusals through the installed CLI carry error.handoff in stewart.result/3.
    for argv in (("collect", "--audit-id", IDENT, "--auditor-stopped", "finished"),
                 ("close", "--audit-id", IDENT, "--actor", "manager"),
                 ("close", "--audit-id", IDENT, "--actor", "manager", "--abandon", "--reason", "cli refusal")):
        refusal = wheel(*_ws_args(checkout), *argv, allowed=(EXIT_REFUSED,))["error"]
        assert refusal["reason"] == "implementation_mismatch", refusal
        assert refusal["handoff"]["state"] == "verified" and refusal["handoff"]["argv"] == expected
        assert any(shlex.join(expected) in step for step in refusal["next_steps"])

    # A retry of the copy's request key is refused too; its records are not touched or replayed.
    request = refused_in_process(lambda: api.collect(checkout.ws, IDENT, auditor_stopped="finished",
                                                     request_key=COPY_KEY))
    assert request.handoff["state"] == "verified" and request.handoff["argv"][:len(prefix)] == prefix
    keyed = wheel(*_ws_args(checkout), "--request-key", COPY_KEY, "collect", "--audit-id", IDENT,
                  "--auditor-stopped", "finished", allowed=(EXIT_REFUSED,))["error"]
    assert keyed["reason"] == "implementation_mismatch" and keyed["handoff"]["argv"][:len(prefix)] == prefix

    # Nothing was written, no collection or close was started, and the copy was never imported or run.
    assert snapshot_tree(audit.common / "stewart") == private
    assert snapshot_tree(Path(audit.prepared["audit_dir"])) == checkout_dir
    assert len(sentinel.lines()) == before, sentinel.lines()[before:]
    assert _foreign_modules(copy.root, copy.home, Path(audit.prepared["audit_dir"])) == []

    # The caller, not Stewart, runs status's rendered actions: the draft is a read under the viewer's own
    # deployment, and the triage it feeds is a mutation under the copy's retained deployment.
    view = api.status(checkout.ws, IDENT)
    drafted = next(item for item in view["next_actions"] if item["action"] == "triage-draft")
    assert drafted["argv"][:len(prefix)] != prefix
    response = json.loads(run_cmd(drafted["argv"], cwd=tmp_path, check=True).stdout)
    assert len(sentinel.lines()) == before, "a read under the viewer imports nothing of the copy"
    response.update(decision="Retain the report.", custody_gaps={key: "reviewed" for key in response["custody_gaps"]})
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(response))
    action = next(item for item in view["next_actions"] if item["action"] == "triage")
    substitutes = {"<response.json>": str(response_file), "<name>": "manager"}
    argv = [substitutes.get(token, token) for token in action["argv"]]
    assert argv[:len(prefix)] == prefix
    result = run_cmd(argv, cwd=tmp_path)
    assert result.returncode in (EXIT_OK, EXIT_ATTENTION), result.stdout + result.stderr
    triaged = list((audit.session / "triage").iterdir())
    assert len(triaged) == 1
    assert json.loads(triaged[0].read_text())["stewart"]["package_sha256"] == copy.digest
    code_root, _ = copy.deployment()
    assert sentinel.lines()[before:] and all(line.endswith(str(code_root / "stewart/__init__.py"))
                                             for line in sentinel.lines()[before:])


@pytest.mark.heavy
def test_resuming_another_implementations_unfinished_close_is_refused_and_handed_off(tmp_path, run_cmd, checkout):
    if os.geteuid() == 0:
        pytest.skip("a read-only directory does not stop removal for root; the failure would not fire")
    sentinel = Sentinel(tmp_path / "sentinel.log")
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n", sentinel=sentinel.path)
    audit = _audit_by(copy, checkout)
    expected = [*copy.prefix(), *_status_arguments(checkout)]
    prefix = expected[:expected.index("--") + 1]
    abandon = ["close", "--audit-id", IDENT, "--actor", "manager", "--abandon", "--reason", "fixture"]
    audit_dir = Path(audit.prepared["audit_dir"])
    sessions = audit.session.parent

    # The copy's own close records CLOSING.json, removes the checkout and then fails at its last item, the
    # session directory, whose parent is read-only.
    sessions.chmod(0o500)
    try:
        failed = copy(*_ws_args(checkout), *abandon, cwd=checkout.repo, allowed=(EXIT_OK, EXIT_ATTENTION))["result"]
    finally:
        sessions.chmod(0o700)
    assert failed["closed"] is None and failed["failed"], f"firing control: the close is unfinished: {failed}"
    assert [item["kind"] for item in failed["failed"]] == ["session"], failed["failed"]
    assert not audit_dir.exists() and audit.session.is_dir()
    closing = Path(failed["closing"])
    assert closing.is_file() and not (closing.parent / "CLOSED.json").exists()
    entry = _entry(api.discover(checkout.repo))
    assert entry["stage"] == "closing" and entry["implementation"]["handoff"]["argv"] == expected

    # Resumption is a mutation: the wheel refuses it, naming the recorded implementation, and writes nothing.
    private = snapshot_tree(audit.common / "stewart")
    before = len(sentinel.lines())
    with pytest.raises(StewartError) as caught:
        api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="fixture")
    assert caught.value.reason == "implementation_mismatch"
    assert caught.value.retained == [str(closing)] and caught.value.handoff["argv"] == expected
    refusal = Wheel(run_cmd, tmp_path)(*_ws_args(checkout), *abandon, allowed=(EXIT_REFUSED,))["error"]
    assert refusal["reason"] == "implementation_mismatch" and refusal["handoff"]["argv"] == expected
    assert snapshot_tree(audit.common / "stewart") == private
    assert len(sentinel.lines()) == before

    # Invariance: the same resumption under the recorded implementation, run explicitly by the caller, finishes.
    resumed = json.loads(run_cmd([*prefix, "--json", *map(str, _ws_args(checkout)), *abandon],
                                 cwd=tmp_path).stdout)["result"]
    assert resumed["resumed"] is True and resumed["closed"] == str(closing.parent / "CLOSED.json")
    assert json.loads(Path(resumed["closed"]).read_text())["stewart"]["package_sha256"] == copy.digest
    assert not audit_dir.exists() and not audit.session.exists() and len(sentinel.lines()) > before


# --- 2. the same bytes elsewhere are the same implementation ----------------------------------------------------


@pytest.mark.heavy
@pytest.mark.parametrize("variant", ["identical", "one-resource-byte"])
def test_identity_is_the_package_bytes_not_the_installation_path(tmp_path, run_cmd, checkout, variant):
    copy = Copy(tmp_path, run_cmd, "elsewhere", extra=b"." if variant == "one-resource-byte" else None)
    installed = Path(stewart.__file__).parent
    assert copy.package.resolve() != installed.resolve(), "the copy lives at another location"
    same = variant == "identical"
    assert (copy.digest == _wheel_digest()) is same
    audit = _audit_by(copy, checkout)
    assert audit.record["stewart"]["invocation"]["code_root"].startswith(str(copy.home))
    collection = audit.collected["collection"]

    entry = _entry(api.discover(checkout.repo))
    assert entry["implementation"]["same"] is same and entry["implementation"]["recorded"] == copy.digest
    assert ("handoff" in entry["implementation"]) is not same
    view = api.status(checkout.ws, IDENT)
    if same:
        # The viewer's own commands: nothing is rebound to the writer's location.
        assert all("handoff" not in action for action in view["next_actions"])
        assert all(Path(action["argv"][3]).is_relative_to(Path(os.environ["STEWART_MANAGER_HOME"]))
                   for action in _mutation_actions(view))
    else:
        _assert_rendered_with(view, copy.prefix(), audit.prepared["session_uuid"])

    def outcome(call):
        try:
            return call()
        except StewartError as exc:
            return exc

    replay = outcome(lambda: api.collect(checkout.ws, IDENT, auditor_stopped="finished", request_key=COPY_KEY))
    collected = outcome(lambda: api.collect(checkout.ws, IDENT, auditor_stopped="finished"))
    closed = outcome(lambda: api.close(checkout.ws, IDENT, actor="manager", abandon=True, reason="fixture"))
    if same:
        assert replay["state"] == "completed" and replay["replayed"] is True
        assert replay["outputs"][0]["name"] == collection
        assert collected["collection"] != collection and collected["session_uuid"] == audit.prepared["session_uuid"]
        assert closed["closed"] and not audit.session.exists()
    else:
        assert all(isinstance(item, StewartError) and item.reason == "implementation_mismatch"
                   for item in (replay, collected, closed)), (replay, collected, closed)
        assert audit.session.is_dir() and [path.name for path in (audit.session / "collections").iterdir()] == [
            collection]


# --- 3. unresolved handoffs name the missing prerequisite and never fall back --------------------------------


def _assert_unresolved(handoff: dict, missing: list[str]) -> None:
    assert handoff["state"] == "unresolved" and handoff["missing"] == missing, handoff
    assert handoff["diagnostics"] and "argv" not in handoff and "runtime" not in handoff, handoff
    own = os.environ["STEWART_MANAGER_HOME"]
    assert own not in json.dumps(handoff), "nothing names the current installation as a substitute"


def _assert_withheld(view: dict, missing: str) -> None:
    assert view["implementation"]["handoff"]["missing"] == [missing]
    assert _mutation_actions(view) == [], view["next_actions"]
    assert any(f"missing {missing}" in item for item in view["outstanding"]), view["outstanding"]


@pytest.mark.heavy
def test_an_in_process_writer_records_no_invocation_to_hand_off(tmp_path, run_cmd, checkout):
    sentinel = Sentinel(tmp_path / "sentinel.log")
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n", sentinel=sentinel.path)
    environment = {**os.environ, "STEWART_MANAGER_HOME": str(tmp_path / "in-process-manager-home")}

    def in_process(*argv, cwd, allowed=(EXIT_OK,)):
        command = [sys.executable, "-I", "-B", "-c", IN_PROCESS, copy.root, "--json", *argv]
        return _envelope(run_cmd(command, cwd=cwd, env=environment), argv, allowed)

    audit = _audit_by(in_process, checkout)
    assert "invocation" not in audit.record["stewart"] and audit.record["stewart"]["package_sha256"] == copy.digest
    fired = sentinel.lines()
    assert fired and all(line.endswith(str(copy.package / "__init__.py")) for line in fired), fired

    before = len(sentinel.lines())
    entry = _entry(api.discover(checkout.repo))
    assert entry["implementation"]["same"] is False
    _assert_unresolved(entry["implementation"]["handoff"], ["invocation"])
    _assert_withheld(api.status(checkout.ws, IDENT), "invocation")
    with pytest.raises(StewartError) as caught:
        api.collect(checkout.ws, IDENT, auditor_stopped="finished")
    assert caught.value.reason == "implementation_mismatch"
    _assert_unresolved(caught.value.handoff, ["invocation"])
    assert "missing invocation" in caught.value.next_steps[0]
    refusal = Wheel(run_cmd, tmp_path)(*_ws_args(checkout), "collect", "--audit-id", IDENT, "--auditor-stopped",
                                       "finished", allowed=(EXIT_REFUSED,))["error"]
    assert refusal["reason"] == "implementation_mismatch"
    _assert_unresolved(refusal["handoff"], ["invocation"])
    assert len(sentinel.lines()) == before
    assert _foreign_modules(copy.root) == []


def _damage_launcher_removed(copy: Copy, aside: Path):
    copy.launcher.rename(aside)
    return lambda: aside.rename(copy.launcher)


def _damage_launcher_altered(copy: Copy, aside: Path):
    original = copy.launcher.read_bytes()
    copy.launcher.write_bytes(original + b"\n# altered\n")
    return lambda: copy.launcher.write_bytes(original)


def _damage_launcher_link(copy: Copy, aside: Path):
    copy.launcher.rename(aside)
    copy.launcher.symlink_to(aside)
    return lambda: (copy.launcher.unlink(), aside.rename(copy.launcher))


def _damage_deployment_byte(copy: Copy, aside: Path):
    member = copy.deployment()[0] / "stewart/resources/README.md"
    original = member.read_bytes()
    member.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    return lambda: member.write_bytes(original)


def _damage_deployment_link(copy: Copy, aside: Path):
    member = copy.deployment()[0] / "stewart/resources/README.md"
    member.rename(aside)
    member.symlink_to(aside)
    return lambda: (member.unlink(), aside.rename(member))


def _damage_deployment_removed(copy: Copy, aside: Path):
    deployment = copy.deployment()[0].parent
    deployment.rename(aside)
    return lambda: aside.rename(deployment)


DAMAGE = {"launcher removed": (_damage_launcher_removed, "launcher"),
          "launcher altered": (_damage_launcher_altered, "launcher"),
          "launcher replaced by a link to its bytes": (_damage_launcher_link, "launcher"),
          "deployment byte altered": (_damage_deployment_byte, "runtime"),
          "deployment member replaced by a link to its bytes": (_damage_deployment_link, "runtime"),
          "deployment removed": (_damage_deployment_removed, "runtime")}


@pytest.mark.heavy
def test_damaged_launcher_or_deployment_leaves_the_handoff_unresolved_without_fallback(tmp_path, run_cmd, checkout):
    sentinel = Sentinel(tmp_path / "sentinel.log")
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n", sentinel=sentinel.path)
    audit = _audit_by(copy, checkout)
    expected = [*copy.prefix(), *_status_arguments(checkout)]
    before = len(sentinel.lines())
    assert before, "firing control: the copy's own runs import it"
    private = snapshot_tree(audit.common / "stewart")

    def verified() -> None:
        handoff = _entry(api.discover(checkout.repo))["implementation"]["handoff"]
        assert handoff["state"] == "verified" and handoff["argv"] == expected, handoff

    verified()
    own = os.environ["STEWART_MANAGER_HOME"]
    for index, (name, (damage, missing)) in enumerate(DAMAGE.items()):
        restore = damage(copy, tmp_path / f"aside-{index}")
        try:
            _assert_unresolved(_entry(api.discover(checkout.repo))["implementation"]["handoff"], [missing])
            _assert_withheld(api.status(checkout.ws, IDENT), missing)
            with pytest.raises(StewartError) as caught:
                api.collect(checkout.ws, IDENT, auditor_stopped="finished")
            assert caught.value.reason == "implementation_mismatch", name
            _assert_unresolved(caught.value.handoff, [missing])
            assert f"missing {missing}" in caught.value.next_steps[0], (name, caught.value.next_steps)
            assert not any(shlex.join(expected[:3]) in step or own in step for step in caught.value.next_steps), name
        finally:
            restore()
        # Invariance: the restored prerequisite verifies to the same argv again.
        verified()
    assert snapshot_tree(audit.common / "stewart") == private
    assert len(sentinel.lines()) == before
    assert _foreign_modules(copy.root, copy.home) == []


class _OsSpy:
    """``os`` for the handoff module, recording every path it stats or tests for access."""

    def __init__(self, seen: list):
        self._seen = seen

    def __getattr__(self, name):
        value = getattr(os, name)
        if name in ("stat", "lstat", "access", "open", "listdir", "scandir", "readlink"):
            def spy(*args, **kwargs):
                self._seen.append((name, str(args[0]) if args else None))
                return value(*args, **kwargs)
            return spy
        return value


def test_untrusted_invocation_fields_are_unresolved_without_observing_outside_the_layout(
        tmp_path, run_cmd, checkout, monkeypatch):
    import stewart.implementation as implementation
    assert api.runtime_handoff is implementation.handoff
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n")
    copy(*_ws_args(checkout), "init", "--audit-id", IDENT, "--input", "input.txt", "--replace-prompt",
         cwd=checkout.repo)
    started = list(_common(checkout.repo).glob(f"stewart/audits/*/{IDENT}/init/*/STARTED.json"))
    assert len(started) == 1
    stamp = json.loads(started[0].read_text())["stewart"]
    code_root, runtime_sha256 = copy.deployment()
    launcher, launcher_sha256 = str(copy.launcher), copy.launcher.name[:-3]
    # A planted copy of the deployment and launcher outside the copy's manager home, byte-identical to the pin.
    planted = tmp_path / "planted"
    shutil.copytree(code_root.parent, planted / "deployments" / runtime_sha256)
    (planted / "launchers").mkdir()
    shutil.copy(copy.launcher, planted / "launchers" / copy.launcher.name)

    seen: list = []
    observe, read = implementation.observe_runtime, implementation.read_regular
    monkeypatch.setattr(implementation, "observe_runtime",
                        lambda root: seen.append(("observe", str(root))) or observe(root))
    monkeypatch.setattr(implementation, "read_regular",
                        lambda location, **kwargs: seen.append(("read", str(location))) or read(location, **kwargs))
    monkeypatch.setattr(implementation, "os", _OsSpy(seen))
    arguments = ["status", "--audit-id", IDENT]

    # Firing control: the recorded stamp verifies, and only the layout and the interpreter are observed.
    offered = api.runtime_handoff(stamp, arguments)
    assert offered["state"] == "verified" and offered["argv"] == [*copy.prefix(), *arguments]
    assert {item[1] for item in seen} == {str(code_root), launcher, sys.executable}, seen

    def variant(**fields):
        changed = _copy.deepcopy(stamp)
        changed["invocation"].update(fields)
        return changed

    def replaced(value):
        changed = _copy.deepcopy(stamp)
        changed["invocation"] = value
        return changed

    def without(key):
        changed = _copy.deepcopy(stamp)
        del changed[key]
        return changed

    untrusted = {
        "no invocation recorded": without("invocation"),
        "recorded command text": replaced(shlex.join(offered["argv"])),
        "recorded argv list": replaced(offered["argv"]),
        "another route": variant(route="isolated-manager/2"),
        "source route": variant(route="source"),
        "no route": variant(route=None),
        "relative code root": variant(code_root=f"deployments/{runtime_sha256}/runtime"),
        "code root with ..": variant(code_root=f"{copy.home}/deployments/../deployments/{runtime_sha256}/runtime"),
        "code root is /": variant(code_root="/"),
        "code root with a trailing slash": variant(code_root=f"{code_root}/"),
        "code root with a NUL": variant(code_root=f"{code_root}\0"),
        "code root in another home than its launcher": variant(
            code_root=str(planted / "deployments" / runtime_sha256 / "runtime")),
        "launcher in another home than its code root": variant(
            launcher=str(planted / "launchers" / copy.launcher.name)),
        "launcher not named by its digest": variant(launcher=str(copy.home / "launchers" / "other.py")),
        "relative launcher": variant(launcher=f"launchers/{copy.launcher.name}"),
        "relative interpreter": variant(interpreter="python3"),
        "uppercase runtime digest": variant(runtime_sha256=runtime_sha256.upper()),
        "short runtime digest": variant(runtime_sha256=runtime_sha256[:63]),
        "non-hex launcher digest": variant(launcher_sha256="g" * 64),
        "runtime digest naming another deployment": variant(runtime_sha256="0" * 64),
        "launcher digest naming another launcher": variant(launcher_sha256="0" * 64),
    }
    for name, value in untrusted.items():
        seen.clear()
        result = api.runtime_handoff(value, arguments)
        assert result["state"] == "unresolved" and result["missing"] == ["invocation"], (name, result)
        assert "argv" not in result and result["diagnostics"], (name, result)
        assert seen == [], f"{name}: observed {seen}"

    # A package identity that does not verify stops before any observation, too.
    tampered = _copy.deepcopy(stamp)
    tampered["members"]["entries"][0]["sha256"] = "0" * 64
    for name, value in {"members differ from the digest": tampered,
                        "no member inventory": without("members"),
                        "another package digest": {**stamp, "package_sha256": "1" * 64}}.items():
        seen.clear()
        result = api.runtime_handoff(value, arguments)
        assert result["state"] == "unresolved" and result["missing"] == ["package_identity"], (name, result)
        assert seen == [], f"{name}: observed {seen}"

    # A well-formed invocation whose interpreter is absent is observed only within its own prerequisites.
    for interpreter in (str(tmp_path / "absent-python"), str(tmp_path)):
        seen.clear()
        result = api.runtime_handoff(variant(interpreter=interpreter), arguments)
        assert result["state"] == "unresolved" and result["missing"] == ["interpreter"], result
        assert {item[1] for item in seen} == {str(code_root), launcher, interpreter}, seen


# --- 4. an unsupported schema is listed only through its discovery envelope -------------------------------------


def _second_audit(checkout, ident: str = "other-question") -> dict:
    checkout.meta["audit_id"] = ident
    checkout.meta["report_path"] = checkout.ws.report_path(ident)
    try:
        return api.prepare(checkout.ws, checkout.prompt_commit())
    finally:
        checkout.meta["audit_id"] = IDENT
        checkout.meta["report_path"] = checkout.ws.report_path(IDENT)


def _bump_schema(session: Path) -> dict:
    """Stand in for a record written by a newer build: an unknown schema with misleading lifecycle fields."""
    location = session / "session.json"
    record = json.loads(location.read_text())
    record.update(schema_version=SESSION_SCHEMA + 1, stage="closed", lifecycle={"closed": True})
    location.write_text(json.dumps(record))
    return record


def test_unsupported_session_schema_is_listed_by_envelope_only_and_not_selected(tmp_path, run_cmd, checkout):
    prepared = support.prepared_session(checkout)
    other = _second_audit(checkout)
    common = _common(checkout.repo)
    wheel = Wheel(run_cmd, tmp_path)

    # Firing control: while the schema is supported, discovery infers the stage, lifetime and owner.
    before = api.discover(checkout.repo)
    entry = _entry(before)
    assert entry["stage"] == "prepared" and entry["lifetime"] == prepared.prepared["session_uuid"]
    assert entry["session"]["supported"] is True and entry["checkout"] == str(checkout.repo)
    assert api.select(checkout.repo, audit_id=IDENT)["reference"]["lifetime"] == prepared.prepared["session_uuid"]

    _bump_schema(prepared.session)
    private = snapshot_tree(common / "stewart")
    found = api.discover(checkout.repo)
    entry = _entry(found)
    assert entry["stage"] == "unsupported" and entry["exit_code"] == EXIT_UNVERIFIED
    assert entry["session"]["path"] == str(prepared.session) and entry["session"]["supported"] is False
    assert entry["session"]["envelope"] == {"schema": SESSION_SCHEMA + 1, "workspace": WS,
                                            "writer": _wheel_digest()}
    assert [problem["reason"] for problem in entry["problems"]] == ["session_schema_unsupported"]
    # No lifecycle state is inferred from the unknown record's other fields.
    assert entry["lifetime"] is None and entry["checkout"] is None
    assert {key: entry["session"][key] for key in ("uuid", "owner", "stage", "collections")} == dict.fromkeys(
        ("uuid", "owner", "stage", "collections"))
    assert found["exit_code"] == EXIT_UNVERIFIED

    with pytest.raises(StewartError) as caught:
        api.select(checkout.repo, audit_id=IDENT)
    assert caught.value.reason == "selection_unresolved" and caught.value.retained == [str(prepared.session)]
    assert caught.value.exit_code == EXIT_UNVERIFIED, "records this implementation cannot read do not verify"
    refusal = wheel("--repo", checkout.repo, "select", "--audit-id", IDENT, allowed=(EXIT_UNVERIFIED,))["error"]
    assert refusal["reason"] == "selection_unresolved"
    cli_entry = _entry(wheel("--repo", checkout.repo, "discover", allowed=(EXIT_UNVERIFIED,))["result"])
    assert cli_entry["stage"] == "unsupported" and cli_entry["lifetime"] is None

    # Invariance: the supported audit beside it is unaffected, and discovery wrote nothing.
    neighbour = _entry(found, "other-question")
    assert neighbour["stage"] == "prepared" and neighbour["lifetime"] == other["session_uuid"]
    assert api.select(checkout.repo, audit_id="other-question")["reference"]["lifetime"] == other["session_uuid"]
    assert snapshot_tree(common / "stewart") == private


@pytest.mark.heavy
def test_unsupported_schema_from_another_build_offers_only_its_verified_handoff(tmp_path, run_cmd, checkout):
    copy = Copy(tmp_path, run_cmd, extra=b"\nA distinguishable test implementation.\n")
    audit = _audit_by(copy, checkout, key=None)
    expected = [*copy.prefix(), *_status_arguments(checkout)]
    _bump_schema(audit.session)

    entry = _entry(api.discover(checkout.repo))
    assert entry["stage"] == "unsupported" and entry["lifetime"] is None
    assert entry["session"]["envelope"]["writer"] == copy.digest
    assert entry["implementation"]["same"] is False and entry["implementation"]["handoff"]["argv"] == expected
    with pytest.raises(StewartError) as caught:
        api.select(checkout.repo, audit_id=IDENT)
    assert caught.value.reason == "selection_unresolved"
    assert any("implementation.handoff" in step for step in caught.value.next_steps)

    # Changed property: once the launcher's bytes no longer verify, no invocation is offered.
    original = copy.launcher.read_bytes()
    copy.launcher.write_bytes(original + b"#")
    try:
        _assert_unresolved(_entry(api.discover(checkout.repo))["implementation"]["handoff"], ["launcher"])
    finally:
        copy.launcher.write_bytes(original)
    assert _entry(api.discover(checkout.repo))["implementation"]["handoff"]["argv"] == expected
