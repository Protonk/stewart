"""Independent final static evidence checks. Supplied programs are inert bytes."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

ROOT = Path('/Users/raccoon/Desktop/Experiments/stewart')
SCRATCH = ROOT / '.scratch/receipt-challenge-01'
OUT = SCRATCH / 'review/attempt-01/integration-check-01'
BASELINE = SCRATCH / 'INTEGRATION-INPUTS-01.json'
DELTA = SCRATCH / 'INTEGRATION-DELTA-02.json'
checks = []
observations = {}


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Repeated control key: ' + key)
        value[key] = item
    return value


def reject(value):
    raise ValueError('Nonfinite JSON: ' + value)


def finite(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('Nonfinite float: ' + value)
    return parsed


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=reject, parse_float=finite)


def check(name, value):
    checks.append({'check': name, 'passed': bool(value)})


def expected(row):
    return {key: row[key] for key in ('bytes', 'sha256')}


def write(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)


def main():
    baseline_bytes = BASELINE.read_bytes()
    baseline = decode(baseline_bytes)
    pins = {row['source']: row for row in baseline['files']}
    observations['baseline_identity'] = identity(baseline_bytes)
    check('257 unique frozen sources', len(pins) == len(baseline['files']) == 257)
    check('expected integration manifest', identity(baseline_bytes)['sha256'] ==
          'a63beab1c04e2677b642f5f750d0b3ee631b30ac9530f4e425b81aa55faf2ac9')
    data = {}
    for source, row in pins.items():
        data[source] = (ROOT / row['snapshot']).read_bytes()
        check('frozen identity ' + source, identity(data[source]) == expected(row))

    def raw(source):
        return data[source]

    def obj(source):
        return decode(raw(source))

    delta_bytes = DELTA.read_bytes()
    delta = decode(delta_bytes)
    observations['delta_identity'] = identity(delta_bytes)
    delta_names = {row['source'] for row in delta['files']}
    check('four exact revised report sources', delta_names == {
        'coordination/receipt-challenge-01/' + name for name in
        ('RESULT.md', 'OBSERVATIONS.md', 'PROVISIONAL-INTERFACE.md', 'REVIEW-DISPOSITION.md')})
    for row in delta['files']:
        check('delta frozen ' + row['source'], identity((ROOT / row['snapshot']).read_bytes()) == expected(row))
        check('delta current ' + row['source'], identity((ROOT / row['source']).read_bytes()) == expected(row))
    mutable_accounts = {'coordination/COORDINATOR-NOTES.md', 'coordination/receipt-challenge-01/PROGRESS.md'}
    observations['mutable_accounts_not_used_to_replace_baseline'] = sorted(mutable_accounts)
    for source, row in pins.items():
        if source not in delta_names | mutable_accounts:
            check('current unchanged ' + source, identity((ROOT / source).read_bytes()) == expected(row))

    for manifest, count, allowed_changes in [
        ('PACKET-REVIEW-INPUTS-01.json', 55, set()),
        ('VARIANT-INPUTS-01.json', 109, {'coordination/receipt-challenge-01/' + name for name in
             ('PROGRESS.md', 'PROVISIONAL-INTERFACE.md', 'REVIEW-DISPOSITION.md', 'packets.py')})]:
        old = obj('.scratch/receipt-challenge-01/' + manifest)
        shared = [row for row in old['files'] if row['source'] in pins]
        changed = {row['source'] for row in shared if expected(row) != expected(pins[row['source']])}
        observations[manifest] = {'shared': len(shared), 'changed_sources': sorted(changed)}
        check(manifest + ' full admitted population', len(shared) == count)
        check(manifest + ' immutable evidence preserved', changed == allowed_changes)

    freeze = obj('.scratch/receipt-challenge-01/READER-FREEZE.json')
    check('reader freeze exactly 23 unique sources', len(freeze['files']) == len({r['source'] for r in freeze['files']}) == 23)
    for row in freeze['files']:
        check('reader freeze witness ' + row['source'], identity((ROOT / row['snapshot']).read_bytes()) == expected(row) == identity(raw(row['source'])))
    for reader in ('r01', 'r02', 'r03', 'r04'):
        for name in ('MEMO.md', 'READS.json', 'PROGRESS.md'):
            source = 'coordination/receipt-challenge-01/recipients/' + reader + '/attempt-01/' + name
            check(reader + ' required readable ' + name, bool(raw(source).decode('utf-8').strip()))
        ledger = obj('coordination/receipt-challenge-01/recipients/' + reader + '/attempt-01/READS.json')
        check(reader + ' ledger identity', ledger['reader'] == reader and ledger['attempt'] == 'attempt-01')
        returned = obj('.scratch/receipt-challenge-01/READER-RETURN-' + reader + '.json')
        check(reader + ' coordinator stopped observation', returned['worker'] == '/root/receipt_' + reader and 'completed/stopped' in returned['observed'])

    packets = obj('.scratch/receipt-challenge-01/READER-PACKETS.json')['packets']
    check('packet mapping', [(p['reader'], p['author'], p['kind']) for p in packets] ==
          [('r01', 'a01', 'original'), ('r02', 'a01', 'reduced'), ('r03', 'a02', 'original'), ('r04', 'a02', 'reduced')])
    packet_data = {}
    packet_objects = {}
    for p in packets:
        reader = p['reader']
        prefix = '.scratch/receipt-challenge-01/reader-packets/' + reader + '/'
        contents = {r['path'][len(prefix):]: raw(r['path']) for r in p['files']}
        packet_data[reader] = contents
        manifest, returned = decode(contents['RETURN-MANIFEST.json']), decode(contents['RETURN.raw'])
        field, primary = ('support', 'answer') if p['author'] == 'a01' else ('artifacts', 'text')
        id_field = 'id' if field == 'support' else 'name'
        check(reader + ' extracted primary independently matches', returned[primary].encode() == contents['primary.txt'])
        check(reader + ' artifact population and bytes independently match', len(returned[field]) == len(manifest['artifacts']) and all(
            a[id_field] == m['submitted_name'] and a['text'].encode() == contents[m['file']]
            for a, m in zip(returned[field], manifest['artifacts'])))
        check(reader + ' raw identity independently matches', identity(contents['RETURN.raw']) == manifest['raw'])
        check(reader + ' all issued packet identities', all(identity(raw(r['path'])) == expected(r) for r in p['files']))
        packet_objects[reader] = (manifest, returned, {a[id_field]: a['text'].encode() for a in returned[field]})
        check(reader + ' expected whole companion membership',
              ({'payload.raw', 'SNAPSHOT.json'} <= set(packet_objects[reader][2])) == (p['kind'] == 'original'))

    observations['packet_file_counts'] = {r: len(v) for r, v in packet_data.items()}
    check('48 delivered packet files', sum(observations['packet_file_counts'].values()) == 48)
    original_observations = {}
    for reader in ('r01', 'r03'):
        contents = packet_data[reader]
        artifacts = packet_objects[reader][2]
        payload_bytes, snapshot = artifacts['payload.raw'], decode(artifacts['SNAPSHOT.json'])
        payload = decode(payload_bytes)
        receipt = decode(contents['base/ACCEPTED.json'])
        answer = identity(payload['answer'].encode())
        support = [dict(position=i, id=a['id'], **identity(a['text'].encode())) for i, a in enumerate(payload['support'])]
        observed = {'raw_transport': identity(payload_bytes), 'primary_text_field': 'answer',
                    'decoded_primary_text_utf8': answer, 'artifact_array_field': 'support',
                    'decoded_artifact_text_utf8_in_submission_order': support,
                    'decoded_primary_and_artifact_utf8_bytes': answer['bytes'] + sum(a['bytes'] for a in support)}
        original_observations[reader] = observed
        check(reader + ' independent receipt raw comparison', receipt['raw_transport'] == identity(payload_bytes))
        check(reader + ' independent decoded envelope equality', snapshot['envelope'] == payload)
        check(reader + ' independent complete byte observations', snapshot['byte_observations'] == observed)
        check(reader + ' capture metadata equality', snapshot['capture_metadata'] == receipt['capture_metadata'])

    r01 = obj('.scratch/receipt-challenge-01/recipients/r01/attempt-01/check_bindings.json')
    check('r01 reported input identities exact', r01['input_identities'] == {n: identity(b) for n, b in packet_data['r01'].items()})
    check('r01 13 packet and four origins comparisons', len(r01['packet_manifest_checks']) == 13 and all(r['equal'] for r in r01['packet_manifest_checks']) and len(r01['origin_checks']) == 4 and all(r['equal'] for r in r01['origin_checks']))
    check('r01 reported computed text identities exact', r01['decoded_answer_identity'] == original_observations['r01']['decoded_primary_text_utf8'] and r01['decoded_support_identities'] == original_observations['r01']['decoded_artifact_text_utf8_in_submission_order'])
    r01_flags = ['return_raw_matches_manifest', 'return_answer_matches_primary_exact_utf8', 'acceptance_payload_binding_equal', 'snapshot_raw_binding_equal', 'snapshot_envelope_equals_decoded_payload', 'acceptance_snapshot_metadata_equal', 'expected_identity_matches_payload', 'answer_identity_equal', 'support_identities_equal', 'decoded_total_equal']
    check('r01 stated central results true', all(r01[k] is True for k in r01_flags))
    payload_bytes = packet_objects['r01'][2]['payload.raw']
    payload = decode(payload_bytes)
    controls = r01['comparison_controls']
    space = payload_bytes + b' '
    serialized = (json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n').encode()
    for name, candidate in [('trailing_space', space), ('reserialized', serialized)]:
        check('r01 control ' + name + ' exact operand', identity(candidate) == controls[name + '_input_identity'])
        check('r01 control ' + name + ' fires with semantic invariance', identity(candidate) != identity(payload_bytes) and decode(candidate) == payload)
    changed = dict(payload, answer=payload['answer'] + ' ')
    check('r01 changed answer defeats envelope comparison', changed != payload and controls['snapshot_answer_appended_space_detected_by_direct_comparison'] is True and controls['snapshot_raw_label_unchanged_in_that_comparison'] is True)

    r03 = obj('.scratch/receipt-challenge-01/recipients/r03/attempt-01/CHECKS.json')
    check('r03 reported input identities exact', r03['input_byte_identities'] == {n: identity(b) for n, b in packet_data['r03'].items()})
    check('r03 fifteen recorded comparisons', len(r03['checks']) == 15 and all(v is True for v in r03['checks'].values()) and r03['all_checks_true'] is True)
    check('r03 reported full observations exact', r03['independently_computed_byte_observations'] == original_observations['r03'])

    for reader, filename, entries_key, observed_key, flag in [('r02', 'CHECKS.json', 'packet_identities', 'observed', 'equals_packet_identity'), ('r04', 'inspection.json', 'packet_checks', 'observed', 'matches_packet')]:
        result = obj('.scratch/receipt-challenge-01/recipients/' + reader + '/attempt-01/' + filename)
        contents = packet_data[reader]
        check(reader + ' reported packet identity population', {r['file'] for r in result[entries_key]} == set(contents) - {'PACKET.json'} and len(result[entries_key]) == len(contents) - 1)
        check(reader + ' all reported identity operands exact', all(r[observed_key] == identity(contents[r['file']]) and r[flag] is True for r in result[entries_key]))
        check(reader + ' intentional check input scope', set(result['intentional_packet_reads']) == {str(ROOT / ('.scratch/receipt-challenge-01/reader-packets/' + reader + '/' + name)) for name in contents})
        check(reader + ' neither original companion is selected', not ({'payload.raw', 'SNAPSHOT.json'} & set(packet_objects[reader][2])))
    r02 = obj('.scratch/receipt-challenge-01/recipients/r02/attempt-01/CHECKS.json')
    check('r02 reported two retained and no historical companions', r02['support_counts'] == {'manifest': 2, 'return': 2} and r02['historical_companion_selected'] == {'payload.raw': False, 'SNAPSHOT.json': False})
    lines = packet_data['r02']['base/capture.py'].decode().splitlines()
    check('r02 source excerpts exact without execution', all(e['text'] == '\n'.join(str(i) + ': ' + lines[i-1] for i in range(e['first_line'], e['last_line'] + 1)) for e in r02['candidate_writer_excerpts']))
    r04 = obj('.scratch/receipt-challenge-01/recipients/r04/attempt-01/inspection.json')
    check('r04 zero artifacts and available label comparison', r04['selected_artifact_count'] == r04['manifest_artifact_count'] == 0 and r04['receipt_raw_transport_equals_origins_payload_identity'] is True)
    final = obj('.scratch/receipt-challenge-01/recipients/r04/attempt-01/final-verification.json')
    check('r04 final required outputs identity', len(final['files']) == 3 and final['required_outputs_verified'] is True and all(identity(raw(str(Path(r['path']).relative_to(ROOT)))) == expected(r) and r['readable_nonempty_utf8'] is True for r in final['files']))

    for author in ('a01', 'a02'):
        returned = obj('.scratch/receipt-challenge-01/AUTHOR-RETURN-' + author + '.json')
        check(author + ' returned/stopped attribution', returned['worker'] == '/root/receipt_' + author and 'stopped before original capture' in returned['state'])
        for kind in ('original', 'reduced'):
            prefix = '.scratch/receipt-challenge-01/captures/' + author + '/' + kind + '/'
            result = obj(prefix + 'CHECKS.json')
            check(author + ' ' + kind + ' recorded nine successful checks', result['exit'] == 0 and result['passed'] == result['total'] == len(result['checks']) == 9 and all(v is True for v in result['checks'].values()))
            command, ended, pid = obj(prefix + 'COMMAND.json'), obj(prefix + 'EXIT.json'), obj(prefix + 'PID.json')
            check(author + ' ' + kind + ' helper invocation and outcome', command['argv'][:4] == ['/usr/bin/python3', '-I', '-B', '-S'] and command['argv'][4] == str(ROOT / 'coordination/receipt-challenge-01/capture.py') and ended['exit'] == 0 and ended['pid'] == pid['pid'] and raw(prefix + 'stderr') == b'')
        provenance = obj('coordination/receipt-challenge-01/variants/' + author + '/PROVENANCE.json')
        check(author + ' recorded four transformation checks', provenance['passed'] == provenance['total'] == len(provenance['checks']) == 4 and all(v is True for v in provenance['checks'].values()))
    companion = obj('.scratch/receipt-challenge-01/ORIGINAL-COMPANION-CHECKS.json')
    check('four original companion checks retained', companion['passed'] == companion['total'] == len(companion['checks']) == 4 and all(r['passed'] is True for r in companion['checks']))

    integration = obj('.scratch/receipt-challenge-01/INTEGRATION-CHECKS-01.json')
    check('root 289 unique successful recorded checks', integration['passed'] == integration['total'] == len(integration['checks']) == len({r['check'] for r in integration['checks']}) == 289 and all(r['passed'] is True for r in integration['checks']))
    check('root exact retained checker source', raw('coordination/receipt-challenge-01/verify.py') == raw('.scratch/receipt-challenge-01/integration-check-01/verify.py'))
    for directory, filename, stdout in [('integration-check-01', 'verify.py', b'289 / 289 integration checks\n'), ('packet-assembly-01', 'packets.py', b'Four exact recipient packets created.\n')]:
        prefix = '.scratch/receipt-challenge-01/' + directory + '/'
        command, ended, pid = obj(prefix + 'COMMAND.json'), obj(prefix + 'EXIT.json'), obj(prefix + 'PID.json')
        check(directory + ' exact invocation prefix', command['argv'][:5] == ['/usr/bin/python3', '-I', '-B', '-S', str(ROOT / ('coordination/receipt-challenge-01/' + filename))] and command['cwd'] == str(ROOT))
        check(directory + ' recorded success and streams', ended['pid'] == pid['pid'] and ended['exit'] == 0 and raw(prefix + 'stderr') == b'' and raw(prefix + 'stdout') == stdout)
    check('packet builder remains reviewed version02', identity(raw('coordination/receipt-challenge-01/packets.py')) == {'bytes': 7225, 'sha256': '503475c8e76167bebd4a4f135b3321324dc92203ebacd4f24c4ee799d3503407'})
    observations['retained_run_counts'] = {'new_helper_captures': 4, 'recorded_capture_checks': 36, 'transformations': 2, 'recorded_transformation_checks': 8, 'original_companion_checks': 4, 'root_integration_checks': 289, 'packet_assembly_invocations': 1}


if __name__ == '__main__':
    OUT.mkdir(exist_ok=False)
    write('check.py', Path(__file__).read_bytes())
    write('COMMAND.json', (json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'argv': ['/usr/bin/python3', '-I', '-B', '-S', str(Path(__file__))], 'cwd': str(ROOT), 'scope': 'Reviewer-authored static comparisons only; supplied subject/helper/builder/reader/root checker code never imported or executed.'}, indent=2) + '\n').encode())
    error = None
    try:
        main()
    except Exception:
        error = traceback.format_exc()
    result = {'checks': checks, 'passed': sum(r['passed'] for r in checks), 'total': len(checks), 'observations': observations, 'error': error}
    exit_code = 0 if error is None and all(r['passed'] for r in checks) else 1
    result['exit'] = exit_code
    write('RESULT.json', (json.dumps(result, indent=2) + '\n').encode())
    output = str(result['passed']) + '/' + str(result['total']) + ' reviewer integration checks\n'
    write('stdout.txt', output.encode())
    write('stderr.txt', (error or '').encode())
    write('EXIT.json', (json.dumps({'exit': exit_code}) + '\n').encode())
    print(output, end='')
    if error:
        print(error, file=sys.stderr)
    raise SystemExit(exit_code)
