"""
experiment_session.py
----------------------
Glue layer over the Thorlabs PTC1 paddle and/or Lakeshore 224 temperature monitor.

Either device may be omitted. Methods that require a missing device raise
RuntimeError with a clear message so the caller always knows what went wrong.

Typical usage — both devices:
    session = ExperimentSession(paddle=ptc1, monitor=ls224)
    session.hold_and_verify(35.0)          # set 35 C, Lakeshore C2 confirms

Paddle only:
    session = ExperimentSession(paddle=ptc1)
    session.set_target(35.0)
    print(session.get_paddle_temp())

Monitor only:
    session = ExperimentSession(monitor=ls224)
    print(session.get_all_temps())
    print(session.get_channel_temp("t_c2"))
"""

import time
import logging

# Default verification channel — Lakeshore C2 is on the paddle surface.
DEFAULT_MONITOR_CHANNEL = "t_c2"

# Convergence parameters (tuneable per call via keyword args).
TOLERANCE_C      = 0.5    # |actual - target| < this to count as "in band"
SETTLE_TIME_S    = 30.0   # must stay in band this long to count as "reached"
POLL_INTERVAL_S  = 5.0    # how often to read while waiting
REACH_TIMEOUT_S  = 600.0  # give up waiting after this (setpoint stays set)


