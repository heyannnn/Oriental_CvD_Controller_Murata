"""
Motor Controller - State machine for motor operations
Manages homing, ready state, and operation execution per station
Supports multiple motors per station (chained on same RS485 bus)
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
    Supports multiple motors per station (reads from config['motors'] array).
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
        self._on_return_to_zero_complete = None  # Callback when return to zero finishes

        # Return to zero behavior
        self.return_to_zero_on_stop = config.get('return_to_zero_on_stop', False)

        # Homing behavior - some stations don't need homing
        self.homing_required = config.get('homing_required', True)

        # Create motor drivers - one per motor in config
        serial_config = config['serial']
        motors_config = config.get('motors', [])

        self.drivers = []
        self.motor_names = []

        for motor_config in motors_config:
            # Use motor-specific port if defined, otherwise use default serial port
            port = motor_config.get('port', serial_config['port'])
            slave_id = motor_config['slave_id']
            name = motor_config.get('name', f'motor_{slave_id}')

            driver = MotorDriver(port=port, slave_id=slave_id)
            self.drivers.append(driver)
            self.motor_names.append(name)

        logger.info(f"Motor controller configured with {len(self.drivers)} motor(s)")

        self.current_operation = None
        self._monitor_task = None
        self._event_loop = None  # Will be set when async context is available

    async def initialize(self):
        """
        Initialize and auto-home all motors.
        This is called on system boot.
        """
        # Save event loop reference for later use from non-async contexts
        self._event_loop = asyncio.get_running_loop()

        logger.info("=" * 70)
        logger.info(f"Initializing motor controller ({len(self.drivers)} motor(s))...")
        logger.info("=" * 70)

        # Connect to all motors
        for i, driver in enumerate(self.drivers):
            try:
                driver.connect()
                logger.info(f"✓ Motor {self.motor_names[i]} (slave_id={driver.slave_id}) connected")
            except Exception as e:
                logger.error(f"✗ Failed to connect to {self.motor_names[i]}: {e}")
                self.state = MotorState.ERROR
                if self._on_error:
                    self._on_error(f"Connection failed for {self.motor_names[i]}: {e}")
                return

        # Check if motors need homing
        if self.homing_required:
            # Check if all motors are already homed
            all_homed = all(driver.is_home_complete() for driver in self.drivers)

            if all_homed:
                logger.info("All motors already homed (HOME_END=True) - skipping homing")
                logger.info("=" * 70)
                logger.info("✓ All motors READY (already homed)")
                logger.info("=" * 70)
                self.state = MotorState.READY

                if self._on_ready:
                    self._on_ready()
            else:
                # Home motors that need homing
                logger.info("HOME_END=False on some motors - Starting homing...")
                self.state = MotorState.HOMING

                try:
                    # Home motors one by one to avoid coroutine issues
                    for i, driver in enumerate(self.drivers):
                        if not driver.is_home_complete():
                            logger.info(f"  Starting homing for {self.motor_names[i]}...")
                            await driver.start_homing(timeout=100)
                            logger.info(f"  ✓ {self.motor_names[i]} homing complete")
                        else:
                            logger.info(f"  {self.motor_names[i]} already homed - skipping")

                    # Log final positions
                    logger.info("=" * 70)
                    for i, driver in enumerate(self.drivers):
                        final_pos = driver.read_position()
                        logger.info(f"✓ {self.motor_names[i]} homed - position: {final_pos}")
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
            logger.info(f"✓ All {len(self.drivers)} motor(s) READY (no homing needed)")
            logger.info("=" * 70)
            self.state = MotorState.READY

            if self._on_ready:
                self._on_ready()

    def start_operation(self, op_no=0):
        """
        Start MEXE operation on all motors and monitor until complete.

        Args:
            op_no: MEXE operation number (same for all motors)
        """
        if self.state != MotorState.READY:
            logger.warning(f"⚠ Cannot start operation - motors not ready (state={self.state.value})")
            return

        # Read current positions before starting
        logger.info("=" * 70)
        logger.info(f"Starting MEXE operation {op_no} on {len(self.drivers)} motor(s)")
        for i, driver in enumerate(self.drivers):
            current_pos = driver.read_position()
            logger.info(f"  {self.motor_names[i]}: starting from position {current_pos}")
        logger.info("=" * 70)

        self.state = MotorState.RUNNING
        self.current_operation = op_no

        # Start operation on all motors
        for i, driver in enumerate(self.drivers):
            driver.start_operation(op_no=op_no)
            logger.info(f"  {self.motor_names[i]}: operation started")

        # Start monitoring task (handle both sync and async contexts)
        if self._event_loop is not None:
            # Schedule in the main event loop (works from any thread)
            self._monitor_task = asyncio.run_coroutine_threadsafe(self._monitor_operation(), self._event_loop)
        else:
            logger.error("Cannot start monitoring - event loop not available")
            return

    async def _monitor_operation(self):
        """
        Monitor operation until ALL motors complete.
        Detects completion when MOVE flag goes False on all motors.
        """
        logger.info(f"Monitoring operation {self.current_operation} on {len(self.drivers)} motor(s)...")
        logger.info(f"Callback set: {self._on_finished is not None}")

        # Wait a moment for operation to start
        await asyncio.sleep(0.5)

        # Track state for each motor
        motor_states = []
        for i in range(len(self.drivers)):
            motor_states.append({
                'operation_started': False,
                'was_moving': False,
                'finished': False
            })

        # Monitor until all operations complete
        start_time = time.time()
        last_log_time = 0

        while True:
            elapsed = time.time() - start_time
            all_finished = True

            # Check each motor
            for i, driver in enumerate(self.drivers):
                if motor_states[i]['finished']:
                    continue  # Already finished, skip

                moving = driver.is_moving()
                position = driver.read_position()

                # Check if operation started (motor started moving)
                if not motor_states[i]['operation_started'] and moving:
                    motor_states[i]['operation_started'] = True
                    motor_states[i]['was_moving'] = True
                    logger.info(f"✓ {self.motor_names[i]} STARTED - Motor is moving")

                # Track if motor was moving
                if moving:
                    motor_states[i]['was_moving'] = True

                # Detect completion: MOVE flag goes False after motor was moving
                if motor_states[i]['operation_started'] and motor_states[i]['was_moving'] and not moving:
                    motor_states[i]['finished'] = True
                    logger.info(f"✓ {self.motor_names[i]} FINISHED - position: {position}")

                # Check if this motor is still running
                if not motor_states[i]['finished']:
                    all_finished = False

            # Log status every 0.5 seconds
            if elapsed - last_log_time >= 0.5:
                status_parts = []
                for i, driver in enumerate(self.drivers):
                    pos = driver.read_position()
                    moving = driver.is_moving()
                    status = "DONE" if motor_states[i]['finished'] else ("MOVE" if moving else "WAIT")
                    status_parts.append(f"{self.motor_names[i]}:{pos}({status})")
                logger.info(f"Op {self.current_operation}: {elapsed:.1f}s | {' | '.join(status_parts)}")
                last_log_time = elapsed

            # All motors finished
            if all_finished:
                logger.info(f"✓ Operation {self.current_operation} FINISHED on all {len(self.drivers)} motor(s)")
                logger.info(f"  Total duration: {elapsed:.1f}s")
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
                self.state = MotorState.READY
                break

            # Timeout safety
            if elapsed > 60000:  # 1000 minutes timeout
                logger.error(f"Operation monitoring timeout after {elapsed:.1f}s")
                self.state = MotorState.ERROR
                break

            await asyncio.sleep(0.1)

    async def _monitor_return_to_zero(self):
        """
        Monitor return-to-zero operation until ALL motors complete.
        Detects completion when MOVE flag goes False on all motors.
        """
        logger.info(f"Monitoring return to zero on {len(self.drivers)} motor(s)...")

        # Wait a moment for motion to start
        await asyncio.sleep(0.3)

        # Track state for each motor
        motor_states = []
        for i in range(len(self.drivers)):
            motor_states.append({
                'motion_started': False,
                'was_moving': False,
                'finished': False
            })

        start_time = time.time()
        last_log_time = 0

        while True:
            elapsed = time.time() - start_time
            all_finished = True

            # Check each motor
            for i, driver in enumerate(self.drivers):
                if motor_states[i]['finished']:
                    continue

                moving = driver.is_moving()
                position = driver.read_position()

                # Check if motion started
                if not motor_states[i]['motion_started'] and moving:
                    motor_states[i]['motion_started'] = True
                    motor_states[i]['was_moving'] = True
                    logger.info(f"  {self.motor_names[i]} returning to zero...")

                if moving:
                    motor_states[i]['was_moving'] = True

                # Detect completion
                if motor_states[i]['motion_started'] and motor_states[i]['was_moving'] and not moving:
                    motor_states[i]['finished'] = True
                    logger.info(f"✓ {self.motor_names[i]} at zero - position: {position}")

                if not motor_states[i]['finished']:
                    all_finished = False

            # Log status every 0.5 seconds
            if elapsed - last_log_time >= 0.5:
                status_parts = []
                for i, driver in enumerate(self.drivers):
                    pos = driver.read_position()
                    moving = driver.is_moving()
                    status = "DONE" if motor_states[i]['finished'] else ("MOVE" if moving else "WAIT")
                    status_parts.append(f"{self.motor_names[i]}:{pos}({status})")
                logger.info(f"Return to zero: {elapsed:.1f}s | {' | '.join(status_parts)}")
                last_log_time = elapsed

            # All motors finished
            if all_finished:
                logger.info(f"✓ Return to zero COMPLETE on all {len(self.drivers)} motor(s)")

                if self._on_return_to_zero_complete:
                    logger.info("Calling on_return_to_zero_complete callback")
                    try:
                        self._on_return_to_zero_complete()
                    except Exception as e:
                        logger.error(f"Error in on_return_to_zero_complete callback: {e}", exc_info=True)

                self.state = MotorState.READY
                break

            # Timeout safety
            if elapsed > 120:  # 2 minutes timeout
                logger.error(f"Return to zero timeout after {elapsed:.1f}s")
                self.state = MotorState.ERROR
                break

            await asyncio.sleep(0.1)

    def stop(self):
        """
        Stop operation on all motors.
        If return_to_zero_on_stop is enabled, stop first then return to position 0 slowly.
        """
        logger.info(f"Stop requested for {len(self.drivers)} motor(s)")

        # Cancel monitoring task first
        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except Exception as e:
                logger.debug(f"Could not cancel monitor task: {e}")

        # Send STOP signal to all motors
        logger.info("Sending STOP signal to all motors...")
        for i, driver in enumerate(self.drivers):
            driver.stop()
            logger.info(f"  {self.motor_names[i]}: stopped")

        # Check if we should return to zero after stopping
        if self.return_to_zero_on_stop:
            time.sleep(0.3)  # Brief pause to ensure motors are stopped
            logger.info("Returning all motors to position 0...")
            for i, driver in enumerate(self.drivers):
                driver.return_to_zero(velocity=5000)
                logger.info(f"  {self.motor_names[i]}: returning to zero")

            # Start monitoring task to detect when return-to-zero completes
            if self._event_loop is not None:
                self._monitor_task = asyncio.run_coroutine_threadsafe(
                    self._monitor_return_to_zero(),
                    self._event_loop
                )
                logger.info("Return to zero monitoring started")
            else:
                logger.warning("Cannot monitor return to zero - event loop not available")
                self.state = MotorState.READY
        else:
            self.state = MotorState.READY

    def clear_alarm(self):
        """Clear alarm on all motors"""
        logger.info(f"Clearing alarm on {len(self.drivers)} motor(s)...")
        for i, driver in enumerate(self.drivers):
            driver.clear_alarm()
            logger.info(f"  {self.motor_names[i]}: alarm cleared")
        logger.info("All alarms cleared - motors should be ready")

    async def reset_to_home(self):
        """
        Reset all motors to home position.
        Re-runs homing sequence on all motors.
        """
        logger.info(f"Resetting {len(self.drivers)} motor(s) to home...")
        self.state = MotorState.HOMING

        try:
            # Home motors one by one
            for i, driver in enumerate(self.drivers):
                logger.info(f"  Homing {self.motor_names[i]}...")
                await driver.start_homing(timeout=100)

            logger.info("Reset complete - all motors READY")
            for i, driver in enumerate(self.drivers):
                pos = driver.read_position()
                logger.info(f"  {self.motor_names[i]}: position {pos}")

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
        """Check if all motors are ready"""
        return self.state == MotorState.READY

    def is_running(self) -> bool:
        """Check if operation is running"""
        return self.state == MotorState.RUNNING

    def close(self):
        """Cleanup all motor connections"""
        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except Exception as e:
                logger.debug(f"Could not cancel monitor task during cleanup: {e}")

        for i, driver in enumerate(self.drivers):
            driver.close()
            logger.info(f"  {self.motor_names[i]}: connection closed")
