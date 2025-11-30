"""
Thermal Camera Interface
Handles MLX90640 thermal camera communication with advanced processing

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
import board
import busio
import adafruit_mlx90640
import cv2
from scipy import ndimage


class ThermalCapture:
    """
    Interface for MLX90640 thermal camera with advanced processing

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
        
        IMPORTANT: Pi 5 works best with refresh_rate=2 (2 Hz)
        Higher rates may cause I2C timeout issues
        """
        self.logger = logging.getLogger(__name__)
        self.i2c_addr = i2c_addr
        # Force maximum 2 Hz on Pi 5 to avoid I2C timeouts
        self.refresh_rate = min(refresh_rate, 2)
        self.mlx = None
        self.i2c = None
        self.frame_shape = (24, 32)  # MLX90640 resolution

        # Advanced processing settings
        self.enable_advanced_processing = enable_advanced_processing
        self.temporal_buffer_size = 5  # Frames to keep for temporal filtering
        self.frame_buffer = deque(maxlen=self.temporal_buffer_size)

        # Bad pixel map (will be learned during operation)
        self.bad_pixels = set()
        self.frame_count = 0

        # Hotspot tracking
        self.hotspots_history = deque(maxlen=10)
        self.hotspot_threshold = 80.0  # °C

        # Ambient temperature for compensation
        self.ambient_temp = None
        
        # Connection health tracking
        self.consecutive_failures = 0
        self.last_successful_frame = None

        if self.refresh_rate != refresh_rate:
            self.logger.warning(
                f"Refresh rate capped at {self.refresh_rate}Hz (requested {refresh_rate}Hz) "
                "for Pi 5 stability"
            )

        self._initialize_camera()

    def _initialize_camera(self, retry_count=3):
        """Initialize I2C connection and camera with retries"""
        for attempt in range(retry_count):
            try:
                self.logger.info(
                    f"Initializing MLX90640 at address 0x{self.i2c_addr:02x} "
                    f"(attempt {attempt + 1}/{retry_count})"
                )

                # Initialize I2C - Blinka doesn't support frequency setting, but that's OK
                self.i2c = busio.I2C(board.SCL, board.SDA)

                # Give I2C bus time to stabilize
                time.sleep(0.5)
                
                # Lock the I2C bus while we initialize
                while not self.i2c.try_lock():
                    time.sleep(0.01)
                
                try:
                    # Initialize MLX90640
                    self.mlx = adafruit_mlx90640.MLX90640(self.i2c)
                    
                    # Set refresh rate (use lowest setting for reliability)
                    self.mlx.refresh_rate = self._get_refresh_rate_constant(self.refresh_rate)
                    
                    self.logger.info(f"MLX90640 refresh rate set to {self.refresh_rate}Hz")

                    # Try to capture a test frame to verify it works
                    # This is where the "math domain error" was happening
                    test_frame = [0] * 768
                    
                    # Give the sensor time to stabilize after init
                    time.sleep(1.0)
                    
                    self.mlx.getFrame(test_frame)
                    
                    # Verify frame has reasonable data
                    test_array = np.array(test_frame)
                    if np.all(test_array == 0) or np.any(np.isnan(test_array)):
                        raise ValueError("Test frame contains invalid data")
                    
                    temp_range = f"{test_array.min():.1f}°C to {test_array.max():.1f}°C"
                    self.logger.info(
                        f"MLX90640 initialized successfully at {self.refresh_rate}Hz "
                        f"(Test frame: {temp_range}, Advanced processing: {self.enable_advanced_processing})"
                    )
                    
                    self.consecutive_failures = 0
                    return
                    
                finally:
                    # Always unlock the I2C bus
                    self.i2c.unlock()

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize MLX90640 (attempt {attempt + 1}/{retry_count}): {e}"
                )
                
                # Clean up and wait before retry
                if self.mlx:
                    self.mlx = None
                if self.i2c:
                    try:
                        if self.i2c.try_lock():
                            self.i2c.unlock()
                        self.i2c.deinit()
                    except:
                        pass
                    self.i2c = None
                
                if attempt < retry_count - 1:
                    wait_time = 2 * (attempt + 1)  # Increasing wait time
                    self.logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"Failed to initialize MLX90640 after {retry_count} attempts")

    def _get_refresh_rate_constant(self, rate):
        """Convert refresh rate to MLX90640 constant"""
        rate_map = {
            0.5: adafruit_mlx90640.RefreshRate.REFRESH_0_5_HZ,
            1: adafruit_mlx90640.RefreshRate.REFRESH_1_HZ,
            2: adafruit_mlx90640.RefreshRate.REFRESH_2_HZ,
            4: adafruit_mlx90640.RefreshRate.REFRESH_4_HZ,
            8: adafruit_mlx90640.RefreshRate.REFRESH_8_HZ,
            16: adafruit_mlx90640.RefreshRate.REFRESH_16_HZ,
            32: adafruit_mlx90640.RefreshRate.REFRESH_32_HZ,
            64: adafruit_mlx90640.RefreshRate.REFRESH_64_HZ,
        }
        return rate_map.get(rate, adafruit_mlx90640.RefreshRate.REFRESH_2_HZ)

    def get_frame(self, max_retries=3, apply_processing=True):
        """
        Capture a thermal frame with optional advanced processing

        Args:
            max_retries: Number of retry attempts
            apply_processing: Apply advanced processing pipeline

        Returns:
            numpy array of shape (24, 32) with temperatures in Celsius
        """
        for attempt in range(max_retries):
            try:
                # Add delay between frames to prevent I2C bus saturation
                if self.last_successful_frame is not None:
                    time_since_last = time.time() - self.last_successful_frame
                    min_interval = 1.0 / self.refresh_rate
                    if time_since_last < min_interval:
                        time.sleep(min_interval - time_since_last)

                frame = [0] * 768  # 24x32 = 768 pixels
                
                # Lock I2C bus during frame capture
                while not self.i2c.try_lock():
                    time.sleep(0.01)
                
                try:
                    self.mlx.getFrame(frame)
                except RuntimeError as e:
                    if "Too many retries" in str(e):
                        self.logger.warning(f"I2C timeout (attempt {attempt + 1}/{max_retries})")
                        self.consecutive_failures += 1
                        
                        # If too many consecutive failures, try to reinitialize
                        if self.consecutive_failures >= 5:
                            self.logger.warning("Too many consecutive failures, reinitializing camera...")
                            self.i2c.unlock()
                            self._reinitialize_camera()
                            return None
                        
                        time.sleep(0.5)  # Longer wait after I2C timeout
                        continue
                    else:
                        raise
                finally:
                    self.i2c.unlock()

                # Convert to numpy array and reshape
                frame_array = np.array(frame, dtype=np.float32).reshape(self.frame_shape)

                # Basic validation
                if not self._validate_frame(frame_array):
                    self.logger.warning(f"Invalid frame data (attempt {attempt + 1})")
                    time.sleep(0.1)
                    continue

                # Apply advanced processing if enabled
                if apply_processing and self.enable_advanced_processing:
                    frame_array = self._process_frame(frame_array)

                # Add to temporal buffer
                self.frame_buffer.append(frame_array.copy())
                self.frame_count += 1
                self.last_successful_frame = time.time()
                self.consecutive_failures = 0

                return frame_array

            except Exception as e:
                self.logger.error(f"Frame capture error (attempt {attempt + 1}): {e}")
                time.sleep(0.2)

        self.logger.error("Failed to capture valid frame after retries")
        return None

    def _reinitialize_camera(self):
        """Reinitialize camera after persistent failures"""
        self.logger.info("Reinitializing thermal camera...")
        try:
            if self.mlx:
                self.mlx = None
            if self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
                self.i2c = None
            
            time.sleep(2)  # Wait for hardware to reset
            self._initialize_camera()
            self.consecutive_failures = 0
            self.logger.info("Camera reinitialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to reinitialize camera: {e}")

    def _process_frame(self, frame):
        """
        Apply advanced processing pipeline to thermal frame

        Steps:
        1. Bad pixel correction
        2. Temporal filtering (if buffer has enough frames)
        3. Spatial denoising
        4. Ambient compensation
        """
        # 1. Bad pixel correction
        frame = self._correct_bad_pixels(frame)

        # 2. Temporal filtering (reduces noise by averaging recent frames)
        if len(self.frame_buffer) >= 3:
            frame = self._temporal_filter(frame)

        # 3. Spatial denoising (Gaussian blur)
        frame = self._spatial_denoise(frame)

        # 4. Ambient compensation (if ambient temp is set)
        if self.ambient_temp is not None:
            frame = self._ambient_compensation(frame)

        return frame

    def _correct_bad_pixels(self, frame):
        """
        Correct bad/dead pixels using interpolation from neighbors

        Bad pixels are detected as outliers that appear consistently
        """
        # Auto-detect bad pixels (very simple heuristic)
        # A more robust implementation would calibrate during startup
        median_temp = np.median(frame)
        std_temp = np.std(frame)

        # Pixels that are >5 std deviations from median might be bad
        outliers = np.abs(frame - median_temp) > (5 * std_temp)

        if np.any(outliers):
            # Replace bad pixels with median of neighbors
            for y, x in zip(*np.where(outliers)):
                # Get neighbor values
                y_min = max(0, y - 1)
                y_max = min(frame.shape[0], y + 2)
                x_min = max(0, x - 1)
                x_max = min(frame.shape[1], x + 2)

                neighbors = frame[y_min:y_max, x_min:x_max]
                frame[y, x] = np.median(neighbors)

                self.bad_pixels.add((y, x))

        return frame

    def _temporal_filter(self, current_frame):
        """
        Temporal filtering: Average recent frames to reduce noise

        This is effective for stationary scenes (transformers)
        Uses exponential weighted moving average
        """
        if len(self.frame_buffer) < 2:
            return current_frame

        # Convert deque to array
        buffer_array = np.array(list(self.frame_buffer))

        # Weighted average: more weight on recent frames
        weights = np.exp(np.linspace(-1, 0, len(buffer_array)))
        weights /= weights.sum()

        # Weighted average along time axis
        filtered = np.average(buffer_array, axis=0, weights=weights)

        return filtered.astype(np.float32)

    def _spatial_denoise(self, frame):
        """
        Spatial denoising using Gaussian filter

        Reduces high-frequency noise while preserving thermal gradients
        """
        # Use small kernel to preserve detail
        denoised = cv2.GaussianBlur(frame, (3, 3), 0.5)

        return denoised

    def _ambient_compensation(self, frame):
        """
        Compensate for ambient temperature

        Thermal cameras can drift with ambient temp changes
        This uses the ambient temp to adjust readings
        """
        if self.ambient_temp is None:
            return frame

        # Simple linear compensation
        # More sophisticated methods would use sensor-specific calibration
        compensation = (self.ambient_temp - 25.0) * 0.1  # 10% drift per 10°C

        return frame - compensation

    def detect_hotspots(self, frame, threshold=None):
        """
        Detect and track thermal hotspots

        Args:
            frame: Thermal frame
            threshold: Temperature threshold for hotspot detection

        Returns:
            List of hotspot dictionaries with location and temperature
        """
        if threshold is None:
            threshold = self.hotspot_threshold

        # Find pixels above threshold
        hotspot_mask = frame > threshold

        # Label connected components (blobs)
        labeled, num_features = ndimage.label(hotspot_mask)

        hotspots = []

        for i in range(1, num_features + 1):
            # Get pixels in this hotspot
            hotspot_pixels = frame[labeled == i]
            hotspot_coords = np.argwhere(labeled == i)

            # Calculate hotspot properties
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

        # Track hotspots history
        self.hotspots_history.append({
            'timestamp': datetime.now().isoformat(),
            'hotspots': hotspots
        })

        return hotspots

    def calculate_thermal_gradient(self, frame):
        """
        Calculate thermal gradient magnitude and direction

        Useful for detecting uneven heating patterns
        that might indicate faults

        Returns:
            gradient_magnitude: Magnitude of temperature gradient
            gradient_direction: Direction of gradient in degrees
        """
        # Calculate gradients using Sobel operators
        grad_x = cv2.Sobel(frame, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(frame, cv2.CV_32F, 0, 1, ksize=3)

        # Magnitude and direction
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        gradient_direction = np.arctan2(grad_y, grad_x) * 180 / np.pi

        return gradient_magnitude, gradient_direction

    def super_resolution_upscale(self, frame, scale_factor=4):
        """
        Upscale thermal frame using bicubic interpolation

        Increases resolution from 24x32 to larger size for better
        visualization and analysis

        Args:
            frame: Input thermal frame (24x32)
            scale_factor: Upscaling factor (default 4 -> 96x128)

        Returns:
            Upscaled frame
        """
        new_height = frame.shape[0] * scale_factor
        new_width = frame.shape[1] * scale_factor

        # Use bicubic interpolation for smooth upscaling
        upscaled = cv2.resize(
            frame,
            (new_width, new_height),
            interpolation=cv2.INTER_CUBIC
        )

        return upscaled

    def get_frame_statistics(self, frame):
        """
        Calculate comprehensive frame statistics

        Returns:
            Dictionary with detailed statistics
        """
        return {
            'min': float(np.min(frame)),
            'max': float(np.max(frame)),
            'mean': float(np.mean(frame)),
            'median': float(np.median(frame)),
            'std': float(np.std(frame)),
            'percentile_95': float(np.percentile(frame, 95)),
            'percentile_5': float(np.percentile(frame, 5)),
            'range': float(np.ptp(frame)),  # peak-to-peak
        }

    def _validate_frame(self, frame):
        """Validate thermal frame data"""
        # Check for reasonable temperature range (-40°C to 300°C)
        if np.any(frame < -40) or np.any(frame > 300):
            return False

        # Check for NaN or inf values
        if np.any(np.isnan(frame)) or np.any(np.isinf(frame)):
            return False

        return True

    def set_ambient_temperature(self, temp):
        """
        Set ambient temperature for compensation

        Args:
            temp: Ambient temperature in Celsius
        """
        self.ambient_temp = temp
        self.logger.info(f"Ambient temperature set to {temp}°C")

    def get_sensor_temp(self):
        """
        Get internal sensor temperature

        This can be used for ambient temperature estimation
        """
        try:
            # The sensor temperature is embedded in the frame data
            # This is a simplified approach - actual implementation may vary
            frame = self.get_frame(apply_processing=False)
            if frame is not None:
                # Sensor temp is typically around ambient
                # Use minimum temperature as estimate
                return float(np.percentile(frame, 10))  # 10th percentile
            return None
        except Exception as e:
            self.logger.error(f"Failed to get sensor temperature: {e}")
            return None

    def apply_emissivity_correction(self, frame, emissivity=0.95):
        """
        Apply emissivity correction to thermal frame

        Stefan-Boltzmann approach:
        T_actual = T_measured / emissivity^0.25

        Args:
            frame: Thermal frame in Celsius
            emissivity: Material emissivity (0-1)

        Returns:
            Corrected frame
        """
        if emissivity == 1.0:
            return frame

        # Convert to Kelvin
        frame_k = frame + 273.15

        # Apply correction
        corrected_k = frame_k / (emissivity ** 0.25)

        # Convert back to Celsius
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
        """Cleanup camera resources"""
        self.logger.info("Closing thermal camera")
        self.logger.info(
            f"Processed {self.frame_count} frames, "
            f"detected {len(self.bad_pixels)} bad pixels"
        )
        
        if self.i2c:
            try:
                if self.i2c.try_lock():
                    self.i2c.unlock()
                self.i2c.deinit()
            except:
                pass
        
        self.mlx = None
        self.i2c = None
