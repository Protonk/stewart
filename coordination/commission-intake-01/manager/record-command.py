import datetime, json, pathlib, subprocess, sys
root = pathlib.Path(__file__).parent
name, *argv = sys.argv[1:]
if not name or '/' in name or not argv:
    raise SystemExit('record identifier and argv required')
def write(suffix, data):
    with (root / (name + suffix)).open('xb') as stream:
        stream.write(data)
write('-command-start.json', json.dumps({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'argv':argv}, indent=2).encode()+b'\n')
try:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
except BaseException as error:
    write('-stdout.bin', b'')
    write('-stderr.bin', repr(error).encode()+b'\n')
    write('-exit.json', json.dumps({'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'launcher_exception':repr(error)}, indent=2).encode()+b'\n')
    raise
write('-stdout.bin', result.stdout)
write('-stderr.bin', result.stderr)
write('-exit.json', json.dumps({'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'returncode':result.returncode}, indent=2).encode()+b'\n')
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
