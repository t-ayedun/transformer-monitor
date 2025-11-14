#!/usr/bin/env python3
"""
Transformer Thermal Monitor - Main Application
Production-ready edge device for transformer thermal monitoring
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
from data_uploader import DataUploader
from utils.logger import setup_logging

# Optional imports for cloud connectivity
try:
    from aws_publisher import AWSPublisher
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from ftp_publisher import FTPPublisher
    FTP_AVAILABLE = True
except ImportError:
    FTP_AVAILABLE = False


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
        self.aws_publisher = None
        self.ftp_publisher = None
        self.data_uploader = None
        self.logger = None
        self.production_mode = False
        
    def initialize(self):
        """Initialize all components"""
        # Setup logging
        setup_logging()
        self.logger = logging.getLogger(__name__)

        # Load configuration
        self.config = ConfigManager()
        self.config.load_configs()
        self.config.validate()

        # Determine production mode
        self.production_mode = self.config.get('production_mode', False)
        mode_str = "PRODUCTION" if self.production_mode else "DEVELOPMENT"

        print(f"Initializing Transformer Monitor ({mode_str} MODE)...")
        self.logger.info("="*60)
        self.logger.info(f"Transformer Thermal Monitor Starting - {mode_str} MODE")
        self.logger.info("="*60)

        site_id = self.config.get('site.id', 'UNKNOWN')
        site_name = self.config.get('site.name', 'Unknown Site')
        self.logger.info(f"Site ID: {site_id}")
        self.logger.info(f"Site Name: {site_name}")
        self.logger.info(f"Production Mode: {self.production_mode}")
        
        # Initialize local buffer first
        self.logger.info("Initializing local buffer...")
        self.local_buffer = LocalBuffer(
            db_path=self.config.get('local_storage.database_path', '/data/buffer/readings.db'),
            max_size_mb=self.config.get('local_storage.max_size_mb', 500)
        )

        # Initialize AWS publisher (if configured)
        if AWS_AVAILABLE and self.config.get('aws.iot.enabled', False):
            self.logger.info("Initializing AWS IoT publisher...")
            try:
                self.aws_publisher = AWSPublisher(
                    endpoint=self.config.get('aws.iot.endpoint'),
                    thing_name=self.config.get('aws.iot.thing_name'),
                    certs={
                        'ca_cert': self.config.get('aws.iot.certificates.ca_cert'),
                        'device_cert': self.config.get('aws.iot.certificates.device_cert'),
                        'private_key': self.config.get('aws.iot.certificates.private_key')
                    },
                    topics={
                        'telemetry': self.config.get('aws.iot.topics.telemetry'),
                        'heartbeat': self.config.get('aws.iot.topics.heartbeat'),
                        'alerts': self.config.get('aws.iot.topics.alerts',
                                                 f"transformers/{site_id}/alerts"),
                        's3_bucket': self.config.get('aws.s3.bucket')
                    },
                    local_buffer=self.local_buffer,
                    enable_compression=True
                )

                # Connect to AWS IoT
                if self.aws_publisher.connect():
                    self.logger.info("✓ Connected to AWS IoT Core")
                else:
                    self.logger.warning("⚠ Failed to connect to AWS IoT (will retry in background)")

            except Exception as e:
                self.logger.error(f"AWS publisher initialization failed: {e}")
                self.aws_publisher = None
        else:
            if not AWS_AVAILABLE:
                self.logger.info("AWS SDK not available (install AWSIoTPythonSDK)")
            else:
                self.logger.info("AWS IoT disabled in configuration")

        # Initialize FTP publisher (if configured)
        if FTP_AVAILABLE and self.config.get('ftp.enabled', False):
            self.logger.info("Initializing FTP publisher...")
            try:
                self.ftp_publisher = FTPPublisher(
                    host=self.config.get('ftp.host'),
                    username=self.config.get('ftp.username'),
                    password=self.config.get('ftp.password'),
                    remote_dir=self.config.get('ftp.remote_dir'),
                    port=self.config.get('ftp.port', 21),
                    passive=self.config.get('ftp.passive', True)
                )
                self.logger.info("✓ FTP publisher initialized")
            except Exception as e:
                self.logger.error(f"FTP publisher initialization failed: {e}")
                self.ftp_publisher = None
        else:
            if not FTP_AVAILABLE:
                self.logger.info("FTP library not available")
            else:
                self.logger.info("FTP disabled in configuration")

        # Initialize data uploader (orchestrates AWS/FTP uploads)
        self.logger.info("Initializing data uploader...")
        self.data_uploader = DataUploader(
            config=self.config,
            aws_publisher=self.aws_publisher,
            ftp_publisher=self.ftp_publisher,
            local_buffer=self.local_buffer
        )
        self.data_uploader.start()
        self.logger.info("✓ Data uploader started")

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
            self.smart_camera = SmartCamera(self.config, data_uploader=self.data_uploader)
            self.smart_camera.start_monitoring()

            # Initialize web interface
            if self.config.get('pi_camera.live_view.enabled', True):
                self.logger.info("Initializing camera web interface...")
                self.camera_web = CameraWebInterface(
                    smart_camera=self.smart_camera,
                    config=self.config,
                    thermal_capture=self.thermal_camera,
                    data_processor=self.data_processor,
                    data_uploader=self.data_uploader,
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
            aws_publisher=self.aws_publisher,  # Pass AWS publisher for heartbeat
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
        mode_str = "PRODUCTION" if self.production_mode else "DEVELOPMENT"
        self.logger.info(f"Starting monitoring loop ({mode_str} mode)...")
        
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

        # Save to local buffer (always, for redundancy)
        self.local_buffer.store(processed_data)

        # Upload telemetry data to AWS IoT (if available)
        if self.data_uploader:
            self.data_uploader.upload_telemetry(processed_data)

        # Update web interface with thermal frame
        if self.camera_web:
            self.camera_web.update_thermal_frame(thermal_frame, processed_data)

        # Check for alerts
        self._check_temperature_alerts(processed_data)

        # Log composite temperature
        composite_temp = processed_data.get('composite_temperature', 0)
        upload_status = "✓ uploaded" if self.aws_publisher and self.aws_publisher.connected else "○ local only"
        self.logger.info(
            f"Capture {capture_count}: "
            f"Composite={composite_temp:.1f}°C "
            f"({upload_status})"
        )

        # Save and upload full thermal frame periodically
        save_interval = self.config.get('data_capture.save_full_frame_interval', 10)
        if capture_count % save_interval == 0:
            if self.data_uploader:
                self.data_uploader.upload_thermal_frame(thermal_frame, processed_data)
    
    def _check_temperature_alerts(self, processed_data):
        """Check for temperature threshold violations and send alerts"""
        if not self.data_uploader:
            return

        # Check each ROI for threshold violations
        for roi in processed_data.get('regions', []):
            alert_level = roi.get('alert_level')

            if alert_level in ['warning', 'critical', 'emergency']:
                alert_data = {
                    'level': alert_level,
                    'roi_name': roi.get('name'),
                    'temperature': roi.get('max_temp'),
                    'avg_temperature': roi.get('avg_temp'),
                    'threshold_exceeded': True,
                    'message': f"{roi.get('name')}: {roi.get('max_temp'):.1f}°C ({alert_level})"
                }

                # Publish alert
                self.data_uploader.upload_alert(alert_data)

                # Log locally
                if alert_level == 'emergency':
                    self.logger.critical(f"🚨 EMERGENCY ALERT: {alert_data['message']}")
                elif alert_level == 'critical':
                    self.logger.error(f"⚠️  CRITICAL ALERT: {alert_data['message']}")
                else:
                    self.logger.warning(f"⚠️  WARNING ALERT: {alert_data['message']}")

    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")
        self.running = False

        # Stop data uploader first (finish pending uploads)
        if self.data_uploader:
            self.data_uploader.stop()

        # Disconnect from cloud services
        if self.aws_publisher:
            self.aws_publisher.stop()

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