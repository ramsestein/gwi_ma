import sys
import time
import serial

def analyze_behavior(port, baudrate):
    print(f"--- Behavior Modeler: {port} @ {baudrate} ---")
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except:
        print("Error opening port.")
        return

    # 1. Inter-Byte Timeout (Packet fragmentation behavior)
    # Determine if device pushes data in blocks or byte-by-byte
    print("\n[Transmission Strategy] Listening...")
    ser.reset_input_buffer()
    
    # Capture 2 seconds
    start = time.time()
    chunks = []
    
    while time.time() - start < 2.0:
        if ser.in_waiting:
            c = ser.read(ser.in_waiting)
            chunks.append((time.perf_counter(), len(c)))
        time.sleep(0.01) # 10ms poll
        
    print(f"Received {len(chunks)} chunks.")
    if not chunks:
        print("No data received.")
    else:
        avg_chunk = sum(c[1] for c in chunks) / len(chunks)
        print(f"Avg Chunk Size: {avg_chunk:.1f} bytes.")
        if avg_chunk < 2:
            print("-> Device sends Byte-by-Byte (Real-time).")
        else:
            print("-> Device buffers data (Burst transmission).")

    # 2. Error Recovery (Requires Active Fuzzing)
    print("\n[Error Recovery] Sending Garbage...")
    # Does it stop? Does it send NAK?
    garbage = b'\xFF\xFF\xFF\x00\x00\x00' * 5
    ser.write(garbage)
    
    time.sleep(1.0)
    resp = ser.read(ser.in_waiting)
    
    if len(resp) == 0:
        print("-> Reaction: SILENCE (Device ignores garbage or crashed).")
    else:
        print(f"-> Reaction: CONTINUED (Received {len(resp)} bytes).")
        # Check if response is error code
        if b'ERR' in resp or b'NAK' in resp or b'\x15' in resp:
             print("   CRITICAL: Device sent NAK/Error Code!")
        elif resp == garbage:
             print("   (It just echoed the garbage back - Loopback?)")
        else:
             print("   (Normal data flow continues - Robust).")

    # 3. Buffer Overflow Test
    # If we stop reading, how long until it chokes?
    # Hard to test without potentially hanging the OS buffer, skipping for safety 
    # unless user specifically asks.
    print("\n[Buffer Test] Skipped (Unsafe for active connection).")

    ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.behavior_modeler <PORT> <BAUD>")
    else:
        analyze_behavior(sys.argv[1], int(sys.argv[2]))
