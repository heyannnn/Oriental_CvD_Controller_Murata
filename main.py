#!/usr/bin/env python3
"""
Oriental Motor CVD Controller - Main Entry Point
Works on all stations - config/local.json defines which station this Pi is

Usage:
    python main.py

Configuration:
    - config/local.json: Defines which station this Pi is
    - config/network_master.json: Defines keyboard/master controller settings
    - config/all_stations.json: All station motor configurations
"""

import sys
import signal
import asyncio
import logging
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

def deep_merge(base, override):
    """Deep merge two dictionaries (override takes precedence)"""
    result = base.copy()
    for key, value in override.items():
        if key.startswith('_'):  # Skip comments
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_local_config():
    """Load local.json to determine which station this Pi is"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(script_dir, 'config', 'local.json')

    if not os.path.exists(local_path):
        logger.error(f"Local config not found: {local_path}")
        logger.error("Please create config/local.json with your station_id")
        sys.exit(1)

    with open(local_path, 'r') as f:
        return json.load(f)


def load_network_master_config():
    """Load network_master.json to see if this Pi controls others"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    master_path = os.path.join(script_dir, 'config', 'network_master.json')

    if not os.path.exists(master_path):
        # If no network master config, return disabled
        return {'enabled': False, 'keyboard': {'enabled': False}}

    with open(master_path, 'r') as f:
        return json.load(f)


def load_station_config(station_id):
    """
    Load station configuration from all_stations.json

    Loads:
      1. config/all_stations.json['default'] (shared settings)
      2. config/all_stations.json[station_id] (station-specific)
      3. Merges default + station-specific
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    all_stations_path = os.path.join(script_dir, 'config', 'all_stations.json')

    if not os.path.exists(all_stations_path):
        logger.error(f"Stations config not found: {all_stations_path}")
        sys.exit(1)

    with open(all_stations_path, 'r') as f:
        all_stations = json.load(f)

    # Get default config
    default_config = all_stations.get('default', {})

    # Get station-specific config
    if station_id not in all_stations:
        logger.error(f"Station '{station_id}' not found in all_stations.json")
        logger.error(f"Available stations: {', '.join([k for k in all_stations.keys() if not k.startswith('_') and k != 'default'])}")
        sys.exit(1)

    station_config = all_stations[station_id]

    # Merge default + station-specific
    config = deep_merge(default_config, station_config)
    config['station_id'] = station_id

    logger.info(f"Loaded station config: all_stations.json['{station_id}']")
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

    # Store event loop reference for keyboard callbacks
    loop = asyncio.get_event_loop()

    # Load local configuration (which station am I?)
    local_config = load_local_config()
    station_id = local_config.get('station_id')

    if not station_id:
        logger.error("station_id not found in config/local.json")
        sys.exit(1)

    # Load station configuration
    config = load_station_config(station_id)

    # Load network master configuration (separate from station)
    network_master_config = load_network_master_config()

    # Apply network master settings if enabled
    if network_master_config.get('enabled'):
        config['network']['is_sender'] = True
        # Build target IPs from station list
        target_stations = network_master_config.get('target_stations', [])
        config['network']['target_ips'] = [
            f"pi-controller-{s}.local" for s in target_stations
        ]
        # Apply keyboard settings from master config
        if network_master_config.get('keyboard', {}).get('enabled'):
            config['keyboard'] = network_master_config['keyboard']

        logger.info("Network master mode: ENABLED (this Pi controls others)")
    else:
        config['network']['is_sender'] = False
        logger.info("Network master mode: DISABLED (listening for commands)")

    logger.info("=" * 70)
    logger.info(f"Oriental Motor CVD Controller - {config.get('station_name', f'Station {station_id}')}")
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
        network_sync=network_sync,
        config=config
    )

    # Wire motor callbacks to sequence manager (if motor exists)
    if motor_controller:
        motor_controller._on_ready = sequence_manager.on_motor_ready
        motor_controller._on_finished = sequence_manager.on_motor_finished
        motor_controller._on_error = sequence_manager.on_motor_error
        motor_controller._on_return_to_zero_complete = sequence_manager.on_return_to_zero_complete

    # Wire network callbacks to sequence manager
    network_sync.set_on_start(sequence_manager.on_network_start)
    network_sync.set_on_stop(sequence_manager.on_network_stop)
    network_sync.set_on_reset(lambda: asyncio.create_task(sequence_manager.on_network_reset()))
    network_sync.set_on_clear_alarm(sequence_manager.on_clear_alarm_pressed)

    # ========================================================================
    # Initialize Keyboard Handler (if enabled in config)
    # ========================================================================
    if config.get('keyboard', {}).get('enabled'):
        keyboard_type = config.get('keyboard', {}).get('type', 'usb')
        logger.info(f"\n[4/4] Initializing keyboard ({keyboard_type})...")

        try:
            keyboard_handler = KeyboardHandler(config)

            # Wire keyboard to sequence manager
            # Note: Keyboard callbacks run in separate thread, need to schedule in main loop
            keyboard_handler.set_on_start(sequence_manager.on_start_pressed)
            keyboard_handler.set_on_stop(sequence_manager.on_stop_pressed)
            keyboard_handler.set_on_clear_alarm(sequence_manager.on_clear_alarm_pressed)

            # Reset is async, so schedule it in the main event loop
            def on_reset_wrapper():
                asyncio.run_coroutine_threadsafe(sequence_manager.on_reset_pressed(), loop)

            keyboard_handler.set_on_reset(on_reset_wrapper)

            logger.info("✓ USB keyboard handler initialized")

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
        logger.info("\nUSB Keyboard Controls:")
        logger.info("  V key   - Toggle start/stop operation")
        logger.info("  C key   - Enter standby mode (return to home)")
        logger.info("  Ctrl    - Clear motor alarm")
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
