#!/usr/bin/env python3
"""
Keyboard Controller - USB keyboard input for master station (Pi-02)
Monitors V and Ctrl+V keys for system control.

Controls:
    V key    - Toggle start/stop
    Ctrl+V   - Reset (stop all, home all, wait for V)
    Ctrl+C   - Exit

This script is launched by main.py on Pi-02 only.
Uses evdev to read directly from USB keyboard (works without terminal).
"""

import logging
import threading
import time

try:
    import evdev
    from evdev import ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# Retry settings for keyboard reconnection
KEYBOARD_RETRY_DELAY = 2.0  # seconds between reconnection attempts
KEYBOARD_MAX_RETRIES = 0    # 0 = infinite retries

logger = logging.getLogger(__name__)


def find_keyboard():
    """Find the first keyboard device."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        capabilities = device.capabilities()
        # Check if device has KEY events and has typical keyboard keys
        if ecodes.EV_KEY in capabilities:
            keys = capabilities[ecodes.EV_KEY]
            # Check for typical keyboard keys (letters, ctrl, etc.)
            if ecodes.KEY_V in keys and ecodes.KEY_LEFTCTRL in keys:
                return device
    return None


class KeyboardController:
    """
    USB keyboard handler for master control station.
    Keys: V (start/stop toggle), Ctrl+V (reset)
    Uses evdev for direct keyboard access (works in background/systemd).
    Automatically reconnects if keyboard disconnects.
    """

    def __init__(self):
        """Initialize keyboard controller."""
        if not EVDEV_AVAILABLE:
            raise ImportError("evdev not available - install with: pip install evdev")

        self._device = find_keyboard()
        if not self._device:
            logger.warning("No keyboard found at startup - will retry when listener starts")

        # Callbacks (set by sequence_manager or main.py)
        self._on_start = None
        self._on_stop = None
        self._on_reset = None
        self._get_is_running = None  # Callback to check if system is running

        # Track modifier keys
        self._ctrl_pressed = False

        # Thread control
        self._running = True
        self._thread = None

        if self._device:
            logger.info(f"Keyboard controller initialized using: {self._device.name}")
        logger.info("Controls: V=toggle start/stop, Ctrl+V=reset")

    def set_on_start(self, callback):
        """Set callback for START (V key when stopped)"""
        self._on_start = callback

    def set_on_stop(self, callback):
        """Set callback for STOP (V key when running)"""
        self._on_stop = callback

    def set_on_reset(self, callback):
        """Set callback for RESET (Ctrl+V)"""
        self._on_reset = callback

    def set_get_is_running(self, callback):
        """Set callback to check if system is currently running"""
        self._get_is_running = callback

    def start(self):
        """Start keyboard listener in background thread"""
        self._thread = threading.Thread(target=self._keyboard_loop, daemon=True)
        self._thread.start()
        logger.info("Keyboard listener started")

    def _reconnect_keyboard(self):
        """Try to reconnect to keyboard device."""
        retry_count = 0
        while self._running:
            retry_count += 1
            if KEYBOARD_MAX_RETRIES > 0 and retry_count > KEYBOARD_MAX_RETRIES:
                logger.error(f"Keyboard reconnection failed after {KEYBOARD_MAX_RETRIES} attempts")
                return False

            logger.info(f"Attempting to reconnect keyboard (attempt {retry_count})...")
            self._device = find_keyboard()
            if self._device:
                logger.info(f"Keyboard reconnected: {self._device.name}")
                self._ctrl_pressed = False  # Reset modifier state
                return True

            time.sleep(KEYBOARD_RETRY_DELAY)

        return False

    def _keyboard_loop(self):
        """Background thread that reads keyboard input via evdev with auto-reconnect"""
        while self._running:
            # Ensure we have a device
            if not self._device:
                if not self._reconnect_keyboard():
                    break
                continue

            try:
                for event in self._device.read_loop():
                    if not self._running:
                        return

                    if event.type != ecodes.EV_KEY:
                        continue

                    # Track Ctrl key state
                    if event.code in (ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL):
                        self._ctrl_pressed = (event.value == 1)  # 1 = pressed, 0 = released
                        continue

                    # Only handle key press (value=1), not release (value=0) or repeat (value=2)
                    if event.value != 1:
                        continue

                    # V key
                    if event.code == ecodes.KEY_V:
                        if self._ctrl_pressed:
                            # Ctrl+V - Reset
                            logger.info("Ctrl+V pressed: RESET")
                            if self._on_reset:
                                self._on_reset()
                        else:
                            # V only - Toggle start/stop
                            is_running = self._get_is_running() if self._get_is_running else False

                            if is_running:
                                logger.info("V key pressed: STOP")
                                if self._on_stop:
                                    self._on_stop()
                            else:
                                logger.info("V key pressed: START")
                                if self._on_start:
                                    self._on_start()

            except OSError as e:
                # Device disconnected (errno 19 = ENODEV)
                if self._running:
                    logger.warning(f"Keyboard disconnected: {e}")
                    self._device = None
                    # Will reconnect on next loop iteration
            except Exception as e:
                if self._running:
                    logger.error(f"Keyboard read error: {e}")
                    self._device = None
                    time.sleep(KEYBOARD_RETRY_DELAY)

    def stop(self):
        """Stop keyboard listener"""
        self._running = False
        logger.info("Keyboard controller stopped")


# For standalone testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    print("=" * 50)
    print("Keyboard Controller Test (evdev)")
    print("=" * 50)
    print("  V key    - Toggle (prints START/STOP)")
    print("  Ctrl+V   - Reset (prints RESET)")
    print("  Ctrl+C   - Exit")
    print("=" * 50)

    # List available devices
    print("\nAvailable input devices:")
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        print(f"  {path}: {device.name}")
    print()

    is_running = False

    def on_start():
        global is_running
        is_running = True
        print(">>> START <<<")

    def on_stop():
        global is_running
        is_running = False
        print(">>> STOP <<<")

    def on_reset():
        global is_running
        is_running = False
        print(">>> RESET <<<")

    def get_is_running():
        return is_running

    controller = KeyboardController()
    controller.set_on_start(on_start)
    controller.set_on_stop(on_stop)
    controller.set_on_reset(on_reset)
    controller.set_get_is_running(get_is_running)

    controller.start()

    try:
        # Keep main thread alive
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        controller.stop()
        print("\nExiting...")
