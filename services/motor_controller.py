"""
Motor Controller - State machine for motor operations
Manages homing, ready state, and operation execution per station
"""

import logging
import asyncio
import time
from enum import Enum
from services.motor_driver import MotorDriver

logger = logging.getLogger(__name__)


class MotorState(Enum):
    """Motor state machine states"""
    DISCONNECTED = "disconnected"
    HOMING = "homing"
    READY = "ready"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"


class MotorController:
    """
    Motor controller with state machine.
    Handles automatic homing on boot and operation execution.
    """

    def __init__(self, config, on_ready=None, on_finished=None, on_error=None):
        """
        Initialize motor controller.

        Args:
            config: Motor config dict with serial and motor settings
            on_ready: Callback when motor becomes ready after homing
            on_finished: Callback when operation finishes
            on_error: Callback on error
        """
        self.config = config
        self.state = MotorState.DISCONNECTED

        # Callbacks
        self._on_ready = on_ready
        self._on_finished = on_finished
        self._on_error = on_error

        # Create motor driver
        serial_config = config['serial']
        motor_config = config['motors'][0]  # Assume single motor for now

        self.driver = MotorDriver(
            port=serial_config['port'],
            slave_id=motor_config['slave_id']
        )

        self.current_operation = None
        self._monitor_task = None

    async def initialize(self):
        """
        Initialize and auto-home motor.
        This is called on system boot.
        """
        logger.info("Initializing motor controller...")

        # Connect to motor
        try:
            self.driver.connect()
        except Exception as e:
            logger.error(f"Failed to connect to motor: {e}")
            self.state = MotorState.ERROR
            if self._on_error:
                self._on_error(f"Connection failed: {e}")
            return

        # Start homing
        logger.info("Starting automatic homing...")
        self.state = MotorState.HOMING

        try:
            await self.driver.start_homing(timeout=100)

            # Homing complete
            logger.info("Homing complete - motor READY")
            self.state = MotorState.READY

            if self._on_ready:
                self._on_ready()

        except Exception as e:
            logger.error(f"Homing failed: {e}")
            self.state = MotorState.ERROR
            if self._on_error:
                self._on_error(f"Homing failed: {e}")

    def start_operation(self, op_no=0):
        """
        Start MEXE operation and monitor until complete.

        Args:
            op_no: MEXE operation number
        """
        if self.state != MotorState.READY:
            logger.warning(f"Cannot start operation - motor not ready (state={self.state.value})")
            return

        logger.info(f"Starting operation {op_no}")
        self.state = MotorState.RUNNING
        self.current_operation = op_no

        # Start operation
        self.driver.start_operation(op_no=op_no)

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_operation())

    async def _monitor_operation(self):
        """
        Monitor operation until completion.
        Sends finished callback when MOVE flag clears.
        """
        logger.info("Monitoring operation...")

        # Wait a moment for motion to start
        await asyncio.sleep(0.5)

        # Monitor until motion stops
        start_time = time.time()
        while True:
            moving = self.driver.is_moving()
            elapsed = time.time() - start_time

            if not moving and elapsed > 1.0:
                # Motion complete
                logger.info(f"Operation {self.current_operation} finished ({elapsed:.1f}s)")
                self.state = MotorState.FINISHED

                if self._on_finished:
                    self._on_finished()

                # Return to ready state
                await asyncio.sleep(0.5)
                self.state = MotorState.READY
                break

            await asyncio.sleep(0.1)

    def stop(self):
        """Emergency stop"""
        logger.info("Emergency stop")
        self.driver.stop()

        # Cancel monitoring task
        if self._monitor_task:
            self._monitor_task.cancel()

        self.state = MotorState.READY

    async def reset_to_home(self):
        """
        Reset to home position.
        Re-runs homing sequence.
        """
        logger.info("Resetting to home...")
        self.state = MotorState.HOMING

        try:
            await self.driver.start_homing(timeout=100)
            logger.info("Reset complete - motor READY")
            self.state = MotorState.READY

            if self._on_ready:
                self._on_ready()

        except Exception as e:
            logger.error(f"Reset homing failed: {e}")
            self.state = MotorState.ERROR
            if self._on_error:
                self._on_error(f"Reset failed: {e}")

    def get_state(self) -> MotorState:
        """Get current motor state"""
        return self.state

    def is_ready(self) -> bool:
        """Check if motor is ready"""
        return self.state == MotorState.READY

    def is_running(self) -> bool:
        """Check if operation is running"""
        return self.state == MotorState.RUNNING

    def close(self):
        """Cleanup"""
        if self._monitor_task:
            self._monitor_task.cancel()
        self.driver.close()
