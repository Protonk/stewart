"""Offline refusal controls for release-pin verification."""

import importlib.util
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("pin", Path(__file__).with_name("pin.py"))
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)


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
        status = "[GNUPG:] VALIDSIG %s 2026-11-10 1794340800 0 4 0 1 10 00\n" % pin.FINGERPRINT
        self.assertTrue(pin.signed_by_release_key(status))
        self.assertFalse(pin.signed_by_release_key(status.replace(pin.FINGERPRINT, "A" * 40)))
        self.assertFalse(pin.signed_by_release_key("[GNUPG:] GOODSIG " + pin.FINGERPRINT))
        self.assertTrue(pin.signed_by_release_key(status.replace(pin.FINGERPRINT, "A" * 40).strip() + " " + pin.FINGERPRINT))
        self.assertTrue(pin.signed_by_release_key("[GNUPG:] NEWSIG\n" + status))

    def test_digest_changes_with_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "file"
            p.write_bytes(b"abc")
            self.assertEqual(pin.digest(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            p.write_bytes(b"abd")
            self.assertNotEqual(pin.digest(p), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main()
