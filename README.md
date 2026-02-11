# Oriental Motor CVD Controller - Multi-Station System

Multi-station synchronized motor control system for Oriental Motor CVD-28-KR drivers with PKP stepper motors, video playback, and LED integration.

## Overview

This system controls **11 independent Raspberry Pi installations** (Prologue → 工程2-10 → Epilogue), each running synchronized video + motor operations + optional LEDs. Station 2 acts as the master keyboard controller, broadcasting START/STOP/RESET commands to all stations via OSC over LAN.

**Key Architecture Principle**: The Raspberry Pi is a **trigger controller only**. All motor motion profiles are pre-programmed using Oriental Motor's **MEXE software** and stored in the driver. The Pi simply selects operation numbers and sends START signals at programmed timecodes.

### USB Keyboard Control

The master station (typically Station 2) can have a USB keyboard connected for manual control:

- **V key**: Toggle start/stop operation
  - First press: Start video + motors on all stations
  - Second press: Stop everything
- **C key**: Enter standby mode
  - Motors return to home position
  - Standby video plays
- **Ctrl key**: Clear motor alarm
  - Clears any active alarms on the motor driver
  - Recovers system from error state

The keyboard can be connected to **any station** - just enable `network_master` mode in that station's config. See `config/README.md` for setup instructions.

## Hardware

### Per Station
- **Raspberry Pi 4** - Main controller
- **Oriental Motor CVD-28-KR** - Stepper driver (1-3 units per station, Modbus RTU via RS-485)
- **PKP266MD28A / PKP268D28A** - Stepper motors
- **24VDC Power Supply** - 3A+ per driver (CVD requires 24V ±10%)
- **Display** - HDMI video output
- **Optional**: WS2812 LED strips (stations 7 and 10)
- **Optional**: USB keyboard (can be on any station, typically station 2)

### Network Topology
- All stations on LAN (192.168.10.10 - 192.168.10.19)
- Station 2 broadcasts OSC commands to all stations
- No peer-to-peer communication between stations

### Communication
- **Motor Control**: Modbus RTU over RS-485, 230400 baud, 8N1
- **Inter-Station**: OSC over UDP (port 9000 listen, 9001 send)
- **Slave IDs**: 1-3 per station (daisy-chained RS-485)

## File Structure

```
Oriental_CvD_Controller_Murata/
├── main.py                      # Orchestrator - service wiring and main loop
│
├── drivers/                     # Motor driver communication
│   ├── oriental_cvd.py          # CVD driver Modbus client
│   └── cvd_define.py            # Register definitions and enums
│
├── services/                    # Modular service layer
│   ├── motor_service.py         # Multi-motor wrapper
│   ├── video_player.py          # VLC video playback
│   ├── sequence_controller.py   # Timecode-based cue engine
│   ├── network_sync.py          # OSC sender/listener
│   ├── keyboard_handler.py      # 3-key GPIO input (station 2)
│   ├── led_strip.py             # WS2812 LED control (stations 7, 10)
│   ├── health_monitor.py        # Background alarm polling
│   └── io_manager.py            # GPIO (limit switches, E-stop, status LED)
│
├── utils/                       # Utilities
│   ├── config_loader.py         # JSON config loader and validator
│   ├── logger.py                # Logging setup
│   ├── watchdog.py              # RPi hardware watchdog wrapper
│   ├── find_registers.py        # Dev tool: scan Modbus registers
│   └── scan_modbus.py           # Dev tool: find connected drivers
│
├── config/                      # Station-specific configs
│   ├── station_02.json          # 工程2 (master keyboard station)
│   ├── station_04.json          # 工程4 (3-motor station)
│   ├── station_06.json          # 工程6 (single motor)
│   ├── station_07.json          # 工程7 (motor + LED)
│   ├── station_epilogue.json    # Epilogue (video-only)
│   └── ...
│
├── tests/                       # Development test scripts
│   ├── test_cvd_main.py         # CVD keyboard test harness
│   └── test_direct_cvd_correct.py
│
├── systemd/                     # Deployment
│   └── oriental-controller.service
│
└── requirements.txt
```

## Station Configuration

### Station Table

