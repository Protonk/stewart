"""Offline refusal controls for release-pin verification."""

import importlib.util
import hashlib
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("pin", Path(__file__).with_name("pin.py"))
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
FIXTURES = Path(__file__).parent / 'testdata/verification'


class PinControls(unittest.TestCase):
    def test_unsupported_attestation_refuses_without_output_or_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pin'
            stderr = io.StringIO()
            with mock.patch.object(sys, 'argv', ['pin.py', str(output), '--attest']), \
                    mock.patch.object(pin, 'fetch') as fetch, mock.patch.object(pin, 'verify') as verify, \
                    redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
                pin.main()
            self.assertEqual(stopped.exception.code, 2)
            self.assertIn('unrecognized arguments: --attest', stderr.getvalue())
            fetch.assert_not_called()
            verify.assert_not_called()
            self.assertFalse(output.exists())
            # With only the unsupported argument removed, reach the selected
            # action without performing network, signature or model operations.
            with mock.patch.object(sys, 'argv', ['pin.py', str(output)]), \
                    mock.patch.object(pin, 'fetch') as fetch, mock.patch.object(pin, 'verify') as verify:
                pin.main()
            fetch.assert_called_once()
            verify.assert_not_called()
            self.assertFalse(output.exists())

    def test_manifest_version_and_checksum(self):
        obj = {"version": pin.VERSION, "platforms": {pin.PLATFORM: {"checksum": "a" * 64}}}
        self.assertEqual(pin.manifest_checksum(json.dumps(obj)), "a" * 64)
        obj["version"] = "different"
        with self.assertRaisesRegex(ValueError, 'manifest version does not match the approved pin'):
            pin.manifest_checksum(json.dumps(obj))
        obj["version"] = pin.VERSION
        obj["platforms"][pin.PLATFORM]["checksum"] = "invalid"
        with self.assertRaisesRegex(ValueError, 'manifest has no valid darwin-arm64 SHA-256'):
            pin.manifest_checksum(json.dumps(obj))

    def test_signature_identity_and_control(self):
        status = (FIXTURES / 'signature.stdout').read_text()
        self.assertTrue(pin.signed_by_release_key(status))
        self.assertFalse(pin.signed_by_release_key(status.replace(pin.FINGERPRINT, "A" * 40)))
        valid = next(line for line in status.splitlines() if line.startswith('[GNUPG:] VALIDSIG '))
        self.assertFalse(pin.signed_by_release_key(status.replace(valid + '\n', '')))
        # A selected primary key may sign through a different subkey. Change
        # only the VALIDSIG signing-key field, preserving its primary identity.
        subkey = valid.replace(pin.FINGERPRINT, 'A' * 40, 1)
        self.assertTrue(pin.signed_by_release_key(status.replace(valid, subkey)))
        self.assertTrue(pin.signed_by_release_key('\r\n'.join(status.splitlines()) + '\r\n'))

    def test_verification_capture_digests(self):
        empty = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        zero = '9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa'
        expected = {
            'dearmor.stdout': (0, empty), 'dearmor.stderr': (0, empty), 'dearmor.exit': (2, zero),
            'signature.stdout': (382, '92fb6272050944cb16ef49d2693fa0ab29c869e5e19107bdf197352e474ef5a6'),
            'signature.stderr': (217, 'ea2578fb0a6dd908573d0c6b848a0112b7ac1271805165adcf6159fc319ccd7b'),
            'signature.exit': (2, zero), 'codesign.stdout': (0, empty),
            'codesign.stderr': (179, 'dbb465ef6079213b7e02121c6f60bda6e4f175dd705fcda236028f6ad5497e35'),
            'codesign.exit': (2, zero), 'codesign-refused.stdout': (0, empty),
            'codesign-refused.stderr': (144, 'd064cf2ee794341db368137bd2b3db5ef061e8395272920ea20d112d87f52ce8'),
            'codesign-refused.exit': (2, '4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865'),
        }
        for name, identity in expected.items():
            with self.subTest(name=name):
                raw = (FIXTURES / name).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), identity)

    def test_logged_verifier_preserves_captured_streams_and_refuses_failed_exit(self):
        # CompletedProcess is a supplied result, not fresh signature verification.
        # The exit-only comparison distinguishes failure propagation from prose.
        for name, exit_override in [('dearmor', None), ('signature', None), ('codesign', None),
                                    ('codesign', 1), ('codesign-refused', None)]:
            with self.subTest(name=name, exit_override=exit_override), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                stdout = (FIXTURES / (name + '.stdout')).read_bytes()
                stderr = (FIXTURES / (name + '.stderr')).read_bytes()
                code = int((FIXTURES / (name + '.exit')).read_bytes()) if exit_override is None else exit_override
                argv = ['/synthetic/verifier', 'public-input-only']
                result = subprocess.CompletedProcess(argv, code, stdout, stderr)
                with mock.patch.object(pin.subprocess, 'run', return_value=result) as launched:
                    if code:
                        with self.assertRaisesRegex(RuntimeError, 'failed \\(exit 1\\); inspect'):
                            pin.run_logged(out, 'verification', argv)
                    else:
                        self.assertEqual(pin.run_logged(out, 'verification', argv), stdout)
                launched.assert_called_once_with(argv, capture_output=True, timeout=90)
                self.assertEqual((out / 'verification.stdout').read_bytes(), stdout)
                self.assertEqual((out / 'verification.stderr').read_bytes(), stderr)
                self.assertEqual((out / 'verification.exit').read_bytes(), (str(code) + '\n').encode())

    def test_digest_changes_with_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "file"
            p.write_bytes(b"abc")
            self.assertEqual(pin.digest(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            p.write_bytes(b"abd")
            self.assertNotEqual(pin.digest(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main()
