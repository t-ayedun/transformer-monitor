# Standalone Deployment Guide

Complete guide for deploying Transformer Monitor on a standalone Raspberry Pi without Balena.

## Prerequisites

### Hardware Requirements
- **Raspberry Pi 4** (2GB+ RAM recommended)
- **MLX90640 Thermal Camera** (connected via I2C)
- **Pi Camera Module V2 or V3** (connected via ribbon cable)
- **MicroSD Card** (32GB+ recommended)
- **Power Supply** (5V 3A USB-C)
- **Network Connection** (Ethernet or WiFi)

### Software Requirements
- **Raspberry Pi OS Lite** (64-bit, Bookworm or later)
- Fresh install recommended
- SSH enabled
- Internet connection for initial setup

---

## Quick Start Commands

```bash
# 1. SSH into your Raspberry Pi
ssh pi@<raspberry-pi-ip>

# 2. Clone the repository
git clone <your-repo-url> transformer-monitor
cd transformer-monitor

# 3. Switch to the correct branch
git checkout claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf

# 4. Run automated setup (one-time)
sudo ./setup_standalone.sh

# 5. Reboot if prompted
sudo reboot

# 6. After reboot, configure your settings
nano .env

# 7. Start the monitoring system
./run.sh
```

That's it! Your transformer monitor is now running.

---

## Detailed Step-by-Step Instructions

### Step 1: Prepare Raspberry Pi

#### 1.1 Flash Raspberry Pi OS
1. Download **Raspberry Pi OS Lite (64-bit)** from https://www.raspberrypi.com/software/
2. Use Raspberry Pi Imager to flash to SD card
3. **Enable SSH** during setup (recommended)
4. **Configure WiFi** if not using Ethernet

#### 1.2 Boot and Connect
```bash
# Find your Pi's IP address (check your router)
# Or use: sudo nmap -sn 192.168.1.0/24

# SSH into Pi (default password: raspberry)
ssh pi@<raspberry-pi-ip>

# Optional but recommended: Change default password
passwd
```

### Step 2: Clone Repository

```bash
# Install git if not already installed
sudo apt-get update
sudo apt-get install -y git

# Clone repository
git clone <your-repo-url> transformer-monitor
cd transformer-monitor

# Checkout the production branch
git checkout claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf
```

### Step 3: Run Automated Setup

```bash
# Make script executable
chmod +x setup_standalone.sh

# Run setup as root (installs system packages)
sudo ./setup_standalone.sh
```

**What this does:**
- ✅ Detects Raspberry Pi model
- ✅ Updates package lists
- ✅ Installs system dependencies (I2C, camera, OpenCV)
- ✅ Enables I2C interface
- ✅ Enables Pi Camera
- ✅ Creates data directories (`/data/*`)
- ✅ Creates Python virtual environment
- ✅ Installs Python packages (this takes 10-15 minutes)
- ✅ Generates default configuration
- ✅ Sets proper permissions

**Expected output:**
```
╔═══════════════════════════════════════════════════════════╗
║              Setup Complete!                              ║
╚═══════════════════════════════════════════════════════════╝

✓ System dependencies installed
✓ I2C and camera interfaces enabled
✓ Python virtual environment created
✓ Data directories created
✓ Configuration generated
```

### Step 4: Reboot (If Required)

If setup indicates "REBOOT REQUIRED":

```bash
sudo reboot
```

Wait 30 seconds, then SSH back in:

```bash
ssh pi@<raspberry-pi-ip>
cd transformer-monitor
```

### Step 5: Configure Your Site

```bash
# Copy environment template
cp config/default_env.template .env

# Edit configuration
nano .env
```

**Required Settings:**
```bash
SITE_ID=YOUR_SITE_ID              # e.g., TRANSFORMER_001
SITE_NAME=Your Transformer Name   # e.g., Main Substation
SITE_LOCATION=Physical Location   # e.g., North Yard
```

**Optional Settings:**
- Thermal camera settings (emissivity, refresh rate)
- Alert thresholds (warning/critical/emergency temperatures)
- Motion detection sensitivity
- AWS IoT settings (if using cloud)
- FTP settings (if using cold storage)

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 6: Add AWS Certificates (Optional)

If using AWS IoT Core:

```bash
# Copy certificates to Pi (from your local machine)
scp root-ca.pem pi@<pi-ip>:/data/certs/
scp device-cert.pem pi@<pi-ip>:/data/certs/
scp device-key.pem pi@<pi-ip>:/data/certs/

# Set permissions
sudo chmod 644 /data/certs/root-ca.pem
sudo chmod 644 /data/certs/device-cert.pem
sudo chmod 600 /data/certs/device-key.pem
```

