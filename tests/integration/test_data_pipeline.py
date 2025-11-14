"""
Integration tests for complete data pipeline
Tests the full flow: Thermal Capture → Processing → Local Buffer → Cloud Upload
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


@pytest.mark.integration
class TestDataPipeline:
    """Test complete data pipeline integration"""

    def test_thermal_capture_to_local_buffer(self, mock_config, sample_thermal_frame):
        """Test thermal data flows from capture to local buffer"""
        from thermal_capture import ThermalCapture
        from data_processor import DataProcessor
        from local_buffer import LocalBuffer

        # Mock thermal camera
        with patch('thermal_capture.board') as mock_board, \
             patch('thermal_capture.busio') as mock_busio, \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_camera.serial_number = "TEST123"
            mock_mlx.MLX90640.return_value = mock_camera
            mock_camera.getFrame.return_value = sample_thermal_frame.flatten().tolist()

            # Initialize components
            thermal = ThermalCapture(i2c_addr=0x33)
            processor = DataProcessor(
                rois=mock_config.get('regions_of_interest'),
                composite_config=mock_config.get('composite_temperature')
            )

            # Create temp database
            import tempfile
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

            try:
                # Capture thermal frame
                frame = thermal.get_frame()
                assert frame is not None
                assert frame.shape == (24, 32)

                # Process data
                processed = processor.process(frame)
                assert 'composite_temperature' in processed
                assert 'regions' in processed

                # Store in buffer
                processed['site_id'] = 'TEST_SITE'
                buffer.store(processed)

                # Verify stored
                recent = buffer.get_recent(limit=1)
                assert len(recent) == 1
                assert recent[0]['site_id'] == 'TEST_SITE'

            finally:
                buffer.close()
                Path(temp_db.name).unlink()

    def test_thermal_capture_to_cloud_upload(self, mock_config, sample_thermal_frame, temp_dir):
        """Test thermal data flows from capture through to cloud upload"""
        from thermal_capture import ThermalCapture
        from data_processor import DataProcessor
        from local_buffer import LocalBuffer
        from data_uploader import DataUploader

        # Mock thermal camera
        with patch('thermal_capture.board') as mock_board, \
             patch('thermal_capture.busio') as mock_busio, \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_mlx.MLX90640.return_value = mock_camera
            mock_camera.getFrame.return_value = sample_thermal_frame.flatten().tolist()

            # Mock AWS publisher
            mock_aws = MagicMock()
            mock_aws.publish_telemetry.return_value = True
            mock_aws.connected = True

            # Initialize components
            thermal = ThermalCapture(i2c_addr=0x33)
            processor = DataProcessor(
                rois=mock_config.get('regions_of_interest'),
                composite_config=mock_config.get('composite_temperature')
            )

            import tempfile
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

            uploader = DataUploader(
                config=mock_config,
                aws_publisher=mock_aws,
                ftp_publisher=None,
                local_buffer=buffer
            )

            try:
                # Capture → Process → Upload pipeline
                frame = thermal.get_frame()
                processed = processor.process(frame)
                processed['site_id'] = 'TEST_SITE'

                # Upload telemetry
                result = uploader.upload_telemetry(processed)

                assert result is True
                mock_aws.publish_telemetry.assert_called_once()
                assert uploader.stats['telemetry_uploaded'] == 1

            finally:
                buffer.close()
                Path(temp_db.name).unlink()

    def test_roi_alert_pipeline(self, mock_config, hot_thermal_frame):
        """Test alert generation and publishing when ROI exceeds thresholds"""
        from data_processor import DataProcessor
        from data_uploader import DataUploader

        # Configure ROI with low thresholds
        roi_config = [{
            'name': 'test_roi',
            'enabled': True,
            'coordinates': [[10, 10], [18, 14]],  # Hot spot area
            'weight': 1.0,
            'emissivity': 0.95,
            'thresholds': {
                'warning': 50.0,
                'critical': 70.0,
                'emergency': 85.0
            }
        }]

        processor = DataProcessor(
            rois=roi_config,
            composite_config={'method': 'weighted_average', 'enabled': True}
        )

        # Mock AWS publisher
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.mqtt_client = MagicMock()

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Process hot frame
        processed = processor.process(hot_thermal_frame)

        # Check for alerts
        roi_data = processed['regions'][0]
        assert roi_data['alert_level'] == 'emergency'
        assert roi_data['max_temp'] > 85.0

        # Publish alert
        alert_data = {
            'level': roi_data['alert_level'],
            'roi_name': roi_data['name'],
            'temperature': roi_data['max_temp'],
            'message': f"Emergency temperature: {roi_data['max_temp']:.1f}°C"
        }

        result = uploader.upload_alert(alert_data)
        assert result is True
        mock_aws.mqtt_client.publish.assert_called_once()

    def test_snapshot_capture_and_upload(self, mock_config, temp_dir):
        """Test visual snapshot capture and upload pipeline"""
        from smart_camera import SmartCamera
        from data_uploader import DataUploader

        # Mock picamera2
        with patch('smart_camera.Picamera2') as mock_picam:
            mock_camera = MagicMock()
            mock_picam.return_value = mock_camera

            # Mock AWS publisher
            mock_aws = MagicMock()
            mock_aws.connected = True

            # Override storage paths to use temp directory
            mock_config.get = lambda k, d=None: {
                'pi_camera.snapshot_interval': 1800,
                'pi_camera.storage.max_local_storage_gb': 10,
                'site.id': 'TEST_SITE'
            }.get(k, d)

            uploader = DataUploader(
                config=mock_config,
                aws_publisher=mock_aws,
                ftp_publisher=None,
                local_buffer=None
            )
            uploader.start()

            camera = SmartCamera(mock_config, data_uploader=uploader)

            # Override storage paths
            camera.snapshot_dir = temp_dir

            try:
                # Capture snapshot
                filepath = camera.capture_snapshot()
                assert filepath is not None

                # Verify queued for upload
                assert len(uploader.upload_queue) == 1
                assert uploader.upload_queue[0]['type'] == 'snapshot'

            finally:
                camera.close()
                uploader.stop()

    def test_video_recording_and_upload(self, mock_config, temp_dir):
        """Test motion video recording and upload pipeline"""
        from smart_camera import SmartCamera
        from data_uploader import DataUploader

        with patch('smart_camera.Picamera2') as mock_picam:
            mock_camera = MagicMock()
            mock_picam.return_value = mock_camera

            mock_aws = MagicMock()
            mock_aws.connected = True

            uploader = DataUploader(
                config=mock_config,
                aws_publisher=mock_aws,
                ftp_publisher=None,
                local_buffer=None
            )
            uploader.start()

            camera = SmartCamera(mock_config, data_uploader=uploader)
            camera.video_dir = temp_dir

            try:
                # Start recording
                camera._start_recording('motion')
                assert camera.is_recording is True

                # Create a dummy video file
                if camera.current_recording_path:
                    with open(camera.current_recording_path, 'w') as f:
                        f.write('test video')

                # Stop recording
                time.sleep(0.5)
                camera._stop_recording()

                # Verify video queued for upload
                assert len(uploader.upload_queue) > 0
                video_items = [item for item in uploader.upload_queue if item['type'] == 'video']
                assert len(video_items) >= 1

            finally:
                camera.close()
                uploader.stop()

    def test_local_buffer_fallback_on_network_failure(self, mock_config, sample_processed_data):
        """Test system falls back to local buffer when cloud unavailable"""
        from local_buffer import LocalBuffer
        from data_uploader import DataUploader

        # Create temp database
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        # No AWS publisher (simulating network failure)
        uploader = DataUploader(
            config=mock_config,
            aws_publisher=None,
            ftp_publisher=None,
            local_buffer=buffer
        )

        try:
            # Attempt upload (should fallback to local buffer)
            result = uploader.upload_telemetry(sample_processed_data)

            # Upload should "fail" (no AWS)
            assert result is False

            # But data should be in local buffer
            recent = buffer.get_recent(limit=1)
            assert len(recent) == 1
            assert recent[0]['site_id'] == sample_processed_data['site_id']

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_worker_processes_upload_queue(self, mock_config, temp_dir):
        """Test background worker processes queued uploads"""
        from data_uploader import DataUploader

        # Create test file
        test_file = f"{temp_dir}/test_thermal.npy"
        np.save(test_file, np.random.rand(24, 32))

        # Mock AWS publisher
        mock_aws = MagicMock()
        mock_aws.upload_image.return_value = True
        mock_aws.connected = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Start worker
        uploader.start()

        try:
            # Add item to queue
            uploader.upload_queue.append({
                'type': 'thermal_frame',
                'filepath': test_file,
                'metadata': {'site_id': 'TEST'},
                'timestamp': time.time()
            })

            # Wait for worker to process
            time.sleep(2)

            # Verify processed
            mock_aws.upload_image.assert_called_once_with(
                test_file,
                'thermal',
                {'site_id': 'TEST'}
            )

            assert uploader.stats['thermal_frames_uploaded'] == 1

        finally:
            uploader.stop()

    def test_multiple_captures_sequential(self, mock_config, sample_thermal_frame):
        """Test multiple thermal captures in sequence"""
        from thermal_capture import ThermalCapture
        from data_processor import DataProcessor
        from data_uploader import DataUploader

        with patch('thermal_capture.board'), \
             patch('thermal_capture.busio'), \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_mlx.MLX90640.return_value = mock_camera

            # Return different temperatures for each capture
            frames = [
                np.random.uniform(20, 30, (24, 32)),
                np.random.uniform(25, 35, (24, 32)),
                np.random.uniform(30, 40, (24, 32))
            ]

            mock_camera.getFrame.side_effect = [f.flatten().tolist() for f in frames]

            mock_aws = MagicMock()
            mock_aws.publish_telemetry.return_value = True
            mock_aws.connected = True

            thermal = ThermalCapture(i2c_addr=0x33)
            processor = DataProcessor(
                rois=mock_config.get('regions_of_interest'),
                composite_config=mock_config.get('composite_temperature')
            )
            uploader = DataUploader(
                config=mock_config,
                aws_publisher=mock_aws,
                ftp_publisher=None,
                local_buffer=None
            )

            temperatures = []

            # Capture 3 frames
            for i in range(3):
                frame = thermal.get_frame()
                assert frame is not None

                processed = processor.process(frame)
                processed['site_id'] = 'TEST_SITE'
                processed['capture_count'] = i

                uploader.upload_telemetry(processed)
                temperatures.append(processed['composite_temperature'])

            # Verify all uploaded
            assert mock_aws.publish_telemetry.call_count == 3
            assert uploader.stats['telemetry_uploaded'] == 3

            # Verify temperatures are different
            assert len(set(temperatures)) > 1  # Should have different values
