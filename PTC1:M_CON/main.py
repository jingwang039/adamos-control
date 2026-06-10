"""
main.py — entrypoint for PTC1 temperature control scripts.

Usage:
    python main.py hold <temperature> [--port PORT | --sim] [--no-wait]
    python main.py sweep [--port PORT | --sim]

Examples:
    python main.py hold 35 --port /dev/cu.usbserial-02323293
    python main.py hold 35 --sim
    python main.py sweep --port /dev/cu.usbserial-02323293
    python main.py sweep --sim
"""

import sys
import argparse

_SCRIPTS = {
    "hold":  "src.hold_temperature",
    "sweep": "src.ptc1_temperature_sweep",
}


def main():
    parser = argparse.ArgumentParser(
        description="PTC1 temperature control",
        usage="%(prog)s {hold,sweep} [script options ...]",
        add_help=False,
    )
    parser.add_argument("script", choices=_SCRIPTS,
                        help="hold — set and hold a temperature; "
                             "sweep — step through a list of temperatures")

    # Parse only the script name; leave everything else for the script's own parser.
    args, remaining = parser.parse_known_args()

    # Replace argv so the script's argparse sees only its own arguments.
    sys.argv = [args.script] + remaining

    if args.script == "hold":
        from src.hold_temperature import main as _main
    else:
        from src.ptc1_temperature_sweep import main as _main

    _main()


if __name__ == "__main__":
    main()
