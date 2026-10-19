"""Assignment metadata: the one ``audit-assignment`` block inside the prompt.

The tool checks declared structure and byte identities. The maintainer owns the
question, the decision it informs, source selection and the completeness of any
grant; none of that is validated here, and the auditor reads the prose, not the
tool.
"""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from stewart import _util as _hash
from stewart._bootstrap import StewartError, capture_regular, read_regular, write_exclusive
from stewart._git import git, git_text, resolve_commit
from stewart._json import loads_control
from stewart.workspace import Workspace, contained, relative

SECTIONS = ("Question", "Decision", "Scope and exclusions", "Evidence", "Stop condition")
FENCE = "audit-assignment"
UNASSIGNED_MARKER = "**UNASSIGNED — complete the five sections and remove this line before launch.**"

REQUIRED_FIELDS = frozenset({"audit_id", "target_commit", "report_path", "input_files"})
OPTIONAL_FIELDS = frozenset(
    {"base_commit", "external_sources", "supplemental_inputs", "scratch_paths", "experiment", "input_manifest"}
)


def audit_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", value):
        raise StewartError(
            "audit_id must be 1–80 lowercase letters, digits, or hyphens", reason="audit_id",
        )
    return value


def prompt_metadata(text: str, ws: Workspace) -> dict:
    """Parse and validate a committed or drafted prompt's metadata and sections."""
    if re.search(r"^\*\*UNASSIGNED\b", text, re.M):
        raise StewartError(
            "PROMPT.md is unassigned; replace the entire stub before preparing an audit",
            reason="unassigned_prompt",
        )
    blocks = re.findall(rf"^```{FENCE}\s*\n(.*?)^```\s*$", text, re.M | re.S)
    if len(blocks) != 1:
        raise StewartError(
            f"PROMPT.md needs exactly one {FENCE} JSON block", reason="assignment_schema",
        )
    try:
        raw = loads_control(blocks[0])
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"assignment block is not valid JSON: {exc}", reason="assignment_schema") from exc
    meta = assignment_metadata(raw, ws)
    for title in SECTIONS:
        match = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not match or not match[1].strip():
            raise StewartError(
                f"assignment needs a nonempty '## {title}' section", reason="assignment_sections",
            )
    if meta.get("experiment") is not None:
        match = re.search(r"^## Experiment authorization\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not match or not match[1].strip():
            raise StewartError(
                "an experiment grant needs a nonempty '## Experiment authorization' section; "
                "the auditor reads that prose and the tool validates only the grant object",
                reason="assignment_sections",
            )
    return meta


def assignment_metadata(meta: object, ws: Workspace, *, manifest_expanded: bool = False) -> dict:
    """Validate assignment shape; a pinned manifest's population is checked on expansion."""
    if (
        not isinstance(meta, dict)
        or not REQUIRED_FIELDS <= meta.keys()
        or meta.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS
    ):
        raise StewartError(
            f"assignment fields: required {sorted(REQUIRED_FIELDS)}, optional {sorted(OPTIONAL_FIELDS)}",
            reason="assignment_schema",
        )
    ident = audit_id(meta["audit_id"])
    if meta["report_path"] != ws.report_path(ident):
        raise StewartError(
            f"report_path must be the unique {ws.reports}/<audit-id>.md path", reason="assignment_schema",
        )
    for key in ("input_files", "external_sources", "supplemental_inputs", "scratch_paths"):
        meta.setdefault(key, [])
        if not isinstance(meta[key], list):
            raise StewartError(f"{key} must be a list", reason="assignment_schema")
    for item in meta["input_files"]:
        relative(item)
    for item in meta["scratch_paths"]:
        if not relative(item).startswith(ws.scratch_prefix(ident)):
            raise StewartError(
                f"scratch_paths must be below {ws.scratch_prefix(ident)}", reason="assignment_schema",
            )
    if "input_manifest" in meta:
        pin = meta["input_manifest"]
        if (not isinstance(pin, dict) or set(pin) != {"path", "sha256"}
                or not isinstance(pin["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])):
            raise StewartError("input_manifest needs exactly path and full SHA-256", reason="input_manifest")
        relative(pin["path"])
    for source in meta["external_sources"]:
        if not isinstance(source, dict) or set(source) != {"url", "purpose"}:
            raise StewartError("each external source needs exactly url and purpose", reason="assignment_schema")
        if not isinstance(source["url"], str):
            raise StewartError("external source url must be a string", reason="assignment_schema")
        parsed = urlsplit(source["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise StewartError(
                "external sources must be public HTTPS URLs without credentials", reason="assignment_schema",
            )
        if not isinstance(source["purpose"], str) or not source["purpose"].strip():
            raise StewartError(
                "external sources need a purpose; maintainer verifies authority under the assigned policy",
                reason="assignment_schema",
            )
    for item in meta["supplemental_inputs"]:
        if (not isinstance(item, dict) or not {"path", "sha256", "provenance"} <= item.keys()
                or item.keys() - {"path", "sha256", "provenance", "custody"}):
            raise StewartError(
                "supplemental inputs need path, sha256, provenance and optional package custody", reason="assignment_schema",
            )
        relative(item["path"])
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise StewartError("supplemental input sha256 must be a full SHA-256 digest", reason="assignment_schema")
        if not isinstance(item["provenance"], str) or not item["provenance"].strip():
            raise StewartError("supplemental inputs need provenance", reason="assignment_schema")
        if "custody" in item:
            from stewart.handoff import validate_custody

            validate_custody(item["custody"])
    inputs = meta["input_files"] + [item["path"] for item in meta["supplemental_inputs"]]
    if len(inputs) != len(set(inputs)):
        raise StewartError("input paths must be unique", reason="assignment_schema")
    if not inputs and not meta["external_sources"] and "input_manifest" not in meta:
        raise StewartError("assignment has no inputs or external sources", reason="assignment_schema")
    if "experiment" in meta:
        # The grant is tool-facing; its validator lives with the wrapper it governs.
        from stewart.experiment import validate_grant

        meta["experiment"] = validate_grant(
            meta["experiment"], meta, ws, inputs_complete="input_manifest" not in meta or manifest_expanded,
        )
    return meta


def expected_inputs(repo: Path, meta: dict, revision: str) -> list[dict]:
    """Resolve expected digests from Git and the assignment, never from live inputs.

    Both preparation and the auditor verifier use this population. Observing
    working bytes is a separate operation so a missing input cannot disappear
    from the verifier's denominator.
    """
    receipts = []
    for rel in meta["input_files"]:
        entry = git_text(repo, "ls-tree", revision, "--", rel)
        if not entry.startswith(("100644 blob ", "100755 blob ")):
            raise StewartError(f"input_files must name committed regular files: {rel}", reason="input_missing")
        data = git(repo, "show", f"{revision}:{rel}").stdout
        receipts.append({"path": rel, "sha256": _hash.sha256_bytes(data), "kind": "committed"})
    for item in meta["supplemental_inputs"]:
        if git(repo, "cat-file", "-e", f"{revision}:{item['path']}", check=False).returncode == 0:
            raise StewartError(
                f"supplemental input collides with a committed path: {item['path']}", reason="input_collision",
            )
        receipts.append(dict(item, kind="supplemental"))
    output_paths = [meta["report_path"], *meta["scratch_paths"]]
    if any(
        item["path"] == output or item["path"].startswith(output + "/") or output.startswith(item["path"] + "/")
        for item in receipts
        for output in output_paths
    ):
        raise StewartError("input paths and writable output paths must not overlap", reason="input_overlap")
    return receipts


def observe_inputs(repo: Path, receipts: Sequence[dict]) -> list[dict]:
    """Read each declared file without following links; retain every failed row.

    This observes bytes at read time, not a continuous preservation interval,
    permission compliance, or whether an auditor has understood a file.
    """
    rows = []
    for item in receipts:
        relative(item["path"])
        info = capture_regular(repo / item["path"])
        rows.append({"path": item["path"], "kind": item["kind"], "expected_sha256": item["sha256"],
                     "observed_sha256": info.get("sha256"), "observed_kind": info["kind"],
                     "observed_detail": info.get("detail"),
                     "matches": info["kind"] == "file" and info.get("sha256") == item["sha256"]})
    return rows


def input_receipts(repo: Path, meta: dict, revision: str) -> list[dict]:
    """Validate selected supplemental bytes while committed inputs come from Git."""
    from stewart.handoff import verify_packaged_inputs

    verify_packaged_inputs(repo, meta["supplemental_inputs"])
    receipts = expected_inputs(repo, meta, revision)
    for row in observe_inputs(repo, [r for r in receipts if r["kind"] == "supplemental"]):
        if not row["matches"]:
            raise StewartError(f"missing or mismatched supplemental input: {row['path']} ({row['observed_kind']})",
                               reason="input_mismatch")
    return receipts


def manifest_document(meta: dict) -> dict:
    """Factor shared provenance out of per-file entries without losing custody."""
    provenance = {}
    entries = []
    for item in meta.get("supplemental_inputs", []):
        description = item["provenance"]
        key = next((k for k, v in provenance.items() if v == description), None)
        if key is None:
            key = f"source-{len(provenance) + 1}"
            provenance[key] = description
        entries.append({**item, "provenance": key})
    return {"schema": "stewart.inputs/1", "input_files": meta["input_files"],
            "provenance": provenance, "supplemental_inputs": entries}


def expand_input_manifest(ws: Workspace, meta: dict) -> dict:
    """Resolve one pinned inventory, then validate the combined input population.

    Manifests cannot recurse. Their own bytes are a supplemental input, so they
    are copied and captured just like the selected data. They must not collide
    with a committed path, writable path, or a member of their own population.
    """
    if "input_manifest" not in meta:
        return meta
    pin = meta["input_manifest"]
    info, payload = read_regular(ws.repo / pin["path"])
    if payload is None or info.get("sha256") != pin["sha256"]:
        raise StewartError(f"input manifest expected {pin['sha256']}, observed {info}: {pin['path']}",
                           reason="input_manifest", next_steps=["preserve the changed inventory; restore its pinned bytes or author a fresh assignment"])
    try:
        doc = loads_control(payload)
    except (ValueError, RecursionError) as exc:
        raise StewartError(f"invalid input manifest: {exc}", reason="input_manifest") from exc
    if (not isinstance(doc, dict) or set(doc) != {"schema", "input_files", "provenance", "supplemental_inputs"}
            or doc["schema"] != "stewart.inputs/1" or not isinstance(doc["input_files"], list)
            or not isinstance(doc["supplemental_inputs"], list) or not isinstance(doc["provenance"], dict)
            or not all(isinstance(k, str) and k and isinstance(v, str) and v.strip() for k, v in doc["provenance"].items())):
        raise StewartError("input manifest requires schema stewart.inputs/1, input_files, provenance and supplemental_inputs",
                           reason="input_manifest")
    entries = []
    for item in doc["supplemental_inputs"]:
        if not isinstance(item, dict) or not isinstance(item.get("provenance"), str) or item["provenance"] not in doc["provenance"]:
            raise StewartError("manifest member needs a declared provenance key", reason="input_manifest")
        entries.append({**item, "provenance": doc["provenance"][item["provenance"]]})
    expanded = {**meta, "input_files": [*meta["input_files"], *doc["input_files"]],
                "supplemental_inputs": [*meta["supplemental_inputs"], *entries]}
    if not expanded["input_files"] and not expanded["supplemental_inputs"] and not meta["external_sources"]:
        raise StewartError("input inventory cannot serve as its own only evidence", reason="input_manifest")
    expanded["supplemental_inputs"].append({**pin, "provenance": "Input inventory pinned by the assignment"})
    return assignment_metadata(expanded, ws, manifest_expanded=True)


def draft(meta: dict) -> str:
    """The unassigned stub: metadata filled, prose sections empty, marker present."""
    sections = list(SECTIONS)
    if meta.get("experiment") is not None:
        sections.append("Experiment authorization")
    return (
        "# Audit assignment\n\n"
        f"{UNASSIGNED_MARKER}\n\n"
        + "\n\n".join(f"## {title}" for title in sections) + "\n\n"
        + f"## Assignment metadata\n\n```{FENCE}\n" + json.dumps(meta, indent=2) + "\n```\n"
    )


def initialize(
    ws: Workspace,
    ident: str,
    target: str,
    *,
    inputs: Sequence[str],
    base: str | None = None,
    sources: Sequence[tuple[str, str]] = (),
    supplemental: Sequence[tuple[str, str]] = (),
    evidence_packages: Sequence[str] = (),
    scratch: Sequence[str] = (),
    experiment: dict | None = None,
    input_manifest: str | None = None,
    replace_prompt: bool = False,
    request_key: str | None = None,
) -> dict:
    """Generate clerical fields; leave the question unassigned for human authoring.

    Every selected input is resolved and validated before an existing prompt is
    replaced. Without ``replace_prompt`` nothing is written, so the result can be
    inspected first. With it, a repository-level draft record states the
    intended writes before they happen and their outcome after.
    """
    from stewart._repository import maintainer
    from stewart.request_keys import file_digest, input_digest, keyed
    maintainer(ws.repo)
    if request_key is not None and not replace_prompt:
        raise StewartError("a preview writes nothing; a request key applies only with --replace-prompt", reason="usage")
    # Supplied bytes are bound by digest, and revisions as the commits they resolve to now.
    requested = {} if request_key is None else {
        "audit_id": ident, "target": resolve_commit(ws.repo, target, exact=False),
        "base": None if base is None else resolve_commit(ws.repo, base, exact=False),
        "inputs": list(inputs), "sources": [list(item) for item in sources],
        "supplemental": [[rel, provenance, file_digest(contained(ws.repo, rel))] for rel, provenance in supplemental],
        "evidence_packages": [[rel, file_digest(contained(ws.repo, rel))] for rel in evidence_packages],
        "scratch": list(scratch), "experiment": None if experiment is None else input_digest(experiment),
        "input_manifest": input_manifest, "replace_prompt": replace_prompt}
    selected = list(inputs)
    return keyed(ws, ident, "init", requested, request_key,
                 lambda plan: _initialize(ws, ident, target, inputs=selected, base=base, sources=sources,
                                          supplemental=supplemental, evidence_packages=evidence_packages,
                                          scratch=scratch, experiment=experiment, input_manifest=input_manifest,
                                          replace_prompt=replace_prompt, request_key=request_key, plan=plan),
                 outputs=lambda result: [{"kind": "draft-record", "path": result["draft_record"]},
                                         *({"kind": "written", "path": item["path"], "sha256": item["sha256"]}
                                           for item in result["written_files"])])


def _initialize(ws: Workspace, ident: str, target: str, *, inputs: Sequence[str], base: str | None,
                sources: Sequence[tuple[str, str]], supplemental: Sequence[tuple[str, str]],
                evidence_packages: Sequence[str], scratch: Sequence[str], experiment: dict | None,
                input_manifest: str | None, replace_prompt: bool, request_key: str | None, plan) -> dict:
    from stewart._repository import maintainer
    maintainer(ws.repo)
    repo = ws.repo
    ident = audit_id(ident)
    target = resolve_commit(repo, target, exact=False)
    meta: dict = {
        "audit_id": ident, "target_commit": target,
        "report_path": ws.report_path(ident), "input_files": list(inputs),
    }
    if base is not None:
        meta["base_commit"] = resolve_commit(repo, base, exact=False)
    if sources:
        meta["external_sources"] = [{"url": url, "purpose": purpose} for url, purpose in sources]
    if supplemental or evidence_packages:
        meta["supplemental_inputs"] = []
        for rel, provenance in supplemental:
            source = contained(repo, rel)
            info, data = read_regular(source)
            if data is None:
                raise StewartError(f"supplemental input must be a regular file: {rel}", reason="input_missing")
            meta["supplemental_inputs"].append(
                {"path": rel, "sha256": info["sha256"], "provenance": provenance}
            )
        from stewart.handoff import package_inputs

        for manifest in evidence_packages:
            meta["supplemental_inputs"].extend(package_inputs(repo, manifest))
    meta["scratch_paths"] = list(scratch) or [ws.scratch_prefix(ident) + "notes"]
    if experiment is not None:
        meta["experiment"] = experiment
    validated = assignment_metadata(loads_control(json.dumps(meta)), ws)
    input_receipts(repo, validated, target)
    for name in ws.guidance_files():
        if name == ws.prompt:
            continue
        if not contained(repo, name).is_file():
            raise StewartError(
                f"workspace is missing its guidance file {name}; initialize a workspace that carries "
                "auditor and maintainer guidance", reason="workspace_guidance",
            )
    from stewart._repository import maintainer, registered_session, session_location
    from stewart.close import require_fresh_audit_id
    common = maintainer(repo)["common_dir"]
    session = session_location(common, ws, ident)
    require_fresh_audit_id(common, ws, ident)
    if not session.exists():
        registered_session(common, session)
    if session.exists() or contained(repo, meta["report_path"]).exists():
        raise StewartError(
            "session or report destination already exists; choose a fresh audit ID",
            reason="destination_exists",
        )
    manifest = None
    if input_manifest is not None:
        relative(input_manifest)
        if input_manifest in [r["path"] for r in expected_inputs(repo, validated, target)]:
            raise StewartError("manifest destination collides with an input", reason="input_overlap")
        if any(input_manifest == p or input_manifest.startswith(p + "/") or p.startswith(input_manifest + "/")
               for p in [meta["report_path"], *meta["scratch_paths"]]):
            raise StewartError("manifest destination overlaps writable output", reason="input_overlap")
        if git(repo, "cat-file", "-e", f"{target}:{input_manifest}", check=False).returncode == 0:
            raise StewartError("input manifest must be uncommitted supplemental material", reason="input_collision")
        location = contained(repo, input_manifest)
        if location.exists():
            raise StewartError("input manifest destination exists; choose a fresh path", reason="destination_exists")
        document = manifest_document(meta)
        payload = (json.dumps(document, indent=2) + "\n").encode()
        manifest = {"path": input_manifest, "sha256": _hash.sha256_bytes(payload), "document": document, "written": None}
        meta = {**meta, "input_files": [], "input_manifest": {k: manifest[k] for k in ("path", "sha256")}}
        meta.pop("supplemental_inputs", None)
    text = draft(meta)
    written = None
    record = None
    written_files: list[dict] = []
    if replace_prompt:
        from stewart.audits import begin_init, finish_init
        from stewart.holdings import refuse_retiring
        refuse_retiring(common, [repo], what="a draft")
        destination = contained(repo, ws.prompt)
        if destination.exists() and not destination.is_file():
            raise StewartError("PROMPT.md destination is not a regular file", reason="destination_exists")
        before, _ = read_regular(destination)
        intended = [{"path": ws.prompt, "role": "prompt", "sha256": _hash.sha256_text(text)}]
        if manifest:
            intended.append({"path": input_manifest, "role": "input_manifest", "sha256": manifest["sha256"]})
        plan([{"kind": "written", "path": str(repo / item["path"]), "sha256": item["sha256"]} for item in intended])
        record = begin_init(ws, ident, intended=intended, prompt_before={"kind": before["kind"],
                                                                         "sha256": before.get("sha256")},
                            target=meta["target_commit"], request_key=request_key)

        def observed() -> list[dict]:
            found = []
            for item in intended:
                info, _ = read_regular(repo / item["path"])
                found.append({"path": item["path"], "role": item["role"], "kind": info["kind"],
                              "sha256": info.get("sha256")})
            return found

        try:
            if manifest:
                location.parent.mkdir(parents=True, exist_ok=True)
                write_exclusive(location, payload)
                manifest["written"] = str(location)
            destination.write_text(text, encoding="utf-8")
        except (OSError, StewartError) as exc:
            finish_init(record, written=observed(), error={"reason": getattr(exc, "reason", "initialization_failed"),
                                                           "message": str(exc)})
            raise StewartError(
                f"could not replace prompt at {destination}: {exc}", reason="initialization_failed",
                retained=[str(record)] + ([str(location)] if manifest else []),
                next_steps=["inspect the prompt, the draft record and any retained inventory; preserve failed writes "
                            "and use a fresh inventory path"],
            ) from exc
        written_files = [{"path": str(repo / item["path"]), "sha256": item["sha256"]} for item in observed()]
        finish_init(record, written=observed(), error=None)
        written = str(destination)
    return {"audit_id": ident, "draft": text, "written": written, "assignment": meta, "input_manifest": manifest,
            "draft_record": None if record is None else str(record), "written_files": written_files}


def copy_supplemental(repo: Path, worktree: Path, item: dict) -> None:
    """Copy one selected supplemental file into the worktree and verify its bytes."""
    from stewart.captured import verified_bytes

    data = verified_bytes(contained(repo, item["path"]), item["sha256"])
    destination = contained(worktree, item["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_exclusive(destination, data)
