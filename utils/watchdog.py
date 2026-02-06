"""
Raspberry Pi hardware watchdog wrapper.

The RPi hardware watchdog reboots the system if not "petted" within
its timeout window (default 60s, configurable via raspi-config).

Prerequisites on the Pi:
    sudo raspi-config  ->  System  ->  Hardware Watchdog  ->  Enable

Usage in main loop:
    from utils.watchdog import Watchdog

    wd = Watchdog()          # opens /dev/watchdog
    ...
    while True:
        do_work()
        wd.pet()             # must be called before timeout, or Pi reboots
    ...
    wd.close()               # disables watchdog cleanly on normal exit
"""

import logging

logger = logging.getLogger(__name__)

WATCHDOG_DEVICE = "/dev/watchdog"


class Watchdog:

    def __init__(self, device: str = WATCHDOG_DEVICE):
        self._fd = None
        try:
            self._fd = open(device, "w")
            logger.info("Hardware watchdog enabled")
        except FileNotFoundError:
            logger.warning(
                "Watchdog device not found. "
                "Enable via: raspi-config -> System -> Hardware Watchdog"
            )
        except PermissionError:
            logger.warning(
                "Permission denied for watchdog. "
                "Run as root or add user to 'watchdog' group."
            )

    def pet(self):
        """Reset the watchdog timer. Call this regularly from the main loop."""
        if self._fd:
            self._fd.write("1")
            self._fd.flush()

    def close(self):
        """Close cleanly — write magic character 'V' to disable watchdog."""
        if self._fd:
            self._fd.write("V")
            self._fd.flush()
            self._fd.close()
            self._fd = None
            logger.info("Hardware watchdog disabled")

    @property
    def enabled(self) -> bool:
        return self._fd is not None
