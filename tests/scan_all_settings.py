#!/usr/bin/env python3
"""
Comprehensive CVD driver scanner
Tries different baud rates, parity settings, and slave IDs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymodbus.client import ModbusSerialClient
import time

COM_PORT = '/dev/cu.usbserial-FT78LMAE'  # Your port

# Common settings for Oriental Motor drivers
BAUD_RATES = [
    9600,      # Default for many drivers
    19200,
    38400,
    57600,
    115200,    # Common for AZ series
    230400,    # Common for CVD series
]

PARITY_SETTINGS = [
    ('N', 1, "None, 1 stop"),      # No parity, 1 stop bit
    ('E', 1, "Even, 1 stop"),      # Even parity, 1 stop bit
    ('O', 1, "Odd, 1 stop"),       # Odd parity, 1 stop bit
]

SLAVE_IDS = [0, 1, 2, 3]  # Most common IDs

print("=" * 70)
print("CVD Driver Comprehensive Scanner")
print("=" * 70)
print(f"Port: {COM_PORT}")
print()
print("This will try:")
print(f"  - {len(BAUD_RATES)} baud rates")
print(f"  - {len(PARITY_SETTINGS)} parity settings")
print(f"  - {len(SLAVE_IDS)} slave IDs")
print(f"  = {len(BAUD_RATES) * len(PARITY_SETTINGS) * len(SLAVE_IDS)} total combinations")
print()
input("Press Enter to start scanning (this will take ~2 minutes)...")
print()

found_settings = []

for baud in BAUD_RATES:
    for parity, stopbits, parity_desc in PARITY_SETTINGS:
        print(f"\nTrying {baud} baud, {parity_desc}...")

        client = ModbusSerialClient(
            port=COM_PORT,
            baudrate=baud,
            parity=parity,
            stopbits=stopbits,
            bytesize=8,
            timeout=0.3
        )

        if not client.connect():
            print(f"  ✗ Failed to open port")
            continue

        for slave_id in SLAVE_IDS:
            sys.stdout.write(f"  Slave {slave_id}: ")
            sys.stdout.flush()

            try:
                result = client.read_holding_registers(address=0x007F, count=1, slave=slave_id)

                if not result.isError():
                    status = result.registers[0]
                    print(f"✓✓✓ FOUND! ✓✓✓")
                    print(f"      Baud: {baud}, Parity: {parity_desc}, Slave ID: {slave_id}")
                    print(f"      Status: 0x{status:04X}")
                    found_settings.append({
                        'baud': baud,
                        'parity': parity,
                        'stopbits': stopbits,
                        'slave_id': slave_id,
                        'status': status
                    })
                    print()
                else:
                    print("✗")
            except:
                print("✗")

            time.sleep(0.05)

        client.close()
        time.sleep(0.1)

print()
print("=" * 70)
print("SCAN COMPLETE")
print("=" * 70)

if found_settings:
    print(f"\n✓ Found {len(found_settings)} working configuration(s):\n")
    for i, settings in enumerate(found_settings, 1):
        print(f"{i}. Baud: {settings['baud']}, Parity: {settings['parity']}, "
              f"Stopbits: {settings['stopbits']}, Slave ID: {settings['slave_id']}")
        print(f"   Status: 0x{settings['status']:04X}")
        print(f"   READY: {'YES' if (settings['status'] & 0x0001) else 'NO'}")
        print()

    print("=" * 70)
    print("UPDATE YOUR CODE WITH THESE SETTINGS:")
    best = found_settings[0]
    print(f"""
client = ModbusSerialClient(
    port='{COM_PORT}',
    baudrate={best['baud']},
    parity='{best['parity']}',
    stopbits={best['stopbits']},
    bytesize=8,
    timeout=1.0
)

SLAVE_ID = {best['slave_id']}
""")
else:
    print("\n✗ No working configuration found!")
    print("\nTroubleshooting:")
    print("  1. Check driver is powered (24VDC, green LED on)")
    print("  2. Check RS-485 wiring (A to A+, B to B-)")
    print("  3. Check USB-RS485 adapter is working")
    print("  4. Try swapping A/B wires (some adapters label backwards)")
    print("  5. Check driver manual for Modbus settings")

print("=" * 70)
