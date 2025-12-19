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
    
    def __init__(self, rois: List[Dict], composite_config: Dict, transformer_detection_config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.rois = rois or []
        self.composite_config = composite_config or {}
        self.transformer_detection_config = transformer_detection_config or {}
        
        # Transformer detection settings
        self.detection_enabled = self.transformer_detection_config.get('enabled', False)
        self.threshold_percentile = self.transformer_detection_config.get('threshold_percentile', 90)
        self.min_region_size = self.transformer_detection_config.get('min_region_size', 50)
        self.fallback_to_full_frame = self.transformer_detection_config.get('fallback_to_full_frame', True)
        
        self.logger.info(f"Initialized with {len(self.rois)} ROIs, transformer detection: {self.detection_enabled}")
    
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
        
        # Calculate composite temperature (legacy) or transformer detection (new)
        if self.detection_enabled:
            # Use automatic transformer detection
            transformer_data = self.detect_transformer_region(thermal_frame)
            result['transformer_region'] = transformer_data
            # Keep composite_temperature for backward compatibility
            result['composite_temperature'] = transformer_data.get('avg_temp')
        elif self.composite_config.get('enabled', True):
            # Legacy ROI-based composite calculation
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
    
    def detect_transformer_region(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Automatically detect transformer region from thermal heatmap
        
        Uses temperature-based segmentation to identify the hottest region
        (assumed to be the transformer) and calculate comprehensive statistics.
        
        Args:
            frame: Thermal frame (24x32)
            
        Returns:
            Dictionary with transformer statistics
        """
        try:
            # Calculate adaptive threshold based on frame statistics
            threshold_temp = np.percentile(frame, self.threshold_percentile)
            
            # Create binary mask of hot regions
            hot_mask = frame >= threshold_temp
            
            # Use connected component analysis to find distinct hot regions
            from scipy import ndimage
            labeled, num_features = ndimage.label(hot_mask)
            
            if num_features == 0:
                # No hot regions detected, fallback
                if self.fallback_to_full_frame:
                    self.logger.warning("No transformer region detected, using full frame")
                    return self._calculate_full_frame_statistics(frame)
                else:
                    return self._empty_transformer_data()
            
            # Find the largest connected region (most likely the transformer)
            region_sizes = [(i, np.sum(labeled == i)) for i in range(1, num_features + 1)]
            largest_region_id = max(region_sizes, key=lambda x: x[1])[0]
            largest_region_size = max(region_sizes, key=lambda x: x[1])[1]
            
            # Check if region is large enough
            if largest_region_size < self.min_region_size:
                if self.fallback_to_full_frame:
                    self.logger.warning(
                        f"Detected region too small ({largest_region_size} pixels), using full frame"
                    )
                    return self._calculate_full_frame_statistics(frame)
                else:
                    return self._empty_transformer_data()
            
            # Extract transformer region data
            transformer_mask = labeled == largest_region_id
            transformer_temps = frame[transformer_mask]
            
            # Calculate comprehensive statistics
            stats = self.calculate_transformer_statistics(transformer_temps)
            stats['pixel_count'] = int(largest_region_size)
            stats['detection_confidence'] = self._calculate_detection_confidence(
                transformer_temps, frame, largest_region_size
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Transformer detection failed: {e}")
            if self.fallback_to_full_frame:
                return self._calculate_full_frame_statistics(frame)
            else:
                return self._empty_transformer_data()
    
    def calculate_transformer_statistics(self, temps: np.ndarray) -> Dict[str, float]:
        """
        Calculate comprehensive statistics for transformer region
        
        Args:
            temps: Array of temperatures from transformer region
            
        Returns:
            Dictionary with min, max, avg, Q1, Q3 temperatures
        """
        return {
            'min_temp': float(np.min(temps)),
            'max_temp': float(np.max(temps)),
            'avg_temp': float(np.mean(temps)),
            'q1_temp': float(np.percentile(temps, 25)),  # 1st quartile
            'q3_temp': float(np.percentile(temps, 75)),  # 3rd quartile
            'median_temp': float(np.median(temps)),
            'std_dev': float(np.std(temps))
        }
    
    def _calculate_full_frame_statistics(self, frame: np.ndarray) -> Dict[str, float]:
        """
        Calculate statistics for entire frame (fallback)
        
        Args:
            frame: Full thermal frame
            
        Returns:
            Dictionary with statistics
        """
        temps = frame.flatten()
        stats = self.calculate_transformer_statistics(temps)
        stats['pixel_count'] = int(frame.size)
        stats['detection_confidence'] = 0.5  # Low confidence (fallback mode)
        return stats
    
    def _empty_transformer_data(self) -> Dict[str, Any]:
        """
        Return empty transformer data structure
        
        Returns:
            Dictionary with None values
        """
        return {
            'min_temp': None,
            'max_temp': None,
            'avg_temp': None,
            'q1_temp': None,
            'q3_temp': None,
            'median_temp': None,
            'std_dev': None,
            'pixel_count': 0,
            'detection_confidence': 0.0
        }
    
    def _calculate_detection_confidence(self, transformer_temps: np.ndarray, 
                                       full_frame: np.ndarray, 
                                       region_size: int) -> float:
        """
        Calculate confidence score for transformer detection
        
        Higher confidence when:
        - Transformer region is significantly hotter than surroundings
        - Region size is reasonable (not too small or too large)
        - Temperature distribution is consistent
        
        Args:
            transformer_temps: Temperatures in detected region
            full_frame: Full thermal frame
            region_size: Size of detected region in pixels
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Temperature contrast (transformer vs background)
        transformer_avg = np.mean(transformer_temps)
        frame_avg = np.mean(full_frame)
        temp_contrast = (transformer_avg - frame_avg) / (frame_avg + 1e-6)
        contrast_score = min(temp_contrast / 0.3, 1.0)  # 30% contrast = full score
        
        # Region size score (prefer 10-50% of frame)
        frame_size = full_frame.size
        size_ratio = region_size / frame_size
        if 0.1 <= size_ratio <= 0.5:
            size_score = 1.0
        elif size_ratio < 0.1:
            size_score = size_ratio / 0.1
        else:
            size_score = max(0.0, 1.0 - (size_ratio - 0.5) / 0.5)
        
        # Temperature consistency (low std dev = more consistent)
        std_dev = np.std(transformer_temps)
        consistency_score = max(0.0, 1.0 - std_dev / 10.0)  # 10°C std = 0 score
        
        # Weighted average
        confidence = (0.5 * contrast_score + 0.3 * size_score + 0.2 * consistency_score)
        
        return float(np.clip(confidence, 0.0, 1.0))
    
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