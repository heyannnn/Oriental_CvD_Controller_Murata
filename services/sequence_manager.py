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

    def __init__(self, motor_controller, network_sync):
        """
        Initialize sequence manager.

        Args:
            motor_controller: MotorController instance
            network_sync: NetworkSync instance for OSC
        """
        self.motor_controller = motor_controller
        self.network_sync = network_sync
        self.state = SystemState.BOOT

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
        """
        logger.info("=== OPERATION FINISHED ===")
        self.state = SystemState.FINISHED

        # Send finished signal to video player
        self.network_sync.send_video_command("finished")

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
        Flow: READY → STANDBY → RUNNING
        """
        if self.state != SystemState.READY:
            logger.warning(f"Cannot start - system not ready (state={self.state.value})")
            return

        logger.info("=== START PRESSED ===")

        # Move to standby
        self.state = SystemState.STANDBY
        logger.info("Sending STANDBY signal...")

        # Send standby to video player
        self.network_sync.send_video_command("standby")

        # Broadcast standby to all stations (if this is station 2)
        self.network_sync.broadcast_start()

        # Start motor operation
        logger.info("Starting motor operation...")
        self.state = SystemState.RUNNING

        # Start operation 0 (or read from config)
        self.motor_controller.start_operation(op_no=0)

        logger.info("=== SYSTEM RUNNING ===")

    def on_stop_pressed(self):
        """
        STOP button pressed.
        Emergency stop all motors.
        """
        logger.info("=== STOP PRESSED ===")

        # Stop motor
        self.motor_controller.stop()

        # Send stop to video player
        self.network_sync.send_video_command("stop")

        # Broadcast stop to all stations
        self.network_sync.broadcast_stop()

        self.state = SystemState.STOPPED
        logger.info("System stopped")

    async def on_reset_pressed(self):
        """
        RESET button pressed.
        Return to home and ready state.
        """
        logger.info("=== RESET PRESSED ===")

        # Stop everything first
        self.motor_controller.stop()
        self.network_sync.send_video_command("reset")
        self.network_sync.broadcast_reset()

        # Reset to home
        logger.info("Resetting to home position...")
        self.state = SystemState.HOMING
        await self.motor_controller.reset_to_home()

        # MotorController will callback on_motor_ready when done

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
