"""
Test CVD-28-KR Stored Data (SD) Operation
Run pre-configured MEXE operation data profiles
"""

import sys
import os
# Add parent directory to path so we can import drivers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymodbus.client import ModbusSerialClient
import time
from drivers.cvd_define import *
from drivers.oriental_cvd import OrientalCvdMotor

COM_PORT = '/dev/ttyUSB0'  # Change for your setup
SLAVE_ID = 1

def main():

    motor = OrientalCvdMotor(port=COM_PORT)

    motor.connect()

    if not motor.isConnected():
        print("Failed to connect")
        return

    print("Connected!\n")
    print("This will run MEXE operation 0")
    print("Make sure you have programmed operation 0 in MEXE before running this!\n")

    input("Press Enter to start operation 0...")

    # Set operation number 0
    motor.set_operation_no(data_no=0, slave_id=SLAVE_ID)
    print("✓ Operation number set to 0")

    # Send START signal
    motor.send_start_signal(slave_id=SLAVE_ID)
    print("✓ START signal sent")

    # Monitor motion for 10 seconds
    print("\nMonitoring motion...")
    for i in range(100):
        status = motor.read_output_signal(slave_id=SLAVE_ID)
        if status:
            moving = (status & OutputSignal.MOVE) != 0
            print(f"  [{i/10:.1f}s] {'MOVING' if moving else 'STOPPED'}", end='\r', flush=True)
            if not moving and i > 10:  # Wait at least 1 second
                print("\n✓ Motion completed")
                break
        time.sleep(0.1)

    motor.close()
    print("\nDone!")

if __name__ == "__main__":
    main()