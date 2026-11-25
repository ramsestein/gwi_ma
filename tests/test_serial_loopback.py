import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pty_link import NullModem
from src.utils import serial_loopback as sl


class TestSerialLoopback(unittest.TestCase):

    def test_frames_cross_a_null_modem_intact(self):
        link = NullModem()
        try:
            results = sl.run_loopback(link.a.path, link.b.path, [9600, 57600], frames=20, size=16, both=True)
        finally:
            link.close()
        self.assertEqual([(r["baud"], r["direction"]) for r in results],
                         [(9600, "A->B"), (9600, "B->A"), (57600, "A->B"), (57600, "B->A")])
        for r in results:
            self.assertEqual((r["ok"], r["lost"], r["corrupt"]), (20, 0, 0))
            self.assertIn("lat_median_ms", r)
        # 2 magic + 4 header + 16 payload + 4 crc = 26 bytes, 10 bits each at 9600 baud
        self.assertAlmostEqual(results[0]["wire_ms"], 26 * 10 / 9600 * 1000, places=2)

    def test_corruption_is_detected(self):
        flip = lambda data: bytes([data[0] ^ 0xFF]) + data[1:]
        link = NullModem(mutate=flip)
        try:
            results = sl.run_loopback(link.a.path, link.b.path, [9600], frames=5, size=8)
        finally:
            link.close()
        self.assertEqual(results[0]["ok"], 0)
        self.assertEqual(results[0]["lost"] + results[0]["corrupt"], 5)

    def test_lost_frames_when_nothing_is_connected(self):
        link = NullModem(mutate=lambda data: b"")
        try:
            results = sl.run_loopback(link.a.path, link.b.path, [9600], frames=3, size=8, timeout=0.2)
        finally:
            link.close()
        self.assertEqual((results[0]["ok"], results[0]["lost"]), (0, 3))

    def test_cli_exit_code(self):
        link = NullModem()
        try:
            with redirect_stdout(io.StringIO()) as out:
                rc = sl.main([link.a.path, link.b.path, "--sweep", "9600,19200", "--frames", "5"])
        finally:
            link.close()
        self.assertEqual(rc, 0)
        self.assertIn("RESULT: OK", out.getvalue())

    def test_bits_per_char(self):
        self.assertEqual(sl.bits_per_char("8N1"), 10)
        self.assertEqual(sl.bits_per_char("7E2"), 11)


if __name__ == "__main__":
    unittest.main()
