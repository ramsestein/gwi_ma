"""
Serial loopback test between two adapters joined by a null-modem cable.

Sends numbered frames from port A and checks that they arrive intact on port B
(and back, with --both). Reports lost and corrupted frames and the one-way
latency compared with the time the bytes need on the wire. Use it to check
adapters, cables and timing before connecting any device.

With a single adapter, join pins 2 (RX) and 3 (TX) of its DB-9 with a wire and
give the same port twice: every frame comes back as an echo.

Usage:
  python -m src.utils.serial_loopback PORT_A PORT_B --baud 57600
  python -m src.utils.serial_loopback COM3 COM3 --baud 57600      (one adapter, pins 2-3 joined)
      [--sweep 9600,19200,57600,115200] [--frames 200] [--size 32]
      [--both] [--format 8N1] [--timeout 1.0]
"""
import argparse
import os
import statistics
import struct
import sys
import time
import zlib
from typing import Callable, Dict, List

import serial

from src.acquisition.serial_tap import PortSpec, open_port, parse_format

MAGIC = b"LB"


def make_frame(seq: int, payload: bytes) -> bytes:
    body = MAGIC + struct.pack("<HH", seq & 0xFFFF, len(payload)) + payload
    return body + struct.pack("<I", zlib.crc32(body))


def bits_per_char(fmt: str) -> float:
    bytesize, parity, stopbits = parse_format(fmt)
    return 1 + bytesize + (0 if parity == serial.PARITY_NONE else 1) + stopbits


def read_exact(port, n: int, timeout: float, clock: Callable[[], float]) -> bytes:
    deadline = clock() + timeout
    buf = b""
    while len(buf) < n and clock() < deadline:
        buf += port.read(n - len(buf))
    return buf


def one_direction(tx, rx, baud: int, fmt: str, frames: int, size: int, timeout: float,
                  clock: Callable[[], float] = time.perf_counter) -> Dict:
    rx.reset_input_buffer()
    ok = lost = corrupt = 0
    latencies: List[float] = []
    frame_len = len(make_frame(0, bytes(size)))
    wire_ms = frame_len * bits_per_char(fmt) / baud * 1000.0

    for seq in range(frames):
        frame = make_frame(seq, os.urandom(size))
        t0 = clock()
        tx.write(frame)
        tx.flush()
        got = read_exact(rx, frame_len, timeout, clock)
        t1 = clock()
        if got == frame:
            ok += 1
            latencies.append((t1 - t0) * 1000.0)
        elif len(got) < frame_len:
            lost += 1
            rx.reset_input_buffer()
        else:
            corrupt += 1
            rx.reset_input_buffer()

    result = {"baud": baud, "frames": frames, "ok": ok, "lost": lost, "corrupt": corrupt,
              "frame_bytes": frame_len, "wire_ms": round(wire_ms, 3)}
    if latencies:
        ordered = sorted(latencies)
        result.update({
            "lat_min_ms": round(ordered[0], 3),
            "lat_median_ms": round(statistics.median(ordered), 3),
            "lat_p95_ms": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 3),
            "lat_max_ms": round(ordered[-1], 3),
        })
    return result


def run_loopback(port_a: str, port_b: str, bauds: List[int], frames: int = 200, size: int = 32,
                 both: bool = False, fmt: str = "8N1", timeout: float = 1.0,
                 opener=open_port) -> List[Dict]:
    single = port_a == port_b  # one adapter with pins 2 and 3 joined (loopback plug)
    results = []
    for baud in bauds:
        a = opener(PortSpec("A", port_a, baud, fmt), timeout=0.05)
        b = a if single else opener(PortSpec("B", port_b, baud, fmt), timeout=0.05)
        try:
            r = one_direction(a, b, baud, fmt, frames, size, timeout)
            r["direction"] = "echo" if single else "A->B"
            results.append(r)
            if both and not single:
                r = one_direction(b, a, baud, fmt, frames, size, timeout)
                r["direction"] = "B->A"
                results.append(r)
        finally:
            a.close()
            if not single:
                b.close()
    return results


def format_results(results: List[Dict]) -> str:
    header = f"{'baud':>7} {'dir':>5} {'ok':>5} {'lost':>5} {'bad':>5} {'wire ms':>8} {'median':>8} {'p95':>8} {'max':>8}"
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(f"{r['baud']:>7} {r['direction']:>5} {r['ok']:>5} {r['lost']:>5} {r['corrupt']:>5} "
                     f"{r['wire_ms']:>8.2f} {r.get('lat_median_ms', float('nan')):>8.2f} "
                     f"{r.get('lat_p95_ms', float('nan')):>8.2f} {r.get('lat_max_ms', float('nan')):>8.2f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Loopback test between two serial ports joined by a null-modem cable.")
    parser.add_argument("port_a")
    parser.add_argument("port_b")
    parser.add_argument("--baud", type=int, default=57600)
    parser.add_argument("--sweep", help="comma-separated baud rates to test, overrides --baud")
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--size", type=int, default=32, help="payload bytes per frame")
    parser.add_argument("--both", action="store_true", help="also test B -> A")
    parser.add_argument("--format", default="8N1")
    parser.add_argument("--timeout", type=float, default=1.0, help="seconds to wait for each frame")
    args = parser.parse_args(argv)

    bauds = [int(b) for b in args.sweep.split(",")] if args.sweep else [args.baud]
    try:
        results = run_loopback(args.port_a, args.port_b, bauds, args.frames, args.size,
                               args.both, args.format, args.timeout)
    except (serial.SerialException, ValueError) as e:
        print(f"Error: {e}")
        return 1

    print(format_results(results))
    print("\nLatency is one-way, from write to the last byte read, in ms.")
    failed = sum(r["lost"] + r["corrupt"] for r in results)
    print("RESULT: OK" if failed == 0 else f"RESULT: {failed} frames lost or corrupted")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
