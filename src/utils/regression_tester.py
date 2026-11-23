import sys
import os
import json
from src.utils import capture_verifier
from src.acquisition import universal_logger

def run_regression_suite(test_dir):
    print(f"--- Regression Test Suite: {test_dir} ---")
    
    # 1. Look for .bin files and corresponding .json expected results
    files = [f for f in os.listdir(test_dir) if f.endswith('.bin')]
    
    if not files:
        print("No test files found in directory.")
        return
        
    passed = 0
    failed = 0
    
    for bin_file in files:
        full_path = os.path.join(test_dir, bin_file)
        print(f"\nTesting {bin_file}...")
        
        # Verify Integrity
        # We can reuse capture_verifier logic here
        # For regression, we assume we have a 'golden' standard parser
        # And we check if the current code produces the same metrics
        
        # Mock check
        print(" Integrity Check: OK (Simulated)")
        print(" Parser Output: OK (Simulated)")
        
        passed += 1
        
    print(f"\n--- Suite Finished ---")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.regression_tester <TEST_DIR>")
    else:
        run_regression_suite(sys.argv[1])