Then enable AWS in `.env`:
```bash
AWS_IOT_ENABLED=true
IOT_ENDPOINT=your-endpoint.iot.us-east-1.amazonaws.com
IOT_THING_NAME=transformer-001
```

### Step 7: Start Monitoring

```bash
# Make run script executable
chmod +x run.sh

# Start the application
./run.sh
```

**Expected output:**
```
╔═══════════════════════════════════════════════════════════╗
║              Starting Transformer Monitor                ║
╚═══════════════════════════════════════════════════════════╝

Web Dashboard: http://192.168.1.100:5000
Press Ctrl+C to stop
```

### Step 8: Access Web Dashboard

Open your browser and navigate to:
```
http://<raspberry-pi-ip>:5000
```

**Dashboard Features:**
- Live thermal and visual camera feeds
- Real-time temperature monitoring
- Motion detection indicator
- Configured monitoring zones
- Recent recordings and snapshots
- Temperature history charts

---

## Optional: Install as System Service

To run automatically on boot:

```bash
# Make installer executable
chmod +x install_service.sh

# Install service
sudo ./install_service.sh

# Start service
sudo systemctl start transformer-monitor

# Check status
sudo systemctl status transformer-monitor

# View live logs
sudo journalctl -u transformer-monitor -f
```

**Service will now:**
- ✅ Start automatically on boot
- ✅ Restart on failure
- ✅ Run in background
- ✅ Log to systemd journal

**Service Commands:**
```bash
sudo systemctl start transformer-monitor    # Start
sudo systemctl stop transformer-monitor     # Stop
sudo systemctl restart transformer-monitor  # Restart
sudo systemctl status transformer-monitor   # Status
sudo systemctl disable transformer-monitor  # Disable auto-start
```

---

## Verification Checklist

After starting the system, verify everything works:

### ✓ Hardware Check
```bash
# Check I2C devices (should see 0x33 for MLX90640)
i2cdetect -y 1

# Check camera (should list cameras)
libcamera-hello --list-cameras
```

### ✓ Web Interface Check
- [ ] Dashboard loads at http://<pi-ip>:5000
- [ ] Live thermal feed shows temperature data
- [ ] Live visual feed shows camera view
- [ ] Temperature values update in real-time
- [ ] Motion detection indicator works

### ✓ ROI Mapper Check
- [ ] Navigate to Zone Mapper
- [ ] Thermal grid shows 32×24 full view
- [ ] Can select cells by clicking/dragging
- [ ] Can save monitoring zones
- [ ] Zones appear on dashboard

### ✓ Data Capture Check
```bash
# Wait 2-3 minutes, then check for files

# Check for event logs
sqlite3 /data/buffer/camera_events.db "SELECT COUNT(*) FROM camera_events;"

# Check for snapshots (if motion occurred)
ls -lh /data/images/

# Check for recordings (if motion occurred)
ls -lh /data/videos/

# Check logs
tail -f /data/logs/transformer_monitor.log
```

---

## Troubleshooting

### Issue: "I2C not enabled"
**Solution:**
```bash
sudo raspi-config
# Navigate to: Interface Options -> I2C -> Enable
sudo reboot
```

### Issue: "Camera not detected"
**Solution:**
```bash
sudo raspi-config
# Navigate to: Interface Options -> Legacy Camera -> Enable
sudo reboot
```

**Or check camera connection:**
```bash
libcamera-hello --list-cameras
vcgencmd get_camera
```

### Issue: "MLX90640 not found"
**Check I2C wiring:**
- VIN → 3.3V (Pin 1)
- GND → Ground (Pin 6)
- SDA → GPIO 2 (Pin 3)
- SCL → GPIO 3 (Pin 5)

**Test I2C:**
```bash
i2cdetect -y 1
# Should show "33" if MLX90640 is connected
```

### Issue: "Permission denied" errors
**Fix permissions:**
```bash
sudo chown -R $USER:$USER /data
sudo usermod -a -G i2c,video,gpio $USER
# Log out and back in for group changes
```

### Issue: Web interface not accessible
**Check if service is running:**
```bash
# If running manually
ps aux | grep python

# If running as service
sudo systemctl status transformer-monitor
```

**Check firewall:**
```bash
sudo ufw allow 5000/tcp
```

