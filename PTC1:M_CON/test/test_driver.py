"""Tests for src/Thorlabs_PTC1_Breadboard.py (thorlabs_ptc1 driver)."""

import unittest
from unittest.mock import patch

from src.Thorlabs_PTC1_Breadboard import thorlabs_ptc1
from src.simulator import MockPTC1Serial
from test.helpers import make_logger, make_plate


class TestThorlabsPTC1Driver(unittest.TestCase):

    def setUp(self):
        self.logger = make_logger()
        self.mock_serial = MockPTC1Serial()
        self.plate = thorlabs_ptc1(port="SIM", logger=self.logger,
                                   ser=self.mock_serial)

    # ── identification ─────────────────────────────────────────────────────────

    def test_check_id_logs_connected(self):
        with self.assertLogs("test", level="INFO") as cm:
            self.plate.check_id()
        self.assertTrue(any("connected" in line for line in cm.output))

    def test_check_id_includes_uid_in_log(self):
        with self.assertLogs("test", level="INFO") as cm:
            self.plate.check_id()
        self.assertTrue(any("PTC1-SIM-0001" in line for line in cm.output))

    def test_check_id_serial_mismatch_warns(self):
        with self.assertLogs("test", level="WARNING") as cm:
            thorlabs_ptc1(port="SIM", logger=self.logger,
                          ser=MockPTC1Serial(), serial_nr="WRONG-SERIAL")
        self.assertTrue(any("does not contain" in line for line in cm.output))

    def test_check_id_no_response_logs_error(self):
        with patch.object(self.plate, "_query", return_value=""):
            with self.assertLogs("test", level="ERROR") as cm:
                self.plate.check_id()
        self.assertTrue(any("did not respond" in line for line in cm.output))

    # ── temperature set / get ──────────────────────────────────────────────────

    def test_set_temperature_sends_millidegrees(self):
        self.plate.set_temperature(30.0)
        self.assertEqual(self.mock_serial._setpoint, 30000)

    def test_set_temperature_decimal(self):
        self.plate.set_temperature(32.5)
        self.assertEqual(self.mock_serial._setpoint, 32500)

    def test_set_temperature_at_lower_boundary(self):
        self.plate.set_temperature(5.0)
        self.assertEqual(self.mock_serial._setpoint, 5000)

    def test_set_temperature_at_upper_boundary(self):
        self.plate.set_temperature(45.0)
        self.assertEqual(self.mock_serial._setpoint, 45000)

    def test_set_temperature_below_min_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.plate.set_temperature(4.9)

    def test_set_temperature_above_max_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.plate.set_temperature(45.1)

    def test_set_temperature_out_of_range_logs_error(self):
        with self.assertLogs("test", level="ERROR"):
            with self.assertRaises(ValueError):
                self.plate.set_temperature(80.0)

    def test_get_setpoint_returns_current_target(self):
        self.assertAlmostEqual(self.plate.get_setpoint(), 25.0)

    def test_get_setpoint_reflects_after_set(self):
        self.plate.set_temperature(35.0)
        self.assertAlmostEqual(self.plate.get_setpoint(), 35.0)

    def test_get_temperature_returns_measured_value(self):
        # MockPTC1Serial returns setpoint - 2 milli-degrees = 24.998 C
        self.assertAlmostEqual(self.plate.get_temperature(), 24.998)

    def test_get_tec_current_in_amps(self):
        self.assertAlmostEqual(self.plate.get_tec_current(), 0.523)

    def test_get_tec_voltage_in_volts(self):
        self.assertAlmostEqual(self.plate.get_tec_voltage(), 1.200)

    # ── custom temperature band ────────────────────────────────────────────────

    def test_min_temp_clamped_to_device_minimum(self):
        plate = make_plate(logger=self.logger, min_temp_c=0.0)
        self.assertEqual(plate.min_temp_c, 5.0)

    def test_max_temp_clamped_to_device_maximum(self):
        plate = make_plate(logger=self.logger, max_temp_c=100.0)
        self.assertEqual(plate.max_temp_c, 45.0)

    def test_tighter_custom_band_is_enforced(self):
        plate = make_plate(logger=self.logger, min_temp_c=10.0, max_temp_c=40.0)
        self.assertEqual(plate.min_temp_c, 10.0)
        self.assertEqual(plate.max_temp_c, 40.0)
        with self.assertRaises(ValueError):
            plate.set_temperature(9.9)
        with self.assertRaises(ValueError):
            plate.set_temperature(40.1)
        plate.set_temperature(25.0)  # valid — must not raise

    # ── error register ─────────────────────────────────────────────────────────

    def test_get_errors_empty_when_no_errors(self):
        self.assertEqual(self.plate.get_errors(), [])

    def test_get_errors_single_bit(self):
        self.mock_serial._errors = 1 << 4   # bit 4 = "no sensor"
        self.assertEqual(self.plate.get_errors(), ["no sensor"])

    def test_get_errors_multiple_bits(self):
        self.mock_serial._errors = (1 << 0) | (1 << 5)  # "TEC not enabled" + "no TEC"
        errors = self.plate.get_errors()
        self.assertIn("TEC not enabled", errors)
        self.assertIn("no TEC", errors)

    def test_get_errors_unparseable_reply(self):
        with patch.object(self.plate, "_query", return_value="garbage"):
            with self.assertLogs("test", level="ERROR"):
                errors = self.plate.get_errors()
        self.assertEqual(errors, ["unreadable error register"])

    def test_clear_errors_resets_register(self):
        self.mock_serial._errors = 0xFF
        self.plate.clear_errors()
        self.assertEqual(self.mock_serial._errors, 0)

    # ── safe state and close ───────────────────────────────────────────────────

    def test_set_safe_state_returns_to_25c(self):
        self.plate.set_temperature(35.0)
        self.plate.set_safe_state()
        self.assertEqual(self.mock_serial._setpoint, 25000)

    def test_set_safe_state_out_of_band_logs_error(self):
        plate = make_plate(logger=self.logger,
                           min_temp_c=20.0, max_temp_c=40.0, safe_temp_c=10.0)
        with self.assertLogs("test", level="ERROR") as cm:
            plate.set_safe_state()
        self.assertTrue(any("outside the allowed band" in line for line in cm.output))

    def test_close_with_safe_state_restores_25c(self):
        self.plate.set_temperature(35.0)
        self.plate.close_connection(go_to_safe_state=True)
        self.assertFalse(self.mock_serial.is_open)
        self.assertEqual(self.mock_serial._setpoint, 25000)

    def test_close_without_safe_state_leaves_setpoint_unchanged(self):
        self.plate.set_temperature(35.0)
        self.plate.close_connection(go_to_safe_state=False)
        self.assertFalse(self.mock_serial.is_open)
        self.assertEqual(self.mock_serial._setpoint, 35000)

    # ── _parse_milli ───────────────────────────────────────────────────────────

    def test_parse_milli_positive(self):
        self.assertAlmostEqual(self.plate._parse_milli("25000"), 25.0)

    def test_parse_milli_negative(self):
        self.assertAlmostEqual(self.plate._parse_milli("-500"), -0.5)

    def test_parse_milli_invalid_returns_none_and_logs_error(self):
        with self.assertLogs("test", level="ERROR"):
            result = self.plate._parse_milli("oops")
        self.assertIsNone(result)

    # ── _query retry ───────────────────────────────────────────────────────────

    def test_query_retries_once_on_unknown_command(self):
        responses = [b"unknown command>\r", b"25000>\r"]
        with patch.object(self.mock_serial, "read_until", side_effect=responses):
            result = self.plate._query("T?")
        self.assertEqual(result, "25000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
