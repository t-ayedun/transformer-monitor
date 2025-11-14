"""
Unit tests for DataUploader
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch, call
from data_uploader import DataUploader


@pytest.mark.unit
class TestDataUploader:
    """Test suite for DataUploader"""

    def test_initialization(self, mock_config, mock_aws_publisher, mock_ftp_publisher, mock_local_buffer):
        """Test DataUploader initializes correctly"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=mock_ftp_publisher,
            local_buffer=mock_local_buffer
        )

        assert uploader.config == mock_config
        assert uploader.aws_publisher == mock_aws_publisher
        assert uploader.ftp_publisher == mock_ftp_publisher
        assert uploader.local_buffer == mock_local_buffer
        assert len(uploader.upload_queue) == 0

    def test_upload_telemetry_success(self, mock_config, mock_aws_publisher, mock_local_buffer, sample_processed_data):
        """Test successful telemetry upload"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=mock_local_buffer
        )

        result = uploader.upload_telemetry(sample_processed_data)

        assert result is True
        mock_aws_publisher.publish_telemetry.assert_called_once()
        assert uploader.stats['telemetry_uploaded'] == 1
        assert uploader.stats['telemetry_failed'] == 0

    def test_upload_telemetry_no_aws(self, mock_config, mock_local_buffer, sample_processed_data):
        """Test telemetry upload when AWS not available"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,  # No AWS
            ftp_publisher=None,
            local_buffer=mock_local_buffer
        )

        result = uploader.upload_telemetry(sample_processed_data)

        assert result is False
        # Should fallback to local buffer
        mock_local_buffer.store.assert_called_once_with(sample_processed_data)

    def test_upload_telemetry_failure(self, mock_config, mock_local_buffer, sample_processed_data):
        """Test telemetry upload handles failures"""
        mock_aws = MagicMock()
        mock_aws.publish_telemetry.return_value = False  # Simulate failure

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=mock_local_buffer
        )

        result = uploader.upload_telemetry(sample_processed_data)

        assert result is False
        assert uploader.stats['telemetry_failed'] == 1

    def test_upload_thermal_frame_queued(self, mock_config, mock_aws_publisher, sample_thermal_frame, sample_processed_data, temp_dir):
        """Test thermal frame upload is queued"""
        mock_config.get = lambda k, d=None: temp_dir if k == 'site.id' else 'TEST_SITE'

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        result = uploader.upload_thermal_frame(sample_thermal_frame, sample_processed_data)

        assert result is True
        assert len(uploader.upload_queue) == 1
        assert uploader.upload_queue[0]['type'] == 'thermal_frame'

    def test_upload_snapshot_queued(self, mock_config, mock_aws_publisher, temp_dir):
        """Test snapshot upload is queued"""
        # Create temp snapshot file
        snapshot_path = f"{temp_dir}/test_snapshot.jpg"
        with open(snapshot_path, 'w') as f:
            f.write('test')

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        result = uploader.upload_snapshot(snapshot_path, {'test': 'metadata'})

        assert result is True
        assert len(uploader.upload_queue) == 1
        assert uploader.upload_queue[0]['type'] == 'snapshot'
        assert uploader.upload_queue[0]['filepath'] == snapshot_path

    def test_upload_video_queued(self, mock_config, mock_aws_publisher, temp_dir):
        """Test video upload is queued"""
        # Create temp video file
        video_path = f"{temp_dir}/test_video.h264"
        with open(video_path, 'w') as f:
            f.write('test video')

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        result = uploader.upload_video(video_path, {'duration': 10})

        assert result is True
        assert len(uploader.upload_queue) == 1
        assert uploader.upload_queue[0]['type'] == 'video'

    def test_upload_alert_immediate(self, mock_config, mock_aws_publisher, sample_alert_data):
        """Test alerts are uploaded immediately (not queued)"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        alert = {
            'level': 'emergency',
            'roi_name': 'test_roi',
            'temperature': 105.2,
            'message': 'Emergency temperature'
        }

        result = uploader.upload_alert(alert)

        # Alert should be published immediately via MQTT
        assert result is True
        mock_aws_publisher.mqtt_client.publish.assert_called_once()

    def test_upload_logs_ftp(self, mock_config, mock_ftp_publisher, temp_dir):
        """Test log upload via FTP"""
        mock_config.get = lambda k, d=None: 'TEST_SITE' if k == 'site.id' else d

        # Create temp log directory with files
        log_dir = f"{temp_dir}/logs"
        import os
        os.makedirs(log_dir, exist_ok=True)
        with open(f"{log_dir}/test.log", 'w') as f:
            f.write('test log')

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,
            ftp_publisher=mock_ftp_publisher,
            local_buffer=None
        )

        result = uploader.upload_logs(log_dir)

        assert result is True
        mock_ftp_publisher.upload_file.assert_called_once()

    def test_get_stats(self, mock_config, mock_aws_publisher, mock_ftp_publisher):
        """Test statistics retrieval"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=mock_ftp_publisher,
            local_buffer=None
        )

        stats = uploader.get_stats()

        assert 'telemetry_uploaded' in stats
        assert 'telemetry_failed' in stats
        assert 'thermal_frames_uploaded' in stats
        assert 'snapshots_uploaded' in stats
        assert 'videos_uploaded' in stats
        assert 'queue_size' in stats
        assert 'aws_connected' in stats
        assert stats['aws_connected'] is True

    def test_start_stop_worker(self, mock_config, mock_aws_publisher):
        """Test worker thread starts and stops"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        uploader.start()
        assert uploader.worker_thread is not None
        assert uploader.worker_thread.is_alive()

        uploader.stop()
        time.sleep(0.5)  # Give thread time to stop
        # Worker should have stopped

    def test_queue_overflow_protection(self, mock_config, mock_aws_publisher):
        """Test upload queue has max size protection"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws_publisher,
            ftp_publisher=None,
            local_buffer=None
        )

        # Queue max is 1000, try to add 1100 items
        for i in range(1100):
            uploader.upload_queue.append({'test': i})

        # Should cap at 1000
        assert len(uploader.upload_queue) <= 1000

    def test_no_aws_no_ftp_local_only(self, mock_config, mock_local_buffer, sample_processed_data):
        """Test system works in local-only mode (no cloud)"""
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,
            ftp_publisher=None,
            local_buffer=mock_local_buffer
        )

        result = uploader.upload_telemetry(sample_processed_data)

        # Should save locally
        assert result is False
        mock_local_buffer.store.assert_called_once()

        # Stats should reflect local-only mode
        stats = uploader.get_stats()
        assert stats['aws_connected'] is False
        assert stats['ftp_available'] is False
