"""Verified reads of retained collection bytes, shared by retention and handoff.

Only captured bytes are returned. The live auditor checkout is never a source.
Archive digests, member identity and file digests are separate checks.
"""
from __future__ import annotations

import io
from pathlib import Path
import re
import tarfile

from stewart import _util as _hash
from stewart._bootstrap import OBSERVATION_SCHEMA, SPECIAL_KINDS, StewartError, read_regular
from stewart._json import loads_control
from stewart.session import COLLECTION_SCHEMA, capture_receipt, record_name
from stewart.workspace import contained, relative


def load_collection(session: Path, ident: str, name: str, *, session_record: dict | None = None) -> tuple[Path, dict, str]:
    record_name(name, what="collection")
    directory = contained(session, f"collections/{name}")
    if not (directory / "STARTED.json").exists():
        raise StewartError(f"no collection named {name} in this session", reason="collection_not_found")
    try:
        receipt, digest = capture_receipt(directory / "collection.json", what="collection receipt")
    except StewartError as exc:
        if exc.reason == "record_missing":
            raise StewartError(
                f"collection {name} is a partial attempt without a receipt; preserve it and collect again",
                reason="collection_incomplete", retained=[str(directory)],
            ) from None
        raise
    if receipt.get("schema_version") != COLLECTION_SCHEMA or receipt.get("audit_id") != ident:
        raise StewartError(
            f"collection {name} has an unsupported receipt schema or belongs to another audit",
            reason="collection_schema", retained=[str(directory)],
        )
    from stewart.runtime import record_assets, record_state
    record_assets(receipt, session_record=session_record)
    runtime_observations(directory, record_state(receipt, session_record=session_record), phases={'collection'})
    return directory, receipt, digest


def collection_digest(receipt: dict, selector: str) -> str:
    """Resolve an explicit capture selector, never a path in the live checkout."""
    if selector == 'REPORT.md':
        digest = receipt.get('report_sha256')
        if receipt.get('report_status') not in ('present', 'empty') or not isinstance(digest, str):
            raise StewartError('the collection captured no report bytes', reason='report_unavailable')
        return digest
    if not isinstance(selector, str) or not selector.startswith('files.tar:'):
        raise StewartError('select REPORT.md or files.tar:<repo-relative-path>', reason='capture_selector')
    rel = relative(selector[len('files.tar:'):])
    checkout = receipt.get('checkout')
    files = checkout.get('files') if isinstance(checkout, dict) else None
    if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
        raise StewartError('collection file inventory is malformed', reason='collection_schema')
    entries = [item for item in files if item.get('path') == rel]
    if len(entries) != 1 or entries[0].get('kind') != 'file':
        raise StewartError(f'no unique captured regular file at {rel}', reason='support_unavailable')
    if not receipt.get('archive_sha256'):
        raise StewartError('the collection has no complete verified archive', reason='support_unavailable')
    digest = entries[0].get('sha256')
    if not isinstance(digest, str):
        raise StewartError('captured file has no digest', reason='collection_schema')
    return digest


def verified_bytes(location: Path, digest: str) -> bytes:
    """Read the bytes whose digest was recorded; unavailable and substituted files fail."""
    info, data = read_regular(location)
    if data is None:
        raise StewartError(f"captured bytes are unavailable ({info['kind']}): {location}; {info.get('detail', '')}",
                           reason='evidence_unavailable', retained=[str(location)],
                           next_steps=['inspect and preserve the unavailable capture; do not substitute live bytes'])
    if info.get('sha256') != digest:
        raise StewartError(f'captured bytes do not match their receipt: {location}', reason='evidence_tampered',
                           retained=[str(location)], next_steps=['inspect and preserve the inconsistent capture'])
    return data


