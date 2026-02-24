# Oriental CVD Motor Controller

Multi-station motor control system for Oriental CVD-28-KR motors with synchronized video playback.

## System Overview

- **Master Station**: Pi-02 (192.168.1.2) - Central controller with USB keyboard input
- **Slave Stations**: Pi-03 through Pi-11 - Controlled by master via OSC
- **Communication**: OSC (Open Sound Control) over UDP
- **Motor Control**: Modbus RTU over RS485

```
                    ┌─────────────────────────────────────┐
                    │  MASTER CONTROL (Pi-02)             │
                    │  192.168.1.2                        │
                    │  - main.py                          │
                    │  - key.py (USB Keyboard via evdev)  │
                    │  - sequence_manager.py              │
                    └─────────────────┬───────────────────┘
                                      │
                         OSC Commands (UDP port 10000)
                         /start, /stop, /reset
                                      │
        ┌──────────┬──────────┬───────┴───┬──────────┬──────────┐
        │          │          │           │          │          │
     Pi-03      Pi-04      Pi-05       Pi-06     ...        Pi-11
     工程3       工程4       工程5        工程6               工程11
   2 Motors    3 Motors   1 Motor     1 Motor            Video Only
```

---

## Station Configuration

| Station | Name | Motors | Homing | Return-to-Zero | Video Sync Delay | Special |
|---------|------|--------|--------|----------------|------------------|---------|
| 02 | 工程2 | 1 | NO | NO | 0s | Master, keyboard control |
| 03 | 工程3 | 2 | NO | NO | 0s | Multi-motor |
| 04 | 工程4 | 3 | NO | NO | 0s | Multi-motor (3) |
| 05 | 工程5 | 1 | YES | YES | 10.5s | HOMES detection |
| 06 | 工程6 | 1 | YES | YES | 1.5s | |
| 07 | 工程7 | 1 | YES | YES | 1.5s | LED control |
| 08 | 工程8 | 2 | YES | YES | 1.5s | HOMES detection, multi-motor |
| 09 | 工程9 | 2 | YES | YES | 1.5s | HOMES detection, multi-motor |
| 10 | 工程10 | 1 | NO | NO | 0s | LED control |
| 11 | 工程11 | 0 | NO | NO | 0s | Video only |

---

## Keyboard Controls (Pi-02 Master)

| Key | Action |
|-----|--------|
| `V` | Toggle start/stop |
| `Ctrl+V` | Reset (stop → clear alarm → home → wait) |
| `Ctrl+C` | Exit program |

---

## File Structure

```
Oriental_CvD_Controller_Murata/
├── main.py                          # Entry point (all Pis)
├── key.py                           # Keyboard input (Pi-02 only)
├── deploy.py                        # Deployment tool (Mac)
├── setup_autostart.py               # Systemd setup (Mac)
│
├── config/
│   ├── all_stations.json            # All station configs (same on all Pis)
│   └── local.json                   # Station ID (different per Pi)
│
├── services/
│   ├── motor_controller.py          # Motor state machine
│   ├── motor_driver.py              # Modbus RS485 driver
│   ├── sequence_manager.py          # Master coordinator (Pi-02 only)
│   └── mp4_player.py                # Video player control
│
└── drivers/
    ├── oriental_cvd.py              # Low-level Modbus client
    └── cvd_define.py                # Constants & enums
```

---

## File Details

### main.py

**Purpose**: Entry point for all stations. Runs on every Pi.

**What it does**:
1. Loads `config/local.json` to determine station ID
2. Loads `config/all_stations.json` to get full configuration
3. Determines if this Pi is master (station 02) or slave
4. Initializes MotorController with motor configuration
5. Sets up OSC listener on port 10000 for receiving commands
6. (Master only) Initializes KeyboardController and SequenceManager
7. Auto-homes motors if required
8. Runs main loop waiting for commands

**Key functions**:
- `load_local_config()` - Read local.json
- `load_station_config(station_id)` - Merge default + station config
- `setup_osc_listener()` - Create OSC server for /start, /stop, /reset
- `main()` - Async main loop

---

### key.py

**Purpose**: USB keyboard input handler. Only used on Pi-02 (master).

