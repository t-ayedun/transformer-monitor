"""
Storage Manager
Manages local video/image storage and cleanup
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread, Event
import time


class StorageManager:
    """Manage local storage with automatic cleanup"""
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        self.video_dir = Path('/data/videos')
        self.image_dir = Path('/data/images')
        
        self.max_storage_gb = config.get('pi_camera.storage.max_local_storage_gb', 10)
        self.cleanup_days = config.get('pi_camera.storage.auto_cleanup_days', 7)
        self.check_interval = 3600  # Check every hour
        
        self.running = False
        self.thread = None
        self.stop_event = Event()
        
        # Ensure directories exist
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start storage monitoring"""
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info("Storage manager started")
    
    def stop(self):
        """Stop storage monitoring"""
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Storage manager stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.cleanup_old_files()
                self.check_storage_limit()
            except Exception as e:
                self.logger.error(f"Storage management error: {e}")
            
            self.stop_event.wait(self.check_interval)
    
    def cleanup_old_files(self):
        """Delete files older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_days)
        deleted_count = 0
        
        for directory in [self.video_dir, self.image_dir]:
            for file_path in directory.rglob('*'):
                if not file_path.is_file():
                    continue
                
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_time < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
        
        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old files")
    
    def check_storage_limit(self):
        """Check if storage exceeds limit"""
        current_usage = self.get_total_size()
        max_bytes = self.max_storage_gb * (1024 ** 3)
        
        if current_usage > max_bytes:
            self.logger.warning(f"Storage limit exceeded: {current_usage / (1024**3):.2f} GB")
    
    def get_total_size(self):
        """Get total size of stored files"""
        total = 0
        for directory in [self.video_dir, self.image_dir]:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total += file_path.stat().st_size
        return total
    
    def get_stats(self):
        """Get storage statistics"""
        video_size = sum(f.stat().st_size for f in self.video_dir.rglob('*') if f.is_file())
        image_size = sum(f.stat().st_size for f in self.image_dir.rglob('*') if f.is_file())
        
        total_size = video_size + image_size
        usage_percent = (total_size / (self.max_storage_gb * 1024**3)) * 100
        
        return {
            'total_size_gb': total_size / (1024**3),
            'max_size_gb': self.max_storage_gb,
            'usage_percent': usage_percent
        }