| Station | Motors | Slave IDs | Keyboard | LED | Notes |
|---------|--------|-----------|----------|-----|-------|
| Prologue | 1 | [1] | no | no | |
| 工程2 | 1 | [1] | **yes** (USB) | no | **Master broadcaster** |
| 工程3 | 1 | [1] | no | no | |
| 工程4 | **3** | [1,2,3] | no | no | Daisy-chain RS-485 |
| 工程5 | 1 | [1] | no | no | |
| 工程6 | 1 | [1] | no | no | |
| 工程7 | 1 | [1] | no | **yes** | WS2812 LED strip |
| 工程8 | 2 | [1,2] | no | no | |
| 工程9 | 2 | [1,2] | no | no | |
| 工程10 | 1 | [1] | no | **yes** | WS2812 LED strip |
| Epilogue | **0** | — | no | no | **Video-only** |

### Example Config (Station 6)

```json
{
  "station_id": "06",
  "station_name": "工程6 (Single Motor Station)",

  "serial": {
    "port": "/dev/ttyUSB0",
    "baudrate": 230400,
    "parity": "N",
    "stopbits": 1
  },

  "motors": [
    {
      "name": "motor_1",
      "slave_id": 1,
      "type": "CVD-28-KR",
      "model": "PKP266MD28A"
    }
  ],

  "network": {
    "listen_port": 9000,
    "send_port": 9001,
    "is_sender": false
  },

  "video": {
    "file": "/home/pi/videos/station_06.mp4",
    "player": "vlc",
    "framerate": 30
  },

  "cues": [
    {
      "time_sec": 2.0,
      "target": "motor_1",
      "action": "start_operation",
      "op_no": 0,
      "trigger": "time"
    },
    {
      "time_sec": 8.0,
      "target": "motor_1",
      "action": "start_operation",
      "op_no": 1,
      "trigger": "time"
    }
  ],

  "logging": {
    "level": "INFO",
    "file": "/var/log/oriental-controller/station_06.log"
  },

  "health_monitor": {
    "enabled": true,
    "poll_interval_sec": 1.0
  }
}
```

## Operation Flow

### 1. MEXE Preparation (Offline)
- Use Oriental Motor's **MEXE02** software to design motion profiles
- Program **Stored Data (SD) operations** 0-255 into each driver via USB
- Each operation number contains: position, velocity, accel/decel, current settings
- Test and verify motion profiles before deploying to Pi

### 2. System Startup
Each Pi boots and runs:
```bash
python main.py --station 06
```

This:
- Loads `config/station_06.json`
- Connects to motor driver(s) via Modbus
- Loads video file (VLC)
- Starts OSC listener on port 9000
- Waits for START signal

### 3. Sequence Execution

#### Station 2 (Master)
1. Operator presses **V key** on USB keyboard (start/stop toggle)
2. Station 2 broadcasts OSC `/start` to all stations (192.168.10.10-19)
3. Press **V key** again to stop, or **C key** to enter standby mode

#### All Stations
1. Receive `/start` via OSC
2. Video playback begins
3. Cue timer starts (t=0)
4. At programmed timecodes, Pi sends:
   - `set_operation_no(op_no)` - select MEXE operation
   - `send_start_signal()` - trigger driver to execute
5. Motor executes pre-programmed motion autonomously
6. Pi monitors status flags (READY, MOVE, IN_POS)

#### USB Keyboard Controls (Master Station)
- **V key**: Toggle start/stop - Press once to start, press again to stop operation
- **C key**: Standby mode - Motors return home, standby video plays
- **Ctrl key**: Clear alarm - Clears motor alarms and recovers from error state

## Key Driver Registers (CVD-28-KR)

| Register | Address | Function |
|----------|---------|----------|
| NET_SEL_DATA_BASE | 0x007A | Operation number selection (0-255) |
| DRIVER_INPUT_COMMAND | 0x007D | Input signals (START/STOP/HOME/AWO) |
| DRIVER_OUTPUT_STATUS | 0x007F | Output signals (READY/MOVE/IN_POS/HOME_END) |
| DIRECT_OPERATION | 0x0058 | Direct data operation area |
| Operation Data Base | 0x1800 + (N × 0x40) | Stored data for operation N |

### Input Signals (0x007D)
- **START** (bit 3): Trigger operation
- **STOP** (bit 5): Stop motion
- **HOME** (bit 4): Start homing
- **AWO** (bit 6): Free mode (excitation off)
- **M0-M2** (bits 0-2): Operation number bits

### Output Signals (0x007F)
- **READY** (bit 0): Driver ready
- **MOVE** (bit 2): Motor moving
- **IN_POS** (bit 4): Positioning complete
- **HOME_END** (bit 7): Homing complete

## Installation

### Raspberry Pi Setup

