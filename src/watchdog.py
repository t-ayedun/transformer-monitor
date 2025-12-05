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
        
        self._enable_watchdog()
    
    def _enable_watchdog(self):
        """Enable hardware watchdog"""
        try:
            # Load watchdog kernel module
            subprocess.run(['modprobe', 'bcm2835_wdt'], check=True)
            self.logger.info("Watchdog module loaded")
        except Exception as e:
            self.logger.warning(f"Failed to load watchdog module: {e}")
    
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
        try:
            # Write to watchdog device
            with open('/dev/watchdog', 'w') as wd:
                wd.write('1')
        except PermissionError:
            # Non-root user cannot pet watchdog, ignore or log once
            pass
        except Exception as e:
            self.logger.error(f"Failed to pet watchdog: {e}")
    
    def _pet_loop(self):
        """Automatic petting loop (backup)"""
        while self.running:
            self.pet()
            self.stop_event.wait(self.timeout // 2)