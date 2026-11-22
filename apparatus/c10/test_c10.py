"""Provider-free controls for C10 packets, evidence reads and launch authority."""
import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
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
import warnings
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'testdata'))
import acceptance_fixtures as captured_acceptance
import c10
import common
from common import (HERE,catalog,compact,digest,inventory,proposal,question_file,read_file,
                    rehearsal_packet,source_hash,strict_json,tree_hash,validate_packet,write_json)
from batch import credential_marker,check_credential,export_snapshot
from batch import execute_batch
from verify import Evidence,PagingObservation,usage_counts,verify,trigger_tokens,compaction_cause,ordinary_body,response_usage
import rawjson
import reporting
import connections
from study import (case_from_question, copy_submission, inspect_submission,
                   study_proposal)
from verify import tree_inventory_from_evidence
import study_build
import host_queue
import smoke
from fake import Auditor, first_message, follow_pages


# The rehearsal inventory, written out from the control specification: six fixed
# cases, ten single-placement controls and six controls whose first placement
# ends interrupted and whose later placement is a separately bound continuation.
FIXED_CASES = ['open-ordinary', 'open-inadequate', 'framing-ordinary', 'framing-inadequate',
               'comparison-ordinary', 'comparison-inadequate']
SINGLE_PLACEMENT_CONTROLS = ['empty', 'unsubmitted', 'provider-rejected', 'lost-run-reply',
                             'reflected-body', 'export-contamination', 'export-failure',
                             'compaction', 'compaction-below', 'compaction-invalid']
# Control: (witnessed interruption point of the first placement, each placement's ending and cause).
CONTINUED_CONTROLS = {
    'continue-cap': (None, [['interrupted', 'max_tokens'], ['sealed', None]]),
    'continue-entries': (None, [['interrupted', 'max_tokens'], ['sealed', None]]),
    'reminder-spent': ('reminder_notice', [['interrupted', 'signal'], ['ended_unsubmitted', None]]),
    'reminder-spent-unheld': ('reminder_notice', [['interrupted', 'signal'], ['ended_unsubmitted', None]]),
    'reminder-spent-submits': ('reminder_notice', [['interrupted', 'signal'], ['sealed', None]]),
    'reminder-unused': ('entry_record', [['interrupted', 'signal'], ['sealed', None]]),
    'p1-signal':('run_started',[['interrupted','signal'],['sealed',None]]),
    'p2-signal':('answer_prepared',[['interrupted','signal'],['sealed',None]]),
}
# Whether the rehearsal provider holds the request in flight until the signal has been sent. Only
# the unheld control is signalled on sight, as a live placement is; the two capped ones are not signalled.
HELD_CONTROLS = {'p1-signal':True,'p2-signal':True,'continue-cap': None, 'continue-entries': None, 'reminder-spent': True,
                 'reminder-spent-unheld': False, 'reminder-spent-submits': True, 'reminder-unused': True}
# Comparisons on each continued control after its final placement: reviewer (cases run, controls
# fired, controls without a subject), report comparisons, operator comparisons or None. The unheld
# control has a subject for the request-cap control only when its signal found a written request.
CONTINUED_COMPARISONS = {'p1-signal': ([(13,12,1)],14,None), 'p2-signal': ([(14,13,0)],14,None),
    'continue-cap': ([(11, 10, 3)], 14, None),
    'continue-entries': ([(12, 11, 2)], 14, None),
    'reminder-spent': ([(14, 13, 0)], 14, 8),
    'reminder-spent-unheld': ([(13, 12, 1), (14, 13, 0)], 14, 8),
    'reminder-spent-submits': ([(14, 13, 0)], 14, None),
    'reminder-unused': ([(14, 13, 0)], 14, None),
}
SECOND_START_REFUSED = {'refused': True, 'phase': 'preflight.prior_runs'}


def control_counts(scenario, shape=0):
    """The `controls` member a finished continued control reports, in the container's form."""
    shapes, reporting, operations = CONTINUED_COMPARISONS[scenario]
    run, fired, absent = shapes[shape]
    def family(count):
        return {'run': count, 'passed': count, 'failed': 0, 'original_unchanged': True}
    return {'review': {**family(run), 'skipped': 0, 'controls': fired, 'controls_fired': fired,
                       'not_applicable': [f'control-without-subject-{n}' for n in range(absent)]},
            'reporting': family(reporting), 'operations': None if operations is None else family(operations)}
TRIAL_SCENARIOS = ["p1-close","p2-close","p2-missed"]
REHEARSAL_AUDITS = ([name + '-r1' for name in FIXED_CASES]
                    + ['control-' + name for name in SINGLE_PLACEMENT_CONTROLS + list(CONTINUED_CONTROLS) + TRIAL_SCENARIOS])

FAKE_KEYCTL = '''import json, os, pathlib, sys, time
root=pathlib.Path(__file__).parent
value=json.loads((root/'response.json').read_text())
assert 'ANTHROPIC_API_KEY' not in os.environ
args=sys.argv[1:]
data=sys.stdin.buffer.read()
with (root/'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(args)+'\\n')
time.sleep(value['sleep'])
if args[0] == 'padd':
    assert data.decode() == value['stdout'].rstrip('\\n')
else:
    assert not data
if args[0] == value.get('fail_at','pipe') and value['exit']:
    sys.stderr.write(value['stderr'])
    sys.exit(value['exit'])
if args == ['get_persistent', '@s']:
    print('111')
elif args[0] == 'padd':
    print('222')
elif args[0] == 'setperm':
    assert args == ['setperm','222','0x003f0000']
elif args[:3] == ['search','111','user'] and args[3] in ['stewart-provider:synthetic','stewart-provider:approved']:
    print('222')
elif args == ['pipe','222']:
    sys.stdout.write(value['stdout'])
else:
    print('keyctl_search: Required key not available',file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'''


def read_reply(call_id, source, start, end, size, text, next_start=None):
    """A captured tool_result for one material read page, shaped as INTERFACE 7.1 and 7.2 describe."""
    envelope = {'schema': 'stewart.reply/3', 'operation': 'read', 'outcome': 'completed',
                'data': {'source': source, 'kind': 'material', 'size': size, 'range': [start, end],
                         'complete': next_start is None, 'cite': {'source': source, 'start': start, 'end': end}},
                'next': [] if next_start is None else [{'tool': 'read', 'input': {'source': source, 'start': next_start}, 'why': 'rest'}]}
    return call_id, [{'type': 'text', 'text': json.dumps(envelope)}, {'type': 'text', 'text': text}]


class RehearsalEffortTests(unittest.TestCase):
    def test_wire_setting_agrees_with_supplied_commission(self):
        family = catalog()['framing-inadequate']['family']
        question = 'Inspect the supplied evidence.'
        for effort in (None, 'low', 'medium', 'high', 'xhigh', 'max'):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as td:
                packet = {'effort': effort}
                peer = Auditor('provider-rejected', Path(td), {}, question, family, packet=packet)
                self.addCleanup(peer.server.server_close)
                body = {'model': 'rehearsal-only', 'system': strict_json(study_build.system_bytes(packet, family)),
                        'tools': study_build.spec.expected_tools(family), 'messages': [first_message(question, 1)]}
                if effort is not None:
                    body['output_config'] = {'effort': effort}
                self.assertEqual(peer.respond(body)[0], 401)
                for invalid in (None, {}, {'effort': 'wrong'}):
                    with self.assertRaises(ValueError):
                        peer.respond({**body, 'output_config': invalid})
                if effort is not None:
                    del body['output_config']
                    with self.assertRaises(ValueError):
                        peer.respond(body)


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
        self.baseline=captured_acceptance.result()
        self.result=captured_acceptance.study_result()

    def check(self,value):
        study_build.check_result(value,self.baseline,self.expected,'arm64')

    def test_declared_difference_is_not_qualification(self):
        self.check(self.result)
        self.assertEqual(len(self.baseline['cases']),133)
        self.assertEqual(self.result['counts']['cases'],
                         {'selected':133,'ran':133,'passed':132,'failed':1,'skipped':0})
        self.assertEqual(self.result['counts']['controls']['fired'],79)
        with self.assertRaisesRegex(ValueError,'did not finish with its declared differences'):
            self.check(self.baseline)
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
        variant=captured_acceptance.release
        mutations=[('unexpected-check',lambda r:variant(r,'c19.arrangement')['failed_names'].append('custody.failed'),
                    'acceptance failure names differ'),
            ('credential-failure',lambda r:variant(r,'credentials.arguments').update(outcome='fail'),
             'study native credential checks did not pass'),
            ('partial-skip',lambda r:variant(r,'c19.arrangement')['parts_skipped'].append('process'),
             'study acceptance skipped a variant'),
            ('missing-case',lambda r:r['cases'].pop(),'omitted or changed the case inventory'),
            ('interrupted',lambda r:r.update(interrupted=True),'did not finish with its declared differences'),
            ('platform',lambda r:r['platform'].update(system='Darwin'),'study acceptance platform differs'),
            ('unfired-driver',lambda r:r['counts']['driver_controls'].update(fired=0),'driver controls did not all fire'),
            ('unassigned',lambda r:r['controls_unassigned'].append('unchecked'),'unassigned acceptance controls'),
            ('broken-control',lambda r:r['broken_checks'].append({'case':'unrelated','sabotage':'x','status':'baseline_failed'}),
             'unexpected broken acceptance check')]
        for name,mutation,reason in mutations:
            value=copy.deepcopy(self.result);mutation(value)
            with self.subTest(mutation=name),self.assertRaisesRegex(ValueError,reason):self.check(value)

    def test_historical_skips_refuse_after_same_study_projection(self):
        original=captured_acceptance.result(run='readiness-01')
        self.assertEqual(original['exit'],0)
        self.assertEqual([c['id'] for c in original['cases'] if c['outcome']=='skipped'],
                         ['c12.run-refusals','c19.bounds.paths'])
        with self.assertRaisesRegex(ValueError,'study acceptance skipped a case'):
            self.check(captured_acceptance.study_result(run='readiness-01'))

    def test_member_order_invariance_and_both_architecture_records(self):
        self.check(json.loads(json.dumps(self.result,sort_keys=True)))
        baseline=captured_acceptance.result('amd64')
        result=captured_acceptance.study_result('amd64')
        self.assertEqual(len(baseline['cases']),131)
        study_build.check_result(result,baseline,self.expected,'amd64')

    def test_credential_failure_cannot_be_declared_expected(self):
        expected=copy.deepcopy(self.expected)
        expected['failed_cases']['credentials.process']=['process.access']
        with self.assertRaises(ValueError):study_build.expectations(expected)

    def test_changed_text_control_baseline_remains_failed(self):
        value=copy.deepcopy(self.result)
        control={'case':'c19.arrangement','sabotage':'changed-text','status':'baseline_failed'}
        value['controls'].append(control);value['controls_never_fired']=['changed-text']
        value['counts']['controls']['total']+=1
        value['counts']['controls']['baseline_failed']+=1
        value['broken_checks']=[control,{'case':None,'sabotage':'changed-text','status':'never_fired'}]
        self.check(value)
        self.assertEqual(value['controls'][-1]['status'],'baseline_failed')
        value['controls'][-1]['status']='not_fired'
        with self.assertRaisesRegex(ValueError,'an acceptance control did not fire'):self.check(value)

    def test_rehearsal_cannot_be_reused_for_another_variant(self):
        packet=study_build.attach(rehearsal_packet(),study_build.draft(self.interface))
        c10.check_rehearsal_inputs(packet,packet)
        changed=copy.deepcopy(packet);changed['study_build']['interface']['instructions']='Different.'
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(packet,changed)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsal_packet(),packet)

    # Build checks as each layout's acceptance.sh declares them; the historical one is what the captured
    # readiness-02 exit records answer, the current one adds the dynamic-ELF control and drops the cmp step.
    LAYOUTS={
        'historical':('stewart.acceptance-driver/1',
            [('build-release',0,''),('build-test',0,''),('static-stewart',0,''),('static-stewart-test',0,''),
             ('build-glibc',0,''),('static-stewart-glibc',1,'control fired: '),('cmp-release-test',1,'control fired: '),
             ('run-release',0,'')]),
        'current':(study_build.spec.DRIVER_SCHEMA,
            [('build-release',0,''),('build-test',0,''),('static-stewart',0,''),('static-stewart-test',0,''),
             ('build-dynamic-control',0,''),('static-dynamic-control',1,'control fired: '),('run-release',0,''),
             ('run-test',0,'')]),
    }

    def source_archive(self,checks):
        script=''.join(f'    expect "$OUT/$b/{name}.exit" {code} "$p: {label}fixture"\n' for name,code,label in checks)
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            member=tarfile.TarInfo('apparatus/acceptance.sh');member.size=len(script.encode())
            archive.addfile(member,io.BytesIO(script.encode()))
        return stream.getvalue()

    def test_build_binding_checks_source_binary_and_evidence(self):
        for layout,(schema,checks) in self.LAYOUTS.items():
            with self.subTest(layout=layout):
                self.check_build_binding(schema,checks)

    def check_build_binding(self,schema,checks):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);acceptance=root/'study';base=root/'base'
            def put(path,data):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            archive=self.source_archive(checks)
            current=schema!='stewart.acceptance-driver/1'
            qualification={'source_commit':'1'*40,'evidence':{'path':'base'}}
            put(acceptance/'host/commit.stdout',('2'*40+'\n').encode())
            put(acceptance/'host/worktree.stdout',b'')
            put(acceptance/'host/DONE',b'done fixture failures=%d\n'%(6 if current else 4))
            put(acceptance/'staging/source.tar',archive)
            for arch in ('arm64','amd64'):
                r=captured_acceptance.study_result(arch)
                r['schema']=schema
                r['binaries']={'release':{'sha256':digest(b'release fixture')},
                               'test':{'sha256':digest(b'test fixture')}}
                put(acceptance/f'bin-{arch}/stewart',b'release fixture')
                put(acceptance/f'bin-{arch}/stewart-test',b'test fixture')
                put(acceptance/f'driver-{arch}/evidence/RESULT.json',compact(r))
                baseline=captured_acceptance.result(arch)
                baseline['schema']=schema
                put(base/f'driver-{arch}/evidence/RESULT.json',compact(baseline))
                put(acceptance/f'driver-{arch}/evidence-copy.exit',captured_acceptance.captured(
                    f'readiness-02/driver-{arch}/evidence-copy.exit'))
                # The observed successful run did not retain a release work
                # archive. These study-failure retention flags remain supplied.
                for name in ('retention-archive','retention-list','retention-sha256'):
                    put(acceptance/f'driver-{arch}/{name}.exit',b'0\n')
                put(acceptance/f'driver-{arch}/selftest.exit',b'1\n')
                put(acceptance/f'driver-{arch}/selftest.stdout',captured_acceptance.study_selftest(arch))
                if current:
                    put(acceptance/f'driver-{arch}/driver-complete.exit',b'1\n')
                for name,code,_label in checks:
                    exit_record=(acceptance/f'build-{arch}/{name}.exit')
                    if current:
                        put(exit_record,b'%d\n'%code)
                    else:
                        put(exit_record,captured_acceptance.captured(f'readiness-02/build-{arch}/{name}.exit'))
            def git(argv,**kwargs):
                if argv[1]=='rev-parse':return ('2'*40+'\n').encode()
                if argv[1]=='merge-base':return ('1'*40+'\n').encode()
                if argv[1]=='for-each-ref':return b'refs/heads/study-fixture\n'
                if argv[1]=='diff':
                    if argv[-1]=='apparatus/driver':
                        self.assertEqual(argv[3],'HEAD')
                    return b'service/src/forms.rs\n' if argv[-1]=='service' else b''
                if argv[1]=='archive':return archive
                raise AssertionError(argv)
            fired=next(name for name,_code,label in checks if label)
            with mock.patch.object(study_build.subprocess,'check_output',side_effect=git):
                value=study_build.make(root,qualification,self.interface,acceptance,self.expected)
                self.assertEqual(study_build.select(root,qualification,value),acceptance/'bin-arm64')
                for name,reason in [('bin-arm64/stewart','study binary digest differs'),
                             ('bin-amd64/stewart-test','study test binary digest differs'),
                             ('driver-arm64/evidence/RESULT.json','study result digest changed'),
                             ('staging/source.tar','study acceptance source binding differs'),
                             ('build-arm64/static-stewart.exit','study binary build/static controls differ'),
                             (f'build-amd64/{fired}.exit','study binary build/static controls differ'),
                             ('driver-arm64/evidence-copy.exit','study acceptance evidence incomplete'),
                             ('driver-arm64/selftest.exit','study self-test exit differs'),
                             ('driver-arm64/selftest.stdout','study self-test differs from declared failures'),
                             *([('driver-amd64/driver-complete.exit','study acceptance did not record its declared case failure')]
                               if current else [])]:
                    path=acceptance/name;old=path.read_bytes();path.write_bytes(old+b'changed')
                    with self.subTest(path=name),self.assertRaisesRegex(ValueError,reason):
                        study_build.select(root,qualification,value)
                    path.write_bytes(old)
                # Each layout is held to its own script: the other layout's checks are absent here.
                (acceptance/'build-arm64'/f'{checks[-1][0]}.exit').unlink()
                with self.assertRaises((ValueError,OSError)):
                    study_build.select(root,qualification,value)
                put(acceptance/'build-arm64'/f'{checks[-1][0]}.exit',b'%d\n'%checks[-1][1])
                changed=copy.deepcopy(value);changed['qualified_base_commit']='3'*40
                with self.assertRaisesRegex(ValueError,'study qualified base differs'):
                    study_build.select(root,qualification,changed)
                def changed_driver(argv,**kwargs):
                    if argv[1]=='diff' and argv[-1]=='apparatus/driver':
                        return b'apparatus/driver/driver_core.py\n'
                    return git(argv,**kwargs)
                with mock.patch.object(study_build.subprocess,'check_output',side_effect=changed_driver):
                    with self.assertRaisesRegex(ValueError,'independent driver'):
                        study_build.select(root,qualification,value)
            self.assertEqual([control for *_rest,control in study_build.build_checks(acceptance/'staging/source.tar')],
                             [bool(label) for *_rest,label in checks])


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
        executable=self.bin/'keyctl'
        executable.write_text('#!'+sys.executable+'\n'+FAKE_KEYCTL)
        executable.chmod(0o700)
        patch=mock.patch.dict(os.environ,{'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH',''),
                                         'ANTHROPIC_API_KEY':'never-read-this-ambient-key'})
        patch.start();self.addCleanup(patch.stop)

    def configure(self,exit=0,stdout=None,stderr='',sleep=0,fail_at='pipe'):
        self.response.write_text(json.dumps({'exit':exit,'stdout':self.key+'\n' if stdout is None else stdout,
                                            'stderr':stderr,'sleep':sleep,'fail_at':fail_at}))

    def test_lookup_reuses_separate_process_without_recording_secret(self):
        for n in range(2):
            self.assertEqual(connections.lookup('synthetic',rehearsal=True,record=self.records/f'{n}.json'),self.key.encode())
        calls=[json.loads(line) for line in (self.bin/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls,[['get_persistent','@s'], ['search','111','user','stewart-provider:synthetic'], ['pipe','222']]*2)
        self.assertTrue(all(self.key.encode() not in path.read_bytes() for path in self.records.iterdir()))

    def test_status_never_requests_or_prints_password(self):
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'c10.py'),'connection','status','synthetic'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['present'])
        self.assertNotIn(self.key.encode(),result.stdout+result.stderr)
        self.assertEqual([json.loads(line)[0] for line in (self.bin/'calls.jsonl').read_text().splitlines()], ['get_persistent','search'])

    def test_provisioning_only_supplies_key_on_padd_stdin(self):
        with mock.patch.object(connections, 'hidden_credential', return_value=self.key.encode()):
            result = connections.provision('synthetic')
        self.assertTrue(result['stored'])
        calls = [json.loads(line) for line in (self.bin/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls, [['get_persistent','@s'], ['padd','user','stewart-provider:synthetic','111'],
                                 ['setperm','222','0x003f0000']])
        self.assertNotIn(self.key, json.dumps([result, calls]))

    def test_guest_missing_metadata_lookup_replays_without_requesting_payload(self):
        observed = strict_json(read_file(HERE.parent/'testdata/keyring/metadata-missing.json'))
        self.assertIs(observed['payload_requested'], False)
        self.configure(exit=observed['exit'], stdout=observed['stdout'], stderr=observed['stderr'], fail_at='search')
        record = self.records/'missing.json'
        with self.assertRaises(connections.ConnectionError) as error:
            connections.status('synthetic',record=record)
        self.assertEqual(error.exception.code,'missing_item')
        result=strict_json(read_file(record))
        self.assertEqual([result['stage'],result['payload_requested'],result['outcome']],['search',False,'missing_item'])
        self.assertNotIn('"pipe"',(self.bin/'calls.jsonl').read_text())

    def test_wrong_label_withholds_payload(self):
        with self.assertRaises(connections.ConnectionError) as caught:
            connections.lookup('different')
        self.assertEqual(caught.exception.code, 'missing_item')
        self.assertNotIn('"pipe"', (self.bin/'calls.jsonl').read_text())

    def test_failures_are_distinct_and_never_echo_tool_streams(self):
        for n,(status,message,code) in enumerate([
            (1,'keyctl_search: Required key not available','missing_item'),
            (1,'keyctl_read_alloc: Permission denied','access_denied'),
            (1,'keyctl_read_alloc: Key has expired','expired_key'),
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

    def test_rehearsal_refuses_a_functional_value_and_maps_invalid_bytes(self):
        # The byte bounds themselves are credential_bytes's (sanity test_launch); one shows the mapping here.
        for value,code in [('functional-looking-value','not_synthetic'),('has space','invalid_credential')]:
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

    def test_saved_collection_uses_bound_label_and_only_pipe_input(self):
        root=self.root/'run';(root/'host').mkdir(parents=True);(root/'staging').mkdir()
        packet=proposal('example-model');packet['account']['credential_label']='synthetic'
        write_json(root/'staging/commission.json',packet)
        write_json(root/'host/RESULT.json',{'schema':'stewart.c10-launch/3','mode':'live','commission_sha256':digest(read_file(root/'staging/commission.json'))})
        write_json(root/'host/operator.json',{'schema':'stewart.c10-operator/1','container':'stewart-c10-1-2','audits':['open-ordinary-r1']})
        args=argparse.Namespace(evidence=root,audit='open-ordinary-r1',operation='collect',confirm=None,connection='synthetic')
        actual_run=subprocess.run
        observed=[]
        def run(argv,**kw):
            if argv[0]=='podman':
                observed.append((argv,kw['input'],kw['env']))
                return subprocess.CompletedProcess(argv,0)
            return actual_run(argv,**kw)
        with mock.patch.object(c10.subprocess,'run',side_effect=run):
            self.assertEqual(c10.host_control(args),0)
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
        self.assertEqual(packet['schema'],'stewart.study-commission/2')
        self.assertEqual(packet['runs'][0]['submission_sha256'],tree_hash(self.folder))
        rehearsed=study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True)
        self.assertEqual([run['id'] for run in rehearsed['runs']],REHEARSAL_AUDITS+['problem-a'])
        packet['schema']='stewart.c10-commission/2'
        with self.assertRaises(ValueError):validate_packet(packet)

    def test_supplied_compaction_scenarios_remain_offline_and_bind_exact_inputs(self):
        for scenario in ['compaction','compaction-below','compaction-invalid']:
            packet=study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True,
                                 scenarios=[('problem-a',scenario)])
            self.assertEqual(packet['runs'][-1]['scenario'],scenario)
            live=study_proposal('example-model',[('problem-a',self.folder)])
            c10.check_rehearsal_inputs(packet,live)
            live['runs'][0]['scenario']=scenario
            with self.assertRaisesRegex(ValueError,'rehearsal-only'):
                validate_packet(live)
        for scenarios in [[('absent','compaction')],[('problem-a','unsubmitted')],
                          [('problem-a','compaction'),('problem-a','compaction-below')]]:
            with self.subTest(scenarios=scenarios),self.assertRaises(ValueError):
                study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True,scenarios=scenarios)
        with self.assertRaisesRegex(ValueError,'rehearsal-only'):
            study_proposal('example-model',[('problem-a',self.folder)],scenarios=[('problem-a','compaction')])

    def test_interrupted_study_names_one_audit_its_point_and_its_ceiling(self):
        study=study_proposal('example-model',[('problem-a',self.folder)])
        packet=validate_packet(c10.interrupted_study(study,'reminder_notice',3))
        self.assertEqual((packet['schema'],packet['max_placements'],packet['interruption'],packet['automatic_continuation']),
                         ('stewart.interruption-commission/3',3,{'after':'reminder_notice','action':'signal'},False))
        self.assertEqual(study['max_placements'],1)
        # Its rehearsal is the ordinary one that includes the same template.
        rehearsed=study_proposal('rehearsal-only',[('problem-a',self.folder)],rehearsal=True)
        c10.check_rehearsal_inputs(rehearsed,packet)
        for reason,value in [('one placement per launch',c10.interrupted_study(study,'reminder_notice',1)),
                             ('one placement per launch',c10.interrupted_study(study,'reminder_notice',5)),
                             ('unsupported interruption point or action',c10.interrupted_study(study,'entry_record',2)),
                             ('an interrupted study names exactly one audit',
                              c10.interrupted_study(study_proposal('example-model',[('problem-a',self.folder),('problem-b',self.folder)]),'reminder_notice',2))]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                validate_packet(value)

    def test_propose_writes_an_unpaid_interrupted_study_and_prints_the_estimate(self):
        base=[sys.executable,'-I','-B',str(HERE/'c10.py'),'propose','--model','example-model',
              '--submission','problem-a',str(self.folder)]
        output=self.root/'interrupted.json'
        result=subprocess.run(base+['--interrupt-after','reminder_notice','--max-placements','2','--output',str(output)],
                              capture_output=True,stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode,0,result.stderr)
        packet=strict_json(read_file(output))
        self.assertEqual((packet['schema'],packet['max_placements'],packet['spending_authority'],packet['bindings']['binary_sha256']),
                         ('stewart.interruption-commission/3',2,None,None))
        # The default 12,000-token output allowance cannot absorb one estimated request and leave 1,024.
        estimate=json.loads(result.stdout.decode().rsplit('Unbound proposal',1)[0])['allowances']['planned_interruption']
        self.assertEqual((estimate['output_charge_if_one_request_is_aborted_in_flight'],
                          estimate['next_placement_ends_limit_reached_before_any_request']),(12000,True))
        for extra in [['--interrupt-after','reminder_notice'],['--max-placements','2']]:
            refused=subprocess.run(base+extra+['--output',str(self.root/'never.json')],capture_output=True,stdin=subprocess.DEVNULL)
            self.assertEqual(refused.returncode,2)
            self.assertIn(b'an interrupted study needs both --interrupt-after and --max-placements',refused.stderr)
            self.assertFalse((self.root/'never.json').exists())

    def test_exact_body_and_attributed_inquiry_survive_rendering(self):
        role_line = 'material-roles: [{"role": "report", "source": "materials/a\u2028b.txt"}]\n'.encode()
        (self.folder/'materials/a\u2028b.txt').write_bytes(b'A report.\n')
        question = self.folder/'question.md'
        question.write_bytes(question.read_bytes().replace(b'family: ', role_line+b'family: ', 1))
        parsed=inspect_submission(self.folder,'problem-a')
        self.assertEqual(parsed['question'],self.body)
        packet=proposal('changed-model');packet['effort']='high'
        rendered=question_file(parsed,packet,'/actual/returns')
        self.assertEqual(rendered.split(b'---\n',2)[2],self.body.encode())
        self.assertIn(role_line, rendered)
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
        self.assertEqual([run['id'] for run in c10.check_rehearsal_inputs(rehearsed,live)],
                         REHEARSAL_AUDITS+['problem-a'])
        moved=copy.deepcopy(live)
        moved['runs'][0]['submission_folder']='/a/new/location/with/the/same/bytes'
        c10.check_rehearsal_inputs(rehearsed,moved)
        changed=copy.deepcopy(live);changed['runs'][0]['submission_sha256']='0'*64
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsed,changed)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsal_packet(),live)
        rehearsed['runs'].pop(0)
        with self.assertRaises(ValueError):c10.check_rehearsal_inputs(rehearsed,live)


