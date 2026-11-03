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
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
import c10
from common import (HERE,catalog,compact,digest,inventory,proposal,question_file,read_file,
                    rehearsal_packet,source_hash,strict_json,tree_hash,validate_packet,write_json)
from batch import credential_marker,check_credential,export_snapshot
from batch import execute_batch
from verify import Evidence,usage_counts,verify


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
