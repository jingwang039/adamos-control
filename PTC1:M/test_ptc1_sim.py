"""
test_ptc1_sim.py
----------------
Runs the Thorlabs_PTC1 driver against a FAKE serial device that imitates the
MTD1020T's replies. Lets you exercise the whole driver with no hardware
attached -- useful because lab/magnet time is scarce.

Run it:  python test_ptc1_sim.py
"""

import logging
from Thorlabs_PTC1_Breadboard import thorlabs_ptc1


class MockPTC1Serial:
    """A minimal stand-in for serial.Serial that mimics the MTD1020T.

    Reply format matches the real unit: digits, then a '>' prompt, then '\\r'.
    """

    def __init__(self):
        self.is_open = True
        self._setpoint = 25000   # milli-degrees C
        self._errors = 0         # error register (0 = no errors)
        self._buf = b""          # bytes waiting to be read back

    def write(self, data):
        cmd = data.decode("ascii").strip()
        self._handle(cmd)

    def _handle(self, cmd):
        if cmd == "m?":
            self._buf += b"MTD1020T FW1.0.5>\r"
        elif cmd == "u?":
            self._buf += b"PTC1-SIM-0001>\r"
        elif cmd == "Te?":
            # pretend the plate sits 0.002 C below its setpoint
            self._buf += ("%d>\r" % (self._setpoint - 2)).encode("ascii")
        elif cmd == "T?":
            self._buf += ("%d>\r" % self._setpoint).encode("ascii")
        elif cmd.startswith("T") and cmd[1:].lstrip("-").isdigit():
            self._setpoint = int(cmd[1:])
            self._buf += b">\r"               # device echoes a prompt after a set
        elif cmd == "A?":
            self._buf += b"523>\r"            # 0.523 A
        elif cmd == "U?":
            self._buf += b"1200>\r"           # 1.200 V
        elif cmd == "E?":
            self._buf += ("%d>\r" % self._errors).encode("ascii")
        elif cmd == "c":
            self._errors = 0
            self._buf += b">\r"
        else:
            self._buf += b"unknown command>\r"

    def flush(self):
        pass

    def reset_input_buffer(self):
        self._buf = b""

    def read_until(self, expected):
        idx = self._buf.find(expected)
        if idx == -1:
            out, self._buf = self._buf, b""
            return out
        end = idx + len(expected)
        out, self._buf = self._buf[:end], self._buf[end:]
        return out

    def close(self):
        self.is_open = False


def main():
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)-8s %(message)s")
    logger = logging.getLogger("ptc1")

    # Inject the fake serial object instead of opening a real port.
    plate = thorlabs_ptc1(port="SIM", logger=logger, serial_nr="0001",
                          ser=MockPTC1Serial())

    print("\n--- basic reads ---")
    print("setpoint  :", plate.get_setpoint(), "C")
    print("measured  :", plate.get_temperature(), "C")
    print("TEC current:", plate.get_tec_current(), "A")
    print("errors    :", plate.get_errors())

    print("\n--- set a new target ---")
    plate.set_temperature(30.0)
    print("setpoint  :", plate.get_setpoint(), "C")

    print("\n--- safety check: try an illegal setpoint ---")
    try:
        plate.set_temperature(80.0)
    except ValueError as e:
        print("correctly refused:", e)

    print("\n--- shutdown (returns to safe temperature) ---")
    plate.close_connection()
    print("port open after close:", plate.ser.is_open)


if __name__ == "__main__":
    main()
