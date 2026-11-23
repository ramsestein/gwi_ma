import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.connection import baud_detector
from src.framing import framing_scanner
from src.utils import capture_verifier

class TestGodModeScanners(unittest.TestCase):

    @patch('src.connection.baud_detector.serial.Serial')
    @patch('src.connection.baud_detector.time.sleep') # Skip sleep
    def test_baud_detector(self, mock_sleep, mock_serial_cls):
        # Mock Serial instance
        mock_ser = MagicMock()
        mock_serial_cls.return_value = mock_ser
        
        # Setup scenario: 9600 baud returns valid ASCII, others return garbage
        def side_effect_read(count):
            # If baud is 9600 (we check the call args of constructor later, 
            # but simpler is to check current "baud" if the logic creates new instances)
            # The logic creates a new Serial for each baud.
            # We can't easily distinguish inside side_effect unless we track calls.
            return b"Hello World" 
            
        mock_ser.read.return_value = b"Hello World"
        mock_ser.in_waiting = 10
        
        # Capture Output
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            # We assume baud_detector iterates standard bauds. 
            # We just want to see if it runs and calculates score.
            baud_detector.detect_baud("COM_TEST")
        finally:
            sys.stdout = sys.__stdout__
            
        output = captured_output.getvalue()
        
        # Since we returned "Hello World" (ASCII) for everything in this mock structure,
        # it should find HIGH CONFIDENCE.
        self.assertIn("HIGH CONFIDENCE", output)
        self.assertIn("Score: 100.0", output) # All characters are ASCII
        
    def test_framing_hdlc(self):
        # Test HDLC detection on bytes
        tmp_file = "test_framing.bin"
        with open(tmp_file, 'wb') as f:
            # Write 10 frames of HDLC
            for i in range(10):
                f.write(b'\x7E' + b'\x00\x01\x02' + b'\x7E')
                
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            framing_scanner.analyze_framing_strategies(tmp_file)
        finally:
            sys.stdout = sys.__stdout__
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
                
        output = captured_output.getvalue()
        self.assertIn("HDLC / Flag-based", output)

    def test_capture_verify(self):
        # Create a dummy capture
        tmp_file = "test_verify.bin"
        with open(tmp_file, 'wb') as f:
           f.write(b"DATA" * 20)
           
        # We need a protocol definition for Verify to really work, 
        # or it just checks file existence if param is missing?
        # The script attempts to load generic protocol manager if not provided.
        # We'll just check if it runs without crashing on a dummy file
        
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            # We mock protocol_manager.load_protocol to return something basic
            with patch('src.analysis.protocol_manager.load_protocol') as mock_load:
                mock_load.return_value = {
                    "packet_structure": {
                        "header": "44415441", # "DATA" in hex
                        "fixed_length": 4
                    }
                }
                capture_verifier.verify_capture(tmp_file)
        finally:
            sys.stdout = sys.__stdout__
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
                
        output = captured_output.getvalue()
        # Should find valid packets since we matched the header
        self.assertIn("Valid Packets", output)
        self.assertIn("Verdict:", output)

if __name__ == '__main__':
    unittest.main()
