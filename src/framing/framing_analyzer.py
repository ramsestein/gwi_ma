import sys
import collections
import time

def analyze_framing(filename):
    print(f"--- Hybrid Framing Analysis (Header + Timeout) ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return
        
    # Since we are analyzing a file, we don't have real "Timeouts" from the serial port.
    # But if we used 'timing_analyzer.py' we might have gap data.
    # Alternatively, if we don't have a capture with timestamps, we look for 
    # "Variable Length with Header" patterns.
    
    print(f"Analyzing {len(data)} bytes for Framing Patterns...")
    
    # 1. Search for repeated headers again (redundant but necessary for context)
    # We look for ANY 2-byte sequence that repeats often
    bigrams = collections.Counter()
    for i in range(len(data)-1):
        bigram = data[i:i+2]
        bigrams[bigram] += 1
        
    common_headers = bigrams.most_common(5)
    print("Most common 2-byte headers:", [f"0x{k.hex().upper()}" for k,v in common_headers])
    
    # 2. For the top header, measure distance variations
    if common_headers:
        top_header = common_headers[0][0]
        print(f"\nAnalyzing Header {top_header.hex().upper()} distribution...")
        
        indices = [i for i in range(len(data)-1) if data[i:i+2] == top_header]
        dists = [indices[i+1] - indices[i] for i in range(len(indices)-1)]
        
        dist_counts = collections.Counter(dists)
        print("Packet Lengths Distributions:")
        for dist, count in dist_counts.most_common(5):
             print(f"  Length {dist}: {count} times")
             
        # Verdict
        unique_dists = len(dist_counts)
        if unique_dists == 1:
             print("-> Verdict: FIXED LENGTH Framing (Header + Count).")
        elif unique_dists < 5:
             print("-> Verdict: MULTIPLE FIXED LENGTHS (Multiplexed Packets).")
        else:
             print("-> Verdict: VARIABLE LENGTH.")
             print("   Likely uses Length Field or Timeout/Delimiter.")
             
             # Locate length byte?
             # Heuristic: Check byte at Header+2 or Header+3
             print("   Checking for Length Byte hypothesis...")
             matches = 0
             for idx in indices[:-1]:
                 # Hyp: Length is at offset 2
                 if idx + 2 < len(data):
                     candidate_len = data[idx+2]
                     real_len = indices[indices.index(idx)+1] - idx
                     if candidate_len == real_len:
                         matches += 1
             
             if matches > len(indices) * 0.8:
                 print("   Found LENGTH BYTE at Offset 2!")
             else:
                 print("   No obvious Length Byte. Likely TIMEOUT or DELIMITER (End byte).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.framing_analyzer <CAPTURE_FILE>")
    else:
        analyze_framing(sys.argv[1])
