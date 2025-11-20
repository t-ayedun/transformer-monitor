"""
Camera Event Logger
Simple SQLite-based logging system for camera surveillance events
"""

import sqlite3
import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional


class EventLogger:
    """Simple event logger for camera surveillance events"""

    def __init__(self, db_path: str = "/data/buffer/camera_events.db"):
        """
        Initialize event logger

        Args:
            db_path: Path to SQLite database file
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with camera_events table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create camera_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS camera_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    image_path TEXT,
                    duration_seconds INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON camera_events(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON camera_events(event_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON camera_events(created_at)
            """)

            conn.commit()
            conn.close()

            self.logger.info(f"Event logger initialized at {self.db_path}")

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    def log_event(
        self,
        event_type: str,
        confidence: float,
        image_path: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        notes: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Insert a new camera event

        Args:
            event_type: Type of event ('maintenance_visit', 'security_breach', 'animal')
            confidence: Confidence score (0.0 to 1.0)
            image_path: Optional path to captured image
            duration_seconds: Optional duration if motion was sustained
            notes: Optional notes about the event
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Event ID from database, or -1 on error
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO camera_events (
                    timestamp, event_type, confidence,
                    image_path, duration_seconds, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                event_type,
                confidence,
                image_path,
                duration_seconds,
                notes
            ))

            event_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.logger.info(
                f"Event logged: ID={event_id}, type={event_type}, "
                f"confidence={confidence:.2f}"
            )

            return event_id

        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
            return -1

    def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query events by type

        Args:
            event_type: Type of event to query
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM camera_events
                WHERE event_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (event_type, limit))

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return events

        except Exception as e:
            self.logger.error(f"Failed to query events by type: {e}")
            return []

    def get_events_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query events by date range

        Args:
            start_date: Start of date range
            end_date: End of date range
            event_type: Optional filter by event type

        Returns:
            List of event dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if event_type:
                cursor.execute("""
                    SELECT * FROM camera_events
                    WHERE timestamp >= ? AND timestamp <= ?
                    AND event_type = ?
                    ORDER BY timestamp DESC
                """, (start_date.isoformat(), end_date.isoformat(), event_type))
            else:
                cursor.execute("""
                    SELECT * FROM camera_events
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                """, (start_date.isoformat(), end_date.isoformat()))

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return events

        except Exception as e:
            self.logger.error(f"Failed to query events by date range: {e}")
            return []

    def get_maintenance_visits(
        self,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get maintenance visit timestamps for maintenance logs

        Args:
            days_back: Number of days to look back

        Returns:
            List of maintenance visit events
        """
        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        return self.get_events_by_date_range(
            start_date,
            end_date,
            event_type='maintenance_visit'
        )

    def get_recent_events(
        self,
        limit: int = 50,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent events

        Args:
            limit: Maximum number of events to return
            event_type: Optional filter by event type

        Returns:
            List of event dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if event_type:
                cursor.execute("""
                    SELECT * FROM camera_events
                    WHERE event_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (event_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM camera_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return events

        except Exception as e:
            self.logger.error(f"Failed to get recent events: {e}")
            return []

    def export_to_csv(
        self,
        output_path: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None
    ) -> bool:
        """
        Export events to CSV file

        Args:
            output_path: Path to output CSV file
            start_date: Optional start date filter
            end_date: Optional end date filter
            event_type: Optional event type filter

        Returns:
            True if successful, False otherwise
        """
        try:
            # Query events based on filters
            if start_date and end_date:
                events = self.get_events_by_date_range(start_date, end_date, event_type)
            elif event_type:
                events = self.get_events_by_type(event_type, limit=10000)
            else:
                events = self.get_recent_events(limit=10000, event_type=event_type)

            if not events:
                self.logger.warning("No events to export")
                return False

            # Write to CSV
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'id', 'timestamp', 'event_type', 'confidence',
                    'image_path', 'duration_seconds', 'notes', 'created_at'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for event in events:
                    writer.writerow(event)

            self.logger.info(f"Exported {len(events)} events to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export to CSV: {e}")
            return False

    def get_event_stats(self) -> Dict[str, Any]:
        """
        Get statistics about logged events

        Returns:
            Dictionary with event statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total events
            cursor.execute("SELECT COUNT(*) FROM camera_events")
            total = cursor.fetchone()[0]

            # Events by type
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM camera_events
                GROUP BY event_type
            """)
            by_type = dict(cursor.fetchall())

            # Average confidence by type
            cursor.execute("""
                SELECT event_type, AVG(confidence) as avg_confidence
                FROM camera_events
                GROUP BY event_type
            """)
            avg_confidence = dict(cursor.fetchall())

            # Events today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute("""
                SELECT COUNT(*) FROM camera_events
                WHERE timestamp >= ?
            """, (today_start.isoformat(),))
            today_count = cursor.fetchone()[0]

            # Events this week
            week_start = datetime.now() - timedelta(days=7)
            cursor.execute("""
                SELECT COUNT(*) FROM camera_events
                WHERE timestamp >= ?
            """, (week_start.isoformat(),))
            week_count = cursor.fetchone()[0]

            conn.close()

            return {
                'total_events': total,
                'events_by_type': by_type,
                'avg_confidence_by_type': avg_confidence,
                'events_today': today_count,
                'events_this_week': week_count
            }

        except Exception as e:
            self.logger.error(f"Failed to get event stats: {e}")
            return {}

    def delete_old_events(self, days_to_keep: int = 90) -> int:
        """
        Delete events older than specified days

        Args:
            days_to_keep: Number of days to keep (default 90)

        Returns:
            Number of events deleted
        """
        try:
            cutoff = datetime.now() - timedelta(days=days_to_keep)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM camera_events
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted > 0:
                self.logger.info(f"Deleted {deleted} old events (older than {days_to_keep} days)")

            return deleted

        except Exception as e:
            self.logger.error(f"Failed to delete old events: {e}")
            return 0

    def get_event_by_id(self, event_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific event by ID

        Args:
            event_id: Event ID to retrieve

        Returns:
            Event dictionary or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM camera_events
                WHERE id = ?
            """, (event_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            self.logger.error(f"Failed to get event by ID: {e}")
            return None

    def update_event_notes(self, event_id: int, notes: str) -> bool:
        """
        Update notes for an event

        Args:
            event_id: Event ID to update
            notes: New notes text

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE camera_events
                SET notes = ?
                WHERE id = ?
            """, (notes, event_id))

            conn.commit()
            conn.close()

            self.logger.info(f"Updated notes for event ID={event_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update event notes: {e}")
            return False

    def close(self):
        """Close database connection (SQLite closes after each operation)"""
        self.logger.info("Event logger closed")
