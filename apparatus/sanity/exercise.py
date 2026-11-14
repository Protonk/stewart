"""Rehearse the sanity run sheet against a loopback fake, never a real provider.

Run inside the offline Linux container through rehearse.py. This is procedure
development, not an addition to the independent acceptance driver or a model
qualification. Every subprocess gets a new, minimal environment.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def verify_package(package, manifest_bytes):
    """Compare delivered members to the independently retained seal manifest."""
    manifest = json.loads(manifest_bytes)
    if (package / 'manifest.json').read_bytes() != manifest_bytes:
        raise ValueError('delivered manifest differs from sealed manifest')
    expected = {'manifest.json'}
    for member in manifest['members']:
        name = member['name']
        if Path(name).name != name or name in expected:
            raise ValueError('unexpected or repeated member name')
        expected.add(name)
        path = package / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('member is not a regular file: ' + name)
        content = path.read_bytes()
        if len(content) != member['size'] or digest(content) != member['sha256']:
            raise ValueError('member bytes differ: ' + name)
    if {p.name for p in package.iterdir()} != expected or manifest['unproduced']:
        raise ValueError('unexpected membership or unproduced members')
    return manifest


class Fake:
    def __init__(self, mode, evidence, materials, question, auth_observer=None):
        self.mode, self.evidence = mode, evidence
        self.materials, self.question = materials, question
        self.key = 'stewart-rehearsal-NOT-A-CREDENTIAL-' + os.urandom(12).hex()
        self.calls, self.failures, self.citations = [], [], []
        self.requests = 0
        self.prepared = None
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                fake.requests += 1
                n = fake.requests
                try:
                    size = int(self.headers['Content-Length'])
                    if self.path != '/v1/messages' or not 0 < size < 1024 * 1024:
                        raise ValueError('unexpected endpoint or request size')
                    body = self.rfile.read(size)
                    (evidence / f'request-{n}.json').write_bytes(body)
                    if auth_observer is not None:
                        auth_observer(n, (self.headers.get('x-api-key') or '').encode('latin1'))
                    if self.headers.get('x-api-key') != fake.key:
                        raise ValueError('request did not carry the synthetic credential')
                    if self.headers.get('anthropic-version') != '2026-10-21':
                        raise ValueError('unexpected API version')
                    if self.headers.get('anthropic-beta') != 'compact-2026-09-04':
                        raise ValueError('unexpected compaction beta')
                    answer = fake.respond(json.loads(body))
                except Exception as error:
                    fake.failures.append(str(error))
                    answer = 400, {'error': {'type': 'rehearsal_error', 'message': str(error)}}
                if answer is None:
                    # A request held until its client was signalled: the request
                    # bytes are witnessed, no response exists and none is sent.
                    write_json(evidence / f'exchange-{n}.json', {'status': None, 'response': 'withheld_after_signal',
                        'synthetic_auth_matched': self.headers.get('x-api-key') == fake.key, 'observed_at': time.time()})
                    self.close_connection = True
                    return
                status, response = answer
                raw = json.dumps(response, separators=(',', ':')).encode()
                (evidence / f'response-{n}.json').write_bytes(raw)
                write_json(evidence / f'exchange-{n}.json', {'status': status, 'synthetic_auth_matched': self.headers.get('x-api-key') == fake.key, 'observed_at': time.time()})
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(raw)

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.server.timeout = 1
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def tools(self, calls):
        blocks = []
        for name, operands in calls:
            tid = f'tool-{len(self.calls) + 1}'
            self.calls.append({'id': tid, 'name': name, 'input': operands})
            blocks.append({'type': 'tool_use', 'id': tid, 'name': name, 'input': operands})
        return self.message(blocks, 'tool_use')

    def message(self, content, stop, output=200):
        return 200, {'id': f'rehearsal-{self.requests}', 'type': 'message', 'role': 'assistant', 'model': 'rehearsal-only', 'content': content, 'stop_reason': stop, 'stop_sequence': None, 'usage': {'input_tokens': 1000, 'output_tokens': output}}

    def respond(self, body):
        if body['model'] != 'rehearsal-only' or 'output_config' in body:
            raise ValueError('rehearsal model or omitted effort changed')
        if body['messages'][0]['content'] != self.question:
            # Messages API permits the initial content as a text-block array.
            if body['messages'][0]['content'] != [{'type': 'text', 'text': self.question}]:
                raise ValueError('question body changed')
        if self.mode == 'provider-rejected':
            return 401, {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'Synthetic rehearsal rejection; no real credential was used.'}}
        results = {}
        for message in body['messages']:
            content = message.get('content')
            if message['role'] == 'user' and isinstance(content, list):
                for block in content:
                    if block.get('type') == 'tool_result':
                        results[block['tool_use_id']] = block['content']
        for call in self.calls:
            if call['id'] not in results:
                raise ValueError('tool reply missing')
            blocks = results[call['id']]
            reply = json.loads(blocks[0]['text'])
            if reply['outcome'] != 'completed':
                raise ValueError('tool refused: ' + call['name'])
            if call['name'] == 'read':
                source = call['input']['source']
                content = blocks[1]['text'] if len(blocks) > 1 else reply['data']['text']
                if content.encode() != self.materials[source]:
                    raise ValueError('read bytes differ from independent input')
            if call['name'] == 'prepare':
                self.prepared = reply['data']['prepared']
        if self.requests == 1:
            return self.tools([('list', {})])
        if self.requests == 2:
            return self.tools([('read', {'source': source}) for source in self.materials])
        if self.requests == 3:
            citations = [json.loads(results[c['id']][0]['text'])['data']['cite'] for c in self.calls if c['name'] == 'read']
            self.citations = citations
            return self.tools([
                ('record_account', {'text': 'For each sensor, the helper keeps the greatest timestamp encountered. Earlier timestamps arriving later do not replace it. Equal timestamps leave the first encountered reading in place. The supplied note does not settle which value the display should prefer in a tie.', 'citations': citations}),
                ('record_observation', {'text': 'Replacement uses a strict greater-than comparison, so equal timestamps do not replace the current reading.', 'citations': [citations[0]]}),
            ])
        if self.mode == 'unsubmitted':
            return self.message([{'type': 'text', 'text': 'Ending without confirmed submission, deliberately for this rehearsal.'}], 'end_turn')
        if self.requests == 4:
            return self.tools([('prepare', {})])
        if self.requests == 5 and self.prepared:
            return self.tools([('submit', {'prepared': self.prepared, 'confirm': True})])
        raise ValueError('unexpected extra request')

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        write_json(self.evidence / 'fake-summary.json', {'requests': self.requests, 'calls': self.calls, 'failures': self.failures, 'usage_is_synthetic': True})


class Procedure:
    def __init__(self, binary, root, template, mode):
        self.binary, self.mode = binary, mode
        self.work = root / mode
        self.work.mkdir()
        self.evidence = root / 'evidence' / mode
        self.evidence.mkdir(parents=True)
        self.folder, self.archive, self.destination = [self.work / name for name in ['submission', 'archive', 'returns']]
        shutil.copytree(template, self.folder)
        self.destination.mkdir()
        home = self.work / 'home'
        home.mkdir()
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(home), 'LANG': 'C.UTF-8'}
        text = (self.folder / 'question.md').read_text().replace('REPLACE-WITH-MODEL', 'rehearsal-only').replace('REPLACE-WITH-ABSOLUTE-DIRECTORY', str(self.destination))
        (self.folder / 'question.md').write_text(text)
        self.question = text.split('---\n', 2)[2]
        shutil.copytree(self.folder, self.evidence / 'input-witness')
        self.materials = {'materials/' + p.name: p.read_bytes() for p in sorted((self.folder / 'materials').iterdir(), reverse=True)}
        self.index = 0

    def command(self, label, *args, extra_env=None, raw=False, expected=0):
        self.index += 1
        stem = self.evidence / f'{self.index:02}-{label}'
        argv = [str(self.binary), *args] + ([] if raw else ['--json'])
        env = dict(self.env, **(extra_env or {}))
        started = time.time()
        with stem.with_suffix('.stdout').open('xb') as stdout, stem.with_suffix('.stderr').open('xb') as stderr:
            proc = subprocess.Popen(argv, env=env, cwd=self.work, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
            timed_out = False
            try:
                rc = proc.wait(timeout=40)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    rc = proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    rc = proc.wait()
        write_json(stem.with_suffix('.json'), {'argv': argv, 'exit': rc, 'timed_out': timed_out, 'started_at': started, 'ended_at': time.time(), 'environment_names': sorted(env)})
        if timed_out or rc != expected:
            raise ValueError(f'{label}: exit {rc}, expected {expected}; see {stem}')
        data = stem.with_suffix('.stdout').read_bytes()
        if raw:
            return data
        reply = json.loads(data)
        if reply.get("schema") != "stewart.reply/2":
            raise ValueError("unsupported Stewart reply schema")
        if reply['outcome'] != 'completed':
            raise ValueError(f'{label}: {reply}')
        return reply['data']

    def execute(self):
        new = self.command('new', 'new', str(self.folder), '--archive', str(self.archive))
        ref = new['reference']
        write_json(self.evidence / 'operator.json', {'reference': ref, 'status': [str(self.binary), 'status', ref, '--json'], 'stop': [str(self.binary), 'close', ref, '--json'], 'stop_ends_authoring': True})
        prepared = self.command('prepare', 'prepare', ref)
        self.command('commission', 'commission', ref, prepared['prepared'], '--i-am-finished')
        self.command('receipt-verify', 'receipt', ref, '--verify')
        witness = {'question-file': (self.folder / 'question.md').read_bytes(), 'question-body': self.question.encode(), **self.materials}
        for item, content in witness.items():
            captured = self.command('readback-' + item.replace('/', '-'), 'receipt', ref, '--read', item, raw=True)
            if captured != content:
                raise ValueError('receipt readback differs: ' + item)
        self.command('status-before', 'status', ref)
        provider_evidence = self.evidence / 'fake-provider'
        provider_evidence.mkdir()
        with Fake(self.mode, provider_evidence, self.materials, self.question) as fake:
            run = self.command('run', 'run', ref, expected=5 if self.mode == 'provider-rejected' else 0, extra_env={'ANTHROPIC_API_KEY': fake.key, 'STEWART_PROVIDER_URL': f'http://127.0.0.1:{fake.server.server_port}'})
        if fake.failures:
            raise ValueError('fake failed: ' + repr(fake.failures))
        before_close = self.command('status-after-run', 'status', ref)
        write_json(self.evidence / 'before-close.json', before_close)
        expected_ending = {'submitted': 'sealed', 'unsubmitted': 'ended_unsubmitted', 'provider-rejected': 'interrupted'}[self.mode]
        if run['ending'] != expected_ending:
            raise ValueError('incorrect run ending')
        if self.mode == 'provider-rejected' and run['cause'] != 'provider_rejected':
            raise ValueError('provider rejection lost')
        auditor_submitted = run['seal']['state'] == 'present' and run['seal']['actor'] == 'auditor'
        if auditor_submitted != (self.mode == 'submitted'):
            raise ValueError('submission classification failed')
        if auditor_submitted and run['delivery']['outcome'] != 'verified':
            raise ValueError('submitted answer was not delivered')
        if auditor_submitted:
            self.inspect_delivery(run)
        # The rehearsal explicitly commissions close after observation,
        # including preservation of unfinished work. It never resumes the model.
        closed = self.command('close', 'close', ref)
        if closed['closure'] == 'unfinished':
            if closed['unfinished_reason'] != 'awaiting_confirmation':
                raise ValueError('unexpected unfinished close')
            self.inspect_delivery(closed)
            token = closed['confirmation']
            closed = self.command('confirm-close', 'close', ref, '--confirm', token)
        if closed['closure'] != 'complete':
            raise ValueError('close did not complete')
        self.command('status-final', 'status', ref)
        packages = list(self.destination.iterdir())
        if len(packages) != 1:
            raise ValueError('unexpected return package count')
        # Compare the return to the sealed manifest in Stewart's retained archive,
        # not to a manifest trusted only because it travelled with the return.
        manifests = list(self.archive.glob('audits/*/seal/manifest-*.json'))
        if len(manifests) != 1:
            raise ValueError('sealed manifest not found')
        manifest_bytes = manifests[0].read_bytes()
        (self.evidence / 'seal-manifest.json').write_bytes(manifest_bytes)
        manifest = verify_package(packages[0], manifest_bytes)
        if manifest['seal']['actor'] != ('auditor' if auditor_submitted else 'manager'):
            raise ValueError('manager closure disguised as auditor submission')
        if auditor_submitted:
            answer = json.loads((packages[0] / 'answer.json').read_bytes())
            if not any(entry.get('citations') for entry in answer['entries']):
                raise ValueError('no cited recorded work')
            # Firing control on a separate copy; the actual delivered original stays intact.
            control = self.work / 'altered-return-control'
            shutil.copytree(packages[0], control)
            with (control / 'answer.md').open('ab') as changed:
                changed.write(b'\nDeliberate verifier control.\n')
            try:
                verify_package(control, manifest_bytes)
            except ValueError as error:
                write_json(self.evidence / 'verifier-control.json', {'fired': True, 'reason': str(error)})
            else:
                raise ValueError('altered return escaped verification')
            verify_package(packages[0], manifest_bytes)  # unchanged-original invariance
        return {'scenario': self.mode, 'ending_before_close': run['ending'], 'auditor_submitted': auditor_submitted, 'sealer_after_close': manifest['seal']['actor'], 'requests': fake.requests, 'usage': run['usage'], 'verified_delivery': True, 'closed': True, 'verifier_control': auditor_submitted}

    def inspect_delivery(self, data):
        manifests = list(self.archive.glob('audits/*/seal/manifest-*.json'))
        if len(manifests) != 1:
            raise ValueError('sealed manifest not found before confirmation')
        content = manifests[0].read_bytes()
        if digest(content) != data['seal']['manifest_sha256']:
            raise ValueError('manifest differs from the recorded seal')
        verify_package(Path(data['delivery']['location']), content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    template = Path(__file__).resolve().parent / 'submission'
    args.work.mkdir(exist_ok=True)
    evidence = args.work / 'evidence'
    evidence.mkdir()
    report = {'mode': 'offline-rehearsal', 'started_at': time.time(), 'scenarios': [], 'failures': [], 'model_calls': 0}
    for mode in ['submitted', 'unsubmitted', 'provider-rejected']:
        try:
            report['scenarios'].append(Procedure(args.binary.resolve(), args.work.resolve(), template, mode).execute())
        except Exception as error:
            report['failures'].append({'scenario': mode, 'error': str(error)})
    report['ended_at'] = time.time()
    write_json(evidence / 'RESULT.json', report)
    print(json.dumps(report, indent=2))
    return bool(report['failures'])


if __name__ == '__main__':
    raise SystemExit(main())
