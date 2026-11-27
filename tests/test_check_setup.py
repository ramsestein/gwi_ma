import importlib.metadata
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import check_setup as cs

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def levels(results):
    return [level for level, _ in results]


class TestCheckSetup(unittest.TestCase):

    def test_python_version(self):
        self.assertEqual(levels(cs.check_python((3, 13, 5))), ["OK"])
        self.assertEqual(levels(cs.check_python((3, 8, 10))), ["FAIL"])

    def test_repo_root(self):
        self.assertEqual(levels(cs.check_repo(REPO)), ["OK"])
        self.assertEqual(levels(cs.check_repo(os.path.join(REPO, "docs"))), ["FAIL"])

    def test_packages_by_role(self):
        installed = {"pyserial": "3.5", "numpy": "2.1.0"}

        def version_of(name):
            if name in installed:
                return installed[name]
            raise importlib.metadata.PackageNotFoundError(name)

        pc = dict(zip([n for n, _ in cs.PC_PACKAGES], cs.check_packages("pc", version_of)))
        self.assertEqual(pc["pyserial"][0], "OK")
        self.assertEqual(pc["scipy"][0], "FAIL")
        self.assertEqual(pc["vitaldb"][0], "WARN")          # optional for now
        self.assertEqual(levels(cs.check_packages("pi", version_of)), ["OK"])

    def test_ports(self):
        self.assertEqual(levels(cs.check_ports([])), ["WARN"])
        ftdi = SimpleNamespace(device="COM3", vid=0x0403, pid=0x6001, serial_number="A10K1ZXY",
                               description="USB Serial Port (COM3)")
        prolific = SimpleNamespace(device="COM4", vid=0x067B, pid=0x2303, serial_number=None,
                                   description="Prolific USB-to-Serial Comm Port (COM4)")
        builtin = SimpleNamespace(device="COM1", vid=None, pid=None)
        results = cs.check_ports([builtin, ftdi, prolific])
        self.assertEqual(levels(results), ["OK", "OK", "WARN"])
        self.assertIn("COM3: 0403:6001 FTDI, serial A10K1ZXY", results[0][1])

    def test_windows_apps(self):
        env = {"ProgramFiles": r"C:\PF", "ProgramFiles(x86)": r"C:\PF86", "LOCALAPPDATA": r"C:\Users\u\AppData\Local"}
        files = {os.path.join(r"C:\PF", "Wireshark", "Wireshark.exe"),
                 os.path.join(r"C:\PF", "Wireshark", "extcap", "USBPcapCMD.exe")}
        dirs = {r"C:\PF", r"C:\PF86", os.path.join(r"C:\PF86", "Vital Recorder")}
        listing = {r"C:\PF": ["Wireshark"], r"C:\PF86": ["Vital Recorder"]}

        results = cs.check_windows_apps(env, isfile=files.__contains__, isdir=dirs.__contains__,
                                        listdir=lambda d: listing.get(d, []))
        self.assertEqual(levels(results), ["OK", "OK", "OK"])
        self.assertIn("Vital Recorder", results[2][1])

        missing = cs.check_windows_apps(env, isfile=lambda p: False, isdir=lambda p: False, listdir=lambda d: [])
        self.assertEqual(levels(missing), ["FAIL", "FAIL", "WARN"])

    def test_linux_serial_access(self):
        self.assertEqual(levels(cs.check_linux_serial_access(["admin", "dialout"], False)), ["OK"])
        self.assertEqual(levels(cs.check_linux_serial_access(["admin"], False)), ["FAIL"])
        self.assertEqual(levels(cs.check_linux_serial_access([], True)), ["OK"])

    def test_default_role(self):
        self.assertEqual(cs.default_role("Linux", "aarch64"), "pi")
        self.assertEqual(cs.default_role("Linux", "x86_64"), "pc")
        self.assertEqual(cs.default_role("Windows", "AMD64"), "pc")

    def test_main_runs_here(self):
        with patch("serial.tools.list_ports.comports", return_value=[]), \
             redirect_stdout(io.StringIO()) as out:
            cwd = os.getcwd()
            os.chdir(REPO)
            try:
                rc = cs.main(["--role", "pi"])
            finally:
                os.chdir(cwd)
        self.assertIn("[OK] pyserial", out.getvalue())
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