class ExperimentSession:
    """
    Wraps an optional PTC1 paddle and an optional Lakeshore 224 monitor into a
    single object with standalone and combined experiment methods.
    """

    def __init__(self, paddle=None, monitor=None, logger=None):
        """
        paddle  : thorlabs_ptc1 instance, or None
        monitor : lakeshore_224 instance, or None
        logger  : standard logging.Logger; if omitted a module-level logger is used
        """
        if paddle is None and monitor is None:
            raise ValueError("Provide at least one device (paddle, monitor, or both).")

        self.paddle  = paddle
        self.monitor = monitor
        self.logger  = logger or logging.getLogger(__name__)

    # -------------------------------------------------------------------------
    # Internal guards
    # -------------------------------------------------------------------------

    def _require_paddle(self):
        if self.paddle is None:
            raise RuntimeError(
                "This operation requires the PTC1 paddle, but none was connected.")

    def _require_monitor(self):
        if self.monitor is None:
            raise RuntimeError(
                "This operation requires the Lakeshore 224 monitor, but none was connected.")

    # -------------------------------------------------------------------------
    # Paddle-only operations
    # -------------------------------------------------------------------------

    def set_target(self, temp_c):
        """Set the paddle setpoint in degrees C. Raises ValueError if out of range."""
        self._require_paddle()
        self.paddle.set_temperature(temp_c)

    def get_setpoint(self):
        """Return the current paddle setpoint in degrees C."""
        self._require_paddle()
        return self.paddle.get_setpoint()

    def get_paddle_temp(self):
        """Read the paddle's own internal sensor in degrees C."""
        self._require_paddle()
        return self.paddle.get_temperature()

    def get_tec_current(self):
        """Return the TEC current in amps (sign indicates heating vs cooling)."""
        self._require_paddle()
        return self.paddle.get_tec_current()

    def get_paddle_errors(self):
        """Return a list of active PTC1 error strings (empty list = all good)."""
        self._require_paddle()
        return self.paddle.get_errors()

    # -------------------------------------------------------------------------
    # Monitor-only operations
    # -------------------------------------------------------------------------

    def get_all_temps(self):
        """Read every Lakeshore 224 channel. Returns a dict, e.g. {'t_c2': 23.1, ...}."""
        self._require_monitor()
        return self.monitor.temperature_celsius()

    def get_channel_temp(self, channel=DEFAULT_MONITOR_CHANNEL):
        """
        Read a single Lakeshore channel by key name ('t_c2', 't_d1', ...).
        Defaults to C2 (the paddle-surface sensor).
        """
        self._require_monitor()
        temps = self.monitor.temperature_celsius()
        if channel not in temps:
            raise KeyError(
                "Unknown channel '%s'. Valid keys: %s" % (channel, sorted(temps.keys())))
        return temps[channel]

    # -------------------------------------------------------------------------
    # Combined: set target and verify with external monitor
    # -------------------------------------------------------------------------

    def hold_and_verify(self, target_c,
                        monitor_channel=DEFAULT_MONITOR_CHANNEL,
                        tolerance_c=TOLERANCE_C,
                        settle_time_s=SETTLE_TIME_S,
                        poll_interval_s=POLL_INTERVAL_S,
                        timeout_s=REACH_TIMEOUT_S):
        """
        Set the paddle to target_c, then wait until the temperature is confirmed.

        With both devices: confirms via the Lakeshore external sensor (more
        trustworthy than the paddle's own sensor for sample-surface temperature).

        With paddle only: falls back to the paddle's internal sensor.

        Returns True if the target was held within tolerance for settle_time_s,
        False if timeout_s elapsed first. The setpoint stays active either way.

        Parameters
        ----------
        target_c         : target temperature in degrees C
        monitor_channel  : Lakeshore key to use for verification (default 't_c2')
        tolerance_c      : how close counts as "reached" (default 0.5 C)
        settle_time_s    : how long to hold within tolerance (default 30 s)
        poll_interval_s  : polling period in seconds (default 5 s)
        timeout_s        : give up after this many seconds (default 600 s)
        """
        self._require_paddle()

        self.paddle.set_temperature(target_c)

        use_external = self.monitor is not None
        if use_external:
            self.logger.info(
                "Paddle setpoint -> %.3f C. Verifying with Lakeshore channel %s ...",
                target_c, monitor_channel)
        else:
            self.logger.info(
                "Paddle setpoint -> %.3f C. "
                "No monitor connected -- verifying with paddle's internal sensor ...",
                target_c)

        start         = time.time()
        in_band_since = None

        while True:
            # Read the verification temperature.
            if use_external:
                try:
                    actual = self.get_channel_temp(monitor_channel)
                except Exception as exc:
                    self.logger.error("Monitor read failed: %s", exc)
                    actual = None
            else:
                actual = self.paddle.get_temperature()

            # When both devices are present, log both sensors side-by-side.
            if use_external:
                paddle_temp = self.paddle.get_temperature()
                if actual is not None and paddle_temp is not None:
                    self.logger.info(
                        "paddle internal: %.3f C | %s (external): %.3f C | target: %.3f C",
                        paddle_temp, monitor_channel, actual, target_c)
            elif actual is not None:
                self.logger.info(
                    "paddle internal: %.3f C | target: %.3f C", actual, target_c)

            errors = self.paddle.get_errors()
            if errors:
                self.logger.error("PTC1 errors: %s", ", ".join(errors))

            # Check convergence criterion.
            if actual is not None:
                if abs(actual - target_c) <= tolerance_c:
                    if in_band_since is None:
                        in_band_since = time.time()
                    elif time.time() - in_band_since >= settle_time_s:
                        self.logger.info(
                            "Confirmed: surface held within %.1f C of %.3f C for %.0f s.",
                            tolerance_c, target_c, settle_time_s)
                        return True
                else:
                    in_band_since = None  # drifted out of band, reset the clock

            if time.time() - start > timeout_s:
                self.logger.warning(
                    "Timed out after %.0f s. Setpoint is still %.3f C, plate keeps regulating.",
                    timeout_s, target_c)
                return False

            time.sleep(poll_interval_s)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def close(self, paddle_safe_state=True):
        """
        Close all connected devices.

        paddle_safe_state : if True, the paddle returns to its safe temperature
                            before disconnecting. Set False to leave it holding
                            its current setpoint (e.g. for a long experiment).
        """
        if self.paddle is not None:
            self.paddle.close_connection(go_to_safe_state=paddle_safe_state)
        if self.monitor is not None:
            self.monitor.close_connection()
        self.logger.info("All devices disconnected.")
