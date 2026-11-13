#!/usr/bin/env python3
"""Offline controls for the literal binary-marker check; no service or model runs."""

import pathlib
import subprocess
import tempfile
import unittest


CHECK = pathlib.Path(__file__).resolve().with_name("check-build-markers.sh")


class MarkerChecks(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="stewart-markers-")
        self.addCleanup(self.work.cleanup)
        self.root = pathlib.Path(self.work.name)
        self.markers = self.root / "markers"
        self.binary = self.root / "binary"
        self.markers.write_bytes(b"development marker\nsecond[marker]\n")
        self.binary.write_bytes(b"\x00other bytes\x00development marker\x00second[marker]\xff")

    def check(self, mode, expected):
        result = subprocess.run(
            ["sh", str(CHECK), mode, str(self.markers), str(self.binary)],
            capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_presence_and_absence_controls(self):
        self.check("present", 0)
        self.check("absent", 1)
        self.binary.write_bytes(b"\x00unrelated release bytes\xff")
        self.check("absent", 0)
        self.check("present", 1)

    def test_one_missing_marker_fails(self):
        self.binary.write_bytes(b"development marker")
        self.check("present", 1)
        self.check("absent", 1)

    def test_matching_is_literal(self):
        self.binary.write_bytes(b"development marker secondm")
        self.check("present", 1)

    def test_unrelated_binary_changes_preserve_result(self):
        self.check("present", 0)
        self.binary.write_bytes(b"prefix\xff" + self.binary.read_bytes() + b"\x00suffix")
        self.check("present", 0)

    def test_no_final_newline_and_leading_dash(self):
        self.markers.write_bytes(b"-literal")
        self.binary.write_bytes(b"\x00-literal\x00")
        self.check("present", 0)

    def test_empty_list_refuses(self):
        self.markers.write_bytes(b"")
        self.check("absent", 2)
        self.check("present", 2)

    def test_blank_line_fails(self):
        self.markers.write_bytes(b"development marker\n\n")
        self.check("present", 1)

    def test_missing_inputs_refuse(self):
        original = self.binary.read_bytes()
        self.binary.unlink()
        self.assertIn(b"cannot read binary:", self.check("absent", 2).stderr)
        self.binary.write_bytes(original)
        self.markers.unlink()
        self.assertIn(b"cannot read marker list:", self.check("present", 2).stderr)


if __name__ == "__main__":
    unittest.main()
