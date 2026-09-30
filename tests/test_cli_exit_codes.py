"""CLI regression checks against a built dumper with RequireAnyKey disabled.

Usage: IL2CPP_DUMPER_EXE=/path/to/Il2CppDumper.exe python -m unittest discover -s tests
"""
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


class ExitCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = str(Path(os.environ["IL2CPP_DUMPER_EXE"]).resolve(strict=True))

    def run_cli(self, *args):
        return subprocess.run([self.exe, *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def test_help_succeeds(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)

    def test_too_many_arguments_fail(self):
        self.assertEqual(self.run_cli("a", "b", "c", "d").returncode, 2)

    def test_single_invalid_argument_fails_without_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli(Path(tmp) / "absent").returncode, 2)

    def test_missing_inputs_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent"
            self.assertEqual(self.run_cli(missing, missing).returncode, 2)

    def test_missing_metadata_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            binary.write_bytes(b"\x7fELF" + bytes(12))
            result = self.run_cli(binary, Path(tmp) / "absent")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Metadata file not found", result.stdout)

    def test_caught_parser_exception_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            metadata = Path(tmp) / "global-metadata.dat"
            binary.write_bytes(b"\x7fELF" + bytes(12))
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 32))
            result = self.run_cli(binary, metadata, tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("not a supported version[32]", result.stdout)
            self.assertFalse((Path(tmp) / "dump.cs").exists())


if __name__ == "__main__":
    unittest.main()