def collection_files(directory: Path, receipt: dict, selectors: list[str]) -> dict[str, bytes]:
    """Verify report/archive/member identities before returning selected file bytes.

    No archive is extracted onto a filesystem, and duplicate member names cannot
    override a receipt's named member. An incomplete archive does not prevent
    selecting an independently captured report.
    """
    from stewart.runtime import record_assets, record_state
    record_assets(receipt)
    runtime_observations(directory, record_state(receipt), phases={'collection'})
    expected = {selector: collection_digest(receipt, selector) for selector in selectors}
    result = {}
    if 'REPORT.md' in expected:
        result['REPORT.md'] = verified_bytes(directory / 'REPORT.md', expected['REPORT.md'])
    archived = [selector for selector in expected if selector.startswith('files.tar:')]
    if archived:
        data = verified_bytes(directory / 'files.tar', receipt['archive_sha256'])
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r') as bundle:
                for selector in archived:
                    rel = selector[len('files.tar:'):]
                    members = [m for m in bundle.getmembers() if m.name == rel]
                    if len(members) != 1 or not members[0].isreg():
                        raise StewartError(f'no unique regular archive member {rel}', reason='support_unavailable')
                    with bundle.extractfile(members[0]) as stream:
                        payload = stream.read()
                    if _hash.sha256_bytes(payload) != expected[selector]:
                        raise StewartError(f'archived bytes for {rel} do not match the collection receipt',
                                           reason='evidence_tampered', retained=[str(directory)])
                    result[selector] = payload
        except tarfile.TarError as exc:
            raise StewartError(f'cannot read captured archive: {exc}', reason='evidence_tampered',
                               retained=[str(directory)]) from exc
    return result


