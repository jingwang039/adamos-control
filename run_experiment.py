"""
run_experiment.py
------------------
Command-line entry point for temperature experiments.

Works with either or both devices:

  Both devices (paddle + external monitor):
    python run_experiment.py hold 35 \\
        --paddle-port /dev/cu.usbserial-XXXX \\
        --monitor-port /dev/cu.usbserial-YYYY \\
        --monitor-serial LSA21X5

  Paddle only:
    python run_experiment.py hold 35 --paddle-port /dev/cu.usbserial-XXXX

  Monitor only (just read temperatures):
    python run_experiment.py monitor --monitor-port /dev/cu.usbserial-YYYY

Run from the adamos_control/ directory:
    cd /Users/wangjing/Desktop/AG_Horns/Tem_Con/adamos_control
    python run_experiment.py hold 35 --paddle-port /dev/cu.usbserial-02323293
"""

import argparse
import logging
import sys
from pathlib import Path

# Make the PTC1 driver importable regardless of where this script is run from.
_PTC1_SRC = Path(__file__).parent.parent / "PTC1:M_CON" / "src"
sys.path.insert(0, str(_PTC1_SRC))


def _build_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("experiment")


def _connect_paddle(port, logger):
    from Thorlabs_PTC1_Breadboard import thorlabs_ptc1
    logger.info("Connecting to PTC1 paddle on %s ...", port)
    return thorlabs_ptc1(port=port, logger=logger)


def _connect_monitor(port, serial_nr, logger):
    from log_maker import log as log_maker_log
    lm = log_maker_log("lakeshore224")
    from Lakeshore_Temperature_Monitor_224 import lakeshore_224
    logger.info("Connecting to Lakeshore 224 on %s ...", port)
    return lakeshore_224(port=port, serial_nr=serial_nr or "", logger=lm.logger)


def cmd_hold(args, logger):
    """Set the paddle to a temperature and hold it (with optional monitor verification)."""
    from experiment_session import ExperimentSession

    paddle  = _connect_paddle(args.paddle_port, logger) if args.paddle_port else None
    monitor = _connect_monitor(args.monitor_port, args.monitor_serial, logger) \
              if args.monitor_port else None

    session = ExperimentSession(paddle=paddle, monitor=monitor, logger=logger)
    try:
        reached = session.hold_and_verify(
            target_c=args.temperature,
            tolerance_c=args.tolerance,
            timeout_s=args.timeout,
            monitor_channel=args.monitor_channel,
        )
        if not reached:
            logger.warning("Setpoint is still active — plate keeps regulating.")
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        # Keep paddle holding after the script exits (same behaviour as PTC1 main.py hold).
        session.close(paddle_safe_state=False)


def cmd_monitor(args, logger):
    """Read all Lakeshore 224 channels continuously until Ctrl-C."""
    from experiment_session import ExperimentSession
    import time

    monitor = _connect_monitor(args.monitor_port, args.monitor_serial, logger)
    session = ExperimentSession(monitor=monitor, logger=logger)
    logger.info("Reading temperatures every %.0f s. Press Ctrl-C to stop.", args.interval)
    try:
        while True:
            temps = session.get_all_temps()
            for key, val in sorted(temps.items()):
                logger.info("  %s: %.3f C", key, val)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Stopped.")
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Temperature experiment controller (PTC1 paddle + Lakeshore 224 monitor).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- hold sub-command ---
    hold_p = sub.add_parser("hold", help="Set paddle temperature and hold.")
    hold_p.add_argument("temperature", type=float,
                        help="Target temperature in degrees C (5-45 C).")
    hold_p.add_argument("--paddle-port", metavar="PORT",
                        help="Serial port for PTC1 paddle, e.g. /dev/cu.usbserial-02323293")
    hold_p.add_argument("--monitor-port", metavar="PORT",
                        help="Serial port for Lakeshore 224 monitor.")
    hold_p.add_argument("--monitor-serial", metavar="SN", default="",
                        help="Lakeshore 224 serial number substring for ID check (optional).")
    hold_p.add_argument("--monitor-channel", metavar="CH", default="t_c2",
                        help="Lakeshore channel to use for verification (default t_c2). "
                             "Choices: t_c2, t_c3, t_c4, t_c5, t_d1, t_d2, t_d3, t_d4, t_d5.")
    hold_p.add_argument("--tolerance", type=float, default=0.5, metavar="C",
                        help="Degrees C within target to count as reached (default 0.5).")
    hold_p.add_argument("--timeout", type=float, default=600.0, metavar="S",
                        help="Stop waiting after this many seconds (default 600).")

    # --- monitor sub-command ---
    mon_p = sub.add_parser("monitor", help="Read Lakeshore 224 channels continuously.")
    mon_p.add_argument("--monitor-port", metavar="PORT", required=True,
                       help="Serial port for Lakeshore 224 monitor.")
    mon_p.add_argument("--monitor-serial", metavar="SN", default="",
                       help="Lakeshore 224 serial number substring for ID check (optional).")
    mon_p.add_argument("--interval", type=float, default=5.0, metavar="S",
                       help="Polling interval in seconds (default 5).")

    args = parser.parse_args()
    logger = _build_logger()

    if args.command == "hold":
        if not args.paddle_port and not args.monitor_port:
            parser.error("Provide at least --paddle-port or --monitor-port.")
        cmd_hold(args, logger)
    elif args.command == "monitor":
        cmd_monitor(args, logger)


if __name__ == "__main__":
    main()
