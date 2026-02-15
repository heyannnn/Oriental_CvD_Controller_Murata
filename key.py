#!/usr/bin/env python3
"""
Keyboard Control Script for Multi-Station System
Runs on master Pi (Pi-02) to control all stations via OSC

Usage:
    python key.py

Controls:
    V key - Start/Stop toggle
    Ctrl+any - Clear alarm
    Ctrl+C - Exit

This script will:
    1. SSH into all Pis and launch main.py automatically
    2. Wait for all stations to initialize
    3. Listen for keyboard input to send OSC commands

Requirements:
    - sshpass installed: sudo apt install sshpass
    - Network connectivity to all station Pis
"""

import logging
import asyncio
import subprocess
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

# SSH credentials (same for all Pis)
SSH_USER = "user"
SSH_PASSWORD = "fukuimurata"
MAIN_PY_PATH = "/home/user/Desktop/ORIENTAL_CVD_CONTROLLER_MURATA"

# All station hostnames and ports
STATIONS = {
    "02": {"host": "pi-controller-02.local", "port": 10000},
    "03": {"host": "pi-controller-03.local", "port": 10000},
    "04": {"host": "pi-controller-04.local", "port": 10000},
    "05": {"host": "pi-controller-05.local", "port": 10000},
    "06": {"host": "pi-controller-06.local", "port": 10000},
    "07": {"host": "pi-controller-07.local", "port": 10000},
    "08": {"host": "pi-controller-08.local", "port": 10000},
    "09": {"host": "pi-controller-09.local", "port": 10000},
    "10": {"host": "pi-controller-10.local", "port": 10000},
    "11": {"host": "pi-controller-11.local", "port": 10000},
}

# Track SSH processes for cleanup
ssh_processes = []

# ============================================================================
# OSC Clients
# ============================================================================

osc_clients = {}

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


# ============================================================================
# SSH Launch Functions
# ============================================================================

def launch_all_stations():
    """Launch main.py on all stations via SSH"""
    global ssh_processes

    logger.info("=" * 70)
    logger.info("LAUNCHING main.py ON ALL STATIONS")
    logger.info("=" * 70)

    for station_id, config in STATIONS.items():
        host = config["host"]

        try:
            # SSH command to start main.py in background
            # Activate venv first, then run main.py
            # Set DISPLAY=:0 so video player can access the screen
            # Using nohup so it keeps running after SSH disconnects
            ssh_cmd = [
                "sshpass", "-p", SSH_PASSWORD,
                "ssh", "-o", "StrictHostKeyChecking=no",
                f"{SSH_USER}@{host}",
                f"cd {MAIN_PY_PATH} && source venv/bin/activate && export DISPLAY=:0 && nohup python main.py > /tmp/main_{station_id}.log 2>&1 &"
            ]

            logger.info(f"Launching station {station_id} ({host})...")
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            ssh_processes.append(process)
            logger.info(f"✓ Station {station_id} launch command sent")

        except Exception as e:
            logger.error(f"✗ Failed to launch station {station_id}: {e}")

    logger.info("=" * 70)
    logger.info(f"Launch commands sent to {len(STATIONS)} stations")
    logger.info("Waiting 10 seconds for all stations to initialize...")
    logger.info("=" * 70)


def stop_all_stations():
    """Stop main.py and video player on all stations via SSH"""
    logger.info("=" * 70)
    logger.info("STOPPING main.py AND video player ON ALL STATIONS")
    logger.info("=" * 70)

    for station_id, config in STATIONS.items():
        host = config["host"]

        try:
            # SSH command to kill main.py and video player
            ssh_cmd = [
                "sshpass", "-p", SSH_PASSWORD,
                "ssh", "-o", "StrictHostKeyChecking=no",
                f"{SSH_USER}@{host}",
                "pkill -f 'python main.py'; pkill -f 'osc_mpv_playlist'"
            ]

            subprocess.run(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"✓ Station {station_id} stopped")

        except Exception as e:
            logger.error(f"✗ Failed to stop station {station_id}: {e}")

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

def send_clear_alarm_command():
    """Send clear alarm command to all stations"""
    logger.info("=" * 70)
    logger.info("SENDING CLEAR ALARM COMMAND TO ALL STATIONS")
    logger.info("=" * 70)

    for station_id, client in osc_clients.items():
        try:
            client.send_message("/clear_alarm", 1)
            logger.info(f"✓ Clear alarm command sent to station {station_id}")
        except Exception as e:
            logger.error(f"✗ Failed to send clear alarm to station {station_id}: {e}")

# ============================================================================
# Keyboard Handler
# ============================================================================

class KeyboardController:
    def __init__(self):
        self.is_running = False
        self._active = True

    async def handle_keyboard(self):
        """Async keyboard handler using readchar"""
        logger.info("Keyboard listener started")

        while self._active:
            try:
                # Read single character (blocking in executor)
                loop = asyncio.get_event_loop()
                key = await loop.run_in_executor(None, readchar.readchar)

                logger.info(f"KEY DETECTED: '{key}'")

                # V key - Start/Stop toggle
                if key.lower() == 'v':
                    if self.is_running:
                        # Stop operation
                        send_stop_command()
                        self.is_running = False
                        logger.info("\n=== OPERATION STOPPED ===\n")
                    else:
                        # Start operation
                        send_start_command()
                        self.is_running = True
                        logger.info("\n=== OPERATION STARTED ===\n")

                # Ctrl+C - Exit program
                elif key == '\x03':  # Ctrl+C is ASCII 3
                    logger.info("\n=== Ctrl+C detected - Exiting ===\n")
                    self._active = False
                    break

                # Other Ctrl key combinations - Clear alarm
                elif ord(key) < 32 and key != '\r' and key != '\n':
                    logger.info(f"\n=== CLEAR ALARM (Ctrl detected) ===\n")
                    send_clear_alarm_command()

            except Exception as e:
                if self._active:
                    logger.error(f"Error handling key press: {e}")

    def stop(self):
        """Stop keyboard listener"""
        self._active = False
        logger.info("Keyboard listener stopped")

# ============================================================================
# Main
# ============================================================================

async def main():
    logger.info("=" * 70)
    logger.info("Multi-Station Keyboard Controller - Master Pi")
    logger.info("=" * 70)

    # Launch main.py on all stations via SSH
    launch_all_stations()

    # Wait for stations to initialize
    await asyncio.sleep(10)

    # Initialize OSC clients
    initialize_osc_clients()

    logger.info("\n" + "=" * 70)
    logger.info("All stations should now be running!")
    logger.info("=" * 70)

    logger.info("\n" + "=" * 70)
    logger.info("Keyboard Controls:")
    logger.info("  V key - Start/Stop toggle")
    logger.info("  Ctrl+any - Clear alarm on all stations")
    logger.info("  Ctrl+C - Exit and stop all stations")
    logger.info("=" * 70 + "\n")

    # Create keyboard controller
    controller = KeyboardController()

    try:
        # Run keyboard handler
        await controller.handle_keyboard()

    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected - shutting down")

    # Stop all stations when exiting
    controller.stop()
    stop_all_stations()
    logger.info("Shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled in main()
