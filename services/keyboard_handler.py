"""
Keyboard Handler - USB keyboard input (Master station only)
Monitors V, C, Ctrl keys on USB keyboard for system control

Uses readchar for better Raspberry Pi compatibility.
"""

import logging
import threading

try:
    import readchar
    READCHAR_AVAILABLE = True
except ImportError:
    READCHAR_AVAILABLE = False

logger = logging.getLogger(__name__)


class KeyboardHandler:
    """
    USB keyboard handler for master control station.
    Keys: V (start/stop toggle), C (standby), Ctrl (emergency)

    Uses readchar instead of pynput for better Pi compatibility.
    """

    def __init__(self, config):
        """
        Initialize USB keyboard handler.

        Args:
            config: Station config dict with 'keyboard' section
        """
        if not READCHAR_AVAILABLE:
            raise ImportError("readchar not available - install with: pip install readchar")

        # Callback placeholders (wired by main.py)
        self._on_start = None
        self._on_stop = None
        self._on_reset = None
        self._on_clear_alarm = None

        # State tracking for V key toggle
        self.is_running = False

        # Thread control
        self._running = True
        self._thread = threading.Thread(target=self._keyboard_loop, daemon=True)
        self._thread.start()

        logger.info("USB keyboard handler initialized (V=start/stop, C=standby, Ctrl=emergency)")

    def set_on_start(self, callback):
        """Set callback for START (V key when stopped)"""
        self._on_start = callback

    def set_on_stop(self, callback):
        """Set callback for STOP (V key when running)"""
        self._on_stop = callback

    def set_on_reset(self, callback):
        """Set callback for RESET/STANDBY (C key)"""
        self._on_reset = callback

    def set_on_clear_alarm(self, callback):
        """Set callback for CLEAR ALARM (Ctrl key)"""
        self._on_clear_alarm = callback

    def _keyboard_loop(self):
        """Background thread that reads keyboard input"""
        logger.info("Keyboard listener thread started")

        while self._running:
            try:
                # Read single character (blocking)
                key = readchar.readchar()

                # Debug log
                # logger.info(f"KEY DETECTED: '{key}' (ord: {ord(key) if len(key) == 1 else 'special'})")

                # V key - Start/Stop toggle
                if key.lower() == 'v':
                    if self.is_running:
                        logger.info("V key pressed: STOP")
                        if self._on_stop:
                            self._on_stop()
                        self.is_running = False
                    else:
                        logger.info("V key pressed: START")
                        if self._on_start:
                            self._on_start()
                        self.is_running = True

                # C key - Standby/Reset
                elif key.lower() == 'c':
                    logger.info("C key pressed: STANDBY/RESET")
                    if self._on_reset:
                        self._on_reset()
                    self.is_running = False

                # Ctrl+C is handled by Python's signal handler
                # Ctrl key alone (ASCII 0x11 for Ctrl+Q, etc.)
                elif ord(key) < 32 and key != '\r' and key != '\n':
                    logger.info(f"Ctrl combo detected (ord: {ord(key)}): CLEAR ALARM")
                    if self._on_clear_alarm:
                        self._on_clear_alarm()

            except Exception as e:
                if self._running:  # Only log if not shutting down
                    logger.error(f"Keyboard read error: {e}")

    def close(self):
        """Cleanup keyboard listener"""
        self._running = False
        logger.info("USB keyboard handler closed")
