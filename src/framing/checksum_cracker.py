import sys

# Standard CRC Parameters: (Name, Width, Poly, Init, XorOut, RefIn, RefOut)
# We handle 8 and 16 bit common ones
CRC_MODELS = [
    ("CRC-8", 8, 0x07, 0x00, 0x00, False, False),
    ("CRC-8/ROHC", 8, 0x07, 0xFF, 0x00, True, True),
    ("CRC-8/MAXIM", 8, 0x31, 0x00, 0x00, True, True),
    ("SUM-8 (Modulo 256)", 8, 0, 0, 0, False, False), # Special
    ("XOR-8", 8, 0, 0, 0, False, False), # Special
    ("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, 0x0000, False, False),
    ("CRC-16/ARC", 16, 0x8005, 0x0000, 0x0000, True, True),
    ("CRC-16/XMODEM", 16, 0x1021, 0x0000, 0x0000, False, False),
    ("CRC-16/MODBUS", 16, 0x8005, 0xFFFF, 0x0000, True, True),
]

def calc_crc(data, model):
    name, width, poly, init, xor_out, ref_in, ref_out = model
    
    if name.startswith("SUM"):
        return sum(data) % 256
    if name.startswith("XOR"):
        x = 0
        for b in data: x ^= b
        return x
        
    crc = init
    mask = (1 << width) - 1
    
    for b in data:
        if ref_in:
            b = int('{:08b}'.format(b)[::-1], 2)
            
        if width == 8:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ poly
                else:
                    crc = (crc << 1)
            crc &= 0xFF
        else: # 16
            crc ^= (b << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ poly
                else:
                    crc = (crc << 1)
            crc &= 0xFFFF
            
    if ref_out:
        # Reflect result
        if width == 8:
            crc = int('{:08b}'.format(crc)[::-1], 2)
        else:
            crc = int('{:016b}'.format(crc)[::-1], 2)
            
    return crc ^ xor_out

def crack_checksum(filename, packet_size):
    print(f"--- Checksum Cracker: {filename} (Size: {packet_size}) ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    packets = [data[i:i+packet_size] for i in range(0, len(data), packet_size)]
    packets = [p for p in packets if len(p) == packet_size]
    
    if not packets: return
    
    print(f"Testing {len(CRC_MODELS)} models on {len(packets)} packets...")
    
    # Strategy: Assume checksum is at the END (last 1 or 2 bytes)
    # Check 1: Last Byte is Checksum of [0:-1]
    # Check 2: Last Byte is Checksum of [1:-1] (skip header)
    # Check 3: Last 2 Bytes are Checksum of [0:-2]
    
    scores = {m[0]: 0 for m in CRC_MODELS}
    
    for p in packets:
        # 8-bit check
        payload_full = p[:-1]
        payload_no_head = p[1:-1]
        target_8 = p[-1]
        
        # 16-bit check
        payload_16 = p[:-2]
        target_16_be = (p[-2] << 8) | p[-1]
        target_16_le = (p[-1] << 8) | p[-2]
        
        for model in CRC_MODELS:
            name, width, _, _, _, _, _ = model
            
            match = False
            if width == 8:
                c1 = calc_crc(payload_full, model)
                c2 = calc_crc(payload_no_head, model)
                if c1 == target_8 or c2 == target_8:
                    match = True
            else: # 16
                c = calc_crc(payload_16, model)
                if c == target_16_be or c == target_16_le:
                    match = True
                    
            if match:
                scores[name] += 1

    print("\n--- Results (Matches / Total Packets) ---")
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    best_name, best_score = sorted_scores[0]
    
    for name, score in sorted_scores:
        if score > 0:
            print(f"{name}: {score}/{len(packets)}")
            
    if best_score == len(packets):
        print(f"\n-> SUCCESS: Protocol uses {best_name}!")
    elif best_score > len(packets) * 0.9:
        print(f"\n-> LIKELY: Protocol uses {best_name} (some errors or misaligned).")
    else:
        print("\n-> FAILED: No standard CRC matched consistently.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.checksum_cracker <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        crack_checksum(sys.argv[1], int(sys.argv[2]))
