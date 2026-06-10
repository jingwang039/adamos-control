"""Tests for src/hold_temperature.py (wait_until_reached)."""

import unittest
from unittest.mock import MagicMock, patch

import src.hold_temperature as hold_temperature
from test.helpers import make_logger


class TestWaitUntilReached(unittest.TestCase):

    def setUp(self):
        self.logger = make_logger()
        self.plate = MagicMock()
        self.plate.get_errors.return_value = []

    def test_returns_true_when_temperature_settles(self):
        self.plate.get_temperature.return_value = 25.0
        # time.time() calls: start=0, in_band_since=1, timeout_check=2, settle_check=32
        with patch("src.hold_temperature.time") as t:
            t.time.side_effect = [0, 1, 2, 32]
            result = hold_temperature.wait_until_reached(self.plate, 25.0, self.logger)
        self.assertTrue(result)

    def test_returns_false_on_timeout(self):
        self.plate.get_temperature.return_value = 30.0  # always out of band
        timeout = hold_temperature.REACH_TIMEOUT_S
        with patch("src.hold_temperature.time") as t:
            t.time.side_effect = [0, timeout + 1]
            result = hold_temperature.wait_until_reached(self.plate, 25.0, self.logger)
        self.assertFalse(result)

    def test_settle_timer_resets_after_leaving_band(self):
        # in band → out of band → in band long enough → True
        self.plate.get_temperature.side_effect = [25.0, 30.0, 25.0, 25.0]
        # time.time: start, in_band_since(iter1), timeout(iter1),
        #            timeout(iter2), in_band_since(iter3), timeout(iter3),
        #            settle_check(iter4)
        with patch("src.hold_temperature.time") as t:
            t.time.side_effect = [0, 1, 2, 3, 4, 5, 36]
            result = hold_temperature.wait_until_reached(self.plate, 25.0, self.logger)
        self.assertTrue(result)

    def test_device_errors_are_logged(self):
        self.plate.get_temperature.return_value = 30.0
        self.plate.get_errors.return_value = ["no sensor"]
        timeout = hold_temperature.REACH_TIMEOUT_S
        with patch("src.hold_temperature.time") as t:
            t.time.side_effect = [0, timeout + 1]
            with self.assertLogs("test", level="ERROR") as cm:
                hold_temperature.wait_until_reached(self.plate, 25.0, self.logger)
        self.assertTrue(any("no sensor" in line for line in cm.output))

    def test_none_temperature_does_not_crash(self):
        self.plate.get_temperature.return_value = None
        timeout = hold_temperature.REACH_TIMEOUT_S
        with patch("src.hold_temperature.time") as t:
            t.time.side_effect = [0, timeout + 1]
            result = hold_temperature.wait_until_reached(self.plate, 25.0, self.logger)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
