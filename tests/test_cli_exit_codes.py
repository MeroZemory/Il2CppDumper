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
                              text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL,
                              creationflags=(subprocess.CREATE_NO_WINDOW |
                                             subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0)

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

    def test_short_executable_inputs_fail_without_unhandled_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            metadata = Path(tmp) / "global-metadata.dat"
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 32))
            for length in range(4):
                with self.subTest(bytes=length):
                    binary.write_bytes(bytes(length))
                    result = self.run_cli(binary, metadata, tmp)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("too short", result.stdout)
                    self.assertNotIn("Exception", result.stdout + result.stderr)
                    self.assertFalse((Path(tmp) / "dump.cs").exists())

    def test_short_metadata_inputs_fail_without_unhandled_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            metadata = Path(tmp) / "global-metadata.dat"
            binary.write_bytes(b"\x7fELF" + bytes(12))
            for length in range(4):
                with self.subTest(bytes=length):
                    metadata.write_bytes(bytes(length))
                    result = self.run_cli(binary, metadata, tmp)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("too short", result.stdout)
                    self.assertNotIn("Exception", result.stdout + result.stderr)
                    self.assertFalse((Path(tmp) / "dump.cs").exists())

    @unittest.skipUnless(os.name == "nt", "Windows exclusive file lock fixture")
    def test_input_read_error_returns_failure_without_unhandled_exception(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "binary"
            metadata = Path(tmp) / "global-metadata.dat"
            binary.write_bytes(b"\x7fELF" + bytes(12))
            metadata.write_bytes(struct.pack("<II", 0xFAB11BAF, 32))
            # GENERIC_READ, no sharing, OPEN_EXISTING: File.Exists still succeeds,
            # while the dumper's File.ReadAllBytes must raise an IOException.
            handle = kernel.CreateFileW(str(binary), 0x80000000, 0, None, 3, 0, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                result = self.run_cli(binary, metadata, tmp)
            finally:
                kernel.CloseHandle(handle)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Cannot read input file", result.stdout)
            self.assertNotIn("Exception", result.stdout + result.stderr)
            self.assertFalse((Path(tmp) / "dump.cs").exists())


if __name__ == "__main__":
    unittest.main()
