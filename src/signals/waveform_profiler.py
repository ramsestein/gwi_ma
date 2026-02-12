import sys
import math

def profile_waveform(filename, packet_size, offset):
    print(f"--- Waveform Profiler: {filename} (Offset {offset}) ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    num_packets = len(data) // packet_size
    values = []
    
    # Extract
    for i in range(num_packets):
        idx = i * packet_size + offset
        if idx < len(data):
            values.append(data[idx])
            
    if not values: return

    # 1. ADC Resolution
    vmin = min(values)
    vmax = max(values)
    vrange = vmax - vmin
    
    print(f"Range: [{vmin}, {vmax}] (Delta: {vrange})")
    
    res_bits = 0
    if vmax < 256: res_bits = 8
    elif vmax < 1024: res_bits = 10
    elif vmax < 4096: res_bits = 12
    elif vmax < 65536: res_bits = 16
    else: res_bits = ">16"
    
    print(f"Estimated ADC Resolution: {res_bits}-bit")
    
    # 2. Interleaving Detection
    # If standard deviation of Even samples vs Odd samples is vastly different, 
    # or if their means are far apart, they are likely different channels.
    even_vals = values[0::2]
    odd_vals = values[1::2]
    
    mean_even = sum(even_vals)/len(even_vals)
    mean_odd = sum(odd_vals)/len(odd_vals)
    
    diff_percent = abs(mean_even - mean_odd) / ((mean_even + mean_odd)/2 + 0.001)
    
    print(f"Interleaving Check (Even vs Odd mean diff): {diff_percent:.2%}")
    if diff_percent > 0.2: # 20% difference
        print(" -> HIGH PROBABILITY of Interleaved Channels (e.g. ECG1, ECG2, ECG1, ECG2...)")
    else:
        print(" -> Likely Single Channel (or channels have similar baselines).")
        
    # 3. Sample Rate (Estimation)
    # We need user input for Link Speed or Packet Rate
    print("\nTo estimate Sample Rate, enter observed Packet Rate (packets/sec).")
    print("If unknown, press Enter.")
    try:
        pr_str = input("Packet Rate: ")
        if pr_str:
            pr = float(pr_str)
            # If interleaved, sample rate is PR / 2
            if diff_percent > 0.2:
                print(f"Estimated Sample Rate (Interleaved): {pr/2:.1f} Hz")
            else:
                print(f"Estimated Sample Rate (Single): {pr:.1f} Hz")
    except:
        pass

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m src.waveform_profiler <CAPTURE_FILE> <PACKET_SIZE> <OFFSET>")
    else:
        profile_waveform(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
