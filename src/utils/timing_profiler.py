import sys
import csv
import statistics
import matplotlib.pyplot as plt

def analyze_timing(csv_file):
    print(f"--- Timing Profiler: {csv_file} ---")
    
    timestamps = []
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            # Try to find a timestamp column
            ts_col = None
            if 'PerfTimestamp' in reader.fieldnames:
                ts_col = 'PerfTimestamp'
            elif 'Timestamp' in reader.fieldnames:
                ts_col = 'Timestamp'
            
            if not ts_col:
                print("No suitable timestamp column found (PerfTimestamp/Timestamp).")
                return
                
            for row in reader:
                try:
                    val = float(row[ts_col])
                    timestamps.append(val)
                except:
                    pass
    except FileNotFoundError:
        print("File not found.")
        return

    if len(timestamps) < 2:
        print("Not enough data.")
        return
        
    # Calculate Deltas
    deltas = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    
    # Stats
    avg_delta = statistics.mean(deltas)
    stdev_delta = statistics.stdev(deltas)
    min_delta = min(deltas)
    max_delta = max(deltas)
    
    packet_rate = 1.0 / avg_delta if avg_delta > 0 else 0
    
    print(f"Processed {len(timestamps)} packets.")
    print(f"Avg Interval: {avg_delta*1000:.2f} ms")
    print(f"Packet Rate:  {packet_rate:.2f} Hz")
    print(f"Jitter (StdDev): {stdev_delta*1000:.2f} ms")
    
    # Burst Detection
    # If we see intervals significantly smaller than average followed by larger ones
    # Heuristic: Delta < Avg/2 is part of burst?
    
    short_intervals = sum(1 for d in deltas if d < avg_delta * 0.5)
    long_intervals = sum(1 for d in deltas if d > avg_delta * 2.0)
    
    print(f"\n[Burst Analysis]")
    print(f"Short Intervals (< 50% avg): {short_intervals}")
    print(f"Long Intervals (> 200% avg): {long_intervals}")
    
    if short_intervals > len(deltas) * 0.3 and long_intervals > len(deltas) * 0.05:
        print("-> Verdict: BURSTY TRAFFIC DETECTED.")
    else:
        print("-> Verdict: Consistent Stream (Low Burstiness).")

    # Plot
    try:
        plt.figure(figsize=(10, 6))
        
        plt.subplot(2, 1, 1)
        plt.plot(deltas)
        plt.title("Inter-Packet Arrival Times")
        plt.ylabel("Seconds")
        
        plt.subplot(2, 1, 2)
        plt.hist(deltas, bins=50)
        plt.title("Delta Histogram")
        plt.xlabel("Seconds")
        
        plt.tight_layout()
        out_png = csv_file + "_timing.png"
        plt.savefig(out_png)
        print(f"Saved plot to {out_png}")
    except Exception as e:
        print(f"Could not plot: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.timing_profiler <LOG_CSV>")
    else:
        analyze_timing(sys.argv[1])
