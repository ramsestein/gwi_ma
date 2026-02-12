import binascii
import struct

def parse_capture(hex_str):
    data = binascii.unhexlify(hex_str.replace('\n', ''))
    
    print(f"Total Bytes: {len(data)}")
    
    # Check for SLIP (0xC0 is END/START)
    if b'\xc0' in data:
        print("possible SLIP framing detected (0xC0 present)")
        frames = data.split(b'\xc0')
        for i, frame in enumerate(frames):
            if len(frame) == 0: continue
            
            # SLIP Escaping (0xDB 0xDC -> 0xC0, 0xDB 0xDD -> 0xDB)
            decoded = frame.replace(b'\xdb\xdc', b'\xc0').replace(b'\xdb\xdd', b'\xdb')
            
            print(f"\nFrame {i} (Len {len(decoded)}):")
            print(f"  HEX: {decoded.hex().upper()}")
            print(f"  ASCII: {decoded.decode('utf-8', errors='ignore')}")
            
            # Try to interpret first bytes
            if len(decoded) > 4:
                # Common Headers?
                # 0x11 could be ... ?
                header = decoded[:4].hex()
                print(f"  Header: {header}")

if __name__ == "__main__":
    with open("dumps/capture_sample.hex", "r") as f:
        content = f.read().strip()
    parse_capture(content)
