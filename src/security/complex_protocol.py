import sys
import collections

def analyze_complexity(filename, packet_size):
    print(f"--- Complex Protocol Analyzer: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    num_packets = len(data) // packet_size
    packets = [data[i*packet_size : (i+1)*packet_size] for i in range(num_packets)]
    
    # 1. TDM (Time Division Multiplexing) Detection
    # Do we see a rotating pattern of "Types"?
    # Assume Byte 0 or 1 is Type
    print("\n[Multiplexing Analysis]")
    
    for offset in [0, 1, 2, 3]: # Check first few bytes
        types = [p[offset] for p in packets]
        
        # Check for periodicity in types
        # e.g. A, B, C, A, B, C... (Period 3)
        if len(types) < 20: continue
        
        # Brute force period check 2..10
        found_period = False
        for period in range(2, 12):
            # Check if type[i] == type[i+period] matches consistently
            matches = sum(1 for i in range(len(types)-period) if types[i] == types[i+period])
            accuracy = matches / (len(types)-period)
            
            if accuracy > 0.95:
                print(f"-> Header Offset {offset} cycles with Period {period}!")
                print(f"   Pattern: {[hex(t) for t in types[:period]]}...")
                print("   Verdict: TDM Detected (Round-Robin).")
                found_period = True
                break
        
        if found_period: break

    # 2. Dependency Tracker
    # Does Byte X change only when Byte Y has a specific value?
    # e.g. "If Byte 0 == 0x80, Byte 5 is SpO2. If Byte 0 == 0x81, Byte 5 is ErrorCode."
    
    print("\n[Dependency Analysis] (Simplified)")
    # We look for "Mode Switching"
    # If Byte 0 has few values (Modes), check if distributions of other bytes change significantly per Mode.
    
    header_offset = 0 # Assume 0 for demo
    modes = collections.defaultdict(list)
    for p in packets:
        modes[p[header_offset]].append(p)
        
    if len(modes) > 1 and len(modes) < 10:
        print(f"Found {len(modes)} Distinct Packet Types (based on Byte 0).")
        
        # Compare Byte 4 (arbitrary payload example) across modes
        target_byte = packet_size // 2 
        
        print(f"Comparing Byte {target_byte} distribution across modes:")
        for m, pkt_list in modes.items():
            vals = [p[target_byte] for p in pkt_list]
            avg = sum(vals)/len(vals)
            print(f"  Type 0x{m:02X}: Avg Value {avg:.1f} (Count {len(pkt_list)})")
            
        print("-> If averages differ wildly, Type determines Payload meaning.")
    else:
        print("Single Packet Type or chaotic header.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.complex_protocol <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        analyze_complexity(sys.argv[1], int(sys.argv[2]))
