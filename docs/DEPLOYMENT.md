# Deployment Guide

## Prerequisites

- Balena account (free tier)
- Raspberry Pi 4 (4GB+ recommended)
- MLX90640 thermal camera
- Raspberry Pi Camera Module (optional)
- MicroSD card (32GB+ industrial grade recommended)
- Teltonika router with RMS enabled
- AWS account with IoT Core access

## Step-by-Step Deployment

### 1. Prepare Raspberry Pi (First Time Only)

On a fresh Raspberry Pi:
```bash
# Clone repository
git clone https://github.com/yourcompany/transformer-monitor.git
cd transformer-monitor

# Run setup script
chmod +x scripts/setup_pi.sh
./scripts/setup_pi.sh

# Reboot
sudo reboot
```

### 2. Set Up Balena
```bash
# Install Balena CLI
npm install -g balena-cli

# Login
balena login

# Create application (first time only)
balena app create transformer-monitor --type raspberrypi4-64

# Add your first device
# Go to dashboard, click "Add device", download image
# Flash image to SD card using Balena Etcher
```

### 3. Configure AWS (Manager Task)

Follow the guide in `AWS_SETUP.md` to:
- Create IoT Thing
- Generate certificates
- Create IoT policy
- Create S3 bucket
- Get IoT endpoint

### 4. Set Device Variables

In Balena dashboard, for each device, set:
```
SITE_ID=SITE_001
SITE_NAME=Transformer Station Alpha
SITE_ADDRESS=123 Power St, Lagos
TRANSFORMER_SN=TXF-2024-001
IOT_ENDPOINT=xxxxx-ats.iot.us-east-1.amazonaws.com
IOT_THING_NAME=transformer-monitor-SITE_001
AWS_REGION=us-east-1
S3_BUCKET_NAME=transformer-thermal-images
LOG_LEVEL=INFO
CAPTURE_INTERVAL=60
```

### 5. Upload Certificates
```bash
# SSH into device
balena ssh <device-uuid>

# Create cert directory
mkdir -p /data/certs

# Exit SSH, then upload from local machine
balena push <device-uuid> ./certs/AmazonRootCA1.pem:/data/certs/
balena push <device-uuid> ./certs/certificate.pem.crt:/data/certs/
balena push <device-uuid> ./certs/private.pem.key:/data/certs/
```

### 6. Deploy Code
```bash
# From project root
balena push transformer-monitor

# Or use deployment script
./scripts/deploy.sh
```

### 7. Verify Deployment
```bash
# Check logs
balena logs <device-uuid> --tail

# SSH for debugging
balena ssh <device-uuid>

# Check I2C devices
i2cdetect -y 1

# Check running processes
ps aux | grep python
```

## Network Setup

### Ethernet Connection (Recommended)

1. Connect Pi to Teltonika router LAN port
2. Configure static IP in router (optional)
3. Device will auto-connect on boot

### WiFi Connection (Backup)

Set in Balena dashboard:
- Device Configuration → Network → WiFi SSID
- Add WiFi password

## Troubleshooting

See `TROUBLESHOOTING.md`

## Updating
```bash
# Make code changes
git add .
git commit -m "Description of changes"
git push

# Deploy update
balena push transformer-monitor

# Balena will automatically update all devices
# Rollback if needed from dashboard
```

## Multi-Site Deployment

For deploying to multiple sites:

1. Clone configuration for each site
2. Set unique device variables per device
3. Upload site-specific certificates
4. Deploy same codebase to all

Each device operates independently with site-specific config.