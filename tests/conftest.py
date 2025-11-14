"""
Pytest configuration and shared fixtures
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config():
    """Mock configuration manager"""
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        'site.id': 'TEST_SITE',
        'site.name': 'Test Site',
        'site.address': 'Test Address',
        'thermal_camera.i2c_address': 0x33,
        'thermal_camera.i2c_bus': 1,
        'thermal_camera.refresh_rate': 4,
        'thermal_camera.resolution': [32, 24],
        'data_capture.interval': 60,
        'data_capture.save_full_frame_interval': 10,
        'local_storage.database_path': '/tmp/test_readings.db',
        'local_storage.max_size_mb': 100,
        'aws.iot.enabled': False,
        'ftp.enabled': False,
        'production_mode': False,
        'regions_of_interest': [
            {
                'name': 'test_roi',
                'enabled': True,
                'coordinates': [[0, 0], [32, 24]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {
                    'warning': 75.0,
                    'critical': 85.0,
                    'emergency': 95.0
                }
            }
        ],
        'composite_temperature': {
            'method': 'weighted_average',
            'enabled': True
        }
    }.get(key, default)
    return config


@pytest.fixture
def sample_thermal_frame():
    """Generate a sample thermal frame (24x32 pixels)"""
    # Create realistic thermal data (20-40°C range)
    frame = np.random.uniform(20, 40, (24, 32))
    return frame


@pytest.fixture
def hot_thermal_frame():
    """Generate a thermal frame with hot spots (for alert testing)"""
    frame = np.random.uniform(20, 30, (24, 32))
    # Add hot spot in center
    frame[10:14, 14:18] = np.random.uniform(90, 100, (4, 4))
    return frame


@pytest.fixture
def mock_thermal_camera():
    """Mock thermal camera"""
    camera = MagicMock()
    camera.get_frame.return_value = np.random.uniform(20, 40, (24, 32))
    camera.get_sensor_temp.return_value = 25.5
    camera.close.return_value = None
    return camera


@pytest.fixture
def mock_aws_publisher():
    """Mock AWS publisher"""
    publisher = MagicMock()
    publisher.connected = True
    publisher.publish_telemetry.return_value = True
    publisher.publish_heartbeat.return_value = True
    publisher.upload_image.return_value = True
    publisher.connect.return_value = True
    publisher.disconnect.return_value = None
    publisher.stop.return_value = None
    publisher.get_stats.return_value = {
        'messages_published': 0,
        'messages_failed': 0,
        'bytes_sent': 0,
        's3_uploads': 0,
        'connected': True
    }
    return publisher


@pytest.fixture
def mock_ftp_publisher():
    """Mock FTP publisher"""
    publisher = MagicMock()
    publisher.upload_data.return_value = True
    publisher.upload_file.return_value = True
    publisher.get_stats.return_value = {
        'uploads_success': 0,
        'uploads_failed': 0,
        'bytes_uploaded': 0
    }
    return publisher


@pytest.fixture
def mock_local_buffer():
    """Mock local buffer"""
    buffer = MagicMock()
    buffer.store.return_value = True
    buffer.get_unsent.return_value = []
    buffer.mark_sent.return_value = None
    buffer.close.return_value = None
    buffer.get_stats.return_value = {
        'total_records': 0,
        'unsent_records': 0,
        'size_mb': 0
    }
    return buffer


@pytest.fixture
def sample_processed_data():
    """Sample processed thermal data"""
    return {
        'timestamp': '2025-11-14T12:00:00Z',
        'site_id': 'TEST_SITE',
        'capture_count': 1,
        'sensor_temp': 25.5,
        'composite_temperature': 32.5,
        'frame_stats': {
            'max_temp': 38.2,
            'min_temp': 28.1,
            'avg_temp': 32.5,
            'median_temp': 32.3,
            'std_dev': 2.1
        },
        'regions': [
            {
                'name': 'test_roi',
                'max_temp': 38.2,
                'min_temp': 28.1,
                'avg_temp': 32.5,
                'median_temp': 32.3,
                'std_dev': 2.1,
                'pixel_count': 768,
                'alert_level': 'normal'
            }
        ]
    }


@pytest.fixture
def sample_alert_data():
    """Sample alert data for emergency situation"""
    return {
        'timestamp': '2025-11-14T12:00:00Z',
        'site_id': 'TEST_SITE',
        'capture_count': 1,
        'sensor_temp': 25.5,
        'composite_temperature': 98.5,
        'frame_stats': {
            'max_temp': 105.2,
            'min_temp': 28.1,
            'avg_temp': 65.5,
            'median_temp': 55.3,
            'std_dev': 15.1
        },
        'regions': [
            {
                'name': 'test_roi',
                'max_temp': 105.2,
                'min_temp': 28.1,
                'avg_temp': 98.5,
                'median_temp': 95.3,
                'std_dev': 15.1,
                'pixel_count': 768,
                'alert_level': 'emergency'
            }
        ]
    }


# Pytest markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for data pipeline"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and load tests"
    )
    config.addinivalue_line(
        "markers", "security: Security validation tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow-running tests (>5 seconds)"
    )
    config.addinivalue_line(
        "markers", "requires_hardware: Tests requiring actual hardware (thermal camera, etc.)"
    )
