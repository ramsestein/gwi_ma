import sys
import math
import collections

def analyze_crypto(filename, packet_size=0):
    print(f"--- Crypto Scanner: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # 1. Global Entropy
    # If entropy is very close to 8.0, it's likely Encrypted or Compressed
    counts = collections.Counter(data)
    prob = [c/len(data) for c in counts.values()]
    entropy = -sum(p * math.log2(p) for p in prob)
    
    print(f"Global Entropy: {entropy:.4f} / 8.0000")
    
    if entropy > 7.95:
        print("-> ALERT: Very High Entropy. Likely Compressed or Encrypted.")
        print("   Standard reverse engineering (looking for patterns) will fail.")
        print("   Look for initial handshake or key exchange.")
    elif entropy < 7.0:
        print("-> Low Entropy. Likely plaintext or simple protocol.")

    # 2. XOR Key Detection (Repeating Key / Vigenere)
    # If we XOR the stream with itself shifted by K, and the result has low entropy, K is likely the key length.
    # This is "Hamming Distance" analysis or Index of Coincidence.
    
    print("\n[XOR / Repeating Key Analysis]")
    best_lag = 0
    best_score = 0
    
    # Check lags 1 to 32 (common key lengths)
    for lag in range(1, 33):
        # Count matches (0x00 in XOR result)
        matches = 0
        limit = min(len(data), 2000)
        for i in range(limit - lag):
            if data[i] == data[i+lag]:
                matches += 1
        
        score = matches / (limit - lag)
        if score > best_score:
            best_score = score
            best_lag = lag
            
    print(f"Best Repeating Pattern Lag: {best_lag} (Coincidence: {best_score:.2%})")
    
    if best_score > 0.06: # Random is 1/256 ~= 0.004
        print(f"-> SUSPICIOUS: Pattern repeats every {best_lag} bytes.")
        print("   Possible reasons: Fixed Packet Size, or XOR Key of this length.")
        
        if packet_size > 0 and packet_size == best_lag:
             print("   (Matches known Packet Size, likely just structure, not encryption)")
        elif best_score > 0.15:
             print("   (High coincidence!) Could be a simple XOR mask.")
             
             # Try to derive key? 
             # Heuristic: Most common byte in ciphertext is likely XOR of Space (0x20) or Null (0x00) with key.
             # If protocol is binary, 0x00 is common. Key[i] = MostCommon(Stream[i::Lag]) ^ 0x00
             potential_key = []
             for i in range(best_lag):
                 col = data[i::best_lag]
                 c = collections.Counter(col).most_common(1)[0][0]
                 # Assume most common byte was 0x00 originally
                 key_byte = c ^ 0x00 
                 potential_key.append(key_byte)
                 
             print(f"   Potential XOR Key (assuming null-heavy plaintext): {bytes(potential_key).hex()}")

    # 3. Signature Scanner
    # Look for common crypto signatures? (PGP, TLS, etc.) - Out of scope for typical med devices
    # But we can check for "Magic Bytes" at start
    print(f"\n[Header Check] First 8 bytes: {data[:8].hex()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.crypto_scanner <CAPTURE_FILE> [KNOWN_PACKET_SIZE]")
    else:
        ps = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        analyze_crypto(sys.argv[1], ps)
