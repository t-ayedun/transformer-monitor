# Transformer Thermal Monitor Documentation

## Overview

This system provides real-time thermal monitoring of distribution transformers using:
- MLX90640 thermal camera (32×24 resolution)
- Raspberry Pi 4 (edge computing)
- Pi Camera 3 (surveillance with motion detection)
- AWS IoT Core (cloud connectivity)
- Teltonika router (remote connectivity)

## Architecture
```
[Transformer] → [Thermal Camera] → [Raspberry Pi] → [Router] → [AWS]
                [Pi Camera 3]    ↗
```

## Key Features

- **Minute-level thermal monitoring** with configurable ROIs
- **Composite temperature calculation** (weighted average)
- **Smart surveillance** with motion-triggered recording
- **Night vision** support with auto-switching
- **Local buffering** for offline operation
- **Remote access** via Balena, RMS, or VPN
- **OTA updates** via Balena
- **Cost-optimized** AWS usage

## Quick Links

- [Deployment Guide](DEPLOYMENT.md)
- [AWS Setup](AWS_SETUP.md)
- [Calibration Procedure](CALIBRATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)

## System Requirements

### Hardware
- Raspberry Pi 4 (4GB RAM minimum, 8GB recommended)
- 32GB+ industrial-grade microSD card
- MLX90640 thermal camera (55° or 110° FOV)
- Pi Camera 3 or Pi Camera 3 NoIR
- Teltonika RUT955/956 router
- Power supplies (5V/3A for Pi)
- Weatherproof enclosure (IP65+)

### Software
- Balena OS (deployed via Balena Cloud)
- Python 3.11
- AWS IoT Core account
- Teltonika RMS account

## Data Flow

1. **Thermal Data** (every minute):
   - Capture 32×24 thermal frame
   - Calculate ROI statistics (max, avg, min per region)
   - Compute composite temperature
   - Publish to AWS IoT Core
   - Store in local buffer (if offline)

2. **Camera Surveillance**:
   - Continuous motion detection (low-res stream)
   - Trigger recording on motion (with 10s pre-buffer)
   - Save video clips locally
   - Upload to S3
   - Periodic snapshots every 30 minutes

3. **System Health**:
   - Heartbeat every 5 minutes
   - Network status monitoring
   - Storage management
   - Watchdog timer

## Configuration

All configuration is managed via YAML files:

- `site_config.yaml` - Site-specific settings
- `aws_config.yaml` - AWS credentials and endpoints
- `logging_config.yaml` - Logging configuration

Configuration can be updated remotely via Balena device variables.

## Remote Access Methods

### 1. Balena (Recommended for software)
```bash
balena ssh <device-uuid>
balena logs <device-uuid> --tail
balena tunnel <device-uuid> -p 5000:5000
```

### 2. Teltonika RMS (For network management)
- Web interface: https://rms.teltonika-networks.com
- CLI access to router
- SSH from router to Pi

### 3. OpenVPN (For full site access)
```bash
sudo openvpn --config site001.ovpn
ssh pi@192.168.1.100
```

### 4. Camera Web Interface
- Via Balena tunnel: `http://localhost:5000`
- Via VPN: `http://192.168.1.100:5000`
- Features: Live view, settings, manual snapshot

## Monitoring & Alerts

Data flows to AWS where you can:
- View real-time dashboards
- Set up CloudWatch alarms
- Receive SNS notifications
- Query historical data
- Generate reports

## Support

For issues or questions:
1. Check [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Review device logs via Balena
3. Contact: support@yourcompany.com