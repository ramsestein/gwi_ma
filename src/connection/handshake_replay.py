"""
Generic Serial Handshake Replayer

Replays a sequence of hex-encoded frames to a serial port to initialize a device connection.
Useful for protocols that require a specific startup sequence (like IntelliVue).

Usage:
    python src/handshake_replay.py <config.json>
    
Config JSON Format:
{
    "port": "COM4",
    "baudrate": 115200,
    "timeout": 1.0,
    "sequence": [
        {"tx": "1101...", "delay": 0.5, "desc": "Association Request"},
        {"tx": "1101...", "wait_for": "C0", "timeout": 2.0, "desc": "Connect Indication"}
    ]
}
"""
import serial
import time
import json
import sys
import binascii

def replay_handshake(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)

    port = config.get('port', 'COM1')
    baud = config.get('baudrate', 115200)
    
    print(f"Opening {port} @ {baud}...")
    try:
        ser = serial.Serial(port, baud, timeout=config.get('timeout', 1.0))
    except Exception as e:
        print(f"Error opening port: {e}")
        return

    print(f"Loaded sequence with {len(config['sequence'])} steps.")
    
    for i, step in enumerate(config['sequence']):
        desc = step.get('desc', f"Step {i+1}")
        tx_hex = step.get('tx', '').replace(' ', '')
        
        if tx_hex:
            tx_bytes = binascii.unhexlify(tx_hex)
            print(f"[TX] {desc} ({len(tx_bytes)} bytes)")
            ser.write(tx_bytes)
            ser.flush()

        delay = step.get('delay', 0)
        if delay > 0:
            time.sleep(delay)

        wait_pattern = step.get('wait_for', '')
        if wait_pattern:
            print(f"     Waiting for response containing '{wait_pattern}'...")
            start_wait = time.time()
            buffer = b''
            found = False
            while time.time() - start_wait < step.get('timeout', 1.0):
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting)
                    buffer += chunk
                    if binascii.unhexlify(wait_pattern) in buffer:
                        found = True
                        break
                time.sleep(0.01)
            
            if found:
                print(f"     [OK] Response received ({len(buffer)} bytes)")
            else:
                print(f"     [TIMEOUT] Pattern not found. Buffer: {buffer.hex().upper()[:40]}...")

    print("Handshake complete. Entering listener mode (Ctrl+C to stop)...")
    try:
        while True:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                print(f"[RX] {data.hex().upper()}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/handshake_replay.py <config.json>")
        sys.exit(1)
        
    replay_handshake(sys.argv[1])
