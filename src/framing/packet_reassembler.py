import sys
import collections
try:
    from . import protocol_manager
except ImportError:
    import protocol_manager

def analyze_fragmentation(bin_file, protocol_file=None):
    print(f"--- Fragmentation Analysis: {bin_file} ---")
    
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # Load Protocol
    if protocol_file:
        import json
        with open(protocol_file, 'r') as f:
            proto = json.load(f)
    else:
        proto = protocol_manager.load_protocol()
        
    struct = proto.get('packet_structure', {})
    header_hex = struct.get('header')
    fixed_len = struct.get('fixed_length')
    
    if not header_hex or not fixed_len:
        print("Protocol header/length not defined. Cannot parse packets to check fragmentation.")
        return
        
    header_bytes = bytes.fromhex(header_hex)
    packets = []
    
    # Extract Packets
    i = 0
    while i < len(data) - fixed_len:
        if data[i:i+len(header_bytes)] == header_bytes:
            packets.append(data[i:i+fixed_len])
            i += fixed_len
        else:
            i += 1
            
    print(f"Extracted {len(packets)} packets. Searching for Sequence Numbers...")
    
    # Heuristic: Find bytes that increment by 1 (modulo 256)
    potential_seq_indices = []
    
    if len(packets) > 10:
        for offset in range(fixed_len):
            score = 0
            misses = 0
            for k in range(len(packets)-1):
                cur = packets[k][offset]
                nxt = packets[k+1][offset]
                if (cur + 1) % 256 == nxt:
                    score += 1
                else:
                    misses += 1
            
            # If > 90% sequential, likely a Sequence Number
            if score > (len(packets)-1) * 0.9:
                potential_seq_indices.append(offset)
                
    if potential_seq_indices:
        print(f"Potential Sequence Number Found at Offset(s): {potential_seq_indices}")
        seq_off = potential_seq_indices[0]
        
        # Check for gaps using this sequence
        expected = packets[0][seq_off]
        gaps = 0
        for p in packets[1:]:
            expected = (expected + 1) % 256
            if p[seq_off] != expected:
                gaps += 1
                print(f"Gap detected! Expected {expected}, got {p[seq_off]}")
                expected = p[seq_off] # Resync
        
        if gaps == 0:
            print("Sequence is perfect. No missing fragments.")
        else:
            print(f"Total Sequence Gaps: {gaps}")
            
    else:
        print("No obvious Sequence Number found. Fragmentation might not be used or used differently.")

    # Reassembly Logic (Interactive)
    # If we had a "More Fragments" flag, we would check it here.
    # Searching for boolean flags that toggle...
    print("\nScanning for 'Start/End' flags...")
    for offset in range(fixed_len):
        values = [p[offset] for p in packets]
        unique = set(values)
        if len(unique) <= 3: # Maybe flags
            # Check pattern
            # e.g., 0x80 (Start), 0x00 (Mid), 0x40 (End)
            # This is hard to generalize without user input, but we list candidates
            print(f"Offset {offset} has few unique values: {[hex(v) for v in unique]}. Candidate for Frame Type?")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.packet_reassembler <BIN_FILE>")
    else:
        analyze_fragmentation(sys.argv[1])
