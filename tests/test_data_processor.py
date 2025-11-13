"""
Unit tests for data processor
"""

import unittest
import numpy as np
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_processor import DataProcessor


class TestDataProcessor(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.rois = [
            {
                'name': 'test_roi',
                'enabled': True,
                'coordinates': [[0, 0], [10, 10]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {
                    'warning': 75.0,
                    'critical': 85.0
                }
            }
        ]
        
        self.composite_config = {
            'method': 'weighted_average',
            'enabled': True
        }
        
        self.processor = DataProcessor(self.rois, self.composite_config)
    
    def test_process_frame(self):
        """Test frame processing"""
        # Create test frame
        frame = np.random.uniform(50, 80, (24, 32))
        
        result = self.processor.process(frame)
        
        # Assertions
        self.assertIn('timestamp', result)
        self.assertIn('regions', result)
        self.assertIn('composite_temperature', result)
        self.assertEqual(len(result['regions']), 1)
    
    def test_composite_calculation(self):
        """Test composite temperature calculation"""
        temps = [70.0, 75.0, 80.0]
        weights = [1.0, 1.5, 1.0]
        
        result = self.processor._calculate_composite(
            temps, weights, 'weighted_average'
        )
        
        # Weighted average = (70*1 + 75*1.5 + 80*1) / (1+1.5+1) = 75.71
        self.assertAlmostEqual(result, 75.71, places=1)
    
    def test_threshold_checking(self):
        """Test temperature threshold detection"""
        thresholds = {
            'warning': 75.0,
            'critical': 85.0,
            'emergency': 95.0
        }
        
        self.assertEqual(
            self.processor._check_thresholds(70.0, thresholds),
            'normal'
        )
        self.assertEqual(
            self.processor._check_thresholds(80.0, thresholds),
            'warning'
        )
        self.assertEqual(
            self.processor._check_thresholds(90.0, thresholds),
            'critical'
        )


if __name__ == '__main__':
    unittest.main()