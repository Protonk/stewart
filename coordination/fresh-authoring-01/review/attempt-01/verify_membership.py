"""Finite snapshot population checks only; no project or study code execution."""
from pathlib import Path
from datetime import datetime, timezone
import json

BASE = Path('.scratch/fresh-authoring-01/pilot-01')
manifest = json.loads((BASE / 'INTEGRATION-INPUTS.json').read_bytes())
index = {r['path']: r for r in manifest['files']}
checks = []
reads = []

def read(path):
    path = str(path)
    reads.append(path)
    return Path(index[path]['snapshot']).read_bytes()

def load(path):
    return json.loads(read(path))

def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})

populations = [
    ('author final outputs', 'coordination/fresh-authoring-01/author/attempt-01', BASE/'witness/final-01/FILES.json'),
    ('author final scratch', str(BASE/'author/attempt-01'), BASE/'witness/final-01/scratch/FILES.json'),
]
for rid in ('r01', 'r02', 'r03'):
    populations.extend([
        (rid+' final outputs', 'coordination/fresh-authoring-01/recipients/'+rid+'/attempt-01', BASE/'responses/second'/rid/'checkpoint/FILES.json'),
        (rid+' final scratch', str(BASE/'recipients'/rid/'attempt-01'), BASE/'responses/second'/rid/'scratch/FILES.json'),
    ])
for label, prefix, inventory_path in populations:
    inv = load(inventory_path)
    named = [r['source'] for r in inv['files']]
    observed = [p for p in index if p.startswith(prefix+'/')]
    check(label+': exactly the pinned original population', len(named) == len(set(named)) and set(named) == set(observed))
    for item in inv['files']:
        check(label+': copy equals pinned original '+item['source'], read(item['source']) == read(item['copy']))
env = load(BASE/'final-submission-01/SNAPSHOT.json')['envelope']
support = {r['id']:r['text'].encode() for r in env['support']}
for name, path in [('draft-helper-stdout.json', BASE/'commands/draft-01/stdout.json'), ('draft-coordinator-result.json', BASE/'commands/draft-01/RESULT.json')]:
    check(name+': exact attributed original', support[name] == read(path))
briefs = []
reveal_briefs = []
for rid in ('r01','r02','r03'):
    briefs.append(read('coordination/fresh-authoring-01/recipients/'+rid+'/BRIEF.md').replace(rid.encode(),b'RECIPIENT'))
    reveal_briefs.append(read('coordination/fresh-authoring-01/recipients/'+rid+'/REVEAL-GRANT.md').replace(rid.encode(),b'RECIPIENT'))
check('recipient briefs differ only by recipient identity', briefs[0] == briefs[1] == briefs[2])
check('reveal briefs differ only by recipient identity', reveal_briefs[0] == reveal_briefs[1] == reveal_briefs[2])
result = {'at':datetime.now(timezone.utc).isoformat(),'checks':checks,'passed':sum(r['passed'] for r in checks),'total':len(checks),'reads':reads,'scope':'Static final original-population and attribution checks; not continuous observation.'}
with (BASE/'review/attempt-01/INDEPENDENT-MEMBERSHIP-CHECKS.json').open('x') as stream:
    json.dump(result,stream,indent=2)
    stream.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','reads')},indent=2))
print(json.dumps([r for r in checks if not r['passed']],indent=2))
