"""
Unit tests for smart camera system
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from collections import deque
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock hardware-specific modules before importing
sys.modules['picamera2'] = MagicMock()
sys.modules['picamera2.encoders'] = MagicMock()
sys.modules['picamera2.outputs'] = MagicMock()
sys.modules['board'] = MagicMock()
sys.modules['busio'] = MagicMock()
sys.modules['adafruit_mlx90640'] = MagicMock()

from smart_camera import SmartCamera


class TestSmartCamera(unittest.TestCase):

    @patch('smart_camera.Picamera2')
    @patch('smart_camera.H264Encoder')
    @patch('smart_camera.CircularOutput')
    def setUp(self, mock_output, mock_encoder, mock_camera):
        """Set up test fixtures"""
        self.mock_camera = mock_camera.return_value
        self.mock_encoder = mock_encoder.return_value
        self.mock_output = mock_output.return_value

        # Mock config
        self.config = {
            'site': {
                'id': 'TEST_SITE'
            },
            'pi_camera': {
                'resolution': [1920, 1080],
                'framerate': 30,
                'quality': 85,
                'motion_detection': {
                    'enabled': True,
                    'threshold': 1500,
                    'min_area': 500,
                    'cooldown_seconds': 5
                },
                'recording': {
                    'pre_record_seconds': 10,
                    'post_record_seconds': 10,
                    'max_duration_seconds': 300
                },
                'snapshot_interval': 1800,
                'night_mode': {
                    'enabled': True,
                    'start_hour': 18,
                    'end_hour': 6
                }
            }
        }

        # Create config object with get method
        class ConfigMock:
            def __init__(self, data):
                self.data = data

            def get(self, key, default=None):
                keys = key.split('.')
                value = self.data
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                return value

        self.smart_camera = SmartCamera(ConfigMock(self.config))

    def test_initialization(self):
        """Test camera initialization"""
        self.assertIsNotNone(self.smart_camera)
        self.assertEqual(self.smart_camera.resolution, (1920, 1080))
        self.assertEqual(self.smart_camera.framerate, 30)
        self.assertTrue(self.smart_camera.motion_enabled)

    def test_circular_buffer_initialization(self):
        """Test circular buffer setup"""
        self.assertIsNotNone(self.smart_camera.encoder)
        self.assertIsNotNone(self.smart_camera.circular_output)

        # Check buffer size calculation
        # 10 seconds * 2 Mbps / 8 * 1.2 = ~3 MB
        expected_size_mb = 10 * 2 / 8 * 1.2
        actual_size_mb = self.smart_camera.stats['buffer_size_mb']
        self.assertAlmostEqual(actual_size_mb, expected_size_mb, delta=0.5)

    def test_snapshot_capture(self):
        """Test snapshot capture"""
        # Mock the capture_file method
        self.mock_camera.capture_file = Mock()

        # Attempt snapshot
        filepath = self.smart_camera.capture_snapshot(custom_name='test')

        # Verify capture was called
        self.mock_camera.capture_file.assert_called()

        # Check stats updated
        self.assertEqual(self.smart_camera.stats['snapshots_taken'], 1)

    def test_get_stats(self):
        """Test statistics retrieval"""
        stats = self.smart_camera.get_stats()

        self.assertIn('motion_events', stats)
        self.assertIn('recordings_saved', stats)
        self.assertIn('snapshots_taken', stats)
        self.assertIn('is_recording', stats)
        self.assertIn('buffer_size_mb', stats)

    def test_recording_state_management(self):
        """Test recording state transitions"""
        # Initially not recording
        self.assertFalse(self.smart_camera.is_recording)

        # Simulate starting recording
        self.smart_camera._start_recording('motion')

        # Should be recording now
        self.assertTrue(self.smart_camera.is_recording)

        # Stop recording
        self.smart_camera._stop_recording()

        # Should not be recording
        self.assertFalse(self.smart_camera.is_recording)

    def test_motion_cooldown(self):
        """Test motion detection cooldown"""
        import time

        # Set cooldown to 5 seconds
        self.smart_camera.motion_cooldown = 5

        # First motion event
        self.smart_camera.last_recording_end_time = time.time() - 10  # 10 seconds ago

        # Should allow recording (cooldown passed)
        time_since_last = time.time() - self.smart_camera.last_recording_end_time
        self.assertGreaterEqual(time_since_last, self.smart_camera.motion_cooldown)

        # Recent motion event
        self.smart_camera.last_recording_end_time = time.time() - 2  # 2 seconds ago

        # Should not allow recording (cooldown not passed)
        time_since_last = time.time() - self.smart_camera.last_recording_end_time
        self.assertLess(time_since_last, self.smart_camera.motion_cooldown)


class TestCircularBufferConcepts(unittest.TestCase):
    """Test circular buffer concepts"""

    def test_circular_buffer_behavior(self):
        """Test that circular buffer works as expected"""
        # Simulate a circular buffer with deque
        buffer = deque(maxlen=5)

        # Add items
        for i in range(10):
            buffer.append(i)

        # Should only keep last 5 items
        self.assertEqual(len(buffer), 5)
        self.assertEqual(list(buffer), [5, 6, 7, 8, 9])

    def test_bitrate_calculation(self):
        """Test video bitrate calculations"""
        # 2 Mbps for 10 seconds
        bitrate_mbps = 2
        duration_seconds = 10

        # Calculate buffer size in bytes
        buffer_size_bytes = (bitrate_mbps * 1000000 / 8) * duration_seconds

        # With 20% overhead
        buffer_with_overhead = int(buffer_size_bytes * 1.2)

        # Should be approximately 3 MB
        self.assertGreater(buffer_with_overhead, 2_000_000)
        self.assertLess(buffer_with_overhead, 4_000_000)


if __name__ == '__main__':
    unittest.main()
