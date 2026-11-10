"""Offline refusal controls for release-pin verification."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("pin", Path(__file__).with_name("pin.py"))
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)


class PinControls(unittest.TestCase):
    def test_manifest_version_and_checksum(self):
        obj = {"version": pin.VERSION, "platforms": {pin.PLATFORM: {"checksum": "a" * 64}}}
        self.assertEqual(pin.manifest_checksum(json.dumps(obj)), "a" * 64)
        obj["version"] = "different"
        with self.assertRaises(ValueError):
            pin.manifest_checksum(json.dumps(obj))
        obj["version"] = pin.VERSION
        obj["platforms"][pin.PLATFORM]["checksum"] = "invalid"
        with self.assertRaises(ValueError):
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
