# OrientalAZController_Murata

Multi-project synchronized motor control system for Oriental Motor AZ/CVD series drivers with video playback integration.

## Overview

This system controls 9 independent Raspberry Pi installations, each managing motor drivers synchronized to video timecode. The architecture supports flexible configuration for different hardware setups including multiple motors, limit switches, and LED indicators.

## System Architecture

### Core Components

```
OrientalAZController_Murata/
├── config/               # Project-specific configuration files
│   ├── project_1.json
│   ├── project_2.json
│   └── ... (up to project_9.json)
├── core/                 # Core functionality modules
│   ├── motor_controller.py    # Motor control abstraction
│   ├── video_player.py        # HDMI video playback
│   ├── timecode_sync.py       # Timecode synchronization
│   └── io_manager.py          # Digital I/O (LEDs, limit switches)
├── definitions/          # Hardware register definitions
│   └── az_registers.py        # Oriental Motor register maps
├── projects/             # Project-specific implementations
│   ├── base_project.py        # Abstract base class
│   ├── project_1.py           # Project 1 specific logic
│   └── ...
├── mexe/                 # MEXE operation data handling
│   └── parser.py              # MEXE file parser/executor
├── utils/                # Helper utilities
└── main.py               # Entry point
```

## Hardware Setup

Each installation consists of:
- **Raspberry Pi** - Main controller, video playback via HDMI
- **Oriental Motor Driver(s)** - AZ/CVD series (RS-485 Modbus RTU)
- **Motor(s)** - 1 to N motors per driver
- **Optional I/O** - Limit switches, LED indicators
- **Display** - HDMI output for synchronized video

### Communication
- **Protocol**: Modbus RTU over RS-485
- **Baudrate**: 230400
- **Default Port**: Configurable per project

## Configuration System

### Project Selection

Set the project number in `config/active_project.txt` or via command line:

```bash
python main.py --project 1
```

### Project Config Structure

Each `config/project_X.json` defines:

```json
{
  "project_id": 1,
  "name": "Project Name",
  "hardware": {
    "com_port": "COM4",
    "slave_ids": [1, 2],
    "motors_per_driver": [1, 2],
    "has_limit_switches": [true, false],
    "has_leds": [false, true]
  },
  "video": {
    "file": "path/to/video.mp4",
    "framerate": 30,
    "timecode_offset": 0
  },
  "mexe": {
    "files": [
      "path/to/operation_data_1.mexe",
      "path/to/operation_data_2.mexe"
    ]
  },
  "timing": {
    "sync_mode": "timecode",  // "timecode" or "sequence"
    "control_points": [
      {"timecode": "00:00:05:00", "action": "start_mexe", "motor_id": 0},
      {"timecode": "00:00:10:00", "action": "stop", "motor_id": 0}
    ]
  }
}
```

## Operation Flow

1. **Initialization**
   - Load project config
   - Initialize motor drivers (Modbus connection)
   - Load MEXE operation data
   - Prepare video player

2. **Synchronization**
   - Start video playback
   - Monitor video timecode
   - Trigger MEXE operations at defined control points
   - Execute intermediate commands (start/stop/pause)

3. **Execution Modes**
   - **Timecode Mode**: Actions triggered by video timecode
   - **Sequence Mode**: Actions triggered by sequential events

## Key Features

### Motor Control
- Direct position/velocity control via Modbus
- MEXE operation data execution
- Real-time monitoring (position, velocity, alarms)
- Limit checking and safety bounds
- Multi-motor coordination

### Video Integration
- HDMI output for synchronized playback
- Timecode tracking
- Frame-accurate triggering
- Video start/stop control

### I/O Management
- Limit switch monitoring
- LED indicator control
- Emergency stop handling
- Status feedback

## Current Implementation Status

### Completed
- [x] Basic motor control (oriental_az.py)
- [x] Register definitions (az_define.py)
- [x] Modbus RTU communication
- [x] Direct operation data (position, velocity)
- [x] Alarm monitoring and reset

### In Progress
- [ ] Config-based project selection
- [ ] Video player integration
- [ ] Timecode synchronization system
- [ ] MEXE parser/executor
- [ ] Multi-motor coordination
- [ ] Project-specific implementations (1-9)

### Planned
- [ ] Limit switch integration
- [ ] LED control
- [ ] Web-based monitoring UI
- [ ] Logging and diagnostics
- [ ] Auto-recovery from errors

## Development Guidelines

### Adding a New Project

1. Create `config/project_X.json` with hardware specs
2. Create `projects/project_X.py` inheriting from `BaseProject`
3. Implement project-specific timing logic
4. Test independently before integration

### Code Organization

- **Core modules**: Hardware-agnostic, reusable
- **Project modules**: Project-specific logic only
- **Config files**: All hardware specs and timing data
- **MEXE files**: Motor movement definitions (external)

### Safety Considerations

- Always set appropriate velocity/acceleration limits
- Implement soft limits in config
- Monitor limit switches in real-time
- Handle Modbus communication errors gracefully
- Emergency stop should kill all motor motion

## Dependencies

```
pymodbus>=3.0.0
pynput
python-osc
numpy
opencv-python  # For video playback
python-timecode  # For SMPTE timecode handling
```

## Usage Examples

### Basic Operation

```bash
# Run project 1
python main.py --project 1

# Run with debug logging
python main.py --project 2 --debug

# Dry-run mode (no actual motor movement)
python main.py --project 3 --dry-run
```

### Keyboard Controls (Development Mode)

- `a`: Test movement preset 1
- `b`: Test movement preset 2
- `c`: Stop motion
- `p`: Execute P-Preset (position reset)
- `r`: Reset alarm
- `t`: Read current position
- `ESC`: Exit program

## Troubleshooting

### Motor Not Moving
1. Check Modbus connection (COM port, baud rate)
2. Verify driver power and alarm status
3. Confirm slave ID matches DIP switch settings
4. Check position limits

### Timecode Sync Issues
1. Verify video framerate matches config
2. Check timecode offset settings
3. Monitor system clock drift
4. Ensure adequate CPU performance

### Communication Errors
1. Check RS-485 wiring and termination
2. Verify baudrate settings on driver
3. Test with single motor first
4. Check for electrical interference

## License

Internal project - Murata

## Contact

For questions or issues, contact the development team.
