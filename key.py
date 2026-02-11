#!/usr/bin/env python3
"""
Keyboard Control Script for Multi-Station System
Runs on Pi 2 (master station) to control all stations via OSC

Usage:
    python keyboard.py

Controls:
    V key (first press) - Launch all stations (SSH start main.py)
    V key (second press) - Start operations
    V key (while running) - Stop operations
    Ctrl+C - Exit

Requirements:
    - SSH keys must be set up for passwordless login to all stations
    - Run: ssh-keygen (if no key exists)
    - Run: ssh-copy-id pi@pi-controller-03.local (for each station)
"""

import logging
import time
import subprocess
import asyncio
import threading
import readchar
from pythonosc import udp_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# All station hostnames and ports
STATIONS = {
    "02": {"host": "pi-controller-02.local", "port": 9010, "user": "user"},
    "03": {"host": "pi-controller-03.local", "port": 9010, "user": "user"},
    "04": {"host": "pi-controller-04.local", "port": 9010, "user": "user"},
    "05": {"host": "pi-controller-05.local", "port": 9010, "user": "user"},
    "06": {"host": "pi-controller-06.local", "port": 9010, "user": "user"},
    "07": {"host": "pi-controller-07.local", "port": 9010, "user": "user"},
    "08": {"host": "pi-controller-08.local", "port": 9010, "user": "user"},
    "09": {"host": "pi-controller-09.local", "port": 9010, "user": "user"},
    "10": {"host": "pi-controller-10.local", "port": 9010, "user": "user"},
    "11": {"host": "pi-controller-11.local", "port": 9010, "user": "user"},
}

# Path to main.py on remote Pis (adjust if different)
REMOTE_MAIN_PATH = "/home/pi/Oriental_CvD_Controller_Murata/main.py"
REMOTE_PYTHON = "python3"  # or full path like /home/pi/venv/bin/python

# Testing mode: Use local subprocess instead of SSH (set to True when testing on same machine)
USE_LOCAL_LAUNCH = True  # Set to False when using real SSH to remote stations

# ============================================================================
# OSC Clients and SSH Processes
# ============================================================================

osc_clients = {}
ssh_processes = {}  # Track SSH processes for each station

def initialize_osc_clients():
    """Create OSC clients for all stations"""
    global osc_clients

    for station_id, config in STATIONS.items():
        try:
            client = udp_client.SimpleUDPClient(config["host"], config["port"])
            osc_clients[station_id] = client
            logger.info(f"OSC client created for station {station_id} ({config['host']}:{config['port']})")
        except Exception as e:
            logger.error(f"Failed to create OSC client for station {station_id}: {e}")

async def launch_station_local(station_id):
    """
    Launch main.py locally (when keyboard.py is running on same machine).

    Args:
        station_id: Station ID string
    """
    try:
        logger.info(f"Launching station {station_id} LOCALLY (same machine)...")

        # Get the directory containing keyboard.py (should be project root)
        import os
        project_dir = os.path.dirname(os.path.abspath(__file__))
        main_path = os.path.join(project_dir, "main.py")

        # Check if venv exists
        venv_python = os.path.join(project_dir, "venv", "bin", "python")
        if os.path.exists(venv_python):
            python_cmd = venv_python
            logger.info(f"Using venv Python: {python_cmd}")
        else:
            python_cmd = "python3"
            logger.info(f"Using system Python: {python_cmd}")

        # Start main.py in background (don't capture output so we can see it live)
        logger.info(f"Starting: {python_cmd} {main_path}")
        logger.info(f"Working directory: {project_dir}")

        process = await asyncio.create_subprocess_exec(
            python_cmd,
            main_path,
            cwd=project_dir
            # Note: Not capturing stdout/stderr so output goes to terminal
        )

        # Give it a moment to start
        await asyncio.sleep(2.0)

        # Check if process is still running
        if process.returncode is None:
            logger.info(f"✓ Station {station_id} launched successfully (PID: {process.pid})")
            logger.info(f"  Check main.py output above for initialization logs")
            return True
        else:
            logger.error(f"✗ Station {station_id} process exited with code {process.returncode}")
            return False

    except Exception as e:
        logger.error(f"✗ Failed to launch station {station_id} locally: {e}")
        import traceback
        traceback.print_exc()
        return False

async def launch_station_remote(station_id, config):
    """
    SSH into a station and start main.py remotely.

    Args:
        station_id: Station ID string
        config: Station config dict with 'host' and 'user'
    """
    user = config["user"]
    host = config["host"]

    # SSH command to start main.py on remote Pi
    # Using nohup to keep process running after SSH disconnects
    ssh_cmd = [
        "ssh",
        f"{user}@{host}",
        f"cd {REMOTE_MAIN_PATH.rsplit('/', 1)[0]} && nohup {REMOTE_PYTHON} {REMOTE_MAIN_PATH} > /tmp/motor_controller.log 2>&1 &"
    ]

    try:
        logger.info(f"Launching station {station_id} via SSH ({host})...")

        # Execute SSH command
        process = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for SSH to complete (should be quick since we're using nohup &)
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)

        if process.returncode == 0:
            logger.info(f"✓ Station {station_id} launched successfully")
            return True
        else:
            logger.error(f"✗ Station {station_id} launch failed: {stderr.decode()}")
            return False

    except asyncio.TimeoutError:
        logger.warning(f"⚠ Station {station_id} SSH timeout (process may still be starting)")
        return True  # Consider it successful if timeout (process is running)
    except Exception as e:
        logger.error(f"✗ Failed to launch station {station_id}: {e}")
        return False

