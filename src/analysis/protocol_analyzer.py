import sys
import struct
import re
import sys
import struct
import re
try:
    from . import protocol_manager
except ImportError:
    import protocol_manager
from collections import Counter

def analyze_value(filename, target_val):
    print(f"Analyzing {filename} for value: {target_val}")
    
    try:
        with open(filename, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # Load protocol to check for known structures
    proto = protocol_manager.load_protocol()
    header_hex = proto['packet_structure']['header']
    fixed_len = proto['packet_structure']['fixed_length']
    
    matches = []

    # Helper to add match
    def add_match(type_, offset, raw_bytes):
        # Calculate context (previous 4 bytes)
        start = max(0, offset - 4)
        context = data[start:offset]
        
        # Calculate offset relative to known packet start (if any)
        packet_offset = -1
        if fixed_len:
            packet_offset = offset % fixed_len
        
        matches.append({
            'type': type_,
            'global_offset': offset,
            'packet_offset': packet_offset,
            'context': context,
            'raw_bytes': raw_bytes
        })

    # 1. Byte search (if value <= 255)
    if target_val <= 255:
        byte_val = struct.pack('B', target_val)
        for m in re.finditer(re.escape(byte_val), data):
            add_match('UINT8', m.start(), byte_val)

    # 2. UINT16 Little Endian
    if target_val <= 65535:
        u16le = struct.pack('<H', target_val)
        for m in re.finditer(re.escape(u16le), data):
            add_match('UINT16_LE', m.start(), u16le)

    # 3. UINT16 Big Endian
    if target_val <= 65535:
        u16be = struct.pack('>H', target_val)
        for m in re.finditer(re.escape(u16be), data):
            add_match('UINT16_BE', m.start(), u16be)

    # --- GOD MODE EXTENSIONS ---

    # 4. Signed Integers (INT8, INT16)
    # Check if target val could be represented as signed
    try:
        if -128 <= target_val <= 127:
            i8 = struct.pack('b', target_val)
            for m in re.finditer(re.escape(i8), data):
                add_match('INT8', m.start(), i8)
        
        if -32768 <= target_val <= 32767:
            i16le = struct.pack('<h', target_val)
            for m in re.finditer(re.escape(i16le), data):
                add_match('INT16_LE', m.start(), i16le)
                
            i16be = struct.pack('>h', target_val)
            for m in re.finditer(re.escape(i16be), data):
                add_match('INT16_BE', m.start(), i16be)
    except:
        pass

    # 5. IEEE 754 Float (32-bit)
    # User input is usually integer (e.g. 98), but floating rep might be 98.0
    try:
        f_val = float(target_val)
        f_le = struct.pack('<f', f_val)
        f_be = struct.pack('>f', f_val)
        
        # Float matching is tricky due to precision, but let's try exact
        for m in re.finditer(re.escape(f_le), data):
            add_match('FLOAT32_LE', m.start(), f_le)
        for m in re.finditer(re.escape(f_be), data):
            add_match('FLOAT32_BE', m.start(), f_be)
    except:
        pass
        
    # 6. Gray Code (8-bit and 16-bit)
    # Convert target to Gray, then search for that binary
    def int_to_gray(n):
        return n ^ (n >> 1)
        
    gray_val = int_to_gray(target_val)
    
    if target_val <= 255:
        g8 = struct.pack('B', gray_val)
        for m in re.finditer(re.escape(g8), data):
            add_match('GRAY_CODE_8', m.start(), g8)
            
    if target_val <= 65535:
        g16 = struct.pack('>H', gray_val) # Assuming BE for Gray usually
        for m in re.finditer(re.escape(g16), data):
            add_match('GRAY_CODE_16_BE', m.start(), g16)

    # ---------------------------


    if not matches:
        print("No matches found.")
        return

    print(f"Found {len(matches)} occurrences.")
    
    # Group by Context/Packet Offset to find patterns
    patterns = Counter()
    for m in matches:
        # If we have a packet structure, group by packet offset
        if m['packet_offset'] != -1:
            key = f"Packet Offset {m['packet_offset']} ({m['type']})"
        else:
            # Otherwise, group by preceding context
            key = f"Context {m['context'].hex()} ({m['type']})"
        patterns[key] += 1

    print("\n--- Potential Patterns ---")
    sorted_patterns = patterns.most_common()
    
    for i, (pattern, count) in enumerate(sorted_patterns):
        print(f"[{i}] {pattern}: Appears {count} times")

    idx = input("\nSelect a pattern number to verify (or 'q' to quit): ")
    if idx.isdigit() and int(idx) < len(sorted_patterns):
        selected_pattern = sorted_patterns[int(idx)][0]
        print(f"\nYou selected: {selected_pattern}")
        
        # Determine definition details
        # Extract matching example
        example_match = next(m for m in matches if (f"Packet Offset {m['packet_offset']} ({m['type']})" == selected_pattern) or (f"Context {m['context'].hex()} ({m['type']})" == selected_pattern))
        
        offset = example_match['packet_offset']
        dtype = example_match['type']
        
        if offset == -1:
            print("Warning: We don't have a fixed packet structure yet.")
            print("We can save this as a 'Context Match' but it's better to find the Header first.")
            # For now, we assume user might want to save it anyway if we support context-based metrics later
            # (Protocol Manager simple version only supports fixed offsets for now, but we can extend)
        
        print(f"This seems to be the value for your metric.")
        metric_name = input("What data is this? (e.g., HR, SPO2, PVC): ").strip()
        
        if metric_name:
            if offset != -1:
                protocol_manager.add_metric(metric_name, offset, dtype)
                print(f"Saved: {metric_name} is at Offset {offset} as {dtype}.")
            else:
                print("Could not save absolute offset (no packet structure defined).")
                print(f"Note: Value found after {example_match['context'].hex()}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python protocol_analyzer.py <CAPTURE_FILE> <SEARCH_VALUE_INT>")
    else:
        filename = sys.argv[1]
        try:
            val = int(sys.argv[2])
            analyze_value(filename, val)
        except ValueError:
            print("Search value must be an integer.")
