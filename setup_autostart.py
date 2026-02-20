#!/usr/bin/env python3
"""
Setup systemd autostart for main.py on all Pi controllers.

Usage:
    python setup_autostart.py install   - Install and enable autostart on all Pis
    python setup_autostart.py remove    - Remove autostart from all Pis
    python setup_autostart.py status    - Check autostart status on all Pis
"""

import subprocess
import sys

# Configuration
PASSWORD = "fukuimurata"
USER = "user"
REMOTE_PATH = "/home/user/Desktop/ORIENTAL_CVD_CONTROLLER_MURATA"
PI_NUMBERS = ["02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]
SERVICE_NAME = "motor-controller"

# Systemd service file content
SERVICE_CONTENT = f"""[Unit]
Description=Oriental Motor CVD Controller
After=network.target

[Service]
Type=simple
User={USER}
WorkingDirectory={REMOTE_PATH}
ExecStart={REMOTE_PATH}/venv/bin/python {REMOTE_PATH}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

def run_ssh(host, command, sudo=False):
    if sudo:
        command = f"echo '{PASSWORD}' | sudo -S {command}"
    cmd = ["sshpass", "-p", PASSWORD, "ssh", f"{USER}@{host}", command]
    return subprocess.run(cmd, capture_output=True)

def install():
    """Install and enable autostart on all Pis."""
    print("=== Installing autostart on all Pis ===\n")

    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        print(f"Pi-{pi}:")

        # Write service file
        escaped_content = SERVICE_CONTENT.replace("'", "'\\''")
        run_ssh(host, f"echo '{escaped_content}' | sudo tee /etc/systemd/system/{SERVICE_NAME}.service > /dev/null", sudo=False)
        print(f"  ✓ Created service file")

        # Reload systemd
        run_ssh(host, "systemctl daemon-reload", sudo=True)
        print(f"  ✓ Reloaded systemd")

        # Enable service
        run_ssh(host, f"systemctl enable {SERVICE_NAME}", sudo=True)
        print(f"  ✓ Enabled autostart")

        # Stop any existing main.py and start service
        run_ssh(host, "pkill -f 'python.*main.py'", sudo=False)
        run_ssh(host, f"systemctl start {SERVICE_NAME}", sudo=True)
        print(f"  ✓ Started service")

        print(f"Pi-{pi}: ✓ Done\n")

def remove():
    """Remove autostart from all Pis."""
    print("=== Removing autostart from all Pis ===\n")

    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        print(f"Pi-{pi}:")

        # Stop service
        run_ssh(host, f"systemctl stop {SERVICE_NAME}", sudo=True)
        print(f"  ✓ Stopped service")

        # Disable service
        run_ssh(host, f"systemctl disable {SERVICE_NAME}", sudo=True)
        print(f"  ✓ Disabled autostart")

        # Remove service file
        run_ssh(host, f"rm -f /etc/systemd/system/{SERVICE_NAME}.service", sudo=True)
        print(f"  ✓ Removed service file")

        # Reload systemd
        run_ssh(host, "systemctl daemon-reload", sudo=True)
        print(f"  ✓ Reloaded systemd")

        print(f"Pi-{pi}: ✓ Done\n")

def status():
    """Check autostart status on all Pis."""
    print("=== Autostart status on all Pis ===\n")

    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"

        # Check if service is enabled
        enabled_result = run_ssh(host, f"systemctl is-enabled {SERVICE_NAME} 2>/dev/null")
        enabled = enabled_result.stdout.decode().strip() == "enabled"

        # Check if service is running
        active_result = run_ssh(host, f"systemctl is-active {SERVICE_NAME} 2>/dev/null")
        active = active_result.stdout.decode().strip() == "active"

        enabled_str = "✓ enabled" if enabled else "✗ disabled"
        active_str = "✓ running" if active else "✗ stopped"

        print(f"Pi-{pi}: {enabled_str}, {active_str}")

def show_help():
    print(__doc__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "install":
        install()
    elif command == "remove":
        remove()
    elif command == "status":
        status()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)
