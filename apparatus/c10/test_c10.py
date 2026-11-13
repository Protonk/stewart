"""Provider-free controls for C10 packets, evidence reads and launch authority."""
import argparse
from contextlib import redirect_stderr
import copy
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import subprocess
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
import c10
import common
from common import (HERE,catalog,compact,digest,inventory,proposal,question_file,read_file,
                    rehearsal_packet,source_hash,strict_json,tree_hash,validate_packet,write_json)
from batch import credential_marker,check_credential,export_snapshot
from batch import execute_batch
from verify import Evidence,PagingObservation,usage_counts,verify
import reporting
import connections
from study import (case_from_question, copy_submission, inspect_submission,
                   study_proposal)
from verify import tree_inventory_from_evidence
import study_build
import host_queue
from fake import follow_pages


def read_reply(call_id, source, start, end, size, text, next_start=None):
    """A captured tool_result for one material read page, shaped as INTERFACE 7.1 and 7.2 describe."""
    envelope = {'schema': 'stewart.reply/2', 'operation': 'read', 'outcome': 'completed',
                'data': {'source': source, 'kind': 'material', 'size': size, 'range': [start, end],
                         'complete': next_start is None, 'cite': {'source': source, 'start': start, 'end': end}},
                'next': [] if next_start is None else [{'tool': 'read', 'input': {'source': source, 'start': next_start}, 'why': 'rest'}]}
    return call_id, [{'type': 'text', 'text': json.dumps(envelope)}, {'type': 'text', 'text': text}]


class FakePagingTests(unittest.TestCase):
    """The scripted auditor follows next-page reads and verifies whole materials."""

    def setUp(self):
        self.big = ('line\n' * 30000).encode()  # three read pages
        self.small = b'short material\n'
        self.materials = {'materials/big.txt': self.big, 'materials/small.txt': self.small}
        self.page = 65536

    def pages(self):
        text = self.big.decode(); out, start = [], 0
        while start < len(text):
            end = min(len(text), start + self.page)
            if end < len(text): end = text.rfind('\n', start, end) + 1
            out.append((start, end)); start = end
        return out

    def test_single_page_materials_need_no_continuation(self):
        calls = [{'id': 't1', 'name': 'read', 'input': {'source': 'materials/small.txt'}}]
        results = dict([read_reply('t1', 'materials/small.txt', 0, len(self.small), len(self.small), self.small.decode())])
        continued = set()
        continuations, pages = follow_pages(calls, results, self.materials, continued)
        self.assertEqual(continuations, [])
        self.assertEqual(continued, set())
        self.assertEqual(pages, {'materials/small.txt': {0: self.small.decode()}})

    def test_multi_page_material_is_followed_once_and_verified_when_complete(self):
        spans = self.pages(); self.assertGreater(len(spans), 2)
        text = self.big.decode(); calls, results, continued = [], {}, set()
        for n, (start, end) in enumerate(spans):
            tid = f't{n + 1}'
            calls.append({'id': tid, 'name': 'read', 'input': {'source': 'materials/big.txt', 'start': start}})
            nxt = spans[n + 1][0] if n + 1 < len(spans) else None
            k, v = read_reply(tid, 'materials/big.txt', start, end, len(self.big), text[start:end], nxt); results[k] = v
            continuations, _ = follow_pages(calls, results, self.materials, continued)
            if nxt is None:
                self.assertEqual(continuations, [])
            else:
                self.assertEqual(continuations, [('read', {'source': 'materials/big.txt', 'start': nxt})])
                # Re-presenting the same results does not issue the continuation twice.
                self.assertEqual(follow_pages(calls, results, self.materials, continued)[0], [])

    def test_altered_page_bytes_are_refused_when_the_chain_completes(self):
        spans = self.pages(); text = self.big.decode(); calls, results = [], {}
        for n, (start, end) in enumerate(spans):
            tid = f't{n + 1}'; page = text[start:end]
            if n == 1: page = page[:-1] + 'x'
            calls.append({'id': tid, 'name': 'read', 'input': {'source': 'materials/big.txt', 'start': start}})
            nxt = spans[n + 1][0] if n + 1 < len(spans) else None
            k, v = read_reply(tid, 'materials/big.txt', start, end, len(self.big), page, nxt); results[k] = v
        with self.assertRaises(ValueError):
            follow_pages(calls, results, self.materials, set())

    def test_incomplete_page_without_next_read_is_refused(self):
        tid, blocks = read_reply('t1', 'materials/big.txt', 0, 100, len(self.big), self.big.decode()[:100], 100)
        envelope = json.loads(blocks[0]['text']); envelope['next'] = []; blocks[0]['text'] = json.dumps(envelope)
        with self.assertRaises(ValueError):
            follow_pages([{'id': tid, 'name': 'read', 'input': {'source': 'materials/big.txt'}}], {tid: blocks}, self.materials, set())


