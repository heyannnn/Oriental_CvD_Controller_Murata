"""
Scan to find valid register addresses on the CVD-28-KR driver
"""
from pymodbus.client import ModbusSerialClient
import time

COM_PORT = 'COM4'
SLAVE_ID = 1

def main():
    client = ModbusSerialClient(
        port=COM_PORT,
        baudrate=230400,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=0.5
    )

    if not client.connect():
        print("Failed to connect")
        return

    print("Connected! Scanning for valid registers...\n")

    # Known register ranges to try for Oriental Motor drivers
    # CVD series might use different addresses than AZ series
    test_ranges = [
        (0x0000, 0x0010, "Basic info"),
        (0x0040, 0x0070, "Direct data area (alternate)"),
        (0x0058, 0x0068, "Direct data area (AZ standard)"),
        (0x007C, 0x0090, "Operation data"),
        (0x0100, 0x0130, "I/O and status area"),
        (0x0180, 0x01A0, "Parameter area"),
        (0x0400, 0x0420, "Extended area 1"),
        (0x0480, 0x04A0, "Extended area 2"),
        (0x1000, 0x1020, "High address area"),
    ]

    valid_addresses = []

    for start, end, desc in test_ranges:
        print(f"\n--- Scanning {desc} (0x{start:04X} - 0x{end:04X}) ---")
        for addr in range(start, end, 2):
            try:
                response = client.read_holding_registers(address=addr, count=1, device_id=SLAVE_ID)
                if not response.isError():
                    val = response.registers[0]
                    # Skip if all bits are 1 (likely invalid)
                    if val != 0xFFFF:
                        print(f"  0x{addr:04X}: {val} (0x{val:04X})")
                        valid_addresses.append((addr, val))
            except Exception as e:
                pass
            time.sleep(0.02)

    print(f"\n\n=== Found {len(valid_addresses)} valid registers ===")
    for addr, val in valid_addresses:
        print(f"  0x{addr:04X} = {val}")

    # Also try to find writable registers for direct operation
    print("\n\n=== Testing write to potential direct data addresses ===")
    test_write_addrs = [0x0040, 0x0042, 0x0044, 0x007D, 0x007E, 0x0180, 0x0400, 0x0480]

    for addr in test_write_addrs:
        try:
            # Try writing a single register
            response = client.write_registers(addr, [0], device_id=SLAVE_ID)
            if not response.isError():
                print(f"  0x{addr:04X}: WRITABLE")
            else:
                print(f"  0x{addr:04X}: Error - {response}")
        except Exception as e:
            print(f"  0x{addr:04X}: Exception - {e}")
        time.sleep(0.05)

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
