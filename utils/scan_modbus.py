"""
Scan for Modbus RTU device - finds correct baudrate and slave ID
"""
from pymodbus.client import ModbusSerialClient
import time

COM_PORT = 'COM4'

# Common baudrates for Oriental Motor drivers
BAUDRATES = [230400]
PARITIES = ['N', 'O']  # Even, None, Odd
SLAVE_IDS = [1, 2, 3, 4, 5, 0]  # Common IDs, try 0 last (broadcast)

# Simple register to read (try a few different ones)
TEST_ADDRESSES = [0x0000, 0x0020, 0x007C]  # Common Oriental Motor addresses

def scan():
    print(f"Scanning {COM_PORT} for Modbus RTU device...\n")

    for baudrate in BAUDRATES:
        for parity in PARITIES:
            print(f"Testing: baudrate={baudrate}, parity={parity}")

            client = ModbusSerialClient(
                port=COM_PORT,
                baudrate=baudrate,
                parity=parity,
                stopbits=1,
                bytesize=8,
                timeout=0.5,
                retries=1
            )

            if not client.connect():
                print(f"  Could not open port")
                continue

            for slave_id in SLAVE_IDS:
                for addr in TEST_ADDRESSES:
                    try:
                        response = client.read_holding_registers(
                            address=addr,
                            count=1,
                            device_id=slave_id
                        )

                        if not response.isError():
                            print(f"\n*** FOUND DEVICE! ***")
                            print(f"  Baudrate: {baudrate}")
                            print(f"  Parity: {parity}")
                            print(f"  Slave ID: {slave_id}")
                            print(f"  Address 0x{addr:04X} = {response.registers[0]}")
                            client.close()
                            return baudrate, parity, slave_id

                    except Exception as e:
                        pass

            client.close()
            time.sleep(0.1)

    print("\nNo device found. Check:")
    print("  1. Wiring (A+/B- connections)")
    print("  2. Driver power is ON")
    print("  3. COM port is correct")
    return None

if __name__ == "__main__":
    result = scan()
    if result:
        print(f"\nUpdate your code with these settings:")
        print(f"  baudrate={result[0]}")
        print(f"  parity='{result[1]}'")
        print(f"  slave_id={result[2]}")
