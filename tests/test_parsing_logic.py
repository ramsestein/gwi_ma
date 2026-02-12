import unittest
import os
import sys
import struct

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.universal_logger import get_value

class TestParsingLogic(unittest.TestCase):
    def test_get_uint8(self):
        packet = b'\x00\x01\x02\x03'
        self.assertEqual(get_value(packet, 1, 'UINT8'), 1)
        self.assertEqual(get_value(packet, 3, 'UINT8'), 3)
        self.assertIsNone(get_value(packet, 4, 'UINT8'))

    def test_get_uint16_le(self):
        packet = b'\x01\x02' # 0x0201 = 513
        self.assertEqual(get_value(packet, 0, 'UINT16_LE'), 513)

    def test_get_uint16_be(self):
        packet = b'\x01\x02' # 0x0102 = 258
        self.assertEqual(get_value(packet, 0, 'UINT16_BE'), 258)

    def test_out_of_bounds(self):
        packet = b'\x00'
        self.assertIsNone(get_value(packet, 0, 'UINT16_LE')) # Needs 2 bytes

if __name__ == '__main__':
    unittest.main()
