"""
ROI Mapper - Visual to Thermal Coordinate Mapping
Uses Pi camera image to help define thermal ROIs
"""

import logging
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
import json


class ROIMapper:
    """Maps visual camera coordinates to thermal camera coordinates"""
    
    def __init__(self, visual_resolution=(1920, 1080), thermal_resolution=(32, 24)):
        self.logger = logging.getLogger(__name__)
        self.visual_res = visual_resolution
        self.thermal_res = thermal_resolution
        
        # Calculate scaling factors
        self.scale_x = thermal_resolution[0] / visual_resolution[0]
        self.scale_y = thermal_resolution[1] / visual_resolution[1]
    
    def visual_to_thermal(self, visual_coords):
        """
        Convert visual camera coordinates to thermal camera coordinates
        
        Args:
            visual_coords: [[x1, y1], [x2, y2]] in visual image pixels
            
        Returns:
            [[x1, y1], [x2, y2]] in thermal frame pixels (0-32, 0-24)
        """
        thermal_coords = []
        
        for x, y in visual_coords:
            thermal_x = int(x * self.scale_x)
            thermal_y = int(y * self.scale_y)
            
            # Clamp to valid thermal range
            thermal_x = max(0, min(self.thermal_res[0] - 1, thermal_x))
            thermal_y = max(0, min(self.thermal_res[1] - 1, thermal_y))
            
            thermal_coords.append([thermal_x, thermal_y])
        
        return thermal_coords
    
    def create_roi_from_clicks(self, click_points, roi_name):
        """
        Create ROI definition from user clicks
        
        Args:
            click_points: List of [x, y] coordinates clicked by user
            roi_name: Name for this ROI
            
        Returns:
            ROI configuration dictionary
        """
        if len(click_points) < 2:
            raise ValueError("Need at least 2 points to define ROI")
        
        # Get bounding box from clicks
        x_coords = [p[0] for p in click_points]
        y_coords = [p[1] for p in click_points]
        
        visual_bbox = [
            [min(x_coords), min(y_coords)],
            [max(x_coords), max(y_coords)]
        ]
        
        # Convert to thermal coordinates
        thermal_bbox = self.visual_to_thermal(visual_bbox)
        
        # Create ROI config
        roi_config = {
            'name': roi_name,
            'enabled': True,
            'coordinates': thermal_bbox,
            'weight': 1.0,
            'emissivity': 0.95,  # Default, user can adjust
            'thresholds': {
                'warning': 75.0,
                'critical': 85.0,
                'emergency': 95.0
            },
            'visual_coordinates': visual_bbox  # Store original for reference
        }
        
        return roi_config
    
    def create_overlay_image(self, visual_image_path, thermal_frame, rois):
        """
        Create visual image with thermal ROIs overlaid
        
        Args:
            visual_image_path: Path to visual image
            thermal_frame: Thermal data array (32x24)
            rois: List of ROI configurations
            
        Returns:
            PIL Image with overlays
        """
        # Load visual image
        visual_img = Image.open(visual_image_path)
        draw = ImageDraw.Draw(visual_img, 'RGBA')
        
        # Define colors for different ROIs
        colors = [
            (255, 0, 0, 128),    # Red
            (0, 255, 0, 128),    # Green
            (0, 0, 255, 128),    # Blue
            (255, 255, 0, 128),  # Yellow
            (255, 0, 255, 128),  # Magenta
        ]
        
        # Draw each ROI
        for idx, roi in enumerate(rois):
            if 'visual_coordinates' not in roi:
                continue
            
            coords = roi['visual_coordinates']
            color = colors[idx % len(colors)]
            
            # Draw rectangle
            draw.rectangle(
                [coords[0], coords[1]],
                outline=color[:3],
                fill=color,
                width=3
            )
            
            # Draw label
            draw.text(
                (coords[0][0], coords[0][1] - 20),
                roi['name'],
                fill=(255, 255, 255, 255)
            )
        
        return visual_img