"""
Test IntelliVue Decoder with the real captured frame from capture_sample.hex.
"""
import unittest
import os
from src.intellivue_decoder import IntelliVueDecoder, SLIP_END


# The actual captured frame from dumps/capture_sample.hex
CAPTURED_HEX = (
    "C011010218E1000002000502100101001700070208002100000000"
    "F13B01FE0016000C07111100FFFFFFFFFFFFFFFF000100060803"
    "000301E400000006002406D000000000"
)


class TestIntelliVueDecoder(unittest.TestCase):

    def setUp(self):
        self.decoder = IntelliVueDecoder()
        self.raw_bytes = bytes.fromhex(CAPTURED_HEX)

    def test_slip_unescape_basic(self):
        """SLIP unescape replaces DB DC -> C0, DB DD -> DB."""
        data = bytes([0xDB, 0xDC, 0x41, 0xDB, 0xDD])
        result = self.decoder._slip_unescape(data)
        self.assertEqual(result, bytes([0xC0, 0x41, 0xDB]))

    def test_slip_unescape_no_escapes(self):
        """Data without escape sequences passes through unchanged."""
        data = bytes([0x11, 0x01, 0x02, 0x18])
        result = self.decoder._slip_unescape(data)
        self.assertEqual(result, data)

    def test_decode_captured_frame_as_raw(self):
        """
        The captured frame starts with C0 but has no trailing C0.
        Decoder should handle gracefully via _parse_frame fallback.
        """
        # Strip the leading C0 (SLIP delimiter) and parse as raw frame
        payload = self.raw_bytes[1:]
        event = self.decoder._parse_frame(payload)

        self.assertIsNotNone(event)
        self.assertEqual(event['type'], 'MIB_SESSION')
        self.assertEqual(event['session_type'], '0x11')

    def test_session_type_0x11(self):
        """Session type 0x11 is decoded as MIB_SESSION."""
        payload = self.raw_bytes[1:]
        event = self.decoder._parse_frame(payload)

        self.assertEqual(event['session_subtype'], '0x01')
        self.assertEqual(event['session_param_1'], 0x02)
        self.assertEqual(event['session_param_2'], 0x18)

    def test_embedded_aarq_detected(self):
        """The frame contains an embedded AARQ (Association Request) at offset 4."""
        payload = self.raw_bytes[1:]
        event = self.decoder._parse_frame(payload)

        self.assertIn('apdu_type', event)
        self.assertIn('AARQ', event['apdu_type'])

    def test_complete_slip_frame(self):
        """A properly framed SLIP packet (with both C0 delimiters) is decoded."""
        # Create a complete SLIP frame with trailing C0
        complete = self.raw_bytes + bytes([SLIP_END])
        events = self.decoder.decode(complete)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'MIB_SESSION')

    def test_slip_frame_build(self):
        """Build a SLIP frame and verify it has proper delimiters."""
        payload = bytes([0x0E, 0xE2, 0x00, 0x00, 0x02, 0x00, 0x02])
        framed = self.decoder._slip_frame(payload)

        self.assertEqual(framed[0], SLIP_END)
        self.assertEqual(framed[-1], SLIP_END)

    def test_empty_frame_returns_none(self):
        """Frames shorter than 4 bytes return None."""
        event = self.decoder._parse_frame(bytes([0x11, 0x01]))
        self.assertIsNone(event)


if __name__ == '__main__':
    unittest.main()
