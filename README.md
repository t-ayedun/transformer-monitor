# Transformer Thermal Monitor

Real-time thermal monitoring system for distribution transformers using MLX90640 and Raspberry Pi.

## Quick Start

1. Flash Balena image to SD card
2. Configure device variables in Balena dashboard
3. Upload certificates to `/data/certs/`
4. Deploy: `balena push transformer-monitor`

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md)
- [AWS Setup](docs/AWS_SETUP.md)
- [Calibration](docs/CALIBRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Architecture
```
Raspberry Pi 4
├── MLX90640 Thermal Camera (I2C)
├── Pi Camera Module
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

Current: v1.0.0 (see VERSION file)