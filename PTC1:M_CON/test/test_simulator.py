"""Tests for src/simulator.py (MockPTC1Serial)."""

import unittest

from src.simulator import MockPTC1Serial


class TestMockPTC1Serial(unittest.TestCase):

    def setUp(self):
        self.mock = MockPTC1Serial()

    def _query(self, cmd):
        """Send one ASCII command and return the reply text (no '>' or whitespace)."""
        self.mock.write((cmd + "\r").encode("ascii"))
        raw = self.mock.read_until(b">")
        return raw.decode("ascii").rstrip(">").strip()

    # ── initial state ──────────────────────────────────────────────────────────

    def test_initial_setpoint_is_25000_milli(self):
        self.assertEqual(self.mock._setpoint, 25000)

    def test_initial_errors_are_zero(self):
        self.assertEqual(self.mock._errors, 0)

    def test_initial_port_is_open(self):
        self.assertTrue(self.mock.is_open)

    # ── identification ─────────────────────────────────────────────────────────

    def test_product_id(self):
        self.assertEqual(self._query("m?"), "MTD1020T FW1.0.5")

    def test_uid(self):
        self.assertEqual(self._query("u?"), "PTC1-SIM-0001")

    # ── temperature queries ────────────────────────────────────────────────────

    def test_get_setpoint(self):
        self.assertEqual(self._query("T?"), "25000")

    def test_measured_temp_is_setpoint_minus_2_milli(self):
        self.assertEqual(self._query("Te?"), "24998")

    def test_set_temperature_updates_setpoint(self):
        self._query("T30000")
        self.assertEqual(self.mock._setpoint, 30000)

    def test_set_temperature_reflected_by_subsequent_query(self):
        self._query("T30000")
        self.assertEqual(self._query("T?"), "30000")

    def test_set_temperature_echoes_prompt_only(self):
        # read_until stops at '>' (inclusive); the trailing '\r' stays in the buffer
        self.mock.write(b"T30000\r")
        reply = self.mock.read_until(b">")
        self.assertEqual(reply, b">")

    # ── electrical queries ─────────────────────────────────────────────────────

    def test_tec_current_is_523_milli_amps(self):
        self.assertEqual(self._query("A?"), "523")

    def test_tec_voltage_is_1200_milli_volts(self):
        self.assertEqual(self._query("U?"), "1200")

    # ── error register ─────────────────────────────────────────────────────────

    def test_error_register_default_zero(self):
        self.assertEqual(self._query("E?"), "0")

    def test_clear_errors_resets_register(self):
        self.mock._errors = 7
        self._query("c")
        self.assertEqual(self.mock._errors, 0)

    # ── edge cases ─────────────────────────────────────────────────────────────

    def test_unknown_command_reply(self):
        self.assertEqual(self._query("X?"), "unknown command")

    def test_close_sets_is_open_false(self):
        self.mock.close()
        self.assertFalse(self.mock.is_open)

    def test_flush_does_not_raise(self):
        self.mock.flush()

    def test_reset_input_buffer_clears_buf(self):
        self.mock.write(b"m?\r")
        self.mock.reset_input_buffer()
        self.assertEqual(self.mock._buf, b"")

    # ── read_until buffering ───────────────────────────────────────────────────

    def test_read_until_returns_up_to_and_including_delimiter(self):
        self.mock._buf = b"25000>\r24998>\r"
        first = self.mock.read_until(b">")
        self.assertEqual(first, b"25000>")

    def test_read_until_advances_buffer_correctly(self):
        # '\r' between responses stays in the buffer and leads the next read
        self.mock._buf = b"25000>\r24998>\r"
        self.mock.read_until(b">")
        second = self.mock.read_until(b">")
        self.assertEqual(second, b"\r24998>")

    def test_read_until_not_found_returns_all_remaining(self):
        self.mock._buf = b"partial"
        result = self.mock.read_until(b">")
        self.assertEqual(result, b"partial")
        self.assertEqual(self.mock._buf, b"")


if __name__ == "__main__":
    unittest.main(verbosity=2)
