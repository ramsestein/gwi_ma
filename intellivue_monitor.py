"""
IntelliVue MX750 Real-Time Vital Signs Monitor (Standalone)

Connects to Philips IntelliVue MX750 via RS232 (USB Adapter),
sends the required 10-frame handshake, and decodes vital signs
(HR, SpO2, NIBP, RR, PR) from the F13B PollAction reply stream.

Outputs vital signs to console table and saves to CSV in 'results/'.

Usage:
  python intellivue_monitor.py [PORT] [BAUD]
  
Examples:
  python intellivue_monitor.py COM4
  python intellivue_monitor.py COM3 115200
"""
import serial
import struct
import time
import sys
import os
import csv
from datetime import datetime

SLIP_END = 0xC0

# ============================================================
# HANDSHAKE (replayed from VitalRecorder USBPcap capture)
# ============================================================
HANDSHAKE_FRAMES = [
    bytes.fromhex("110100EE0DEC05081301001601028000140200027DE1DC3180A0808001010000A280A003000001A4803080020101060452010001308006025101000000003080020102060C2A8648CE14020100000001013080060C2A8648CE140201000000020100000000000061803080020101A0806080A180060C2A8648CE14020100000003010000BE802880060C2A8648CE140201000000010102010281488000000040000000000000008000000020000000000000000001002C000100288000000000000000000002BC000002BCFFFFFFFF600000000001000CF00100088800000000000000000000000000000000000000000000EBE6C1"),
    bytes.fromhex("1101001CE10000020002001400010001000E002100000000004847000D060000290EC1"),
    bytes.fromhex("11010030E10000020001002800020007002200210000000000000000F13B0014000100010009080300010008F13E0004000400496441C1"),
    bytes.fromhex("11010030E10000020001002800030007002200210000000000000000F13B0014000200010006080300010008F13E000400040049F517C1"),
    bytes.fromhex("11010030E10000020001002800040007002200210000000000000000F13B0014000300010036080100010008F13E000400040049409CC1"),
    bytes.fromhex("11010024E10000020001001C000500070016002100000000000000000C160008000400010006081015A8C1"),
    bytes.fromhex("11010030E10000020001002800060007002200210000000000000000F13B0014000500010009080300010008F13E000400040049CB3FC1"),
    bytes.fromhex("11010030E10000020001002800070007002200210000000000000000F13B0014000600010006080300010008F13E0004000400495A69C1"),
    bytes.fromhex("11010030E10000020001002800080007002200210000000000000000F13B0014000700010036080100010008F13E000400040049BDA5C1"),
    bytes.fromhex("11010024E10000020001001C000900070016002100000000000000000C16000800080001002A08077A18C1"),
]

# ============================================================
# KNOWN OIDs (Philips IntelliVue nomenclature)
# ============================================================
OID_NAMES = {
    0x0002: 'ECG', 0x0100: 'ECG_I', 0x0101: 'ECG_II', 0x0102: 'ECG_III',
    0x0300: 'ST', 0x3F20: 'QT', 0x4182: 'HR', 0x4261: 'EV',
    0x4822: 'Pulse', 0x4A14: 'ABP_S', 0x4A16: 'ABP_D', 0x4A18: 'ABP_M',
    0x4A24: 'NIBP_S', 0x4A26: 'NIBP_D', 0x4A28: 'NIBP_M',
    0x4BB0: 'Perf', 0x4BB4: 'PR', 0x4BB8: 'SpO2',
    0x5000: 'RR', 0x500A: 'FR', 0x5004: 'EtCO2',
    0x5804: 'PPC', 0xF03D: 'STindx', 0x4BC4: 'SpO2_cfg',
}


def slip_unescape(data):
    """SLIP unescape: DB DC -> C0, DB DD -> DB."""
    result = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xDB and i + 1 < len(data):
            if data[i + 1] == 0xDC:
                result.append(0xC0)
                i += 2
                continue
            elif data[i + 1] == 0xDD:
                result.append(0xDB)
                i += 2
                continue
        result.append(data[i])
        i += 1
    return bytes(result)


def float32_11073(data):
    """Decode IEEE 11073 FLOATType (32-bit): 8-bit exp + 24-bit mantissa."""
    val = struct.unpack('>I', data[:4])[0]
    # Special values
    if val in (0x007FFFFF, 0x00800000, 0x007FFFFE, 0x00800002, 0xFFFFFFFF):
        return None
    exp = (val >> 24) & 0xFF
    if exp >= 128:
        exp -= 256
    mant = val & 0x00FFFFFF
    if mant >= 0x800000:
        mant -= 0x1000000
    return mant * (10.0 ** exp)


