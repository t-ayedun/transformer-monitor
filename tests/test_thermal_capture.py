"""
Unit tests for thermal capture
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock hardware-specific modules
sys.modules['board'] = MagicMock()
sys.modules['busio'] = MagicMock()
sys.modules['adafruit_mlx90640'] = MagicMock()

from thermal_capture import ThermalCapture


class TestThermalCapture(unittest.TestCase):

    @patch('thermal_capture.busio.I2C')
    @patch('thermal_capture.adafruit_mlx90640.MLX90640')
    def setUp(self, mock_mlx, mock_i2c):
        """Set up test fixtures"""
        self.mock_mlx = mock_mlx.return_value
        self.mock_i2c = mock_i2c.return_value
        
        self.capture = ThermalCapture(i2c_addr=0x33, i2c_bus=1, refresh_rate=8)
    
    def test_initialization(self):
        """Test camera initialization"""
        self.assertIsNotNone(self.capture)
        self.assertEqual(self.capture.i2c_addr, 0x33)
        self.assertEqual(self.capture.refresh_rate, 8)
    
    def test_get_frame_valid(self):
        """Test getting valid thermal frame"""
        # Mock frame data
        mock_frame = list(np.random.uniform(20, 80, 768))
        
        def mock_getFrame(frame):
            frame[:] = mock_frame
        
        self.mock_mlx.getFrame = mock_getFrame
        
        frame = self.capture.get_frame()
        
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (24, 32))
        self.assertTrue(np.all(frame >= 20))
        self.assertTrue(np.all(frame <= 80))
    
    def test_get_frame_invalid(self):
        """Test handling of invalid frame data"""
        # Mock invalid frame (out of range)
        mock_frame = list(np.random.uniform(300, 400, 768))
        
        def mock_getFrame(frame):
            frame[:] = mock_frame
        
        self.mock_mlx.getFrame = mock_getFrame
        
        frame = self.capture.get_frame()
        
        # Should return None for invalid data
        self.assertIsNone(frame)
    
    def test_emissivity_correction(self):
        """Test emissivity correction calculation"""
        # Test frame at 50°C
        test_frame = np.full((24, 32), 50.0)
        
        # Apply correction for emissivity 0.95
        corrected = self.capture.apply_emissivity_correction(test_frame, 0.95)
        
        # Corrected temperature should be higher
        self.assertTrue(np.all(corrected > test_frame))
        
        # Test with emissivity 1.0 (no correction)
        no_correction = self.capture.apply_emissivity_correction(test_frame, 1.0)
        np.testing.assert_array_almost_equal(no_correction, test_frame)
    
    def test_frame_validation(self):
        """Test frame validation logic"""
        # Valid frame
        valid_frame = np.random.uniform(20, 80, (24, 32))
        self.assertTrue(self.capture._validate_frame(valid_frame))
        
        # Frame with temp too low
        cold_frame = np.full((24, 32), -50.0)
        self.assertFalse(self.capture._validate_frame(cold_frame))
        
        # Frame with temp too high
        hot_frame = np.full((24, 32), 400.0)
        self.assertFalse(self.capture._validate_frame(hot_frame))
        
        # Frame with NaN
        nan_frame = np.full((24, 32), np.nan)
        self.assertFalse(self.capture._validate_frame(nan_frame))


if __name__ == '__main__':
    unittest.main()