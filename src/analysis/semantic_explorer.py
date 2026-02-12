import sys
import collections
import struct

def analyze_semantics(filename, packet_size):
    print(f"--- Semantic Explorer: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    num_packets = len(data) // packet_size
    print(f"Scanning {num_packets} packets (Size: {packet_size}) for Physiological Data...")

    # Define Physiological Ranges
    # (Name, Min, Max, Unit)
    ranges = [
        ("HR (Heart Rate)", 30, 250, "BPM"),
        ("SpO2", 50, 100, "%"),
        ("Resp Rate", 4, 60, "RPM"),
        ("Temp (C)", 30.0, 43.0, "C"),
        ("Temp (F)", 90.0, 109.0, "F"),
        ("Sys BP", 60, 250, "mmHg"),
        ("Dia BP", 30, 150, "mmHg"),
        ("EtCO2", 0, 100, "mmHg")
    ]

    # Pre-extract columns for speed
    columns = collections.defaultdict(list)
    for i in range(num_packets):
        start = i * packet_size
        packet = data[start : start + packet_size]
        for off, val in enumerate(packet):
            columns[off].append(val)

    print("\n[Physiological Range Matches]")
    print(f"{'Offset':<8} | {'Metric Candidate':<20} | {'Confidence':<10} | {'Min/Max/Avg'}")
    print("-" * 75)

    for offset, values in columns.items():
        # Clean values (remove 0xFF or 0x00 if they are common 'invalid' markers)
        valid_values = [v for v in values if v != 0 and v != 255]
        if not valid_values: continue
        
        vmin = min(valid_values)
        vmax = max(valid_values)
        vavg = sum(valid_values) / len(valid_values)
        
        # Check against ranges
        for name, rmin, rmax, unit in ranges:
            # Simple Byte Check
            if vmin >= rmin and vmax <= rmax:
                # Calculate "Coverage" (how much of the range is used)
                # If range is narrow (e.g. SpO2 98-100), it might be valid but low variance
                confidence = "Medium"
                if vmax - vmin > (rmax - rmin) * 0.1:
                    confidence = "High"
                
                # Temp logic separation
                if "Temp" in name:
                    # Distinction C vs F often clear by value magnitude
                    pass 
                
                print(f"{offset:<8} | {name:<20} | {confidence:<10} | {vmin}/{vmax}/{vavg:.1f} {unit}")

    # ASCII Number Detection (Mixed Protocol)
    print("\n[Mixed Protocol] Scanning for ASCII Numbers embedded in Binary...")
    # Heuristic: contiguous bytes that form strings "0"-"9"
    # We look for window of bytes
    
    unique_strings = set()
    
    for i in range(num_packets):
        start = i * packet_size
        packet = data[start : start + packet_size]
        
        # Try to decode packet as ASCII, replacing errors
        try:
            text = packet.decode('ascii', errors='ignore')
            # specific strict cleanup
            clean_text = "".join([c if c.isdigit() or c in ".-" else ' ' for c in text])
            parts = clean_text.split()
            for p in parts:
                if len(p) >= 2 and p.replace('.','').isdigit():
                    unique_strings.add(p)
        except:
            pass
            
    if unique_strings:
        print(f"Found {len(unique_strings)} unique numeric strings. Examples: {list(unique_strings)[:5]}")
        print(" -> Protocol likely contains ASCII-encoded values.")
    else:
        print("No embedded ASCII numbers found.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.semantic_explorer <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        analyze_semantics(sys.argv[1], int(sys.argv[2]))
