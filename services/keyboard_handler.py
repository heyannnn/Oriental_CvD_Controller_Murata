"""
Keyboard Handler - USB keyboard input (Master station only)
Monitors V, C, Ctrl keys on USB keyboard for system control
"""

import logging

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

logger = logging.getLogger(__name__)


class KeyboardHandler:
    """
    USB keyboard handler for master control station.
    Keys: V (start/stop toggle), C (standby), Ctrl (emergency)
    """

    def __init__(self, config):
        """
        Initialize USB keyboard handler.

        Args:
            config: Station config dict with 'keyboard' section
        """
        if not PYNPUT_AVAILABLE:
            raise ImportError("pynput not available - install with: pip install pynput")

        # Callback placeholders (wired by main.py)
        self._on_start = None
        self._on_stop = None
        self._on_reset = None
        self._on_clear_alarm = None

        # State tracking for V key toggle
        self.is_running = False

        # Start keyboard listener
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()

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

    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            # V key - Start/Stop toggle
            if hasattr(key, 'char') and key.char == 'v':
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
            elif hasattr(key, 'char') and key.char == 'c':
                logger.info("C key pressed: STANDBY/RESET")
                if self._on_reset:
                    self._on_reset()
                self.is_running = False  # Reset state to stopped

            # Ctrl key - Clear alarm
            elif key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                logger.info("Ctrl pressed: CLEAR ALARM")
                if self._on_clear_alarm:
                    self._on_clear_alarm()

        except AttributeError:
            # Key doesn't have 'char' attribute (special keys)
            pass

    def close(self):
        """Cleanup keyboard listener"""
        if self.listener:
            self.listener.stop()
            logger.info("USB keyboard handler closed")
