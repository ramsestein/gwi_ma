import sys
import math
import collections
from collections import Counter

def calculate_entropy(data):
    if not data:
        return 0
    entropy = 0
    counter = Counter(data)
    length = len(data)
    for count in counter.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def analyze_entropy(filename, packet_size=None):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    print(f"Analyzing Entropy for {filename} ({len(data)} bytes)...")

    if packet_size is None or packet_size <= 0:
        # If no packet size, we can't do column-based entropy easily.
        # We could try to auto-detect or just do a sliding window entropy?
        # Column-based is most useful for structure.
        print("Packet size is required for structural entropy analysis.")
        try:
            packet_size = int(input("Enter Packet Size (or estimated): "))
        except:
            return

    # Organize data into columns
    columns = collections.defaultdict(list)
    num_packets = len(data) // packet_size
    
    for i in range(num_packets):
        start = i * packet_size
        packet = data[start : start + packet_size]
        for offset, byte in enumerate(packet):
            columns[offset].append(byte)

    print(f"\n--- Entropy Map (Packet Size: {packet_size}) ---")
    print("Offset | Entropy (0-8) | Type Hint")
    print("-" * 45)

    for offset in range(packet_size):
        col_data = columns[offset]
        ent = calculate_entropy(col_data)
        
        # Heuristic for Type Hint
        hint = "Unknown"
        if ent < 0.1:
            hint = "CONST / Header"
        elif ent < 2.0:
            hint = "Enum / Flag"
        elif ent < 4.0:
            hint = "Counter / Low-Var"
        elif ent > 7.5:
            hint = "Random / Checksum / LSB"
        else:
            hint = "Data / High-Var"
            
        # Visualize bar
        bar_len = int(ent * 2)
        bar = "#" * bar_len
        
        print(f"{offset:4} | {ent:5.2f} {bar:16} | {hint}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.entropy_analyzer <CAPTURE_FILE> [PACKET_SIZE]")
    else:
        pkl = int(sys.argv[2]) if len(sys.argv) > 2 else None
        analyze_entropy(sys.argv[1], pkl)
