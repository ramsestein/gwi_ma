"""
USBPcap conversation extractor.

Rebuilds the ordered, timestamped serial conversation between a PC application
(e.g. VitalRecorder) and a USB-serial adapter from a Wireshark/USBPcap capture
(.pcapng or .pcap, link type 249). It also decodes the adapter's line settings
(baud rate, data bits, parity, stop bits, DTR/RTS, flow control) from the USB
control transfers, so you learn how the application configures the port.

Unlike pcap_extractor.py (one blob per endpoint), this keeps who said what and
when, which is what you need to learn a request/response protocol.

Outputs, for a given prefix:
  <prefix>_timeline.csv   one row per message: t_rel_s, dir, nbytes, hex, ascii, note
  <prefix>_H2D.bin        host -> device bytes (what the PC application sent)
  <prefix>_D2H.bin        device -> host bytes (what the monitor answered)
  <prefix>_summary.json   devices seen, selected device, line settings, FTDI handling

The .bin files can be fed to the rest of the toolkit (framing_scanner,
packet_finder, checksum_cracker...).

Usage:
  python -m src.acquisition.usbpcap_conversation capture.pcapng [prefix]
      [--device [IFACE:]BUS:ADDR] [--ftdi auto|on|off] [--ftdi-packet 64]
      [--gap-ms 5] [--show 40]

Notes:
  - Timestamps are taken on the PC side of the USB bus. Adapters buffer
    received bytes (FTDI flushes every 16 ms by default), so device->host
    timing is only accurate to a few milliseconds.
  - FTDI adapters prefix every IN packet with 2 status bytes. They are removed
    automatically when the adapter is detected (by VID 0x0403 or by pattern).
"""
import argparse
import csv
import json
import os
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

LINKTYPE_USBPCAP = 249

XFER_ISOCHRONOUS = 0
XFER_INTERRUPT = 1
XFER_CONTROL = 2
XFER_BULK = 3

STAGE_SETUP = 0
STAGE_DATA = 1
STAGE_STATUS = 2
STAGE_COMPLETE = 3

USB_VENDORS = {
    0x0403: "FTDI",
    0x067B: "Prolific (PL2303)",
    0x0557: "ATEN",
    0x10C4: "Silicon Labs (CP210x)",
    0x1A86: "WCH (CH340/CH341)",
    0x2341: "Arduino",
}

PARITY_NAMES = {0: "N", 1: "O", 2: "E", 3: "M", 4: "S"}
CDC_STOP_NAMES = {0: "1", 1: "1.5", 2: "2"}
FTDI_FRACTIONS = [0.0, 0.5, 0.25, 0.125, 0.375, 0.625, 0.75, 0.875]


# --------------------------------------------------------------------------
# Capture file readers
# --------------------------------------------------------------------------

def _tsresol_to_seconds(value: int) -> float:
    if value & 0x80:
        return 2.0 ** -(value & 0x7F)
    return 10.0 ** -value


def _iter_pcapng(raw: bytes) -> Iterator[Tuple[int, float, bytes]]:
    pos = 0
    endian = "<"
    linktypes: List[int] = []
    resolutions: List[float] = []

    while pos + 12 <= len(raw):
        block_type = struct.unpack_from(endian + "I", raw, pos)[0]

        if block_type == 0x0A0D0D0A:  # Section Header Block
            bom = raw[pos + 8:pos + 12]
            endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            linktypes, resolutions = [], []

        block_len = struct.unpack_from(endian + "I", raw, pos + 4)[0]
        if block_len < 12 or pos + block_len > len(raw):
            break
        body = raw[pos + 8:pos + block_len - 4]

        if block_type == 1:  # Interface Description Block
            linktype = struct.unpack_from(endian + "H", body, 0)[0]
            resolution = 1e-6
            opt = 8
            while opt + 4 <= len(body):
                code, length = struct.unpack_from(endian + "HH", body, opt)
                if code == 0:
                    break
                if code == 9 and length >= 1:  # if_tsresol
                    resolution = _tsresol_to_seconds(body[opt + 4])
                opt += 4 + length + ((4 - length % 4) % 4)
            linktypes.append(linktype)
            resolutions.append(resolution)

        elif block_type == 6:  # Enhanced Packet Block
            iface, ts_high, ts_low, cap_len = struct.unpack_from(endian + "IIII", body, 0)
            if iface < len(linktypes) and linktypes[iface] == LINKTYPE_USBPCAP:
                ts = ((ts_high << 32) | ts_low) * resolutions[iface]
                yield iface, ts, body[20:20 + cap_len]

        pos += block_len


