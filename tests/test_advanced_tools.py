import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestAdvancedTools(unittest.TestCase):
    
    @patch('src.simulation.command_fuzzer.serial.Serial')
    @patch('src.simulation.command_fuzzer.time.sleep') # Skip sleep
    def test_fuzzer_sends_payloads(self, mock_sleep, mock_serial_cls):
        from src.simulation import command_fuzzer
        
        mock_ser = MagicMock()
        mock_serial_cls.return_value = mock_ser
        # Simulate silence initially
        mock_ser.in_waiting = 0 
        
        command_fuzzer.fuzz("COM1", 9600)
        
        # Check if it tried to write known payloads
        self.assertTrue(mock_ser.write.called)
        # Verify it sent at least one of the common payloads
        call_args = [args[0] for args, _ in mock_ser.write.call_args_list]
        self.assertIn(b'\x05', call_args) # ENQ
        self.assertIn(b'HELLO\r', call_args)

    def test_bit_analyzer_logic(self):
        from src.analysis import bit_analyzer
        from io import StringIO
        
        # Create dummy data: 2 bytes, 10 samples
        # Packet size 2.
        # Byte 0: 0x00, 0x01, 0x00, 0x01... (Bit 0 toggling)
        # Byte 1: 0xFF...
        data = b'\x00\xFF\x01\xFF' * 5 
        
        with patch('builtins.open', mock_open(read_data=data)):
            capturedOutput = StringIO()
            sys.stdout = capturedOutput
            
            # Analyze Byte 0 (Offset 0), Packet Size 2
            bit_analyzer.analyze_column_bits("dummy.bin", 2, 0)
            
            sys.stdout = sys.__stdout__
            output = capturedOutput.getvalue()
            
            # Should show 0x00 and 0x01
            self.assertIn("00", output)
            self.assertIn("01", output)
            # Should check for bit representation
            self.assertIn("00000001", output)

    @patch('src.utils.timing_analyzer.serial.Serial')
    @patch('src.utils.timing_analyzer.time.time')
    def test_timing_analyzer_gaps(self, mock_time, mock_serial_cls):
        from src.utils import timing_analyzer
        from io import StringIO
        
        mock_ser = MagicMock()
        mock_serial_cls.return_value = mock_ser
        
        # Simulate 3 bytes:
        # 1. Byte 1 at t=0
        # 2. Byte 2 at t=0.005 (5ms, small gap)
        # 3. Byte 3 at t=0.050 (50ms, large gap -> Packet boundary)
        
        mock_ser.in_waiting = 1
        mock_ser.read.return_value = b'\x00'
        
        # Side effects for time.time(): start, byte1, byte2, byte3, then stop loop
        # We need to control the loop in timing_analyzer. It runs while True.
        # We can raise KeyboardInterrupt to stop it.
        
        mock_time.side_effect = [
            100.000, # Initial last_time
            100.002, # Byte 1 arrives (2ms gap)
            100.005, # Byte 2 arrives (3ms gap from previous read)
            100.055, # Byte 3 arrives (50ms gap)
            KeyboardInterrupt # Stop
        ]
        
        capturedOutput = StringIO()
        sys.stdout = capturedOutput
        
        try:
            timing_analyzer.analyze_timing("COM1", 9600)
        except KeyboardInterrupt:
            pass
            
        sys.stdout = sys.__stdout__
        output = capturedOutput.getvalue()
        
        self.assertIn("Captured 3 gaps", output)
        # We expect to see a max gap of ~50ms
        self.assertIn("50.00 ms", output)

if __name__ == '__main__':
    unittest.main()