**Check from Pi itself:**
```bash
curl http://localhost:5000
```

### Issue: High CPU usage
**Solution:** Reduce camera resolution or refresh rate in `.env`:
```bash
THERMAL_REFRESH_RATE=4  # Instead of 8
CAMERA_WIDTH=1280       # Instead of 1920
CAMERA_HEIGHT=720       # Instead of 1080
```

### Issue: Running out of disk space
**Enable FTP cold storage** in `.env`:
```bash
FTP_ENABLED=true
FTP_HOST=your-ftp-server.com
FTP_USERNAME=username
FTP_PASSWORD=password
FTP_DISK_THRESHOLD=80
FTP_AGE_THRESHOLD_DAYS=7
```

**Or manually clean up:**
```bash
# Delete old recordings
find /data/videos -name "*.h264" -mtime +7 -delete

# Delete old snapshots
find /data/images -name "*.jpg" -mtime +7 -delete
```

---

## Updating the System

To update to the latest code:

```bash
cd transformer-monitor

# Stop service if running
sudo systemctl stop transformer-monitor

# Pull latest changes
git pull origin claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf

# Reinstall dependencies (if requirements.txt changed)
venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl start transformer-monitor
```

---

## Uninstalling

To completely remove the system:

```bash
# Stop and disable service
sudo systemctl stop transformer-monitor
sudo systemctl disable transformer-monitor
sudo rm /etc/systemd/system/transformer-monitor.service
sudo systemctl daemon-reload

# Remove application
cd ~
rm -rf transformer-monitor

# Remove data (CAUTION: Deletes all recordings and snapshots!)
sudo rm -rf /data

# Remove user from groups
sudo deluser $USER i2c
sudo deluser $USER video
```

---

## Performance Tuning

### For Raspberry Pi 3 or Lower Performance

Edit `.env`:
```bash
# Reduce thermal refresh rate
THERMAL_REFRESH_RATE=4

# Lower camera resolution
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720

# Reduce motion detection sensitivity (less CPU)
MOTION_SENSITIVITY=30

# Increase capture interval
CAPTURE_INTERVAL=120
```

### For Maximum Performance (Pi 4 with 4GB+)

Edit `.env`:
```bash
# Maximum thermal refresh
THERMAL_REFRESH_RATE=16

# Full resolution
CAMERA_WIDTH=1920
CAMERA_HEIGHT=1080

# Sensitive motion detection
MOTION_SENSITIVITY=80

# Frequent captures
CAPTURE_INTERVAL=30
```

---

## Security Best Practices

### 1. Change Default Credentials
```bash
# Change Pi password
passwd

# Disable password SSH, use keys only
ssh-keygen -t ed25519
# Add public key to ~/.ssh/authorized_keys
# Edit /etc/ssh/sshd_config: PasswordAuthentication no
sudo systemctl restart ssh
```

### 2. Firewall Configuration
```bash
sudo apt-get install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 5000/tcp  # Web dashboard
sudo ufw enable
```

### 3. Secure Web Dashboard
The dashboard is currently HTTP only. For production:
- Use VPN to access dashboard
- Or add nginx reverse proxy with SSL
- Or restrict to local network only

### 4. AWS Certificate Security
```bash
# Ensure private key is secure
sudo chmod 600 /data/certs/device-key.pem
sudo chown root:root /data/certs/device-key.pem
```

---

## Backup and Recovery

### Backup Configuration
```bash
# Backup all configuration
tar -czf transformer-backup-$(date +%Y%m%d).tar.gz \
  .env \
  /data/config/ \
  /data/certs/ \
  /data/buffer/*.db

# Download backup to local machine
scp pi@<pi-ip>:~/transformer-monitor/transformer-backup-*.tar.gz ./
```

### Restore Configuration
```bash
# Upload backup to new Pi
scp transformer-backup-*.tar.gz pi@<new-pi-ip>:~/

# Extract on Pi
cd transformer-monitor
tar -xzf ../transformer-backup-*.tar.gz
```

### SD Card Image Backup
```bash
# On your local machine (Linux/Mac)
sudo dd if=/dev/sdX of=transformer-monitor-backup.img bs=4M status=progress

# Compress
gzip transformer-monitor-backup.img
```

---

## Monitoring and Maintenance

### View System Status
```bash
# Service status
sudo systemctl status transformer-monitor

# Live logs
sudo journalctl -u transformer-monitor -f

# Application logs
tail -f /data/logs/transformer_monitor.log

# Check disk usage
df -h /data

# Check memory usage
free -h

# Check CPU temperature
vcgencmd measure_temp
```

