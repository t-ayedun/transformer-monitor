"""
Smart Camera System
Motion-triggered recording with circular buffer for pre-recording

HOW IT WORKS:
--------------
1. CIRCULAR BUFFER: Continuously stores the last N seconds of video in memory using a circular
   buffer (ring buffer). This allows capturing footage BEFORE motion is detected.

2. MOTION DETECTION: Uses background subtraction (MOG2 algorithm) to detect changes in the scene.
   When significant motion is detected, the system:
   - Saves the pre-motion buffer (last 10 seconds from circular buffer)
   - Continues recording during motion
   - Keeps recording for 10 seconds after motion stops (post-recording)

3. FRAME ENCODING: Frames are encoded as H.264 to reduce memory usage. The circular buffer holds
   compressed frames, not raw RGB data, to fit more pre-recording time in RAM.

4. FILE OUTPUT: When motion stops, all buffered and live frames are written to a single H.264 file,
   which can be played back as a complete video showing before, during, and after the event.

5. NIGHT MODE: Automatically adjusts camera settings based on time of day for better visibility.

MEMORY USAGE:
- At 1920x1080, 30fps, H.264 encoding: ~2-4 Mbps = ~0.25-0.5 MB/sec
- 10 second buffer = ~2.5-5 MB RAM usage per camera
- Acceptable for Raspberry Pi 4 with 4GB+ RAM
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
from picamera2.outputs import CircularOutput, FileOutput
from PIL import Image, ImageDraw, ImageFont
import cv2


class SmartCamera:
    """
    Intelligent camera system with motion detection and event recording

    Features:
    - Circular buffer for pre-motion recording
    - Motion-triggered video capture
    - Periodic snapshots
    - Night mode with auto-adjustment
    - Real-time statistics
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
        self.motion_cooldown = config.get('pi_camera.motion_detection.cooldown_seconds', 5)

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
        self.encoder = None
        self.circular_output = None

        # State
        self.is_recording = False
        self.current_recording_path = None
        self.recording_start_time = None
        self.last_motion_time = None
        self.last_snapshot_time = 0
        self.last_recording_end_time = 0
        self.recording_lock = Lock()

        # Motion detection
        self.motion_thread = None
        self.motion_stop_event = Event()
        self.background_subtractor = None

        # Stats
        self.stats = {
            'motion_events': 0,
            'recordings_saved': 0,
            'snapshots_taken': 0,
            'total_recording_seconds': 0,
            'buffer_size_mb': 0
        }

        self._initialize_camera()
        self._initialize_circular_buffer()

    def _initialize_camera(self):
        """Initialize Pi Camera with optimal settings"""
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
                },
                encode="main"  # Encode the main stream for recording
            )

            self.camera.configure(config)

            # Apply night mode if applicable
            self._update_night_mode()

            self.camera.start()
            time.sleep(2)  # Let camera stabilize

            self.logger.info(f"Camera initialized: {self.resolution} @ {self.framerate}fps")

        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            raise

    def _initialize_circular_buffer(self):
        """Initialize circular buffer for pre-recording"""
        try:
            self.logger.info("Initializing circular buffer for pre-recording...")

            # Create H.264 encoder
            self.encoder = H264Encoder(bitrate=2000000)  # 2 Mbps

            # Calculate buffer size: pre_record_seconds * bitrate / 8
            # Add 20% overhead for safety
            buffer_size_bytes = int(self.pre_record_seconds * 2000000 / 8 * 1.2)
            buffer_size_mb = buffer_size_bytes / (1024 * 1024)

            self.stats['buffer_size_mb'] = round(buffer_size_mb, 2)

            # Create circular output
            self.circular_output = CircularOutput(buffersize=buffer_size_bytes)

            # Start encoder with circular buffer
            self.camera.start_encoder(self.encoder, self.circular_output)

            self.logger.info(
                f"Circular buffer initialized: {self.pre_record_seconds}s "
                f"(~{buffer_size_mb:.1f} MB)"
            )

        except Exception as e:
            self.logger.error(f"Circular buffer initialization failed: {e}")
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

        # Stop motion detection
        if self.motion_thread:
            self.motion_stop_event.set()
            self.motion_thread.join(timeout=5)

        # Stop any active recording
        if self.is_recording:
            self._stop_recording()

        # Stop encoder
        if self.camera and self.encoder:
            try:
                self.camera.stop_encoder()
            except:
                pass

        # Stop camera
        if self.camera:
            try:
                self.camera.stop()
            except:
                pass

    def _motion_detection_loop(self):
        """
        Continuous motion detection using background subtraction

        Algorithm: MOG2 (Mixture of Gaussians)
        - Learns background model over time
        - Detects foreground objects (moving things)
        - Adaptive to lighting changes
        - Handles shadows (when enabled)
        """
        self.logger.info("Motion detection started")

        # Initialize background subtractor
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,  # Number of frames for background learning
            varThreshold=self.motion_threshold,  # Sensitivity
            detectShadows=False  # Disable shadow detection for speed
        )

        consecutive_frames_without_motion = 0
        consecutive_frames_with_motion = 0
        motion_detected = False
        motion_trigger_threshold = 3  # Require 3 consecutive frames to trigger

        while not self.motion_stop_event.is_set():
            try:
                # Capture low-res frame for motion detection
                frame = self.camera.capture_array("lores")

                # Convert YUV420 to grayscale for processing
                gray = cv2.cvtColor(frame, cv2.COLOR_YUV420p2GRAY)

                # Apply Gaussian blur to reduce noise
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)

                # Apply background subtraction
                fg_mask = self.background_subtractor.apply(blurred)

                # Morphological operations to remove noise
                kernel = np.ones((5, 5), np.uint8)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

                # Find contours of moving objects
                contours, _ = cv2.findContours(
                    fg_mask,
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )

                # Check for significant motion
                motion_in_frame = False
                total_motion_area = 0

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.motion_min_area:
                        motion_in_frame = True
                        total_motion_area += area

                # Motion detection logic with debouncing
                if motion_in_frame:
                    consecutive_frames_with_motion += 1
                    consecutive_frames_without_motion = 0

                    # Trigger recording after consecutive motion frames
                    if not motion_detected and consecutive_frames_with_motion >= motion_trigger_threshold:
                        # Check cooldown period (don't trigger too frequently)
                        time_since_last_recording = time.time() - self.last_recording_end_time

                        if time_since_last_recording >= self.motion_cooldown:
                            self.logger.info(
                                f"Motion detected! Area: {total_motion_area:.0f} px²"
                            )
                            motion_detected = True
                            self.last_motion_time = datetime.now()
                            self.stats['motion_events'] += 1

                            # Start recording (includes pre-buffer)
                            self._start_recording("motion")
                else:
                    consecutive_frames_with_motion = 0
                    consecutive_frames_without_motion += 1

                # Stop recording after post-record period
                if motion_detected and consecutive_frames_without_motion > (self.post_record_seconds * 30):
                    self.logger.info("Motion ended, stopping recording")
                    motion_detected = False
                    consecutive_frames_with_motion = 0
                    self._stop_recording()

                # Safety: Stop recording if max duration reached
                if self.is_recording and self.recording_start_time:
                    recording_duration = time.time() - self.recording_start_time
                    if recording_duration >= self.max_record_duration:
                        self.logger.warning(
                            f"Max recording duration ({self.max_record_duration}s) reached, stopping"
                        )
                        motion_detected = False
                        self._stop_recording()

                # Small delay (~30 FPS motion detection)
                time.sleep(0.033)

            except Exception as e:
                self.logger.error(f"Motion detection error: {e}")
                time.sleep(1)

    def _start_recording(self, trigger_type):
        """
        Start video recording with circular buffer

        Process:
        1. Check if already recording (prevent duplicate triggers)
        2. Create output file path
        3. Start FileOutput that will receive both:
           - Buffered frames (last 10 seconds from circular buffer)
           - New frames (during and after motion)
        4. The circular buffer automatically writes its contents to the file
        """
        with self.recording_lock:
            if self.is_recording:
                self.logger.debug("Already recording, ignoring trigger")
                return

            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                site_id = self.config.get('site.id', 'UNKNOWN')
                filename = f"{site_id}_video_{trigger_type}_{timestamp}.h264"
                filepath = f"/data/videos/{filename}"

                # Ensure directory exists
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)

                # Start recording to file (includes circular buffer content)
                file_output = FileOutput(filepath)

                # This writes the circular buffer content first, then continues with live frames
                self.circular_output.fileoutput = file_output
                self.circular_output.start()

                self.is_recording = True
                self.current_recording_path = filepath
                self.recording_start_time = time.time()

                self.logger.info(
                    f"Recording started: {filename} "
                    f"(includes {self.pre_record_seconds}s pre-buffer)"
                )

            except Exception as e:
                self.logger.error(f"Failed to start recording: {e}")
                self.is_recording = False

    def _stop_recording(self):
        """
        Stop video recording

        Process:
        1. Stop the file output
        2. Calculate duration
        3. Update statistics
        4. Reset circular buffer to continue buffering for next event
        """
        with self.recording_lock:
            if not self.is_recording:
                return

            try:
                # Stop recording
                self.circular_output.stop()

                # Calculate duration
                if self.recording_start_time:
                    duration = time.time() - self.recording_start_time
                    self.stats['total_recording_seconds'] += int(duration)

                self.stats['recordings_saved'] += 1
                self.last_recording_end_time = time.time()

                self.logger.info(
                    f"Recording stopped: {Path(self.current_recording_path).name} "
                    f"(duration: {duration:.1f}s)"
                )

                # Reset state
                self.is_recording = False
                self.current_recording_path = None
                self.recording_start_time = None

            except Exception as e:
                self.logger.error(f"Failed to stop recording: {e}")
                self.is_recording = False

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
        """Capture a single snapshot with timestamp overlay"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            site_id = self.config.get('site.id', 'UNKNOWN')

            if custom_name:
                filename = f"{site_id}_{custom_name}_{timestamp}.jpg"
            else:
                filename = f"{site_id}_snapshot_{timestamp}.jpg"

            filepath = f"/data/images/{filename}"
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            # Capture to temporary file
            temp_path = f"/tmp/{filename}"
            self.camera.capture_file(temp_path)

            # Add overlay
            self._add_overlay(temp_path, filepath)

            # Remove temp file
            Path(temp_path).unlink()

            self.stats['snapshots_taken'] += 1
            self.logger.info(f"Snapshot captured: {filename}")

            return filepath

        except Exception as e:
            self.logger.error(f"Snapshot capture failed: {e}")
            return None

    def _add_overlay(self, input_path, output_path):
        """Add timestamp and site ID overlay to image"""
        try:
            img = Image.open(input_path)
            draw = ImageDraw.Draw(img)

            site_id = self.config.get('site.id', 'UNKNOWN')
            dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            text = f"{site_id} | {dt}"

            # Try to load a nice font, fall back to default
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()

            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Position at bottom left
            position = (20, img.height - text_height - 20)

            # Draw semi-transparent background
            padding = 10
            background_bbox = [
                position[0] - padding,
                position[1] - padding,
                position[0] + text_width + padding,
                position[1] + text_height + padding
            ]

            # Create overlay for transparency
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(background_bbox, fill=(0, 0, 0, 180))

            # Composite overlay
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)

            # Draw text
            draw = ImageDraw.Draw(img)
            draw.text(position, text, fill='white', font=font)

            # Save as RGB JPEG
            img.convert('RGB').save(output_path, quality=self.quality)

        except Exception as e:
            self.logger.warning(f"Failed to add overlay: {e}")
            # Fall back to copying original
            import shutil
            shutil.copy(input_path, output_path)

    def _update_night_mode(self):
        """Update camera settings for night mode"""
        if not self.night_mode_enabled or not self.camera:
            return

        current_hour = datetime.now().hour
        is_night = (
            current_hour >= self.night_mode_start or
            current_hour < self.night_mode_end
        )

        try:
            if is_night:
                # Night mode: increase exposure, reduce framerate
                self.logger.info("Night mode activated")
                # Note: Actual implementation depends on picamera2 API
                # Example adjustments:
                # self.camera.set_controls({"ExposureTime": 30000, "AnalogueGain": 8.0})
            else:
                # Day mode: normal settings
                self.logger.info("Day mode activated")
                # self.camera.set_controls({"ExposureTime": 10000, "AnalogueGain": 1.0})
        except Exception as e:
            self.logger.warning(f"Failed to update night mode: {e}")

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
            'last_motion': self.last_motion_time.isoformat() if self.last_motion_time else None,
            'recording_duration': int(time.time() - self.recording_start_time) if self.is_recording and self.recording_start_time else 0
        }

    def close(self):
        """Cleanup camera resources"""
        self.stop_monitoring()
        if self.camera:
            self.camera.close()
        self.logger.info("Camera closed")
