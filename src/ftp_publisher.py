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
            'bytes_uploaded': 0
        }
    
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
    
    def upload_data(self, data, filename=None):
        """
        Upload JSON data to FTP server
        
        Args:
            data: Dictionary to upload as JSON
            filename: Optional filename, auto-generated if not provided
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
            
            # Convert data to JSON bytes
            json_str = json.dumps(data, indent=2)
            json_bytes = json_str.encode('utf-8')
            
            # Upload
            with self.connection_lock:
                self.ftp.storbinary(
                    f'STOR {filename}',
                    io.BytesIO(json_bytes)
                )
            
            self.stats['uploads_success'] += 1
            self.stats['bytes_uploaded'] += len(json_bytes)
            
            self.logger.info(f"Uploaded to FTP: {filename} ({len(json_bytes)} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"FTP upload failed: {e}")
            self.stats['uploads_failed'] += 1
            self.ftp = None  # Force reconnect on next attempt
            return False
    
    def upload_file(self, filepath, remote_path=None):
        """
        Upload a file to FTP server

        Args:
            filepath: Local file path
            remote_path: Optional remote path (can include subdirectories)
                        e.g., "videos/file.h264" or "events/2024-01-20/security/image.jpg"
        """
        if not self._ensure_connection():
            self.stats['uploads_failed'] += 1
            return False

        try:
            path = Path(filepath)
            if not path.exists():
                self.logger.error(f"File not found: {filepath}")
                return False

            if not remote_path:
                remote_path = path.name

            # Create subdirectories if remote_path contains /
            if '/' in remote_path:
                remote_dir = '/'.join(remote_path.split('/')[:-1])
                remote_filename = remote_path.split('/')[-1]

                # Create subdirectories
                with self.connection_lock:
                    try:
                        # Navigate to base directory
                        self.ftp.cwd(self.remote_dir)

                        # Create subdirectories
                        for subdir in remote_dir.split('/'):
                            if subdir:
                                try:
                                    self.ftp.mkd(subdir)
                                except ftplib.error_perm:
                                    pass  # Directory might exist
                                self.ftp.cwd(subdir)

                        # Upload file
                        with open(filepath, 'rb') as f:
                            self.ftp.storbinary(f'STOR {remote_filename}', f)

                        # Return to base directory
                        self.ftp.cwd(self.remote_dir)

                    except Exception as e:
                        # Return to base directory on error
                        try:
                            self.ftp.cwd(self.remote_dir)
                        except:
                            pass
                        raise
            else:
                # Simple upload to base directory
                with open(filepath, 'rb') as f:
                    with self.connection_lock:
                        self.ftp.storbinary(f'STOR {remote_path}', f)

            file_size = path.stat().st_size
            self.stats['uploads_success'] += 1
            self.stats['bytes_uploaded'] += file_size

            self.logger.debug(f"Uploaded file to FTP: {remote_path} ({file_size} bytes)")
            return True

        except Exception as e:
            self.logger.error(f"FTP file upload failed ({remote_path}): {e}")
            self.stats['uploads_failed'] += 1
            self.ftp = None
            return False
    
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