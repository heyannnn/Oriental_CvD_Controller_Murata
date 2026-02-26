"""
MP4 Player Service - Video player control via OSC
Sends commands to local video player (osc_mpv_playlist.py)
"""

import logging

try:
    from pythonosc import udp_client
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False

logger = logging.getLogger(__name__)


class MP4Player:
    """
    Video player control via OSC.
    Sends playlist load commands to local video player.
    """

    def __init__(self, config):
        """
        Initialize MP4 player controller.

        Args:
            config: Station config dict with 'network' section
        """
        if not OSC_AVAILABLE:
            logger.warning("python-osc not available, video control disabled")
            self.client = None
            return

        net_config = config.get('network', {})

        # Video player OSC config
        self.video_player_ip = net_config.get('video_player_ip', '127.0.0.1')
        self.video_player_port = net_config.get('video_player_port', 9000)

        # Station config for video behavior
        self.homing_required = config.get('homing_required', True)
        self.video_only = config.get('video_only', False)

        # Create OSC client
        try:
            self.client = udp_client.SimpleUDPClient(
                self.video_player_ip,
                self.video_player_port
            )
            logger.info(f"MP4 player controller initialized ({self.video_player_ip}:{self.video_player_port})")
        except Exception as e:
            logger.error(f"Failed to create video player client: {e}")
            self.client = None

    def send_command(self, command):
        """
        Send command to video player.

        Args:
            command: Command string (start, standby, stop)

        Video Behavior:
          Stations WITH homing (5,6,7,8,9):
            - "start" -> NormalOperation.csv (first cycle)
            - "standby" -> Sync.csv (loop cycles)
            - "stop" -> Waiting.csv

          Stations WITHOUT homing (2,3,4,10):
            - "start" -> NormalOperation.csv (first cycle)
            - "standby" -> NormalOperation.csv (loop cycles)
            - "stop" -> Waiting.csv

          Video-only station (11):
            - "start" -> NormalOperation.csv (first cycle)
            - "standby" -> Sync.csv (loop cycles, 30s each)
            - "stop" -> Waiting.csv
        """
        if not self.client:
            return

        try:
            if self.homing_required:
                # Stations 5,6,7,8,9 - have homing, use 3 different videos
                if command == "start":
                    self.client.send_message("/playlist/load", ["./NormalOperation.csv"])
                    logger.info("Video: /playlist/load [NormalOperation.csv] (first cycle)")
                elif command == "standby":
                    self.client.send_message("/playlist/load", ["./Sync.csv"])
                    logger.info("Video: /playlist/load [Sync.csv] (loop cycle)")
                elif command == "stop":
                    self.client.send_message("/playlist/load", ["./Waiting.csv"])
                    logger.info("Video: /playlist/load [Waiting.csv] (stopped)")
                else:
                    logger.debug(f"Video command '{command}' - no action defined")
            elif self.video_only:
                # Station 11 - video only, loop Sync.csv after NormalOperation
                if command == "start":
                    self.client.send_message("/playlist/load", ["./NormalOperation.csv"])
                    logger.info("Video: /playlist/load [NormalOperation.csv] (first cycle)")
                elif command == "standby":
                    self.client.send_message("/playlist/load", ["./Sync.csv"])
                    logger.info("Video: /playlist/load [Sync.csv] (loop cycle)")
                elif command == "stop":
                    self.client.send_message("/playlist/load", ["./Waiting.csv"])
                    logger.info("Video: /playlist/load [Waiting.csv] (stopped)")
                else:
                    logger.debug(f"Video command '{command}' - no action defined")
            else:
                # Stations 2,3,4,10 - no homing, use 2 videos only
                if command == "start":
                    self.client.send_message("/playlist/load", ["./NormalOperation.csv"])
                    logger.info("Video: /playlist/load [NormalOperation.csv] (first cycle)")
                elif command == "standby":
                    self.client.send_message("/playlist/load", ["./NormalOperation.csv"])
                    logger.info("Video: /playlist/load [NormalOperation.csv] (loop cycle)")
                elif command == "stop":
                    self.client.send_message("/playlist/load", ["./Waiting.csv"])
                    logger.info("Video: /playlist/load [Waiting.csv] (stopped)")
                else:
                    logger.debug(f"Video command '{command}' - no action defined")

        except Exception as e:
            logger.error(f"Failed to send video command '{command}': {e}")

    def load_playlist(self, csv_file):
        """
        Load specific playlist CSV.

        Args:
            csv_file: CSV filename (e.g., "NormalOperation.csv")
        """
        if not self.client:
            return

        try:
            self.client.send_message("/playlist/load", [f"./{csv_file}"])
            logger.info(f"Video: /playlist/load [{csv_file}]")
        except Exception as e:
            logger.error(f"Failed to load playlist '{csv_file}': {e}")
