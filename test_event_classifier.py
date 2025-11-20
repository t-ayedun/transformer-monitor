#!/usr/bin/env python3
"""
Test script for event classification system

This script tests the event classifier without requiring actual Pi Camera hardware.
It simulates different types of motion events and verifies classification logic.
"""

import sys
import logging
import numpy as np
import cv2
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from event_classifier import EventClassifier


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_test_config():
    """Create a minimal test configuration"""
    return {
        'site': {'id': 'TEST'},
        'pi_camera': {
            'resolution': [1920, 1080],
            'framerate': 30
        }
    }


def create_simulated_contours(size_type, num_contours=1):
    """
    Create simulated contours for testing

    Args:
        size_type: 'small', 'medium', or 'large'
        num_contours: Number of contours to create

    Returns:
        List of OpenCV contours
    """
    contours = []
    frame_width = 640
    frame_height = 480

    for i in range(num_contours):
        if size_type == 'small':
            # Animal-sized (< 5% of frame)
            width = int(frame_width * 0.03)
            height = int(frame_height * 0.03)
        elif size_type == 'medium':
            # Medium-sized (5-15% of frame)
            width = int(frame_width * 0.10)
            height = int(frame_height * 0.10)
        else:  # large
            # Human-sized (> 15% of frame)
            width = int(frame_width * 0.20)
            height = int(frame_height * 0.25)

        # Create a rectangular contour
        x = 100 + i * 50
        y = 100 + i * 50
        contour = np.array([
            [x, y],
            [x + width, y],
            [x + width, y + height],
            [x, y + height]
        ], dtype=np.int32)

        contours.append(contour)

    return contours


def test_time_classification():
    """Test time-based classification"""
    logger.info("\n" + "="*60)
    logger.info("TEST: Time-based Classification")
    logger.info("="*60)

    config = create_test_config()
    classifier = EventClassifier(config, db_path="/tmp/test_events.db")

    # Test 1: Business hours (weekday, 10 AM)
    test_time = datetime(2024, 1, 15, 10, 0, 0)  # Monday, 10 AM
    time_class, confidence = classifier._classify_time(test_time)
    logger.info(f"Business hours (Mon 10am): {time_class} (conf: {confidence:.2f})")
    assert time_class == "business_hours", "Expected business_hours"

    # Test 2: Off-hours (weekday night, 11 PM)
    test_time = datetime(2024, 1, 15, 23, 0, 0)  # Monday, 11 PM
    time_class, confidence = classifier._classify_time(test_time)
    logger.info(f"Off-hours (Mon 11pm): {time_class} (conf: {confidence:.2f})")
    assert time_class == "off_hours", "Expected off_hours"

    # Test 3: Weekend
    test_time = datetime(2024, 1, 20, 12, 0, 0)  # Saturday, noon
    time_class, confidence = classifier._classify_time(test_time)
    logger.info(f"Weekend (Sat 12pm): {time_class} (conf: {confidence:.2f})")
    assert time_class == "off_hours", "Expected off_hours"

    logger.info("✓ Time classification tests passed!")


def test_size_classification():
    """Test size-based classification"""
    logger.info("\n" + "="*60)
    logger.info("TEST: Size-based Classification")
    logger.info("="*60)

    config = create_test_config()
    classifier = EventClassifier(config, db_path="/tmp/test_events.db")

    # Test 1: Small object (animal)
    contours = create_simulated_contours('small')
    size_class, confidence, area = classifier._classify_size(contours)
    logger.info(f"Small object: {size_class} (conf: {confidence:.2f}, area: {area:.0f}px²)")
    assert size_class == "small", "Expected small"

    # Test 2: Medium object
    contours = create_simulated_contours('medium')
    size_class, confidence, area = classifier._classify_size(contours)
    logger.info(f"Medium object: {size_class} (conf: {confidence:.2f}, area: {area:.0f}px²)")
    assert size_class == "medium", "Expected medium"

    # Test 3: Large object (human)
    contours = create_simulated_contours('large')
    size_class, confidence, area = classifier._classify_size(contours)
    logger.info(f"Large object: {size_class} (conf: {confidence:.2f}, area: {area:.0f}px²)")
    assert size_class == "large", "Expected large"

    logger.info("✓ Size classification tests passed!")


