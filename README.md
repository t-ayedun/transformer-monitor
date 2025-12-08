# Transformer Thermal Monitor

Real-time thermal monitoring system for distribution transformers using MLX90640 and Raspberry Pi.

> [!IMPORTANT]
> **Major Upgrade (Nov 2025)**: This system has been significantly upgraded for the Raspberry Pi 4 with advanced thermal processing, circular buffer recording, and network resilience.
> See [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md) for full details.

## Quick Start

1. Flash Balena image to SD card
2. Configure device variables in Balena dashboard
3. Upload certificates to `/data/certs/`
4. Deploy: `balena push transformer-monitor`

## Key Features

- **Advanced Thermal Processing**: Real-time denoising, hotspot tracking, and super-resolution.
- **Smart Recording**: Circular buffer captures 10s *before* motion events.
- **Network Resilience**: Store-and-forward with compression for unreliable connections.
- **Web Interface**: Live thermal/visual streams and interactive ROI mapping.

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md)
- [AWS Setup](docs/AWS_SETUP.md)
- [Calibration](docs/CALIBRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Architecture

```
Raspberry Pi 4 (4GB+)
├── MLX90640 Thermal Camera (I2C)
├── Pi Camera Module (Official v2/v3)
└── Network (Ethernet/WiFi) → Teltonika Router
    └── AWS IoT Core (MQTT)
        ├── S3 (images)
        ├── Timestream (metrics)
        └── SNS (alerts)
```

## Configuration

All site-specific settings via Balena Device Variables:
- `SITE_ID`: Unique site identifier
- `IOT_ENDPOINT`: AWS IoT endpoint
- `IOT_THING_NAME`: AWS IoT thing name
- `FTP_HOST`, `FTP_USERNAME`, `FTP_PASSWORD`: FTP server details

## Version

Current: v1.1.0 (Reflecting recently completed upgrades)