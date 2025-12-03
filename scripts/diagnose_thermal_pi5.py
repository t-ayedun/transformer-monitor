#!/usr/bin/env python3
"""
Diagnostic script for MLX90640 thermal camera on Pi 5
Tests different approaches to fix the "Too many retries" error
"""

import sys
import time
import board
import busio

print("=" * 60)
print("MLX90640 Pi 5 Diagnostic Tool")
print("=" * 60)

# Test 1: Check I2C bus
print("\n[Test 1] Checking I2C bus...")
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    print("✓ I2C bus initialized at 400kHz")
except Exception as e:
    print(f"✗ I2C initialization failed: {e}")
    sys.exit(1)

# Test 2: Detect MLX90640
print("\n[Test 2] Detecting MLX90640 at 0x33...")
try:
    import adafruit_mlx90640
    mlx = adafruit_mlx90640.MLX90640(i2c)
    print("✓ MLX90640 detected and initialized")
except Exception as e:
    print(f"✗ MLX90640 detection failed: {e}")
    sys.exit(1)

# Test 3: Set refresh rate
print("\n[Test 3] Setting refresh rate...")
try:
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ  # Slower for Pi 5
    print("✓ Refresh rate set to 2 Hz (slower for Pi 5)")
except Exception as e:
    print(f"⚠ Refresh rate setting failed: {e}")

# Test 4: Attempt frame capture with different strategies
print("\n[Test 4] Testing frame capture strategies...")

strategies = [
    ("Standard (no delay)", 0),
    ("Short delay (0.5s)", 0.5),
    ("Medium delay (1.0s)", 1.0),
    ("Long delay (2.0s)", 2.0),
]

for strategy_name, delay in strategies:
    print(f"\n  Strategy: {strategy_name}")
    frame = [0] * 768
    
    for attempt in range(3):
        try:
            if delay > 0 and attempt > 0:
                time.sleep(delay)
            
            mlx.getFrame(frame)
            
            # Quick validation
            import numpy as np
            frame_array = np.array(frame, dtype=np.float32).reshape(24, 32)
            temp_min = frame_array.min()
            temp_max = frame_array.max()
            
            if -40 < temp_min < 300 and -40 < temp_max < 300:
                print(f"    ✓ SUCCESS on attempt {attempt + 1}")
                print(f"      Temperature range: {temp_min:.1f}°C to {temp_max:.1f}°C")
                break
            else:
                print(f"    ⚠ Invalid data on attempt {attempt + 1}")
        except RuntimeError as e:
            if "Too many retries" in str(e):
                print(f"    ✗ 'Too many retries' error on attempt {attempt + 1}")
            else:
                print(f"    ✗ RuntimeError on attempt {attempt + 1}: {e}")
        except Exception as e:
            print(f"    ✗ Error on attempt {attempt + 1}: {e}")
    else:
        print(f"    ✗ FAILED after 3 attempts")

# Test 5: Check if lowering I2C frequency helps
print("\n[Test 5] Testing with lower I2C frequency (100kHz)...")
try:
    i2c_slow = busio.I2C(board.SCL, board.SDA, frequency=100000)
    mlx_slow = adafruit_mlx90640.MLX90640(i2c_slow)
    mlx_slow.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_1_HZ
    
    frame = [0] * 768
    time.sleep(2)  # Give it time to stabilize
    mlx_slow.getFrame(frame)
    
    import numpy as np
    frame_array = np.array(frame, dtype=np.float32).reshape(24, 32)
    print(f"✓ SUCCESS with slow I2C!")
    print(f"  Temperature range: {frame_array.min():.1f}°C to {frame_array.max():.1f}°C")
    print("\n  RECOMMENDATION: Use 100kHz I2C frequency and 1-2 Hz refresh rate on Pi 5")
except Exception as e:
    print(f"✗ Slow I2C also failed: {e}")

print("\n" + "=" * 60)
print("Diagnostic complete. Check results above.")
print("=" * 60)
