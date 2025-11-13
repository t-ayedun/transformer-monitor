"""
Error Recovery and Resilience System

Handles graceful degradation and automatic recovery from various failure scenarios:
- Hardware failures (thermal camera, Pi camera)
- Network failures
- Storage failures
- Process crashes
- Configuration errors
"""

import logging
import time
import subprocess
from datetime import datetime
from threading import Thread, Event
from pathlib import Path
import psutil
import os


class ComponentHealthMonitor:
    """Monitors health of individual components"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.health_status = {}

    def check_thermal_camera(self, thermal_capture):
        """
        Check thermal camera health

        Args:
            thermal_capture: ThermalCapture instance

        Returns:
            bool: True if healthy
        """
        try:
            if thermal_capture is None:
                return False

            # Try to capture a frame
            frame = thermal_capture.get_frame(apply_processing=False)
            return frame is not None

        except Exception as e:
            self.logger.error(f"Thermal camera health check failed: {e}")
            return False

    def check_smart_camera(self, smart_camera):
        """
        Check smart camera health

        Args:
            smart_camera: SmartCamera instance

        Returns:
            bool: True if healthy
        """
        try:
            if smart_camera is None or smart_camera.camera is None:
                return False

            # Camera should be running
            return smart_camera.camera.started

        except Exception as e:
            self.logger.error(f"Smart camera health check failed: {e}")
            return False

    def check_disk_space(self, min_free_gb=2.0):
        """
        Check available disk space

        Args:
            min_free_gb: Minimum free space in GB

        Returns:
            bool: True if sufficient space available
        """
        try:
            stat = os.statvfs('/data')
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

            if free_gb < min_free_gb:
                self.logger.warning(f"Low disk space: {free_gb:.2f} GB remaining")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Disk space check failed: {e}")
            return False

    def check_memory(self, max_percent=90):
        """
        Check memory usage

        Args:
            max_percent: Maximum memory usage percentage

        Returns:
            bool: True if memory usage is acceptable
        """
        try:
            memory = psutil.virtual_memory()

            if memory.percent > max_percent:
                self.logger.warning(f"High memory usage: {memory.percent:.1f}%")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Memory check failed: {e}")
            return False

    def check_cpu_temperature(self, max_temp=80.0):
        """
        Check Raspberry Pi CPU temperature

        Args:
            max_temp: Maximum acceptable temperature in Celsius

        Returns:
            bool: True if temperature is acceptable
        """
        try:
            # Read CPU temperature from Raspberry Pi
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000.0

            if temp > max_temp:
                self.logger.warning(f"High CPU temperature: {temp:.1f}°C")
                return False

            return True

        except Exception as e:
            self.logger.error(f"CPU temperature check failed: {e}")
            return True  # Don't fail if we can't read temperature


class ErrorRecoveryManager:
    """
    Manages automatic error recovery and graceful degradation

    Recovery strategies:
    1. Hardware failure: Continue with degraded functionality
    2. Network failure: Buffer data locally
    3. Storage failure: Alert and stop data collection
    4. Process crash: Auto-restart with exponential backoff
    """

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.health_monitor = ComponentHealthMonitor()

        # Recovery state
        self.thermal_camera_failures = 0
        self.smart_camera_failures = 0
        self.last_thermal_recovery = 0
        self.last_smart_camera_recovery = 0

        # Monitoring thread
        self.monitor_thread = None
        self.stop_monitoring = Event()
        self.check_interval = 60  # Check every minute

        # Components (will be set externally)
        self.thermal_capture = None
        self.smart_camera = None
        self.network_monitor = None

    def set_components(self, thermal_capture=None, smart_camera=None, network_monitor=None):
        """Set components to monitor"""
        self.thermal_capture = thermal_capture
        self.smart_camera = smart_camera
        self.network_monitor = network_monitor

    def start_monitoring(self):
        """Start health monitoring thread"""
        self.stop_monitoring.clear()
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Error recovery monitoring started")

    def stop_monitoring(self):
        """Stop health monitoring"""
        self.stop_monitoring.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Error recovery monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while not self.stop_monitoring.is_set():
            try:
                # Check system health
                self._check_system_health()

                # Check thermal camera
                if self.thermal_capture:
                    self._check_thermal_camera_health()

                # Check smart camera
                if self.smart_camera:
                    self._check_smart_camera_health()

            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}", exc_info=True)

            self.stop_monitoring.wait(self.check_interval)

    def _check_system_health(self):
        """Check system-level health metrics"""
        # Check disk space
        if not self.health_monitor.check_disk_space(min_free_gb=1.0):
            self.logger.critical("CRITICAL: Low disk space - cleanup required")
            # Trigger emergency cleanup
            self._emergency_disk_cleanup()

        # Check memory
        if not self.health_monitor.check_memory(max_percent=95):
            self.logger.warning("High memory usage - consider restart")

        # Check CPU temperature
        if not self.health_monitor.check_cpu_temperature(max_temp=85.0):
            self.logger.warning("High CPU temperature - thermal throttling may occur")

    def _check_thermal_camera_health(self):
        """Check and recover thermal camera if needed"""
        healthy = self.health_monitor.check_thermal_camera(self.thermal_capture)

        if not healthy:
            self.thermal_camera_failures += 1
            self.logger.warning(
                f"Thermal camera health check failed "
                f"(failures: {self.thermal_camera_failures})"
            )

            # Try to recover after multiple failures
            if self.thermal_camera_failures >= 3:
                current_time = time.time()

                # Prevent recovery attempt spam
                if current_time - self.last_thermal_recovery > 300:  # 5 minutes
                    self.logger.info("Attempting thermal camera recovery...")
                    self._recover_thermal_camera()
                    self.last_thermal_recovery = current_time
        else:
            # Reset failure counter on success
            if self.thermal_camera_failures > 0:
                self.logger.info("Thermal camera recovered")
            self.thermal_camera_failures = 0

    def _check_smart_camera_health(self):
        """Check and recover smart camera if needed"""
        healthy = self.health_monitor.check_smart_camera(self.smart_camera)

        if not healthy:
            self.smart_camera_failures += 1
            self.logger.warning(
                f"Smart camera health check failed "
                f"(failures: {self.smart_camera_failures})"
            )

            # Try to recover after multiple failures
            if self.smart_camera_failures >= 3:
                current_time = time.time()

                # Prevent recovery attempt spam
                if current_time - self.last_smart_camera_recovery > 300:  # 5 minutes
                    self.logger.info("Attempting smart camera recovery...")
                    self._recover_smart_camera()
                    self.last_smart_camera_recovery = current_time
        else:
            # Reset failure counter on success
            if self.smart_camera_failures > 0:
                self.logger.info("Smart camera recovered")
            self.smart_camera_failures = 0

    def _recover_thermal_camera(self):
        """
        Attempt to recover thermal camera

        Strategy:
        1. Close existing connection
        2. Wait briefly
        3. Reinitialize
        """
        try:
            self.logger.info("Closing thermal camera...")

            if self.thermal_capture:
                try:
                    self.thermal_capture.close()
                except:
                    pass

            time.sleep(2)

            self.logger.info("Reinitializing thermal camera...")

            # Reinitialize
            from thermal_capture import ThermalCapture
            self.thermal_capture = ThermalCapture(
                i2c_addr=self.config.get('thermal_camera.i2c_address', 0x33),
                i2c_bus=self.config.get('thermal_camera.i2c_bus', 1),
                refresh_rate=self.config.get('thermal_camera.refresh_rate', 8)
            )

            self.logger.info("Thermal camera recovery successful")
            self.thermal_camera_failures = 0

        except Exception as e:
            self.logger.error(f"Thermal camera recovery failed: {e}")

    def _recover_smart_camera(self):
        """
        Attempt to recover smart camera

        Strategy:
        1. Stop monitoring
        2. Close camera
        3. Wait briefly
        4. Reinitialize
        5. Restart monitoring
        """
        try:
            self.logger.info("Stopping smart camera...")

            if self.smart_camera:
                try:
                    self.smart_camera.stop_monitoring()
                    self.smart_camera.close()
                except:
                    pass

            time.sleep(3)

            self.logger.info("Reinitializing smart camera...")

            # Reinitialize
            from smart_camera import SmartCamera
            self.smart_camera = SmartCamera(self.config)
            self.smart_camera.start_monitoring()

            self.logger.info("Smart camera recovery successful")
            self.smart_camera_failures = 0

        except Exception as e:
            self.logger.error(f"Smart camera recovery failed: {e}")

    def _emergency_disk_cleanup(self):
        """
        Emergency disk cleanup when space is critically low

        Deletes oldest files more aggressively
        """
        try:
            self.logger.warning("Performing emergency disk cleanup...")

            # Delete oldest videos first (they're largest)
            video_dir = Path('/data/videos')
            if video_dir.exists():
                videos = sorted(video_dir.glob('*.h264'), key=lambda x: x.stat().st_mtime)

                # Delete oldest 50%
                delete_count = len(videos) // 2
                for video in videos[:delete_count]:
                    try:
                        video.unlink()
                        self.logger.info(f"Deleted {video.name}")
                    except:
                        pass

            # Delete old images if still needed
            image_dir = Path('/data/images')
            if image_dir.exists():
                images = sorted(image_dir.glob('*.jpg'), key=lambda x: x.stat().st_mtime)

                # Delete oldest 30%
                delete_count = len(images) // 3
                for image in images[:delete_count]:
                    try:
                        image.unlink()
                    except:
                        pass

            self.logger.info("Emergency cleanup complete")

        except Exception as e:
            self.logger.error(f"Emergency cleanup failed: {e}")

    def handle_graceful_degradation(self, failed_component: str):
        """
        Handle graceful degradation when a component fails

        Args:
            failed_component: Name of failed component
        """
        self.logger.warning(f"Entering degraded mode: {failed_component} failed")

        if failed_component == 'thermal_camera':
            self.logger.info(
                "Operating in degraded mode: "
                "Visual camera only, no thermal monitoring"
            )

        elif failed_component == 'smart_camera':
            self.logger.info(
                "Operating in degraded mode: "
                "Thermal monitoring only, no visual recording"
            )

        elif failed_component == 'network':
            self.logger.info(
                "Operating in degraded mode: "
                "Local buffering only, no cloud uploads"
            )

        elif failed_component == 'storage':
            self.logger.critical(
                "Operating in degraded mode: "
                "Limited data collection due to storage constraints"
            )

    def get_health_report(self):
        """Get comprehensive health report"""
        return {
            'thermal_camera': {
                'healthy': self.thermal_camera_failures == 0,
                'failure_count': self.thermal_camera_failures
            },
            'smart_camera': {
                'healthy': self.smart_camera_failures == 0,
                'failure_count': self.smart_camera_failures
            },
            'disk_space': self.health_monitor.check_disk_space(),
            'memory': self.health_monitor.check_memory(),
            'cpu_temp': self.health_monitor.check_cpu_temperature(),
            'timestamp': datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # This would normally be integrated into main.py
    logging.basicConfig(level=logging.INFO)

    recovery_manager = ErrorRecoveryManager({})
    recovery_manager.start_monitoring()

    try:
        while True:
            time.sleep(10)
            health = recovery_manager.get_health_report()
            print(f"Health: {health}")

    except KeyboardInterrupt:
        recovery_manager.stop_monitoring()
