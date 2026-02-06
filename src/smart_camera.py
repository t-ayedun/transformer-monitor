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
import psutil

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import CircularOutput, FileOutput
from PIL import Image, ImageDraw, ImageFont
import cv2

from event_classifier import EventClassifier
from event_logger import EventLogger
from camera_snapshot import CameraSnapshot


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

    def __init__(self, config, aws_publisher=None, media_uploader=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.aws_publisher = aws_publisher
        self.media_uploader = media_uploader

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
        # Reduced default from 300s to 60s to prevent large files
        self.max_record_duration = config.get('pi_camera.recording.max_duration_seconds', 60)
        # Hard limit for file size (50MB)
        self.max_file_size_bytes = 50 * 1024 * 1024

        # Snapshot settings
        self.snapshot_interval = config.get('pi_camera.snapshot_interval', 1800)

        # Night mode
        self.night_mode_enabled = config.get('pi_camera.night_mode.enabled', True)
        self.night_mode_start = config.get('pi_camera.night_mode.start_hour', 18)
        self.night_mode_end = config.get('pi_camera.night_mode.end_hour', 6)

        # Performance optimization settings
        self.frame_skip = config.get('event_detection.performance.frame_skip', 3)
        self.motion_detection_resolution = tuple(
            config.get('event_detection.performance.motion_detection_resolution', [640, 480])
        )
        self.sleep_between_checks = config.get('event_detection.performance.sleep_between_checks', 0.1)

        # Low-risk hours (disable detection to save CPU)
        self.low_risk_enabled = config.get('event_detection.performance.low_risk_hours.enabled', False)
        self.low_risk_start = config.get('event_detection.performance.low_risk_hours.start_hour', 2)
        self.low_risk_end = config.get('event_detection.performance.low_risk_hours.end_hour', 5)

        # CPU monitoring
        self.cpu_monitoring_enabled = config.get('event_detection.performance.cpu_monitoring.enabled', True)
        self.cpu_log_interval = config.get('event_detection.performance.cpu_monitoring.log_interval', 300)
        self.process = psutil.Process(os.getpid())

        # Cloud publishing settings
        self.cloud_publishing_enabled = config.get('event_detection.cloud_publishing.enabled', True)
        self.publish_all_events = config.get('event_detection.cloud_publishing.publish_all_events', False)

        # Per-event type publishing settings
        self.publish_maintenance = {
            'telemetry': config.get('event_detection.cloud_publishing.maintenance_visit.publish_telemetry', True),
            'images': config.get('event_detection.cloud_publishing.maintenance_visit.upload_images', True)
        }
        self.publish_security = {
            'telemetry': config.get('event_detection.cloud_publishing.security_breach.publish_telemetry', True),
            'images': config.get('event_detection.cloud_publishing.security_breach.upload_images', True)
        }
        self.publish_animal = {
            'telemetry': config.get('event_detection.cloud_publishing.animal.publish_telemetry', False),
            'images': config.get('event_detection.cloud_publishing.animal.upload_images', False)
        }

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

        # Event classification
        self.event_classifier = EventClassifier(config)
        self.current_event_classification = None
        self.current_event_contours = []

        # Event snapshots (start, peak, end)
        self.event_snapshots = []  # List of snapshot paths for current event
        self.event_snapshots_raw = []  # Raw snapshot paths before processing
        self.snapshot_start_captured = False
        self.snapshot_peak_captured = False

        # Event logging
        self.event_logger = EventLogger()

        # Snapshot manager (no camera, used for processing only)
        self.snapshot_manager = CameraSnapshot(
            resolution=[1920, 1080],  # Not used, but required
            quality=85,
            init_camera=False  # Don't initialize camera - we'll pass our camera instance
        )

        # Stats
        self.stats = {
            'motion_events': 0,
            'recordings_saved': 0,
            'snapshots_taken': 0,
            'total_recording_seconds': 0,
            'buffer_size_mb': 0,
            'classified_events': 0
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
                    "size": self.motion_detection_resolution,  # Use configured resolution
                    "format": "YUV420"
                },
                encode="main"  # Encode the main stream for recording
            )

            self.camera.configure(config)

            # Apply night mode if applicable
            self._update_night_mode()

            self.camera.start()
            time.sleep(2)  # Let camera stabilize

            # Share camera instance with snapshot manager
            self.snapshot_manager.camera = self.camera

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

        # Start image cleanup thread
        Thread(target=self._image_cleanup_loop, daemon=True).start()

        # Start CPU monitoring thread
        if self.cpu_monitoring_enabled:
            Thread(target=self._cpu_monitoring_loop, daemon=True).start()

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
        - Optimized for low CPU usage on Raspberry Pi

        Performance Optimizations:
        - Frame skipping (process every Nth frame)
        - Lower resolution for motion detection
        - Faster background subtraction parameters
        - Sleep between checks to reduce CPU load
        - Optional low-risk hours (disabled detection)
        """
        self.logger.info(
            f"Motion detection started (frame_skip={self.frame_skip}, "
            f"resolution={self.motion_detection_resolution})"
        )

        # Initialize background subtractor with optimized parameters for speed
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=200,  # Reduced from 500 - faster learning, less memory
            varThreshold=self.motion_threshold,  # Sensitivity
            detectShadows=False  # Disable shadow detection for speed
        )

        consecutive_frames_without_motion = 0
        consecutive_frames_with_motion = 0
        motion_detected = False
        motion_trigger_threshold = 3  # Require 3 consecutive frames to trigger
        frame_counter = 0  # For frame skipping

        while not self.motion_stop_event.is_set():
            try:
                # Check if we're in low-risk hours (optional CPU saving)
                if self.low_risk_enabled and self._is_low_risk_hour():
                    if frame_counter % 300 == 0:  # Log every 5 minutes (at 1 fps)
                        self.logger.debug("Low-risk hours: motion detection paused")
                    time.sleep(1)  # Sleep longer during low-risk hours
                    frame_counter += 1
                    continue

                # Frame skipping for CPU optimization
                frame_counter += 1
                if frame_counter % self.frame_skip != 0:
                    time.sleep(self.sleep_between_checks)
                    continue

                # Capture low-res frame for motion detection
                frame = self.camera.capture_array("lores")

                # Downscale frame if configured (further CPU optimization)
                if frame.shape[:2] != self.motion_detection_resolution[::-1]:
                    frame = cv2.resize(
                        frame,
                        self.motion_detection_resolution,
                        interpolation=cv2.INTER_LINEAR  # Fast interpolation
                    )

                # Convert YUV420 to grayscale for processing
                gray = cv2.cvtColor(frame, cv2.COLOR_YUV420p2GRAY)

                # Apply Gaussian blur to reduce noise (smaller kernel for speed)
                blurred = cv2.GaussianBlur(gray, (3, 3), 0)

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
                significant_contours = []

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.motion_min_area:
                        motion_in_frame = True
                        total_motion_area += area
                        significant_contours.append(contour)

                # Motion detection logic with debouncing
                if motion_in_frame:
                    consecutive_frames_with_motion += 1
                    consecutive_frames_without_motion = 0

                    # Classify motion event (updates continuously during motion)
                    if significant_contours:
                        self.current_event_contours = significant_contours
                        self.current_event_classification = self.event_classifier.classify_event(
                            significant_contours,
                            frame.shape[:2]  # (height, width)
                        )

                    # Capture PEAK snapshot (after 30 seconds of motion, if not already captured)
                    if (motion_detected and not self.snapshot_peak_captured and
                        self.recording_start_time and
                        (time.time() - self.recording_start_time) > 30):
                        try:
                            peak_snapshot_raw = self.capture_snapshot(custom_name="event_peak_raw")
                            if peak_snapshot_raw:
                                self.event_snapshots_raw.append(peak_snapshot_raw)
                                self.snapshot_peak_captured = True
                                self.logger.debug("Event peak snapshot captured (raw)")
                        except Exception as e:
                            self.logger.warning(f"Failed to capture peak snapshot: {e}")

                    # Trigger recording after consecutive motion frames
                    if not motion_detected and consecutive_frames_with_motion >= motion_trigger_threshold:
                        # Check cooldown period (don't trigger too frequently)
                        time_since_last_recording = time.time() - self.last_recording_end_time

                        if time_since_last_recording >= self.motion_cooldown:
                            event_type = (
                                self.current_event_classification['event_type']
                                if self.current_event_classification
                                else 'unknown'
                            )
                            confidence = (
                                self.current_event_classification['confidence_score']
                                if self.current_event_classification
                                else 0.0
                            )

                            self.logger.info(
                                f"Motion detected! Area: {total_motion_area:.0f} px², "
                                f"Type: {event_type} (confidence: {confidence:.2f})"
                            )
                            motion_detected = True
                            self.last_motion_time = datetime.now()
                            self.stats['motion_events'] += 1

                            # Reset event snapshots for new event
                            self.event_snapshots = []
                            self.event_snapshots_raw = []
                            self.snapshot_start_captured = False
                            self.snapshot_peak_captured = False

                            # Start recording (includes pre-buffer)
                            self._start_recording("motion")

                            # Capture START snapshot (raw)
                            try:
                                start_snapshot_raw = self.capture_snapshot(custom_name="event_start_raw")
                                if start_snapshot_raw:
                                    self.event_snapshots_raw.append(start_snapshot_raw)
                                    self.snapshot_start_captured = True
                                    self.logger.debug("Event start snapshot captured (raw)")
                            except Exception as e:
                                self.logger.warning(f"Failed to capture start snapshot: {e}")
                else:
                    consecutive_frames_with_motion = 0
                    consecutive_frames_without_motion += 1

                # Stop recording after post-record period
                if motion_detected and consecutive_frames_without_motion > (self.post_record_seconds * 30):
                    self.logger.info("Motion ended, stopping recording")
                    motion_detected = False
                    consecutive_frames_with_motion = 0

                    # Capture END snapshot (raw)
                    try:
                        end_snapshot_raw = self.capture_snapshot(custom_name="event_end_raw")
                        if end_snapshot_raw:
                            self.event_snapshots_raw.append(end_snapshot_raw)
                            self.logger.debug("Event end snapshot captured (raw)")
                    except Exception as e:
                        self.logger.warning(f"Failed to capture end snapshot: {e}")

                    # Process all raw snapshots through event snapshot manager
                    if self.current_event_classification and self.event_snapshots_raw:
                        try:
                            site_id = self.config.get('site.id', 'UNKNOWN')
                            event_type = self.current_event_classification['event_type']
                            confidence = self.current_event_classification['confidence_score']
                            timestamp = self.current_event_classification.get('timestamp')

                            snapshot_types = ['start', 'peak', 'end']
                            for i, raw_path in enumerate(self.event_snapshots_raw):
                                snapshot_type = snapshot_types[i] if i < len(snapshot_types) else 'extra'

                                processed_path = self.snapshot_manager.process_event_snapshot(
                                    source_image_path=raw_path,
                                    event_type=event_type,
                                    snapshot_type=snapshot_type,
                                    confidence=confidence,
                                    site_id=site_id,
                                    timestamp=timestamp
                                )

                                if processed_path:
                                    self.event_snapshots.append(processed_path)

                                # Clean up raw file
                                try:
                                    Path(raw_path).unlink()
                                except:
                                    pass

                            self.logger.info(f"Processed {len(self.event_snapshots)} event snapshots")

                            # Create summary image if we have all 3 snapshots
                            if len(self.event_snapshots) == 3:
                                try:
                                    summary_path = self.snapshot_manager.create_summary_image(
                                        snapshot_paths=self.event_snapshots,
                                        event_type=event_type,
                                        timestamp=timestamp
                                    )
                                    if summary_path:
                                        self.logger.info(f"Created summary image: {summary_path}")
                                except Exception as e:
                                    self.logger.warning(f"Failed to create summary image: {e}")

                        except Exception as e:
                            self.logger.error(f"Failed to process event snapshots: {e}")

                    # Use first processed snapshot as primary image
                    primary_snapshot = self.event_snapshots[0] if self.event_snapshots else None

                    # Store classified event in database
                    if self.current_event_classification:
                        try:
                            # Store in event_classifier database
                            event_id = self.event_classifier.store_event(
                                self.current_event_classification,
                                image_path=primary_snapshot,
                                video_path=self.current_recording_path
                            )
                            self.stats['classified_events'] += 1

                            # Build notes with snapshot info
                            snapshot_info = f"Snapshots: {len(self.event_snapshots)} (start/peak/end)"
                            area_info = f"Area: {self.current_event_classification.get('motion_area', 0):.0f}px²"

                            self.logger.info(
                                f"Event classified and stored: ID={event_id}, "
                                f"{snapshot_info}"
                            )

                            # Also log in event_logger for surveillance logs
                            duration = int(time.time() - self.recording_start_time) if self.recording_start_time else None

                            # Include paths of all snapshots in notes
                            if self.event_snapshots:
                                snapshot_paths_str = ', '.join([Path(p).name for p in self.event_snapshots])
                            else:
                                snapshot_paths_str = 'None'

                            self.event_logger.log_event(
                                event_type=self.current_event_classification['event_type'],
                                confidence=self.current_event_classification['confidence_score'],
                                image_path=primary_snapshot,
                                duration_seconds=duration,
                                notes=f"{area_info}. {snapshot_info}. Files: {snapshot_paths_str}",
                                timestamp=self.current_event_classification.get('timestamp')
                            )

                            # Publish to AWS IoT Core and S3 (if configured)
                            self._publish_event_to_cloud(
                                self.current_event_classification,
                                self.event_snapshots,
                                self.current_recording_path
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to store classified event: {e}")

                    # Stop recording and reset classification
                    self._stop_recording()
                    self.current_event_classification = None
                    self.current_event_contours = []
                    self.event_snapshots = []
                    self.event_classifier.reset_motion_tracking()

                # Safety: Stop recording if max duration reached OR file too large
                if self.is_recording and self.recording_start_time:
                    recording_duration = time.time() - self.recording_start_time
                    
                    # Check file size if path exists
                    file_size_exceeded = False
                    if self.current_recording_path and os.path.exists(self.current_recording_path):
                        try:
                            if os.path.getsize(self.current_recording_path) > self.max_file_size_bytes:
                                file_size_exceeded = True
                                self.logger.warning(f"Max file size ({self.max_file_size_bytes/1024/1024}MB) exceeded, forcing stop")
                        except OSError:
                            pass

                    if recording_duration >= self.max_record_duration or file_size_exceeded:
                        reason = "duration" if recording_duration >= self.max_record_duration else "size"
                        self.logger.warning(
                            f"Recording limit reached ({reason}), stopping. Duration: {recording_duration:.1f}s"
                        )
                        motion_detected = False

                        # Store event even if max duration reached
                        if self.current_event_classification:
                            try:
                                # Use available snapshots
                                primary_snapshot = self.event_snapshots[0] if self.event_snapshots else None

                                event_id = self.event_classifier.store_event(
                                    self.current_event_classification,
                                    image_path=primary_snapshot,
                                    video_path=self.current_recording_path
                                )
                                self.stats['classified_events'] += 1

                                # Also log in event_logger
                                duration = int(recording_duration)
                                snapshot_info = f"Snapshots: {len(self.event_snapshots)} (start/peak/end)"
                                area_info = f"Area: {self.current_event_classification.get('motion_area', 0):.0f}px²"

                                if self.event_snapshots:
                                    snapshot_paths_str = ', '.join([Path(p).name for p in self.event_snapshots])
                                else:
                                    snapshot_paths_str = 'None'

                                self.event_logger.log_event(
                                    event_type=self.current_event_classification['event_type'],
                                    confidence=self.current_event_classification['confidence_score'],
                                    image_path=primary_snapshot,
                                    duration_seconds=duration,
                                    notes=f"Max duration reached. {area_info}. {snapshot_info}. Files: {snapshot_paths_str}",
                                    timestamp=self.current_event_classification.get('timestamp')
                                )

                                # Publish to AWS IoT Core and S3 (if configured)
                                self._publish_event_to_cloud(
                                    self.current_event_classification,
                                    self.event_snapshots,
                                    self.current_recording_path
                                )
                            except Exception as e:
                                self.logger.error(f"Failed to store classified event: {e}")

                        self._stop_recording()
                        self.current_event_classification = None
                        self.current_event_contours = []
                        self.event_snapshots = []
                        self.event_classifier.reset_motion_tracking()

                # Configurable sleep between checks (CPU optimization)
                time.sleep(self.sleep_between_checks)

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
                filepath = f"/home/smartie/transformer_monitor_data/videos/{filename}"

                # Ensure directory exists
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)

                # Start recording to file (includes circular buffer content)
                # Picamera2 CircularOutput expects a file-like object or filename depending on usage.
                # The error "Must pass io.BufferedIOBase" suggests it strictly wants an open file object.
                self.output_file = open(filepath, "wb")
                
                # This writes the circular buffer content first, then continues with live frames
                self.circular_output.fileoutput = self.output_file
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
                
                # Upload video if configured
                if self.media_uploader:
                    metadata = {
                        'site_id': self.config.get('site.id', 'UNKNOWN'),
                        'timestamp': datetime.fromtimestamp(self.recording_start_time).isoformat(),
                        'duration': duration,
                        'trigger': 'motion'
                    }
                    self.media_uploader.queue_video(self.current_recording_path, metadata)

                # Reset state
                self.is_recording = False
                self.current_recording_path = None
                self.recording_start_time = None

                # Close file if opened
                if hasattr(self, 'output_file') and self.output_file:
                    self.output_file.close()
                    self.output_file = None

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

            filepath = f"/home/smartie/transformer_monitor_data/images/{filename}"
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
            
            # Upload visual snapshot
            if self.media_uploader:
                metadata = {
                    'site_id': site_id,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'snapshot'
                }
                self.media_uploader.queue_visual_image(filepath, metadata)

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

    def _image_cleanup_loop(self):
        """Periodically cleanup old event images"""
        while True:
            try:
                # Run cleanup daily at 3 AM
                time.sleep(3600)  # Check every hour

                current_hour = datetime.now().hour
                if current_hour == 3:
                    # Get retention days from config
                    days_to_keep = self.config.get('event_detection.storage.keep_days', 30)
                    deleted = self.snapshot_manager.cleanup_old_images(days_to_keep=days_to_keep)
                    if deleted > 0:
                        self.logger.info(f"Cleaned up {deleted} old event images (retention: {days_to_keep} days)")

                    # Sleep for an hour to avoid running multiple times at 3 AM
                    time.sleep(3600)

            except Exception as e:
                self.logger.error(f"Image cleanup error: {e}")
                time.sleep(3600)

    def _is_low_risk_hour(self):
        """
        Check if current hour is within low-risk period

        Returns:
            bool: True if current time is in low-risk hours
        """
        current_hour = datetime.now().hour

        if self.low_risk_start < self.low_risk_end:
            # Normal range (e.g., 2 AM to 5 AM)
            return self.low_risk_start <= current_hour < self.low_risk_end
        else:
            # Wraps around midnight (e.g., 23:00 to 02:00)
            return current_hour >= self.low_risk_start or current_hour < self.low_risk_end

    def _cpu_monitoring_loop(self):
        """
        Monitor CPU and memory usage, log periodically

        Target: < 25% average CPU, < 40% peak during events
        """
        if not self.cpu_monitoring_enabled:
            return

        self.logger.info(f"CPU monitoring started (interval: {self.cpu_log_interval}s)")

        while True:
            try:
                # Get CPU and memory usage
                cpu_percent = self.process.cpu_percent(interval=1)
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                # Get system-wide CPU
                system_cpu = psutil.cpu_percent(interval=0)

                # Log performance metrics
                self.logger.info(
                    f"Performance: CPU={cpu_percent:.1f}% (system={system_cpu:.1f}%), "
                    f"Memory={memory_mb:.1f}MB, "
                    f"Recording={self.is_recording}, "
                    f"Events={self.stats['motion_events']}"
                )

                # Warn if CPU usage is too high
                if cpu_percent > 40:
                    self.logger.warning(
                        f"High CPU usage detected: {cpu_percent:.1f}% "
                        f"(target: <25% avg, <40% peak)"
                    )

                # Sleep until next check
                time.sleep(self.cpu_log_interval)

            except Exception as e:
                self.logger.error(f"CPU monitoring error: {e}")
                time.sleep(self.cpu_log_interval)

    def _should_publish_event(self, event_type):
        """
        Check if event should be published to cloud based on config

        Args:
            event_type: Type of event (maintenance_visit, security_breach, animal)

        Returns:
            Dict with 'telemetry' and 'images' boolean flags
        """
        if not self.cloud_publishing_enabled or not self.aws_publisher:
            return {'telemetry': False, 'images': False}

        # Publish all events if configured
        if self.publish_all_events:
            return {'telemetry': True, 'images': True}

        # Check per-event type settings
        if event_type == 'maintenance_visit':
            return self.publish_maintenance
        elif event_type == 'security_breach':
            return self.publish_security
        elif event_type == 'animal':
            return self.publish_animal
        else:
            return {'telemetry': False, 'images': False}

    def _publish_event_to_cloud(self, event_classification, snapshot_paths, video_path=None):
        """
        Publish event to AWS IoT Core and S3 (if configured)

        Args:
            event_classification: Event classification dict from event_classifier
            snapshot_paths: List of paths to event snapshot images
            video_path: Optional path to video recording

        This method gracefully handles missing AWS credentials:
        - Returns immediately if aws_publisher is None
        - Logs warning but doesn't raise errors
        - System continues working with local storage only
        """
        if not self.aws_publisher:
            self.logger.debug("AWS publisher not configured, skipping cloud publish")
            return

        try:
            event_type = event_classification['event_type']
            should_publish = self._should_publish_event(event_type)

            if not should_publish['telemetry'] and not should_publish['images']:
                self.logger.debug(f"Cloud publishing disabled for {event_type}")
                return

            # Publish event telemetry to IoT Core
            if should_publish['telemetry']:
                telemetry_data = {
                    'event_type': event_type,
                    'confidence': event_classification['confidence_score'],
                    'timestamp': event_classification.get('timestamp', datetime.now()).isoformat(),
                    'site_id': self.config.get('site.id', 'UNKNOWN'),
                    'motion_area': event_classification.get('motion_area', 0),
                    'motion_pattern': event_classification.get('motion_pattern', 'unknown'),
                    'time_classification': event_classification.get('time_classification', 'unknown'),
                    'size_classification': event_classification.get('size_classification', 'unknown'),
                    'video_path': Path(video_path).name if video_path else None,
                    'snapshot_count': len(snapshot_paths),
                    'snapshot_files': [Path(p).name for p in snapshot_paths] if snapshot_paths else []
                }

                success = self.aws_publisher.publish_telemetry(telemetry_data)
                if success:
                    self.logger.info(f"Published {event_type} event to AWS IoT Core")
                else:
                    self.logger.warning(f"Failed to publish {event_type} event (will retry)")

            # Upload event images to S3
            if should_publish['images'] and snapshot_paths:
                for snapshot_path in snapshot_paths:
                    if snapshot_path and Path(snapshot_path).exists():
                        # Determine snapshot type from filename
                        filename = Path(snapshot_path).name
                        if 'start' in filename:
                            image_type = 'event_start'
                        elif 'peak' in filename:
                            image_type = 'event_peak'
                        elif 'end' in filename:
                            image_type = 'event_end'
                        elif 'summary' in filename:
                            image_type = 'event_summary'
                        else:
                            image_type = 'event_snapshot'

                        metadata = {
                            'site_id': self.config.get('site.id', 'UNKNOWN'),
                            'event_type': event_type,
                            'confidence': str(event_classification['confidence_score']),
                            'timestamp': event_classification.get('timestamp', datetime.now()).isoformat()
                        }

                        success = self.aws_publisher.upload_image(
                            snapshot_path,
                            image_type,
                            metadata
                        )

                        if success:
                            self.logger.info(f"Uploaded {image_type} to S3: {filename}")
                        else:
                            self.logger.warning(f"Failed to upload {image_type} (will retry)")

        except Exception as e:
            # Graceful error handling - log but don't crash
            self.logger.error(f"Cloud publishing error: {e}", exc_info=True)
            self.logger.info("Event saved locally, cloud publishing failed")

    def get_stats(self):
        """Get camera statistics"""
        stats = {
            **self.stats,
            'is_recording': self.is_recording,
            'last_motion': self.last_motion_time.isoformat() if self.last_motion_time else None,
            'recording_duration': int(time.time() - self.recording_start_time) if self.is_recording and self.recording_start_time else 0
        }

        # Add event classification stats
        try:
            event_stats = self.event_classifier.get_event_stats()
            stats['event_classification'] = event_stats
        except Exception as e:
            self.logger.debug(f"Failed to get event stats: {e}")

        # Add event logger stats
        try:
            log_stats = self.event_logger.get_event_stats()
            stats['event_log'] = log_stats
        except Exception as e:
            self.logger.debug(f"Failed to get event log stats: {e}")

        # Add current event type if motion is active
        if self.current_event_classification:
            stats['current_event_type'] = self.current_event_classification['event_type']
            stats['current_event_confidence'] = self.current_event_classification['confidence_score']

        return stats

    def get_recent_events(self, limit=10):
        """Get recent classified events"""
        try:
            return self.event_classifier.get_recent_events(limit)
        except Exception as e:
            self.logger.error(f"Failed to get recent events: {e}")
            return []

    def get_event_log(self, limit=50, event_type=None):
        """Get recent surveillance event logs"""
        try:
            return self.event_logger.get_recent_events(limit, event_type)
        except Exception as e:
            self.logger.error(f"Failed to get event log: {e}")
            return []

    def get_maintenance_visits(self, days_back=30):
        """Get maintenance visit logs for maintenance tracking"""
        try:
            return self.event_logger.get_maintenance_visits(days_back)
        except Exception as e:
            self.logger.error(f"Failed to get maintenance visits: {e}")
            return []

    def export_event_log(self, output_path, start_date=None, end_date=None, event_type=None):
        """Export surveillance event log to CSV"""
        try:
            return self.event_logger.export_to_csv(output_path, start_date, end_date, event_type)
        except Exception as e:
            self.logger.error(f"Failed to export event log: {e}")
            return False

    def close(self):
        """Cleanup camera resources"""
        self.stop_monitoring()
        if self.camera:
            self.camera.close()
        self.logger.info("Camera closed")
