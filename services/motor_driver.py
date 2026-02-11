"""
Motor Driver - Low-level Modbus wrapper for CVD-28-KR
Thin wrapper around oriental_cvd.py for basic motor commands
"""

import logging
from drivers.oriental_cvd import OrientalCvdMotor
from drivers.cvd_define import OutputSignal, InputSignal, OPMode

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
        For operations 0-7: Use M0-M2 bits + START bit
        For operations 8+: Would need to use different method (not implemented)

        Args:
            op_no: MEXE operation number (0-7 supported)
        """
        logger.info(f"Starting operation {op_no} (slave_id={self.slave_id})")

        if op_no > 7:
            logger.error(f"Operation numbers > 7 not yet supported (got {op_no})")
            return False

        # Build command: operation number (bits 0-2) + START bit (bit 3)
        # Operation 0: 0x0008 (just START)
        # Operation 1: 0x0009 (M0 + START)
        # Operation 2: 0x000A (M1 + START)
        # etc.
        cmd_value = (op_no & 0x07) | InputSignal.START

        logger.info(f"Sending START command: 0x{cmd_value:04X} (op_no={op_no} encoded in bits 0-2)")

        # Write directly to input command register
        result = self.client.client.write_register(
            address=0x007D,
            value=cmd_value,
            device_id=self.slave_id
        )

        if result.isError():
            logger.error(f"Failed to start operation {op_no}: {result}")
            return False
        else:
            logger.info(f"✓ Operation {op_no} started successfully")

            # Clear command after a brief delay
            import time
            time.sleep(0.05)
            self.client.client.write_register(
                address=0x007D,
                value=0x0000,
                device_id=self.slave_id
            )
            return True

    def return_to_zero(self, velocity=2000):
        """
        Execute a return-to-zero operation using direct operation.
        Uses ABSOLUTE positioning mode to move back to position 0.

        Args:
            velocity: Speed for return motion (pulses/sec), default 2000 (slow/safe)
        """
        logger.info(f"Direct operation: return to position 0 at velocity {velocity} (slave_id={self.slave_id})")

        # Use direct operation to move to absolute position 0
        # This immediately starts the motion without needing to program a data slot
        self.client.start_direct_operation(
            data_no=0,
            position=0,
            velocity=velocity,
            startRate=1000,
            stopRate=1000,
            mode=OPMode.ABSOLUTE,
            current=1.0,
            slave_id=self.slave_id
        )

        logger.info("Return to zero started via direct operation")
        return True

    def stop(self):
        """Send STOP signal to motor"""
        logger.info(f"Stopping motor (slave_id={self.slave_id})")

        # Use existing function to send STOP signal
        result = self.client.send_input_signal(
            signal=InputSignal.STOP,
            slave_id=self.slave_id
        )

        if result:
            logger.info("Motor stopped successfully")

            # Clear command
            import time
            time.sleep(0.1)
            self.client.send_input_signal(
                signal=InputSignal.OFF,
                slave_id=self.slave_id
            )
        else:
            logger.error(f"Failed to stop motor")

    def clear_alarm(self):
        """Clear motor alarm"""
        logger.info(f"Clearing alarm (slave_id={self.slave_id})")

        from drivers.cvd_define import InputSignal

        # Send alarm reset signal
        result = self.client.send_input_signal(signal=InputSignal.ALM_RST, slave_id=self.slave_id)

        if result:
            logger.info("Alarm cleared successfully")

            # Clear command after a short delay
            import time
            time.sleep(0.1)
            self.client.send_input_signal(signal=InputSignal.OFF, slave_id=self.slave_id)
        else:
            logger.error("Failed to clear alarm")

    # ========================================================================
    # Status Queries
    # ========================================================================

    def is_ready(self) -> bool:
        """
        Check if motor is ready.

        Returns:
            True if READY flag is set
        """
        # Use existing function from oriental_cvd.py
        return self.client.checkReadyFlag(slave_id=self.slave_id)

    def is_moving(self) -> bool:
        """
        Check if motor is currently moving.

        Returns:
            True if MOVE flag is set
        """
        # Use existing function from oriental_cvd.py
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        return (status & OutputSignal.MOVE) != 0

    def is_in_position(self) -> bool:
        """
        Check if motor has reached target position.
        Uses AREA0 signal which can be configured for positioning complete in MEXE02.
        Alternatively, position complete = READY=1 && MOVE=0.

        Returns:
            True if in position (READY and not MOVE)
        """
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        # In position when ready and not moving
        ready = (status & OutputSignal.READY) != 0
        moving = (status & OutputSignal.MOVE) != 0
        return ready and not moving

    def get_alarm_status(self) -> bool:
        """
        Check if motor has an alarm.

        Returns:
            True if alarm is active
        """
        status = self.client.read_output_signal(slave_id=self.slave_id)
        if status is None:
            return False
        return (status & OutputSignal.ALM_A) != 0

    def read_position(self) -> int:
        """
        Read current position.

        Returns:
            Current position in pulses, or 0 on error
        """
        from drivers.cvd_define import MonitorCommand
        pos = self.client.read_monitor(MonitorCommand.COMMAND_POSITION, slave_id=self.slave_id)
        return pos if pos is not None else 0

    def read_running_operation(self) -> int:
        """
        Read currently running operation number.

        Returns:
            Operation number (0-255) if running, -1 if stopped, None on error
        """
        from drivers.cvd_define import MonitorCommand
        op_no = self.client.read_monitor(MonitorCommand.RUNNING_DATA_NO, slave_id=self.slave_id)
        return op_no

    def get_detailed_status(self) -> dict:
        """
        Read and parse detailed status from register 0x007F.

        Returns:
            Dict with all status bit values (all 16 bits)
        """
        result = self.client.client.read_holding_registers(
            address=0x007F,
            count=1,
            device_id=self.slave_id
        )

        if result.isError():
            return None

        status = result.registers[0]

        return {
            "raw_value": f"0x{status:04X}",
            "MOVE": bool(status & OutputSignal.MOVE),         # Bit 13 - Motor is moving
            "READY": bool(status & OutputSignal.READY),       # Bit 5 - Ready for next command
            "ALARM": bool(status & OutputSignal.ALM_A),       # Bit 7 - Alarm active (A-contact)
            "INFO": bool(status & OutputSignal.INFO),         # Bit 6 - Information occurring
            "HOME_END": bool(status & OutputSignal.HOME_END), # Bit 4 - Homing complete
            "SYS_BSY": bool(status & OutputSignal.SYS_BSY),   # Bit 8 - Internal processing
            "AREA0": bool(status & OutputSignal.AREA0),       # Bit 9 - Area output 0
            "AREA1": bool(status & OutputSignal.AREA1),       # Bit 10 - Area output 1
            "TIM": bool(status & OutputSignal.TIM),           # Bit 12 - Timing signal
        }
