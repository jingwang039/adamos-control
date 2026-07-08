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

`hold` keeps running (and regulating) until you stop it -- while it runs,
type a new temperature + Enter to change the setpoint live, or 'q' + Enter
(or Ctrl-C) to stop.

Run from the adamos_control/ directory:
    cd /Users/wangjing/Desktop/AG_Horns/Tem_Con/adamos_control
    python run_experiment.py hold 35 --paddle-port /dev/cu.usbserial-02323293
"""

import argparse
import logging
import queue
import sys
import threading
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


def _start_stdin_reader(logger):
    """Start a daemon thread that pushes each stdin line onto a queue.

    Lets the main loop poll for new setpoints without blocking on input().
    """
    line_q = queue.Queue()

    def _reader():
        logger.info("stdin reader thread started (isatty=%s).", sys.stdin.isatty())
        try:
            for line in sys.stdin:
                line = line.strip()
                # Logged unconditionally (even for blank/junk lines) so it's
                # obvious whether keystrokes are reaching this process at all
                # -- if you never see this line after typing + Enter, the
                # terminal you're typing into isn't this process's stdin.
                logger.info("stdin received: %r", line)
                line_q.put(line)
        except Exception:
            logger.exception("stdin reader thread crashed.")
        # sys.stdin iteration only returns (without an exception) at EOF --
        # i.e. this process's stdin isn't a live interactive stream, so live
        # setpoint changes will never work no matter what you type.
        logger.warning(
            "stdin closed (EOF) -- live setpoint changes are disabled for the "
            "rest of this run. This usually means the script wasn't launched "
            "with an interactive terminal attached to it.")

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return line_q


def cmd_hold(args, logger):
    """Set the paddle to a temperature and hold it, allowing the setpoint to
    be changed live by typing a new value + Enter (with optional monitor
    verification)."""
    from experiment_session import ExperimentSession

    paddle  = _connect_paddle(args.paddle_port, logger) if args.paddle_port else None
    monitor = _connect_monitor(args.monitor_port, args.monitor_serial, logger) \
              if args.monitor_port else None

    session    = ExperimentSession(paddle=paddle, monitor=monitor, logger=logger)
    stop_event = threading.Event()
    line_q     = _start_stdin_reader(logger)

    def get_target():
        new_val = None
        while not line_q.empty():
            line = line_q.get_nowait()
            if not line:
                continue
            if line.lower() in ("q", "quit", "exit"):
                stop_event.set()
                return None
            try:
                new_val = float(line)
            except ValueError:
                logger.warning("Ignoring input %r — type a number to change the "
                                "setpoint, or 'q' to stop.", line)
        return new_val

    logger.info(
        "Holding %.3f C. Type a new temperature + Enter anytime to change the "
        "setpoint, or 'q' + Enter (or Ctrl-C) to stop.", args.temperature)

    try:
        session.hold_continuous(
            initial_target_c=args.temperature,
            tolerance_c=args.tolerance,
            poll_interval_s=args.interval,
            get_target=get_target,
            stop_event=stop_event,
        )
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
    hold_p = sub.add_parser("hold", help="Set paddle temperature and hold "
                            "(setpoint can be changed live while it runs).")
    hold_p.add_argument("temperature", type=float,
                        help="Target temperature in degrees C (5-45 C).")
    hold_p.add_argument("--paddle-port", metavar="PORT",
                        help="Serial port for PTC1 paddle, e.g. /dev/cu.usbserial-02323293")
    hold_p.add_argument("--monitor-port", metavar="PORT",
                        help="Serial port for Lakeshore 224 monitor.")
    hold_p.add_argument("--monitor-serial", metavar="SN", default="",
                        help="Lakeshore 224 serial number substring for ID check (optional).")
    hold_p.add_argument("--tolerance", type=float, default=0.5, metavar="C",
                        help="Degrees C within target to count as reached (default 0.5).")
    hold_p.add_argument("--interval", type=float, default=5.0, metavar="S",
                        help="Polling interval in seconds (default 5).")

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
