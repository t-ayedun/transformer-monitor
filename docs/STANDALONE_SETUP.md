# Standalone Setup Guide (No Balena)

This guide explains how to run the Transformer Monitor as a standalone system without Balena Cloud.

## What Changes?

| Feature | With Balena | Without Balena (Standalone) |
|---------|-------------|----------------------------|
| **Config** | Dashboard Variables | `.env` file on device |
| **Updates** | `balena push` | `git pull` on device |
| **Remote Access** | Built-in VPN / Public URL | You must provide (VPN, Tailscale, or Teltonika RMS) |
| **Logs** | Dashboard Logs | `journalctl -u transformer-monitor` |

## Setup Instructions

### 1. Prepare the Environment

Create a `.env` file in the project root (`~/transformer-monitor/.env`):

```bash
cd ~/transformer-monitor
nano .env
```

Paste your configuration (ensure these match your AWS setup):

```ini
# Site Configuration
SITE_ID=SITE_001
SITE_NAME=Substation Alpha
IOT_ENDPOINT=abc12345.iot.us-east-1.amazonaws.com
IOT_THING_NAME=transformer-monitor-pi4
AWS_REGION=us-east-1
AWS_IOT_ENABLED=true

# Optional: FTP Storage (if used)
# FTP_HOST=192.168.1.5
# FTP_USERNAME=user
# FTP_PASSWORD=pass
```

### 2. Verify Certificates
Ensure your AWS certificates are in the correct place:
```bash
ls -l /data/certs/
# Should verify: AmazonRootCA1.pem, certificate.pem.crt, private.pem.key
```

### 3. Run the Auto-Start Script
If you haven't already:
```bash
sudo ./scripts/install_autostart.sh
```

### 4. Reboot
```bash
sudo reboot
```

## How it Works
The system detects it is not running in a container and automatically looks for the `.env` file to generate the actual configuration files (`/data/config/site_config.yaml` and `/data/config/aws_config.yaml`).