def _iter_pcap(raw: bytes) -> Iterator[Tuple[int, float, bytes]]:
    magic = raw[:4]
    formats = {
        b"\xd4\xc3\xb2\xa1": ("<", 1e-6),
        b"\xa1\xb2\xc3\xd4": (">", 1e-6),
        b"\x4d\x3c\xb2\xa1": ("<", 1e-9),
        b"\xa1\xb2\x3c\x4d": (">", 1e-9),
    }
    endian, frac = formats[magic]
    linktype = struct.unpack_from(endian + "I", raw, 20)[0] & 0x0FFFFFFF
    if linktype != LINKTYPE_USBPCAP:
        raise ValueError(f"pcap link type is {linktype}, expected USBPcap ({LINKTYPE_USBPCAP})")

    pos = 24
    while pos + 16 <= len(raw):
        ts_sec, ts_frac, incl_len, _ = struct.unpack_from(endian + "IIII", raw, pos)
        pos += 16
        yield 0, ts_sec + ts_frac * frac, raw[pos:pos + incl_len]
        pos += incl_len


def iter_capture(raw: bytes) -> Iterator[Tuple[int, float, bytes]]:
    """Yield (interface_id, timestamp_seconds, usbpcap_packet) for each packet."""
    if raw[:4] == b"\x0a\x0d\x0d\x0a":
        return _iter_pcapng(raw)
    if raw[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        return _iter_pcap(raw)
    raise ValueError("Not a pcap/pcapng file")


# --------------------------------------------------------------------------
# USBPcap records
# --------------------------------------------------------------------------

@dataclass
class UrbRecord:
    ts: float
    iface: int
    irp_id: int
    status: int
    info: int
    bus: int
    device: int
    endpoint: int
    transfer: int
    stage: Optional[int]
    data: bytes

    @property
    def is_completion(self) -> bool:
        return bool(self.info & 0x01)

    @property
    def key(self) -> Tuple[int, int, int]:
        return (self.iface, self.bus, self.device)


def parse_usbpcap(iface: int, ts: float, pkt: bytes) -> Optional[UrbRecord]:
    if len(pkt) < 27:
        return None
    header_len = struct.unpack_from("<H", pkt, 0)[0]
    irp_id = struct.unpack_from("<Q", pkt, 2)[0]
    status = struct.unpack_from("<I", pkt, 10)[0]
    info = pkt[16]
    bus = struct.unpack_from("<H", pkt, 17)[0]
    device = struct.unpack_from("<H", pkt, 19)[0]
    endpoint = pkt[21]
    transfer = pkt[22]
    data_len = struct.unpack_from("<I", pkt, 23)[0]
    stage = pkt[27] if transfer == XFER_CONTROL and header_len >= 28 and len(pkt) >= 28 else None
    data = pkt[header_len:header_len + data_len]
    return UrbRecord(ts, iface, irp_id, status, info, bus, device, endpoint, transfer, stage, data)


# --------------------------------------------------------------------------
# Control transfers: line settings
# --------------------------------------------------------------------------

@dataclass
class ControlTransfer:
    ts: float
    key: Tuple[int, int, int]
    setup: bytes
    out_data: bytes = b""
    in_data: bytes = b""

    @property
    def request_type(self) -> int:
        return self.setup[0]

    @property
    def request(self) -> int:
        return self.setup[1]

    @property
    def value(self) -> int:
        return struct.unpack_from("<H", self.setup, 2)[0]

    @property
    def index(self) -> int:
        return struct.unpack_from("<H", self.setup, 4)[0]


def collect_control_transfers(records: List[UrbRecord]) -> List[ControlTransfer]:
    pending: Dict[Tuple[Tuple[int, int, int], int], ControlTransfer] = {}
    done: List[ControlTransfer] = []

    for rec in records:
        if rec.transfer != XFER_CONTROL:
            continue
        slot = (rec.key, rec.irp_id)
        if rec.stage == STAGE_SETUP and not rec.is_completion and len(rec.data) >= 8:
            if slot in pending:
                done.append(pending.pop(slot))
            ctl = ControlTransfer(rec.ts, rec.key, rec.data[:8], out_data=rec.data[8:])
            pending[slot] = ctl
        elif slot in pending:
            ctl = pending[slot]
            if rec.stage == STAGE_DATA and rec.data:
                if rec.is_completion:
                    ctl.in_data += rec.data
                else:
                    ctl.out_data += rec.data
            elif rec.stage == STAGE_COMPLETE or (rec.stage is None and rec.is_completion):
                if rec.data and ctl.request_type & 0x80:
                    ctl.in_data += rec.data
                done.append(pending.pop(slot))

    done.extend(pending.values())
    done.sort(key=lambda c: c.ts)
    return done


def _ftdi_baud(value: int, index: int) -> float:
    divisor = value & 0x3FFF
    frac_code = ((value >> 14) & 0x03) | ((index & 0x01) << 2)
    base = 12_000_000 if index & 0x0200 else 3_000_000
    if divisor == 0 and frac_code == 0:
        return float(base)
    if divisor == 1 and frac_code == 0:
        return base * 2 / 3
    return base / (divisor + FTDI_FRACTIONS[frac_code])


def describe_control(ctl: ControlTransfer) -> Optional[Tuple[str, dict]]:
    """Return (description, settings_update) for serial-relevant requests."""
    rt, req, val, idx = ctl.request_type, ctl.request, ctl.value, ctl.index

    # CDC ACM / Prolific PL2303 (class requests)
    if rt == 0x21 and req == 0x20 and len(ctl.out_data) >= 7:
        baud, stop, parity, bits = struct.unpack_from("<IBBB", ctl.out_data, 0)
        fmt = f"{bits}{PARITY_NAMES.get(parity, '?')}{CDC_STOP_NAMES.get(stop, '?')}"
        return (f"SET_LINE_CODING {baud} {fmt}",
                {"baudrate": baud, "format": fmt})
    if rt == 0xA1 and req == 0x21 and len(ctl.in_data) >= 7:
        baud, stop, parity, bits = struct.unpack_from("<IBBB", ctl.in_data, 0)
        fmt = f"{bits}{PARITY_NAMES.get(parity, '?')}{CDC_STOP_NAMES.get(stop, '?')}"
        return (f"GET_LINE_CODING {baud} {fmt}", {})
    if rt == 0x21 and req == 0x22:
        dtr, rts = val & 1, (val >> 1) & 1
        return (f"SET_CONTROL_LINE_STATE DTR={dtr} RTS={rts}", {"dtr": dtr, "rts": rts})
    if rt == 0x21 and req == 0x23:
        return (f"SEND_BREAK {val} ms", {})

    # FTDI (vendor requests to the device)
    if rt == 0x40 and req == 0x03:
        baud = _ftdi_baud(val, idx)
        return (f"FTDI SET_BAUDRATE ~{baud:.0f} (wValue=0x{val:04X} wIndex=0x{idx:04X})",
                {"baudrate": round(baud)})
    if rt == 0x40 and req == 0x04:
        bits = val & 0xFF
        parity = (val >> 8) & 0x07
        stop = {0: "1", 1: "1.5", 2: "2"}.get((val >> 11) & 0x07, "?")
        brk = " BREAK" if val & 0x4000 else ""
        fmt = f"{bits}{PARITY_NAMES.get(parity, '?')}{stop}"
        return (f"FTDI SET_DATA {fmt}{brk}", {"format": fmt})
    if rt == 0x40 and req == 0x02:
        mode = idx >> 8
        names = [n for bit, n in ((1, "RTS/CTS"), (2, "DTR/DSR"), (4, "XON/XOFF")) if mode & bit]
        flow = "+".join(names) or "none"
        return (f"FTDI SET_FLOW_CTRL {flow}", {"flow_control": flow})
    if rt == 0x40 and req == 0x01:
        parts = []
        if val & 0x0100:
            parts.append(f"DTR={val & 1}")
        if val & 0x0200:
            parts.append(f"RTS={(val >> 1) & 1}")
        update = {}
        if val & 0x0100:
            update["dtr"] = val & 1
        if val & 0x0200:
            update["rts"] = (val >> 1) & 1
        return (f"FTDI SET_MODEM_CTRL {' '.join(parts) or 'no change'}", update)
    if rt == 0x40 and req == 0x09:
        return (f"FTDI SET_LATENCY_TIMER {val & 0xFF} ms", {"ftdi_latency_ms": val & 0xFF})

    # Silicon Labs CP210x (vendor requests to the interface)
    if rt == 0x41 and req == 0x1E and len(ctl.out_data) >= 4:
        baud = struct.unpack_from("<I", ctl.out_data, 0)[0]
        return (f"CP210x SET_BAUDRATE {baud}", {"baudrate": baud})
    if rt == 0x41 and req == 0x03:
        stop = {0: "1", 1: "1.5", 2: "2"}.get(val & 0x0F, "?")
        parity = PARITY_NAMES.get((val >> 4) & 0x0F, "?")
        bits = (val >> 8) & 0xFF
        fmt = f"{bits}{parity}{stop}"
        return (f"CP210x SET_LINE_CTL {fmt}", {"format": fmt})
    if rt == 0x41 and req == 0x07:
        parts = []
        update = {}
        if val & 0x0100:
            parts.append(f"DTR={val & 1}")
            update["dtr"] = val & 1
        if val & 0x0200:
            parts.append(f"RTS={(val >> 1) & 1}")
            update["rts"] = (val >> 1) & 1
        return (f"CP210x SET_MHS {' '.join(parts) or 'no change'}", update)

    # WCH CH340: register writes, reported raw
    if rt == 0x40 and req in (0x9A, 0xA1, 0xA4):
        return (f"CH34x vendor 0x{req:02X} wValue=0x{val:04X} wIndex=0x{idx:04X}", {})

    return None


def device_descriptor_ids(controls: List[ControlTransfer]) -> Dict[Tuple[int, int, int], Tuple[int, int]]:
    ids = {}
    for ctl in controls:
        if ctl.request_type == 0x80 and ctl.request == 0x06 and (ctl.value >> 8) == 1:
            d = ctl.in_data
            if len(d) >= 12 and d[1] == 0x01:
                ids[ctl.key] = struct.unpack_from("<HH", d, 8)
    return ids


# --------------------------------------------------------------------------
# Bulk data
# --------------------------------------------------------------------------

@dataclass
class Chunk:
    ts: float
    direction: str  # "H2D" or "D2H"
    data: bytes


def bulk_chunks(records: List[UrbRecord], key: Tuple[int, int, int]) -> List[Chunk]:
    chunks = []
    for rec in records:
        if rec.key != key or rec.transfer != XFER_BULK or not rec.data:
            continue
        if rec.endpoint & 0x80:
            if rec.is_completion:
                chunks.append(Chunk(rec.ts, "D2H", rec.data))
        elif not rec.is_completion:
            chunks.append(Chunk(rec.ts, "H2D", rec.data))
    return chunks


def looks_like_ftdi(chunks: List[Chunk]) -> bool:
    ins = [c.data for c in chunks if c.direction == "D2H"]
    if len(ins) < 10:
        return False
    status_like = sum(1 for d in ins if len(d) >= 2 and (d[0] & 0x0F) == 0x01)
    status_only = sum(1 for d in ins if len(d) == 2)
    return status_like >= 0.95 * len(ins) and status_only >= 0.2 * len(ins)


def strip_ftdi_status(chunks: List[Chunk], packet_size: int) -> List[Chunk]:
    out = []
    for c in chunks:
        if c.direction != "D2H":
            out.append(c)
            continue
        payload = b"".join(c.data[i + 2:i + packet_size] for i in range(0, len(c.data), packet_size))
        if payload:
            out.append(Chunk(c.ts, c.direction, payload))
    return out


@dataclass
class Message:
    ts: float
    direction: str
    data: bytes = b""
    note: str = ""


def group_messages(chunks: List[Chunk], gap_s: float) -> List[Message]:
    messages: List[Message] = []
    last_ts: Dict[str, float] = {}
    for c in chunks:
        prev = messages[-1] if messages else None
        if (prev is not None and prev.direction == c.direction
                and c.ts - last_ts[c.direction] <= gap_s):
            prev.data += c.data
        else:
            messages.append(Message(c.ts, c.direction, c.data))
        last_ts[c.direction] = c.ts
    return messages


# --------------------------------------------------------------------------
# Main extraction
# --------------------------------------------------------------------------

@dataclass
class Conversation:
    messages: List[Message]
    h2d: bytes
    d2h: bytes
    summary: dict = field(default_factory=dict)


def parse_device_arg(text: str) -> Tuple[Optional[int], int, int]:
    parts = [int(p) for p in text.split(":")]
    if len(parts) == 2:
        return (None, parts[0], parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2])
    raise ValueError("--device must be BUS:ADDR or IFACE:BUS:ADDR")


