import serial
import time
import sys
import os

def simulate_device(port, baud, capture_file):
    try:
        # For simulation we usually need a virtual port pair (e.g. COM10 <-> COM11)
        # We connect to one end, the logger connects to the other.
        ser = serial.Serial(port, baud)
        print(f"Simulator streaming on {port} @ {baud}")
        print(f"playing {capture_file}...")
    except Exception as e:
        print(f"Error opening port {port}: {e}")
        return

    with open(capture_file, 'rb') as f:
        data = f.read()

    # Loop forever
    try:
        while True:
            # Send in chunks to simulate timing (rough approximation)
            chunk_size = 10
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i+chunk_size]
                ser.write(chunk)
                time.sleep(0.01) # 10ms per 10 bytes approx
                
            print("Looping playback...")
            time.sleep(1) # Gap between loops
            
    except KeyboardInterrupt:
        print("Stopped.")
        ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m src.device_simulator <virtual_port> <baud> <capture_file>")
        print("Note: You need a virtual serial port pair (like com0com) for this to work with real software.")
    else:
        simulate_device(sys.argv[1], int(sys.argv[2]), sys.argv[3])
