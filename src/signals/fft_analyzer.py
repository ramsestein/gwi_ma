import sys
import numpy as np
import matplotlib.pyplot as plt

def analyze_fft(filename, packet_size, offset):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    # Extract column
    values = []
    num_packets = len(data) // packet_size
    for i in range(num_packets):
        idx = i * packet_size + offset
        if idx < len(data):
            values.append(data[idx])

    if not values:
        print("No data extracted.")
        return

    print(f"Analyzing {len(values)} samples at Offset {offset}...")
    
    # Convert to numpy array
    signal = np.array(values)
    
    # Remove DC component (mean) to see fluctuations better
    signal_ac = signal - np.mean(signal)
    
    # FFT
    fft_vals = np.fft.rfft(signal_ac)
    fft_freq = np.fft.rfftfreq(len(signal_ac))
    
    # Magnitude
    magnitude = np.abs(fft_vals)
    
    # Peak detection
    peak_idx = np.argmax(magnitude)
    peak_freq = fft_freq[peak_idx]
    
    print(f"Dominant Frequency (Relative): {peak_freq:.4f}")
    
    # Interpretation attempt
    # If packet rate is X Hz, then Real Freq = peak_freq * X
    print("Note: To get Hz, multiply Relative Freq by Packet Rate (packets/sec).")
    
    if peak_freq < 0.001:
        print(" -> Static/DC signal (Status byte or Flag)")
    elif mag_variance(magnitude) > 50: # Arbitrary threshold for "spiky" spectrum
        print(" -> Periodic Signal (Likely Waveform or Counter)")
    else:
        print(" -> Noise-like or insufficient periodicity")

    # Plot
    try:
        plt.figure(figsize=(10, 6))
        
        plt.subplot(2, 1, 1)
        plt.plot(signal[:500]) # Plot first 500 samples
        plt.title(f"Raw Signal (Offset {offset}) - First 500 samples")
        plt.grid(True)
        
        plt.subplot(2, 1, 2)
        plt.plot(fft_freq, magnitude)
        plt.title("Frequency Spectrum (FFT)")
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Could not plot: {e}")

def mag_variance(magnitude):
    # Normalized interaction to check if there are distinct peaks
    return np.std(magnitude) / (np.mean(magnitude) + 1e-6)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m src.fft_analyzer <CAPTURE_FILE> <PACKET_SIZE> <OFFSET>")
    else:
        analyze_fft(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
