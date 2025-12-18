"""
Thermal Image Generator
Generates high-quality thermal images from MLX90640 data with proper colormaps
"""

import numpy as np
import cv2
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional


class ThermalImageGenerator:
    """
    Generate thermal images with proper color mapping and annotations
    
    Features:
    - Multiple colormap options (hot, jet, inferno)
    - Temperature scale legend
    - ROI boundary visualization
    - Hotspot highlighting with labels
    - Upscaling for better visibility
    """
    
    def __init__(self, colormap: str = 'hot', output_resolution: Tuple[int, int] = (640, 480)):
        """
        Initialize thermal image generator
        
        Args:
            colormap: OpenCV colormap name ('hot', 'jet', 'inferno', 'turbo')
            output_resolution: Target resolution (width, height)
        """
        self.logger = logging.getLogger(__name__)
        self.output_resolution = output_resolution
        
        # Map colormap names to OpenCV constants
        self.colormap_map = {
            'hot': cv2.COLORMAP_HOT,
            'jet': cv2.COLORMAP_JET,
            'inferno': cv2.COLORMAP_INFERNO,
            'turbo': cv2.COLORMAP_TURBO,
            'rainbow': cv2.COLORMAP_RAINBOW,
            'viridis': cv2.COLORMAP_VIRIDIS
        }
        
        self.colormap = self.colormap_map.get(colormap.lower(), cv2.COLORMAP_HOT)
        self.colormap_name = colormap.lower()
        
        self.logger.info(f"Thermal image generator initialized: {colormap} colormap, {output_resolution} resolution")
    
    def generate_image(self, 
                      thermal_frame: np.ndarray,
                      rois: Optional[List[Dict]] = None,
                      hotspots: Optional[List[Dict]] = None,
                      metadata: Optional[Dict] = None,
                      add_scale: bool = True) -> np.ndarray:
        """
        Generate thermal image with all annotations
        
        Args:
            thermal_frame: Raw thermal data (24x32)
            rois: List of ROI dictionaries with coordinates and names
            hotspots: List of hotspot dictionaries with center and temperature
            metadata: Additional metadata (site_id, timestamp, etc.)
            add_scale: Whether to add temperature scale legend
            
        Returns:
            RGB image as numpy array
        """
        # Normalize and apply colormap
        thermal_img = self._apply_colormap(thermal_frame)
        
        # Upscale to target resolution
        thermal_img = self._upscale(thermal_img)
        
        # Add ROI boundaries
        if rois:
            thermal_img = self._draw_rois(thermal_img, rois, thermal_frame.shape)
        
        # Add hotspot markers
        if hotspots:
            thermal_img = self._draw_hotspots(thermal_img, hotspots, thermal_frame.shape)
        
        # Add temperature scale
        if add_scale:
            thermal_img = self._add_temperature_scale(thermal_img, thermal_frame)
        
        # Add metadata overlay
        if metadata:
            thermal_img = self._add_metadata_overlay(thermal_img, metadata)
        
        return thermal_img
    
    def _apply_colormap(self, thermal_frame: np.ndarray) -> np.ndarray:
        """
        Apply colormap to thermal data
        
        Normalizes temperature data to 0-255 range and applies colormap
        """
        # Get temperature range
        temp_min = np.min(thermal_frame)
        temp_max = np.max(thermal_frame)
        
        # Normalize to 0-255
        if temp_max > temp_min:
            normalized = ((thermal_frame - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(thermal_frame, dtype=np.uint8)
        
        # Apply colormap
        colored = cv2.applyColorMap(normalized, self.colormap)
        
        return colored
    
    def _upscale(self, image: np.ndarray) -> np.ndarray:
        """Upscale image to target resolution using bicubic interpolation"""
        return cv2.resize(image, self.output_resolution, interpolation=cv2.INTER_CUBIC)
    
    def _draw_rois(self, image: np.ndarray, rois: List[Dict], original_shape: Tuple) -> np.ndarray:
        """
        Draw ROI boundaries on image
        
        Args:
            image: RGB image
            rois: List of ROI configs with coordinates
            original_shape: Original thermal frame shape (24, 32)
        """
        # Calculate scaling factors
        scale_y = self.output_resolution[1] / original_shape[0]
        scale_x = self.output_resolution[0] / original_shape[1]
        
        for roi in rois:
            if not roi.get('enabled', True):
                continue
            
            coords = roi.get('coordinates', [])
            if len(coords) < 2:
                continue
            
            # Scale coordinates
            x_min, y_min = coords[0]
            x_max, y_max = coords[1]
            
            pt1 = (int(x_min * scale_x), int(y_min * scale_y))
            pt2 = (int(x_max * scale_x), int(y_max * scale_y))
            
            # Draw rectangle
            color = (0, 255, 0)  # Green
            thickness = 2
            cv2.rectangle(image, pt1, pt2, color, thickness)
            
            # Add ROI name label
            name = roi.get('name', 'ROI')
            label_pos = (pt1[0] + 5, pt1[1] + 20)
            cv2.putText(image, name, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, 1, cv2.LINE_AA)
        
        return image
    
    def _draw_hotspots(self, image: np.ndarray, hotspots: List[Dict], original_shape: Tuple) -> np.ndarray:
        """
        Draw hotspot markers with temperature labels
        
        Args:
            image: RGB image
            hotspots: List of hotspot dicts with center and max_temp
            original_shape: Original thermal frame shape
        """
        scale_y = self.output_resolution[1] / original_shape[0]
        scale_x = self.output_resolution[0] / original_shape[1]
        
        for hotspot in hotspots:
            center = hotspot.get('center', (0, 0))
            max_temp = hotspot.get('max_temp', 0)
            
            # Scale center coordinates
            center_scaled = (int(center[0] * scale_x), int(center[1] * scale_y))
            
            # Draw crosshair
            color = (255, 0, 255)  # Magenta
            size = 10
            thickness = 2
            
            # Horizontal line
            cv2.line(image, 
                    (center_scaled[0] - size, center_scaled[1]),
                    (center_scaled[0] + size, center_scaled[1]),
                    color, thickness)
            
            # Vertical line
            cv2.line(image,
                    (center_scaled[0], center_scaled[1] - size),
                    (center_scaled[0], center_scaled[1] + size),
                    color, thickness)
            
            # Add temperature label
            label = f"{max_temp:.1f}°C"
            label_pos = (center_scaled[0] + 15, center_scaled[1] - 10)
            
            # Add background for better readability
            (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image,
                         (label_pos[0] - 2, label_pos[1] - text_height - 2),
                         (label_pos[0] + text_width + 2, label_pos[1] + 2),
                         (0, 0, 0), -1)
            
            cv2.putText(image, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, color, 1, cv2.LINE_AA)
        
        return image
    
    def _add_temperature_scale(self, image: np.ndarray, thermal_frame: np.ndarray) -> np.ndarray:
        """
        Add temperature scale legend to image
        
        Creates a vertical color bar with temperature labels
        """
        temp_min = np.min(thermal_frame)
        temp_max = np.max(thermal_frame)
        
        # Create scale bar
        scale_width = 30
        scale_height = 200
        scale_margin = 20
        
        # Generate gradient
        gradient = np.linspace(255, 0, scale_height, dtype=np.uint8)
        gradient = np.tile(gradient.reshape(-1, 1), (1, scale_width))
        
        # Apply same colormap
        scale_colored = cv2.applyColorMap(gradient, self.colormap)
        
        # Position in top-right corner
        x_pos = self.output_resolution[0] - scale_width - scale_margin
        y_pos = scale_margin
        
        # Add scale to image
        image[y_pos:y_pos+scale_height, x_pos:x_pos+scale_width] = scale_colored
        
        # Add border
        cv2.rectangle(image, 
                     (x_pos, y_pos), 
                     (x_pos + scale_width, y_pos + scale_height),
                     (255, 255, 255), 1)
        
        # Add temperature labels
        label_x = x_pos + scale_width + 5
        
        # Max temp (top)
        cv2.putText(image, f"{temp_max:.1f}°C", (label_x, y_pos + 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Min temp (bottom)
        cv2.putText(image, f"{temp_min:.1f}°C", (label_x, y_pos + scale_height - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Mid temp (middle)
        temp_mid = (temp_max + temp_min) / 2
        cv2.putText(image, f"{temp_mid:.1f}°C", (label_x, y_pos + scale_height // 2),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
        return image
    
    def _add_metadata_overlay(self, image: np.ndarray, metadata: Dict) -> np.ndarray:
        """
        Add metadata overlay (site ID, timestamp) to bottom-left corner
        """
        site_id = metadata.get('site_id', 'UNKNOWN')
        timestamp = metadata.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Format timestamp if it's ISO format
        if 'T' in str(timestamp):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        text = f"{site_id} | {timestamp}"
        
        # Position at bottom-left
        margin = 10
        font_scale = 0.5
        thickness = 1
        
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        y_pos = self.output_resolution[1] - margin - baseline
        x_pos = margin
        
        # Add semi-transparent background
        overlay = image.copy()
        cv2.rectangle(overlay,
                     (x_pos - 5, y_pos - text_height - 5),
                     (x_pos + text_width + 5, y_pos + baseline + 5),
                     (0, 0, 0), -1)
        
        # Blend overlay
        alpha = 0.7
        image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)
        
        # Add text
        cv2.putText(image, text, (x_pos, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255),
                   thickness, cv2.LINE_AA)
        
        return image
    
    def save_image(self, image: np.ndarray, filepath: str, quality: int = 95) -> bool:
        """
        Save thermal image to file
        
        Args:
            image: RGB image
            filepath: Output file path
            quality: JPEG quality (0-100)
            
        Returns:
            True if successful
        """
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Save as PNG for lossless quality, or JPEG for smaller size
            if filepath.lower().endswith('.png'):
                cv2.imwrite(filepath, image)
            else:
                cv2.imwrite(filepath, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            
            self.logger.debug(f"Saved thermal image: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save thermal image: {e}")
            return False
    
    def generate_and_save(self,
                         thermal_frame: np.ndarray,
                         output_path: str,
                         rois: Optional[List[Dict]] = None,
                         hotspots: Optional[List[Dict]] = None,
                         metadata: Optional[Dict] = None) -> bool:
        """
        Convenience method to generate and save in one call
        
        Returns:
            True if successful
        """
        image = self.generate_image(thermal_frame, rois, hotspots, metadata)
        return self.save_image(image, output_path)
