"""
Serial tap: timestamped capture of one or two serial ports, either listening
only (passive Y) or forwarding between them (active bridge).

Tap mode (default) never writes to any port. Use it with a Y cable where each
adapter only has RX and GND connected, one adapter per direction, to see what
two devices say to each other (e.g. BIS <-> Masimo). With a single port it
simply records what a device emits (e.g. the BIS ASCII output).

Bridge mode (--bridge) forwards everything read on one port to the other, so
the PC or Pi sits in the middle (device A <-> adapter A | adapter B <-> device B)
and logs both directions. Control lines (DTR/RTS) are not forwarded.

Runs on Windows (COM3) and Linux (/dev/ttyUSB0); needs only pyserial.

Outputs, for a given prefix:
  <prefix>_timeline.csv   one row per message: idx, t_rel_s, dir, nbytes, hex, ascii, note
                          (dir is the name of the port the bytes came from, or EVENT)
  <prefix>_<NAME>.bin     raw bytes received on each port
  <prefix>_summary.json   start time, mode, port settings, byte and message counts

While it runs, type a note and press Enter to mark an event (e.g. "sensor off"),
press Enter on an empty line to see the counters, and Ctrl+C to stop.

Usage:
  python -m src.acquisition.serial_tap PORT [PORT2] --baud 9600
      [--baud2 N] [--format 8N1] [--names BIS,MASIMO] [--bridge]
      [--prefix dumps/session1] [--gap-ms 5] [--echo] [--dtr on|off] [--rts on|off]
"""
import argparse
import csv
import datetime
import json
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import serial

PARITIES = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
            "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}
STOPBITS = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}


@dataclass
class PortSpec:
    name: str
    device: str
    baudrate: int
    fmt: str = "8N1"
    dtr: bool = True
    rts: bool = True


def parse_format(fmt: str):
    match = re.fullmatch(r"([5-8])([NEOMS])(1|1\.5|2)", fmt.upper())
    if not match:
        raise ValueError(f"Bad format '{fmt}', expected e.g. 8N1, 7E1, 8N2")
    return int(match.group(1)), PARITIES[match.group(2)], STOPBITS[match.group(3)]


def open_port(spec: PortSpec, timeout: float = 0.05) -> serial.Serial:
    bytesize, parity, stopbits = parse_format(spec.fmt)
    ser = serial.Serial()
    ser.port = spec.device
    ser.baudrate = spec.baudrate
    ser.bytesize = bytesize
    ser.parity = parity
    ser.stopbits = stopbits
    ser.timeout = timeout
    ser.dtr = spec.dtr
    ser.rts = spec.rts
    ser.open()
    return ser


def _ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


