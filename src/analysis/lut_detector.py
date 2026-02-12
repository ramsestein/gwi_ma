import sys
import collections
import statistics

def detect_luts(filename, packet_size=None):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    if packet_size is None:
        try:
            packet_size = int(input("Enter Packet Size: "))
        except:
            return

    num_packets = len(data) // packet_size
    print(f"Scanning {num_packets} packets for Lookup Tables (LUTs)...")
    
    threshold_unique = min(20, num_packets * 0.1) # Arbitrary low number of unique values
    
    print(f"\n{'Offset':<6} | {'Unique':<6} | {'Top Values (Count)':<40} | {'Verdict'}")
    print("-" * 80)
    
    for offset in range(packet_size):
        # Extract column
        column = []
        for i in range(num_packets):
            idx = i * packet_size + offset
            if idx < len(data):
                column.append(data[idx])
                
        # Analyze
        counter = collections.Counter(column)
        unique_count = len(counter)
        most_common = counter.most_common(3)
        
        # Heuristics
        verdict = ""
        if unique_count == 1:
            verdict = "Constant (Not LUT)"
        elif unique_count < threshold_unique:
            # Check if values are small integers (0, 1, 2...) -> Index LUT
            # Or arbitrary bytes -> Status Enum
            
            keys = sorted(counter.keys())
            is_sequential = True
            for k in range(len(keys)-1):
                if keys[k+1] != keys[k] + 1:
                    is_sequential = False
                    break
            
            if is_sequential:
                verdict = "Likely INDEX (Sequential)"
            else:
                verdict = "Likely ENUM / STATUS"
        else:
            verdict = "Numeric / High Entropy"
            
        if "Likely" in verdict:
            top_str = ", ".join([f"0x{k:02X}({v})" for k,v in most_common])
            print(f"{offset:<6} | {unique_count:<6} | {top_str:<40} | {verdict}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.lut_detector <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        detect_luts(sys.argv[1], int(sys.argv[2]))
