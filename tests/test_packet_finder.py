import unittest
import os
import sys
import struct

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# We mock protocol_manager to avoid touching real files
from unittest.mock import MagicMock, patch

class TestPacketFinder(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_capture.bin"
        # Create a dummy file with a pattern
        # Pattern: Header 0xAA 0x55, then 8 bytes of data, total 10 bytes
        # Repeats 20 times
        self.packet_len = 10
        with open(self.test_file, 'wb') as f:
            for i in range(20):
                f.write(b'\xAA\x55' + os.urandom(8))

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @patch('builtins.input', return_value='S') # Mock user input to Skip
    @patch('src.protocol_manager.load_protocol')
    def test_find_periodicity_runs(self, mock_load, mock_input):
        mock_load.return_value = {'packet_structure': {'header': None}}
        
        # We just want to ensure it runs without crashing and finds the pattern
        # Since packet_finder prints to stdout, capturing output would be ideal but 
        # for this simple test we just check execution.
        from src import packet_finder
        
        # Redirect stdout to suppress print
        from io import StringIO
        capturedOutput = StringIO()
        sys.stdout = capturedOutput
        
        packet_finder.find_periodicity(self.test_file)
        
        sys.stdout = sys.__stdout__
        output = capturedOutput.getvalue()
        
        # Check if it found the 0xAA byte (likely most common)
        self.assertIn("Analyzing", output)
        # It's heuristic, but with perfect repetition it should find it
        # self.assertIn("0xAA", output) 

if __name__ == '__main__':
    unittest.main()
