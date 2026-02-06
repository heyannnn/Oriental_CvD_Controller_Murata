#!/usr/bin/env python3
"""
Scan for CVD driver slave ID
Tests all possible slave IDs (0-10) to find which one responds
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymodbus.client import ModbusSerialClient
import time

COM_PORT = '/dev/cu.usbserial-FT78LMAE'  # Your port (use cu. not tty. on Mac)

print("=" * 70)
print("CVD Driver Slave ID Scanner")
print("=" * 70)
print(f"Port: {COM_PORT}")
print()
print("Trying different slave IDs...")
print()

client = ModbusSerialClient(
    port=COM_PORT,
    baudrate=230400,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=0.5  # Shorter timeout for faster scanning
)

if not client.connect():
    print("❌ Failed to open serial port")
    sys.exit(1)

print("✓ Serial port opened")
print()

# Try slave IDs 0-10 (0 is broadcast, 1-10 are common)
for slave_id in range(0, 11):
    sys.stdout.write(f"Testing slave ID {slave_id:2d} ... ")
    sys.stdout.flush()

    try:
        # Try reading output status register (0x007F)
        result = client.read_holding_registers(address=0x007F, count=1, slave=slave_id)

        if not result.isError():
            status = result.registers[0]
            print(f"✓ FOUND! Response: 0x{status:04X}")
            print(f"   READY: {'YES' if (status & 0x0001) else 'NO'}")
            print(f"   MOVE:  {'YES' if (status & 0x0004) else 'NO'}")
            print(f"   ALARM: {'YES' if (status & 0x0100) else 'NO'}")
            print()
        else:
            print("✗ No response")
    except Exception as e:
        print(f"✗ Error")

    time.sleep(0.1)  # Small delay between tries

client.close()

print()
print("=" * 70)
print("Scan complete")
print("If no slave ID responded, check:")
print("  1. Driver is powered (24VDC)")
print("  2. RS-485 wiring (A and B terminals)")
print("  3. Baud rate setting on driver (should be 230400)")
print("  4. Driver DIP switches for slave ID")
print("=" * 70)
