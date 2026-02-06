#!/usr/bin/env python3
"""
Quick utility to ping all Raspberry Pi stations and check connectivity
"""

import subprocess
import platform
import sys

# Station configuration: hostname and IP address
# Format: (station_id, hostname, ip_address)
STATIONS = [
    ("03", "pi-controller-03.local", None),  # Add IP if known
    ("04", "pi-controller-04.local", None),
    ("05", "pi-controller-05.local", None),
    ("06", "pi-controller-06.local", None),
    ("07", "pi-controller-07.local", None),
    ("08", "pi-controller-08.local", None),
    ("09", "pi-controller-09.local", "192.168.11.45"),  # Known IP
    ("10", "pi-controller-10.local", None),
    ("11", "pi-controller-11.local", None),
]


def ping(host, count=1, timeout=1):
    """
    Ping a host and return True if reachable.

    Args:
        host: Hostname or IP address
        count: Number of ping packets to send
        timeout: Timeout in seconds

    Returns:
        True if host responds, False otherwise
    """
    # Determine ping command based on OS
    system = platform.system().lower()

    if system == "windows":
        # Windows: ping -n count -w timeout_ms host
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    else:
        # macOS/Linux: ping -c count -W timeout host
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        # Run ping command
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"Error pinging {host}: {e}")
        return False


def main():
    print("=" * 70)
    print("Raspberry Pi Station Connectivity Check")
    print("=" * 70)
    print(f"Pinging {len(STATIONS)} stations...\n")

    results = {}
    online_count = 0

    for station_id, hostname, ip_address in STATIONS:
        sys.stdout.write(f"Station {station_id} ({hostname:30s}) ... ")
        sys.stdout.flush()

        # Try hostname first
        reachable = ping(hostname, count=1, timeout=2)

        # If hostname fails but IP is available, try IP
        if not reachable and ip_address:
            sys.stdout.write(f"\n  → Trying IP {ip_address:20s} ... ")
            sys.stdout.flush()
            reachable = ping(ip_address, count=1, timeout=2)

        results[station_id] = {
            'hostname': hostname,
            'ip': ip_address,
            'reachable': reachable
        }

        if reachable:
            print("✓ ONLINE")
            online_count += 1
        else:
            print("✗ OFFLINE")

    # Summary
    print("\n" + "=" * 70)
    print(f"Summary: {online_count}/{len(STATIONS)} stations online")
    print("=" * 70)

    if online_count > 0:
        print("\nOnline stations:")
        for station_id, info in results.items():
            if info['reachable']:
                ip_str = f" ({info['ip']})" if info['ip'] else ""
                print(f"  ✓ Station {station_id}: {info['hostname']}{ip_str}")

    if online_count < len(STATIONS):
        print("\nOffline stations:")
        for station_id, info in results.items():
            if not info['reachable']:
                print(f"  ✗ Station {station_id}: {info['hostname']}")

    print()
    return 0 if online_count == len(STATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
