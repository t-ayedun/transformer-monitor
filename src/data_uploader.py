"""
Data Uploader
Orchestrates data uploads to AWS IoT (MQTT), S3, and FTP
"""

import logging
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from threading import Thread, Event, Lock
from collections import deque


class DataUploader:
    """
    Coordinates data uploads to various destinations

    Features:
    - Temperature data → AWS IoT MQTT (real-time)
    - Thermal frames → S3 (periodic)
    - Visual snapshots → S3 (periodic)
    - Motion videos → S3 (on event)
    - System logs → FTP (daily)
    - Automatic fallback to local storage on failure
    """

    def __init__(self, config, aws_publisher=None, ftp_publisher=None, local_buffer=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.aws_publisher = aws_publisher
        self.ftp_publisher = ftp_publisher
        self.local_buffer = local_buffer

        # Upload configuration
        self.upload_thermal_frames = config.get('aws.s3.upload.thermal_images', True)
        self.upload_snapshots = config.get('aws.s3.upload.camera_snapshots', True)
        self.thermal_frame_interval = config.get('data_capture.save_full_frame_interval', 10)

        # Upload queue for background processing
        self.upload_queue = deque(maxlen=1000)
        self.queue_lock = Lock()

        # Background worker
        self.worker_thread = None
        self.stop_worker = Event()

        # Statistics
        self.stats = {
            'telemetry_uploaded': 0,
            'telemetry_failed': 0,
            'thermal_frames_uploaded': 0,
            'snapshots_uploaded': 0,
            'videos_uploaded': 0,
            'logs_uploaded': 0,
            'total_bytes_uploaded': 0
        }

        # Track last upload times
        self.last_thermal_frame_upload = 0
        self.last_log_upload = 0

        self.logger.info("Data uploader initialized")

    def start(self):
        """Start background upload worker"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_worker.clear()
            self.worker_thread = Thread(target=self._upload_worker, daemon=True)
            self.worker_thread.start()
            self.logger.info("Upload worker started")

    def stop(self):
        """Stop background upload worker"""
        if self.worker_thread:
            self.logger.info("Stopping upload worker...")
            self.stop_worker.set()
            self.worker_thread.join(timeout=10)
            self.logger.info("Upload worker stopped")

    def upload_telemetry(self, processed_data: Dict[str, Any]) -> bool:
        """
        Upload temperature telemetry data via MQTT

        Args:
            processed_data: Processed thermal data from DataProcessor

        Returns:
            True if uploaded successfully (or queued for retry)
        """
        if not self.aws_publisher:
            self.logger.debug("AWS publisher not available, buffering locally")
            if self.local_buffer:
                self.local_buffer.store(processed_data)
            return False

        try:
            # Add timestamp if not present
            if 'timestamp' not in processed_data:
                processed_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'

            # Publish to MQTT
            success = self.aws_publisher.publish_telemetry(processed_data)

            if success:
                self.stats['telemetry_uploaded'] += 1
                self.logger.debug("Telemetry uploaded successfully")
            else:
                self.stats['telemetry_failed'] += 1
                # AWS publisher handles local buffering and retry

            return success

        except Exception as e:
            self.logger.error(f"Telemetry upload error: {e}")
            self.stats['telemetry_failed'] += 1

            # Fallback to local buffer
            if self.local_buffer:
                self.local_buffer.store(processed_data)

            return False

    def upload_thermal_frame(self, thermal_frame: np.ndarray, metadata: Dict[str, Any]) -> bool:
        """
        Upload thermal frame to S3 (queued for background upload)

        Args:
            thermal_frame: Numpy array (24, 32) with temperatures
            metadata: Associated metadata (site_id, timestamp, etc.)

        Returns:
            True if queued successfully
        """
        if not self.upload_thermal_frames or not self.aws_publisher:
            return False

        try:
            # Save thermal frame to local file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            site_id = metadata.get('site_id', 'unknown')
            filename = f"{site_id}_thermal_{timestamp}.npy"
            filepath = f"/data/thermal_frames/{filename}"

            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            # Save numpy array
            np.save(filepath, thermal_frame)

            # Queue for upload
            with self.queue_lock:
                self.upload_queue.append({
                    'type': 'thermal_frame',
                    'filepath': filepath,
                    'metadata': metadata,
                    'timestamp': time.time()
                })

            self.logger.debug(f"Thermal frame queued for upload: {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Thermal frame queue error: {e}")
            return False

    def upload_snapshot(self, filepath: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Upload visual snapshot to S3 (queued for background upload)

        Args:
            filepath: Path to snapshot image file
            metadata: Optional metadata

        Returns:
            True if queued successfully
        """
        if not self.upload_snapshots or not self.aws_publisher:
            return False

        try:
            with self.queue_lock:
                self.upload_queue.append({
                    'type': 'snapshot',
                    'filepath': filepath,
                    'metadata': metadata or {},
                    'timestamp': time.time()
                })

            self.logger.debug(f"Snapshot queued for upload: {Path(filepath).name}")
            return True

        except Exception as e:
            self.logger.error(f"Snapshot queue error: {e}")
            return False

    def upload_video(self, filepath: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Upload motion video to S3 (queued for background upload)

        Args:
            filepath: Path to video file
            metadata: Optional metadata (trigger_type, duration, etc.)

        Returns:
            True if queued successfully
        """
        if not self.aws_publisher:
            return False

        try:
            with self.queue_lock:
                self.upload_queue.append({
                    'type': 'video',
                    'filepath': filepath,
                    'metadata': metadata or {},
                    'timestamp': time.time()
                })

            self.logger.info(f"Video queued for upload: {Path(filepath).name}")
            return True

        except Exception as e:
            self.logger.error(f"Video queue error: {e}")
            return False

    def upload_logs(self, log_dir: str = "/data/logs") -> bool:
        """
        Upload system logs to FTP (if configured)

        Args:
            log_dir: Directory containing log files

        Returns:
            True if uploaded successfully
        """
        if not self.ftp_publisher:
            return False

        try:
            # Create tarball of logs
            timestamp = datetime.now().strftime('%Y%m%d')
            site_id = self.config.get('site.id', 'unknown')
            archive_name = f"{site_id}_logs_{timestamp}.tar.gz"
            archive_path = f"/tmp/{archive_name}"

            # Tar logs (system command)
            import subprocess
            result = subprocess.run(
                ['tar', '-czf', archive_path, '-C', log_dir, '.'],
                capture_output=True,
                timeout=60
            )

            if result.returncode != 0:
                self.logger.error(f"Log archive creation failed: {result.stderr}")
                return False

            # Upload via FTP
            success = self.ftp_publisher.upload_file(archive_path, archive_name)

            if success:
                self.stats['logs_uploaded'] += 1
                self.last_log_upload = time.time()
                self.logger.info(f"Logs uploaded: {archive_name}")

            # Cleanup temp file
            try:
                Path(archive_path).unlink()
            except:
                pass

            return success

        except Exception as e:
            self.logger.error(f"Log upload error: {e}")
            return False

    def upload_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Publish alert to AWS IoT (high priority)

        Args:
            alert_data: Alert information (level, temperature, roi, etc.)

        Returns:
            True if published successfully
        """
        if not self.aws_publisher:
            return False

        try:
            topic = self.config.get('aws.iot.topics.alerts',
                                   f"transformers/{self.config.get('site.id')}/alerts")

            # Add timestamp
            alert_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
            alert_data['site_id'] = self.config.get('site.id')

            # Publish directly (bypass queue for alerts)
            payload = json.dumps(alert_data)
            self.aws_publisher.mqtt_client.publish(topic, payload, 1)  # QoS 1

            self.logger.warning(f"Alert published: {alert_data.get('level')} - {alert_data.get('message')}")
            return True

        except Exception as e:
            self.logger.error(f"Alert publish error: {e}")
            return False

    def _upload_worker(self):
        """Background worker that processes upload queue"""
        self.logger.info("Upload worker running")

        while not self.stop_worker.is_set():
            try:
                # Process upload queue
                if len(self.upload_queue) > 0:
                    with self.queue_lock:
                        if len(self.upload_queue) > 0:
                            item = self.upload_queue.popleft()
                        else:
                            item = None

                    if item:
                        self._process_upload_item(item)
                else:
                    # No items, sleep briefly
                    time.sleep(1)

                # Periodic log upload (daily)
                if (self.ftp_publisher and
                    time.time() - self.last_log_upload > 86400):  # 24 hours
                    self.upload_logs()

            except Exception as e:
                self.logger.error(f"Upload worker error: {e}")
                time.sleep(5)

        self.logger.info("Upload worker exited")

    def _process_upload_item(self, item: Dict):
        """
        Process a single upload queue item

        Args:
            item: Upload item dictionary
        """
        item_type = item['type']
        filepath = item['filepath']
        metadata = item.get('metadata', {})

        try:
            if not Path(filepath).exists():
                self.logger.warning(f"Upload file not found: {filepath}")
                return

            # Determine upload type and execute
            if item_type == 'thermal_frame':
                success = self.aws_publisher.upload_image(
                    filepath,
                    'thermal',
                    metadata
                )
                if success:
                    self.stats['thermal_frames_uploaded'] += 1
                    # Cleanup local file after successful upload
                    try:
                        Path(filepath).unlink()
                    except:
                        pass

            elif item_type == 'snapshot':
                success = self.aws_publisher.upload_image(
                    filepath,
                    'snapshot',
                    metadata
                )
                if success:
                    self.stats['snapshots_uploaded'] += 1
                    # Keep snapshots locally for web interface

            elif item_type == 'video':
                success = self.aws_publisher.upload_image(
                    filepath,
                    'video',
                    metadata
                )
                if success:
                    self.stats['videos_uploaded'] += 1
                    # Cleanup large video files after upload
                    try:
                        Path(filepath).unlink()
                        self.logger.info(f"Video uploaded and removed: {Path(filepath).name}")
                    except:
                        pass

            else:
                self.logger.warning(f"Unknown upload type: {item_type}")

        except Exception as e:
            self.logger.error(f"Upload processing error for {item_type}: {e}")

            # Re-queue failed uploads (with limit)
            if item.get('retry_count', 0) < 3:
                item['retry_count'] = item.get('retry_count', 0) + 1
                with self.queue_lock:
                    self.upload_queue.append(item)
                self.logger.info(f"Re-queued {item_type} for retry (attempt {item['retry_count']})")

    def get_stats(self) -> Dict[str, Any]:
        """Get upload statistics"""
        return {
            **self.stats,
            'queue_size': len(self.upload_queue),
            'aws_connected': self.aws_publisher.connected if self.aws_publisher else False,
            'ftp_available': self.ftp_publisher is not None
        }
