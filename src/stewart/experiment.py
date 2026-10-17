"""Optional bounded experiment execution: grant, frozen release, one-shot attempt.

Ordinary static audits need none of this. Construction permission and execution
permission stay distinct: the committed assignment carries the grant as one
``experiment`` object, the manager's release selects exact artifact bytes
inside that grant and cannot widen it, and each release authorizes exactly one
invocation. The wrapper is a narrow subprocess runner for a portable bounded
trial. It is not a sandbox, a model launcher, a native experiment framework or
an experimental designer, and it never certifies continuous preservation,
complete import provenance, in-process activity bounds or the absence of
external effects. Endpoint equality establishes the named endpoint property
and nothing more.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from stewart import _util as _hash
from stewart._git import git
from stewart._bootstrap import StewartError, capture_regular, read_regular
from stewart.ledger import POPULATIONS, measurement_problem, parse_rows, prerequisites, summarize
from stewart.session import (
    ATTEMPT_SCHEMA,
    RELEASE_SCHEMA,
    load_session,
    capture_receipt,
    now,
    read_receipt,
    record_name,
    stamp,
    tool_identity,
    write_receipt,
)
from stewart.workspace import Workspace, contained, relative
from stewart.runtime import child_command, observe_phase, record_state, require_match, runtime_state
from stewart._bootstrap import check_child_imports

GRANT_FIELDS = frozenset({
    "schema", "permission", "script", "freeze", "output_area", "protected_manifest",
    "interpreter", "environment", "cwd", "argv_template", "invocations",
})
PERMISSIONS = ("construction", "construction+execution")
#: Interpreter policies a committed prompt may name; release resolves them.
INTERPRETERS = {
    "repo-venv": "the maintainer checkout's .venv/bin/python",
    "tool-interpreter": "the interpreter running this tool",
}
#: ``minimal`` passes PATH and locale, and points HOME into the attempt.
#: Isolated child startup admits the script directory and project root explicitly.
ENVIRONMENTS = ("minimal",)
PLACEHOLDERS = ("{interpreter}", "{script}", "{root}", "{manifest}", "{output}")
GRANT_SCHEMA = "stewart.experiment-grant/2"
ROWS_NAME = "ledger.jsonl"
RECEIPT_NAME = "receipt.json"

_REVIEW_FIELDS = frozenset({"cases", "admissibility_reasoning", "static_review", "limits"})
_CASE_FIELDS = frozenset({"id", "population", "role", "expected_admission", "prediction", "measurements"})


def _under(path: str, prefixes: list[str]) -> bool:
    return any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in prefixes)


def validate_grant(grant: object, meta: dict, ws: Workspace, *, inputs_complete: bool = True) -> dict:
    """Validate grant shape and containment; never its wisdom.

    Raw prompts with a pinned inventory defer only input membership until
    assignment expansion, before preparation can allocate a session.
    """
    if not isinstance(grant, dict) or set(grant) - GRANT_FIELDS or not (GRANT_FIELDS - {"freeze"}) <= set(grant):
        raise StewartError(
            f"experiment grant fields: {sorted(GRANT_FIELDS - {'freeze'})} with optional freeze",
            reason="grant_schema",
        )
    if grant["permission"] not in PERMISSIONS:
        raise StewartError(f"experiment permission must be one of {PERMISSIONS}", reason="grant_schema")
    if grant["schema"] != GRANT_SCHEMA:
        raise StewartError(f"experiment grant schema must be {GRANT_SCHEMA}", reason="grant_schema")
    scratch = meta.get("scratch_paths", [])
    for key in ("script", "output_area"):
        if not _under(relative(grant[key]), scratch):
            raise StewartError(f"experiment {key} must sit under a declared scratch path", reason="grant_containment")
    freeze = grant.get("freeze", [])
    if not isinstance(freeze, list):
        raise StewartError("experiment freeze must be a list of paths", reason="grant_schema")
    for item in freeze:
        if not _under(relative(item), scratch):
            raise StewartError(f"frozen artifact must sit under a declared scratch path: {item}", reason="grant_containment")
    if _under(grant["script"], [grant["output_area"]]) or any(_under(item, [grant["output_area"]]) for item in freeze):
        raise StewartError("frozen artifacts must not live inside the child-writable output area", reason="grant_containment")
    inputs = list(meta.get("input_files", [])) + [item["path"] for item in meta.get("supplemental_inputs", [])]
    protected_manifest = relative(grant["protected_manifest"])
    if inputs_complete and protected_manifest not in inputs:
        raise StewartError("protected_manifest must be a pinned committed or supplemental input", reason="grant_containment")
    if grant["interpreter"] not in INTERPRETERS:
        raise StewartError(f"interpreter policy must be one of {sorted(INTERPRETERS)}", reason="grant_schema")
    if grant["environment"] not in ENVIRONMENTS:
        raise StewartError(f"environment policy must be one of {ENVIRONMENTS}", reason="grant_schema")
    if grant["cwd"] != "worktree":
        raise StewartError("cwd must be 'worktree' in the initial interface", reason="grant_schema")
    template = grant["argv_template"]
    if not isinstance(template, list) or not template or not all(isinstance(t, str) and t for t in template):
        raise StewartError("argv_template must be a nonempty list of tokens", reason="grant_schema")
    for token in template:
        if "{" in token or "}" in token:
            if token not in PLACEHOLDERS:
                raise StewartError(f"unknown placeholder {token!r}; allowed: {PLACEHOLDERS}", reason="grant_schema")
    if "{script}" not in template:
        raise StewartError("argv_template must include {script}", reason="grant_schema")
    _script_index(template)
    if grant["invocations"] != 1:
        raise StewartError("invocations must be exactly 1 in the initial interface", reason="grant_schema")
    return {**grant, "freeze": list(freeze)}


def _script_index(template: list[str]) -> int:
    """Support script-mode Python only; script arguments retain their exact order."""
    if (template.count("{interpreter}") != 1 or template.count("{script}") != 1
            or not (template[:2] == ["{interpreter}", "{script}"]
                    or template[:3] == ["{interpreter}", "-B", "{script}"])):
        raise StewartError("child argv must start with {interpreter}, optional -B, then {script}; "
                           "interpreter/script placeholders cannot repeat", reason="child_argv",
                           next_steps=["author an explicit Python-script grant; -c, -m, shell wrappers and other interpreter flags are unsupported"])
    return template.index("{script}")


def _validate_review(review: object) -> dict:
    if not isinstance(review, dict) or set(review) != _REVIEW_FIELDS:
        raise StewartError(f"review fields must be exactly {sorted(_REVIEW_FIELDS)}", reason="review_schema")
    cases = review["cases"]
    if not isinstance(cases, list) or not cases:
        raise StewartError("review must declare at least one case", reason="review_schema")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != _CASE_FIELDS:
            raise StewartError(f"each case needs exactly {sorted(_CASE_FIELDS)}", reason="review_schema")
        if not isinstance(case["id"], str) or not case["id"] or case["id"] in seen:
            raise StewartError("case ids must be unique nonempty strings", reason="review_schema")
        seen.add(case["id"])
        if case["population"] not in POPULATIONS:
            raise StewartError(f"case population must be one of {POPULATIONS}", reason="review_schema")
        if not isinstance(case["expected_admission"], bool):
            raise StewartError("expected_admission must be true or false", reason="review_schema")
        problem = measurement_problem(case["measurements"], case["expected_admission"])
        if problem:
            raise StewartError(f"case {case['id']}: {problem}", reason="review_schema")
        for key in ("role", "prediction"):
            if not isinstance(case[key], str) or not case[key].strip():
                raise StewartError(f"case {key} must be nonempty text", reason="review_schema")
    if not isinstance(review["admissibility_reasoning"], str) or not review["admissibility_reasoning"].strip():
        raise StewartError("admissibility_reasoning must be nonempty text; the tool checks it exists, not that it is right",
                           reason="review_schema")
    for key in ("static_review", "limits"):
        if not isinstance(review[key], list) or not all(isinstance(i, str) and i.strip() for i in review[key]):
            raise StewartError(f"{key} must be a list of nonempty statements", reason="review_schema")
    if not review["static_review"]:
        raise StewartError("static_review must record at least one statement", reason="review_schema")
    return review


def _frozen_digest(worktree: Path, rel: str) -> str:
    info = capture_regular(contained(worktree, rel))
    if info["kind"] != "file":
        raise StewartError(f"frozen artifact is not a readable regular file: {rel} ({info['kind']})", reason="frozen_unavailable")
    return info["sha256"]


def _read_manifest(worktree: Path, rel: str) -> dict[str, str]:
    document = read_receipt(contained(worktree, rel), what="protected manifest")
    files = document.get("files")
    if not isinstance(files, dict) or not files or not all(
        isinstance(k, str) and isinstance(v, str) and len(v) == 64 for k, v in files.items()
    ):
        raise StewartError("protected manifest must map repo-relative paths to SHA-256 digests under 'files'",
                           reason="manifest_schema")
    for path in files:
        relative(path)
    return dict(sorted(files.items()))


def _resolve_interpreter(ws: Workspace, policy: str) -> str:
    if policy == "tool-interpreter":
        return sys.executable
    candidate = ws.repo / ".venv" / "bin" / "python"
    if not candidate.is_file():
        raise StewartError(f"interpreter policy repo-venv needs {candidate}", reason="interpreter_unavailable")
    return str(candidate)


def _environment(policy: str, worktree: Path, attempt_dir: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(attempt_dir / "home"),
        "LC_ALL": "C.UTF-8",
    }


def _verify_pinned_inputs(worktree: Path, record: dict, *, reason: str) -> None:
    """Preparation's input receipts remain authoritative through release and launch."""
    changed = []
    for item in record["inputs"]:
        info = capture_regular(worktree / item["path"])
        if info.get("sha256") != item["sha256"]:
            changed.append(item["path"])
    if changed:
        raise StewartError(
            "pinned inputs differ from preparation: " + ", ".join(changed), reason=reason,
            retained=[str(worktree)],
            next_steps=["retain the changed evidence; an intentional baseline change needs a fresh assignment"],
        )


