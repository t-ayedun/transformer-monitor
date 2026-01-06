
import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from media_uploader import MediaUploader
from ftp_cold_storage import FTPColdStorage

class TestFTPStructure(unittest.TestCase):
    def setUp(self):
        self.mock_ftp = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.get.side_effect = lambda key, default=None: {
            'site.id': 'C468',
            'ftp.thermal_image_interval': 60,
            'ftp.upload_on_alert': True,
            'media.videos.upload_after_recording': True,
            'ftp_storage.enabled': True
        }.get(key, default)

    def test_media_uploader_thermal_path(self):
        """Test MediaUploader generates correct thermal path: {SiteID}/{YYYY-MM-DD}/thermal/{filename}"""
        uploader = MediaUploader(self.mock_ftp, self.mock_config)
        
        # Override generate_remote_path to be public or access protected
        # Accessing protected method for testing
        
        metadata = {'timestamp': '2025-01-05T10:00:00Z'}
        local_path = '/tmp/test_image.png'
        
        remote_path = uploader._generate_remote_path(local_path, 'thermal', metadata)
        
        # EXPECTED NEW STRUCTURE
        self.assertEqual(remote_path, 'C468/2025-01-05/thermal/test_image.png')

    def test_media_uploader_video_path(self):
        """Test MediaUploader generates correct video path"""
        uploader = MediaUploader(self.mock_ftp, self.mock_config)
        
        metadata = {'timestamp': '2025-01-05T10:00:00Z'}
        local_path = '/tmp/test_video.h264'
        
        remote_path = uploader._generate_remote_path(local_path, 'videos', metadata)
        
        # EXPECTED NEW STRUCTURE
        self.assertEqual(remote_path, 'C468/2025-01-05/videos/test_video.h264')

    @patch('ftp_cold_storage.FTPPublisher')
    def test_cold_storage_csv_upload(self, mock_ftp_class):
        """Test Cold Storage uploads CSV to correct path"""
        mock_ftp_instance = mock_ftp_class.return_value
        mock_ftp_instance.upload_file.return_value = True
        
        storage = FTPColdStorage(self.mock_config)
        storage.ftp = mock_ftp_instance # Inject mock
        
        # Setup fake file
        test_file = Path('/tmp/C468_Temperature_20250105_1000.csv')
        # We need to mock _upload_file to capture the path instead of running full logic
        # OR we can mock the glob/stat calls to run _process_temperature_csvs
        
        # Verify that upload_file was called with the correct path
        # We need to simulate the loop in _process_temperature_csvs
        
        # Manually construct expected path for this file
        site_id = 'C468'
        date_str = '2025-01-05'
        filename = test_file.name
        expected_path = f"{site_id}/{date_str}/{filename}"
        
        # Initialize stats to avoid key error if touched
        storage.stats['files_uploaded'] = 0
        storage.stats['files_deleted'] = 0
        
        # Direct call to helper if we refactor, but for now let's reproduce the logic we want to test
        # or mock the glob to return our test file
        
        with patch.object(Path, 'rglob', return_value=[test_file]):
            with patch.object(Path, 'stat') as mock_stat:
                # Mock mtime to be old enough (2 hours ago)
                mock_stat.return_value.st_mtime = (datetime.now().timestamp() - 7200)
                
                # Mock exists() to ensure early return doesn't trigger
                with patch.object(Path, 'exists', return_value=True):
                    # Also mock unlink to avoid deleting real files (though /tmp/ is safe)
                    with patch.object(Path, 'unlink'):
                        storage._process_temperature_csvs()
        
        # Verify upload_file called with expected path
        # Note: FTPColdStorage._upload_file converts local_path to string before calling ftp.upload_file
        mock_ftp_instance.upload_file.assert_called_with(str(test_file), expected_path)

if __name__ == '__main__':
    unittest.main()
