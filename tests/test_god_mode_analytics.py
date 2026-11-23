import unittest
import struct
import math
import os
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis import entropy_analyzer
from src.analysis import semantic_explorer
from src.framing import packet_reassembler
from src.analysis import lut_detector
# Note: visualization tools like fft_analyzer might be harder to test headlessly via unit tests, 
# but we can test the calculation logic if extracted. 
# For now keeping to the pure logic modules.

class TestGodModeAnalytics(unittest.TestCase):

    def test_entropy_calculation(self):
        # Low entropy (all same)
        data_low = b'\x00' * 50
        ent_low = entropy_analyzer.calculate_entropy(data_low)
        self.assertEqual(ent_low, 0.0)

        # High entropy (random-ish)
        data_high = bytes(range(256))
        ent_high = entropy_analyzer.calculate_entropy(data_high)
        # Max entropy for 256 symbols is 8 bits
        self.assertAlmostEqual(ent_high, 8.0, delta=0.1)

    def test_semantic_ranges(self):
        # Create a fake packet with HR=60, SpO2=98
        # Format: [ID, HR, SPO2, TEMP]
        # Ranges: HR(30-250), SpO2(50-100)
        
        # We will mock the file reading by mocking open(), or easier: 
        # Refactor semantic_explorer to accept bytes, but since we can't easily refactor all now,
        # we will create a temporary file.
        
        tmp_file = "test_semantic.bin"
        with open(tmp_file, 'wb') as f:
            for i in range(10):
                # ID=0x01, HR=60+i, SpO2=98, Garbage=0xFF
                packet = struct.pack('BBBB', 0x01, 60+i, 98, 0xFF)
                f.write(packet)
                
        # Redirect stdout to capture output
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            semantic_explorer.analyze_semantics(tmp_file, 4)
        finally:
            sys.stdout = sys.__stdout__
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
                
        output = captured_output.getvalue()
        
        # HR should be detected at Offset 1
        # HR should be detected at Offset 1
        self.assertIn("HR (Heart Rate)", output)
        # Check for "1" at start of line or before HR
        # Output format: "1        | HR ..."
        self.assertTrue("1 " in output and "| HR" in output, "Offset 1 not associated with HR")
        
        # SpO2 should be detected at Offset 2
        self.assertIn("SpO2", output)
        
    def test_lut_detection(self):
        # Create a file with a counter (Offset 0) and a Status Enumeration (Offset 1)
        # Status only has values 0x10 and 0x20
        tmp_file = "test_lut.bin"
        with open(tmp_file, 'wb') as f:
            for i in range(50):
                status = 0x10 if i % 2 == 0 else 0x20
                f.write(struct.pack('BB', i, status))
                
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            lut_detector.detect_luts(tmp_file, 2)
        finally:
            sys.stdout = sys.__stdout__
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        
        output = captured_output.getvalue()
        
        # Offset 1 should be "Likely ENUM / STATUS"
        # We check for the verdict string
        self.assertIn("Likely ENUM / STATUS", output)
        self.assertIn("0x10", output)
        self.assertIn("0x20", output)

if __name__ == '__main__':
    unittest.main()
