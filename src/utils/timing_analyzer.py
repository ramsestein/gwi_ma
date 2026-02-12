import serial
import time
import sys
import statistics

def analyze_timing(port, baud):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"Listening on {port} @ {baud} for timing analysis...")
    except Exception as e:
        print(f"Error: {e}")
        return

    print("Collecting data... (Press Ctrl+C to stop and see stats)")
    
    deltas = []
    last_time = time.time()
    
    try:
        while True:
            if ser.in_waiting > 0:
                # Read one byte at a time to be precise
                ser.read(1)
                now = time.time()
                delta = (now - last_time) * 1000 # ms
                if delta > 1: # Ignore super fast bursts (CPU tick resolution limits)
                    deltas.append(delta)
                    # print(f"{delta:.2f} ms") # Too verbose
                last_time = now
            else:
                pass # Busy wait for precision
                
    except KeyboardInterrupt:
        print("\nAnalysis Stopped.")
        if not deltas:
            print("No data received.")
            return

        print(f"\nCaptured {len(deltas)} gaps.")
        
        # Filter typical byte intervals vs packet gaps
        # Rough heuristic: Gaps > 10ms might be packet boundaries
        gaps = [d for d in deltas if d > 10]
        
        if gaps:
            print("\nPotential Packet Delimiters (Gaps > 10ms):")
            print(f"Min Gap: {min(gaps):.2f} ms")
            print(f"Max Gap: {max(gaps):.2f} ms")
            print(f"Avg Gap: {statistics.mean(gaps):.2f} ms")
            try:
                print(f"Mode Gap: {statistics.mode(gaps):.2f} ms")
            except: pass
        else:
            print("No significant gaps found. Continuous stream?")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.timing_analyzer <port> <baud>")
    else:
        analyze_timing(sys.argv[1], int(sys.argv[2]))
