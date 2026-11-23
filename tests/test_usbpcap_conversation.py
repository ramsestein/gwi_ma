import csv
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.acquisition import usbpcap_conversation as uc

COMPLETION = 1
SUBMIT = 0


def usbpcap(irp, info, bus, dev, ep, xfer, data=b"", stage=None, status=0):
    header_len = 28 if xfer == uc.XFER_CONTROL else 27
    header = struct.pack("<HQIHBHHBBI", header_len, irp, status, 0, info, bus, dev, ep, xfer, len(data))
    if xfer == uc.XFER_CONTROL:
        header += bytes([stage if stage is not None else 0])
    return header + data


def control(irp, bus, dev, ts, setup, out_data=b"", in_data=b""):
    """USBPcap-style control transfer: SETUP, optional DATA stages, COMPLETE."""
    pkts = [(ts, usbpcap(irp, SUBMIT, bus, dev, 0x00, uc.XFER_CONTROL, setup, uc.STAGE_SETUP))]
    if out_data:
        pkts.append((ts, usbpcap(irp, SUBMIT, bus, dev, 0x00, uc.XFER_CONTROL, out_data, uc.STAGE_DATA)))
    if in_data:
        pkts.append((ts + 0.0001, usbpcap(irp, COMPLETION, bus, dev, 0x80, uc.XFER_CONTROL, in_data, uc.STAGE_DATA)))
    pkts.append((ts + 0.0002, usbpcap(irp, COMPLETION, bus, dev, 0x00, uc.XFER_CONTROL, b"", uc.STAGE_COMPLETE)))
    return pkts


def bulk_out(irp, bus, dev, ts, data, ep=0x02):
    return [(ts, usbpcap(irp, SUBMIT, bus, dev, ep, uc.XFER_BULK, data)),
            (ts + 0.0001, usbpcap(irp, COMPLETION, bus, dev, ep, uc.XFER_BULK))]


def bulk_in(irp, bus, dev, ts, data, ep=0x83):
    return [(ts - 0.5, usbpcap(irp, SUBMIT, bus, dev, ep, uc.XFER_BULK)),
            (ts, usbpcap(irp, COMPLETION, bus, dev, ep, uc.XFER_BULK, data))]


def setup_packet(request_type, request, value=0, index=0, length=0):
    return struct.pack("<BBHHH", request_type, request, value, index, length)


def pcapng(packets):
    def block(btype, body):
        pad = (4 - len(body) % 4) % 4
        total = 12 + len(body) + pad
        return struct.pack("<II", btype, total) + body + b"\0" * pad + struct.pack("<I", total)

    out = block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += block(1, struct.pack("<HHI", uc.LINKTYPE_USBPCAP, 0, 65535))
    for ts, pkt in sorted(packets, key=lambda p: p[0]):
        micros = int(round(ts * 1e6))
        out += block(6, struct.pack("<IIIII", 0, micros >> 32, micros & 0xFFFFFFFF, len(pkt), len(pkt)) + pkt)
    return out


def pcap(packets):
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, uc.LINKTYPE_USBPCAP)
    for ts, pkt in sorted(packets, key=lambda p: p[0]):
        sec = int(ts)
        usec = int(round((ts - sec) * 1e6))
        out += struct.pack("<IIII", sec, usec, len(pkt), len(pkt)) + pkt
    return out


def prolific_session():
    """A PL2303 adapter (bus 1, addr 5) next to a mouse (bus 1, addr 2)."""
    bus, dev = 1, 5
    descriptor = bytes([18, 1, 0x10, 0x01, 0, 0, 0, 64]) + struct.pack("<HH", 0x067B, 0x2303) + bytes(6)
    pkts = []
    pkts += control(1, bus, dev, 1000.000, setup_packet(0x80, 0x06, 0x0100, 0, 18), in_data=descriptor)
    pkts += control(2, bus, dev, 1000.010, setup_packet(0x21, 0x20, 0, 0, 7),
                    out_data=struct.pack("<IBBB", 57600, 0, 0, 8))
    pkts += control(3, bus, dev, 1000.020, setup_packet(0x21, 0x22, 0x0003))
    pkts += bulk_out(4, bus, dev, 1000.100, b"\x02\x01\x00\x03")
    pkts += bulk_in(5, bus, dev, 1000.120, b"\xaa\x55\x10")
    pkts += bulk_in(6, bus, dev, 1000.122, b"\x11\x12")          # same reply, 2 ms later -> merged
    pkts += bulk_out(7, bus, dev, 1000.200, b"\x02\x02\x00\x03")
    pkts += bulk_in(8, bus, dev, 1000.250, b"OK\r\n")
    # A mouse on the same bus: interrupt data plus a tiny bulk transfer.
    pkts.append((1000.050, usbpcap(20, COMPLETION, 1, 2, 0x81, uc.XFER_INTERRUPT, b"\x00\x01\x00")))
    pkts += bulk_out(21, 1, 2, 1000.060, b"\x01")
    return pkts


