"""
simulator.py
------------
A minimal stand-in for serial.Serial that mimics the MTD1020T reply format.
Used by the --sim flag in hold_temperature and ptc1_temperature_sweep, and
injected directly into the driver in unit tests.

Reply format matches the real unit: digits, then a '>' prompt, then '\\r'.
"""


class MockPTC1Serial:

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
