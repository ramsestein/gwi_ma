import serial
import time
import sys

def scan_flow_control(port, baudrate=9600):
    print(f"--- Flow Control Scanner on {port} @ {baudrate} ---")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except Exception as e:
        print(f"Error: {e}")
        return

    # 1. Echo Detection
    print("\n[Echo Detection] Testing for electrical echo...")
    test_pattern = b"TEST1234"
    ser.write(test_pattern)
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting)
    
    if test_pattern in resp:
        print("-> ALERT: Device ECHOS commands back. (Half-Duplex or Local Echo ON)")
        print(f"   Received: {resp}")
    else:
        print("-> No Echo detected.")

    # 2. XON/XOFF Test
    print("\n[Software Flow Control] Testing XOFF (0x13)...")
    # Strategy: Send XOFF. If device stops, it supports it.
    # HARD to test without causing issues, but let's try measuring rate.
    
    # Listening baseline
    start = time.time()
    bytes_0 = 0
    while time.time() - start < 2.0:
        if ser.in_waiting:
            bytes_0 += len(ser.read(ser.in_waiting))
        time.sleep(0.1)
        
    print(f"   Baseline Rate: {bytes_0/2.0:.1f} bytes/sec")
    
    if bytes_0 > 0:
        # Send XOFF
        print("   Sending XOFF...")
        ser.write(b'\x13')
        
        # Measure
        start = time.time()
        bytes_1 = 0
        while time.time() - start < 2.0:
            if ser.in_waiting:
                bytes_1 += len(ser.read(ser.in_waiting))
            time.sleep(0.1)
            
        print(f"   Post-XOFF Rate: {bytes_1/2.0:.1f} bytes/sec")
        
        if bytes_1 < bytes_0 * 0.1:
            print("-> Verdict: Device SUPPORTS XON/XOFF (Stopped transmitting).")
            # Send XON to be nice
            ser.write(b'\x11')
        else:
             print("-> Verdict: Ignores XON/XOFF.")
    else:
        print("   (No data flowing, cannot test flow control)")

    ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.flow_control_scanner <PORT> [BAUD]")
    else:
        baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
        scan_flow_control(sys.argv[1], baud)
