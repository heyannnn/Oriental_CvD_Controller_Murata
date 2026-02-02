"""
Test CVD-28-KR Stored Data (SD) Operation
Run pre-configured MEXE operation data profiles
"""

from pymodbus.client import ModbusSerialClient
import time
from az_define import *
from oriental_az import *

COM_PORT = 'COM4'
SLAVE_ID = 1

def main():
    
    motor = OrientalMotor(com_port=COM_PORT, slave_id=SLAVE_ID)
    motor.connect()

    if not motor.isConnected():
        print("Failed to connect")
        return

    print("Connected!\n")

    print("\nMethod : op# in lower bits + start")
    input("Press Enter to try...")
    # Some drivers use format: operation_no | START_BIT
    combined_cmd = 8 | 0x0008  # Operation #0 + START bit (bit 3)
    response = motor.client.write_register(ADDR_DRIVE_INPUT_CMD, combined_cmd, device_id=SLAVE_ID)
    print(f"  Write combined cmd (0x{combined_cmd:04X}) to 0x007D: {response}")
    time.sleep(2)

    response = motor.client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_STOP, device_id=SLAVE_ID)

    motor.close()
    print("\nDone! Did any method make the motor move?")

if __name__ == "__main__":
    main()
