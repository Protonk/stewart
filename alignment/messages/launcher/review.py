"""Summarize retained sanity evidence without a provider call or archive mutation.

Reads verified exported tar members directly, never extracts them. Raw model
prose remains in the retained evidence; this report lists operations and usage.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_support import digest


def summarize(root):
    session = json.loads((root / 'container/RESULT.json').read_bytes())
    report = {'schema': 'stewart.sanity-review/1', 'mode': session['mode'],
        'outcome': session['outcome'], 'failures': session['failures'],
        'scenarios': session['scenarios'], 'exports': [], 'operations': []}
    for item in session.get('exports', []):
        scenario = item['scenario']
        if scenario not in ['live', 'submitted', 'unsubmitted', 'provider-rejected', 'interrupted', 'reflected-body', 'export-contamination', 'export-failure']:
            raise ValueError('unknown scenario in retained session')
        report['exports'].append({'scenario': scenario, 'outcome': item['outcome'], 'scan': item['scan']})
        if item['outcome'] != 'exported':
            continue
        path = root / 'container' / scenario / 'work.tar'
        if path.stat().st_size != item['archive']['bytes'] or digest(path.read_bytes()) != item['archive']['sha256']:
            raise ValueError('export differs from recorded digest: ' + scenario)
        with tarfile.open(path, 'r:') as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts:
                    raise ValueError('unsafe member name in retained export')
                if not member.isfile() or member.size > 2**20 or '/stage/' in member.name:
                    continue
                command = re.fullmatch(r'private/evidence/\d+-[^/]+\.json', member.name)
                record = re.fullmatch(r'private/archive/audits/[^/]+/(?:log/\d+|runs/\d+/(?:attempt-\d+-\d+|result-\d+))\.json', member.name)
                if not (command or record):
                    continue
                try:
                    value = json.load(archive.extractfile(member))
                except (UnicodeError, json.JSONDecodeError):
                    report['operations'].append({'scenario': scenario, 'source': member.name, 'unreadable': True})
                    continue
                entry = {'scenario': scenario, 'source': str(path.relative_to(root)) + '::' + member.name}
                if command:
                    entry.update(kind='command', operation=value.get('argv', [None, None])[1],
                        exit=value.get('exit'), started_at=value.get('started_at'), ended_at=value.get('ended_at'))
                else:
                    body = value.get('body', {})
                    entry.update(kind=value.get('kind'), at=value.get('at'))
                    if value.get('kind') == 'provider_attempt':
                        entry.update(request=body.get('request'), attempt=body.get('attempt'),
                            outcome=body.get('outcome'), then=body.get('then'), charged=body.get('charged'),
                            credential_reflection=body.get('credential_reflection'))
                    elif value.get('kind') == 'tool_result':
                        entry.update(tool=body.get('tool'), call=body.get('call'),
                            outcome=body.get('outcome'), replay_of=body.get('replay_of'), revision=body.get('revision'))
                report['operations'].append(entry)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        report = summarize(args.evidence)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(1, 'Review incomplete: ' + str(error) + '\n')
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Mode: {report['mode']}; recorded outcome: {report['outcome']}")
        for scenario in report['scenarios']:
            print(f"{scenario['scenario']}: ending={scenario['ending']}; auditor_submitted={scenario['auditor_submitted']}; delivery_verified={scenario['delivery_verified']}; closed={scenario['closed']}")
            print('  Usage (reported and estimated): ' + json.dumps(scenario['usage'], sort_keys=True))
        for item in report['exports']:
            print(f"{item['scenario']}: export={item['outcome']}; scan matches={item['scan']['files_with_matches']}; scan errors={item['scan']['errors']}")
        print(f"{len(report['operations'])} operation records indexed; --json includes their source locations.")
        if report['failures']:
            print('Recorded failures: ' + ', '.join(report['failures']))
    return bool(report['failures'])


if __name__ == '__main__':
    raise SystemExit(main())
