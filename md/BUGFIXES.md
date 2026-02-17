# Bug Fixes - Motor Control Issues

## Issue 1: MOVE Signal Not Reading Properly ✅ FIXED

### Problem
The MOVE flag and other motor status signals were not being read correctly due to a parameter naming bug in `oriental_cvd.py`.

### Root Cause
Functions in `oriental_cvd.py` used `slave_id` as the parameter name, but when calling other methods, they incorrectly used `device_id=slave_id` instead of `slave_id=slave_id`.

**Example of the bug:**
```python
# WRONG - Before fix
def checkReadyFlag(self, slave_id=1):
    status = self.read_output_signal(device_id=slave_id)  # ❌ Wrong parameter name

# CORRECT - After fix
def checkReadyFlag(self, slave_id=1):
    status = self.read_output_signal(slave_id=slave_id)  # ✅ Correct parameter name
```

### Files Fixed
- `drivers/oriental_cvd.py`
  - `checkReadyFlag()` - Line 389
  - `checkHomeEndFlag()` - Line 397
  - `_wait_homing_complete()` - Lines 408, 412, 417
  - `start_homing_async()` - Lines 435, 438, 441, 446, 450
  - `start_continous_macro()` - Line 306
  - `send_start_signal()` - Line 309
  - `send_stop_signal()` - Line 312
  - `send_signal_reset()` - Line 315
  - `set_operation_data()` - Line 342

### Impact
Now the MOVE signal, READY signal, HOME_END signal, and all other motor status flags are read correctly.

---

## Issue 2: No Auto-Homing When Motor Powers On ✅ FIXED

### Problem
When a motor is powered off and then powered back on (while main.py is still running), the motor would not automatically re-home itself. This caused position errors.

### Root Cause
The system only checked the `homing_required` config setting during boot, but didn't detect when a motor lost its position due to power cycling.

### Solution
Modified `motor_controller.py` to check the motor's **HOME_END flag** after connecting:
- If HOME_END flag is False → Motor needs homing (lost position)
- If homing_required config is True → Always home on boot
- Otherwise → Motor is already homed, skip homing

**New Logic:**
```python
# Check motor state
home_end_status = self.driver.is_home_complete()
needs_homing = self.homing_required or not home_end_status

if needs_homing:
    if not home_end_status:
        logger.info("⚠ Motor HOME_END flag is False - motor needs homing")
    # Perform homing...
```

### Files Modified
- `services/motor_controller.py` - `initialize()` method (lines 91-123)

### Impact
Motors now automatically re-home when:
1. System boots up (if homing_required = true)
2. Motor is powered off/on while main.py is running
3. Motor loses position for any reason

---

## Issue 3: C Key Reset/Homing Removed ✅ FIXED

### Problem
The C key was triggering reset/homing operations, which is no longer needed in the new architecture.

### Solution
Removed C key handler from `key.py`:
- Removed `send_reset_command()` function
- Removed C key handler from keyboard loop
- Updated documentation to remove C key references
- Kept only: V key (start/stop) and Ctrl (clear alarm)

### Files Modified
- `key.py`
  - Removed C key documentation (line 11)
  - Removed `send_reset_command()` function
  - Removed C key handler from keyboard loop
  - Updated keyboard controls message

### Impact
Simplified keyboard controls:
- **V key**: Start/Stop toggle only
- **Ctrl+any**: Clear alarm
- **Ctrl+C**: Exit program

No more accidental homing operations from C key.

---

## Testing Checklist

### Test MOVE Signal Reading
```bash
# On Station 05
python main.py

# Expected log output:
# - MOVE: True (when motor is moving)
# - MOVE: False (when motor is stopped)
# - HOME_END: True (after homing complete)
```

### Test Auto-Homing on Power-Up
```bash
# 1. Start main.py with motor powered on
python main.py
# Expected: Motor homes (if homing_required or HOME_END=False)

# 2. While main.py is running, power off the motor
# 3. Power on the motor again
# Expected: On next operation start, system detects HOME_END=False and re-homes
```

### Test Simplified Keyboard Controls
```bash
# On master Pi
python key.py

# Press V → Should start all stations
# Press V again → Should stop all stations
# Press Ctrl+any → Should clear alarms
# Press C → Should do nothing (removed)
```

---

## Summary

All three critical issues have been resolved:

1. ✅ **MOVE signal bug fixed** - Parameter naming corrected
2. ✅ **Auto-homing on power-up** - Detects motor state via HOME_END flag
3. ✅ **C key removed** - Simplified keyboard controls

The system is now more robust and will automatically recover from motor power cycles.
