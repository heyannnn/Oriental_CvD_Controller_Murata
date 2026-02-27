#!/usr/bin/env python3
"""
LED Controller for stations 07 and 10.
Uses NeoPixel LEDs via SPI (GPIO 10).

Can be imported by motor_controller.py or run standalone.

Station 07 Animation:
    - Delay 1.5s, then RED for 11s, then OFF, loop

Station 10 Animation:
    - Delay 4.5s, then loop every 5s:
        - down_LED (pixel 0): RED blink once (0.5s)
        - up_LED (pixel 1): BLUE blink 12 times during 4.5s
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Try to import NeoPixel - will fail on non-Pi systems
try:
    import board
    import neopixel_spi as neopixel
    NEOPIXEL_AVAILABLE = True
except ImportError:
    NEOPIXEL_AVAILABLE = False

# Station-specific settings
STATION_CONFIG = {
    "07": {
        "num_pixels": 15,
        "red": (255, 0, 0),
        "blue": (0, 0, 255),
    },
    "10": {
        "num_pixels": 2,
        "red": (0, 255, 0),  # Different color mapping for station 10
        "blue": (255, 0, 255),
    },
}


class LEDController:
    """LED controller with station-specific animations."""

    def __init__(self, station_id, video_sync_delay_sec=0.0):
        """
        Initialize LED controller.

        Args:
            station_id: "07" or "10"
            video_sync_delay_sec: Delay before starting LED animation (syncs with motor)
        """
        self.station_id = station_id
        self.video_sync_delay_sec = video_sync_delay_sec
        self.config = STATION_CONFIG.get(station_id, STATION_CONFIG["07"])
        self.num_pixels = self.config["num_pixels"]
        self.RED = self.config["red"]
        self.BLUE = self.config["blue"]
        self.pixels = None
        self._running = False
        self._thread = None
        self._indicator_running = False
        self._indicator_thread = None
        self.GREEN = (0, 255, 0)

        if not NEOPIXEL_AVAILABLE:
            logger.warning("NeoPixel not available - LED disabled")
            return

        try:
            spi = board.SPI()
            self.pixels = neopixel.NeoPixel_SPI(
                spi,
                self.num_pixels,
                pixel_order=neopixel.GRB,
                auto_write=False
            )
            self.all_off()
            logger.info(f"LED controller initialized for station {station_id} ({self.num_pixels} pixels)")
        except Exception as e:
            logger.error(f"Failed to initialize NeoPixel: {e}")
            self.pixels = None

    def all_on(self, color):
        """Turn all pixels to specified color."""
        if not self.pixels:
            return
        for i in range(self.num_pixels):
            self.pixels[i] = color
        self.pixels.show()

    def all_off(self):
        """Turn all pixels off."""
        if not self.pixels:
            return
        for i in range(self.num_pixels):
            self.pixels[i] = (0, 0, 0)
        self.pixels.show()

    def set_pixel(self, index, color):
        """Set single pixel to color."""
        if not self.pixels or index >= self.num_pixels:
            return
        self.pixels[index] = color
        self.pixels.show()

    def on_start(self, skip_sync_delay=False):
        """
        Start LED animation based on station.

        Args:
            skip_sync_delay: If True, skip the video_sync_delay (used for loop cycles)
        """
        if not self.pixels:
            logger.warning("Cannot start LED - pixels not initialized")
            return

        # Stop any indicator and turn off LED immediately
        self._indicator_running = False
        time.sleep(0.1)
        self.all_off()

        self._running = True
        self._skip_sync_delay = skip_sync_delay

        if self.station_id == "07":
            self._thread = threading.Thread(target=self._animation_07, daemon=True)
        elif self.station_id == "10":
            self._thread = threading.Thread(target=self._animation_10, daemon=True)
        else:
            logger.warning(f"No LED animation defined for station {self.station_id}")
            return

        self._thread.start()
        logger.info(f"LED animation started for station {self.station_id} (skip_sync_delay={skip_sync_delay})")

    def on_stop(self):
        """Stop LED animation and turn off."""
        self._running = False
        self._indicator_running = False
        time.sleep(0.2)  # Give thread time to exit
        self.all_off()
        logger.info("LED stopped")

    def on_reset(self):
        """Reset LED (same as stop)."""
        self.on_stop()

    # ========================================================================
    # Homing Indicator (Station 07 only)
    # ========================================================================

    def start_homing_indicator(self):
        """Start blinking BLUE to indicate stations are homing."""
        if not self.pixels:
            logger.warning("Cannot start homing indicator - pixels not initialized")
            return

        # Stop any existing animation
        self._running = False
        self._indicator_running = False
        time.sleep(0.2)

        self._indicator_running = True
        self._indicator_thread = threading.Thread(target=self._homing_blink, daemon=True)
        self._indicator_thread.start()
        logger.info("LED homing indicator started (blinking BLUE)")

    def _homing_blink(self):
        """Blink BLUE while homing."""
        while self._indicator_running:
            self.all_on(self.BLUE)
            for _ in range(5):  # 0.5s on
                if not self._indicator_running:
                    self.all_off()
                    return
                time.sleep(0.1)
            self.all_off()
            for _ in range(5):  # 0.5s off
                if not self._indicator_running:
                    return
                time.sleep(0.1)

    def show_ready(self):
        """Show solid GREEN to indicate all stations ready."""
        if not self.pixels:
            return

        # Stop blinking
        self._indicator_running = False
        time.sleep(0.2)

        self.all_on(self.GREEN)
        logger.info("LED showing READY (solid GREEN)")

    def stop_indicator(self):
        """Stop the homing indicator (called before starting normal animation)."""
        self._indicator_running = False
        time.sleep(0.2)
        self.all_off()
        logger.info("LED indicator stopped")

    def _animation_07(self):
        """
        Station 07 animation (single cycle, follows motor loop):
        - Wait video_sync_delay_sec (sync with motor) - only on first cycle
        - 0s - 1.5s: OFF
        - 1.5s - 6s: Fade in (brightness 0 to max)
        - 6s - 12.5s: Full brightness
        - 12.5s - 14.5s: Fade out (brightness max to 0)
        - 14.5s - 15s: OFF
        - OFF (stays off until motor loops and calls on_start again)
        """
        # Timing config - use 20ms steps for smooth 50fps animation
        STEP_TIME = 0.02  # 20ms = 50fps (smooth fades)
        STEPS_PER_SEC = int(1.0 / STEP_TIME)  # 50 steps per second

        # Wait for video sync delay first (only on first cycle)
        if not self._skip_sync_delay:
            logger.info(f"Station 07: Starting LED animation ({self.num_pixels} pixels), sync delay: {self.video_sync_delay_sec}s")
            sync_steps = int(self.video_sync_delay_sec * STEPS_PER_SEC)
            for _ in range(sync_steps):
                if not self._running:
                    return
                time.sleep(STEP_TIME)
        else:
            logger.info(f"Station 07: Starting LED animation ({self.num_pixels} pixels), no sync delay (loop cycle)")

        # 0s - 1.5s: OFF
        off_steps = int(1.5 * STEPS_PER_SEC)  # 75 steps
        for _ in range(off_steps):
            if not self._running:
                return
            time.sleep(STEP_TIME)

        # 1.5s - 6s: Fade in (4.5 seconds)
        fade_in_duration = 4.5
        fade_in_steps = int(fade_in_duration * STEPS_PER_SEC)  # 225 steps
        base_r, base_g, base_b = self.RED
        logger.info("Station 07: Fade in starting")
        for step in range(fade_in_steps):
            if not self._running:
                self.all_off()
                return
            brightness = (step + 1) / fade_in_steps
            color = (int(base_r * brightness), int(base_g * brightness), int(base_b * brightness))
            self.all_on(color)
            time.sleep(STEP_TIME)

        # 6s - 12.5s: Full brightness (6.5 seconds)
        self.all_on(self.RED)
        full_steps = int(6.5 * STEPS_PER_SEC)  # 325 steps
        for _ in range(full_steps):
            if not self._running:
                self.all_off()
                return
            time.sleep(STEP_TIME)

        # 12.5s - 14.5s: Fade out (2 seconds)
        fade_out_duration = 2.0
        fade_out_steps = int(fade_out_duration * STEPS_PER_SEC)  # 100 steps
        logger.info("Station 07: Fade out starting")
        for step in range(fade_out_steps):
            if not self._running:
                self.all_off()
                return
            brightness = 1.0 - ((step + 1) / fade_out_steps)
            color = (int(base_r * brightness), int(base_g * brightness), int(base_b * brightness))
            self.all_on(color)
            time.sleep(STEP_TIME)

        # 14.5s - 15s: OFF (0.5 seconds)
        self.all_off()
        end_steps = int(0.5 * STEPS_PER_SEC)  # 25 steps
        for _ in range(end_steps):
            if not self._running:
                return
            time.sleep(STEP_TIME)
        self._running = False
        logger.info("Station 07: LED cycle complete, waiting for next motor loop")

    def _animation_10(self):
        """
        Station 10 animation:
        - Wait video_sync_delay_sec (sync with motor) - only on first cycle
        - Delay 4.5s
        - Loop every 5s:
            - down_LED (pixel 0): RED blink once (0.5s total)
            - up_LED (pixel 1): BLUE blink 12 times during 4.5s
        """
        OFF = (0, 0, 0)

        # Wait for video sync delay first (only on first cycle)
        if not self._skip_sync_delay:
            logger.info(f"Station 10: Starting LED animation ({self.num_pixels} pixels), sync delay: {self.video_sync_delay_sec}s")
            sync_chunks = int(self.video_sync_delay_sec * 10)
            for _ in range(sync_chunks):
                if not self._running:
                    return
                time.sleep(0.1)
        else:
            logger.info(f"Station 10: Starting LED animation ({self.num_pixels} pixels), no sync delay (loop cycle)")

        # Initial delay 4.5s
        for _ in range(45):  # 4.5s in 0.1s chunks
            if not self._running:
                return
            time.sleep(0.1)

        while self._running:
            # down_LED: RED blink once (0.5s total)
            self.set_pixel(0, self.RED)
            time.sleep(0.25)
            if not self._running:
                self.all_off()
                return
            self.set_pixel(0, OFF)
            time.sleep(0.25)

            # up_LED: BLUE blink 12 times during 4.5s
            blink_duration = 4.5 / 12  # ~0.375s
            on_time = blink_duration / 2
            off_time = blink_duration / 2

            for _ in range(12):
                if not self._running:
                    self.all_off()
                    return
                self.set_pixel(1, self.BLUE)
                time.sleep(on_time)
                if not self._running:
                    self.all_off()
                    return
                self.set_pixel(1, OFF)
                time.sleep(off_time)

        self.all_off()

    def close(self):
        """Cleanup."""
        self._running = False
        self.all_off()
        logger.info("LED controller closed")


# For standalone testing
if __name__ == "__main__":
    import sys
    import signal

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    if len(sys.argv) < 3:
        print("Usage: python led_controller.py <station> <start|stop>")
        print("  station: 07 or 10")
        print("  command: start or stop")
        sys.exit(1)

    station = sys.argv[1]
    command = sys.argv[2]

    controller = LEDController(station_id=station)

    def signal_handler(signum, frame):
        controller.on_stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if command == "stop":
        controller.on_stop()
        print(f"Station {station}: LED stopped")
        sys.exit(0)

    if command == "start":
        controller.on_start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            controller.on_stop()
            print("\nStopped")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
