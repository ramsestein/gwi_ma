import serial
import time
import sys
import threading

def bridge(port_a, port_b, baud):
    try:
        ser_a = serial.Serial(port_a, baud, timeout=0.1)
        ser_b = serial.Serial(port_b, baud, timeout=0.1)
        print(f"Bridging {port_a} <==> {port_b} @ {baud}")
    except Exception as e:
        print(f"Error: {e}")
        return

    def forward(source, dest, label):
        try:
            while True:
                data = source.read(source.in_waiting or 1)
                if data:
                    print(f"[{label}] {data.hex()}")
                    dest.write(data)
        except Exception:
            pass

    t1 = threading.Thread(target=forward, args=(ser_a, ser_b, f"{port_a}->{port_b}"))
    t2 = threading.Thread(target=forward, args=(ser_b, ser_a, f"{port_b}->{port_a}"))
    
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m src.serial_bridge <port_device> <port_software> <baud>")
    else:
        bridge(sys.argv[1], sys.argv[2], int(sys.argv[3]))
