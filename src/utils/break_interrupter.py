import serial
import time
import sys

def send_break(port, baud=115200):
    print(f"--- Sending Serial Break on {port} ---")
    print("Strategy: Power DTR/RTS -> Send BREAK (Reset UART) -> Listen")
    
    try:
        # OPEN PORT
        ser = serial.Serial(port, baud, timeout=1.0, rtscts=False, dsrdtr=False)
        
        # POWER UP
        ser.dtr = True
        ser.rts = True
        ser.reset_input_buffer()
        print(" [State] Power ON.")
        time.sleep(1.0)
        
        # SEND BREAK
        print(" [Tx] Sending BREAK signal (0.5s)...")
        ser.send_break(duration=0.5)
        print(" [Tx] BREAK sent.")
        
        # LISTEN
        print(" [Rx] Listening for response (post-reset)...")
        start_time = time.time()
        while time.time() - start_time < 10:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                if len(data) > 0:
                    print(f"\n[SUCCESS] RESPONSE: {data.hex().upper()}")
                    return
            time.sleep(0.01)
            
        print("\n--- No Response ---")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try: ser.close()
        except: pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.break_interrupter <PORT>")
    else:
        send_break(sys.argv[1])
