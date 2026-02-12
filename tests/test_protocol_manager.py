import unittest
import os
import json
import shutil
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import protocol_manager

class TestProtocolManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for results during tests
        self.test_dir = "test_results"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        
        # Override the PROTOCOL_FILE for testing
        protocol_manager.PROTOCOL_FILE = os.path.join(self.test_dir, "protocol_definition.json")
        
        if os.path.exists(protocol_manager.PROTOCOL_FILE):
            os.remove(protocol_manager.PROTOCOL_FILE)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_creates_default(self):
        proto = protocol_manager.load_protocol()
        self.assertIsNotNone(proto)
        self.assertIn('connection', proto)
        self.assertTrue(os.path.exists(protocol_manager.PROTOCOL_FILE))

    def test_update_connection(self):
        protocol_manager.update_connection("COM99", 9600)
        proto = protocol_manager.load_protocol()
        self.assertEqual(proto['connection']['port'], "COM99")
        self.assertEqual(proto['connection']['baudrate'], 9600)

    def test_add_metric(self):
        protocol_manager.add_metric("HR", 10, "UINT8")
        proto = protocol_manager.load_protocol()
        self.assertIn("HR", proto['metrics'])
        self.assertEqual(proto['metrics']['HR']['offset'], 10)

    def test_add_waveform(self):
        protocol_manager.add_waveform("ECG", 20, "UINT16", count=5)
        proto = protocol_manager.load_protocol()
        self.assertIn("ECG", proto['waveforms'])
        self.assertEqual(proto['waveforms']['ECG']['count'], 5)

if __name__ == '__main__':
    unittest.main()
