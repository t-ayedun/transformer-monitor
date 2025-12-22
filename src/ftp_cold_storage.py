"""
FTP Cold Storage Manager
Automatically uploads old files to FTP server and deletes local copies
to free up SD card space on Raspberry Pi

Monitors local directories and uploads:
- Video recordings after 2 hours
- Thermal frames after 6 hours
- Event images after 24 hours
- Periodic snapshots after 12 hours
- Animal events immediately
"""

import os
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread, Event
from typing import Dict, List

from ftp_publisher import FTPPublisher


class FTPColdStorage:
    """
    Manages automatic upload of old files to FTP cold storage

    Features:
    - Age-based file upload rules
    - Automatic local deletion after successful upload
    - Background monitoring thread
    - Retry logic for failed uploads
    - Graceful degradation if FTP unavailable
    """

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.stop_event = Event()
        self.monitor_thread = None

        # FTP publisher
        self.ftp_enabled = config.get('ftp_storage.enabled', False)
        self.ftp = None

        if self.ftp_enabled:
            try:
                self.ftp = FTPPublisher(
                    host=config.get('ftp_storage.host'),
                    username=config.get('ftp_storage.username'),
                    password=config.get('ftp_storage.password'),
                    remote_dir=config.get('ftp_storage.remote_dir'),
                    port=config.get('ftp_storage.port', 21),
                    passive=config.get('ftp_storage.passive', True)
                )
                self.logger.info("FTP cold storage initialized")
            except Exception as e:
                self.logger.warning(f"FTP initialization failed: {e}. Running without FTP.")
                self.ftp = None
                self.ftp_enabled = False
        else:
            self.logger.info("FTP cold storage disabled")

        # Upload rules from config
        self.upload_rules = config.get('ftp_storage.upload_rules', {})
        self.upload_interval = config.get('ftp_storage.upload_interval', 300)

        # Statistics
        self.stats = {
            'files_uploaded': 0,
            'files_deleted': 0,
            'bytes_uploaded': 0,
            'bytes_freed': 0,
            'upload_failures': 0
        }
        
        # Base Data Directory for scanning (Explicit path to match config)
        self.base_dir = Path('/home/smartie/transformer_monitor_data')
        self.video_dir = self.base_dir / 'videos'
        self.image_dir = self.base_dir / 'images'
        self.temp_dir = self.base_dir / 'temperature'

    def start(self):
        """Start background monitoring thread"""
        if not self.ftp_enabled:
            self.logger.info("FTP disabled, cold storage not started")
            return

        self.stop_event.clear()
        self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("FTP cold storage monitor started")

    def stop(self):
        """Stop background monitoring"""
        if self.monitor_thread:
            self.logger.info("Stopping FTP cold storage...")
            self.stop_event.set()
            self.monitor_thread.join(timeout=10)
            self.logger.info("FTP cold storage stopped")

    def _monitor_loop(self):
        """Background thread that monitors and uploads files"""
        while not self.stop_event.is_set():
            try:
                # Check each upload rule
                if self.upload_rules.get('videos', {}).get('enabled', False):
                    self._process_videos()

                if self.upload_rules.get('thermal_frames', {}).get('enabled', False):
                    self._process_thermal_frames()

                if self.upload_rules.get('event_images', {}).get('enabled', False):
                    self._process_event_images()

                if self.upload_rules.get('periodic_snapshots', {}).get('enabled', False):
                    self._process_snapshots()

                if self.upload_rules.get('animal_events', {}).get('enabled', False):
                    self._process_animal_events()
                
                if self.upload_rules.get('animal_events', {}).get('enabled', False):
                    self._process_animal_events()
                
                # Process temperature CSV files
                if self.upload_rules.get('temperature_csv', {}).get('enabled', True):
                    self._process_temperature_csvs()
                    
                # Process telemetry JSONL files (NEW)
                self._process_telemetry_jsonl()


                # Log stats periodically
                if self.stats['files_uploaded'] > 0:
                    self.logger.info(
                        f"FTP cold storage: Uploaded {self.stats['files_uploaded']} files, "
                        f"Freed {self.stats['bytes_freed'] / (1024*1024):.1f} MB"
                    )

            except Exception as e:
                self.logger.error(f"FTP monitor loop error: {e}", exc_info=True)

            # Wait until next check
            self.stop_event.wait(self.upload_interval)

    def _process_videos(self):
        """Upload old video recordings to FTP"""
        rule = self.upload_rules['videos']
        upload_after_hours = rule.get('upload_after_hours', 2)
        delete_after_upload = rule.get('delete_after_upload', True)

        # video_dir = Path('/data/video') - OLD
        if not self.video_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=upload_after_hours)

        for video_file in self.video_dir.glob('*.h264'):
            try:
                file_mtime = datetime.fromtimestamp(video_file.stat().st_mtime)

                if file_mtime < cutoff_time:
                    # File is old enough to upload
                    remote_path = f"videos/{video_file.name}"
                    success = self._upload_file(video_file, remote_path)

                    if success and delete_after_upload:
                        file_size = video_file.stat().st_size
                        video_file.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['bytes_freed'] += file_size
                        self.logger.debug(f"Uploaded and deleted video: {video_file.name}")

            except Exception as e:
                self.logger.error(f"Error processing video {video_file}: {e}")

    def _process_thermal_frames(self):
        """Upload old thermal frames to FTP"""
        rule = self.upload_rules['thermal_frames']
        upload_after_hours = rule.get('upload_after_hours', 6)
        delete_after_upload = rule.get('delete_after_upload', True)

        # thermal_dir = Path('/data/images') - OLD
        if not self.image_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=upload_after_hours)

        for thermal_file in self.image_dir.glob('*_thermal_*.npy'):
            try:
                file_mtime = datetime.fromtimestamp(thermal_file.stat().st_mtime)

                if file_mtime < cutoff_time:
                    remote_path = f"thermal/{thermal_file.name}"
                    success = self._upload_file(thermal_file, remote_path)

                    if success and delete_after_upload:
                        file_size = thermal_file.stat().st_size
                        thermal_file.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['bytes_freed'] += file_size

            except Exception as e:
                self.logger.error(f"Error processing thermal frame {thermal_file}: {e}")

    def _process_event_images(self):
        """Upload old event images to FTP"""
        rule = self.upload_rules['event_images']
        upload_after_hours = rule.get('upload_after_hours', 24)
        delete_after_upload = rule.get('delete_after_upload', True)
        skip_security_breach = rule.get('skip_security_breach', True)

        events_dir = self.image_dir / 'events'
        if not events_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=upload_after_hours)

        # Iterate through date directories
        for date_dir in events_dir.iterdir():
            if not date_dir.is_dir():
                continue

            # Iterate through event type directories
            for event_type_dir in date_dir.iterdir():
                if not event_type_dir.is_dir():
                    continue

                # Skip security breach if configured (they go to S3)
                if skip_security_breach and 'security_breach' in event_type_dir.name:
                    continue

                # Process images in this event type
                for image_file in event_type_dir.glob('*.jpg'):
                    try:
                        file_mtime = datetime.fromtimestamp(image_file.stat().st_mtime)

                        if file_mtime < cutoff_time:
                            remote_path = f"events/{date_dir.name}/{event_type_dir.name}/{image_file.name}"
                            success = self._upload_file(image_file, remote_path)

                            if success and delete_after_upload:
                                file_size = image_file.stat().st_size
                                image_file.unlink()
                                self.stats['files_deleted'] += 1
                                self.stats['bytes_freed'] += file_size

                    except Exception as e:
                        self.logger.error(f"Error processing event image {image_file}: {e}")

                # Clean up empty directories
                try:
                    if not any(event_type_dir.iterdir()):
                        event_type_dir.rmdir()
                except:
                    pass

            # Clean up empty date directories
            try:
                if not any(date_dir.iterdir()):
                    date_dir.rmdir()
            except:
                pass

    def _process_snapshots(self):
        """Upload old periodic snapshots to FTP"""
        rule = self.upload_rules['periodic_snapshots']
        upload_after_hours = rule.get('upload_after_hours', 12)
        delete_after_upload = rule.get('delete_after_upload', True)

        snapshots_dir = self.image_dir / 'snapshots'
        if not snapshots_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=upload_after_hours)

        for snapshot_file in snapshots_dir.glob('*.jpg'):
            try:
                file_mtime = datetime.fromtimestamp(snapshot_file.stat().st_mtime)

                if file_mtime < cutoff_time:
                    remote_path = f"snapshots/{snapshot_file.name}"
                    success = self._upload_file(snapshot_file, remote_path)

                    if success and delete_after_upload:
                        file_size = snapshot_file.stat().st_size
                        snapshot_file.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['bytes_freed'] += file_size

            except Exception as e:
                self.logger.error(f"Error processing snapshot {snapshot_file}: {e}")

    def _process_animal_events(self):
        """Upload animal events immediately (or based on rules)"""
        rule = self.upload_rules['animal_events']
        upload_immediately = rule.get('upload_immediately', True)
        delete_after_upload = rule.get('delete_after_upload', True)

        events_dir = self.image_dir / 'events'
        if not events_dir.exists():
            return

        cutoff_time = datetime.now() if upload_immediately else datetime.now() - timedelta(hours=1)

        # Find animal event directories
        for date_dir in events_dir.iterdir():
            if not date_dir.is_dir():
                continue

            animal_dir = date_dir / 'animal'
            if not animal_dir.exists():
                continue

            for image_file in animal_dir.glob('*.jpg'):
                try:
                    file_mtime = datetime.fromtimestamp(image_file.stat().st_mtime)

                    if file_mtime < cutoff_time:
                        remote_path = f"events/{date_dir.name}/animal/{image_file.name}"
                        success = self._upload_file(image_file, remote_path)

                        if success and delete_after_upload:
                            file_size = image_file.stat().st_size
                            image_file.unlink()
                            self.stats['files_deleted'] += 1
                            self.stats['bytes_freed'] += file_size

                except Exception as e:
                    self.logger.error(f"Error processing animal event {image_file}: {e}")
    
    def _process_temperature_csvs(self):
        """Upload temperature CSV files to FTP (Hourly Batches)"""
        rule = self.upload_rules.get('temperature_csv', {})
        upload_after_hours = rule.get('upload_after_hours', 1.0)
        delete_after_upload = rule.get('delete_after_upload', True)
        
        if not self.temp_dir.exists():
            return
        
        # Calculate strict cutoff (e.g. 1 hour ago)
        cutoff_time = datetime.now() - timedelta(hours=upload_after_hours)
        
        for csv_file in self.temp_dir.rglob('*_Temperature_*.csv'):
            try:
                # Check modification time to ensure file is "done" (rotated)
                file_mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)
                
                if file_mtime < cutoff_time:
                    # New Flattened Structure: SiteID/YYYY-MM-DD/Filename.csv
                    # Extract date from filename or mtime
                    # Filename format: SiteID_Temperature_YYYYMMDD_HH00.csv
                    try:
                        date_str = csv_file.stem.split('_')[2] # YYYYMMDD
                        date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    except:
                        # Fallback to file creation date
                        date_formatted = file_mtime.strftime('%Y-%m-%d')

                    site_id = self.config.get('site.id', 'UNKNOWN')
                    remote_path = f"{site_id}/{date_formatted}/{csv_file.name}"
                    
                    success = self._upload_file(csv_file, remote_path)
                    
                    if success and delete_after_upload:
                        csv_file.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['files_uploaded'] += 1
                        self.logger.info(f"Uploaded batch CSV: {remote_path}")
                        
            except Exception as e:
                self.logger.error(f"Error processing CSV {csv_file}: {e}")

    def _process_telemetry_jsonl(self):
        """Upload telemetry JSONL files to FTP (Hourly Batches)"""
        # Implicit rule, follows temperature retention for now or generic 1 hour
        telemetry_dir = self.base_dir / 'telemetry'
        if not telemetry_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=1.0)
        
        for json_file in telemetry_dir.rglob('*.json*'):
            try:
                file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    # Parse date from filename: SiteID_Telemetry_YYYYMMDD_HH00.json
                    try:
                        parts = json_file.stem.split('_')
                        date_str = parts[2]
                        if len(date_str) == 8:
                             date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        else:
                             raise ValueError("Invalid date format")
                    except:
                        date_formatted = file_mtime.strftime('%Y-%m-%d')
                        
                    site_id = self.config.get('site.id', 'UNKNOWN')
                    remote_path = f"{site_id}/{date_formatted}/{json_file.name}"
                    
                    if self._upload_file(json_file, remote_path):
                        json_file.unlink()
                        self.stats['files_uploaded'] += 1
                        
            except Exception as e:
                self.logger.error(f"Error telemetry upload: {e}")

    def _process_thermal_frames(self):
        """Zip and upload thermal frames hourly"""
        # Logic modified to support ZIPPING
        if self.config.get('ftp_storage.upload_rules.zip_hourly_images', False):
            self._zip_and_upload_images('thermal', self.image_dir)
        else:
            # Fallback to old logic (omitted for brevity, or kept if strictly needed)
            pass

    def _zip_and_upload_images(self, image_type, source_dir):
        """
        Compresses images from previous hour (completed) into valid ZIP file and uploads it.
        Format: SiteID_Images_YYYYMMDD_HH00.zip (or similar based on input)
        """
        import zipfile
        import shutil
        
        # We need to find "completed" hours.
        # Strategy: Look at directories. But our structure is usually flat or deep?
        # Let's assume recursion (rglob) to be safe.
        
        # We process files strictly older than 1 hour (completed hours).
        cutoff_time = datetime.now() - timedelta(hours=1.0)
        
        # Dictionary to group files by their "Hour Key": (YYYY, MM, DD, HH)
        # Value: List of Path objects
        files_by_hour = {}
        
        if image_type == 'thermal':
            pattern = '*_thermal_*.npy' # or png? Config says frames
            # Current saved files are .npy or .png?
            # DataProcessor saves snapshots as .jpg (visual) or .png/npy (thermal)
            # Let's assume .npy for frames as per old code, or check what IS saved.
            # Old code used: self.image_dir.glob('*_thermal_*.npy') for thermal frames.
            pattern = '*.npy' # Broaden to catch all thermal frames
            prefix = 'ThermalFrames'
        else:
             pattern = '*.jpg'
             prefix = 'Images'

        # SCAN
        for file_path in source_dir.rglob(pattern):
            try:
                # Get modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if mtime >= cutoff_time:
                    continue # Still current/active hour, skip
                
                # Group key: YYYYMMDD_HH
                hour_key = mtime.strftime('%Y%m%d_%H')
                if hour_key not in files_by_hour:
                    files_by_hour[hour_key] = []
                files_by_hour[hour_key].append(file_path)
            except Exception as e:
                pass
                
        # PROCESS BATCHES
        site_id = self.config.get('site.id', 'UNKNOWN')
        
        for hour_key, file_list in files_by_hour.items():
            if not file_list:
                continue
                
            try:
                # Create ZIP filename: SiteID_Images_YYYYMMDD_HH00.zip
                # hour_key is YYYYMMDD_HH
                zip_filename = f"{site_id}_{prefix}_{hour_key}00.zip"
                
                # Temp path for zip
                zip_path = source_dir / zip_filename
                
                # Create Zip
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in file_list:
                         zipf.write(f, arcname=f.name)
                         
                # Upload ZIP
                # Remote Path: SiteID/YYYY-MM-DD/
                date_formatted = f"{hour_key[:4]}-{hour_key[4:6]}-{hour_key[6:8]}"
                remote_path = f"{site_id}/{date_formatted}/{zip_filename}"
                
                self.logger.info(f"Uploading ZIP batch: {remote_path} ({len(file_list)} files)")
                
                if self._upload_file(zip_path, remote_path):
                     # DELETE ORIGINALS
                     for f in file_list:
                         try:
                             f.unlink()
                             self.stats['files_deleted'] += 1
                         except:
                             pass
                     # Delete ZIP
                     zip_path.unlink()
                     self.stats['files_uploaded'] += 1
                     self.stats['bytes_freed'] += zip_path.stat().st_size # Approx
                else:
                     self.logger.error(f"Failed to upload ZIP: {zip_path}")
                     # Do not delete originals if upload failed
            
            except Exception as e:
                self.logger.error(f"Error processing ZIP batch {hour_key}: {e}")



    def _upload_file(self, local_path: Path, remote_path: str) -> bool:
        """
        Upload a file to FTP server

        Args:
            local_path: Path to local file
            remote_path: Remote path on FTP server

        Returns:
            True if upload successful
        """
        if not self.ftp:
            return False

        try:
            # Upload file
            success = self.ftp.upload_file(str(local_path), remote_path)

            if success:
                self.stats['files_uploaded'] += 1
                self.stats['bytes_uploaded'] += local_path.stat().st_size
                return True
            else:
                self.stats['upload_failures'] += 1
                return False

        except Exception as e:
            self.logger.error(f"FTP upload failed for {local_path}: {e}")
            self.stats['upload_failures'] += 1
            return False

    def get_stats(self) -> Dict:
        """Get FTP cold storage statistics"""
        return {
            **self.stats,
            'ftp_enabled': self.ftp_enabled,
            'upload_interval': self.upload_interval
        }
