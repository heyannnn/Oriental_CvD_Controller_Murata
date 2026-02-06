"""
Keyboard Handler - 3-key GPIO input (Station 2 only)
Monitors START, STOP, RESET buttons wired to GPIO pins
"""

import logging

try:
    from gpiozero import Button
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

logger = logging.getLogger(__name__)


class KeyboardHandler:
    """
    3-key GPIO keyboard handler for master control station.
    Buttons: START, STOP, RESET
    """

    def __init__(self, config):
        """
        Initialize keyboard handler.

        Args:
            config: Station config dict with 'keyboard.gpio' section
        """
        if not GPIOZERO_AVAILABLE:
            logger.warning("gpiozero not available, keyboard disabled")
            self.buttons = {}
            return

        gpio_config = config['keyboard']['gpio']

        # Initialize GPIO buttons with pull-up resistors
        self.buttons = {
            'start': Button(gpio_config['start_button'], pull_up=True),
            'stop': Button(gpio_config['stop_button'], pull_up=True),
            'reset': Button(gpio_config['reset_button'], pull_up=True)
        }

        # Callback placeholders (wired by main.py)
        self._on_start = None
        self._on_stop = None
        self._on_reset = None

        # Wire button events
        self.buttons['start'].when_pressed = self._handle_start
        self.buttons['stop'].when_pressed = self._handle_stop
        self.buttons['reset'].when_pressed = self._handle_reset

        logger.info("Keyboard handler initialized (3-key GPIO)")

    def set_on_start(self, callback):
        """Set callback for START button press"""
        self._on_start = callback

    def set_on_stop(self, callback):
        """Set callback for STOP button press"""
        self._on_stop = callback

    def set_on_reset(self, callback):
        """Set callback for RESET button press"""
        self._on_reset = callback

    def _handle_start(self):
        """Internal handler for START button"""
        logger.info("START button pressed")
        if self._on_start:
            self._on_start()

    def _handle_stop(self):
        """Internal handler for STOP button"""
        logger.info("STOP button pressed")
        if self._on_stop:
            self._on_stop()

    def _handle_reset(self):
        """Internal handler for RESET button"""
        logger.info("RESET button pressed")
        if self._on_reset:
            self._on_reset()

    def close(self):
        """Cleanup GPIO resources"""
        if self.buttons:
            for button in self.buttons.values():
                button.close()
            logger.info("Keyboard handler closed")