**What it does**:
1. Uses `evdev` library to read directly from USB keyboard device
2. Works even when running as systemd service (no terminal required)
3. Monitors V key for start/stop toggle
4. Monitors Ctrl+V for reset
5. Calls SequenceManager callbacks on key press

**Key classes**:
- `KeyboardController` - Main keyboard handler

**Key methods**:
- `find_keyboard()` - Find USB keyboard device in /dev/input/
- `start()` - Begin keyboard listener thread
- `stop()` - Stop listening
- `_keyboard_loop()` - Background thread reading key events
- `set_on_start(callback)` - Set start callback
- `set_on_stop(callback)` - Set stop callback
- `set_on_reset(callback)` - Set reset callback

**Requirements**:
- `pip install evdev`
- User must be in `input` group: `sudo usermod -aG input user`

---

### services/sequence_manager.py

**Purpose**: Master coordinator. Only runs on Pi-02.

**What it does**:
1. Receives keyboard input callbacks from KeyboardController
2. Sends OSC commands (/start, /stop, /reset) to all slave stations
3. Receives /status messages from all slaves
4. Tracks system state (is_running, is_resetting)
5. Coordinates with local MotorController for Pi-02's own motors

**Key classes**:
- `SequenceManager` - Main coordinator

**Key methods**:
- `on_start_pressed()` - Handle V key when stopped
- `on_stop_pressed()` - Handle V key when running
- `on_reset_pressed()` - Handle Ctrl+V
- `_send_to_all(command)` - Send OSC to all stations
- `_handle_status(station_id, state)` - Receive status from slave
- `get_is_running()` - Return current running state
- `start_server()` - Start OSC server
- `stop_server()` - Stop OSC server

---

### services/motor_controller.py

**Purpose**: State machine for motor operations. Runs on all Pis with motors.

**What it does**:
1. Manages motor state (DISCONNECTED, HOMING, HOME_END, RUNNING, READY, ERROR, RESETTING)
2. Handles /start, /stop, /reset commands
3. Controls video player via MP4Player
4. Monitors motor status (alarm, HOMES sensor, ready)
5. Auto-recovers from errors (clear alarm, re-home)
6. Sends status updates to master via OSC

**Key classes**:
- `MotorController` - Main state machine
- `MotorState` - Enum of states

**Key methods**:
- `initialize()` - Connect motors, auto-home if needed
- `on_start()` - Handle /start command
- `on_stop()` - Handle /stop command
- `on_reset()` - Handle /reset command
- `start_operation(op_no)` - Start MEXE operation
- `stop()` - Stop all motors
- `clear_alarm()` - Clear motor alarms
- `_monitor_operation()` - Background monitoring thread
- `_auto_reset()` - Auto-recover from error
- `_send_status()` - Send state to master
- `get_state()` - Return current state

**States**:
- `DISCONNECTED` - Not connected to motors
- `HOMING` - Homing in progress
- `HOME_END` - Homed and ready
- `RUNNING` - Operation in progress
- `READY` - Operation complete, can loop
- `ERROR` - Alarm detected
- `RESETTING` - Reset in progress

---

### services/motor_driver.py

**Purpose**: Low-level Modbus RS485 driver. Wraps OrientalCvdMotor.

**What it does**:
1. Manages RS485 serial connection
2. Shares connection between multiple motors on same bus
3. Sends Modbus commands to motors
4. Reads motor status registers

**Key classes**:
- `MotorDriver` - Driver for single motor
- `_SharedClientManager` - Manages shared connections

**Key methods**:
- `connect()` - Connect via shared Modbus client
- `close()` - Disconnect (only closes if last reference)
- `send_home_command()` - Send HOME signal
- `is_home_complete()` - Check HOME_END flag
- `start_operation(op_no)` - Start MEXE operation (0-7)
- `stop()` - Send STOP signal
- `clear_alarm()` - Send ALM_RST signal
- `return_to_zero(velocity)` - Move to position 0
- `is_ready()` - Check READY flag
- `get_alarm_status()` - Check ALARM flag
- `is_homes_detected()` - Check HOMES sensor
- `read_position()` - Get current position

**Shared Connection**:
```
Multiple motors on same RS485 bus share one connection:

MotorDriver(slave_id=1) ─┐
MotorDriver(slave_id=2) ─┼─► Shared OrientalCvdMotor client
MotorDriver(slave_id=3) ─┘
```

---

### services/mp4_player.py

