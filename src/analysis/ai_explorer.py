import sys
import collections
# We essentially aggregate logic from other modules to form "Hypotheses"

def generate_hypotheses(filename, packet_size):
    print(f"--- AI Hypothesis Explorer: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    num_packets = len(data) // packet_size
    print(f"Analyzing {num_packets} packets (Size: {packet_size})...")

    # 1. Gather Column Stats
    columns = collections.defaultdict(list)
    for i in range(num_packets):
        start = i * packet_size
        packet = data[start : start + packet_size]
        for off, val in enumerate(packet):
            columns[off].append(val)

    hypotheses = []

    for off, values in columns.items():
        # Entropy
        counts = collections.Counter(values)
        unique_count = len(counts)
        prob = [c/len(values) for c in counts.values()]
        entropy = -sum(p * (p and import_math_log2(p) or 0) for p in prob)
        
        # Ranges
        vmin = min(values)
        vmax = max(values)
        
        # Hypothesis Generation
        
        # H1: Constant / Header / ID
        if unique_count == 1:
            confidence = "100%"
            hypotheses.append(f"Offset {off}: CONSTANT (Value: 0x{values[0]:02X}) -> Header or ID. ({confidence})")
            continue
            
        # H2: Counter
        # Check if values increment
        is_counter = True
        deltas = [values[i+1] - values[i] for i in range(len(values)-1)]
        # Allow wrap-around negatives, but mostly +1
        # Simple check: 90% of deltas are 1 or -255
        inc_count = sum(1 for d in deltas if d == 1 or d == -255)
        if inc_count > len(deltas) * 0.9:
            hypotheses.append(f"Offset {off}: COUNTER (Increments in >90% packets). (High Confidence)")
            continue

        # H3: Vital Signs (HR, SpO2)
        # HR: 30-200. SpO2: 80-100.
        if 30 <= vmin and vmax <= 200:
            if vmax - vmin > 10: # Has some variance
                hypotheses.append(f"Offset {off}: PHYSIOLOGICAL (Range {vmin}-{vmax}). Candidate for HR/MAP/Sys.")
        
        if 80 <= vmin and vmax <= 100:
             hypotheses.append(f"Offset {off}: PHYSIOLOGICAL (Range {vmin}-{vmax}). Candidate for SpO2/TempF.")

        # H4: Checksum / Noise
        if entropy > 7.0 and unique_count > 200:
             hypotheses.append(f"Offset {off}: HIGH ENTROPY ({entropy:.2f}). Likely Checksum or LSB of Waveform.")

    print("\n--- Generated Hypotheses ---")
    for h in hypotheses:
        print(h)
        
def import_math_log2(x):
    import math
    return math.log2(x)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.ai_explorer <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        generate_hypotheses(sys.argv[1], int(sys.argv[2]))
