#!/usr/bin/env python3
"""
Oriental Motor CVD Controller - Station 2 (Master)
State-machine based flow with keyboard control

Flow:
  BOOT → HOMING → READY → START → RUNNING → FINISHED → READY
            ↑                                     ↓
            └───────────── RESET ────────────────┘
"""

import sys
import signal
import asyncio
import logging

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

from services.motor_controller import MotorController
from services.sequence_manager import SequenceManager
from services.network_sync import NetworkSync
from services.keyboard_handler import KeyboardHandler

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

STATION_CONFIG = {
    "station_id": "02",
    "station_name": "工程2 (Master)",

    "serial": {
        "port": "/dev/ttyUSB0",  # Change for your setup
        "baudrate": 230400,
        "parity": "N",
        "stopbits": 1
    },

    "motors": [
        {
            "name": "motor_1",
            "slave_id": 1,
            "type": "CVD-28-KR"
        }
    ],

    "keyboard": {
        "enabled": True,
        "gpio": {
            "start_button": 17,
            "stop_button": 27,
            "reset_button": 22
        }
    },

    "network": {
        "listen_port": 9000,
        "send_port": 9001,
        "is_sender": True,
        "target_ips": [
            # Add other station IPs here
            # "192.168.10.11",
            # "192.168.10.12",
            # etc.
        ],
        "video_player_ip": "127.0.0.1",  # Video player on same Pi
        "video_player_port": 9002
    }
}


# ============================================================================
# Global References
# ============================================================================

motor_controller = None
sequence_manager = None
network_sync = None
keyboard_handler = None


# ============================================================================
# Signal Handlers
# ============================================================================

def shutdown(signum, frame):
    """Clean shutdown on SIGTERM/SIGINT"""
    logger.info("Shutting down...")

    if motor_controller:
        motor_controller.stop()
        motor_controller.close()

    if network_sync:
        network_sync.stop()

    if keyboard_handler:
        keyboard_handler.close()

    logger.info("Shutdown complete")
    sys.exit(0)


# ============================================================================
# Main
# ============================================================================

async def main():
    global motor_controller, sequence_manager, network_sync, keyboard_handler

    logger.info("=" * 70)
    logger.info("Oriental Motor CVD Controller - Station 2 (Master)")
    logger.info("=" * 70)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # ========================================================================
    # Initialize Network Sync
    # ========================================================================
    logger.info("\n[1/4] Initializing network sync...")
    network_sync = NetworkSync(STATION_CONFIG)
    network_sync.start_listener()

    # ========================================================================
    # Initialize Motor Controller
    # ========================================================================
    logger.info("\n[2/4] Initializing motor controller...")

    motor_controller = MotorController(
        config=STATION_CONFIG,
        on_ready=None,  # Will be set by sequence_manager
        on_finished=None,
        on_error=None
    )

    # ========================================================================
    # Initialize Sequence Manager
    # ========================================================================
    logger.info("\n[3/4] Initializing sequence manager...")

    sequence_manager = SequenceManager(
        motor_controller=motor_controller,
        network_sync=network_sync
    )

    # Wire motor callbacks to sequence manager
    motor_controller._on_ready = sequence_manager.on_motor_ready
    motor_controller._on_finished = sequence_manager.on_motor_finished
    motor_controller._on_error = sequence_manager.on_motor_error

    # Wire network callbacks to sequence manager
    network_sync.set_on_start(sequence_manager.on_network_start)
    network_sync.set_on_stop(sequence_manager.on_network_stop)
    network_sync.set_on_reset(lambda: asyncio.create_task(sequence_manager.on_network_reset()))

    # ========================================================================
    # Initialize Keyboard Handler
    # ========================================================================
    logger.info("\n[4/4] Initializing keyboard (3-key GPIO)...")

    try:
        keyboard_handler = KeyboardHandler(STATION_CONFIG)

        # Wire keyboard to sequence manager
        keyboard_handler.set_on_start(sequence_manager.on_start_pressed)
        keyboard_handler.set_on_stop(sequence_manager.on_stop_pressed)
        keyboard_handler.set_on_reset(lambda: asyncio.create_task(sequence_manager.on_reset_pressed()))

        logger.info("✓ Keyboard handler initialized")

    except Exception as e:
        logger.warning(f"Keyboard not available: {e}")
        keyboard_handler = None

    # ========================================================================
    # System Boot - Auto Homing
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("SYSTEM BOOT - Starting Initialization")
    logger.info("=" * 70)

    await sequence_manager.initialize()

    # ========================================================================
    # Main Loop
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("System Ready - Waiting for Commands")
    logger.info("=" * 70)
    logger.info("\nKeyboard Controls:")
    logger.info("  START button  - Start operation")
    logger.info("  STOP button   - Emergency stop")
    logger.info("  RESET button  - Reset to home")
    logger.info("\nPress Ctrl+C to exit")
    logger.info("=" * 70 + "\n")

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected")
        shutdown(signal.SIGINT, None)


if __name__ == "__main__":
    asyncio.run(main())
