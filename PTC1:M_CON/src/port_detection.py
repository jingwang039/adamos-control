"""
port_detection.py
-----------------
Automatic USB serial-port detection: snapshot the ports that exist right now,
prompt the user to plug the device in, then poll until exactly one new port
appears and return its name.
"""

import time

import serial.tools.list_ports


POLL_INTERVAL_S  = 0.5
DETECT_TIMEOUT_S = 60.0


def detect_new_port(poll_interval=POLL_INTERVAL_S, timeout=DETECT_TIMEOUT_S):
    """Prompt the user to connect the PTC1 and return the port it appears on.

    Takes a snapshot of currently connected serial ports, then polls every
    `poll_interval` seconds until a new port shows up.  If nothing appears
    within `timeout` seconds, raises TimeoutError.

    When more than one port appears simultaneously, the lexicographically first
    name is returned so the result is deterministic.
    """
    before = {p.device for p in serial.tools.list_ports.comports()}

    print("Plug the PTC1 into a USB port now ...", flush=True)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        after = {p.device for p in serial.tools.list_ports.comports()}
        new = after - before
        if new:
            port = sorted(new)[0]
            print("Detected: %s" % port, flush=True)
            return port
        time.sleep(poll_interval)

    raise TimeoutError(
        "No new USB port detected after %.0f seconds." % timeout)
