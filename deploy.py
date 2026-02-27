#!/usr/bin/env python3
"""
Deploy files to all Pi controllers and run main.py.

Usage:
    python deploy.py deploy    - Deploy files and start main.py
    python deploy.py files     - Deploy files only (no restart)
    python deploy.py start     - Start main.py on all Pis
    python deploy.py stop      - Stop main.py on all Pis
    python deploy.py status    - Check if main.py is running on each Pi
    python deploy.py logs      - Show recent logs from all Pis
    python deploy.py logs 05   - Follow logs from Pi-05 in real-time
"""

import subprocess
import sys

# Configuration
PASSWORD = "fukuimurata"
USER = "user"
REMOTE_PATH = "/home/user/Desktop/ORIENTAL_CVD_CONTROLLER_MURATA/"
PI_NUMBERS = ["02", "03", "04", "05", "06", "07", "08", "09", "10","11"]
#PI_NUMBERS = ["02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]

# Files to deploy to ALL Pis
FILES_ALL = [
    ("config/all_stations.json", "config/all_stations.json"),
    ("main.py", "main.py"),
    ("services/motor_controller.py", "services/motor_controller.py"),
    ("services/motor_driver.py", "services/motor_driver.py"),
    ("services/mp4_player.py", "services/mp4_player.py"),
]

# Additional files for Pi-02 only
FILES_PI02_ONLY = [
    ("key.py", "key.py"),
    ("services/sequence_manager.py", "services/sequence_manager.py"),
]

# Additional files for Pi-07 and Pi-10 (LED stations)
FILES_LED_STATIONS = [
    ("services/led_controller.py", "services/led_controller.py"),
]

# Files to keep in services folder for LED stations
KEEP_SERVICES_LED = ["motor_controller.py", "motor_driver.py", "mp4_player.py", "led_controller.py"]

# Files to keep in root folder
KEEP_ROOT_ALL = ["main.py"]
KEEP_ROOT_PI02 = ["main.py", "key.py"]

# Files to keep in services folder
KEEP_SERVICES_ALL = ["motor_controller.py", "motor_driver.py", "mp4_player.py"]
KEEP_SERVICES_PI02 = ["motor_controller.py", "motor_driver.py", "mp4_player.py", "sequence_manager.py"]

def run_ssh(host, command):
    cmd = ["sshpass", "-p", PASSWORD, "ssh", f"{USER}@{host}", command]
    return subprocess.run(cmd, capture_output=True)


def status():
    """Check if main.py is running on each Pi."""
    print("=== Checking main.py status ===\n")
    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        result = run_ssh(host, "pgrep -a -f 'python.*main.py'")
        if result.returncode == 0 and result.stdout:
            print(f"Pi-{pi}: ✓ RUNNING - {result.stdout.decode().strip()}")
        else:
            print(f"Pi-{pi}: ✗ NOT RUNNING")

def start():
    """Start main.py on all Pis."""
    print("=== Starting main.py on all Pis ===\n")
    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        run_ssh(host, "pkill -f 'python.*main.py'")
        run_ssh(host, f"cd {REMOTE_PATH} && source venv/bin/activate && nohup python main.py > /dev/null 2>&1 &")
        print(f"Pi-{pi}: ▶ started")

def stop():
    """Stop main.py on all Pis."""
    print("=== Stopping main.py on all Pis ===\n")
    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        run_ssh(host, "pkill -f 'python.*main.py'")
        print(f"Pi-{pi}: ■ stopped")

def logs():
    """Show recent logs from each Pi."""
    print("=== Recent logs from all Pis ===\n")
    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        print(f"--- Pi-{pi} ---")
        result = run_ssh(host, f"tail -20 /tmp/main_{pi}.log 2>/dev/null || echo 'No log file found'")
        print(result.stdout.decode() if result.stdout else "No output")
        print()

def logs_follow(pi_number):
    """Follow logs from a specific Pi in real-time."""
    host = f"pi-controller-{pi_number}.local"
    print(f"=== Following logs from Pi-{pi_number} (Ctrl+C to stop) ===\n")
    cmd = ["sshpass", "-p", PASSWORD, "ssh", f"{USER}@{host}", f"tail -f /tmp/main_{pi_number}.log"]
    subprocess.run(cmd)

def deploy_files():
    """Deploy files only, no restart."""
    for pi in PI_NUMBERS:
        host = f"pi-controller-{pi}.local"
        print(f"\n=== Pi-{pi} ===")

        # Determine which files to deploy
        files = FILES_ALL.copy()
        if pi == "02":
            files += FILES_PI02_ONLY
        if pi in ["07", "10"]:
            files += FILES_LED_STATIONS

        # Deploy files
        success = True
        for local_path, remote_name in files:
            cmd = [
                "sshpass", "-p", PASSWORD,
                "scp", local_path,
                f"{USER}@{host}:{REMOTE_PATH}{remote_name}"
            ]
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"  ✗ Failed: {local_path}")
                success = False
            else:
                print(f"  ✓ {remote_name}")

        # Clean up extra .py files
        if pi == "02":
            keep_root = KEEP_ROOT_PI02
            keep_services = KEEP_SERVICES_PI02
        elif pi in ["07", "10"]:
            keep_root = KEEP_ROOT_ALL
            keep_services = KEEP_SERVICES_LED
        else:
            keep_root = KEEP_ROOT_ALL
            keep_services = KEEP_SERVICES_ALL

        keep_root_str = " ".join([f"! -name '{f}'" for f in keep_root])
        run_ssh(host, f"find {REMOTE_PATH} -maxdepth 1 -name '*.py' {keep_root_str} -delete")

        keep_services_str = " ".join([f"! -name '{f}'" for f in keep_services])
        run_ssh(host, f"find {REMOTE_PATH}services -maxdepth 1 -name '*.py' {keep_services_str} -delete")

        print(f"  🧹 cleaned extra .py files")

        if success:
            print(f"✓ Pi-{pi} deployed")
        else:
            print(f"✗ Pi-{pi} had errors")

def show_help():
    print(__doc__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "deploy":
        deploy_files()
        start()
    elif command == "files":
        deploy_files()
    elif command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "status":
        status()
    elif command == "logs":
        if len(sys.argv) >= 3:
            # Follow specific Pi logs
            logs_follow(sys.argv[2])
        else:
            # Show all logs
            logs()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)
