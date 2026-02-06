#!/usr/bin/env python3
"""
Quick utility to find available serial ports
Helps identify the USB-RS485 adapter port
"""

import sys
import glob

def find_serial_ports():
    """List all available serial ports on this system"""

    if sys.platform.startswith('darwin'):  # macOS
        ports = glob.glob('/dev/tty.usb*')
        ports += glob.glob('/dev/cu.usb*')
    elif sys.platform.startswith('linux'):  # Linux/RPi
        ports = glob.glob('/dev/ttyUSB*')
        ports += glob.glob('/dev/ttyACM*')
    elif sys.platform.startswith('win'):  # Windows
        ports = []
        for i in range(1, 256):
            try:
                import serial
                s = serial.Serial(f'COM{i}')
                s.close()
                ports.append(f'COM{i}')
            except (OSError, serial.SerialException):
                pass
    else:
        ports = []

    return sorted(ports)

def main():
    print("Searching for serial ports...")
    ports = find_serial_ports()

    if not ports:
        print("\n❌ No serial ports found!")
        print("\nTroubleshooting:")
        print("  1. Make sure USB-RS485 adapter is plugged in")
        print("  2. Check if driver is installed (CH340, FTDI, etc.)")
        if sys.platform.startswith('darwin'):
            print("  3. Run: ls /dev/tty.* | grep usb")
        elif sys.platform.startswith('linux'):
            print("  3. Run: ls /dev/ttyUSB*")
        return 1

    print(f"\n✓ Found {len(ports)} serial port(s):\n")
    for port in ports:
        print(f"  {port}")

    print("\n" + "=" * 70)
    print("Copy one of the ports above and paste it into:")
    print("  tests/test_station2_nogpio.py")
    print("  (Update the COM_PORT variable)")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
