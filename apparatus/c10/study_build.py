"""Explicit, unqualified family-guidance builds for interface experiments.

The independent driver stays unchanged. Its text/version failures are retained,
reviewed and named in the build binding. All other checks, especially the native
credential cases, must still pass. This path supports family guidance only;
tools, validation, custody, rendering and submission keep their existing checks.
"""
import copy
from pathlib import Path
import re
import subprocess

from common import (compact, digest, fields, file_hash, identifier,
                    read_file, require, strict_json)
from launch import credential_cases_qualified, host_environment
import driver_core as spec

SCHEMA = 'stewart.interface-commission/1'
ARCHES = ('arm64', 'amd64')


def interface(value):
    fields(value, ['schema', 'id', 'family', 'version', 'instructions'], 'interface')
    require(value['schema'] == 'stewart.c10-interface/1' and identifier(value['id']),
            'invalid interface identity')
    require(value['family'] == 'open-inquiry' and type(value['version']) is int
            and value['version'] > 1, 'family guidance needs a new version')
    require(isinstance(value['instructions'], str) and 0 < len(value['instructions']) <= 16384
            and '\0' not in value['instructions'], 'invalid family guidance')
    return value


def expectations(value):
    fields(value, ['failed_cases', 'selftest_failures'], 'study expectations')
    require(isinstance(value['failed_cases'], dict) and bool(value['failed_cases']),
            'name the reviewed expected failed cases before binding the study')
    for name, checks in value['failed_cases'].items():
        require(isinstance(name, str) and not name.startswith('credentials.')
                and isinstance(checks, list) and bool(checks)
                and checks == sorted(set(checks))
                and all(isinstance(c, str) and c for c in checks), 'invalid expected case failures')
    require(isinstance(value['selftest_failures'], list) and bool(value['selftest_failures'])
            and value['selftest_failures'] == sorted(set(value['selftest_failures']))
            and all(isinstance(c, str) and c for c in value['selftest_failures']),
            'name the expected driver self-test failures')
    return value


def draft(value):
    """Native fake-provider iteration only; host selection refuses missing evidence."""
    return {'schema': 'stewart.c10-study-build/1', 'status': 'unqualified',
            'interface': interface(value), 'qualified_base_commit': None,
            'variant_commit': None, 'acceptance_folder': None,
            'source_archive_sha256': None, 'expected': None,
            'results_sha256': None, 'binaries_sha256': None}


def validate(value, *, bound=False):
    fields(value, ['schema', 'status', 'interface', 'qualified_base_commit', 'variant_commit',
            'acceptance_folder', 'source_archive_sha256', 'expected',
            'results_sha256', 'binaries_sha256'], 'study build')
    require(value['schema'] == 'stewart.c10-study-build/1' and value['status'] == 'unqualified',
            'study builds are explicitly unqualified')
    interface(value['interface'])
    for name, length in [('qualified_base_commit', 40), ('variant_commit', 40),
                         ('source_archive_sha256', 64)]:
        v = value[name]
        require((v is None and not bound) or isinstance(v, str)
                and re.fullmatch('[0-9a-f]{'+str(length)+'}', v), 'invalid study source identity')
    folder = value['acceptance_folder']
    require((folder is None and not bound) or isinstance(folder, str)
            and Path(folder).is_absolute() and not any(ord(c) < 32 for c in folder),
            'study acceptance needs an absolute retained folder')
    if value['expected'] is not None:
        expectations(value['expected'])
    else:
        require(not bound, 'missing study failure expectations')
    for name in ['results_sha256', 'binaries_sha256']:
        hashes = value[name]
        if hashes is None:
            require(not bound, 'missing study evidence identities')
        else:
            fields(hashes, ARCHES, name)
            require(all(isinstance(h, str) and re.fullmatch('[0-9a-f]{64}', h)
                        for h in hashes.values()), 'invalid study evidence digest')
    return value


def attach(packet, build):
    """Create a new packet schema; old packets and historical receipts stay intact."""
    packet = copy.deepcopy(packet)
    packet['schema'] = SCHEMA
    packet['study_build'] = validate(copy.deepcopy(build))
    for run in packet['runs']:
        run.setdefault('submission_folder', None)
    return packet