def release(ws: Workspace, ident: str, *, review: dict, actor: str) -> dict:
    """Freeze exact artifacts within the grant and record the manager's review."""
    session, record = load_session(ws, ident)
    grant = record["assignment"].get("experiment")
    if grant is None:
        raise StewartError("the assignment grants no experiment", reason="no_grant")
    grant = validate_grant(grant, record["assignment"], ws)
    if grant["permission"] != "construction+execution":
        raise StewartError("the assignment grants construction only; execution is not authorized", reason="execution_not_granted")
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError("a release needs an attributed actor", reason="actor_required")
    validated = _validate_review(review)
    name = stamp()
    runtime = runtime_state(record['runtime'])
    observe_phase(runtime, session / 'releases', 'release', directory=f'runtime-{name}')
    require_match(session / 'releases', runtime, phases={'release'})
    worktree = contained(session, "worktree")
    if not worktree.is_dir():
        raise StewartError("the worktree is gone; nothing can be released", reason="worktree_missing")
    head = git(worktree, "rev-parse", "HEAD", check=False)
    if head.returncode or head.stdout.decode().strip() != record["prompt_commit"]:
        raise StewartError("the worktree HEAD is not the prompt commit; collect the unexpected commit first",
                           reason="checkout_identity")
    _verify_pinned_inputs(worktree, record, reason="pinned_input_changed")
    frozen = {grant["script"]: _frozen_digest(worktree, grant["script"])}
    for item in grant["freeze"]:
        frozen[item] = _frozen_digest(worktree, item)
    frozen[grant["protected_manifest"]] = _frozen_digest(worktree, grant["protected_manifest"])
    manifest = _read_manifest(worktree, grant["protected_manifest"])
    observed = _hash_protected(worktree, manifest)
    drift = [rel for rel in manifest if observed[rel] != manifest[rel]]
    if drift:
        raise StewartError("protected state differs from the pinned manifest: " + ", ".join(drift),
                           reason="protected_baseline_mismatch", retained=[str(worktree)])
    output = contained(worktree, grant["output_area"])
    if output.exists():
        # A consumed release leaves its output area behind on purpose: the bytes
        # there are evidence until a collection has captured them. The cost of a
        # failed attempt is therefore a manual step, named here rather than hidden.
        raise StewartError(f"output area already exists; release needs a fresh destination: {grant['output_area']}",
                           reason="destination_exists", retained=[str(output)],
                           next_steps=["collect the worktree so the existing output area is captured, verify the "
                                       "attempt's retained copies, then move or remove that directory by hand; "
                                       "Stewart never deletes it",
                                       "or assign a fresh audit ID whose grant names a new output area"])
    attempt_dir = session / "attempts" / name
    interpreter = _resolve_interpreter(ws, grant["interpreter"])
    substitutions = {
        "{interpreter}": interpreter, "{script}": grant["script"], "{root}": str(worktree),
        "{manifest}": grant["protected_manifest"], "{output}": grant["output_area"],
    }
    argv = [substitutions.get(token, token) for token in grant["argv_template"]]
    child = child_command(record["runtime"], interpreter=interpreter, worktree=worktree, script=grant["script"],
                          script_sha256=frozen[grant["script"]], arguments=argv[_script_index(grant["argv_template"]) + 1:])
    check_child_imports(child["project_paths"])
    document = {
        "schema_version": RELEASE_SCHEMA,
        "name": name,
        "recorded_at": now().isoformat(),
        "audit_id": ident,
        "workspace": ws.rel,
        "actor": actor,
        "prompt_commit": record["prompt_commit"],
        "grant": grant,
        "grant_sha256": _hash.sha256_canonical_json(grant),
        "frozen": frozen,
        "manifest_files": len(manifest),
        "interpreter": interpreter,
        "environment": _environment(grant["environment"], worktree, attempt_dir),
        "cwd": str(worktree),
        "approved_argv": argv,
        "argv": child["argv"],
        "child": child,
        "output_area": grant["output_area"],
        "rows": f"{grant['output_area']}/{ROWS_NAME}",
        "child_receipt": f"{grant['output_area']}/{RECEIPT_NAME}",
        "review": validated,
        "invocations": 1,
        "runtime": runtime,
        "attempt": str(attempt_dir),
        "output_area_policy": "run creates the output area empty, and the attempt HOME outside it, before launch; "
                              "the child must accept an existing empty directory",
        "stewart": tool_identity(),
    }
    (session / "releases").mkdir(mode=0o700, exist_ok=True)
    location = session / "releases" / f"{name}.json"
    write_receipt(location, document)
    return {"audit_id": ident, "release": name, "path": str(location), "record": document}


