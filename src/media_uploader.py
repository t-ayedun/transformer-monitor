"""
Media Uploader
Manages upload queue for thermal images, visual images, and videos to FTP
"""

import logging
import time
from pathlib import Path
from threading import Thread, Lock, Event
from collections import deque
from datetime import datetime
from typing import Dict, Optional


class MediaUploader:
    """
    Manages media file uploads to FTP with queue and retry logic
    
    Features:
    - Upload queue for thermal/visual images and videos
    - Automatic retry on failure
    - Bandwidth throttling
    - Local cleanup after successful upload
    - Organized folder structure on FTP
    """
    
    def __init__(self, ftp_publisher, config):
        """
        Initialize media uploader
        
        Args:
            ftp_publisher: FTPPublisher instance
            config: ConfigManager instance
        """
        self.logger = logging.getLogger(__name__)
        self.ftp = ftp_publisher
        self.config = config
        
        # Upload queue
        self.upload_queue = deque()
        self.queue_lock = Lock()
        
        # Upload thread
        self.upload_thread = None
        self.stop_event = Event()
        self.running = False
        
        # Settings
        self.thermal_image_interval = config.get('ftp.thermal_image_interval', 600)
        self.upload_on_alert = config.get('ftp.upload_on_alert', True)
        self.upload_after_recording = config.get('media.videos.upload_after_recording', True)
        self.keep_local_days = config.get('media.videos.keep_local_days', 1)
        
        # Tracking
        self.last_thermal_upload = 0
        self.stats = {
            'thermal_uploaded': 0,
            'visual_uploaded': 0,
            'videos_uploaded': 0,
            'upload_failures': 0,
            'queue_size': 0
        }
        
        self.logger.info("Media uploader initialized")
    
    def start(self):
        """Start upload worker thread"""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        self.upload_thread = Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()
        
        self.logger.info("Media uploader started")
    
    def stop(self):
        """Stop upload worker thread"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.upload_thread:
            self.upload_thread.join(timeout=10)
        
        self.logger.info("Media uploader stopped")
    
    def queue_thermal_image(self, filepath: str, metadata: Dict, priority: bool = False):
        """
        Queue thermal image for upload
        
        Args:
            filepath: Local file path
            metadata: Image metadata (site_id, timestamp, alert_level, etc.)
            priority: If True, upload immediately (for alerts)
        """
        # Check if enough time has passed since last upload
        current_time = time.time()
        
        if not priority and (current_time - self.last_thermal_upload < self.thermal_image_interval):
            self.logger.debug("Skipping thermal image upload (interval not reached)")
            return
        
        # Generate remote path with date-based folder structure
        remote_path = self._generate_remote_path(filepath, 'thermal', metadata)
        
        upload_item = {
            'type': 'thermal',
            'local_path': filepath,
            'remote_path': remote_path,
            'metadata': metadata,
            'priority': priority,
            'attempts': 0,
            'max_attempts': 3
        }
        
        with self.queue_lock:
            if priority:
                # Add to front of queue
                self.upload_queue.appendleft(upload_item)
            else:
                self.upload_queue.append(upload_item)
            
            self.stats['queue_size'] = len(self.upload_queue)
        
        self.last_thermal_upload = current_time
        self.logger.debug(f"Queued thermal image: {Path(filepath).name} (priority={priority})")
    
    def queue_visual_image(self, filepath: str, metadata: Dict):
        """
        Queue visual image for upload (motion event)
        
        Args:
            filepath: Local file path
            metadata: Image metadata
        """
        remote_path = self._generate_remote_path(filepath, 'visual', metadata)
        
        upload_item = {
            'type': 'visual',
            'local_path': filepath,
            'remote_path': remote_path,
            'metadata': metadata,
            'priority': False,
            'attempts': 0,
            'max_attempts': 3
        }
        
        with self.queue_lock:
            self.upload_queue.append(upload_item)
            self.stats['queue_size'] = len(self.upload_queue)
        
        self.logger.debug(f"Queued visual image: {Path(filepath).name}")
    
    def queue_video(self, filepath: str, metadata: Dict):
        """
        Queue video for upload (motion recording)
        
        Args:
            filepath: Local file path
            metadata: Video metadata
        """
        if not self.upload_after_recording:
            self.logger.debug("Video upload disabled in config")
            return
        
        remote_path = self._generate_remote_path(filepath, 'videos', metadata)
        
        upload_item = {
            'type': 'video',
            'local_path': filepath,
            'remote_path': remote_path,
            'metadata': metadata,
            'priority': False,
            'attempts': 0,
            'max_attempts': 5  # More retries for large files
        }
        
        with self.queue_lock:
            self.upload_queue.append(upload_item)
            self.stats['queue_size'] = len(self.upload_queue)
        
        self.logger.debug(f"Queued video: {Path(filepath).name}")
    
    def _generate_remote_path(self, filepath: str, media_type: str, metadata: Dict) -> str:
        """
        Generate organized remote path with date-based folders
        
        Format: /{SiteID}/{YYYY-MM-DD}/{media_type}/{filename}
        
        Args:
            filepath: Local file path
            media_type: 'thermal', 'visual', or 'videos'
            metadata: Metadata dict with timestamp
            
        Returns:
            Remote path string
        """
        filename = Path(filepath).name
        
        # Extract date from metadata or filename
        timestamp = metadata.get('timestamp', datetime.now().isoformat())
        
        try:
            if 'T' in str(timestamp):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
        except:
            dt = datetime.now()
            
        # Get Site ID
        site_id = self.config.get('site.id', 'UNKNOWN')
        date_str = dt.strftime('%Y-%m-%d')
        
        # Build path: C468/2025-01-05/thermal/filename.png
        remote_path = f"{site_id}/{date_str}/{media_type}/{filename}"
        
        return remote_path
    
    def _upload_worker(self):
        """Background worker that processes upload queue"""
        while self.running:
            try:
                # Get next item from queue
                upload_item = None
                
                with self.queue_lock:
                    if len(self.upload_queue) > 0:
                        upload_item = self.upload_queue.popleft()
                        self.stats['queue_size'] = len(self.upload_queue)
                
                if upload_item:
                    self._process_upload(upload_item)
                else:
                    # Queue empty, sleep briefly
                    self.stop_event.wait(5)
            
            except Exception as e:
                self.logger.error(f"Upload worker error: {e}")
                time.sleep(5)
    
    def _process_upload(self, upload_item: Dict):
        """
        Process a single upload item
        
        Args:
            upload_item: Upload item dict from queue
        """
        local_path = upload_item['local_path']
        remote_path = upload_item['remote_path']
        media_type = upload_item['type']
        
        # Check if file still exists
        if not Path(local_path).exists():
            self.logger.warning(f"File not found, skipping upload: {local_path}")
            return
        
        # Attempt upload
        try:
            success = self.ftp.upload_file(local_path, remote_path)
            
            if success:
                # Update stats
                if media_type == 'thermal':
                    self.stats['thermal_uploaded'] += 1
                elif media_type == 'visual':
                    self.stats['visual_uploaded'] += 1
                elif media_type == 'video':
                    self.stats['videos_uploaded'] += 1
                
                # Cleanup local file if configured
                self._cleanup_local_file(local_path, media_type)
                
                self.logger.info(f"Uploaded {media_type}: {Path(local_path).name}")
            else:
                # Upload failed, retry if attempts remaining
                upload_item['attempts'] += 1
                
                if upload_item['attempts'] < upload_item['max_attempts']:
                    # Re-queue for retry
                    with self.queue_lock:
                        self.upload_queue.append(upload_item)
                        self.stats['queue_size'] = len(self.upload_queue)
                    
                    self.logger.warning(
                        f"Upload failed, will retry ({upload_item['attempts']}/{upload_item['max_attempts']}): "
                        f"{Path(local_path).name}"
                    )
                else:
                    self.stats['upload_failures'] += 1
                    self.logger.error(f"Upload failed after {upload_item['max_attempts']} attempts: {Path(local_path).name}")
        
        except Exception as e:
            self.logger.error(f"Upload processing error: {e}")
            self.stats['upload_failures'] += 1
    
    def _cleanup_local_file(self, filepath: str, media_type: str):
        """
        Delete local file after successful upload
        
        Args:
            filepath: Local file path
            media_type: Type of media
        """
        try:
            # Only delete videos and visual images, keep thermal images
            if media_type in ['video', 'visual']:
                Path(filepath).unlink()
                self.logger.debug(f"Deleted local file: {filepath}")
        except Exception as e:
            self.logger.warning(f"Failed to delete local file: {e}")
    
    def get_stats(self) -> Dict:
        """Get upload statistics"""
        with self.queue_lock:
            self.stats['queue_size'] = len(self.upload_queue)
        
        return self.stats.copy()
    
    def force_thermal_upload(self, filepath: str, metadata: Dict):
        """
        Force immediate thermal image upload (for alerts)
        
        Args:
            filepath: Local file path
            metadata: Image metadata
        """
        self.queue_thermal_image(filepath, metadata, priority=True)
