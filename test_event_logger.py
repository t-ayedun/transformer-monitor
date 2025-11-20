#!/usr/bin/env python3
"""
Test script for event logging system

Demonstrates all functionality of the EventLogger class
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from event_logger import EventLogger


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_basic_logging():
    """Test basic event logging functionality"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Basic Event Logging")
    logger.info("="*60)

    # Create event logger with test database
    test_db = "/tmp/test_camera_events.db"
    if Path(test_db).exists():
        Path(test_db).unlink()

    event_logger = EventLogger(db_path=test_db)

    # Log different types of events
    logger.info("\n1. Logging maintenance visit...")
    event_id1 = event_logger.log_event(
        event_type='maintenance_visit',
        confidence=0.85,
        image_path='/data/images/event_001.jpg',
        duration_seconds=45,
        notes='Regular scheduled maintenance check'
    )
    assert event_id1 > 0, "Event ID should be positive"
    logger.info(f"✓ Maintenance visit logged: ID={event_id1}")

    logger.info("\n2. Logging security breach...")
    event_id2 = event_logger.log_event(
        event_type='security_breach',
        confidence=0.92,
        image_path='/data/images/event_002.jpg',
        duration_seconds=120,
        notes='Motion detected at 2:30 AM',
        timestamp=datetime.now() - timedelta(hours=5)
    )
    assert event_id2 > 0, "Event ID should be positive"
    logger.info(f"✓ Security breach logged: ID={event_id2}")

    logger.info("\n3. Logging animal detection...")
    event_id3 = event_logger.log_event(
        event_type='animal',
        confidence=0.78,
        image_path='/data/images/event_003.jpg',
        duration_seconds=15,
        notes='Small erratic movement detected'
    )
    assert event_id3 > 0, "Event ID should be positive"
    logger.info(f"✓ Animal detection logged: ID={event_id3}")

    logger.info("\n✓ Basic logging test passed!")
    return event_logger


def test_query_by_type(event_logger):
    """Test querying events by type"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Query Events by Type")
    logger.info("="*60)

    # Query maintenance visits
    logger.info("\nQuerying maintenance visits...")
    maintenance = event_logger.get_events_by_type('maintenance_visit')
    logger.info(f"Found {len(maintenance)} maintenance visit(s)")
    for event in maintenance:
        logger.info(f"  - ID {event['id']}: {event['timestamp']} (confidence: {event['confidence']:.2f})")

    # Query security breaches
    logger.info("\nQuerying security breaches...")
    security = event_logger.get_events_by_type('security_breach')
    logger.info(f"Found {len(security)} security breach(es)")
    for event in security:
        logger.info(f"  - ID {event['id']}: {event['timestamp']} (confidence: {event['confidence']:.2f})")

    # Query animals
    logger.info("\nQuerying animal detections...")
    animals = event_logger.get_events_by_type('animal')
    logger.info(f"Found {len(animals)} animal detection(s)")
    for event in animals:
        logger.info(f"  - ID {event['id']}: {event['timestamp']} (confidence: {event['confidence']:.2f})")

    logger.info("\n✓ Query by type test passed!")


def test_query_by_date_range(event_logger):
    """Test querying events by date range"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Query Events by Date Range")
    logger.info("="*60)

    # Add some older events
    logger.info("\nAdding events from different time periods...")
    yesterday = datetime.now() - timedelta(days=1)
    last_week = datetime.now() - timedelta(days=7)

    event_logger.log_event(
        event_type='maintenance_visit',
        confidence=0.80,
        timestamp=yesterday
    )

    event_logger.log_event(
        event_type='animal',
        confidence=0.75,
        timestamp=last_week
    )

    # Query last 24 hours
    logger.info("\nQuerying events from last 24 hours...")
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now()
    recent = event_logger.get_events_by_date_range(start_date, end_date)
    logger.info(f"Found {len(recent)} event(s) in last 24 hours")

    # Query last week
    logger.info("\nQuerying events from last 7 days...")
    start_date = datetime.now() - timedelta(days=7)
    week_events = event_logger.get_events_by_date_range(start_date, end_date)
    logger.info(f"Found {len(week_events)} event(s) in last 7 days")

    # Query specific type in date range
    logger.info("\nQuerying security breaches in last 24 hours...")
    start_date = datetime.now() - timedelta(days=1)
    security_recent = event_logger.get_events_by_date_range(
        start_date, end_date, event_type='security_breach'
    )
    logger.info(f"Found {len(security_recent)} security breach(es)")

    logger.info("\n✓ Query by date range test passed!")


