"""Observe the first billable write at a loopback endpoint, across a placement file-size limit."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import shutil
import signal
import threading

from batch import Audit
from common import FILE_SIZE_LIMIT, catalog, file_hash, proposal, question_file, read_file, require, strict_json
from study import study_proposal


class Receiver(HTTPServer):
    def get_request(self):
        sock, address = super().get_request()
        self.connections += 1
        return sock, address


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length']))
        self.server.bodies.append({'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()})
        response = b'{"type":"error","error":{"type":"invalid_request_error","message":"offline control"}}'
        self.send_response(400)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):
        pass


def verify_result(value, writer):
    require(value['schema']=='stewart.c10-file-bound-controls/1' and value['writer_sha256']==writer
            and value['limit_bytes']==FILE_SIZE_LIMIT, 'file-bound control identity differs')
    small, fired, unchanged = value['cases']
    require([x['name'] for x in value['cases']]==['small-bounded','large-bounded','large-unbounded']
            and all(x['run_started'] and x['group_gone'] and x['supervisor_retained_stream'] for x in value['cases']),
            'file-bound control inventory differs')
    require(small['bounded'] and fired['bounded'] and not unchanged['bounded']
            and small['connections']==len(small['bodies'])==1
            and unchanged['connections']==len(unchanged['bodies'])==1
            and 0<small['capture_bytes']<FILE_SIZE_LIMIT<unchanged['capture_bytes']
            and 0<small['bodies'][0]['bytes']<unchanged['bodies'][0]['bytes']
            and fired['connections']==0 and fired['bodies']==[] and fired['exit']==-signal.SIGXFSZ
            and not fired['run_ended'] and small['run_ended'] and unchanged['run_ended']
            and fired['capture_bytes']==FILE_SIZE_LIMIT and fired['question_sha256']==unchanged['question_sha256']
            and all(x['hard_limit']==FILE_SIZE_LIMIT for x in (small,fired)),
            'file-size limit did not distinguish the first provider write')


def exercise(binary, root, key, *, local=False):
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    base = catalog()['open-ordinary']
    packet = proposal('rehearsal-only', rehearsal=True)
    cases = []
    for name, body, bound in [('small-bounded','Observe this local example.\\n',True),
                             ('large-bounded','Q'*(FILE_SIZE_LIMIT+4096)+'\\n',True),
                             ('large-unbounded','Q'*(FILE_SIZE_LIMIT+4096)+'\\n',False)]:
        template = root/(name+'-template')
        template.mkdir()
        shutil.copytree(base['root']/'materials', template/'materials')
        specimen = {**base,'question':body,'inquiry':'capture-file-limit'}
        (template/'question.md').write_bytes(question_file(specimen,packet,Path('/tmp')))
        p = study_proposal('rehearsal-only', [(name,template)],rehearsal=True)
        p['file_size_limit'] = FILE_SIZE_LIMIT if bound else None
        audit = Audit(binary,root/name,p,p['runs'][-1],mode='rehearse',local=local)
        audit.intake()
        audit.bound_folder = audit.evidence
        with Receiver(('127.0.0.1',0),Handler) as receiver:
            receiver.connections, receiver.bodies = 0,[]
            thread = threading.Thread(target=receiver.serve_forever)
            thread.start()
            try:
                try:
                    audit.command('run','run',audit.ref,key=key,endpoint=f'http://127.0.0.1:{receiver.server_port}')
                except RuntimeError:
                    if name!='large-bounded':
                        raise
            finally:
                receiver.shutdown()
                thread.join()
        command = strict_json(read_file(next(audit.evidence.glob('*-run.json'))))
        group_gone = False
        try:
            os.killpg(command['pid'],0)
        except ProcessLookupError:
            group_gone = True
        records = [strict_json(read_file(x)) for x in audit.log_folder().iterdir()]
        capture = audit.log_folder().parent/'runs/1/request-1.json'
        guard = strict_json(read_file(audit.evidence/'file-bound.json')) if bound else None
        # The independent supervisor records a file larger than the limit after
        # the placement, including the firing case where Stewart could not.
        stream = audit.evidence/'supervisor-control.bin'
        sample = b'S'*(FILE_SIZE_LIMIT+1)
        stream.write_bytes(sample)
        cases.append({'name': name, 'bounded':bound,'question_sha256':hashlib.sha256(body.encode()).hexdigest(),
            'run_started':sum(r['kind']=='run_started' for r in records)==1,
            'run_ended':any(r['kind']=='run_ended' for r in records),'group_gone':group_gone,
            'exit':command['exit'],'connections':receiver.connections,'bodies':receiver.bodies,
            'capture_bytes':capture.stat().st_size, 'capture_sha256':file_hash(capture),
            'hard_limit':guard['hard'] if guard else None, 'supervisor_retained_stream':stream.read_bytes()==sample})
    result = {'schema':'stewart.c10-file-bound-controls/1','writer_sha256':file_hash(binary),
              'limit_bytes':FILE_SIZE_LIMIT,'cases':cases}
    verify_result(result,result['writer_sha256'])
    return result
