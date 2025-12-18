"""
FTP Publisher
Handles file uploads to FTP server
"""

import ftplib
import json
import io
import logging
from pathlib import Path
from datetime import datetime
from threading import Lock
import time


class FTPPublisher:
    """Publishes data to FTP server"""
    
    def __init__(self, host, username, password, remote_dir, port=21, passive=True):
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_dir = remote_dir
        self.passive = passive
        
        self.connection_lock = Lock()
        self.last_connection_time = 0
        self.connection_timeout = 300  # Reconnect after 5 minutes
        self.ftp = None
        
        self.stats = {
            'uploads_success': 0,
            'uploads_failed': 0,
            'bytes_uploaded': 0,
            'telemetry_batches': 0
        }
        
        # Telemetry buffer for batching
        self.telemetry_buffer = []
        self.buffer_lock = Lock()
        self.last_batch_upload = 0
        self.batch_interval = 300  # 5 minutes default
    
    def _connect(self):
        """Establish FTP connection"""
        try:
            if self.ftp:
                try:
                    self.ftp.quit()
                except:
                    pass
            
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, self.port, timeout=30)
            self.ftp.login(self.username, self.password)
            
            if self.passive:
                self.ftp.set_pasv(True)
            
            # Change to remote directory
            try:
                self.ftp.cwd(self.remote_dir)
            except ftplib.error_perm:
                # Directory doesn't exist, try to create it
                self._create_remote_dir(self.remote_dir)
                self.ftp.cwd(self.remote_dir)
            
            self.last_connection_time = time.time()
            self.logger.info(f"Connected to FTP server: {self.host}")
            return True
            
        except Exception as e:
            self.logger.error(f"FTP connection failed: {e}")
            self.ftp = None
            return False
    
    def _create_remote_dir(self, path):
        """Create remote directory recursively"""
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current += '/' + part
            try:
                self.ftp.mkd(current)
            except ftplib.error_perm:
                # Directory might already exist
                pass
    
    def _ensure_connection(self):
        """Ensure FTP connection is active"""
        with self.connection_lock:
            # Check if connection is stale
            if (not self.ftp or 
                time.time() - self.last_connection_time > self.connection_timeout):
                return self._connect()
            
            # Test connection with NOOP
            try:
                self.ftp.voidcmd("NOOP")
                return True
            except:
                return self._connect()
    
    def upload_telemetry_data(self, data: dict):
        """
        Queue and batch upload telemetry data
        
        Args:
            data: Telemetry data dictionary
        """
        with self.buffer_lock:
            self.telemetry_buffer.append(data)
            
            # Check if buffer is full or time interval reached
            current_time = time.time()
            if (len(self.telemetry_buffer) >= 50 or 
                current_time - self.last_batch_upload >= self.batch_interval):
                self._flush_telemetry_buffer()

    def _flush_telemetry_buffer(self):
        """Flush telemetry buffer to FTP"""
        if not self.telemetry_buffer:
            return

        try:
            # Create batch payload
            timestamp = datetime.utcnow()
            date_path = timestamp.strftime('%Y/%m/%d')
            file_ts = timestamp.strftime('%Y%m%d_%H%M%S')
            site_id = self.telemetry_buffer[0].get('site_id', 'UNKNOWN')
            
            # Take a snapshot of current buffer
            current_batch = list(self.telemetry_buffer)
            
            batch_data = {
                'batch_id': f"{site_id}_{file_ts}",
                'timestamp': timestamp.isoformat() + 'Z',
                'record_count': len(current_batch),
                'records': current_batch
            }
            
            # Generate remote path: /telemetry/YYYY/MM/DD/site_telemetry_timestamp.json
            remote_path = f"/telemetry/{date_path}/{site_id}_telemetry_{file_ts}.json"
            
            # Upload
            if self.upload_data(batch_data, remote_path, is_remote_path=True):
                # Only clear buffer if upload succeeded
                # Use slicing to remove only the items we just uploaded
                # (in case new items were added during upload)
                with self.buffer_lock:
                    # Remove the items we just uploaded
                    # This is a bit simplistic, assumes FIFO. 
                    # For now just clear what we took.
                    self.telemetry_buffer = [x for x in self.telemetry_buffer if x not in current_batch]
                    
                self.last_batch_upload = time.time()
                self.stats['telemetry_batches'] += 1
                self.logger.info(f"Uploaded telemetry batch: {remote_path} ({len(current_batch)} records)")
            else:
                self.logger.warning(f"Failed to upload telemetry batch, keeping {len(current_batch)} records in buffer")
                # Optional: Limit buffer size to prevent OOM
                with self.buffer_lock:
                    if len(self.telemetry_buffer) > 1000:
                        self.telemetry_buffer = self.telemetry_buffer[-1000:]
                        self.logger.warning("Telemetry buffer trimmed to 1000 records")
            
        except Exception as e:
            self.logger.error(f"Failed to flush telemetry buffer: {e}")

    def upload_data(self, data, filename=None, is_remote_path=False):
        """
        Upload JSON data to FTP server
        
        Args:
            data: Dictionary to upload as JSON
            filename: Filename or full remote path
            is_remote_path: If True, treats filename as full path including directories
        """
        if not self._ensure_connection():
            self.stats['uploads_failed'] += 1
            return False
        
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                site_id = data.get('site_id', 'UNKNOWN')
                filename = f"{site_id}_data_{timestamp}.json"
            
            # Handle remote directory structure
            target_file = filename
            if is_remote_path and '/' in filename:
                remote_dir = '/'.join(filename.split('/')[:-1])
                target_file = filename.split('/')[-1]
                
                # Ensure directory exists
                with self.connection_lock:
                    self._create_remote_dir_from_path(remote_dir)
                    try:
                        self.ftp.cwd(self.remote_dir + remote_dir)
                    except:
                        # Try absolute if relative failed
                        try:
                            self.ftp.cwd(remote_dir)
                        except:
                            pass
            
            # Convert data to JSON bytes
            json_str = json.dumps(data, indent=2)
            json_bytes = json_str.encode('utf-8')
            
            # Upload
            with self.connection_lock:
                self.ftp.storbinary(
                    f'STOR {target_file}',
                    io.BytesIO(json_bytes)
                )
                
                # Return to base directory if we changed it
                if is_remote_path:
                    self.ftp.cwd(self.remote_dir)
            
            self.stats['uploads_success'] += 1
            self.stats['bytes_uploaded'] += len(json_bytes)
            
            self.logger.debug(f"Uploaded to FTP: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"FTP upload failed: {e}")
            self.stats['uploads_failed'] += 1
            self.ftp = None  # Force reconnect on next attempt
            return False
    
    def upload_file(self, filepath, remote_filename=None):
        """
        Upload a file to FTP server with automatic directory creation
        
        Args:
            filepath: Local file path
            remote_filename: Remote path (can include directories like /thermal/2025/12/15/file.png)
        """
        if not self._ensure_connection():
            self.stats['uploads_failed'] += 1
            return False
        
        try:
            path = Path(filepath)
            if not path.exists():
                self.logger.error(f"File not found: {filepath}")
                return False
            
            if not remote_filename:
                remote_filename = path.name
            
            # If remote_filename contains directories, create them
            if '/' in remote_filename:
                # Extract directory path
                remote_dir = '/'.join(remote_filename.split('/')[:-1])
                remote_file = remote_filename.split('/')[-1]
                
                # Create directory structure
                with self.connection_lock:
                    self._create_remote_dir_from_path(remote_dir)
                    
                    # Change to target directory
                    try:
                        self.ftp.cwd(self.remote_dir + remote_dir)
                    except:
                        self.ftp.cwd(self.remote_dir)
                        self._create_remote_dir_from_path(remote_dir)
                        self.ftp.cwd(self.remote_dir + remote_dir)
                    
                    # Upload file
                    with open(filepath, 'rb') as f:
                        self.ftp.storbinary(f'STOR {remote_file}', f)
                    
                    # Return to base directory
                    self.ftp.cwd(self.remote_dir)
            else:
                # Simple upload to base directory
                with open(filepath, 'rb') as f:
                    with self.connection_lock:
                        self.ftp.storbinary(f'STOR {remote_filename}', f)
            
            file_size = path.stat().st_size
            self.stats['uploads_success'] += 1
            self.stats['bytes_uploaded'] += file_size
            
            self.logger.info(f"Uploaded file to FTP: {remote_filename} ({file_size} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"FTP file upload failed: {e}")
            self.stats['uploads_failed'] += 1
            self.ftp = None
            return False
    
    def _create_remote_dir_from_path(self, path):
        """
        Create remote directory structure from path
        
        Args:
            path: Path like /thermal/2025/12/15
        """
        if not path or path == '/':
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current += '/' + part
            try:
                self.ftp.mkd(current)
                self.logger.debug(f"Created FTP directory: {current}")
            except:
                # Directory might already exist
                pass
    
    def upload_batch(self, data_list, prefix='batch'):
        """
        Upload multiple data records in a single file
        
        Args:
            data_list: List of data dictionaries
            prefix: Filename prefix
        """
        if not data_list:
            return False
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        site_id = data_list[0].get('site_id', 'UNKNOWN')
        filename = f"{site_id}_{prefix}_{timestamp}.json"
        
        batch_data = {
            'batch_timestamp': datetime.utcnow().isoformat() + 'Z',
            'record_count': len(data_list),
            'records': data_list
        }
        
        return self.upload_data(batch_data, filename)
    
    def get_stats(self):
        """Get upload statistics"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['uploads_success'] / 
                (self.stats['uploads_success'] + self.stats['uploads_failed'])
                if (self.stats['uploads_success'] + self.stats['uploads_failed']) > 0 
                else 0
            )
        }
    
    def close(self):
        """Close FTP connection"""
        if self.ftp:
            try:
                self.ftp.quit()
            except:
                pass
            self.ftp = None
            self.logger.info("FTP connection closed")