"""Tests for src/ptc1_temperature_sweep.py (wait_for_settle and run_sweep)."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

import src.ptc1_temperature_sweep as ptc1_temperature_sweep
from test.helpers import make_logger


class TestWaitForSettle(unittest.TestCase):

    def setUp(self):
        self.logger = make_logger()
        self.plate = MagicMock()
        self.plate.get_errors.return_value = []

    def test_returns_true_and_last_temp_when_settled(self):
        self.plate.get_temperature.return_value = 30.0
        # time.time: start=0, in_band_since=1, timeout_check=2, settle_check=32
        with patch("src.ptc1_temperature_sweep.time") as t:
            t.time.side_effect = [0, 1, 2, 32]
            settled, last_temp = ptc1_temperature_sweep.wait_for_settle(
                self.plate, 30.0, self.logger)
        self.assertTrue(settled)
        self.assertAlmostEqual(last_temp, 30.0)

    def test_returns_false_and_last_temp_on_timeout(self):
        self.plate.get_temperature.return_value = 35.0  # always out of band
        timeout = ptc1_temperature_sweep.STEP_TIMEOUT_S
        with patch("src.ptc1_temperature_sweep.time") as t:
            t.time.side_effect = [0, timeout + 1]
            settled, last_temp = ptc1_temperature_sweep.wait_for_settle(
                self.plate, 30.0, self.logger)
        self.assertFalse(settled)
        self.assertAlmostEqual(last_temp, 35.0)

    def test_none_temperature_handled_gracefully(self):
        self.plate.get_temperature.return_value = None
        timeout = ptc1_temperature_sweep.STEP_TIMEOUT_S
        with patch("src.ptc1_temperature_sweep.time") as t:
            t.time.side_effect = [0, timeout + 1]
            settled, last_temp = ptc1_temperature_sweep.wait_for_settle(
                self.plate, 30.0, self.logger)
        self.assertFalse(settled)
        self.assertIsNone(last_temp)

    def test_device_errors_are_logged(self):
        self.plate.get_temperature.return_value = 35.0
        self.plate.get_errors.return_value = ["thermal latch-up"]
        timeout = ptc1_temperature_sweep.STEP_TIMEOUT_S
        with patch("src.ptc1_temperature_sweep.time") as t:
            t.time.side_effect = [0, timeout + 1]
            with self.assertLogs("test", level="ERROR") as cm:
                ptc1_temperature_sweep.wait_for_settle(self.plate, 30.0, self.logger)
        self.assertTrue(any("thermal latch-up" in line for line in cm.output))


class TestRunSweep(unittest.TestCase):

    def setUp(self):
        self.logger = make_logger()
        self.plate = MagicMock()
        self.plate.get_setpoint.return_value = 30.0
        fd, self.tmpcsv = tempfile.mkstemp(suffix=".csv")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.tmpcsv):
            os.unlink(self.tmpcsv)

    def _run_sweep(self, targets, settle_return=(True, 30.0)):
        with patch("src.ptc1_temperature_sweep.wait_for_settle",
                   return_value=settle_return), \
             patch("src.ptc1_temperature_sweep.OUTPUT_CSV", self.tmpcsv), \
             patch("src.ptc1_temperature_sweep.datetime") as mock_dt:
            mock_dt.now.return_value.isoformat.return_value = "2026-01-01T00:00:00"
            ptc1_temperature_sweep.run_sweep(self.plate, targets, self.logger)
        with open(self.tmpcsv) as f:
            return f.read()

    def test_set_temperature_called_once_per_target(self):
        targets = [24.0, 25.0, 26.0]
        self._run_sweep(targets)
        self.assertEqual(self.plate.set_temperature.call_count, len(targets))

    def test_set_temperature_called_in_order(self):
        targets = [24.0, 25.0, 26.0]
        self._run_sweep(targets)
        self.plate.set_temperature.assert_has_calls([call(t) for t in targets])

    def test_csv_header_is_written(self):
        content = self._run_sweep([30.0])
        for col in ("timestamp", "target_C", "measured_C", "setpoint_C", "settled"):
            self.assertIn(col, content)

    def test_csv_contains_each_target(self):
        content = self._run_sweep([30.0, 35.0])
        self.assertIn("30.000", content)
        self.assertIn("35.000", content)

    def test_settled_step_logged_as_true(self):
        content = self._run_sweep([30.0], settle_return=(True, 30.0))
        self.assertIn("True", content)

    def test_timed_out_step_logged_as_false(self):
        content = self._run_sweep([30.0], settle_return=(False, 29.5))
        self.assertIn("False", content)

    def test_timed_out_step_still_writes_a_row(self):
        content = self._run_sweep([30.0], settle_return=(False, 29.5))
        data_lines = [l for l in content.splitlines() if l.strip()]
        self.assertGreaterEqual(len(data_lines), 2)  # header + at least one data row


if __name__ == "__main__":
    unittest.main(verbosity=2)
