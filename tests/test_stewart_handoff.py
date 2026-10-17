"""Evidence handoff reads captured identities; import pins a self-contained package.

Pairs distinguish live worktree edits from capture edits, and selection from
acceptance. Packages are portable custody records, not authenticated testimony.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import tarfile

import pytest

from stewart import _util as _hash
from stewart.assignment import assignment_metadata, expand_input_manifest, initialize, input_receipts
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.experiment import release, run
from stewart.handoff import export_evidence, package_inputs
from stewart.prepare import prepare
import stewart_support as support

pytestmark = pytest.mark.system


def captured(checkout):
    prepared = support.prepared_session(checkout, report='Captured report\n')
    artifact = f'{checkout.ws.scratch}/one-question/artifacts/candidate.py'
    destination = prepared.worktree / artifact
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b'print("captured candidate")\n')
    collection = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped="finished")
    return prepared, collection, artifact


def export(checkout, collection, selectors, output='.scratch/package'):
    return export_evidence(checkout.ws, checkout.meta['audit_id'], collection=collection['collection'],
                           selectors=selectors, output=output, actor='receiving manager')


@pytest.mark.parametrize('compact', [False, True])
def test_selected_captured_bytes_survive_live_edits_and_source_removal_and_prepare(checkout, compact):
    prepared, collection, artifact = captured(checkout)
    prepared.report.write_text('Live report is a different assertion\n')
    (prepared.worktree / artifact).write_bytes(b'raise RuntimeError("live")\n')
    before = support.snapshot_tree(prepared.session)
    exported = export(checkout, collection, ['REPORT.md', f'files.tar:{artifact}'])
    assert support.snapshot_tree(prepared.session) == before, 'export must not repair, triage or alter its source'
    package = checkout.repo / exported['package']
    manifest = support.read_json(package)
    assert manifest['source']['receipt_sha256'] == _hash.sha256_bytes((Path(collection['path']) / 'collection.json').read_bytes())
    assert [e['selector'] for e in manifest['entries']] == ['REPORT.md', f'files.tar:{artifact}']
    assert (package.parent / manifest['entries'][0]['file']).read_bytes() == b'Captured report\n'
    assert (package.parent / manifest['entries'][1]['file']).read_bytes() == b'print("captured candidate")\n'
    # Portability control: import consults the package only, not the originating records.
    shutil.rmtree(prepared.session)
    result = initialize(checkout.ws, 'receiving-question', 'HEAD', inputs=[], evidence_packages=[exported['package']],
                        input_manifest='.scratch/receiving-inputs.json' if compact else None, replace_prompt=compact)
    expanded = expand_input_manifest(checkout.ws, assignment_metadata(result['assignment'], checkout.ws))
    items = [item for item in expanded['supplemental_inputs'] if 'custody' in item]
    assert len(items) == 4, 'manifest, source receipt and exactly the two selected files must all be pinned'
    assert {i['custody']['member'] for i in items} == {'manifest.json', 'source.json', 'files/0000.md', 'files/0001.py'}
    revision = checkout.prompt_commit(text=support.assignment_text(result['assignment']))
    prepared_next = prepare(checkout.ws, revision)
    for item in items:
        assert _hash.sha256_bytes((Path(prepared_next['worktree']) / item['path']).read_bytes()) == item['sha256']
    with pytest.raises(StewartError) as refused:
        initialize(checkout.ws, 'overlap', 'HEAD', inputs=[], evidence_packages=[exported['package'], exported['package']])
    assert refused.value.reason == 'assignment_schema', 'duplicate package membership must not silently deduplicate'


def test_export_refuses_changed_capture_but_ignores_unselected_archive(checkout):
    prepared, collection, artifact = captured(checkout)
    archive = Path(collection['path']) / 'files.tar'
    archive.write_bytes(b'corrupt archive')
    exported = export(checkout, collection, ['REPORT.md'])
    assert package_inputs(checkout.repo, exported['package']), 'independently captured report remains usable'
    with pytest.raises(StewartError) as refused:
        export(checkout, collection, [f'files.tar:{artifact}'], '.scratch/bad-archive')
    assert refused.value.reason == 'evidence_tampered'
    report = Path(collection['path']) / 'REPORT.md'
    report.write_text('rewritten capture')
    with pytest.raises(StewartError) as refused:
        export(checkout, collection, ['REPORT.md'], '.scratch/bad-report')
    assert refused.value.reason == 'evidence_tampered'
    assert not (checkout.repo / '.scratch/bad-report').exists(), 'validate before publishing any package'


def test_duplicate_archive_member_is_refused_even_when_archive_digest_matches(checkout):
    _, collection, artifact = captured(checkout)
    directory = Path(collection['path'])
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as bundle:
        for payload in (b'first', b'last'):
            member = tarfile.TarInfo(artifact)
            member.size = len(payload)
            bundle.addfile(member, io.BytesIO(payload))
    (directory / 'files.tar').write_bytes(data.getvalue())
    receipt = support.read_json(directory / 'collection.json')
    receipt['archive_sha256'] = _hash.sha256_bytes(data.getvalue())
    (directory / 'collection.json').write_text(json.dumps(receipt))
    with pytest.raises(StewartError) as refused:
        export(checkout, collection, [f'files.tar:{artifact}'])
    assert refused.value.reason == 'support_unavailable', 'member identity cannot be chosen by tar order'


@pytest.mark.parametrize('mutation,reason', [
    ('payload', 'evidence_tampered'), ('source', 'evidence_tampered'),
    ('rehashed_payload', 'package_binding'), ('foreign_identity', 'package_binding'),
    ('duplicate_member', 'package_schema'), ('escape', 'path_escape'),
    ('symlink', 'evidence_unavailable'), ('fifo', 'evidence_unavailable'), ('bad_kind', 'package_schema'),
])
def test_package_checks_source_binding_member_identity_and_file_kind(checkout, mutation, reason):
    _, collection, _ = captured(checkout)
    exported = export(checkout, collection, ['REPORT.md'])
    location = checkout.repo / exported['package']
    manifest = support.read_json(location)
    payload = location.parent / manifest['entries'][0]['file']
    if mutation in {'payload', 'rehashed_payload'}:
        payload.write_bytes(b'reauthored claim')
        if mutation == 'rehashed_payload':
            manifest['entries'][0].update(sha256=_hash.sha256_bytes((payload).read_bytes()), size=payload.stat().st_size)
    elif mutation == 'source':
        (location.parent / 'source.json').write_text('{}')
    elif mutation == 'foreign_identity':
        manifest['source']['audit_id'] = 'other-question'
    elif mutation == 'duplicate_member':
        manifest['entries'].append(dict(manifest['entries'][0]))
    elif mutation == 'escape':
        manifest['entries'][0]['file'] = '../outside'
    elif mutation in {'symlink', 'fifo'}:
        payload.unlink()
        if mutation == 'symlink':
            payload.symlink_to(checkout.repo / 'input.txt')
        else:
            os.mkfifo(payload)
    elif mutation == 'bad_kind':
        manifest['source']['kind'] = []
    location.write_text(json.dumps(manifest))
    with pytest.raises(StewartError) as refused:
        package_inputs(checkout.repo, exported['package'])
    assert refused.value.reason == reason


def test_pinned_manifest_and_complete_membership_are_rechecked(checkout):
    _, collection, _ = captured(checkout)
    exported = export(checkout, collection, ['REPORT.md'])
    initialized = initialize(checkout.ws, 'receiving', 'HEAD', inputs=[], evidence_packages=[exported['package']])
    meta = initialized['assignment']
    original = list(meta['supplemental_inputs'])
    meta['supplemental_inputs'] = original[:-1]
    with pytest.raises(StewartError) as refused:
        input_receipts(checkout.repo, meta, meta['target_commit'])
    assert refused.value.reason == 'package_binding'
    meta['supplemental_inputs'] = original
    location = checkout.repo / exported['package']
    location.write_text(location.read_text() + '\n')
    with pytest.raises(StewartError) as refused:
        input_receipts(checkout.repo, meta, meta['target_commit'])
    assert refused.value.reason == 'package_binding', 'even semantically harmless byte movement invalidates a pinned input'


def test_export_is_exclusive_and_partial_publication_is_retained(checkout, monkeypatch):
    import stewart.handoff as handoff

    _, collection, _ = captured(checkout)
    exported = export(checkout, collection, ['REPORT.md'])
    directory = (checkout.repo / exported['package']).parent
    before = support.snapshot_tree(directory)
    with pytest.raises(StewartError) as refused:
        export(checkout, collection, ['REPORT.md'])
    assert refused.value.reason == 'destination_exists' and support.snapshot_tree(directory) == before
    def fail_manifest(*args, **kwargs):
        raise OSError('synthetic publication failure')
    monkeypatch.setattr(handoff, 'write_receipt', fail_manifest)
    with pytest.raises(StewartError) as refused:
        export(checkout, collection, ['REPORT.md'], '.scratch/partial-package')
    assert refused.value.reason == 'export_failed' and refused.value.retained and refused.value.next_steps
    assert (checkout.repo / '.scratch/partial-package/source.json').is_file()
    assert not (checkout.repo / '.scratch/partial-package/manifest.json').exists()


def test_attempt_package_keeps_exact_streams_rows_and_receipt_and_refuses_substitution(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd)
    exp = support.prepared_experiment(checkout)
    released = release(checkout.ws, checkout.meta['audit_id'], review=support.REVIEW, actor='manager')
    result = run(checkout.ws, checkout.meta['audit_id'], release=released['release'], timeout=60)
    selectors = ['ATTEMPT.json', 'ledger.jsonl', 'child-receipt.json', 'stdout.txt', 'stderr.txt']
    exported = export_evidence(checkout.ws, checkout.meta['audit_id'], attempt=released['release'],
                               selectors=selectors, output='.scratch/attempt-package', actor='manager')
    assert len(package_inputs(checkout.repo, exported['package'])) == 7
    manifest = support.read_json(checkout.repo / exported['package'])
    for entry in manifest['entries']:
        payload = checkout.repo / exported['package']
        assert (payload.parent / entry['file']).read_bytes() == (Path(result['path']) / entry['selector']).read_bytes()
    assert result['record']['streams']['stdout.txt']['sha256'] == _hash.sha256_bytes(b'done\n')
    (exp.worktree / support.OUTPUT / 'ledger.jsonl').write_text('ignored live change')
    (Path(result['path']) / 'stdout.txt').write_text('replaced capture')
    with pytest.raises(StewartError) as refused:
        export_evidence(checkout.ws, checkout.meta['audit_id'], attempt=released['release'],
                        selectors=['stdout.txt'], output='.scratch/tampered', actor='manager')
    assert refused.value.reason == 'evidence_tampered'
    # The already-exported package stays valid; it is a separate pinned handoff.
    assert len(package_inputs(checkout.repo, exported['package'])) == 7
