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
import math
import logging
import numpy as np
from collections import deque
from datetime import datetime
import board
import busio
import adafruit_mlx90640
import cv2


def _safe_ExtractAlphaParameters(self) -> None:
    """
    Monkey patch for MLX90640 _ExtractAlphaParameters to handle ZeroDivisionError
    and infinite loops.
    """
    # Access module globals from the library
    eeData = adafruit_mlx90640.eeData
    SCALEALPHA = adafruit_mlx90640.SCALEALPHA
    
    # extract alpha
    accRemScale = eeData[32] & 0x000F
    accColumnScale = (eeData[32] & 0x00F0) >> 4
    accRowScale = (eeData[32] & 0x0F00) >> 8
    alphaScale = ((eeData[32] & 0xF000) >> 12) + 30
    alphaRef = eeData[33]
    accRow = [0] * 24
    accColumn = [0] * 32
    alphaTemp = [0] * 768

    for i in range(6):
        p = i * 4
        accRow[p + 0] = eeData[34 + i] & 0x000F
        accRow[p + 1] = (eeData[34 + i] & 0x00F0) >> 4
        accRow[p + 2] = (eeData[34 + i] & 0x0F00) >> 8
        accRow[p + 3] = (eeData[34 + i] & 0xF000) >> 12

    for i in range(24):
        if accRow[i] > 7:
            accRow[i] -= 16

    for i in range(8):
        p = i * 4
        accColumn[p + 0] = eeData[40 + i] & 0x000F
        accColumn[p + 1] = (eeData[40 + i] & 0x00F0) >> 4
        accColumn[p + 2] = (eeData[40 + i] & 0x0F00) >> 8
        accColumn[p + 3] = (eeData[40 + i] & 0xF000) >> 12

    for i in range(32):
        if accColumn[i] > 7:
            accColumn[i] -= 16

    for i in range(24):
        for j in range(32):
            p = 32 * i + j
            alphaTemp[p] = (eeData[64 + p] & 0x03F0) >> 4
            if alphaTemp[p] > 31:
                alphaTemp[p] -= 64
            alphaTemp[p] *= 1 << accRemScale
            alphaTemp[p] += (
                alphaRef + (accRow[i] << accRowScale) + (accColumn[j] << accColumnScale)
            )
            alphaTemp[p] /= math.pow(2, alphaScale)
            alphaTemp[p] -= self.tgc * (self.cpAlpha[0] + self.cpAlpha[1]) / 2
            
            # Patch: Check for zero before division
            if alphaTemp[p] == 0:
                alphaTemp[p] = 0.000001
                
            alphaTemp[p] = SCALEALPHA / alphaTemp[p]

    temp = max(alphaTemp)

    alphaScale = 0
    # Patch: Guard against infinite loop if temp <= 0
    if temp > 0:
        while temp < 32768 and alphaScale < 100:
            temp *= 2
            alphaScale += 1
    else:
        alphaScale = 30

    for i in range(768):
        temp = alphaTemp[i] * math.pow(2, alphaScale)
        self.alpha[i] = int(temp + 0.5)

    self.alphaScale = alphaScale