```bash
# Clone repo
cd ~
git clone https://github.com/heyannnn/Oriental_CvD_Controller_Murata.git
cd Oriental_CvD_Controller_Murata

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install VLC (for video playback)
sudo apt-get update
sudo apt-get install vlc

# Enable hardware watchdog (optional but recommended)
sudo raspi-config
# → System Options → Hardware Watchdog → Enable

# Configure station ID in systemd service
sudo nano systemd/oriental-controller.service
# Edit: Environment="STATION_ID=06"

# Deploy systemd service
sudo cp systemd/oriental-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable oriental-controller
sudo systemctl start oriental-controller

# Check status
sudo systemctl status oriental-controller
sudo journalctl -u oriental-controller -f
```

### Development (Mac/Linux)

```bash
# Clone repo
git clone https://github.com/heyannnn/Oriental_CvD_Controller_Murata.git
cd Oriental_CvD_Controller_Murata

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (skip RPi-only packages)
pip install pymodbus pyserial numpy readchar python-osc PyYAML python-vlc python-timecode

# Run test scripts
python tests/test_cvd_main.py
```

## Dependencies

```
# Core
pymodbus>=3.0.0           # Modbus RTU communication
pyserial>=3.5             # Serial port access
numpy>=1.24.0             # Numerical operations

# Communication
python-osc>=1.8.0         # OSC inter-station sync

# Keyboard (master station only)
pynput>=1.7.0             # USB keyboard listener

# Video
python-vlc>=3.0.0         # VLC Python bindings (requires VLC installed)
python-timecode>=1.4.0    # Timecode handling

# RPi-only (install on Pi, skip on dev machines)
gpiozero>=1.6.0           # GPIO control (only for LED strips)
rpi-ws281x>=5.0.0         # WS2812 LED strips (stations 7, 10)

# Dev-only (local testing)
readchar>=4.0.0           # Keyboard input (test scripts)
opencv-python>=4.8.0      # Optional: local video preview
```

## Development Tools

### Find Valid Modbus Registers
```bash
python utils/find_registers.py
```

### Scan for Connected Drivers
```bash
python utils/scan_modbus.py
```

### Test CVD Driver (Keyboard Control)
```bash
python tests/test_cvd_main.py
```

Keyboard:
- `s`: Send START signal
- `t`: Send STOP signal
- `h`: Start homing
- `0-9`: Select operation number
- `r`: Read position
- `ESC`: Exit

## Troubleshooting

### Motor Not Moving
1. Check 24VDC power to CVD driver (green LED on)
2. Verify RS-485 wiring (A/B terminals)
3. Check Modbus connection: `python utils/scan_modbus.py`
4. Verify slave ID matches DIP switches on driver
5. Check alarm status: read register 0x007F, bit 8 = ALARM
6. Ensure MEXE operation is programmed in driver

### OSC Not Working
1. Verify all Pis on same subnet (192.168.10.x)
2. Check firewall: `sudo ufw allow 9000/udp`
3. Test with: `python -c "from pythonosc import udp_client; c = udp_client.SimpleUDPClient('192.168.10.11', 9001); c.send_message('/start', [])"`

### Video Sync Issues
1. Ensure VLC installed: `vlc --version`
2. Check video file path in config
3. Monitor cue timing in logs: `journalctl -u oriental-controller -f`

### LED Not Working (Stations 7, 10)
1. Verify WS2812 wiring: 5V/GND/DATA to GPIO18
2. Check permissions: user must be in `gpio` group
3. Test standalone: `sudo python -c "from rpi_ws281x import PixelStrip, Color; ..."`

## Safety Notes

- **24VDC ONLY**: CVD-28-KR requires 24V ±10%. Do not use 12V adapters.
- **E-Stop**: Wired to GPIO22, triggers immediate motor stop via AWO signal
- **Limit Switches**: Wired to driver directly, not Pi GPIO (driver handles protection)
- **Watchdog**: Hardware watchdog reboots Pi if main loop freezes (must "pet" every 60s)
- **Excitation**: Use `set_free_mode(True)` to de-energize motors when idle

## MEXE Workflow

1. Open MEXE02 software on Windows
2. Connect CVD driver via USB
3. Design motion profile:
   - Position (pulses)
   - Velocity (pps)
   - Acceleration/Deceleration (ms)
   - Current (% of rated)
4. Write to Stored Data operation number (0-255)
5. Disconnect USB, reconnect RS-485 to Pi
6. Update station config cue table with operation number
7. Test with Pi

## License

Internal project - Murata

## Contact

For questions or issues, contact the development team.