class StudyBuildTests(unittest.TestCase):
    def setUp(self):
        self.interface={'schema':'stewart.c10-interface/1','id':'guidance-test',
                        'family':'open-inquiry','version':2,'instructions':'Compose an account.'}
        self.expected={'failed_cases':{'c19.arrangement':['open.system-bytes']},
                       'selftest_failures':['docs.family open-inquiry']}
        def case(name):
            return {'id':name,'outcome':'pass','variants':[{'binary':'release','sabotage':None,
                'outcome':'pass','parts_skipped':[],'skip_reason':None,'failed_names':[]}]}
        cases=[case(name) for name in ['credentials.arguments','credentials.input',
               'credentials.reflection','credentials.process','c19.arrangement']]
        self.baseline={'cases':copy.deepcopy(cases)}
        cases[-1]['outcome']='fail';cases[-1]['variants'][0].update(outcome='fail',failed_names=['open.system-bytes'])
        self.result={'schema':'stewart.acceptance-driver/1','interrupted':False,'exit':1,
            'platform':{'system':'Linux','machine':'aarch64','euid':1000},'cases':cases,
            'failed_cases':['c19.arrangement'], 'controls_unassigned':[], 'controls_never_fired':[],
            'controls':[],'broken_checks':[],
            'counts':{'cases':{'selected':5,'ran':5,'skipped':0,'failed':1},
                      'driver_controls':{'total':1,'fired':1}}}

    def check(self,value):
        study_build.check_result(value,self.baseline,self.expected,'arm64')

    def test_declared_difference_is_not_qualification(self):
        self.check(self.result)
        packet=study_build.attach(rehearsal_packet(),study_build.draft(self.interface))
        validate_packet(packet,rehearsal=True)
        self.assertEqual(packet['study_build']['status'],'unqualified')
        self.assertEqual(study_build.family_id(packet,'open-inquiry'),'open-inquiry/2')
        self.assertEqual(study_build.family_id(packet,'comparison'),'comparison/1')

    def test_changed_guidance_keeps_orientation_and_other_family(self):
        packet=study_build.attach(rehearsal_packet(),study_build.draft(self.interface))
        old=strict_json(study_build.system_bytes({},'open-inquiry'))
        new=strict_json(study_build.system_bytes(packet,'open-inquiry'))
        self.assertEqual(new[0],old[0])
        self.assertEqual(new[1]['text'],self.interface['instructions'])
        self.assertEqual(study_build.system_bytes(packet,'comparison'),study_build.system_bytes({},'comparison'))
        self.assertEqual(study_build.system_bytes({},'open-inquiry'),study_build.spec.expected_system_bytes('open-inquiry'))

    def test_draft_and_false_qualification_cannot_reach_live(self):
        value=study_build.draft(self.interface)
        with self.assertRaises(ValueError):study_build.validate(value,bound=True)
        value['status']='qualified'
        with self.assertRaises(ValueError):study_build.validate(value)
        packet=rehearsal_packet();packet['study_build']=study_build.draft(self.interface)
        with self.assertRaises(ValueError):validate_packet(packet,rehearsal=True)

    def test_unexpected_failures_and_skips_are_refused(self):
        mutations=[lambda r:r['cases'][-1]['variants'][0]['failed_names'].append('custody.failed'),
            lambda r:r['cases'][0]['variants'][0].update(outcome='fail'),
            lambda r:r['cases'][0]['variants'][0]['parts_skipped'].append('process'),
            lambda r:r['cases'].pop(),lambda r:r.update(interrupted=True),
            lambda r:r['platform'].update(system='Darwin'),
            lambda r:r['counts']['driver_controls'].update(fired=0),
            lambda r:r['controls_unassigned'].append('unchecked'),
            lambda r:r['broken_checks'].append({'case':'unrelated','sabotage':'x','status':'baseline_failed'})]
        for mutation in mutations:
            value=copy.deepcopy(self.result);mutation(value)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.check(value)

    def test_credential_failure_cannot_be_declared_expected(self):
        expected=copy.deepcopy(self.expected)
        expected['failed_cases']['credentials.process']=['process.access']
        with self.assertRaises(ValueError):study_build.expectations(expected)

    def test_changed_text_control_baseline_remains_failed(self):
        value=copy.deepcopy(self.result)
        control={'case':'c19.arrangement','sabotage':'changed-text','status':'baseline_failed'}
        value['controls']=[control];value['controls_never_fired']=['changed-text']
        value['broken_checks']=[control,{'case':None,'sabotage':'changed-text','status':'never_fired'}]
        self.check(value)
        self.assertEqual(value['controls'][0]['status'],'baseline_failed')
        value['controls'][0]['status']='not_fired'
        with self.assertRaises(ValueError):self.check(value)

    def test_rehearsal_cannot_be_reused_for_another_variant(self):
        packet=study_build.attach(rehearsal_packet(),study_build.draft(self.interface))
        c10.check_rehearsal_inputs(packet,packet)
        changed=copy.deepcopy(packet);changed['study_build']['interface']['instructions']='Different.'
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(packet,changed)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsal_packet(),packet)

    def test_live_draft_refuses_before_credential_or_container(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            packet=study_build.attach(proposal('example-model'),study_build.draft(self.interface))
            packet['bindings']={k:'filled' for k in packet['bindings']}
            packet['account']={k:'approved' for k in packet['account']}
            packet['spending_authority']='Fixture only.'
            path=root/'packet.json';write_json(path,packet)
            args=argparse.Namespace(mode='live',evidence=c10.REPO/'.scratch/study-never-launched',
                commission=path,approved_commission=digest(read_file(path)),rehearsal=root,
                qualification='unused',connection=None)
            with mock.patch.object(c10,'bindings') as bind,mock.patch.object(c10,'hidden_credential') as key:
                with self.assertRaises(ValueError):c10.launch_batch(args)
                bind.assert_not_called();key.assert_not_called()

    def test_build_binding_checks_source_binary_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);acceptance=root/'study';base=root/'base'
            def put(path,data):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            qualification={'source_commit':'1'*40,'evidence':{'path':'base'}}
            put(acceptance/'host/commit.stdout',('2'*40+'\n').encode())
            put(acceptance/'host/worktree.stdout',b'')
            put(acceptance/'host/DONE',b'done fixture failures=4\n')
            put(acceptance/'staging/source.tar',b'archive fixture')
            for arch in ('arm64','amd64'):
                r=copy.deepcopy(self.result)
                r['platform']['machine']='aarch64' if arch=='arm64' else 'x86_64'
                r['binaries']={'release':{'sha256':digest(b'release fixture')},
                               'test':{'sha256':digest(b'test fixture')}}
                put(acceptance/f'bin-{arch}/stewart',b'release fixture')
                put(acceptance/f'bin-{arch}/stewart-test',b'test fixture')
                put(acceptance/f'driver-{arch}/evidence/RESULT.json',compact(r))
                put(base/f'driver-{arch}/evidence/RESULT.json',compact(self.baseline))
                for name in ('evidence-copy','retention-archive','retention-list','retention-sha256'):
                    put(acceptance/f'driver-{arch}/{name}.exit',b'0\n')
                put(acceptance/f'driver-{arch}/selftest.exit',b'1\n')
                put(acceptance/f'driver-{arch}/selftest.stdout',
                    b'FAIL docs.family open-inquiry (fixture)\nself-test: 2 checks, 1 passed, 1 failed, 0 skipped\n')
                for name,code in [('build-release',0),('build-test',0),('static-stewart',0),
                    ('static-stewart-test',0),('build-glibc',0),('static-stewart-glibc',1),
                    ('cmp-release-test',1),('run-release',0)]:
                    put(acceptance/f'build-{arch}/{name}.exit',(str(code)+'\n').encode())
            def git(argv,**kwargs):
                if argv[1]=='rev-parse':return ('2'*40+'\n').encode()
                if argv[1]=='merge-base':return ('1'*40+'\n').encode()
                if argv[1]=='for-each-ref':return b'refs/heads/study-fixture\n'
                if argv[1]=='diff':
                    if argv[-1]=='apparatus/driver':
                        self.assertEqual(argv[3],'HEAD')
                    return b'service/src/forms.rs\n' if argv[-1]=='service' else b''
                if argv[1]=='archive':return b'archive fixture'
                raise AssertionError(argv)
            with mock.patch.object(study_build.subprocess,'check_output',side_effect=git):
                value=study_build.make(root,qualification,self.interface,acceptance,self.expected)
                self.assertEqual(study_build.select(root,qualification,value),acceptance/'bin-arm64')
                for name in ['bin-arm64/stewart','bin-amd64/stewart-test',
                             'driver-arm64/evidence/RESULT.json','staging/source.tar',
                             'build-arm64/static-stewart.exit','driver-arm64/evidence-copy.exit']:
                    path=acceptance/name;old=path.read_bytes();path.write_bytes(old+b'changed')
                    with self.subTest(path=name),self.assertRaises(ValueError):
                        study_build.select(root,qualification,value)
                    path.write_bytes(old)
                changed=copy.deepcopy(value);changed['qualified_base_commit']='3'*40
                with self.assertRaises(ValueError):study_build.select(root,qualification,changed)
                def changed_driver(argv,**kwargs):
                    if argv[1]=='diff' and argv[-1]=='apparatus/driver':
                        return b'apparatus/driver/driver_core.py\n'
                    return git(argv,**kwargs)
                with mock.patch.object(study_build.subprocess,'check_output',side_effect=changed_driver):
                    with self.assertRaisesRegex(ValueError,'independent driver'):
                        study_build.select(root,qualification,value)


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bin=self.root/'bin';self.bin.mkdir()
        self.records=self.root/'records';self.records.mkdir()
        self.key='c10-NONFUNCTIONAL-private-test-value'
        self.response=self.bin/'response.json'
        self.configure()
        executable=self.bin/'security'
        executable.write_text('#!'+sys.executable+'\n'+'''import json, os, pathlib, sys, time
root=pathlib.Path(__file__).parent
value=json.loads((root/'response.json').read_text())
assert 'ANTHROPIC_API_KEY' not in os.environ
assert not sys.stdin.buffer.read()
with (root/'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(sys.argv[1:])+'\\n')
time.sleep(value['sleep'])
sys.stdout.write(value['stdout'])
sys.stderr.write(value['stderr'])
sys.exit(value['exit'])
''')
        executable.chmod(0o700)
        patch=mock.patch.dict(os.environ,{'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH',''),
                                         'ANTHROPIC_API_KEY':'never-read-this-ambient-key'})
        patch.start();self.addCleanup(patch.stop)

    def configure(self,exit=0,stdout=None,stderr='',sleep=0):
        self.response.write_text(json.dumps({'exit':exit,'stdout':self.key+'\n' if stdout is None else stdout,
                                            'stderr':stderr,'sleep':sleep}))

    def test_lookup_reuses_separate_process_without_recording_secret(self):
        for n in range(2):
            self.assertEqual(connections.lookup('synthetic',rehearsal=True,record=self.records/f'{n}.json'),self.key.encode())
        calls=[json.loads(line) for line in (self.bin/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls,[['find-generic-password','-s','stewart-provider','-a','synthetic','-w']]*2)
        self.assertTrue(all(self.key.encode() not in path.read_bytes() for path in self.records.iterdir()))

    def test_status_never_requests_or_prints_password(self):
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'c10.py'),'connection','status','synthetic'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['present'])
        self.assertNotIn(self.key.encode(),result.stdout+result.stderr)
        self.assertNotIn('-w',json.loads((self.bin/'calls.jsonl').read_text()))

    def test_failures_are_distinct_and_never_echo_tool_streams(self):
        for n,(status,message,code) in enumerate([
            (44,'The specified item could not be found in the keychain.','missing_item'),
            (128,'User canceled the operation.','access_denied'),
            (36,'User interaction is not allowed.','locked_keychain'),
            (44,'One or more parameters passed to a function were not valid.\nThe specified item could not be found.','lookup_failed'),
            (1,'unexpected diagnostic','lookup_failed')]):
            self.configure(exit=status,stderr=message+' '+self.key)
            with self.subTest(code=code),self.assertRaises(connections.ConnectionError) as caught:
                connections.lookup('synthetic',record=self.records/f'{n}.json')
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn(self.key,str(caught.exception))
            self.assertNotIn(self.key.encode(),(self.records/f'{n}.json').read_bytes())

    def test_missing_tool_and_deadline(self):
        with mock.patch.dict(os.environ,{'PATH':str(self.root/'absent')}):
            with self.assertRaises(connections.ConnectionError) as caught:connections.lookup('synthetic')
            self.assertEqual(caught.exception.code,'missing_tool')
        self.configure(sleep=2)
        with self.assertRaises(connections.ConnectionError) as caught:connections.lookup('synthetic',timeout=.05)
        self.assertEqual(caught.exception.code,'deadline')

    def test_rehearsal_and_credential_bounds(self):
        for value,code in [('functional-looking-value','not_synthetic'),('', 'invalid_credential'),
                           ('x'*4097,'invalid_credential'),('has space','invalid_credential')]:
            self.configure(stdout=value)
            with self.subTest(code=code),self.assertRaises(connections.ConnectionError) as caught:
                connections.lookup('synthetic',rehearsal=True)
            self.assertEqual(caught.exception.code,code)

    def test_label_mismatch_precedes_lookup_and_binding(self):
        packet=proposal('example-model');packet['account']['credential_label']='approved'
        with mock.patch.object(connections.subprocess,'run') as run:
            with self.assertRaises(connections.ConnectionError):connections.validate_label('different',packet)
            run.assert_not_called()
        for name in ['', '-flag', '../escape', 'line\nbreak']:
            with self.subTest(name=name),self.assertRaises(connections.ConnectionError):connections.lookup(name)
        self.assertFalse((self.bin/'calls.jsonl').exists())

    def test_live_mismatched_connection_refuses_before_launch(self):
        packet=proposal('example-model')
        packet['bindings']={key:'filled' for key in packet['bindings']}
        packet['account']={key:'approved' for key in packet['account']}
        packet['spending_authority']='Synthetic validation fixture; no provider calls.'
        path=self.root/'packet.json';write_json(path,packet)
        args=argparse.Namespace(mode='live',evidence=c10.REPO/'.scratch/c10-authority-never-created',
            commission=path,approved_commission=digest(read_file(path)),rehearsal=self.root,
            qualification='unused',connection='different')
        with mock.patch.object(c10,'bindings') as bind,mock.patch.object(c10,'connection_key') as lookup:
            with self.assertRaises(connections.ConnectionError):c10.launch_batch(args)
            bind.assert_not_called();lookup.assert_not_called()

    def test_saved_collection_uses_bound_label_and_only_pipe_input(self):
        root=self.root/'run';(root/'host').mkdir(parents=True);(root/'staging').mkdir()
        packet=proposal('example-model');packet['account']['credential_label']='synthetic'
        write_json(root/'staging/commission.json',packet)
        write_json(root/'host/RESULT.json',{'mode':'live','commission_sha256':digest(read_file(root/'staging/commission.json'))})
        write_json(root/'host/operator.json',{'container':'stewart-c10-1-2','audits':['open-ordinary-r1']})
        args=argparse.Namespace(evidence=root,audit='open-ordinary-r1',operation='collect',confirm=None,connection='synthetic')
        actual_run=subprocess.run
        observed=[]
        def run(argv,**kw):
            if argv[0]=='container':
                observed.append((argv,kw['input'],kw['env']))
                return subprocess.CompletedProcess(argv,0)
            return actual_run(argv,**kw)
        with mock.patch.object(c10.subprocess,'run',side_effect=run),mock.patch.object(c10,'hidden_credential') as prompt:
            self.assertEqual(c10.host_control(args),0)
            prompt.assert_not_called()
        self.assertEqual(observed[0][1],self.key.encode())
        self.assertNotIn(self.key,json.dumps([observed[0][0],observed[0][2]]))
        self.assertTrue(all(self.key.encode() not in path.read_bytes() for path in root.rglob('*') if path.is_file()))
        args.connection='different'
        with self.assertRaises(connections.ConnectionError):c10.host_control(args)


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.folder=self.root/'submission';(self.folder/'materials/empty').mkdir(parents=True)
        (self.folder/'materials/text.txt').write_bytes(b'unchanged\r\n')
        self.body='Exact question.\r\nSecond line.\n'
        self.case={'family':'open-inquiry','question':self.body,'inquiry':'study example','varies':'stw1:example'}
        (self.folder/'question.md').write_bytes(question_file(self.case,proposal('example-model'),'/placeholder'))

    def test_packet_separates_studies_and_keeps_full_rehearsal(self):
        packet=study_proposal('example-model',[('problem-a',self.folder)])
        self.assertEqual(packet['schema'],'stewart.study-commission/1')
        self.assertEqual(packet['runs'][0]['submission_sha256'],tree_hash(self.folder))
        self.assertEqual(len(study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True)['runs']),14)
        self.assertEqual(len(rehearsal_packet()['runs']),13)
        packet['schema']='stewart.c10-commission/1'
        with self.assertRaises(ValueError):validate_packet(packet)

    def test_exact_body_and_attributed_inquiry_survive_rendering(self):
        parsed=inspect_submission(self.folder,'problem-a')
        self.assertEqual(parsed['question'],self.body)
        packet=proposal('changed-model');packet['effort']='high'
        rendered=question_file(parsed,packet,'/actual/returns')
        self.assertEqual(rendered.split(b'---\n',2)[2],self.body.encode())
        for line in [b'model: changed-model\n',b'inquiry: study example\n',b'varies: stw1:example\n',b'effort: high\n']:
            self.assertIn(line,rendered)

    def test_changed_input_refuses_before_copy_and_empty_dirs_are_bound(self):
        expected=tree_hash(self.folder)
        copy_submission(self.folder,self.root/'copy',expected)
        self.assertEqual(tree_hash(self.root/'copy'),expected)
        (self.folder/'materials/empty').rmdir()
        with self.assertRaises(ValueError):copy_submission(self.folder,self.root/'wrong',expected)
        self.assertFalse((self.root/'wrong').exists())

    def test_template_identity_includes_directory_membership(self):
        evidence=Evidence(self.root)
        def member(name, raw):
            return {'path':name, 'type':'file', 'bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest()}
        expected = [{'path':'materials', 'type':'directory'},
                    {'path':'materials/empty', 'type':'directory'},
                    member('materials/text.txt', b'unchanged\r\n'),
                    member('question.md', (self.folder/'question.md').read_bytes())]
        self.assertEqual(tree_inventory_from_evidence(evidence,'submission/'),expected)
        evidence.close()
        (self.folder/'materials/empty').rmdir()
        changed_evidence = Evidence(self.root)
        self.addCleanup(changed_evidence.close)
        self.assertEqual(tree_inventory_from_evidence(changed_evidence,'submission/'),
                         [item for item in expected if item['path'] != 'materials/empty'])

    def test_invalid_template_cannot_be_proposed(self):
        raw=read_file(self.folder/'question.md')
        for changed in [raw.replace(b'inquiry:',b'unknown:'),raw.replace(b'family: open-inquiry',b'family: nonsense'),
                        raw.replace(b'family: open-inquiry',b'family: open-inquiry\nfamily: comparison')]:
            with self.subTest(changed=changed[:60]),self.assertRaises(ValueError):case_from_question(changed,'problem-a')
        (self.folder/'materials/link').symlink_to('text.txt')
        with self.assertRaises(ValueError):study_proposal('example-model',[('problem-a',self.folder)])

    def test_selected_guidance_is_bound_and_survives_copy_and_rendering(self):
        # A same-named material stays evidence; only the explicit root selection instructs.
        (self.folder/'materials/guidance.md').write_bytes(b'Ordinary evidence.\n')
        stock=inspect_submission(self.folder,'problem-a')
        self.assertNotIn('guidance',stock)
        original=tree_hash(self.folder)
        raw=b'\xef\xbb\xbfDevelop a connected account.\r\n\r\n'
        (self.folder/'guidance.md').write_bytes(raw)
        with self.assertRaises(ValueError):inspect_submission(self.folder,'problem-a')
        self.case['guidance']='guidance.md'
        (self.folder/'question.md').write_bytes(question_file(self.case,proposal('example-model'),'/placeholder'))
        case=inspect_submission(self.folder,'problem-a')
        self.assertNotEqual(case['sha256'],original)
        self.assertIn(b'guidance: guidance.md\n',question_file(case,proposal('changed-model'),'/actual'))
        copy_submission(self.folder,self.root/'copy',case['sha256'])
        self.assertEqual(read_file(self.root/'copy/guidance.md'),raw)
        effective=strict_json(study_build.system_bytes({},'open-inquiry',raw))
        self.assertEqual(effective[1]['text'].encode(),raw)
        (self.folder/'guidance.md').write_bytes(raw+b'Changed.\n')
        with self.assertRaises(ValueError):copy_submission(self.folder,self.root/'changed',case['sha256'])
        self.assertFalse((self.root/'changed').exists())

    def test_guidance_refusals_precede_proposal(self):
        self.case['guidance']='guidance.md'
        question=question_file(self.case,proposal('example-model'),'/placeholder')
        (self.folder/'question.md').write_bytes(question)
        with self.assertRaises(ValueError):study_proposal('example-model',[('problem-a',self.folder)])
        for raw in [b'',b' \t\r\n',b'x\0y',b'\xff',b'x'*262145]:
            (self.folder/'guidance.md').write_bytes(raw)
            with self.subTest(raw=raw[:10]),self.assertRaises(ValueError):
                study_proposal('example-model',[('problem-a',self.folder)])
        (self.folder/'guidance.md').write_bytes(b'Valid.\n')
        for changed in [question.replace(b'guidance.md',b'other.md'),
                        question.replace(b'family: open-inquiry',b'family: comparison')]:
            (self.folder/'question.md').write_bytes(changed)
            with self.assertRaises(ValueError):study_proposal('example-model',[('problem-a',self.folder)])

    def test_supplied_guidance_and_study_build_refuse_before_audit_creation(self):
        from batch import Audit
        self.case['guidance']='guidance.md'
        (self.folder/'question.md').write_bytes(question_file(self.case,proposal('example-model'),'/placeholder'))
        (self.folder/'guidance.md').write_bytes(b'Connected account.\n')
        packet=study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True)
        packet['study_build']={'fixture':'override'}
        target=self.root/'audit'
        with self.assertRaisesRegex(ValueError,'not both'):
            Audit('/unused-binary',target,packet,packet['runs'][-1],mode='rehearse',local=True)
        self.assertFalse(target.exists())

    def test_rehearsal_covers_exact_inputs_and_keeps_fixed_controls(self):
        live=study_proposal('example-model',[('problem-a',self.folder)])
        rehearsed=study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True)
        self.assertEqual(len(c10.check_rehearsal_inputs(rehearsed,live)),14)
        moved=copy.deepcopy(live)
        moved['runs'][0]['submission_folder']='/a/new/location/with/the/same/bytes'
        c10.check_rehearsal_inputs(rehearsed,moved)
        changed=copy.deepcopy(live);changed['runs'][0]['submission_sha256']='0'*64
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsed,changed)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsal_packet(),live)
        rehearsed['runs'].pop(0)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsed,live)


