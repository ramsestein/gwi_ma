import sys
import os

def analyze_bits(filename, target_byte_index=None):
    with open(filename, 'rb') as f:
        data = f.read()

    print(f"Analyzing {len(data)} bytes in {filename}...")
    
    if target_byte_index is None:
        # Overview Mode: Find bytes that change
        # Logic: If we align by packet size, we could check specific columns.
        # Without packet alignment, it's hard to track "byte 4 of packet".
        # Let's assume user gives us a Period/Packet Size or we look for "most variable bytes"
        print("Usage hint: Provide a packet size to align the data grid.")
        # For now, just a simple heatmap of bit transitions is too complex for console
        # Let's just do a bit toggle counter
        print("Calculating bit variability...")
        # This is a naive check across the whole stream
        return

    # Column Mode: We act as if the file is a matrix of width `period`
    # Wait, the user usually wants to see "Byte X" inside the packet.
    # So we need packet size.
    
def analyze_column_bits(filename, packet_size, offset):
    with open(filename, 'rb') as f:
        data = f.read()
    
    # Slice data
    values = []
    for i in range(offset, len(data), packet_size):
        values.append(data[i])
        
    print(f"extracted {len(values)} samples of Byte Offset {offset} (Packet Size {packet_size})")
    
    print("\nBit History (Oldest -> Newest):")
    print("idx | Hex | Bin      | Flags (76543210)")
    print("-" * 40)
    
    # Collapse identical consecutive rows to save space
    last_val = -1
    for i, val in enumerate(values):
        if val == last_val and i < len(values)-1:
            continue
            
        bin_str = format(val, '08b')
        print(f"{i:4} | {val:02X}  | {bin_str} | ", end='')
        
        # Visualize flags
        flags = []
        for bit_idx in range(8):
            if (val >> bit_idx) & 1:
                flags.append(str(bit_idx))
            else:
                flags.append('.')
        print(''.join(reversed(flags)))
        
        last_val = val

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m src.bit_analyzer <filename> <packet_size> <byte_offset>")
    else:
        analyze_column_bits(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
