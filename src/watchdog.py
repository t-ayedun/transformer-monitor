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
        """Start watchdog (no-op, uses manual petting)"""
        self.running = True
        self.logger.info("Watchdog timer active (waiting for manual petting)")
    
    def stop(self):
        """Stop watchdog"""
        self.running = False
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