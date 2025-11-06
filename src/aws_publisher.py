"""
AWS IoT Publisher
Handles MQTT publishing to AWS IoT Core and S3 uploads
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any
from threading import Thread, Lock

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import boto3
from botocore.exceptions import ClientError


class AWSPublisher:
    """Publishes data to AWS IoT Core and S3"""
    
    def __init__(self, endpoint: str, thing_name: str, certs: Dict,
                 topics: Dict, local_buffer=None):
        self.logger = logging.getLogger(__name__)
        self.endpoint = endpoint
        self.thing_name = thing_name
        self.certs = certs
        self.topics = topics
        self.local_buffer = local_buffer
        
        self.mqtt_client = None
        self.s3_client = None
        self.connected = False
        self.connection_lock = Lock()
        
        self._init_mqtt_client()
        self._init_s3_client()
    
    def _init_mqtt_client(self):
        """Initialize MQTT client"""
        try:
            self.mqtt_client = AWSIoTMQTTClient(self.thing_name)
            self.mqtt_client.configureEndpoint(self.endpoint, 8883)
            
            self.mqtt_client.configureCredentials(
                self.certs['ca_cert'],
                self.certs['private_key'],
                self.certs['device_cert']
            )
            
            # Connection configuration
            self.mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
            self.mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite
            self.mqtt_client.configureDrainingFrequency(2)  # 2 Hz
            self.mqtt_client.configureConnectDisconnectTimeout(10)
            self.mqtt_client.configureMQTTOperationTimeout(5)
            
            self.logger.info("MQTT client initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MQTT client: {e}")
            raise
    
    def _init_s3_client(self):
        """Initialize S3 client using IoT credentials"""
        try:
            # Note: In production, use IoT credentials provider or instance profile
            # For now, we'll use certificate-based auth only for MQTT
            # S3 uploads can be done via presigned URLs or separate IAM role
            self.s3_client = boto3.client('s3')
            self.logger.info("S3 client initialized")
        except Exception as e:
            self.logger.warning(f"S3 client initialization failed: {e}")
            self.s3_client = None
    
    def connect(self, max_retries=3):
        """Connect to AWS IoT Core"""
        for attempt in range(max_retries):
            try:
                with self.connection_lock:
                    if self.connected:
                        return True
                    
                    self.logger.info(f"Connecting to AWS IoT (attempt {attempt + 1})...")
                    self.mqtt_client.connect()
                    self.connected = True
                    self.logger.info("Connected to AWS IoT Core")
                    
                    # Start buffered data upload in background
                    if self.local_buffer:
                        Thread(target=self._upload_buffered_data, daemon=True).start()
                    
                    return True
                    
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                time.sleep(5 * (attempt + 1))
        
        self.logger.error("Failed to connect after retries")
        return False
    
    def disconnect(self):
        """Disconnect from AWS IoT"""
        with self.connection_lock:
            if self.connected:
                try:
                    self.mqtt_client.disconnect()
                    self.connected = False
                    self.logger.info("Disconnected from AWS IoT")
                except Exception as e:
                    self.logger.error(f"Disconnect error: {e}")
    
    def publish_telemetry(self, data: Dict[str, Any]) -> bool:
        """Publish telemetry data to AWS IoT"""
        if not self.connected:
            self.logger.warning("Not connected, buffering data locally")
            if self.local_buffer:
                self.local_buffer.store(data)
            return False
        
        try:
            topic = self.topics['telemetry']
            payload = json.dumps(data)
            
            self.mqtt_client.publish(topic, payload, 1)  # QoS 1
            self.logger.debug(f"Published telemetry to {topic}")
            return True
            
        except Exception as e:
            self.logger.error(f"Publish failed: {e}")
            if self.local_buffer:
                self.local_buffer.store(data)
            return False
    
    def publish_heartbeat(self, data: Dict[str, Any]) -> bool:
        """Publish heartbeat message"""
        if not self.connected:
            return False
        
        try:
            topic = self.topics['heartbeat']
            payload = json.dumps(data)
            
            self.mqtt_client.publish(topic, payload, 0)  # QoS 0 for heartbeat
            self.logger.debug("Published heartbeat")
            return True
            
        except Exception as e:
            self.logger.error(f"Heartbeat publish failed: {e}")
            return False
    
    def upload_image(self, filepath: str, image_type: str, 
                    metadata: Dict = None) -> bool:
        """Upload image to S3"""
        if not self.s3_client:
            self.logger.warning("S3 client not available")
            return False
        
        try:
            # Construct S3 key
            filename = Path(filepath).name
            s3_key = f"images/{image_type}/{filename}"
            
            # Prepare metadata
            s3_metadata = {
                'site-id': metadata.get('site_id', 'unknown') if metadata else 'unknown',
                'image-type': image_type
            }
            
            # Upload
            bucket = self.topics.get('s3_bucket')  # Should be in config
            self.s3_client.upload_file(
                filepath,
                bucket,
                s3_key,
                ExtraArgs={'Metadata': s3_metadata}
            )
            
            self.logger.info(f"Uploaded {filename} to S3: {s3_key}")
            return True
            
        except ClientError as e:
            self.logger.error(f"S3 upload failed: {e}")
            return False
    
    def _upload_buffered_data(self):
        """Upload buffered data from local storage"""
        if not self.local_buffer:
            return
        
        self.logger.info("Starting buffered data upload...")
        
        try:
            buffered_records = self.local_buffer.get_unsent(limit=100)
            
            for record in buffered_records:
                if not self.connected:
                    break
                
                success = self.publish_telemetry(record['data'])
                
                if success:
                    self.local_buffer.mark_sent(record['id'])
                    time.sleep(0.1)  # Rate limiting
                else:
                    break
            
            self.logger.info(f"Uploaded {len(buffered_records)} buffered records")
            
        except Exception as e:
            self.logger.error(f"Buffered upload error: {e}")