"""
AWS IoT Publisher
Handles MQTT publishing to AWS IoT Core and S3 uploads with network resilience

Features:
- Exponential backoff retry logic
- Data compression for bandwidth saving
- Network status monitoring
- Automatic reconnection
- Bandwidth throttling
- Failed upload retry queue
"""

import json
import logging
import time
import gzip
import io
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Thread, Lock, Event
from collections import deque
from datetime import datetime

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, BotoCoreError
import requests


class NetworkResilience:
    """Helper class for network resilience features"""

    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
        """
        Calculate exponential backoff delay

        Args:
            attempt: Retry attempt number (0-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            Delay in seconds
        """
        delay = min(base_delay * (2 ** attempt), max_delay)
        return delay

    @staticmethod
    def compress_json(data: Dict) -> bytes:
        """
        Compress JSON data using gzip

        Args:
            data: Dictionary to compress

        Returns:
            Compressed bytes
        """
        json_str = json.dumps(data)
        return gzip.compress(json_str.encode('utf-8'))

    @staticmethod
    def decompress_json(compressed: bytes) -> Dict:
        """
        Decompress gzip JSON data

        Args:
            compressed: Compressed bytes

        Returns:
            Dictionary
        """
        json_str = gzip.decompress(compressed).decode('utf-8')
        return json.loads(json_str)

    @staticmethod
    def check_internet_connectivity(timeout: int = 5) -> bool:
        """
        Check if internet is accessible

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if internet is accessible
        """
        try:
            response = requests.get('https://www.google.com', timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False


class AWSPublisher:
    """
    Publishes data to AWS IoT Core and S3 with enhanced network resilience

    Features:
    - Automatic reconnection with exponential backoff
    - Data compression to reduce bandwidth
    - Retry queue for failed uploads
    - Network status monitoring
    - Bandwidth throttling
    """

    def __init__(self, endpoint: str, thing_name: str, certs: Dict,
                 topics: Dict, local_buffer=None, enable_compression: bool = True):
        self.logger = logging.getLogger(__name__)
        self.endpoint = endpoint
        self.thing_name = thing_name
        self.certs = certs
        self.topics = topics
        self.local_buffer = local_buffer
        self.enable_compression = enable_compression

        # Connection state
        self.mqtt_client = None
        self.s3_client = None
        self.connected = False
        self.connection_lock = Lock()
        self.last_connection_attempt = 0
        self.connection_attempts = 0

        # Network monitoring
        self.network_available = False
        self.network_check_interval = 30  # seconds
        self.network_monitor_thread = None
        self.stop_monitor = Event()

        # Retry queue for failed uploads
        self.failed_upload_queue = deque(maxlen=100)
        self.retry_thread = None
        self.stop_retry = Event()

        # Statistics
        self.stats = {
            'messages_published': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'bytes_saved_compression': 0,
            's3_uploads': 0,
            's3_failures': 0,
            'reconnection_count': 0,
            'retries_successful': 0
        }

        # Bandwidth throttling
        self.max_bytes_per_second = 50000  # 50 KB/s default
        self.bytes_sent_this_second = 0
        self.last_throttle_reset = time.time()

        self._init_mqtt_client()
        self._init_s3_client()

        # Start background threads
        self._start_network_monitor()
        self._start_retry_thread()

    def _init_mqtt_client(self):
        """Initialize MQTT client with resilient configuration"""
        try:
            self.logger.info("Initializing MQTT client...")

            self.mqtt_client = AWSIoTMQTTClient(self.thing_name)
            self.mqtt_client.configureEndpoint(self.endpoint, 8883)

            self.mqtt_client.configureCredentials(
                self.certs['ca_cert'],
                self.certs['private_key'],
                self.certs['device_cert']
            )

            # Enhanced connection configuration for resilience
            self.mqtt_client.configureAutoReconnectBackoffTime(1, 128, 20)
            self.mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite queue
            self.mqtt_client.configureDrainingFrequency(2)  # 2 Hz
            self.mqtt_client.configureConnectDisconnectTimeout(30)  # Longer timeout
            self.mqtt_client.configureMQTTOperationTimeout(10)

            self.logger.info("MQTT client initialized with enhanced resilience")

        except Exception as e:
            self.logger.error(f"Failed to initialize MQTT client: {e}")
            raise

    def _init_s3_client(self):
        """S3 client not used - using FTP for media uploads instead"""
        self.s3_client = None
        self.logger.info("S3 client disabled (using FTP for media)")

    def _start_network_monitor(self):
        """Start background thread to monitor network status"""
        self.network_monitor_thread = Thread(target=self._network_monitor_loop, daemon=True)
        self.network_monitor_thread.start()
        self.logger.info("Network monitor started")

    def _network_monitor_loop(self):
        """Monitor network connectivity in background"""
        while not self.stop_monitor.is_set():
            try:
                self.network_available = NetworkResilience.check_internet_connectivity()

                if self.network_available and not self.connected:
                    self.logger.info("Network available, attempting reconnection...")
                    self.connect()
                elif not self.network_available and self.connected:
                    self.logger.warning("Network lost")

            except Exception as e:
                self.logger.error(f"Network monitor error: {e}")

            self.stop_monitor.wait(self.network_check_interval)

    def _start_retry_thread(self):
        """Start background thread to retry failed uploads"""
        self.retry_thread = Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.start()
        self.logger.info("Retry thread started")

    def _retry_loop(self):
        """Retry failed uploads in background"""
        while not self.stop_retry.is_set():
            try:
                if self.connected and len(self.failed_upload_queue) > 0:
                    # Try to resend failed messages
                    item = self.failed_upload_queue.popleft()

                    if item['type'] == 'telemetry':
                        success = self.publish_telemetry(item['data'], retry=False)
                    elif item['type'] == 's3':
                        success = self.upload_image(
                            item['filepath'],
                            item['image_type'],
                            item['metadata'],
                            retry=False
                        )
                    else:
                        success = False

                    if success:
                        self.stats['retries_successful'] += 1
                        self.logger.info(f"Successfully retried {item['type']} upload")
                    else:
                        # Put back in queue
                        self.failed_upload_queue.append(item)

            except Exception as e:
                self.logger.error(f"Retry loop error: {e}")

            time.sleep(10)  # Check every 10 seconds

    def connect(self, max_retries: int = 5) -> bool:
        """
        Connect to AWS IoT Core with exponential backoff

        Args:
            max_retries: Maximum number of connection attempts

        Returns:
            True if connected successfully
        """
        with self.connection_lock:
            if self.connected:
                return True

            # Prevent connection attempt spam
            time_since_last_attempt = time.time() - self.last_connection_attempt
            if time_since_last_attempt < 10:
                self.logger.debug("Too soon since last connection attempt")
                return False

            self.last_connection_attempt = time.time()

        for attempt in range(max_retries):
            try:
                delay = NetworkResilience.exponential_backoff(attempt)

                if attempt > 0:
                    self.logger.info(f"Connection attempt {attempt + 1}/{max_retries} (waiting {delay:.1f}s)...")
                    time.sleep(delay)

                self.mqtt_client.connect()

                with self.connection_lock:
                    self.connected = True
                    self.connection_attempts = attempt + 1

                if attempt > 0:
                    self.stats['reconnection_count'] += 1

                self.logger.info("Connected to AWS IoT Core")

                # Start buffered data upload in background
                if self.local_buffer:
                    Thread(target=self._upload_buffered_data, daemon=True).start()

                return True

            except Exception as e:
                self.logger.error(f"Connection failed (attempt {attempt + 1}): {e}")

        self.logger.error(f"Failed to connect after {max_retries} retries")
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

    def _throttle_bandwidth(self, payload_size: int):
        """
        Throttle bandwidth usage

        Args:
            payload_size: Size of data to send in bytes
        """
        current_time = time.time()

        # Reset counter every second
        if current_time - self.last_throttle_reset >= 1.0:
            self.bytes_sent_this_second = 0
            self.last_throttle_reset = current_time

        # Wait if we exceed bandwidth limit
        if self.bytes_sent_this_second + payload_size > self.max_bytes_per_second:
            sleep_time = 1.0 - (current_time - self.last_throttle_reset)
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.bytes_sent_this_second = 0
                self.last_throttle_reset = time.time()

        self.bytes_sent_this_second += payload_size

    def publish_telemetry(self, data: Dict[str, Any], retry: bool = True) -> bool:
        """
        Publish telemetry data to AWS IoT with compression and retry

        Args:
            data: Telemetry data dictionary
            retry: Whether to add to retry queue on failure

        Returns:
            True if published successfully
        """
        if not self.connected:
            self.logger.warning("Not connected, buffering data locally")
            if self.local_buffer:
                self.local_buffer.store(data)
            if retry:
                self.failed_upload_queue.append({'type': 'telemetry', 'data': data})
            return False

        try:
            topic = self.topics['telemetry']

            # Prepare payload with optional compression
            if self.enable_compression:
                compressed = NetworkResilience.compress_json(data)
                payload = compressed
                original_size = len(json.dumps(data))
                compressed_size = len(compressed)
                self.stats['bytes_saved_compression'] += (original_size - compressed_size)
            else:
                payload = json.dumps(data)

            # Throttle bandwidth
            self._throttle_bandwidth(len(payload))

            # Publish
            self.mqtt_client.publish(topic, payload, 1)  # QoS 1

            self.stats['messages_published'] += 1
            self.stats['bytes_sent'] += len(payload)

            self.logger.debug(f"Published telemetry to {topic}")
            return True

        except Exception as e:
            self.logger.error(f"Publish failed: {e}")
            self.stats['messages_failed'] += 1

            if self.local_buffer:
                self.local_buffer.store(data)

            if retry:
                self.failed_upload_queue.append({'type': 'telemetry', 'data': data})

            return False

    def publish_heartbeat(self, data: Dict[str, Any]) -> bool:
        """
        Publish heartbeat message (no retry)

        Args:
            data: Heartbeat data

        Returns:
            True if published successfully
        """
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
                     metadata: Dict = None, retry: bool = True) -> bool:
        """
        S3 upload disabled - using FTP for media uploads instead
        
        This method is kept for backward compatibility but does nothing.
        Use FTP publisher via media_uploader for image uploads.
        """
        self.logger.debug("S3 upload skipped (using FTP instead)")
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

                success = self.publish_telemetry(record['data'], retry=False)

                if success:
                    self.local_buffer.mark_sent(record['id'])
                    time.sleep(0.1)  # Rate limiting
                else:
                    break

            self.logger.info(f"Uploaded {len(buffered_records)} buffered records")

        except Exception as e:
            self.logger.error(f"Buffered upload error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics"""
        return {
            **self.stats,
            'connected': self.connected,
            'network_available': self.network_available,
            'failed_queue_size': len(self.failed_upload_queue),
            'connection_attempts': self.connection_attempts
        }

    def stop(self):
        """Stop all background threads and disconnect"""
        self.logger.info("Stopping AWS publisher...")

        # Stop threads
        self.stop_monitor.set()
        self.stop_retry.set()

        if self.network_monitor_thread:
            self.network_monitor_thread.join(timeout=5)

        if self.retry_thread:
            self.retry_thread.join(timeout=5)

        # Disconnect
        self.disconnect()

        self.logger.info("AWS publisher stopped")