def parse_poll_reply(frame):
    """
    Parse an IntelliVue F13B PollAction reply frame.
    
    Corrected header structure (verified against USBPcap):
    F13B(2) + action_len(2) + poll_number(2) + rel_time(4) +
    abs_time(8) + polled_type(4) + polled_attr_grp(2) +
    poll_info_list: count(2) + length(2)
    Then: SingleContextPoll[count] each with:
      context_id(2) + obs_count(2) + obs_length(2)
      Then: ObservationPoll[obs_count] each with:
        obj_handle(2) + attr_count(2) + attr_length(2)
        Then: Attribute[attr_count] each with:
          attr_id(2) + attr_len(2) + data[attr_len]
    """
    vitals = {}
    waveforms = {}

    # Find F13B marker
    idx = frame.find(b'\xF1\x3B')
    if idx < 0 or idx > 30:
        return vitals, waveforms

    pos = idx

    # F13B header
    action_type = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
    action_len = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2

    # Poll header: 22 bytes (Empirically verified)
    # poll_number(2) + sequence(2) + rel_time(4) + abs_time(8) + polled_type(4) + attr_grp(2) (approx)
    if pos + 22 > len(frame):
        return vitals, waveforms

    poll_number = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
    # Skip the next 20 bytes of header fields (sequence, times, type, group)
    # We don't need them for vital extraction
    pos += 20

    # poll_info_list: count(2) + length(2)
    if pos + 4 > len(frame):
        return vitals, waveforms

    pi_count = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
    pi_len = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2

    # SingleContextPoll entries
    for sc in range(min(pi_count, 20)):
        if pos + 6 > len(frame):
            break

        sc_context = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
        sc_count = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
        sc_len = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2

        if sc_count == 0 or sc_len == 0:
            continue

        # ObservationPoll entries
        sc_end = pos + sc_len
        for op in range(min(sc_count, 50)):
            if pos + 6 > len(frame) or pos >= sc_end:
                break

            obj_handle = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
            attr_count = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
            attr_len = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2

            attr_end = min(pos + attr_len, len(frame))

            for a in range(min(attr_count, 50)):
                if pos + 4 > len(frame) or pos >= attr_end:
                    break

                aid = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2
                alen = struct.unpack('>H', frame[pos:pos+2])[0]; pos += 2

                if alen > 5000 or pos + alen > len(frame):
                    pos = attr_end
                    break

                aval = frame[pos:pos+alen]

                # --- Decode NuObsValue (single numeric) ---
                if aid == 0x094F and len(aval) >= 8:
                    physio = struct.unpack('>H', aval[0:2])[0]
                    state = struct.unpack('>H', aval[2:4])[0]
                    fv = float32_11073(aval[4:8])
                    name = OID_NAMES.get(physio, 'OID_{:04X}'.format(physio))
                    if fv is not None:
                        # Clean up value
                        vitals[name] = round(fv, 2)

                # --- Decode NuCmpdObsValue (compound numeric) ---
                elif aid == 0x0950 and len(aval) >= 4:
                    cc = struct.unpack('>H', aval[0:2])[0]
                    cl = struct.unpack('>H', aval[2:4])[0]
                    cpos = 4
                    for ci in range(min(cc, 20)):
                        if cpos + 8 > len(aval):
                            break
                        physio = struct.unpack('>H', aval[cpos:cpos+2])[0]
                        state = struct.unpack('>H', aval[cpos+2:cpos+4])[0]
                        fv = float32_11073(aval[cpos+4:cpos+8])
                        name = OID_NAMES.get(physio, 'OID_{:04X}'.format(physio))
                        if fv is not None:
                            vitals[name] = round(fv, 2)
                        cpos += 8

                # --- Decode SaObsValue (waveform samples) ---
                elif aid == 0x0951 and len(aval) >= 4:
                    waveforms['handle_{:04X}'.format(obj_handle)] = aval

                # --- Decode SaCmpdObsValue ---
                elif aid == 0x0952 and len(aval) >= 4:
                    waveforms['cmpd_{:04X}'.format(obj_handle)] = aval

                pos += alen

            # Ensure we don't go past the observation boundary
            pos = min(pos, attr_end)

    return vitals, waveforms


