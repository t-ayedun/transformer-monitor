"""
Watchdog Timer
Ensures system reboots if application hangs
"""

import logging
import subprocess
import os
from threading import Thread, Event


class WatchdogTimer:
    """Hardware watchdog timer manager"""

    def __init__(self, timeout: int = 60):
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.running = False
        self.thread = None
        self.stop_event = Event()
        self.enabled = False

        self._enable_watchdog()

    def _enable_watchdog(self):
        """Enable hardware watchdog"""
        # Check if watchdog device is accessible
        if not os.path.exists('/dev/watchdog'):
            self.logger.info("Watchdog device not found - running in development mode")
            self.enabled = False
            return

        # Check if we can access the watchdog device
        if not os.access('/dev/watchdog', os.W_OK):
            self.logger.info("Watchdog device not writable - running without watchdog")
            self.enabled = False
            return

        try:
            # Load watchdog kernel module (only if we have permissions)
            subprocess.run(['modprobe', 'bcm2835_wdt'], check=False, capture_output=True)
            self.enabled = True
            self.logger.info("Watchdog module loaded and enabled")
        except Exception as e:
            self.logger.info(f"Watchdog not available: {e}")
            self.enabled = False
    
    def start(self):
        """Start watchdog petting thread"""
        if not self.enabled:
            self.logger.debug("Watchdog not enabled - skipping start")
            return

        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._pet_loop, daemon=True)
        self.thread.start()

        self.logger.info("Watchdog timer started")
    
    def stop(self):
        """Stop watchdog"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.logger.info("Watchdog timer stopped")
    
    def pet(self):
        """Pet the watchdog (reset timer)"""
        if not self.enabled:
            return

        try:
            # Write to watchdog device
            with open('/dev/watchdog', 'w') as wd:
                wd.write('1')
        except Exception as e:
            self.logger.error(f"Failed to pet watchdog: {e}")
    
    def _pet_loop(self):
        """Automatic petting loop (backup)"""
        while self.running:
            self.pet()
            self.stop_event.wait(self.timeout // 2)