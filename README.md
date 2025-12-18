# Transformer Thermal Monitor

Real-time thermal monitoring system for distribution transformers using MLX90640 thermal camera and Raspberry Pi.

> [!IMPORTANT]
> **Major Upgrade (Nov 2025)**: This system has been significantly upgraded for the Raspberry Pi 4 with advanced thermal processing, circular buffer recording, and network resilience.
> See [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md) for full details.

## Quick Start
**For complete deployment instructions, see:** [**DEPLOYMENT_MASTER_GUIDE.md**](DEPLOYMENT_MASTER_GUIDE.md)

## Key Features

- **Advanced Thermal Processing**: Real-time denoising, hotspot tracking, and super-resolution.
- **Smart Recording**: Circular buffer captures 10s *before* motion events.
- **Network Resilience**: Store-and-forward with compression for unreliable connections.
- **Web Interface**: Live thermal/visual streams and interactive ROI mapping.

## Documentation

### Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/t-ayedun/transformer-monitor.git
cd transformer-monitor
git checkout stable-deployment

# 2. Install dependencies
pip3 install --break-system-packages -r requirements.txt

# 3. Create data directories
sudo mkdir -p /data/{config,logs,images,buffer,certs}
sudo chown -R $USER:$USER /data

# 4. Configure site
cp config/site_config.template.yaml /data/config/site_config.yaml
nano /data/config/site_config.yaml  # Edit site details

# 5. Run
python3 src/main.py
```

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

## 📚 Documentation

- **[Complete Deployment Guide](DEPLOYMENT_MASTER_GUIDE.md)** - Full setup instructions
- [Calibration Guide](docs/CALIBRATION.md) - Thermal camera calibration
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## 🌐 Web Interface

Access the monitoring dashboard at: `http://<pi-ip>:5000`

Features:
- Live thermal stream (2 Hz)
- Temperature monitoring with ROI analysis
- Motion-triggered event recording
- ROI configuration tool
- System status and diagnostics

## ☁️ AWS IoT Integration

The system publishes data to AWS IoT Core:
- Thermal telemetry every 60 seconds
- Heartbeat every 5 minutes
- Alert notifications on threshold violations
- Image uploads to S3 on critical events

See [DEPLOYMENT_MASTER_GUIDE.md](DEPLOYMENT_MASTER_GUIDE.md#7-aws-iot-core-setup) for AWS setup.

## 🔧 System Architecture

```
Raspberry Pi 4/5
├── MLX90640 Thermal Camera (I2C) → 2 Hz thermal data
├── Pi Camera Module 3 → Motion detection & recording
└── Ethernet → Teltonika Router → AWS IoT Core
    ├── MQTT (telemetry, heartbeat, alerts)
    ├── S3 (thermal images, event videos)
    └── RMS Connect (remote access)
```

## 📊 Features

- ✅ **Thermal Monitoring**: Accurate temperature measurement with ROI analysis
- ✅ **Motion Detection**: Automatic event recording with pre/post buffering
- ✅ **Cloud Integration**: AWS IoT Core with MQTT and S3 storage
- ✅ **Remote Access**: Teltonika RMS Connect for remote management
- ✅ **Auto-Start**: Systemd service for automatic startup
- ✅ **Data Resilience**: Local buffering when network unavailable
- ✅ **Web Dashboard**: Real-time monitoring and configuration

## 🛠️ Maintenance

```bash
# Check service status
sudo systemctl status transformer-monitor

# View logs
sudo journalctl -u transformer-monitor -f

# Restart service
sudo systemctl restart transformer-monitor

# Update code
cd ~/transformer-monitor
git pull origin stable-deployment
sudo systemctl restart transformer-monitor
```

## 📞 Support

For issues or questions, see:
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/t-ayedun/transformer-monitor/issues)
- Email: support@smarterise.com

## 📄 License

Proprietary - Smarterise Energy Solutions

---

**Version:** 1.0  
**Compatible with:** Raspberry Pi 4B, Raspberry Pi 5  
**Last Updated:** December 2024
Current: v1.1.0 (Reflecting recently completed upgrades)
