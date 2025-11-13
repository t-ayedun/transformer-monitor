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

        # For 32GB SD card: Reserve ~20GB for recordings
        # (leaving space for OS, logs, database, temp files)
        self.max_storage_gb = config.get('pi_camera.storage.max_local_storage_gb', 20)
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

    def _delete_oldest_files(self, bytes_to_free):
        """
        Delete oldest files until enough space is freed

        Strategy: Delete videos first (larger files), then images
        Priority: Oldest files first
        """
        deleted_bytes = 0
        files_deleted = 0

        # Collect all files with their modification times
        all_files = []

        for directory in [self.video_dir, self.image_dir]:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        all_files.append({
                            'path': file_path,
                            'size': stat.st_size,
                            'mtime': stat.st_mtime
                        })
                    except Exception as e:
                        self.logger.warning(f"Could not stat {file_path}: {e}")

        # Sort by modification time (oldest first)
        all_files.sort(key=lambda x: x['mtime'])

        # Delete oldest files until we free enough space
        for file_info in all_files:
            if deleted_bytes >= bytes_to_free:
                break

            try:
                file_path = file_info['path']
                file_size = file_info['size']

                file_path.unlink()
                deleted_bytes += file_size
                files_deleted += 1

                self.logger.debug(f"Deleted {file_path.name} ({file_size / (1024**2):.2f} MB)")

            except Exception as e:
                self.logger.error(f"Failed to delete {file_path}: {e}")

        self.logger.info(
            f"Deleted {files_deleted} files to free space "
            f"({deleted_bytes / (1024**3):.2f} GB freed)"
        )

        return deleted_bytes

    def check_storage_limit(self):
        """Check if storage exceeds limit and delete oldest files if needed"""
        current_usage = self.get_total_size()
        max_bytes = self.max_storage_gb * (1024 ** 3)

        if current_usage > max_bytes:
            self.logger.warning(
                f"Storage limit exceeded: {current_usage / (1024**3):.2f} GB / "
                f"{self.max_storage_gb} GB. Deleting oldest files..."
            )

            # Calculate how much space we need to free (with 10% buffer)
            bytes_to_free = int((current_usage - max_bytes) * 1.1)

            # Delete oldest files until we free enough space
            deleted_bytes = self._delete_oldest_files(bytes_to_free)

            self.logger.info(
                f"Freed {deleted_bytes / (1024**3):.2f} GB by deleting old files"
            )
    
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