#!/usr/bin/env python3
"""
Configuration Generator
Generates site-specific configuration files from templates
"""

import yaml
from pathlib import Path
from datetime import datetime


class ConfigGenerator:
    """Generates configuration files for a new site"""

    def __init__(self, site_id, site_name, transformer_sn, output_dir):
        self.site_id = site_id
        self.site_name = site_name
        self.transformer_sn = transformer_sn
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_site_config(self, timezone='UTC', address=''):
        """Generate site_config.yaml"""
        config = {
            'production_mode': True,  # Enable production mode for deployed sites
            'site': {
                'id': self.site_id,
                'name': self.site_name,
                'location': {
                    'address': address,
                    'latitude': None,
                    'longitude': None
                },
                'timezone': timezone,
                'contact': {
                    'email': None,
                    'phone': None
                }
            },
            'transformer': {
                'serial_number': self.transformer_sn,
                'manufacturer': None,
                'model': None,
                'type': 'Distribution',
                'rating_kva': 100,
                'year_installed': None,
                'last_maintenance': None
            },
            'thermal_camera': {
                'model': 'MLX90640',
                'i2c_address': 0x33,
                'i2c_bus': 1,
                'refresh_rate': 4,
                'resolution': [32, 24],
                'emissivity': 0.95
            },
            'regions_of_interest': [
                {
                    'name': 'full_frame',
                    'enabled': True,
                    'coordinates': [[0, 0], [32, 24]],
                    'weight': 1.0,
                    'emissivity': 0.95,
                    'thresholds': {
                        'warning': 75.0,
                        'critical': 85.0,
                        'emergency': 95.0
                    }
                }
            ],
            'composite_temperature': {
                'method': 'weighted_average',
                'enabled': True
            },
            'pi_camera': {
                'enabled': True,
                'model': 'Pi Camera 3',
                'resolution': [1920, 1080],
                'framerate': 30,
                'quality': 85,
                'motion_detection': {
                    'enabled': True,
                    'threshold': 1500,
                    'min_area': 500
                },
                'recording': {
                    'pre_record_seconds': 10,
                    'post_record_seconds': 10,
                    'max_duration_seconds': 300
                },
                'snapshot_interval': 1800,  # 30 minutes
                'night_mode': {
                    'enabled': True,
                    'start_hour': 18,
                    'end_hour': 6,
                    'ir_leds_enabled': False
                },
                'storage': {
                    'max_local_storage_gb': 10,
                    'auto_cleanup_days': 7
                },
                'live_view': {
                    'enabled': True,
                    'port': 5000,
                    'require_auth': True,
                    'username': 'admin',
                    'password': 'changeme'  # Should be changed after deployment
                }
            },
            'data_capture': {
                'interval': 60,  # 1 minute
                'save_full_frame_interval': 10,
                'buffer_size': 100
            },
            'local_storage': {
                'enabled': True,
                'database_path': '/data/buffer/readings.db',
                'max_size_mb': 500,
                'retention_days': 7
            },
            'network': {
                'router': {
                    'local_ip': '192.168.1.1'
                },
                'pi': {
                    'static_ip': '192.168.1.100'
                },
                'connectivity': {
                    'check_interval': 60
                }
            },
            'heartbeat': {
                'enabled': True,
                'interval': 300  # 5 minutes
            },
            'logging': {
                'level': 'INFO',
                'max_file_size_mb': 10,
                'backup_count': 5,
                'log_to_console': True
            }
        }

        output_file = self.output_dir / 'site_config.yaml'
        with open(output_file, 'w') as f:
            f.write(f"# Site Configuration: {self.site_id}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Site: {self.site_name}\n")
            f.write(f"# Transformer: {self.transformer_sn}\n\n")
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config

    def generate_aws_config(self, iot_endpoint, thing_name, region, cert_paths):
        """Generate aws_config.yaml"""
        config = {
            'aws': {
                'region': region,
                'iot': {
                    'enabled': True,
                    'endpoint': iot_endpoint,
                    'thing_name': thing_name,
                    'certificates': {
                        'ca_cert': cert_paths['ca_cert'],
                        'device_cert': cert_paths['device_cert'],
                        'private_key': cert_paths['private_key']
                    },
                    'topics': {
                        'telemetry': f'transformers/{self.site_id}/telemetry',
                        'heartbeat': f'transformers/{self.site_id}/heartbeat',
                        'alerts': f'transformers/{self.site_id}/alerts'
                    },
                    'qos': 1,
                    'keep_alive': 300
                },
                's3': {
                    'bucket': f'transformer-monitor-data-{region}',
                    'upload': {
                        'thermal_images': True,
                        'camera_snapshots': True,
                        'videos': True
                    },
                    'prefix': f'{self.site_id}/'
                }
            }
        }

        output_file = self.output_dir / 'aws_config.yaml'
        with open(output_file, 'w') as f:
            f.write(f"# AWS Configuration: {self.site_id}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config

    def generate_ftp_config(self, host, username, password, port=21, remote_dir=None):
        """Generate ftp_config.yaml (optional)"""
        config = {
            'ftp': {
                'enabled': True,
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'remote_dir': remote_dir or f'/transformer-monitor/{self.site_id}',
                'passive': True,
                'timeout': 30,
                'upload_logs': True,
                'log_interval': 86400  # Daily
            }
        }

        output_file = self.output_dir / 'ftp_config.yaml'
        with open(output_file, 'w') as f:
            f.write(f"# FTP Configuration: {self.site_id}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# WARNING: Contains sensitive credentials\n\n")
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions
        output_file.chmod(0o600)

        return config

    def generate_docker_env(self, iot_endpoint, thing_name, region):
        """Generate .env file for Docker"""
        env_content = f"""# Environment Variables for {self.site_id}
# Generated: {datetime.now().isoformat()}

# Site Information
SITE_ID={self.site_id}
SITE_NAME={self.site_name}
TRANSFORMER_SN={self.transformer_sn}
TIMEZONE=UTC

# AWS Configuration
AWS_REGION={region}
IOT_ENDPOINT={iot_endpoint}
IOT_THING_NAME={thing_name}

# Production Mode
PRODUCTION_MODE=true

# Logging
LOG_LEVEL=INFO
"""

        output_file = self.output_dir / '.env'
        output_file.write_text(env_content)

        return env_content


if __name__ == '__main__':
    # Test configuration generation
    import sys

    if len(sys.argv) < 4:
        print("Usage: python generate_config.py <site_id> <site_name> <transformer_sn>")
        sys.exit(1)

    site_id = sys.argv[1]
    site_name = sys.argv[2]
    transformer_sn = sys.argv[3]

    generator = ConfigGenerator(
        site_id=site_id,
        site_name=site_name,
        transformer_sn=transformer_sn,
        output_dir=f'./output/{site_id}/config'
    )

    # Generate configurations
    print("Generating site configuration...")
    generator.generate_site_config()

    print("Generating AWS configuration...")
    generator.generate_aws_config(
        iot_endpoint='test.iot.us-east-1.amazonaws.com',
        thing_name=f'{site_id}-monitor',
        region='us-east-1',
        cert_paths={
            'ca_cert': '/data/certificates/AmazonRootCA1.pem',
            'device_cert': '/data/certificates/device.pem.crt',
            'private_key': '/data/certificates/private.pem.key'
        }
    )

    print("Generating Docker environment file...")
    generator.generate_docker_env(
        iot_endpoint='test.iot.us-east-1.amazonaws.com',
        thing_name=f'{site_id}-monitor',
        region='us-east-1'
    )

    print(f"\n✓ Configuration files generated in ./output/{site_id}/config/")
