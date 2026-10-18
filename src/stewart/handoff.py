"""Selected captured evidence packaged for another assignment.

The exporter reads verified collections/attempts, never the live worktree. A
package keeps the exact source receipt and selected bytes under a digest-bearing
manifest. Import verifies these bindings and pins every package member as a
supplemental input. Provenance records custody observations, not scientific review
or authenticated authorship; the receiving manager still selects and interprets.
"""
from __future__ import annotations

import os
from pathlib import Path

from stewart import _util as _hash
from stewart import _util as path
from stewart._bootstrap import StewartError, open_directory, write_exclusive
from stewart._json import loads_control
from stewart.captured import (
    RUNTIME_CAPTURE_FILES, collection_digest, collection_files, load_collection, pristine_runtime_files,
    runtime_assets_payloads, runtime_capture_files, runtime_observations, verified_bytes, verify_runtime_capture,
)
from stewart.session import (
    ATTEMPT_SCHEMA, COLLECTION_SCHEMA, RELEASE_SCHEMA, capture_receipt, load_session,
    now, record_name, session_dir, tool_identity, write_receipt,
)
from stewart.workspace import Workspace, contained, relative

#: Schema 4 binds pristine assets and complete observed-runtime capture groups.
PACKAGE_SCHEMA = 'stewart.evidence-package/5'
_MANIFEST_FIELDS = {'schema', 'actor', 'exported_at', 'source', 'entries', 'stewart', 'runtime', 'runtime_assets'}
_SOURCE_FIELDS = {'kind', 'workspace', 'audit_id', 'record', 'receipt_sha256'}
_CUSTODY_FIELDS = {'package', 'manifest_sha256', 'member'}


def _digest(value: object) -> bool:
    """A package binding is a complete lowercase SHA-256, not a shortened display ID."""
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_custody(value: object) -> None:
    """Validate the structured package reference carried by one supplemental input."""
    if not isinstance(value, dict) or set(value) != _CUSTODY_FIELDS or not _digest(value['manifest_sha256']):
        raise StewartError('custody needs package, manifest_sha256 and member', reason='package_schema')
    relative(value['package'])
    relative(value['member'])


def _attempt_digest(receipt: dict, selector: str, receipt_digest: str) -> str:
    if selector == 'ATTEMPT.json':
        return receipt_digest
    if selector in ('ledger.jsonl', 'child-receipt.json'):
        item = receipt.get('ledger' if selector == 'ledger.jsonl' else 'child_receipt') or {}
        capture = item.get('capture') if isinstance(item, dict) else None
    elif selector in ('stdout.txt', 'stderr.txt'):
        streams = receipt.get('streams')
        capture = streams.get(selector) if isinstance(streams, dict) else None
    else:
        raise StewartError('select ATTEMPT.json, ledger.jsonl, child-receipt.json, stdout.txt or stderr.txt',
                           reason='capture_selector')
    if not isinstance(capture, dict) or capture.get('kind') != 'file' or not _digest(capture.get('sha256')):
        raise StewartError(f'attempt has no verified regular capture for {selector}', reason='capture_unavailable')
    return capture['sha256']


def _source_identity(source: dict, receipt: dict) -> None:
    schema = COLLECTION_SCHEMA if source['kind'] == 'collection' else ATTEMPT_SCHEMA
    if (receipt.get('schema_version') != schema or receipt.get('audit_id') != source['audit_id']
            or receipt.get('workspace') != source['workspace'] or receipt.get('name') != source['record']):
        raise StewartError('source receipt schema or identity does not match the package source', reason='package_binding')
    from stewart.runtime import record_assets, record_state
    state = record_state(receipt)
    record_assets(receipt)
    phases = {'collection'} if source['kind'] == 'collection' else {'before', 'after'}
    if not isinstance(state['observations'], dict) or set(state['observations']) != phases:
        raise StewartError('source receipt lacks its required runtime observations', reason='package_binding')


def _source_runtime(receipt: dict) -> dict:
    from stewart.runtime import record_state
    state = record_state(receipt)
    return state['identity']


def _runtime_selector(receipt: dict, selector: str) -> tuple[str, str | None, str] | None:
    """Expanded package members have an explicit group, phase and fixed basename."""
    if selector.startswith('runtime-assets:'):
        name = selector.split(':', 1)[1]
        if name not in {'manifest.json', 'files.tar'}:
            raise StewartError('unknown pristine runtime member', reason='capture_selector')
        return 'assets', None, name
    if selector.startswith('runtime-observation:'):
        parts = selector.split(':')
        if (len(parts) != 3 or parts[1] not in receipt['runtime']['observations']
                or parts[2] not in RUNTIME_CAPTURE_FILES):
            raise StewartError('unknown runtime observation member or phase', reason='capture_selector')
        return 'observation', parts[1], parts[2]
    return None