**Purpose**: Video player control via OSC.

**What it does**:
1. Sends OSC commands to local video player (127.0.0.1:9000)
2. Loads different playlists based on state

**Key classes**:
- `MP4Player` - Video player controller

**Key methods**:
- `send_command(command)` - Send playlist load command

**Video files**:
- `NormalOperation.csv` - Normal operation video
- `Sync.csv` - Loop sync point video (stations with homing)
- `Waiting.csv` - Idle/stopped video

---

### config/all_stations.json

**Purpose**: Master configuration for all stations. Same file on all Pis.

**Structure**:
```json
{
  "default": {
    "serial": {"port": "/dev/ttyAMA0", "baudrate": 230400},
    "network": {"listen_port": 10000, "master_ip": "192.168.1.2"},
    "loop_delay_sec": 0.0
  },
  "stations": {
    "02": {
      "station_name": "工程2",
      "motors": [{"slave_id": 1}],
      "homing_required": false
    },
    "05": {
      "station_name": "工程5",
      "motors": [{"slave_id": 1}],
      "homing_required": true,
      "return_to_zero_on_stop": true,
      "video_sync_delay_sec": 10.5
    }
  }
}
```

**Config inheritance**: Each station's config = `default` merged with `stations[id]`

---

### config/local.json

**Purpose**: Identifies which station this Pi is. Different on each Pi.

**Structure**:
```json
{
  "station_id": "05"
}
```

---

### deploy.py

**Purpose**: Deployment and management tool. Run from Mac.

**Commands**:
```bash
python deploy.py deploy    # Deploy files and start main.py
python deploy.py files     # Deploy files only (no restart)
python deploy.py start     # Start main.py on all Pis
python deploy.py stop      # Stop main.py on all Pis
python deploy.py status    # Check if main.py is running
python deploy.py logs      # Show recent logs from all Pis
python deploy.py logs 05   # Follow Pi-05 logs in real-time
```

**What it deploys**:

All Pis:
- `config/all_stations.json`
- `main.py`
- `services/motor_controller.py`
- `services/motor_driver.py`
- `services/mp4_player.py`

Pi-02 only (additional):
- `key.py`
- `services/sequence_manager.py`

---

### setup_autostart.py

**Purpose**: Setup systemd autostart. Run from Mac.

**Commands**:
```bash
python setup_autostart.py install   # Install and enable autostart
python setup_autostart.py remove    # Remove autostart
python setup_autostart.py status    # Check autostart status
```

**What it does**:
1. Creates `/etc/systemd/system/motor-controller.service` on each Pi
2. Enables service to start on boot
3. Starts service immediately

---

## Data Flow

### Startup Sequence

```
main.py starts
    │
    ├── Load config/local.json
    │   └── "I am station 05"
    │
    ├── Load config/all_stations.json
    │   └── Get motors, network, homing settings
    │
    ├── Initialize MotorController
    │   ├── Connect to motors via RS485
    │   └── Auto-home if homing_required=true
    │
    ├── Setup OSC listener (port 10000)
    │   └── Listen for /start, /stop, /reset
    │
    └── (Pi-02 only)
        ├── Start KeyboardController
        └── Start SequenceManager
```

### Start Operation (V key pressed)

```
USB Keyboard (Pi-02)
    │
    ▼
key.py detects V key
    │
    ▼
sequence_manager.on_start_pressed()
    │
    ├──► OSC /start to Pi-03
    ├──► OSC /start to Pi-04
    ├──► OSC /start to Pi-05
    │    ...
    └──► OSC /start to Pi-11
    │
    ▼
Each Pi: motor_controller.on_start()
    │
    ├── mp4_player.send_command("start")
    │   └── /playlist/load NormalOperation.csv
    │
    ├── Wait video_sync_delay_sec
    │
    ├── motor_driver.start_operation(0)
    │   └── Modbus command to motor
    │
    └── Monitor until READY
        │
        └── Send /status to master
```

### Stop Operation (V key pressed while running)

```
sequence_manager.on_stop_pressed()
    │
    ├──► OSC /stop to all stations
    │
    ▼
Each Pi: motor_controller.on_stop()
    │
    ├── motor_driver.stop()
    │
    ├── (if return_to_zero_on_stop)
    │   └── motor_driver.return_to_zero()
    │
    └── mp4_player.send_command("stop")
        └── /playlist/load Waiting.csv
```

