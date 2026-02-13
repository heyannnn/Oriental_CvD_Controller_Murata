"""
Network Sync Service - OSC-based inter-station communication
Station 2 broadcasts START/STOP/RESET to all stations
All stations listen for these commands
"""

import logging
import threading

try:
    from pythonosc import udp_client
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import BlockingOSCUDPServer
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

logger = logging.getLogger(__name__)


class NetworkSync:
    """
    OSC-based network synchronization.

    Station 2 (master): broadcasts /start, /stop, /reset to all stations
    All stations: listen for these commands and execute locally
    """

    def __init__(self, config):
        """
        Initialize network sync.

        Args:
            config: Station config dict with 'network' section
        """
        if not OSC_AVAILABLE:
            logger.warning("python-osc not available, network sync disabled")
            self.client = None
            self.server = None
            return

        net_config = config.get('network', {})

        self.listen_port = net_config.get('listen_port', 10000)
        self.send_port = net_config.get('send_port', 10001)
        self.is_sender = net_config.get('is_sender', False)
        self.target_ips = net_config.get('target_ips', [])

        # Video player OSC config
        self.video_player_ip = net_config.get('video_player_ip', '127.0.0.1')
        self.video_player_port = net_config.get('video_player_port', 9000)

        # OSC client (for broadcasting)
        self.client = None
        if self.is_sender:
            # We'll send to multiple IPs, so create clients on-demand
            logger.info(f"Network sync sender enabled (targets: {len(self.target_ips)} stations)")

        # OSC server (for listening)
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/start", self._handle_start)
        self.dispatcher.map("/stop", self._handle_stop)
        self.dispatcher.map("/reset", self._handle_reset)
        self.dispatcher.map("/clear_alarm", self._handle_clear_alarm)

        # Keyboard control commands
        self.dispatcher.map("/control/launch", self._handle_launch)
        self.dispatcher.map("/control/start", self._handle_control_start)
        self.dispatcher.map("/control/stop", self._handle_control_stop)

        self.server = BlockingOSCUDPServer(("0.0.0.0", self.listen_port), self.dispatcher)
        self.server_thread = None

        # Callback placeholders (wired by main.py)
        self._on_start = None
        self._on_stop = None
        self._on_reset = None
        self._on_launch = None
        self._on_clear_alarm = None

    def set_on_start(self, callback):
        """Set callback for START command"""
        self._on_start = callback

    def set_on_stop(self, callback):
        """Set callback for STOP command"""
        self._on_stop = callback

    def set_on_reset(self, callback):
        """Set callback for RESET command"""
        self._on_reset = callback

    def set_on_launch(self, callback):
        """Set callback for LAUNCH command"""
        self._on_launch = callback

    def set_on_clear_alarm(self, callback):
        """Set callback for CLEAR_ALARM command"""
        self._on_clear_alarm = callback

    def start_listener(self):
        """Start OSC server in background thread"""
        if not self.server:
            return

        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )
        self.server_thread.start()
        logger.info(f"OSC listener started on port {self.listen_port}")

    def stop(self):
        """Stop OSC server"""
        if self.server:
            self.server.shutdown()
            logger.info("OSC listener stopped")

    def broadcast_start(self):
        """Broadcast START command to all target stations"""
        if not self.is_sender:
            return

        logger.info("Broadcasting START to all stations")
        for ip in self.target_ips:
            try:
                client = udp_client.SimpleUDPClient(ip, self.send_port)
                client.send_message("/start", [])
            except Exception as e:
                logger.error(f"Failed to send START to {ip}: {e}")

    def broadcast_stop(self):
        """Broadcast STOP command to all target stations"""
        if not self.is_sender:
            return

        logger.info("Broadcasting STOP to all stations")
        for ip in self.target_ips:
            try:
                client = udp_client.SimpleUDPClient(ip, self.send_port)
                client.send_message("/stop", [])
            except Exception as e:
                logger.error(f"Failed to send STOP to {ip}: {e}")

    def broadcast_reset(self):
        """Broadcast RESET command to all target stations"""
        if not self.is_sender:
            return

        logger.info("Broadcasting RESET to all stations")
        for ip in self.target_ips:
            try:
                client = udp_client.SimpleUDPClient(ip, self.send_port)
                client.send_message("/reset", [])
            except Exception as e:
                logger.error(f"Failed to send RESET to {ip}: {e}")

    def broadcast_clear_alarm(self):
        """Broadcast CLEAR_ALARM command to all target stations"""
        if not self.is_sender:
            return

        logger.info("Broadcasting CLEAR_ALARM to all stations")
        for ip in self.target_ips:
            try:
                client = udp_client.SimpleUDPClient(ip, self.send_port)
                client.send_message("/clear_alarm", [])
            except Exception as e:
                logger.error(f"Failed to send CLEAR_ALARM to {ip}: {e}")

    def _handle_start(self, address, *args):
        """OSC handler for /start (inter-station broadcast)"""
        logger.info("Received START command via OSC")
        if self._on_start:
            self._on_start()

    def _handle_stop(self, address, *args):
        """OSC handler for /stop (inter-station broadcast)"""
        logger.info("Received STOP command via OSC")
        if self._on_stop:
            self._on_stop()

    def _handle_reset(self, address, *args):
        """OSC handler for /reset (inter-station broadcast)"""
        logger.info("Received RESET command via OSC")
        if self._on_reset:
            self._on_reset()

    def _handle_launch(self, address, *args):
        """OSC handler for /control/launch (from keyboard.py)"""
        logger.info("Received LAUNCH command from keyboard controller")
        if self._on_launch:
            self._on_launch()

    def _handle_control_start(self, address, *args):
        """OSC handler for /control/start (from keyboard.py)"""
        logger.info("Received START command from keyboard controller")
        if self._on_start:
            self._on_start()

    def _handle_control_stop(self, address, *args):
        """OSC handler for /control/stop (from keyboard.py)"""
        logger.info("Received STOP command from keyboard controller")
        if self._on_stop:
            self._on_stop()

    def _handle_clear_alarm(self, address, *args):
        """OSC handler for /clear_alarm (inter-station broadcast)"""
        logger.info("Received CLEAR_ALARM command via OSC")
        if self._on_clear_alarm:
            self._on_clear_alarm()

    # ========================================================================
    # Video Player Commands
    # ========================================================================

    def send_video_command(self, command, params=None):
        """
        Send command to external video player program.

        Args:
            command: Command string (ready, standby, start, stop, finished, error)
            params: Optional dict of parameters
        """
        if not OSC_AVAILABLE:
            return

        try:
            client = udp_client.SimpleUDPClient(self.video_player_ip, self.video_player_port)

            if command in ("start", "standby"):
                # Send as /video/<command> with parameters
                client.send_message("/playlist/load", ["./NormalOperation.csv"])
            elif command == "stop":
                # Send as /video/<command>
                client.send_message("/playlist/load", ["./Waiting.csv"])

            logger.info(f"Sent video command: /video/{command}")

        except Exception as e:
            logger.error(f"Failed to send video command {command}: {e}")
