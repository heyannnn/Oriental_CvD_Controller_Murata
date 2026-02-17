# Operation Completion Detection - Changed to MOVE Flag

## What Changed

**Before:** System detected operation completion by monitoring `RUNNING_DATA_NO` register (waiting for value -1)

**After:** System detects operation completion when `MOVE` flag goes False (motor stops moving)

---

## Why This Change?

### **Better for Video Synchronization**

The new method is more precise for syncing with video playback because:
- You know **exactly when the motor stops moving**
- MOVE flag transitions at the moment motion ends
- Perfect for triggering video events
- No delay between motion stop and detection

### **Simpler and More Reliable**

- MOVE flag is a direct hardware signal
- No need to parse operation numbers
- Works consistently for all operation types
- Easier to debug (just watch MOVE flag)

---

## New Completion Detection Logic

### **Code Changes** (motor_controller.py:166-230)

```python
async def _monitor_operation(self):
    """
    Monitor operation until completion.
    Detects completion when MOVE flag goes False (motor stops moving).
    """
    operation_started = False
    was_moving = False

    while True:
        # Read motor status
        moving = self.driver.is_moving()
        position = self.driver.read_position()

        # Check if operation started (motor started moving)
        if not operation_started and moving:
            operation_started = True
            was_moving = True
            logger.info("✓ Operation STARTED - Motor is moving (MOVE=True)")

        # Track if motor was moving
        if moving:
            was_moving = True

        # Detect completion: MOVE flag goes False after motor was moving
        if operation_started and was_moving and not moving:
            logger.info("✓ Operation FINISHED - Motor stopped (MOVE=False)")
            self.state = MotorState.FINISHED

            # Call callback
            if self._on_finished:
                self._on_finished()

            # Return to ready
            self.state = MotorState.READY
            break

        await asyncio.sleep(0.1)
```

### **State Transitions:**

```
1. Operation starts
   ├─ MOVE flag: False → True
   └─ Log: "Operation STARTED - Motor is moving"

2. Motor moves
   ├─ MOVE flag: True
   └─ Position changes
   └─ Log every 0.5s: "Op 0: 2.5s | Pos: 1234 | MOVE: True"

3. Operation completes
   ├─ MOVE flag: True → False
   └─ Log: "Operation FINISHED - Motor stopped (MOVE=False)"
   └─ Call on_motor_finished() callback

4. Wait delay (3 seconds)
   └─ sequence_manager._loop_next_cycle()
   └─ Log: "Waiting 3.0s before next cycle..."

5. Restart operation
   └─ Start operation 0 again
   └─ Back to step 1
```

---

## How MOVE Flag Works

### **OutputSignal.MOVE Definition** (cvd_define.py:377)

```python
class OutputSignal(IntFlag):
    MOVE = 1 << 13   # Bit 13 of output status register
```

### **Reading MOVE Flag:**

```python
# Read from register 0x007F (Driver Output Status)
status = self.client.read_holding_registers(address=0x007F, count=1, device_id=slave_id)

# Check bit 13
moving = (status & OutputSignal.MOVE) != 0

# Returns:
# True  - Motor is currently moving
# False - Motor is stopped
```

### **MOVE Flag Timing:**

| Motor State | MOVE Flag | Description |
|-------------|-----------|-------------|
| At rest | False | Motor not moving |
| START signal sent | False → True | Motor begins acceleration |
| Moving | True | Motor in motion |
| Reaches target | True → False | Motor decelerates and stops |
| Stopped | False | Motor at target position |

---

## Loop Delay Configuration

After operation completes, the system waits before restarting.

### **Configuration** (config/all_stations.json:25)

```json
{
  "loop_delay_sec": 3.0
}
```

### **Implementation** (sequence_manager.py:183-212)

