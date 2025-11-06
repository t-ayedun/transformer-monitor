#!/usr/bin/env python3
"""
Transformer Thermal Monitor - Main Application (TEST MODE)
"""

import os
import sys
import time
import signal
import logging
import logging.config
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from thermal_capture import ThermalCapture
from smart_camera import SmartCamera
from camera_web_interface import CameraWebInterface
from data_processor import DataProcessor
from local_buffer import LocalBuffer
from heartbeat import HeartbeatMonitor
from watchdog import WatchdogTimer
from network_monitor import NetworkMonitor
from storage_manager import StorageManager
from utils.logger import setup_logging


class TransformerMonitor:
    """Main application class"""
    
    def __init__(self):
        self.running = False
        self.config = None
        self.thermal_camera = None
        self.smart_camera = None
        self.camera_web = None
        self.data_processor = None
        self.local_buffer = None
        self.heartbeat = None
        self.watchdog = None
        self.network_monitor = None
        self.storage_manager = None
        self.logger = None
        
    def initialize(self):
        """Initialize all components"""
        print("Initializing Transformer Monitor (TEST MODE)...")
        
        # Setup logging
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*50)
        self.logger.info("Transformer Monitor Starting (TEST MODE)")
        self.logger.info("="*50)
        
        # Load configuration
        self.config = ConfigManager()
        self.config.load_configs()
        self.config.validate()
        
        site_id = self.config.get('site.id', 'UNKNOWN')
        self.logger.info(f"Site ID: {site_id}")
        
        # Initialize local buffer first
        self.logger.info("Initializing local buffer...")
        self.local_buffer = LocalBuffer(
            db_path=self.config.get('local_storage.database_path', '/data/buffer/readings.db'),
            max_size_mb=self.config.get('local_storage.max_size_mb', 500)
        )
        
        # Initialize thermal camera
        self.logger.info("Initializing thermal camera...")
        self.thermal_camera = ThermalCapture(
            i2c_addr=self.config.get('thermal_camera.i2c_address', 0x33),
            i2c_bus=self.config.get('thermal_camera.i2c_bus', 1),
            refresh_rate=self.config.get('thermal_camera.refresh_rate', 8)
        )
        
        # Initialize data processor
        self.logger.info("Initializing data processor...")
        self.data_processor = DataProcessor(
            rois=self.config.get('regions_of_interest'),
            composite_config=self.config.get('composite_temperature')
        )
        
        # Initialize smart camera (if enabled)
        if self.config.get('pi_camera.enabled', False):
            self.logger.info("Initializing smart camera...")
            self.smart_camera = SmartCamera(self.config)
            self.smart_camera.start_monitoring()
            
            # Initialize web interface
            if self.config.get('pi_camera.live_view.enabled', True):
                self.logger.info("Initializing camera web interface...")
                self.camera_web = CameraWebInterface(
                    self.smart_camera,
                    self.config,
                    port=5000
                )
                self.camera_web.start()
        
        # Initialize network monitor
        self.logger.info("Initializing network monitor...")
        self.network_monitor = NetworkMonitor(self.config)
        self.network_monitor.start()
        
        # Initialize storage manager
        self.logger.info("Initializing storage manager...")
        self.storage_manager = StorageManager(self.config)
        self.storage_manager.start()
        
        # Initialize heartbeat monitor
        self.logger.info("Initializing heartbeat monitor...")
        self.heartbeat = HeartbeatMonitor(
            interval=self.config.get('heartbeat.interval', 300),
            aws_publisher=None,  # No AWS for now
            config=self.config
        )
        self.heartbeat.start()
        
        # Initialize watchdog
        self.logger.info("Initializing watchdog timer...")
        self.watchdog = WatchdogTimer()
        self.watchdog.start()
        
        self.logger.info("Initialization complete!")
        
    def run(self):
        """Main monitoring loop"""
        self.running = True
        self.logger.info("Starting monitoring loop (TEST MODE)...")
        
        capture_interval = self.config.get('data_capture.interval', 60)
        
        last_thermal_capture = 0
        capture_count = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # Pet the watchdog
                self.watchdog.pet()
                
                # Thermal capture
                if current_time - last_thermal_capture >= capture_interval:
                    try:
                        self.capture_thermal_data(capture_count)
                        last_thermal_capture = current_time
                        capture_count += 1
                    except Exception as e:
                        self.logger.error(f"Thermal capture failed: {e}", exc_info=True)
                
                # Sleep briefly
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            self.cleanup()
    
    def capture_thermal_data(self, capture_count):
        """Capture and process thermal data"""
        # Capture thermal frame
        thermal_frame = self.thermal_camera.get_frame()
        
        if thermal_frame is None:
            self.logger.warning("Failed to capture thermal frame")
            return
        
        # Process data
        processed_data = self.data_processor.process(thermal_frame)
        
        # Add metadata
        processed_data['site_id'] = self.config.get('site.id')
        processed_data['capture_count'] = capture_count
        processed_data['sensor_temp'] = self.thermal_camera.get_sensor_temp()
        
        # Save to local buffer
        self.local_buffer.store(processed_data)
        
        # Log (since no AWS/FTP/MQTT)
        self.logger.info(
            f"Capture {capture_count}: "
            f"Composite={processed_data.get('composite_temperature', 0):.1f}°C "
            f"(saved to local buffer)"
        )
        
        # Save full frame periodically
        save_interval = self.config.get('data_capture.save_full_frame_interval', 10)
        if capture_count % save_interval == 0:
            self.save_thermal_frame(thermal_frame, processed_data)
    
    def save_thermal_frame(self, frame, metadata):
        """Save full thermal frame to file"""
        import numpy as np
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        site_id = self.config.get('site.id')
        filename = f"{site_id}_thermal_{timestamp}.npy"
        filepath = f"/data/images/{filename}"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        np.save(filepath, frame)
        
        self.logger.debug(f"Saved thermal frame: {filename}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")
        self.running = False
        
        if self.heartbeat:
            self.heartbeat.stop()
        
        if self.watchdog:
            self.watchdog.stop()
        
        if self.network_monitor:
            self.network_monitor.stop()
        
        if self.storage_manager:
            self.storage_manager.stop()
        
        if self.smart_camera:
            self.smart_camera.close()
        
        if self.thermal_camera:
            self.thermal_camera.close()
        
        if self.local_buffer:
            self.local_buffer.close()
        
        self.logger.info("Shutdown complete")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = TransformerMonitor()
    
    try:
        monitor.initialize()
        monitor.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)