import sys
import collections

def track_dependencies(filename, packet_size):
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print("File not found.")
        return

    num_packets = len(data) // packet_size
    print(f"Scanning {num_packets} packets for Inter-Packet Dependencies...")
    
    # We look for: Value in Packet N [Offset X]  ==>  Changes Structure/Content of Packet N+1
    
    # Simple Heuristic:
    # Does a field in Packet N predict the ID of Packet N+1?
    
    # Extract columns
    columns = collections.defaultdict(list)
    for i in range(num_packets):
        start = i * packet_size
        packet = data[start : start + packet_size]
        for off, val in enumerate(packet):
            columns[off].append(val)
            
    # Assuming Offset 0 is ID (Multiplexing)
    ids = columns[0]
    
    # Check correlations between Packet N (Offset X) and Packet N+1 (Offset 0 aka ID)
    print("\n[Predictive Analysis] Can previous packet fields predict next Packet ID?")
    
    for offset in range(1, packet_size):
        # We check pairs: (Val_N_Offset, ID_N_Plus_1)
        pairs = []
        for i in range(num_packets - 1):
            val_n = columns[offset][i]
            id_next = ids[i+1]
            pairs.append((val_n, id_next))
            
        # Calculate conditional entropy or just consistence
        # Map: Val_N -> Set(ID_Next)
        mapping = collections.defaultdict(set)
        for v, next_id in pairs:
            mapping[v].add(next_id)
            
        # Evaluation
        predictive_power = 0
        total_unique_vals = len(mapping)
        if total_unique_vals < 2: continue # Constant field, useless
        
        deterministic_count = 0
        for v, possible_nexts in mapping.items():
            if len(possible_nexts) == 1:
                deterministic_count += 1
                
        percent_det = deterministic_count / total_unique_vals
        
        if percent_det > 0.8:
            print(f"Offset {offset} is HIGHLY PREDICTIVE of next Packet ID ({percent_det:.0%} deterministic).")
            print(" -> This implies a 'Request-Response' or 'Sequence State Machine'.")
            
    # Time Series Dependencies
    # Does Offset X increment?
    for offset in range(packet_size):
        col = columns[offset]
        diffs = [(col[i+1] - col[i]) % 256 for i in range(len(col)-1)]
        common_diff = collections.Counter(diffs).most_common(1)
        if common_diff and common_diff[0][1] > len(diffs)*0.9:
            print(f"Offset {offset} behaves as a COUNTER (Increment {common_diff[0][0]}).")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.dependency_tracker <CAPTURE_FILE> <PACKET_SIZE>")
    else:
        track_dependencies(sys.argv[1], int(sys.argv[2]))
