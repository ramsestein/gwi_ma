import unittest
import sys
import os
import numpy as np
from io import StringIO
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis import stat_analyzer
from src.analysis import ai_explorer
from src.framing import checksum_cracker
from src.security import crypto_scanner
from src.security import complex_protocol

class TestSingularityFeatures(unittest.TestCase):

    def setUp(self):
        self.tmp_file = "test_singularity.bin"
    
    def tearDown(self):
        # stat_analyzer also writes <capture>_autocorr.png next to the capture
        for path in (self.tmp_file, self.tmp_file + "_autocorr.png"):
            if os.path.exists(path):
                os.remove(path)

    def capture_stdout(self, func, *args):
        captured = StringIO()
        sys.stdout = captured
        try:
            func(*args)
        finally:
            sys.stdout = sys.__stdout__
        return captured.getvalue()

    def test_autocorrelation_periodicity(self):
        # Create data with period 10
        pattern = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A'
        data = pattern * 20 # 200 bytes
        with open(self.tmp_file, 'wb') as f:
            f.write(data)
            
        output = self.capture_stdout(stat_analyzer.analyze_statistics, self.tmp_file, 20)
        
        # Should detect Lag 10
        self.assertIn("Lag 10", output)
        self.assertIn("Correlation 1.0000", output)

    def test_ai_hypothesis_counter(self):
        # Create packet with a counter at offset 0
        with open(self.tmp_file, 'wb') as f:
            for i in range(50):
                f.write(bytes([i % 256, 0x00, 0x00])) # 3 byte packet
                
        output = self.capture_stdout(ai_explorer.generate_hypotheses, self.tmp_file, 3)
        
        self.assertIn("Offset 0: COUNTER", output)
        self.assertIn("Offset 1: CONSTANT", output)

    def test_checksum_cracker_crc8(self):
        # Create packet with simple SUM-8 checksum
        # Packet: [0x01, 0x02, Checksum=0x03]
        data = b''
        for i in range(10):
            pkl = bytes([1, 2, 3]) # 1+2 = 3
            data += pkl
            
        with open(self.tmp_file, 'wb') as f:
            f.write(data)
            
        output = self.capture_stdout(checksum_cracker.crack_checksum, self.tmp_file, 3)
        
        self.assertIn("SUM-8 (Modulo 256)", output)
        self.assertIn("SUCCESS", output)

    def test_crypto_xor_detection(self):
        # Create data XORed with key 0xAA
        # Plaintext: 0x00 * 100 -> Cipher: 0xAA * 100
        data = b'\xAA' * 100
        with open(self.tmp_file, 'wb') as f:
            f.write(data)
            
        output = self.capture_stdout(crypto_scanner.analyze_crypto, self.tmp_file)
        
        self.assertIn("Pattern repeats every 1 bytes", output) 
        # Or low entropy because it's constant, but crypto scanner checks repeating keys

    def test_tdm_detection(self):
        # Pattern A, B, A, B in first byte
        # Packet size 2
        data = b''
        for i in range(20):
            header = 0xA0 if i % 2 == 0 else 0xB0
            data += bytes([header, 0x00])
            
        with open(self.tmp_file, 'wb') as f:
            f.write(data)
            
        output = self.capture_stdout(complex_protocol.analyze_complexity, self.tmp_file, 2)
        
        self.assertIn("cycles with Period 2", output)
        self.assertIn("TDM Detected", output)

if __name__ == '__main__':
    unittest.main()
