"""
Configuration Manager
Handles loading and merging configuration from multiple sources
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Manages application configuration from multiple sources"""
    
    def __init__(self):
        self.config = {}
        self.logger = logging.getLogger(__name__)
        
        # Configuration file paths
        self.config_dir = Path('/app/config')
        self.data_config_dir = Path('/data/config')
        self.data_config_dir.mkdir(parents=True, exist_ok=True)
        
    def load_configs(self):
        """Load configuration from templates and environment variables"""
        
        # 1. Load site config template
        site_template = self.config_dir / 'site_config.template.yaml'
        site_config_path = self.data_config_dir / 'site_config.yaml'
        
        # Copy template if config doesn't exist
        if not site_config_path.exists() and site_template.exists():
            self.logger.info("Creating site config from template")
            self._copy_and_substitute(site_template, site_config_path)
        
        # Load site config
        if site_config_path.exists():
            with open(site_config_path) as f:
                site_config = yaml.safe_load(f)
                self.config.update(site_config)
        
        # 2. Load AWS config template
        aws_template = self.config_dir / 'aws_config.template.yaml'
        aws_config_path = self.data_config_dir / 'aws_config.yaml'
        
        if not aws_config_path.exists() and aws_template.exists():
            self.logger.info("Creating AWS config from template")
            self._copy_and_substitute(aws_template, aws_config_path)
        
        if aws_config_path.exists():
            with open(aws_config_path) as f:
                aws_config = yaml.safe_load(f)
                self.config.update(aws_config)
        
        # 3. Load logging config
        logging_config_path = self.config_dir / 'logging_config.yaml'
        if logging_config_path.exists():
            with open(logging_config_path) as f:
                self.logging_config = yaml.safe_load(f)
        
        # 4. Override with environment variables
        self._apply_env_overrides()
        
        self.logger.info(f"Configuration loaded for site: {self.get('site.id', 'UNKNOWN')}")
    
    def _copy_and_substitute(self, template_path: Path, output_path: Path):
        """Copy template and substitute environment variables"""
        with open(template_path) as f:
            content = f.read()
        
        # Simple template substitution
        env_vars = {
            'SITE_ID': os.getenv('SITE_ID', 'SITE_UNKNOWN'),
            'SITE_NAME': os.getenv('SITE_NAME', 'Unknown Site'),
            'SITE_ADDRESS': os.getenv('SITE_ADDRESS', 'Unknown Address'),
            'TRANSFORMER_SN': os.getenv('TRANSFORMER_SN', 'UNKNOWN'),
            'IOT_ENDPOINT': os.getenv('IOT_ENDPOINT', ''),
            'IOT_THING_NAME': os.getenv('IOT_THING_NAME', ''),
            'AWS_REGION': os.getenv('AWS_REGION', 'us-east-1'),
            'S3_BUCKET_NAME': os.getenv('S3_BUCKET_NAME', ''),
            'FTP_HOST': os.getenv('FTP_HOST', ''),
            'FTP_USERNAME': os.getenv('FTP_USERNAME', ''),
            'FTP_PASSWORD': os.getenv('FTP_PASSWORD', ''),
        }
        
        for key, value in env_vars.items():
            content = content.replace(f'{{{{{key}}}}}', str(value))
        
        with open(output_path, 'w') as f:
            f.write(content)
    
    def _apply_env_overrides(self):
        """Override config with environment variables"""
        # Direct environment variable overrides
        env_overrides = {
            'LOG_LEVEL': 'logging.level',
            'CAPTURE_INTERVAL': 'data_capture.interval',
            'HEARTBEAT_INTERVAL': 'heartbeat.interval',
        }
        
        for env_key, config_key in env_overrides.items():
            value = os.getenv(env_key)
            if value:
                self.set(config_key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('aws.iot.endpoint')
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def validate(self):
        """Validate required configuration"""
        required_fields = [
            'site.id',
            'thermal_camera.i2c_address',
        ]
        
        missing = []
        for field in required_fields:
            if self.get(field) is None:
                missing.append(field)
        
        if missing:
            raise ValueError(f"Missing required configuration fields: {missing}")
        
        # Validate AWS config if enabled
        if self.get('aws.iot.enabled'):
            aws_required = [
                'aws.iot.endpoint',
                'aws.iot.thing_name',
                'aws.iot.certificates.ca_cert',
                'aws.iot.certificates.device_cert',
                'aws.iot.certificates.private_key',
            ]
            
            missing_aws = []
            for field in aws_required:
                value = self.get(field)
                if not value:
                    missing_aws.append(field)
                elif field.endswith('_cert') or field.endswith('_key'):
                    # Check if certificate files exist
                    if not Path(value).exists():
                        missing_aws.append(f"{field} (file not found: {value})")
            
            if missing_aws:
                self.logger.warning(f"AWS IoT configuration incomplete: {missing_aws}")
                self.logger.warning("AWS IoT will be disabled")
                self.set('aws.iot.enabled', False)
    
    def save_config(self, config_type='site'):
        """Save current configuration to file"""
        if config_type == 'site':
            path = self.data_config_dir / 'site_config.yaml'
        elif config_type == 'aws':
            path = self.data_config_dir / 'aws_config.yaml'
        else:
            raise ValueError(f"Unknown config type: {config_type}")
        
        with open(path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
        
        self.logger.info(f"Configuration saved to {path}")