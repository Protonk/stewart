"""Provider-free controls for C10 packets, evidence reads and launch authority."""
import argparse
from contextlib import redirect_stderr
import copy
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import subprocess
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
import c10
from common import (HERE,catalog,compact,digest,inventory,proposal,question_file,read_file,
                    rehearsal_packet,source_hash,strict_json,tree_hash,validate_packet,write_json)
from batch import credential_marker,check_credential,export_snapshot
from batch import execute_batch
from verify import Evidence,usage_counts,verify
import connections
from study import (case_from_question, copy_submission, inspect_submission,
                   study_proposal)
from verify import tree_inventory_from_evidence


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
        self.assertEqual(tree_inventory_from_evidence(evidence,'submission/'),inventory(self.folder))

    def test_invalid_template_cannot_be_proposed(self):
        raw=read_file(self.folder/'question.md')
        for changed in [raw.replace(b'inquiry:',b'unknown:'),raw.replace(b'family: open-inquiry',b'family: nonsense'),
                        raw.replace(b'family: open-inquiry',b'family: open-inquiry\nfamily: comparison')]:
            with self.subTest(changed=changed[:60]),self.assertRaises(ValueError):case_from_question(changed,'problem-a')
        (self.folder/'materials/link').symlink_to('text.txt')
        with self.assertRaises(ValueError):study_proposal('example-model',[('problem-a',self.folder)])

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
        self.assertEqual(len(cases),6)
        self.assertEqual(len(proposal('example-model',repetitions=3)['runs']),18)
        self.assertEqual(len(rehearsal_packet()['runs']),13)

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
            packet=Path(temp)/'packet.json';write_json(packet,proposal('example-model'))
            args=argparse.Namespace(mode='live',evidence=c10.REPO/'.scratch/c10-authority-never-created',
                commission=packet,approved_commission='0'*64,rehearsal=Path(temp),qualification='unused')
            with mock.patch.object(c10,'bindings') as bind:
                with self.assertRaises(ValueError):c10.launch_batch(args)
                bind.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def test_unexpected_outcome_stops_batch_without_replacing_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'out';out.mkdir()
            sessions=[]
            for n in range(2):
                evidence=root/f'evidence-{n}';evidence.mkdir()
                audit=mock.Mock(evidence=evidence,phase='run',run_item={'id':f'audit-{n}','scenario':'submitted'})
                audit.execute.return_value={'audit':f'audit-{n}','state':'not_submitted'}
                sessions.append(audit)
            with mock.patch('batch.locked_export',return_value={'outcome':'exported'}):
                result=execute_batch(None,None,out,{},'live',b'synthetic',sessions,None,local=True)
            sessions[0].execute.assert_called_once()
            sessions[1].execute.assert_not_called()
            self.assertEqual((result['planned'],result['observed'],result['failed'],result['not_started']),(2,1,1,1))
            self.assertEqual(result['audits'][1]['state'],'not_started')
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
            self.assertEqual(result['audits'][0]['state'],'unknown')
            self.assertTrue((sessions[0].evidence/'failure.json').is_file())
            self.assertEqual(result['not_started'],1)

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

    def test_credential_reentry_must_match_without_persisting_key(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'marker.json';key=b'synthetic-very-long-key-for-test'
            credential_marker(path,key);check_credential(path,key)
            self.assertNotIn(key,path.read_bytes())
            with self.assertRaises(ValueError):check_credential(path,b'wrong-key')

    def test_incomplete_export_withholds_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'root';root.mkdir();(root/'original').write_bytes(b'untouched')
            result=export_snapshot(root,Path(temp)/'out',b'synthetic')
            self.assertEqual(result['outcome'],'withheld')
            self.assertEqual((root/'original').read_bytes(),b'untouched')
            self.assertFalse((Path(temp)/'out/work.tar').exists())

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


if __name__=='__main__':
    unittest.main()
