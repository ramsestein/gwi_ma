import sys
import struct

# Common CRC-16 Tables (truncated for brevity, usually generated or imported)
# For this script we will use a library approach or simple implementations

def calculate_checksums(data):
    results = {}
    
    # Simple Sums
    results['Sum (8-bit)'] = sum(data) & 0xFF
    results['Sum (16-bit)'] = sum(data) & 0xFFFF
    results['XOR (8-bit)'] = 0
    for b in data:
        results['XOR (8-bit)'] ^= b
        
    # 2's Complement
    results['2s Complement (8-bit)'] = (0 - sum(data)) & 0xFF
    
    return results

def find_checksum(packet_bytes):
    # Assume the checksum is at the END of the packet (last 1 or 2 bytes)
    # We test the payload (everything except last 1 or 2 bytes)
    
    if len(packet_bytes) < 4:
        return

    print(f"Testing packet (len={len(packet_bytes)}): {packet_bytes.hex()}")

    # Check 1-byte checksum at the end
    payload_1 = packet_bytes[:-1]
    target_1 = packet_bytes[-1]
    
    calcs_1 = calculate_checksums(payload_1)
    
    for name, val in calcs_1.items():
        if val == target_1:
            print(f"  [MATCH] 1-byte Checksum '{name}': Calculated 0x{val:02X} == Target 0x{target_1:02X}")

    # Check 2-byte checksum at the end (Little Endian)
    payload_2 = packet_bytes[:-2]
    target_2 = struct.unpack('<H', packet_bytes[-2:])[0]
    
    calcs_2 = calculate_checksums(payload_2)
    # Note: Adding full CRC16 logic here would be long, but we can check simple sums
    if calcs_2['Sum (16-bit)'] == target_2:
        print(f"  [MATCH] 2-byte Sum (LE): Calculated 0x{calcs_2['Sum (16-bit)']:04X} == Target 0x{target_2:04X}")

    # Check 2-byte checksum at the end (Big Endian)
    target_2_be = struct.unpack('>H', packet_bytes[-2:])[0]
    if calcs_2['Sum (16-bit)'] == target_2_be:
         print(f"  [MATCH] 2-byte Sum (BE): Calculated 0x{calcs_2['Sum (16-bit)']:04X} == Target 0x{target_2_be:04X}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python checksum_finder.py <HEX_STRING>")
        print("Example: python checksum_finder.py AA55010203FC")
    else:
        hex_str = sys.argv[1].replace(' ', '')
        try:
            data = bytes.fromhex(hex_str)
            find_checksum(data)
        except ValueError:
            print("Invalid hex string.")