def _verify_runtime_selections(receipt: dict, payloads: dict[str, bytes]) -> None:
    """A selected runtime group is complete and independently bound to the source."""
    from stewart.runtime import record_assets, record_state
    state, assets = record_state(receipt), record_assets(receipt)
    pristine, observations = {}, {}
    for selector, data in payloads.items():
        parsed = _runtime_selector(receipt, selector)
        if parsed is None:
            continue
        kind, phase, name = parsed
        if kind == 'assets':
            pristine[name] = data
        else:
            observations.setdefault(phase, {})[name] = data
    if pristine:
        runtime_assets_payloads(state['identity'], assets, pristine)
    for phase, data in observations.items():
        verify_runtime_capture(state['identity'], state['observations'][phase], data)


def export_evidence(ws: Workspace, ident: str, *, collection: str | None = None, attempt: str | None = None,
                    selectors: list[str], output: str, actor: str) -> dict:
    """Export selected captured files exclusively; output is a new repo-relative directory.

    Collections use REPORT.md or files.tar:<repo-relative-path> selectors.
    Attempts use ATTEMPT.json, ledger.jsonl, child-receipt.json, stdout.txt and
    stderr.txt. Both accept runtime-assets and runtime-observation:<phase> groups,
    which include the complete verification material. Including a file does not
    accept any claim in it. The manifest is
    written last; a failed publication is retained and requires a fresh output.
    """
    try:
        return _export_evidence(ws, ident, collection=collection, attempt=attempt,
                                selectors=selectors, output=output, actor=actor)
    except StewartError as exc:
        raise StewartError(str(exc), reason=exc.reason,
                           retained=exc.retained or [str(session_dir(ws, ident))],
                           next_steps=exc.next_steps or [
                               'inspect the named source record and select only its available regular captures; '
                               'preserve inconsistent evidence and use a fresh output directory',
                           ]) from exc


