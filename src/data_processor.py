"""
Data Processor
Processes thermal frames and calculates ROI statistics
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Any


class DataProcessor:
    """Process thermal data and calculate statistics"""
    
    def __init__(self, rois: List[Dict], composite_config: Dict):
        self.logger = logging.getLogger(__name__)
        self.rois = rois
        self.composite_config = composite_config
        
        self.logger.info(f"Initialized with {len(rois)} ROIs")
    
    def process(self, thermal_frame: np.ndarray) -> Dict[str, Any]:
        """
        Process thermal frame and calculate all statistics
        
        Args:
            thermal_frame: numpy array (24, 32) with temperatures
            
        Returns:
            Dictionary with processed data
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        result = {
            'timestamp': timestamp,
            'regions': [],
            'composite_temperature': None,
            'frame_stats': self._calculate_frame_stats(thermal_frame)
        }
        
        # Process each ROI
        roi_temps = []
        roi_weights = []
        
        for roi_config in self.rois:
            if not roi_config.get('enabled', True):
                continue
            
            roi_data = self._process_roi(thermal_frame, roi_config)
            result['regions'].append(roi_data)
            
            # Collect for composite calculation
            roi_temps.append(roi_data['max_temp'])
            roi_weights.append(roi_config.get('weight', 1.0))
        
        # Calculate composite temperature
        if self.composite_config.get('enabled', True):
            result['composite_temperature'] = self._calculate_composite(
                roi_temps,
                roi_weights,
                method=self.composite_config.get('method', 'weighted_average')
            )
        
        return result
    
    def _process_roi(self, frame: np.ndarray, roi_config: Dict) -> Dict[str, Any]:
        """Process a single region of interest"""
        name = roi_config['name']
        coords = roi_config['coordinates']
        
        # Extract ROI from frame
        # coords format: [[x_min, y_min], [x_max, y_max]]
        x_min, y_min = coords[0]
        x_max, y_max = coords[1]
        
        roi_data = frame[y_min:y_max, x_min:x_max]
        
        # Apply emissivity correction if specified
        emissivity = roi_config.get('emissivity', 0.95)
        if emissivity != 1.0:
            roi_data = self._apply_emissivity(roi_data, emissivity)
        
        # Calculate statistics
        stats = {
            'name': name,
            'max_temp': float(np.max(roi_data)),
            'min_temp': float(np.min(roi_data)),
            'avg_temp': float(np.mean(roi_data)),
            'median_temp': float(np.median(roi_data)),
            'std_dev': float(np.std(roi_data)),
            'pixel_count': int(roi_data.size)
        }
        
        # Check thresholds
        thresholds = roi_config.get('thresholds', {})
        stats['alert_level'] = self._check_thresholds(stats['max_temp'], thresholds)
        
        return stats
    
    def _calculate_frame_stats(self, frame: np.ndarray) -> Dict[str, float]:
        """Calculate statistics for entire frame"""
        return {
            'max_temp': float(np.max(frame)),
            'min_temp': float(np.min(frame)),
            'avg_temp': float(np.mean(frame)),
            'median_temp': float(np.median(frame)),
            'std_dev': float(np.std(frame))
        }
    
    def _calculate_composite(self, temps: List[float], weights: List[float], 
                            method: str) -> float:
        """
        Calculate composite temperature from multiple ROIs
        
        Methods:
            - weighted_average: sum(temp * weight) / sum(weight)
            - max: maximum temperature across all ROIs
            - average: simple average of all ROI max temps
        """
        if not temps:
            return None
        
        if method == 'weighted_average':
            return float(np.average(temps, weights=weights))
        elif method == 'max':
            return float(np.max(temps))
        elif method == 'average':
            return float(np.mean(temps))
        else:
            self.logger.warning(f"Unknown composite method: {method}, using average")
            return float(np.mean(temps))
    
    def _apply_emissivity(self, data: np.ndarray, emissivity: float) -> np.ndarray:
        """Apply emissivity correction using Stefan-Boltzmann"""
        # Convert to Kelvin
        data_k = data + 273.15
        
        # Apply correction: T_actual = T_measured / ε^0.25
        corrected_k = data_k / (emissivity ** 0.25)
        
        # Convert back to Celsius
        return corrected_k - 273.15
    
    def _check_thresholds(self, temperature: float, thresholds: Dict) -> str:
        """
        Check temperature against thresholds
        
        Returns: 'normal', 'warning', 'critical', or 'emergency'
        """
        if not thresholds:
            return 'normal'
        
        if temperature >= thresholds.get('emergency', float('inf')):
            return 'emergency'
        elif temperature >= thresholds.get('critical', float('inf')):
            return 'critical'
        elif temperature >= thresholds.get('warning', float('inf')):
            return 'warning'
        else:
            return 'normal'