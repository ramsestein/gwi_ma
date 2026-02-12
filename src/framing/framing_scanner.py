import sys
import collections

def analyze_framing_strategies(filename):
    print(f"--- Framing Master Analysis: {filename} ---")
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    if not data: return

    verdicts = []

    # 1. HDLC Detection (Flag 0x7E)
    hdlc_flags = data.count(b'\x7E')
    if hdlc_flags > 5:
        avg_dist = len(data) / hdlc_flags
        verdicts.append(f"HDLC / Flag-based (Found {hdlc_flags} 0x7E flags, avg dist {avg_dist:.1f})")

    # 2. SLIP Detection (0xC0, 0xDB)
    slip_ends = data.count(b'\xC0')
    slip_escs = data.count(b'\xDB')
    if slip_ends > 5:
        verdicts.append(f"SLIP Protocol (Found {slip_ends} END bytes, {slip_escs} ESC bytes)")
        
        # Check for IntelliVue MIB signature (SLIP + 11 01 ... E1 00)
        # We look for C0 11 01 or C0 around it
        if b'\xC0\x11\x01' in data or b'\xC0\x09\x01' in data:
            verdicts.append("  -> Potential IntelliVue MIB Protocol detected (11 01 Session Header)")


    # 3. ASCII Lines (CR/LF)
    crs = data.count(b'\r')
    lfs = data.count(b'\n')
    crlfs = data.count(b'\r\n')
    
    if crlfs > 5:
        verdicts.append(f"ASCII Line-based (CRLF) - Found {crlfs} lines")
    elif crs > 5 and lfs == 0:
        verdicts.append(f"ASCII Line-based (CR only) - Found {crs} lines")
    elif lfs > 5 and crs == 0:
        verdicts.append(f"ASCII Line-based (LF only) - Found {lfs} lines")

    # 4. Length Byte Heuristic (Binary Variable Length)
    # We iterate small possible offsets (0..4) and assume they are length
    best_len_match = (0, 0) # (Offset, Score)
    
    for offset in range(4): # Check first 4 bytes as candidate for length
        # Start at 0
        idx = 0
        matches = 0
        total_checks = 0
        
        while idx + offset < len(data):
            # Predicted length
            plen = data[idx+offset]
            
            # Sanity check for length
            if plen < 4 or plen > 200: 
                idx += 1
                continue
                
            # Jump
            next_idx = idx + plen
            total_checks += 1
            
            # Check if this "structure" holds? 
            # Ideally we check if the NEXT packet also has a valid length
            # But simpler: check if we just don't crash and maybe patterns look similar?
            
            # Let's verify by "Header Consistency" 
            # If we assume Byte 0 is header, does data[next_idx] == data[idx]?
            if next_idx < len(data) and data[next_idx] == data[idx]:
                matches += 1
                
            idx = next_idx

        # Score this offset
        # IF matches > 5 and ratio is high
        if total_checks > 5:
            ratio = matches / total_checks
            if ratio > 0.8:
                verdicts.append(f"Variable Length Binary (Length at Offset {offset}, Header Byte 0x{data[0]:02X})")

    # 5. Sentinel (STX/ETX)
    stx = data.count(b'\x02')
    etx = data.count(b'\x03')
    if stx > 5 and etx > 5 and abs(stx - etx) < stx * 0.2:
        verdicts.append("STX/ETX Framed (Start/End Text Markers)")


    print("\n--- Detected Framing Strategies ---")
    if verdicts:
        for v in verdicts:
            print(f"- {v}")
    else:
        print("No standard framing detected. Likely Fixed Length (use packet_finder.py) or Proprietary.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.framing_scanner <CAPTURE_FILE>")
    else:
        analyze_framing_strategies(sys.argv[1])
