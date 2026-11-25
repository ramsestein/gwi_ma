import csv
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pty_link import PtyPort
from src.acquisition import serial_tap as st


def wait_for(condition, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def read_rows(prefix):
    with open(prefix + "_timeline.csv", newline="") as f:
        return list(csv.DictReader(f))


class TestSerialTap(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prefix = os.path.join(self.tmp.name, "out", "session")
        self.ptys = []

    def tearDown(self):
        for p in self.ptys:
            p.close()
        self.tmp.cleanup()

    def pty(self):
        p = PtyPort()
        self.ptys.append(p)
        return p

    def test_tap_logs_both_directions_and_never_writes(self):
        bis, masimo = self.pty(), self.pty()
        specs = [st.PortSpec("BIS", bis.path, 9600), st.PortSpec("MASIMO", masimo.path, 9600)]
        cap = st.SerialCapture(specs, self.prefix, gap_ms=20)
        cap.start()

        bis.write(b"BIS 45 SQI 98\r\n")
        self.assertTrue(wait_for(lambda: cap.bytes_in["BIS"] == 15))
        time.sleep(0.1)
        cap.mark("sensor off")
        masimo.write(b"\x05")
        self.assertTrue(wait_for(lambda: cap.bytes_in["MASIMO"] == 1))
        time.sleep(0.1)
        summary = cap.stop()

        rows = read_rows(self.prefix)
        self.assertEqual([r["dir"] for r in rows], ["BIS", "EVENT", "MASIMO"])
        self.assertEqual(rows[0]["ascii"], "BIS 45 SQI 98..")
        self.assertEqual(rows[1]["note"], "sensor off")
        self.assertEqual(rows[2]["hex"], "05")
        self.assertLess(float(rows[0]["t_rel_s"]), float(rows[2]["t_rel_s"]))

        # Tap mode must not send anything to either device.
        self.assertEqual(bis.read(timeout=0.2), b"")
        self.assertEqual(masimo.read(timeout=0.2), b"")

        with open(self.prefix + "_BIS.bin", "rb") as f:
            self.assertEqual(f.read(), b"BIS 45 SQI 98\r\n")
        with open(self.prefix + "_summary.json") as f:
            saved = json.load(f)
        self.assertEqual(saved["mode"], "tap")
        self.assertEqual(saved["bytes"], {"BIS": 15, "MASIMO": 1})
        self.assertEqual(summary["events"], 1)

    def test_chunks_merge_within_gap_and_split_after_it(self):
        bis = self.pty()
        cap = st.SerialCapture([st.PortSpec("BIS", bis.path, 57600)], self.prefix, gap_ms=100)
        cap.start()
        bis.write(b"AB")
        time.sleep(0.02)
        bis.write(b"CD")              # within the gap: same message
        time.sleep(0.4)
        bis.write(b"EF")              # after the gap: new message
        self.assertTrue(wait_for(lambda: cap.bytes_in["BIS"] == 6))
        time.sleep(0.2)
        cap.stop()

        self.assertEqual([r["ascii"] for r in read_rows(self.prefix)], ["ABCD", "EF"])

    def test_bridge_forwards_both_ways(self):
        dev_a, dev_b = self.pty(), self.pty()
        specs = [st.PortSpec("VITALREC", dev_a.path, 57600), st.PortSpec("BIS", dev_b.path, 57600)]
        cap = st.SerialCapture(specs, self.prefix, bridge=True, gap_ms=20)
        cap.start()

        dev_a.write(b"\x02REQ\x03")
        self.assertEqual(dev_b.read_until(5), b"\x02REQ\x03")
        dev_b.write(b"\x02DATA\x03")
        self.assertEqual(dev_a.read_until(6), b"\x02DATA\x03")
        time.sleep(0.1)
        summary = cap.stop()

        rows = read_rows(self.prefix)
        self.assertEqual([(r["dir"], r["hex"]) for r in rows],
                         [("VITALREC", "02 52 45 51 03"), ("BIS", "02 44 41 54 41 03")])
        self.assertEqual(summary["mode"], "bridge")
        self.assertEqual(summary["forward_errors"], 0)

    def test_validation(self):
        p = self.pty()
        with self.assertRaises(ValueError):
            st.SerialCapture([st.PortSpec("A", p.path, 9600)], self.prefix, bridge=True)
        with self.assertRaises(ValueError):
            st.SerialCapture([st.PortSpec("A", p.path, 9600), st.PortSpec("A", p.path, 9600)], self.prefix)
        self.assertEqual(st.parse_format("7e1")[0], 7)
        with self.assertRaises(ValueError):
            st.parse_format("9N1")

    def test_cli_marks_events_and_writes_summary(self):
        bis = self.pty()
        bis.write(b"hello")
        with patch("builtins.input", side_effect=["", "impedance check", KeyboardInterrupt()]), \
             redirect_stdout(io.StringIO()) as out:
            rc = st.main([bis.path, "--baud", "9600", "--names", "BIS", "--prefix", self.prefix])
        self.assertEqual(rc, 0)
        self.assertIn("TAP (listen only", out.getvalue())
        with open(self.prefix + "_summary.json") as f:
            self.assertEqual(json.load(f)["events"], 1)
        self.assertIn("impedance check", [r["note"] for r in read_rows(self.prefix)])

    def test_cli_rejects_bad_port(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = st.main(["/dev/does-not-exist", "--baud", "9600", "--prefix", self.prefix])
        self.assertEqual(rc, 1)
        self.assertIn("Error opening ports", out.getvalue())


if __name__ == "__main__":
    unittest.main()
