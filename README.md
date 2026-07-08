# ADAMOS Temperature Control

Python control software for the ADAMOS experiment (University of Hamburg).

Controls two devices:
- **Thorlabs PTC1(/M)** temperature-controlled breadboard (via USB serial)
- **Lakeshore 224** temperature monitor (via USB serial)

The main entry point (`run_experiment.py`) can run either device alone or both
together — setting the PTC1 setpoint and verifying it with the Lakeshore as an
independent external sensor.

---

## Quick start (brand-new machine)

Follow these steps in order the first time you set this up on a machine.
Each one links to more detail further down if something goes wrong.

1. **Get the code:**
   ```bash
   git clone https://github.com/jingwang039/adamos-control.git
   cd adamos-control/adamos_control
   ```
2. **Install the Python packages** — see [Requirements](#requirements):
   ```bash
   pip3 install --break-system-packages pyserial colorama discord-webhook
   ```
3. **One-time Linux hardware setup** — see [Linux hardware setup](#linux-hardware-setup):
   add yourself to the `dialout` group and load the Lakeshore's USB driver.
   Both are one-off; you won't need to repeat them on this machine again.
4. **Plug in the PTC1 and/or Lakeshore 224 via USB.**
5. **Find out which port is which:**
   ```bash
   python3 run_experiment.py ports
   ```
6. **Run it** — see [Usage](#usage) for the full command reference:
   ```bash
   python3 run_experiment.py hold 35 --paddle-port /dev/ttyUSB0 --monitor-port /dev/ttyUSB1
   ```
   (using whatever ports step 5 reported).

If anything goes wrong at any step, check [Troubleshooting](#troubleshooting)
at the bottom of this file.

---

## Project layout

```
adamos_control/
    run_experiment.py               ← main entry point (both devices)
    experiment_session.py           ← glue layer over both drivers
    Lakeshore_Temperature_Monitor_224.py  ← Lakeshore 224 driver
    log_maker.py                    ← logging helper

PTC1:M_CON/                         ← PTC1 standalone entry point
    main.py                         ← entrypoint: hold / sweep
    src/
        Thorlabs_PTC1_Breadboard.py ← PTC1 driver
        hold_temperature.py
        ptc1_temperature_sweep.py
        port_detection.py
        simulator.py
    test/
```

---

## Requirements

Python 3.6 or newer, plus these packages:

```
pip3 install pyserial colorama discord-webhook
```

On systems with an externally-managed Python (Debian/Ubuntu with Python 3.12+):

```
pip3 install --break-system-packages pyserial colorama discord-webhook
```

---

## Linux hardware setup

### Serial port permissions

Add yourself to the `dialout` group (one-time setup), then log out and back in:

```bash
sudo usermod -aG dialout $USER
```

Until you log out, grant access to the ports directly:

```bash
sudo chmod a+rw /dev/ttyUSB0 /dev/ttyUSB1
```

### Lakeshore 224 USB driver

The Lakeshore 224 uses a Silicon Labs USB chip (`1fb9:0204`) that is not bound
to the `cp210x` kernel module by default. Load the module and register the
device ID:

```bash
sudo modprobe cp210x
echo "1fb9 0204" | sudo tee /sys/bus/usb-serial/drivers/cp210x/new_id
```

Make it persistent across reboots:

```bash
echo "cp210x" | sudo tee /etc/modules-load.d/cp210x.conf
```

After this, `/dev/ttyUSB1` (or similar) will appear when the Lakeshore is
connected.

### Identify which port is which

```bash
ls -la /dev/serial/by-id/
```

Typical result on this machine:

| Device | Port |
|--------|------|
| Thorlabs PTC1 (`FTDI`, serial `02323293`) | `/dev/ttyUSB0` |
| Lakeshore 224 (`Silicon Labs`, `1fb9:0204`) | `/dev/ttyUSB1` |

---

## Usage

All commands are run from the `adamos_control/` directory:

```bash
cd adamos_control
```

### Identify connected devices (do this first)

Before running anything else, find out which port each instrument is on:

```bash
python3 run_experiment.py ports
```

This lists every connected USB serial device and guesses which one is the
PTC1 vs the Lakeshore 224, e.g.:

```
Connected USB serial devices:
  /dev/ttyUSB0   THORLABS PTC1 - THORLABS PTC1            vid:pid=0403:6015 serial=02323293  <- looks like Thorlabs PTC1
  /dev/ttyUSB1   Model 224 Temperature Monitor - Model 224 Temperature Monitor vid:pid=1fb9:0204 serial=LSA21X5  <- looks like Lakeshore 224
```

Use the port shown (e.g. `/dev/ttyUSB0`) for `--paddle-port` / `--monitor-port`
below. If a device you expect doesn't show up, see
[Linux hardware setup](#linux-hardware-setup) above (permissions, cp210x
driver) or run `ls -la /dev/serial/by-id/` as a manual fallback.

### Hold temperature and verify with Lakeshore (both devices)

```bash
python3 run_experiment.py hold 35 \
    --paddle-port /dev/ttyUSB0 \
    --monitor-port /dev/ttyUSB1
```

Logs the Lakeshore C2 reading against the target every few seconds and keeps
running — it does not exit on its own. While it's running:

- Type a new temperature and press **Enter** to change the setpoint live,
  without restarting the program.
- Type **`q`** and press Enter (or press **Ctrl-C**) to stop; the plate keeps
  holding its last setpoint after the script exits.

Optional flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--tolerance C` | 0.5 | Degrees C to count as "reached" |
| `--interval S` | 5 | Polling / logging interval in seconds |
| `--monitor-serial SN` | | Lakeshore serial number substring for ID check |

### Read Lakeshore temperatures only (no PTC1)

```bash
python3 run_experiment.py monitor --monitor-port /dev/ttyUSB1
```

Prints all channels every 5 seconds. Press Ctrl-C to stop. Use `--interval` to
change the polling rate:

```bash
python3 run_experiment.py monitor --monitor-port /dev/ttyUSB1 --interval 1
```

---

## Lakeshore 224 temperature monitor

### Available channels

The monitor reads 9 input channels simultaneously:

| Key | Input | Typical use |
|-----|-------|-------------|
| `t_c2` | C2 | Paddle surface (used by default for PTC1 verification) |
| `t_c3` | C3 | |
| `t_c4` | C4 | |
| `t_c5` | C5 | |
| `t_d1` | D1 | |
| `t_d2` | D2 | |
| `t_d3` | D3 | |
| `t_d4` | D4 | |
| `t_d5` | D5 | |

Only channels with a sensor physically connected return valid readings.
Unconnected channels read **-273.15 °C** (0 K — open circuit).

### Reading a specific channel for PTC1 verification

By default, `hold` uses channel C2 to verify the paddle surface temperature.
To use a different channel pass `--monitor-channel`:

```bash
python3 run_experiment.py hold 35 \
    --paddle-port /dev/ttyUSB0 \
    --monitor-port /dev/ttyUSB1 \
    --monitor-channel t_d1
```

### Sensor troubleshooting

**Channel reads -273.15 °C or jumps wildly:**
- Check the sensor cable is firmly seated in the correct input on the Lakeshore
  front panel.
- Verify the sensor type configured on the instrument matches the physical
  sensor: on the Lakeshore front panel go to `Input → <channel> → Sensor Type`.

### PTC1 only (no Lakeshore)

```bash
cd ../PTC1:M_CON

# Hold at a temperature
python3 main.py hold 35 --port /dev/ttyUSB0

# Run a temperature sweep
python3 main.py sweep --port /dev/ttyUSB0

# Test without hardware
python3 main.py hold 35 --sim
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'Thorlabs_PTC1_Breadboard'`**
Run `run_experiment.py` from inside the `adamos_control/` directory, not the
repo root.

**`Permission denied: '/dev/ttyUSB0'`**
Either add yourself to `dialout` (requires logout) or run
`sudo chmod a+rw /dev/ttyUSB0 /dev/ttyUSB1` as a temporary fix.

**Lakeshore not appearing as `/dev/ttyUSBx`**
Load the driver: `sudo modprobe cp210x && echo "1fb9 0204" | sudo tee /sys/bus/usb-serial/drivers/cp210x/new_id`

**Lakeshore C2 reads -273.15 °C or jumps wildly**
No valid sensor on that channel — check the sensor is plugged into the C2 input
on the Lakeshore front panel and the sensor type matches what is configured in
the instrument menu (`Input → C2 → Sensor Type`).

**`ModuleNotFoundError: No module named 'colorama'`**
`pip3 install --break-system-packages colorama`

**Replies come back empty (`b''`) / nothing happens.**
Almost always the MODE switch is not on "USB", or another program (e.g. the
Thorlabs GUI) is holding the port. Check both.

**Garbled / unreadable output.**
Usually a baud-rate mismatch. The PTC1 uses 115200 baud and the Lakeshore 224
uses 57600 baud — both are set correctly by the drivers.

**Note for developers:** the PTC1 (firmware FW1.0.5) ends every command with a
carriage return (`\r`) and every reply with a `>` prompt. This differs from the
open-source `thorlabs-mtd415t` library, which assumes a line feed (`\n`). If
you adapt code from that library, keep the `\r` behaviour — it's what this
hardware actually expects.
