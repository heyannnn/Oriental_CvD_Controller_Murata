#!/usr/bin/env python3
"""
Oriental Motor CVD Controller - Main Entry Point
Works on all stations - config/local.json defines which station this Pi is

Usage:
    python main.py

Configuration:
    - config/local.json: Defines which station this Pi is (only difference per Pi)
    - config/all_stations.json: All station configurations (same on all Pis)

Station 02 (Master):
    - Also launches key.py and sequence_manager for keyboard control
    - Sends OSC commands to all stations
    - Receives status from all stations

Stations 03-11:
    - Receives OSC commands from master
    - Sends status back to master
    - Controls local motors and video
"""

import sys
import signal
import asyncio
import logging
import json
import os
import threading

# Setup logging - will add file handler after we know station_id
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


def setup_file_logging(station_id):
    """Add file logging to /tmp/main_XX.log"""
    log_file = f"/tmp/main_{station_id}.log"
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    ))
    logging.getLogger().addHandler(file_handler)
    logger.info(f"Logging to {log_file}")


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


def load_station_config(station_id):
    """
    Load station configuration from all_stations.json

    Loads:
      1. config/all_stations.json['default'] (shared settings)
      2. config/all_stations.json['stations'][station_id] (station-specific)
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

    # Get stations dict
    stations = all_stations.get('stations', all_stations)

    # Get station-specific config
    if station_id not in stations:
        logger.error(f"Station '{station_id}' not found in all_stations.json")
        available = [k for k in stations.keys() if not k.startswith('_') and k != 'default']
        logger.error(f"Available stations: {', '.join(available)}")
        sys.exit(1)

    station_config = stations[station_id]

    # Merge default + station-specific
    config = deep_merge(default_config, station_config)
    config['station_id'] = station_id

    logger.info(f"Loaded config for station {station_id}")
    return config


# ============================================================================
# Global References
# ============================================================================

motor_controller = None
sequence_manager = None
keyboard_controller = None


# ============================================================================
# Signal Handlers
# ============================================================================

def shutdown(signum, frame):
    """Clean shutdown on SIGTERM/SIGINT"""
    logger.info("Shutting down...")

    if motor_controller:
        motor_controller.stop()
        motor_controller.close()

    if sequence_manager:
        sequence_manager.stop_server()

    if keyboard_controller:
        keyboard_controller.stop()

    logger.info("Shutdown complete")
    sys.exit(0)


# ============================================================================
# Video-Only Controller (for stations without motors, like station 11)
# ============================================================================

class VideoOnlyController:
    """Simple controller for video-only stations (station 11)

    on_start: sends NormalOperation.csv (video player will loop it)
    on_stop/on_reset: sends Waiting.csv
    """

    def __init__(self, config):
        self.config = config
        self.station_id = config.get('station_id', '00')
        self.state = "home_end"  # Always ready

        # Video player
        from services.mp4_player import MP4Player
        self.mp4_player = MP4Player(config)

        # OSC client for sending status to master
        self.master_ip = config.get('network', {}).get('master_ip', '192.168.1.2')
        self.master_port = config.get('network', {}).get('master_port', 10000)
        self.status_client = None

        try:
            from pythonosc import udp_client
            self.status_client = udp_client.SimpleUDPClient(self.master_ip, self.master_port)
        except Exception as e:
            logger.warning(f"Could not create status client: {e}")

        logger.info(f"Video-only controller initialized (station {self.station_id})")

    def _send_status(self):
        """Send status to master"""
        if self.status_client:
            try:
                self.status_client.send_message("/status", [self.station_id, self.state])
                logger.debug(f"Sent status: {self.state}")
            except Exception as e:
                logger.warning(f"Failed to send status: {e}")

    def on_start(self):
        logger.info("=== START RECEIVED (video only) ===")
        self.state = "running"
        self.mp4_player.send_command("start")  # Plays NormalOperation.csv (looped by video player)
        self._send_status()

    def on_stop(self):
        logger.info("=== STOP RECEIVED (video only) ===")
        self.state = "home_end"
        self.mp4_player.send_command("stop")  # Plays Waiting.csv
        self._send_status()

    def on_reset(self):
        logger.info("=== RESET RECEIVED (video only) ===")
        self.state = "home_end"
        self.mp4_player.send_command("stop")  # Plays Waiting.csv
        self._send_status()

    async def initialize(self):
        """Wait for boot sync, then send initial status to master"""
        # Send "booting" status immediately so master knows we exist
        self._send_status_value("booting")

        # Wait 5 seconds on boot to let all stations power up and master to start listening
        logger.info("Waiting 5 seconds for all stations to boot...")
        await asyncio.sleep(5.0)
        self._send_status()

    def _send_status_value(self, status_value):
        """Send specific status value to master"""
        if self.status_client:
            try:
                self.status_client.send_message("/status", [self.station_id, status_value])
                logger.debug(f"Sent status: {status_value}")
            except Exception as e:
                logger.warning(f"Failed to send status: {e}")

    def stop(self):
        pass

    def close(self):
        pass


# ============================================================================
# OSC Listener for receiving commands
# ============================================================================

def setup_osc_listener(config, controller, led_controller=None):
    """Setup OSC listener for receiving /start, /stop, /reset commands"""
    try:
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import BlockingOSCUDPServer
    except ImportError:
        logger.warning("python-osc not available, OSC disabled")
        return None

    listen_port = config.get('network', {}).get('listen_port', 10000)

    dispatcher = Dispatcher()

    # Map OSC commands to controller methods (motor or video-only)
    def handle_start(address, *args):
        logger.info("Received /start via OSC")
        if controller:
            controller.on_start()

    def handle_stop(address, *args):
        logger.info("Received /stop via OSC")
        if controller:
            controller.on_stop()

    def handle_reset(address, *args):
        logger.info("Received /reset via OSC")
        if controller:
            controller.on_reset()

    dispatcher.map("/start", handle_start)
    dispatcher.map("/stop", handle_stop)
    dispatcher.map("/reset", handle_reset)

    # LED indicator commands (station 07 only)
    if led_controller:
        def handle_led_homing(address, *args):
            logger.info("Received /led/homing via OSC")
            led_controller.start_homing_indicator()

        def handle_led_ready(address, *args):
            logger.info("Received /led/ready via OSC")
            led_controller.show_ready()

        def handle_led_off(address, *args):
            logger.info("Received /led/off via OSC")
            led_controller.stop_indicator()

        dispatcher.map("/led/homing", handle_led_homing)
        dispatcher.map("/led/ready", handle_led_ready)
        dispatcher.map("/led/off", handle_led_off)

    try:
        server = BlockingOSCUDPServer(("0.0.0.0", listen_port), dispatcher)
        logger.info(f"OSC listener on port {listen_port}")

        # Start server in background thread
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        return server
    except Exception as e:
        logger.error(f"Failed to start OSC listener: {e}")
        return None


# ============================================================================
# Main
# ============================================================================

async def main():
    global motor_controller, sequence_manager, keyboard_controller

    # Load local configuration (which station am I?)
    local_config = load_local_config()
    station_id = local_config.get('station_id')

    if not station_id:
        logger.error("station_id not found in config/local.json")
        sys.exit(1)

    # Setup file logging to /tmp/main_XX.log
    setup_file_logging(station_id)

    # Load station configuration
    config = load_station_config(station_id)

    # Check if this is the master station (Pi-02)
    is_master = (station_id == "02")

    logger.info("=" * 70)
    logger.info(f"Oriental Motor CVD Controller - {config.get('station_name', f'Station {station_id}')}")
    if is_master:
        logger.info("*** MASTER STATION - Keyboard Control Enabled ***")
    logger.info("=" * 70)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C

    # ========================================================================
    # Initialize Controller (motor or video-only)
    # ========================================================================
    if config.get('motors') and len(config['motors']) > 0:
        from services.motor_controller import MotorController
        logger.info("\n[1/3] Initializing motor controller...")
        motor_controller = MotorController(config=config)
    else:
        logger.info("\n[1/3] No motors - using video-only controller")
        motor_controller = VideoOnlyController(config=config)

    # ========================================================================
    # Initialize OSC Listener (all stations receive commands)
    # For Pi-02 (master), sequence_manager handles OSC instead
    # ========================================================================
    if is_master:
        logger.info("\n[2/3] Skipping OSC listener (master uses sequence_manager)")
        osc_server = None
    else:
        logger.info("\n[2/3] Initializing OSC listener...")
        # Get LED controller for station 07 (for homing indicator)
        led_controller_for_osc = None
        if station_id == "07" and hasattr(motor_controller, 'led_controller'):
            led_controller_for_osc = motor_controller.led_controller
        osc_server = setup_osc_listener(config, motor_controller, led_controller_for_osc)

    # ========================================================================
    # Initialize Master Components (Pi-02 only)
    # ========================================================================
    if is_master:
        logger.info("\n[3/3] Initializing master components (keyboard + sequence manager)...")

        # Import master-only components
        from key import KeyboardController
        from services.sequence_manager import SequenceManager

        # Create sequence manager (handles both sending commands AND receiving status)
        sequence_manager = SequenceManager(config=config)
        sequence_manager.set_local_motor_controller(motor_controller)
        sequence_manager.start_server()

        # Create keyboard controller
        try:
            keyboard_controller = KeyboardController()
            keyboard_controller.set_on_start(sequence_manager.on_start_pressed)
            keyboard_controller.set_on_stop(sequence_manager.on_stop_pressed)
            keyboard_controller.set_on_reset(sequence_manager.on_reset_pressed)
            keyboard_controller.set_get_is_running(sequence_manager.get_is_running)
            keyboard_controller.start()
            logger.info("  Keyboard controller initialized")
        except Exception as e:
            logger.warning(f"  Keyboard not available: {e}")
            keyboard_controller = None

    else:
        logger.info("\n[3/3] Not master - skipping keyboard/sequence manager")

    # ========================================================================
    # System Boot - Initialize Motors
    # ========================================================================
    if motor_controller:
        logger.info("\n" + "=" * 70)
        logger.info("SYSTEM BOOT - Initializing Motors")
        logger.info("=" * 70)

        await motor_controller.initialize()
    else:
        logger.info("\n" + "=" * 70)
        logger.info("SYSTEM BOOT (No motors)")
        logger.info("=" * 70)

    # ========================================================================
    # Main Loop
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("System Ready - Waiting for Commands")
    logger.info("=" * 70)

    if is_master and keyboard_controller:
        logger.info("\nKeyboard Controls:")
        logger.info("  V key    - Toggle start/stop")
        logger.info("  Ctrl+V   - Reset (stop, home, wait)")
        logger.info("  Ctrl+C   - Exit")
    else:
        logger.info("\nListening for OSC commands from master (Pi-02)")

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