def _runtime_observation(data: bytes) -> dict:
    """Validate failure-bearing observations without treating them as executable manifests."""
    value = loads_control(data)
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'entries'}
            or value['schema_version'] != OBSERVATION_SCHEMA or not isinstance(value['entries'], list)):
        raise StewartError('invalid captured runtime observation', reason='runtime_capture_schema')
    names, regular = [], set()
    kinds = {'file', 'directory', 'symlink', 'unreadable', 'missing', *SPECIAL_KINDS}
    for item in value['entries']:
        if (not isinstance(item, dict) or not {'path', 'kind', 'size', 'sha256'} <= set(item)
                or set(item) - {'path', 'kind', 'size', 'sha256', 'detail', 'target'}
                or item['kind'] not in kinds):
            raise StewartError('invalid runtime observation entry', reason='runtime_capture_schema')
        name = item['path']
        if name != '.':
            relative(name)
        elif item['kind'] in {'file', 'directory', 'symlink'}:
            raise StewartError('invalid runtime root diagnostic', reason='runtime_capture_schema')
        names.append(name)
        if any(not isinstance(item[key], str) for key in ('detail', 'target') if key in item):
            raise StewartError('runtime diagnostic must be text', reason='runtime_capture_schema')
        if item['kind'] == 'file':
            if (name in regular or type(item['size']) is not int or item['size'] < 0
                    or not isinstance(item['sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is None):
                raise StewartError('invalid regular runtime member identity', reason='runtime_capture_schema')
            regular.add(name)
        elif item['size'] is not None or item['sha256'] is not None:
            raise StewartError('nonregular runtime entry cannot claim file bytes', reason='runtime_capture_schema')
    if names != sorted(names):
        raise StewartError('runtime observation must be sorted', reason='runtime_capture_schema')
    return value


def runtime_archive(data: bytes, expected: dict[str, dict]) -> dict[str, bytes]:
    """Verify the complete regular-member archive; never extract it to disk."""
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r') as archive:
            members = archive.getmembers()
            if len(members) != len(expected) or {m.name for m in members} != set(expected):
                raise StewartError('runtime archive membership differs from its observation', reason='evidence_tampered')
            result = {}
            for member in members:
                pin = expected[member.name]
                if not member.isreg() or member.size != pin['size']:
                    raise StewartError('runtime archive member is not the captured regular file', reason='evidence_tampered')
                with archive.extractfile(member) as stream:
                    payload = stream.read()
                if _hash.sha256_bytes(payload) != pin['sha256']:
                    raise StewartError('runtime archive member digest differs', reason='evidence_tampered')
                result[member.name] = payload
            return result
    except tarfile.TarError as exc:
        raise StewartError(f'cannot read runtime archive: {exc}', reason='evidence_tampered') from exc


def runtime_assets_payloads(identity: dict, assets: dict, data: dict[str, bytes]) -> dict[str, bytes]:
    """Verify pristine bytes from private storage or a package through one reader."""
    from stewart.runtime import validate_assets, validate_binding
    validate_binding(identity)
    validate_assets(assets)
    if set(data) != {'manifest.json', 'files.tar'}:
        raise StewartError('pristine assets need the manifest and complete archive', reason='runtime_assets')
    for name, key in (('manifest.json', 'manifest_sha256'), ('files.tar', 'archive_sha256')):
        if _hash.sha256_bytes(data[name]) != assets[key]:
            raise StewartError('pristine runtime bytes differ from their pins', reason='evidence_tampered')
    try:
        manifest = loads_control(data['manifest.json'])
    except (ValueError, RecursionError) as exc:
        raise StewartError(f'cannot interpret pristine runtime manifest: {exc}', reason='runtime_assets') from exc
    if manifest != identity['manifest']:
        raise StewartError('pristine runtime manifest differs from preparation', reason='runtime_assets')
    files = {item['path']: item for item in manifest['entries'] if item['kind'] == 'file'}
    return runtime_archive(data['files.tar'], files)


def _pristine_runtime(session: Path, record: dict) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Read and verify the private assets once for either consumer representation."""
    from stewart.runtime import validate_assets
    assets = validate_assets(record.get('runtime_assets'))
    directory = contained(session, 'runtime-pristine')
    data = {name: verified_bytes(directory / name, assets[key])
            for name, key in (('manifest.json', 'manifest_sha256'), ('files.tar', 'archive_sha256'))}
    return data, runtime_assets_payloads(record.get('runtime'), assets, data)


def pristine_runtime_files(session: Path, record: dict) -> dict[str, bytes]:
    """Return verified private assets, never an exposed copy or newer code."""
    return _pristine_runtime(session, record)[0]


def pristine_runtime(session: Path, record: dict) -> dict[str, bytes]:
    """Read privately retained payloads; missing assets never trigger live fallback."""
    return _pristine_runtime(session, record)[1]


RUNTIME_CAPTURE_FILES = frozenset({'capture.json', 'before.json', 'after.json', 'files.tar'})


def runtime_reference(reference: object) -> dict:
    """Validate a capture pin even when its bytes are not selected for export."""
    if not isinstance(reference, dict) or set(reference) not in ({'directory', 'sha256'}, {'directory', 'error'}):
        raise StewartError('invalid runtime capture reference', reason='runtime_capture_schema')
    relative(reference['directory'])
    if 'error' in reference:
        error = reference['error']
        if (not isinstance(error, dict) or set(error) != {'reason', 'message'}
                or not all(isinstance(error[key], str) and error[key] for key in error)):
            raise StewartError('invalid runtime capture failure', reason='runtime_capture_schema')
    elif (not isinstance(reference['sha256'], str)
          or re.fullmatch(r'[0-9a-f]{64}', reference['sha256']) is None):
        raise StewartError('invalid runtime capture digest', reason='runtime_capture_schema')
    return reference


def runtime_capture_files(parent: Path, reference: dict) -> dict[str, bytes]:
    """Read one complete private capture group; the caller verifies its binding."""
    runtime_reference(reference)
    if 'error' in reference:
        raise StewartError('runtime capture failed; no complete observation group is available',
                           reason='runtime_capture_unavailable', retained=[str(parent / reference['directory'])])
    directory = contained(parent, reference['directory'])
    data = {}
    for name in sorted(RUNTIME_CAPTURE_FILES):
        info, payload = read_regular(directory / name)
        if payload is None:
            raise StewartError(f"runtime capture member is unavailable ({info['kind']})", reason='evidence_unavailable',
                               retained=[str(directory / name)])
        data[name] = payload
    return data


def verify_runtime_capture(identity: dict, reference: dict, data: dict[str, bytes]) -> dict:
    """Verify a capture identically in private storage and self-contained exports."""
    from stewart.runtime import CAPTURE_SCHEMA, ENDPOINT_LIMIT, observation_matches, validate_binding
    validate_binding(identity)
    runtime_reference(reference)
    if 'error' in reference:
        raise StewartError('failed runtime capture cannot supply a complete observation group',
                           reason='runtime_capture_unavailable')
    if set(data) != RUNTIME_CAPTURE_FILES:
        raise StewartError('runtime observation requires every captured member', reason='runtime_capture_schema')
    if _hash.sha256_bytes(data['capture.json']) != reference['sha256']:
        raise StewartError('runtime capture receipt differs from its pin', reason='evidence_tampered')
    try:
        record = loads_control(data['capture.json'])
        if (not isinstance(record, dict) or set(record) != {
                'schema_version', 'runtime', 'digests', 'movement', 'matches_expected',
                'captured_files', 'completed_at', 'limit'}
                or record['schema_version'] != CAPTURE_SCHEMA or record['runtime'] != identity
                or record['limit'] != ENDPOINT_LIMIT or not isinstance(record['completed_at'], str)
                or type(record['movement']) is not bool or type(record['matches_expected']) is not bool
                or type(record['captured_files']) is not int):
            raise StewartError('invalid runtime capture receipt', reason='runtime_capture_schema')
        digests = record['digests']
        if (not isinstance(digests, dict) or set(digests) != RUNTIME_CAPTURE_FILES - {'capture.json'}
                or any(not isinstance(d, str) or re.fullmatch(r'[0-9a-f]{64}', d) is None for d in digests.values())):
            raise StewartError('runtime capture lacks its complete byte identities', reason='runtime_capture_schema')
        if any(_hash.sha256_bytes(data[name]) != digest for name, digest in digests.items()):
            raise StewartError('runtime capture bytes differ from their pins', reason='evidence_tampered')
        before, after = (_runtime_observation(data[name]) for name in ('before.json', 'after.json'))
        expected_files = {item['path']: item for item in before['entries'] if item['kind'] == 'file'}
        runtime_archive(data['files.tar'], expected_files)
        movement = before != after
        matched = observation_matches(before, identity) and observation_matches(after, identity) and not movement
        if (record['movement'] != movement or record['matches_expected'] != matched
                or record['captured_files'] != len(expected_files)):
            raise StewartError('runtime capture claims disagree with their observations', reason='runtime_capture_schema')
        return record
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        if isinstance(exc, StewartError):
            raise
        raise StewartError(f'malformed runtime capture: {exc}', reason='runtime_capture_schema') from exc


def runtime_observations(parent: Path, state: dict, *, phases: set[str]) -> dict[str, dict]:
    """Recheck captured bytes and derived claims without reading the live runtime.

    A mismatching or missing exposed runtime can have a perfectly valid capture.
    Tampering with that private capture instead refuses custody interpretation.
    """
    if not isinstance(state, dict) or set(state) != {'identity', 'observations'}:
        raise StewartError('invalid runtime observation binding', reason='runtime_capture_schema')
    observations = state['observations']
    if not isinstance(observations, dict) or set(observations) != phases:
        raise StewartError('required runtime observations are absent or unexpected', reason='runtime_capture_schema')
    result = {}
    for phase, reference in observations.items():
        runtime_reference(reference)
        if 'error' in reference:
            from stewart.runtime import ENDPOINT_LIMIT
            result[phase] = {'state': 'failed', 'error': reference['error'], 'matches_expected': False,
                             'movement': None, 'captured_files': None, 'limit': ENDPOINT_LIMIT}
        else:
            result[phase] = verify_runtime_capture(state['identity'], reference, runtime_capture_files(parent, reference))
    return result


def runtime_recovery(session: Path, name: str, session_record: dict) -> tuple[dict, dict]:
    """Validate a historical recovery without consulting its materialized directory."""
    from stewart.runtime import RECOVERY_ACTIVATION, RECOVERY_SCHEMA, binding, record_assets, record_state
    record_name(name, what='runtime-recovery')
    directory = contained(session, f'runtime-recoveries/{name}')
    source, digest = capture_receipt(session / 'session.json', what='session record')
    record, _ = capture_receipt(directory / 'RECOVERY.json', what='runtime recovery')
    if (source != session_record or record.get('schema_version') != RECOVERY_SCHEMA
            or record.get('name') != name or record.get('audit_id') != session_record['assignment']['audit_id']
            or record.get('workspace') != session_record['workspace'] or record.get('session_sha256') != digest
            or record.get('source_runtime') != session_record['runtime'] or type(record.get('materialized')) is not bool
            or record.get('activation') != RECOVERY_ACTIVATION
            or not isinstance(record.get('recorded_at'), str)
            or 'error' not in record or (record['error'] is not None and not isinstance(record['error'], dict))
            or ('observation_error' in record and not isinstance(record['observation_error'], str))
            or not isinstance(record.get('actor'), str) or not record['actor'].strip()):
        raise StewartError('runtime recovery differs from its source session', reason='binding_mismatch')
    record_assets(record, session_record=session_record)
    state = record_state(record)
    destination = Path(session_record['repo']) / '.scratch/stewart-runtimes' / f"{session_record['session_uuid']}-recovered-{name}"
    if state['identity'] != binding(destination, session_record['runtime']['manifest']):
        raise StewartError('runtime recovery changed the source code identity or destination', reason='binding_mismatch')
    capture = runtime_observations(directory, state, phases={'recovery'})['recovery']
    if record['materialized'] and not record.get('error') and not record.get('observation_error') and not capture['matches_expected']:
        raise StewartError('runtime recovery claims success without a matching observation', reason='runtime_capture_schema')
    return record, capture
