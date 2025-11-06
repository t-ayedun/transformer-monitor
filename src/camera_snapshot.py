"""
Camera Snapshot
Handles Raspberry Pi camera captures
"""

import logging
from datetime import datetime
from pathlib import Path
from picamera2 import Picamera2
from PIL import Image, ImageDraw, ImageFont


class CameraSnapshot:
    """Raspberry Pi camera interface"""
    
    def __init__(self, resolution: list, quality: int = 85):
        self.logger = logging.getLogger(__name__)
        self.resolution = tuple(resolution)
        self.quality = quality
        self.camera = None
        
        self._init_camera()
    
    def _init_camera(self):
        """Initialize Pi camera"""
        try:
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(
                main={"size": self.resolution}
            )
            self.camera.configure(config)
            self.camera.start()
            
            self.logger.info(f"Camera initialized at {self.resolution}")
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            self.camera = None
    
    def capture(self, add_timestamp: bool = True) -> str:
        """
        Capture image from Pi camera
        
        Returns: Path to saved image
        """
        if not self.camera:
            self.logger.error("Camera not initialized")
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"snapshot_{timestamp}.jpg"
            filepath = f"/data/images/{filename}"
            
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Capture
            self.camera.capture_file(filepath)
            
            # Add timestamp overlay if requested
            if add_timestamp:
                self._add_timestamp_overlay(filepath)
            
            self.logger.info(f"Captured snapshot: {filename}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Capture failed: {e}")
            return None
    
    def _add_timestamp_overlay(self, filepath: str):
        """Add timestamp overlay to image"""
        try:
            img = Image.open(filepath)
            draw = ImageDraw.Draw(img)
            
            # Timestamp text
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Use default font (or specify path to TTF font)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            # Position at bottom-right
            text_bbox = draw.textbbox((0, 0), timestamp, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            position = (img.width - text_width - 20, img.height - text_height - 20)
            
            # Draw shadow
            draw.text((position[0]+2, position[1]+2), timestamp, fill='black', font=font)
            # Draw text
            draw.text(position, timestamp, fill='white', font=font)
            
            img.save(filepath, quality=self.quality)
            
        except Exception as e:
            self.logger.warning(f"Failed to add timestamp overlay: {e}")
    
    def close(self):
        """Close camera"""
        if self.camera:
            self.camera.stop()
            self.camera.close()
            self.logger.info("Camera closed")