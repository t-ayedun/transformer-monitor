#!/usr/bin/env python3
"""
Field Calibration Tool
Helps calibrate thermal camera against contact thermometer readings
"""

import sys
import time
import argparse
from pathlib import Path
import yaml
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from thermal_capture import ThermalCapture
from data_processor import DataProcessor


def load_config():
    """Load site configuration"""
    config_path = Path('/data/config/site_config.yaml')
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / 'config' / 'site_config.template.yaml'
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def capture_reference_reading(thermal_camera, roi_processor, contact_temp, num_samples=10):
    """
    Capture thermal readings and compare with contact thermometer
    
    Args:
        thermal_camera: ThermalCapture instance
        roi_processor: DataProcessor instance
        contact_temp: Temperature from contact thermometer
        num_samples: Number of samples to average
    """
    print(f"\nCapturing {num_samples} thermal readings...")
    thermal_readings = []
    
    for i in range(num_samples):
        frame = thermal_camera.get_frame()
        if frame is not None:
            # Process frame
            data = roi_processor.process(frame)
            
            # Get max temp from main ROI (usually full_frame or specific area)
            main_roi = data['regions'][0]  # First ROI
            thermal_readings.append(main_roi['max_temp'])
            
            print(f"  Sample {i+1}/{num_samples}: {main_roi['max_temp']:.2f}°C")
            time.sleep(1)
        else:
            print(f"  Sample {i+1}/{num_samples}: Failed to capture")
    
    if not thermal_readings:
        print("ERROR: No valid thermal readings captured")
        return None
    
    thermal_avg = np.mean(thermal_readings)
    thermal_std = np.std(thermal_readings)
    
    print(f"\nResults:")
    print(f"  Contact thermometer: {contact_temp:.2f}°C")
    print(f"  Thermal camera avg:  {thermal_avg:.2f}°C")
    print(f"  Standard deviation:  {thermal_std:.2f}°C")
    print(f"  Difference:          {thermal_avg - contact_temp:.2f}°C")
    
    return {
        'contact_temp': contact_temp,
        'thermal_avg': thermal_avg,
        'thermal_std': thermal_std,
        'difference': thermal_avg - contact_temp
    }


def calculate_calibration(measurements):
    """
    Calculate calibration offset and multiplier from multiple measurements
    
    Args:
        measurements: List of measurement dictionaries
    """
    if len(measurements) < 2:
        print("ERROR: Need at least 2 measurements for calibration")
        return None
    
    # Extract data
    contact_temps = [m['contact_temp'] for m in measurements]
    thermal_temps = [m['thermal_avg'] for m in measurements]
    
    # Linear regression: contact = multiplier * thermal + offset
    # Using numpy polyfit (degree 1 for linear)
    coeffs = np.polyfit(thermal_temps, contact_temps, 1)
    multiplier, offset = coeffs
    
    print("\n" + "="*50)
    print("CALIBRATION RESULTS")
    print("="*50)
    print(f"Offset:     {offset:+.2f}°C")
    print(f"Multiplier: {multiplier:.4f}")
    print()
    print("Corrected formula:")
    print(f"  T_actual = {multiplier:.4f} * T_measured {offset:+.2f}")
    print()
    
    # Verify calibration
    print("Verification:")
    for i, m in enumerate(measurements):
        corrected = multiplier * m['thermal_avg'] + offset
        error = corrected - m['contact_temp']
        print(f"  Point {i+1}: {m['contact_temp']:.1f}°C → "
              f"{corrected:.1f}°C (error: {error:+.2f}°C)")
    
    return {
        'offset': float(offset),
        'multiplier': float(multiplier)
    }


def main():
    parser = argparse.ArgumentParser(description='Thermal Camera Calibration Tool')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive mode (prompt for each measurement)')
    parser.add_argument('--measurements', type=int, default=3,
                       help='Number of calibration points (default: 3)')
    args = parser.parse_args()
    
    print("="*50)
    print("THERMAL CAMERA CALIBRATION TOOL")
    print("="*50)
    print()
    print("This tool helps calibrate the MLX90640 thermal camera")
    print("against contact thermometer readings.")
    print()
    print("You will need:")
    print("  1. Contact thermometer (infrared or probe)")
    print("  2. Access to transformer at various temperatures")
    print("  3. Stable measurement conditions")
    print()
    
    # Load config
    print("Loading configuration...")
    config = load_config()
    
    # Initialize thermal camera
    print("Initializing thermal camera...")
    thermal_config = config['thermal_camera']
    thermal_camera = ThermalCapture(
        i2c_addr=thermal_config['i2c_address'],
        i2c_bus=thermal_config['i2c_bus'],
        refresh_rate=thermal_config['refresh_rate']
    )
    
    # Initialize data processor
    roi_processor = DataProcessor(
        rois=config['regions_of_interest'],
        composite_config=config['composite_temperature']
    )
    
    print("Camera ready!")
    print()
    
    # Collect measurements
    measurements = []
    
    for i in range(args.measurements):
        print(f"\n{'='*50}")
        print(f"MEASUREMENT {i+1}/{args.measurements}")
        print('='*50)
        
        if args.interactive:
            input("Position contact thermometer on measurement point and press Enter...")
        
        # Get contact temperature
        while True:
            try:
                contact_temp_str = input("Enter contact thermometer reading (°C): ")
                contact_temp = float(contact_temp_str)
                if 0 <= contact_temp <= 200:
                    break
                else:
                    print("Temperature should be between 0 and 200°C")
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        # Capture thermal reading
        result = capture_reference_reading(thermal_camera, roi_processor, contact_temp)
        
        if result:
            measurements.append(result)
            print(f"\n✓ Measurement {i+1} recorded")
        else:
            print(f"\n✗ Measurement {i+1} failed")
            retry = input("Retry this measurement? (y/n): ")
            if retry.lower() == 'y':
                i -= 1  # Repeat this measurement
    
    # Calculate calibration
    if len(measurements) >= 2:
        calibration = calculate_calibration(measurements)
        
        if calibration:
            print("\n" + "="*50)
            print("SAVE CALIBRATION")
            print("="*50)
            
            save = input("\nSave calibration to config? (y/n): ")
            
            if save.lower() == 'y':
                # Update config
                config_path = Path('/data/config/site_config.yaml')
                
                config['thermal_camera']['calibration']['enabled'] = True
                config['thermal_camera']['calibration']['offset'] = calibration['offset']
                config['thermal_camera']['calibration']['multiplier'] = calibration['multiplier']
                
                with open(config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
                
                print(f"\n✓ Calibration saved to {config_path}")
                print("\nRestart the application for changes to take effect:")
                print("  balena restart <device-uuid>")
            else:
                print("\nCalibration NOT saved. To apply manually:")
                print(f"  thermal_camera.calibration.enabled: true")
                print(f"  thermal_camera.calibration.offset: {calibration['offset']:.2f}")
                print(f"  thermal_camera.calibration.multiplier: {calibration['multiplier']:.4f}")
    
    # Cleanup
    thermal_camera.close()
    print("\nCalibration complete!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCalibration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)