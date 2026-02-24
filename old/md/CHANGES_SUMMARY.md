# Recent Changes Summary

## Change 1: Added RUNNING_OP to Monitoring Logs ✅

### What Changed
Added `RUNNING_OP` (RUNNING_DATA_NO register value) back to the monitoring logs for debugging purposes.

### Why
- Even though we don't use RUNNING_OP to detect completion anymore (we use MOVE flag)
- It's still useful for monitoring and debugging
- Helps track which operation the motor thinks it's executing

### Files Modified
- `services/motor_controller.py` - `_monitor_operation()` method (line ~185)

### New Log Format
**Before:**
```
Op 0: 8.9s | Pos: -18851 | MOVE: True | READY: False | IN_POS: False
```

**After:**
```
Op 0: 8.9s | Pos: -18851 | RUNNING_OP: 0 | MOVE: True | IN_POS: False
```

### RUNNING_OP Values
| Value | Meaning |
|-------|---------|
| 0-255 | Currently executing operation number |
| -1 | No operation running (motor idle) |
| None | Error reading register |

---

## Change 2: Return-to-Zero Completion Callback ✅

### What Changed
Added detection and callback when return-to-zero motion completes after pressing V key to stop.

### Why
For stations with `return_to_zero_on_stop: true` (stations 5, 6, 7, 8, 9):
- Previously: Motor would start returning to position 0, but no notification when complete
- Now: System detects when motor reaches position 0 and triggers callback
- Perfect for video synchronization (know when motor is back at home)

### How It Works

#### **When You Press V to Stop:**

```
1. V key pressed (while running)
   ↓
2. Send STOP signal to motor
   ↓
3. Motor stops current operation
   ↓
4. Check: return_to_zero_on_stop = true?
   ├─ Yes (Stations 5,6,7,8,9):
   │  ├─ Send return_to_zero command
   │  ├─ Start monitoring MOVE flag
   │  └─ Wait for MOVE = False
   │      ↓
   │  When MOVE = False:
   │      ├─ Log: "✓ Return to zero COMPLETE"
   │      ├─ Call callback: on_return_to_zero_complete()
   │      └─ Send video command: "returned_to_zero"
   │
   └─ No (Stations 2,3,4,10):
      └─ Just stop at current position
```

### Files Modified
1. **`services/motor_controller.py`**
   - Added `_on_return_to_zero_complete` callback attribute
   - Added `_monitor_return_to_zero()` async method
   - Modified `stop()` method to start monitoring

2. **`services/sequence_manager.py`**
   - Added `on_return_to_zero_complete()` callback handler
   - Sends video command "returned_to_zero"

3. **`main.py`**
   - Wired callback: `motor_controller._on_return_to_zero_complete = sequence_manager.on_return_to_zero_complete`

### Example Logs

**Station 5 (return_to_zero_on_stop = true):**
```
[INFO] === STOP PRESSED ===
[INFO] Looping mode disabled
[INFO] Stop requested
[INFO] Sending STOP signal...
[INFO] Motor stopped successfully
[INFO] Returning to position 0 via direct operation...
[INFO] Return to zero monitoring started
[INFO] Monitoring return to zero...
[INFO] Return to zero started - Motor is moving
[INFO] Return to zero: 0.5s | Pos:     2800 | MOVE: True
[INFO] Return to zero: 1.0s | Pos:     1600 | MOVE: True
[INFO] Return to zero: 1.5s | Pos:      800 | MOVE: True
[INFO] Return to zero: 2.0s | Pos:      200 | MOVE: True
[INFO] Return to zero: 2.5s | Pos:        0 | MOVE: False
[INFO] ✓ Return to zero COMPLETE - Motor at position: 0 (2.6s)
[INFO] Calling on_return_to_zero_complete callback
[INFO] === RETURN TO ZERO COMPLETE ===
[INFO] Motor has returned to home position (0)
[INFO] Sent video command: /video/returned_to_zero
```

**Station 2 (return_to_zero_on_stop = false):**
```
[INFO] === STOP PRESSED ===
[INFO] Looping mode disabled
[INFO] Stop requested
[INFO] Sending STOP signal...
[INFO] Motor stopped successfully
[INFO] System in standby - motors at position 0 or stopped
```

---

## Configuration Reference

### Stations with Return-to-Zero
These stations return to position 0 after stop and trigger the callback:

| Station | Config Setting | Behavior on Stop |
|---------|----------------|------------------|
| 05 | `return_to_zero_on_stop: true` | Returns to 0, triggers callback |
| 06 | `return_to_zero_on_stop: true` | Returns to 0, triggers callback |
| 07 | `return_to_zero_on_stop: true` | Returns to 0, triggers callback |
| 08 | `return_to_zero_on_stop: true` | Returns to 0, triggers callback |
| 09 | `return_to_zero_on_stop: true` | Returns to 0, triggers callback |

### Stations without Return-to-Zero
These stations stop at current position, no callback:

| Station | Config Setting | Behavior on Stop |
|---------|----------------|------------------|
| 02 | `return_to_zero_on_stop: false` | Stops at current position |
| 03 | `return_to_zero_on_stop: false` | Stops at current position |
| 04 | `return_to_zero_on_stop: false` | Stops at current position |
| 10 | `return_to_zero_on_stop: false` | Stops at current position |

---

## Video Synchronization Integration

### OSC Commands Sent to Video Player

The system now sends these video sync commands:

| Command | When | Stations |
|---------|------|----------|
| `ready` | After homing complete | All |
| `standby` | When V key pressed (start) | All |
| `finished` | When operation completes (MOVE=False) | All |
| `stop` | When V key pressed (stop) | All |
| **`returned_to_zero`** | **When return-to-zero completes** | **5,6,7,8,9** |

### Video Player Integration Example

Your video player can listen for these OSC messages:

```python
# Pseudo-code for video player
@osc_handler("/video/returned_to_zero")
def on_motor_returned_to_zero():
    print("Motor is back at home position")
    # Trigger video action, reset video to start, etc.
    video.reset()
    video.show_idle_screen()
```

---

## Testing

### Test Return-to-Zero Callback (Station 05)

```bash
# 1. Start main.py on Station 05
python main.py

# Expected: Homing happens, motor at position 0

# 2. Start key.py on master
python key.py

# 3. Press V to start operation
# Expected: Motor runs operation 0, loops

# 4. Press V again to stop
# Expected logs:
# - "STOP PRESSED"
# - "Returning to position 0 via direct operation..."
# - "Return to zero: X.Xs | Pos: XXXX | MOVE: True"
# - "✓ Return to zero COMPLETE - Motor at position: 0"
# - "RETURN TO ZERO COMPLETE"
# - "Sent video command: /video/returned_to_zero"
```

### Test RUNNING_OP in Logs

```bash
# Start any station
python main.py

# Press V to start
# Watch logs for:
# Op 0: 1.0s | Pos: 580 | RUNNING_OP: 0 | MOVE: True | IN_POS: False
#                        ^^^^^^^^^^^^^^^^
#                        This is the new addition
```

---

## Summary

**Change 1: RUNNING_OP in logs**
- ✅ Added for debugging/monitoring
- ✅ Shows which operation motor is executing
- ✅ Not used for completion detection (MOVE flag is used)

**Change 2: Return-to-zero callback**
- ✅ Detects when motor finishes returning to position 0
- ✅ Triggers callback for video synchronization
- ✅ Only active on stations 5, 6, 7, 8, 9
- ✅ Logs completion message
- ✅ Sends OSC command to video player

Both changes improve monitoring, debugging, and video synchronization capabilities!
