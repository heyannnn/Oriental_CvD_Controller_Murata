"""
Motor Controller - State machine for motor operations
Manages homing, ready state, and operation execution per station
Supports multiple motors per station (chained on same RS485 bus)
Controls video player, LED animations, and sends status to master (Pi-02)
"""

import logging
import asyncio
import time
from enum import Enum
from services.motor_driver import MotorDriver
from services.mp4_player import MP4Player

# LED controller - optional, only for stations 07 and 10
try:
    from services.led_controller import LEDController
    LED_AVAILABLE = True
except ImportError:
    LED_AVAILABLE = False

try:
    from pythonosc import udp_client
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False


logger = logging.getLogger(__name__)


class MotorState(Enum):
    """Motor state machine states"""
    DISCONNECTED = "disconnected"
    HOMING = "homing"
    HOME_END = "home_end"      # Homing complete, waiting for start
    RUNNING = "running"
    READY = "ready"            # Operation complete, can loop
    ERROR = "error"
    RESETTING = "resetting"    # Reset in progress (stop -> clear alarm -> home)


class MotorController:
    """
    Motor controller with state machine.
    Handles homing, operation execution, auto-reset, video control, and status reporting.
    Supports multiple motors per station (reads from config['motors'] array).
    """

    def __init__(self, config):
        """
        Initialize motor controller.

        Args:
            config: Station config dict with serial and motor settings
        """
        self.config = config
        self.station_id = config.get('station_id', '00')
        self.state = MotorState.DISCONNECTED

        # Callbacks (set by main.py or sequence_manager)
        self._on_home_end = None      # Called when homing complete
        self._on_ready = None         # Called when operation complete
        self._on_error = None         # Called on error
        self._on_state_change = None  # Called on any state change

        # Return to zero behavior
        self.return_to_zero_on_stop = config.get('return_to_zero_on_stop', False)

        # Homing behavior - some stations don't need homing
        self.homing_required = config.get('homing_required', True)

        # HOMES sensor detection (stations 5, 8, 9)
        self.check_homes_during_running = config.get('check_homes_during_running', False)

        # Loop behavior
        self.is_looping = False
        self.cycle_count = 0
        self.loop_delay_sec = config.get('loop_delay_sec', 0.0)
        self.video_sync_delay_sec = config.get('video_sync_delay_sec', 1.0)

        # Video-only station (station 11) - no motors, just loop video
        self.video_only = config.get('video_only', False)
        self.sync_video_duration_sec = config.get('sync_video_duration_sec', 30.0)

        # Create motor drivers - one per motor in config
        serial_config = config.get('serial', {})
        motors_config = config.get('motors', [])

        self.drivers = []
        self.motor_names = []

        for motor_config in motors_config:
            port = motor_config.get('port', serial_config.get('port', '/dev/ttyAMA0'))
            slave_id = motor_config['slave_id']
            name = motor_config.get('name', f'motor_{slave_id}')

            driver = MotorDriver(port=port, slave_id=slave_id)
            self.drivers.append(driver)
            self.motor_names.append(name)

        if self.video_only:
            logger.info("Motor controller configured as VIDEO-ONLY station")
        else:
            logger.info(f"Motor controller configured with {len(self.drivers)} motor(s)")

        # Video player control
        self.mp4_player = MP4Player(config)

        # LED controller (stations 07 and 10 only)
        self.led_controller = None
        led_config = config.get('led', {})
        if led_config.get('enabled', False) and self.station_id in ["07", "10"] and LED_AVAILABLE:
            try:
                self.led_controller = LEDController(
                    station_id=self.station_id,
                    video_sync_delay_sec=self.video_sync_delay_sec
                )
                logger.info(f"LED controller initialized for station {self.station_id}")
            except Exception as e:
                logger.error(f"Failed to initialize LED controller: {e}")

        # OSC client for sending status to master (Pi-02)
        self.master_ip = config.get('network', {}).get('master_ip', 'pi-controller-02.local')
        self.master_port = config.get('network', {}).get('master_port', 10000)
        self.status_client = None
        if OSC_AVAILABLE:
            try:
                self.status_client = udp_client.SimpleUDPClient(self.master_ip, self.master_port)
            except Exception as e:
                logger.warning(f"Could not create status client: {e}")

        self.current_operation = None
        self._monitor_task = None
        self._delayed_start_task = None
        self._event_loop = None
        self._abort_flag = False  # Set to True to abort running operations
        self._video_command_time = None  # Track when video command sent

    def _set_state(self, new_state):
        """Set state and notify callbacks"""
        old_state = self.state
        self.state = new_state
        logger.info(f"State: {old_state.value} -> {new_state.value}")

        # Send status to master
        self._send_status()

        # Notify state change callback
        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def _send_status(self):
        """Send current state to master (Pi-02) via OSC"""
        self._send_status_value(self.state.value)

    def _send_status_value(self, status_value):
        """Send specific status value to master (Pi-02) via OSC"""
        if not self.status_client:
            return

        try:
            # /status [station_id] [state]
            self.status_client.send_message("/status", [self.station_id, status_value])
            logger.debug(f"Sent status: /status {self.station_id} {status_value}")
        except Exception as e:
            logger.warning(f"Failed to send status: {e}")

    # ========================================================================
    # Initialization & Homing
    # ========================================================================

    async def initialize(self):
        """
        Initialize and auto-home all motors.
        Called on system boot.
        """
        self._event_loop = asyncio.get_running_loop()

        # Send "booting" status immediately so master knows we exist
        self._send_status_value("booting")

        # Wait 5 seconds on boot to let all stations power up and master to start listening
        logger.info("Waiting 5 seconds for all stations to boot...")
        await asyncio.sleep(5.0)

        logger.info("=" * 70)
        logger.info(f"Initializing motor controller ({len(self.drivers)} motor(s))...")
        logger.info("=" * 70)

        # Connect to all motors
        for i, driver in enumerate(self.drivers):
            try:
                driver.connect()
                logger.info(f"  {self.motor_names[i]} (slave_id={driver.slave_id}) connected")
            except Exception as e:
                logger.error(f"  Failed to connect {self.motor_names[i]}: {e}")
                self._set_state(MotorState.ERROR)
                if self._on_error:
                    self._on_error(f"Connection failed: {e}")
                return

        # Check if motors need homing
        if self.homing_required:
            all_homed = all(driver.is_home_complete() for driver in self.drivers)

            if all_homed:
                logger.info("All motors already homed (HOME_END=True)")
                self._set_state(MotorState.HOME_END)
                if self._on_home_end:
                    self._on_home_end()
            else:
                logger.info("Starting parallel homing...")
                self._set_state(MotorState.HOMING)

                try:
                    await self._parallel_homing(timeout=100)
                    self._set_state(MotorState.HOME_END)
                    if self._on_home_end:
                        self._on_home_end()
                except Exception as e:
                    logger.error(f"Homing failed: {e}")
                    self._set_state(MotorState.ERROR)
                    if self._on_error:
                        self._on_error(f"Homing failed: {e}")
        else:
            logger.info("Homing not required - skipping")
            self._set_state(MotorState.HOME_END)
            if self._on_home_end:
                self._on_home_end()

    async def _parallel_homing(self, timeout=100):
        """Home all motors in parallel."""
        needs_homing = []
        for i, driver in enumerate(self.drivers):
            if not driver.is_home_complete():
                needs_homing.append(i)
                logger.info(f"  {self.motor_names[i]}: needs homing")
            else:
                logger.info(f"  {self.motor_names[i]}: already homed")

        if not needs_homing:
            return

        # Send HOME command to all
        for i in needs_homing:
            self.drivers[i].send_home_command()

        # Wait for all HOME_END
        start_time = time.time()
        last_log_time = 0

        while True:
            elapsed = time.time() - start_time

            all_homed = True
            homed_count = 0
            for i in needs_homing:
                if self.drivers[i].is_home_complete():
                    homed_count += 1
                else:
                    all_homed = False

            if elapsed - last_log_time >= 0.05:
                logger.info(f"Homing: {elapsed:.1f}s | HOME_END: {homed_count}/{len(needs_homing)}")
                last_log_time = elapsed

            if all_homed:
                logger.info(f"Homing complete in {elapsed:.1f}s")
                for i in needs_homing:
                    self.drivers[i].clear_home_command()
                return

            if elapsed > timeout:
                for i in needs_homing:
                    self.drivers[i].clear_home_command()
                raise Exception(f"Homing timeout after {elapsed:.1f}s")

            await asyncio.sleep(0.2)

    # ========================================================================
    # OSC Command Handlers (called from main.py OSC listener)
    # ========================================================================

    def on_start(self):
        """Handle /start OSC command"""
        if self.state in [MotorState.HOMING, MotorState.RESETTING]:
            logger.warning(f"Ignoring /start - busy ({self.state.value})")
            return

        if self.state not in [MotorState.HOME_END, MotorState.READY]:
            logger.warning(f"Cannot start - state is {self.state.value}")
            return

        logger.info("=== START RECEIVED ===")
        self.is_looping = True
        self._abort_flag = False  # Clear abort flag on new start
        self.cycle_count = 1

        # Start LED animation
        if self.led_controller:
            self.led_controller.on_start()

        # Video-only station: just loop Sync.csv forever
        if self.video_only:
            self._set_state(MotorState.RUNNING)
            if self._event_loop:
                asyncio.run_coroutine_threadsafe(self._video_only_loop(), self._event_loop)
            return

        # Send video command
        self._video_command_time = time.time()  # Record timestamp
        self.mp4_player.send_command("start")

        # Wait for video sync delay, then start operation
        if self._event_loop:
            self._delayed_start_task = asyncio.run_coroutine_threadsafe(self._delayed_start(), self._event_loop)

    async def _delayed_start(self):
        """Wait for video sync delay, then start operation"""
        logger.info(f"Waiting {self.video_sync_delay_sec}s for video sync...")
        await asyncio.sleep(self.video_sync_delay_sec)
        if self._abort_flag:
            logger.info("Delayed start aborted")
            return
        self.start_operation(op_no=0)

    async def _video_only_loop(self):
        """Video-only station loop: send standby command every 30s to loop Sync.csv"""
        while self.is_looping:
            logger.info(f"Video-only: Sending standby (Sync.csv) - cycle {self.cycle_count}")
            self.mp4_player.send_command("standby")
            self.cycle_count += 1
            await asyncio.sleep(self.sync_video_duration_sec)

        logger.info("Video-only loop stopped")
        self._set_state(MotorState.HOME_END)

    def on_stop(self):
        """Handle /stop OSC command"""
        logger.info("=== STOP RECEIVED ===")
        self.is_looping = False
        self._abort_flag = True  # Signal running operations to abort

        # Cancel any pending delayed start
        if self._delayed_start_task:
            try:
                self._delayed_start_task.cancel()
            except:
                pass

        # Stop LED animation
        if self.led_controller:
            self.led_controller.on_stop()

        self.stop()
        self.mp4_player.send_command("stop")

    def on_reset(self):
        """Handle /reset OSC command - stop, clear alarm, home, wait"""
        logger.info("=== RESET RECEIVED ===")
        self.is_looping = False
        self._abort_flag = True  # Signal running operations to abort

        # Stop LED animation
        if self.led_controller:
            self.led_controller.on_stop()

        # Cancel any pending tasks
        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except:
                pass
        if self._delayed_start_task:
            try:
                self._delayed_start_task.cancel()
            except:
                pass

        self.mp4_player.send_command("stop")

        # Stations without homing_required (02, 03, 04, 10, 11): just stop and wait
        if not self.homing_required:
            logger.info("Homing not required - stopping and waiting for other stations")
            for driver in self.drivers:
                driver.stop()
            # Go to HOME_END state (ready to accept start when all stations ready)
            self._set_state(MotorState.HOME_END)
            return

        # Stations with homing_required (05, 06, 07, 08, 09): full reset
        self._set_state(MotorState.RESETTING)

        # Stop -> clear alarm -> home
        if self._event_loop:
            asyncio.run_coroutine_threadsafe(self._do_reset(), self._event_loop)

    async def _do_reset(self):
        """Perform reset sequence: stop -> clear alarm -> home -> wait"""
        # Stop all motors
        for driver in self.drivers:
            driver.stop()
        await asyncio.sleep(0.3)

        # Clear alarms
        for driver in self.drivers:
            driver.clear_alarm()
        await asyncio.sleep(0.3)

        # Home all motors
        self._set_state(MotorState.HOMING)
        try:
            await self._parallel_homing(timeout=100)
            self._set_state(MotorState.HOME_END)
            if self._on_home_end:
                self._on_home_end()
        except Exception as e:
            logger.error(f"Reset homing failed: {e}")
            self._set_state(MotorState.ERROR)
            if self._on_error:
                self._on_error(f"Reset failed: {e}")

    # ========================================================================
    # Operation Control
    # ========================================================================

    def start_operation(self, op_no=0):
        """Start MEXE operation on all motors"""
        if self.state not in [MotorState.HOME_END, MotorState.READY]:
            logger.warning(f"Cannot start operation - state is {self.state.value}")
            return

        logger.info(f"Starting operation {op_no} on {len(self.drivers)} motor(s)")
        self._set_state(MotorState.RUNNING)
        self.current_operation = op_no

        for i, driver in enumerate(self.drivers):
            motor_start_time = time.time()
            delay_ms = (motor_start_time - self._video_command_time) * 1000 if self._video_command_time else 0
            logger.info(f"  t({self.motor_names[i]}_start) - t(video_start) = {delay_ms:.1f}ms")
            driver.start_operation(op_no=op_no)

        if self._event_loop:
            self._monitor_task = asyncio.run_coroutine_threadsafe(
                self._monitor_operation(), self._event_loop
            )

    async def _monitor_operation(self):
        """Monitor operation until complete, check for alarms and HOMES"""
        await asyncio.sleep(0.3)

        ready_went_low = [False] * len(self.drivers)
        start_time = time.time()
        last_log_time = 0

        while True:
            # Check abort flag
            if self._abort_flag:
                logger.info("Monitor operation aborted")
                return

            elapsed = time.time() - start_time

            # Check for alarm
            for i, driver in enumerate(self.drivers):
                if driver.get_alarm_status():
                    logger.error(f"ALARM detected on {self.motor_names[i]}!")
                    await self._auto_reset()
                    return

            # Check for HOMES signal (stations 5, 8, 9)
            if self.check_homes_during_running:
                for i, driver in enumerate(self.drivers):
                    if driver.is_homes_detected():
                        logger.warning(f"HOMES detected on {self.motor_names[i]} during running!")
                        await self._auto_reset()
                        return

            # Check READY flags
            all_ready = True
            for i, driver in enumerate(self.drivers):
                ready = driver.is_ready()
                if not ready:
                    ready_went_low[i] = True
                motor_done = ready and ready_went_low[i]
                if not motor_done:
                    all_ready = False

            if elapsed - last_log_time >= 0.05:
                ready_count = sum(1 for i in range(len(self.drivers))
                                  if self.drivers[i].is_ready() and ready_went_low[i])
                logger.info(f"Op {self.current_operation}: {elapsed:.1f}s | READY: {ready_count}/{len(self.drivers)}")
                last_log_time = elapsed

            if all_ready:
                logger.info(f"Operation {self.current_operation} complete ({elapsed:.1f}s)")
                self._set_state(MotorState.READY)

                if self._on_ready:
                    try:
                        self._on_ready()
                    except Exception as e:
                        logger.error(f"Error in on_ready callback: {e}")

                # Handle looping
                if self.is_looping:
                    await self._loop_next_cycle()
                return

            if elapsed > 60000:
                logger.error("Operation timeout")
                self._set_state(MotorState.ERROR)
                return

            await asyncio.sleep(0.2)

    async def _loop_next_cycle(self):
        """Handle loop to next cycle"""
        if not self.is_looping:
            return

        if self.loop_delay_sec > 0:
            logger.info(f"Waiting {self.loop_delay_sec}s before next cycle...")
            await asyncio.sleep(self.loop_delay_sec)

        if not self.is_looping:
            return

        self.cycle_count += 1
        logger.info(f"=== Starting cycle {self.cycle_count} ===")

        # Start LED animation for this cycle (skip sync delay on loop cycles)
        if self.led_controller:
            self.led_controller.on_start(skip_sync_delay=True)

        self._video_command_time = time.time()  # Record timestamp
        self.mp4_player.send_command("standby")
        self.start_operation(op_no=0)

    async def _auto_reset(self):
        """Auto-reset on alarm or HOMES detection: stop -> clear -> home -> restart loop"""
        logger.info("=== AUTO RESET ===")

        # Stop
        for driver in self.drivers:
            driver.stop()
        await asyncio.sleep(0.3)

        # Clear alarm
        for driver in self.drivers:
            driver.clear_alarm()
        await asyncio.sleep(0.3)

        # Home
        self._set_state(MotorState.HOMING)
        try:
            await self._parallel_homing(timeout=100)
            self._set_state(MotorState.HOME_END)

            # Auto-restart loop
            if self.is_looping:
                logger.info("Auto-restarting operation after reset...")
                self.mp4_player.send_command("start")
                await asyncio.sleep(self.video_sync_delay_sec)
                self.start_operation(op_no=0)

        except Exception as e:
            logger.error(f"Auto-reset failed: {e}")
            self._set_state(MotorState.ERROR)

    def stop(self):
        """Stop all motors"""
        logger.info(f"Stopping {len(self.drivers)} motor(s)")

        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except:
                pass

        for i, driver in enumerate(self.drivers):
            driver.stop()

        if self.return_to_zero_on_stop:
            time.sleep(0.3)
            for i, driver in enumerate(self.drivers):
                driver.return_to_zero(velocity=5000)

            if self._event_loop:
                self._monitor_task = asyncio.run_coroutine_threadsafe(
                    self._monitor_return_to_zero(), self._event_loop
                )
        else:
            self._set_state(MotorState.HOME_END)

    async def _monitor_return_to_zero(self):
        """Monitor return to zero until complete"""
        await asyncio.sleep(0.3)

        # Check if already at zero
        already_at_zero = []
        for i, driver in enumerate(self.drivers):
            pos = driver.read_position()
            ready = driver.is_ready()
            at_zero = (abs(pos) < 10) and ready
            already_at_zero.append(at_zero)
            if at_zero:
                logger.info(f"  {self.motor_names[i]}: already at 0")

        if all(already_at_zero):
            logger.info("Return to zero complete (already at 0)")
            self._set_state(MotorState.HOME_END)
            return

        ready_went_low = already_at_zero.copy()
        start_time = time.time()
        last_log_time = 0

        while True:
            elapsed = time.time() - start_time

            all_ready = True
            for i, driver in enumerate(self.drivers):
                ready = driver.is_ready()
                if not ready:
                    ready_went_low[i] = True
                motor_done = ready and ready_went_low[i]
                if not motor_done:
                    all_ready = False

            if elapsed - last_log_time >= 0.05:
                ready_count = sum(1 for i in range(len(self.drivers))
                                  if self.drivers[i].is_ready() and ready_went_low[i])
                logger.info(f"Return to zero: {elapsed:.1f}s | READY: {ready_count}/{len(self.drivers)}")
                last_log_time = elapsed

            if all_ready:
                logger.info(f"Return to zero complete ({elapsed:.1f}s)")
                self._set_state(MotorState.HOME_END)
                return

            if elapsed > 120:
                logger.error("Return to zero timeout")
                self._set_state(MotorState.ERROR)
                return

            await asyncio.sleep(0.2)

    def clear_alarm(self):
        """Clear alarm on all motors"""
        logger.info("Clearing alarms...")
        for driver in self.drivers:
            driver.clear_alarm()

    # ========================================================================
    # Status
    # ========================================================================

    def get_state(self) -> MotorState:
        """Get current motor state"""
        return self.state

    def is_running(self) -> bool:
        """Check if operation is running"""
        return self.state == MotorState.RUNNING

    def can_accept_start(self) -> bool:
        """Check if we can accept /start command"""
        return self.state in [MotorState.HOME_END, MotorState.READY]

    def close(self):
        """Cleanup"""
        if self._monitor_task:
            try:
                self._monitor_task.cancel()
            except:
                pass

        # Close LED controller
        if self.led_controller:
            self.led_controller.close()

        for i, driver in enumerate(self.drivers):
            driver.close()
            logger.info(f"  {self.motor_names[i]}: closed")
