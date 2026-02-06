"""
Test CVD-28-KR with correct register addresses
Based on Oriental Motor CVD series documentation
"""
from pymodbus.client import ModbusSerialClient
import time

COM_PORT = 'COM4'
SLAVE_ID = 1

# CVD Series Register Addresses (from Oriental Motor documentation)
ADDR_DRIVE_INPUT_CMD = 0x007D   # Drive Input Command Register

# Drive Input Command Values (for register 0x007D)
CMD_STOP = 0           # Stop motor
CMD_START = 3          # Start motor
CMD_JOG_PLUS = 4096    # JOG forward (0x1000)
CMD_JOG_MINUS = 8192   # JOG reverse (0x2000)
CMD_MANUAL_FWD = 16384 # Manual forward (0x4000)
CMD_MANUAL_REV = 32768 # Manual backward (0x8000)
CMD_RESET_FAULT = 256  # Reset fault (0x0100)
CMD_HOME = 64          # Home position

def main():
    client = ModbusSerialClient(
        port=COM_PORT,
        baudrate=230400,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1
    )

    if not client.connect():
        print("Failed to connect")
        return

    print("Connected!\n")

    # Read the drive input command register
    print("=== Reading CVD Registers ===")
    response = client.read_holding_registers(address=ADDR_DRIVE_INPUT_CMD, count=1, device_id=SLAVE_ID)
    if not response.isError():
        print(f"Drive Input Command (0x007D): {response.registers[0]}")
    else:
        print(f"Error reading 0x007D: {response}")

    # Try reading nearby registers to find status
    print("\n=== Scanning nearby registers ===")
    for addr in range(0x007C, 0x0085):
        response = client.read_holding_registers(address=addr, count=1, device_id=SLAVE_ID)
        if not response.isError():
            val = response.registers[0]
            if val != 0xFFFF:
                print(f"  0x{addr:04X}: {val} (0x{val:04X})")

    # First, try to reset any fault
    print("\n=== Resetting Fault ===")
    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_RESET_FAULT, device_id=SLAVE_ID)
    print(f"Reset result: {response}")
    time.sleep(0.5)

    # Clear the command
    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_STOP, device_id=SLAVE_ID)
    time.sleep(0.2)

    # Try JOG forward
    print("\n=== Testing JOG Forward ===")
    input("Press Enter to JOG forward for 2 seconds...")

    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_JOG_PLUS, device_id=SLAVE_ID)
    print(f"JOG+ result: {response}")

    time.sleep(2)

    # Stop
    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_STOP, device_id=SLAVE_ID)
    print(f"Stop result: {response}")

    # Try Manual Forward
    print("\n=== Testing Manual Forward ===")
    input("Press Enter to run manual forward for 2 seconds...")

    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_MANUAL_FWD, device_id=SLAVE_ID)
    print(f"Manual FWD result: {response}")

    time.sleep(2)

    # Stop
    response = client.write_register(ADDR_DRIVE_INPUT_CMD, CMD_STOP, device_id=SLAVE_ID)
    print(f"Stop result: {response}")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