def _export_evidence(ws: Workspace, ident: str, *, collection: str | None, attempt: str | None,
                     selectors: list[str], output: str, actor: str) -> dict:
    """Validate all selections before exclusively publishing their package."""
    if (collection is None) == (attempt is None):
        raise StewartError('select exactly one collection or attempt', reason='export_source')
    if (not selectors or not all(isinstance(s, str) and s for s in selectors)
            or len(set(selectors)) != len(selectors)):
        raise StewartError('select one or more distinct captured files explicitly', reason='export_selection')
    if not isinstance(actor, str) or not actor.strip():
        raise StewartError('export needs an attributed actor', reason='actor_required')
    session, session_record = load_session(ws, ident)
    ordinary = [selector for selector in selectors if selector != 'runtime-assets'
                and not selector.startswith('runtime-observation:')]
    kind = 'collection' if collection is not None else 'attempt'
    name = record_name(collection if collection is not None else attempt, what=kind)
    if collection is not None:
        directory, receipt, digest = load_collection(session, ident, name, session_record=session_record)
        source_path = directory / 'collection.json'
        files = collection_files(directory, receipt, ordinary)
    else:
        directory = contained(session, f'attempts/{name}')
        source_path = directory / 'ATTEMPT.json'
        receipt, digest = capture_receipt(source_path, what='completed attempt')
        if receipt.get('schema_version') != ATTEMPT_SCHEMA or receipt.get('audit_id') != ident:
            raise StewartError('unsupported or foreign attempt receipt', reason='attempt_schema', retained=[str(directory)])
        release_name = record_name(receipt.get('release'), what='release')
        release, release_digest = capture_receipt(contained(session, f'releases/{release_name}.json'), what='release')
        if (release_digest != receipt.get('release_sha256') or release.get('schema_version') != RELEASE_SCHEMA
                or release.get('audit_id') != ident or release.get('workspace') != ws.rel):
            raise StewartError('attempt no longer matches its release', reason='binding_mismatch', retained=[str(directory)])
        from stewart.runtime import record_state
        runtime_observations(directory, record_state(receipt, session_record=session_record), phases={'before', 'after'})
        runtime_observations(session / 'releases', record_state(release, session_record=session_record), phases={'release'})
        files = {s: verified_bytes(directory / s, _attempt_digest(receipt, s, digest)) for s in ordinary}
    from stewart.runtime import record_assets
    assets = record_assets(receipt, session_record=session_record)
    selected = {}
    for selector in selectors:
        if selector == 'runtime-assets':
            selected.update({f'runtime-assets:{name}': data for name, data in pristine_runtime_files(session, session_record).items()})
        elif selector.startswith('runtime-observation:'):
            phase = selector.split(':', 1)[1]
            reference = receipt['runtime']['observations'].get(phase)
            if reference is None:
                raise StewartError('select a runtime observation phase recorded by this source', reason='capture_selector')
            selected.update({f'runtime-observation:{phase}:{name}': data
                             for name, data in runtime_capture_files(directory, reference).items()})
        else:
            selected[selector] = files[selector]
    files = selected
    _verify_runtime_selections(receipt, files)
    source = {'kind': kind, 'workspace': ws.rel, 'audit_id': ident, 'record': name, 'receipt_sha256': digest}
    _source_identity(source, receipt)
    source_bytes = verified_bytes(source_path, digest)
    destination = contained(ws.repo, output)
    manifest = {'schema': PACKAGE_SCHEMA, 'actor': actor, 'exported_at': now().isoformat(),
                'source': source, 'entries': [], 'stewart': tool_identity(), 'runtime': _source_runtime(receipt),
                'runtime_assets': assets}
    for index, (selector, data) in enumerate(files.items()):
        suffix = Path(selector.split(':', 1)[-1]).suffix
        manifest['entries'].append({'selector': selector, 'file': f'files/{index:04d}{suffix}',
                                    'sha256': _hash.sha256_bytes(data), 'size': len(data)})
    # The chosen parent must exist. Pin it before creating anything, then keep
    # the new directory pinned so ancestor substitution cannot redirect writes.
    try:
        with open_directory(destination.parent) as parent:
            os.mkdir(destination.name, mode=0o700, dir_fd=parent)
            with open_directory(Path(destination.name), dir_fd=parent) as package:
                os.mkdir('files', mode=0o700, dir_fd=package)
                write_exclusive(Path('source.json'), source_bytes, dir_fd=package)
                for entry in manifest['entries']:
                    write_exclusive(Path(entry['file']), files[entry['selector']], dir_fd=package)
                write_receipt(Path('manifest.json'), manifest, dir_fd=package)
    except FileExistsError as exc:
        raise StewartError('export destination or member exists; nothing is overwritten', reason='destination_exists',
                           retained=[str(destination)], next_steps=['choose a fresh package directory']) from exc
    except OSError as exc:
        raise StewartError(f'cannot publish evidence package: {exc}', reason='export_failed',
                           retained=[str(destination)],
                           next_steps=['retain partial output; ensure the parent directory exists and choose a fresh output']) from exc
    return {'audit_id': ident, 'package': path.rel(destination / 'manifest.json', ws.repo),
            'source': source, 'entries': manifest['entries'],
            'next_steps': ['initialize the receiving assignment with --evidence-package <package>; author its scope separately']}


def package_inputs(repo: Path, manifest_path: str, *, expected_digest: str | None = None) -> list[dict]:
    """Verify a self-contained package and return its pinned supplemental inputs.

    This does not consult the originating session or accept scientific claims.
    Source and payload bytes are checked against the manifest, then payload
    digests are checked against the retained source receipt independently.
    """
    try:
        return _package_inputs(repo, manifest_path, expected_digest=expected_digest)
    except StewartError as exc:
        raise StewartError(str(exc), reason=exc.reason, retained=exc.retained or [str(repo / str(manifest_path))],
                           next_steps=exc.next_steps or [
                               'inspect the package manifest, source receipt and selected files; preserve the '
                               'inconsistent package and export a fresh one before drafting the assignment',
                           ]) from exc


