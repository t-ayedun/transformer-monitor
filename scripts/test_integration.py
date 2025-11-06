#!/usr/bin/env python3
"""
Integration Test Script
Tests all components
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def print_status(test_name, passed):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status} - {test_name}")
    return passed


def test_imports():
    """Test that all modules can be imported"""
    try:
        from config_manager import ConfigManager
        from thermal_capture import ThermalCapture
        from smart_camera import SmartCamera
        from data_processor import DataProcessor
        from local_buffer import LocalBuffer
        print_status("Module Imports", True)
        return True
    except Exception as e:
        print(f"✗ FAIL - Module Imports: {e}")
        return False


def test_thermal_camera():
    """Test thermal camera"""
    try:
        import board
        import busio
        import adafruit_mlx90640
        
        i2c = busio.I2C(board.SCL, board.SDA)
        mlx = adafruit_mlx90640.MLX90640(i2c)
        frame = [0] * 768
        mlx.getFrame(frame)
        
        return print_status("Thermal Camera", max(frame) > 0)
    except Exception as e:
        print(f"✗ FAIL - Thermal Camera: {e}")
        return False


def test_pi_camera():
    """Test Pi Camera"""
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.start()
        time.sleep(2)
        camera.capture_file("/tmp/test.jpg")
        camera.close()
        
        return print_status("Pi Camera", Path("/tmp/test.jpg").exists())
    except Exception as e:
        print(f"✗ FAIL - Pi Camera: {e}")
        return False


def main():
    print("=" * 50)
    print("Transformer Monitor Integration Test")
    print("=" * 50)
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("Thermal Camera", test_thermal_camera),
        ("Pi Camera", test_pi_camera),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        try:
            results.append(test_func())
        except Exception as e:
            print(f"✗ FAIL - {test_name}: {e}")
            results.append(False)
        time.sleep(1)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 50)
    
    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()