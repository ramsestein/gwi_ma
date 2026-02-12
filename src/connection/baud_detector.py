import serial
import sys
import time
import collections

STANDARD_BAUDS = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

def rate_quality(data):
    if not data: return 0.0
    
    # metrics
    total = len(data)
    ascii_print = sum(1 for b in data if 32 <= b <= 126 or b in [10, 13])
    nulls = data.count(b'\x00')
    ffs = data.count(b'\xFF')
    high_bit = sum(1 for b in data if b > 127)
    
    # Heuristics
    # 1. Too many NULLs or FFs often means framing error or wrong baud
    if nulls > total * 0.5 or ffs > total * 0.5:
        return 0.1
        
    # 2. Pure ASCII is a strong signal
    score = (ascii_print / total) * 100
    
    # 3. Structure / Entropy check (optional, simple here)
    # If we have repeated patterns, that's good.
    counts = collections.Counter(data)
    if len(counts) < 5 and total > 50:
        # Suspiciously low variance (garbage)
        return 0.2
        
    return score

def detect_baud(port):
    print(f"--- Smart Baud Detector on {port} ---")
    
    scores = []
    
    for baud in STANDARD_BAUDS:
        print(f"Testing {baud}...", end='', flush=True)
        try:
            ser = serial.Serial(port, baud, timeout=1.5)
            ser.reset_input_buffer()
            # Wait for data
            time.sleep(1.0)
            if ser.in_waiting > 0:
                data = ser.read(min(ser.in_waiting, 500))
                score = rate_quality(data)
                scores.append((baud, score, len(data)))
                print(f" Read {len(data)} bytes. Quality Score: {score:.1f}")
            else:
                print(" No Data.")
            ser.close()
        except Exception as e:
            print(f" Error: {e}")
            
    # Verdict
    print("\n--- Results ---")
    scores.sort(key=lambda x: x[1], reverse=True)
    
    if not scores:
        print("No valid data received on any baud rate.")
        return

    best_baud, best_score, count = scores[0]
    
    if best_score > 80:
        print(f"-> Verdict: HIGH CONFIDENCE in {best_baud} baud (Score: {best_score:.1f}).")
        print("   Likely ASCII or Structured Data.")
    elif best_score > 40:
        print(f"-> Verdict: PROBABLE match at {best_baud} baud (Score: {best_score:.1f}).")
        print("   Might be Binary protocol.")
    else:
        print("-> Verdict: INCONCLUSIVE. Highest score was low.")
        print("   Check cabling, inverted logic, or non-standard baud rates.")

    print("\nTop 3 Candidates:")
    for b, s, c in scores[:3]:
        print(f"  {b} baud: Score {s:.1f} ({c} bytes analyzed)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.baud_detector <PORT>")
    else:
        detect_baud(sys.argv[1])
