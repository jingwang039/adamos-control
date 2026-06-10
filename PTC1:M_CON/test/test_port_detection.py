"""Tests for src/port_detection.py (detect_new_port)."""

import unittest
from unittest.mock import MagicMock, patch

from src.port_detection import detect_new_port


def _port(device):
    """Return a minimal mock that looks like a ListPortInfo entry."""
    p = MagicMock()
    p.device = device
    return p


class TestDetectNewPort(unittest.TestCase):

    def test_returns_port_that_appeared_after_prompt(self):
        before = [_port("/dev/cu.existing")]
        after  = [_port("/dev/cu.existing"), _port("/dev/cu.usbserial-NEW")]
        with patch("serial.tools.list_ports.comports", side_effect=[before, after]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1]), \
             patch("src.port_detection.time.sleep"):
            result = detect_new_port()
        self.assertEqual(result, "/dev/cu.usbserial-NEW")

    def test_waits_until_port_appears(self):
        # port absent on first poll, present on second
        existing = [_port("/dev/cu.existing")]
        with_new  = [_port("/dev/cu.existing"), _port("/dev/cu.usbserial-NEW")]
        with patch("serial.tools.list_ports.comports",
                   side_effect=[existing, existing, with_new]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1, 2]), \
             patch("src.port_detection.time.sleep"):
            result = detect_new_port()
        self.assertEqual(result, "/dev/cu.usbserial-NEW")

    def test_raises_timeout_when_nothing_appears(self):
        existing = [_port("/dev/cu.existing")]
        with patch("serial.tools.list_ports.comports", return_value=existing), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 61]), \
             patch("src.port_detection.time.sleep"):
            with self.assertRaises(TimeoutError):
                detect_new_port(timeout=60)

    def test_timeout_error_message_includes_duration(self):
        with patch("serial.tools.list_ports.comports", return_value=[]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 31]), \
             patch("src.port_detection.time.sleep"):
            with self.assertRaises(TimeoutError) as cm:
                detect_new_port(timeout=30)
        self.assertIn("30", str(cm.exception))

    def test_works_when_no_ports_existed_before(self):
        with patch("serial.tools.list_ports.comports",
                   side_effect=[[], [_port("/dev/cu.usbserial-FIRST")]]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1]), \
             patch("src.port_detection.time.sleep"):
            result = detect_new_port()
        self.assertEqual(result, "/dev/cu.usbserial-FIRST")

    def test_returns_lexicographically_first_when_multiple_appear(self):
        before = []
        after  = [_port("/dev/cu.usbserial-Z"), _port("/dev/cu.usbserial-A")]
        with patch("serial.tools.list_ports.comports", side_effect=[before, after]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1]), \
             patch("src.port_detection.time.sleep"):
            result = detect_new_port()
        self.assertEqual(result, "/dev/cu.usbserial-A")

    def test_ignores_ports_that_were_already_present(self):
        before   = [_port("/dev/cu.already-there")]
        after    = [_port("/dev/cu.already-there"), _port("/dev/cu.usbserial-NEW")]
        with patch("serial.tools.list_ports.comports", side_effect=[before, after]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1]), \
             patch("src.port_detection.time.sleep"):
            result = detect_new_port()
        self.assertNotEqual(result, "/dev/cu.already-there")
        self.assertEqual(result, "/dev/cu.usbserial-NEW")

    def test_sleep_is_called_between_polls(self):
        existing  = [_port("/dev/cu.existing")]
        with_new  = [_port("/dev/cu.existing"), _port("/dev/cu.usbserial-NEW")]
        with patch("serial.tools.list_ports.comports",
                   side_effect=[existing, existing, with_new]), \
             patch("src.port_detection.time.monotonic", side_effect=[0, 1, 2]), \
             patch("src.port_detection.time.sleep") as mock_sleep:
            detect_new_port(poll_interval=0.5)
        mock_sleep.assert_called_with(0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
