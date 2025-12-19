"""
AWS IoT Configuration Manager
Centralized configuration and validation for AWS IoT Core connectivity
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple


class AWSIoTConfig:
    """
    Manages AWS IoT Core configuration and validates setup
    
    Handles:
    - Certificate file validation
    - Endpoint configuration
    - Connection parameters
    - Graceful fallback to local-only mode
    """
    
    def __init__(self, config_manager):
        """
        Initialize AWS IoT configuration
        
        Args:
            config_manager: ConfigManager instance with loaded config
        """
        self.logger = logging.getLogger(__name__)
        self.config = config_manager
        self.enabled = False
        self.endpoint = None
        self.thing_name = None
        self.certs = {}
        self.topics = {}
        
        self._load_configuration()
    
    def _load_configuration(self):
        """Load and validate AWS IoT configuration"""
        try:
            # Check if AWS IoT is enabled
            self.enabled = self.config.get('aws_iot.enabled', False)
            
            if not self.enabled:
                self.logger.info("AWS IoT is disabled in configuration")
                return
            
            # Load endpoint and thing name
            self.endpoint = self.config.get('aws_iot.endpoint')
            self.thing_name = self.config.get('aws_iot.thing_name')
            
            if not self.endpoint or not self.thing_name:
                self.logger.warning("AWS IoT endpoint or thing_name not configured")
                self.enabled = False
                return
            
            # Load certificate paths
            certs_dir = self.config.get('aws_iot.certs_dir', '/home/smartie/transformer_monitor_data/certs')
            
            self.certs = {
                'ca_cert': os.path.join(certs_dir, 'AmazonRootCA1.pem'),
                'device_cert': os.path.join(certs_dir, 'certificate.pem.crt'),
                'private_key': os.path.join(certs_dir, 'private.pem.key')
            }
            
            # Validate certificates exist
            if not self._validate_certificates():
                self.logger.warning("AWS IoT certificates not found or invalid")
                self.enabled = False
                return
            
            # Load topics
            site_id = self.config.get('site.id', 'UNKNOWN')
            self.topics = {
                'telemetry': f"dt/transformer/{self.thing_name}/telemetry",
                'heartbeat': f"dt/transformer/{self.thing_name}/heartbeat",
                'command': f"cmd/transformer/{self.thing_name}/#"
            }
            
            # Load connection parameters
            self.telemetry_interval = self.config.get('aws_iot.telemetry_interval', 60)
            self.heartbeat_interval = self.config.get('aws_iot.heartbeat_interval', 300)
            self.compression = self.config.get('aws_iot.compression', True)
            self.bandwidth_limit_kbps = self.config.get('aws_iot.bandwidth_limit_kbps', 50)
            
            self.logger.info(
                f"AWS IoT configuration loaded: "
                f"endpoint={self.endpoint}, thing={self.thing_name}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load AWS IoT configuration: {e}")
            self.enabled = False
    
    def _validate_certificates(self) -> bool:
        """
        Validate that all required certificate files exist
        
        Returns:
            True if all certificates are present
        """
        for cert_name, cert_path in self.certs.items():
            if not Path(cert_path).exists():
                self.logger.warning(f"Certificate not found: {cert_name} at {cert_path}")
                return False
            
            # Check file is readable
            if not os.access(cert_path, os.R_OK):
                self.logger.warning(f"Certificate not readable: {cert_name} at {cert_path}")
                return False
        
        return True
    
    def is_enabled(self) -> bool:
        """Check if AWS IoT is enabled and properly configured"""
        return self.enabled
    
    def get_connection_params(self) -> Dict:
        """
        Get connection parameters for AWS IoT publisher
        
        Returns:
            Dictionary with endpoint, thing_name, certs, topics
        """
        if not self.enabled:
            return None
        
        return {
            'endpoint': self.endpoint,
            'thing_name': self.thing_name,
            'certs': self.certs,
            'topics': self.topics,
            'enable_compression': self.compression,
            'bandwidth_limit_kbps': self.bandwidth_limit_kbps
        }
    
    def get_intervals(self) -> Tuple[int, int]:
        """
        Get telemetry and heartbeat intervals
        
        Returns:
            (telemetry_interval, heartbeat_interval) in seconds
        """
        return (self.telemetry_interval, self.heartbeat_interval)
    
    def get_status(self) -> Dict:
        """
        Get current configuration status
        
        Returns:
            Status dictionary for monitoring/debugging
        """
        return {
            'enabled': self.enabled,
            'endpoint': self.endpoint if self.enabled else None,
            'thing_name': self.thing_name if self.enabled else None,
            'certificates_valid': self._validate_certificates() if self.enabled else False,
            'telemetry_interval': self.telemetry_interval if self.enabled else None,
            'heartbeat_interval': self.heartbeat_interval if self.enabled else None,
            'compression': self.compression if self.enabled else None
        }