### Reset Operation (Ctrl+V pressed)

```
sequence_manager.on_reset_pressed()
    │
    ├──► OSC /reset to all stations
    │
    ▼
Each Pi: motor_controller.on_reset()
    │
    ├── motor_driver.stop()
    │
    ├── motor_driver.clear_alarm()
    │
    ├── (if homing_required)
    │   └── motor_driver.send_home_command()
    │       └── Wait for HOME_END
    │
    └── mp4_player.send_command("stop")
```

---

## OSC Protocol

### Commands (Master → Slaves)

| Message | Description |
|---------|-------------|
| `/start` | Start operation |
| `/stop` | Stop operation |
| `/reset` | Reset (stop, clear alarm, home) |

### Status (Slaves → Master)

| Message | Parameters | Description |
|---------|------------|-------------|
| `/status` | station_id, state | Report current state |

States: `disconnected`, `homing`, `home_end`, `running`, `ready`, `error`, `resetting`

### Video Control (Local)

| Message | Parameters | Description |
|---------|------------|-------------|
| `/playlist/load` | filename | Load video playlist |

Files: `./NormalOperation.csv`, `./Sync.csv`, `./Waiting.csv`

---

## Network Configuration

| Pi | IP Address | OSC Port | Role |
|----|------------|----------|------|
| 02 | 192.168.1.2 | 10000 | Master |
| 03 | 192.168.1.3 | 10000 | Slave |
| 04 | 192.168.1.4 | 10000 | Slave |
| 05 | 192.168.1.5 | 10000 | Slave |
| 06 | 192.168.1.6 | 10000 | Slave |
| 07 | 192.168.1.7 | 10000 | Slave |
| 08 | 192.168.1.8 | 10000 | Slave |
| 09 | 192.168.1.9 | 10000 | Slave |
| 10 | 192.168.1.10 | 10000 | Slave |
| 11 | 192.168.1.11 | 10000 | Slave |

Video player on each Pi: `127.0.0.1:9000`

---

## Motor State Machine

```
    ┌─────────────────┐
    │   DISCONNECTED  │
    └────────┬────────┘
             │ initialize()
             ▼
    ┌─────────────────┐
    │     HOMING      │ ◄── auto-home on startup
    └────────┬────────┘
             │ HOME_END flag
             ▼
    ┌─────────────────┐
    │    HOME_END     │ ◄── ready for commands
    └────┬───────┬────┘
         │       │
   on_start() on_reset()
         │       │
         ▼       ▼
┌──────────────┐  ┌──────────────┐
│   RUNNING    │  │  RESETTING   │
└──────┬───────┘  └──────┬───────┘
       │                 │
  READY flag        home complete
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│    READY     │  │   HOME_END   │
│ (can loop)   │  └──────────────┘
└──────────────┘
```

---

## Error Handling

### Alarm Detection
- MotorController monitors ALARM flag every 0.2s
- On alarm: stop → clear_alarm → home → continue or wait

### HOMES Sensor (Stations 05, 08, 09)
- Monitors HOMES sensor during operation
- If triggered: auto-reset (motor hit home sensor unexpectedly)

### Connection Loss
- OSC send failures are logged but don't crash
- Station reconnects and resumes on restart

---

## Logging

Log files: `/tmp/main_XX.log` (XX = station ID)

View logs:
```bash
python deploy.py logs        # Recent logs from all
python deploy.py logs 05     # Follow Pi-05 live
```

Or manually:
```bash
sshpass -p 'fukuimurata' ssh user@pi-controller-05.local "tail -f /tmp/main_05.log"
```

---

## Quick Start

### 1. Deploy to all Pis
```bash
python deploy.py deploy
```

### 2. Check status
```bash
python deploy.py status
```

### 3. Control via keyboard on Pi-02
- Press `V` to start
- Press `V` again to stop
- Press `Ctrl+V` to reset

### 4. Setup autostart (optional)
```bash
python setup_autostart.py install
```

---

## Requirements

### On Pis
- Python 3.7+
- `pip install pymodbus python-osc evdev`
- User in `input` group (Pi-02): `sudo usermod -aG input user`

### On Mac (for deployment)
- `brew install hudochenkov/sshpass/sshpass`
