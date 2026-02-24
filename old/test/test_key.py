#!/usr/bin/env python3
"""
Keyboard control test for CVD motor
Press 'v' to start/stop operation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymodbus.client import ModbusSerialClient
import time
import readchar

COM_PORT = '/dev/tty.usbserial-FT78LMAE'  # Raspberry Pi USB port (use /dev/cu.usbserial-FT78LMAE on Mac, Raspi: /dev/ttyUSB0)
SLAVE_ID = 1

print("=" * 70)
print("CVD Motor Keyboard Control")
print("=" * 70)
print(f"Port: {COM_PORT}")
print(f"Slave ID: {SLAVE_ID}")
print()

# Connect
client = ModbusSerialClient(
    port=COM_PORT,
    baudrate=230400,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1.0
)

if not client.connect():
    print("❌ Failed to connect")
    sys.exit(1)

print("✓ Connected")
print()
print("Controls:")
print("  'v' - Start/Stop motor (toggle)")
print("  'q' - Quit")
print()
print("Waiting for commands...")
print()

is_running = False

try:
    while True:
        # Read keyboard
        key = readchar.readchar()

        if key == 'v':
            # Toggle START/STOP
            is_running = not is_running

            if is_running:
                # START
                print("\n>>> START - Sending operation 0...")

                # Method: Write START bit directly
                result = client.write_register(address=0x007D, value=0x0008, device_id=SLAVE_ID)

                if result.isError():
                    print(f"❌ Error: {result}")
                    is_running = False
                else:
                    print("✓ START signal sent - motor running")
                    print("(Press 'v' again to stop)")

            else:
                # STOP
                print("\n>>> STOP - Stopping motor...")

                result = client.write_register(address=0x007D, value=0x0020, device_id=SLAVE_ID)

                if result.isError():
                    print(f"❌ Error: {result}")
                else:
                    print("✓ STOP signal sent - motor stopped")
                    time.sleep(0.2)

                    # Clear command
                    client.write_register(address=0x007D, value=0x0000, device_id=SLAVE_ID)

        elif key == 'q':
            print("\n\nQuitting...")
            break

except KeyboardInterrupt:
    print("\n\nCtrl+C detected")

finally:
    # Stop motor and cleanup
    print("Sending STOP command...")
    client.write_register(address=0x007D, value=0x0020, device_id=SLAVE_ID)
    time.sleep(0.1)
    client.write_register(address=0x007D, value=0x0000, device_id=SLAVE_ID)
    client.close()
    print("✓ Closed")
