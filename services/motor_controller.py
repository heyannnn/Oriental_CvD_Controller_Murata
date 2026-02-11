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

        # Return to zero behavior
        self.return_to_zero_on_stop = config.get('return_to_zero_on_stop', False)

        # Homing behavior - some stations don't need homing
        self.homing_required = config.get('homing_required', True)

        # Create motor driver
        serial_config = config['serial']
        motor_config = config['motors'][0]  # Assume single motor for now

        self.driver = MotorDriver(
            port=serial_config['port'],
            slave_id=motor_config['slave_id']
        )

        self.current_operation = None
        self._monitor_task = None
        self._event_loop = None  # Will be set when async context is available

    async def initialize(self):
        """
        Initialize and auto-home motor.
        This is called on system boot.
        """
        # Save event loop reference for later use from non-async contexts
        self._event_loop = asyncio.get_running_loop()

        logger.info("=" * 70)
        logger.info("Initializing motor controller...")
        logger.info("=" * 70)

        # Connect to motor
        try:
            self.driver.connect()
            logger.info("✓ Motor driver connected")
        except Exception as e:
            logger.error(f"✗ Failed to connect to motor: {e}")
            self.state = MotorState.ERROR
            if self._on_error:
                self._on_error(f"Connection failed: {e}")
            return

        # Start homing (if required)
        if self.homing_required:
            logger.info("Starting automatic homing to position 0...")
            self.state = MotorState.HOMING

            try:
                await self.driver.start_homing(timeout=100)

                # Read final position to verify
                final_pos = self.driver.read_position()
                logger.info("=" * 70)
                logger.info(f"✓ Homing complete - Motor READY at position: {final_pos}")
                logger.info("=" * 70)

                self.state = MotorState.READY

                if self._on_ready:
                    self._on_ready()

            except Exception as e:
                logger.error(f"✗ Homing failed: {e}")
                self.state = MotorState.ERROR
                if self._on_error:
                    self._on_error(f"Homing failed: {e}")
        else:
            logger.info("Homing not required for this station - skipping")
            logger.info("=" * 70)
            logger.info("✓ Motor READY (no homing)")
            logger.info("=" * 70)
            self.state = MotorState.READY

            if self._on_ready:
                self._on_ready()

    def start_operation(self, op_no=0):
        """
        Start MEXE operation and monitor until complete.

        Args:
            op_no: MEXE operation number
        """
        if self.state != MotorState.READY:
            logger.warning(f"⚠ Cannot start operation - motor not ready (state={self.state.value})")
            return

        # Read current position before starting
        current_pos = self.driver.read_position()
        logger.info("=" * 70)
        logger.info(f"Starting MEXE operation {op_no} from position: {current_pos}")
        logger.info("=" * 70)

        self.state = MotorState.RUNNING
        self.current_operation = op_no

        # Start operation
        self.driver.start_operation(op_no=op_no)

        # Start monitoring task (handle both sync and async contexts)
        # If called from keyboard thread, use saved event loop
        if self._event_loop is not None:
            # Schedule in the main event loop (works from any thread)
            self._monitor_task = asyncio.run_coroutine_threadsafe(self._monitor_operation(), self._event_loop)
        else:
            # No saved loop yet - this shouldn't happen after initialize()
            logger.error("Cannot start monitoring - event loop not available")
            return

    async def _monitor_operation(self):
        """
        Monitor operation until completion.
        Uses RUNNING_DATA_NO register to detect true completion (not just motion stop).
        This handles operations with dwell times, retracts, or multi-step moves correctly.
        """
        logger.info(f"Monitoring operation {self.current_operation}...")
        logger.info(f"Callback set: {self._on_finished is not None}")

        # Wait a moment for operation to start
        await asyncio.sleep(0.5)

        # Monitor until operation completes
        start_time = time.time()
        last_log_time = 0
        operation_started = False

        while True:
            # Read running operation number from driver
            running_op = self.driver.read_running_operation()
            moving = self.driver.is_moving()
            ready = self.driver.is_ready()
            in_pos = self.driver.is_in_position()
            position = self.driver.read_position()
            elapsed = time.time() - start_time

            # Check if operation started
            if not operation_started and running_op == self.current_operation:
                operation_started = True
                logger.info(f"Operation {self.current_operation} confirmed started (RUNNING_DATA_NO={running_op})")

            # Log status every 0.5 seconds to avoid spam
            if elapsed - last_log_time >= 0.5:
                logger.info(f"Op {self.current_operation}: {elapsed:.1f}s | Pos: {position:8d} | RUNNING_OP: {running_op} | MOVE: {moving} | IN_POS: {in_pos}")
                last_log_time = elapsed

            # Detect operation completion: RUNNING_DATA_NO becomes -1
            if operation_started and running_op == -1:
                # Operation truly complete (driver says so, not just motion stopped)
                logger.info(f"✓ Operation {self.current_operation} FINISHED - Final pos: {position} ({elapsed:.1f}s)")
                logger.info(f"  RUNNING_DATA_NO = -1 (operation complete)")
                self.state = MotorState.FINISHED

                if self._on_finished:
                    logger.info("Calling on_finished callback")
                    try:
                        self._on_finished()
                    except Exception as e:
                        logger.error(f"Error in on_finished callback: {e}", exc_info=True)
                else:
                    logger.warning("No on_finished callback set!")

                # Return to ready state
                await asyncio.sleep(0.5)
                self.state = MotorState.READY
                break

            # Timeout safety (if operation doesn't start or complete in reasonable time)
            if elapsed > 300:  # 5 minutes timeout
                logger.error(f"Operation monitoring timeout after {elapsed:.1f}s")
                logger.error(f"  RUNNING_DATA_NO = {running_op}, expected 0 or -1")
                self.state = MotorState.ERROR
                break

            await asyncio.sleep(0.1)

    def stop(self):
        """
        Stop operation.
        If return_to_zero_on_stop is enabled, stop first then return to position 0 slowly.
        Otherwise, just stop in current position.
        """
        logger.info("Stop requested")

        # Cancel monitoring task first
        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except Exception as e:
                logger.debug(f"Could not cancel monitor task: {e}")

        # First, send STOP signal to halt current motion immediately
        logger.info("Sending STOP signal...")
        self.driver.stop()

        # Check if we should return to zero after stopping
        if self.return_to_zero_on_stop:
            import time
            time.sleep(0.3)  # Brief pause to ensure motor is stopped
            logger.info("Returning to position 0 via direct operation...")
            self.driver.return_to_zero(velocity=1000)  # Slow speed for safety
            # Note: Motor will move to position 0, we stay in READY state

        self.state = MotorState.READY

    def clear_alarm(self):
        """Clear motor alarm"""
        logger.info("Clearing motor alarm...")
        self.driver.clear_alarm()
        logger.info("Alarm cleared - motor should be ready")

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
            try:
                self._monitor_task.cancel()
            except Exception as e:
                logger.debug(f"Could not cancel monitor task during cleanup: {e}")
        self.driver.close()
