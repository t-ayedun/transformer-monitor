"""
Network Monitor
Monitors connectivity and reports issues
"""

import logging
import subprocess
from threading import Thread, Event
import time


class NetworkMonitor:
    """Monitor network connectivity"""
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.running = False
        self.thread = None
        self.stop_event = Event()
        
        self.status = {
            'ethernet': False,
            'wifi': False,
            'internet': False
        }
    
    def start(self):
        """Start monitoring"""
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info("Network monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Network monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        check_interval = self.config.get('network.connectivity.check_interval', 60)
        
        while self.running:
            self.check_connectivity()
            self.stop_event.wait(check_interval)
    
    def check_connectivity(self):
        """Check all network interfaces"""
        self.status['ethernet'] = self._check_interface('eth0')
        self.status['wifi'] = self._check_interface('wlan0')
        self.status['internet'] = self._ping('8.8.8.8')
        
        if not self.status['internet']:
            self.logger.warning("No internet connectivity!")
        
        return self.status
    
    def _check_interface(self, interface):
        """Check if network interface is up"""
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'UP' in result.stdout and 'state UP' in result.stdout
        except:
            return False
    
    def _ping(self, host, count=1):
        """Ping a host"""
        try:
            result = subprocess.run(
                ['ping', '-c', str(count), '-W', '2', host],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def get_status(self):
        """Get current network status"""
        return self.status