class PacketTests(unittest.TestCase):
    def test_catalog_covers_families_and_inadequate_variants(self):
        cases=catalog()
        self.assertEqual({(item['family'], item['variant']) for item in cases.values()},
                         {('open-inquiry','ordinary'), ('open-inquiry','inadequate'),
                          ('inquiry-framing','ordinary'), ('inquiry-framing','inadequate'),
                          ('comparison','ordinary'), ('comparison','inadequate')})
        self.assertEqual(len(proposal('example-model',repetitions=3)['runs']),18)
        self.assertEqual(len(rehearsal_packet()['runs']),13)

    def test_catalog_refuses_missing_family_or_variant_and_changed_specimen(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(HERE/'specimens', root/'specimens')
            original = read_file(HERE/'catalog.json')
            (root/'catalog.json').write_bytes(original)
            with mock.patch.object(common, 'HERE', root):
                packet = proposal('example-model')
                for field, value in [('family','comparison'), ('variant','inadequate')]:
                    changed = json.loads(original)
                    changed['cases'] = [case for case in changed['cases'] if case[field] != value]
                    (root/'catalog.json').write_text(json.dumps(changed))
                    with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'catalog must cover ordinary and inadequate evidence for all three families'):
                        catalog()
                (root/'catalog.json').write_bytes(original)
                self.assertEqual(len(catalog()), 6)
                path = root/'specimens/open-ordinary/materials/src/a.py'
                before = path.read_bytes()
                path.write_bytes(before + b'\nchanged specimen\n')
                with self.assertRaisesRegex(ValueError, 'specimen differs from packet'):
                    validate_packet(packet)
                path.write_bytes(before)
                extra = root/'specimens/open-ordinary/materials/unlisted.txt'
                extra.write_bytes(b'unlisted input\n')
                with self.assertRaisesRegex(ValueError, 'specimen differs from packet'):
                    validate_packet(packet)
                extra.unlink()
                validate_packet(packet)

    def test_material_copies_preserve_example_bytes(self):
        for item in strict_json(read_file(HERE/'specimen-provenance.json')):
            self.assertEqual(read_file(HERE/item['copy']),read_file(HERE.parents[1]/item['source']))

    def test_question_binding_preserves_body_and_selected_family(self):
        packet=proposal('example-model')
        for case in catalog().values():
            raw=question_file(case,packet,Path('/work/returns'))
            self.assertEqual(raw.split(b'---\n',2)[2],case['question'].encode())
            self.assertIn(('family: '+case['family']+'\n').encode(),raw)
            self.assertNotIn(b'effort:',raw)
        packet['effort']='high'
        self.assertIn(b'effort: high\n',question_file(case,packet,Path('/work/returns')))

    def test_unpaid_proposal_cannot_be_approved(self):
        with self.assertRaises(ValueError):
            validate_packet(proposal('example-model'),approved=True)

    def test_live_packet_cannot_use_fake_model_or_control(self):
        for field,value in [('model','rehearsal-only'),('endpoint','http://127.0.0.1:1'),('proxy','http://localhost:1')]:
            p=proposal('example-model'); p[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_packet(p)
        p=proposal('example-model');p['runs'][0]['scenario']='empty'
        with self.assertRaises(ValueError):
            validate_packet(p)

    def test_no_implicit_placement_retry_or_continuation(self):
        for field,value in [('max_placements',2),('max_placements',True),('permitted_request_attempts',5),
                            ('permitted_request_attempts',4.0),('automatic_continuation',True),('stop_after_seconds',0)]:
            p=proposal('example-model');p[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                validate_packet(p)

    def test_repeated_audit_or_case_repetition_is_refused(self):
        p=proposal('example-model')
        p['runs'].append(copy.deepcopy(p['runs'][0]))
        with self.assertRaises(ValueError):validate_packet(p)
        p['runs'][-1]['id']='another-id'
        with self.assertRaises(ValueError):validate_packet(p)

    def test_unknown_fields_and_changed_specimen_are_refused(self):
        p=proposal('example-model');p['autmatic_continuation']=False
        with self.assertRaises(ValueError):validate_packet(p)
        p=proposal('example-model');p['runs'][0]['submission_sha256']='0'*64
        with self.assertRaises(ValueError):validate_packet(p)

    def test_mistyped_and_exhausted_allowances_are_refused(self):
        for key,value in [('turns',True),('input_tokens',1.2),('output_tokens',1023),('turns',2**48+1)]:
            p=proposal('example-model');p['limits'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_packet(p)

    def test_duplicate_json_and_nonfinite_numbers_are_refused(self):
        for raw in ['{"a":1,"a":2}','{"limits":{"turns":1,"turns":2}}','{"n":NaN}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):strict_json(raw)

    def test_bad_audit_paths_are_refused(self):
        for value in ['../another','/absolute','a/b','A','a' * 81]:
            p=proposal('example-model');p['runs'][0]['id']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate_packet(p)

    def test_live_missing_authority_refuses_before_container_or_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            packet=Path(temp)/'packet.json';write_json(packet,proposal('example-model'))
            args=argparse.Namespace(mode='live',evidence=c10.REPO/'.scratch/c10-authority-never-created',
                commission=packet,approved_commission=digest(read_file(packet)),rehearsal=Path(temp),qualification='unused')
            with mock.patch.object(c10,'bindings') as bind,mock.patch.object(c10,'hidden_credential') as prompt:
                with self.assertRaises(ValueError):c10.launch_batch(args)
                bind.assert_not_called();prompt.assert_not_called()

    def test_changed_approved_digest_refuses_before_bindings(self):
        with tempfile.TemporaryDirectory() as temp:
            value = proposal('example-model')
            value['spending_authority'] = 'synthetic gate control; no launch'
            value['account'] = {key:'synthetic-label' for key in value['account']}
            value['bindings'] = {key:'synthetic-binding' for key in value['bindings']}
            validate_packet(value, approved=True)
            packet=Path(temp)/'packet.json';write_json(packet,value)
            args=argparse.Namespace(mode='live',evidence=c10.REPO/'.scratch/c10-authority-never-created',
                commission=packet,approved_commission='0'*64,rehearsal=Path(temp),qualification='unused')
            with mock.patch.object(c10,'bindings') as bind:
                with self.assertRaisesRegex(ValueError, 'commission differs from approved digest'):c10.launch_batch(args)
                bind.assert_not_called()
            args.approved_commission = digest(read_file(packet))
            with mock.patch.object(c10,'bindings',side_effect=RuntimeError('digest gate passed')) as bind:
                with self.assertRaisesRegex(RuntimeError, '^digest gate passed$'):
                    c10.launch_batch(args)
                bind.assert_called_once()


class EvidenceTests(unittest.TestCase):
    def test_checked_limit_stop_is_not_failure_and_does_not_start_next_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'out';out.mkdir()
            sessions=[]
            for n in range(2):
                evidence=root/f'evidence-{n}';evidence.mkdir()
                audit=mock.Mock(evidence=evidence,phase='run',run_item={'id':f'audit-{n}','scenario':'submitted'})
                audit.execute.return_value={'audit':f'audit-{n}','placement':'observed',
                    'caller_reply_lost':False,'automatic_close':None,
                    'review_before_close':{'outcome':'checked','ending':'limit_reached',
                        'auditor_submitted':False,'delivery_verified':False}}
                sessions.append(audit)
            with mock.patch('batch.locked_export',return_value={'outcome':'exported'}):
                result=execute_batch(None,None,out,{},'live',b'synthetic',sessions,None,local=True)
            sessions[0].execute.assert_called_once()
            sessions[1].execute.assert_not_called()
            self.assertEqual((result['planned'],result['observed'],result['failed'],result['not_started']),(2,1,0,1))
            self.assertEqual(result['audits'][1]['placement'],'not_started')
            self.assertEqual(result['halt']['reason'],'without_auditor_submission')
            self.assertNotIn('expected_observation',result['audits'][0])
            self.assertTrue((sessions[1].evidence/'events/0001.json').is_file())

    def test_unknown_effects_stop_batch_and_keep_failure_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'out';out.mkdir()
            sessions=[]
            for n in range(2):
                evidence=root/f'evidence-{n}';evidence.mkdir()
                audit=mock.Mock(evidence=evidence,phase='run',run_item={'id':f'audit-{n}','scenario':'submitted'})
                audit.execute.side_effect=RuntimeError('uncertain caller reply')
                sessions.append(audit)
            result=execute_batch(None,None,out,{},'live',b'synthetic',sessions,None,local=True)
            sessions[0].execute.assert_called_once()
            sessions[1].execute.assert_not_called()
            self.assertEqual(result['audits'][0]['placement'],'unknown')
            self.assertEqual(result['failed'],1)
            self.assertNotIn('uncertain caller reply',json.dumps(result))
            self.assertTrue((sessions[0].evidence/'failure.json').is_file())
            self.assertEqual(result['not_started'],1)

    def test_export_exception_does_not_erase_an_observed_placement(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'out';out.mkdir();evidence=root/'evidence';evidence.mkdir()
            audit=mock.Mock(evidence=evidence,phase='status-export',
                            run_item={'id':'audit','scenario':'submitted'})
            audit.execute.return_value={'audit':'audit','placement':'observed','caller_reply_lost':False,
                'automatic_close':None,'review_before_close':{'outcome':'checked','ending':'limit_reached',
                    'auditor_submitted':False,'delivery_verified':False}}
            with mock.patch('batch.locked_export',side_effect=PermissionError('PRIVATE TEXT')):
                result=execute_batch(None,None,out,{},'live',b'synthetic',[audit],None,local=True)
            self.assertEqual((result['observed'],result['failed']),(1,1))
            self.assertEqual(result['audits'][0]['review_before_close']['outcome'],'checked')
            self.assertEqual(result['audits'][0]['failure']['stage'],'export')
            self.assertNotIn('PRIVATE TEXT',json.dumps(result))

    def test_inventory_keeps_nested_hidden_and_empty_members(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'empty').mkdir();(root/'nested').mkdir();(root/'nested/.hidden').write_bytes(b'\xef\xbb\xbf\r\n')
            found=inventory(root)
            self.assertEqual([x['path'] for x in found],['empty','nested','nested/.hidden'])
            original=tree_hash(root)
            (root/'nested/.hidden').write_bytes(b'\xef\xbb\xbf\n')
            self.assertNotEqual(tree_hash(root),original)

    def test_inventory_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'target').write_bytes(b'x');(root/'alias').symlink_to('target')
            with self.assertRaises(ValueError):inventory(root)

    def test_bounded_file_read_and_missing_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'large').write_bytes(b'x'*100)
            with self.assertRaises(ValueError):read_file(root/'large',99)
            evidence=Evidence(root)
            with self.assertRaises(ValueError):evidence.read('missing')
            with self.assertRaises(ValueError):evidence.read('../outside')

    def archive(self,path,members):
        with tarfile.open(path,'w') as archive:
            for name,data,kind in members:
                member=tarfile.TarInfo(name);member.type=kind
                member.size=len(data) if kind==tarfile.REGTYPE else 0
                archive.addfile(member,io.BytesIO(data) if kind==tarfile.REGTYPE else None)
        return digest(path.read_bytes())

    def test_export_digest_has_a_firing_control(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'export.tar'
            expected=self.archive(path,[('private/value',b'original',tarfile.REGTYPE)])
            evidence=Evidence(path,expected);self.assertEqual(evidence.read('value'),b'original');evidence.close()
            with path.open('ab') as stream:stream.write(b'changed')
            with self.assertRaises(ValueError):Evidence(path,expected)

    def test_tar_duplicate_path_traversal_and_links_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            for n,members in enumerate([
                [('private/x',b'a',tarfile.REGTYPE),('private/x',b'b',tarfile.REGTYPE)],
                [('private/../x',b'a',tarfile.REGTYPE)],
                [('private/x',b'',tarfile.SYMTYPE)],
                [('outside/x',b'a',tarfile.REGTYPE)],
            ]):
                path=Path(temp)/str(n);expected=self.archive(path,members)
                with self.subTest(n=n),self.assertRaises(ValueError):Evidence(path,expected)

    def test_review_missing_evidence_is_explicit_and_never_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            result=verify(Evidence(temp))
            self.assertEqual(result['outcome'],'incomplete')
            self.assertEqual(result['failures'],['missing_evidence'])
            self.assertFalse(result['model_qualified'])
            self.assertIsNone(result['coverage'])
            self.assertIsNone(result['closed'])

    def test_credential_reentry_must_match_without_persisting_key(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'marker.json';key=b'synthetic-very-long-key-for-test'
            credential_marker(path,key);check_credential(path,key)
            self.assertNotIn(key,path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'credential differs from the original placement; export withheld'):
                check_credential(path,b'wrong-key')

    def test_incomplete_export_withholds_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'root';root.mkdir();(root/'original').write_bytes(b'untouched')
            result=export_snapshot(root,Path(temp)/'out',b'synthetic')
            self.assertEqual(result['outcome'],'withheld')
            self.assertEqual(result['reasons'], ['evidence_incomplete'])
            self.assertEqual(result['evidence_state'], 'missing_or_malformed_evidence')
            self.assertEqual((root/'original').read_bytes(),b'untouched')
            self.assertFalse((Path(temp)/'out/work.tar').exists())
            import test_launch
            test_launch.LaunchTests().complete_evidence(root)
            complete = export_snapshot(root, Path(temp)/'complete-out', b'synthetic')
            self.assertEqual(complete['outcome'], 'exported')
            self.assertEqual(complete['reasons'], [])
            self.assertEqual(complete['evidence_state'], 'complete')
            self.assertEqual((root/'original').read_bytes(), b'untouched')

    def test_usage_iterations_replace_top_level_totals(self):
        counts=usage_counts({'input_tokens':999,'output_tokens':999,
            'iterations':[{'type':'message','input_tokens':2,'output_tokens':3},
                          {'type':'compaction','input_tokens':5,'output_tokens':7,'cache_read_input_tokens':11}]})
        self.assertEqual(counts,{'input_tokens':7,'output_tokens':10,'cache_creation_input_tokens':0,'cache_read_input_tokens':11})

    def test_invalid_usage_cannot_fall_back_to_smaller_totals(self):
        for value in [[],[{'type':'unknown','input_tokens':0,'output_tokens':0}],
                      [{'type':'message','input_tokens':True,'output_tokens':0}],
                      [{'type':'message','input_tokens':2**48,'output_tokens':0}]*2]:
            with self.subTest(value=value),self.assertRaises(ValueError):usage_counts({'input_tokens':0,'output_tokens':0,'iterations':value})


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root/'batch'
        self.batch.mkdir()
        packet = proposal('example-model',['open-ordinary'])
        self.audit = packet['runs'][0]['id']
        write_json(self.batch/'PLAN.json',{'schema':'stewart.c10-plan/1','commission':packet,
                   'binary_sha256':None,'audits':[self.audit]})
        (self.root/'proposal.md').write_text('Question: was a next-page call offered and attempted?\n')
        self.manifest = self.root/'block.json'
        write_json(self.manifest,{'schema':'stewart.experiment-block/1',
            'proposal':{'author':'Experimenter','document':self.ref(self.root/'proposal.md')},
            'batches':[self.ref(self.batch/'PLAN.json')]})
        write_json(self.batch/'RESULT.json',{'schema':'stewart.c10-session/2','mode':'live',
            'local_iteration_only':False,'planned':1,'observed':1,'failed':0,'not_started':0,
            'halt':None,'skipped_checks':[],
            'audits':[{'audit':self.audit,'placement':'observed','failed':False}]})

    def ref(self,path):
        return {'path':str(path),'sha256':digest(read_file(path))}

    def report(self):
        return reporting.assemble(self.manifest)

    def test_missing_observation_stays_unknown_and_assessment_does_not_gate_return(self):
        report = reporting.write_report(self.manifest,self.root/'return')
        self.assertIsNone(report['assessment'])
        self.assertIsNone(reporting.latest_review(report['technical']['batches'][0]['audits'][0]))
        self.assertIn('current_evidence_unavailable',str(reporting.current_issues(report)))
        self.assertIn('Pending.',read_file(self.root/'return/report.md').decode())
        self.assertEqual(report['technical_sha256'],self.report()['technical_sha256'])

    def test_assessment_is_attributed_and_later_position_requires_reconciliation(self):
        original = self.report()
        (self.root/'assessment.md').write_text('Unresolved designer judgment. Billing deferred by the principal.\n')
        path = self.root/'assessment.json'
        write_json(path,{'schema':'stewart.experiment-assessment/1',
            'technical_sha256':original['technical_sha256'],
            'assessment':{'author':'A named experimenter','document':self.ref(self.root/'assessment.md')}})
        current = reporting.assemble(self.manifest,path)
        self.assertEqual(current['assessment']['basis'],'current')
        self.assertEqual(original['technical'],current['technical'])
        self.assertEqual(reporting.current_issues(original),reporting.current_issues(current))
        snapshot = self.batch/self.audit/'export-0001'
        snapshot.mkdir(parents=True)
        write_json(snapshot/'EXPORT.json',{'outcome':'withheld','started_at':1,'ended_at':2,
            'evidence_state':'incomplete','scan':{'files_with_matches':[],'errors':[]}})
        later = reporting.assemble(self.manifest,path)
        self.assertEqual(later['assessment']['basis'],'earlier_position')
        self.assertNotEqual(later['technical_sha256'],original['technical_sha256'])
        self.assertIn('not assumed current',reporting.render(later))
        self.assertEqual(later['assessment']['text'],current['assessment']['text'])

    def test_changed_author_text_fires_binding_check_and_no_old_output_is_rewritten(self):
        output = self.root/'return'
        reporting.write_report(self.manifest,output)
        old = read_file(output/'report.json')
        with self.assertRaises(reporting.ReportError) as error:
            reporting.write_report(self.manifest,output)
        self.assertEqual(error.exception.code,'output_exists')
        (self.root/'proposal.md').write_text('Changed question\n')
        with self.assertRaises(reporting.ReportError) as error:
            self.report()
        self.assertEqual(error.exception.code,'source_changed')
        self.assertEqual(old,read_file(output/'report.json'))

    def test_new_question_cannot_reuse_an_assessments_current_basis(self):
        first = self.report()
        (self.root/'proposal.md').write_text('A different question about the same trials.\n')
        manifest = strict_json(read_file(self.manifest))
        manifest['proposal']['document'] = self.ref(self.root/'proposal.md')
        self.manifest.write_text(json.dumps(manifest))
        self.assertNotEqual(first['technical_sha256'],self.report()['technical_sha256'])

    def test_later_withholding_does_not_borrow_an_earlier_checked_state(self):
        earlier = {'snapshot':'export-0001','review':{'outcome':'checked','closed':False}}
        audit = {'snapshots':[earlier]}
        self.assertIs(reporting.latest_review(audit),earlier['review'])
        audit['snapshots'].append({'snapshot':'export-0002','review':None,'export':'withheld'})
        self.assertIsNone(reporting.latest_review(audit))
        self.assertFalse(audit['snapshots'][0]['review']['closed'])

    def test_later_checked_observation_can_resolve_unknown_effects_without_erasing_failure(self):
        report = self.report()
        batch = report['technical']['batches'][0]
        session = batch['session']['record']
        session.update(failed=1,observed=0)
        session['audits'][0].update(placement='unknown',failed=True)
        self.assertTrue(reporting.current_issues(report))
        batch['audits'][0]['snapshots'].append({'review':{'outcome':'checked'}})
        self.assertEqual(reporting.current_issues(report),[])
        self.assertEqual(session['failed'],1)
        self.assertEqual(session['audits'][0]['placement'],'unknown')
        session['audits'][0].update(placement='not_started')
        self.assertEqual(reporting.current_issues(report)[0][1],'placement_observed_after_not_started_record')

    def test_historical_session_is_linked_without_schema_conversion(self):
        path = self.batch/'RESULT.json'
        path.write_text('{"schema":"stewart.c10-session/1","outcome":"failed"}\n')
        old = read_file(path)
        session = self.report()['technical']['batches'][0]['session']
        self.assertEqual(session['assessment'],'unsupported_schema')
        self.assertIsNone(session['record'])
        self.assertEqual(session['source']['sha256'],digest(old))
        self.assertEqual(read_file(path),old)

    def test_malformed_export_preserves_inventory_and_hides_exception_text(self):
        snapshot = self.batch/self.audit/'export-0001'
        snapshot.mkdir(parents=True)
        (snapshot/'EXPORT.json').write_text('PRIVATE-CREDENTIAL-SHAPED-TEXT')
        report = self.report()
        self.assertNotIn('PRIVATE-CREDENTIAL',json.dumps(report))
        row = report['technical']['batches'][0]['audits'][0]
        self.assertEqual(row['audit'],self.audit)
        self.assertEqual(row['snapshots'][0]['reasons'],['export_metadata_unreadable'])

    def test_paging_observation_has_firing_differing_and_prose_invariance_cases(self):
        first = read_reply('id','materials/big',0,10,20,'first',10)[1][0]['text']
        last = read_reply('id','materials/big',10,20,20,'last')[1][0]['text']
        for prose in ['correct answer','incorrect answer']:
            p = PagingObservation()
            p.observe('read',{'source':'materials/big'},json.loads(last))
            p.observe('record_account',{'text':prose},{'outcome':'completed'})
            self.assertEqual(p.counts['next_calls_offered'],0)
            self.assertEqual(p.counts['exact_next_call_attempts'],0)
        offered = PagingObservation()
        offered.observe('read',{'source':'materials/big'},json.loads(first))
        self.assertEqual(offered.counts['next_calls_offered'],1)
        self.assertEqual(offered.counts['exact_next_call_attempts'],0)
        offered.observe('read',{'source':'materials/big','start':10},json.loads(last))
        self.assertEqual(offered.counts['exact_next_call_attempts'],1)
        self.assertEqual(offered.counts['incomplete_pages'],1)
        with self.assertRaises(KeyError):
            PagingObservation().observe('read',{}, {'outcome':'completed','data':{},'next':[]})


class HostQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.scratch').mkdir()
        patch = mock.patch.object(host_queue, 'REPO', self.root)
        patch.start(); self.addCleanup(patch.stop)
        self.config = {'campaign': 'test-campaign', 'authority': 'bounded test authority',
            'model': 'test-model', 'qualification': 'test-qualified',
            'account': {'account_label': 'test', 'workspace_id': 'test-workspace', 'credential_label': 'test-key'},
            'synthetic_connection': 'test-synthetic', 'placement_ceiling': 2, 'budget_usd': 50,
            'console': {'scope': 'test workspace', 'month': host_queue.datetime.now(host_queue.timezone.utc).strftime('%Y-%m'),
                'limit_usd': 60, 'starting_spend_usd': 10, 'recorded_by': 'test operator',
                'recorded_at': 'test time', 'credential_binding': 'test-key belongs to this workspace'}}
        self.packet = proposal('test-model', ['open-ordinary'])
        self.packet['account'] = self.config['account'].copy()
        self.packet['spending_authority'] = self.config['authority']
        self.packet['bindings'] = dict.fromkeys(self.packet['bindings'], 'test-binding')
        self.packet['bindings']['qualification_id'] = 'test-qualified'
        self.path = self.root / 'packet.json'
        self.save_packet()
        self.request = {'operation': 'live', 'evidence': str(self.root / '.scratch/live-01'),
            'packet': str(self.path), 'sha256': digest(read_file(self.path)),
            'rehearsal': str(self.root / '.scratch/rehearsal-01')}

    def save_packet(self):
        self.path.write_text(json.dumps(self.packet))
        if hasattr(self, 'request'):
            self.request['sha256'] = digest(read_file(self.path))

    def test_live_needs_explicit_enable_and_current_console_record(self):
        with self.assertRaisesRegex(ValueError, 'offline'):
            host_queue.command(self.request, self.config, False)
        for console in [None, {**self.config['console'], 'month': '2000-01'},
                        {**self.config['console'], 'limit_usd': 10}]:
            with self.subTest(console=console), self.assertRaises(ValueError):
                host_queue.configuration({**self.config, 'console': console}, True)
        host_queue.configuration({**self.config, 'console': None}, False)

    def test_console_headroom_does_not_change_the_campaign_budget(self):
        config = {**self.config, 'console': {**self.config['console'],
                  'limit_usd': 54, 'starting_spend_usd': 3.91}}
        self.assertIs(host_queue.configuration(config, True), config)
        self.assertEqual(config['budget_usd'], 50)
        self.assertEqual(config['console']['starting_spend_usd'], 3.91)

    def test_valid_live_command_retains_launcher_checks_and_account(self):
        argv, charge = host_queue.command(self.request, self.config, True)
        self.assertEqual(charge, 1)
        self.assertEqual(argv[3], str(host_queue.HERE / 'c10.py'))
        for flag, value in [('--approved-commission', self.request['sha256']),
                            ('--rehearsal', self.request['rehearsal']), ('--connection', 'test-key')]:
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertNotIn('shell', argv)

    def test_different_model_authority_account_and_multiple_placements_refuse(self):
        original = copy.deepcopy(self.packet)
        for change in [{'model': 'other'}, {'spending_authority': 'other'},
                       {'account': {**self.packet['account'], 'credential_label': 'other'}},
                       {'runs': proposal('test-model', ['open-ordinary', 'open-inadequate'])['runs']}]:
            with self.subTest(change=change):
                self.packet = {**copy.deepcopy(original), **change}; self.save_packet()
                with self.assertRaises(ValueError):
                    host_queue.command(self.request, self.config, True)

    def test_changed_packet_and_existing_evidence_refuse(self):
        self.path.write_bytes(read_file(self.path) + b' ')
        with self.assertRaisesRegex(ValueError, 'digest'):
            host_queue.command(self.request, self.config, True)
        self.save_packet()
        Path(self.request['evidence']).mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            host_queue.command(self.request, self.config, True)

    def test_control_scope_and_no_surrender(self):
        out = self.root / '.scratch/live-01'
        (out / 'staging').mkdir(parents=True)
        (out / 'staging/commission.json').write_bytes(read_file(self.path))
        request = {'operation': 'collect', 'evidence': str(out), 'audit': 'open-ordinary-r1', 'confirm': None}
        argv, charge = host_queue.command(request, self.config, False)
        self.assertEqual(charge, 0); self.assertEqual(argv[-2:], ['--connection', 'test-key'])
        for operation in ['surrender', 'resume', 'delete', 'sh']:
            with self.assertRaises(ValueError):
                host_queue.command({**request, 'operation': operation}, self.config, False)
        with self.assertRaises(ValueError):
            host_queue.command(request, {**self.config, 'authority': 'different'}, False)

    def test_dispatch_retains_streams_and_never_repeats_claim(self):
        (self.root / 'claims').mkdir()
        argv = [sys.executable, '-I', '-B', '-c', 'import sys; print("fake output"); print("fake error", file=sys.stderr); sys.exit(7)']
        self.assertEqual(host_queue.dispatch(self.root, 'attempt', b'{}', argv, 1, 'config'), 7)
        claim = self.root / 'claims/attempt'
        self.assertEqual(read_file(claim / 'stdout'), b'fake output\n')
        self.assertEqual(read_file(claim / 'stderr'), b'fake error\n')
        self.assertFalse(host_queue.reconciled(claim))
        with self.assertRaises(FileExistsError):
            host_queue.dispatch(self.root, 'attempt', b'{}', argv, 1, 'config')
        self.assertEqual(strict_json(read_file(claim / 'result.json'))['exit'], 7)

    def test_interruption_keeps_claim_and_needs_attributed_evidence(self):
        (self.root / 'claims').mkdir()
        with mock.patch.object(host_queue.subprocess, 'run', side_effect=OSError('lost caller')):
            with self.assertRaises(OSError):
                host_queue.dispatch(self.root, 'attempt', b'{}', ['fake'], 1, 'config')
        claim = self.root / 'claims/attempt'
        self.assertFalse((claim / 'result.json').exists())
        self.assertFalse(host_queue.reconciled(claim))
        (claim / 'result.json').write_bytes(b'{"exit":')
        self.assertFalse(host_queue.reconciled(claim))
        witness = self.root / 'witness.json'; witness.write_bytes(b'{"observed":"fake stopped"}')
        write_json(claim / 'reconciliation.json', {'author': 'test reader', 'disposition': 'fake effects reconciled',
            'evidence': [{'path': str(witness), 'sha256': digest(read_file(witness))}]})
        self.assertTrue(host_queue.reconciled(claim))
        witness.write_bytes(b'changed')
        with self.assertRaises(ValueError): host_queue.reconciled(claim)

    def test_queue_placement_bound(self):
        queue = self.root / 'queue'
        (queue / 'requests').mkdir(parents=True)
        (queue / 'claims/previous').mkdir(parents=True)
        write_json(queue / 'claims/previous/command.json', {'placement_charge': 1})
        write_json(queue / 'claims/previous/result.json', {'exit': 0})
        (queue / 'claims/earlier').mkdir()
        write_json(queue / 'claims/earlier/command.json', {'placement_charge': 1})
        write_json(queue / 'claims/earlier/result.json', {'exit': 0})
        write_json(queue / 'requests/next.json', self.request)
        config = self.root / 'config.json'; write_json(config, self.config)
        with mock.patch.object(host_queue.subprocess, 'check_output', return_value=b''), \
             mock.patch.object(host_queue, 'source_hash', return_value='source'), \
             mock.patch.object(host_queue, 'dispatch') as dispatch:
            with self.assertRaisesRegex(ValueError, 'ceiling'):
                host_queue.serve(queue, config, True, once=True)
            dispatch.assert_not_called()

    def test_serial_queue_restart_skips_completed_request(self):
        queue = self.root / 'queue'
        (queue / 'requests').mkdir(parents=True)
        write_json(queue / 'requests/offline.json', {'operation': 'rehearse',
            'evidence': str(self.root / '.scratch/offline'), 'submissions': []})
        config = self.root / 'config.json'; write_json(config, self.config)
        with mock.patch.object(host_queue.subprocess, 'check_output', return_value=b''), \
             mock.patch.object(host_queue, 'source_hash', return_value='source'), \
             mock.patch.object(host_queue.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(host_queue.serve(queue, config, False, once=True), 0)
            self.assertEqual(host_queue.serve(queue, config, False, once=True), 0)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(len(list((queue / 'sessions').iterdir())), 2)
        self.assertEqual(strict_json(read_file(queue / 'claims/offline/command.json'))['placement_charge'], 0)

    def test_second_runner_cannot_claim_while_first_holds_lock(self):
        queue = self.root / 'queue'; queue.mkdir()
        config = self.root / 'config.json'; write_json(config, self.config)
        with (queue / 'lock').open('a') as first:
            host_queue.fcntl.flock(first, host_queue.fcntl.LOCK_EX | host_queue.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                host_queue.serve(queue, config, False, once=True)

    def test_torn_claim_metadata_reserves_a_slot_but_allows_offline_recovery(self):
        queue = self.root / 'queue'
        (queue / 'requests').mkdir(parents=True)
        damaged = queue / 'claims/damaged'; damaged.mkdir(parents=True)
        (damaged / 'command.json').write_bytes(b'{"placement_charge":')
        self.assertEqual(host_queue.placement_charge(damaged), 1)
        write_json(queue / 'requests/offline.json', {'operation': 'rehearse',
            'evidence': str(self.root / '.scratch/offline'), 'submissions': []})
        config = self.root / 'config.json'; write_json(config, self.config)
        with mock.patch.object(host_queue.subprocess, 'check_output', return_value=b''), \
             mock.patch.object(host_queue, 'source_hash', return_value='source'), \
             mock.patch.object(host_queue.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(host_queue.serve(queue, config, False, once=True), 0)


if __name__=='__main__':
    unittest.main()
