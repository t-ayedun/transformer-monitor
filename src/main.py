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

# New components for simplified architecture
from aws_iot_config import AWSIoTConfig
from aws_publisher import AWSPublisher
from ftp_publisher import FTPPublisher
from media_uploader import MediaUploader
from thermal_image_generator import ThermalImageGenerator


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
        
        # New components
        self.aws_iot_config = None
        self.aws_publisher = None
        self.ftp_publisher = None
        self.media_uploader = None
        self.thermal_image_gen = None
        self.last_thermal_image_time = 0
        
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
            composite_config=self.config.get('composite_temperature'),
            transformer_detection_config=self.config.get('transformer_detection', {})
        )
        
        # Initialize FTP publisher (if configured)
        ftp_enabled = self.config.get('ftp.enabled', False)
        if ftp_enabled:
            self.logger.info("FTP enabled, initializing publisher...")
            try:
                # Get password from env var or config
                ftp_password = os.getenv('FTP_PASSWORD') or self.config.get('ftp.password', '')
                
                self.ftp_publisher = FTPPublisher(
                    host=self.config.get('ftp.host'),
                    username=self.config.get('ftp.username'),
                    password=ftp_password,
                    remote_dir=self.config.get('ftp.remote_dir', '/transformer-data'),
                    port=self.config.get('ftp.port', 21),
                    passive=self.config.get('ftp.passive_mode', True)
                )
                
                # Initialize media uploader
                self.media_uploader = MediaUploader(self.ftp_publisher, self.config)
                self.media_uploader.start()
            except Exception as e:
                self.logger.error(f"Failed to initialize FTP publisher: {e}")
                self.ftp_publisher = None
                self.media_uploader = None
        else:
            self.logger.info("FTP disabled or not configured")

        # Initialize smart camera (if enabled)
        if self.config.get('pi_camera.enabled', False):
            self.logger.info("Initializing smart camera...")
            self.smart_camera = SmartCamera(self.config, media_uploader=self.media_uploader)
            self.smart_camera.start_monitoring()
            
            # Initialize web interface
            if self.config.get('pi_camera.live_view.enabled', True):
                self.logger.info("Initializing camera web interface...")
                self.camera_web = CameraWebInterface(
                    smart_camera=self.smart_camera,
                    config=self.config,
                    thermal_capture=self.thermal_camera,
                    data_processor=self.data_processor,
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
        
        # Initialize AWS IoT (if configured)
        self.logger.info("Checking AWS IoT configuration...")
        self.aws_iot_config = AWSIoTConfig(self.config)
        
        if self.aws_iot_config.is_enabled():
            self.logger.info("AWS IoT enabled, initializing publisher...")
            try:
                conn_params = self.aws_iot_config.get_connection_params()
                self.aws_publisher = AWSPublisher(
                    endpoint=conn_params['endpoint'],
                    thing_name=conn_params['thing_name'],
                    certs=conn_params['certs'],
                    topics=conn_params['topics'],
                    local_buffer=self.local_buffer,
                    enable_compression=conn_params['enable_compression']
                )
                self.aws_publisher.max_bytes_per_second = conn_params['bandwidth_limit_kbps'] * 1024
                self.aws_publisher.connect()
            except Exception as e:
                self.logger.error(f"Failed to initialize AWS publisher: {e}")
                self.aws_publisher = None
        else:
            self.logger.info("AWS IoT disabled or not configured")
        

        
        # Initialize thermal image generator
        self.logger.info("Initializing thermal image generator...")
        colormap = self.config.get('media.thermal_images.colormap', 'hot')
        resolution = tuple(self.config.get('media.thermal_images.resolution', [640, 480]))
        self.thermal_image_gen = ThermalImageGenerator(colormap=colormap, output_resolution=resolution)
        
        # Initialize heartbeat monitor
        self.logger.info("Initializing heartbeat monitor...")
        self.heartbeat = HeartbeatMonitor(
            interval=self.config.get('heartbeat.interval', 300),
            aws_publisher=self.aws_publisher,
            ftp_publisher=self.ftp_publisher,  # Pass FTP publisher
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
        
        # Detect hotspots
        hotspots = self.thermal_camera.detect_hotspots(thermal_frame)
        if hotspots:
            processed_data['hotspots'] = hotspots
        
        # Save to local buffer
        self.local_buffer.store(processed_data)

        # Publish to AWS IoT via MQTT (if enabled)
        if self.aws_publisher:
            try:
                telemetry_payload = self._format_telemetry_payload(processed_data)
                self.aws_publisher.publish_telemetry(telemetry_payload)
            except Exception as e:
                self.logger.error(f"Failed to publish telemetry: {e}")
        
        # Upload to FTP (if enabled)
        if self.ftp_publisher:
            try:
                telemetry_payload = self._format_telemetry_payload(processed_data)
                self.ftp_publisher.upload_telemetry_data(telemetry_payload)
            except Exception as e:
                self.logger.error(f"Failed to queue telemetry for FTP: {e}")

        # Update web interface with thermal frame
        if self.camera_web:
            self.camera_web.update_thermal_frame(thermal_frame, processed_data)

        # Generate and upload thermal image (if configured)
        current_time = time.time()
        thermal_image_interval = self.config.get('ftp.thermal_image_interval', 600)
        upload_on_alert = self.config.get('ftp.upload_on_alert', True)
        
        # Check if we should generate thermal image
        should_generate = False
        is_priority = False
        
        # Check interval
        if current_time - self.last_thermal_image_time >= thermal_image_interval:
            should_generate = True
        
        # Check for alerts
        if upload_on_alert and processed_data.get('regions'):
            for region in processed_data['regions']:
                alert_level = region.get('alert_level', 'normal')
                if alert_level in ['warning', 'critical', 'emergency']:
                    should_generate = True
                    is_priority = True
                    break
        
        if should_generate and self.thermal_image_gen and self.media_uploader:
            try:
                # Generate thermal image
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                site_id = self.config.get('site.id', 'UNKNOWN')
                filename = f"{site_id}_thermal_{timestamp}.png"
                filepath = f"/data/images/thermal/{filename}"
                
                # Ensure directory exists
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                
                # Generate image with annotations
                rois = self.config.get('regions_of_interest', [])
                metadata = {
                    'site_id': site_id,
                    'timestamp': processed_data.get('timestamp')
                }
                
                success = self.thermal_image_gen.generate_and_save(
                    thermal_frame,
                    filepath,
                    rois=rois,
                    hotspots=hotspots,
                    metadata=metadata
                )
                
                if success:
                    # Queue for FTP upload
                    self.media_uploader.queue_thermal_image(
                        filepath,
                        metadata,
                        priority=is_priority
                    )
                    self.last_thermal_image_time = current_time
                    
            except Exception as e:
                self.logger.error(f"Failed to generate/upload thermal image: {e}")

        # Log
        comp_temp = processed_data.get('composite_temperature') or 0
        status_parts = [f"Capture {capture_count}: Composite={comp_temp:.1f}°C"]
        
        if self.aws_publisher and self.aws_publisher.connected:
            status_parts.append("[AWS: ✓]")
        else:
            status_parts.append("[Local only]")
        
        self.logger.info(" ".join(status_parts))

        # Save full frame periodically (for debugging/analysis)
        save_interval = self.config.get('data_capture.save_full_frame_interval', 10)
        if capture_count % save_interval == 0:
            self.save_thermal_frame(thermal_frame, processed_data)
    
    def _format_telemetry_payload(self, processed_data: Dict) -> Dict:
        """Format telemetry data for MQTT publishing (optimized payload)"""
        payload = {
            'timestamp': processed_data.get('timestamp'),
            'site_id': processed_data.get('site_id'),
            'device_type': 'thermal',
            'data': {
                'sensor_temp': processed_data.get('sensor_temp'),
                'frame_stats': processed_data.get('frame_stats', {})
            }
        }
        
        # Add transformer detection data (new)
        if processed_data.get('transformer_region'):
            transformer = processed_data['transformer_region']
            payload['data']['transformer'] = {
                'min_temp': transformer.get('min_temp'),
                'max_temp': transformer.get('max_temp'),
                'avg_temp': transformer.get('avg_temp'),
                'q1_temp': transformer.get('q1_temp'),
                'q3_temp': transformer.get('q3_temp'),
                'detection_confidence': transformer.get('detection_confidence')
            }
        else:
            # Legacy: use composite temperature
            payload['data']['composite_temp'] = processed_data.get('composite_temperature')
        
        # Add ROI data (simplified)
        if processed_data.get('regions'):
            payload['data']['hotspots'] = []
            for region in processed_data['regions']:
                payload['data']['hotspots'].append({
                    'roi': region.get('name'),
                    'min': region.get('min_temp'),
                    'max': region.get('max_temp'),
                    'avg': region.get('avg_temp'),
                    'alert': region.get('alert_level', 'normal')
                })
        
        # Add detected hotspots average
        if processed_data.get('hotspots'):
            hotspot_temps = [h.get('max_temp', 0) for h in processed_data['hotspots']]
            if hotspot_temps:
                payload['data']['hotspot_avg'] = sum(hotspot_temps) / len(hotspot_temps)
        
        return payload
    
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
        
        # Stop media uploader
        if self.media_uploader:
            self.media_uploader.stop()
        
        # Disconnect AWS publisher
        if self.aws_publisher:
            self.aws_publisher.stop()
        
        # Close FTP publisher
        if self.ftp_publisher:
            self.ftp_publisher.close()
        
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