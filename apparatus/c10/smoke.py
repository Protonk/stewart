"""Native iteration against local fakes; no model calls or Linux qualification.

Use an existing native binary and a new absolute evidence directory. Retains every
audit and witness. The production launcher never enables this local process path.
Each continued control gets its later placement through the same continuation
step the container runs, from a packet bound to its exported first snapshot.
"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import (CONTINUED, INTERRUPTION_POINTS, LIMITS, digest, rehearsal_packet, source_hash,
                    validate_packet, write_json, file_hash, require, read_file, strict_json)
from batch import prepare_batch, execute_batch, credential_marker, rehearsal_script
from placements import Refused, run_continuation
from study import study_proposal
from study_build import attach, draft
from verify import Evidence, verify


def continuation_packet(batch, audit, placement, script, results, evidence):
    """Bind a later placement the way a host would: from the newest exported snapshot's bytes.

    The expected ending comes from the fixed control; usage, reference and the
    newest log record come from the export, not from what the launcher will observe.
    """
    snapshot = sorted((results/audit).iterdir())[-1]
    e = Evidence(snapshot/'work.tar', strict_json(read_file(snapshot/'EXPORT.json'))['archive']['sha256'])
    try:
        usage = verify(e)['usage']
        logs = sorted((n for n in e.names if '/log/' in n), key=lambda n: int(n.rsplit('/', 1)[1][:-5]))
        head, reference = digest(e.read(logs[-1])), e.json('operator.json')['reference']
    finally:
        e.close()
    ending, cause = CONTINUED[script]['endings'][placement-2]
    return {'schema': 'stewart.c10-continuation/1', 'evidence': str(evidence), 'audit': audit,
        'container': 'stewart-c10-0-0', 'reference': reference, 'placement': placement,
        'max_placements': len(CONTINUED[script]['endings']),
        'prior': {'runs': placement-1, 'last_ending': ending, 'last_cause': cause, 'log_head_sha256': head,
                  'usage': {key: sum(usage[key].values()) for key in LIMITS}},
        'model': batch['model'], 'limits': batch['limits'], 'endpoint': batch['endpoint'], 'proxy': None,
        'interruption': None, 'permitted_request_attempts': 4, 'automatic_continuation': False,
        'stop_after_seconds': batch['stop_after_seconds'], 'spending_authority': batch['spending_authority'],
        'account': batch['account'], 'bindings': {**batch['bindings'], 'apparatus_sha256': source_hash()}}


def starts(root, placement):
    """How many times the service recorded starting this placement."""
    log = next((root/'archive/audits').iterdir())/'log'
    records = [strict_json(read_file(path)) for path in log.iterdir()]
    return sum(record['kind'] == 'run_started' and record['body']['run'] == placement for record in records)


def continue_with_attempt_controls(binary, evidence, path, audit, placement, key, witness, **options):
    """One continuation, surrounded by the controls on who may start it and how often.

    A wrong key is refused first and starts nothing; the right key then proceeds
    as the second attempt. Afterwards the same packet is refused twice over: by
    the attempt records, and, with those set aside in a scratch result folder,
    by the service's own count of placements.
    """
    private, results, root = evidence/'private', evidence/'results', evidence/'private'/audit
    def run(out, read_key):
        return run_continuation(binary, private, out, path, 'rehearse', read_key, local=True, witness=witness, **options)
    rows = []
    def record(name, ok, **facts):
        rows.append({'check': name, 'passed': bool(ok), **facts})
    wrong = run(results, lambda: b'c10-NONFUNCTIONAL-not-the-original-key')
    record('wrong-key-starts-nothing', wrong['attempt'] == 1 and wrong['placement_state'] == 'not_started'
           and wrong['failed'] is True and wrong['failure']['phase'] == 'credential.differs'
           and starts(root, placement) == 0 and not (root/'evidence'/f'placement-{placement:04d}').exists(),
           state=wrong['placement_state'], phase=wrong['failure']['phase'])
    result = run(results, lambda: key)
    record('right-key-proceeds-as-next-attempt', result['attempt'] == 2 and result['placement_state'] == 'observed'
           and starts(root, placement) == 1, state=result['placement_state'], starts=starts(root, placement))
    folder = results/'continuations'/f'{audit}-p{placement}'
    try:
        run(results, lambda: key)
        record('completed-placement-refuses-another-attempt', False)
    except Refused:
        record('completed-placement-refuses-another-attempt',
               sorted(item.name for item in folder.iterdir()) == ['attempt-1', 'attempt-2'] and starts(root, placement) == 1)
    scratch = evidence/'second-start-controls'/f'{audit}-p{placement}'
    scratch.mkdir(mode=0o700, parents=True)
    def unread():
        raise RuntimeError('the credential must not be requested')
    again = run(scratch, unread)
    record('service-run-count-refuses-without-attempt-records', again['attempt'] == 1 and again['placement_state'] == 'not_started'
           and again['failure']['phase'] == 'preflight.prior_runs' and starts(root, placement) == 1
           and not (scratch/'continuations'/f'{audit}-p{placement}'/'attempt-1/READY.json').exists(),
           state=again['placement_state'], phase=again['failure']['phase'])
    write_json(scratch/'CONTROLS.json', {'schema': 'stewart.c10-attempt-controls/1', 'checks': rows,
        'run': len(rows), 'passed': sum(row['passed'] for row in rows), 'failed': sum(not row['passed'] for row in rows)})
    return result, rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--case',help='One catalog case; default runs the whole rehearsal')
    parser.add_argument('--audit',help='One named audit/control from the rehearsal inventory')
    parser.add_argument('--check-operations',action='store_true',help='After an unsubmitted control, explicitly test manager close and collection')
    parser.add_argument('--submission',action='append',nargs=2,metavar=('ID','FOLDER'),
                        help='Add a hashed study template to the full rehearsal')
    parser.add_argument('--interface',type=Path,help='Native-only family-guidance specification; no live authority')
    parser.add_argument('--interruption',choices=INTERRUPTION_POINTS,
                        help='With exactly one --submission: rehearse it alone as an interruption commission, then its continuation')
    args=parser.parse_args()
    require(args.evidence.is_absolute() and not args.evidence.exists(),'use a new absolute evidence directory')
    args.evidence.mkdir(mode=0o700)
    packet=study_proposal('rehearsal-only',args.submission,rehearsal=True) if args.submission else rehearsal_packet()
    if args.interruption:
        # The shape of a live interrupted study: one supplied audit, a witnessed
        # point in its first placement and a separately bound second placement.
        require(args.submission and len(args.submission)==1 and not (args.interface or args.case or args.audit or args.check_operations),
                'an interruption rehearsal takes exactly one --submission and no other selection')
        packet.update(schema='stewart.interruption-commission/1',max_placements=2,
            interruption={'after':args.interruption,'signal':'SIGTERM'},
            runs=[run for run in packet['runs'] if run['submission_folder'] is not None])
        validate_packet(packet,rehearsal=True)
    if args.interface:
        packet=attach(packet,draft(strict_json(read_file(args.interface))))
    if args.case:
        packet['runs']=[r for r in packet['runs'] if r['case']==args.case and r['scenario']=='submitted']
        require(bool(packet['runs']),'unknown case')
    if args.audit:
        require(args.case is None,'choose --case or --audit')
        packet['runs']=[r for r in packet['runs'] if r['id']==args.audit]
        require(bool(packet['runs']),'unknown audit')
    require(not args.check_operations or any(r['id']=='control-unsubmitted' for r in packet['runs']),
            'operator checks need control-unsubmitted')
    packet['bindings']['binary_sha256']=file_hash(args.binary)
    write_json(args.evidence/'commission.json',packet)
    sessions=prepare_batch(args.binary.resolve(),args.evidence/'private',args.evidence/'results',packet,'rehearse',local=True)
    witness=args.evidence/'credential-witness'
    witness.mkdir()
    key=b'c10-NONFUNCTIONAL-'+os.urandom(24).hex().encode()
    (witness/'canary.bin').write_bytes(key)
    checks=args.evidence/'credential-check';checks.mkdir(mode=0o700)
    for audit in sessions:
        credential_marker(checks/(audit.root.name+'.json'),key)
    report=execute_batch(args.binary.resolve(),args.evidence/'private',args.evidence/'results',packet,'rehearse',key,sessions,witness,local=True)
    for item in report['audits']:
        print(item['audit'],item['placement'],item.get('review_before_close',{}).get('failures',[]))
    print(f"Native iteration only: planned={report['planned']} observed={report['observed']} failed={report['failed']} not_started={report['not_started']} skipped_checks={len(report['skipped_checks'])}; model_calls=0")
    failed=report['failed'] > 0 or report['not_started'] > 0
    if args.check_operations and not failed:
        from check_operations import exercise
        controls=exercise(args.evidence)
        print(f"Operator controls: run={controls['run']} passed={controls['passed']} failed={controls['failed']}; original snapshot unchanged={controls['original_snapshot_unchanged']}")
        failed=controls['failed']>0
    # Later placements, one separately bound packet each; a failed first placement gets none.
    whole=args.case is None and args.audit is None and not args.submission and not args.interface
    packets=args.evidence/'continuation-packets';packets.mkdir(mode=0o700)
    for item,run in zip(report['audits'],packet['runs']):
        script=rehearsal_script(packet,run)
        if script not in CONTINUED or item.get('expected_observation') is not True:
            continue
        for placement in range(2,len(CONTINUED[script]['endings'])+1):
            path=packets/f"{run['id']}-p{placement}.json"
            write_json(path,continuation_packet(packet,run['id'],placement,script,args.evidence/'results',args.evidence))
            result,attempts=continue_with_attempt_controls(args.binary.resolve(),args.evidence,path,run['id'],placement,key,witness,
                operator_controls=args.check_operations,report_controls=args.check_operations and whole)
            review=result['review'] or {}
            print(f"{run['id']} placement {placement} attempt {result['attempt']}: {result['placement_state']}, expected_observation={result['expected_observation']}, "
                  f"ending={review.get('ending')}, export={(result['export'] or {}).get('outcome')}, review failures={review.get('failures')}, "
                  f"second_start={result['second_start']}, controls={result['controls']}")
            print(f"{run['id']} placement {placement} attempt controls: run={len(attempts)} passed={sum(row['passed'] for row in attempts)} "
                  f"failed={sum(not row['passed'] for row in attempts)}")
            bad=result['failed'] or not all(row['passed'] for row in attempts)
            failed=failed or bad
            if bad:
                break
    held=args.evidence/'private/control-reminder-spent'
    if not failed and held.exists():
        # The held control always has a request aborted on the wire to build these on.
        from check_review import exercise_cut_off
        controls=exercise_cut_off(held,args.evidence/'cut-off-controls',key)
        print(f"Cut-off body controls: run={controls['run']} passed={controls['passed']} failed={controls['failed']} "
              f"controls_fired={controls['controls_fired']}/{controls['controls']}; original unchanged={controls['original_unchanged']}")
        failed=controls['failed']>0 or not controls['original_unchanged']
    return failed


if __name__=='__main__':
    raise SystemExit(main())
