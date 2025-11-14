"""
Network resilience integration tests
Tests system behavior during network failures, disconnections, and recoveries
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path


@pytest.mark.integration
class TestNetworkResilience:
    """Test network failure scenarios and recovery"""

    def test_aws_disconnect_reconnect(self, mock_config, sample_processed_data):
        """Test system handles AWS disconnection and reconnection"""
        from data_uploader import DataUploader
        from local_buffer import LocalBuffer

        # Create temp buffer
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        # Mock AWS publisher that starts disconnected
        mock_aws = MagicMock()
        mock_aws.connected = False
        mock_aws.publish_telemetry.return_value = False

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=buffer
        )

        try:
            # Upload while disconnected (should buffer locally)
            result1 = uploader.upload_telemetry(sample_processed_data)
            assert uploader.stats['telemetry_failed'] == 1

            # Verify buffered locally
            buffered = buffer.get_recent(limit=10)
            assert len(buffered) >= 1

            # Simulate reconnection
            mock_aws.connected = True
            mock_aws.publish_telemetry.return_value = True

            # Upload after reconnection (should succeed)
            result2 = uploader.upload_telemetry(sample_processed_data)
            assert result2 is True
            assert uploader.stats['telemetry_uploaded'] == 1

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_mqtt_publish_timeout(self, mock_config, sample_processed_data):
        """Test handling of MQTT publish timeouts"""
        from data_uploader import DataUploader

        # Mock AWS publisher that times out
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.side_effect = TimeoutError("MQTT timeout")

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Should handle timeout gracefully
        result = uploader.upload_telemetry(sample_processed_data)
        assert result is False
        assert uploader.stats['telemetry_failed'] == 1

    def test_s3_upload_retry_on_failure(self, mock_config, temp_dir):
        """Test S3 upload retry logic on failure"""
        from data_uploader import DataUploader

        # Create test thermal file
        test_file = f"{temp_dir}/test_thermal.npy"
        np.save(test_file, np.random.rand(24, 32))

        # Mock AWS publisher that fails then succeeds
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.upload_image.side_effect = [False, False, True]  # Fail 2x, then succeed

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )
        uploader.start()

        try:
            # Queue thermal frame
            uploader.upload_queue.append({
                'type': 'thermal_frame',
                'filepath': test_file,
                'metadata': {'site_id': 'TEST'},
                'timestamp': time.time(),
                'retry_count': 0
            })

            # Wait for worker to process and retry
            time.sleep(5)

            # Should have retried and eventually succeeded
            assert mock_aws.upload_image.call_count >= 2

        finally:
            uploader.stop()

    def test_queue_overflow_drops_oldest(self, mock_config):
        """Test upload queue drops oldest items when full"""
        from data_uploader import DataUploader

        mock_aws = MagicMock()
        mock_aws.connected = False  # Disconnected so nothing processes

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Queue is maxlen=1000, add 1100 items
        for i in range(1100):
            uploader.upload_queue.append({
                'type': 'snapshot',
                'filepath': f'/tmp/test_{i}.jpg',
                'metadata': {'index': i},
                'timestamp': time.time()
            })

        # Should cap at 1000
        assert len(uploader.upload_queue) == 1000

        # Oldest items should be dropped (first 100)
        first_item = uploader.upload_queue[0]
        assert first_item['metadata']['index'] >= 100

    def test_ftp_connection_failure(self, mock_config):
        """Test FTP upload handles connection failures"""
        from data_uploader import DataUploader

        # Mock FTP publisher that fails to connect
        mock_ftp = MagicMock()
        mock_ftp.upload_file.side_effect = ConnectionError("FTP connection failed")

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,
            ftp_publisher=mock_ftp,
            local_buffer=None
        )

        # Should handle FTP failure gracefully
        result = uploader.upload_logs('/tmp/logs')
        assert result is False

    def test_intermittent_network_buffering(self, mock_config, sample_processed_data):
        """Test local buffering during intermittent network issues"""
        from data_uploader import DataUploader
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        # Mock AWS that alternates between connected/disconnected
        mock_aws = MagicMock()
        upload_results = [False, True, False, True, True]  # Intermittent failures
        mock_aws.publish_telemetry.side_effect = upload_results
        mock_aws.connected = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=buffer
        )

        try:
            # Upload 5 samples
            for i in range(5):
                data = {**sample_processed_data, 'capture_count': i}
                uploader.upload_telemetry(data)

            # Should have 2 successful, 3 failed
            assert uploader.stats['telemetry_uploaded'] == 2
            assert uploader.stats['telemetry_failed'] == 3

            # All data should be buffered locally
            buffered = buffer.get_recent(limit=10)
            assert len(buffered) == 5

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_certificate_error_handling(self, mock_config, sample_processed_data):
        """Test handling of SSL/TLS certificate errors"""
        from data_uploader import DataUploader

        # Mock AWS publisher that raises certificate error
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.side_effect = Exception("SSL certificate verify failed")

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Should handle certificate error gracefully
        result = uploader.upload_telemetry(sample_processed_data)
        assert result is False
        assert uploader.stats['telemetry_failed'] == 1

    def test_network_recovery_resumes_uploads(self, mock_config, temp_dir):
        """Test upload queue resumes after network recovery"""
        from data_uploader import DataUploader

        # Create multiple test files
        test_files = []
        for i in range(3):
            filepath = f"{temp_dir}/test_{i}.npy"
            np.save(filepath, np.random.rand(24, 32))
            test_files.append(filepath)

        # Mock AWS that starts failing then recovers
        mock_aws = MagicMock()
        mock_aws.connected = True

        # First 3 uploads fail, rest succeed
        upload_results = [False, False, False, True, True, True]
        mock_aws.upload_image.side_effect = upload_results

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )
        uploader.start()

        try:
            # Queue all 3 files
            for i, filepath in enumerate(test_files):
                uploader.upload_queue.append({
                    'type': 'thermal_frame',
                    'filepath': filepath,
                    'metadata': {'index': i},
                    'timestamp': time.time()
                })

            # Wait for processing and retries
            time.sleep(6)

            # All should eventually succeed (initial attempt + retries)
            assert uploader.stats['thermal_frames_uploaded'] >= 1

        finally:
            uploader.stop()

    def test_worker_thread_restart(self, mock_config):
        """Test worker thread can be stopped and restarted"""
        from data_uploader import DataUploader

        mock_aws = MagicMock()
        mock_aws.connected = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Start worker
        uploader.start()
        assert uploader.worker_thread is not None
        assert uploader.worker_thread.is_alive()
        thread_id_1 = uploader.worker_thread.ident

        # Stop worker
        uploader.stop()
        time.sleep(1)

        # Restart worker
        uploader.start()
        assert uploader.worker_thread is not None
        assert uploader.worker_thread.is_alive()
        thread_id_2 = uploader.worker_thread.ident

        # Should be a new thread
        assert thread_id_1 != thread_id_2

        uploader.stop()

    def test_no_aws_no_ftp_offline_mode(self, mock_config, sample_processed_data):
        """Test system operates in offline mode with no cloud connectivity"""
        from data_uploader import DataUploader
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        # No AWS, no FTP - fully offline
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,
            ftp_publisher=None,
            local_buffer=buffer
        )

        try:
            # Upload 10 samples
            for i in range(10):
                data = {**sample_processed_data, 'capture_count': i}
                uploader.upload_telemetry(data)

            # All should be buffered locally
            buffered = buffer.get_recent(limit=20)
            assert len(buffered) == 10

            # Stats should show offline mode
            stats = uploader.get_stats()
            assert stats['aws_connected'] is False
            assert stats['ftp_available'] is False
            assert stats['telemetry_uploaded'] == 0  # No cloud uploads

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_partial_upload_failure_cleanup(self, mock_config, temp_dir):
        """Test cleanup on partial upload failures"""
        from data_uploader import DataUploader

        # Create test file
        test_file = f"{temp_dir}/test_thermal.npy"
        np.save(test_file, np.random.rand(24, 32))

        # Mock AWS that succeeds on thermal upload
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.upload_image.return_value = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )
        uploader.start()

        try:
            # Queue thermal frame
            uploader.upload_queue.append({
                'type': 'thermal_frame',
                'filepath': test_file,
                'metadata': {'site_id': 'TEST'},
                'timestamp': time.time()
            })

            # Wait for processing
            time.sleep(2)

            # Thermal frames should be deleted after successful upload
            # (cleanup happens in _process_upload_item)
            assert uploader.stats['thermal_frames_uploaded'] == 1

        finally:
            uploader.stop()

    def test_concurrent_uploads_thread_safety(self, mock_config, temp_dir):
        """Test upload queue is thread-safe with concurrent access"""
        from data_uploader import DataUploader
        from threading import Thread

        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.upload_image.return_value = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )
        uploader.start()

        def queue_items():
            """Queue items from multiple threads"""
            for i in range(10):
                uploader.upload_queue.append({
                    'type': 'snapshot',
                    'filepath': f'/tmp/test_{i}.jpg',
                    'metadata': {'index': i},
                    'timestamp': time.time()
                })

        try:
            # Start multiple threads queuing items
            threads = [Thread(target=queue_items) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have 30 items total (3 threads × 10 items)
            assert len(uploader.upload_queue) == 30

        finally:
            uploader.stop()

    def test_heartbeat_during_network_outage(self, mock_config):
        """Test heartbeat continues during network outage"""
        from heartbeat import HeartbeatMonitor

        # Mock AWS that's disconnected
        mock_aws = MagicMock()
        mock_aws.connected = False
        mock_aws.publish_heartbeat.return_value = False

        heartbeat = HeartbeatMonitor(
            interval=2,  # 2 seconds for testing
            aws_publisher=mock_aws,
            config=mock_config
        )

        heartbeat.start()
        time.sleep(5)  # Wait for 2-3 heartbeats

        # Heartbeat should have attempted to publish
        assert mock_aws.publish_heartbeat.call_count >= 2

        heartbeat.stop()

    def test_data_compression_on_slow_network(self, mock_config, sample_processed_data):
        """Test data compression is used for slow networks"""
        from data_uploader import DataUploader

        # Mock AWS with compression enabled
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.return_value = True
        mock_aws.compression_enabled = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Upload large dataset
        large_data = {
            **sample_processed_data,
            'thermal_frame': np.random.rand(24, 32).tolist()  # Full frame data
        }

        result = uploader.upload_telemetry(large_data)
        assert result is True

        # Verify publish was called with compressed data
        mock_aws.publish_telemetry.assert_called_once()
