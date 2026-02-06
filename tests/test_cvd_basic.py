#!/usr/bin/env python3
"""
Basic CVD driver test - diagnose communication issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymodbus.client import ModbusSerialClient
import time
from drivers.cvd_define import *

COM_PORT = '/dev/cu.usbserial-FT78LMAE'  # Your port
SLAVE_ID = 1

def test_connection():
    """Test basic Modbus connection"""
    print("=" * 70)
    print("CVD Driver Diagnostic Test")
    print("=" * 70)
    print(f"Port: {COM_PORT}")
    print(f"Slave ID: {SLAVE_ID}")
    print()

    client = ModbusSerialClient(
        port=COM_PORT,
        baudrate=230400,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1.0
    )

    if not client.connect():
        print("❌ Failed to open serial port")
        return

    print("✓ Serial port opened")
    print()

    # Test 1: Read output status (should always work)
    print("[Test 1] Reading output status register (0x007F)...")
    try:
        result = client.read_holding_registers(address=0x007F, count=1, slave=SLAVE_ID)
        if result.isError():
            print(f"  ❌ Error: {result}")
        else:
            status = result.registers[0]
            print(f"  ✓ Success! Status = 0x{status:04X}")
            print(f"    READY: {'YES' if (status & 0x0001) else 'NO'}")
            print(f"    MOVE:  {'YES' if (status & 0x0004) else 'NO'}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    time.sleep(0.5)

    # Test 2: Try writing to input command register (0x007D) - single register
    print("\n[Test 2] Writing to input command register (0x007D)...")
    print("  Sending STOP command (0x0020)...")
    try:
        result = client.write_register(address=0x007D, value=0x0020, slave=SLAVE_ID)
        if result.isError():
            print(f"  ❌ Error: {result}")
        else:
            print(f"  ✓ Success! Write accepted")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    time.sleep(0.5)

    # Test 3: Try the old method - operation number + START in one command
    print("\n[Test 3] Old method - Operation 0 + START combined...")
    print("  Writing 0x0008 (START bit) to 0x007D...")
    try:
        result = client.write_register(address=0x007D, value=0x0008, slave=SLAVE_ID)
        if result.isError():
            print(f"  ❌ Error: {result}")
        else:
            print(f"  ✓ Success! Command sent")
            print("\n  Monitoring for 5 seconds...")

            for i in range(50):
                result = client.read_holding_registers(address=0x007F, count=1, slave=SLAVE_ID)
                if not result.isError():
                    status = result.registers[0]
                    moving = (status & 0x0004) != 0
                    print(f"    [{i/10:.1f}s] {'MOVING' if moving else 'STOPPED'}", end='\r', flush=True)
                    if not moving and i > 10:
                        print("\n  ✓ Motion completed (or never started)")
                        break
                time.sleep(0.1)

            # Send STOP
            client.write_register(address=0x007D, value=0x0020, slave=SLAVE_ID)
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    client.close()
    print("\n\n" + "=" * 70)
    print("Diagnostic complete")
    print("=" * 70)

if __name__ == "__main__":
    test_connection()
