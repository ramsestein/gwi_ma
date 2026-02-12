import sys
import json
import collections
import statistics
try:
    from . import protocol_manager
    from . import checksum_utils
except ImportError:
    import protocol_manager
    import checksum_utils

def verify_capture(bin_file, protocol_file=None):
    print(f"--- Capture Verification: {bin_file} ---")
    
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    if not data:
        print("Empty file.")
        return
        
    # Load Protocol
    if protocol_file:
        with open(protocol_file, 'r') as f:
            proto = json.load(f)
    else:
        proto = protocol_manager.load_protocol()
        
    struct = proto.get('packet_structure', {})
    header_hex = struct.get('header')
    fixed_len = struct.get('fixed_length')
    validation = proto.get('validation', {})
    
    if not header_hex or not fixed_len:
        print("Protocol definition incomplete (Header or Fixed Length missing).")
        return
        
    header_bytes = bytes.fromhex(header_hex)
    
    # Analysis Vars
    total_bytes = len(data)
    total_packets = 0
    valid_packets = 0
    crc_errors = 0
    sync_losses = 0
    gaps = []
    
    # Payload Stats
    metrics = proto.get('metrics', {})
    metric_values = collections.defaultdict(list)
    
    # Scanning Loop
    i = 0
    last_packet_end = -1
    
    while i < total_bytes - fixed_len:
        # Check Header
        if data[i:i+len(header_bytes)] == header_bytes:
            # Candidate PacketFound
            if last_packet_end != -1:
                gap = i - last_packet_end
                if gap > 0:
                    sync_losses += 1
                    gaps.append(gap)
            
            packet = data[i : i+fixed_len]
            total_packets += 1
            
            # Verify Checksum
            is_valid = True
            if validation and validation.get('algorithm'):
                if not checksum_utils.validate_packet(packet, validation):
                    crc_errors += 1
                    is_valid = False
            
            if is_valid:
                valid_packets += 1
                # Extract Metrics for Stats
                from .universal_logger import get_value # Reuse extraction logic if possible or reimplement simple one
                # Reimplementing simple extraction to avoid circular imports or complex deps
                for name, m in metrics.items():
                    try:
                        off = m['offset']
                        dtype = m['type']
                        val = None
                        if off < len(packet):
                            if dtype == 'UINT8': val = packet[off]
                            elif dtype == 'UINT16_LE': val = packet[off] + (packet[off+1] << 8)
                            elif dtype == 'UINT16_BE': val = (packet[off] << 8) + packet[off+1]
                            # Add others as needed
                        
                        if val is not None:
                            metric_values[name].append(val * m.get('scale', 1))
                    except:
                        pass

            last_packet_end = i + fixed_len
            i += fixed_len
        else:
            i += 1
            
    # Report
    print(f"\n[Integrity Report]")
    print(f"Total Data: {total_bytes} bytes")
    print(f"Total Packets Detected: {total_packets}")
    print(f"Valid Packets (CRC OK): {valid_packets} ({valid_packets/total_packets*100:.1f}%)" if total_packets else "Valid Packets: 0")
    print(f"Corrupted Packets: {crc_errors}")
    print(f"Sync Losses / Gaps: {sync_losses}")
    if gaps:
        print(f"Avg Gap Size: {sum(gaps)/len(gaps):.1f} bytes")
        
    print(f"\n[Metric Statistics]")
    for name, values in metric_values.items():
        if values:
            try:
                mean = statistics.mean(values)
                stdev = statistics.stdev(values) if len(values) > 1 else 0
                vmin = min(values)
                vmax = max(values)
                print(f"{name:10} | Mean: {mean:8.2f} | StdDev: {stdev:8.2f} | Range: [{vmin}, {vmax}]")
            except:
                print(f"{name}: Error calculating stats")
        else:
            print(f"{name}: No data extracted")

    # Quality Score
    score = 100
    if total_packets > 0:
        score -= (crc_errors / total_packets) * 50
        score -= (sync_losses / total_packets) * 20
    else:
        score = 0
    
    print(f"\nOverall Capture Quality Score: {max(0, score):.1f}/100")
    if score > 90: print("Verdict: EXCELLENT - Ready for Research")
    elif score > 70: print("Verdict: GOOD - Acceptable with filtering")
    else: print("Verdict: POOR - Check cabling or protocol definition")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.capture_verifier <BIN_FILE> [PROTOCOL_JSON]")
    else:
        proto = sys.argv[2] if len(sys.argv) > 2 else None
        verify_capture(sys.argv[1], proto)
