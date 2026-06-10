"""
hold_temperature.py
--------------------
Set the Thorlabs PTC1 breadboard to a target temperature and LEAVE IT HOLDING
there, so you can run experiments on a stable surface.

This is different from the sweep: it does NOT cool back down on exit. The PTC1
keeps regulating to the setpoint on its own (in firmware), so the plate stays
at temperature even after this program finishes and even if you close Python.

Usage (via main.py):
    python main.py hold 35 --port /dev/cu.usbserial-02323293
    python main.py hold 35 --sim          (offline test, no hardware)

Options:
    --no-wait   set the target and exit at once, without waiting for it to arrive

WHEN YOU ARE DONE with your experiment, return the plate to a resting state --
either set it back to room temperature or power the unit off, e.g.:
    python main.py hold 25 --port /dev/cu.usbserial-02323293
"""

import argparse
import logging
import time

from .Thorlabs_PTC1_Breadboard import thorlabs_ptc1


# How we confirm the plate has actually reached the target before saying so.
TOLERANCE_C     = 0.1     # "reached" means within this of the target
SETTLE_TIME_S   = 30.0    # ...and held there this long
POLL_INTERVAL_S = 5.0     # how often to read while waiting
REACH_TIMEOUT_S = 600.0   # stop waiting for confirmation after this (it keeps trying)


def wait_until_reached(plate, target, logger):
    """Poll until the plate holds within tolerance of target for the settle
    time. Returns True if confirmed, False if it timed out (the setpoint is
    still set either way)."""
    start = time.time()
    in_band_since = None

    while True:
        temp = plate.get_temperature()

        errors = plate.get_errors()
        if errors:
            logger.error("Device errors: %s", errors)

        if temp is not None:
            logger.info("measured %.3f C (target %.3f C)", temp, target)
            if abs(temp - target) <= TOLERANCE_C:
                if in_band_since is None:
                    in_band_since = time.time()
                elif time.time() - in_band_since >= SETTLE_TIME_S:
                    return True
            else:
                in_band_since = None

        if time.time() - start > REACH_TIMEOUT_S:
            return False

        time.sleep(POLL_INTERVAL_S)


def main():
    parser = argparse.ArgumentParser(
        description="Set the PTC1 to a temperature and hold it for experiments.")
    parser.add_argument("temperature", type=float,
                        help="target temperature in deg C")
    parser.add_argument("--port", help="serial port, e.g. /dev/cu.usbserial-02323293")
    parser.add_argument("--sim", action="store_true",
                        help="run against the built-in simulator (no hardware)")
    parser.add_argument("--no-wait", action="store_true",
                        help="set the target and exit immediately, without "
                             "waiting to confirm it has been reached")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    logger = logging.getLogger("hold")

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
        # The driver refuses (raises ValueError) any out-of-range temperature.
        plate.set_temperature(args.temperature)

        if args.no_wait:
            logger.info("Setpoint sent. Plate will reach %.3f C on its own.",
                        args.temperature)
        else:
            logger.info("Waiting for the plate to reach and hold %.3f C ...",
                        args.temperature)
            reached = wait_until_reached(plate, args.temperature, logger)
            if reached:
                logger.info("Plate is holding at %.3f C -- you can start your experiment.",
                            args.temperature)
            else:
                logger.warning("Could not confirm %.3f C within %.0f s, but the "
                               "setpoint is set and the plate keeps regulating.",
                               args.temperature, REACH_TIMEOUT_S)
    except ValueError as exc:
        logger.error("Temperature not set: %s", exc)
    finally:
        # The crucial difference from the sweep: close WITHOUT returning to a
        # safe temperature, so the plate stays where you put it.
        plate.close_connection(go_to_safe_state=False)
        logger.info("Disconnected. The plate holds %.3f C until you change it "
                    "or power off.", args.temperature)
