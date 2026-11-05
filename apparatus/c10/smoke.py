"""Native iteration against local fakes; no model calls or Linux qualification.

Use an existing native binary and a new absolute evidence directory. Retains every
audit and witness. The production launcher never enables this local process path.
"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import rehearsal_packet, write_json, file_hash, require
from batch import prepare_batch, execute_batch, credential_marker
from study import study_proposal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--case',help='One catalog case; default runs the whole rehearsal')
    parser.add_argument('--audit',help='One named audit/control from the rehearsal inventory')
    parser.add_argument('--check-operations',action='store_true',help='After an unsubmitted control, explicitly test manager close and collection')
    parser.add_argument('--submission',action='append',nargs=2,metavar=('ID','FOLDER'),
                        help='Add a hashed study template to the full rehearsal')
    args=parser.parse_args()
    require(args.evidence.is_absolute() and not args.evidence.exists(),'use a new absolute evidence directory')
    args.evidence.mkdir(mode=0o700)
    packet=study_proposal('rehearsal-only',args.submission,rehearsal=True) if args.submission else rehearsal_packet()
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
        print(item['audit'],item['state'],item.get('review',{}).get('failures',[]))
    print(f"Native iteration only: planned={report['planned']} observed={report['observed']} failed={report['failed']} not_started={report['not_started']} skipped_checks={len(report['skipped_checks'])}; model_calls=0")
    if args.check_operations and report['failed']==report['not_started']==0:
        from check_operations import exercise
        controls=exercise(args.evidence)
        print(f"Operator controls: run={controls['run']} passed={controls['passed']} failed={controls['failed']}; original snapshot unchanged={controls['original_snapshot_unchanged']}")
        return controls['failed']>0
    return report['failed'] > 0 or report['not_started'] > 0


if __name__=='__main__':
    raise SystemExit(main())