```python
async def _loop_next_cycle(self):
    # Wait for configured delay
    logger.info(f"Waiting {self.loop_delay_sec}s before next cycle...")

    for remaining in range(int(self.loop_delay_sec), 0, -1):
        logger.info(f"  {remaining}s...")
        await asyncio.sleep(1.0)

    # Restart operation
    self.cycle_count += 1
    logger.info(f"=== Starting cycle {self.cycle_count} ===")
    self.motor_controller.start_operation(op_no=0)
```

**You can change the delay by editing `loop_delay_sec` in config.**

---

## Example Operation Log

```
[INFO] === Starting cycle 1 ===
[INFO] Starting MEXE operation 0 from position: 0
[INFO] Monitoring operation 0...
[INFO] ✓ Operation 0 STARTED - Motor is moving (MOVE=True)
[INFO] Op 0: 0.5s | Pos:      120 | MOVE: True  | READY: False | IN_POS: False
[INFO] Op 0: 1.0s | Pos:      580 | MOVE: True  | READY: False | IN_POS: False
[INFO] Op 0: 1.5s | Pos:     1240 | MOVE: True  | READY: False | IN_POS: False
[INFO] Op 0: 2.0s | Pos:     2100 | MOVE: True  | READY: False | IN_POS: False
[INFO] Op 0: 2.5s | Pos:     3000 | MOVE: True  | READY: False | IN_POS: False
[INFO] Op 0: 3.0s | Pos:     3000 | MOVE: False | READY: True  | IN_POS: True
[INFO] ✓ Operation 0 FINISHED - Motor stopped (MOVE=False)
[INFO]   Final position: 3000 | Duration: 3.1s
[INFO] Calling on_finished callback
[INFO] === OPERATION FINISHED ===
[INFO] Waiting 3.0s before next cycle...
[INFO]   3s...
[INFO]   2s...
[INFO]   1s...
[INFO] === Starting cycle 2 ===
[INFO] Starting MEXE operation 0 from position: 3000
...
```

---

## Which Stations Use This?

### **Stations with Homing (5, 6, 7, 8, 9):**
- ✅ Track operation completion via MOVE flag
- ✅ Loop automatically with delay
- ✅ Perfect for video synchronization

### **Stations without Homing (2, 3, 4, 10):**
- ✅ Also track operation completion via MOVE flag
- ✅ Loop automatically with delay
- Note: No home sensor, but MOVE flag still works

**The MOVE flag works on ALL stations**, regardless of homing configuration!

---

## Benefits Summary

| Aspect | Old Method (RUNNING_DATA_NO) | New Method (MOVE Flag) |
|--------|------------------------------|------------------------|
| **Precision** | Register polling | Direct hardware signal |
| **Video Sync** | Less precise | Exact motion end detection |
| **Simplicity** | Parse operation number | Simple True/False |
| **Reliability** | Register may not update | Hardware signal always accurate |
| **Debug** | Hard to trace | Easy to observe |

---

## Testing

### **Verify MOVE Flag Detection:**

```bash
# Run main.py on Station 05
python main.py

# Press V on master to start
# Watch logs for:
# - "Operation STARTED - Motor is moving (MOVE=True)"
# - "MOVE: True" during motion
# - "Operation FINISHED - Motor stopped (MOVE=False)"
# - "Waiting 3.0s before next cycle..."
# - Automatic restart
```

### **Change Loop Delay:**

```json
// In config/all_stations.json
{
  "loop_delay_sec": 5.0  // Change from 3.0 to 5.0 seconds
}

// Restart main.py to apply
```

---

## Summary

**Operation Completion Detection:**
- **Old:** Wait for RUNNING_DATA_NO == -1
- **New:** Wait for MOVE flag False (motor stopped)

**Why Better:**
- Exact motion end detection
- Perfect for video sync
- Simpler and more reliable
- Works on all stations

**Loop Behavior:**
1. Start operation 0
2. Detect MOVE = True (started)
3. Detect MOVE = False (finished)
4. Wait 3 seconds (configurable)
5. Restart operation 0
6. Repeat until V key pressed again