def realtime_monitor(port, baud=115200, duration=120):
    """Connect to IntelliVue and display real-time vital signs."""
    print("=" * 55)
    print("  IntelliVue MX750 Real-Time Vital Signs Monitor")
    print("=" * 55)
    print("  Port: {} @ {}".format(port, baud))
    print("  Duration: {}s (Ctrl+C to stop)".format(duration))
    print()

    os.makedirs("results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = "results/vitals_{}.csv".format(ts)
    bin_file = "results/stream_{}.bin".format(ts)

    # Open serial port
    try:
        ser = serial.Serial(port, baud, timeout=0.5, rtscts=False, dsrdtr=False)
        ser.dtr = True
        ser.rts = True
        ser.reset_input_buffer()
        print("[OK] Port opened")
    except Exception as e:
        print("[ERROR] Cannot open {}: {}".format(port, e))
        return

    # Send handshake
    print("[TX] Sending handshake ({} frames)...".format(len(HANDSHAKE_FRAMES)))
    for i, frame in enumerate(HANDSHAKE_FRAMES):
        ser.write(bytes([SLIP_END]) + frame)
        ser.flush()
        if i == 0:
            time.sleep(0.5)
            if ser.in_waiting > 0:
                resp = ser.read(ser.in_waiting)
                if b'\xc0' in resp:
                    print("[RX] Monitor responded: {} bytes (SLIP)".format(len(resp)))
                else:
                    print("[RX] Monitor responded: {} bytes".format(len(resp)))
        else:
            time.sleep(0.05)

    print("[OK] Handshake complete. Monitoring...")
    print()
    print("  {:<10s} {:>6s} {:>6s} {:>6s} {:>6s} {:>8s} {:>6s}".format(
        "Time", "HR", "SpO2", "PR", "RR", "NIBP", "Perf"))
    print("  " + "-" * 52)

    # CSV header
    all_fields = ['timestamp', 'HR', 'SpO2', 'PR', 'RR', 'NIBP_S', 'NIBP_D',
                  'NIBP_M', 'ABP_S', 'ABP_D', 'ABP_M', 'Perf', 'EtCO2',
                  'Pulse', 'FR', 'ST', 'QT', 'EV']

    with open(csv_file, 'w', newline='') as cf:
        writer = csv.DictWriter(cf, fieldnames=all_fields)
        writer.writeheader()

    # Main loop
    buffer = bytearray()
    start = time.time()
    last_vitals = {}
    last_display = 0
    frame_count = 0
    poll_count = 0
    wave_count = 0

    with open(bin_file, 'wb') as bf:
        try:
            while time.time() - start < duration:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    buffer.extend(data)
                    bf.write(data)

                    # Extract complete SLIP frames
                    while SLIP_END in buffer:
                        idx = buffer.index(SLIP_END)
                        if idx > 2:
                            raw_frame = bytes(buffer[:idx])
                            frame = slip_unescape(raw_frame)
                            frame_count += 1

                            # Try to parse as poll reply
                            if b'\xF1\x3B' in frame:
                                vitals, waveforms = parse_poll_reply(frame)
                                if vitals:
                                    poll_count += 1
                                    last_vitals.update(vitals)
                                if waveforms:
                                    wave_count += 1

                        buffer = buffer[idx + 1:]

                    # Display every 1 second
                    now = time.time()
                    if now - last_display >= 1.0:
                        last_display = now
                        ts_str = datetime.now().strftime("%H:%M:%S")

                        hr = last_vitals.get('HR', '')
                        spo2 = last_vitals.get('SpO2', '')
                        pr = last_vitals.get('PR', last_vitals.get('Pulse', ''))
                        rr = last_vitals.get('RR', last_vitals.get('FR', ''))
                        nibp_s = last_vitals.get('NIBP_S', '')
                        nibp_d = last_vitals.get('NIBP_D', '')
                        perf = last_vitals.get('Perf', '')

                        nibp = "{}/{}".format(nibp_s, nibp_d) if nibp_s else ''

                        print("  {:<10s} {:>6s} {:>6s} {:>6s} {:>6s} {:>8s} {:>6s}".format(
                            ts_str,
                            str(hr) if hr != '' else '--',
                            str(spo2) if spo2 != '' else '--',
                            str(pr) if pr != '' else '--',
                            str(rr) if rr != '' else '--',
                            nibp if nibp else '--',
                            str(perf) if perf != '' else '--',
                        ))

                        # Write to CSV
                        if last_vitals:
                            row = {'timestamp': datetime.now().isoformat()}
                            row.update(last_vitals)
                            with open(csv_file, 'a', newline='') as cf:
                                writer = csv.DictWriter(cf, fieldnames=all_fields)
                                writer.writerow({k: row.get(k, '') for k in all_fields})
                else:
                    time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n  [STOPPED]")

    ser.close()

    print()
    print("=" * 55)
    print("  CAPTURE SUMMARY")
    print("  Duration: {:.0f}s".format(time.time() - start))
    print("  Frames: {} (poll replies: {}, waveforms: {})".format(
        frame_count, poll_count, wave_count))
    print("  Binary: {}".format(bin_file))
    print("  CSV: {}".format(csv_file))
    if last_vitals:
        print("  Last vitals: {}".format(last_vitals))
    print("=" * 55)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python intellivue_monitor.py <PORT> [BAUD] [DURATION]")
        print("  PORT: COM port (e.g. COM4)")
        sys.exit(1)

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else 120

    realtime_monitor(port, baud, dur)
