#!/usr/bin/env python3
"""
Oriental Motor CVD Controller - Main Entry Point
Works on all stations - config file defines station-specific settings

Usage:
    python main.py --station 02
    python main.py --station prologue
    python main.py --station epilogue
"""

import sys
import signal
import asyncio
import logging
import argparse
import json
import os

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
# Configuration Loading
# ============================================================================

def load_config(station_id):
    """Load station config from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', f'station_{station_id}.json')

    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    logger.info(f"Loaded config: {config_path}")
    return config


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

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Oriental Motor CVD Controller')
    parser.add_argument('--station', type=str, required=True,
                        help='Station ID (e.g., 02, 04, prologue, epilogue)')
    args = parser.parse_args()

    # Load station config
    config = load_config(args.station)

    logger.info("=" * 70)
    logger.info(f"Oriental Motor CVD Controller - {config.get('station_name', f'Station {args.station}')}")
    logger.info("=" * 70)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # ========================================================================
    # Initialize Network Sync
    # ========================================================================
    logger.info("\n[1/4] Initializing network sync...")
    network_sync = NetworkSync(config)
    network_sync.start_listener()

    # ========================================================================
    # Initialize Motor Controller (if motors configured)
    # ========================================================================
    if config.get('motors') and len(config['motors']) > 0:
        logger.info("\n[2/4] Initializing motor controller...")

        motor_controller = MotorController(
            config=config,
            on_ready=None,  # Will be set by sequence_manager
            on_finished=None,
            on_error=None
        )
    else:
        logger.info("\n[2/4] No motors configured - skipping motor controller")
        motor_controller = None

    # ========================================================================
    # Initialize Sequence Manager
    # ========================================================================
    logger.info("\n[3/4] Initializing sequence manager...")

    sequence_manager = SequenceManager(
        motor_controller=motor_controller,
        network_sync=network_sync
    )

    # Wire motor callbacks to sequence manager (if motor exists)
    if motor_controller:
        motor_controller._on_ready = sequence_manager.on_motor_ready
        motor_controller._on_finished = sequence_manager.on_motor_finished
        motor_controller._on_error = sequence_manager.on_motor_error

    # Wire network callbacks to sequence manager
    network_sync.set_on_start(sequence_manager.on_network_start)
    network_sync.set_on_stop(sequence_manager.on_network_stop)
    network_sync.set_on_reset(lambda: asyncio.create_task(sequence_manager.on_network_reset()))

    # ========================================================================
    # Initialize Keyboard Handler (if enabled in config)
    # ========================================================================
    if config.get('keyboard', {}).get('enabled'):
        logger.info("\n[4/4] Initializing keyboard (3-key GPIO)...")

        try:
            keyboard_handler = KeyboardHandler(config)

            # Wire keyboard to sequence manager
            keyboard_handler.set_on_start(sequence_manager.on_start_pressed)
            keyboard_handler.set_on_stop(sequence_manager.on_stop_pressed)
            keyboard_handler.set_on_reset(lambda: asyncio.create_task(sequence_manager.on_reset_pressed()))

            logger.info("✓ Keyboard handler initialized")

        except Exception as e:
            logger.warning(f"Keyboard not available: {e}")
            keyboard_handler = None
    else:
        logger.info("\n[4/4] Keyboard not enabled in config - skipping")
        keyboard_handler = None

    # ========================================================================
    # System Boot - Auto Homing (only if motors exist)
    # ========================================================================
    if motor_controller:
        logger.info("\n" + "=" * 70)
        logger.info("SYSTEM BOOT - Starting Initialization")
        logger.info("=" * 70)

        await sequence_manager.initialize()
    else:
        logger.info("\n" + "=" * 70)
        logger.info("SYSTEM READY (No motors to initialize)")
        logger.info("=" * 70)

    # ========================================================================
    # Main Loop
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("System Ready - Waiting for Commands")
    logger.info("=" * 70)

    if keyboard_handler:
        logger.info("\nKeyboard Controls:")
        logger.info("  START button  - Start operation")
        logger.info("  STOP button   - Emergency stop")
        logger.info("  RESET button  - Reset to home")
    else:
        logger.info("\nListening for OSC commands from master station")

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
