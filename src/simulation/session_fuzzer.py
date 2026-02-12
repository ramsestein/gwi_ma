import sys
import serial
import time
import random

def fuzz_session(port, baudrate):
    print(f"--- Session Fuzzer: {port} @ {baudrate} ---")
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except:
        print("Error opening port.")
        return

    # 1. Keep-Alive / Watchdog Test
    print("\n[Watchdog Test] Listening for auto-disconnect...")
    # Passive listen
    ser.reset_input_buffer()
    start_time = time.time()
    last_data_time = start_time
    
    while time.time() - start_time < 10:
        if ser.in_waiting:
            ser.read(ser.in_waiting)
            last_data_time = time.time()
        time.sleep(0.1)
        
    silence_duration = time.time() - last_data_time
    if silence_duration > 5:
        print(f" -> stream DIED after {silence_duration:.1f}s of silence.")
        print(" -> Device likely needs Keep-Alive polling.")
    else:
        print(" -> Stream seems continuous (Passive mode ok).")

    # 2. Command Injection (Auth / Subscription)
    print("\n[Command Injection] Testing common medical control sequences...")
    commands = [
        b'\x05', # ENQ (Enquire)
        b'\x04', # EOT (End of Tx)
        b'\x16', # SYN (Synchronous Idle)
        b'START',
        b'CONNECT',
        b'\x1B\x44' # ESC+D (Common weird reset)
    ]
    
    for cmd in commands:
        print(f"Injecting: {cmd.hex()}... ", end='')
        ser.write(cmd)
        time.sleep(0.5)
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting)
            print(f"RESPONSE: {resp.hex().upper()}")
        else:
            print("No reaction.")

    ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.session_fuzzer <PORT> <BAUD>")
    else:
        fuzz_session(sys.argv[1], int(sys.argv[2]))