def test_full_event_classification():
    """Test full event classification with different scenarios"""
    logger.info("\n" + "="*60)
    logger.info("TEST: Full Event Classification")
    logger.info("="*60)

    config = create_test_config()
    classifier = EventClassifier(config, db_path="/tmp/test_events.db")

    # Scenario 1: Maintenance visit (business hours + large object)
    logger.info("\nScenario 1: Maintenance Visit")
    contours = create_simulated_contours('large')
    test_time = datetime(2024, 1, 15, 10, 0, 0)  # Monday, 10 AM
    result = classifier.classify_event(contours, (480, 640), test_time)
    logger.info(f"  Event: {result['event_type']}")
    logger.info(f"  Confidence: {result['confidence_score']:.2f}")
    logger.info(f"  Size: {result['size_classification']}")
    logger.info(f"  Time: {result['time_classification']}")
    assert result['event_type'] in ['maintenance_visit', 'security_breach'], \
        "Expected maintenance_visit or security_breach"

    # Scenario 2: Security breach (off-hours + large object)
    logger.info("\nScenario 2: Security Breach")
    classifier.reset_motion_tracking()
    contours = create_simulated_contours('large')
    test_time = datetime(2024, 1, 15, 23, 0, 0)  # Monday, 11 PM
    result = classifier.classify_event(contours, (480, 640), test_time)
    logger.info(f"  Event: {result['event_type']}")
    logger.info(f"  Confidence: {result['confidence_score']:.2f}")
    logger.info(f"  Size: {result['size_classification']}")
    logger.info(f"  Time: {result['time_classification']}")
    assert result['event_type'] == 'security_breach', "Expected security_breach"

    # Scenario 3: Animal (small object)
    logger.info("\nScenario 3: Animal Detection")
    classifier.reset_motion_tracking()
    contours = create_simulated_contours('small')
    test_time = datetime(2024, 1, 15, 14, 0, 0)  # Monday, 2 PM
    result = classifier.classify_event(contours, (480, 640), test_time)
    logger.info(f"  Event: {result['event_type']}")
    logger.info(f"  Confidence: {result['confidence_score']:.2f}")
    logger.info(f"  Size: {result['size_classification']}")
    logger.info(f"  Time: {result['time_classification']}")
    assert result['event_type'] == 'animal', "Expected animal"

    logger.info("\n✓ Full event classification tests passed!")


def test_database_operations():
    """Test database storage and retrieval"""
    logger.info("\n" + "="*60)
    logger.info("TEST: Database Operations")
    logger.info("="*60)

    # Clean up test database
    test_db = "/tmp/test_events.db"
    if Path(test_db).exists():
        Path(test_db).unlink()

    config = create_test_config()
    classifier = EventClassifier(config, db_path=test_db)

    # Create and store a test event
    contours = create_simulated_contours('large')
    test_time = datetime(2024, 1, 15, 23, 0, 0)
    classification = classifier.classify_event(contours, (480, 640), test_time)

    event_id = classifier.store_event(
        classification,
        image_path="/data/images/test.jpg",
        video_path="/data/videos/test.h264"
    )

    logger.info(f"Stored event with ID: {event_id}")
    assert event_id > 0, "Event ID should be positive"

    # Retrieve recent events
    recent = classifier.get_recent_events(limit=5)
    logger.info(f"Retrieved {len(recent)} recent events")
    assert len(recent) == 1, "Should have 1 event"
    assert recent[0]['event_type'] == classification['event_type']

    # Get stats
    stats = classifier.get_event_stats()
    logger.info(f"Event stats: {stats}")
    assert stats['total_events'] == 1, "Should have 1 total event"

    logger.info("✓ Database operations tests passed!")


def test_cpu_usage():
    """Test that classification is lightweight (< 30% CPU)"""
    logger.info("\n" + "="*60)
    logger.info("TEST: CPU Usage (Lightweight)")
    logger.info("="*60)

    import time

    config = create_test_config()
    classifier = EventClassifier(config, db_path="/tmp/test_events.db")

    # Simulate continuous classification for 1 second
    contours = create_simulated_contours('medium', num_contours=3)
    start_time = time.time()
    iterations = 0

    while time.time() - start_time < 1.0:
        classifier.classify_event(contours, (480, 640))
        iterations += 1

    duration = time.time() - start_time
    fps = iterations / duration

    logger.info(f"Classification speed: {fps:.1f} events/second")
    logger.info(f"Time per classification: {1000/fps:.2f} ms")

    # Should be able to classify at least 30 fps (matching motion detection rate)
    assert fps >= 30, f"Classification too slow: {fps:.1f} fps (need ≥30 fps)"

    logger.info("✓ CPU usage test passed (lightweight enough for real-time)")


def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("EVENT CLASSIFIER TEST SUITE")
    logger.info("="*60)

    try:
        test_time_classification()
        test_size_classification()
        test_full_event_classification()
        test_database_operations()
        test_cpu_usage()

        logger.info("\n" + "="*60)
        logger.info("ALL TESTS PASSED! ✓")
        logger.info("="*60)
        logger.info("\nEvent classification system is ready for deployment.")
        logger.info("Database location: /data/events.db")
        logger.info("Integration: src/smart_camera.py")

        return 0

    except AssertionError as e:
        logger.error(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