class NativeSmokeTests(unittest.TestCase):
    def test_failures_stop_later_continuations_and_clean_batch_runs_them(self):
        for failure, not_started, continued_failure, expected_calls in [
                (1, 0, False, 0), (0, 1, False, 0),
                (0, 0, True, 1), (0, 0, False, 2)]:
            with self.subTest(failure=failure, not_started=not_started, continued_failure=continued_failure), \
                    tempfile.TemporaryDirectory() as folder:
                root=Path(folder)/'evidence'
                packet=rehearsal_packet()
                packet['runs']=[r for r in packet['runs'] if r['id'] in
                                ['control-continue-cap','control-continue-entries']]
                report={'audits':[{'audit':r['id'],'placement':'observed','expected_observation':True}
                                  for r in packet['runs']],
                        'planned':2,'observed':2-not_started,'failed':failure,
                        'not_started':not_started,'skipped_checks':[]}
                result={'failed':continued_failure,'review':{},'attempt':2,'placement_state':'observed',
                        'expected_observation':not continued_failure,'export':{},'second_start':{},'controls':{}}
                with mock.patch.object(sys,'argv',['smoke.py','--binary',str(root.parent/'binary'),
                                                  '--evidence',str(root)]), \
                        mock.patch.object(smoke,'rehearsal_packet',return_value=packet), \
                        mock.patch.object(smoke,'file_hash',return_value='0'*64), \
                        mock.patch.object(smoke,'prepare_batch',return_value=[]), \
                        mock.patch.object(smoke,'execute_batch',return_value=report), \
                        mock.patch.object(smoke,'continuation_packet',return_value={}) as bind, \
                        mock.patch.object(smoke,'continue_with_attempt_controls',return_value=(result,[{'passed':True}])) as later, \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(smoke.main(),bool(failure or not_started or continued_failure))
                self.assertEqual(later.call_count,expected_calls)
                self.assertEqual(bind.call_count,expected_calls)
                self.assertEqual(len(list((root/'continuation-packets').glob('*.json'))),expected_calls)


