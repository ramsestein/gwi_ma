import serial
import time
import sys

# Common wakeup/handshake bytes and strings
FUZZ_PAYLOADS = [
    b'\x05', # ENQ
    b'\x02', # STX
    b'\x00', # NULL
    b'\x0D', # CR
    b'\x0A', # LF
    b'\x1B', # ESC
    b'HELLO\r',
    b'ID\r',
    b'VER\r',
    b'?',
    b'\x01\x0D', # SOH CR
]

def fuzz(port, baud):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"Fuzzing {port} @ {baud}...")
    except Exception as e:
        print(f"Error opening port: {e}")
        return

    print("Listening for initial silence...")
    time.sleep(2)
    
    if ser.in_waiting > 0:
        print("Device is already sending data! No need to fuzz.")
        print(f"Received: {ser.read(ser.in_waiting)}")
        ser.close()
        return

    for payload in FUZZ_PAYLOADS:
        print(f"Sending: {payload.hex()} ({payload})")
        ser.write(payload)
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            resp = ser.read(ser.in_waiting)
            print(f"\n[!] RESPONSE DETECTED!")
            print(f"    Trigger: {payload.hex()}")
            print(f"    Response: {resp.hex()} ({resp})")
            print("    Keep this trigger in mind for the protocol definition!")
            break
        else:
            print("    No response.")
            
    print("\nFuzzing complete.")
    ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.command_fuzzer <port> <baud>")
    else:
        fuzz(sys.argv[1], int(sys.argv[2]))
