"""
Sequence Manager - Master brain for Pi-02
Receives keyboard input, sends OSC to all stations, receives status from all stations.
Coordinates system-wide operations.
"""

import logging
import threading
import json

try:
    from pythonosc import udp_client
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import BlockingOSCUDPServer
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

logger = logging.getLogger(__name__)


class SequenceManager:
    """
    Master sequence manager for Pi-02.
    Coordinates all stations via OSC.
    """

    def __init__(self, config):
        """
        Initialize sequence manager.

        Args:
            config: Full config dict with all_stations info
        """
        self.config = config
        self.station_id = config.get('station_id', '02')

        # Load all stations config
        self.all_stations = self._load_all_stations()

        # Track state of all stations
        self.station_states = {}
        for station_id in self.all_stations:
            self.station_states[station_id] = "unknown"

        # System state
        self.is_running = False
        self.is_resetting = False

        # OSC clients for sending to stations
        self.osc_clients = {}
        if OSC_AVAILABLE:
            self._init_osc_clients()

        # OSC server for receiving status
        self.server = None
        self.server_thread = None
        if OSC_AVAILABLE:
            self._init_osc_server()

        # Callback to local motor controller
        self._local_motor_controller = None

        logger.info(f"Sequence manager initialized for {len(self.all_stations)} stations")

    def _load_all_stations(self):
        """Load all stations config"""
        try:
            with open('config/all_stations.json', 'r') as f:
                data = json.load(f)
                return data.get('stations', {})
        except Exception as e:
            logger.error(f"Failed to load all_stations.json: {e}")
            return {}

    def _init_osc_clients(self):
        """Create OSC clients for all stations"""
        for station_id, station_config in self.all_stations.items():
            host = station_config.get('host', f'pi-controller-{station_id}.local')
            port = station_config.get('osc_port', 10000)

            try:
                client = udp_client.SimpleUDPClient(host, port)
                self.osc_clients[station_id] = client
                logger.info(f"OSC client for station {station_id}: {host}:{port}")
            except Exception as e:
                logger.error(f"Failed to create OSC client for station {station_id}: {e}")

    def _init_osc_server(self):
        """Initialize OSC server for receiving status from all stations"""
        listen_port = self.config.get('network', {}).get('listen_port', 10000)

        dispatcher = Dispatcher()
        dispatcher.map("/status", self._handle_status)
        # Also handle commands sent to self (Pi-02)
        dispatcher.map("/start", self._handle_start_osc)
        dispatcher.map("/stop", self._handle_stop_osc)
        dispatcher.map("/reset", self._handle_reset_osc)

        try:
            self.server = BlockingOSCUDPServer(("0.0.0.0", listen_port), dispatcher)
            logger.info(f"OSC server listening on port {listen_port} (status + commands)")
        except Exception as e:
            logger.error(f"Failed to create OSC server: {e}")

    def _handle_start_osc(self, address, *args):
        """Handle /start OSC for local motor controller"""
        if self._local_motor_controller:
            self._local_motor_controller.on_start()

    def _handle_stop_osc(self, address, *args):
        """Handle /stop OSC for local motor controller"""
        if self._local_motor_controller:
            self._local_motor_controller.on_stop()

    def _handle_reset_osc(self, address, *args):
        """Handle /reset OSC for local motor controller"""
        if self._local_motor_controller:
            self._local_motor_controller.on_reset()

    def start_server(self):
        """Start OSC server in background thread"""
        if not self.server:
            return

        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )
        self.server_thread.start()
        logger.info("OSC status server started")

    def stop_server(self):
        """Stop OSC server"""
        if self.server:
            self.server.shutdown()

    def set_local_motor_controller(self, controller):
        """Set reference to local motor controller"""
        self._local_motor_controller = controller

    # ========================================================================
    # Keyboard Input Handlers (called by key.py)
    # ========================================================================

    def on_start_pressed(self):
        """V key pressed when stopped - start all stations"""
        if self.is_resetting:
            logger.warning("Ignoring START - reset in progress")
            return

        if self.is_running:
            logger.warning("Already running")
            return

        logger.info("=" * 70)
        logger.info("START PRESSED - Sending /start to all stations")
        logger.info("=" * 70)

        self.is_running = True
        self._send_to_all("/start")

    def on_stop_pressed(self):
        """V key pressed when running - stop all stations"""
        logger.info("=" * 70)
        logger.info("STOP PRESSED - Sending /stop to all stations")
        logger.info("=" * 70)

        self.is_running = False
        self._send_to_all("/stop")

    def on_reset_pressed(self):
        """Ctrl+V pressed - reset all stations (stop, home, wait)"""
        logger.info("=" * 70)
        logger.info("RESET PRESSED - Sending /reset to all stations")
        logger.info("=" * 70)

        self.is_running = False
        self.is_resetting = True
        self._send_to_all("/reset")

    def get_is_running(self):
        """Check if system is running (for V key toggle)"""
        return self.is_running

    # ========================================================================
    # OSC Send
    # ========================================================================

    def _send_to_all(self, command):
        """Send OSC command to all stations"""
        for station_id, client in self.osc_clients.items():
            try:
                client.send_message(command, [])
                logger.info(f"  Sent {command} to station {station_id}")
            except Exception as e:
                logger.error(f"  Failed to send {command} to station {station_id}: {e}")

    # ========================================================================
    # OSC Receive (Status from stations)
    # ========================================================================

    def _handle_status(self, address, *args):
        """Handle /status [station_id] [state] from stations"""
        if len(args) < 2:
            return

        station_id = str(args[0])
        state = str(args[1])

        old_state = self.station_states.get(station_id, "unknown")
        self.station_states[station_id] = state

        if old_state != state:
            logger.info(f"Station {station_id}: {old_state} -> {state}")
            # Log summary when state changes
            self._log_status_summary()

        # Check if all stations homed (after reset)
        if self.is_resetting:
            if self._check_all_stations_homed():
                logger.info("=" * 70)
                logger.info("All stations HOME_END - Reset complete, waiting for V")
                logger.info("=" * 70)
                self.is_resetting = False

    def _log_status_summary(self):
        """Log a summary of all station states grouped by state"""
        # Group stations by state
        by_state = {}
        for sid, state in self.station_states.items():
            if state not in by_state:
                by_state[state] = []
            by_state[state].append(sid)

        # Build summary line
        parts = []
        for state in ['homing', 'resetting', 'error', 'home_end', 'running', 'ready', 'unknown', 'disconnected']:
            if state in by_state:
                stations = ','.join(sorted(by_state[state]))
                parts.append(f"{state.upper()}:[{stations}]")

        if parts:
            logger.info(f"  Status: {' | '.join(parts)}")

    def _check_all_stations_homed(self):
        """Check if all stations are in HOME_END state"""
        for station_id, state in self.station_states.items():
            if state != "home_end":
                return False
        return True

    def get_all_station_states(self):
        """Get dictionary of all station states"""
        return self.station_states.copy()

    # ========================================================================
    # Status
    # ========================================================================

    def get_status_summary(self):
        """Get summary of all station states"""
        summary = []
        for station_id, state in sorted(self.station_states.items()):
            summary.append(f"{station_id}:{state}")
        return " | ".join(summary)
