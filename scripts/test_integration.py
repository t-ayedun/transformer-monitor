#!/usr/bin/env python3
"""
Integration Test Script
Tests all components with hardware detection

This script detects whether it's running on a Raspberry Pi
and adjusts tests accordingly.
"""

import sys
import time
import platform
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def is_raspberry_pi():
    """Check if running on Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            return 'BCM' in cpuinfo or 'Raspberry Pi' in cpuinfo
    except:
        return False


def print_status(test_name, passed, skipped=False):
    """Print test status"""
    if skipped:
        status = "⊘ SKIP"
    elif passed:
        status = "✓ PASS"
    else:
        status = "✗ FAIL"
    print(f"{status} - {test_name}")
    return passed


def test_imports():
    """Test that all modules can be imported (with mocking for hardware)"""
    try:
        # Mock hardware modules if not on Raspberry Pi
        if not is_raspberry_pi():
            from unittest.mock import MagicMock
            sys.modules['board'] = MagicMock()
            sys.modules['busio'] = MagicMock()
            sys.modules['adafruit_mlx90640'] = MagicMock()
            sys.modules['picamera2'] = MagicMock()
            sys.modules['picamera2.encoders'] = MagicMock()
            sys.modules['picamera2.outputs'] = MagicMock()

        from config_manager import ConfigManager
        from thermal_capture import ThermalCapture
        from smart_camera import SmartCamera
        from data_processor import DataProcessor
        from local_buffer import LocalBuffer
        from aws_publisher import AWSPublisher
        from error_recovery import ErrorRecoveryManager
        from camera_web_interface import CameraWebInterface

        print_status("Module Imports", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Module Imports: {e}")
        return False


def test_config_manager():
    """Test configuration manager"""
    try:
        from config_manager import ConfigManager

        config = ConfigManager()

        # Test get/set
        config.set('test.value', 123)
        assert config.get('test.value') == 123

        # Test nested get
        config.config = {'nested': {'key': 'value'}}
        assert config.get('nested.key') == 'value'

        print_status("Config Manager", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Config Manager: {e}")
        return False


def test_data_processor():
    """Test data processor"""
    try:
        import numpy as np
        from data_processor import DataProcessor

        # Create test ROIs
        rois = [
            {
                'name': 'test_roi',
                'enabled': True,
                'coordinates': [[0, 0], [10, 10]],
                'weight': 1.0,
                'emissivity': 0.95,
                'thresholds': {
                    'warning': 75.0,
                    'critical': 85.0,
                    'emergency': 95.0
                }
            }
        ]

        composite_config = {
            'enabled': True,
            'method': 'weighted_average'
        }

        processor = DataProcessor(rois, composite_config)

        # Create test thermal frame
        frame = np.random.uniform(20, 80, (24, 32))

        # Process frame
        result = processor.process(frame)

        assert 'regions' in result
        assert 'composite_temperature' in result
        assert len(result['regions']) == 1

        print_status("Data Processor", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Data Processor: {e}")
        return False


def test_local_buffer():
    """Test local buffer"""
    try:
        from local_buffer import LocalBuffer
        import tempfile

        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name

        buffer = LocalBuffer(db_path=db_path, max_size_mb=1)

        # Store data
        test_data = {
            'timestamp': '2025-01-01T00:00:00Z',
            'temperature': 45.5
        }
        buffer.store(test_data)

        # Get unsent data
        unsent = buffer.get_unsent(limit=10)
        assert len(unsent) > 0

        # Cleanup
        buffer.close()
        Path(db_path).unlink()

        print_status("Local Buffer", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Local Buffer: {e}")
        return False


def test_thermal_camera():
    """Test thermal camera (hardware required)"""
    if not is_raspberry_pi():
        print_status("Thermal Camera", False, skipped=True)
        print("  → Hardware test skipped (not on Raspberry Pi)")
        return None  # Skipped

    try:
        import board
        import busio
        import adafruit_mlx90640

        i2c = busio.I2C(board.SCL, board.SDA)
        mlx = adafruit_mlx90640.MLX90640(i2c)
        frame = [0] * 768
        mlx.getFrame(frame)

        result = max(frame) > 0
        print_status("Thermal Camera", result)
        return result
    except Exception as e:
        print(f"✗ FAIL - Thermal Camera: {e}")
        return False


def test_pi_camera():
    """Test Pi Camera (hardware required)"""
    if not is_raspberry_pi():
        print_status("Pi Camera", False, skipped=True)
        print("  → Hardware test skipped (not on Raspberry Pi)")
        return None  # Skipped

    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.start()
        time.sleep(2)
        camera.capture_file("/tmp/test.jpg")
        camera.close()

        result = Path("/tmp/test.jpg").exists()
        print_status("Pi Camera", result)

        # Cleanup
        if result:
            Path("/tmp/test.jpg").unlink()

        return result
    except Exception as e:
        print(f"✗ FAIL - Pi Camera: {e}")
        return False


def test_web_interface():
    """Test web interface initialization"""
    try:
        from camera_web_interface import CameraWebInterface
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.get = Mock(return_value='TEST_SITE')

        # Just test initialization, don't start server
        web = CameraWebInterface(
            smart_camera=None,
            config=mock_config,
            thermal_capture=None,
            data_processor=None,
            port=5000
        )

        print_status("Web Interface Init", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Web Interface Init: {e}")
        return False


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("Transformer Monitor Integration Test")
    print("=" * 60)

    # Detect platform
    on_pi = is_raspberry_pi()
    print(f"\nPlatform: {platform.system()} {platform.machine()}")
    print(f"Raspberry Pi: {'Yes' if on_pi else 'No'}")

    if not on_pi:
        print("\n⚠️  Note: Running on non-Pi system")
        print("   Hardware tests will be skipped")
        print("   For full testing, run on Raspberry Pi 4\n")

    print("=" * 60)

    # Define all tests
    tests = [
        ("Module Imports", test_imports),
        ("Config Manager", test_config_manager),
        ("Data Processor", test_data_processor),
        ("Local Buffer", test_local_buffer),
        ("Web Interface Init", test_web_interface),
        ("Thermal Camera", test_thermal_camera),
        ("Pi Camera", test_pi_camera),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        try:
            result = test_func()
            if result is not None:  # None means skipped
                results.append(result)
        except Exception as e:
            print(f"✗ FAIL - {test_name}: {e}")
            results.append(False)
        time.sleep(0.5)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    print(f"Results: {passed}/{total} tests passed")

    if total < len(tests):
        skipped = len(tests) - total
        print(f"         {skipped} tests skipped (hardware not available)")

    print("=" * 60)

    # Exit with success if all run tests passed
    # Skipped tests don't count as failures
    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
