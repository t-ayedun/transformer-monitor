## Site Provisioning Guide

Complete guide for provisioning and deploying new transformer monitoring sites.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Workflow](#detailed-workflow)
- [Deployment Options](#deployment-options)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

## Overview

Site provisioning automates the complete setup of a new transformer monitoring site, including:

- AWS IoT Thing creation and certificate generation
- Site-specific configuration generation
- S3 bucket structure creation
- Balena device registration and configuration
- Deployment package creation

**Time to provision:** ~10 minutes per site
**Time to deploy:** ~30 minutes per site (including flashing and first boot)

## Prerequisites

### Required Tools

1. **Python 3.9+** with dependencies:
   ```bash
   pip install boto3 pyyaml
   ```

2. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   # Required permissions: IoT, S3
   ```

3. **Balena CLI** (for Balena deployments):
   ```bash
   npm install -g balena-cli
   balena login
   ```

### Required Information

For each site, gather:

- **Site ID** - Unique identifier (e.g., `SITE_001`, `TX_MAIN_SUB`)
- **Site Name** - Human-readable name (e.g., "Main Substation")
- **Transformer Serial Number** - Physical transformer identifier
- **Site Address** - Physical location
- **Timezone** - Site timezone (e.g., `America/New_York`, `UTC`)
- **AWS Region** - AWS region to use (e.g., `us-east-1`)

### Optional Information

- **FTP Server Details** - If using FTP for log backups
- **Contact Information** - Site operator email/phone

## Quick Start

### Provision a New Site

```bash
cd transformer-monitor

# Provision site
python scripts/provision/provision_site.py \
  --site-id SITE_001 \
  --site-name "Main Substation" \
  --transformer-sn TX-12345 \
  --aws-region us-east-1 \
  --timezone America/New_York \
  --address "123 Power St, City, State"

# Output will be in: ./provisioned_sites/SITE_001/
```

### Deploy to Balena

```bash
# Deploy to Balena cloud
./scripts/deploy_balena.sh SITE_001

# Flash SD card with generated image
balena local flash provisioned_sites/SITE_001/balena-SITE_001.img

# After device boots and comes online, upload certificates
./scripts/upload_certificates.sh SITE_001

# Monitor deployment
balena logs SITE_001-monitor --tail
```

## Detailed Workflow

### Step 1: Provision Site

The provisioning script creates all necessary AWS and configuration resources:

```bash
python scripts/provision/provision_site.py \
  --site-id SITE_001 \
  --site-name "Main Substation" \
  --transformer-sn TX-12345 \
  --aws-region us-east-1 \
  --timezone America/New_York \
  --address "123 Power St" \
  --balena-app transformer-monitor
```

**What this does:**

1. **Creates AWS IoT Thing** named `SITE_001-monitor`
2. **Generates certificates** and keys for secure MQTT connection
3. **Creates IoT policy** with appropriate permissions
4. **Sets up S3 bucket structure** for data storage
5. **Generates configuration files** (site_config.yaml, aws_config.yaml)
6. **Creates deployment package** with all necessary files
7. **Generates Balena configuration** for cloud deployment

**Output structure:**

```
provisioned_sites/SITE_001/
├── certificates/
│   ├── AmazonRootCA1.pem       # AWS Root CA
│   ├── device.pem.crt          # Device certificate
│   ├── private.pem.key         # Private key (600 permissions)
│   ├── public.pem.key          # Public key
│   └── iot_policy.json         # IoT policy document
├── config/
│   ├── site_config.yaml        # Site configuration
│   ├── aws_config.yaml         # AWS IoT configuration
│   └── .env                    # Environment variables
├── balena/
│   ├── device_env_vars.json    # Balena env vars
│   └── register_device.sh      # Device registration script
├── deployment_package/
│   ├── certificates/           # Copy of certificates
│   ├── config/                 # Copy of configuration
│   └── README.md               # Deployment instructions
└── SITE_001_deployment_YYYYMMDD.zip  # Complete archive
```

### Step 2: Review Generated Files

Before deployment, review:

1. **Site Configuration** (`config/site_config.yaml`):
   - Verify site details (ID, name, address)
   - Check thermal camera settings (I2C address, refresh rate)
   - Review ROI configuration
   - Confirm thresholds (warning: 75°C, critical: 85°C, emergency: 95°C)

2. **AWS Configuration** (`config/aws_config.yaml`):
   - Verify IoT endpoint and thing name
   - Check MQTT topics
   - Confirm S3 bucket and prefix

3. **Certificates** (`certificates/`):
   - Verify all certificate files exist
   - Check private key permissions (should be 600)
   - **Securely backup certificates** to encrypted storage

### Step 3A: Deploy with Balena (Recommended)

Balena provides fleet management, OTA updates, and remote access.

#### 3A.1: Create Balena Application

```bash
# Create application (one-time for fleet)
balena app create transformer-monitor --type raspberrypi4-64
```

#### 3A.2: Deploy Site

```bash
# Run deployment script
./scripts/deploy_balena.sh SITE_001
```

This script will:
- Register device with Balena
- Set environment variables
- Build and push Docker image to Balena cloud
- Download configured Balena OS image
- Configure OS with device credentials

#### 3A.3: Flash SD Card

```bash
# Flash SD card with Balena OS
balena local flash provisioned_sites/SITE_001/balena-SITE_001.img

# Or manually with Etcher:
# 1. Download Etcher from balena.io/etcher
# 2. Select balena-SITE_001.img
# 3. Select SD card
# 4. Flash
```

#### 3A.4: Upload Certificates

After device boots and comes online (check `balena devices`):

```bash
# Wait for device to appear online
balena devices | grep SITE_001

# Upload certificates
./scripts/upload_certificates.sh SITE_001

# Restart application to load certificates
balena restart SITE_001-monitor
```

#### 3A.5: Verify Deployment

```bash
# View device logs
balena logs SITE_001-monitor --tail

# SSH to device
balena ssh SITE_001-monitor

# Check certificate files
balena ssh SITE_001-monitor 'ls -la /data/certificates/'

# Check AWS IoT connection
balena logs SITE_001-monitor | grep "Connected to AWS IoT"
```

### Step 3B: Manual Deployment (Alternative)

For sites without reliable internet or Balena access.

#### 3B.1: Prepare Raspberry Pi

1. **Flash Raspberry Pi OS**:
   ```bash
   # Download Raspberry Pi OS Lite (64-bit)
   # Flash to SD card using Raspberry Pi Imager
   ```

2. **Configure SSH and WiFi**:
   - Enable SSH (create empty `ssh` file in boot partition)
   - Configure WiFi (create `wpa_supplicant.conf` in boot partition)

#### 3B.2: Copy Deployment Package

```bash
# Copy deployment package to Pi
scp -r provisioned_sites/SITE_001/deployment_package/* pi@<pi-ip>:/home/pi/transformer-monitor/

# SSH to Pi
ssh pi@<pi-ip>
```

#### 3B.3: Install on Pi

```bash
# On the Pi:
cd /home/pi/transformer-monitor

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip docker.io docker-compose

# Install Python dependencies
pip3 install -r requirements.txt

# Copy certificates
sudo mkdir -p /data/certificates
sudo cp deployment_package/certificates/* /data/certificates/
sudo chmod 600 /data/certificates/private.pem.key

# Copy configuration
sudo mkdir -p /data/config
sudo cp deployment_package/config/* /data/config/

# Start with Docker Compose
docker-compose up -d
```

#### 3B.4: Verify Installation

```bash
# Check containers
docker ps

# View logs
docker-compose logs -f transformer-monitor

# Test thermal camera
python3 -c "from thermal_capture import ThermalCapture; t = ThermalCapture(); print('Camera OK')"

# Test AWS IoT connection
docker-compose logs | grep "Connected to AWS IoT"
```

## Deployment Options Comparison

| Feature | Balena | Manual |
|---------|--------|--------|
| Fleet management | ✓ | ✗ |
| OTA updates | ✓ | ✗ (manual) |
| Remote SSH access | ✓ | Requires VPN |
| Environment variables | Dashboard | Config files |
| Multi-device rollout | Easy | Manual per device |
| Cost | $2/device/month | Free |
| Complexity | Low | Medium |
| Offline operation | ✓ | ✓ |

**Recommendation:** Use Balena for production deployments with 5+ sites.

## Post-Deployment Verification

### 1. Device Health Check

Access web interface (if on local network):

```
http://<device-ip>:5000/
http://<device-ip>:5000/health/deep
```

Expected response from `/health/deep`:
```json
{
  "status": "healthy",
  "components": {
    "thermal_camera": {"status": "ok"},
    "visual_camera": {"status": "ok"},
    "data_uploader": {"status": "ok"}
  },
  "network": {
    "aws_iot": {"connected": true}
  }
}
```

### 2. AWS IoT Verification

```bash
# Subscribe to MQTT topic to see live telemetry
aws iot-data subscribe \
  --topic "transformers/SITE_001/telemetry" \
  --region us-east-1

# Should see temperature data every 60 seconds
```

### 3. S3 Data Verification

```bash
# List uploaded thermal frames
aws s3 ls s3://transformer-monitor-data-us-east-1/SITE_001/thermal_frames/ \
  --region us-east-1

# Download a thermal frame
aws s3 cp s3://transformer-monitor-data-us-east-1/SITE_001/thermal_frames/SITE_001_thermal_20240101_120000.npy . \
  --region us-east-1
```

### 4. Visual Verification

1. Access live view: `http://<device-ip>:5000/`
2. Check thermal overlay is visible
3. Verify temperature readings are reasonable (20-40°C ambient)
4. Test ROI mapper functionality

## ROI Configuration

After deployment, configure Regions of Interest:

1. **Access ROI Mapper**:
   ```
   http://<device-ip>:5000/roi_mapper
   ```

2. **Define ROIs**:
   - Click "Freeze Image" to lock thermal frame
   - Click and drag to select region
   - Set ROI name and thresholds:
     - Warning: 75°C (typical)
     - Critical: 85°C
     - Emergency: 95°C
   - Click "Save ROI"

3. **Save Configuration**:
   - Click "Download Config" to backup
   - Configuration automatically saved to device

## Monitoring and Maintenance

### Balena Dashboard

- **Device Status**: Check online/offline
- **Logs**: Real-time log streaming
- **Environment Variables**: Update configuration remotely
- **Updates**: Push OTA updates to fleet

### AWS IoT Core

- **MQTT Test Client**: Monitor live telemetry
  - Topic: `transformers/SITE_001/telemetry`
  - Topic: `transformers/SITE_001/alerts`

- **Device Shadow**: View last reported state

### S3 Data Access

```bash
# List all data for a site
aws s3 ls --recursive s3://transformer-monitor-data-us-east-1/SITE_001/

# Sync all data locally
aws s3 sync s3://transformer-monitor-data-us-east-1/SITE_001/ ./local_data/SITE_001/
```

## Troubleshooting

### Device Not Connecting to AWS IoT

**Symptoms:** Logs show "Failed to connect to AWS IoT"

**Solutions:**

1. **Verify certificates are uploaded**:
   ```bash
   balena ssh SITE_001-monitor 'ls -la /data/certificates/'
   ```

2. **Check certificate permissions**:
   ```bash
   balena ssh SITE_001-monitor 'stat -c "%a %n" /data/certificates/private.pem.key'
   # Should show: 600
   ```

3. **Verify IoT endpoint**:
   ```bash
   balena env list -d SITE_001-monitor | grep IOT_ENDPOINT
   ```

4. **Test network connectivity**:
   ```bash
   balena ssh SITE_001-monitor 'ping -c 3 google.com'
   ```

5. **Check IoT policy attachment**:
   ```bash
   aws iot list-principal-policies \
     --principal <certificate-arn> \
     --region us-east-1
   ```

### Thermal Camera Not Detected

**Symptoms:** Logs show "Failed to initialize thermal camera"

**Solutions:**

1. **Enable I2C**:
   ```bash
   balena ssh SITE_001-monitor
   # Check I2C is enabled
   ls /dev/i2c-*
   ```

2. **Check camera connection**:
   ```bash
   balena ssh SITE_001-monitor 'i2cdetect -y 1'
   # Should show device at 0x33
   ```

3. **Verify camera power**: Ensure MLX90640 has 3.3V power

### Visual Camera Not Working

**Symptoms:** Web interface shows "Camera unavailable"

**Solutions:**

1. **Check camera connection**: Ensure ribbon cable is properly seated

2. **Enable camera in config**:
   ```bash
   balena ssh SITE_001-monitor
   # Check /boot/config.txt has:
   # start_x=1
   # gpu_mem=128
   ```

3. **Test camera**:
   ```bash
   balena ssh SITE_001-monitor
   libcamera-hello --list-cameras
   ```

### High Memory Usage

**Symptoms:** Device becomes slow, OOM errors

**Solutions:**

1. **Check upload queue size**:
   - Access `/health/deep` endpoint
   - If queue > 500 items, network upload is slow

2. **Reduce local storage retention**:
   - Edit `site_config.yaml`: `local_storage.retention_days: 3`

3. **Disable video recording temporarily**:
   - Edit `site_config.yaml`: `pi_camera.enabled: false`

### Missing Data in S3

**Symptoms:** Expected thermal frames or snapshots not in S3

**Solutions:**

1. **Check upload statistics**:
   ```bash
   curl http://<device-ip>:5000/health/deep
   # Check data_uploader.stats.thermal_frames_uploaded
   ```

2. **Verify S3 permissions**:
   ```bash
   aws s3 ls s3://transformer-monitor-data-us-east-1/SITE_001/
   ```

3. **Check worker thread**:
   - View logs for "Upload worker" messages
   - Restart application if worker crashed

## Security Best Practices

### Certificate Management

1. **Storage**:
   - Store certificates in password manager or encrypted storage
   - Never commit certificates to git
   - Use separate certificates per site

2. **Rotation**:
   - Rotate certificates annually
   - Use AWS IoT certificate rotation feature

3. **Backups**:
   - Keep secure backups of all certificates
   - Store in multiple secure locations

### Access Control

1. **Balena Access**:
   - Use Balena organizations for team access
   - Enable 2FA for all Balena accounts
   - Use separate Balena apps per customer/region

2. **AWS Access**:
   - Use IAM roles with least privilege
   - Separate AWS accounts per customer
   - Enable CloudTrail for audit logging

3. **Web Interface**:
   - Always enable authentication in production
   - Change default password immediately
   - Use HTTPS (behind reverse proxy if needed)

### Network Security

1. **VPN Access**:
   - Use OpenVPN for remote site access
   - Teltonika routers support built-in OpenVPN

2. **Firewall**:
   - Only expose necessary ports (443, 8883)
   - Use security groups in AWS
   - Configure router firewall rules

## Multi-Site Deployment

For deploying to many sites:

### Batch Provisioning

```bash
# Create CSV with site details
cat > sites.csv <<EOF
site_id,site_name,transformer_sn,address,timezone
SITE_001,Main Substation,TX-001,123 Main St,America/New_York
SITE_002,East Substation,TX-002,456 East St,America/New_York
SITE_003,West Substation,TX-003,789 West St,America/Chicago
EOF

# Batch provision
while IFS=, read -r site_id site_name tx_sn address tz; do
  echo "Provisioning $site_id..."
  python scripts/provision/provision_site.py \
    --site-id "$site_id" \
    --site-name "$site_name" \
    --transformer-sn "$tx_sn" \
    --address "$address" \
    --timezone "$tz" \
    --aws-region us-east-1
done < <(tail -n +2 sites.csv)
```

### Fleet Deployment

1. **Provision all sites** (generates certificates and configs)
2. **Pre-configure SD cards** with Balena OS
3. **Ship to site technicians** with installation instructions
4. **Upload certificates remotely** after devices come online

## Support and Resources

### Documentation

- [Transformer Monitor README](./README.md)
- [Test Suite Documentation](./tests/README.md)
- [Deployment Plan](./DEPLOYMENT_PLAN.md)
- [Remote Access Strategy](./REMOTE_ACCESS_STRATEGY.md)

### AWS Resources

- [AWS IoT Core Developer Guide](https://docs.aws.amazon.com/iot/latest/developerguide/)
- [AWS IoT Device SDK for Python](https://github.com/aws/aws-iot-device-sdk-python-v2)
- [S3 Developer Guide](https://docs.aws.amazon.com/s3/index.html)

### Balena Resources

- [Balena Documentation](https://www.balena.io/docs/)
- [Balena CLI Reference](https://www.balena.io/docs/reference/balena-cli/)
- [balenaHub (Docker images)](https://hub.balena.io/)

### Hardware Resources

- [MLX90640 Datasheet](https://www.melexis.com/en/product/MLX90640/)
- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
- [Teltonika RUT955 Manual](https://teltonika-networks.com/products/routers/rut955/)

## Appendix

### Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| SITE_ID | Yes | Unique site identifier | `SITE_001` |
| SITE_NAME | Yes | Human-readable name | `Main Substation` |
| TRANSFORMER_SN | Yes | Transformer serial | `TX-12345` |
| TIMEZONE | Yes | Site timezone | `America/New_York` |
| AWS_REGION | Yes | AWS region | `us-east-1` |
| IOT_ENDPOINT | Yes | AWS IoT endpoint | `xxx.iot.us-east-1.amazonaws.com` |
| IOT_THING_NAME | Yes | AWS IoT thing name | `SITE_001-monitor` |
| PRODUCTION_MODE | Yes | Enable production mode | `true` |
| FTP_HOST | No | FTP server | `ftp.example.com` |
| FTP_USERNAME | No | FTP username | `user` |
| FTP_PASSWORD | No | FTP password | `pass` |

### AWS IAM Policy

Required IAM permissions for provisioning:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:CreateThing",
        "iot:CreateKeysAndCertificate",
        "iot:CreatePolicy",
        "iot:AttachPolicy",
        "iot:AttachThingPrincipal",
        "iot:DescribeEndpoint"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:PutBucketPolicy"
      ],
      "Resource": "arn:aws:s3:::transformer-monitor-data-*"
    }
  ]
}
```

### Cost Estimation

Per-site monthly costs:

| Service | Cost | Notes |
|---------|------|-------|
| AWS IoT Core | $0.50 | ~30K messages/month |
| AWS S3 | $0.50 | ~10GB storage |
| AWS Data Transfer | $1.00 | Outbound data |
| Balena | $2.00 | Per device (optional) |
| Cellular Data (Teltonika) | $10-30 | Varies by plan |
| **Total** | **$14-34/site/month** | Without cellular: $2-4 |

### Changelog

- **v1.0.0** (2024-01-XX) - Initial provisioning system
- **v1.1.0** (2024-XX-XX) - Added Balena support
- **v1.2.0** (2024-XX-XX) - Batch provisioning support
