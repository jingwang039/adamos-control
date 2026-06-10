# PTC1 Temperature-Controlled Breadboard — Control Software

Python control software for the **Thorlabs PTC1(/M)** temperature-controlled
breadboard, used in the ADAMOS experiment (University of Hamburg).

The PTC1 is driven internally by a Thorlabs **MTD1020T** TEC controller, which
these scripts talk to directly over USB. This means you do **not** need the
Thorlabs Windows GUI — the software here runs on Linux, macOS, and Windows,
because all it needs is the serial port the device presents.

---

## The files and what each one does

| File | Role | Run it directly? |
|------|------|------------------|
| `Thorlabs_PTC1_Breadboard.py` | **The driver.** Knows how to talk to the plate (commands, units, safety limits). Everything else uses it. | No — it's imported by the others |
| `hold_temperature.py` | Set the plate to a temperature and **hold it** for running experiments. | Yes |
| `ptc1_temperature_sweep.py` | Step through a list of temperatures and **log** them to a CSV (characterization). | Yes |
| `test_ptc1_sim.py` | A **simulated** plate, so you can test the scripts with no hardware. | Yes (or via `--sim`) |

**Keep all four files in the same folder.** The two programs you run import the
driver (and the simulator, when using `--sim`), so they fail immediately if the
driver file is missing.

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
2. Power the unit on and connect the USB cable to your computer.
3. **Do not run the Thorlabs GUI at the same time** — only one program can use
   the serial port at once. (You don't need the GUI at all for these scripts.)

Over USB the valid temperature range is **5 to 45 °C**. The driver refuses any
value outside that, so a typo cannot drive the plate somewhere unsafe.

---

## Finding the port

You need the name of the serial port the plate appears as. It differs per OS.

**Linux**

```
ls /dev/ttyUSB*
```

Usually `/dev/ttyUSB0`. If you get a "permission denied" error when running a
script, add yourself to the `dialout` group once, then log out and back in:

```
sudo usermod -a -G dialout $USER
```

**macOS**

```
ls /dev/cu.usbserial*
```

Something like `/dev/cu.usbserial-02323293`. **Use the `cu.` name, not the
`tty.` one** — the `tty.` version will hang on opening.

**Windows**

Open **Device Manager → Ports (COM & LPT)**. The plate appears as a
"USB Serial Port" with a name like `COM4`. Use that name (e.g. `COM4`) as the
port. If no COM port appears, install the **FTDI VCP driver** (from Thorlabs or
ftdichip.com) — but you still do not need to launch the Thorlabs GUI.

---

## Usage

In the examples below, replace the port with your own (see above). On Windows,
use `python` instead of `python3`, and your `COMx` name instead of the
`/dev/...` path.

### Hold the plate at a temperature (for experiments)

The target temperature is the **first thing after the filename**:

```
python3 hold_temperature.py 35 --port /dev/cu.usbserial-02323293
```

This sets 35 °C, waits until the plate reaches and holds it, then disconnects
**leaving the plate at 35 °C**. The controller keeps regulating on its own, so
the plate stays warm even after the program ends and even if you close the
terminal. Decimals are fine (e.g. `32.5`). Add `--no-wait` to set the target
and exit at once without waiting for confirmation.

**When you finish your experiment, return the plate to a resting state** — set
it back down or power the unit off:

```
python3 hold_temperature.py 25 --port /dev/cu.usbserial-02323293
```

### Run a logged temperature sweep (for characterization)

Edit the list of temperatures at the top of `ptc1_temperature_sweep.py`:

```python
TARGETS_C = [24.0, 25.0, 26.0]
```

Then run it:

```
python3 ptc1_temperature_sweep.py --port /dev/cu.usbserial-02323293
```

It visits each temperature, waits for it to settle, writes a row to
`sweep_results.csv`, and at the end **returns the plate to 25 °C** (this is the
opposite of `hold_temperature.py` — the sweep is for measuring, not for holding
a plate for experiments). Settling rule and timing are constants at the top of
the file.

### Test without hardware

Any script can run against the simulator with `--sim` instead of `--port`:

```
python3 hold_temperature.py 35 --sim
python3 ptc1_temperature_sweep.py --sim
python3 test_ptc1_sim.py
```

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
