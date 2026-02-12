import serial
import time
import sys
import serial.tools.list_ports

def scan_control_lines(port_name, baudrate=9600):
    print(f"\n[Physical Layer] Scanning Control Lines on {port_name}...")
    
    combinations = [
        (False, False), # DTR=0, RTS=0
        (True, False),  # DTR=1, RTS=0
        (False, True),  # DTR=0, RTS=1
        (True, True)    # DTR=1, RTS=1
    ]
    
    try:
        ser = serial.Serial(port_name, baudrate, timeout=1)
    except Exception as e:
        print(f"Could not open port: {e}")
        return

    results = []
    
    for dtr, rts in combinations:
        print(f"Testing state: DTR={int(dtr)}, RTS={int(rts)}...", end='', flush=True)
        
        ser.dtr = dtr
        ser.rts = rts
        ser.reset_input_buffer()
        
        # Listen for a bit
        time.sleep(1.5)
        
        if ser.in_waiting > 0:
            bytes_read = ser.read(ser.in_waiting)
            print(f" RECEIVED {len(bytes_read)} bytes.")
            print(f"  -> Sample: {bytes_read[:10].hex().upper()}")
            results.append((dtr, rts, bytes_read))
        else:
            print(" NO DATA.")
            
    ser.close()
    
    # Recommendation
    valid_configs = [r for r in results if len(r[2]) > 0]
    if not valid_configs:
        print("\n-> Verdict: No data received with any control line combination.")
    else:
        print(f"\n-> Verdict: {len(valid_configs)} combinations worked.")
        best = max(valid_configs, key=lambda x: len(x[2]))
        print(f"   Recommended: DTR={best[0]}, RTS={best[1]}")

def check_inverted_logic(raw_bytes):
    """
    Simulates inverted logic by bit-flipping the read bytes (NOT operation).
    Then checks if the result looks like meaningful text or low entropy data.
    """
    print(f"\n[Physical Layer] Checking for Inverted Logic (TTL/RS232 Mismatch)...")
    
    if not raw_bytes:
        print("No data to analyze.")
        return

    inverted = bytes([~b & 0xFF for b in raw_bytes])
    
    print(f"Original Sample: {raw_bytes[:10].hex().upper()}")
    print(f"Inverted Sample: {inverted[:10].hex().upper()}")
    
    # Heuristics
    # 1. Check for readable ASCII in inverted
    ascii_printables = sum(1 for b in inverted if 32 <= b <= 126)
    ascii_ratio = ascii_printables / len(inverted)
    
    print(f"Inverted ASCII Ratio: {ascii_ratio:.2%}")
    
    if ascii_ratio > 0.7:
        print("-> Verdict: HIGH PROBABILITY of Inverted Logic.")
        print("   The device might be outputting TTL levels to an RS232 port or vice versa.")
        print(f"   Decoded Text Preview: {inverted[:20]}")
    else:
        print("-> Verdict: Inverted logic unlikely (result is not clear ASCII).")
        # Could add check for common protocol headers here

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.physical_forensics <PORT> [BAUD]")
        print("Usage (Static Analysis): python -m src.physical_forensics analyze <BIN_FILE>")
    else:
        cmd = sys.argv[1]
        
        if cmd == "analyze":
             if len(sys.argv) < 3:
                 print("Need a bin file.")
             else:
                 with open(sys.argv[2], 'rb') as f:
                     data = f.read(100) # Read first 100 bytes
                 check_inverted_logic(data)
        else:
            baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
            scan_control_lines(cmd, baud)
