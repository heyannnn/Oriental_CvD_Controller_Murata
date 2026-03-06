"""
Sequence Manager - Master brain for Pi-02
Receives keyboard input, sends OSC to all stations, receives status from all stations.
Coordinates system-wide operations.
"""

import logging
import threading
import json
import time

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
        self.is_stopping = False  # True until all stations HOME_END after stop
        self.is_booting = True  # True until all stations HOME_END after boot
        self.boot_start_time = None  # Track boot start time for timeout
        self.boot_timeout_sec = 25.0  # Timeout for boot - start anyway after this
        self._boot_timer_thread = None
        self.reset_start_time = None  # Track reset start time for timeout
        self.reset_timeout_sec = 25.0  # Timeout for reset
        self._reset_timer_thread = None
        self.stop_start_time = None  # Track stop start time for timeout
        self.stop_timeout_sec = 25.0  # Timeout for stop
        self._stop_timer_thread = None

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

        # Check if LED homing indicator is enabled for station 07
        station_07_config = self.all_stations.get("07", {})
        led_config = station_07_config.get("led", {})
        self.led_homing_indicator_enabled = led_config.get("homing_indicator", False)

        logger.info(f"Sequence manager initialized for {len(self.all_stations)} stations")
        if self.led_homing_indicator_enabled:
            logger.info("LED homing indicator enabled for station 07")

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
        # Remote keyboard simulation (from deploy.py)
        dispatcher.map("/key/v", self._handle_key_v)
        dispatcher.map("/key/reset", self._handle_key_reset)

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

    def _handle_key_v(self, address, *args):
        """Handle /key/v - simulate V key press (toggle start/stop)"""
        logger.info("Remote: /key/v received (simulating V key)")
        if self.is_running:
            self.on_stop_pressed()
        else:
            self.on_start_pressed()

    def _handle_key_reset(self, address, *args):
        """Handle /key/reset - simulate Ctrl+V press"""
        logger.info("Remote: /key/reset received (simulating Ctrl+V)")
        self.on_reset_pressed()

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
        if self.is_booting:
            logger.warning("Ignoring START - boot homing in progress")
            return

        if self.is_resetting:
            logger.warning("Ignoring START - reset in progress")
            return

        if self.is_stopping:
            logger.warning("Ignoring START - stop in progress")
            return

        if self.is_running:
            logger.warning("Already running")
            return

        logger.info("=" * 70)
        logger.info("START PRESSED - Sending /start to all stations")
        logger.info("=" * 70)

        # Turn off LED indicator before starting
        self._send_led_off()
        self.is_running = True
        self._send_to_all("/start")

    def on_stop_pressed(self):
        """V key pressed when running - stop all stations"""
        logger.info("=" * 70)
        logger.info("STOP PRESSED - Sending /stop to all stations")
        logger.info("=" * 70)

        self.is_running = False
        self.is_stopping = True
        self.stop_start_time = time.time()
        self._send_to_all("/stop")
        # Start LED homing indicator on station 07
        self._send_led_homing()
        # Start stop timeout checker
        self._stop_timer_thread = threading.Thread(target=self._stop_timeout_checker, daemon=True)
        self._stop_timer_thread.start()
        logger.info(f"Stop timer started ({self.stop_timeout_sec}s timeout)")

    def on_reset_pressed(self):
        """Ctrl+V pressed - reset all stations (stop, home, wait)"""
        logger.info("=" * 70)
        logger.info("RESET PRESSED - Sending /reset to all stations")
        logger.info("=" * 70)

        self.is_running = False
        self.is_resetting = True
        self.reset_start_time = time.time()
        self._send_to_all("/reset")
        # Start LED homing indicator on station 07
        self._send_led_homing()
        # Start reset timeout checker
        self._reset_timer_thread = threading.Thread(target=self._reset_timeout_checker, daemon=True)
        self._reset_timer_thread.start()
        logger.info(f"Reset timer started ({self.reset_timeout_sec}s timeout)")

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

    def _send_to_station(self, station_id, command):
        """Send OSC command to a specific station"""
        if station_id in self.osc_clients:
            try:
                self.osc_clients[station_id].send_message(command, [])
                logger.info(f"  Sent {command} to station {station_id}")
            except Exception as e:
                logger.error(f"  Failed to send {command} to station {station_id}: {e}")

    def _send_led_homing(self):
        """Tell LED 07 to show homing indicator (blinking BLUE)"""
        if not self.led_homing_indicator_enabled:
            return
        self._send_to_station("07", "/led/homing")

    def _send_led_ready(self):
        """Tell LED 07 to show ready indicator (solid GREEN)"""
        if not self.led_homing_indicator_enabled:
            return
        self._send_to_station("07", "/led/ready")

    def _send_led_off(self):
        """Tell LED 07 to turn off indicator"""
        if not self.led_homing_indicator_enabled:
            return
        self._send_to_station("07", "/led/off")

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

        # Check if all stations homed (after stop)
        if self.is_stopping:
            if self._check_all_stations_homed():
                self._do_stop_complete()

        # Check if all stations homed (after reset)
        if self.is_resetting:
            if self._check_all_stations_homed():
                self._do_reset_complete()

        # Check if all stations homed (after boot) - auto-start
        if self.is_booting:
            # Start boot timer when first status received
            if self.boot_start_time is None:
                self.boot_start_time = time.time()
                logger.info(f"Boot timer started ({self.boot_timeout_sec}s timeout)")
                # Start background timer thread
                self._boot_timer_thread = threading.Thread(target=self._boot_timeout_checker, daemon=True)
                self._boot_timer_thread.start()

            # Start LED homing indicator when station 07 first reports (meaning it's ready to receive)
            if station_id == "07" and old_state == "unknown":
                self._send_led_homing()

            if self._check_all_stations_homed():
                self._do_boot_complete()

    def _do_boot_complete(self):
        """Handle boot complete - all stations HOME_END"""
        if not self.is_booting:
            return
        logger.info("=" * 70)
        logger.info("All stations HOME_END - Boot complete")
        logger.info("=" * 70)
        self.is_booting = False
        # Show green LED for 2 seconds, then start
        self._send_led_ready()
        logger.info("Showing GREEN for 2 seconds before auto-start...")
        # Start in background thread to not block OSC handler
        threading.Thread(target=self._delayed_auto_start, daemon=True).start()

    def _delayed_auto_start(self):
        """Wait 2 seconds showing green, then start"""
        time.sleep(2.0)
        logger.info("AUTO-STARTING all stations")
        logger.info("=" * 70)
        self._send_led_off()
        self.is_running = True
        self._send_to_all("/start")

    def _do_boot_timeout(self):
        """Handle boot timeout - start anyway"""
        if not self.is_booting:
            return
        not_ready = [sid for sid, s in self.station_states.items() if s != "home_end"]
        logger.warning("=" * 70)
        logger.warning(f"Boot TIMEOUT ({self.boot_timeout_sec}s) - Starting anyway!")
        logger.warning(f"Stations not ready: {not_ready}")
        logger.warning("=" * 70)
        self.is_booting = False
        # Show green LED for 2 seconds, then start
        self._send_led_ready()
        logger.info("Showing GREEN for 2 seconds before auto-start...")
        threading.Thread(target=self._delayed_auto_start, daemon=True).start()

    def _boot_timeout_checker(self):
        """Background thread to check boot timeout"""
        while self.is_booting:
            time.sleep(0.5)
            if self.boot_start_time is None:
                continue
            elapsed = time.time() - self.boot_start_time
            if elapsed >= self.boot_timeout_sec:
                self._do_boot_timeout()
                return

    def _do_reset_complete(self):
        """Handle reset complete - all stations HOME_END"""
        if not self.is_resetting:
            return
        logger.info("=" * 70)
        logger.info("All stations HOME_END - Reset complete, waiting for V")
        logger.info("=" * 70)
        self.is_resetting = False
        self.reset_start_time = None
        # Show LED ready indicator (solid GREEN)
        self._send_led_ready()

    def _do_reset_timeout(self):
        """Handle reset timeout - allow V key to start anyway"""
        if not self.is_resetting:
            return
        not_ready = [sid for sid, s in self.station_states.items() if s != "home_end"]
        logger.warning("=" * 70)
        logger.warning(f"Reset TIMEOUT ({self.reset_timeout_sec}s) - Ready for V key!")
        logger.warning(f"Stations not ready: {not_ready}")
        logger.warning("=" * 70)
        self.is_resetting = False
        self.reset_start_time = None
        # Show LED ready indicator (solid GREEN) - V key can now start
        self._send_led_ready()

    def _reset_timeout_checker(self):
        """Background thread to check reset timeout"""
        while self.is_resetting:
            time.sleep(0.5)
            if self.reset_start_time is None:
                continue
            elapsed = time.time() - self.reset_start_time
            if elapsed >= self.reset_timeout_sec:
                self._do_reset_timeout()
                return

    def _do_stop_complete(self):
        """Handle stop complete - all stations HOME_END"""
        if not self.is_stopping:
            return
        logger.info("=" * 70)
        logger.info("All stations HOME_END - Stop complete, waiting for V")
        logger.info("=" * 70)
        self.is_stopping = False
        self.stop_start_time = None
        # Show LED ready indicator (solid GREEN)
        self._send_led_ready()

    def _do_stop_timeout(self):
        """Handle stop timeout - allow V key to start anyway"""
        if not self.is_stopping:
            return
        not_ready = [sid for sid, s in self.station_states.items() if s != "home_end"]
        logger.warning("=" * 70)
        logger.warning(f"Stop TIMEOUT ({self.stop_timeout_sec}s) - Ready for V key!")
        logger.warning(f"Stations not ready: {not_ready}")
        logger.warning("=" * 70)
        self.is_stopping = False
        self.stop_start_time = None
        # Show LED ready indicator (solid GREEN) - V key can now start
        self._send_led_ready()

    def _stop_timeout_checker(self):
        """Background thread to check stop timeout"""
        while self.is_stopping:
            time.sleep(0.5)
            if self.stop_start_time is None:
                continue
            elapsed = time.time() - self.stop_start_time
            if elapsed >= self.stop_timeout_sec:
                self._do_stop_timeout()
                return

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