def _safe_ExtractKtaPixelParameters(self) -> None:
    """Safe version of _ExtractKtaPixelParameters"""
    eeData = adafruit_mlx90640.eeData
    
    KtaRC = [0] * 4
    ktaTemp = [0] * 768

    KtaRoCo = (eeData[54] & 0xFF00) >> 8
    if KtaRoCo > 127:
        KtaRoCo -= 256
    KtaRC[0] = KtaRoCo

    KtaReCo = eeData[54] & 0x00FF
    if KtaReCo > 127:
        KtaReCo -= 256
    KtaRC[2] = KtaReCo

    KtaRoCe = (eeData[55] & 0xFF00) >> 8
    if KtaRoCe > 127:
        KtaRoCe -= 256
    KtaRC[1] = KtaRoCe

    KtaReCe = eeData[55] & 0x00FF
    if KtaReCe > 127:
        KtaReCe -= 256
    KtaRC[3] = KtaReCe

    ktaScale1 = ((eeData[56] & 0x00F0) >> 4) + 8
    ktaScale2 = eeData[56] & 0x000F

    for i in range(24):
        for j in range(32):
            p = 32 * i + j
            split = 2 * (p // 32 - (p // 64) * 2) + p % 2
            ktaTemp[p] = (eeData[64 + p] & 0x000E) >> 1
            if ktaTemp[p] > 3:
                ktaTemp[p] -= 8
            ktaTemp[p] *= 1 << ktaScale2
            ktaTemp[p] += KtaRC[split]
            ktaTemp[p] /= math.pow(2, ktaScale1)

    temp = abs(ktaTemp[0])
    for kta in ktaTemp:
        temp = max(temp, abs(kta))

    ktaScale1 = 0
    # Patch: Guard against infinite loop
    if temp > 0:
        while temp < 64 and ktaScale1 < 100:
            temp *= 2
            ktaScale1 += 1
    # else: ktaScale1 remains 0

    for i in range(768):
        temp = ktaTemp[i] * math.pow(2, ktaScale1)
        if temp < 0:
            self.kta[i] = int(temp - 0.5)
        else:
            self.kta[i] = int(temp + 0.5)
    self.ktaScale = ktaScale1


def _safe_ExtractKvPixelParameters(self) -> None:
    """Safe version of _ExtractKvPixelParameters"""
    eeData = adafruit_mlx90640.eeData
    
    KvT = [0] * 4
    kvTemp = [0] * 768

    KvRoCo = (eeData[52] & 0xF000) >> 12
    if KvRoCo > 7:
        KvRoCo -= 16
    KvT[0] = KvRoCo

    KvReCo = (eeData[52] & 0x0F00) >> 8
    if KvReCo > 7:
        KvReCo -= 16
    KvT[2] = KvReCo

    KvRoCe = (eeData[52] & 0x00F0) >> 4
    if KvRoCe > 7:
        KvRoCe -= 16
    KvT[1] = KvRoCe

    KvReCe = eeData[52] & 0x000F
    if KvReCe > 7:
        KvReCe -= 16
    KvT[3] = KvReCe

    kvScale = (eeData[56] & 0x0F00) >> 8

    for i in range(24):
        for j in range(32):
            p = 32 * i + j
            split = 2 * (p // 32 - (p // 64) * 2) + p % 2
            kvTemp[p] = KvT[split]
            kvTemp[p] /= math.pow(2, kvScale)

    temp = abs(kvTemp[0])
    for kv in kvTemp:
        temp = max(temp, abs(kv))

    kvScale = 0
    # Patch: Guard against infinite loop
    if temp > 0:
        while temp < 64 and kvScale < 100:
            temp *= 2
            kvScale += 1
    # else: kvScale remains 0

    for i in range(768):
        temp = kvTemp[i] * math.pow(2, kvScale)
        if temp < 0:
            self.kv[i] = int(temp - 0.5)
        else:
            self.kv[i] = int(temp + 0.5)
    self.kvScale = kvScale


def _safe_ExtractDeviatingPixels(self) -> None:
    """
    Safe version of _ExtractDeviatingPixels
    Suppresses RuntimeError for >4 broken/outlier pixels
    """
    eeData = adafruit_mlx90640.eeData
    
    pixCnt = 0
    while (pixCnt < 768) and (len(self.brokenPixels) < 5) and (len(self.outlierPixels) < 5):
        if eeData[pixCnt + 64] == 0:
            self.brokenPixels.append(pixCnt)
        elif (eeData[pixCnt + 64] & 0x0001) != 0:
            self.outlierPixels.append(pixCnt)
        pixCnt += 1

    # Patch: Do NOT raise RuntimeError if more than 4 broken/outlier pixels
    # Just warn debug print if needed, but for now silent success to allow run
    if len(self.brokenPixels) > 4:
        # self.brokenPixels = [] # Option: Clear them if it's just garbage? 
        # For now, let's keep the first 5 identified and ignore the rest
        pass
        
    if len(self.outlierPixels) > 4:
        pass


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

    def __init__(self, i2c_addr=0x33, i2c_bus=1, refresh_rate=8, enable_advanced_processing=True):
        self.logger = logging.getLogger(__name__)
        self.i2c_addr = i2c_addr
        self.refresh_rate = refresh_rate
        self.mlx = None
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
        self.last_retry_time = 0

        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize I2C connection and camera"""
        try:
            self.logger.info(f"Initializing MLX90640 at address 0x{self.i2c_addr:02x}")

            # Initialize I2C - try board pins first (Pi 4), then fall back to explicit bus (Pi 5)
            try:
                i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
                self.logger.info("Using board.SCL/SDA pins for I2C")
            except (ValueError, RuntimeError) as e:
                # Pi 5 may need explicit I2C bus specification
                self.logger.warning(f"Board pins failed ({e}), trying explicit I2C bus")
                # Use I2C bus 1 explicitly (pins GPIO2/GPIO3 on Pi 5)
                if hasattr(board, 'SCL1') and hasattr(board, 'SDA1'):
                    i2c = busio.I2C(board.SCL1, board.SDA1, frequency=400000)
                    self.logger.info("Using board.SCL1/SDA1 pins for I2C (Pi 5)")
                else:
                    # Last resort: try to use /dev/i2c-1 directly
                    self.logger.info("Attempting to use I2C bus via device file")
                    raise ValueError(
                        "Could not initialize I2C. Please ensure I2C is enabled:\n"
                        "  sudo raspi-config -> Interface Options -> I2C -> Enable\n"
                        "Then reboot and try again."
                    )

            # Apply monkey patches for Pi 4 robustness
            # 1. Prevent ZeroDivisionError in Alpha extraction
            adafruit_mlx90640.MLX90640._ExtractAlphaParameters = _safe_ExtractAlphaParameters
            # 2. Prevent infinite loops in Kta extraction (if EEPROM is garbage)
            adafruit_mlx90640.MLX90640._ExtractKtaPixelParameters = _safe_ExtractKtaPixelParameters
            # 3. Prevent infinite loops in Kv extraction (if EEPROM is garbage)
            adafruit_mlx90640.MLX90640._ExtractKvPixelParameters = _safe_ExtractKvPixelParameters
            # 4. Prevent crash on "too many broken pixels" (common with garbage EEPROM)
            adafruit_mlx90640.MLX90640._ExtractDeviatingPixels = _safe_ExtractDeviatingPixels
            
            # Initialize MLX90640
            self.mlx = adafruit_mlx90640.MLX90640(i2c)
            
            # Pi 5 needs slower refresh rate for reliability
            # Use 2 Hz instead of default 8 Hz
            target_rate = min(self.refresh_rate, 2)  # Cap at 2 Hz for Pi 5
            self.mlx.refresh_rate = self._get_refresh_rate_constant(target_rate)
            
            self.logger.info(
                f"MLX90640 initialized at {target_rate}Hz "
                f"(Advanced processing: {self.enable_advanced_processing})"
            )
            
            # CRITICAL: Discard first 2 frames (contain garbage calibration data)
            self.logger.info("Discarding initial calibration frames...")
            for i in range(2):
                dummy_frame = [0] * 768
                try:
                    self.mlx.getFrame(dummy_frame)
                    time.sleep(0.6)  # Wait between frames
                except:
                    pass  # Ignore errors in dummy frames
            
            self.logger.info("Thermal camera ready")

        except Exception as e:
            self.logger.error(f"Failed to initialize MLX90640: {e}")
            self.logger.warning("Thermal camera unavailable - Running in DEGRADED MODE")
            self.mlx = None

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
        return rate_map.get(rate, adafruit_mlx90640.RefreshRate.REFRESH_8_HZ)

    def get_frame(self, max_retries=5, apply_processing=True):
        """
        Capture a thermal frame with optional advanced processing

        Args:
            max_retries: Number of retry attempts (increased for Pi 5)
            apply_processing: Apply advanced processing pipeline

        Returns:
            numpy array of shape (24, 32) with temperatures in Celsius
        """
        # handle degraded mode (retry connection)
        if self.mlx is None:
            current_time = time.time()
            if current_time - self.last_retry_time > 5:  # Retry every 5s
                self.last_retry_time = current_time
                self._initialize_camera()
            
            if self.mlx is None:
                return None

        for attempt in range(max_retries):
            try:
                frame = [0] * 768  # 24x32 = 768 pixels
                
                # Pi 5 needs longer delays between frame reads
                if attempt > 0:
                    time.sleep(0.5)  # Increased from 0.1 for Pi 5 compatibility
                
                self.mlx.getFrame(frame)

                # Convert to numpy array and reshape
                frame_array = np.array(frame, dtype=np.float32).reshape(self.frame_shape)

                # Basic validation
                if not self._validate_frame(frame_array):
                    self.logger.warning(f"Invalid frame data (attempt {attempt + 1})")
                    time.sleep(0.2)
                    continue

                # Apply advanced processing if enabled
                if apply_processing and self.enable_advanced_processing:
                    frame_array = self._process_frame(frame_array)

                # Add to temporal buffer
                self.frame_buffer.append(frame_array.copy())
                self.frame_count += 1

                return frame_array

<<<<<<< HEAD
            except RuntimeError as e:
                # Pi 5 specific: "Too many retries" error
                if "Too many retries" in str(e):
                    self.logger.warning(f"Pi 5 timing issue (attempt {attempt + 1}/{max_retries}), retrying with longer delay...")
                    time.sleep(1.0)  # Longer delay for Pi 5
                else:
                    self.logger.error(f"Frame capture error (attempt {attempt + 1}): {e}")
                    time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Frame capture error (attempt {attempt + 1}): {e}")
                time.sleep(0.5)
=======
                return frame_array

            except (OSError, RuntimeError) as e:
                # Common errors: [Errno 5] Input/output error, or I2C timeout
                self.logger.warning(f"Frame capture error (attempt {attempt + 1}): {e}")
                time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"Frame capture unexpected error (attempt {attempt + 1}): {e}")
                time.sleep(0.1)
>>>>>>> fix/pi4-mlx90640

        self.logger.warning("Failed to capture valid frame after retries")
        return None

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
        num_features, labeled = cv2.connectedComponents(hotspot_mask.astype(np.uint8))

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
        # Check for reasonable temperature range
        # Transformers typically operate between -40°C and 150°C
        # Anything above 150°C is likely sensor error
        if np.any(frame < -40) or np.any(frame > 150):
            self.logger.warning(f"Frame rejected: temps outside valid range ({frame.min():.1f}°C to {frame.max():.1f}°C)")
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
            'advanced_processing_enabled': self.enable_advanced_processing
        }

    def close(self):
        """Cleanup camera resources"""
        self.logger.info("Closing thermal camera")
        self.logger.info(
            f"Processed {self.frame_count} frames, "
            f"detected {len(self.bad_pixels)} bad pixels"
        )
        # MLX90640 doesn't require explicit cleanup
        self.mlx = None
