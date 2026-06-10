"""
ptc1_temperature_sweep.py
-------------------------
Automated step-wise temperature sweep for the Thorlabs PTC1 breadboard.

For each target temperature it:
  1. commands the setpoint,
  2. polls the measured temperature until it stays within TOLERANCE of the
     target for SETTLE_TIME seconds (or gives up after STEP_TIMEOUT),
  3. logs a timestamped row to a CSV,
  4. moves to the next target.

At the end it returns the plate to a safe temperature and closes the port.

Usage (via main.py):
    python main.py sweep --sim
    python main.py sweep --port /dev/cu.usbserial-02323293
"""

import argparse
import csv
import logging
import time
from datetime import datetime

from .Thorlabs_PTC1_Breadboard import thorlabs_ptc1


# ============================ EDIT THESE ============================

# The exact temperatures to visit, in order (deg C). Edit this list freely.
TARGETS_C = [30.0, 35.0]

# Settling rule: stay within TOLERANCE_C of the target for SETTLE_TIME_S
# continuous seconds before the point is considered stable and logged.
TOLERANCE_C   = 0.1     # how close to target counts as "there"
SETTLE_TIME_S = 30.0    # how long it must stay there
STEP_TIMEOUT_S = 300.0  # give up on a step after this long (safety net)
POLL_INTERVAL_S = 2.0   # how often to read the temperature

OUTPUT_CSV = "sweep_results.csv"

# ====================================================================


def wait_for_settle(plate, target, logger):
    """Poll until the temperature holds within tolerance for the settle time.

    Returns (settled, last_temp): settled is True if it stabilised, False if it
    timed out. last_temp is the final measured value.
    """
    start = time.time()
    in_band_since = None
    last_temp = None

    while True:
        last_temp = plate.get_temperature()

        # Stop immediately if the device flags an error mid-step.
        errors = plate.get_errors()
        if errors:
            logger.error("Device errors during step to %.3f C: %s", target, errors)

        if last_temp is not None and abs(last_temp - target) <= TOLERANCE_C:
            # We're in the band. Start (or continue) the hold timer.
            if in_band_since is None:
                in_band_since = time.time()
            elif time.time() - in_band_since >= SETTLE_TIME_S:
                return True, last_temp
        else:
            # Left the band; reset the hold timer.
            in_band_since = None

        if time.time() - start > STEP_TIMEOUT_S:
            logger.warning("Step to %.3f C timed out after %.0f s (last: %s C).",
                           target, STEP_TIMEOUT_S, last_temp)
            return False, last_temp

        time.sleep(POLL_INTERVAL_S)


def run_sweep(plate, targets, logger):
    logger.info("Starting sweep over %d targets: %s", len(targets), targets)

    with open(OUTPUT_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        # Header (written every run; fine for a first version).
        writer.writerow(["timestamp", "target_C", "measured_C",
                         "setpoint_C", "settled"])

        for target in targets:
            logger.info("--- stepping to %.3f C ---", target)
            plate.set_temperature(target)

            settled, measured = wait_for_settle(plate, target, logger)

            row = [datetime.now().isoformat(timespec="seconds"),
                   "%.3f" % target,
                   "%.3f" % measured if measured is not None else "",
                   "%.3f" % plate.get_setpoint(),
                   settled]
            writer.writerow(row)
            f.flush()  # save each point as it happens, not just at the end

            status = "settled" if settled else "TIMED OUT"
            logger.info("Logged %.3f C target -> %s C (%s).",
                        target, measured, status)

    logger.info("Sweep complete. Results in %s", OUTPUT_CSV)


def main():
    parser = argparse.ArgumentParser(description="PTC1 temperature sweep")
    parser.add_argument("--port", help="serial port, e.g. /dev/cu.usbserial-02323293")
    parser.add_argument("--sim", action="store_true",
                        help="run against the built-in simulator (no hardware)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    logger = logging.getLogger("sweep")

    if args.sim:
        from .simulator import MockPTC1Serial
        plate = thorlabs_ptc1(port="SIM", logger=logger, ser=MockPTC1Serial())
    elif args.port:
        plate = thorlabs_ptc1(port=args.port, logger=logger)
    else:
        from .port_detection import detect_new_port
        try:
            port = detect_new_port()
        except TimeoutError as exc:
            parser.error(str(exc))
        plate = thorlabs_ptc1(port=port, logger=logger)

    try:
        run_sweep(plate, TARGETS_C, logger)
    finally:
        # Always bring the plate to a safe state, even if the sweep errors out.
        plate.close_connection()
