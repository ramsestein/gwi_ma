"""
Generic Structure Brute-forcer

Helps find protocol field offsets by brute-forcing "Length" and "Count" fields
around a known anchor (e.g., a header signature).

Usage:
    python src/structure_bruteforcer.py <file.bin> <hex_pattern> [search_range]

Example:
    python src/structure_bruteforcer.py dumps/stream.bin F13B 30
    
Logic:
    1. Finds all occurrences of <hex_pattern>.
    2. For each occurrence, scans +/- [search_range] bytes.
    3. Interprets bytes as potential 16-bit or 32-bit Integers.
    4. Checks if those Integers match:
       - Distance to end of file/frame.
       - Distance to next pattern occurrence.
       - A reasonable "Count" (e.g., 1-100).
"""
import struct
import sys
import binascii

def find_candidate_structures(data, pattern_bytes, search_range=30):
    candidates = []
    
    start = 0
    while True:
        idx = data.find(pattern_bytes, start)
        if idx == -1:
            break
        
        candidates.append(idx)
        start = idx + 1
        
    print(f"Found {len(candidates)} occurrences of {pattern_bytes.hex().upper()}")
    
    # Analyze header candidates
    # We look for Length fields that explain the data size
    
    for i, idx in enumerate(candidates):
        # Define limits
        frame_end = candidates[i+1] if i+1 < len(candidates) else len(data)
        available = frame_end - idx
        
        print(f"\n--- Occurrence #{i+1} @ {idx} (Available: {available} bytes) ---")
        
        # Scan forward from the pattern to find Length fields
        for offset in range(0, min(available, search_range)):
            pos = idx + offset
            if pos + 2 > len(data): break
            
            # Try 16-bit Big Endian
            val16be = struct.unpack_from('>H', data, pos)[0]
            # Try 16-bit Little Endian
            val16le = struct.unpack_from('<H', data, pos)[0]
            
            # Heuristic: Match specific relationship
            # 1. Exact match to end of frame
            # 2. Match to end of frame minus small footer (1-4 bytes)
            
            if check_match(val16be, available - offset, "16BE", offset): continue
            if check_match(val16le, available - offset, "16LE", offset): continue
            
            # Try 32-bit
            if pos + 4 <= len(data):
                val32be = struct.unpack_from('>I', data, pos)[0]
                val32le = struct.unpack_from('<I', data, pos)[0]
                check_match(val32be, available - offset, "32BE", offset)
                check_match(val32le, available - offset, "32LE", offset)

def check_match(val, distance, type_str, offset):
    # Rule 1: Exact Length Match
    if val == distance:
        print(f"  [OFFSET +{offset}] {type_str} = {val} MATCHES exact distance to next frame/end")
        return True
    
    # Rule 2: Length Match ignoring header size (e.g., Length starts AFTER the length field)
    # distance includes the length field itself (2 or 4 bytes). 
    # Usually Length value = (Distance - sizeof(LengthField))
    size = 2 if "16" in type_str else 4
    if val == (distance - size):
        print(f"  [OFFSET +{offset}] {type_str} = {val} MATCHES payload length (excluding length field)")
        return True

    # Rule 3: Match with Footer
    diff = distance - val
    if 0 < diff <= 4:
         print(f"  [OFFSET +{offset}] {type_str} = {val} MATCHES distance with {diff}-byte footer")
         return True
         
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/structure_bruteforcer.py <file.bin> <hex_pattern> [range]")
        sys.exit(1)
        
    filename = sys.argv[1]
    pattern = binascii.unhexlify(sys.argv[2])
    search_range = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    
    with open(filename, 'rb') as f:
        data = f.read()
        
    find_candidate_structures(data, pattern, search_range)
