import io
import os
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import serial_ports as sp


def port(device, vid, pid, serial_number=None, location=None, product="USB Serial"):
    return SimpleNamespace(device=device, vid=vid, pid=pid, serial_number=serial_number,
                           location=location, product=product, description=product)


FTDI_A = port("/dev/ttyUSB0", 0x0403, 0x6001, "A10K1ZXY", "1-1.2:1.0")
FTDI_B = port("/dev/ttyUSB1", 0x0403, 0x6001, "A10K2QRS", "1-1.3:1.0")
CH340 = port("/dev/ttyUSB2", 0x1A86, 0x7523, None, "1-1.4:1.0")
BUILTIN = port("/dev/ttyAMA0", None, None)
ALL = [FTDI_A, FTDI_B, CH340, BUILTIN]


class TestSerialPorts(unittest.TestCase):

    def test_list_skips_non_usb_ports(self):
        self.assertEqual([p.device for p in sp.list_adapters(ALL)],
                         ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"])

    def test_rules_by_serial_and_by_socket(self):
        rules = sp.build_rules({"BIS": "/dev/ttyUSB0", "MASIMO": "/dev/ttyUSB1",
                                "RESEARCH": "/dev/ttyUSB2"}, ALL)
        self.assertIn('ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", '
                      'ATTRS{serial}=="A10K1ZXY", SYMLINK+="ttyBIS"', rules)
        self.assertIn('ATTRS{serial}=="A10K2QRS", SYMLINK+="ttyMASIMO"', rules)
        self.assertIn('SUBSYSTEM=="tty", KERNELS=="1-1.4:1.0", SYMLINK+="ttyRESEARCH"', rules)
        self.assertIn("always plug it into the same socket", rules)
        self.assertIn('ATTR{latency_timer}="1"', rules)

    def test_duplicate_serial_falls_back_to_socket(self):
        clone_a = port("/dev/ttyUSB0", 0x067B, 0x2303, "0123456", "1-1.2:1.0")
        clone_b = port("/dev/ttyUSB1", 0x067B, 0x2303, "0123456", "1-1.3:1.0")
        rules = sp.build_rules({"BIS": "/dev/ttyUSB0"}, [clone_a, clone_b])
        self.assertIn('KERNELS=="1-1.2:1.0", SYMLINK+="ttyBIS"', rules)
        self.assertNotIn("latency_timer", rules)

    def test_unknown_device_and_bad_role(self):
        with self.assertRaises(ValueError):
            sp.build_rules({"BIS": "/dev/ttyUSB9"}, ALL)
        with self.assertRaises(ValueError):
            sp.build_rules({"BIS-1": "/dev/ttyUSB0"}, ALL)

    def test_cli(self):
        with patch("serial.tools.list_ports.comports", return_value=ALL):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sp.main([]), 0)
            self.assertIn("0403:6001  serial=A10K1ZXY", out.getvalue())

            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sp.main(["--udev", "BIS=/dev/ttyUSB0"]), 0)
            self.assertTrue(out.getvalue().startswith("# Fixed names"))

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                self.assertEqual(sp.main(["--udev", "BIS=/dev/ttyUSB7"]), 1)
            self.assertIn("not a connected USB-serial adapter", err.getvalue())


if __name__ == "__main__":
    unittest.main()
