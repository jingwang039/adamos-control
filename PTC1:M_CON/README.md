# PTC1 Temperature-Controlled Breadboard — Control Software

Python control software for the **Thorlabs PTC1(/M)** temperature-controlled
breadboard, used in the ADAMOS experiment (University of Hamburg).

The PTC1 is driven internally by a Thorlabs **MTD1020T** TEC controller, which
these scripts talk to directly over USB. This means you do **not** need the
Thorlabs Windows GUI — the software here runs on Linux, macOS, and Windows,
because all it needs is the serial port the device presents.

---

## Project layout

```
main.py                          ← single entrypoint for all scripts
src/
    Thorlabs_PTC1_Breadboard.py  ← driver: commands, units, safety limits
    simulator.py                 ← software-only fake device (used by --sim)
    port_detection.py            ← auto-detects which USB port the device appeared on
    hold_temperature.py          ← hold a temperature for experiments
    ptc1_temperature_sweep.py    ← step through temperatures and log to CSV
test/
    test_driver.py
    test_simulator.py
    test_port_detection.py
    test_hold_temperature.py
    test_sweep.py
```

Run tests (no hardware needed):

```
python3 -m unittest discover -s test -p "test_*.py" -v
```

---

## Requirements

* Python 3 (3.6 or newer)
* The `pyserial` package

Install pyserial:

```
pip install pyserial
```

On macOS or Linux, if pip complains about an "externally managed environment",
use a virtual environment instead:

```
python3 -m venv ~/ptc1-env
source ~/ptc1-env/bin/activate
pip install pyserial
```

---

## Hardware setup (do this first, every time)

1. Set the front-panel **MODE switch to "USB"** (not the knob/front-panel).
   In front-panel mode the device ignores everything sent over USB.
2. **Do not run the Thorlabs GUI at the same time** — only one program can use
   the serial port at once. (You don't need the GUI at all for these scripts.)

Over USB the valid temperature range is **5 to 45 °C**. The driver refuses any
value outside that, so a typo cannot drive the plate somewhere unsafe.

---

## Usage

All scripts are run through `main.py`. On Windows use `python` instead of
`python3` and your `COMx` name for the port.

There are three ways to tell the script which port to use:

| Method | When to use |
|--------|-------------|
| No port argument | **Recommended.** The script prompts you to plug in the device and finds the port automatically. |
| `--port PORT` | You already know the port name (e.g. from a previous run). |
| `--sim` | No hardware — runs against a built-in software simulator. |

### Hold the plate at a temperature (for experiments)

**Auto-detect the port (not yet implemented):**

```
python3 main.py hold 35
```

The script prints `Plug the PTC1 into a USB port now ...` and waits. Plug the
device in; it detects the new port automatically and continues. You have 60
seconds to connect the device before it times out.

**Explicit port:**

```
python3 main.py hold 35 --port /dev/cu.usbserial-02323293
```

Both forms set 35 °C, wait until the plate reaches and holds it, then
disconnect **leaving the plate at 35 °C**. The controller keeps regulating on
its own, so the plate stays warm even after the program ends. Decimals are fine
(e.g. `32.5`). Add `--no-wait` to set the target and exit immediately without
waiting for confirmation.

**When you finish your experiment, return the plate to a resting state:**

```
python3 main.py hold 25
```

### Run a logged temperature sweep (for characterization)

Edit the list of temperatures at the top of `src/ptc1_temperature_sweep.py`:

```python
TARGETS_C = [24.0, 25.0, 26.0]
```

**Auto-detect the port:**

```
python3 main.py sweep
```

**Explicit port:**

```
python3 main.py sweep --port /dev/cu.usbserial-02323293
```

The sweep visits each temperature, waits for it to settle, writes a row to
`sweep_results.csv`, and at the end **returns the plate to 25 °C**. Settling
rule and timing are constants at the top of `src/ptc1_temperature_sweep.py`.

### Test without hardware

Both scripts accept `--sim` to run against the built-in software simulator:

```
python3 main.py hold 35 --sim
python3 main.py sweep --sim
```

### Finding the port manually

If you need the port name (e.g. to pass `--port`):

**Linux** — usually `/dev/ttyUSB0`:
```
ls /dev/ttyUSB*
```
If you get "permission denied", add yourself to the `dialout` group once, then
log out and back in:
```
sudo usermod -a -G dialout $USER
```

**macOS** — something like `/dev/cu.usbserial-02323293`:
```
ls /dev/cu.usbserial*
```
**Use the `cu.` name, not `tty.`** — the `tty.` version hangs on open. The
auto-detect feature handles this correctly on its own.

**Windows** — open **Device Manager → Ports (COM & LPT)**. The plate appears
as "USB Serial Port" with a name like `COM4`. If nothing appears, install the
**FTDI VCP driver** from Thorlabs or ftdichip.com.

---

## Troubleshooting

**Replies come back empty (`b''`) / nothing happens.** Almost always the MODE
switch is not on "USB", or another program (e.g. the Thorlabs GUI) is holding
the port. Check both.

**The port doesn't show up.** On Windows, install the FTDI VCP driver. On Linux,
check the cable and that the unit is powered. On macOS, make sure you're looking
for `cu.usbserial*`.

**"Permission denied" on Linux.** Add yourself to the `dialout` group (above).

**Garbled / unreadable output.** Usually a baud-rate mismatch; this hardware
uses 115200 baud, which the driver already sets.

---

## Note for developers

This driver was verified on a real PTC1 running firmware **FW1.0.5**, which uses
a **carriage return (`\r`)** to end commands and ends every reply with a `>`
prompt. This differs from the open-source `thorlabs-mtd415t` library, which
assumes a line feed (`\n`). If you adapt code from that library, keep the `\r`
behaviour — it is what this hardware actually expects.
