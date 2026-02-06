#!/usr/bin/env python3
"""
Test Station 2 without GPIO (for Mac/dev machine testing)
Uses keyboard input instead of GPIO buttons

Prerequisites:
- CVD driver connected via USB-RS485 adapter
- MEXE operation 0 programmed
- Update COM_PORT below
"""

import sys
import os
import asyncio
import logging

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

from services.motor_controller import MotorController
from services.sequence_manager import SequenceManager
from services.network_sync import NetworkSync
import readchar

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG - EDIT THIS
# ============================================================================

# Find your port with: ls /dev/tty.* (Mac) or ls /dev/ttyUSB* (Linux) or Device Manager (Windows)
# Mac example: /dev/tty.usbserial-XXXX
# Linux/RPi: /dev/ttyUSB0
# Windows: COM4
COM_PORT = "/dev/tty.usbserial-AB0JVDHO"  # ← CHANGE THIS

TEST_CONFIG = {
    "station_id": "02",
    "serial": {
        "port": COM_PORT,
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
    "network": {
        "listen_port": 9000,
        "send_port": 9001,
        "is_sender": True,
        "target_ips": [],
        "video_player_ip": "127.0.0.1",
        "video_player_port": 9002
    }
}


# ============================================================================
# Main
# ============================================================================

async def keyboard_loop(sequence_manager):
    """
    Keyboard input loop (runs in executor thread).
    """
    logger.info("\n" + "=" * 70)
    logger.info("Keyboard Controls:")
    logger.info("  's' - START")
    logger.info("  't' - STOP")
    logger.info("  'r' - RESET")
    logger.info("  'q' - QUIT")
    logger.info("=" * 70 + "\n")

    while True:
        try:
            key = await asyncio.to_thread(readchar.readchar)

            if key == 's':
                logger.info("\n[KEYBOARD] START pressed")
                sequence_manager.on_start_pressed()

            elif key == 't':
                logger.info("\n[KEYBOARD] STOP pressed")
                sequence_manager.on_stop_pressed()

            elif key == 'r':
                logger.info("\n[KEYBOARD] RESET pressed")
                await sequence_manager.on_reset_pressed()

            elif key == 'q':
                logger.info("\n[KEYBOARD] QUIT")
                break

        except KeyboardInterrupt:
            break


async def main():
    logger.info("=" * 70)
    logger.info("Station 2 Test (No GPIO - Keyboard Input)")
    logger.info("=" * 70)

    # Initialize components
    logger.info("\nInitializing...")

    network_sync = NetworkSync(TEST_CONFIG)
    network_sync.start_listener()

    motor_controller = MotorController(
        config=TEST_CONFIG,
        on_ready=None,
        on_finished=None,
        on_error=None
    )

    sequence_manager = SequenceManager(
        motor_controller=motor_controller,
        network_sync=network_sync
    )

    # Wire callbacks
    motor_controller._on_ready = sequence_manager.on_motor_ready
    motor_controller._on_finished = sequence_manager.on_motor_finished
    motor_controller._on_error = sequence_manager.on_motor_error

    # System boot - auto homing
    logger.info("\n" + "=" * 70)
    logger.info("SYSTEM BOOT - Starting Auto-Homing")
    logger.info("=" * 70)

    await sequence_manager.initialize()

    # Start keyboard input loop
    try:
        await keyboard_loop(sequence_manager)
    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected")

    # Cleanup
    logger.info("\nShutting down...")
    motor_controller.stop()
    motor_controller.close()
    network_sync.stop()
    logger.info("Done")


if __name__ == "__main__":
    asyncio.run(main())
