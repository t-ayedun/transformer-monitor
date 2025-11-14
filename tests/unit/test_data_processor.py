"""
Unit tests for DataProcessor
"""

import pytest
import numpy as np
from data_processor import DataProcessor


@pytest.mark.unit
class TestDataProcessor:
    """Test suite for DataProcessor"""

    def test_initialization(self, mock_config):
        """Test DataProcessor initializes correctly"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)

        assert processor.rois == rois
        assert processor.composite_config == composite_config
        assert len(processor.rois) == 1

    def test_process_frame_basic(self, mock_config, sample_thermal_frame):
        """Test basic frame processing"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # Check structure
        assert 'timestamp' in result
        assert 'regions' in result
        assert 'composite_temperature' in result
        assert 'frame_stats' in result

        # Check regions processed
        assert len(result['regions']) == 1
        assert result['regions'][0]['name'] == 'test_roi'

    def test_frame_stats_calculation(self, mock_config, sample_thermal_frame):
        """Test frame statistics are calculated correctly"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        stats = result['frame_stats']

        # Verify stats are within expected range
        assert 20 <= stats['min_temp'] <= 40
        assert 20 <= stats['max_temp'] <= 40
        assert 20 <= stats['avg_temp'] <= 40
        assert stats['min_temp'] <= stats['avg_temp'] <= stats['max_temp']
        assert stats['std_dev'] >= 0

    def test_roi_processing(self, mock_config, sample_thermal_frame):
        """Test ROI processing calculates statistics correctly"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        roi_data = result['regions'][0]

        # Check all expected fields present
        assert 'name' in roi_data
        assert 'max_temp' in roi_data
        assert 'min_temp' in roi_data
        assert 'avg_temp' in roi_data
        assert 'median_temp' in roi_data
        assert 'std_dev' in roi_data
        assert 'pixel_count' in roi_data
        assert 'alert_level' in roi_data

        # Verify pixel count (full frame: 24*32 = 768)
        assert roi_data['pixel_count'] == 768

    def test_composite_temperature_weighted_average(self, mock_config, sample_thermal_frame):
        """Test composite temperature calculation (weighted average)"""
        rois = mock_config.get('regions_of_interest')
        composite_config = {'method': 'weighted_average', 'enabled': True}

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # Composite should be close to average for single ROI
        assert result['composite_temperature'] is not None
        assert 20 <= result['composite_temperature'] <= 40

    def test_composite_temperature_max(self, mock_config, sample_thermal_frame):
        """Test composite temperature calculation (max method)"""
        rois = mock_config.get('regions_of_interest')
        composite_config = {'method': 'max', 'enabled': True}

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # For single ROI, composite max should equal ROI avg
        assert result['composite_temperature'] == result['regions'][0]['avg_temp']

    def test_composite_temperature_disabled(self, mock_config, sample_thermal_frame):
        """Test composite temperature when disabled"""
        rois = mock_config.get('regions_of_interest')
        composite_config = {'method': 'weighted_average', 'enabled': False}

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        assert result['composite_temperature'] is None

    def test_threshold_normal(self, mock_config, sample_thermal_frame):
        """Test alert level detection - normal"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # Sample frame is 20-40°C, should be normal
        assert result['regions'][0]['alert_level'] == 'normal'

    def test_threshold_warning(self, mock_config):
        """Test alert level detection - warning"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        # Create frame with warning-level temps (75-85°C)
        frame = np.full((24, 32), 80.0)

        processor = DataProcessor(rois, composite_config)
        result = processor.process(frame)

        assert result['regions'][0]['alert_level'] == 'warning'

    def test_threshold_critical(self, mock_config):
        """Test alert level detection - critical"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        # Create frame with critical-level temps (85-95°C)
        frame = np.full((24, 32), 90.0)

        processor = DataProcessor(rois, composite_config)
        result = processor.process(frame)

        assert result['regions'][0]['alert_level'] == 'critical'

    def test_threshold_emergency(self, mock_config):
        """Test alert level detection - emergency"""
        rois = mock_config.get('regions_of_interest')
        composite_config = mock_config.get('composite_temperature')

        # Create frame with emergency-level temps (>95°C)
        frame = np.full((24, 32), 100.0)

        processor = DataProcessor(rois, composite_config)
        result = processor.process(frame)

        assert result['regions'][0]['alert_level'] == 'emergency'

    def test_multiple_rois(self, mock_config, sample_thermal_frame):
        """Test processing multiple ROIs"""
        rois = [
            {
                'name': 'roi_1',
                'enabled': True,
                'coordinates': [[0, 0], [16, 12]],  # Half frame
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            },
            {
                'name': 'roi_2',
                'enabled': True,
                'coordinates': [[16, 12], [32, 24]],  # Other half
                'weight': 1.5,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            }
        ]
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # Should process both ROIs
        assert len(result['regions']) == 2
        assert result['regions'][0]['name'] == 'roi_1'
        assert result['regions'][1]['name'] == 'roi_2'

        # Each ROI should have correct pixel count (half frame each)
        assert result['regions'][0]['pixel_count'] == 192  # 16*12
        assert result['regions'][1]['pixel_count'] == 192  # 16*12

    def test_disabled_roi_skipped(self, mock_config, sample_thermal_frame):
        """Test disabled ROIs are skipped"""
        rois = [
            {
                'name': 'enabled_roi',
                'enabled': True,
                'coordinates': [[0, 0], [16, 12]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            },
            {
                'name': 'disabled_roi',
                'enabled': False,  # Disabled
                'coordinates': [[16, 12], [32, 24]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            }
        ]
        composite_config = mock_config.get('composite_temperature')

        processor = DataProcessor(rois, composite_config)
        result = processor.process(sample_thermal_frame)

        # Only enabled ROI should be processed
        assert len(result['regions']) == 1
        assert result['regions'][0]['name'] == 'enabled_roi'

    def test_emissivity_correction(self, mock_config):
        """Test emissivity correction is applied"""
        # Create two ROIs with different emissivity
        rois = [
            {
                'name': 'low_emissivity',
                'enabled': True,
                'coordinates': [[0, 0], [32, 24]],
                'weight': 1.0,
                'emissivity': 0.70,  # Low emissivity
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            }
        ]
        composite_config = {'method': 'weighted_average', 'enabled': True}

        # Create uniform temperature frame
        frame = np.full((24, 32), 50.0)

        processor = DataProcessor(rois, composite_config)
        result = processor.process(frame)

        # With lower emissivity, corrected temperature should be higher
        assert result['regions'][0]['avg_temp'] > 50.0

    def test_weighted_composite_multiple_rois(self, mock_config):
        """Test weighted average composite with different weights"""
        rois = [
            {
                'name': 'light_weight',
                'enabled': True,
                'coordinates': [[0, 0], [16, 24]],
                'weight': 0.5,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            },
            {
                'name': 'heavy_weight',
                'enabled': True,
                'coordinates': [[16, 0], [32, 24]],
                'weight': 2.0,
                'emissivity': 0.95,
                'thresholds': {'warning': 75, 'critical': 85, 'emergency': 95}
            }
        ]
        composite_config = {'method': 'weighted_average', 'enabled': True}

        # Create frame with different temps in each half
        frame = np.zeros((24, 32))
        frame[:, 0:16] = 30.0  # Left half (light weight)
        frame[:, 16:32] = 60.0  # Right half (heavy weight)

        processor = DataProcessor(rois, composite_config)
        result = processor.process(frame)

        # Composite should be closer to heavy_weight ROI (60°C)
        # weighted avg = (30*0.5 + 60*2.0) / (0.5 + 2.0) = (15 + 120) / 2.5 = 54
        assert 50 < result['composite_temperature'] < 60
        assert result['composite_temperature'] > 45  # Significantly influenced by heavier weight
