"""Offline profile-producer controls. All signature/live records here are temporary synthetic fixtures."""

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profile_producer', HERE / 'profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
sys.path.insert(0, str(HERE.parent / 'driver'))
from claude_code_surface import REQUIRED_CHECKS


class ProfileControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='stewart-profile-controls-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.binary = self.root / 'harness-canary'
        self.marker = self.root / 'unexpected-launch'
        self.binary.write_text('#!/bin/sh\nprintf unexpected > "' + str(self.marker) + '"\nexit 97\n')
        self.binary.chmod(0o700)
        self.pin_root = self.root / 'retained-pin'
        self.pin_root.mkdir()
        self.config, self.home, self.tmp = [self.root / name for name in ('login', 'home', 'temporary')]
        for directory in (self.config, self.home, self.tmp):
            directory.mkdir()
        (self.config / 'credential-canary').write_bytes(b'not-to-be-read')
        binary_sha = profile.sha(self.binary.read_bytes())
        manifest = profile.compact({'version': profile.pin.VERSION,
                                   'platforms': {profile.pin.PLATFORM: {'checksum': binary_sha}}})
        (self.pin_root / 'manifest.json').write_bytes(manifest)
        (self.pin_root / 'manifest.json.sig').write_bytes(b'synthetic public signature')
        (self.pin_root / 'claude-code.asc').write_bytes(b'synthetic public key')
        self.receipt = {'version': profile.pin.VERSION, 'platform': profile.pin.PLATFORM,
                        'binary': str(self.binary), 'sha256': binary_sha, 'manifest_sha256': profile.sha(manifest),
                        'signer': profile.pin.FINGERPRINT, 'verification': 'synthetic-prior-verification'}
        (self.pin_root / 'pin.json').write_bytes(profile.compact(self.receipt))
        self.install = self.root / 'prepared-installation'
        self.calls, self.reads = [], []
        original_read = profile.read_file

        def observed_read(path, *args, **kwargs):
            path = Path(path)
            self.reads.append(path)
            self.assertFalse(path == self.config or self.config in path.parents, 'credential store was read')
            return original_read(path, *args, **kwargs)

        with mock.patch.object(profile.pin, 'run_logged', side_effect=self.fake_verify), \
                mock.patch.object(profile.shutil, 'which', side_effect=lambda name: '/synthetic/' + name), \
                mock.patch.object(profile, 'read_file', side_effect=observed_read), contextlib.redirect_stdout(io.StringIO()):
            profile.prepare(self.pin_root / 'pin.json', self.install, self.config, self.home, self.tmp)
        self.observation = self.root / 'observation'
        (self.observation / 'inputs').mkdir(parents=True)
        (self.observation / 'witness').mkdir()
        (self.observation / 'inputs/launch.json').write_bytes((self.install / 'launch.json').read_bytes())
        (self.observation / 'inputs/surface.json').write_bytes(profile.compact({'schema': 'synthetic-test-surface'}))
        (self.observation / 'inputs/tools.json').write_bytes(profile.compact([{'name': 'synthetic-test-tool'}]))
        (self.observation / 'witness/observed.bin').write_bytes(b'temporary synthetic unit-test witness\n')
        self.review = self.root / 'CHECK.json'
        self.output = self.root / 'profile.json'
        self.rebind()

    def fake_verify(self, out, name, argv):
        self.calls.append((name, argv))
        self.assertNotEqual(argv[0], str(self.binary))
        data = (('[GNUPG:] VALIDSIG %s 2026-11-10 1794340800 0 4 0 1 10 00\n' % profile.pin.FINGERPRINT).encode()
                if name == 'signature' else b'')
        (out / (name + '.stdout')).write_bytes(data)
        (out / (name + '.stderr')).write_bytes(b'')
        (out / (name + '.exit')).write_bytes(b'0\n')
        return data

    def rebind(self, observation_change=None, review_change=None):
        members = []
        for name in ('inputs/launch.json', 'inputs/surface.json', 'inputs/tools.json', 'witness/observed.bin'):
            raw = (self.observation / name).read_bytes()
            members.append({'path': name, 'bytes': len(raw), 'sha256': profile.sha(raw)})
        manifest = profile.compact({'schema': 'stewart.claude-code.surface-evidence/1', 'members': members})
        (self.observation / 'EVIDENCE.json').write_bytes(manifest)
        bindings = {key: profile.sha((self.observation / ('inputs/' + name + '.json')).read_bytes())
                    for name, key in (('launch', 'launch_sha256'), ('surface', 'surface_sha256'), ('tools', 'tools_sha256'))}
        bindings['model'] = 'synthetic-unit-test-model'
        # These are parser fixtures, not emitted rehearsal results or live evidence.
        observation = dict(schema='stewart.claude-code.surface-observation/1', mode='real-harness',
                           scope='supplied-surface', started_at='2026-11-12T00:00:00Z', finished_at='2026-11-12T00:01:00Z',
                           evidence_manifest_sha256=profile.sha(manifest), stopping='observed',
                           checks=[{'id': name, 'outcome': 'observed', 'evidence': ['witness/observed.bin']}
                                   for name in REQUIRED_CHECKS], **bindings)
        if observation_change:
            observation_change(observation)
        raw = profile.compact(observation)
        (self.observation / 'OBSERVATION.json').write_bytes(raw)
        review = dict(schema='stewart.claude-code.reviewed-check/1', scope='supplied-surface',
                      checked_at=observation['finished_at'], observation_sha256=profile.sha(raw),
                      reviewer='synthetic unit-test reviewer', reviewed_at='2026-11-12T00:02:00Z', outcome='observed', **bindings)
        if review_change:
            review_change(review)
        self.review.write_bytes(profile.compact(review))

    def assemble(self):
        with contextlib.redirect_stdout(io.StringIO()):
            profile.assemble(self.install, self.observation, self.review, self.output)
        return profile.decode(self.output.read_bytes())

    def refused(self, message):
        with self.assertRaisesRegex((ValueError, OSError), message):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.marker.exists())

    def test_valid_profile_preserves_exact_launch_and_review_digest_without_launch(self):
        launch = (self.install / 'launch.json').read_bytes()
        result = self.assemble()
        self.assertEqual(result['schema'], 'stewart.claude-code.profile/2')
        self.assertIn(b'"launch":' + launch + b',"installation":', self.output.read_bytes())
        self.assertEqual(result['check']['launch_sha256'], profile.sha(launch))
        self.assertEqual(result['check']['evidence_sha256'], profile.sha(self.review.read_bytes()))
        self.assertEqual([name for name, _ in self.calls], ['dearmor', 'signature', 'codesign'])
        self.assertFalse(self.marker.exists())
        with self.assertRaises(FileExistsError):
            self.assemble()

    def test_canary_fires_when_explicitly_started_by_control(self):
        self.assertFalse(self.marker.exists())
        result = subprocess.run([str(self.binary)], capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 97)
        self.assertEqual(self.marker.read_bytes(), b'unexpected')

    def test_whitespace_inside_launch_value_is_preserved(self):
        raw = json.dumps(profile.decode((self.install / 'launch.json').read_bytes()), indent=2).encode()
        (self.install / 'launch.json').write_bytes(raw)
        (self.observation / 'inputs/launch.json').write_bytes(raw)
        prepared = profile.decode((self.install / 'PREPARATION.json').read_bytes())
        prepared['launch_sha256'] = profile.sha(raw)
        (self.install / 'PREPARATION.json').write_bytes(profile.compact(prepared))
        self.rebind()
        result = self.assemble()
        self.assertEqual(result['check']['launch_sha256'], profile.sha(raw))
        self.assertIn(b'"launch":' + raw + b',"installation":', self.output.read_bytes())

    def test_rehearsal_is_never_eligible(self):
        self.rebind(lambda row: row.update(mode='synthetic-rehearsal'))
        self.refused('rehearsal is not eligible')

    def test_missing_failed_unexercised_and_unwitnessed_checks_refuse(self):
        changes = [lambda row: row['checks'].pop(),
                   lambda row: row['checks'][0].update(outcome='failed'),
                   lambda row: row['checks'][0].update(outcome='unexercised'),
                   lambda row: row['checks'][0].update(evidence=[]),
                   lambda row: row['checks'][0].update(evidence=['absent'])]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.rebind(change)
                self.refused('comparison')
        self.rebind()
        self.assemble()  # Normal invariance after the refusals.

    def test_unknown_stopping_refuses(self):
        self.rebind(lambda row: row.update(stopping='unknown'))
        self.refused('stopped')

    def test_date_without_clock_is_not_a_verification_timestamp(self):
        self.rebind(review_change=lambda row: row.update(reviewed_at='2026-11-12Z'))
        self.refused('complete UTC timestamp')

    def test_review_and_input_bindings_refuse_changed_identity(self):
        changes = [lambda row: row.update(model='another-model'),
                   lambda row: row.update(observation_sha256='0' * 64),
                   lambda row: row.update(checked_at='2026-11-11T00:00:00Z'),
                   lambda row: row.update(reviewed_at='2026-11-11T00:00:00Z')]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.rebind(review_change=change)
                self.refused('review|Review')

    def test_changed_and_unlisted_witnesses_refuse(self):
        path = self.observation / 'witness/observed.bin'
        original = path.read_bytes()
        path.write_bytes(b'changed')
        self.refused('evidence bytes changed')
        path.write_bytes(original)
        extra = self.observation / 'witness/unlisted'
        extra.write_bytes(b'not in manifest')
        self.refused('omits files')
        extra.unlink()
        self.assemble()

    def test_symlink_and_special_witnesses_refuse_without_reading(self):
        path = self.observation / 'witness/observed.bin'
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(self.config / 'credential-canary')
        self.refused('link|loop|Too many')
        path.unlink()
        os.mkfifo(path)
        self.refused('regular file')
        path.unlink()
        path.write_bytes(original)
        self.assemble()

    def test_harness_digest_change_refuses_without_execution(self):
        self.binary.write_bytes(b'changed executable')
        self.refused('executable changed')

    def test_failed_installation_record_refuses(self):
        (self.install / 'installation/verification/codesign.exit').write_bytes(b'1\n')
        # Keep the evidence binding valid so only the failed verifier outcome
        # can refuse this installation, not the changed-file inventory check.
        path = self.install / 'PREPARATION.json'
        prepared = json.loads(path.read_bytes())
        prepared['verification_files'] = profile.verification_inventory(self.install / 'installation')
        path.write_bytes(profile.compact(prepared))
        self.refused('installation verification did not pass: codesign')

    def test_public_signature_and_key_must_remain_exact_and_present(self):
        for name in ('manifest.json.sig', 'claude-code.asc'):
            path = self.install / 'installation' / name
            original = path.read_bytes()
            for mutation in ('changed', 'missing'):
                with self.subTest(member=name, mutation=mutation):
                    if mutation == 'changed':
                        path.write_bytes(b'changed public evidence')
                    else:
                        path.unlink()
                    self.refused('verification evidence')
                    path.write_bytes(original)
        self.assemble()

    def test_output_cannot_mutate_either_input_evidence_tree(self):
        folders = [self.observation, self.install, self.install / 'installation']
        alias = self.observation.with_name(self.observation.name.upper())
        if alias.is_dir():
            folders.append(alias)  # Exercise the host's case-insensitive alias.
        for folder in folders:
            with self.subTest(folder=folder.name):
                self.output = folder / 'new-profile.json'
                self.refused('outside the .* evidence directory')

    def test_wrong_public_signature_refuses_preparation(self):
        out = self.root / 'wrong-signature'
        def wrong(out, name, argv):
            result = self.fake_verify(out, name, argv)
            return result.replace(profile.pin.FINGERPRINT.encode(), b'A' * 40)
        with mock.patch.object(profile.pin, 'run_logged', side_effect=wrong), \
                mock.patch.object(profile.shutil, 'which', return_value='/synthetic/verifier'):
            with self.assertRaisesRegex(ValueError, 'pinned release key'):
                profile.prepare(self.pin_root / 'pin.json', out, self.config, self.home, self.tmp)
        self.assertFalse((out / 'launch.json').exists())
        self.assertFalse(self.marker.exists())

    def test_duplicate_control_json_refuses(self):
        raw = self.review.read_bytes()
        self.review.write_bytes(raw[:-1] + b',"outcome":"observed"}')
        self.refused('duplicate JSON')


if __name__ == '__main__':
    unittest.main()
