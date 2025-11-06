"""
Configuration Validators
"""

import logging
from pathlib import Path
from typing import Dict, List, Any


class ConfigValidator:
    """Validates configuration settings"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.errors = []
        self.warnings = []
    
    def validate_all(self, config: Dict) -> bool:
        """
        Validate entire configuration
        
        Returns: True if valid, False if errors found
        """
        self.errors = []
        self.warnings = []
        
        # Validate each section
        self.validate_site_config(config)
        self.validate_thermal_camera(config)
        self.validate_camera_config(config)
        self.validate_aws_config(config)
        self.validate_roi_config(config)
        
        # Log results
        if self.errors:
            for error in self.errors:
                self.logger.error(f"Config validation error: {error}")
        
        if self.warnings:
            for warning in self.warnings:
                self.logger.warning(f"Config validation warning: {warning}")
        
        return len(self.errors) == 0
    
    def validate_site_config(self, config: Dict):
        """Validate site configuration"""
        site = config.get('site', {})
        
        if not site.get('id'):
            self.errors.append("site.id is required")
        
        if not site.get('name'):
            self.warnings.append("site.name not set")
    
    def validate_thermal_camera(self, config: Dict):
        """Validate thermal camera settings"""
        camera = config.get('thermal_camera', {})
        
        if not camera:
            self.errors.append("thermal_camera configuration missing")
            return
        
        # Check I2C address
        i2c_addr = camera.get('i2c_address')
        if i2c_addr not in [0x32, 0x33]:
            self.warnings.append(
                f"Unusual I2C address: {hex(i2c_addr)}. "
                "MLX90640 typically uses 0x33"
            )
        
        # Check refresh rate
        refresh_rate = camera.get('refresh_rate', 8)
        valid_rates = [0.5, 1, 2, 4, 8, 16, 32, 64]
        if refresh_rate not in valid_rates:
            self.errors.append(
                f"Invalid refresh_rate: {refresh_rate}. "
                f"Must be one of {valid_rates}"
            )
        
        # Check emissivity
        emissivity = camera.get('emissivity', 0.95)
        if not 0.1 <= emissivity <= 1.0:
            self.errors.append(
                f"Invalid emissivity: {emissivity}. "
                "Must be between 0.1 and 1.0"
            )
    
    def validate_camera_config(self, config: Dict):
        """Validate Pi camera settings"""
        camera = config.get('pi_camera', {})
        
        if not camera.get('enabled'):
            return  # Camera disabled, skip validation
        
        # Check resolution
        resolution = camera.get('resolution', [1920, 1080])
        if not isinstance(resolution, list) or len(resolution) != 2:
            self.errors.append("pi_camera.resolution must be [width, height]")
        
        # Check motion detection settings
        motion = camera.get('motion_detection', {})
        if motion.get('enabled'):
            threshold = motion.get('threshold', 1500)
            if threshold < 100 or threshold > 5000:
                self.warnings.append(
                    f"motion_detection.threshold={threshold} may be too "
                    f"{'low' if threshold < 100 else 'high'}"
                )
        
        # Check night mode
        night = camera.get('night_mode', {})
        if night.get('enabled'):
            start = night.get('start_hour', 18)
            end = night.get('end_hour', 6)
            if not (0 <= start < 24 and 0 <= end < 24):
                self.errors.append("Invalid night_mode hours")
    
    def validate_aws_config(self, config: Dict):
        """Validate AWS configuration"""
        aws = config.get('aws', {})
        iot = aws.get('iot', {})
        
        if not iot.get('enabled'):
            self.warnings.append("AWS IoT is disabled")
            return
        
        # Check required fields
        required = ['endpoint', 'thing_name', 'region']
        for field in required:
            if not iot.get(field):
                self.errors.append(f"aws.iot.{field} is required")
        
        # Check certificates
        certs = iot.get('certificates', {})
        for cert_name in ['ca_cert', 'device_cert', 'private_key']:
            cert_path = certs.get(cert_name)
            if cert_path:
                if not Path(cert_path).exists():
                    self.errors.append(f"Certificate not found: {cert_path}")
            else:
                self.errors.append(f"aws.iot.certificates.{cert_name} not set")
    
    def validate_roi_config(self, config: Dict):
        """Validate regions of interest"""
        rois = config.get('regions_of_interest', [])
        
        if not rois:
            self.warnings.append("No regions of interest defined")
            return
        
        frame_size = config.get('thermal_camera', {}).get('resolution', [32, 24])
        max_x, max_y = frame_size
        
        for i, roi in enumerate(rois):
            # Check name
            if not roi.get('name'):
                self.errors.append(f"ROI {i}: name is required")
            
            # Check coordinates
            coords = roi.get('coordinates')
            if not coords or len(coords) != 2:
                self.errors.append(
                    f"ROI {roi.get('name', i)}: coordinates must be "
                    "[[x1,y1], [x2,y2]]"
                )
                continue
            
            x1, y1 = coords[0]
            x2, y2 = coords[1]
            
            # Validate bounds
            if not (0 <= x1 < x2 <= max_x and 0 <= y1 < y2 <= max_y):
                self.errors.append(
                    f"ROI {roi.get('name')}: coordinates out of bounds. "
                    f"Frame size is {frame_size}"
                )
            
            # Check thresholds
            thresholds = roi.get('thresholds', {})
            warning = thresholds.get('warning', 0)
            critical = thresholds.get('critical', 0)
            emergency = thresholds.get('emergency', 0)
            
            if not (warning < critical < emergency):
                self.warnings.append(
                    f"ROI {roi.get('name')}: thresholds should be "
                    "warning < critical < emergency"
                )
    
    def get_report(self) -> str:
        """Get validation report as string"""
        report = []
        
        if self.errors:
            report.append("ERRORS:")
            for error in self.errors:
                report.append(f"  - {error}")
        
        if self.warnings:
            report.append("\nWARNINGS:")
            for warning in self.warnings:
                report.append(f"  - {warning}")
        
        if not self.errors and not self.warnings:
            report.append("Configuration is valid")
        
        return "\n".join(report)