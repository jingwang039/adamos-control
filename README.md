# ADAMOS Temperature Control

Python control software for the ADAMOS experiment (University of Hamburg).

Controls two devices:
- **Thorlabs PTC1(/M)** temperature-controlled breadboard (via USB serial)
- **Lakeshore 224** temperature monitor (via USB serial)

The main entry point (`run_experiment.py`) can run either device alone or both
together — setting the PTC1 setpoint and verifying it with the Lakeshore as an
independent external sensor.

---

## Project layout

```
adamos_control/
    run_experiment.py               ← main entry point (both devices)
    experiment_session.py           ← glue layer over both drivers
    Lakeshore_Temperature_Monitor_224.py  ← Lakeshore 224 driver
    log_maker.py                    ← logging helper
    PTC1:M/                         ← legacy standalone PTC1 scripts

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

### Hold temperature and verify with Lakeshore (both devices)

```bash
python3 run_experiment.py hold 35 \
    --paddle-port /dev/ttyUSB0 \
    --monitor-port /dev/ttyUSB1
```

Waits until the Lakeshore C2 channel confirms the surface is within 0.5 °C of
35 °C for 30 seconds, then exits leaving the plate actively regulating.

Optional flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--tolerance C` | 0.5 | Degrees C to count as "reached" |
| `--timeout S` | 600 | Give up after this many seconds |
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