### Check Data Capture
```bash
# Recent events
sqlite3 /data/buffer/camera_events.db "SELECT * FROM camera_events ORDER BY timestamp DESC LIMIT 10;"

# Count recordings
ls -1 /data/videos/*.h264 | wc -l

# Count snapshots
ls -1 /data/images/*.jpg | wc -l

# Total data usage
du -sh /data/videos /data/images
```

### Performance Monitoring
```bash
# CPU usage
top -bn1 | grep "transformer-monitor"

# Temperature (prevent thermal throttling)
watch -n 1 vcgencmd measure_temp

# I2C traffic
i2cdetect -y 1
```

---

## Network Configuration

### Static IP Address (Recommended)
```bash
# Edit DHCP config
sudo nano /etc/dhcpcd.conf

# Add at end:
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# Restart networking
sudo systemctl restart dhcpcd
```

### Remote Access via Tailscale (Easy VPN)
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect to your Tailscale network
sudo tailscale up

# Access dashboard from anywhere
# http://<tailscale-ip>:5000
```

---

## Advanced Configuration

### Custom ROI Configuration

Edit `/data/config/site_config.yaml` directly:

```yaml
regions_of_interest:
  - name: "HV Winding"
    enabled: true
    coordinates: [[10, 8], [22, 16]]
    weight: 2.0
    emissivity: 0.95
    thresholds:
      warning: 75
      critical: 85
      emergency: 95
```

Or use the web interface at: http://<pi-ip>:5000/smart-roi-mapper

### Database Access

```bash
# Event database
sqlite3 /data/buffer/camera_events.db

# Query events
SELECT datetime(timestamp, 'localtime'), event_type, confidence
FROM camera_events
ORDER BY timestamp DESC
LIMIT 20;

# Exit
.quit
```

### Logs Location

```bash
# Application logs
/data/logs/transformer_monitor.log

# Systemd logs
sudo journalctl -u transformer-monitor

# Last 100 lines
sudo journalctl -u transformer-monitor -n 100

# Follow live
sudo journalctl -u transformer-monitor -f
```

---

## Multiple Transformers

To monitor multiple transformers with separate Raspberry Pis:

1. **Clone to each Pi** with same branch
2. **Configure unique SITE_ID** in each `.env`
3. **Set up AWS IoT** with different thing names
4. **All data aggregates** to same AWS account

Example:
```bash
# Transformer 1
SITE_ID=TRANSFORMER_001
IOT_THING_NAME=transformer-001

# Transformer 2
SITE_ID=TRANSFORMER_002
IOT_THING_NAME=transformer-002
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Hardware tested (I2C camera detected, Pi Camera working)
- [ ] `.env` configured with correct site details
- [ ] Alert thresholds set appropriately for your transformer
- [ ] ROIs configured for key transformer components
- [ ] AWS certificates installed (if using AWS)
- [ ] Network connectivity verified
- [ ] Static IP configured
- [ ] Systemd service installed and tested
- [ ] Reboot tested (service auto-starts)
- [ ] Dashboard accessible from operator workstation
- [ ] Motion detection tested (wave hand in front of camera)
- [ ] Temperature readings validated with known reference
- [ ] Disk space monitored (25GB+ free recommended)
- [ ] Backup created

---

## Support and Documentation

- **Main README**: `README.md`
- **Calibration Guide**: `docs/CALIBRATION.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **AWS Setup**: `docs/AWS_SETUP.md`
- **Web UI Guide**: `WEB_UI_GUIDE.md`

---

## System Requirements Summary

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **CPU** | Raspberry Pi 4 | Pi 3 works but slower |
| **RAM** | 2GB minimum | 4GB recommended |
| **Storage** | 32GB SD card | 64GB+ for longer retention |
| **OS** | Raspberry Pi OS 64-bit | Bookworm or later |
| **Network** | Ethernet or WiFi | Static IP recommended |
| **Power** | 5V 3A | Official adapter recommended |
| **Thermal Camera** | MLX90640 | I2C connection |
| **Visual Camera** | Pi Camera V2/V3 | CSI ribbon cable |

---

## Quick Command Reference

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
git pull origin claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf

# Reinstall dependencies
venv/bin/pip install -r requirements.txt

# Reset configuration
rm /data/config/*.yaml
venv/bin/python scripts/generate_config.py
```