class SerialCapture:
    """Reads one or two ports in background threads and logs what they receive."""

    def __init__(self, specs: List[PortSpec], prefix: str, bridge: bool = False,
                 gap_ms: float = 5.0, echo: bool = False,
                 opener: Callable[[PortSpec], serial.Serial] = open_port,
                 clock: Callable[[], float] = time.monotonic):
        if not 1 <= len(specs) <= 2:
            raise ValueError("Give one or two ports")
        if bridge and len(specs) != 2:
            raise ValueError("Bridge mode needs two ports")
        if len({s.name for s in specs}) != len(specs):
            raise ValueError("Port names must be different")
        self.specs = specs
        self.prefix = prefix
        self.bridge = bridge
        self.gap_s = gap_ms / 1000.0
        self.echo = echo
        self.opener = opener
        self.clock = clock

        self.ports: List[serial.Serial] = []
        self.bytes_in: Dict[str, int] = {s.name: 0 for s in specs}
        self.messages: Dict[str, int] = {s.name: 0 for s in specs}
        self.forward_errors = 0
        self.events = 0
        self.read_errors: List[str] = []

        self._queue: "queue.Queue" = queue.Queue()
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self._t0 = 0.0
        self._start_wall: Optional[datetime.datetime] = None
        self._summary: Optional[dict] = None

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> None:
        directory = os.path.dirname(self.prefix)
        if directory:
            os.makedirs(directory, exist_ok=True)
        for spec in self.specs:
            try:
                self.ports.append(self.opener(spec))
            except Exception:
                for port in self.ports:
                    port.close()
                raise

        self._bins = {s.name: open(f"{self.prefix}_{_safe_name(s.name)}.bin", "wb") for s in self.specs}
        self._csv_file = open(f"{self.prefix}_timeline.csv", "w", newline="")
        self._csv = csv.writer(self._csv_file)
        self._csv.writerow(["idx", "t_rel_s", "dir", "nbytes", "hex", "ascii", "note"])
        self._row_idx = 0

        self._start_wall = datetime.datetime.now().astimezone()
        self._t0 = self.clock()

        for i, spec in enumerate(self.specs):
            other = self.ports[1 - i] if self.bridge else None
            t = threading.Thread(target=self._reader, args=(spec.name, self.ports[i], other), daemon=True)
            t.start()
            self._threads.append(t)
        self._writer_thread = threading.Thread(target=self._writer, daemon=True)
        self._writer_thread.start()

    def mark(self, text: str) -> None:
        self._queue.put(("event", self.clock(), "EVENT", text))

    def stop(self) -> dict:
        if self._summary is not None:
            return self._summary
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._queue.put(("end", self.clock(), "", None))
        self._writer_thread.join(timeout=5)
        for port in self.ports:
            try:
                port.close()
            except Exception:
                pass
        for f in self._bins.values():
            f.close()
        self._csv_file.close()

        self._summary = {
            "start_time": self._start_wall.isoformat() if self._start_wall else None,
            "duration_s": round(self.clock() - self._t0, 3),
            "mode": "bridge" if self.bridge else "tap",
            "ports": [{"name": s.name, "device": s.device, "baudrate": s.baudrate, "format": s.fmt,
                       "dtr": s.dtr, "rts": s.rts} for s in self.specs],
            "bytes": dict(self.bytes_in),
            "messages": dict(self.messages),
            "events": self.events,
            "forward_errors": self.forward_errors,
            "read_errors": self.read_errors,
            "gap_ms": self.gap_s * 1000.0,
        }
        with open(f"{self.prefix}_summary.json", "w") as f:
            json.dump(self._summary, f, indent=2)
        return self._summary

    def output_paths(self) -> List[str]:
        names = [f"{self.prefix}_timeline.csv"]
        names += [f"{self.prefix}_{_safe_name(s.name)}.bin" for s in self.specs]
        names.append(f"{self.prefix}_summary.json")
        return names

    # ---- threads ---------------------------------------------------------

    def _reader(self, name: str, port: serial.Serial, forward_to: Optional[serial.Serial]) -> None:
        while not self._stop.is_set():
            try:
                data = port.read(port.in_waiting or 1)
            except Exception as e:  # unplugged adapter, closed port...
                if not self._stop.is_set():
                    self.read_errors.append(f"{name}: {e}")
                    self._queue.put(("event", self.clock(), "EVENT", f"read error on {name}: {e}"))
                return
            if not data:
                continue
            ts = self.clock()
            if forward_to is not None:
                try:
                    forward_to.write(data)
                except Exception:
                    self.forward_errors += 1
            self._queue.put(("data", ts, name, data))

    def _writer(self) -> None:
        pending = None  # [name, t_first, t_last, bytearray]

        def flush():
            nonlocal pending
            if pending:
                name, t_first, _, buf = pending
                self._write_row(t_first, name, bytes(buf), "")
                self.messages[name] += 1
                pending = None

        while True:
            try:
                kind, ts, name, payload = self._queue.get(timeout=0.05)
            except queue.Empty:
                if pending and self.clock() - pending[2] > self.gap_s:
                    flush()
                    self._csv_file.flush()
                continue

            if kind == "end":
                flush()
                break
            if kind == "event":
                flush()
                self.events += 1
                self._write_row(ts, "EVENT", b"", payload)
                self._csv_file.flush()
                continue

            self.bytes_in[name] += len(payload)
            self._bins[name].write(payload)
            if pending and pending[0] == name and ts - pending[2] <= self.gap_s:
                pending[2] = ts
                pending[3] += payload
            else:
                flush()
                pending = [name, ts, ts, bytearray(payload)]

    def _write_row(self, ts: float, direction: str, data: bytes, note: str) -> None:
        t_rel = ts - self._t0
        self._csv.writerow([self._row_idx, f"{t_rel:.6f}", direction, len(data),
                            data.hex(" "), _ascii(data), note])
        self._row_idx += 1
        if self.echo:
            if direction == "EVENT":
                print(f"{t_rel:10.3f}  EVENT  {note}", flush=True)
            else:
                shown = data[:24].hex(" ") + (" ..." if len(data) > 24 else "")
                print(f"{t_rel:10.3f}  {direction:<8} ({len(data):4d}) {shown}  |{_ascii(data[:24])}|", flush=True)