def extract_conversation(raw: bytes, device: Optional[str] = None, ftdi: str = "auto",
                         ftdi_packet: int = 64, gap_ms: float = 5.0) -> Conversation:
    records = [r for r in (parse_usbpcap(i, ts, p) for i, ts, p in iter_capture(raw)) if r]
    if not records:
        raise ValueError("No USBPcap packets found in capture")

    controls = collect_control_transfers(records)
    ids = device_descriptor_ids(controls)

    stats: Dict[Tuple[int, int, int], Dict[str, int]] = defaultdict(lambda: {"H2D": 0, "D2H": 0})
    for rec in records:
        if rec.transfer == XFER_BULK and rec.data:
            if rec.endpoint & 0x80 and rec.is_completion:
                stats[rec.key]["D2H"] += len(rec.data)
            elif not rec.endpoint & 0x80 and not rec.is_completion:
                stats[rec.key]["H2D"] += len(rec.data)

    if not stats:
        raise ValueError("No bulk (serial data) transfers found in capture")

    if device:
        want_iface, want_bus, want_dev = parse_device_arg(device)
        matches = [k for k in stats if k[1] == want_bus and k[2] == want_dev
                   and (want_iface is None or k[0] == want_iface)]
        if not matches:
            raise ValueError(f"Device {device} has no bulk data. Seen: {sorted(stats)}")
        selected = matches[0]
    else:
        selected = max(stats, key=lambda k: stats[k]["H2D"] + stats[k]["D2H"])

    vid_pid = ids.get(selected)
    chunks = bulk_chunks(records, selected)

    if ftdi == "on":
        is_ftdi, reason = True, "forced"
    elif ftdi == "off":
        is_ftdi, reason = False, "disabled"
    elif vid_pid and vid_pid[0] == 0x0403:
        is_ftdi, reason = True, "VID 0x0403"
    elif vid_pid:
        is_ftdi, reason = False, f"VID 0x{vid_pid[0]:04X}"
    else:
        is_ftdi = looks_like_ftdi(chunks)
        reason = "status-byte pattern" if is_ftdi else "no FTDI pattern"
    if is_ftdi:
        chunks = strip_ftdi_status(chunks, ftdi_packet)

    messages = group_messages(chunks, gap_ms / 1000.0)

    line_events = []
    settings: dict = {}
    for ctl in controls:
        if ctl.key != selected:
            continue
        described = describe_control(ctl)
        if described:
            text, update = described
            settings.update(update)
            line_events.append({"ts": ctl.ts, "event": text})
            messages.append(Message(ctl.ts, "CTRL", b"", text))

    messages.sort(key=lambda m: (m.ts, m.direction != "CTRL"))
    h2d = b"".join(c.data for c in chunks if c.direction == "H2D")
    d2h = b"".join(c.data for c in chunks if c.direction == "D2H")

    t0 = min(r.ts for r in records)
    summary = {
        "devices": [
            {
                "iface": k[0], "bus": k[1], "address": k[2],
                "vid_pid": f"{ids[k][0]:04X}:{ids[k][1]:04X}" if k in ids else None,
                "vendor": USB_VENDORS.get(ids[k][0]) if k in ids else None,
                "bulk_h2d_bytes": v["H2D"], "bulk_d2h_bytes": v["D2H"],
            }
            for k, v in sorted(stats.items())
        ],
        "selected_device": {"iface": selected[0], "bus": selected[1], "address": selected[2]},
        "ftdi": {"detected": is_ftdi, "reason": reason, "packet_size": ftdi_packet},
        "line_settings": settings,
        "line_events": [{"t_rel_s": round(e["ts"] - t0, 6), "event": e["event"]} for e in line_events],
        "h2d_bytes": len(h2d),
        "d2h_bytes": len(d2h),
        "messages": sum(1 for m in messages if m.direction != "CTRL"),
        "duration_s": round(max(r.ts for r in records) - t0, 6),
        "t0": t0,
    }
    return Conversation(messages, h2d, d2h, summary)


