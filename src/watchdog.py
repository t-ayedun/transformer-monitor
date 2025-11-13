"""
Watchdog Timer
Ensures system reboots if application hangs
"""

import logging
import subprocess
from threading import Thread, Event


class WatchdogTimer:
    """Hardware watchdog timer manager"""

    def __init__(self, timeout: int = 60):
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.running = False
        self.thread = None
        self.stop_event = Event()
        self.watchdog_available = False

        self._enable_watchdog()
    
    def _enable_watchdog(self):
        """Enable hardware watchdog"""
        try:
            # Load watchdog kernel module
            subprocess.run(['modprobe', 'bcm2835_wdt'], check=True,
                         capture_output=True, timeout=5)
            self.logger.info("Watchdog module loaded")
        except Exception as e:
            self.logger.debug(f"Failed to load watchdog module: {e}")

        # Check if watchdog device is accessible
        try:
            import os
            if os.path.exists('/dev/watchdog') and os.access('/dev/watchdog', os.W_OK):
                self.watchdog_available = True
                self.logger.info("Watchdog device is accessible")
            else:
                self.watchdog_available = False
                self.logger.warning(
                    "Watchdog device not accessible (requires sudo/root). "
                    "Watchdog functionality disabled. "
                    "Run with 'sudo' to enable hardware watchdog."
                )
        except Exception as e:
            self.watchdog_available = False
            self.logger.warning(f"Cannot access watchdog device: {e}")
    
    def start(self):
        """Start watchdog petting thread"""
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
        if not self.watchdog_available:
            return

        try:
            # Write to watchdog device
            with open('/dev/watchdog', 'w') as wd:
                wd.write('1')
        except Exception as e:
            # Disable watchdog if it fails
            self.watchdog_available = False
            self.logger.error(f"Failed to pet watchdog: {e}. Watchdog disabled.")
    
    def _pet_loop(self):
        """Automatic petting loop (backup)"""
        while self.running:
            self.pet()
            self.stop_event.wait(self.timeout // 2)