class PacketTests(unittest.TestCase):
    def test_catalog_covers_families_and_inadequate_variants(self):
        cases=catalog()
        self.assertEqual({(item['family'], item['variant']) for item in cases.values()},
                         {('open-inquiry','ordinary'), ('open-inquiry','inadequate'),
                          ('inquiry-framing','ordinary'), ('inquiry-framing','inadequate'),
                          ('comparison','ordinary'), ('comparison','inadequate')})
        self.assertEqual(len(proposal('example-model',repetitions=3)['runs']),18)

    def test_rehearsal_inventory_is_the_specified_cases_and_controls(self):
        packet=rehearsal_packet()
        self.assertEqual([run['id'] for run in packet['runs']],REHEARSAL_AUDITS)
        self.assertEqual([run['scenario'] for run in packet['runs']],
                         ['submitted']*6+SINGLE_PLACEMENT_CONTROLS+list(CONTINUED_CONTROLS)+TRIAL_SCENARIOS)
        self.assertEqual({name:(value['interruption'],value['endings']) for name,value in common.CONTINUED.items()},
                         CONTINUED_CONTROLS)
        self.assertEqual({name:value['held'] for name,value in common.CONTINUED.items()},HELD_CONTROLS)
        self.assertEqual((len(packet['runs']),len(common.CONTINUED)),(27,8))
        # Every first launch is one placement; a later one is never implied by the packet.
        self.assertEqual((packet['max_placements'],packet['automatic_continuation']),(1,False))
        # INTERFACE 6.4: an interrupted in-flight request is charged its whole
        # max_tokens (at most 16,000), and 1,024 must remain for the next placement.
        self.assertGreaterEqual(packet['limits']['output_tokens'],16000+1024)

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

    def test_rehearsal_folder_name_must_carry_its_continuation_records(self):
        # Each continued control keeps host records in `<rehearsal>-<audit>-p2`, itself an identifier of at most 80 characters.
        def args(name):
            return argparse.Namespace(mode='rehearse',evidence=c10.REPO/'.scratch'/name,commission=None,
                approved_commission=None,rehearsal=None,qualification='unused')
        with mock.patch.object(c10,'bindings',side_effect=RuntimeError('name gate passed')) as bind:
            for name in ['r'*50,'Rehearsal-01','rehearsal_01']:
                with self.subTest(name=name),self.assertRaisesRegex(c10.Refused,'continuation controls keep their records in new folders'):
                    c10.launch_batch(args(name))
            bind.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'^name gate passed$'):
                c10.launch_batch(args('c10-name-gate-never-created'))
        self.assertFalse((c10.REPO/'.scratch/c10-name-gate-never-created').exists())

    def test_live_packet_refusals_name_their_reason_before_bindings_or_credential(self):
        """Each refusal differs from an approved packet in one respect and stops before any binding check,
        keyring lookup or prompt; the approved packet itself passes to the binding check."""
        def approved(value):
            value['spending_authority'] = 'synthetic gate control; no launch'
            value['account'] = {key:'synthetic-label' for key in value['account']}
            value['bindings'] = {key:'synthetic-binding' for key in value['bindings']}
            return value
        interface = {'schema':'stewart.c10-interface/1','id':'guidance-test','family':'open-inquiry','version':2,
                     'instructions':'Compose an account.'}
        evidence = c10.REPO/'.scratch/c10-authority-never-created'
        cases = [
            ('unpaid proposal', proposal('example-model'), None, None,
             ValueError, 'approved packet has unfilled authority or bindings'),
            ('changed digest', approved(proposal('example-model')), '0'*64, None,
             ValueError, 'commission differs from approved digest'),
            ('draft study build', approved(study_build.attach(proposal('example-model'), study_build.draft(interface))),
             None, None, ValueError, 'invalid study source identity'),
            ('another saved connection', approved(proposal('example-model')), None, 'different',
             connections.ConnectionError, 'differs from the packet credential_label'),
        ]
        with tempfile.TemporaryDirectory() as temp:
            for name, value, approval, connection, error, reason in cases:
                packet = Path(temp)/(name.replace(' ','-')+'.json');write_json(packet,value)
                args = argparse.Namespace(mode='live',evidence=evidence,commission=packet,
                    approved_commission=approval or digest(read_file(packet)),rehearsal=Path(temp),
                    qualification='unused',connection=connection)
                with self.subTest(refusal=name), mock.patch.object(c10,'bindings') as bind, \
                        mock.patch.object(c10,'connection_key') as lookup:
                    with self.assertRaisesRegex(error, reason):
                        c10.launch_batch(args)
                    bind.assert_not_called();lookup.assert_not_called()
            packet = Path(temp)/'approved.json';write_json(packet,approved(proposal('example-model')))
            args = argparse.Namespace(mode='live',evidence=evidence,commission=packet,
                approved_commission=digest(read_file(packet)),rehearsal=Path(temp),qualification='unused',connection=None)
            with mock.patch.object(c10,'bindings',side_effect=RuntimeError('digest gate passed')) as bind, \
                    mock.patch.object(c10,'connection_key') as lookup:
                with self.assertRaisesRegex(RuntimeError, '^digest gate passed$'):
                    c10.launch_batch(args)
                bind.assert_called_once();lookup.assert_not_called()
        self.assertFalse(evidence.exists())


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
            test_launch.complete_evidence(root)
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

    def test_compaction_trigger_uses_all_top_level_counts_independently_of_charges(self):
        usage={'input_tokens':100000,'cache_creation_input_tokens':30000,
               'cache_read_input_tokens':19799,'output_tokens':200,
               'iterations':[{'type':'message','input_tokens':900000,'output_tokens':1}]}
        self.assertEqual(trigger_tokens(usage),149999)
        self.assertEqual(usage_counts(usage)['input_tokens'],900000)
        usage['cache_read_input_tokens']=19800
        self.assertEqual(trigger_tokens(usage),150000)
        usage['iterations']=[{'type':'message','input_tokens':1,'output_tokens':1}]
        self.assertEqual(trigger_tokens(usage),150000)
        self.assertEqual(usage_counts(usage)['input_tokens'],1)
        for invalid in [True,-1,2**48+1,None]:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                trigger_tokens({**usage,'input_tokens':invalid})

    def test_signed_summary_shape_and_failure_causes(self):
        def response(blocks,stop='compaction'):
            return rawjson.parse(b'{"content":'+blocks+b',"stop_reason":'+compact(stop)+b'}')
        signed=b'{"type":"compaction","content":"summary","signature":"signed"}'
        self.assertIsNone(compaction_cause(response(b'['+signed+b']')))
        opaque=signed[:-1]+b',"opaque":1,"opaque":2}'
        self.assertIsNone(compaction_cause(response(b'[ '+opaque+b' ]')))
        for block in [b'[]',b'['+signed+b','+signed+b']',b'[null]',
                      b'['+signed.replace(b'"signed"',b'""')+b']',
                      b'['+signed.replace(b'"summary"',b'5')+b']',
                      b'['+signed[:-1]+b',"signature":"signed"}]',
                      b'['+signed[:-1]+b',"type":"compaction"}]']:
            with self.subTest(block=block):
                self.assertEqual(compaction_cause(response(block)),'protocol_anomaly')
        for stop,cause in [('max_tokens','max_tokens'),('refusal','provider_refusal'),
                           ('model_context_window_exceeded','context_exhausted'),
                           ('end_turn','protocol_anomaly'),('stop_sequence','protocol_anomaly'),
                           ('tool_use','protocol_anomaly'),('new_stop','protocol_anomaly')]:
            with self.subTest(stop=stop):
                self.assertEqual(compaction_cause(response(b'['+signed+b']',stop)),cause)

    def test_summary_request_splices_pinned_settings_and_signed_bytes(self):
        arrangement=rawjson.parse(b'{"model":"m","system":[ ],"tools":[],"request_extra":'
                                  b'{"output_config": {"effort":"high"}},'
                                  b'"compaction":{"trigger_tokens":150000,"request":{"type":"summarize"}}}')
        signed=b'{"role":"assistant","content":[ {"type":"compaction", "content":"s", "signature":"x", "unknown":7} ]}'
        prefix=b'{"model":"m","max_tokens":1234,"system":[ ],"tools":[],"output_config": {"effort":"high"}'
        self.assertEqual(ordinary_body(arrangement,1234,[signed],True),
                         prefix+b',"compaction":{"type":"summarize"},"messages":['+signed+b']}')
        self.assertEqual(ordinary_body(arrangement,1234,[signed]),prefix+b',"messages":['+signed+b']}')

    def test_raw_response_usage_refuses_duplicates_and_invalid_top_level_counts(self):
        usage=(b'{"input_tokens":999,"output_tokens":999,"iterations":['
               b'{"type":"message","input_tokens":2,"output_tokens":3},'
               b'{"type":"compaction","input_tokens":5,"output_tokens":7}]}')
        def parse(raw):
            return rawjson.parse(b'{"content":[],"stop_reason":"compaction","usage":'+raw+b'}')
        self.assertEqual(response_usage(parse(usage),True),
                         {'input_tokens':7,'output_tokens':10,'cache_creation_input_tokens':0,'cache_read_input_tokens':0})
        for raw in [usage.replace(b'"type":"compaction"',b'"type":"compaction","type":"compaction"'),
                    usage.replace(b'"input_tokens":5',b'"input_tokens":5,"input_tokens":5'),
                    usage[:-1]+b',"iterations":null}',
                    usage.replace(b'"input_tokens":999',b'"input_tokens":999,"input_tokens":999')]:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'response_usage_members'):
                response_usage(parse(raw),True)
        for raw in [usage.replace(b'"input_tokens":999',b'"input_tokens":true'),
                    usage.replace(b'"output_tokens":999',b'"output_tokens":-1')]:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'invalid_usage_count'):
                response_usage(parse(raw),True)
        for raw in [b'{"input_tokens":1,"output_tokens":2}',
                    b'{"input_tokens":1,"output_tokens":2,"iterations":null}',
                    usage.replace(b'"type":"compaction"',b'"type":"message"')]:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'summary_usage_iterations'):
                response_usage(parse(raw),True)
        unknown=usage.replace(b'"type":"compaction"',b'"type":"compaction","opaque":1,"opaque":2')
        self.assertEqual(response_usage(parse(unknown),True),response_usage(parse(usage),True))


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
    def test_launcher_checkout_retains_its_own_git_metadata_and_objects(self):
        git = self.root/'.git'
        git.write_text('gitdir: /agent-controlled/metadata')
        with self.assertRaisesRegex(ValueError, 'standalone'):
            host_queue.check_repository(self.root)
        git.unlink()
        (git/'objects/info').mkdir(parents=True)
        (git/'objects/info/alternates').write_text('/agent-controlled/objects')
        with self.assertRaisesRegex(ValueError, 'standalone'):
            host_queue.check_repository(self.root)
        (git/'objects/info/alternates').unlink()
        with mock.patch.object(host_queue,'protected'):
            host_queue.check_repository(self.root)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.scratch').mkdir()
        patch = mock.patch.object(host_queue, 'REPO', self.root)
        patch.start(); self.addCleanup(patch.stop)
        price = {'context_tokens':1000000, 'bands':[{'through_input_tokens':1000000,
            'input_tokens':10000,'cache_creation_input_tokens':10000,
            'cache_read_input_tokens':10000,'output_tokens':50000}]}
        self.config = {'schema':'stewart.c10-campaign/3',
            'envelope':{'cases':list(catalog()),'submissions':{},'efforts':[None],
                        'limits':{'turns':12,'input_tokens':160000,'output_tokens':30000},
                        'max_placements':2,'watchdog_seconds':900,'study_build_sha256':None,
                        'pricing':{'test-model':price,'test-diagnostic':price}},
            'campaign':'test-campaign','authority':'bounded test authority','qualification':'test-qualified',
            'account':{'account_label':'test','workspace_id':'test-workspace','credential_label':'test-key'},
            'synthetic_connection':'test-synthetic','placement_ceiling':2,'budget_usd':50,
            'wave':1,'wave_one_ceiling':2,'wave_one_model':'test-model',
            'cards':str(self.root/'cards'),'grant_path':str(self.root/'grant.json')}
        self.grant(self.config)
        self.real_exposure=host_queue.exposure_review
        safe_exposure=mock.patch.object(host_queue,'exposure_review',return_value=True)
        safe_exposure.start();self.addCleanup(safe_exposure.stop)
        self.real_card=host_queue.frozen_card
        card_patch=mock.patch.object(host_queue,'frozen_card',return_value=('test-slot',b'{}'))
        card_patch.start();self.addCleanup(card_patch.stop)
        settlement=mock.patch.object(host_queue,'priced_export',return_value=True)
        settlement.start();self.addCleanup(settlement.stop)
        self.packet = proposal('test-model', ['open-ordinary'])
        self.packet['limits']['input_tokens']=90000
        self.packet['account'] = self.config['account'].copy()
        self.packet['file_size_limit'] = 131072
        self.packet['spending_authority'] = self.config['authority']
        self.packet['bindings'] = dict.fromkeys(self.packet['bindings'], 'test-binding')
        self.packet['bindings']['qualification_id'] = 'test-qualified'
        self.packets = self.root/'queue/packets'
        self.packets.mkdir(parents=True)
        self.path = self.packets / 'packet.json'
        self.save_packet()
        self.publish = host_queue.result_summary
        def summary(queue,name,request,code,slots,money,**extra):
            if code==0 and request.get('operation') in ['live','continue','rehearse']:
                # Child process is stubbed in these queue tests.
                record=Path(request.get('record',request['evidence']))
                (record/'host').mkdir(parents=True)
                write_json(record/'host/operator.json',{'schema':'stewart.c10-operator/1','audits':[]})
                write_json(record/'host/RESULT.json',{'outcome':'stubbed'})
            return self.publish(queue,name,request,code,slots,money,**extra)
        publication=mock.patch.object(host_queue,'result_summary',side_effect=summary)
        publication.start(); self.addCleanup(publication.stop)
        self.request = {'operation': 'live', 'evidence': str(self.root / '.scratch/live-01'),
            'packet': str(self.path), 'sha256': digest(read_file(self.path)),
            'rehearsal': str(self.root / '.scratch/rehearsal-01')}

    def save_packet(self):
        self.path.write_text(json.dumps(self.packet))
        if hasattr(self, 'request'):
            self.request['sha256'] = digest(read_file(self.path))

    def grant(self, config):
        record={'schema':'stewart.runtime-trials.envelope/1','waves':2,'campaign':config['campaign'],
                'grant':config['authority'],'messages':{'endpoint':'https://api.anthropic.com',
                'models':list(config['envelope']['pricing']),'wave_one_model':config['wave_one_model'],
                'credential_label':config['account']['credential_label'],'placements':config['placement_ceiling'],
                'wave_one_placements':config['wave_one_ceiling'],'cap_usd_cents':host_queue.cents(config['budget_usd'])}}
        raw=json.dumps(record).encode()
        Path(config['grant_path']).write_bytes(raw)
        config['grant_sha256']=digest(raw)
        return config

    def test_live_needs_explicit_enable_and_exact_protected_grant(self):
        with self.assertRaisesRegex(ValueError,'offline'):
            host_queue.command(self.request,self.config,False)
        for change in [{'grant_sha256':'f'*64},{'placement_ceiling':3},{'budget_usd':51},
                       {'authority':'another commission'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                host_queue.configuration({**self.config,**change},True)

    def test_both_models_share_nonrenewing_allowance_and_wave_one_is_sonnet_only(self):
        self.assertFalse(host_queue.model_allowed(self.config,'test-diagnostic'))
        wave_two={**self.config,'wave':2}
        self.assertTrue(host_queue.model_allowed(host_queue.configuration(wave_two,True),'test-diagnostic'))
        self.assertEqual(wave_two['budget_usd'],self.config['budget_usd'])

    def test_frozen_card_binds_packet_and_refuses_duplicate_slot_on_restart(self):
        d=Path(self.config['cards']);d.mkdir()
        name=self.packet['runs'][0]['id']
        card={'campaign':self.config['campaign'],'wave':1,'trial':name,'placement':1,
            'question':'fixture open inquiry','reason':'uninterrupted reference',
            'packet_sha256':self.request['sha256'],'model':self.packet['model'],
            'qualification':self.packet['bindings']['qualification_id'],'apparatus_sha256':'test-binding',
            'writer_sha256':'test-binding','grant_sha256':self.config['grant_sha256'],'file_size_limit':131072}
        slot=name+'-p1'
        write_json(d/(slot+'.json'),card)
        self.assertEqual(self.real_card(self.config,self.packet,self.request,[]),(slot,read_file(d/(slot+'.json'))))
        claim=self.root/'earlier-claim';claim.mkdir()
        write_json(claim/'command.json',{'slot':slot})
        with self.assertRaisesRegex(ValueError,'already claimed'):
            self.real_card(self.config,self.packet,self.request,[claim])
        with self.assertRaisesRegex(ValueError,'differs'):
            self.real_card(self.config,self.packet,{**self.request,'sha256':'0'*64},[])

    def test_staged_source_collision_withholds_credential_and_records_only_fixed_roles(self):
        staging=self.root/'staging'
        staging.mkdir()
        secret=b'c10-NONFUNCTIONAL-offline-control'
        (staging/'source.tar').write_bytes(b'archived fixture: '+secret)
        inputs=staging/'submissions'
        inputs.mkdir()
        escaped=b''.join(b'\\u%04x'%c for c in secret)
        (inputs/'private-name').write_bytes(escaped)
        proc=mock.Mock()
        report={'credential_sent':False}
        with self.assertRaisesRegex(ValueError,'staged'):
            c10.handoff(proc,staging,secret,report)
        proc.stdin.write.assert_not_called()
        self.assertFalse(report['credential_sent'])
        self.assertEqual(report['staging_scan']['findings'],[
            {'artifact':'source archive','producer':'git archive','form':'literal','files':1},
            {'artifact':'submission','producer':'input staging','form':'ASCII JSON escape','files':1}])
        self.assertNotIn(secret.decode(),json.dumps(report))
        self.assertNotIn('private-name',json.dumps(report))
        (staging/'source.tar').write_bytes(b'ordinary source')
        (inputs/'private-name').write_bytes(b'ordinary submission')
        c10.handoff(proc,staging,secret,report)
        proc.stdin.write.assert_called_once_with(secret)
        self.assertTrue(report['credential_sent'])

    def test_host_and_current_snapshot_scans_are_both_required(self):
        tree=Path(self.request['evidence'])
        (tree/'host').mkdir(parents=True)
        audit=self.packet['runs'][0]['id']
        first=tree/'container'/audit/'export-0001'
        first.mkdir(parents=True)
        scan={'files':3,'errors':0,'files_with_matches':0}
        host=tree/'host/RESULT.json'
        meta=first/'EXPORT.json'
        queue=self.root/'queue'
        for case in ('only-host','only-export','malformed','missing-stage','complete'):
            (queue/'claims'/case).mkdir(parents=True)
            host.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
            if case!='only-export':
                doc={'host_scan':scan}
                if case!='missing-stage': doc['staging_scan']=scan
                write_json(host,doc)
            if case!='only-host':
                write_json(meta,{'scan':scan} if case!='malformed' else {'scan':{}})
            with self.subTest(case=case):
                self.assertEqual(self.real_exposure(queue,case,self.request,self.packet),case=='complete')

    def test_continuation_requires_both_host_trees_and_its_own_export(self):
        original=Path(self.request['evidence'])
        record=self.root/'.scratch/continuation'
        request={**self.request,'operation':'continue','record':str(record)}
        packet={'audit':'example','placement':2}
        scan={'files':4,'errors':0,'files_with_matches':0}
        receipt={'scan':scan}
        folder=original/'container/example'
        for snapshot in ('export-0001','export-0002'):
            (folder/snapshot).mkdir(parents=True)
            write_json(folder/snapshot/'EXPORT.json',receipt)
        session_path=original/'container/continuations/example-p2/attempt-1/RESULT.json'
        session_path.parent.mkdir(parents=True)
        session={'schema':'stewart.c10-continuation-session/1','audit':'example','placement':2,
                 'attempt':1,'packet_sha256':request['sha256'],'snapshot':'export-0002','export':receipt}
        (record/'host').mkdir(parents=True)
        queue=self.root/'queue'
        for case in ('complete','absent-host-tree','prior-only','different-attempt','missing-current'):
            with self.subTest(case=case):
                scans={'record':scan,'evidence':scan}
                if case=='absent-host-tree': del scans['evidence']
                (record/'host/RESULT.json').unlink(missing_ok=True)
                session_path.unlink(missing_ok=True)
                write_json(record/'host/RESULT.json',{'attempt':1,'staging_scan':scan,'host_scan':scans})
                current=session.copy()
                if case=='prior-only': current['snapshot']='export-0001'
                if case=='different-attempt': current['attempt']=2
                if case=='missing-current': (folder/'export-0002/EXPORT.json').unlink()
                write_json(session_path,current)
                (queue/'claims'/case).mkdir(parents=True)
                self.assertEqual(self.real_exposure(queue,case,request,packet),case=='complete')

    def test_unsuccessful_scan_publishes_no_archive_even_when_dispatch_exited_zero(self):
        queue=self.root/'queue'
        (queue/'requests').mkdir()
        write_json(queue/'requests/first.json',self.request)
        config=self.root/'config.json'
        write_json(config,self.config)
        with mock.patch.object(host_queue,'exposure_review',side_effect=self.real_exposure), \
             mock.patch.object(host_queue.subprocess,'check_output',return_value=b''), \
             mock.patch.object(host_queue,'source_hash',return_value='source'), \
             mock.patch.object(host_queue.subprocess,'run',return_value=subprocess.CompletedProcess([],0)), \
             mock.patch.object(host_queue,'publish_exports') as publish:
            self.assertEqual(host_queue.serve(queue,config,True,once=True),1)
            publish.assert_not_called()
        self.assertFalse(list((queue/'results').glob('*.tar')))
        self.assertEqual(strict_json(read_file(queue/'results/first.json'))['exit'],1)

    def test_positive_exposure_count_stops_before_publishing_and_contains_only_counts(self):
        d=Path(self.request['evidence'])
        (d/'host').mkdir(parents=True)
        write_json(d/'host/RESULT.json',{'host_scan':{'files':3,'errors':0,'files_with_matches':1}})
        queue=self.root/'queue';(queue/'claims/exposure').mkdir(parents=True)
        self.assertFalse(self.real_exposure(queue,'exposure',self.request,self.packet))
        self.assertTrue((queue/'STOP').is_file())
        self.assertEqual(strict_json(read_file(queue/'claims/exposure/exposure.json')),
                         {'scans':1,'files_examined':3,'files_with_matches':1,'errors':2,'credential_printed':False})

    def test_price_bands_known_cache_and_unknown_usage(self):
        from billing import charge,worst_case
        def band(n, rate):
            return dict(through_input_tokens=n,input_tokens=rate,cache_creation_input_tokens=2*rate,
                        cache_read_input_tokens=rate//10,output_tokens=5*rate)
        card={'context_tokens':1000000,'bands':[band(100000,100000),band(1000000,500000)]}
        rows=[{'basis':'reported','input_tokens':100000,'cache_creation_input_tokens':0,
               'cache_read_input_tokens':1,'output_tokens':200},
              {'basis':'estimated','input_tokens':20,'cache_creation_input_tokens':0,
               'cache_read_input_tokens':0,'output_tokens':16000}]
        usage={'turns':{'reported':1,'estimated':1},'input_tokens':{'reported':100001,'estimated':20},
               'output_tokens':{'reported':200,'estimated':16000}}
        actual=charge(card,{'billing':rows,'usage':usage})
        self.assertEqual(actual['microdollars_times_million'],100000*500000+50000+200*2500000+20*1000000+16000*2500000)
        with self.assertRaisesRegex(ValueError,'does not equal'):
            charge(card,{'billing':rows[:-1],'usage':usage})
        with self.assertRaisesRegex(ValueError,'compaction'):
            worst_case(card,{'input_tokens':150000,'output_tokens':1024})

    def test_large_capture_reservation_covers_retry_and_terminal_estimates(self):
        from billing import worst_case
        rates = json.loads((Path(__file__).resolve().parents[2]/'alignment/messages/pricing-2026-11-21.json').read_bytes())
        limits = {'turns':16,'input_tokens':1000000,'output_tokens':24000}
        for model, cents in [('claude-haiku-5-5',482),('claude-opus-5-5',3852)]:
            with self.subTest(model=model):
                self.assertEqual(worst_case(rates[model],limits,file_limit=655360),cents)
                with self.assertRaisesRegex(ValueError,'compaction'):
                    worst_case(rates[model],limits)
        # At fewer turns, actual potentially billed lost replies dominate the byte estimate.
        self.assertEqual(worst_case(rates['claude-opus-5-5'],{**limits,'turns':5},file_limit=655360),3280)

    def test_compaction_queue_refuses_over_budget_or_used_slot_before_launch(self):
        from study import study_proposal
        from compaction_specimen import generate
        for name in ('exact', 'over', 'used'):
            with self.subTest(name=name):
                queue = self.root/name
                for sub in ('requests','packets','submissions','claims'):
                    (queue/sub).mkdir(parents=True)
                material = queue/'submissions/traces'
                generate(material)
                packet = study_proposal('test-model',[('traces',material)])
                packet.update(file_size_limit=655360, limits={'turns':16,'input_tokens':1000000,'output_tokens':24000},
                              max_placements=1, account=self.config['account'], spending_authority=self.config['authority'],
                              bindings=self.packet['bindings'])
                cfg = {**self.config,'placement_ceiling':1,'wave_one_ceiling':1}
                cfg['envelope'] = {**cfg['envelope'],'limits':packet['limits'],'submissions':{'traces':packet['runs'][0]['submission_sha256']}}
                amount = host_queue.reservation(cfg,1,packet)
                cfg['budget_usd'] = (amount - (name=='over'))/100
                self.grant(cfg)
                grant = Path(cfg['grant_path'])
                grant.write_text(json.dumps({**json.loads(grant.read_bytes()),'file_size_limit':655360}))
                cfg['grant_sha256'] = digest(grant.read_bytes())
                path = queue/'packets/traces.json'
                write_json(path,packet)
                write_json(queue/'requests/try.json',{**self.request,'evidence':str(self.root/'.scratch'/name),
                           'packet':str(path),'sha256':digest(path.read_bytes())})
                if name=='used':
                    earlier=queue/'claims/earlier'
                    earlier.mkdir()
                    write_json(earlier/'result.json',{'exit':0})
                    write_json(earlier/'command.json',{'placement_charge':1,'reserved_cents':amount})
                config=self.root/(name+'.json')
                write_json(config,cfg)
                with mock.patch.object(host_queue.subprocess,'check_output',return_value=b''), mock.patch.object(
                        host_queue,'source_hash',return_value='source'), mock.patch.object(host_queue.subprocess,'run',
                        return_value=subprocess.CompletedProcess([],0)) as child:
                    code=host_queue.serve(queue,config,True,once=True)
                if name=='exact':
                    self.assertEqual((code,child.call_count),(0,1))
                else:
                    self.assertEqual((code,child.call_count),(1,0))
                    reason = 'campaign budget exhausted' if name=='over' else 'campaign placement ceiling reached'
                    self.assertEqual(json.loads((queue/'results/try.json').read_bytes())['reason'],reason)
                    self.assertFalse((queue/'claims/try').exists())

    def test_pre_send_estimate_can_exceed_context_and_guard_is_mandatory(self):
        from billing import worst_case
        rate=dict(through_input_tokens=1000000,input_tokens=2000000,cache_creation_input_tokens=4000000,
                  cache_read_input_tokens=100000,output_tokens=10000000)
        card={'context_tokens':1000000,'bands':[rate]}
        self.assertEqual(worst_case(card,{'turns':12,'input_tokens':90000,'output_tokens':16000}),468)
        self.assertEqual(worst_case(card,{'turns':24,'input_tokens':100000,'output_tokens':48000}),542)
        with self.assertRaisesRegex(ValueError, '128 KiB'):
            host_queue.check_envelope({**self.packet,'file_size_limit':None},self.config,None)

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

    def continuation(self,**changes):
        evidence=self.root/'.scratch/earlier-01'
        evidence.mkdir(exist_ok=True)
        packet={'schema':'stewart.c10-continuation/3','evidence':str(evidence),'audit':'case-a',
            'container':'stewart-c10-1-2','reference':'stw1:'+'a'*17+':'+'b'*17+':/work/c10-private/case-a/archive',
            'placement':2,'max_placements':2,
            'prior':{'runs':1,'last_ending':'interrupted','last_cause':'max_tokens','log_head_sha256':None,'usage':None},
            'model':'test-model','limits':{'turns':12,'input_tokens':90000,'output_tokens':30000},
            'endpoint':'https://api.anthropic.com','proxy':None,'interruption':None,'permitted_request_attempts':4,
            'automatic_continuation':False,'file_size_limit':131072,'stop_after_seconds':900,'spending_authority':self.config['authority'],
            'account':self.config['account'].copy(),
            'bindings':{**dict.fromkeys(common.BINDINGS,'test-binding'),'qualification_id':'test-qualified'},**changes}
        path=self.packets/'continuation.json'
        path.write_text(json.dumps(packet))
        return {'operation':'continue','evidence':str(evidence),'record':str(self.root/'.scratch/later-01'),
                'packet':str(path),'sha256':digest(read_file(path)),'rehearsal':str(self.root/'.scratch/rehearsal-01')}

    def test_continue_request_keeps_the_live_guarantees(self):
        request=self.continuation()
        argv,charge=host_queue.command(request,self.config,True)
        self.assertEqual(charge,1)
        self.assertEqual(argv[3:8],[str(host_queue.HERE/'c10.py'),'continue','live',request['evidence'],request['record']])
        for flag,value in [('--packet',request['packet']),('--approved-packet',request['sha256']),
                           ('--rehearsal',request['rehearsal']),('--connection','test-key'),
                           ('--qualification','test-qualified')]:
            self.assertEqual(argv[argv.index(flag)+1],value)
        with self.assertRaisesRegex(ValueError,'offline'):
            host_queue.command(request,self.config,False)
        with self.assertRaisesRegex(ValueError,'packet digest differs'):
            host_queue.command({**request,'sha256':'0'*64},self.config,True)
        with self.assertRaisesRegex(ValueError,'continuation request fields differ'):
            host_queue.command({**request,'audit':'case-a'},self.config,True)
        other=self.root/'.scratch/another-01';other.mkdir()
        with self.assertRaisesRegex(ValueError,'packet continues an audit in another evidence folder'):
            host_queue.command({**request,'evidence':str(other)},self.config,True)
        with self.assertRaisesRegex(ValueError,'retained evidence of the original launch is missing'):
            host_queue.command({**request,'evidence':str(self.root/'.scratch/absent-01')},self.config,True)
        # Neither packet kind passes under the other operation.
        with self.assertRaisesRegex(ValueError,'commission fields differ'):
            host_queue.command({**self.request,'packet':request['packet'],'sha256':request['sha256']},self.config,True)
        with self.assertRaisesRegex(ValueError,'continuation fields differ'):
            host_queue.command({**request,'packet':self.request['packet'],'sha256':self.request['sha256']},self.config,True)
        for change in [{'model':'other'},{'spending_authority':'other'},{'spending_authority':None},
                       {'account':{**self.config['account'],'credential_label':'other'}},
                       {'bindings':{**dict.fromkeys(common.BINDINGS,'test-binding'),'qualification_id':'other'}}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                host_queue.command(self.continuation(**change),self.config,True)
        Path(request['record']).mkdir()
        with self.assertRaisesRegex(ValueError,'continuation record already exists'):
            host_queue.command(self.continuation(),self.config,True)

    def test_continue_claims_one_slot_once_and_waits_for_reconciliation(self):
        queue=self.root/'queue'
        (queue/'requests').mkdir(parents=True)
        write_json(queue/'requests/second.json',self.continuation())
        config=self.root/'config.json';write_json(config,self.config)
        def serve():
            with mock.patch.object(host_queue.subprocess,'check_output',return_value=b''), \
                 mock.patch.object(host_queue,'source_hash',return_value='source'), \
                 mock.patch.object(host_queue.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run, \
                 redirect_stdout(io.StringIO()):
                return host_queue.serve(queue,config,True,once=True),run.call_count
        # An earlier paid claim that failed blocks this one until it is reconciled.
        (queue/'claims/first').mkdir(parents=True)
        write_json(queue/'claims/first/command.json',{'placement_charge':1,'reserved_cents':100})
        write_json(queue/'claims/first/result.json',{'exit':1})
        write_json(queue/'claims/first/request.json',{'operation':'live','evidence':str(self.root/'.scratch/earlier-01')})
        self.assertEqual(serve(),(1,0))
        self.assertIn('unfinished host claim',strict_json(read_file(queue/'results/second.json'))['reason'])
        self.assertFalse((queue/'claims/second').exists())
        witness=self.root/'witness.json';witness.write_bytes(b'{"observed":"fixture stopped"}')
        write_json(queue/'claims/first/reconciliation.json',{'author':'test reader','disposition':'fixture effects reconciled',
            'evidence':[{'path':str(witness),'sha256':digest(read_file(witness))}]})
        write_json(queue/'requests/reconciled.json', self.continuation())
        self.assertEqual(serve(),(0,1))
        write_json(queue/'claims/reconciled/settlement.json',{'schema':'stewart.c10-settlement/1',
            'reserved_cents':2,'cents':1})
        command=strict_json(read_file(queue/'claims/reconciled/command.json'))
        self.assertEqual((command['placement_charge'],command['argv'][4:6]),(1,['continue','live']))
        # The claimed request is never dispatched again, and both slots stay charged.
        self.assertEqual(serve(),(0,0))
        write_json(queue/'requests/third.json',{**self.continuation(),'record':str(self.root/'.scratch/later-02')})
        self.assertEqual(serve(),(1,0))
        self.assertIn('ceiling',strict_json(read_file(queue/'results/third.json'))['reason'])

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
        self.assertEqual(host_queue.dispatch(self.root, 'attempt', b'{}', argv, 1, 'config', 100), 7)
        claim = self.root / 'claims/attempt'
        self.assertEqual(read_file(claim / 'stdout'), b'fake output\n')
        self.assertEqual(read_file(claim / 'stderr'), b'fake error\n')
        self.assertFalse(host_queue.reconciled(claim))
        with self.assertRaises(FileExistsError):
            host_queue.dispatch(self.root, 'attempt', b'{}', argv, 1, 'config', 100)
        self.assertEqual(strict_json(read_file(claim / 'result.json'))['exit'], 7)

    def test_interruption_keeps_claim_and_needs_attributed_evidence(self):
        (self.root / 'claims').mkdir()
        with mock.patch.object(host_queue.subprocess, 'run', side_effect=OSError('lost caller')):
            with self.assertRaises(OSError):
                host_queue.dispatch(self.root, 'attempt', b'{}', ['fake'], 1, 'config', 100)
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
        write_json(queue / 'claims/previous/command.json', {'placement_charge': 1,'reserved_cents':100})
        write_json(queue / 'claims/previous/result.json', {'exit': 0})
        (queue / 'claims/earlier').mkdir()
        write_json(queue / 'claims/earlier/command.json', {'placement_charge': 1,'reserved_cents':100})
        write_json(queue / 'claims/earlier/result.json', {'exit': 0})
        write_json(queue / 'requests/next.json', self.request)
        config = self.root / 'config.json'; write_json(config, self.config)
        with mock.patch.object(host_queue.subprocess, 'check_output', return_value=b''), \
             mock.patch.object(host_queue, 'source_hash', return_value='source'), \
             mock.patch.object(host_queue, 'dispatch') as dispatch:
            self.assertEqual(host_queue.serve(queue, config, True, once=True),1)
            self.assertIn('ceiling',strict_json(read_file(queue/'results/next.json'))['reason'])
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

    def test_packet_input_is_snapshotted_and_stays_below_inbox(self):
        session=self.root/'session';session.mkdir()
        snapshot=host_queue.snapshot_packet(self.request,self.root/'queue',session,'accepted')
        original=read_file(Path(snapshot['packet']))
        self.path.write_bytes(b'changed after admission')
        self.assertEqual(read_file(Path(snapshot['packet'])),original)
        private=self.root/'private.json';private.write_text('private bytes')
        self.path.unlink();self.path.symlink_to(private)
        for path in [private,self.path]:
            with self.subTest(path=path), self.assertRaises((ValueError,OSError)):
                host_queue.snapshot_packet({**self.request,'packet':str(path)},self.root/'queue',session,'refused')

    def test_budget_gate_withholds_dispatch_for_one_cent_over_and_unknown_cost(self):
        # The recorded price and full attempt bounds are operator inputs.
        unit=host_queue.reservation(self.config,1,self.packet)
        self.assertEqual(unit,2)
        for name,headroom,prior in [('within',unit,None),('over',unit-1,None),('after',2*unit-1,unit),('unknown',5000,None)]:
            with self.subTest(name=name):
                queue=self.root/name
                for directory in ['requests','packets','claims']:
                    (queue/directory).mkdir(parents=True)
                path=queue/'packets/approved.json';path.write_bytes(read_file(self.path))
                write_json(queue/'requests/case.json',{**self.request,'packet':str(path),'evidence':str(self.root/'.scratch'/name)})
                if prior or name=='unknown':
                    claim=queue/'claims/earlier';claim.mkdir()
                    write_json(claim/'result.json',{'exit':0})
                    if prior:
                        write_json(claim/'command.json',{'placement_charge':1,'reserved_cents':prior})
                config=self.root/(name+'.json')
                write_json(config,self.grant({**self.config,'budget_usd':headroom/100,'placement_ceiling':10}))
                with mock.patch.object(host_queue.subprocess,'check_output',return_value=b''), \
                        mock.patch.object(host_queue,'source_hash',return_value='source'), \
                        mock.patch.object(host_queue.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as invoked:
                    code=host_queue.serve(queue,config,True,once=True)
                self.assertEqual((code,invoked.call_count),(0,1) if name=='within' else (1,0))
                self.assertEqual((queue/'claims/case').exists(),name=='within')

    def test_caller_cannot_expand_limits_or_choose_uncommissioned_input_or_effort(self):
        for key,value in [('limits',{**self.packet['limits'],'turns':13}),('effort','high')]:
            with self.subTest(key=key):
                original=self.packet[key];self.packet[key]=value;self.save_packet()
                with self.assertRaises(ValueError):
                    host_queue.command(self.request,self.config,True)
                self.packet[key]=original
        self.save_packet()
        envelope={**self.config['envelope'],'cases':[]}
        with self.assertRaisesRegex(ValueError,'case outside commission'):
            host_queue.command(self.request,{**self.config,'envelope':envelope},True)

    def test_published_archives_are_digest_verified_and_withheld_snapshots_stay_private(self):
        results=self.root/'published';results.mkdir()
        evidence=self.root/'.scratch/campaign'
        audit=evidence/'container/case-a'
        clean=audit/'export-0001';clean.mkdir(parents=True)
        data=b'only the credential-scanned export'
        expected={'sha256':digest(data),'bytes':len(data)}
        receipt={'schema':'stewart.c10-export/2','outcome':'exported','evidence_state':'complete',
                 'scan':{'files_with_matches':[],'errors':[]},'archive':expected}
        write_json(clean/'EXPORT.json',receipt)
        (clean/'work.tar').write_bytes(data)
        withheld=audit/'export-0002';withheld.mkdir()
        write_json(withheld/'EXPORT.json',{'outcome':'withheld'})
        (withheld/'work.tar').write_bytes(b'private original must stay private')
        published=host_queue.publish_exports(results,evidence,['case-a'])
        self.assertEqual(len(published),1)
        archive=results/published[0]['file']
        self.assertEqual((archive.read_bytes(),archive.stat().st_mode & 0o777),(data,0o640))
        self.assertEqual(list(results.iterdir()),[archive])
        self.assertEqual(host_queue.publish_exports(results,evidence,['case-a']),published)
        altered=audit/'export-0003';altered.mkdir()
        write_json(altered/'EXPORT.json',{**receipt,'archive':{'sha256':'0'*64,'bytes':len(data)}})
        (altered/'work.tar').write_bytes(data)
        with self.assertRaisesRegex(ValueError,'differs from its receipt'):
            host_queue.publish_exports(results,evidence,['case-a'])
        self.assertEqual(list(results.iterdir()),[archive])

    def test_documented_synthetic_rehearsal_reserves_fake_placements_against_the_same_envelope(self):
        document=(HERE/'HOST-QUEUE.md').read_text()
        config=host_queue.configuration(json.loads(document.split('```json',1)[1].split('```',1)[0]),False)
        request={'operation':'rehearse','evidence':str(self.root/'.scratch/queue-boundary'),'submissions':[]}
        argv,slots=host_queue.command(request,config,False)
        self.assertIn('rehearse',argv)
        self.assertEqual(slots,35)
        self.assertEqual(host_queue.reservation(config,slots),host_queue.cents(config['budget_usd']))
        self.assertEqual(config['placement_ceiling'],2*slots)

    def test_second_runner_cannot_claim_while_first_holds_lock(self):
        queue = self.root / 'queue'
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
        self.assertEqual(host_queue.charges(damaged,self.config), (2,5000))
        write_json(queue / 'requests/offline.json', {'operation': 'rehearse',
            'evidence': str(self.root / '.scratch/offline'), 'submissions': []})
        config = self.root / 'config.json'; write_json(config, self.config)
        with mock.patch.object(host_queue.subprocess, 'check_output', return_value=b''), \
             mock.patch.object(host_queue, 'source_hash', return_value='source'), \
             mock.patch.object(host_queue.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(host_queue.serve(queue, config, False, once=True), 0)


# A stand-in for Podman, limited to what the continuation launcher
# sends. `/work` is a temporary directory and `/out` the retained folder's
# `container/`. The launcher's own delivery scripts run unchanged against that
# directory; the placement process follows a per-audit plan set by each test.
FAKE_CONTAINER = '''import hashlib, json, os, pathlib, shutil, subprocess, sys, time
root = pathlib.Path(__file__).parent
state = json.loads((root/'container.json').read_text())
argv = sys.argv[1:]
assert 'ANTHROPIC_API_KEY' not in os.environ
with (root/'container-calls.jsonl').open('a') as stream:
    stream.write(json.dumps(argv)+'\\n')
if argv == ['--version']:
    print('podman version 5.4.2')
    sys.exit(0)
if argv[0] == 'info':
    print('true'); sys.exit(0)
if argv[0] == 'inspect':
    print('{}')
    sys.exit(0)
assert argv[0] == 'exec', argv
rest = argv[2:] if argv[1] == '--interactive' else argv[1:]
assert rest[0] == state['name'], rest[0]
command = rest[1:]
def local(path):
    assert path.startswith('/work/'), path
    return state['work'] + path[len('/work'):]
if command[0] == 'sh':
    sys.exit(0 if os.path.isdir(local(command[2].split()[-1])) else 1)
assert command[:3] == ['env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin'], command
command = [item for item in command[3:] if item != 'HOME=/work']
assert command[:3] == ['python3', '-I', '-B'], command
if command[3] == '-c':
    if 'socket' in command[4]:
        print('TCP connection established; no credential or API request sent')
        sys.exit(0)
    sys.exit(subprocess.run([sys.executable, '-I', '-B', '-c', command[4], local(command[5]), *command[6:]]).returncode)
script = pathlib.Path(local(command[3]))
assert script.is_file(), 'the delivered code directory lacks ' + command[3]
if script.name == 'operations.py':
    if command[5] == 'collect':
        (root/'operations-stdin.sha256').write_text(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())
    print(json.dumps({'audit': command[4], 'operation': command[5]}))
    sys.exit(0)
assert script.name == 'placements.py' and command[4] in ['rehearse', 'live'], command
assert command[5:8] == ['--binary', '/bin-in/stewart', '--packet'], command
packet = json.loads(pathlib.Path(local(command[8])).read_text())
audit, placement = packet['audit'], packet['placement']
base = pathlib.Path(state['out'])/'continuations'/f'{audit}-p{placement}'
base.mkdir(parents=True, exist_ok=True)
attempt = max([int(path.name.split('-')[1]) for path in base.iterdir()], default=0) + 1
plan = state['placements'][audit]
plan = plan[attempt-1] if isinstance(plan, list) else plan
folder = base/f'attempt-{attempt}'
folder.mkdir()
def refuse(stage):
    # What the container half records when it stops before spawning the service.
    detail = {'phase': stage, 'error_type': 'ValueError'}
    (folder/'RESULT.json').write_text(json.dumps({'schema': 'stewart.c10-continuation-session/1', 'mode': command[4],
        'audit': audit, 'placement': placement, 'placement_state': 'not_started', 'failed': True, 'failure': detail}))
    (folder/'FAILURE.json').write_text(json.dumps(detail))
    sys.exit(1)
if plan['ready'] is None:
    time.sleep(plan.get('sleep', 0))
    if plan.get('refuses'):
        refuse(plan['refuses'])
    sys.exit(plan['exit'])
(folder/'READY.json').write_text(json.dumps({'attempt': attempt, **plan['ready']}))
key = sys.stdin.buffer.read()
with (root/'placement-stdin.jsonl').open('a') as stream:
    stream.write(json.dumps({'audit': audit, 'mode': command[4], 'attempt': attempt, 'bytes': len(key),
                             'sha256': hashlib.sha256(key).hexdigest()})+'\\n')
if hashlib.sha256(key).hexdigest() != state['key_sha256']:
    refuse('credential.differs' if key else 'credential.read')
with (root/'starts.jsonl').open('a') as stream:
    stream.write(json.dumps({'audit': audit, 'placement': placement, 'attempt': attempt})+'\\n')
if plan.get('leak'):
    (folder/'leak').write_bytes(b'reflected ' + key)
if plan.get('failure'):
    (folder/'FAILURE.json').write_text(json.dumps({'phase': 'placement', 'error_type': 'RuntimeError'}))
if plan.get('export'):
    target = pathlib.Path(state['out'])/audit/plan['export']
    target.mkdir()
    shutil.copyfile(root/'exports'/(audit+'.tar'), target/'work.tar')
if plan.get('result') is not None:
    (folder/'RESULT.json').write_text(json.dumps(plan['result']))
sys.exit(plan['exit'])
'''


class ContinuationTests(unittest.TestCase):
    """Host checks for one later placement of a retained audit; no container, model or keyring."""
    container='stewart-c10-1700000000-4242'
    bound={'qualification_id':'fixture-qualification','binary_sha256':'1'*64,'source_commit':'2'*40,
           'apparatus_sha256':'3'*64,'image':'docker.io/library/python@sha256:'+'4'*64,'catalog_sha256':'5'*64}
    # One placement's run_ended usage in the fixture log, and the sums a limit counts.
    charge={'turns':{'reported':2,'estimated':1},'input_tokens':{'reported':100,'estimated':10},
            'output_tokens':{'reported':50,'estimated':5}}
    used={'turns':3,'input_tokens':110,'output_tokens':55}

    @staticmethod
    def reference_for(audit):
        return 'stw1:'+'a'*17+':'+'b'*17+':/work/c10-private/'+audit+'/archive'

    @classmethod
    def setUpClass(cls):
        cls.shared=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.shared.cleanup)
        cls.repo=Path(cls.shared.name)/'repo'
        for name in common.SOURCE_PATHS:
            path=cls.repo/name
            if path.suffix:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('# fixture '+name+'\n')
            else:
                path.mkdir(parents=True)
        for name in ['placements','operations']:
            (cls.repo/'apparatus/c10'/(name+'.py')).write_text('# fixture stand-in; the fake container never runs it\n')
        (cls.repo/'apparatus/sanity/session.py').write_text('# fixture\n')
        def git(*argv):
            subprocess.run(['git','-c','user.name=fixture','-c','user.email=fixture@example.invalid',
                            '-c','commit.gpgsign=false',*argv],cwd=cls.repo,check=True,capture_output=True)
        git('init','-q')
        git('add','.')
        git('commit','-q','-m','fixture')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.scratch=self.repo/'.scratch';self.scratch.mkdir()
        self.addCleanup(shutil.rmtree,self.scratch)
        self.addCleanup(os.umask,os.umask(0o077))
        self.bin=self.root/'bin';(self.bin/'exports').mkdir(parents=True)
        self.work=self.root/'container/work'
        self.key='c10-NONFUNCTIONAL-'+os.urandom(12).hex()
        (self.bin/'response.json').write_text(json.dumps({'exit':0,'stdout':self.key+'\n','stderr':'','sleep':0}))
        for name,body in [('keyctl',FAKE_KEYCTL),('podman',FAKE_CONTAINER)]:
            (self.bin/name).write_text('#!'+sys.executable+'\n'+body);(self.bin/name).chmod(0o700)
        for target,values in [(os.environ,{'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH',''),
                                           'ANTHROPIC_API_KEY':'never-read-this-ambient-key'})]:
            patch=mock.patch.dict(target,values);patch.start();self.addCleanup(patch.stop)
        self.reviews={}
        self.audits=[]
        self.bind=subprocess.CompletedProcess([],0,b'qualification record checked\n',b'')
        for name,value in [('REPO',self.repo),('review_batch',mock.Mock(side_effect=self.review)),
                           ('bindings',mock.Mock(side_effect=lambda *a,**k:(dict(self.bound),Path('/unused'),self.bind,self.bound['image'])))]:
            patch=mock.patch.object(c10,name,value);patch.start();self.addCleanup(patch.stop)
        self.evidence=self.scratch/'earlier-01'
        self.plans={}

    # --- fixture construction

    def log_archive(self,path,audit,endings):
        """An export holding one audit's operator binding and a chained log; returns the log head."""
        members=[('private/operator.json',json.dumps({'audit':audit,'reference':self.reference_for(audit)}).encode()),
                 ('private/evidence/process-observation-index.json',b'{"controls_fired":2,"inspection_denied":true}')]
        previous,count=None,0
        def record(kind,**body):
            nonlocal previous,count
            count+=1
            raw=(json.dumps({'record':'stewart.record/1','audit':'fixture','kind':kind,
                             'body':{'prev':previous,**body}})+'\n').encode()
            members.append((f'private/archive/audits/fixture/log/{count}.json',raw))
            previous=hashlib.sha256(raw).hexdigest()
        record('accepted')
        for number,ending in enumerate(endings,1):
            record('run_started',run=number,continuing=number>1)
            if ending is not None:
                record('run_ended',run=number,ending=ending[0],cause=ending[1],usage=self.charge)
        with tarfile.open(path,'w') as archive:
            for name,data in members:
                member=tarfile.TarInfo(name);member.size=len(data)
                archive.addfile(member,io.BytesIO(data))
        return previous

    def export(self,audit,endings,name='export-0001',withheld=False):
        folder=self.evidence/'container'/audit/name
        folder.mkdir(parents=True)
        if withheld:
            self.reviews[audit,name]=None
            return None
        head=self.log_archive(folder/'work.tar',audit,endings)
        write_json(folder/'EXPORT.json',{'outcome':'exported','archive':{'sha256':common.file_hash(folder/'work.tar')}})
        self.expect_review(audit,name,endings)
        return head

    def expect_review(self,audit,name,endings):
        sealed=endings[-1] is not None and endings[-1][0]=='sealed'
        self.reviews[audit,name]={'outcome':'checked','ending':None if endings[-1] is None else endings[-1][0],
                                  'auditor_submitted':sealed,'delivery_verified':sealed}

        scenario=audit.removeprefix('control-')
        if scenario in common.TRIAL_CONTROLS:
            point,action=common.TRIAL_CONTROLS[scenario]
            outcome='unexercised' if scenario=='p2-missed' else 'pass'
            self.reviews[audit,name].update(placements=[{'interruption':{'point':point,'outcome':outcome}}],
                trial={'outcome':'pass' if action=='close' or len(endings)>1 else outcome})

    def review(self,folder):
        """What the reviewer reports for the fixture's exports; the archives themselves are read for real."""
        rows=[]
        for audit in self.audits:
            base=Path(folder)/'container'/audit
            snapshots=[]
            for path in sorted(base.glob('export-*')) if base.is_dir() else []:
                review=self.reviews[audit,path.name]
                snapshots.append({'snapshot':path.name,'export':'withheld','review':None} if review is None else
                    {'snapshot':path.name,'export':'exported','review':review,
                     'archive':{'sha256':common.file_hash(path/'work.tar'),'bytes':(path/'work.tar').stat().st_size}})
            rows.append({'audit':audit,'case':'open-ordinary','snapshots':snapshots})
        return {'audits':rows}

    def retain(self,mode='rehearse',exports=(('control-continue-cap',[['interrupted','max_tokens']]),),**changes):
        """The records an original launch leaves, with each named audit's first export."""
        for name in ['host','staging','container']:
            (self.evidence/name).mkdir(parents=True)
        if mode=='rehearse':
            packet=rehearsal_packet()
            packet['account']={'account_label':'synthetic connection rehearsal','workspace_id':'offline',
                               'credential_label':'synthetic'}
        else:
            packet=proposal('example-model',['open-ordinary'])
            packet['account']={key:'approved' for key in packet['account']}
            packet['spending_authority']='Fixture only; no provider call.'
        packet['bindings']=dict(self.bound)
        packet.update(changes)
        self.mode,self.original=mode,packet
        self.audits=[run['id'] for run in packet['runs']]
        raw=json.dumps(packet).encode()
        (self.evidence/'staging/commission.json').write_bytes(raw)
        write_json(self.evidence/'host/operator.json',{'schema':'stewart.c10-operator/1','container':self.container,'audits':self.audits})
        write_json(self.evidence/'host/RESULT.json',{'schema':'stewart.c10-launch/3','mode':mode,
            'outcome':'completed' if mode=='rehearse' else 'observed','bindings':dict(self.bound),
            'container':self.container,'platform_image':self.bound['image'],'commission_sha256':digest(raw)})
        self.heads={audit:self.export(audit,endings) for audit,endings in exports}
        self.first=exports[0][0]
        for audit,_ in exports:
            (self.work/'c10-private'/audit).mkdir(parents=True)
            self.plans[audit]=self.plan(audit)
        (self.work/'code/apparatus/c10').mkdir(parents=True)
        (self.work/'code/apparatus/c10/operations.py').write_text('# launch-time source, without continuation support\n')
        self.configure()

    def plan(self,audit,placement=2,**changes):
        result={'schema':'stewart.c10-continuation-session/1','mode':self.mode,'audit':audit,'placement':placement,
            'placement_state':'observed','failed':False,
            'outcome':'passed' if self.mode=='rehearse' else 'observed'}
        if self.mode=='rehearse':
            scenario=audit[len('control-'):]
            final=placement==len(CONTINUED_CONTROLS[scenario][1])
            result.update(expected_observation=True,second_start=dict(SECOND_START_REFUSED),
                          controls=control_counts(scenario) if final else None)
        return {'ready':{'continuation_preflight_verified':True,'audit':audit,'placement':placement},
                'exit':0,'result':result,**changes}

    def configure(self):
        (self.bin/'container.json').write_text(json.dumps({'name':self.container,'work':str(self.work),
            'out':str(self.evidence/'container'),'placements':self.plans,'key_sha256':digest(self.key.encode())}))

    def packet(self,of=None,name='packet.json',**changes):
        """A bound, paid packet for an audit's next placement, with the named members changed."""
        study=strict_json(read_file(self.evidence/'staging/commission.json'))['schema']=='stewart.interruption-commission/3'
        value=c10.continuation_proposal(self.evidence,of or self.first,
                                        max_placements=None if study else common.MAX_PLACEMENTS)
        value.update(max_placements=2,spending_authority=self.original['spending_authority'],
                     account=self.original['account'],bindings=dict(self.bound))
        for key,item in changes.items():
            if isinstance(item,dict) and isinstance(value[key],dict):
                value[key]={**value[key],**item}
            else:
                value[key]=item
        path=self.root/name
        path.write_text(json.dumps(value,indent=2))
        return path

    def args(self,packet,record='later-01',**changes):
        values={'mode':self.mode,'evidence':self.evidence,'record':self.scratch/record,'packet':packet,
                'approved_packet':digest(read_file(packet)) if self.mode=='live' else None,
                'rehearsal':self.scratch/'rehearsal-01' if self.mode=='live' else None,
                'qualification':'fixture-qualification','connection':None}
        return argparse.Namespace(**{**values,**changes})

    def run_continuation(self,args,**options):
        """Return (failed, host record) for a launch that got as far as its record folder."""
        if args.mode=='rehearse' and args.connection is None:
            options.setdefault('synthetic_key',self.key.encode())
        with redirect_stdout(io.StringIO()):
            failed=c10.continue_placement(args,**options)
        return failed,strict_json(read_file(args.record/'host/RESULT.json'))

    def published(self,audit,attempt=1,placement=2):
        """Where the container publishes one attempt, seen from the host."""
        return self.evidence/'container/continuations'/f'{audit}-p{placement}'/f'attempt-{attempt}'

    def supply(self,key=None,exit=0,stderr=''):
        """What the fake keyring returns for the next lookup."""
        (self.bin/'response.json').write_text(json.dumps({'exit':exit,'stdout':(key or self.key)+'\n','stderr':stderr,'sleep':0}))

    def calls(self,name='container-calls.jsonl'):
        path=self.bin/name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def assert_refused_untouched(self,reason,args,**options):
        """A refusal for its stated reason, before any record, container command or credential use."""
        logs=['container-calls.jsonl','calls.jsonl','placement-stdin.jsonl','starts.jsonl']
        before=[self.calls(name) for name in logs]
        with self.assertRaisesRegex(c10.Refused,reason):
            self.run_continuation(args,**options)
        self.assertFalse(args.record.exists())
        self.assertEqual([self.calls(name) for name in logs],before)

    def tree(self,root):
        return {path.relative_to(root).as_posix():path.read_bytes() for path in sorted(root.rglob('*')) if path.is_file()}

    # --- the placement itself

    def test_rehearsed_continuation_records_every_step_and_changes_nothing_already_there(self):
        self.retain()
        before={name:self.tree(self.evidence/name) for name in ['host','staging']}
        exports_before=self.tree(self.evidence/'container/control-continue-cap')
        launch_time=self.tree(self.work/'code')
        packet=self.packet()
        failed,report=self.run_continuation(self.args(packet))
        self.assertFalse(failed)
        self.assertEqual((report['schema'],report['mode'],report['outcome'],report['credential_sent'],report['container_exit']),
                         ('stewart.c10-continuation-launch/2','rehearse','completed',True,0))
        record=self.scratch/'later-01'
        # The host wrote only to its new record folder; the earlier folder gained what the container published.
        self.assertEqual({name:self.tree(self.evidence/name) for name in ['host','staging']},before)
        self.assertEqual(self.tree(self.evidence/'container/control-continue-cap'),exports_before)
        published=self.published('control-continue-cap')
        self.assertEqual((report['attempt'],strict_json(read_file(published/'READY.json'))['attempt']),(1,1))
        self.assertEqual(report['session'],{'path':str(published/'RESULT.json'),
                                            'sha256':digest(read_file(published/'RESULT.json'))})
        self.assertEqual(report['retained_launch']['sha256'],digest(read_file(self.evidence/'host/RESULT.json')))
        self.assertEqual(report['prior_observed']['log_head_sha256'],self.heads['control-continue-cap'])
        # Source: the committed archive, extracted beside the launch-time code, which stays as it was.
        archive=read_file(record/'staging/source.tar')
        code=self.work/('code-'+digest(archive)[:12])
        self.assertEqual(report['code'],{'directory':'/work/'+code.name,'source_archive_sha256':digest(archive),'created':True})
        with tarfile.open(record/'staging/source.tar') as source:
            expected={member.name:source.extractfile(member).read() for member in source if member.isfile()}
        self.assertEqual(self.tree(code),{**expected,'.ready':b''})
        self.assertIn('apparatus/c10/placements.py',expected)
        self.assertEqual(self.tree(self.work/'code'),launch_time)
        # Packet: exact bytes, in a directory this record folder alone owns.
        self.assertEqual(read_file(self.work/'continuation-packets/later-01/commission.json'),read_file(packet))
        self.assertEqual(read_file(record/'staging/commission.json'),read_file(packet))
        self.assertEqual(report['commission_sha256'],digest(read_file(packet)))
        # Every command has argv, both streams and an exit; the rehearsal makes no network preflight.
        for label in ['version','rootless','container-ready','source','source-delivery','packet-delivery','container-inspect']:
            for suffix in ['.argv.json','.stdout','.stderr','.exit']:
                self.assertTrue((record/'host'/(label+suffix)).is_file(),label+suffix)
            self.assertEqual(read_file(record/'host'/(label+'.exit')),b'0\n')
        self.assertFalse((record/'host/network-preflight.exit').exists())
        placement=strict_json(read_file(record/'host/placement.argv.json'))
        self.assertEqual(placement,['podman','exec','--interactive',self.container,'env','-i',
            'PATH=/usr/local/bin:/usr/bin:/bin','HOME=/work','python3','-I','-B',
            '/work/'+code.name+'/apparatus/c10/placements.py','rehearse','--binary','/bin-in/stewart',
            '--packet','/work/continuation-packets/later-01/commission.json'])
        # The key travelled only on the placement's standard input.
        self.assertEqual(self.calls('placement-stdin.jsonl'),[{'audit':'control-continue-cap','mode':'rehearse',
            'attempt':1,'bytes':len(self.key),'sha256':digest(self.key.encode())}])
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':'control-continue-cap','placement':2,'attempt':1}])
        self.assertNotIn(self.key,json.dumps(self.calls()))
        for root in [record,self.evidence]:
            self.assertTrue(all(self.key.encode() not in data for data in self.tree(root).values()))
        self.assertEqual({name:(scan['files_with_matches'],scan['errors']) for name,scan in report['host_scan'].items()},
                         {'record':(0,0),'evidence':(0,0)})
        operator=strict_json(read_file(record/'host/operator.json'))
        self.assertEqual((operator['container'],operator['audits'],operator['code'],operator['evidence'],operator['attempt']),
                         (self.container,['control-continue-cap'],'/work/'+code.name,str(self.evidence),1))

    def test_live_continuation_needs_exact_digest_rehearsal_and_tcp_preflight(self):
        self.retain('live',exports=(('open-ordinary-r1',[['interrupted','max_tokens']]),))
        packet=self.packet()
        common.validate_continuation(strict_json(read_file(packet)),approved=True)
        self.assert_refused_untouched('packet differs from the approved digest',self.args(packet,approved_packet='0'*64))
        c10.bindings.assert_not_called()
        self.assert_refused_untouched('needs --approved-packet and a retained --rehearsal',self.args(packet,rehearsal=None))
        # The retained rehearsal named here does not exist; the gate is reached only after every packet check.
        self.assert_refused_untouched('retained rehearsal refused',self.args(packet))
        c10.bindings.assert_called_once()
        with mock.patch.object(c10,'check_rehearsal') as rehearsal:
            failed,report=self.run_continuation(self.args(packet))
        rehearsal.assert_called_once_with(self.scratch/'rehearsal-01',self.bound,self.original,connection=True)
        self.assertFalse(failed)
        self.assertEqual((report['outcome'],report['credential_source']),('observed',connections.source('approved')))
        self.assertEqual(read_file(self.scratch/'later-01/host/network-preflight.exit'),b'0\n')
        self.assertEqual(self.calls('placement-stdin.jsonl')[0]['sha256'],digest(self.key.encode()))
        self.assertEqual([args[0] for args in self.calls('calls.jsonl')],['get_persistent','search','pipe'])

    def test_saved_connection_is_looked_up_only_after_the_preflight_record(self):
        self.retain()
        failed,report=self.run_continuation(self.args(self.packet(),connection='synthetic'))
        self.assertFalse(failed)
        self.assertEqual(report['credential_source'],connections.source('synthetic'))
        self.assertEqual(self.calls('calls.jsonl'),[['get_persistent','@s'], ['search','111','user','stewart-provider:synthetic'], ['pipe','222']])
        self.assertEqual(self.calls('placement-stdin.jsonl')[0]['sha256'],digest(self.key.encode()))
        self.assertNotIn(self.key.encode(),read_file(self.scratch/'later-01/host/connection.json'))
        with self.assertRaises(connections.ConnectionError):
            self.run_continuation(self.args(self.packet('control-continue-cap','other.json'),'later-02',connection='different'))
        self.assertFalse((self.scratch/'later-02').exists())
        # Without a connection, only the rehearsal itself can supply its generated key.
        with self.assertRaisesRegex(c10.Refused,"needs its rehearsal's own synthetic credential"),redirect_stdout(io.StringIO()):
            c10.continue_placement(self.args(self.packet('control-continue-cap','third.json'),'later-03'))

    # --- refusals before the container or a credential

    def test_packet_for_another_evidence_container_audit_reference_or_writer_refuses(self):
        self.retain(exports=(('control-continue-cap',[['interrupted','max_tokens']]),
                             ('control-continue-entries',[['interrupted','max_tokens']])))
        other=self.scratch/'another-01';other.mkdir()
        for reason,changes in [
                ('packet names another evidence folder',{'evidence':str(other)}),
                ('packet names another container',{'container':'stewart-c10-9-9'}),
                ('packet names an audit this launch did not retain',{'audit':'somebody-else'}),
                ('packet names another audit reference',{'audit':'control-continue-entries'}),
                ('packet names another audit reference',
                 {'reference':self.reference_for('control-continue-cap').replace('a'*17,'c'*17)}),
                ('packet bindings differ from the committed apparatus',{'bindings':{'binary_sha256':'9'*64}}),
                ('packet bindings differ from the committed apparatus',{'bindings':{'apparatus_sha256':'9'*64}}),
                ('model or cumulative limits differ',{'limits':{'turns':13}})]:
            with self.subTest(changes=changes):
                self.assert_refused_untouched(reason,self.args(self.packet('control-continue-cap',**changes)))
        # The same writer the packet and qualification name must be the one the audit was launched with.
        launch=strict_json(read_file(self.evidence/'host/RESULT.json'))
        (self.evidence/'host/RESULT.json').unlink()
        write_json(self.evidence/'host/RESULT.json',{**launch,'bindings':{**launch['bindings'],'binary_sha256':'8'*64}})
        self.assert_refused_untouched('the qualified writer or image differs from the retained launch',
                                      self.args(self.packet('control-continue-cap')))
        (self.evidence/'host/RESULT.json').unlink()
        write_json(self.evidence/'host/RESULT.json',launch)
        failed,report=self.run_continuation(self.args(self.packet('control-continue-cap')))
        self.assertEqual((failed,report['audit'],report['reference']),
                         (False,'control-continue-cap',self.reference_for('control-continue-cap')))

    def test_rehearsal_packet_cannot_continue_a_live_audit(self):
        self.retain('live',exports=(('open-ordinary-r1',[['interrupted','max_tokens']]),))
        packet=self.packet()
        self.assert_refused_untouched('continuation packet is not valid: model does not match launch mode',
                                      self.args(packet,mode='rehearse',approved_packet=None,rehearsal=None))

    def test_placement_beyond_its_ceiling_refuses(self):
        self.retain(exports=(('control-continue-cap',[['interrupted','max_tokens'],['interrupted','signal']]),))
        # Two placements are recorded; the next would be the third.
        self.assertEqual(strict_json(read_file(self.packet()))['placement'],3)
        self.assert_refused_untouched('continuation packet is not valid: placement outside the commissioned ceiling',
                                      self.args(self.packet()))
        self.assert_refused_untouched('continuation packet is not valid: placement outside the commissioned ceiling',
            self.args(self.packet(placement=5,max_placements=5,prior={'runs':4})))
        # A packet cannot raise the ceiling an interrupted study was commissioned with.
        raw=read_file(self.evidence/'staging/commission.json')
        commissioned={**strict_json(raw),'schema':'stewart.interruption-commission/3','max_placements':3,
                      'interruption':{'after':'reminder_notice','action':'signal'}}
        changed=json.dumps(commissioned).encode()
        (self.evidence/'staging/commission.json').write_bytes(changed)
        launch=strict_json(read_file(self.evidence/'host/RESULT.json'))
        (self.evidence/'host/RESULT.json').unlink()
        write_json(self.evidence/'host/RESULT.json',{**launch,'commission_sha256':digest(changed)})
        raised=self.packet(max_placements=4)
        self.assert_refused_untouched('placement ceiling differs from the one commissioned for this audit',self.args(raised))
        self.plans['control-continue-cap']=self.plan('control-continue-cap',3);self.configure()
        within=self.packet(name='within.json',max_placements=3)
        failed,report=self.run_continuation(self.args(within))
        self.assertEqual((failed,report['placement']),(False,3))

    def test_prior_state_mismatch_refuses_before_credential_or_container(self):
        self.retain(exports=(('control-continue-cap',[['interrupted','max_tokens']]),))
        for reason,changes in [
                ('prior placement count or ending differs from the latest export',{'prior':{'last_cause':'signal'}}),
                ('prior placement count or ending differs from the latest export',
                 {'placement':3,'max_placements':3,'prior':{'runs':2}}),
                ('prior log head differs from the latest export',{'prior':{'log_head_sha256':'0'*64}}),
                ('prior usage differs from the latest export',{'prior':{'usage':{**self.used,'output_tokens':54}}})]:
            with self.subTest(changes=changes):
                self.assert_refused_untouched(reason,self.args(self.packet(**changes),connection='synthetic'))
        # A later collection that was withheld leaves no current observation to bind to.
        packet=self.packet()
        self.export('control-continue-cap',None,'export-0002',withheld=True)
        self.assert_refused_untouched('latest export of this audit is not a checked observation',
                                      self.args(packet,connection='synthetic'))
        shutil.rmtree(self.evidence/'container/control-continue-cap/export-0002')
        # A packet approved before the state was known binds nothing; the launcher records what it found.
        unknown=self.packet(name='unknown.json',prior={'log_head_sha256':None,'usage':None})
        failed,report=self.run_continuation(self.args(unknown,connection='synthetic'))
        self.assertFalse(failed)
        self.assertEqual({key:report['prior_observed'][key] for key in ['runs','last_ending','last_cause','log_head_sha256','usage','snapshot']},
            {'runs':1,'last_ending':'interrupted','last_cause':'max_tokens','usage':self.used,
             'log_head_sha256':self.heads['control-continue-cap'],'snapshot':'export-0001'})

    def test_repeated_placement_and_reused_record_folder_refuse(self):
        self.retain()
        packet=self.packet()
        self.assertFalse(self.run_continuation(self.args(packet))[0])
        with self.assertRaisesRegex(c10.Refused,'the record folder already exists'):
            self.run_continuation(self.args(packet))
        # The first attempt was observed: the placement started, so no new record folder reopens it.
        before=self.calls()
        with self.assertRaisesRegex(c10.Refused,'an earlier attempt of this placement started or may have started'):
            self.run_continuation(self.args(packet,'later-02'))
        self.assertFalse((self.scratch/'later-02').exists())
        self.assertEqual(self.calls(),before)
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':'control-continue-cap','placement':2,'attempt':1}])

    def test_host_applies_the_shared_admission_rule_before_any_container_or_credential_use(self):
        # The admission table itself is test_placements.AttemptAdmissionTests (common.settled_attempts).
        self.retain()
        packet=self.packet()
        earlier=self.published(self.first)
        earlier.mkdir(parents=True)
        result={'schema':'stewart.c10-continuation-session/1','mode':'rehearse','audit':self.first,'placement':2,
                'placement_state':'not_started','failed':True}
        (earlier/'RESULT.json').write_text(json.dumps({**result,'placement_state':'unknown'}))
        self.assert_refused_untouched('an earlier attempt of this placement started or may have started',self.args(packet))
        (earlier/'RESULT.json').write_text(json.dumps(result))
        stray=earlier.parent/'READY.json';stray.write_text('{}')
        self.assert_refused_untouched('the placement holds records that are not numbered attempts',self.args(packet))
        stray.unlink()
        # Two attempts that started nothing: the third proceeds, and is the only start.
        second=self.published(self.first,2);second.mkdir()
        (second/'RESULT.json').write_text(json.dumps(result))
        failed,report=self.run_continuation(self.args(packet))
        self.assertEqual((failed,report['outcome'],report['attempt']),(False,'completed',3))
        self.assertEqual(report['session']['path'],str(self.published(self.first,3)/'RESULT.json'))
        self.assertEqual(strict_json(read_file(self.published(self.first,3)/'READY.json'))['attempt'],3)
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':self.first,'placement':2,'attempt':3}])
        self.assertEqual(strict_json(read_file(earlier/'RESULT.json')),result)

    def test_preexisting_credential_in_staged_packet_never_reaches_the_child(self):
        account={'account_label':self.key,'workspace_id':'offline','credential_label':'synthetic'}
        self.retain(account=account)
        failed,report=self.run_continuation(self.args(self.packet(),connection='synthetic'))
        self.assertTrue(failed)
        self.assertFalse(report['credential_sent'])
        self.assertEqual(report['staging_scan']['findings'],[
            {'artifact':'commission','producer':'packet staging','form':'literal','files':1}])
        self.assertEqual(self.calls('starts.jsonl'),[])
        self.assertEqual([row['bytes'] for row in self.calls('placement-stdin.jsonl')],[0])

    def test_wrong_key_starts_nothing_and_the_right_key_proceeds_as_the_next_attempt(self):
        self.retain()
        packet=self.packet()
        self.supply('c10-NONFUNCTIONAL-'+'0'*24)
        failed,report=self.run_continuation(self.args(packet,'later-01',connection='synthetic'))
        self.assertTrue(failed)
        self.assertEqual((report['outcome'],report['attempt'],report['credential_sent'],report['container_exit']),
                         ('not_started',1,True,1))
        self.assertEqual(report['not_started'],{'container_stage':'credential.differs','host_step':'placement-result'})
        self.assertIn('Not started at credential.differs',report['error'])
        self.assertIn('A further attempt is permitted as a new launch with a new record folder',report['error'])
        self.assertNotIn('incomplete',report['error'])
        first=self.published(self.first)
        self.assertEqual(report['session'],{'path':str(first/'RESULT.json'),'sha256':digest(read_file(first/'RESULT.json'))})
        self.assertEqual(report['container_failure']['sha256'],digest(read_file(first/'FAILURE.json')))
        self.assertEqual(self.calls('starts.jsonl'),[])
        # The same packet, a new record folder and the original key: attempt 2, one start in all.
        self.supply()
        failed,report=self.run_continuation(self.args(packet,'later-02',connection='synthetic'))
        self.assertEqual((failed,report['outcome'],report['attempt']),(False,'completed',2))
        self.assertEqual(report['session']['path'],str(self.published(self.first,2)/'RESULT.json'))
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':self.first,'placement':2,'attempt':2}])
        self.assertEqual([(row['attempt'],row['sha256']==digest(self.key.encode())) for row in self.calls('placement-stdin.jsonl')],
                         [(1,False),(2,True)])
        self.assertEqual(len([args for args in self.calls('calls.jsonl') if args[0]=='pipe']),2)
        # Having started, the placement is closed to any further attempt.
        with self.assertRaisesRegex(c10.Refused,'an earlier attempt of this placement started or may have started'):
            self.run_continuation(self.args(packet,'later-03',connection='synthetic'))

    def test_denied_keyring_or_container_refusal_is_not_started_and_may_be_followed(self):
        audits=['control-continue-cap','control-continue-entries']
        self.retain(exports=tuple((audit,[['interrupted','max_tokens']]) for audit in audits))
        # The keyring denies the lookup: nothing is sent, and the container records that it started nothing.
        denied=self.packet(audits[0],'denied.json')
        self.supply(exit=1,stderr='keyctl_read_alloc: Permission denied')
        failed,report=self.run_continuation(self.args(denied,'later-01',connection='synthetic'))
        self.assertTrue(failed)
        self.assertEqual((report['outcome'],report['credential_sent'],report['connection_error'],report['container_exit']),
                         ('not_started',False,'access_denied',1))
        self.assertEqual(report['not_started'],{'container_stage':'credential.read','host_step':'credential-handoff'})
        self.assertEqual([row['bytes'] for row in self.calls('placement-stdin.jsonl')],[0])
        self.supply()
        failed,report=self.run_continuation(self.args(denied,'later-02',connection='synthetic'))
        self.assertEqual((failed,report['attempt'],report['outcome']),(False,2,'completed'))
        # The container's preflight refuses before READY: no lookup at all, then a permitted second attempt.
        refused=self.packet(audits[1],'refused.json')
        self.plans[audits[1]]=[self.plan(audits[1],ready=None,refuses='preflight.prior_usage'),self.plan(audits[1])]
        self.configure()
        lookups=len(self.calls('calls.jsonl'))
        failed,report=self.run_continuation(self.args(refused,'later-03',connection='synthetic'))
        self.assertTrue(failed)
        self.assertEqual((report['outcome'],report['credential_sent'],report['not_started']),
                         ('not_started',False,{'container_stage':'preflight.prior_usage','host_step':'preflight'}))
        self.assertEqual(len(self.calls('calls.jsonl')),lookups)
        failed,report=self.run_continuation(self.args(refused,'later-04',connection='synthetic'))
        self.assertEqual((failed,report['attempt'],report['outcome']),(False,2,'completed'))
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':audit,'placement':2,'attempt':2} for audit in audits])

    def test_incomplete_original_launch_or_unreadable_records_refuse(self):
        self.retain()
        packet=self.packet()
        launch=strict_json(read_file(self.evidence/'host/RESULT.json'))
        for reason,value in [('the original launch record is incomplete',{**launch,'outcome':'failed'}),
                             ('the retained packet differs from its launch record',{**launch,'commission_sha256':'0'*64}),
                             ('the retained container identity is missing or inconsistent',{**launch,'container':'stewart-c10-9-9'}),
                             ('does not hold an original launch record',{**launch,'schema':'stewart.c10-continuation-launch/2'})]:
            (self.evidence/'host/RESULT.json').unlink()
            write_json(self.evidence/'host/RESULT.json',value)
            with self.subTest(reason=reason):
                self.assert_refused_untouched(reason,self.args(packet))
        (self.evidence/'host/RESULT.json').unlink()
        self.assert_refused_untouched('the retained launch records are missing or unreadable',self.args(packet))
        write_json(self.evidence/'host/RESULT.json',launch)
        self.assert_refused_untouched('the new record folder must be an absolute path directly under .scratch',
                                      self.args(packet,record=self.root/'elsewhere'))
        self.assertFalse(self.run_continuation(self.args(packet))[0])

    def test_command_line_refusal_states_its_reason_and_that_nothing_started(self):
        self.retain()
        argv=[sys.executable,'-I','-B',str(HERE/'c10.py'),'continue','rehearse',str(self.evidence),
              str(self.root/'outside-scratch'),'--packet',str(self.packet()),'--qualification','fixture-qualification',
              '--connection','synthetic']
        result=subprocess.run(argv,capture_output=True,stdin=subprocess.DEVNULL)
        self.assertEqual((result.returncode,result.stdout),(1,b''))
        self.assertEqual(result.stderr,b'Refused: the new record folder must be an absolute path directly under .scratch, '
            b'named with lowercase letters, digits and hyphens. Nothing was started in the container and no credential was read.\n')
        self.assertEqual((self.calls(),self.calls('calls.jsonl')),([],[]))

    # --- failures after the container was touched: recorded, never retried

    def test_existing_code_directory_with_different_content_stops_before_the_placement(self):
        audits=['control-continue-cap','control-continue-entries','control-reminder-spent']
        self.retain(exports=tuple((audit,[['interrupted','max_tokens']]) for audit in audits))
        failed,first=self.run_continuation(self.args(self.packet(audits[0],'a.json'),'later-01'))
        self.assertEqual((failed,first['code']['created']),(False,True))
        # The same committed source is already there: accepted as it is, not rewritten.
        code=self.work/first['code']['directory'][len('/work/'):]
        stamp=(code/'apparatus/c10/placements.py').stat().st_mtime_ns
        failed,second=self.run_continuation(self.args(self.packet(audits[1],'b.json'),'later-02'))
        self.assertEqual((failed,second['code']),(False,{**first['code'],'created':False}))
        self.assertEqual((code/'apparatus/c10/placements.py').stat().st_mtime_ns,stamp)
        original=self.tree(code)
        for change in ['changed','extra','missing']:
            if change=='changed':
                (code/'apparatus/c10/placements.py').write_text('# altered inside the container\n')
            elif change=='extra':
                (code/'apparatus/c10/unlisted.py').write_text('# not in the committed source\n')
            else:
                (code/'apparatus/sanity/session.py').unlink()
            altered=self.tree(code)
            with self.subTest(change=change):
                record='later-'+change
                failed,report=self.run_continuation(self.args(self.packet(audits[2],change+'.json'),record,connection='synthetic'))
                self.assertTrue(failed)
                self.assertEqual((report['outcome'],report['failure']['step'],report['credential_sent']),
                                 ('failed','source-delivery',False))
                self.assertIn('incomplete at source-delivery',report['error'])
                self.assertEqual(read_file(self.scratch/record/'host/source-delivery.stderr'),
                                 b'existing code directory differs from the committed source; nothing was changed\n')
                self.assertEqual(self.tree(code),altered)
                self.assertFalse(self.published(audits[2]).parent.exists())
                self.assertFalse((self.scratch/record/'host/placement.argv.json').exists())
                self.assertEqual(self.calls('calls.jsonl'),[])
            shutil.rmtree(code)
            for name,data in original.items():
                (code/name).parent.mkdir(parents=True,exist_ok=True)
                (code/name).write_bytes(data)
        self.assertEqual(len(self.calls('placement-stdin.jsonl')),2)
        # Restored to the committed source, the directory is accepted again.
        failed,report=self.run_continuation(self.args(self.packet(audits[2],'restored.json'),'later-restored'))
        self.assertEqual((failed,report['code']['created']),(False,False))

    def test_preflight_record_missing_or_naming_another_attempt_sends_no_credential(self):
        audits=['control-continue-cap','control-continue-entries','control-reminder-spent-submits',
                'control-reminder-spent','control-reminder-unused']
        self.retain(exports=tuple((audit,[['interrupted','max_tokens']]) for audit in audits))
        ready={'continuation_preflight_verified':True,'placement':2}
        self.plans[audits[0]]=self.plan(audits[0],ready=None,exit=1)
        self.plans[audits[1]]=self.plan(audits[1],ready={**ready,'audit':audits[0]})
        self.plans[audits[2]]=self.plan(audits[2],ready={**ready,'audit':audits[2],'attempt':2})
        self.plans[audits[3]]=self.plan(audits[3],ready=None,exit=0,sleep=1)
        self.configure()
        # The fourth process outlives both deadlines; the launcher reports its state unknown and leaves it.
        warnings.simplefilter('ignore',ResourceWarning)
        self.addCleanup(warnings.simplefilter,'default',ResourceWarning)
        for number,audit in enumerate(audits[:4]):
            with self.subTest(audit=audit),mock.patch.object(c10,'READY_SECONDS',0.4),mock.patch.object(c10,'STOP_SECONDS',0.2):
                record=f'later-0{number}'
                failed,report=self.run_continuation(self.args(self.packet(audit,audit+'.json'),record,connection='synthetic'))
                self.assertTrue(failed)
                self.assertEqual((report['outcome'],report['failure']['step'],report['credential_sent']),
                                 ('failed','preflight',False))
                self.assertIn('incomplete at preflight',report['error'])
                self.assertNotIn('not_started',report)
                # No keyring lookup, no prompt and no byte on the placement's input.
                self.assertEqual(self.calls('calls.jsonl'),[])
                self.assertFalse((self.scratch/record/'host/connection.json').exists())
                self.assertEqual([row for row in self.calls('placement-stdin.jsonl') if row['bytes']],[])
                self.assertEqual(self.calls('starts.jsonl'),[])
        self.assertEqual(report['container_process_state'],'unknown; use recorded operator commands')
        # The process that ended without a preflight record or a result left its start uncertain for good.
        first=strict_json(read_file(self.scratch/'later-00/host/RESULT.json'))
        self.assertEqual((first['container_exit'],'session' in first),(1,False))
        self.assert_refused_untouched('an earlier attempt of this placement started or may have started',
                                      self.args(self.packet(audits[0],'again.json'),'later-again',connection='synthetic'))
        # A record that names another attempt is read at the expected path and is not the one awaited.
        self.assertEqual(strict_json(read_file(self.published(audits[2])/'READY.json'))['attempt'],2)
        failed,report=self.run_continuation(self.args(self.packet(audits[4],'ready.json'),'later-ready',connection='synthetic'))
        self.assertEqual((failed,report['credential_sent']),(False,True))
        self.assertEqual(len([args for args in self.calls('calls.jsonl') if args[0]=='pipe']),1)
        self.assertEqual(self.calls('starts.jsonl'),[{'audit':audits[4],'placement':2,'attempt':1}])

    def test_failed_unobserved_or_credential_bearing_placement_is_incomplete(self):
        audits=['control-continue-cap','control-continue-entries','control-reminder-spent',
                'control-reminder-spent-submits','control-reminder-unused']
        self.retain(exports=tuple((audit,[['interrupted','max_tokens']]) for audit in audits))
        good={audit:self.plan(audit)['result'] for audit in audits}
        self.plans[audits[0]]=self.plan(audits[0],result=None,failure=True,exit=1)
        self.plans[audits[1]]=self.plan(audits[1],result={**good[audits[1]],'failed':True},exit=1)
        self.plans[audits[2]]=self.plan(audits[2],result={**good[audits[2]],'expected_observation':False})
        self.plans[audits[3]]=self.plan(audits[3],result=good[audits[3]],exit=1)
        self.plans[audits[4]]=self.plan(audits[4],result=good[audits[4]],leak=True)
        self.configure()
        for audit,step in zip(audits,['placement-result']*4+['host-scan']):
            with self.subTest(audit=audit):
                record='later-'+audit
                failed,report=self.run_continuation(self.args(self.packet(audit,audit+'.json'),record))
                self.assertTrue(failed)
                self.assertEqual((report['outcome'],report['failure']['step'],report['credential_sent']),('failed',step,True))
                self.assertIn('Nothing is retried',report['error'])
                self.assertNotIn(self.key,json.dumps(report))
        first=strict_json(read_file(self.scratch/('later-'+audits[0])/'host/RESULT.json'))
        self.assertEqual(first['container_failure'],{'path':str(self.published(audits[0])/'FAILURE.json'),
            'sha256':digest(read_file(self.published(audits[0])/'FAILURE.json'))})
        self.assertNotIn('session',first)
        second=strict_json(read_file(self.scratch/('later-'+audits[1])/'host/RESULT.json'))
        self.assertEqual(second['session']['sha256'],digest(read_file(self.published(audits[1])/'RESULT.json')))
        leaked=strict_json(read_file(self.scratch/('later-'+audits[4])/'host/RESULT.json'))
        self.assertEqual((leaked['host_scan']['record']['files_with_matches'],leaked['host_scan']['evidence']['files_with_matches']),(0,1))
        # One start each; a failure never led to a second one.
        self.assertEqual([row['audit'] for row in self.calls('starts.jsonl')],audits)
        # Each of these started a placement, so none may be attempted again.
        for audit in audits:
            with self.assertRaisesRegex(c10.Refused,'an earlier attempt of this placement started or may have started'):
                self.run_continuation(self.args(self.packet(audit,audit+'-again.json'),'again-'+audit))

    # --- later custody actions on a continued audit

    def test_control_runs_the_code_directory_its_record_folder_names(self):
        self.retain()
        failed,report=self.run_continuation(self.args(self.packet(),connection='synthetic'))
        self.assertFalse(failed)
        record,code=self.scratch/'later-01',report['code']['directory']
        def control(folder,operation,connection=None):
            args=argparse.Namespace(evidence=folder,audit='control-continue-cap',operation=operation,confirm=None,
                                    connection=connection)
            with mock.patch.object(sys,'stdout',io.TextIOWrapper(io.BytesIO())):
                status=c10.host_control(args)
            return status,self.calls()[-1]
        # The original launch's own record names no code directory: its launch-time source is used.
        self.assertEqual(control(self.evidence,'status'),(0,['exec',self.container,'env','-i',
            'PATH=/usr/local/bin:/usr/bin:/bin','python3','-I','-B','/work/code/apparatus/c10/operations.py',
            'control-continue-cap','status']))
        self.assertEqual(control(record,'status')[1][8],code+'/apparatus/c10/operations.py')
        status,argv=control(record,'collect','synthetic')
        self.assertEqual((status,argv[:2],argv[9]),(0,['exec','--interactive'],code+'/apparatus/c10/operations.py'))
        self.assertEqual((self.bin/'operations-stdin.sha256').read_text(),digest(self.key.encode()))
        # The export lands in the original folder through /out, so both trees are scanned.
        for suffix in ['.scan.json','.evidence-scan.json']:
            scans=list((record/'host/operators').glob('*'+suffix))
            self.assertEqual(len(scans),1,suffix)
            self.assertEqual((strict_json(read_file(scans[0]))['files_with_matches'],strict_json(read_file(scans[0]))['errors']),(0,0))
        self.assertEqual(list((self.evidence/'host').glob('operators/*.evidence-scan.json')),[])
        operator=strict_json(read_file(record/'host/operator.json'))
        before=self.calls()
        for reason,value in [('unknown code directory',{**operator,'code':'/work/elsewhere'}),
                             ('unknown code directory',{**operator,'code':'/work/code-XYZ'}),
                             ('record folder names another retained audit',{**operator,'container':'stewart-c10-9-9'})]:
            (record/'host/operator.json').unlink()
            write_json(record/'host/operator.json',value)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,reason):
                control(record,'status')
        self.assertEqual(self.calls(),before)

    # --- proposals and binding

    def test_proposal_reads_prior_state_from_the_latest_export_and_runs_nothing(self):
        audits=['control-continue-cap','control-continue-entries','control-reminder-spent',
                'control-reminder-spent-submits']
        self.retain(exports=((audits[0],[['interrupted','max_tokens']]),(audits[1],[['sealed',None]]),
                             (audits[2],[None]),(audits[3],[['interrupted','process_gone']])))
        value=c10.continuation_proposal(self.evidence,audits[0],max_placements=3,interruption='reminder_notice',
                                        stop_after_seconds=120)
        self.assertEqual(value,{'schema':'stewart.c10-continuation/3','evidence':str(self.evidence),'audit':audits[0],
            'container':self.container,'reference':self.reference_for(audits[0]),'placement':2,'max_placements':3,
            'prior':{'runs':1,'last_ending':'interrupted','last_cause':'max_tokens',
                     'log_head_sha256':self.heads[audits[0]],'usage':self.used},
            'model':'rehearsal-only','limits':self.original['limits'],'endpoint':'loopback-fake','proxy':None,
            'interruption':{'after':'reminder_notice','action':'signal'},'permitted_request_attempts':4,
            'automatic_continuation':False,'file_size_limit':None,'stop_after_seconds':120,'spending_authority':None,
            'account':{'account_label':None,'workspace_id':None,'credential_label':None},
            'bindings':dict.fromkeys(common.BINDINGS)})
        with self.assertRaises(ValueError):
            common.validate_continuation(copy.deepcopy(value),rehearsal=True,approved=True)
        for audit,reason,options in [
                (None,'this launch retained several audits; name one with --audit',{'max_placements':2}),
                ('somebody-else','this launch did not retain that audit',{'max_placements':2}),
                (audits[0],'state the newly commissioned ceiling with --max-placements',{}),
                (audits[1],'only the next placement of an audit whose last placement was recorded interrupted',{'max_placements':2}),
                (audits[2],'the last placement has no recorded ending',{'max_placements':2}),
                (audits[3],'only the next placement of an audit whose last placement was recorded interrupted',{'max_placements':2}),
                ('control-reminder-unused','the audit has no export to read its prior state from',{'max_placements':2})]:
            with self.subTest(audit=audit,reason=reason),self.assertRaisesRegex(c10.Refused,reason):
                c10.continuation_proposal(self.evidence,audit,**options)
        # A second interrupted placement in a later export moves the proposal to the third.
        self.export(audits[0],[['interrupted','max_tokens'],['interrupted','signal']],'export-0002')
        later=c10.continuation_proposal(self.evidence,audits[0],max_placements=3)
        self.assertEqual((later['placement'],later['prior']['runs'],later['prior']['last_cause'],later['prior']['usage']),
                         (3,2,'signal',{key:2*count for key,count in self.used.items()}))
        self.assertEqual(self.calls(),[])
        c10.bindings.assert_not_called()

    def test_binding_keeps_the_retained_writer_and_an_unpaid_proposal(self):
        self.retain('live',exports=(('open-ordinary-r1',[['interrupted','max_tokens']]),))
        value=c10.continuation_proposal(self.evidence,max_placements=2)
        self.assertEqual((value['model'],value['endpoint']),('example-model','https://api.anthropic.com'))
        bound=c10.bind_continuation(value,'fixture-qualification')
        self.assertEqual(bound,{**value,'bindings':self.bound})
        c10.bindings.assert_called_once_with('fixture-qualification',None)
        with self.assertRaisesRegex(ValueError,'approved packet has unfilled authority or bindings'):
            common.validate_continuation(copy.deepcopy(bound),approved=True)
        common.validate_continuation({**bound,'spending_authority':'Fixture only.',
                                      'account':{key:'approved' for key in bound['account']}},approved=True)
        with self.assertRaisesRegex(c10.Refused,'bind an unpaid proposal with null account fields'):
            c10.bind_continuation({**value,'spending_authority':'already paid'},'fixture-qualification')
        with self.assertRaisesRegex(c10.Refused,'packet names another container'):
            c10.bind_continuation({**value,'container':'stewart-c10-9-9'},'fixture-qualification')
        self.bound={**self.bound,'binary_sha256':'7'*64}
        with self.assertRaisesRegex(c10.Refused,'the qualified writer or image differs from the retained launch'):
            c10.bind_continuation(value,'fixture-qualification')
        self.assertEqual(self.calls(),[])

    def test_allowance_outlook_states_the_shared_allowance_facts(self):
        # The arithmetic is batch.allowance_facts and common.limit_exhausted (test_placements.ArithmeticTests);
        # the outlook only maps a packet's limits and observed usage onto it.
        limits={'turns':12,'input_tokens':160000,'output_tokens':12000}
        usage={'turns':3,'input_tokens':110,'output_tokens':55}
        allowances={key:{'limit':limits[key],'used':usage[key]} for key in limits}
        self.assertEqual(c10.allowance_outlook(limits,usage,'reminder_notice'),
                         c10.allowance_facts(allowances,{'after':'reminder_notice','action':'signal'}))
        plain=c10.allowance_outlook(limits,usage,None)
        self.assertEqual((plain['remaining'],plain['planned_interruption']),
                         ({'turns':9,'input_tokens':159890,'output_tokens':11945},None))

    # --- the rehearsal's continuation controls

    def rehearsed(self):
        """A rehearsal folder whose six continued controls each await their second placement."""
        self.retain(exports=tuple(('control-'+name,[endings[0]]) for name,(_,endings) in CONTINUED_CONTROLS.items()))
        for name,(_,endings) in CONTINUED_CONTROLS.items():
            audit='control-'+name
            self.log_archive(self.bin/'exports'/(audit+'.tar'),audit,endings)
            self.expect_review(audit,'export-0002',endings)
            self.plans[audit]=self.plan(audit,export='export-0002')
        self.configure()

    def continue_controls(self,connection=None):
        with redirect_stdout(io.StringIO()):
            failed=c10.rehearse_continuations(self.evidence,self.original,'fixture-qualification',connection,
                                              None if connection else self.key.encode())
        return failed,strict_json(read_file(self.evidence/'host/continuations.json'))

    def check_controls(self,**options):
        c10.check_rehearsed_continuations(self.evidence,strict_json(read_file(self.evidence/'host/RESULT.json')),
                                          self.original['runs'],self.review(self.evidence),**options)

    @contextmanager
    def replaced(self,path,value):
        original=path.read_bytes()
        path.write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode())
        try:
            yield
        finally:
            path.write_bytes(original)

    def test_rehearsal_continues_every_control_and_live_admission_requires_it(self):
        self.rehearsed()
        failed,record=self.continue_controls()
        self.assertFalse(failed)
        audits=['control-'+name for name in CONTINUED_CONTROLS]
        self.assertEqual((record['planned'],record['completed'],record['failed'],record['not_started']),(8,8,0,0))
        self.assertEqual([(row['audit'],row['record'],row['started'],row['failed']) for row in record['continuations']],
                         [(audit,str(self.scratch/('earlier-01-'+audit+'-p2')),True,False) for audit in audits])
        # One placement start per control, each with the rehearsal's own key; source delivered once.
        self.assertEqual([(row['audit'],row['sha256']) for row in self.calls('placement-stdin.jsonl')],
                         [(audit,digest(self.key.encode())) for audit in audits])
        created=[strict_json(read_file(self.scratch/('earlier-01-'+audit+'-p2')/'host/RESULT.json'))['code']['created']
                 for audit in audits]
        self.assertEqual(created,[True]+[False]*7)
        for audit in audits:
            packet=strict_json(read_file(self.evidence/'host'/('continuation-'+audit+'.json')))
            self.assertEqual((packet['model'],packet['endpoint'],packet['placement'],packet['max_placements'],
                              packet['interruption'],packet['prior']['log_head_sha256']),
                             ('rehearsal-only','loopback-fake',2,2,None,self.heads[audit]))
            self.assertNotIn(self.key.encode(),read_file(self.evidence/'host'/('continuation-'+audit+'.json')))
        self.check_controls()
        # Each refusal below changes one retained fact of an otherwise passing rehearsal.
        sample='control-reminder-spent'
        launch=self.scratch/('earlier-01-'+sample+'-p2')/'host/RESULT.json'
        session=self.published(sample)/'RESULT.json'
        ended=self.evidence/'container'/sample/'export-0002/work.tar'
        host=strict_json(read_file(launch))
        with self.replaced(self.evidence/'host/continuations.json',{**record,'schema':'other'}):
            with self.assertRaisesRegex(ValueError,'continuation controls missing, failed or not started'):
                self.check_controls()
        for change in [{'outcome':'failed'},{'outcome':'not_started'},{'mode':'live'},{'attempt':2},{'container':'stewart-c10-9-9'},
                       {'bindings':{**host['bindings'],'apparatus_sha256':'9'*64}},{'commission_sha256':'0'*64},
                       {'code':{**host['code'],'directory':'/work/code'}}]:
            with self.subTest(change=change),self.replaced(launch,{**host,**change}):
                with self.assertRaisesRegex(ValueError,'continuation control did not complete through the host path'):
                    self.check_controls()
        with self.replaced(session,read_file(session)+b' '):
            with self.assertRaisesRegex(ValueError,'continuation control did not complete through the host path'):
                self.check_controls()
        with self.assertRaisesRegex(ValueError,'saved connections require a synthetic connection continuation'):
            self.check_controls(connection=True)
        # Its control says the reminder was spent and the next ordinary ending ends authoring unsubmitted.
        self.log_archive(self.root/'sealed.tar',sample,[['interrupted','signal'],['sealed',None]])
        with self.replaced(ended,read_file(self.root/'sealed.tar')):
            with self.assertRaisesRegex(ValueError,'continued audit did not end as its control specifies'):
                self.check_controls()
        self.log_archive(self.root/'once.tar',sample,[['interrupted','signal']])
        with self.replaced(ended,read_file(self.root/'once.tar')):
            with self.assertRaisesRegex(ValueError,'continued audit did not end as its control specifies'):
                self.check_controls()
        checked=self.reviews[sample,'export-0002']
        self.reviews[sample,'export-0002']={**checked,'outcome':'incomplete'}
        with self.assertRaisesRegex(ValueError,'continued audit lacks a checked export after its final placement'):
            self.check_controls()
        self.reviews[sample,'export-0002']={**checked,'ending':'sealed','auditor_submitted':True,'delivery_verified':True}
        with self.assertRaisesRegex(ValueError,'continued audit submission differs from its control'):
            self.check_controls()
        self.reviews[sample,'export-0002']=checked
        self.check_controls()
        # Live admission reads the same records with the rest of the rehearsal's inventory.
        for run in self.original['runs']:
            if run['scenario'] not in CONTINUED_CONTROLS:
                self.export(run['id'],[['sealed',None]])
        container=self.evidence/'container'
        write_json(container/'PLAN.json',{'schema':'stewart.c10-plan/1','commission':self.original})
        session={'schema':'stewart.c10-session/2','outcome':'passed','local_iteration_only':False,
            'planned':len(REHEARSAL_AUDITS),'observed':len(REHEARSAL_AUDITS),'failed':0,'not_started':0,'skipped_checks':[],
            'audits':[{'audit':audit,'expected_observation':True} for audit in REHEARSAL_AUDITS]}
        write_json(container/'RESULT.json',session)
        for name,value in [('review-controls',{'failed':0,'controls':12,'controls_fired':12,'passed':14,'run':14,'original_unchanged':True}),
                           ('compaction-controls',{'schema':'stewart.c10-compaction-controls/1','failed':0,
                               'controls':19,'controls_fired':19,'passed':26,'run':26,
                               'original_unchanged':True,'same_selected_answer':True}),
                           ('operator-controls',{'failed':0,'passed':7,'run':7,'original_snapshot_unchanged':True}),
                           ('report-controls',{'failed':0,'passed':11,'run':11,'original_unchanged':True})]:
            (container/name).mkdir()
            write_json(container/name/'RESULT.json',value)
        report=c10.check_rehearsal(self.evidence,self.bound)
        self.assertEqual([row['audit'] for row in report['audits']],REHEARSAL_AUDITS)
        # Supplied scenarios require their own template controls and must still
        # leave the whole inventory available for the later admission checks.
        supplied=copy.deepcopy(self.original)
        supplied['schema']='stewart.study-commission/2'
        for run in supplied['runs']:
            run['submission_folder']=None
        extended=copy.deepcopy(session)
        added=[]
        for scenario,count in [('compaction',16),('compaction-below',8),('compaction-invalid',13)]:
            audit='large-'+scenario
            added.append(audit);self.audits.append(audit)
            self.export(audit,[['interrupted','protocol_anomaly']] if scenario=='compaction-invalid' else [['sealed',None]])
            supplied['runs'].append({'id':audit,'case':audit,'repetition':1,'scenario':scenario,
                'submission_sha256':'a'*64,'submission_folder':str(self.root/'large-submission')})
            extended['audits'].append({'audit':audit,'expected_observation':True})
            path=container/'study-review-controls'/audit
            path.mkdir(parents=True)
            write_json(path/'RESULT.json',{'failed':0,'run':count,'passed':count,'controls':count-2,
                       'controls_fired':count-2,'original_unchanged':True})
        extended['planned']=extended['observed']=len(supplied['runs'])
        with self.replaced(container/'PLAN.json',{'schema':'stewart.c10-plan/1','commission':supplied}),\
                self.replaced(container/'RESULT.json',extended):
            c10.check_rehearsal(self.evidence,self.bound)
            for audit in added:
                path=container/'study-review-controls'/audit/'RESULT.json'
                value=strict_json(read_file(path))
                with self.replaced(path,{**value,'controls_fired':value['controls_fired']-1}):
                    with self.assertRaisesRegex(ValueError,'study template controls missing or incomplete'):
                        c10.check_rehearsal(self.evidence,self.bound)
        self.audits=[audit for audit in self.audits if audit not in added]
        compaction=container/'compaction-controls/RESULT.json'
        checked=strict_json(read_file(compaction))
        for changed in [{'failed':1},{'controls_fired':18},{'passed':25},
                        {'original_unchanged':False},{'same_selected_answer':False}]:
            with self.subTest(changed=changed),self.replaced(compaction,{**checked,**changed}):
                with self.assertRaisesRegex(ValueError,'compaction controls missing or incomplete'):
                    c10.check_rehearsal(self.evidence,self.bound)
        with self.assertRaisesRegex(ValueError,'rehearsal source, binary, image or catalog differs'):
            c10.check_rehearsal(self.evidence,{**self.bound,'apparatus_sha256':'9'*64})
        # The earlier thirteen-audit inventory is not a rehearsal of this apparatus.
        single=[run for run in self.original['runs'] if run['scenario'] not in CONTINUED_CONTROLS]
        with self.replaced(container/'PLAN.json',{'schema':'stewart.c10-plan/1','commission':{**self.original,'runs':single}}):
            with self.assertRaisesRegex(ValueError,'rehearsal omitted or changed fixed conformance controls'):
                c10.check_rehearsal(self.evidence,self.bound)
        with self.replaced(container/'RESULT.json',{**session,'planned':13,'observed':13,'audits':session['audits'][:13]}):
            with self.assertRaisesRegex(ValueError,'incomplete rehearsal inventory'):
                c10.check_rehearsal(self.evidence,self.bound)
        with self.assertRaisesRegex(ValueError,'saved connections require a synthetic connection rehearsal'):
            c10.check_rehearsal(self.evidence,self.bound,connection=True)
        (self.evidence/'host/continuations.json').unlink()
        for check in [self.check_controls,lambda:c10.check_rehearsal(self.evidence,self.bound)]:
            with self.assertRaisesRegex(ValueError,'continuation controls missing, failed or not started'):
                check()

    def test_failed_continuation_control_fails_the_rehearsal_and_starts_no_later_one(self):
        self.rehearsed()
        failing='control-continue-entries'
        self.plans[failing]['result']['expected_observation']=False
        self.configure()
        failed,record=self.continue_controls()
        self.assertTrue(failed)
        self.assertEqual((record['planned'],record['completed'],record['failed'],record['not_started']),(8,1,1,6))
        self.assertEqual([(row['started'],row['failed']) for row in record['continuations']],
                         [(True,False),(True,True)]+[(False,None)]*6)
        self.assertEqual([row['audit'] for row in self.calls('placement-stdin.jsonl')],['control-continue-cap',failing])
        self.assertEqual(sorted(path.name for path in self.scratch.iterdir()),
                         ['earlier-01','earlier-01-control-continue-cap-p2','earlier-01-'+failing+'-p2'])
        with self.assertRaisesRegex(ValueError,'continuation controls missing, failed or not started'):
            self.check_controls()

    def test_control_whose_first_placement_ended_otherwise_is_not_continued(self):
        self.rehearsed()
        # The output-cap control's first placement must end at the cap, not by a signal.
        audit='control-continue-cap'
        shutil.rmtree(self.evidence/'container'/audit)
        self.export(audit,[['interrupted','signal']])
        failed,record=self.continue_controls()
        self.assertTrue(failed)
        row=record['continuations'][0]
        self.assertEqual((record['completed'],record['failed'],record['not_started']),(0,1,7))
        self.assertEqual((row['audit'],row['started'],row['failed'],row['reason']),
                         (audit,False,True,'the first placement did not end as this control specifies'))
        self.assertEqual((self.calls(),self.calls('placement-stdin.jsonl')),([],[]))

    def test_continued_audit_controls_need_their_exact_counts(self):
        def check(scenario,shape=0,**changes):
            controls=control_counts(scenario,shape)
            for family,change in changes.items():
                controls[family]=change if change is None or controls[family] is None else {**controls[family],**change}
            c10.continuation_controls({'controls':controls},scenario)
        for scenario in CONTINUED_CONTROLS:
            check(scenario)
        # The unheld control's signal either found a written request or did not; nothing else is admissible.
        check('reminder-spent-unheld',1)
        reviewer='continued-audit reviewer controls failed, incomplete or differ in count'
        report='continued-audit report controls failed, incomplete or differ in count'
        operator='continued-audit operator controls failed, incomplete or differ in count'
        for reason,scenario,changes in [
                (reviewer,'reminder-spent',{'review':{'failed':1,'passed':13}}),
                (reviewer,'reminder-spent',{'review':{'passed':13}}),
                (reviewer,'reminder-spent',{'review':{'skipped':1}}),
                (reviewer,'reminder-spent',{'review':{'controls_fired':12}}),
                (reviewer,'reminder-spent',{'review':{'original_unchanged':False}}),
                (reviewer,'reminder-spent',{'review':{'run':13,'passed':13,'controls':12,'controls_fired':12,'not_applicable':['one']}}),
                (reviewer,'continue-cap',{'review':{'not_applicable':['one','two']}}),
                (reviewer,'continue-cap',{'review':{'run':14,'passed':14,'controls':13,'controls_fired':13,'not_applicable':[]}}),
                (reviewer,'continue-entries',{'review':{'run':11,'passed':11,'controls':10,'controls_fired':10,'not_applicable':['a','b','c']}}),
                (reviewer,'reminder-spent-unheld',{'review':{'run':12,'passed':12,'controls':11,'controls_fired':11,'not_applicable':['a','b']}}),
                (reviewer,'reminder-spent-unheld',{'review':{'not_applicable':[]}}),
                (reviewer,'reminder-unused',{'review':None}),
                (report,'reminder-unused',{'reporting':{'run':11,'passed':11}}),
                (report,'reminder-unused',{'reporting':{'failed':1,'passed':13}}),
                (report,'reminder-unused',{'reporting':{'original_unchanged':False}}),
                (report,'reminder-unused',{'reporting':None}),
                (operator,'reminder-spent',{'operations':{'run':7,'passed':7}}),
                (operator,'reminder-spent',{'operations':{'failed':1,'passed':7}}),
                (operator,'reminder-spent-unheld',{'operations':{'original_unchanged':False}}),
                (operator,'reminder-spent',{'operations':None}),
                (operator,'reminder-spent-unheld',{'operations':None})]:
            with self.subTest(reason=reason,scenario=scenario,changes=changes),self.assertRaisesRegex(ValueError,reason):
                check(scenario,**changes)
        # Manager close belongs to the controls left unsubmitted; a sealed control has none to report.
        submitted=control_counts('reminder-unused')
        submitted['operations']={'run':8,'passed':8,'failed':0,'original_unchanged':True}
        with self.assertRaisesRegex(ValueError,'operator controls ran on a submitted audit'):
            c10.continuation_controls({'controls':submitted},'reminder-unused')
        for controls in [None,{key:value for key,value in control_counts('continue-cap').items() if key!='reporting'}]:
            with self.assertRaisesRegex(ValueError,'continued-audit controls missing'):
                c10.continuation_controls({'controls':controls},'continue-cap')

    def test_rehearsed_continuation_fails_without_its_second_start_refusal_or_exact_controls(self):
        audits=['control-continue-cap','control-continue-entries','control-reminder-spent','control-reminder-spent-unheld']
        self.retain(exports=tuple((audit,[['interrupted','max_tokens']]) for audit in audits))
        good={audit:self.plan(audit)['result'] for audit in audits}
        # The same packet reached preflight again and was not stopped by the service's placement count.
        self.plans[audits[0]]=self.plan(audits[0],result={**good[audits[0]],'second_start':{'refused':False,'phase':None}})
        self.plans[audits[1]]=self.plan(audits[1],result={**good[audits[1]],'second_start':{'refused':True,'phase':'preflight.audit_state'}})
        short=control_counts('reminder-spent');short['operations'].update(run=7,passed=7)
        self.plans[audits[2]]=self.plan(audits[2],result={**good[audits[2]],'controls':short})
        self.plans[audits[3]]=self.plan(audits[3],result={**good[audits[3]],'controls':control_counts('reminder-spent-unheld',1)})
        self.configure()
        for audit in audits[:3]:
            with self.subTest(audit=audit):
                failed,report=self.run_continuation(self.args(self.packet(audit,audit+'.json'),'later-'+audit))
                self.assertTrue(failed)
                self.assertEqual((report['outcome'],report['failure']['step'],report['credential_sent']),
                                 ('failed','placement-result',True))
        failed,report=self.run_continuation(self.args(self.packet(audits[3],'unheld.json'),'later-unheld'))
        self.assertEqual((failed,report['outcome']),(False,'completed'))
        for audit,reason in [(audits[0],'a second start of the same placement was not refused by the placement count'),
                             (audits[1],'a second start of the same placement was not refused by the placement count')]:
            with self.assertRaisesRegex(ValueError,reason):
                c10.continuation_session(self.published(audit)/'RESULT.json','rehearse',audit,2)
        c10.continuation_session(self.published(audits[3])/'RESULT.json','rehearse',audits[3],2)


if __name__=='__main__':
    unittest.main()
