"""
Event Classification System for Pi Camera Motion Detection

Classifies motion events into three categories:
- maintenance_visit: Scheduled maintenance during business hours
- security_breach: Unexpected activity during off-hours
- animal: Small, erratic movements

Uses lightweight OpenCV methods for low CPU usage on Raspberry Pi.
"""

import os
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional
import numpy as np
import cv2


class EventClassifier:
    """
    Lightweight event classifier for Pi Camera motion events

    Classification criteria:
    1. Time of day: Business hours (8am-5pm weekdays) vs off-hours
    2. Motion pattern: Slow/sustained vs quick/erratic
    3. Object size: Large (human) vs small (animal)
    """

    # Event types
    EVENT_MAINTENANCE = "maintenance_visit"
    EVENT_SECURITY = "security_breach"
    EVENT_ANIMAL = "animal"

    # Time thresholds
    BUSINESS_START_HOUR = 8
    BUSINESS_END_HOUR = 17  # 5 PM
    BUSINESS_DAYS = [0, 1, 2, 3, 4]  # Monday-Friday

    # Size thresholds (percentage of frame)
    ANIMAL_SIZE_THRESHOLD = 0.20  # < 20% of frame = animal
    MAINTENANCE_SIZE_THRESHOLD = 0.30  # > 30% of frame = maintenance (human close to camera)

    # Duration thresholds (seconds)
    ANIMAL_DURATION_THRESHOLD = 30  # < 30 seconds = likely animal
    MAINTENANCE_DURATION_THRESHOLD = 120  # > 2 minutes = likely maintenance

    # Motion pattern thresholds
    ERRATIC_MOTION_THRESHOLD = 0.6  # Direction changes per second
    SUSTAINED_MOTION_DURATION = 3.0  # Seconds for initial pattern detection

    def __init__(self, config, db_path="/data/events.db"):
        """
        Initialize event classifier

        Args:
            config: Application configuration
            db_path: Path to SQLite database
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.db_path = db_path

        # Motion tracking for pattern analysis
        self.motion_history = []  # List of (timestamp, centroid, area)
        self.motion_start_time = None

        # Frame info for size calculation
        self.frame_width = 640  # Low-res frame width
        self.frame_height = 480  # Low-res frame height
        self.frame_area = self.frame_width * self.frame_height

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for event storage"""
        try:
            # Ensure directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    image_path TEXT,
                    video_path TEXT,
                    motion_area REAL,
                    motion_pattern TEXT,
                    time_classification TEXT,
                    size_classification TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on timestamp for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON events(timestamp)
            """)

            # Create index on event_type
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON events(event_type)
            """)

            conn.commit()
            conn.close()

            self.logger.info(f"Event database initialized: {self.db_path}")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def classify_event(
        self,
        contours,
        frame_shape: Tuple[int, int],
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Classify a motion event based on multiple factors

        Args:
            contours: List of OpenCV contours from motion detection
            frame_shape: Tuple of (height, width) of the frame
            timestamp: Event timestamp (default: now)

        Returns:
            Dictionary with classification results:
            {
                'event_type': str,
                'confidence_score': float (0-1),
                'motion_area': float,
                'motion_pattern': str,
                'time_classification': str,
                'size_classification': str
            }
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Update frame dimensions
        self.frame_height, self.frame_width = frame_shape
        self.frame_area = self.frame_width * self.frame_height

        # Initialize motion tracking on first detection
        if self.motion_start_time is None:
            self.motion_start_time = timestamp
            self.motion_history = []

        # Analyze time of day
        time_class, time_confidence = self._classify_time(timestamp)

        # Analyze object size
        size_class, size_confidence, total_area = self._classify_size(contours)

        # Analyze motion pattern
        pattern_class, pattern_confidence = self._classify_motion_pattern(
            contours, timestamp
        )

        # Calculate duration since motion started
        duration_seconds = 0
        if self.motion_start_time:
            duration_seconds = (timestamp - self.motion_start_time).total_seconds()

        # Combine classifications with duration
        event_type, confidence = self._combine_classifications(
            time_class, time_confidence,
            size_class, size_confidence,
            pattern_class, pattern_confidence,
            duration_seconds
        )

        result = {
            'event_type': event_type,
            'confidence_score': confidence,
            'motion_area': total_area,
            'motion_pattern': pattern_class,
            'time_classification': time_class,
            'size_classification': size_class,
            'timestamp': timestamp
        }

        self.logger.debug(
            f"Event classified: {event_type} "
            f"(confidence: {confidence:.2f}, size: {size_class}, "
            f"pattern: {pattern_class}, time: {time_class})"
        )

        return result

    def _classify_time(self, timestamp: datetime) -> Tuple[str, float]:
        """
        Classify based on time of day and day of week

        Returns:
            Tuple of (classification, confidence)
        """
        hour = timestamp.hour
        weekday = timestamp.weekday()

        # Business hours: 8am-5pm Monday-Friday
        is_business_hours = (
            self.BUSINESS_START_HOUR <= hour < self.BUSINESS_END_HOUR and
            weekday in self.BUSINESS_DAYS
        )

        if is_business_hours:
            # During business hours: likely maintenance
            return "business_hours", 0.8
        else:
            # Off-hours: likely security breach or animal
            return "off_hours", 0.9

    def _classify_size(self, contours) -> Tuple[str, float, float]:
        """
        Classify based on object size in frame

        Returns:
            Tuple of (classification, confidence, total_area)
        """
        if not contours:
            return "unknown", 0.0, 0.0

        # Calculate total motion area
        total_area = sum(cv2.contourArea(c) for c in contours)
        area_percentage = total_area / self.frame_area

        # Find largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        largest_area = cv2.contourArea(largest_contour)
        largest_percentage = largest_area / self.frame_area

        # Classify based on size with updated thresholds
        if largest_percentage < self.ANIMAL_SIZE_THRESHOLD:
            # Small object (< 20%): likely animal
            confidence = min(0.9, 0.5 + (self.ANIMAL_SIZE_THRESHOLD - largest_percentage) * 4)
            return "small", confidence, total_area
        elif largest_percentage > self.MAINTENANCE_SIZE_THRESHOLD:
            # Very large object (> 30%): likely human/maintenance
            confidence = min(0.95, 0.6 + (largest_percentage - self.MAINTENANCE_SIZE_THRESHOLD) * 2)
            return "large", confidence, total_area
        else:
            # Medium size (20-30%): uncertain
            return "medium", 0.5, total_area

    def _classify_motion_pattern(
        self,
        contours,
        timestamp: datetime
    ) -> Tuple[str, float]:
        """
        Classify based on motion pattern over time

        Analyzes:
        - Direction consistency (erratic vs steady)
        - Speed (fast vs slow)
        - Duration (sustained vs brief)

        Returns:
            Tuple of (classification, confidence)
        """
        if not contours:
            return "unknown", 0.0

        # Calculate centroid of motion
        total_area = sum(cv2.contourArea(c) for c in contours)
        if total_area == 0:
            return "unknown", 0.0

        # Weighted centroid based on contour areas
        cx_sum = 0
        cy_sum = 0
        for contour in contours:
            M = cv2.moments(contour)
            if M['m00'] != 0:
                cx = M['m10'] / M['m00']
                cy = M['m01'] / M['m00']
                area = cv2.contourArea(contour)
                cx_sum += cx * area
                cy_sum += cy * area

        centroid = (cx_sum / total_area, cy_sum / total_area)

        # Add to history
        self.motion_history.append({
            'timestamp': timestamp,
            'centroid': centroid,
            'area': total_area
        })

        # Keep only recent history (last 10 seconds)
        cutoff_time = timestamp.timestamp() - 10.0
        self.motion_history = [
            h for h in self.motion_history
            if h['timestamp'].timestamp() > cutoff_time
        ]

        # Need at least 5 samples for pattern analysis
        if len(self.motion_history) < 5:
            return "initializing", 0.3

        # Calculate motion metrics
        direction_changes = 0
        total_distance = 0

        for i in range(1, len(self.motion_history)):
            prev = self.motion_history[i-1]
            curr = self.motion_history[i]

            # Calculate distance moved
            dx = curr['centroid'][0] - prev['centroid'][0]
            dy = curr['centroid'][1] - prev['centroid'][1]
            distance = np.sqrt(dx**2 + dy**2)
            total_distance += distance

            # Check for direction change (comparing with previous movement)
            if i >= 2:
                prev2 = self.motion_history[i-2]
                prev_dx = prev['centroid'][0] - prev2['centroid'][0]
                prev_dy = prev['centroid'][1] - prev2['centroid'][1]

                # Calculate angle change
                if prev_dx != 0 or prev_dy != 0:
                    prev_angle = np.arctan2(prev_dy, prev_dx)
                    curr_angle = np.arctan2(dy, dx)
                    angle_diff = abs(curr_angle - prev_angle)

                    # Normalize angle difference to [0, π]
                    if angle_diff > np.pi:
                        angle_diff = 2 * np.pi - angle_diff

                    # Count as direction change if > 45 degrees
                    if angle_diff > np.pi / 4:
                        direction_changes += 1

        # Calculate metrics
        duration = (
            self.motion_history[-1]['timestamp'].timestamp() -
            self.motion_history[0]['timestamp'].timestamp()
        )

        if duration > 0:
            direction_change_rate = direction_changes / duration
            avg_speed = total_distance / duration
        else:
            direction_change_rate = 0
            avg_speed = 0

        # Classify pattern
        if direction_change_rate > self.ERRATIC_MOTION_THRESHOLD:
            # Erratic motion: likely animal
            confidence = min(0.85, 0.5 + direction_change_rate)
            return "erratic", confidence
        elif duration >= self.SUSTAINED_MOTION_DURATION and avg_speed < 50:
            # Slow, sustained motion: likely human/maintenance
            confidence = min(0.85, 0.5 + (duration / 10.0))
            return "sustained", confidence
        else:
            # Medium confidence
            return "steady", 0.5

    def _combine_classifications(
        self,
        time_class: str, time_conf: float,
        size_class: str, size_conf: float,
        pattern_class: str, pattern_conf: float,
        duration_seconds: float = 0
    ) -> Tuple[str, float]:
        """
        Combine individual classifications into final event type with duration-based rules

        Specific classification rules:
        1. Business hours + large size (>30%) + duration >2min = maintenance_visit (HIGH confidence)
        2. Off-hours (night/weekend) + any motion = security_breach (HIGH confidence)
        3. Small size (<20%) + duration <30sec = animal (HIGH confidence)
        4. Fallback rules for ambiguous cases

        Args:
            duration_seconds: Time elapsed since motion started (in seconds)

        Returns:
            Tuple of (event_type, confidence_score)
        """
        # RULE 1: Clear maintenance visit
        # Weekday AND 8am-5pm AND duration >2min AND object size >30%
        if (time_class == "business_hours" and
            size_class == "large" and
            duration_seconds > self.MAINTENANCE_DURATION_THRESHOLD):
            # High confidence maintenance visit
            confidence = min(0.95, (time_conf * 0.3 + size_conf * 0.4 + 0.3))
            return self.EVENT_MAINTENANCE, confidence

        # RULE 2: Clear animal detection
        # Small object (<20%) AND short duration (<30sec)
        if (size_class == "small" and
            duration_seconds < self.ANIMAL_DURATION_THRESHOLD):
            # High confidence animal
            confidence = min(0.92, (size_conf * 0.6 + 0.4))
            return self.EVENT_ANIMAL, confidence

        # RULE 3: Any small object is likely animal (regardless of duration)
        if size_class == "small":
            # Medium-high confidence animal
            confidence = min(0.85, size_conf * 0.9)
            return self.EVENT_ANIMAL, confidence

        # RULE 4: Off-hours + any motion = security breach
        # (night OR weekend) AND motion detected
        if time_class == "off_hours":
            # High confidence security breach
            if size_class == "large":
                confidence = min(0.90, (time_conf * 0.5 + size_conf * 0.5))
            else:
                confidence = min(0.75, time_conf * 0.85)
            return self.EVENT_SECURITY, confidence

        # RULE 5: Business hours + large object + sustained motion = maintenance
        # (Even if duration < 2min, still likely maintenance)
        if (time_class == "business_hours" and
            size_class == "large" and
            pattern_class == "sustained"):
            # Medium-high confidence maintenance
            confidence = min(0.85, (time_conf * 0.4 + size_conf * 0.3 + pattern_conf * 0.3))
            return self.EVENT_MAINTENANCE, confidence

        # RULE 6: Business hours + erratic = Animal (bird/squirrel near camera)
        if time_class == "business_hours" and pattern_class == "erratic":
            confidence = min(0.70, pattern_conf * 0.8)
            return self.EVENT_ANIMAL, confidence

        # Default fallback: Business hours with unclear signal = maintenance (low confidence)
        if time_class == "business_hours":
            confidence = min(0.55, time_conf * 0.65)
            return self.EVENT_MAINTENANCE, confidence

        # Final fallback: Off-hours with unclear signal = security breach (low confidence)
        confidence = min(0.50, time_conf * 0.60)
        return self.EVENT_SECURITY, confidence

    def store_event(
        self,
        classification: Dict,
        image_path: Optional[str] = None,
        video_path: Optional[str] = None
    ) -> int:
        """
        Store classified event in database

        Args:
            classification: Classification result from classify_event()
            image_path: Optional path to snapshot image
            video_path: Optional path to video recording

        Returns:
            Event ID from database
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO events (
                    timestamp, event_type, confidence_score,
                    image_path, video_path, motion_area,
                    motion_pattern, time_classification, size_classification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                classification['timestamp'].isoformat(),
                classification['event_type'],
                classification['confidence_score'],
                image_path,
                video_path,
                classification['motion_area'],
                classification['motion_pattern'],
                classification['time_classification'],
                classification['size_classification']
            ))

            event_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.logger.info(
                f"Event stored: ID={event_id}, "
                f"type={classification['event_type']}, "
                f"confidence={classification['confidence_score']:.2f}"
            )

            return event_id

        except Exception as e:
            self.logger.error(f"Failed to store event: {e}")
            return -1

    def get_recent_events(self, limit: int = 10) -> list:
        """
        Get recent events from database

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return events

        except Exception as e:
            self.logger.error(f"Failed to get recent events: {e}")
            return []

    def get_event_stats(self) -> Dict:
        """
        Get statistics about classified events

        Returns:
            Dictionary with event statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total events by type
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM events
                GROUP BY event_type
            """)
            type_counts = dict(cursor.fetchall())

            # Average confidence by type
            cursor.execute("""
                SELECT event_type, AVG(confidence_score) as avg_confidence
                FROM events
                GROUP BY event_type
            """)
            avg_confidence = dict(cursor.fetchall())

            # Total events
            cursor.execute("SELECT COUNT(*) FROM events")
            total = cursor.fetchone()[0]

            conn.close()

            return {
                'total_events': total,
                'events_by_type': type_counts,
                'avg_confidence_by_type': avg_confidence
            }

        except Exception as e:
            self.logger.error(f"Failed to get event stats: {e}")
            return {}

    def reset_motion_tracking(self):
        """Reset motion tracking for new event"""
        self.motion_history = []
        self.motion_start_time = None