def _stop(process: subprocess.Popen) -> None:
    """Stop the child through its process group; descendants outside it are not claimed."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _hash_protected(worktree: Path, manifest: dict[str, str]) -> dict[str, str | None]:
    observed: dict[str, str | None] = {}
    for rel in manifest:
        try:
            info = capture_regular(contained(worktree, rel))
        except StewartError:
            info = {"kind": "unsupported"}
        observed[rel] = info.get("sha256") if info["kind"] == "file" else None
    return observed


def _capture_output(worktree: Path, rel: str, destination: Path) -> tuple[dict, bytes | None]:
    """Keep the exact regular-file bytes parsed by the wrapper, independently of the child.

    Unavailable or special outputs are observations, not blocking path reads.
    The private destination is exclusive and never replaced by a retry.
    """
    try:
        location = contained(worktree, rel)
        info, data = read_regular(location)
    except StewartError as exc:
        info, data = {"kind": "unsupported", "detail": str(exc)}, None
    captured = {"source": rel, **info, "retained": None}
    if data is not None:
        with destination.open("xb") as stream:
            stream.write(data)
        captured["retained"] = str(destination)
    return captured, data


def run(ws: Workspace, ident: str, *, release: str, timeout: float | None = None) -> dict:
    """Consume one release exactly once; record launch, outcome, endpoints and rows independently."""
    session, record = load_session(ws, ident)
    name = record_name(release, what="release")
    location = contained(session, f"releases/{name}.json")
    document, release_digest = capture_receipt(location, what="release record")
    if document.get("schema_version") != RELEASE_SCHEMA or document.get("audit_id") != ident:
        raise StewartError("release record has an unsupported schema or belongs to another audit", reason="release_schema")
    child = document.get("child")
    if (not isinstance(child, dict) or set(child) != {"schema", "launcher", "project_paths", "ledger", "argv"}
            or not isinstance(child["launcher"], dict)
            or not isinstance(document.get("approved_argv"), list)
            or not all(isinstance(token, str) for token in document["approved_argv"])):
        raise StewartError("release lacks its child invocation binding", reason="release_schema", retained=[str(location)])
    attempts = session / "attempts"
    attempts.mkdir(mode=0o700, exist_ok=True)
    attempt_dir = attempts / name
    try:
        attempt_dir.mkdir(mode=0o700)
    except FileExistsError:
        raise StewartError(
            f"release {name} is already consumed; another attempt needs a new release consistent with the assignment",
            reason="release_consumed", retained=[str(attempt_dir)],
        ) from None
    reserved_at = now().isoformat()
    write_receipt(attempt_dir / "RESERVED.json", {"reserved_at": reserved_at, "release": name, "audit_id": ident})
    errors: list[str] = []
    result: dict = {
        "schema_version": ATTEMPT_SCHEMA,
        "name": name,
        "release": name,
        "release_sha256": release_digest,
        "audit_id": ident,
        "workspace": ws.rel,
        "reserved_at": reserved_at,
        "prompt_commit": record["prompt_commit"],
        "target_commit": record["target_commit"],
        "errors": errors,
        "process": {"launched": False, "argv": document["argv"], "cwd": document["cwd"], "started_at": None,
                    "finished_at": None, "exit_code": None, "signal": None, "timed_out": False, "interrupted": False},
        "approved_argv": document["approved_argv"],
        "child": document["child"],
        "endpoint": {"compared": 0, "changed": [], "baseline_matched_manifest": None, "preserved": None,
                     "claim": "named protected files byte-identical at launch and after exit; nothing in between"},
        "child_receipt": {"path": document["child_receipt"], "state": "absent"},
        "ledger": None,
        "stdout": str(attempt_dir / "stdout.txt"),
        "stderr": str(attempt_dir / "stderr.txt"),
        # The wrapper, not the child, creates the output area; a child that
        # requires its absence fails on entry, and this field says why.
        "output_area": {"path": document["output_area"], "created_by_wrapper": False,
                        "home": document["environment"]["HOME"]},
        "stewart": tool_identity(),
        "runtime": runtime_state(record['runtime']),
        "runtime_assets": record['runtime_assets'],
    }
    worktree = Path(document["cwd"])
    refusal: StewartError | None = None
    try:
        observe_phase(result['runtime'], attempt_dir, 'before')
        released_runtime = record_state(document, session_record=record)
        require_match(session / 'releases', released_runtime, phases={'release'})
        require_match(attempt_dir, result['runtime'], phases={'before'})
        if not worktree.is_dir():
            raise StewartError("the worktree is gone; the release cannot run", reason="worktree_missing")
        head = git(worktree, "rev-parse", "HEAD", check=False)
        if head.returncode or head.stdout.decode().strip() != record["prompt_commit"]:
            raise StewartError("the worktree HEAD is not the prompt commit", reason="release_invalidated")
        grant = record["assignment"].get("experiment")
        if (grant is None or document["grant"] != grant
                or _hash.sha256_canonical_json(grant) != document["grant_sha256"]):
            raise StewartError("the assignment's grant no longer matches the release", reason="release_invalidated")
        grant = validate_grant(grant, record["assignment"], ws)
        substitutions = {"{interpreter}": document["interpreter"], "{script}": grant["script"],
                         "{root}": str(worktree), "{manifest}": grant["protected_manifest"], "{output}": grant["output_area"]}
        approved = [substitutions.get(token, token) for token in grant["argv_template"]]
        child_binding = child_command(record["runtime"], interpreter=document["interpreter"], worktree=worktree,
                                      script=grant["script"], script_sha256=document["frozen"][grant["script"]],
                                      arguments=approved[_script_index(grant["argv_template"]) + 1:],
                                      launcher=document["child"]["launcher"])
        if (approved != document["approved_argv"] or child_binding != document["child"]
                or child_binding["argv"] != document["argv"]):
            raise StewartError("child invocation differs from the released bindings", reason="release_invalidated")
        check_child_imports(child_binding["project_paths"])
        for rel, digest in document["frozen"].items():
            observed = capture_regular(contained(worktree, rel))
            if observed.get("sha256") != digest:
                raise StewartError(f"frozen artifact changed since release: {rel}", reason="release_invalidated")
        output = contained(worktree, document["output_area"])
        if output.exists():
            raise StewartError("output area is no longer fresh", reason="release_invalidated")
        manifest = _read_manifest(worktree, grant["protected_manifest"])
        before = _hash_protected(worktree, manifest)
        result["endpoint"]["compared"] = len(manifest)
        drift = sorted(rel for rel, digest in manifest.items() if before[rel] != digest)
        result["endpoint"]["baseline_matched_manifest"] = not drift
        if drift:
            result["endpoint"]["changed"] = drift
            raise StewartError("protected state differs from the manifest before launch: " + ", ".join(drift),
                               reason="release_invalidated")
        _verify_pinned_inputs(worktree, record, reason="release_invalidated")
        output.mkdir(parents=True)
        result["output_area"]["created_by_wrapper"] = True
        home = Path(document["environment"]["HOME"])
        home.mkdir(parents=True, exist_ok=True)
        process = result["process"]
        with (attempt_dir / "stdout.txt").open("xb") as out, (attempt_dir / "stderr.txt").open("xb") as err:
            process["started_at"] = now().isoformat()
            child = subprocess.Popen(
                document["argv"], cwd=worktree, env=document["environment"], stdin=subprocess.DEVNULL,
                stdout=out, stderr=err, start_new_session=True,
            )
            process["launched"] = True
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process["timed_out"] = True
                _stop(child)
            except KeyboardInterrupt:
                process["interrupted"] = True
                _stop(child)
            process["finished_at"] = now().isoformat()
        code = child.returncode
        if code is not None and code < 0:
            process["signal"] = -code
        else:
            process["exit_code"] = code
        if process["timed_out"]:
            errors.append(f"child stopped after {timeout}s timeout")
        if process["interrupted"]:
            errors.append("attempt interrupted; child stopped")
        if process["signal"] is not None:
            errors.append(f"child terminated by signal {process['signal']}")
        elif code:
            errors.append(f"child exited {code}")
        after = _hash_protected(worktree, manifest)
        changed = sorted(rel for rel in manifest if after[rel] != before[rel])
        result["endpoint"]["changed"] = changed
        result["endpoint"]["preserved"] = not changed
        if changed:
            errors.append("protected state changed across the attempt: " + ", ".join(changed))
        captured, data = _capture_output(worktree, document["child_receipt"], attempt_dir / "child-receipt.json")
        result["child_receipt"]["capture"] = captured
        if data is not None:
            try:
                parsed = json.loads(data)
                result["child_receipt"].update(state="parsed", keys=sorted(parsed) if isinstance(parsed, dict) else None,
                                               sha256=captured["sha256"])
            except (OSError, ValueError, RecursionError) as exc:
                result["child_receipt"].update(state="malformed", detail=str(exc))
                errors.append("child receipt is malformed")
        elif captured["kind"] != "missing":
            result["child_receipt"]["state"] = "unsupported"
            errors.append("child receipt is not a readable regular file: " + captured.get("detail", captured["kind"]))
        captured, data = _capture_output(worktree, document["rows"], attempt_dir / ROWS_NAME)
        rows, problems = parse_rows(data) if data is not None else (
            [], [{"line": 0, "problem": "ledger capture unavailable: " + captured.get("detail", captured["kind"])}])
        summary = summarize(rows, cases=document["review"]["cases"])
        unmet = prerequisites(summary)
        if problems:
            unmet.append(f"{len(problems)} ledger line(s) malformed or unavailable")
        # A fired control is the expected outcome, so the mismatching-case lists
        # sit beside the anomalies rather than among them.
        result["ledger"] = {"rows_path": document["rows"], "rows": len(rows), "malformed": problems,
                            "capture": captured,
                            "summary": summary["populations"],
                            "mismatching_cases": summary["mismatching_cases"],
                            "anomalies": {k: v for k, v in summary.items()
                                          if k not in ("populations", "mismatching_cases")},
                            "unmet": unmet}
        if problems:
            errors.append(f"{len(problems)} ledger line(s) malformed or absent")
    except StewartError as exc:
        errors.append(str(exc))
        refusal = exc
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    try:
        observe_phase(result['runtime'], attempt_dir, 'after')
        require_match(attempt_dir, result['runtime'], phases={'before', 'after'})
    except (StewartError, OSError) as exc:
        errors.append(f'runtime observation: {exc}')
    # Capture stream identities even after a handled launch failure. Handoff
    # reads these retained files, never mutable output paths in the worktree.
    result["streams"] = {name: capture_regular(attempt_dir / name) for name in ("stdout.txt", "stderr.txt")}
    write_receipt(attempt_dir / "ATTEMPT.json", result)
    if refusal is not None and not result["process"]["launched"]:
        raise StewartError(str(refusal), reason=refusal.reason, retained=[str(attempt_dir)],
                           next_steps=["a changed launched assignment needs a fresh audit ID and prompt-only commit; "
                                       "another attempt needs a new release"])
    return {"audit_id": ident, "attempt": name, "path": str(attempt_dir), "record": result, "errors": errors}