async def launch_all_stations():
    """Launch main.py on all stations via SSH or local subprocess"""
    if USE_LOCAL_LAUNCH:
        logger.info("=" * 70)
        logger.info("LAUNCHING STATIONS LOCALLY (Testing Mode)")
        logger.info("=" * 70)
    else:
        logger.info("=" * 70)
        logger.info("LAUNCHING ALL STATIONS VIA SSH")
        logger.info("=" * 70)

    # Launch all stations in parallel
    tasks = []
    for station_id, config in STATIONS.items():
        if USE_LOCAL_LAUNCH:
            # Use local subprocess (for testing on same machine)
            task = launch_station_local(station_id)
        else:
            # Use SSH (for production multi-Pi setup)
            task = launch_station_remote(station_id, config)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count successes
    success_count = sum(1 for r in results if r is True)
    logger.info("=" * 70)
    logger.info(f"Launch complete: {success_count}/{len(STATIONS)} stations started")
    logger.info("=" * 70)

    # Wait a moment for all stations to boot and start listening
    logger.info("Waiting 5 seconds for all stations to initialize...")
    await asyncio.sleep(5)

# ============================================================================
# OSC Commands
# ============================================================================

def send_start_command():
    """Send start command to all stations"""
    logger.info("=" * 70)
    logger.info("SENDING START COMMAND TO ALL STATIONS")
    logger.info("=" * 70)

    for station_id, client in osc_clients.items():
        try:
            client.send_message("/start", 1)
            logger.info(f"✓ Start command sent to station {station_id}")
        except Exception as e:
            logger.error(f"✗ Failed to send start to station {station_id}: {e}")

def send_stop_command():
    """Send stop command to all stations"""
    logger.info("=" * 70)
    logger.info("SENDING STOP COMMAND TO ALL STATIONS")
    logger.info("=" * 70)

    for station_id, client in osc_clients.items():
        try:
            client.send_message("/stop", 1)
            logger.info(f"✓ Stop command sent to station {station_id}")
        except Exception as e:
            logger.error(f"✗ Failed to send stop to station {station_id}: {e}")

# ============================================================================
# Keyboard Handler
# ============================================================================

class KeyboardController:
    def __init__(self, event_loop):
        self.is_running = False
        self.launched = False
        self.event_loop = event_loop  # Store event loop for async calls
        self._running = True
        self._thread = None

    def _keyboard_loop(self):
        """Background thread that reads keyboard input using readchar"""
        logger.info("Keyboard listener thread started")

        while self._running:
            try:
                # Read single character (blocking)
                key = readchar.readchar()

                logger.info(f"KEY DETECTED: '{key}'")

                # V key - Start/Stop toggle
                if key.lower() == 'v':
                    if not self.launched:
                        # First V key press - launch all stations via SSH
                        logger.info("\n=== LAUNCHING ALL STATIONS VIA SSH ===\n")
                        # Schedule async launch in event loop
                        asyncio.run_coroutine_threadsafe(
                            self._async_launch(),
                            self.event_loop
                        )
                        self.launched = True
                    elif not self.is_running:
                        # Start operation
                        send_start_command()
                        self.is_running = True
                        logger.info("\n=== OPERATION STARTED ===\n")
                    else:
                        # Stop operation
                        send_stop_command()
                        self.is_running = False
                        logger.info("\n=== OPERATION STOPPED ===\n")

            except Exception as e:
                if self._running:
                    logger.error(f"Error handling key press: {e}")

    async def _async_launch(self):
        """Async wrapper for launching stations"""
        await launch_all_stations()
        logger.info("\nAll stations launched and ready!")
        logger.info("Press V again to start operation\n")

    def start(self):
        """Start keyboard listener"""
        self._thread = threading.Thread(target=self._keyboard_loop, daemon=True)
        self._thread.start()
        logger.info("Keyboard listener started")

    def stop(self):
        """Stop keyboard listener"""
        self._running = False
        logger.info("Keyboard listener stopped")

# ============================================================================
# Main
# ============================================================================

async def main():
    logger.info("=" * 70)
    logger.info("Multi-Station Keyboard Controller - Pi 2 Master")
    logger.info("=" * 70)

    # Get event loop
    loop = asyncio.get_event_loop()

    # Initialize OSC clients
    initialize_osc_clients()

    # Start keyboard controller
    controller = KeyboardController(event_loop=loop)
    controller.start()

    logger.info("\n" + "=" * 70)
    logger.info("Keyboard Controls:")
    if USE_LOCAL_LAUNCH:
        logger.info("  V key (first press) - Launch stations LOCALLY (testing mode)")
    else:
        logger.info("  V key (first press) - Launch all stations via SSH")
    logger.info("  V key (after launch) - Toggle start/stop operation")
    logger.info("  Ctrl+C - Exit")
    logger.info("=" * 70)

    if USE_LOCAL_LAUNCH:
        logger.info("\n⚙️  LOCAL TESTING MODE - Will run main.py as subprocess")
        logger.info("   Set USE_LOCAL_LAUNCH = False for production SSH mode\n")
    else:
        logger.info("\n⚙️  SSH MODE - Ensure SSH keys are set up!")
        logger.info("   Run: ssh-copy-id pi@pi-controller-XX.local\n")

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected - shutting down")
        controller.stop()
        logger.info("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
