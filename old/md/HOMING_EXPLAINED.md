# How Homing Works - Complete Explanation

## Overview

This document explains exactly what happens when the system performs motor homing.

---

## Homing Command Flow

### **Step-by-Step Trace Through Code**

```
1. motor_controller.initialize()
   └─> motor_controller.py:91-123

2. Check if homing needed
   └─> home_end_status = driver.is_home_complete()
   └─> needs_homing = homing_required or not home_end_status

3. If needs homing:
   └─> await driver.start_homing(timeout=100)
       └─> motor_driver.py:45-53

4. driver.start_homing() calls:
   └─> self.client.start_homing_async(timeout=timeout, slave_id=self.slave_id)
       └─> oriental_cvd.py:433-454

5. oriental_cvd.start_homing_async() sends:
   └─> self.send_input_signal(signal=InputSignal.HOME, slave_id=slave_id)
       └─> oriental_cvd.py:266-287
```

---

## What Command is Sent to Motor?

### **InputSignal.HOME Definition** (cvd_define.py:332)

```python
class InputSignal(IntFlag):
    HOME = 1 << 4   # Bit 4 = 0x0010 = 0b00010000
```

### **Binary Breakdown:**

| Bit Position | 15-5 | 4 | 3 | 2 | 1 | 0 |
|--------------|------|---|---|---|---|---|
| Binary Value | 0000 0000 000**1** 0000 |
| Hex Value    | **0x0010** |
| Decimal      | **16** |

**What this means:**
- Bit 4 is set to `1`
- All other bits are `0`
- This is the HOME signal

---

## How the Signal is Written to Motor

### **send_input_signal() Method** (oriental_cvd.py:266-287)

```python
def send_input_signal(self, signal: InputSignal, slave_id=1) -> bool:
    """
    Write to IORegister.DRIVER_INPUT_COMMAND lower register (0x007D)
    """
    address = IORegister.DRIVER_INPUT_COMMAND + 1  # 0x007D
    value = int(signal)  # Convert InputSignal.HOME to integer (0x0010)

    # Write to Modbus register
    result = self.client.write_register(
        address=address,      # 0x007D (Driver Input Command lower register)
        value=value,          # 0x0010 (HOME bit set)
        device_id=slave_id    # Modbus slave ID (default 1)
    )

    return not result.isError()
```

### **Modbus Command Details:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| Function Code | FC06 (Write Single Register) | Modbus function to write one register |
| Register Address | 0x007D | Driver Input Command (lower 16 bits) |
| Value | 0x0010 | HOME signal (bit 4 = 1) |
| Slave ID | 1 | Motor Modbus address |

**Actual Modbus Packet:**
```
[Slave ID][Function][Address High][Address Low][Value High][Value Low][CRC]
   0x01      0x06       0x00          0x7D        0x00        0x10    [CRC]
```

---

## What Happens During Homing

### **1. Send HOME Signal**
```python
self.send_input_signal(signal=InputSignal.HOME, slave_id=slave_id)
# Writes 0x0010 to register 0x007D
```

### **2. Monitor Homing Progress** (oriental_cvd.py:404-427)

```python
async def _wait_homing_complete(self, slave_id=1):
    while True:
        # Check HOME_END flag
        b = self.checkHomeEndFlag(slave_id=slave_id)

        # Read current position
        position = self.read_monitor(MonitorCommand.COMMAND_POSITION, slave_id=slave_id)

        # Read status flags
        status = self.read_output_signal(slave_id=slave_id)
        ready_flag = (status & OutputSignal.READY) != 0
        move_flag = (status & OutputSignal.MOVE) != 0

        # Print progress
        print(f"Homing: {elapsed:.1f}s | Pos: {position:8d} | READY: {ready_flag} | MOVE: {move_flag} | HOME_END: {b}")

        # If HOME_END flag is set, homing is complete
        if b:
            break

        await asyncio.sleep(0.2)  # Check every 200ms
```

### **3. Completion Detection**

The system monitors **OutputSignal.HOME_END** flag:

```python
class OutputSignal(IntFlag):
    HOME_END = 1 << 4   # Bit 4 of output status register (0x007F)
```

**Read from register 0x007F (Driver Output Status):**
- When homing starts: HOME_END = 0 (False)
- When homing complete: HOME_END = 1 (True)

### **4. Clear HOME Signal**

```python
# After homing complete, turn off HOME signal
self.send_input_signal(signal=InputSignal.OFF, slave_id=slave_id)
# Writes 0x0000 to register 0x007D
```

---

## Register Map Summary

| Register | Address | Purpose | Read/Write |
|----------|---------|---------|------------|
| DRIVER_INPUT_COMMAND (lower) | 0x007D | Send commands (HOME, START, STOP, etc.) | Write |
| DRIVER_OUTPUT_STATUS (lower) | 0x007F | Read status flags (HOME_END, MOVE, READY, etc.) | Read |
| COMMAND_POSITION | 0x00C6 | Current motor position | Read |

---

## Example Homing Sequence Log

```
[INFO] Starting automatic homing to position 0...
[INFO] Homing started...
Homing: 0.2s | Pos:        0 | READY: True  | MOVE: False | HOME_END: False
Homing: 0.4s | Pos:     -120 | READY: False | MOVE: True  | HOME_END: False
Homing: 0.6s | Pos:     -580 | READY: False | MOVE: True  | HOME_END: False
Homing: 0.8s | Pos:    -1240 | READY: False | MOVE: True  | HOME_END: False
Homing: 1.0s | Pos:    -2100 | READY: False | MOVE: True  | HOME_END: False
...
Homing: 3.8s | Pos:   -15600 | READY: False | MOVE: True  | HOME_END: False
Homing: 4.0s | Pos:        0 | READY: True  | MOVE: False | HOME_END: True ✓
[INFO] Homing completed successfully. Final position: 0
[INFO] ✓ Homing complete - Motor READY at position: 0
```

**What's happening:**
1. Motor starts moving (MOVE=True, READY=False)
2. Position becomes negative as motor searches for home sensor
3. When home sensor triggered, motor returns to position 0
4. HOME_END flag becomes True
5. Motor stops (MOVE=False, READY=True)

---

## Why Homing is Important

### **Without Homing:**
- Motor doesn't know its absolute position
- HOME_END flag = False
- Cannot perform accurate position moves
- Risk of position drift over time

### **After Homing:**
- Motor knows position 0 (reference point)
- HOME_END flag = True
- All position moves are accurate
- System can detect if motor was power-cycled

### **Auto-Homing Logic:**
```python
# Check if motor needs homing
home_end_status = self.driver.is_home_complete()  # Read HOME_END flag
needs_homing = self.homing_required or not home_end_status

if not home_end_status:
    logger.info("⚠ Motor HOME_END flag is False - motor needs homing")
    # Automatically perform homing
```

This ensures:
- Motor always has correct position reference
- System recovers automatically from power cycles
- Position accuracy is maintained

---

## Summary

**Homing Command:**
```
Command: InputSignal.HOME (0x0010, bit 4)
Register: 0x007D (DRIVER_INPUT_COMMAND lower)
Method: Modbus FC06 (Write Single Register)
```

**Completion Detection:**
```
Status: OutputSignal.HOME_END (bit 4)
Register: 0x007F (DRIVER_OUTPUT_STATUS lower)
Method: Modbus FC03 (Read Holding Registers)
```

**Result:**
- Motor moves to home sensor
- Returns to position 0
- Sets HOME_END flag = True
- System is ready for accurate positioning
