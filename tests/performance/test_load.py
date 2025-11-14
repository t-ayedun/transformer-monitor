"""
Performance and load tests
Tests system performance, memory usage, and stability under load
"""

import pytest
import time
import psutil
import os
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import threading


@pytest.mark.performance
@pytest.mark.slow
class TestPerformance:
    """Performance and load testing"""

    def test_thermal_capture_framerate(self):
        """Test thermal camera achieves target framerate"""
        from thermal_capture import ThermalCapture

        with patch('thermal_capture.board'), \
             patch('thermal_capture.busio'), \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_mlx.MLX90640.return_value = mock_camera
            mock_camera.getFrame.return_value = np.random.rand(768).tolist()

            thermal = ThermalCapture(i2c_addr=0x33, refresh_rate=4)

            # Capture 20 frames and measure time
            start_time = time.time()
            frame_count = 20

            for _ in range(frame_count):
                frame = thermal.get_frame()
                assert frame is not None

            elapsed = time.time() - start_time
            fps = frame_count / elapsed

            # Should achieve at least 3 FPS (4Hz refresh with overhead)
            assert fps >= 3.0, f"FPS too low: {fps:.2f}"

    def test_data_processing_latency(self, mock_config, sample_thermal_frame):
        """Test data processing completes within acceptable latency"""
        from data_processor import DataProcessor

        processor = DataProcessor(
            rois=mock_config.get('regions_of_interest'),
            composite_config=mock_config.get('composite_temperature')
        )

        # Process 100 frames and measure average latency
        latencies = []

        for _ in range(100):
            start = time.time()
            processed = processor.process(sample_thermal_frame)
            latency = (time.time() - start) * 1000  # Convert to ms
            latencies.append(latency)

        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        p95_latency = np.percentile(latencies, 95)

        # Processing should be fast
        assert avg_latency < 50, f"Average latency too high: {avg_latency:.2f}ms"
        assert p95_latency < 100, f"P95 latency too high: {p95_latency:.2f}ms"
        assert max_latency < 200, f"Max latency too high: {max_latency:.2f}ms"

    def test_mqtt_publish_throughput(self, mock_config, sample_processed_data):
        """Test MQTT publish throughput"""
        from data_uploader import DataUploader

        # Mock AWS publisher
        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.return_value = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Publish 100 messages
        start_time = time.time()
        message_count = 100

        for i in range(message_count):
            data = {**sample_processed_data, 'capture_count': i}
            uploader.upload_telemetry(data)

        elapsed = time.time() - start_time
        throughput = message_count / elapsed

        # Should achieve at least 50 msg/sec
        assert throughput >= 50, f"Throughput too low: {throughput:.2f} msg/sec"

    def test_memory_usage_thermal_capture(self, mock_config):
        """Test memory usage during continuous thermal capture"""
        from thermal_capture import ThermalCapture
        from data_processor import DataProcessor

        with patch('thermal_capture.board'), \
             patch('thermal_capture.busio'), \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_mlx.MLX90640.return_value = mock_camera
            mock_camera.getFrame.return_value = np.random.rand(768).tolist()

            thermal = ThermalCapture(i2c_addr=0x33)
            processor = DataProcessor(
                rois=mock_config.get('regions_of_interest'),
                composite_config=mock_config.get('composite_temperature')
            )

            # Measure memory before
            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Capture and process 1000 frames
            for _ in range(1000):
                frame = thermal.get_frame()
                processed = processor.process(frame)

            # Measure memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_increase = mem_after - mem_before

            # Memory increase should be minimal (< 50 MB)
            assert mem_increase < 50, f"Memory leak detected: {mem_increase:.2f} MB increase"

    def test_upload_queue_performance(self, mock_config, temp_dir):
        """Test upload queue handles high volume"""
        from data_uploader import DataUploader

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
            # Queue 500 items rapidly
            start_time = time.time()

            for i in range(500):
                uploader.upload_queue.append({
                    'type': 'snapshot',
                    'filepath': f'/tmp/test_{i}.jpg',
                    'metadata': {'index': i},
                    'timestamp': time.time()
                })

            queue_time = time.time() - start_time

            # Queuing should be fast (< 1 second for 500 items)
            assert queue_time < 1.0, f"Queue operations too slow: {queue_time:.2f}s"

            # Verify all queued
            assert len(uploader.upload_queue) == 500

        finally:
            uploader.stop()

    def test_local_buffer_write_performance(self, temp_dir, sample_processed_data):
        """Test local buffer write performance"""
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=100)

        try:
            # Write 1000 records
            start_time = time.time()
            record_count = 1000

            for i in range(record_count):
                data = {**sample_processed_data, 'capture_count': i}
                buffer.store(data)

            elapsed = time.time() - start_time
            write_rate = record_count / elapsed

            # Should achieve at least 100 writes/sec
            assert write_rate >= 100, f"Write rate too low: {write_rate:.2f} writes/sec"

            # Verify all stored
            recent = buffer.get_recent(limit=1100)
            assert len(recent) == record_count

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_local_buffer_read_performance(self, temp_dir, sample_processed_data):
        """Test local buffer read performance"""
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=100)

        try:
            # Populate with 1000 records
            for i in range(1000):
                data = {**sample_processed_data, 'capture_count': i}
                buffer.store(data)

            # Read records multiple times
            start_time = time.time()
            read_count = 100

            for _ in range(read_count):
                records = buffer.get_recent(limit=100)
                assert len(records) == 100

            elapsed = time.time() - start_time
            read_rate = read_count / elapsed

            # Should achieve at least 50 reads/sec
            assert read_rate >= 50, f"Read rate too low: {read_rate:.2f} reads/sec"

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_cpu_usage_normal_operation(self, mock_config):
        """Test CPU usage during normal operation"""
        from thermal_capture import ThermalCapture
        from data_processor import DataProcessor

        with patch('thermal_capture.board'), \
             patch('thermal_capture.busio'), \
             patch('thermal_capture.adafruit_mlx90640') as mock_mlx:

            mock_camera = MagicMock()
            mock_mlx.MLX90640.return_value = mock_camera
            mock_camera.getFrame.return_value = np.random.rand(768).tolist()

            thermal = ThermalCapture(i2c_addr=0x33)
            processor = DataProcessor(
                rois=mock_config.get('regions_of_interest'),
                composite_config=mock_config.get('composite_temperature')
            )

            # Measure CPU usage over 100 captures
            process = psutil.Process(os.getpid())
            cpu_samples = []

            for _ in range(100):
                cpu_before = process.cpu_percent(interval=0.01)
                frame = thermal.get_frame()
                processed = processor.process(frame)
                cpu_after = process.cpu_percent(interval=0.01)
                cpu_samples.append((cpu_before + cpu_after) / 2)

            avg_cpu = np.mean(cpu_samples)
            max_cpu = np.max(cpu_samples)

            # CPU usage should be reasonable (< 50% on average)
            assert avg_cpu < 50, f"Average CPU too high: {avg_cpu:.2f}%"
            assert max_cpu < 90, f"Max CPU too high: {max_cpu:.2f}%"

    def test_concurrent_operations_performance(self, mock_config, temp_dir):
        """Test performance with concurrent capture, processing, and upload"""
        from data_uploader import DataUploader
        import threading

        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.return_value = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )
        uploader.start()

        results = {'telemetry_count': 0, 'queue_count': 0}
        lock = threading.Lock()

        def upload_telemetry():
            """Upload telemetry in background"""
            for i in range(50):
                data = {'site_id': 'TEST', 'temperature': 25.0 + i}
                uploader.upload_telemetry(data)
                with lock:
                    results['telemetry_count'] += 1
                time.sleep(0.01)

        def queue_uploads():
            """Queue uploads in background"""
            for i in range(50):
                uploader.upload_queue.append({
                    'type': 'snapshot',
                    'filepath': f'/tmp/test_{i}.jpg',
                    'metadata': {'index': i},
                    'timestamp': time.time()
                })
                with lock:
                    results['queue_count'] += 1
                time.sleep(0.01)

        try:
            # Run concurrent operations
            start_time = time.time()

            t1 = threading.Thread(target=upload_telemetry)
            t2 = threading.Thread(target=queue_uploads)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            elapsed = time.time() - start_time

            # Should complete in reasonable time (< 3 seconds)
            assert elapsed < 3.0, f"Concurrent operations too slow: {elapsed:.2f}s"

            # Verify all operations completed
            assert results['telemetry_count'] == 50
            assert results['queue_count'] == 50

        finally:
            uploader.stop()

    @pytest.mark.slow
    def test_24hour_stability_simulation(self, mock_config, sample_processed_data):
        """Simulate 24-hour operation (1440 minutes compressed to ~30 seconds)"""
        from data_uploader import DataUploader
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=100)

        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.return_value = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=buffer
        )
        uploader.start()

        try:
            # Measure memory at start
            process = psutil.Process(os.getpid())
            mem_start = process.memory_info().rss / 1024 / 1024  # MB

            # Simulate 1440 captures (1 per minute for 24 hours)
            # Compressed to run in ~30 seconds
            capture_count = 1440
            start_time = time.time()

            for i in range(capture_count):
                data = {**sample_processed_data, 'capture_count': i}
                uploader.upload_telemetry(data)
                buffer.store(data)

                # Brief sleep every 100 captures
                if i % 100 == 0:
                    time.sleep(0.01)

            elapsed = time.time() - start_time

            # Measure memory at end
            mem_end = process.memory_info().rss / 1024 / 1024  # MB
            mem_increase = mem_end - mem_start

            # Verify performance
            assert elapsed < 60, f"24h simulation too slow: {elapsed:.2f}s"
            assert uploader.stats['telemetry_uploaded'] == capture_count
            assert mem_increase < 100, f"Memory leak: {mem_increase:.2f} MB increase"

            # Verify data integrity
            buffered = buffer.get_recent(limit=1500)
            assert len(buffered) == capture_count

        finally:
            uploader.stop()
            buffer.close()
            Path(temp_db.name).unlink()

    def test_large_thermal_frame_processing(self, mock_config):
        """Test processing performance with large thermal frames"""
        from data_processor import DataProcessor

        # Create large thermal frame (simulate higher resolution sensor)
        large_frame = np.random.uniform(20, 40, (48, 64))  # 2x resolution

        processor = DataProcessor(
            rois=mock_config.get('regions_of_interest'),
            composite_config=mock_config.get('composite_temperature')
        )

        # Process 100 large frames
        start_time = time.time()

        for _ in range(100):
            # Resize to standard 24x32 for processing
            frame_24x32 = large_frame[::2, ::2]
            processed = processor.process(frame_24x32)

        elapsed = time.time() - start_time
        fps = 100 / elapsed

        # Should still achieve good performance
        assert fps >= 30, f"Large frame processing too slow: {fps:.2f} FPS"

    def test_network_stats_overhead(self, mock_config):
        """Test statistics collection has minimal overhead"""
        from data_uploader import DataUploader

        mock_aws = MagicMock()
        mock_aws.connected = True

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Get stats 1000 times
        start_time = time.time()

        for _ in range(1000):
            stats = uploader.get_stats()
            assert 'telemetry_uploaded' in stats

        elapsed = time.time() - start_time
        calls_per_sec = 1000 / elapsed

        # Stats retrieval should be very fast (> 1000 calls/sec)
        assert calls_per_sec >= 1000, f"Stats retrieval too slow: {calls_per_sec:.2f} calls/sec"

    def test_roi_processing_scalability(self, sample_thermal_frame):
        """Test processing performance with many ROIs"""
        from data_processor import DataProcessor

        # Create 20 ROIs
        rois = []
        for i in range(20):
            rois.append({
                'name': f'roi_{i}',
                'enabled': True,
                'coordinates': [[i, i], [i + 5, i + 5]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            })

        processor = DataProcessor(
            rois=rois,
            composite_config={'method': 'weighted_average', 'enabled': True}
        )

        # Process 100 frames
        start_time = time.time()

        for _ in range(100):
            processed = processor.process(sample_thermal_frame)
            assert len(processed['regions']) == 20

        elapsed = time.time() - start_time
        fps = 100 / elapsed

        # Should still achieve good performance with many ROIs
        assert fps >= 10, f"Multi-ROI processing too slow: {fps:.2f} FPS"
