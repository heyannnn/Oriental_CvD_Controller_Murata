# System Architecture - State Machine Flow

## Overview

Simplified state-machine based control system. **MEXE handles all motion timing**. The Pi is just a trigger controller + OSC broadcaster.

## Components

### 1. MotorDriver (Low-level)
- Thin wrapper around `oriental_cvd.py`
- Basic commands: `start_homing()`, `start_operation()`, `stop()`, `is_moving()`, `is_ready()`
- No state management

### 2. MotorController (State Machine)
- Per-station motor state management
- States: `DISCONNECTED → HOMING → READY → RUNNING → FINISHED`
- Auto-homes on boot
- Monitors operation completion
- Callbacks: `on_ready`, `on_finished`, `on_error`

### 3. SequenceManager (Main Coordinator)
- System-level state machine
- States: `BOOT → HOMING → READY → STANDBY → RUNNING → FINISHED`
- Coordinates MotorController + VideoPlayer (OSC) + Network
- Handles keyboard commands
- Broadcasts to other stations

### 4. KeyboardHandler (Station 2 only)
- 3 GPIO buttons: START, STOP, RESET
- Wired to SequenceManager

### 5. NetworkSync (OSC)
- Broadcasts `/start`, `/stop`, `/reset` to all stations
- Sends `/video/ready`, `/video/start`, etc. to video player program

---

## State Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SYSTEM BOOT                                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  State: HOMING                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ MotorController.initialize()                                  │  │
│  │   → MotorDriver.start_homing()                                │  │
│  │   → Monitor until HOME_END flag set                           │  │
│  │   → Callback: on_motor_ready()                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  State: READY                                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ SequenceManager.on_motor_ready()                              │  │
│  │   → Send OSC: /video/ready                                    │  │
│  │   → Log: "System ready - waiting for START"                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ⏸️  WAITING FOR KEYBOARD INPUT                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                        ┌──────────┐
                        │  START   │  ← Keyboard button pressed
                        │  PRESSED │
                        └──────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  State: STANDBY                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ SequenceManager.on_start_pressed()                            │  │
│  │   → Send OSC: /video/standby                                  │  │
│  │   → Broadcast OSC: /start (to all stations)                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  State: RUNNING                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ MotorController.start_operation(op_no=0)                      │  │
│  │   → MotorDriver.start_operation(0)                            │  │
│  │   → Monitor: is_moving() every 100ms                          │  │
│  │   → Wait until MOVE flag clears                               │  │
│  │   → Callback: on_motor_finished()                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  State: FINISHED                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ SequenceManager.on_motor_finished()                           │  │
│  │   → Send OSC: /video/finished                                 │  │
│  │   → Return to READY state                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                         Back to READY
```

---

## Emergency Actions

### STOP Button
```
ANY STATE → STOPPED
  → MotorController.stop()
  → Send OSC: /video/stop
  → Broadcast OSC: /stop
```

### RESET Button
```
ANY STATE → HOMING
  → MotorController.stop()
  → Send OSC: /video/reset
  → Broadcast OSC: /reset
  → MotorController.reset_to_home()
  → (returns to READY when complete)
```

---

## OSC Communication

### Station-to-Station (Station 2 → All)
- `/start` - Start all operations
- `/stop` - Emergency stop all
- `/reset` - Reset all to home

### Pi → Video Player Program
- `/video/ready` - Motors homed and ready
- `/video/standby` - Prepare to play
- `/video/start` - Begin playback (not used in new flow)
- `/video/stop` - Stop playback
- `/video/finished` - Operation complete
- `/video/error` - Error occurred

---

## File Structure (New)

```
services/
├── motor_driver.py          # Low-level Modbus wrapper
├── motor_controller.py      # Motor state machine
├── sequence_manager.py      # Main coordinator
├── network_sync.py          # OSC sender/receiver
└── keyboard_handler.py      # GPIO buttons (station 2 only)

main_station2.py             # Station 2 entry point (with keyboard)
tests/test_station2_nogpio.py  # Mac test version (keyboard input)
```

---

## Key Differences from Old Architecture

| Old (Timecode) | New (State Machine) |
|---|---|
| Cue table with timestamps | No cue table |
| `sequence_controller.py` ticks every 100ms | `sequence_manager.py` state transitions |
| Video playback drives timing | MEXE drives motion timing |
| `motor_service.py` (multi-motor) | `motor_controller.py` (state machine) |
| Complex service wiring | Simple callbacks |
| `main.py` 200+ lines | `main_station2.py` 120 lines |

---

## Testing Flow

### 1. Mac Development (without hardware)
```bash
# Edit COM_PORT in test file
python tests/test_station2_nogpio.py

# Press keys:
# 's' = START
# 't' = STOP
# 'r' = RESET
# 'q' = QUIT
```

### 2. Raspberry Pi Deployment
```bash
# Deploy code
ssh user@pi-controller-02.local
cd ~/Oriental_CvD_Controller_Murata
git pull

# Run with GPIO keyboard
python main_station2.py

# Or install as systemd service
sudo systemctl start oriental-controller
```

### 3. Expected Console Output
```
=======================================================================
Oriental Motor CVD Controller - Station 2 (Master)
=======================================================================

[1/4] Initializing network sync...
✓ OSC listener started on port 9000

[2/4] Initializing motor controller...

[3/4] Initializing sequence manager...

[4/4] Initializing keyboard (3-key GPIO)...
✓ Keyboard handler initialized

=======================================================================
SYSTEM BOOT - Starting Initialization
=======================================================================
Starting motor homing...
Homing complete - motor READY
=== MOTOR READY ===
Sent video command: /video/ready

=======================================================================
System Ready - Waiting for Commands
=======================================================================

[User presses START button]

=== START PRESSED ===
Sending STANDBY signal...
Sent video command: /video/standby
Starting motor operation...
=== SYSTEM RUNNING ===
Starting operation 0 (slave_id=1)
Monitoring operation...
Operation 0 finished (5.2s)
=== OPERATION FINISHED ===
Sent video command: /video/finished
System ready for next operation
```

---

## Next Steps

1. ✅ Create simplified architecture
2. ⏳ Test on Mac with motor connected
3. ⏳ Deploy to Pi-02 with GPIO keyboard
4. ⏳ Test full flow: boot → home → ready → start → finish
5. ⏳ Add error handling and recovery
6. ⏳ Deploy to all stations (non-keyboard versions)
