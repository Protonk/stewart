"""Compare captured bytes with frozen predictions; never execute subject code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / '.scratch/construction-execution-01'
CHECKS = []


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated control key: ' + key)
        value[key] = item
    return value


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def read(name):
    return decode((ROOT / name).read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(label, actual, expected):
    # Canonical JSON also distinguishes booleans from integers in observations.
    encode = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
    passed = encode(actual) == encode(expected)
    item = {'check': label, 'passed': passed}
    if not passed:
        item.update(actual=actual, expected=expected)
    CHECKS.append(item)


def compare():
    prep = read('PREPARATION.json')
    expected = read('EXPECTED.json')
    reservation = read('RUN-RESERVATION.json')
    before = read('PRELAUNCH.json')
    after = read('POSTRUN.json')
    end = read('EXIT.json')
    raw = (ROOT / 'observer.stdout').read_bytes()
    err = (ROOT / 'observer.stderr').read_bytes()
    check('preparation bound before launch', reservation['preparation_sha256'],
          sha((ROOT / 'PREPARATION.json').read_bytes()))
    check('launch driver matches reviewed identity', reservation['driver'],
          read('PREFLIGHT-DISPOSITION.json')['reviewed_driver'])
    check('frozen expected identity', sha((ROOT / 'EXPECTED.json').read_bytes()), prep['expected']['sha256'])
    check('stdout retained length', len(raw), end['stdout']['bytes'])
    check('stdout retained digest', sha(raw), end['stdout']['sha256'])
    check('stderr retained digest', sha(err), end['stderr']['sha256'])
    check('process exit', end['exit'], 0)
    check('stderr empty', len(err), 0)
    check('no run failure or intervention', [p.name for p in ROOT.iterdir()
          if p.name in ('RUN-FAILURE.json', 'TIMEOUT.json', 'KILL.json',
                        'PARENT-FAILURE-INTERVENTION.json', 'PARENT-FAILURE-KILL.json')], [])
    check('child termination precedes postrun inventory', after['termination_observed'], True)
    check('parent prelaunch stage', before['stage'], prep['stage'])
    check('parent prelaunch witness', before['witness'], prep['witness'])
    check('parent postrun stage', after['stage'], prep['stage'])
    check('parent postrun witness', after['witness'], prep['witness'])
    for name in ('stage_matches_preparation', 'witness_matches_preparation',
                 'interpreter_matches_preparation'):
        check('postrun ' + name, after[name], True)
    check('parent continuous preservation unestablished', after['continuous_preservation_established'], False)
    names = ('A-complete.jsonl', 'B-duplicate.jsonl', 'C-note-invariant.jsonl',
             'D-control-extinguished.jsonl', 'E-admission-before-reach.jsonl', 'F-parse-problem.jsonl')
    check('expected specimen membership', sorted(expected), sorted(names))
    records = [decode(line) for line in raw.splitlines()]
    check('exact record count', len(records), 8)
    check('exact record stage order', [r['stage'] for r in records], ['before'] + ['specimen'] * 6 + ['after'])
    check('exact specimen order', [r.get('name') for r in records[1:-1]], list(names))
    if len(records) != 8:
        raise ValueError('No positional interpretation of incomplete or extra records')
    first, last = records[0], records[-1]
    hashes = {}
    for name, item in prep['stage'].items():
        if item['kind'] != 'file':
            continue
        if name == 'specimens/observe-proposed.py':
            key = 'observer'
        else:
            key = name.replace('specimens/', 'authored/', 1)
        hashes[key] = item['sha256']
        raw_input = (ROOT / 'stage' / name).read_bytes()
        check('current protected file: ' + name, sha(raw_input), item['sha256'])
        check('independent staged witness: ' + name,
              (ROOT / 'witness/stage' / name).read_bytes() == raw_input, True)
    check('child before exact protected hashes', first['hashes'], hashes)
    check('child after exact protected hashes', last['hashes'], hashes)
    check('child observed Python version', first['python'], prep['probe']['version'])
    check('child observed executable', first['executable'], prep['probe']['executable'])
    check('child before preservation scope', first['continuous_preservation_established'], False)
    check('child after preservation scope', last['continuous_preservation_established'], False)
    check('child endpoint claim', last['same_at_endpoints'], True)
    for name, record in zip(names, records[1:7]):
        spec = expected[name]
        entry = prep['stage']['specimens/' + name]
        check(name + ' read digest', record['sha256'], entry['sha256'])
        check(name + ' read length', record['bytes'], entry['bytes'])
        for key in ('parsed_rows', 'raw_valid_compare_rows', 'summary', 'prerequisites'):
            check(name + ' ' + key, record[key], spec[key])
        if spec['parse_problem'] is None:
            check(name + ' parse problems', record['parse_problems'], [])
        else:
            problem = spec['parse_problem']
            check(name + ' parse problem count', len(record['parse_problems']), problem['count'])
            check(name + ' parse problem line', [x['line'] for x in record['parse_problems']], [problem['line']])
            check(name + ' parse problem category',
                  all(x['problem'].startswith(problem['prefix']) for x in record['parse_problems']), True)
    a, b, c, d, e, f = records[1:7]
    check('A/B unchanged raw count', b['raw_valid_compare_rows'], a['raw_valid_compare_rows'])
    check('A/B unchanged firing control', b['summary']['populations']['control'], a['summary']['populations']['control'])
    check('C note-only summary invariance', c['summary'], a['summary'])
    check('C note-only prerequisite invariance', c['prerequisites'], a['prerequisites'])
    check('D control responds to operand', d['summary']['populations']['control']['mismatches'], 0)
    check('E invalid admission not counted', e['summary']['populations']['ordinary']['admitted'], 0)
    check('F summary equals A despite separate parse gap', f['summary'], a['summary'])
    check('F prerequisites equal A despite separate parse gap', f['prerequisites'], a['prerequisites'])


if __name__ == '__main__':
    failure = None
    try:
        compare()
    except BaseException:
        failure = traceback.format_exc()
    result = {'at': datetime.now(timezone.utc).isoformat(), 'checks': CHECKS,
              'passed': sum(item['passed'] for item in CHECKS), 'total': len(CHECKS),
              'exception': failure, 'observer_invocations_by_this_comparator': 0,
              'code_sha256': sha(Path(__file__).read_bytes())}
    with (ROOT / 'COMPARISON-01.json').open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(f"Captured-output comparisons: {result['passed']}/{result['total']}; exception: {bool(failure)}")
    sys.exit(1 if failure or result['passed'] != result['total'] else 0)
