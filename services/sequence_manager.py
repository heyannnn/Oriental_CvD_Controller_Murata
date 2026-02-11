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

        logger.info("Sequence manager initialized")

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

    def on_motor_ready(self):
        """
        Callback from MotorController when homing complete.
        """
        logger.info("=== MOTOR READY ===")
        self.state = SystemState.READY

        # Send ready signal to video player (OSC)
        self.network_sync.send_video_command("ready")

        logger.info("System ready - waiting for START command")

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

    # ========================================================================
    # Keyboard Commands (from KeyboardHandler)
    # ========================================================================

    def on_start_pressed(self):
        """
        START button pressed.
        Flow: READY → STANDBY → RUNNING (with looping enabled)
        """
        if self.state != SystemState.READY:
            logger.warning(f"Cannot start - system not ready (state={self.state.value})")
            return

        logger.info("=== START PRESSED ===")

        # Enable looping mode
        self.is_looping = True
        self.cycle_count = 1

        # Move to standby
        self.state = SystemState.STANDBY
        logger.info("Sending STANDBY signal...")

        # Send standby to video player
        self.network_sync.send_video_command("standby")

        # Broadcast standby to all stations (if this is station 2)
        self.network_sync.broadcast_start()

        # Start motor operation
        logger.info(f"Starting looping mode (delay: {self.loop_delay_sec}s between cycles)")
        logger.info(f"=== Starting cycle {self.cycle_count} ===")
        self.state = SystemState.RUNNING

        # Start operation 0 (or read from config)
        self.motor_controller.start_operation(op_no=0)

        logger.info("=== SYSTEM RUNNING ===")

    def on_stop_pressed(self):
        """
        STOP button pressed.
        Emergency stop all motors and disable looping.
        """
        logger.info("=== STOP PRESSED ===")

        # Disable looping mode
        self.is_looping = False
        logger.info("Looping mode disabled")

        # Stop motor
        self.motor_controller.stop()

        # Send stop to video player
        self.network_sync.send_video_command("stop")

        # Broadcast stop to all stations
        self.network_sync.broadcast_stop()

        self.state = SystemState.STOPPED
        logger.info("System stopped")

    async def _loop_next_cycle(self):
        """
        Internal method to handle looping delay and restart.
        Called from on_motor_finished when looping is enabled.
        """
        import asyncio

        # Wait for the configured delay
        logger.info(f"Waiting {self.loop_delay_sec}s before next cycle...")
        for remaining in range(int(self.loop_delay_sec), 0, -1):
            if not self.is_looping:
                logger.info("Looping cancelled during delay")
                self.state = SystemState.READY
                return
            logger.info(f"  {remaining}s...")
            await asyncio.sleep(1.0)

        # Check if looping is still enabled (user might have pressed stop during delay)
        if not self.is_looping:
            logger.info("Looping cancelled")
            self.state = SystemState.READY
            return

        # Increment cycle count and restart
        self.cycle_count += 1
        logger.info(f"=== Starting cycle {self.cycle_count} ===")
        self.state = SystemState.RUNNING

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

    def on_network_start(self):
        """
        START command received via OSC (for non-keyboard stations).
        Same as on_start_pressed but without keyboard.
        """
        logger.info("START command received via network")
        self.on_start_pressed()

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