def family_id(packet, family):
    build = packet.get('study_build')
    value = interface(build['interface']) if build is not None else None
    return family + '/' + str(value['version'] if value and value['family'] == family else 1)


def system_bytes(packet, family, guidance=None):
    require(guidance is None or packet.get('study_build') is None, 'supplied guidance and a study-build override cannot be combined')
    result = spec.expected_system_bytes(family, guidance)
    build = packet.get('study_build')
    if build is not None:
        value = interface(build['interface'])
        if value['family'] == family:
            blocks = strict_json(result)
            blocks[1]['text'] = value['instructions']
            result = compact(blocks)
    return result


def check_result(result, baseline, expected, arch):
    """Refuse missing cases, new failure names, skipped checks or credential failures."""
    expectations(expected)
    require(result['schema'] == 'stewart.acceptance-driver/1'
            and result['interrupted'] is False and result['exit'] == 1,
            'study acceptance did not finish with its declared differences')
    require(result['platform']['system'] == 'Linux'
            and result['platform']['machine'] == ('aarch64' if arch == 'arm64' else 'x86_64')
            and result['platform']['euid'] != 0, 'study acceptance platform differs')
    require(credential_cases_qualified(result), 'study native credential checks did not pass')
    cases = result['cases']
    require([c['id'] for c in cases] == [c['id'] for c in baseline['cases']],
            'study acceptance omitted or changed the case inventory')
    actual = {}
    for case, base_case in zip(cases, baseline['cases']):
        failures = set()
        require(case['outcome'] in ['pass', 'fail'], 'study acceptance skipped a case')
        base_variants = {(v['binary'],v.get('sabotage')):v for v in base_case['variants']}
        require([(v['binary'],v.get('sabotage')) for v in case['variants']]
                == [(v['binary'],v.get('sabotage')) for v in base_case['variants']],
                'study acceptance omitted or changed a case variant')
        for variant in case['variants']:
            base_variant = base_variants[(variant['binary'],variant.get('sabotage'))]
            require(variant.get('parts_skipped') == base_variant.get('parts_skipped')
                    and not variant.get('skip_reason')
                    and variant['outcome'] in ['pass', 'fail'], 'study acceptance skipped a variant')
            if variant.get('sabotage') is None:
                failures.update(variant['failed_names'])
        if failures:
            actual[case['id']] = sorted(failures)
        require(case['outcome'] == 'pass' or case['id'] in expected['failed_cases'],
                'unexpected failed acceptance case')
    require(actual == expected['failed_cases'], 'acceptance failure names differ from the declared study')
    require(set(result['failed_cases']) == set(actual), 'acceptance failure inventory differs')
    counts = result['counts']['cases']
    require(counts['selected'] == counts['ran'] == len(cases) and counts['skipped'] == 0
            and counts['failed'] == len(actual), 'incomplete study acceptance counts')
    require(not result['controls_unassigned'], 'unassigned acceptance controls')
    for control in result['controls']:
        require(control['status'] == 'fired' or control['status'] == 'baseline_failed'
                and control['case'] in actual, 'an acceptance control did not fire')
    # A changed text can invalidate a control's baseline. Its full result remains
    # retained; any other broken control is refused, never relabelled a pass.
    allowed_controls = {c['sabotage'] for c in result['controls']
                        if c['status'] == 'baseline_failed' and c['case'] in actual}
    require(set(result['controls_never_fired']) <= allowed_controls,
            'unexpected unfired acceptance control')
    for broken in result['broken_checks']:
        require((broken['status'] == 'baseline_failed' and broken['case'] in actual
                 or broken['status'] == 'never_fired' and broken['case'] is None)
                and broken.get('sabotage') in allowed_controls,
                'unexpected broken acceptance check')
    require(result['counts']['driver_controls']['total'] == result['counts']['driver_controls']['fired'],
            'driver controls did not all fire')


