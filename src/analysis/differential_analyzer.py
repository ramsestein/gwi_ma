import sys
import difflib

def compare_files(file1, file2):
    try:
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            data1 = f1.read()
            data2 = f2.read()
    except FileNotFoundError:
        print("One of the files was not found.")
        return

    print(f"Comparing {file1} ({len(data1)} bytes) vs {file2} ({len(data2)} bytes)")

    min_len = min(len(data1), len(data2))
    diff_count = 0
    
    print("\n--- Byte-by-Byte Comparison (First 50 differences) ---")
    print(f"{'Offset':<10} | {file1:<15} | {file2:<15}")
    print("-" * 50)

    for i in range(min_len):
        b1 = data1[i]
        b2 = data2[i]
        if b1 != b2:
            diff_count += 1
            if diff_count <= 50:
                print(f"{i:<10} | {hex(b1):<15} | {hex(b2):<15}")
    
    if diff_count > 50:
        print(f"... and {diff_count - 50} more differences.")
    
    print(f"\nTotal different bytes: {diff_count} / {min_len} ({diff_count/min_len*100:.2f}%)")

    # Simple constant detection
    # If a byte is the same in both files at the same offset, it might be a header or structure
    print("\n--- Potential Fixed Headers/Structure (First 20 sequences > 3 bytes) ---")
    match_len = 0
    match_start = 0
    matches_found = 0
    
    for i in range(min_len):
        if data1[i] == data2[i]:
            if match_len == 0:
                match_start = i
            match_len += 1
        else:
            if match_len >= 3 and matches_found < 20: # filtering for significant matches
                seq = data1[match_start:match_start+match_len]
                print(f"Offset {match_start}: {seq.hex()} (Len: {match_len})")
                matches_found += 1
            match_len = 0

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python differential_analyzer.py <FILE1> <FILE2>")
    else:
        compare_files(sys.argv[1], sys.argv[2])
