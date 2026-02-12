import sys
import numpy as np
import matplotlib.pyplot as plt
import collections

def analyze_statistics(filename, max_lag=200):
    print(f"--- Statistical Analysis: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # Convert to numpy array of integers
    byte_array = np.frombuffer(data, dtype=np.uint8)
    n = len(byte_array)
    
    if n < max_lag * 2:
        print("Not enough data for autocorrelation.")
        return

    print(f"Analyzing {n} bytes...")

    # 1. Autocorrelation (Detect Periodic Structure)
    print("\n[Autocorrelation] Calculating periodicity...")
    # diverse stats allows us to see if byte[i] correlates with byte[i+k]
    # We'll do a simplified approach: Hamming distance or matching bytes at lag k
    
    lags = np.arange(1, max_lag)
    correlations = []
    
    # We want to find k where data[i] == data[i+k] often
    # Vectorized approach
    for k in lags:
        # Compare array[0:-k] with array[k:]
        matches = np.sum(byte_array[:-k] == byte_array[k:])
        correlations.append(matches / (n - k))
        
    correlations = np.array(correlations)
    
    # Find peaks
    threshold = np.mean(correlations) + 2 * np.std(correlations)
    peaks = np.where(correlations > threshold)[0]
    
    print("Significant Periodicity Peaks (Potential Packet Lengths):")
    if len(peaks) > 0:
        # Sort by correlation strength
        sorted_peaks = sorted(peaks, key=lambda i: correlations[i], reverse=True)
        for i in sorted_peaks[:5]:
            lag = lags[i]
            print(f"  Lag {lag}: Correlation {correlations[i]:.4f}")
    else:
        print("  No strong periodicity found.")

    # 2. Markov Chain Analysis (Transition Probability)
    print("\n[Markov Chain] Analyzing Byte Transitions...")
    # Matrix 256x256
    transitions = np.zeros((256, 256), dtype=np.int32)
    
    # Count transitions
    # We can use zip
    for b1, b2 in zip(byte_array[:-1], byte_array[1:]):
        transitions[b1, b2] += 1
        
    # Analyze high probability transitions
    print("Most probable transitions (Structure candidates):")
    structure_found = False
    
    for row in range(256):
        total = np.sum(transitions[row])
        if total > n * 0.005: # Only consider bytes that appear reasonably often
            # finding normalized probabilities
            probs = transitions[row] / total
            best_next = np.argmax(probs)
            max_prob = probs[best_next]
            
            if max_prob > 0.8: # If byte X is followed by byte Y > 80% of time
                print(f"  0x{row:02X} -> 0x{best_next:02X} (Prob: {max_prob:.2%})")
                structure_found = True
                
    if not structure_found:
        print("  No deterministic transitions found (High Entropy/Random).")

    # Plot (Autocorrelation)
    try:
        plt.figure(figsize=(10, 5))
        plt.plot(lags, correlations)
        plt.title(f"Byte Stream Autocorrelation (File: {filename})")
        plt.xlabel("Lag (Bytes)")
        plt.ylabel("Correlation Coefficient")
        plt.grid(True)
        # plt.show() # Uncomment to show window, or save
        out_png = filename + "_autocorr.png"
        plt.savefig(out_png)
        print(f"Saved plot to {out_png}")
    except Exception as e:
        print(f"Could not plot: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.stat_analyzer <CAPTURE_FILE> [MAX_LAG]")
    else:
        lag = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        analyze_statistics(sys.argv[1], lag)