def make(repo, qualification, spec_value, acceptance, expected):
    """Bind existing Linux evidence; never run containers or alter qualification."""
    acceptance = Path(acceptance)
    require(acceptance.is_absolute(), 'use an absolute study acceptance folder')
    value = draft(spec_value)
    value.update(qualified_base_commit=qualification['source_commit'],
                 variant_commit=read_file(acceptance/'host/commit.stdout').decode().strip(),
                 acceptance_folder=str(acceptance), expected=expectations(expected),
                 source_archive_sha256=file_hash(acceptance/'staging/source.tar'),
                 results_sha256={a: file_hash(acceptance/f'driver-{a}/evidence/RESULT.json') for a in ARCHES},
                 binaries_sha256={a: file_hash(acceptance/f'bin-{a}/stewart') for a in ARCHES})
    select(repo, qualification, value)
    return value


def select(repo, qualification, value):
    validate(value, bound=True)
    require(value['qualified_base_commit'] == qualification['source_commit'],
            'study qualified base differs')
    env = host_environment()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo, env=env).decode().strip()
    commit = value['variant_commit']
    require(git('rev-parse', commit+'^{commit}') == commit, 'study source commit is missing')
    require(git('merge-base', qualification['source_commit'], commit) == qualification['source_commit'],
            'study commit does not descend from its qualified base')
    require(bool(git('for-each-ref', '--contains', commit, '--format=%(refname)')),
            'keep the study source reachable under a ref')
    require(not git('diff', '--name-only', 'HEAD', commit, '--', 'apparatus/driver'),
            'study builds must retain the committed apparatus checkout\'s independent driver')
    changed = set(git('diff', '--name-only', qualification['source_commit'], commit, '--', 'service').splitlines())
    require('service/src/forms.rs' in changed and changed <= {
                'service/src/forms.rs', 'service/tests/manager.rs', 'service/tests/manager_seal.rs'},
            'this study route supports family guidance and its version assertions only')
    root = Path(value['acceptance_folder'])
    require(read_file(root/'host/commit.stdout').decode().strip() == commit
            and file_hash(root/'staging/source.tar') == value['source_archive_sha256'],
            'study acceptance source binding differs')
    archived = subprocess.check_output(['git','archive','--format=tar',commit,'service','apparatus','docs'],
                                       cwd=repo,env=env)
    require(digest(archived) == value['source_archive_sha256'], 'study archive is not the named commit')
    require(read_file(root/'host/DONE').startswith(b'done '), 'study acceptance stopped early')
    require(read_file(root/'host/DONE').rstrip().endswith(b' failures=4'),
            'study acceptance has unexpected host failures')
    require(not read_file(root/'host/worktree.stdout').strip(), 'study acceptance used a dirty source checkout')
    for arch in ARCHES:
        result_path = root/f'driver-{arch}/evidence/RESULT.json'
        require(file_hash(result_path) == value['results_sha256'][arch], 'study result digest changed')
        result = strict_json(read_file(result_path))
        base = strict_json(read_file(repo/qualification['evidence']['path']/f'driver-{arch}/evidence/RESULT.json'))
        check_result(result, base, value['expected'], arch)
        binary = root/f'bin-{arch}/stewart'
        require(file_hash(binary) == value['binaries_sha256'][arch]
                == result['binaries']['release']['sha256'], 'study binary digest differs')
        require(file_hash(root/f'bin-{arch}/stewart-test') == result['binaries']['test']['sha256'],
                'study test binary digest differs')
        for name, code in [('build-release', 0), ('build-test', 0), ('static-stewart', 0),
                           ('static-stewart-test', 0), ('build-glibc', 0),
                           ('static-stewart-glibc', 1), ('cmp-release-test', 1), ('run-release', 0)]:
            require(read_file(root/f'build-{arch}/{name}.exit') == (str(code)+'\n').encode(),
                    'study binary build/static controls differ')
        for name in ['evidence-copy', 'retention-archive', 'retention-list', 'retention-sha256']:
            require(read_file(root/f'driver-{arch}/{name}.exit') == b'0\n', 'study acceptance evidence incomplete')
        require(read_file(root/f'driver-{arch}/selftest.exit') == b'1\n', 'study self-test exit differs')
        lines = read_file(root/f'driver-{arch}/selftest.stdout').decode().splitlines()
        failed = sorted(line[5:].split(' (',1)[0] for line in lines if line.startswith('FAIL '))
        require(failed == value['expected']['selftest_failures']
                and not any(line.startswith('skip ') for line in lines)
                and lines[-1].endswith('0 skipped'), 'study self-test differs from declared failures')
    return root/'bin-arm64'
