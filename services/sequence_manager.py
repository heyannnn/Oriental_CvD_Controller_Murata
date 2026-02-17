"""
Sequence Manager - Main state machine coordinator
Manages overall system state and coordinates motor controller + video player
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """System-wide state machine"""
    BOOT = "boot"
    HOMING = "homing"
    READY = "ready"
    STANDBY = "standby"
    RUNNING = "running"
    FINISHED = "finished"
    STOPPED = "stopped"
    ERROR = "error"


class SequenceManager:
    """
    Main sequence coordinator.
    Manages system state and coordinates all components.

    Flow:
      BOOT → HOMING → READY → (START) → STANDBY → RUNNING → FINISHED → READY
                                  ↑                              ↓
                                  └────────── (RESET) ──────────┘
    """

    def __init__(self, motor_controller, network_sync, config=None):
        """
        Initialize sequence manager.

        Args:
            motor_controller: MotorController instance
            network_sync: NetworkSync instance for OSC
            config: Station config dict (optional)
        """
        self.motor_controller = motor_controller
        self.network_sync = network_sync
        self.state = SystemState.BOOT

        # Looping configuration
        self.is_looping = False
        self.cycle_count = 0
        self.loop_delay_sec = config.get('loop_delay_sec', 3.0) if config else 3.0

        # Video synchronization (delay for first start only)
        self.video_sync_delay_sec = config.get('video_sync_delay_sec', 1.0) if config else 1.0

        logger.info("Sequence manager initialized")
        logger.info(f"Video sync delay: {self.video_sync_delay_sec}s (first cycle only)")

    async def initialize(self):
        """
        System initialization - auto-home motors.
        Called on boot.
        """
        logger.info("=== SYSTEM BOOT ===")
        self.state = SystemState.BOOT

        # Start motor homing
        logger.info("Starting motor homing...")
        self.state = SystemState.HOMING

        # MotorController will callback when ready
        await self.motor_controller.initialize()

    async def initialize_video_only(self):
        """
        System initialization for video-only stations (no motors).
        Auto-starts video playback.
        """
        import asyncio

        logger.info("=== SYSTEM BOOT (VIDEO ONLY) ===")
        self.state = SystemState.BOOT

        # Enable looping mode
        self.is_looping = True
        self.cycle_count = 1

        # Send start to video player (NormalOperation.csv)
        logger.info("Sending START signal to video player...")
        self.network_sync.send_video_command("start")

        # Wait for video sync delay
        logger.info(f"Waiting {self.video_sync_delay_sec}s for video intro...")
        await asyncio.sleep(self.video_sync_delay_sec)

        self.state = SystemState.RUNNING
        logger.info("=== VIDEO ONLY STATION RUNNING ===")

    def on_motor_ready(self):
        """
        Callback from MotorController when homing complete (or no homing needed).
        Auto-starts operation: send video command, wait delay, start motors.
        """
        logger.info("=== MOTOR READY - AUTO STARTING ===")

        # Auto-start operation after homing
        import asyncio
        if self.motor_controller and self.motor_controller._event_loop:
            asyncio.run_coroutine_threadsafe(
                self._auto_start_operation(),
                self.motor_controller._event_loop
            )
        else:
            # Fallback if no event loop (shouldn't happen)
            logger.warning("No event loop available for auto-start")
            self.state = SystemState.READY

    async def _auto_start_operation(self):
        """
        Auto-start operation after homing completes.
        Sends video command, waits for sync delay, then starts motors.
        """
        import asyncio

        # Enable looping mode
        self.is_looping = True
        self.cycle_count = 1

        # Send start to video player (NormalOperation.csv)
        logger.info("Sending START signal to video player...")
        self.network_sync.send_video_command("start")

        # Broadcast start to all stations (if this is master)
        self.network_sync.broadcast_start()

        # Wait for video sync delay
        logger.info(f"Waiting {self.video_sync_delay_sec}s for video intro...")
        await asyncio.sleep(self.video_sync_delay_sec)

        # Start motor operation
        logger.info(f"=== Starting cycle {self.cycle_count} ===")
        self.state = SystemState.RUNNING

        if self.motor_controller:
            self.motor_controller.start_operation(op_no=0)

        logger.info("=== SYSTEM RUNNING ===")

    def on_motor_finished(self):
        """
        Callback from MotorController when operation finishes.
        If looping is enabled, wait and restart the operation.
        """
        logger.info("=== OPERATION FINISHED ===")
        self.state = SystemState.FINISHED

        # Send finished signal to video player
        self.network_sync.send_video_command("finished")

        # Check if we should loop
        if self.is_looping:
            # Schedule next cycle
            import asyncio
            if self.motor_controller._event_loop:
                asyncio.run_coroutine_threadsafe(
                    self._loop_next_cycle(),
                    self.motor_controller._event_loop
                )
            else:
                logger.warning("Cannot loop - event loop not available")
                self.state = SystemState.READY
        else:
            # Return to ready state
            self.state = SystemState.READY
            logger.info("System ready for next operation")

    def on_motor_error(self, error_msg):
        """
        Callback from MotorController on error.
        """
        logger.error(f"=== MOTOR ERROR: {error_msg} ===")
        self.state = SystemState.ERROR

        # Send error to video player
        self.network_sync.send_video_command("error", {"message": error_msg})

    def on_return_to_zero_complete(self):
        """
        Callback from MotorController when return-to-zero motion completes.
        This is called after stop() for stations with return_to_zero_on_stop enabled.
        """
        logger.info("=== RETURN TO ZERO COMPLETE ===")
        logger.info("Motor has returned to home position (0)")

        # Send finished signal to video player (optional, for video sync)
        self.network_sync.send_video_command("returned_to_zero")

    # ========================================================================
    # Keyboard Commands (from KeyboardHandler)
    # ========================================================================

    async def on_start_pressed(self):
        """
        START button pressed (V key when not running).
        Flow: READY → STANDBY → RUNNING (looping handled by video completion)
        Waits video_sync_delay_sec before starting motor to sync with video intro.
        """
        if self.state != SystemState.READY and self.state != SystemState.STANDBY and self.state != SystemState.STOPPED:
            logger.warning(f"Cannot start - system not ready (state={self.state.value})")
            return

        logger.info("=== START PRESSED ===")

        # Enable looping mode (will continue after each operation finishes)
        self.is_looping = True
        self.cycle_count = 1

        # Move to standby
        self.state = SystemState.STANDBY
        logger.info("Sending START signal...")

        # Send start to video player (first cycle uses NormalOperation.csv)
        self.network_sync.send_video_command("start")

        # Broadcast start to all stations (if this is master)
        self.network_sync.broadcast_start()

        # Wait for video intro to play before starting motor
        import asyncio
        logger.info(f"Waiting {self.video_sync_delay_sec}s for video intro to play...")
        await asyncio.sleep(self.video_sync_delay_sec)

        # Start motor operation
        logger.info(f"=== Starting cycle {self.cycle_count} ===")
        self.state = SystemState.RUNNING

        # Start operation 0 (or read from config)
        if self.motor_controller:
            self.motor_controller.start_operation(op_no=0)

        logger.info("=== SYSTEM RUNNING ===")

    def on_stop_pressed(self):
        """
        STOP button pressed (V key when running).
        Stop motors (return to zero if configured) and disable looping.
        """
        logger.info("=== STOP PRESSED ===")

        # Disable looping mode
        self.is_looping = False
        logger.info("Looping mode disabled")

        # Stop motor (may return to zero depending on config)
        if self.motor_controller:
            self.motor_controller.stop()

        # Send stop to video player
        self.network_sync.send_video_command("stop")

        # Broadcast stop to all stations
        self.network_sync.broadcast_stop()

        self.state = SystemState.STANDBY
        logger.info("System in standby - motors at position 0 or stopped")

    async def _loop_next_cycle(self):
        """
        Internal method to handle looping delay and restart.
        Called from on_motor_finished when looping is enabled.
        """
        import asyncio

        # Wait for the configured delay
        logger.info(f"Waiting {self.loop_delay_sec}s before next cycle...")
        await asyncio.sleep(self.loop_delay_sec)

        # Check if looping is still enabled (user might have pressed stop during delay)
        if not self.is_looping:
            logger.info("Looping cancelled")
            self.state = SystemState.READY
            return

        # Increment cycle count and restart
        self.cycle_count += 1
        logger.info(f"=== Starting cycle {self.cycle_count} ===")
        self.state = SystemState.RUNNING

        # Send standby signal to reload Sync.csv for this cycle
        self.network_sync.send_video_command("standby")

        # Start operation 0 again
        self.motor_controller.start_operation(op_no=0)

    async def on_reset_pressed(self):
        """
        RESET button pressed.
        Return to home and ready state.
        """
        logger.info("=== RESET PRESSED ===")

        # Disable looping
        self.is_looping = False

        # Stop everything first
        self.motor_controller.stop()
        self.network_sync.send_video_command("reset")
        self.network_sync.broadcast_reset()

        # Reset to home
        logger.info("Resetting to home position...")
        self.state = SystemState.HOMING
        await self.motor_controller.reset_to_home()

        # MotorController will callback on_motor_ready when done

    def on_clear_alarm_pressed(self):
        """
        CLEAR ALARM button pressed (Ctrl key).
        Clear motor alarm and attempt recovery.
        """
        logger.info("=== CLEAR ALARM PRESSED ===")

        if self.motor_controller:
            self.motor_controller.clear_alarm()

            # If in error state, try to return to ready
            if self.state == SystemState.ERROR:
                self.state = SystemState.READY
                logger.info("System recovered from error state")
        else:
            logger.warning("No motor controller - cannot clear alarm")

    # ========================================================================
    # OSC Network Commands (received from station 2)
    # ========================================================================

    async def on_network_start(self):
        """
        START command received via OSC (for non-keyboard stations).
        Same as on_start_pressed but without keyboard.
        """
        logger.info("START command received via network")
        await self.on_start_pressed()

    def on_network_stop(self):
        """STOP command received via OSC"""
        logger.info("STOP command received via network")
        self.on_stop_pressed()

    async def on_network_reset(self):
        """RESET command received via OSC"""
        logger.info("RESET command received via network")
        await self.on_reset_pressed()

    # ========================================================================
    # Status
    # ========================================================================

    def get_state(self) -> SystemState:
        """Get current system state"""
        return self.state

    def is_ready(self) -> bool:
        """Check if system is ready"""
        return self.state == SystemState.READY

    def is_running(self) -> bool:
        """Check if system is currently running (for V key toggle)"""
        return self.state == SystemState.RUNNING