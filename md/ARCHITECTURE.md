# System Architecture - Clean Master-Slave Design

## Overview

This system controls multiple Oriental Motor stations via a centralized master Pi with USB keyboard control.

```
┌─────────────────────────────────────┐
│  Master Pi (key.py)                 │
│  - USB keyboard attached            │
│  - Sends OSC commands               │
│  - No motors connected              │
└───────────┬─────────────────────────┘
            │ OSC Network (UDP)
            │ Port 9010
            ↓
┌───────────────────────────────────────────────┐
│  Slave Pis (main.py auto-start)              │
│  Stations: 02, 03, 04, 05, 06, 07, 08, 09, 10│
│  - Motors via Modbus RS-485                  │
│  - Listen for OSC commands                   │
│  - Execute operations                        │
└───────────────────────────────────────────────┘
```

## Components

### Master Pi (runs key.py)
- **Purpose**: Centralized keyboard control
- **Hardware**: USB keyboard
- **Software**: key.py only
- **Network**: Sends OSC to all stations

### Slave Pis (run main.py)
- **Purpose**: Motor control
- **Hardware**: Oriental Motor via RS-485
- **Software**: main.py (auto-starts via systemd)
- **Network**: Listens for OSC commands

## System Behavior

### Boot Sequence

**On Power-Up:**

1. All slave Pis boot
2. Systemd auto-starts main.py on each Pi
3. Each main.py:
   - Loads config/local.json → Gets station ID
   - Loads config/all_stations.json → Gets motor config
   - Connects to motor via Modbus
   - Performs homing if `homing_required: true`
   - Starts OSC listener on port 9010
   - Enters READY state

**Station-Specific Homing:**

| Station | Homing Required | Return to Zero on Stop |
|---------|----------------|------------------------|
| 02      | No             | No                     |
| 03      | No             | No                     |
| 04      | No             | No                     |
| 05      | Yes            | Yes                    |
| 06      | Yes            | Yes                    |
| 07      | Yes            | Yes                    |
| 08      | Yes            | Yes                    |
| 09      | Yes            | Yes                    |
| 10      | No             | No                     |

### Keyboard Controls

Run key.py on master Pi:

```bash
python key.py
```

**Available Keys:**

| Key    | Action                                    |
|--------|-------------------------------------------|
| V      | Toggle Start/Stop                         |
| C      | Reset all stations to home                |
| Ctrl   | Clear alarm on all stations               |
| Ctrl+C | Exit key.py (stations keep running)       |

### Operation Flow

**Press V Key (First Time - Start):**
```
key.py → OSC /start → All stations
  ↓
Stations receive /start
  ↓
sequence_manager.on_network_start()
  ↓
motor_controller.start_operation(op_no=0)
  ↓
Motor executes MEXE operation 0
  ↓
Looping enabled: Repeats after 3 seconds
```

**Press V Key (Second Time - Stop):**
```
key.py → OSC /stop → All stations
  ↓
Stations receive /stop
  ↓
sequence_manager.on_network_stop()
  ↓
motor_controller.stop()
  ↓
If return_to_zero_on_stop: Return to position 0
Else: Stop at current position
  ↓
STATE: STANDBY
```

**Press C Key (Reset):**
```
key.py → OSC /reset → All stations
  ↓
Stations receive /reset
  ↓
sequence_manager.on_reset_pressed()
  ↓
motor_controller.reset_to_home()
  ↓
STATE: HOMING → READY
```

**Press Ctrl Key (Clear Alarm):**
```
key.py → OSC /clear_alarm → All stations
  ↓
Stations receive /clear_alarm
  ↓
sequence_manager.on_clear_alarm_pressed()
  ↓
motor_controller.clear_alarm()
```

## Configuration

### Station Configuration

Each Pi has two config files:

**config/local.json** (Unique per Pi):
```json
{
  "station_id": "05"
}
```

**config/all_stations.json** (Same on all Pis):
```json
{
  "default": {
    "serial": {"port": "/dev/tty.usbserial-FT78LMAE"},
    "network": {"listen_port": 9010},
    "keyboard": {"enabled": false}
  },
  "05": {
    "station_name": "工程5",
    "motors": [{"slave_id": 1}],
    "homing_required": true,
    "return_to_zero_on_stop": true
  }
}
```

### Master Configuration

**key.py** contains station list:
```python
STATIONS = {
    "02": {"host": "pi-controller-02.local", "port": 9010},
    "03": {"host": "pi-controller-03.local", "port": 9010},
    # ... all stations
}
```

## Installation

### On Each Slave Pi

1. Install the systemd service:
```bash
sudo cp motor-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable motor-controller.service
sudo systemctl start motor-controller.service
```

2. Verify it's running:
```bash
sudo systemctl status motor-controller.service
```

3. Check logs:
```bash
sudo journalctl -u motor-controller.service -f
```

### On Master Pi

1. Just run key.py:
```bash
python key.py
```

## Network Requirements

- All Pis must be on same network
- Hostname resolution must work (`.local` mDNS)
- UDP port 9010 must be open
- No firewall blocking OSC traffic

Test connectivity:
```bash
ping pi-controller-05.local
```

## Motor Operations

Operations are **programmed in MEXE02 software**, not in Python code.

- Python code only **triggers** operations
- Operation 0 = First programmed operation in MEXE02
- Position, speed, acceleration set in MEXE02
- Python monitors completion via RUNNING_DATA_NO register

## State Machine

### System States (sequence_manager.py)

```
BOOT → HOMING → READY ⟷ STANDBY ⟷ RUNNING → FINISHED
                   ↑                            ↓
                   └────── (loop after 3s) ─────┘
```

### Motor States (motor_controller.py)

```
DISCONNECTED → HOMING → READY → RUNNING → FINISHED → READY
                           ↓        ↓
                         ERROR ←────┘
```

## Troubleshooting

### Stations not responding to key presses

1. Check stations are running:
```bash
# On each slave Pi
sudo systemctl status motor-controller.service
```

2. Check network connectivity:
```bash
# From master Pi
ping pi-controller-05.local
```

3. Check OSC listener:
```bash
# On slave Pi
sudo journalctl -u motor-controller.service | grep "OSC listener"
```

### Motor not homing

- Check `homing_required` in config
- Check motor is powered on
- Check RS-485 connection
- Check logs: `sudo journalctl -u motor-controller.service -n 100`

### Motor moves but doesn't stop

- Operation 0 might not be programmed in MEXE02
- Check MEXE02 software for operation settings
- Monitor RUNNING_DATA_NO register (should become -1 when done)

## Files Reference

| File                      | Purpose                          |
|---------------------------|----------------------------------|
| key.py                    | Master keyboard controller       |
| main.py                   | Station entry point              |
| motor-controller.service  | Systemd auto-start service       |
| config/local.json         | Station ID (unique per Pi)       |
| config/all_stations.json  | All station configurations       |
| services/motor_controller.py | Motor state machine           |
| services/motor_driver.py  | Low-level Modbus commands        |
| services/sequence_manager.py | System coordinator            |
| services/network_sync.py  | OSC communication                |
| drivers/oriental_cvd.py   | Oriental Motor driver            |

## Development Notes

- **keyboard_handler.py** is disabled (not used in this architecture)
- All keyboard control via key.py on master Pi only
- Stations listen for OSC, no local keyboard
- Auto-start via systemd ensures reliability
- Looping delay: 3 seconds (configurable in config)
