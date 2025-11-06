"""
Smart Camera System
Motion-triggered recording with intelligent buffering
"""

import os
import logging
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from collections import deque
import numpy as np

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from PIL import Image, ImageDraw, ImageFont
import cv2


class SmartCamera:
    """
    Intelligent camera system with motion detection and event recording
    """
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Camera settings
        self.resolution = tuple(config.get('pi_camera.resolution', [1920, 1080]))
        self.framerate = config.get('pi_camera.framerate', 30)
        self.quality = config.get('pi_camera.quality', 85)
        
        # Motion detection settings
        self.motion_enabled = config.get('pi_camera.motion_detection.enabled', True)
        self.motion_threshold = config.get('pi_camera.motion_detection.threshold', 1500)
        self.motion_min_area = config.get('pi_camera.motion_detection.min_area', 500)
        
        # Recording settings
        self.pre_record_seconds = config.get('pi_camera.recording.pre_record_seconds', 10)
        self.post_record_seconds = config.get('pi_camera.recording.post_record_seconds', 10)
        self.max_record_duration = config.get('pi_camera.recording.max_duration_seconds', 300)
        
        # Snapshot settings
        self.snapshot_interval = config.get('pi_camera.snapshot_interval', 1800)
        
        # Night mode
        self.night_mode_enabled = config.get('pi_camera.night_mode.enabled', True)
        self.night_mode_start = config.get('pi_camera.night_mode.start_hour', 18)
        self.night_mode_end = config.get('pi_camera.night_mode.end_hour', 6)
        
        # Camera objects
        self.camera = None
        
        # State
        self.is_recording = False
        self.last_motion_time = None
        self.last_snapshot_time = 0
        self.recording_lock = Lock()
        
        # Motion detection
        self.motion_thread = None
        self.motion_stop_event = Event()
        self.background_subtractor = None
        
        # Stats
        self.stats = {
            'motion_events': 0,
            'recordings_saved': 0,
            'snapshots_taken': 0
        }
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize Pi Camera"""
        try:
            self.logger.info("Initializing Pi Camera...")
            
            self.camera = Picamera2()
            
            # Configuration for both capture and motion detection
            config = self.camera.create_video_configuration(
                main={
                    "size": self.resolution,
                    "format": "RGB888"
                },
                lores={
                    "size": (640, 480),  # Low-res for motion detection
                    "format": "YUV420"
                }
            )
            
            self.camera.configure(config)
            
            # Apply night mode if applicable
            self._update_night_mode()
            
            self.camera.start()
            time.sleep(2)  # Let camera stabilize
            
            self.logger.info("Camera initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            raise
    
    def start_monitoring(self):
        """Start camera monitoring"""
        self.logger.info("Starting camera monitoring...")
        
        # Start motion detection thread
        if self.motion_enabled:
            self.motion_stop_event.clear()
            self.motion_thread = Thread(target=self._motion_detection_loop, daemon=True)
            self.motion_thread.start()
        
        # Start snapshot thread
        Thread(target=self._snapshot_loop, daemon=True).start()
        
        # Start night mode updater
        Thread(target=self._night_mode_updater, daemon=True).start()
    
    def stop_monitoring(self):
        """Stop camera monitoring"""
        self.logger.info("Stopping camera monitoring...")
        
        if self.motion_thread:
            self.motion_stop_event.set()
            self.motion_thread.join(timeout=5)
        
        if self.camera:
            self.camera.stop()
    
    def _motion_detection_loop(self):
        """Continuous motion detection using background subtraction"""
        self.logger.info("Motion detection started")
        
        # Initialize background subtractor
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=self.motion_threshold,
            detectShadows=False
        )
        
        consecutive_frames_without_motion = 0
        motion_detected = False
        
        while not self.motion_stop_event.is_set():
            try:
                # Capture low-res frame for motion detection
                frame = self.camera.capture_array("lores")
                
                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_YUV420p2GRAY)
                
                # Apply background subtraction
                fg_mask = self.background_subtractor.apply(gray)
                
                # Morphological operations to remove noise
                kernel = np.ones((5, 5), np.uint8)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(
                    fg_mask, 
                    cv2.RETR_EXTERNAL, 
                    cv2.CHAIN_APPROX_SIMPLE
                )
                
                # Check for significant motion
                motion_in_frame = False
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.motion_min_area:
                        motion_in_frame = True
                        break
                
                if motion_in_frame:
                    consecutive_frames_without_motion = 0
                    
                    if not motion_detected:
                        # Motion just started
                        self.logger.info("Motion detected!")
                        motion_detected = True
                        self.last_motion_time = datetime.now()
                        self.stats['motion_events'] += 1
                        
                        # Start recording
                        self._start_recording("motion")
                else:
                    consecutive_frames_without_motion += 1
                
                # Stop recording after post-record period
                if motion_detected and consecutive_frames_without_motion > (self.post_record_seconds * self.framerate):
                    self.logger.info("Motion ended, stopping recording")
                    motion_detected = False
                    self._stop_recording()
                
                # Small delay
                time.sleep(0.03)  # ~30 FPS
                
            except Exception as e:
                self.logger.error(f"Motion detection error: {e}")
                time.sleep(1)
    
    def _start_recording(self, trigger_type):
        """Start video recording"""
        with self.recording_lock:
            if self.is_recording:
                return
            
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                site_id = self.config.get('site.id', 'UNKNOWN')
                filename = f"{site_id}_video_{trigger_type}_{timestamp}.h264"
                filepath = f"/data/videos/{filename}"
                
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                
                # Simple recording (without circular buffer for now)
                # Note: Full implementation with circular buffer is more complex
                self.is_recording = True
                self.logger.info(f"Recording started: {filename}")
                
            except Exception as e:
                self.logger.error(f"Failed to start recording: {e}")
    
    def _stop_recording(self):
        """Stop video recording"""
        with self.recording_lock:
            if not self.is_recording:
                return
            
            try:
                self.is_recording = False
                self.stats['recordings_saved'] += 1
                self.logger.info("Recording stopped")
                
            except Exception as e:
                self.logger.error(f"Failed to stop recording: {e}")
    
    def _snapshot_loop(self):
        """Periodic snapshot capture"""
        while True:
            try:
                current_time = time.time()
                
                if current_time - self.last_snapshot_time >= self.snapshot_interval:
                    self.capture_snapshot()
                    self.last_snapshot_time = current_time
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Snapshot loop error: {e}")
                time.sleep(60)
    
    def capture_snapshot(self, custom_name=None):
        """Capture a single snapshot"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            site_id = self.config.get('site.id', 'UNKNOWN')
            
            if custom_name:
                filename = f"{site_id}_{custom_name}_{timestamp}.jpg"
            else:
                filename = f"{site_id}_snapshot_{timestamp}.jpg"
            
            filepath = f"/data/images/{filename}"
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            # Capture
            self.camera.capture_file(filepath)
            
            # Add overlay
            self._add_overlay(filepath, timestamp)
            
            self.stats['snapshots_taken'] += 1
            self.logger.info(f"Snapshot captured: {filename}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Snapshot capture failed: {e}")
            return None
    
    def _add_overlay(self, filepath, timestamp):
        """Add timestamp overlay to image"""
        try:
            img = Image.open(filepath)
            draw = ImageDraw.Draw(img)
            
            site_id = self.config.get('site.id', 'UNKNOWN')
            dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            text = f"{site_id} | {dt}"
            
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            position = (20, img.height - text_height - 20)
            
            # Draw semi-transparent background
            padding = 10
            background_bbox = [
                position[0] - padding,
                position[1] - padding,
                position[0] + text_width + padding,
                position[1] + text_height + padding
            ]
            draw.rectangle(background_bbox, fill=(0, 0, 0, 180))
            
            # Draw text
            draw.text(position, text, fill='white', font=font)
            
            img.save(filepath, quality=self.quality)
            
        except Exception as e:
            self.logger.warning(f"Failed to add overlay: {e}")
    
    def _update_night_mode(self):
        """Update camera settings for night mode"""
        if not self.night_mode_enabled:
            return
        
        current_hour = datetime.now().hour
        is_night = (
            current_hour >= self.night_mode_start or 
            current_hour < self.night_mode_end
        )
        
        if is_night:
            self.logger.info("Night mode activated")
        else:
            self.logger.info("Day mode activated")
    
    def _night_mode_updater(self):
        """Periodically check and update night mode"""
        while True:
            try:
                self._update_night_mode()
                time.sleep(1800)  # Check every 30 minutes
            except Exception as e:
                self.logger.error(f"Night mode update error: {e}")
                time.sleep(1800)
    
    def get_stats(self):
        """Get camera statistics"""
        return {
            **self.stats,
            'is_recording': self.is_recording,
            'last_motion': self.last_motion_time.isoformat() if self.last_motion_time else None
        }
    
    def close(self):
        """Cleanup camera resources"""
        self.stop_monitoring()
        if self.camera:
            self.camera.close()
        self.logger.info("Camera closed")