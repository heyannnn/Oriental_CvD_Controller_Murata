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
    python deploy.py v           - Toggle start/stop (simulates V key on Pi-02)
    python deploy.py reset       - Reset all stations (simulates Ctrl+V on Pi-02)
    python deploy.py diff        - ローカルとリモートのファイルを比較（チェックサムベース）
    python deploy.py diff --verbose - ファイルの差分を詳細表示

Network Mode:
    --vpn                        - Tailscale VPN経由で接続 (default: ローカルネットワーク)

Examples:
    python deploy.py status                    # ローカルネットワーク経由
    python deploy.py --vpn status              # Tailscale VPN経由
    python deploy.py --vpn deploy              # VPN経由でデプロイ
    python deploy.py --vpn files 
    python deploy.py --vpn v                   # Toggle start/stop (simulates V key on Pi-02)
    python deploy.py --vpn reset               # Toggle start/stop (simulates V key on Pi-02)
    python deploy.py --vpn diff                # ローカルとリモートのファイルを比較
    python deploy.py --vpn diff --verbose      # ファイルの差分を詳細表示
    python deploy.py --vpn disablerom
    python deploy.py --vpn checkrom
    python deploy.py --vpn enablerom 
    python deploy.py --vpn reboot


"""

import subprocess
import sys
import hashlib
import os

# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

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

def send_key_v():
    """Send /key/v to Pi-02 (simulates V key - toggle start/stop)."""
    host = get_host("02")
    print(f"=== Sending /key/v to Pi-02 ({NETWORK_MODE.upper()} mode) ===")
    cmd = f"cd {REMOTE_PATH} && source venv/bin/activate && python3 -c \"from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 10000); client.send_message('/key/v', []); print('V key sent')\""
    result = run_ssh(host, cmd)
    print(result.stdout.decode() if result.stdout else "Done")

def send_key_ctrl_v():
    """Send /key/reset to Pi-02 (simulates Ctrl+V - reset all)."""
    host = get_host("02")
    print(f"=== Sending /key/reset to Pi-02 ({NETWORK_MODE.upper()} mode) ===")
    cmd = f"cd {REMOTE_PATH} && source venv/bin/activate && python3 -c \"from pythonosc import udp_client; client = udp_client.SimpleUDPClient('127.0.0.1', 10000); client.send_message('/key/reset', []); print('Ctrl+V (reset) sent')\""
    result = run_ssh(host, cmd)
    print(result.stdout.decode() if result.stdout else "Done")

def get_local_checksum(file_path):
    """Calculate MD5 checksum of a local file."""
    try:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        return None

def get_remote_checksum(host, remote_path):
    """Get MD5 checksum of a remote file via SSH."""
    result = run_ssh(host, f"md5sum {remote_path} 2>/dev/null || echo 'ERROR'")
    if result.returncode == 0 and result.stdout:
        output = result.stdout.decode().strip()
        if output and output != 'ERROR' and not output.startswith('md5sum:'):
            # md5sum output format: "checksum filename"
            return output.split()[0]
    return None

def get_remote_diff(host, local_path, remote_path):
    """Get actual diff between local and remote file."""
    try:
        # Create a temporary file on remote with local content
        with open(local_path, 'r', encoding='utf-8') as f:
            local_content = f.read()

        # Escape single quotes in content for shell
        escaped_content = local_content.replace("'", "'\\''")

        # Create temp file and run diff
        temp_file = f"/tmp/deploy_diff_temp_{os.getpid()}"
        cmd = f"cat > {temp_file} << 'DEPLOY_DIFF_EOF'\n{escaped_content}\nDEPLOY_DIFF_EOF\n"
        cmd += f"diff -u {remote_path} {temp_file} 2>/dev/null; rm -f {temp_file}"

        result = run_ssh(host, cmd)
        if result.stdout:
            return result.stdout.decode()
        return "Unable to generate diff"
    except Exception as e:
        return f"Error generating diff: {str(e)}"

def format_diff_readable(diff_output, pi_number):
    """Format diff output in a more readable way with colors."""
    lines = diff_output.split('\n')
    formatted_lines = []
    line_num = None

    for line in lines:
        # Skip the file headers (--- and +++)
        if line.startswith('---') or line.startswith('+++'):
            continue

        # Parse the line numbers from @@ -X,Y +A,B @@
        if line.startswith('@@'):
            # Extract line number information
            parts = line.split()
            if len(parts) >= 3:
                # Get the remote line number (first number after @@)
                remote_line = parts[1].strip('-').split(',')[0]
                formatted_lines.append(f"\n    {Colors.CYAN}[Around line {remote_line}]{Colors.RESET}")
            continue

        # Lines starting with - are in remote (removed)
        if line.startswith('-'):
            content = line[1:]  # Remove the - prefix
            formatted_lines.append(f"      {Colors.RED}REMOTE (Pi-{pi_number}): {content}{Colors.RESET}")

        # Lines starting with + are in local (added)
        elif line.startswith('+'):
            content = line[1:]  # Remove the + prefix
            formatted_lines.append(f"      {Colors.GREEN}LOCAL:           {content}{Colors.RESET}")

        # Lines with no prefix are context (unchanged)
        elif line.strip():
            # Only show context if it's meaningful (not just whitespace)
            if len(line.strip()) > 0:
                formatted_lines.append(f"      {Colors.BLUE}       {line}{Colors.RESET}")

    return '\n'.join(formatted_lines)

def compare_files(verbose=False):
    """Compare local files with remote files on each Pi."""
    print(f"=== Comparing files with remote stations ({NETWORK_MODE.upper()} mode) ===\n")

    # Track checksums for cross-station comparison
    # Structure: {file_name: {pi_number: checksum}}
    file_checksums = {}
    online_stations = set()

    for pi in PI_NUMBERS:
        host = get_host(pi)
        print(f"Pi-{pi} ({host}):")

        # Determine which files this Pi should have
        files = FILES_ALL.copy()
        if pi == "02":
            files += FILES_PI02_ONLY
        if pi in ["07", "10"]:
            files += FILES_LED_STATIONS

        # Test connectivity first
        test_result = run_ssh(host, "echo 'online'")
        if test_result.returncode != 0:
            print(f"  {Colors.YELLOW}⚠ OFFLINE - Cannot connect to Pi-{pi}{Colors.RESET}")
            print()
            continue

        online_stations.add(pi)

        # Compare each file
        has_differences = False
        for local_path, remote_name in files:
            remote_full_path = f"{REMOTE_PATH}{remote_name}"

            # Check if local file exists
            if not os.path.exists(local_path):
                print(f"  {Colors.YELLOW}⚠ {remote_name} - LOCAL FILE MISSING{Colors.RESET}")
                has_differences = True
                continue

            # Get checksums
            local_checksum = get_local_checksum(local_path)
            remote_checksum = get_remote_checksum(host, remote_full_path)

            # Track checksums for cross-station comparison
            if remote_name not in file_checksums:
                file_checksums[remote_name] = {}
            file_checksums[remote_name][pi] = remote_checksum

            if local_checksum is None:
                print(f"  {Colors.YELLOW}⚠ {remote_name} - ERROR reading local file{Colors.RESET}")
                has_differences = True
            elif remote_checksum is None:
                print(f"  {Colors.YELLOW}⚠ {remote_name} - MISSING on remote{Colors.RESET}")
                has_differences = True
            elif local_checksum == remote_checksum:
                print(f"  {Colors.GREEN}✓ {remote_name} - identical{Colors.RESET}")
            else:
                print(f"  {Colors.RED}✗ {remote_name} - DIFFERENT{Colors.RESET}")
                has_differences = True

                # Show detailed diff if verbose mode
                if verbose:
                    print(f"    {Colors.BOLD}Changes:{Colors.RESET}")
                    diff_output = get_remote_diff(host, local_path, remote_full_path)
                    formatted_diff = format_diff_readable(diff_output, pi)
                    print(formatted_diff)
                    print()

        if not has_differences:
            print(f"  {Colors.GREEN}✅ All files identical{Colors.RESET}")

        print()

    # Show cross-station comparison summary
    if len(online_stations) > 1:
        print(f"\n{Colors.BOLD}=== Station-to-Station Comparison ==={Colors.RESET}\n")

        for file_name in sorted(file_checksums.keys()):
            checksums = file_checksums[file_name]

            # Group stations by checksum
            checksum_groups = {}
            for pi, checksum in checksums.items():
                if checksum is not None and checksum != 'ERROR':
                    if checksum not in checksum_groups:
                        checksum_groups[checksum] = []
                    checksum_groups[checksum].append(pi)

            # Display grouped stations
            print(f"{Colors.CYAN}{file_name}:{Colors.RESET}")

            if len(checksum_groups) == 0:
                print(f"  {Colors.YELLOW}No valid checksums found{Colors.RESET}")
            elif len(checksum_groups) == 1:
                all_pis = sorted(list(checksum_groups.values())[0])
                print(f"  {Colors.GREEN}✓ All stations identical: Pi-{', Pi-'.join(all_pis)}{Colors.RESET}")
            else:
                # Multiple versions exist
                group_num = 1
                for checksum, pis in sorted(checksum_groups.items(), key=lambda x: len(x[1]), reverse=True):
                    pis_sorted = sorted(pis)
                    if len(pis) == 1:
                        print(f"  {Colors.YELLOW}⚠ Different (unique): Pi-{pis_sorted[0]}{Colors.RESET}")
                    else:
                        print(f"  {Colors.BLUE}Group {group_num} (identical): Pi-{', Pi-'.join(pis_sorted)}{Colors.RESET}")
                        group_num += 1

            print()

def show_help():
    print(__doc__)

if __name__ == "__main__":
    # Parse --vpn and --verbose flags
    args = sys.argv[1:]
    verbose = False

    if "--vpn" in args:
        NETWORK_MODE = "vpn"
        args.remove("--vpn")

    if "--verbose" in args:
        verbose = True
        args.remove("--verbose")

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
    elif command == "v":
        send_key_v()
    elif command == "reset":
        send_key_ctrl_v()
    elif command == "diff":
        compare_files(verbose=verbose)
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)
