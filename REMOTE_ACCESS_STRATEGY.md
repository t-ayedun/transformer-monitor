# Remote Access & Fleet Management Strategy

## Executive Summary

This document extends the main deployment plan with remote access, fleet management, and cellular connectivity strategies for production transformer monitoring sites.

**Key Technologies**:
- **Balena**: Fleet management and remote deployment
- **OpenVPN**: Secure remote access to devices
- **Teltonika Router**: Industrial cellular gateway with failover

---

## Table of Contents

1. [Network Architecture](#1-network-architecture)
2. [Balena Fleet Management](#2-balena-fleet-management)
3. [OpenVPN Remote Access](#3-openvpn-remote-access)
4. [Teltonika Router Integration](#4-teltonika-router-integration)
5. [Deployment Strategy](#5-deployment-strategy)
6. [Security Considerations](#6-security-considerations)
7. [Troubleshooting & Maintenance](#7-troubleshooting--maintenance)

---

## 1. Network Architecture

### Standard Site Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         REMOTE SITE                             │
│                                                                 │
│  ┌──────────────────┐         ┌─────────────────┐              │
│  │  Raspberry Pi 4  │────────▶│   Teltonika     │              │
│  │  Transformer     │  Eth    │   RUT955/RUT956 │              │
│  │    Monitor       │         │   Router        │              │
│  └──────────────────┘         └────────┬────────┘              │
│                                        │                        │
│                                   Dual WAN:                     │
│                                   ├─ 4G/LTE (Primary)           │
│                                   └─ Ethernet (Backup)          │
│                                        │                        │
└────────────────────────────────────────┼────────────────────────┘
                                         │
                                    INTERNET
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
            ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
            │  AWS IoT     │    │   Balena     │    │   OpenVPN    │
            │   Core       │    │   Cloud      │    │   Server     │
            │  (MQTT/S3)   │    │  (Fleet)     │    │  (Access)    │
            └──────────────┘    └──────────────┘    └──────────────┘
```

### Network Redundancy Strategy

**Primary Connection**: 4G/LTE via Teltonika router
- Always-on cellular connectivity
- Typical bandwidth: 10-50 Mbps
- Latency: 50-150ms
- Data allowance: 5-20 GB/month per site

**Backup Connection**: Ethernet (if available)
- Automatic failover via Teltonika
- Used when 4G signal weak
- Preferred for large uploads

**Offline Operation**: Local buffering
- All data saved locally first
- Auto-sync when connectivity restored
- Up to 7 days of buffered data

---

## 2. Balena Fleet Management

### Why Balena?

**Benefits**:
- ✅ Over-the-air (OTA) updates for entire fleet
- ✅ Remote device access via balenaCloud
- ✅ Device health monitoring
- ✅ Environment variable management per site
- ✅ Application versioning and rollback
- ✅ Built-in VPN for secure access
- ✅ Docker-based deployment (already using Docker)

### Balena Architecture

```
┌────────────────────────────────────────────────────────┐
│                    BALENA CLOUD                        │
│                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Fleet      │  │  Application │  │  Release    │ │
│  │  Management  │  │   Versions   │  │  History    │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Device List │  │ Environment  │  │   Logs &    │ │
│  │   (Sites)    │  │  Variables   │  │  Metrics    │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
└────────────────────────┬───────────────────────────────┘
                         │ balenaOS + Supervisor
                         ▼
          ┌─────────────────────────────────┐
          │     Raspberry Pi @ Site         │
          │                                 │
          │  ┌────────────────────────────┐ │
          │  │  transformer-monitor       │ │
          │  │  (Docker Container)        │ │
          │  │                            │ │
          │  │  - Python app              │ │
          │  │  - Config from env vars    │ │
          │  │  - Logs to balena          │ │
          │  └────────────────────────────┘ │
          │                                 │
          │  ┌────────────────────────────┐ │
          │  │  balenaEngine (Docker)     │ │
          │  └────────────────────────────┘ │
          │                                 │
          │  ┌────────────────────────────┐ │
          │  │  balenaOS (Yocto Linux)    │ │
          │  └────────────────────────────┘ │
          └─────────────────────────────────┘
```

### Balena Configuration Files

#### `balena.yml` (Fleet Configuration)
```yaml
name: transformer-monitor-fleet
type: raspberrypi4-64
description: "Transformer thermal monitoring edge devices"

data:
  applicationEnvironmentVariables:
    - PRODUCTION_MODE: "true"
    - LOG_LEVEL: "INFO"
    - CAPTURE_INTERVAL: "60"
    - HEARTBEAT_INTERVAL: "300"

  defaultDeviceType: raspberrypi4-64

  supportedDeviceTypes:
    - raspberrypi4-64
    - raspberrypi3-64
```

#### `docker-compose.yml` (Multi-Container App)
```yaml
version: '2.1'

services:
  # Main application
  transformer-monitor:
    build: .
    privileged: true  # Required for I2C, camera access
    network_mode: host
    restart: always

    volumes:
      - 'data:/data'
      - '/dev:/dev'  # Hardware access

    devices:
      - "/dev/i2c-1:/dev/i2c-1"  # Thermal camera
      - "/dev/video0:/dev/video0"  # Pi camera
      - "/dev/gpiomem:/dev/gpiomem"

    environment:
      # Site-specific (set via balena dashboard)
      - SITE_ID
      - SITE_NAME
      - SITE_ADDRESS
      - TIMEZONE
      - TRANSFORMER_SN

      # AWS IoT (set via balena dashboard)
      - IOT_ENDPOINT
      - IOT_THING_NAME
      - AWS_REGION
      - S3_BUCKET_NAME

      # FTP (optional, set via balena dashboard)
      - FTP_HOST
      - FTP_USERNAME
      - FTP_PASSWORD

      # System
      - PRODUCTION_MODE=true
      - UDEV=1  # Enable hardware detection

    labels:
      io.balena.features.kernel-modules: '1'
      io.balena.features.firmware: '1'
      io.balena.features.dbus: '1'
      io.balena.features.supervisor-api: '1'
      io.balena.features.balena-api: '1'

  # Optional: MQTT bridge for local data access
  mqtt-bridge:
    image: eclipse-mosquitto:latest
    restart: always
    ports:
      - "1883:1883"
    volumes:
      - 'mqtt-data:/mosquitto/data'

volumes:
  data:
  mqtt-data:
```

#### `Dockerfile.template` (Balena-Optimized)
```dockerfile
# Use balena base image for Raspberry Pi 4
FROM balenalib/raspberrypi4-64-debian:bullseye

# Install system dependencies
RUN install_packages \
    python3 \
    python3-pip \
    python3-dev \
    i2c-tools \
    libopencv-dev \
    libatlas-base-dev \
    libhdf5-dev \
    libjasper-dev \
    libqtgui4 \
    libqt4-test \
    && apt-get clean

# Enable I2C
RUN echo "dtparam=i2c_arm=on" >> /boot/config.txt

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create data directory
RUN mkdir -p /data/buffer /data/images /data/videos /data/certs /data/logs

# Expose web interface port
EXPOSE 5000

# Set entrypoint
CMD ["python3", "src/main.py"]
```

### Balena Device Variables (Per Site)

Set these via Balena dashboard for each device:

| Variable | Example | Description |
|----------|---------|-------------|
| `SITE_ID` | `SITE_001` | Unique site identifier |
| `SITE_NAME` | `Downtown Substation` | Human-readable name |
| `SITE_ADDRESS` | `123 Main St, City` | Physical location |
| `TIMEZONE` | `America/New_York` | Local timezone |
| `TRANSFORMER_SN` | `TX-12345` | Transformer serial number |
| `IOT_ENDPOINT` | `xxxxx.iot.us-east-1.amazonaws.com` | AWS IoT endpoint |
| `IOT_THING_NAME` | `transformer-monitor-SITE_001` | AWS IoT thing name |
| `AWS_REGION` | `us-east-1` | AWS region |
| `S3_BUCKET_NAME` | `transformer-monitor-data` | S3 bucket for uploads |

### Balena Fleet Operations

#### Deploy to Fleet
```bash
# 1. Install balena CLI
npm install -g balena-cli

# 2. Login
balena login

# 3. Create fleet (first time)
balena fleet create transformer-monitor-fleet \
  --type raspberrypi4-64

# 4. Push application
cd /path/to/transformer-monitor
balena push transformer-monitor-fleet

# Balena builds and deploys to ALL devices in fleet
```

#### Add New Device to Fleet
```bash
# 1. Download balenaOS image
balena os download raspberrypi4-64 --version latest

# 2. Configure image with WiFi/credentials
balena os configure downloaded-image.img \
  --fleet transformer-monitor-fleet \
  --config-network ethernet

# 3. Flash to SD card
balena local flash downloaded-image.img

# 4. Insert SD card into Pi and power on
# Device auto-registers with fleet
```

#### Update Entire Fleet
```bash
# Simply push new code
balena push transformer-monitor-fleet

# Balena automatically:
# - Builds new Docker image
# - Deploys to all devices
# - Rolling update (no downtime)
# - Rollback available if issues
```

#### Monitor Fleet
```bash
# View all devices
balena devices

# View device logs
balena logs <device-uuid> --tail

# SSH into device
balena ssh <device-uuid>

# Check device status
balena device <device-uuid>
```

---

## 3. OpenVPN Remote Access

### Architecture

```
┌────────────────────────────────────────────────────┐
│                 CENTRAL VPN SERVER                 │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  OpenVPN Server (UDP 1194)                   │ │
│  │  - Certificate Authority                     │ │
│  │  - Client certificates per technician        │ │
│  │  - IP pool: 10.8.0.0/24                     │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  Routes to Site Networks                     │ │
│  │  - 192.168.1.0/24 → SITE_001                │ │
│  │  - 192.168.2.0/24 → SITE_002                │ │
│  │  - 192.168.3.0/24 → SITE_003                │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ SITE_001 │   │ SITE_002 │   │ SITE_003 │
    │ Teltonika│   │ Teltonika│   │ Teltonika│
    │  Router  │   │  Router  │   │  Router  │
    │          │   │          │   │          │
    │ VPN      │   │ VPN      │   │ VPN      │
    │ Client   │   │ Client   │   │ Client   │
    └─────┬────┘   └─────┬────┘   └─────┬────┘
          │              │              │
          ▼              ▼              ▼
      Raspberry      Raspberry      Raspberry
         Pi             Pi             Pi
    192.168.1.100  192.168.2.100  192.168.3.100
```

### OpenVPN Server Setup

#### Install on Ubuntu/Debian Server
```bash
#!/bin/bash
# install_openvpn_server.sh

# Install OpenVPN and Easy-RSA
apt-get update
apt-get install -y openvpn easy-rsa

# Initialize PKI
make-cadir ~/openvpn-ca
cd ~/openvpn-ca

# Configure CA
cat > vars <<EOF
set_var EASYRSA_REQ_COUNTRY    "US"
set_var EASYRSA_REQ_PROVINCE   "State"
set_var EASYRSA_REQ_CITY       "City"
set_var EASYRSA_REQ_ORG        "Transformer Monitor"
set_var EASYRSA_REQ_EMAIL      "admin@example.com"
set_var EASYRSA_REQ_OU         "IT Department"
EOF

# Build CA
./easyrsa init-pki
./easyrsa build-ca nopass

# Generate server certificate
./easyrsa gen-req server nopass
./easyrsa sign-req server server

# Generate DH parameters
./easyrsa gen-dh

# Generate TLS auth key
openvpn --genkey secret ta.key

# Copy to OpenVPN directory
cp pki/ca.crt /etc/openvpn/
cp pki/issued/server.crt /etc/openvpn/
cp pki/private/server.key /etc/openvpn/
cp ta.key /etc/openvpn/
cp pki/dh.pem /etc/openvpn/

# Create server config
cat > /etc/openvpn/server.conf <<EOF
port 1194
proto udp
dev tun
ca ca.crt
cert server.crt
key server.key
dh dh.pem
tls-auth ta.key 0

# VPN subnet
server 10.8.0.0 255.255.255.0

# Routes to site networks
push "route 192.168.1.0 255.255.255.0"
push "route 192.168.2.0 255.255.255.0"
push "route 192.168.3.0 255.255.255.0"

# Client-to-client communication
client-to-client

# Keepalive
keepalive 10 120

# Compression
compress lz4-v2
push "compress lz4-v2"

# Logging
status /var/log/openvpn-status.log
log-append /var/log/openvpn.log
verb 3

# Security
cipher AES-256-CBC
auth SHA256
tls-version-min 1.2
EOF

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Configure firewall
ufw allow 1194/udp
ufw allow OpenSSH
ufw enable

# Start OpenVPN
systemctl start openvpn@server
systemctl enable openvpn@server
```

#### Generate Client Certificate (Per Site Router)
```bash
#!/bin/bash
# generate_site_vpn_cert.sh SITE_001

SITE_ID=$1

cd ~/openvpn-ca

# Generate client cert
./easyrsa gen-req $SITE_ID nopass
./easyrsa sign-req client $SITE_ID

# Create client config
cat > ~/${SITE_ID}.ovpn <<EOF
client
dev tun
proto udp
remote your-vpn-server.com 1194
resolv-retry infinite
nobind
persist-key
persist-tun

# Certificates inline
<ca>
$(cat pki/ca.crt)
</ca>

<cert>
$(cat pki/issued/${SITE_ID}.crt)
</cert>

<key>
$(cat pki/private/${SITE_ID}.key)
</key>

<tls-auth>
$(cat ta.key)
</tls-auth>
key-direction 1

# Security
cipher AES-256-CBC
auth SHA256
tls-version-min 1.2

# Compression
compress lz4-v2

# Logging
verb 3
EOF

echo "Client config created: ~/${SITE_ID}.ovpn"
echo "Upload this to Teltonika router"
```

---

## 4. Teltonika Router Integration

### Recommended Models

| Model | Features | Use Case |
|-------|----------|----------|
| **RUT955** | 4G LTE, Dual SIM, WiFi, I/O | Standard deployment |
| **RUT956** | 4G LTE Cat 6, Dual SIM, WiFi | High bandwidth sites |
| **RUT241** | 4G LTE, Compact | Space-constrained locations |
| **RUTX11** | 5G, WiFi 6, Dual SIM | Future-proof installations |

### Teltonika Configuration

#### 1. Basic Network Setup
```
Network → LAN
  - IP Address: 192.168.X.1 (X = site number)
  - DHCP: Enabled
  - DHCP Range: 192.168.X.100-200

Network → WAN
  - Primary: Mobile (4G/LTE)
  - Backup: WAN (Ethernet if available)
  - Failover: Enable
```

#### 2. OpenVPN Client Configuration
```
Services → VPN → OpenVPN

Configuration Type: Client
Remote Host/IP: your-vpn-server.com
Remote Port: 1194
Protocol: UDP
LZO Compression: Adaptive
TLS Authentication: Enabled

Upload Certificates:
  - CA Certificate: ca.crt
  - Client Certificate: SITE_XXX.crt
  - Client Key: SITE_XXX.key
  - TLS Auth Key: ta.key

Advanced:
  - Keep Alive: 10 120
  - Persist TUN: Enabled
  - Persist Key: Enabled
  - Auth Retry: nointeract
```

#### 3. Static IP for Raspberry Pi
```
Network → DHCP → Static Leases

MAC Address: [Pi's MAC address]
IP Address: 192.168.X.100
Hostname: transformer-monitor-SITEXX
```

#### 4. Port Forwarding (Optional for Direct Access)
```
Network → Firewall → Port Forwarding

Name: Web Interface
Protocol: TCP
External Port: 8080
Internal IP: 192.168.X.100
Internal Port: 5000
```

#### 5. Monitoring & Alerts
```
Services → Mobile Utilities → SMS

Enable SMS Alerts for:
  - VPN Connection Lost
  - Mobile Connection Lost
  - High Data Usage (>80% of limit)
  - Reboot Events

SMS Recipients: [Admin phone numbers]
```

#### 6. Data Usage Management
```
Services → Mobile Utilities → Data Limit

Monthly Data Limit: 10 GB
Warning at 80%: Send SMS
Action at 95%: Throttle speed
Reset Day: 1st of month
```

### Teltonika RMS (Remote Management)

**Benefits**:
- Centralized management of all routers
- Remote configuration changes
- Firmware updates
- Monitoring and alerts
- Troubleshooting tools

**Setup**:
```
System → RMS → RMS Settings

Enable RMS: Yes
RMS Server: https://rms.teltonika-networks.com
Register device to your account
```

---

## 5. Deployment Strategy

### Deployment Workflow

```
┌─────────────────────────────────────────────────────┐
│                  PREPARATION                        │
│                                                     │
│  1. Provision AWS IoT Thing                        │
│  2. Generate VPN certificates                      │
│  3. Configure Balena device variables              │
│  4. Pre-configure Teltonika router                 │
│  5. Flash Raspberry Pi with balenaOS              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                SITE INSTALLATION                    │
│                                                     │
│  1. Install Teltonika router                       │
│  2. Connect Raspberry Pi to router                 │
│  3. Install MLX90640 thermal camera                │
│  4. Install Pi Camera 3                            │
│  5. Power on and verify connectivity               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                REMOTE VALIDATION                    │
│                                                     │
│  1. Check Balena dashboard (device online)         │
│  2. Verify VPN connection (ping device)            │
│  3. Access web interface via VPN                   │
│  4. Configure ROIs via web interface               │
│  5. Verify AWS IoT telemetry                       │
│  6. Verify S3 uploads                              │
└─────────────────────────────────────────────────────┘
```

### Pre-Deployment Checklist

**AWS Configuration**:
- [ ] IoT Thing created
- [ ] Certificates generated and downloaded
- [ ] IoT Policy attached
- [ ] S3 bucket created with encryption
- [ ] CloudWatch alarms configured

**VPN Configuration**:
- [ ] Client certificate generated for site
- [ ] .ovpn file uploaded to Teltonika
- [ ] VPN route added for site subnet
- [ ] Firewall rules configured

**Balena Configuration**:
- [ ] Device added to fleet
- [ ] Environment variables set
- [ ] AWS certificates uploaded (base64 encoded)
- [ ] Latest application deployed

**Hardware Preparation**:
- [ ] Raspberry Pi 4 (4GB+ RAM)
- [ ] balenaOS flashed to SD card
- [ ] MLX90640 thermal camera
- [ ] Pi Camera 3
- [ ] Teltonika router pre-configured
- [ ] Power supply (5V 3A for Pi)
- [ ] Weatherproof enclosure
- [ ] Mounting hardware

### Site Installation Script

Create a **site installation guide** that field technicians can follow:

```markdown
# Site Installation Guide - SITE_XXX

## Equipment
- Pre-configured Teltonika RUT955 router
- Raspberry Pi 4 with balenaOS
- MLX90640 thermal camera
- Pi Camera 3
- Cables and mounting hardware

## Steps

### 1. Router Installation
1. Mount Teltonika router in secure location
2. Connect 4G antenna to router
3. Insert SIM card (check activation)
4. Connect power (12-24V DC)
5. Wait 2 minutes for boot
6. Verify LED status:
   - Power: Green solid
   - Mobile: Green blinking
   - WiFi: Green solid

### 2. Raspberry Pi Setup
1. Connect thermal camera to I2C pins
2. Connect Pi Camera to CSI port
3. Connect Ethernet cable to Teltonika
4. Connect power to Pi
5. Wait 5 minutes for first boot

### 3. Verification
1. Check Balena dashboard:
   - Device shows "Online"
   - Application downloaded

2. Connect to VPN from laptop

3. Access web interface:
   http://192.168.X.100:5000

4. Verify cameras working:
   - Thermal stream visible
   - Visual stream visible

5. Contact central team for final validation

## Troubleshooting

**Device not showing in Balena**:
- Check Ethernet cable connection
- Verify router has internet (4G/LTE connected)
- Check router DHCP assigned IP to Pi
- Wait 10 minutes for initial sync

**Cannot access via VPN**:
- Verify VPN shows connected on router
- Check firewall rules on router
- Verify correct subnet (192.168.X.0/24)
- Try rebooting router

**Thermal camera not working**:
- Check I2C connection (GPIO pins 3 & 5)
- SSH to device: `i2cdetect -y 1` should show 0x33
- Check camera power (3.3V)

**Support Contact**: [Your phone/email]
```

---

## 6. Security Considerations

### Network Security

**Teltonika Firewall**:
```
Firewall → General Settings
  - SPI Firewall: Enabled
  - Drop Invalid Packets: Enabled

Firewall → Traffic Rules
  - Block all incoming from WAN
  - Allow VPN to LAN
  - Allow LAN to WAN (outbound only)
```

**VPN Only Access**:
- **Do NOT** expose ports directly to internet
- **All** remote access via VPN
- Use strong VPN certificates (4096-bit RSA)

### Application Security

**Balena Security**:
- Use Balena's built-in SSH (authenticated via Balena account)
- Enable 2FA on Balena account
- Limit team member access per role

**AWS Security**:
- Unique certificates per device
- Least-privilege IoT policies
- Rotate certificates annually
- Monitor CloudTrail for unauthorized access

### Physical Security

**Enclosure**:
- Weatherproof NEMA 4X rated
- Tamper-evident seals
- Locked (physical lock)

**Installation**:
- Mount out of reach (>2m height)
- Hide cables in conduit
- Secure router and Pi separately

---

## 7. Troubleshooting & Maintenance

### Remote Diagnostics via Balena

```bash
# SSH into device
balena ssh <device-uuid>

# Check running containers
balena ps

# View logs
balena logs transformer-monitor --tail 100

# Restart application
balena restart transformer-monitor

# Check I2C devices
i2cdetect -y 1

# Check network
ping 8.8.8.8
traceroute aws-iot-endpoint

# Check disk space
df -h

# Check memory
free -h
```

### Remote Diagnostics via VPN

```bash
# Connect VPN
sudo openvpn admin.ovpn

# SSH to device
ssh pi@192.168.X.100

# Check service status
systemctl status transformer-monitor

# View logs
journalctl -u transformer-monitor -f

# Check health
curl http://192.168.X.100:5000/health/deep | jq

# Restart service
sudo systemctl restart transformer-monitor
```

### Common Issues

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Device offline in Balena | No internet | Check Teltonika 4G signal, reboot router |
| VPN not connecting | Certificate issue | Regenerate cert, re-upload to router |
| High data usage | Video uploads | Adjust snapshot/video intervals |
| Thermal camera errors | I2C issue | Check connections, try `i2cdetect -y 1` |
| AWS upload failures | Certificate expired | Rotate AWS IoT certificates |
| Slow VPN | Bandwidth limit | Check Teltonika data usage, upgrade plan |

### Maintenance Schedule

**Weekly**:
- [ ] Check Balena dashboard (all devices online)
- [ ] Review AWS CloudWatch alerts
- [ ] Check VPN connection status

**Monthly**:
- [ ] Review data usage per site
- [ ] Check for application updates
- [ ] Verify backup connectivity

**Quarterly**:
- [ ] On-site inspection (if possible)
- [ ] Review and update firmware (Teltonika, Raspberry Pi)
- [ ] Clean camera lenses
- [ ] Check physical security

**Annually**:
- [ ] Rotate AWS IoT certificates
- [ ] Renew VPN certificates
- [ ] Review and optimize data capture intervals
- [ ] Update Balena application

---

## 8. Cost Analysis

### Per-Site Monthly Costs

| Item | Cost | Notes |
|------|------|-------|
| 4G/LTE Data Plan | $20-40 | 5-20 GB/month |
| Balena (up to 10 devices) | $0 | Free tier |
| Balena (10+ devices) | $15/device | Standard plan |
| VPN Server | $10-20 | Shared across all sites |
| AWS IoT/S3 | $2-5 | Per site |
| **Total (1-10 sites)** | **$32-65/site** | |
| **Total (10+ sites)** | **$47-80/site** | |

### One-Time Setup Costs

| Item | Cost | Quantity |
|------|------|----------|
| Teltonika RUT955 | $200 | Per site |
| Raspberry Pi 4 (4GB) | $55 | Per site |
| MLX90640 Sensor | $60 | Per site |
| Pi Camera 3 | $25 | Per site |
| Enclosure & Mounting | $50 | Per site |
| **Total Hardware** | **$390/site** | |
| VPN Server Setup | $100 | One-time |
| Balena Fleet Setup | $0 | One-time |

**ROI Calculation** (100 sites):
- Monthly: $3,900 - $6,500
- Annual: $46,800 - $78,000
- Hardware: $39,000 (one-time)
- Total Year 1: $85,800 - $117,000

---

## 9. Implementation Checklist

### Phase 1: Infrastructure Setup
- [ ] Set up OpenVPN server
- [ ] Create Balena fleet
- [ ] Prepare Docker configuration for Balena
- [ ] Test VPN connectivity
- [ ] Test Balena deployment

### Phase 2: Pilot Deployment (2 sites)
- [ ] Provision AWS IoT Things
- [ ] Generate VPN certificates
- [ ] Configure Teltonika routers
- [ ] Flash Raspberry Pi with balenaOS
- [ ] Install at pilot sites
- [ ] Remote validation
- [ ] Monitor for 2 weeks

### Phase 3: Scale Rollout
- [ ] Refine deployment process
- [ ] Create site installation kits
- [ ] Train field technicians
- [ ] Deploy to remaining sites
- [ ] Set up monitoring dashboards

---

## 10. Next Steps

1. **Immediate**:
   - Review and approve remote access strategy
   - Decide on VPN vs. Balena VPN vs. both
   - Select Teltonika router model
   - Set up Balena account

2. **Week 1**:
   - Set up OpenVPN server OR use Balena VPN
   - Create Balena fleet
   - Adapt Docker configuration
   - Order pilot hardware

3. **Week 2-3**:
   - Configure pilot routers
   - Prepare pilot Raspberry Pis
   - Deploy pilot sites
   - Validate remote access

4. **Week 4+**:
   - Scale deployment
   - Monitor and optimize

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Author**: Claude (AI Assistant)
**Status**: Awaiting Approval
