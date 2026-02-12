import serial
import serial.tools.list_ports
import json
import time

def scan_ports():
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
        return []
    return [port.device for port in ports]

def scan_configurations():
    ports = scan_ports()
    if not ports:
        return

    baudrates = [115200]
    parities = [serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD]
    stopbits = [serial.STOPBITS_ONE, serial.STOPBITS_TWO]
    bytesizes = [serial.SEVENBITS, serial.EIGHTBITS]

    valid_configs = []

    print(f"Found ports: {ports}")

    for port in ports:
        print(f"Scanning port: {port}")
        for baud in baudrates:
            for parity in parities:
                for stop in stopbits:
                    for size in bytesizes:
                        config_desc = f"Baud: {baud}, Parity: {parity}, Stop: {stop}, Size: {size}"
                        print(f"Testing {config_desc} (Waiting 15s)...", end='\r')
                        
                        try:
                            with serial.Serial(port, baudrate=baud, parity=parity, stopbits=stop, bytesize=size, timeout=1) as ser:
                                # Try to read for a bit
                                time.sleep(15) # User requested "Patience = 15s"
                                if ser.in_waiting > 0:
                                    data = ser.read(ser.in_waiting)
                                    print(f"\n\n[DETECTED DATA] on {port} with {config_desc}")
                                    print(f"Hex: {data.hex()}")
                                    try:
                                        print(f"ASCII: {data.decode('utf-8', errors='ignore')}")
                                    except:
                                        print("ASCII: (decode error)")
                                    
                                    user_input = input("Is this valid? (S/N): ").strip().upper()
                                    if user_input == 'S':
                                        valid_configs.append({
                                            'port': port,
                                            'baudrate': baud,
                                            'parity': parity,
                                            'stopbits': stop,
                                            'bytesize': size
                                        })
                                        print("Configuration saved.")
                                        
                                        # Write immediately to file just in case
                                        with open('valid_configs.json', 'w') as f:
                                            json.dump(valid_configs, f, indent=4)
                                    else:
                                        print("Discarded.")
                        except serial.SerialException as e:
                            # print(f"\nError opening {config_desc}: {e}")
                            pass
                        except Exception as e:
                            print(f"\nUnexpected error: {e}")

    print("\nScan complete.")
    if valid_configs:
        print(f"Found {len(valid_configs)} valid configurations.")
        with open('valid_configs.json', 'w') as f:
            json.dump(valid_configs, f, indent=4)
        print("Saved to valid_configs.json")
    else:
        print("No valid configurations found/saved.")

if __name__ == "__main__":
    scan_configurations()