def _ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def write_outputs(conv: Conversation, prefix: str, source: str) -> List[str]:
    directory = os.path.dirname(prefix)
    if directory:
        os.makedirs(directory, exist_ok=True)
    t0 = conv.summary["t0"]
    paths = [f"{prefix}_timeline.csv", f"{prefix}_H2D.bin", f"{prefix}_D2H.bin", f"{prefix}_summary.json"]

    with open(paths[0], "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["idx", "t_rel_s", "dir", "nbytes", "hex", "ascii", "note"])
        for i, m in enumerate(conv.messages):
            writer.writerow([i, f"{m.ts - t0:.6f}", m.direction, len(m.data),
                             m.data.hex(" "), _ascii(m.data), m.note])
    with open(paths[1], "wb") as f:
        f.write(conv.h2d)
    with open(paths[2], "wb") as f:
        f.write(conv.d2h)
    with open(paths[3], "w") as f:
        json.dump(dict(conv.summary, source=source), f, indent=2)
    return paths


def print_report(conv: Conversation, show: int) -> None:
    s = conv.summary
    print("\nUSB devices with serial (bulk) data:")
    for d in s["devices"]:
        ident = f" {d['vid_pid']} {d['vendor'] or ''}".rstrip() if d["vid_pid"] else ""
        print(f"  iface {d['iface']} bus {d['bus']} addr {d['address']}{ident}: "
              f"H2D {d['bulk_h2d_bytes']} B, D2H {d['bulk_d2h_bytes']} B")
    sel = s["selected_device"]
    print(f"Selected: iface {sel['iface']} bus {sel['bus']} addr {sel['address']}")
    print(f"FTDI status bytes stripped: {s['ftdi']['detected']} ({s['ftdi']['reason']})")
    print(f"Line settings: {s['line_settings'] or 'not seen (port opened before capture started?)'}")
    print(f"Totals: H2D {s['h2d_bytes']} B, D2H {s['d2h_bytes']} B, "
          f"{s['messages']} messages over {s['duration_s']:.1f} s")

    if show:
        print(f"\nFirst {show} events:")
        t0 = s["t0"]
        for m in conv.messages[:show]:
            if m.direction == "CTRL":
                print(f"  {m.ts - t0:10.6f}  CTRL  {m.note}")
            else:
                hexs = m.data[:24].hex(" ") + (" ..." if len(m.data) > 24 else "")
                print(f"  {m.ts - t0:10.6f}  {m.direction}  ({len(m.data):4d}) {hexs}  |{_ascii(m.data[:24])}|")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild a serial conversation from a USBPcap capture.")
    parser.add_argument("capture", help=".pcapng or .pcap captured with USBPcap")
    parser.add_argument("prefix", nargs="?", help="output prefix (default: dumps/<capture name>)")
    parser.add_argument("--device", help="pick the adapter: BUS:ADDR or IFACE:BUS:ADDR (default: most bulk data)")
    parser.add_argument("--ftdi", choices=["auto", "on", "off"], default="auto",
                        help="strip FTDI 2-byte status headers (default: auto)")
    parser.add_argument("--ftdi-packet", type=int, default=64,
                        help="FTDI max packet size: 64 full-speed, 512 high-speed")
    parser.add_argument("--gap-ms", type=float, default=5.0,
                        help="merge same-direction chunks closer than this (default 5 ms)")
    parser.add_argument("--show", type=int, default=40, help="events to print (0 = none)")
    args = parser.parse_args(argv)

    with open(args.capture, "rb") as f:
        raw = f.read()
    try:
        conv = extract_conversation(raw, args.device, args.ftdi, args.ftdi_packet, args.gap_ms)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    prefix = args.prefix or os.path.join("dumps", os.path.splitext(os.path.basename(args.capture))[0])
    print_report(conv, args.show)
    paths = write_outputs(conv, prefix, args.capture)
    print("\nWritten:")
    for p in paths:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
