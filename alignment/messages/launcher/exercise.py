"""The loopback fake provider and return-package check shared by the sanity and C10 launchers.

Sessions run inside an offline Linux container; nothing here contacts a real
provider. This is procedure apparatus, not part of the independent acceptance
driver, and it qualifies no model.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import threading
import time

from session_support import digest, write_json

# The Messages API version and compaction beta every request must carry. The
# sanity container's source archive holds only the Messages launcher, so these are
# kept here; the C10 tests compare them with the specification-derived values.
API_VERSION = '2026-10-21'
ANTHROPIC_BETA = 'compact-2026-09-04'


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
    # A non-compacted full-size history can exceed 1 MiB. Keep the fake bounded
    # by the procedural reviewer's maximum evidence-member size instead.
    max_request_bytes = 64 * 1024 * 1024

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
                    if self.path != '/v1/messages':
                        raise ValueError('unexpected endpoint')
                    if not 0 < size <= fake.max_request_bytes:
                        raise ValueError('request size outside fake provider bound')
                    body = self.rfile.read(size)
                    if len(body) != size:
                        raise ValueError('incomplete fake provider request body')
                    (evidence / f'request-{n}.json').write_bytes(body)
                    if auth_observer is not None:
                        auth_observer(n, (self.headers.get('x-api-key') or '').encode('latin1'))
                    if self.headers.get('x-api-key') != fake.key:
                        raise ValueError('request did not carry the synthetic credential')
                    if self.headers.get('anthropic-version') != API_VERSION:
                        raise ValueError('unexpected API version')
                    if self.headers.get('anthropic-beta') != ANTHROPIC_BETA:
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
