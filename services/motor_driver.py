"""
Motor Driver - Low-level Modbus wrapper for CVD-28-KR
Thin wrapper around oriental_cvd.py for basic motor commands
"""

import logging
from drivers.oriental_cvd import OrientalCvdMotor
from drivers.cvd_define import OutputSignal, InputSignal

logger = logging.getLogger(__name__)


class MotorDriver:
    """
    Low-level motor driver interface.
    Provides simple command methods without state management.
    """

    def __init__(self, port, slave_id=1):
        """
        Initialize motor driver.

        Args:
            port: Serial port (e.g., /dev/ttyUSB0)
            slave_id: Modbus slave ID (1-247)
        """
        self.port = port
        self.slave_id = slave_id
        self.client = OrientalCvdMotor(port=port)

    def connect(self):
        """Connect to motor driver via Modbus"""
        self.client.connect()
        logger.info(f"Motor driver connected (slave_id={self.slave_id})")

    def close(self):
        """Close Modbus connection"""
        self.client.close()
        logger.info("Motor driver disconnected")

    # ========================================================================
    # Homing Commands
    # ========================================================================

    async def start_homing(self, timeout=100):
        """
        Start homing operation (async).

        Args:
            timeout: Max homing time in seconds
        """
        logger.info(f"Starting homing (slave_id={self.slave_id})")
        await self.client.start_homing_async(timeout=timeout, slave_id=self.slave_id)

    def is_homing(self) -> bool:
        """
        Check if motor is currently homing.

        Returns:
            True if homing in progress
        """
        # Homing is complete when HOME_END flag is set
        # While homing, HOME_END is False
        return not self.client.checkHomeEndFlag(slave_id=self.slave_id)

    def is_home_complete(self) -> bool:
        """
        Check if homing is complete.

        Returns:
            True if HOME_END flag is set
        """
        return self.client.checkHomeEndFlag(slave_id=self.slave_id)

    # ========================================================================
    # Operation Commands
    # ========================================================================

    def start_operation(self, op_no=0):
        """
        Start MEXE operation by number.

        Args:
            op_no: MEXE operation number (0-255)
        """
        logger.info(f"Starting operation {op_no} (slave_id={self.slave_id})")

        # Set operation number
        self.client.set_operation_no(data_no=op_no, slave_id=self.slave_id)

        # Send START signal
        self.client.send_start_signal(slave_id=self.slave_id)

    def stop(self):
        """Send STOP signal to motor"""
        logger.info(f"Stopping motor (slave_id={self.slave_id})")
        self.client.send_stop_signal(slave_id=self.slave_id)

    # ========================================================================
    # Status Queries
    # ========================================================================

    def is_ready(self) -> bool:
        """
        Check if motor is ready.

        Returns:
            True if READY flag is set
        """
        return self.client.checkReadyFlag(slave_id=self.slave_id)

    def is_moving(self) -> bool:
        """
        Check if motor is currently moving.

        Returns:
            True if MOVE flag is set
        """
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        return (status & OutputSignal.MOVE) != 0

    def is_in_position(self) -> bool:
        """
        Check if motor has reached target position.

        Returns:
            True if IN_POS flag is set
        """
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        return (status & OutputSignal.IN_POS) != 0

    def get_alarm_status(self) -> bool:
        """
        Check if motor has an alarm.

        Returns:
            True if alarm is active
        """
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        return (status & OutputSignal.ALARM) != 0

    def read_position(self) -> int:
        """
        Read current position.

        Returns:
            Current position in pulses, or 0 on error
        """
        from drivers.cvd_define import MonitorCommand
        pos = self.client.read_monitor(MonitorCommand.FEEDBACK_POS, slave_id=self.slave_id)
        return pos if pos is not None else 0
