"""
Thermal Camera Interface
Handles MLX90640 thermal camera communication with advanced processing
Uses PyMLX90640 library (more stable on Pi 5)

Advanced Features:
- Image denoising (Gaussian and temporal filtering)
- Ambient temperature compensation
- Hotspot detection and tracking
- Thermal gradient analysis
- Super-resolution upscaling
- Bad pixel correction
"""

import time
import logging
import numpy as np
from collections import deque
from datetime import datetime
import cv2
from scipy import ndimage

try:
    from PyMLX90640 import LibMLX90640 as mlx_lib
    from PyMLX90640.MLX90640 import MLX90640, RefreshRate
    LIBRARY_AVAILABLE = True
except ImportError:
    LIBRARY_AVAILABLE = False
    print("WARNING: PyMLX90640 not installed. Install with: pip install RPI-PyMLX90640")


class ThermalCapture:
    """
    Interface for MLX90640 thermal camera with advanced processing
    Uses PyMLX90640 library for better Pi 5 compatibility

    Processing Pipeline:
    1. Raw frame capture
    2. Bad pixel correction
    3. Temporal filtering (noise reduction)
    4. Spatial denoising
    5. Ambient compensation (optional)
    6. Emissivity correction
    7. Super-resolution upscaling (optional)
    """

    def __init__(self, i2c_addr=0x33, i2c_bus=1, refresh_rate=2, enable_advanced_processing=True):
        """
        Initialize thermal camera
        
        Args:
            i2c_addr: I2C address (default 0x33)
            i2c_bus: I2C bus number (default 1)
            refresh_rate: Camera refresh rate in Hz (2 recommended for Pi 5)
            enable_advanced_processing: Enable noise filtering and processing
        """
        if not LIBRARY_AVAILABLE:
            raise ImportError("PyMLX90640 library not installed")
            
        self.logger = logging.getLogger(__name__)
        self.i2c_addr = i2c_addr
        self.i2c_bus = i2c_bus
        self.refresh_rate = refresh_rate
        self.mlx = None
        self.frame_shape = (24, 32)  # MLX90640 resolution

        # Advanced processing settings
        self.enable_advanced_processing = enable_advanced_processing
        self.temporal_buffer_size = 5
        self.frame_buffer = deque(maxlen=self.temporal_buffer_size)

        # Bad pixel map
        self.bad_pixels = set()
        self.frame_count = 0

        # Hotspot tracking
        self.hotspots_history = deque(maxlen=10)
        self.hotspot_threshold = 80.0  # °C

        # Ambient temperature
        self.ambient_temp = None
        
        # Connection health
        self.consecutive_failures = 0
        self.last_successful_frame = None

        self._initialize_camera()

    def _initialize_camera(self, retry_count=3):
        """Initialize MLX90640 with PyMLX90640 library"""
        for attempt in range(retry_count):
            try:
                self.logger.info(
                    f"Initializing MLX90640 at 0x{self.i2c_addr:02x} on bus {self.i2c_bus} "
                    f"(attempt {attempt + 1}/{retry_count})"
                )

                # Initialize camera
                self.mlx = MLX90640(
                    address=self.i2c_addr,
                    i2c_bus=self.i2c_bus
                )
                
                # Set refresh rate
                refresh_rate_map = {
                    0.5: RefreshRate.REFRESH_0_5_HZ,
                    1: RefreshRate.REFRESH_1_HZ,
                    2: RefreshRate.REFRESH_2_HZ,
                    4: RefreshRate.REFRESH_4_HZ,
                    8: RefreshRate.REFRESH_8_HZ,
                    16: RefreshRate.REFRESH_16_HZ,
                    32: RefreshRate.REFRESH_32_HZ,
                    64: RefreshRate.REFRESH_64_HZ,
                }
                
                rate_const = refresh_rate_map.get(self.refresh_rate, RefreshRate.REFRESH_2_HZ)
                self.mlx.set_refresh_rate(rate_const)
                
                self.logger.info(f"Refresh rate set to {self.refresh_rate} Hz")

                # Test frame capture
                test_frame = self.mlx.get_frame()
                
                if test_frame is None or len(test_frame) != 768:
                    raise ValueError("Invalid test frame")
                
                test_array = np.array(test_frame)
                if np.all(test_array == 0) or np.any(np.isnan(test_array)):
                    raise ValueError("Test frame contains invalid data")
                
                temp_range = f"{test_array.min():.1f}°C to {test_array.max():.1f}°C"
                self.logger.info(
                    f"MLX90640 initialized successfully! "
                    f"Test frame: {temp_range}, "
                    f"Advanced processing: {self.enable_advanced_processing}"
                )
                
                self.consecutive_failures = 0
                return

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize MLX90640 (attempt {attempt + 1}/{retry_count}): {e}"
                )
                
                if self.mlx:
                    try:
                        self.mlx.cleanup()
                    except:
                        pass
                    self.mlx = None
                
                if attempt < retry_count - 1:
                    wait_time = 2 * (attempt + 1)
                    self.logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"Failed to initialize MLX90640 after {retry_count} attempts")

    def get_frame(self, max_retries=3, apply_processing=True):
        """
        Capture a thermal frame

        Args:
            max_retries: Number of retry attempts
            apply_processing: Apply advanced processing pipeline

        Returns:
            numpy array of shape (24, 32) with temperatures in Celsius
        """
        for attempt in range(max_retries):
            try:
                # Respect frame rate limit
                if self.last_successful_frame is not None:
                    time_since_last = time.time() - self.last_successful_frame
                    min_interval = 1.0 / self.refresh_rate
                    if time_since_last < min_interval:
                        time.sleep(min_interval - time_since_last)

                # Get frame from sensor
                frame_data = self.mlx.get_frame()
                
                if frame_data is None or len(frame_data) != 768:
                    self.logger.warning(f"Invalid frame data (attempt {attempt + 1})")
                    time.sleep(0.2)
                    continue

                # Convert to numpy array
                frame_array = np.array(frame_data, dtype=np.float32).reshape(self.frame_shape)

                # Validate
                if not self._validate_frame(frame_array):
                    self.logger.warning(f"Frame validation failed (attempt {attempt + 1})")
                    time.sleep(0.1)
                    continue

                # Apply processing
                if apply_processing and self.enable_advanced_processing:
                    frame_array = self._process_frame(frame_array)

                # Update buffers
                self.frame_buffer.append(frame_array.copy())
                self.frame_count += 1
                self.last_successful_frame = time.time()
                self.consecutive_failures = 0

                return frame_array

            except Exception as e:
                self.logger.error(f"Frame capture error (attempt {attempt + 1}): {e}")
                self.consecutive_failures += 1
                
                # Reinitialize if too many failures
                if self.consecutive_failures >= 5:
                    self.logger.warning("Too many failures, reinitializing...")
                    self._reinitialize_camera()
                
                time.sleep(0.2)

        self.logger.error("Failed to capture valid frame after retries")
        return None

    def _reinitialize_camera(self):
        """Reinitialize camera after failures"""
        self.logger.info("Reinitializing thermal camera...")
        try:
            if self.mlx:
                try:
                    self.mlx.cleanup()
                except:
                    pass
                self.mlx = None
            
            time.sleep(2)
            self._initialize_camera()
            self.consecutive_failures = 0
            self.logger.info("Camera reinitialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to reinitialize: {e}")

    def _process_frame(self, frame):
        """Apply processing pipeline"""
        frame = self._correct_bad_pixels(frame)
        
        if len(self.frame_buffer) >= 3:
            frame = self._temporal_filter(frame)
        
        frame = self._spatial_denoise(frame)
        
        if self.ambient_temp is not None:
            frame = self._ambient_compensation(frame)
        
        return frame

    def _correct_bad_pixels(self, frame):
        """Correct bad pixels using neighbor interpolation"""
        median_temp = np.median(frame)
        std_temp = np.std(frame)
        outliers = np.abs(frame - median_temp) > (5 * std_temp)

        if np.any(outliers):
            for y, x in zip(*np.where(outliers)):
                y_min = max(0, y - 1)
                y_max = min(frame.shape[0], y + 2)
                x_min = max(0, x - 1)
                x_max = min(frame.shape[1], x + 2)
                neighbors = frame[y_min:y_max, x_min:x_max]
                frame[y, x] = np.median(neighbors)
                self.bad_pixels.add((y, x))

        return frame

    def _temporal_filter(self, current_frame):
        """Temporal filtering with exponential weighting"""
        if len(self.frame_buffer) < 2:
            return current_frame

        buffer_array = np.array(list(self.frame_buffer))
        weights = np.exp(np.linspace(-1, 0, len(buffer_array)))
        weights /= weights.sum()
        filtered = np.average(buffer_array, axis=0, weights=weights)
        return filtered.astype(np.float32)

    def _spatial_denoise(self, frame):
        """Gaussian spatial denoising"""
        return cv2.GaussianBlur(frame, (3, 3), 0.5)

    def _ambient_compensation(self, frame):
        """Ambient temperature compensation"""
        if self.ambient_temp is None:
            return frame
        compensation = (self.ambient_temp - 25.0) * 0.1
        return frame - compensation

    def detect_hotspots(self, frame, threshold=None):
        """Detect thermal hotspots"""
        if threshold is None:
            threshold = self.hotspot_threshold

        hotspot_mask = frame > threshold
        labeled, num_features = ndimage.label(hotspot_mask)
        hotspots = []

        for i in range(1, num_features + 1):
            hotspot_pixels = frame[labeled == i]
            hotspot_coords = np.argwhere(labeled == i)
            max_temp = np.max(hotspot_pixels)
            avg_temp = np.mean(hotspot_pixels)
            center_y, center_x = hotspot_coords.mean(axis=0)
            area = len(hotspot_pixels)

            hotspots.append({
                'center': (int(center_x), int(center_y)),
                'max_temp': float(max_temp),
                'avg_temp': float(avg_temp),
                'area': int(area),
                'timestamp': datetime.now().isoformat()
            })

        self.hotspots_history.append({
            'timestamp': datetime.now().isoformat(),
            'hotspots': hotspots
        })

        return hotspots

    def calculate_thermal_gradient(self, frame):
        """Calculate thermal gradient"""
        grad_x = cv2.Sobel(frame, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(frame, cv2.CV_32F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        gradient_direction = np.arctan2(grad_y, grad_x) * 180 / np.pi
        return gradient_magnitude, gradient_direction

    def super_resolution_upscale(self, frame, scale_factor=4):
        """Upscale frame using bicubic interpolation"""
        new_height = frame.shape[0] * scale_factor
        new_width = frame.shape[1] * scale_factor
        return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

    def get_frame_statistics(self, frame):
        """Calculate frame statistics"""
        return {
            'min': float(np.min(frame)),
            'max': float(np.max(frame)),
            'mean': float(np.mean(frame)),
            'median': float(np.median(frame)),
            'std': float(np.std(frame)),
            'percentile_95': float(np.percentile(frame, 95)),
            'percentile_5': float(np.percentile(frame, 5)),
            'range': float(np.ptp(frame)),
        }

    def _validate_frame(self, frame):
        """Validate frame data"""
        if np.any(frame < -40) or np.any(frame > 300):
            return False
        if np.any(np.isnan(frame)) or np.any(np.isinf(frame)):
            return False
        return True

    def set_ambient_temperature(self, temp):
        """Set ambient temperature for compensation"""
        self.ambient_temp = temp
        self.logger.info(f"Ambient temperature set to {temp}°C")

    def get_sensor_temp(self):
        """Get sensor temperature estimate"""
        try:
            frame = self.get_frame(apply_processing=False)
            if frame is not None:
                return float(np.percentile(frame, 10))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get sensor temperature: {e}")
            return None

    def apply_emissivity_correction(self, frame, emissivity=0.95):
        """Apply emissivity correction"""
        if emissivity == 1.0:
            return frame
        frame_k = frame + 273.15
        corrected_k = frame_k / (emissivity ** 0.25)
        return corrected_k - 273.15

    def get_processing_stats(self):
        """Get processing statistics"""
        return {
            'frames_processed': self.frame_count,
            'bad_pixels_detected': len(self.bad_pixels),
            'buffer_size': len(self.frame_buffer),
            'hotspots_tracked': len(self.hotspots_history),
            'advanced_processing_enabled': self.enable_advanced_processing,
            'consecutive_failures': self.consecutive_failures
        }

    def close(self):
        """Cleanup resources"""
        self.logger.info("Closing thermal camera")
        self.logger.info(
            f"Processed {self.frame_count} frames, "
            f"detected {len(self.bad_pixels)} bad pixels"
        )
        if self.mlx:
            try:
                self.mlx.cleanup()
            except:
                pass
            self.mlx = None
