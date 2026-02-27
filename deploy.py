#!/usr/bin/env python3
"""
Deploy files to all Pi controllers and run main.py.

Usage:
    python deploy.py deploy      - コードをデプロイして main.py を起動
    python deploy.py files       - コードのみをデプロイ（再起動なし）
    python deploy.py start       - すべてのPiで main.py を起動
    python deploy.py stop        - すべてのPiで main.py を停止
    python deploy.py status      - 各Piで main.py が実行中か確認
    python deploy.py logs        - すべてのPiの最新ログを表示
    python deploy.py logs 05     - Pi-05 のログをリアルタイムで表示
    python deploy.py shutdown    - すべてのPiをシャットダウン
    python deploy.py reboot      - すべてのPiを再起動
    python deploy.py enablerom   - すべてのPiでROMを有効化
    python deploy.py disablerom  - すべてのPiでROMを無効化
    python deploy.py checkrom    - すべてのPiのROMの状態を確認

Network Mode:
    --vpn                        - Tailscale VPN経由で接続 (default: ローカルネットワーク)

Examples:
    python deploy.py status              # ローカルネットワーク経由
    python deploy.py --vpn status        # Tailscale VPN経由
    python deploy.py --vpn deploy        # VPN経由でデプロイ
"""

import subprocess
import sys

# Configuration
PASSWORD = "fukuimurata"
USER = "user"
REMOTE_PATH = "/home/user/Desktop/ORIENTAL_CVD_CONTROLLER_MURATA/"
PI_NUMBERS = ["02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]

# Network mode: "local" or "vpn"
NETWORK_MODE = "local"

# Tailscale VPN IP addresses for each Pi
VPN_IPS = {
    "02": "100.95.18.36",
    "03": "100.110.165.2",   # TODO: Update with actual Tailscale IP
    "04": "100.105.24.13",   # TODO: Update with actual Tailscale IP
    "05": "100.111.230.21",   # TODO: Update with actual Tailscale IP
    "06": "100.70.13.126",   # TODO: Update with actual Tailscale IP
    "07": "100.66.51.23",   # TODO: Update with actual Tailscale IP
    "08": "100.82.59.50",   # TODO: Update with actual Tailscale IP
    "09": "100.100.28.93",   # TODO: Update with actual Tailscale IP
    "10": "100.70.174.26",   # TODO: Update with actual Tailscale IP
    "11": "100.72.93.23",   # TODO: Update with actual Tailscale IP
}


def get_host(pi_number):
    """Get hostname/IP for a Pi based on network mode."""
    if NETWORK_MODE == "vpn":
        return VPN_IPS.get(pi_number, f"100.95.18.{int(pi_number) + 34}")
    else:
        return f"pi-controller-{pi_number}.local"

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
    print(f"=== Checking main.py status ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        result = run_ssh(host, "pgrep -a -f 'python.*main.py'")
        if result.returncode == 0 and result.stdout:
            print(f"Pi-{pi}: ✓ RUNNING - {result.stdout.decode().strip()}")
        else:
            print(f"Pi-{pi}: ✗ NOT RUNNING")

def start():
    """Start main.py on all Pis."""
    print(f"=== Starting main.py on all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        run_ssh(host, "pkill -f 'python.*main.py'")
        run_ssh(host, f"cd {REMOTE_PATH} && source venv/bin/activate && nohup python main.py > /dev/null 2>&1 &")
        print(f"Pi-{pi}: ▶ started")

def stop():
    """Stop main.py on all Pis."""
    print(f"=== Stopping main.py on all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        run_ssh(host, "pkill -f 'python.*main.py'")
        print(f"Pi-{pi}: ■ stopped")

def logs():
    """Show recent logs from each Pi."""
    print(f"=== Recent logs from all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        print(f"--- Pi-{pi} ---")
        result = run_ssh(host, f"tail -20 /tmp/main_{pi}.log 2>/dev/null || echo 'No log file found'")
        print(result.stdout.decode() if result.stdout else "No output")
        print()

def logs_follow(pi_number):
    """Follow logs from a specific Pi in real-time."""
    host = get_host(pi_number)
    print(f"=== Following logs from Pi-{pi_number} ({NETWORK_MODE.upper()} mode, Ctrl+C to stop) ===\n")
    cmd = ["sshpass", "-p", PASSWORD, "ssh", f"{USER}@{host}", f"tail -f /tmp/main_{pi_number}.log"]
    subprocess.run(cmd)

def deploy_files():
    """Deploy files only, no restart."""
    print(f"=== Deploying files ({NETWORK_MODE.upper()} mode) ===")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        print(f"\n=== Pi-{pi} ({host}) ===")

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

def shutdown_all():
    """Shutdown all Pis."""
    print(f"=== Shutting down all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        run_ssh(host, "sudo shutdown -h now")
        print(f"Pi-{pi}: ⏻ shutdown initiated")

def reboot_all():
    """Reboot all Pis."""
    print(f"=== Rebooting all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        run_ssh(host, "sudo reboot")
        print(f"Pi-{pi}: ↻ reboot initiated")

def enable_rom():
    """Enable read-only filesystem on all Pis."""
    print(f"=== Enabling read-only filesystem on all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        result = run_ssh(host, "~/EnableROM.sh")
        if result.returncode == 0:
            print(f"Pi-{pi}: ✓ ROM enabled")
        else:
            print(f"Pi-{pi}: ✗ Failed - {result.stderr.decode().strip() if result.stderr else 'unknown error'}")

def disable_rom():
    """Disable read-only filesystem on all Pis."""
    print(f"=== Disabling read-only filesystem on all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        result = run_ssh(host, "~/DisableROM.sh")
        if result.returncode == 0:
            print(f"Pi-{pi}: ✓ ROM disabled")
        else:
            print(f"Pi-{pi}: ✗ Failed - {result.stderr.decode().strip() if result.stderr else 'unknown error'}")

def check_rom():
    """Check read-only filesystem status on all Pis."""
    print(f"=== Checking ROM status on all Pis ({NETWORK_MODE.upper()} mode) ===\n")
    for pi in PI_NUMBERS:
        host = get_host(pi)
        result = run_ssh(host, "~/CheckROM.sh")
        output = result.stdout.decode().strip() if result.stdout else "unknown"
        print(f"Pi-{pi}: {output}")

def show_help():
    print(__doc__)

if __name__ == "__main__":
    # Parse --vpn flag
    args = sys.argv[1:]
    if "--vpn" in args:
        NETWORK_MODE = "vpn"
        args.remove("--vpn")

    if len(args) < 1:
        show_help()
        sys.exit(1)

    command = args[0].lower()

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
        if len(args) >= 2:
            # Follow specific Pi logs
            logs_follow(args[1])
        else:
            # Show all logs
            logs()
    elif command == "shutdown":
        shutdown_all()
    elif command == "reboot":
        reboot_all()
    elif command == "enablerom":
        enable_rom()
    elif command == "disablerom":
        disable_rom()
    elif command == "checkrom":
        check_rom()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)