def counters_line(cap: SerialCapture) -> str:
    parts = [f"{n}: {cap.bytes_in[n]} B / {cap.messages[n]} msg" for n in cap.bytes_in]
    elapsed = cap.clock() - cap._t0
    extra = f" | forward errors: {cap.forward_errors}" if cap.bridge else ""
    return f"[{elapsed:7.1f} s] " + " | ".join(parts) + f" | events: {cap.events}{extra}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Timestamped serial capture: passive tap or bridge.")
    parser.add_argument("ports", nargs="+", help="one or two ports, e.g. COM3 COM4 or /dev/ttyUSB0 /dev/ttyUSB1")
    parser.add_argument("--baud", type=int, required=True, help="baud rate of the first port (and the second, unless --baud2)")
    parser.add_argument("--baud2", type=int, help="baud rate of the second port, if different")
    parser.add_argument("--format", default="8N1", help="data bits, parity, stop bits (default 8N1)")
    parser.add_argument("--names", help="comma-separated names for the ports, e.g. BIS,MASIMO (default A,B)")
    parser.add_argument("--bridge", action="store_true", help="forward between the two ports instead of only listening")
    parser.add_argument("--prefix", help="output prefix (default dumps/tap_<date>_<time>)")
    parser.add_argument("--gap-ms", type=float, default=5.0, help="merge bytes from the same port closer than this (default 5 ms)")
    parser.add_argument("--echo", action="store_true", help="print every message as it is logged")
    parser.add_argument("--dtr", choices=["on", "off"], default="on", help="DTR state on open (default on)")
    parser.add_argument("--rts", choices=["on", "off"], default="on", help="RTS state on open (default on)")
    args = parser.parse_args(argv)

    if len(args.ports) > 2:
        parser.error("give one or two ports")
    names = args.names.split(",") if args.names else ["A", "B"][:len(args.ports)]
    if len(names) != len(args.ports):
        parser.error("--names must have one name per port")
    try:
        parse_format(args.format)
    except ValueError as e:
        parser.error(str(e))

    bauds = [args.baud, args.baud2 or args.baud]
    specs = [PortSpec(n, p, bauds[i], args.format, args.dtr == "on", args.rts == "on")
             for i, (n, p) in enumerate(zip(names, args.ports))]
    prefix = args.prefix or os.path.join("dumps", datetime.datetime.now().strftime("tap_%Y%m%d_%H%M%S"))

    cap = SerialCapture(specs, prefix, bridge=args.bridge, gap_ms=args.gap_ms, echo=args.echo)
    try:
        cap.start()
    except (serial.SerialException, ValueError) as e:
        print(f"Error opening ports: {e}")
        return 1

    mode = "BRIDGE (forwarding)" if args.bridge else "TAP (listen only, nothing is sent)"
    print(f"{mode}: " + ", ".join(f"{s.name}={s.device}@{s.baudrate} {s.fmt}" for s in specs))
    print("Type a note + Enter to mark an event, Enter alone for counters, Ctrl+C to stop.")
    try:
        while True:
            line = input()
            if line.strip():
                cap.mark(line.strip())
                print(f"  event marked: {line.strip()}")
            else:
                print(counters_line(cap))
    except (KeyboardInterrupt, EOFError):
        pass

    summary = cap.stop()
    print("\n" + counters_line(cap))
    if summary["read_errors"]:
        print("Read errors: " + "; ".join(summary["read_errors"]))
    print("Written:")
    for path in cap.output_paths():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