class TestUsbpcapConversation(unittest.TestCase):

    def test_prolific_conversation(self):
        conv = uc.extract_conversation(pcapng(prolific_session()))
        s = conv.summary

        self.assertEqual(s["selected_device"], {"iface": 0, "bus": 1, "address": 5})
        dev = next(d for d in s["devices"] if d["address"] == 5)
        self.assertEqual(dev["vid_pid"], "067B:2303")
        self.assertEqual(s["line_settings"], {"baudrate": 57600, "format": "8N1", "dtr": 1, "rts": 1})
        self.assertFalse(s["ftdi"]["detected"])

        self.assertEqual(conv.h2d, b"\x02\x01\x00\x03\x02\x02\x00\x03")
        self.assertEqual(conv.d2h, b"\xaa\x55\x10\x11\x12OK\r\n")

        flow = [(m.direction, m.data) for m in conv.messages if m.direction != "CTRL"]
        self.assertEqual(flow, [
            ("H2D", b"\x02\x01\x00\x03"),
            ("D2H", b"\xaa\x55\x10\x11\x12"),
            ("H2D", b"\x02\x02\x00\x03"),
            ("D2H", b"OK\r\n"),
        ])
        notes = [m.note for m in conv.messages if m.direction == "CTRL"]
        self.assertEqual(notes, ["SET_LINE_CODING 57600 8N1", "SET_CONTROL_LINE_STATE DTR=1 RTS=1"])

    def test_pcap_and_pcapng_agree(self):
        a = uc.extract_conversation(pcapng(prolific_session()))
        b = uc.extract_conversation(pcap(prolific_session()))
        self.assertEqual((a.h2d, a.d2h), (b.h2d, b.d2h))
        self.assertEqual(a.summary["line_settings"], b.summary["line_settings"])

    def test_device_selection(self):
        conv = uc.extract_conversation(pcapng(prolific_session()), device="1:2")
        self.assertEqual(conv.summary["selected_device"]["address"], 2)
        self.assertEqual(conv.h2d, b"\x01")
        with self.assertRaises(ValueError):
            uc.extract_conversation(pcapng(prolific_session()), device="1:9")

    def test_ftdi_status_bytes_detected_and_stripped(self):
        bus, dev = 2, 7
        pkts = []
        pkts += control(1, bus, dev, 10.0, setup_packet(0x40, 0x03, 0x4138, 0))   # 9600
        pkts += control(2, bus, dev, 10.01, setup_packet(0x40, 0x04, 0x0008))     # 8N1
        irp = 10
        t = 10.1
        expected = b""
        for i in range(30):
            # Idle polls return only the 2 status bytes.
            pkts += bulk_in(irp, bus, dev, t, b"\x01\x60", ep=0x81)
            irp += 1
            t += 0.016
            if i % 3 == 0:
                payload = bytes([0x80 | i, i, 0x0D])
                pkts += bulk_in(irp, bus, dev, t, b"\x31\x60" + payload, ep=0x81)
                expected += payload
                irp += 1
                t += 0.016
        # One 64+ byte transfer: status bytes repeat every 64-byte packet.
        big = bytes(range(62)) + bytes(range(100, 110))
        pkts += bulk_in(irp, bus, dev, t + 1, b"\x01\x60" + big[:62] + b"\x01\x60" + big[62:], ep=0x81)
        expected += big

        conv = uc.extract_conversation(pcapng(pkts), gap_ms=1)
        self.assertTrue(conv.summary["ftdi"]["detected"])
        self.assertEqual(conv.summary["ftdi"]["reason"], "status-byte pattern")
        self.assertEqual(conv.d2h, expected)
        self.assertEqual(conv.summary["line_settings"], {"baudrate": 9600, "format": "8N1"})

        raw = uc.extract_conversation(pcapng(pkts), ftdi="off")
        self.assertTrue(raw.d2h.startswith(b"\x01\x60"))

    def test_ftdi_baud_decoding(self):
        self.assertAlmostEqual(uc._ftdi_baud(0x4138, 0), 9600, places=3)
        self.assertLess(abs(uc._ftdi_baud(0xC034, 0) - 57600) / 57600, 0.005)
        self.assertEqual(uc._ftdi_baud(0x001A, 0), 3_000_000 / 26)      # 115200 approx
        self.assertEqual(uc._ftdi_baud(0, 0), 3_000_000)

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = os.path.join(tmp, "vitalrecorder_bis.pcapng")
            with open(cap, "wb") as f:
                f.write(pcapng(prolific_session()))
            prefix = os.path.join(tmp, "out", "bis")
            with redirect_stdout(io.StringIO()) as out:
                rc = uc.main([cap, prefix, "--show", "5"])
            self.assertEqual(rc, 0)
            self.assertIn("SET_LINE_CODING 57600 8N1", out.getvalue())

            with open(prefix + "_H2D.bin", "rb") as f:
                self.assertEqual(f.read(), b"\x02\x01\x00\x03\x02\x02\x00\x03")
            with open(prefix + "_timeline.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["dir"] for r in rows], ["CTRL", "CTRL", "H2D", "D2H", "H2D", "D2H"])
            self.assertEqual(rows[3]["hex"], "aa 55 10 11 12")
            with open(prefix + "_summary.json") as f:
                summary = json.load(f)
            self.assertEqual(summary["line_settings"]["baudrate"], 57600)

    def test_rejects_non_capture(self):
        with self.assertRaises(ValueError):
            uc.extract_conversation(b"not a capture at all")


if __name__ == "__main__":
    unittest.main()
