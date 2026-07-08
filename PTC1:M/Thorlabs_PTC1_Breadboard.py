
import serial
import time

# Map the MTD1020T error-register bits to human-readable messages.
# (bit index -> meaning), from the Thorlabs MTD415T/MTD1020T datasheet.
ERROR_BITS = {
    0:  "TEC not enabled",
    1:  "internal temperature too high",
    2:  "thermal latch-up",
    3:  "cycling time too small",
    4:  "no sensor",
    5:  "no TEC",
    6:  "TEC polarity reversed",
    13: "value out of range",
    14: "invalid command",
}


class thorlabs_ptc1:
    """
    Driver for the Thorlabs PTC1(/M) temperature-controlled breadboard.

    The PTC1 is driven internally by a Thorlabs MTD1020T TEC controller, which
    is what actually receives these serial commands. Commands are short ASCII
    strings ending in a carriage return '\\r', sent at 115200 baud (8-N-1).
    Every reply ends with a '>' prompt, which this driver strips automatically.

    Temperatures are exchanged with the device in MILLI-degrees Celsius
    (e.g. 25.000 C is sent as the command "T25000"). This class converts for
    you, so every method here works in plain degrees Celsius.

    -------------------------------------------------------------------------
    HARDWARE SETUP required before this class will work:
      * Set the front-panel MODE switch to "USB" (not the knob/front-panel).
      * Close the Thorlabs GUI -- only one program may own the serial port.
      * Over USB the valid setpoint range is 5 to 45 C.
    -------------------------------------------------------------------------

    Because this instrument SETS temperature (unlike the read-only Lakeshore
    224), every setpoint is checked against an allowed band and REFUSED if it
    falls outside. Refusing -- rather than silently clamping -- keeps mistakes
    visible instead of hiding them.
    """

    # Hardware setpoint limits over USB, from the Thorlabs documentation.
    DEVICE_MIN_C = 5.0
    DEVICE_MAX_C = 45.0

    def __init__(self, port, logger, serial_nr=None,
                 min_temp_c=DEVICE_MIN_C, max_temp_c=DEVICE_MAX_C,
                 safe_temp_c=25.0, ser=None):
        """
        port        : serial port, e.g. "/dev/ttyUSB0" (Linux) or "COM4" (Windows)
        logger      : a logger object (same pattern as the Lakeshore 224 driver)
        serial_nr   : optional expected device serial/uid, checked on connect
        min_temp_c  : lowest setpoint this driver will allow (default 5 C)
        max_temp_c  : highest setpoint this driver will allow (default 45 C)
        safe_temp_c : neutral temperature the plate returns to on shutdown
        ser         : normally None (a real serial port is opened). A fake serial
                      object can be injected here for offline testing / simulation.
        """
        self.logger = logger
        self.device_serial = serial_nr

        # Allowed setpoint band. Never wider than the device's own 5-45 C limits,
        # but you may pass a tighter band for your experiment.
        self.min_temp_c = max(min_temp_c, self.DEVICE_MIN_C)
        self.max_temp_c = min(max_temp_c, self.DEVICE_MAX_C)
        self.safe_temp_c = safe_temp_c

        if ser is not None:
            # Injected (e.g. simulated) serial object -- used for testing.
            self.ser = ser
        else:
            # Real hardware. 115200 8-N-1 is the MTD1020T's interface.
            self.ser = serial.Serial(
                port     = port,
                baudrate = 115200,
                bytesize = serial.EIGHTBITS,
                parity   = serial.PARITY_NONE,
                stopbits = serial.STOPBITS_ONE,
                timeout  = 5.0)

        self.check_id()

    #############################################################################
    # Low-level helpers
    #############################################################################

    def _query(self, command, retries=1):
        """Send a query like 'Te?' and return the reply as a stripped string.

        The MTD controller occasionally answers the very first command after
        connecting with 'unknown command'; we retry once to absorb that quirk.
        """
        reply = ""
        for _ in range(retries + 1):
            self.ser.reset_input_buffer()
            self.ser.write((command + "\r").encode("ascii"))
            self.ser.flush()
            # This firmware ends every reply with a '>' prompt, so read up to it.
            raw = self.ser.read_until(b">").decode("ascii", "replace")
            reply = raw.strip().rstrip(">").strip()
            if reply and reply != "unknown command":
                return reply
            time.sleep(0.1)
        return reply

    def _command(self, command):
        """Send a setting command (no '?'). The device echoes a prompt after a
        set, so we read up to it to keep the buffer clean for the next query."""
        self.ser.reset_input_buffer()
        self.ser.write((command + "\r").encode("ascii"))
        self.ser.flush()
        self.ser.read_until(b">")

    def _parse_milli(self, response):
        """Convert a milli-unit integer reply (e.g. '25000') to a float (25.0).
        Returns None and logs if the reply cannot be parsed."""
        try:
            return int(response) / 1000.0
        except (ValueError, TypeError):
            self.logger.error("Could not parse PTC1 reply: %r" % response)
            return None

    #############################################################################
    # Identification
    #############################################################################

    def check_id(self):
        self.logger.debug("* check_id command entered (Thorlabs_PTC1). *")
        idn = self._query("m?")   # product name + firmware version
        uid = self._query("u?")   # unique device identifier
        if idn:
            self.logger.info("Thorlabs PTC1 is connected (id: %s, uid: %s)." % (idn, uid))
            if self.device_serial is not None and self.device_serial not in uid:
                self.logger.warning(
                    "PTC1 uid '%s' does not contain the expected serial '%s'."
                    % (uid, self.device_serial))
        else:
            self.logger.error("Thorlabs PTC1 did not respond to identification query!")

    def close_connection(self, go_to_safe_state=True):
        self.logger.debug("* close_connection command entered (Thorlabs_PTC1). *")
        if go_to_safe_state:
            self.set_safe_state()
        self.ser.close()
        self.logger.debug("Thorlabs PTC1 connection is closed.")

    #############################################################################
    # Set / get temperature
    #############################################################################

    def set_temperature(self, temp_c):
        """Set the target temperature in degrees Celsius.

        Refuses (raises ValueError) any value outside the allowed band, so an
        out-of-range request can never be sent to the hardware.
        """
        self.logger.debug("* set_temperature command entered (Thorlabs_PTC1). *")
        if not (self.min_temp_c <= temp_c <= self.max_temp_c):
            self.logger.error(
                "Refusing setpoint %.3f C: outside allowed band %.3f-%.3f C."
                % (temp_c, self.min_temp_c, self.max_temp_c))
            raise ValueError("Setpoint %.3f C out of allowed range" % temp_c)

        millidegrees = int(round(temp_c * 1000))
        self._command("T%d" % millidegrees)
        self.logger.info("PTC1 setpoint set to %.3f C." % temp_c)

    def get_setpoint(self):
        """Return the current target temperature in degrees Celsius."""
        self.logger.debug("* get_setpoint command entered (Thorlabs_PTC1). *")
        return self._parse_milli(self._query("T?"))

    def get_temperature(self):
        """Return the actual measured breadboard temperature in degrees Celsius."""
        self.logger.debug("* get_temperature command entered (Thorlabs_PTC1). *")
        return self._parse_milli(self._query("Te?"))

    def get_tec_current(self):
        """Actual TEC current in amps (sign indicates heating vs cooling)."""
        self.logger.debug("* get_tec_current command entered (Thorlabs_PTC1). *")
        return self._parse_milli(self._query("A?"))

    def get_tec_voltage(self):
        """Actual TEC voltage in volts."""
        self.logger.debug("* get_tec_voltage command entered (Thorlabs_PTC1). *")
        return self._parse_milli(self._query("U?"))

    #############################################################################
    # Errors and safe shutdown
    #############################################################################

    def get_errors(self):
        """Return a list of active error messages (empty list means all good)."""
        self.logger.debug("* get_errors command entered (Thorlabs_PTC1). *")
        response = self._query("E?")
        try:
            register = int(response)
        except (ValueError, TypeError):
            self.logger.error("Could not read PTC1 error register: %r" % response)
            return ["unreadable error register"]

        active = [msg for bit, msg in ERROR_BITS.items() if register & (1 << bit)]
        if active:
            self.logger.warning("PTC1 reports errors: %s" % ", ".join(active))
        return active

    def clear_errors(self):
        self.logger.debug("* clear_errors command entered (Thorlabs_PTC1). *")
        self._command("c")

    def set_safe_state(self):
        """Return the plate to a neutral temperature so the TEC is not driving
        hard when left unattended. (The MTD command set has no explicit
        'disable output'; an ambient setpoint is the safe equivalent.)"""
        self.logger.debug("* set_safe_state command entered (Thorlabs_PTC1). *")
        try:
            self.set_temperature(self.safe_temp_c)
        except ValueError:
            self.logger.error("Safe temperature %.3f C is outside the allowed band!"
                              % self.safe_temp_c)