def _package_inputs(repo: Path, manifest_path: str, *, expected_digest: str | None) -> list[dict]:
    """Resolve package bindings without requiring the originating session."""
    location = contained(repo, manifest_path)
    if location.name != 'manifest.json':
        raise StewartError('an evidence package is addressed by its manifest.json', reason='package_schema')
    manifest, manifest_digest = capture_receipt(location, what='evidence package manifest')
    if expected_digest is not None and manifest_digest != expected_digest:
        raise StewartError('package manifest changed since assignment initialization', reason='package_binding')
    if (set(manifest) != _MANIFEST_FIELDS or manifest.get('schema') != PACKAGE_SCHEMA
            or not isinstance(manifest.get('actor'), str) or not manifest['actor'].strip()
            or not isinstance(manifest.get('exported_at'), str)):
        raise StewartError('unsupported evidence package manifest', reason='package_schema')
    source = manifest['source']
    if (not isinstance(source, dict) or set(source) != _SOURCE_FIELDS
            or source['kind'] not in ('collection', 'attempt') or not _digest(source['receipt_sha256'])):
        raise StewartError('invalid evidence package source', reason='package_schema')
    relative(source['workspace'])
    from stewart.assignment import audit_id
    audit_id(source['audit_id'])
    record_name(source['record'], what=source['kind'])
    source_bytes = verified_bytes(location.parent / 'source.json', source['receipt_sha256'])
    try:
        # A matching digest proves these are the selected bytes, not that their
        # control meaning is unambiguous. Payload files below stay opaque.
        receipt = loads_control(source_bytes)
        if not isinstance(receipt, dict):
            raise ValueError('source receipt must be an object')
        _source_identity(source, receipt)
        if manifest['runtime'] != _source_runtime(receipt):
            raise StewartError('package runtime identity differs from its source receipt', reason='package_binding')
        from stewart.runtime import record_assets
        assets = record_assets(receipt)
        if manifest['runtime_assets'] != assets:
            raise StewartError('package pristine asset pins differ from its source receipt', reason='package_binding')
        entries = manifest['entries']
        if not isinstance(entries, list) or not entries:
            raise ValueError('package needs at least one selected entry')
        seen_files, seen_selectors, payloads = set(), set(), {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'selector', 'file', 'sha256', 'size'}:
                raise ValueError('entry needs selector, file, sha256 and size')
            member = relative(entry['file'])
            selector = entry['selector']
            if not member.startswith('files/') or member in seen_files or not isinstance(selector, str) or selector in seen_selectors:
                raise ValueError('package files and selectors must be distinct; files must be under files/')
            seen_files.add(member); seen_selectors.add(selector)
            runtime_member = _runtime_selector(receipt, selector)
            if runtime_member is None:
                digest = (collection_digest(receipt, selector) if source['kind'] == 'collection'
                          else _attempt_digest(receipt, selector, source['receipt_sha256']))
            else:
                group, phase, name = runtime_member
                if group == 'assets':
                    digest = assets['manifest_sha256' if name == 'manifest.json' else 'archive_sha256']
                else:
                    # The complete group is verified below, binding these
                    # members through its source-pinned capture.json.
                    if 'error' in receipt['runtime']['observations'][phase]:
                        raise StewartError('failed runtime observation has no complete group', reason='runtime_capture_unavailable')
                    digest = receipt['runtime']['observations'][phase]['sha256'] if name == 'capture.json' else entry['sha256']
            if not _digest(entry['sha256']) or entry['sha256'] != digest:
                raise StewartError('package entry disagrees with its source receipt', reason='package_binding')
            data = verified_bytes(location.parent / member, digest)
            if type(entry['size']) is not int or entry['size'] != len(data):
                raise ValueError('package entry size differs from captured bytes')
            payloads[selector] = data
        _verify_runtime_selections(receipt, payloads)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        if isinstance(exc, StewartError):
            raise
        raise StewartError(f'malformed package/source record: {exc}', reason='package_schema') from exc
    members = [('manifest.json', manifest_digest), ('source.json', source['receipt_sha256'])]
    members += [(e['file'], e['sha256']) for e in entries]
    return [{'path': path.rel(location.parent / member, repo), 'sha256': digest,
             'provenance': f"Captured evidence package from {source['workspace']} audit {source['audit_id']} "
                           f"{source['kind']} {source['record']}; custody reference, not a scientific endorsement.",
             'custody': {'package': manifest_path, 'manifest_sha256': manifest_digest, 'member': member}}
            for member, digest in members]


def verify_packaged_inputs(repo: Path, inputs: list[dict]) -> None:
    """Reconcile committed input metadata with every member of each pinned package."""
    groups = {}
    for item in inputs:
        if 'custody' in item:
            validate_custody(item['custody'])
            ref = item['custody']
            groups.setdefault((ref['package'], ref['manifest_sha256']), []).append(item)
    for (package, digest), members in groups.items():
        expected = package_inputs(repo, package, expected_digest=digest)
        if sorted(members, key=lambda x: x['path']) != sorted(expected, key=lambda x: x['path']):
            raise StewartError('assignment package members differ from the pinned manifest', reason='package_binding',
                               retained=[str(repo / package)],
                               next_steps=['draft with --evidence-package to pin the complete package; '
                                           'a changed launched assignment needs a fresh audit ID'])
