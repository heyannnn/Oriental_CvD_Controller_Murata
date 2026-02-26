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
        time.sleep(0.2)  # Give thread time to exit
        self.all_off()
        logger.info("LED stopped")

    def on_reset(self):
        """Reset LED (same as stop)."""
        self.on_stop()

    def _animation_07(self):
        """
        Station 07 animation (single cycle, follows motor loop):
        - Wait video_sync_delay_sec (sync with motor) - only on first cycle
        - Delay 1.5s
        - RED for 11s
        - OFF (stays off until motor loops and calls on_start again)
        """
        # Wait for video sync delay first (only on first cycle)
        if not self._skip_sync_delay:
            logger.info(f"Station 07: Starting LED animation ({self.num_pixels} pixels), sync delay: {self.video_sync_delay_sec}s")
            sync_chunks = int(self.video_sync_delay_sec * 10)
            for _ in range(sync_chunks):
                if not self._running:
                    return
                time.sleep(0.1)
        else:
            logger.info(f"Station 07: Starting LED animation ({self.num_pixels} pixels), no sync delay (loop cycle)")

        # Delay 1.5s
        for _ in range(15):  # 1.5s in 0.1s chunks
            if not self._running:
                return
            time.sleep(0.1)

        # RED for 11s
        self.all_on(self.RED)
        for _ in range(110):  # 11s in 0.1s chunks
            if not self._running:
                self.all_off()
                return
            time.sleep(0.1)

        # OFF - stays off until next on_start() call
        self.all_off()
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
