# 🔥 Transformer Thermal Monitor - Complete Deployment Guide

**Version:** 1.0  
**Last Updated:** December 2024  
**Supported Hardware:** Raspberry Pi 4B, Raspberry Pi 5

---

## 📋 Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Hardware Setup](#hardware-setup)
3. [Network Configuration (Teltonika Router)](#network-configuration-teltonika-router)
4. [Raspberry Pi Initial Setup](#raspberry-pi-initial-setup)
5. [Software Installation](#software-installation)
6. [Site Configuration](#site-configuration)
7. [AWS IoT Core Setup (Optional)](#aws-iot-core-setup-optional)
8. [FTP Data Transfer (Recommended)](#ftp-data-transfer-recommended)
9. [ROI Configuration](#roi-configuration)
10. [Remote Access (RMS Connect)](#remote-access-rms-connect)
11. [Testing & Validation](#testing--validation)
12. [Production Deployment](#production-deployment)
13. [Troubleshooting](#troubleshooting)
14. [Maintenance](#maintenance)
15. [Quick Command Reference](#quick-command-reference)

---

## 1. Pre-Deployment Checklist

### 📦 **Equipment Required**

**Hardware:**
- [ ] Raspberry Pi 4B or Pi 5 (4GB+ RAM recommended)
- [ ] MLX90640 Thermal Camera (I2C interface)
- [ ] Raspberry Pi Camera Module 3
- [ ] 32GB+ microSD card (Class 10 or better)
- [ ] 5V 3A USB-C power supply (official Raspberry Pi adapter)
- [ ] Ethernet cable (Cat5e or better)
- [ ] Weatherproof enclosure (if outdoor installation)
- [ ] Mounting hardware

**Network:**
- [ ] Teltonika router with RMS Connect enabled
- [ ] Active SIM card with data plan (if using cellular)
- [ ] Ethernet port available on router

**Tools:**
- [ ] Laptop/tablet for initial configuration
- [ ] microSD card reader
- [ ] Screwdriver set
- [ ] Cable ties/organizers

**Software/Accounts:**
- [ ] AWS account with IoT Core access
- [ ] Teltonika RMS Connect account
- [ ] GitHub account (for code access)
- [ ] SSH client (Terminal on Mac/Linux, PuTTY on Windows)

---

## 2. Hardware Setup

### 🔌 **Physical Connections**

#### **Step 1: Connect Thermal Camera (MLX90640)**

```
MLX90640 Pin    →    Raspberry Pi Pin
─────────────────────────────────────
VIN (3.3V)      →    Pin 1 (3.3V)
GND             →    Pin 6 (GND)
SCL             →    Pin 5 (GPIO 3 / SCL)
SDA             →    Pin 3 (GPIO 2 / SDA)
```

**Important:**
- Use short wires (< 15cm) to minimize I2C interference
- Double-check polarity - reversed power can damage the sensor
- Ensure secure connections - loose wires cause intermittent failures

#### **Step 2: Connect Pi Camera Module 3**

1. Locate the camera connector (between HDMI ports)
2. Gently pull up the black plastic clip
3. Insert ribbon cable with blue side facing Ethernet port
4. Push down the clip to secure

**Important:**
- Handle ribbon cable carefully - it's fragile
- Ensure cable is fully inserted and straight
- Camera lens should face away from the Pi

#### **Step 3: Connect to Teltonika Router**

1. Connect Ethernet cable from Pi to any LAN port on Teltonika router
2. Connect power supply to Pi (do NOT power on yet)

---

## 3. Network Configuration (Teltonika Router)

### 🌐 **Router Setup**

#### **Step 1: Access Router Web Interface**

```bash
# Default router IP (check your router model)
http://192.168.1.1

# Default credentials (CHANGE THESE!)
Username: admin
Password: admin01
```

#### **Step 2: Configure DHCP Reservation**

1. Navigate to **Network → LAN → DHCP Server**
2. Find the Raspberry Pi in connected devices (hostname: `smarterise-site-X`)
3. Click "Add Static Lease"
4. Assign a fixed IP (e.g., `192.168.1.100`)
5. Save and apply

**Why:** Ensures Pi always gets the same IP address for remote access

#### **Step 3: Enable Port Forwarding (Optional)**

If you need direct SSH access without RMS:

1. Navigate to **Network → Firewall → Port Forwarding**
2. Add rule:
   - **Name:** SSH-Pi-Site-A
   - **Protocol:** TCP
   - **External Port:** 2222 (or any high port)
   - **Internal IP:** 192.168.1.100 (your Pi's IP)
   - **Internal Port:** 22
3. Save and apply

**Security Warning:** Only enable if absolutely necessary. Use RMS Connect instead.

#### **Step 4: Verify Internet Connection**

1. Check router status: **System → Administration → Status**
2. Verify mobile connection is active
3. Note the public IP address (needed for remote access)

---

## 4. Raspberry Pi Initial Setup

### 💿 **Prepare SD Card**

#### **Step 1: Download Raspberry Pi OS**

```bash
# Use Raspberry Pi Imager (recommended)
# Download from: https://www.raspberrypi.com/software/

# Choose:
# - OS: Raspberry Pi OS Lite (64-bit) - No desktop needed
# - Storage: Your microSD card
```

#### **Step 2: Configure OS Settings (BEFORE Writing)**

Click the gear icon ⚙️ in Raspberry Pi Imager:

```
Hostname: smarterise-site-a  (change per site)
Enable SSH: ✓ Use password authentication
Username: smartie
Password: [CREATE STRONG PASSWORD]
Wireless LAN: [SKIP - using Ethernet]
Locale: Africa/Lagos
Keyboard: us
```

#### **Step 3: Write Image and Boot**

1. Click "Write" and wait for completion
2. Insert SD card into Raspberry Pi
3. Connect Ethernet cable
4. Connect power supply
5. Wait 2-3 minutes for first boot

#### **Step 4: Find Pi's IP Address**

**Option A:** Check router's connected devices list

**Option B:** Use network scanner
```bash
# On your laptop (same network)
nmap -sn 192.168.1.0/24 | grep smarterise
```

**Option C:** Connect monitor and keyboard, run:
```bash
hostname -I
```

---

## 5. Software Installation

### 📥 **Initial SSH Connection**

```bash
# From your laptop
ssh smartie@192.168.1.100

# First login will ask to accept fingerprint - type 'yes'
# Enter the password you set during imaging
```

### 🔧 **System Update**

```bash
# Update package lists
sudo apt-get update

# Upgrade all packages (takes 5-10 minutes)
sudo apt-get upgrade -y

# Reboot
sudo reboot

# Wait 1 minute, then reconnect
ssh smartie@192.168.1.100
```

### 🐍 **Install Dependencies**

```bash
# Install system packages
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    i2c-tools \
    git \
    libatlas-base-dev \
    libopenjp2-7 \
    libtiff5 \
    libgfortran5 \
    python3-lgpio \
    python3-rpi-lgpio

# Enable I2C and Camera
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
# Navigate to: Interface Options → Camera → Enable
# Select Finish → Reboot? Yes

# Wait 1 minute, reconnect
ssh smartie@192.168.1.100
```

### 📦 **Clone Repository**

```bash
# Clone the project
cd ~
git clone https://github.com/t-ayedun/transformer-monitor.git
cd transformer-monitor

# Checkout stable branch
git checkout stable-deployment

# Verify you're on the right branch
git branch
# Should show: * stable-deployment
```

### 🔨 **Install Python Dependencies**

```bash
# Install system-wide (recommended for Pi)
pip3 install --break-system-packages -r requirements.txt

# This takes 10-15 minutes
# Ignore warnings about "externally-managed-environment"
```

### ✅ **Verify Hardware**

```bash
# Check I2C devices (should see 0x33)
i2cdetect -y 1

# Expected output:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:                         -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- -- -- 33 -- -- -- -- -- -- -- -- -- -- -- --
# ...

# Check camera
libcamera-hello --list-cameras

# Expected output:
# Available cameras
# 0 : imx708 [4608x2592] (/base/soc/i2c0mux/i2c@1/imx708@1a)
```

**If thermal camera (0x33) not detected:**
```bash
# Check wiring
# Reboot and try again
sudo reboot
```

---

## 6. Site Configuration

### ⚙️ **Create Configuration Files**

```bash
# Create data directories
sudo mkdir -p /data/{config,logs,images,buffer,certs}
sudo chown -R smartie:smartie /data

# Copy template to active config
cp config/site_config.template.yaml /data/config/site_config.yaml

# Edit site configuration
nano /data/config/site_config.yaml
```

### 📝 **Site Configuration Template**

Edit `/data/config/site_config.yaml`:

```yaml
# SITE INFORMATION
site:
  id: "SITE_A"  # ← CHANGE THIS (unique per site)
  name: "Transformer Station Alpha"  # ← CHANGE THIS
  location:
    address: "123 Power Street, Lagos"  # ← CHANGE THIS
    latitude: 6.5244  # ← CHANGE THIS (optional)
    longitude: 3.3792  # ← CHANGE THIS (optional)
  timezone: "Africa/Lagos"

# TRANSFORMER DETAILS
transformer:
  type: "Distribution Transformer"
  rating_kva: 500  # ← CHANGE THIS
  serial_number: "TRF-2024-001"  # ← CHANGE THIS
  manufacturer: "ABB"  # ← CHANGE THIS
  installation_date: "2024-01-15"  # ← CHANGE THIS

# THERMAL CAMERA
thermal_camera:
  model: "MLX90640"
  i2c_address: 0x33  # Don't change unless using different address
  i2c_bus: 1
  refresh_rate: 2  # 2 Hz for Pi 5, can use 8 for Pi 4
  resolution: [32, 24]
  emissivity: 0.95

# DATA CAPTURE
data_capture:
  interval: 60  # Capture every 60 seconds
  sync_to_minute: true  # Sync to top of minute
  save_full_frame_interval: 10  # Save full frame every 10 captures
  buffer_size: 100

# PI CAMERA
pi_camera:
  enabled: true
  model: "Pi Camera 3"
  resolution: [1920, 1080]
  framerate: 30
  quality: 85
  
  motion_detection:
    enabled: true
    threshold: 1500
    min_area: 500
    
  recording:
    pre_record_seconds: 10
    post_record_seconds: 10
    max_duration_seconds: 300
    
  snapshot_interval: 1800  # 30 minutes
  
  night_mode:
    enabled: true
    start_hour: 18
    end_hour: 6
    
  storage:
    max_local_storage_gb: 10
    auto_cleanup_days: 7

# LOCAL STORAGE
local_storage:
  enabled: true
  database_path: "/data/buffer/readings.db"
  max_size_mb: 500
  retention_days: 7

# NETWORK
network:
  router:
    local_ip: "192.168.1.1"
  pi:
    static_ip: "192.168.1.100"  # ← CHANGE THIS (match DHCP reservation)
  connectivity:
    check_interval: 60

# HEARTBEAT
heartbeat:
  enabled: true
  interval: 300  # 5 minutes

# LOGGING
logging:
  level: "INFO"
  max_file_size_mb: 10
  backup_count: 5
  log_to_console: true

# AWS IoT (configure in next section)
aws:
  iot:
    enabled: false  # Set to true after AWS setup
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## 7. AWS IoT Core Setup (Optional)

### ☁️ **AWS Console Configuration**

#### **Step 1: Create IoT Thing**

1. Log into AWS Console: https://console.aws.amazon.com
2. Navigate to **IoT Core** (search in services)
3. Select region: **us-east-1** (or your preferred region)
4. Go to **Manage → All devices → Things**
5. Click **Create things**
6. Select **Create single thing**
7. Thing name: `transformer-site-a` (match your site ID)
8. Click **Next**
9. **Auto-generate certificates** (recommended)
10. Click **Create thing**

#### **Step 2: Download Certificates**

**CRITICAL:** Download these files immediately (you can't download them again):

- ✅ Device certificate (`xxxxxxx-certificate.pem.crt`)
- ✅ Private key (`xxxxxxx-private.pem.key`)
- ✅ Root CA certificate (Amazon Root CA 1)

**Save these files securely** - you'll upload them to the Pi later.

#### **Step 3: Create IoT Policy**

1. Go to **Secure → Policies**
2. Click **Create policy**
3. Policy name: `TransformerMonitorPolicy`
4. Add statements:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect",
        "iot:Publish",
        "iot:Subscribe",
        "iot:Receive"
      ],
      "Resource": "*"
    }
  ]
}
```

5. Click **Create**

#### **Step 4: Attach Policy to Certificate**

1. Go to **Secure → Certificates**
2. Find your certificate (created in Step 1)
3. Click on it
4. Go to **Policies** tab
5. Click **Attach policies**
6. Select `TransformerMonitorPolicy`
7. Click **Attach**

#### **Step 5: Get IoT Endpoint**

1. Go to **Settings** (left sidebar)
2. Copy **Device data endpoint** (e.g., `xxxxxx-ats.iot.us-east-1.amazonaws.com`)
3. Save this - you'll need it for configuration

#### **Step 6: Create S3 Bucket (for images)**

1. Navigate to **S3** service
2. Click **Create bucket**
3. Bucket name: `transformer-monitor-site-a` (must be globally unique)
4. Region: Same as IoT Core (e.g., us-east-1)
5. Block all public access: ✓ (keep checked)
6. Click **Create bucket**

### 📤 **Upload Certificates to Pi**

**From your laptop:**

```bash
# Navigate to where you downloaded the certificates
cd ~/Downloads

# Upload to Pi (replace with your actual filenames)
scp xxxxxxx-certificate.pem.crt smartie@192.168.1.100:/data/certs/device.crt
scp xxxxxxx-private.pem.key smartie@192.168.1.100:/data/certs/private.key
scp AmazonRootCA1.pem smartie@192.168.1.100:/data/certs/root-ca.pem

# Set correct permissions
ssh smartie@192.168.1.100
chmod 600 /data/certs/*.key
chmod 644 /data/certs/*.crt /data/certs/*.pem
```

### 🔧 **Configure AWS in Site Config**

**On the Pi:**

```bash
nano /data/config/site_config.yaml
```

Add/update AWS section:

```yaml
aws:
  iot:
    enabled: true  # ← Change to true
    endpoint: "xxxxxx-ats.iot.us-east-1.amazonaws.com"  # ← Your endpoint
    thing_name: "transformer-site-a"  # ← Your thing name
    region: "us-east-1"  # ← Your region
    
    certificates:
      ca_cert: "/data/certs/root-ca.pem"
      device_cert: "/data/certs/device.crt"
      private_key: "/data/certs/private.key"
    
    topics:
      telemetry: "transformer/site-a/telemetry"
      heartbeat: "transformer/site-a/heartbeat"
      alerts: "transformer/site-a/alerts"
      events: "transformer/site-a/events"
  
  s3:
    enabled: true
    bucket_name: "transformer-monitor-site-a"  # ← Your bucket name
    region: "us-east-1"

# Thermal publishing configuration
thermal_publishing:
  enabled: true
  telemetry:
    publish_interval: 60  # Publish every 60 seconds
    include_roi_details: true
    include_frame_stats: false
  
  alerts:
    publish_immediately: true
    alert_levels: ["warning", "critical", "emergency"]
  
  thermal_images:
    upload_to_s3: true
    upload_on_alert: true
    alert_levels: ["critical", "emergency"]
```

**Save:** `Ctrl+X`, `Y`, `Enter`

---


---

## 8. FTP Data Transfer (Recommended)

Infrastructure is managed via FTP to your cPanel server. This is the primary method for long-term data storage.

### 8.1 Create FTP Account
1. Log in to **cPanel** → **Files** → **FTP Accounts**
2. **Username**: `transformer-monitor` (example)
3. **Directory**: `transformer-data` (Remove `public_html/` prefix for privacy)
4. **Quota**: Unlimited or 10GB+

### 8.2 Directory Structure
The system automatically creates:
```
/transformer-data/
├── telemetry/YYYY/MM/DD/  # JSON metrics
├── thermal/YYYY/MM/DD/    # Raw thermal images
├── visual/YYYY/MM/DD/     # Visual snapshots
└── videos/YYYY/MM/DD/     # Motion event recordings
```

### 8.3 Configuration
Update `/data/config/site_config.yaml`:
```yaml
ftp:
  enabled: true
  host: "ftp.yourdomain.com"
  port: 21
  username: "transformer-monitor@yourdomain.com"
  password: "YOUR_STRONG_PASSWORD"  # OR use env var FTP_PASSWORD
  remote_dir: "/transformer-data"
  passive_mode: true
  
  # Intervals
  thermal_image_interval: 600    # 10 mins
  telemetry_upload_interval: 300 # 5 mins
  batch_telemetry: true
  organize_by_date: true
```

### 8.4 Troubleshooting FTP
- **Connection Refused**: Whitelist Pi's IP in cPanel/Firewall.
- **Passive Mode**: Ensure `passive_mode: true` is set (critical for NAT).
- **Permissions**: Ensure FTP user has Write access.

---

## 9. ROI Configuration


### 🎯 **Region of Interest Setup**

ROIs define which parts of the thermal image to monitor for temperature.

#### **Step 1: Access Web Interface**

```bash
# From your laptop (on same network as Pi)
# Open browser and go to:
http://192.168.1.100:5000
```

#### **Step 2: Navigate to ROI Mapper**

1. Click **"ROI Mapper"** in the navigation menu
2. You'll see a live view from the Pi camera overlaid with thermal data

#### **Step 3: Define ROIs**

**Method 1: Visual Click-to-Define**

1. Click **"Add ROI"** button
2. Enter ROI name (e.g., "Top Winding", "Core", "Oil Tank")
3. Click on the image to define corners of the region
4. Minimum 2 clicks (creates rectangle)
5. Click **"Save ROI"**
6. Repeat for each region you want to monitor

**Method 2: Manual Configuration**

Edit `/data/config/site_config.yaml`:

```yaml
regions_of_interest:
  - name: "Top Winding"
    enabled: true
    coordinates: [[8, 4], [24, 12]]  # [[x_min, y_min], [x_max, y_max]]
    weight: 1.5  # Higher weight = more important in composite temp
    emissivity: 0.95
    thresholds:
      warning: 75.0    # °C
      critical: 85.0   # °C
      emergency: 95.0  # °C
  
  - name: "Bottom Winding"
    enabled: true
    coordinates: [[8, 12], [24, 20]]
    weight: 1.5
    emissivity: 0.95
    thresholds:
      warning: 75.0
      critical: 85.0
      emergency: 95.0
  
  - name: "Core"
    enabled: true
    coordinates: [[10, 8], [22, 16]]
    weight: 1.0
    emissivity: 0.92  # Steel has lower emissivity
    thresholds:
      warning: 80.0
      critical: 90.0
      emergency: 100.0

# Composite temperature calculation
composite_temperature:
  enabled: true
  method: "weighted_average"  # Options: weighted_average, max, average
```

#### **Step 4: Test ROI Configuration**

```bash
# On the Pi
cd ~/transformer-monitor
python3 src/main.py

# Watch for:
# - "Initializing data processor..."
# - "Initialized with X ROIs"
# - Temperature readings for each ROI

# Press Ctrl+C to stop after verification
```

---

## 9. Remote Access (RMS Connect)

### 🌐 **Teltonika RMS Setup**

#### **Step 1: Register Device on RMS**

1. Go to https://rms.teltonika-networks.com
2. Log in with your company account
3. Navigate to **Devices**
4. Your router should appear (if SIM is active and RMS is enabled)
5. Click on the router to view details

#### **Step 2: Enable Remote Access**

1. In router settings, go to **Services → Remote Access**
2. Enable **RMS Connect**
3. Configure:
   - **Protocol:** SSH
   - **Port:** 22
   - **Local IP:** 192.168.1.100 (your Pi's IP)
   - **Description:** Transformer Monitor Site A
4. Save configuration

#### **Step 3: Access Pi via RMS**

**From RMS Web Interface:**

1. Go to **Devices** → Select your router
2. Click **Remote Access**
3. Select the SSH connection you created
4. Click **Connect**
5. Browser-based terminal will open
6. Login with: `smartie` / [your password]

**Via RMS CLI (Advanced):**

```bash
# Install RMS CLI tool (one-time setup)
# Download from: https://wiki.teltonika-networks.com/view/RMS_CLI

# Connect to device
rms-cli connect --device [DEVICE_ID] --service ssh

# You'll be prompted for credentials
```

---

## 10. Testing & Validation

### ✅ **Pre-Production Tests**

#### **Test 1: Hardware Verification**

```bash
cd ~/transformer-monitor

# Run diagnostic script
python3 scripts/diagnose_thermal_pi5.py

# Expected output:
# ✓ I2C bus initialized
# ✓ MLX90640 detected
# ✓ SUCCESS with all strategies
# Temperature range: 25-35°C (room temperature)
```

#### **Test 2: Thermal Capture**

```bash
# Quick thermal test
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from thermal_capture import ThermalCapture

thermal = ThermalCapture(i2c_addr=0x33, refresh_rate=2)
frame = thermal.get_frame()
if frame is not None:
    print(f"✓ Thermal OK: {frame.min():.1f}°C to {frame.max():.1f}°C")
else:
    print("✗ Thermal FAILED")
thermal.close()
EOF
```

#### **Test 3: Camera Test**

```bash
# Capture test image
libcamera-still -o /tmp/test.jpg

# Check if file exists
ls -lh /tmp/test.jpg

# Expected: File size > 500KB
```

#### **Test 4: Network Connectivity**

```bash
# Test internet
ping -c 4 8.8.8.8

# Test AWS IoT endpoint (if configured)
ping -c 4 [your-iot-endpoint].iot.us-east-1.amazonaws.com

# Expected: 0% packet loss
```

#### **Test 5: Full System Test**

```bash
cd ~/transformer-monitor

# Set test environment
export SITE_ID="SITE_A"
export LOG_LEVEL="INFO"

# Run for 2 minutes
timeout 120 python3 src/main.py

# Watch for:
# ✓ "Thermal camera ready"
# ✓ "Smart camera initialized"
# ✓ "Web interface started on port 5000"
# ✓ "Synchronized! Starting captures at top of each minute"
# ✓ "Capture 0: Composite=XX.X°C"
# ✓ "Published thermal telemetry to AWS" (if AWS enabled)
```

#### **Test 6: Web Interface**

```bash
# From your laptop browser:
http://192.168.1.100:5000

# Verify:
# ✓ Dashboard loads
# ✓ Live thermal stream visible
# ✓ Temperature readings displayed
# ✓ ROI mapper accessible
# ✓ System status shows "Active"
```

#### **Test 7: AWS Data Flow** (if AWS enabled)

**In AWS Console:**

1. Go to **IoT Core → Test → MQTT test client**
2. Subscribe to topic: `transformer/site-a/#` (wildcard)
3. You should see messages every 60 seconds:
   - `transformer/site-a/telemetry` - Temperature data
   - `transformer/site-a/heartbeat` - System health

**Check S3:**

1. Go to **S3** → Your bucket
2. Navigate to folders (created automatically)
3. Verify images are being uploaded (if alerts triggered)

---

## 11. Production Deployment

### 🚀 **Auto-Start Configuration**

#### **Step 1: Create Systemd Service**

```bash
sudo nano /etc/systemd/system/transformer-monitor.service
```

Paste this configuration:

```ini
[Unit]
Description=Transformer Thermal Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=smartie
WorkingDirectory=/home/smartie/transformer-monitor
Environment="PYTHONUNBUFFERED=1"
Environment="SITE_ID=SITE_A"
ExecStart=/usr/bin/python3 /home/smartie/transformer-monitor/src/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryLimit=1G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
```

**Save:** `Ctrl+X`, `Y`, `Enter`

#### **Step 2: Enable and Start Service**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable transformer-monitor

# Start service now
sudo systemctl start transformer-monitor

# Check status
sudo systemctl status transformer-monitor

# Expected output:
# ● transformer-monitor.service - Transformer Thermal Monitor
#    Loaded: loaded (/etc/systemd/system/transformer-monitor.service; enabled)
#    Active: active (running) since ...
```

#### **Step 3: View Logs**

```bash
# Real-time logs
sudo journalctl -u transformer-monitor -f

# Last 100 lines
sudo journalctl -u transformer-monitor -n 100

# Logs since boot
sudo journalctl -u transformer-monitor -b
```

#### **Step 4: Reboot Test**

```bash
# Reboot Pi
sudo reboot

# Wait 2 minutes, then reconnect
ssh smartie@192.168.1.100

# Check if service auto-started
sudo systemctl status transformer-monitor

# Should show: Active: active (running)
```

### 📊 **Monitoring & Alerts**

#### **Set Up Log Rotation**

```bash
sudo nano /etc/logrotate.d/transformer-monitor
```

```
/data/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 smartie smartie
}
```

#### **Set Up Disk Space Monitoring**

```bash
# Add to crontab
crontab -e

# Add this line (checks disk space daily at 2 AM)
0 2 * * * df -h /data | tail -1 | awk '{if($5+0 > 80) print "WARNING: Disk usage at "$5}' | logger -t disk-monitor
```

---

## 12. Troubleshooting

### 🔧 **Common Issues**

#### **Issue: Thermal camera not detected**

**Symptoms:**
```
Failed to initialize MLX90640: No Hardware I2C
```

**Solutions:**

1. **Check wiring:**
   ```bash
   # Power off Pi first!
   sudo shutdown -h now
   
   # Verify connections match pinout in Section 2
   # Power on and test
   i2cdetect -y 1
   ```

2. **Enable I2C:**
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Enable
   sudo reboot
   ```

3. **Check for conflicts:**
   ```bash
   # List I2C devices
   ls /dev/i2c*
   
   # Should show: /dev/i2c-1
   ```

#### **Issue: "Too many retries" error**

**Symptoms:**
```
Frame capture error: Too many retries
```

**Solutions:**

1. **Lower refresh rate** (already done in stable-deployment branch)
2. **Check power supply** - Weak power causes I2C errors
3. **Shorten I2C wires** - Long wires cause signal degradation

#### **Issue: Pi camera not working**

**Symptoms:**
```
Failed to initialize camera
```

**Solutions:**

1. **Enable camera:**
   ```bash
   sudo raspi-config
   # Interface Options → Camera → Enable
   sudo reboot
   ```

2. **Check ribbon cable:**
   ```bash
   # Test camera
   libcamera-hello --list-cameras
   
   # Should show: imx708 [4608x2592]
   ```

3. **Update firmware:**
   ```bash
   sudo apt-get update
   sudo apt-get full-upgrade
   sudo reboot
   ```

#### **Issue: No internet connection**

**Symptoms:**
```
Network monitor: No connectivity
AWS publisher: Connection failed
```

**Solutions:**

1. **Check Ethernet cable:**
   ```bash
   # Check link status
   ip link show eth0
   
   # Should show: state UP
   ```

2. **Check router:**
   ```bash
   # Ping router
   ping -c 4 192.168.1.1
   
   # Check DHCP
   ip addr show eth0
   ```

3. **Check DNS:**
   ```bash
   # Test DNS resolution
   nslookup google.com
   
   # If fails, set DNS manually
   sudo nano /etc/resolv.conf
   # Add: nameserver 8.8.8.8
   ```

#### **Issue: AWS IoT connection failed**

**Symptoms:**
```
AWS IoT initialization failed
Failed to connect to IoT endpoint
```

**Solutions:**

1. **Verify certificates:**
   ```bash
   ls -lh /data/certs/
   
   # Should show:
   # -rw-r--r-- device.crt
   # -rw------- private.key
   # -rw-r--r-- root-ca.pem
   
   # Check permissions
   chmod 600 /data/certs/private.key
   chmod 644 /data/certs/device.crt /data/certs/root-ca.pem
   ```

2. **Test endpoint connectivity:**
   ```bash
   # Ping IoT endpoint
   ping -c 4 [your-endpoint].iot.us-east-1.amazonaws.com
   
   # Test MQTT port
   telnet [your-endpoint].iot.us-east-1.amazonaws.com 8883
   ```

3. **Verify policy attachment:**
   - Go to AWS Console → IoT Core → Secure → Certificates
   - Check that policy is attached to your certificate

#### **Issue: High CPU usage**

**Symptoms:**
```
System slow, thermal throttling
```

**Solutions:**

1. **Check CPU temperature:**
   ```bash
   vcgencmd measure_temp
   
   # Should be < 70°C
   # If > 80°C, add heatsink or fan
   ```

2. **Reduce thermal refresh rate:**
   ```bash
   nano /data/config/site_config.yaml
   # Change: refresh_rate: 1  (from 2)
   ```

3. **Disable advanced processing:**
   ```bash
   # Edit thermal_capture.py initialization
   # Set: enable_advanced_processing=False
   ```

#### **Issue: SD card full**

**Symptoms:**
```
No space left on device
Storage manager: Disk usage critical
```

**Solutions:**

1. **Check disk usage:**
   ```bash
   df -h /data
   du -sh /data/*
   ```

2. **Clean old files:**
   ```bash
   # Delete old images (older than 7 days)
   find /data/images -type f -mtime +7 -delete
   
   # Clean logs
   sudo journalctl --vacuum-time=7d
   ```

3. **Enable FTP cold storage** (moves old files to FTP server):
   ```bash
   nano /data/config/site_config.yaml
   # Add FTP configuration (see Section 13)
   ```

---

## 13. Maintenance

### 🔄 **Regular Maintenance Tasks**

#### **Weekly:**

```bash
# Check system status
ssh smartie@192.168.1.100
sudo systemctl status transformer-monitor

# Check disk space
df -h /data

# Check logs for errors
sudo journalctl -u transformer-monitor --since "1 week ago" | grep -i error

# Verify AWS data flow (if enabled)
# Check AWS Console → IoT Core → Test → MQTT test client
```

#### **Monthly:**

```bash
# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Check for code updates
cd ~/transformer-monitor
git fetch origin
git log HEAD..origin/stable-deployment --oneline

# If updates available:
git pull origin stable-deployment
sudo systemctl restart transformer-monitor

# Clean old data
find /data/images -type f -mtime +30 -delete
```

#### **Quarterly:**

```bash
# Full system backup
# Backup configuration
tar -czf ~/backup-$(date +%Y%m%d).tar.gz /data/config /data/certs

# Download backup to laptop
# From laptop:
scp smartie@192.168.1.100:~/backup-*.tar.gz ~/backups/

# Test disaster recovery
# Create fresh SD card and restore from backup
```

### 📈 **Performance Monitoring**

```bash
# Create monitoring script
nano ~/monitor.sh
```

```bash
#!/bin/bash
echo "=== System Status ==="
echo "CPU Temp: $(vcgencmd measure_temp)"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h /data | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo ""
echo "=== Service Status ==="
systemctl is-active transformer-monitor
echo ""
echo "=== Recent Captures ==="
journalctl -u transformer-monitor --since "1 hour ago" | grep "Capture" | tail -5
```

```bash
chmod +x ~/monitor.sh

# Run anytime
~/monitor.sh
```

---

## 14. Site-Specific Deployment Checklist

### 📋 **Before Leaving Site**

- [ ] Hardware securely mounted
- [ ] All cables connected and secured
- [ ] Thermal camera positioned correctly
- [ ] Pi camera has clear view of transformer
- [ ] Ethernet cable connected to router
- [ ] Power supply connected
- [ ] System boots automatically
- [ ] Service running: `sudo systemctl status transformer-monitor`
- [ ] Web interface accessible: `http://192.168.1.100:5000`
- [ ] ROIs configured and tested
- [ ] AWS IoT connection verified (if enabled)
- [ ] RMS Connect access tested
- [ ] Temperature readings look reasonable (20-40°C ambient)
- [ ] Motion detection working (wave hand in front of camera)
- [ ] Logs show no errors: `sudo journalctl -u transformer-monitor -n 50`
- [ ] Documentation updated with site-specific details
- [ ] Contact information for site access recorded
- [ ] Backup configuration saved

---

## 15. Quick Reference

### 🔑 **Essential Commands**

```bash
# SSH to Pi
ssh smartie@192.168.1.100

# Check service status
sudo systemctl status transformer-monitor

# View live logs
sudo journalctl -u transformer-monitor -f

# Restart service
sudo systemctl restart transformer-monitor

# Stop service
sudo systemctl stop transformer-monitor

# Start service
sudo systemctl start transformer-monitor

# Check disk space
df -h /data

# Check temperature
vcgencmd measure_temp

# Test thermal camera
i2cdetect -y 1

# Test Pi camera
libcamera-hello --list-cameras

# Update code
cd ~/transformer-monitor
git pull origin stable-deployment
sudo systemctl restart transformer-monitor

# Reboot Pi
sudo reboot
```

### 📞 **Support Contacts**

**Technical Issues:**
- Email: support@smarterise.com
- Phone: +234-XXX-XXX-XXXX

**AWS Support:**
- AWS Console: https://console.aws.amazon.com
- Documentation: https://docs.aws.amazon.com/iot/

**Teltonika RMS:**
- RMS Portal: https://rms.teltonika-networks.com
- Support: https://teltonika-networks.com/support

---

## 16. Appendix

### 📚 **Additional Resources**

**Hardware Documentation:**
- MLX90640 Datasheet: https://www.melexis.com/en/product/MLX90640/
- Raspberry Pi Documentation: https://www.raspberrypi.com/documentation/
- Pi Camera 3 Guide: https://www.raspberrypi.com/documentation/accessories/camera.html

**Software Documentation:**
- Project Repository: https://github.com/t-ayedun/transformer-monitor
- Python Documentation: https://docs.python.org/3/
- Flask Documentation: https://flask.palletsprojects.com/

**Network Documentation:**
- Teltonika Router Manual: [Check your router model]
- RMS Connect Guide: https://wiki.teltonika-networks.com/view/RMS

---

## ✅ **Deployment Complete!**

Your transformer monitoring system is now fully operational. The system will:

- ✅ Capture thermal data every 60 seconds (synced to minute)
- ✅ Stream live thermal view at 2 Hz
- ✅ Detect motion and record events
- ✅ Send data to AWS IoT Core (if configured)
- ✅ Store data locally with automatic cleanup
- ✅ Auto-start on power-on
- ✅ Accessible remotely via RMS Connect

**Next Steps:**
1. Monitor system for 24-48 hours
2. Adjust ROI thresholds based on actual temperatures
3. Set up AWS CloudWatch alerts (optional)
4. Configure email/SMS notifications (optional)
5. Deploy to additional sites

**Questions?** Refer to the troubleshooting section or contact support.

---

**Document Version:** 1.0  
**Last Updated:** December 2024  
**Author:** Teniola Ayedun  
**License:** Proprietary - Smarterise Energy Solutions

---

## 15. Quick Command Reference

```bash
# Start monitoring (foreground)
./run.sh

# Start as service (background)
sudo systemctl start transformer-monitor

# Stop service
sudo systemctl stop transformer-monitor

# View logs
sudo journalctl -u transformer-monitor -f

# Check status
sudo systemctl status transformer-monitor

# Access dashboard
http://<pi-ip>:5000

# Update code
git pull origin stable-deployment

# Reinstall dependencies
venv/bin/pip install -r requirements.txt
```
