import sys
import collections
from collections import Counter
import sys
import collections
from collections import Counter
from src.analysis import protocol_manager

def find_periodicity(filename):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    if len(data) < 100:
        print("Not enough data to analyze periodicity.")
        return

    print(f"Analyzing {filename} ({len(data)} bytes)...")
    
    # Load current protocol to avoid re-asking known things
    proto = protocol_manager.load_protocol()
    known_header = proto['packet_structure']['header']

    # 1. Frequency Analysis
    counts = Counter(data)

    # 2. Distance Analysis for common bytes
    print("\n--- Periodicity Check ---")
    
    candidates = []

    # Check top 10 most common bytes for periodicity
    for target_byte, _ in counts.most_common(10):
        positions = [i for i, b in enumerate(data) if b == target_byte]
        if len(positions) < 5:
            continue
            
        diffs = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
        diff_counts = Counter(diffs)
        
        # Look for a dominant distance
        if not diff_counts:
            continue
            
        most_common_diff, count = diff_counts.most_common(1)[0]
        
        # If >50% of intervals are the same, it's a strong candidate
        if count > len(positions) * 0.5: 
            candidates.append({
                'byte': target_byte,
                'interval': most_common_diff,
                'confidence': count/len(diffs)
            })

    if not candidates:
        print("No strong periodic patterns found.")
        return

    print(f"Found {len(candidates)} candidate patterns.")
    
    for cand in candidates:
        byte_hex = f"{cand['byte']:02X}"
        if known_header and byte_hex in known_header:
            print(f"Skipping known header byte 0x{byte_hex}...")
            continue

        print(f"\n[CANDIDATE] Byte 0x{byte_hex} repeats every {cand['interval']} bytes (Confidence: {cand['confidence']:.0%})")
        print(f"Context: {data[0: cand['interval']*2].hex()}...")  # Print a bit of context
        
        action = input("What is this? (H=Header, F=Footer, I=Ignore, S=Skip): ").strip().upper()
        
        if action == 'H':
            print(f"Marking 0x{byte_hex} as Header.")
            # Update protocol definition
            proto = protocol_manager.load_protocol()
            proto['packet_structure']['header'] = byte_hex
            proto['packet_structure']['fixed_length'] = cand['interval']
            protocol_manager.save_protocol(proto)
            
        elif action == 'F':
            print(f"Marking 0x{byte_hex} as Footer.")
            proto = protocol_manager.load_protocol()
            proto['packet_structure']['footer'] = byte_hex
            protocol_manager.save_protocol(proto)
            
        elif action == 'I':
            print("Ignored.")
        else:
            print("Skipped.")

    print("\nAnalysis complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python packet_finder.py <CAPTURE_FILE>")
    else:
        find_periodicity(sys.argv[1])
