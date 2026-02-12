import serial
import time
import sys
import itertools

def negotiate_version(port, baudrate):
    print(f"--- Version Negotiation Fuzzer on {port} @ {baudrate} ---")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except Exception as e:
        print(f"Error opening port: {e}")
        return

    # Common Handshake Candidates
    # 1. Standard ASCII
    chk_ascii = [b"HELLO", b"VER", b"VERSION", b"CONNECT", b"?"]
    # 2. Control Characters
    chk_ctrl = [b"\x05", b"\x02", b"\x00", b"\x1B"] # ENQ, STX, NULL, ESC
    # 3. Binary Sequences
    chk_bin = [b"\xAA\x55", b"\xFF\xFF", b"\x00\xFF"]
    
    candidates = chk_ascii + chk_ctrl + chk_bin
    
    responses = {}
    
    print(f"Testing {len(candidates)} handshake candidates...")
    
    for payload in candidates:
        print(f"Sending: {payload.hex().upper()} ({payload}) ... ", end='', flush=True)
        
        # Clear buffer
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Send
        ser.write(payload)
        
        # Listen
        time.sleep(1.0)
        resp = ser.read(ser.in_waiting)
        
        if resp:
            print(f"Replied ({len(resp)} bytes): {resp[:10].hex().upper()}")
            # Store hash of response to group same behaviors
            resp_sig = (len(resp), resp[:5]) 
            if resp_sig not in responses:
                responses[resp_sig] = []
            responses[resp_sig].append(payload)
        else:
            print("No Response")

    ser.close()
    
    print("\n--- Negotiation Analysis ---")
    if not responses:
        print("Device remained silent for all candidates.")
    else:
        for sig, triggers in responses.items():
            l, start = sig
            print(f"Response Type [Len:{l}, Start:{start.hex().upper()}]: Triggered by {len(triggers)} inputs")
            print(f"  Sample Triggers: {[t.hex().upper() for t in triggers[:3]]}")
    
    # Versioning Inference
    if len(responses) > 1:
        print("\n-> Verdict: MULTIPLE BEHAVIORS DETECTED.")
        print("   The device reacts differently to different inputs.")
        print("   This strongly suggests a Negotiation/Handshake phase.")
    else:
        print("\n-> Verdict: Static behavior (or only 1 valid handshake found).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.version_negotiator <PORT> [BAUD]")
    else:
        baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
        negotiate_version(sys.argv[1], baud)
