"""Captured acceptance-reader inputs and explicitly synthetic study differences.

This is test support, never a qualification or launch-authority source.
"""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent / 'acceptance'
ORIGINS = json.loads((HERE / 'ORIGINS.json').read_bytes())['records']


def captured(name):
    row = ORIGINS[name]
    stored = (HERE / row['path']).read_bytes()
    assert (len(stored), hashlib.sha256(stored).hexdigest()) == (row['stored_bytes'], row['stored_sha256'])
    raw = gzip.decompress(stored) if row['path'].endswith('.gz') else stored
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (row['bytes'], row['sha256'])
    return raw


def result(arch='arm64', run='readiness-02'):
    return json.loads(captured(run + '/driver-' + arch + '/evidence/RESULT.json'))


def case(value, name):
    return next(row for row in value['cases'] if row['id'] == name)


def release(value, name):
    return next(row for row in case(value, name)['variants'] if row['binary'] == 'release' and row['sabotage'] is None)


def study_result(arch='arm64', run='readiness-02'):
    """Add one invented c19 text failure and its summary consequences to a copy.

    No captured run demonstrates this study difference. Keeping the remaining
    full inventory and control results lets the reader's comparisons encounter
    real record shapes, including the historical skipped-case specimen.
    """
    value = result(arch, run)
    entry = case(value, 'c19.arrangement')
    variant = release(value, 'c19.arrangement')
    assert entry['outcome'] == variant['outcome'] == 'pass' and variant['checks_failed'] == 0
    entry['outcome'] = variant['outcome'] = 'fail'
    variant['checks_passed'] -= 1
    variant['checks_failed'] = 1
    variant['failed_names'] = ['open.system-bytes']
    variant['failures'] = [{'name': 'open.system-bytes', 'ok': False, 'detail': 'synthetic study difference'}]
    value['failed_cases'] = ['c19.arrangement']
    value['exit'] = 1
    for kind in ('cases', 'variants'):
        value['counts'][kind]['passed'] -= 1
        value['counts'][kind]['failed'] += 1
    value['counts']['checks']['passed'] -= 1
    value['counts']['checks']['failed_outside_controls'] += 1
    return value


def study_selftest(arch):
    """Project the matching one-check failure onto the full captured selftest."""
    assert captured('readiness-02/driver-' + arch + '/selftest.exit') == b'0\n'
    raw = captured('readiness-02/driver-' + arch + '/selftest.stdout')
    old = b'ok   docs.family open-inquiry\n'
    assert raw.count(old) == 1
    raw = raw.replace(old, b'FAIL docs.family open-inquiry (synthetic study difference)\n')
    old = b'self-test: 403 checks, 403 passed, 0 failed, 0 skipped\n'
    assert raw.endswith(old)
    return raw[:-len(old)] + b'self-test: 403 checks, 402 passed, 1 failed, 0 skipped\n'
