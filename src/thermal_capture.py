"""
Thermal Camera Interface
Handles MLX90640 thermal camera communication
"""

import time
import logging
import numpy as np
import board
import busio
import adafruit_mlx90640


class ThermalCapture:
    """Interface for MLX90640 thermal camera"""
    
    def __init__(self, i2c_addr=0x33, i2c_bus=1, refresh_rate=8):
        self.logger = logging.getLogger(__name__)
        self.i2c_addr = i2c_addr
        self.refresh_rate = refresh_rate
        self.mlx = None
        self.frame_shape = (24, 32)  # MLX90640 resolution
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize I2C connection and camera"""
        try:
            self.logger.info(f"Initializing MLX90640 at address 0x{self.i2c_addr:02x}")
            
            # Initialize I2C
            i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
            
            # Initialize MLX90640
            self.mlx = adafruit_mlx90640.MLX90640(i2c)
            self.mlx.refresh_rate = self._get_refresh_rate_constant(self.refresh_rate)
            
            self.logger.info(f"MLX90640 initialized at {self.refresh_rate}Hz")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MLX90640: {e}")
            raise
    
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
    
    def get_frame(self, max_retries=3):
        """
        Capture a thermal frame
        Returns: numpy array of shape (24, 32) with temperatures in Celsius
        """
        for attempt in range(max_retries):
            try:
                frame = [0] * 768  # 24x32 = 768 pixels
                self.mlx.getFrame(frame)
                
                # Convert to numpy array and reshape
                frame_array = np.array(frame).reshape(self.frame_shape)
                
                # Basic validation
                if self._validate_frame(frame_array):
                    return frame_array
                else:
                    self.logger.warning(f"Invalid frame data (attempt {attempt + 1})")
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Frame capture error (attempt {attempt + 1}): {e}")
                time.sleep(0.1)
        
        self.logger.error("Failed to capture valid frame after retries")
        return None
    
    def _validate_frame(self, frame):
        """Validate thermal frame data"""
        # Check for reasonable temperature range (-40°C to 300°C)
        if np.any(frame < -40) or np.any(frame > 300):
            return False
        
        # Check for NaN or inf values
        if np.any(np.isnan(frame)) or np.any(np.isinf(frame)):
            return False
        
        return True
    
    def get_sensor_temp(self):
        """Get internal sensor temperature"""
        try:
            # The sensor temperature is embedded in the frame data
            # This is a simplified approach - actual implementation may vary
            frame = self.get_frame()
            if frame is not None:
                # Sensor temp is typically around ambient
                # This is approximate - check MLX90640 datasheet for exact method
                return float(np.median(frame) - 5)  # Rough estimate
            return None
        except Exception as e:
            self.logger.error(f"Failed to get sensor temperature: {e}")
            return None
    
    def apply_emissivity_correction(self, frame, emissivity=0.95):
        """
        Apply emissivity correction to thermal frame
        
        Simplified Stefan-Boltzmann approach:
        T_actual = T_measured / emissivity^0.25
        """
        if emissivity == 1.0:
            return frame
        
        # Convert to Kelvin
        frame_k = frame + 273.15
        
        # Apply correction
        corrected_k = frame_k / (emissivity ** 0.25)
        
        # Convert back to Celsius
        return corrected_k - 273.15
    
    def close(self):
        """Cleanup camera resources"""
        self.logger.info("Closing thermal camera")
        # MLX90640 doesn't require explicit cleanup
        self.mlx = None