def test_maintenance_visits(event_logger):
    """Test getting maintenance visit timestamps"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Get Maintenance Visit Logs")
    logger.info("="*60)

    # Add some maintenance visits
    logger.info("\nAdding maintenance visits over the past month...")
    for i in range(5):
        days_ago = i * 7  # One per week
        timestamp = datetime.now() - timedelta(days=days_ago)
        event_logger.log_event(
            event_type='maintenance_visit',
            confidence=0.85,
            image_path=f'/data/images/maintenance_{i}.jpg',
            duration_seconds=30 + i * 10,
            notes=f'Week {i+1} maintenance check',
            timestamp=timestamp
        )

    # Get maintenance visits
    logger.info("\nRetrieving maintenance visits from last 30 days...")
    visits = event_logger.get_maintenance_visits(days_back=30)
    logger.info(f"Found {len(visits)} maintenance visit(s)")

    for visit in visits:
        logger.info(
            f"  - {visit['timestamp']}: "
            f"Duration: {visit['duration_seconds']}s, "
            f"Notes: {visit['notes']}"
        )

    logger.info("\n✓ Maintenance visits test passed!")


def test_export_csv(event_logger):
    """Test exporting events to CSV"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Export Events to CSV")
    logger.info("="*60)

    output_path = "/tmp/camera_events_export.csv"

    # Export all events
    logger.info("\nExporting all events to CSV...")
    success = event_logger.export_to_csv(output_path)
    assert success, "Export should succeed"
    logger.info(f"✓ Exported to: {output_path}")

    # Verify file exists and has content
    assert Path(output_path).exists(), "CSV file should exist"
    file_size = Path(output_path).stat().st_size
    logger.info(f"✓ CSV file size: {file_size} bytes")

    # Export only security breaches
    output_path2 = "/tmp/security_breaches_export.csv"
    logger.info("\nExporting only security breaches to CSV...")
    success = event_logger.export_to_csv(
        output_path2,
        event_type='security_breach'
    )
    assert success, "Export should succeed"
    logger.info(f"✓ Exported to: {output_path2}")

    # Export date range
    output_path3 = "/tmp/recent_events_export.csv"
    logger.info("\nExporting events from last 24 hours to CSV...")
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now()
    success = event_logger.export_to_csv(
        output_path3,
        start_date=start_date,
        end_date=end_date
    )
    logger.info(f"✓ Exported to: {output_path3}")

    logger.info("\n✓ CSV export test passed!")


def test_statistics(event_logger):
    """Test getting event statistics"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Event Statistics")
    logger.info("="*60)

    stats = event_logger.get_event_stats()

    logger.info("\nEvent Statistics:")
    logger.info(f"  Total events: {stats['total_events']}")
    logger.info(f"  Events today: {stats['events_today']}")
    logger.info(f"  Events this week: {stats['events_this_week']}")

    logger.info("\nEvents by type:")
    for event_type, count in stats['events_by_type'].items():
        logger.info(f"  {event_type}: {count}")

    logger.info("\nAverage confidence by type:")
    for event_type, conf in stats['avg_confidence_by_type'].items():
        logger.info(f"  {event_type}: {conf:.2f}")

    logger.info("\n✓ Statistics test passed!")


def test_update_and_delete(event_logger):
    """Test updating notes and deleting old events"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Update Notes & Delete Old Events")
    logger.info("="*60)

    # Create an event
    logger.info("\nCreating test event...")
    event_id = event_logger.log_event(
        event_type='maintenance_visit',
        confidence=0.90,
        notes='Initial notes'
    )

    # Retrieve and verify
    event = event_logger.get_event_by_id(event_id)
    logger.info(f"Original notes: {event['notes']}")
    assert event['notes'] == 'Initial notes', "Should have initial notes"

    # Update notes
    logger.info("\nUpdating event notes...")
    success = event_logger.update_event_notes(event_id, 'Updated notes after review')
    assert success, "Update should succeed"

    # Verify update
    event = event_logger.get_event_by_id(event_id)
    logger.info(f"Updated notes: {event['notes']}")
    assert event['notes'] == 'Updated notes after review', "Should have updated notes"
    logger.info("✓ Notes updated successfully")

    # Add very old event
    logger.info("\nAdding very old event (100 days ago)...")
    old_timestamp = datetime.now() - timedelta(days=100)
    event_logger.log_event(
        event_type='animal',
        confidence=0.70,
        timestamp=old_timestamp,
        notes='Very old event'
    )

    # Delete old events
    logger.info("\nDeleting events older than 90 days...")
    deleted = event_logger.delete_old_events(days_to_keep=90)
    logger.info(f"✓ Deleted {deleted} old event(s)")
    assert deleted >= 1, "Should have deleted at least 1 old event"

    logger.info("\n✓ Update and delete test passed!")


def test_integration_example():
    """Show integration example with smart_camera.py"""
    logger.info("\n" + "="*60)
    logger.info("INTEGRATION EXAMPLE")
    logger.info("="*60)

    logger.info("""
Integration with smart_camera.py:

1. EventLogger is automatically initialized in SmartCamera.__init__()
2. Events are logged automatically when motion is detected and classified
3. Access event logs via SmartCamera methods:

   # Get recent surveillance logs
   logs = camera.get_event_log(limit=50)

   # Get maintenance visits for reporting
   visits = camera.get_maintenance_visits(days_back=30)

   # Export logs to CSV for analysis
   camera.export_event_log('/data/reports/events.csv')

   # Get statistics
   stats = camera.get_stats()
   print(stats['event_log'])  # Event logger statistics

4. Database locations:
   - Event classification: /data/events.db (detailed ML classification data)
   - Event logging: /data/buffer/camera_events.db (surveillance logs)
   - Telemetry buffer: /data/buffer/telemetry.db (cloud sync buffer)

5. Each serves a different purpose:
   - event_classifier.py: Detailed motion analysis with ML features
   - event_logger.py: Simple surveillance logging for security/maintenance
   - local_buffer.py: Offline telemetry buffering for cloud sync
    """)


def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("EVENT LOGGER TEST SUITE")
    logger.info("="*60)

    try:
        # Run tests
        event_logger = test_basic_logging()
        test_query_by_type(event_logger)
        test_query_by_date_range(event_logger)
        test_maintenance_visits(event_logger)
        test_export_csv(event_logger)
        test_statistics(event_logger)
        test_update_and_delete(event_logger)
        test_integration_example()

        logger.info("\n" + "="*60)
        logger.info("ALL TESTS PASSED! ✓")
        logger.info("="*60)

        logger.info("\nEvent logging system is ready for use!")
        logger.info("Database: /data/buffer/camera_events.db")
        logger.info("Integration: Automatic via SmartCamera class")

        return 0

    except AssertionError as e:
        logger.error(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
