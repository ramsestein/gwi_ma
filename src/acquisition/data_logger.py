import os
import serial
import time
import datetime
import threading
import queue
import sys
import struct

# Configuration
# You can hardcode these or make them arguments if you prefer
DEFAULT_BAUDRATE = 115200 

def log_data(port, baudrate):
    try:
        ser = serial.Serial(port, baudrate, timeout=0.1)
        print(f"Connected to {port} at {baudrate} baud.")
    except serial.SerialException as e:
        print(f"Error connecting to {port}: {e}")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Ensure results dir exists (it should, but safety first)
    if not os.path.exists("results"):
        os.makedirs("results")
        
    filename = os.path.join("results", f"capture_{timestamp}.bin")
    log_filename = os.path.join("results", f"capture_{timestamp}_events.txt")
    
    print(f"Logging raw data to {filename}")
    print(f"Logging events to {log_filename}")
    print("Press Ctrl+C to stop.")
    print("Type an event description and press Enter to mark an event (e.g., 'HR=80').")

    data_queue = queue.Queue()
    stop_event = threading.Event()

    def read_serial():
        with open(filename, "wb") as f:
            while not stop_event.is_set():
                try:
                    if ser.in_waiting > 0:
                        data = ser.read(ser.in_waiting)
                        if data:
                            f.write(data)
                            f.flush()
                            # Optional: print hex to screen? Might be too fast.
                            # print(data.hex(), end=' ', flush=True)
                    else:
                        time.sleep(0.01)
                except Exception as e:
                    print(f"Serial read error: {e}")
                    break

    serial_thread = threading.Thread(target=read_serial)
    serial_thread.start()

    try:
        with open(log_filename, "w") as log_f:
            while True:
                user_input = input() # Blocking input for user events
                timestamp_event = datetime.datetime.now().isoformat()
                log_entry = f"{timestamp_event}: {user_input}\n"
                log_f.write(log_entry)
                log_f.flush()
                print(f"Event logged: {user_input}")
                
    except KeyboardInterrupt:
        print("\nStopping logger...")
        stop_event.set()
        serial_thread.join()
        ser.close()
        print("Done.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_logger.py <COM_PORT> [BAUDRATE]")
        print("Example: python data_logger.py COM3 115200")
    else:
        port = sys.argv[1]
        baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUDRATE
        log_data(port, baud)
