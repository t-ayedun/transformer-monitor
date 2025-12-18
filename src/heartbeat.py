"""
Heartbeat Monitor
Sends periodic health status messages
"""

import logging
import psutil
import time
from datetime import datetime
from threading import Thread, Event


class HeartbeatMonitor:
    """Monitors system health and sends periodic heartbeat"""
    
    def __init__(self, interval: int, aws_publisher, config, ftp_publisher=None):
        self.logger = logging.getLogger(__name__)
        self.interval = interval
        self.aws_publisher = aws_publisher
        self.ftp_publisher = ftp_publisher
        self.config = config
        
        self.running = False
        self.thread = None
        self.stop_event = Event()
    
    def start(self):
        """Start heartbeat monitoring"""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        
        self.logger.info(f"Heartbeat monitor started (interval: {self.interval}s)")
    
    def stop(self):
        """Stop heartbeat monitoring"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.logger.info("Heartbeat monitor stopped")
    
    def _run(self):
        """Main heartbeat loop"""
        while self.running:
            try:
                self._send_heartbeat()
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
            
            # Wait for interval or until stopped
            self.stop_event.wait(self.interval)
    
    def _send_heartbeat(self):
        """Collect and send system health data"""
        heartbeat_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'site_id': self.config.get('site.id'),
            'status': 'online',
            'system': self._get_system_stats()
        }
        
        # Send to AWS
        if self.aws_publisher:
            self.aws_publisher.publish_heartbeat(heartbeat_data)
            
        # Send to FTP (as heartbeat.json)
        if self.ftp_publisher:
            try:
                self.ftp_publisher.upload_data(
                    heartbeat_data, 
                    filename='heartbeat.json'
                )
            except Exception as e:
                self.logger.warning(f"FTP heartbeat failed: {e}")
    
    def _get_system_stats(self) -> dict:
        """Collect system statistics"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'temperature': self._get_cpu_temperature(),
                'uptime_seconds': time.time() - psutil.boot_time()
            }
        except Exception as e:
            self.logger.error(f"Failed to collect system stats: {e}")
            return {}
    
    def _get_cpu_temperature(self) -> float:
        """Get Raspberry Pi CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
                return temp
        except:
            return None