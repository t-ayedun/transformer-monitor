# Phase 4: Pilot Deployment Guide

Complete guide for pilot deployment of transformer monitoring sites. This phase validates the complete provisioning and deployment workflow with 1-2 real sites before full rollout.

## Table of Contents

- [Pilot Objectives](#pilot-objectives)
- [Site Selection](#site-selection)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Hardware Installation](#hardware-installation)
- [Software Deployment](#software-deployment)
- [Validation and Testing](#validation-and-testing)
- [Monitoring Period](#monitoring-period)
- [Feedback Collection](#feedback-collection)
- [Go/No-Go Criteria](#gono-go-criteria)
- [Troubleshooting Log](#troubleshooting-log)

## Pilot Objectives

### Goals

1. **Validate Provisioning Workflow**
   - Test provision_site.py script with real site data
   - Verify AWS IoT Thing creation
   - Confirm certificate generation and deployment
   - Validate configuration file generation

2. **Test Deployment Process**
   - Validate hardware setup procedures
   - Test Balena deployment workflow
   - Verify manual deployment procedures (fallback)
   - Confirm certificate upload process

3. **Verify System Operation**
   - Confirm thermal camera captures data correctly
   - Verify visual camera captures snapshots/videos
   - Test AWS IoT telemetry upload
   - Validate S3 data storage
   - Confirm local buffering works
   - Test alert generation and publishing

4. **Assess Operational Readiness**
   - Monitor stability over 1 week minimum
   - Measure performance metrics
   - Identify any issues or edge cases
   - Document lessons learned

5. **Validate Documentation**
   - Test all setup instructions
   - Verify troubleshooting procedures
   - Confirm monitoring procedures work
   - Identify documentation gaps

### Success Criteria

- ✅ Provisioning completes without errors
- ✅ Device connects to AWS IoT successfully
- ✅ Thermal data uploads every 60 seconds
- ✅ S3 storage working (thermal frames, snapshots)
- ✅ Local buffering works during network outages
- ✅ System runs for 7 days without crashes
- ✅ Temperature alerts trigger correctly
- ✅ Web interface accessible and functional
- ✅ Documentation is complete and accurate

## Site Selection

### Criteria for Pilot Sites

**Ideal Pilot Site Characteristics:**

1. **Accessibility**
   - Easy physical access for troubleshooting
   - Within reasonable travel distance
   - Good cell/internet connectivity

2. **Technical Environment**
   - Stable power supply
   - Good network connectivity (Ethernet or 4G/LTE)
   - Indoor or protected location (easier initial deployment)
   - Typical transformer operation (not critical infrastructure)

3. **Support**
   - On-site technical contact available
   - Site operator willing to provide feedback
   - Flexible for adjustments/iterations

4. **Representative**
   - Similar to planned rollout sites
   - Typical environmental conditions
   - Representative transformer type

### Recommended Pilot Configuration

**Pilot Site 1:** Lab/Office Testing
- **Location:** Office or lab environment
- **Hardware:** Raspberry Pi 4B or 5
- **Network:** Ethernet connection
- **Purpose:** Validate software, provisioning, AWS integration
- **Duration:** 1 week

**Pilot Site 2:** Field Deployment
- **Location:** Actual substation or transformer site
- **Hardware:** Full production hardware (Pi 4B + Teltonika router)
- **Network:** 4G/LTE cellular
- **Purpose:** Validate real-world deployment, environmental factors
- **Duration:** 2-4 weeks

## Pre-Deployment Checklist

### Phase 4.1: Preparation (Week 5, Days 1-2)

#### Equipment Preparation

**For Each Pilot Site:**

- [ ] Raspberry Pi 4B or 5 (tested and working)
- [ ] Official power supply (15W for Pi 4, 27W for Pi 5)
- [ ] microSD card (32GB+, flashed with OS)
- [ ] MLX90640 thermal camera module
- [ ] Raspberry Pi Camera Module 3
- [ ] Camera cable (150mm, 15-pin)
- [ ] Jumper wires for thermal camera (female-to-female, 4 wires)
- [ ] Ethernet cable (5m minimum)
- [ ] Case with cooling (fan or active cooler)
- [ ] Mounting hardware (depends on site)

**Optional (for field site):**
- [ ] Teltonika RUT955/956 router
- [ ] 4G/LTE SIM card with data plan
- [ ] External LTE antenna
- [ ] IP65 enclosure
- [ ] Power strip with surge protection
- [ ] Cable glands and sealing

**Tools:**
- [ ] Laptop with SSH client
- [ ] USB keyboard and mouse
- [ ] Micro-HDMI to HDMI cable (for Pi 4B) or mini-HDMI (for Pi 5)
- [ ] HDMI monitor
- [ ] Screwdrivers (Phillips #1, #2)
- [ ] Multimeter
- [ ] Label maker or labels
- [ ] Cable ties
- [ ] Electrical tape

#### Software Preparation

- [ ] AWS account configured with IoT access
- [ ] AWS CLI installed and configured on laptop
- [ ] Balena account created (if using Balena)
- [ ] Balena CLI installed on laptop
- [ ] Repository cloned on laptop
- [ ] Provisioning scripts tested locally
- [ ] Python dependencies installed (`pip install -r scripts/provision/requirements.txt`)

#### Documentation Ready

- [ ] HARDWARE_SETUP.md printed or accessible
- [ ] PROVISIONING.md printed or accessible
- [ ] This PILOT_DEPLOYMENT.md printed or accessible
- [ ] Site information collected (see below)
- [ ] Deployment checklist printed
- [ ] Troubleshooting log template ready

#### Site Information Collection

For each pilot site, collect:

```yaml
Site Information:
  Site ID: PILOT_001
  Site Name: Main Substation - Pilot
  Physical Address: 123 Main St, City, State, ZIP
  GPS Coordinates:
    Latitude: 40.7128
    Longitude: -74.0060
  Timezone: America/New_York

Transformer Details:
  Serial Number: TX-PILOT-001
  Manufacturer: General Electric
  Model: TransFlex 100
  Type: Distribution
  Rating (kVA): 100
  Year Installed: 2015
  Last Maintenance: 2024-01-15

Network Configuration:
  Connection Type: Ethernet / 4G LTE
  Router Model: Teltonika RUT955 (if applicable)
  Static IP: 192.168.1.100 (if applicable)

Contacts:
  Site Operator:
    Name: John Doe
    Email: john.doe@utility.com
    Phone: +1-555-123-4567
  On-Call Technician:
    Name: Jane Smith
    Email: jane.smith@utility.com
    Phone: +1-555-987-6543
```

### Phase 4.2: Provisioning (Week 5, Day 3)

#### Step 1: Run Provisioning Script

```bash
# On your laptop

cd transformer-monitor

# Provision pilot site
python scripts/provision/provision_site.py \
  --site-id PILOT_001 \
  --site-name "Main Substation - Pilot" \
  --transformer-sn TX-PILOT-001 \
  --aws-region us-east-1 \
  --timezone America/New_York \
  --address "123 Main St, City, State" \
  --balena-app transformer-monitor-pilot

# Checklist:
# [ ] Script completes without errors
# [ ] AWS IoT Thing created (verify in AWS Console)
# [ ] Certificates generated in provisioned_sites/PILOT_001/certificates/
# [ ] Configuration files created in provisioned_sites/PILOT_001/config/
# [ ] Deployment package created
# [ ] ZIP archive created
```

#### Step 2: Verify Provisioning Output

```bash
# Check provisioning output
cd provisioned_sites/PILOT_001

# Verify certificates exist
ls -la certificates/
# [ ] AmazonRootCA1.pem exists
# [ ] device.pem.crt exists
# [ ] private.pem.key exists (with 600 permissions)
# [ ] public.pem.key exists
# [ ] iot_policy.json exists

# Verify configuration
ls -la config/
# [ ] site_config.yaml exists and looks correct
# [ ] aws_config.yaml exists and looks correct
# [ ] .env file exists with correct variables

# Verify Balena configuration
ls -la balena/
# [ ] device_env_vars.json exists
# [ ] register_device.sh exists and is executable

# Verify deployment package
ls -la deployment_package/
# [ ] deployment_package.zip exists
# [ ] README.md exists with instructions
```

#### Step 3: Backup Certificates

```bash
# CRITICAL: Backup certificates securely

# Option A: Encrypted USB drive
cp -r certificates/ /media/usb/PILOT_001_certificates/
# Encrypt USB drive

# Option B: Password manager
# Store private.pem.key in password manager (1Password, LastPass, etc.)

# Option C: Encrypted cloud storage
# Upload to encrypted cloud storage (not regular cloud!)

# [ ] Certificates backed up to encrypted location
# [ ] Backup location documented
# [ ] Test certificate restore from backup
```

#### Step 4: Verify AWS Resources

```bash
# Verify IoT Thing
aws iot describe-thing --thing-name PILOT_001-monitor --region us-east-1
# [ ] Thing exists with correct attributes

# Verify IoT Policy
aws iot get-policy --policy-name PILOT_001-monitor-policy --region us-east-1
# [ ] Policy exists with correct permissions

# Verify IoT Endpoint
aws iot describe-endpoint --endpoint-type iot:Data-ATS --region us-east-1
# [ ] Endpoint matches config/aws_config.yaml

# Verify S3 bucket
aws s3 ls s3://transformer-monitor-data-us-east-1/PILOT_001/
# [ ] Bucket structure created (may be empty initially)
```

## Hardware Installation

### Phase 4.3: Hardware Setup (Week 5, Day 4)

#### Step 1: Raspberry Pi Preparation

**Follow HARDWARE_SETUP.md for detailed instructions**

**Summary checklist:**

- [ ] SD card flashed with Raspberry Pi OS (64-bit Lite)
- [ ] SSH enabled
- [ ] WiFi configured (if not using Ethernet)
- [ ] Hostname set to: `transformer-monitor-PILOT_001`
- [ ] First boot completed
- [ ] System updated (`sudo apt-get update && sudo apt-get upgrade`)
- [ ] I2C enabled (`sudo raspi-config → Interface Options → I2C`)
- [ ] Camera enabled (built-in libcamera support)
- [ ] GPU memory set to 128MB
- [ ] Timezone configured
- [ ] Filesystem expanded
- [ ] Docker installed (if using Docker deployment)

#### Step 2: Hardware Assembly

**MLX90640 Thermal Camera:**

- [ ] Thermal camera wired to GPIO pins:
  - VIN → Pin 1 (3.3V)
  - GND → Pin 6 (GND)
  - SCL → Pin 5 (GPIO 3)
  - SDA → Pin 3 (GPIO 2)
- [ ] Connections verified with multimeter (continuity test)
- [ ] Thermal camera detected: `sudo i2cdetect -y 1` shows 0x33
- [ ] Wires secured with cable ties
- [ ] Strain relief applied

**Raspberry Pi Camera Module 3:**

- [ ] Camera cable connected to Pi
  - Blue tab facing away from PCB
  - Contacts facing toward PCB
  - Connector closed firmly
- [ ] Camera detected: `libcamera-hello --list-cameras`
- [ ] Cable routed to avoid interference
- [ ] Camera securely mounted

**Enclosure:**

- [ ] Pi mounted in case/enclosure
- [ ] Heat sinks installed (if not using fan)
- [ ] Fan installed and tested (if applicable)
- [ ] Ventilation adequate
- [ ] All cables routed properly
- [ ] Cable glands installed (for outdoor enclosure)

#### Step 3: Power and Network

- [ ] Power supply connected (15W for Pi 4, 27W for Pi 5)
- [ ] Power supply verified with multimeter (5V ±0.25V)
- [ ] Network cable connected (or WiFi configured)
- [ ] Network connectivity tested: `ping google.com`
- [ ] Static IP configured (if required)
- [ ] DNS working: `nslookup google.com`
- [ ] NTP synchronized: `timedatectl`

#### Step 4: Initial Hardware Testing

```bash
# SSH to Pi
ssh pi@192.168.1.100

# Test thermal camera
sudo i2cdetect -y 1
# [ ] Device shows at 0x33

# Test visual camera
libcamera-hello --list-cameras
# [ ] Camera Module 3 detected

# Test capture
libcamera-still -o test.jpg
# [ ] Image captured successfully

# Check system health
vcgencmd measure_temp
# [ ] Temperature reasonable (< 65°C for Pi 4, < 70°C for Pi 5)

vcgencmd get_throttled
# [ ] No throttling (0x0)

free -h
# [ ] Sufficient free memory

df -h
# [ ] Sufficient free disk space (> 5GB)
```

## Software Deployment

### Phase 4.4: Software Installation (Week 5, Day 4-5)

#### Option A: Balena Deployment (Recommended for Pilot)

**Step 1: Deploy to Balena Cloud**

```bash
# On your laptop
cd transformer-monitor

# Deploy to Balena
./scripts/deploy_balena.sh PILOT_001

# Checklist:
# [ ] Balena application exists or created
# [ ] Device registered as PILOT_001-monitor
# [ ] Environment variables configured
# [ ] Docker image built and pushed
# [ ] Balena OS image downloaded
# [ ] OS image configured with device credentials
```

**Step 2: Flash SD Card**

```bash
# Flash SD card with Balena OS
balena local flash provisioned_sites/PILOT_001/balena-PILOT_001.img

# Or use Etcher GUI

# Checklist:
# [ ] SD card flashed successfully
# [ ] SD card ejected safely
# [ ] SD card labeled: "PILOT_001 - Balena"
```

**Step 3: First Boot**

```bash
# Insert SD card into Pi
# Power on Pi
# Wait 2-5 minutes for first boot and Balena registration

# Check device status
balena devices | grep PILOT_001

# Checklist:
# [ ] Device appears in Balena dashboard
# [ ] Device status: Online
# [ ] Application downloading/running
```

**Step 4: Upload Certificates**

```bash
# Wait for device to be online
# Then upload certificates
./scripts/upload_certificates.sh PILOT_001

# Checklist:
# [ ] Certificates uploaded successfully
# [ ] Private key has 600 permissions
# [ ] Application restarted after certificate upload
```

**Step 5: Verify Application**

```bash
# View logs
balena logs PILOT_001-monitor --tail

# Check for:
# [ ] "Starting Transformer Monitor" message
# [ ] "Thermal camera initialized" message
# [ ] "Visual camera initialized" message
# [ ] "Connected to AWS IoT" message
# [ ] No error messages

# SSH to device
balena ssh PILOT_001-monitor

# Verify certificates
ls -la /data/certificates/
# [ ] All certificates present
# [ ] Private key is 600 permissions

# Check configuration
cat /app/config/site_config.yaml
# [ ] Site ID is PILOT_001
# [ ] Production mode is true
```

#### Option B: Manual Deployment (Alternative)

**If Balena is not available or for testing manual process:**

```bash
# SSH to Pi
ssh pi@192.168.1.100

# Clone repository
git clone https://github.com/yourusername/transformer-monitor.git
cd transformer-monitor

# Create directories
sudo mkdir -p /data/certificates
sudo mkdir -p /data/config
sudo mkdir -p /data/logs
sudo mkdir -p /data/buffer

# Set permissions
sudo chown -R pi:pi /data

# Copy certificates from laptop
# On laptop:
scp -r provisioned_sites/PILOT_001/certificates/* pi@192.168.1.100:/data/certificates/

# Copy configuration
scp -r provisioned_sites/PILOT_001/config/* pi@192.168.1.100:/data/config/

# On Pi: Install Docker and start
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker pi

# Exit and re-login
exit
ssh pi@192.168.1.100

# Start application
cd transformer-monitor
docker-compose up -d

# View logs
docker-compose logs -f

# Checklist:
# [ ] Application starts successfully
# [ ] Thermal camera initialized
# [ ] Visual camera initialized
# [ ] AWS IoT connected
# [ ] No error messages
```

## Validation and Testing

### Phase 4.5: System Validation (Week 5, Day 5)

#### Test 1: Thermal Camera Data Capture

```bash
# Access device (Balena SSH or manual SSH)

# Test thermal capture
# Check logs for thermal capture messages
balena logs PILOT_001-monitor | grep "thermal"

# Expected to see:
# "Thermal frame captured" every 60 seconds
# "Thermal data processed" with temperature readings

# Checklist:
# [ ] Thermal frames captured every 60 seconds
# [ ] Temperature readings reasonable (15-40°C ambient)
# [ ] No error messages
# [ ] Max temperature detected (should be > min)
```

**Validation Criteria:**
- Capture rate: 1 frame per minute (configurable)
- Temperature range: 10-50°C (ambient)
- No failed captures over 1 hour period

#### Test 2: Visual Camera Snapshot

```bash
# Access web interface
# Navigate to: http://<device-ip>:5000

# Or test via command line:
curl http://<device-ip>:5000/capture_snapshot

# Checklist:
# [ ] Web interface loads successfully
# [ ] Live view shows camera feed
# [ ] Thermal overlay visible
# [ ] Snapshot can be captured manually
# [ ] Snapshot saved locally
# [ ] Snapshot uploaded to S3 (if configured)
```

**Validation Criteria:**
- Web interface accessible within 2 seconds
- Live view updates at ~10 FPS
- Thermal overlay matches thermal camera data
- Snapshots captured successfully

#### Test 3: AWS IoT Telemetry

```bash
# On laptop, subscribe to MQTT topic
aws iot-data subscribe \
  --topic "transformers/PILOT_001/telemetry" \
  --region us-east-1

# OR use AWS IoT Console MQTT Test Client

# Checklist:
# [ ] MQTT messages received every 60 seconds
# [ ] Message contains:
#     - site_id: PILOT_001
#     - timestamp
#     - composite_temperature
#     - regions array with temperature data
# [ ] No message gaps (reliable delivery)
# [ ] QoS 1 confirmed (at-least-once delivery)
```

**Validation Criteria:**
- Message frequency: Every 60 seconds (±5 seconds)
- Message delivery: 100% over 1 hour
- Message format: Valid JSON
- Temperature data: Present and reasonable

#### Test 4: S3 Data Storage

```bash
# Check S3 bucket for uploaded data
aws s3 ls s3://transformer-monitor-data-us-east-1/PILOT_001/ --recursive

# Should see:
# PILOT_001/thermal_frames/PILOT_001_thermal_YYYYMMDD_HHMMSS.npy
# PILOT_001/snapshots/PILOT_001_snapshot_YYYYMMDD_HHMMSS.jpg

# Download and verify thermal frame
aws s3 cp s3://transformer-monitor-data-us-east-1/PILOT_001/thermal_frames/PILOT_001_thermal_20240101_120000.npy test.npy

# Verify file
python3 <<EOF
import numpy as np
frame = np.load('test.npy')
print(f"Shape: {frame.shape}")  # Should be (24, 32)
print(f"Min: {frame.min():.2f}°C")
print(f"Max: {frame.max():.2f}°C")
EOF

# Checklist:
# [ ] Thermal frames uploaded to S3
# [ ] Snapshots uploaded to S3 (if configured)
# [ ] Files downloadable and valid
# [ ] File naming convention correct
# [ ] S3 bucket structure correct (PILOT_001/thermal_frames/, etc.)
```

**Validation Criteria:**
- Thermal frame upload: Every 10 minutes
- Snapshot upload: Every 30 minutes (default)
- File integrity: 100% valid files
- Storage cost: Within expected range

#### Test 5: Local Buffering

```bash
# Test local buffer during network disruption

# SSH to device
balena ssh PILOT_001-monitor

# Check buffer database
ls -lh /data/buffer/readings.db

# Query recent readings
sqlite3 /data/buffer/readings.db "SELECT COUNT(*) FROM readings;"

# Temporarily disconnect network (simulate outage)
# For Ethernet: unplug cable
# For WiFi: disable WiFi on router

# Wait 5 minutes

# Verify local buffering
sqlite3 /data/buffer/readings.db "SELECT COUNT(*) FROM readings WHERE timestamp > datetime('now', '-5 minutes');"

# Should show readings captured during outage

# Reconnect network

# Verify buffered data uploads
# Check AWS IoT for backfilled data

# Checklist:
# [ ] Local buffer captures data during outage
# [ ] Data preserved in SQLite database
# [ ] Network reconnects automatically
# [ ] Buffered data uploaded after reconnection
# [ ] No data loss during outage
```

**Validation Criteria:**
- Buffer retention: All data during 30-minute outage
- Auto-recovery: Network reconnects within 60 seconds
- Backfill upload: All buffered data uploaded within 10 minutes
- Data integrity: 100% data preserved

#### Test 6: Alert Generation

```bash
# Trigger alert by creating hot spot
# (Use heat gun, hand, or warm object near thermal camera)

# Monitor for alert
aws iot-data subscribe \
  --topic "transformers/PILOT_001/alerts" \
  --region us-east-1

# Watch device logs
balena logs PILOT_001-monitor | grep "alert"

# Checklist:
# [ ] Alert detected when temperature exceeds warning threshold (75°C)
# [ ] Alert published to MQTT topic
# [ ] Alert contains:
#     - level (warning/critical/emergency)
#     - temperature
#     - roi_name
#     - timestamp
# [ ] Alert logged locally
```

**Validation Criteria:**
- Alert latency: < 5 seconds from detection to publish
- Alert accuracy: Correct temperature and severity
- Alert delivery: 100% published to MQTT

#### Test 7: ROI Configuration

```bash
# Access ROI mapper web interface
http://<device-ip>:5000/roi_mapper

# Configure ROI:
# 1. Click "Freeze Image"
# 2. Click and drag to select region
# 3. Enter ROI name: "Test ROI"
# 4. Set thresholds:
#    - Warning: 75°C
#    - Critical: 85°C
#    - Emergency: 95°C
# 5. Click "Save ROI"

# Verify ROI saved
# Check logs for "ROI saved" message

# Test ROI temperature monitoring
# Observe telemetry includes ROI data

# Checklist:
# [ ] ROI mapper loads and displays thermal image
# [ ] Image can be frozen
# [ ] ROI can be drawn by drag
# [ ] ROI details can be edited
# [ ] ROI saved successfully
# [ ] ROI appears in telemetry data
# [ ] ROI temperature calculated correctly
```

#### Test 8: Performance Monitoring

```bash
# Monitor system performance over 1 hour

# CPU usage
balena ssh PILOT_001-monitor
htop

# Expected: 15-25% CPU usage average

# Memory usage
free -h

# Expected: 200-400 MB used

# Temperature
vcgencmd measure_temp

# Expected: Pi 4B: 50-65°C, Pi 5: 55-70°C

# Network usage
vnstat -l

# Expected: ~50 KB/minute (telemetry) + uploads

# Disk usage
df -h

# Expected: < 30% used

# Checklist:
# [ ] CPU usage < 40% average
# [ ] Memory usage < 50%
# [ ] Temperature < 70°C (Pi 4) or < 75°C (Pi 5)
# [ ] No thermal throttling
# [ ] Network usage reasonable
# [ ] Disk space sufficient (> 5GB free)
# [ ] No memory leaks over 1 hour
```

**Performance Baselines:**
- CPU: 15-25% average during operation
- Memory: 200-400 MB
- Temperature: 50-70°C (with cooling)
- Thermal capture: 3-4 FPS
- Processing latency: 30-50ms per frame
- Network: ~3-5 KB/s average

### Phase 4.6: Deployment Validation Checklist

**Complete this checklist for each pilot site:**

```
Pilot Site: PILOT_001
Date: _____________
Technician: _____________

Hardware Installation:
[ ] Raspberry Pi powered and booting
[ ] Thermal camera connected and detected
[ ] Visual camera connected and detected
[ ] Network connection established
[ ] Web interface accessible
[ ] All cables secured properly
[ ] Enclosure closed and sealed (if applicable)

Software Configuration:
[ ] Application running in Docker
[ ] AWS IoT connection established
[ ] Certificates loaded correctly
[ ] Site configuration correct (site_config.yaml)
[ ] Production mode enabled
[ ] Timezone configured correctly

Data Collection:
[ ] Thermal data captured every 60 seconds
[ ] Visual snapshots captured (interval: _____)
[ ] AWS IoT telemetry uploading
[ ] S3 storage working
[ ] Local buffer working
[ ] No error messages in logs

Functionality:
[ ] Web interface live view working
[ ] Thermal overlay displaying
[ ] ROI configured and monitoring
[ ] Alerts can be triggered
[ ] Motion detection working (if enabled)
[ ] Video recording working (if enabled)

Performance:
[ ] CPU usage reasonable (< 40%)
[ ] Memory usage acceptable (< 50%)
[ ] Temperature acceptable (< 70°C)
[ ] No thermal throttling
[ ] Network bandwidth sufficient
[ ] Response time acceptable (< 2s)

Documentation:
[ ] Site information documented
[ ] Configuration backed up
[ ] Certificates backed up securely
[ ] Contact information recorded
[ ] Deployment notes logged

Sign-off:
[ ] System operational and validated
[ ] Site operator notified
[ ] Monitoring schedule confirmed

Technician Signature: ___________________
Date/Time: ___________________
```

## Monitoring Period

### Phase 4.7: 1-Week Monitoring (Week 5-6)

#### Daily Monitoring Tasks

**Day 1-7: Daily Checks**

```bash
# Morning check (run daily)

# 1. Check device status
balena devices | grep PILOT_001
# [ ] Device online

# 2. Check application health
curl http://<device-ip>:5000/health/deep

# Expected status: "healthy"
# [ ] All components OK

# 3. Check MQTT telemetry
aws iot-data subscribe --topic "transformers/PILOT_001/telemetry" --region us-east-1
# Listen for 2 minutes
# [ ] Messages received consistently

# 4. Check S3 uploads
aws s3 ls s3://transformer-monitor-data-us-east-1/PILOT_001/thermal_frames/ --recursive | tail -20
# [ ] Recent thermal frames present

# 5. Review logs
balena logs PILOT_001-monitor --tail 100
# [ ] No error messages
# [ ] No warnings
# [ ] Regular operation confirmed

# 6. Check system metrics
balena ssh PILOT_001-monitor
vcgencmd measure_temp  # Temperature
free -h                 # Memory
df -h                   # Disk
# [ ] All metrics within acceptable ranges

# Log results in monitoring spreadsheet
```

#### Monitoring Metrics

Track these metrics daily:

| Metric | Target | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Day 6 | Day 7 |
|--------|--------|-------|-------|-------|-------|-------|-------|-------|
| Device Online | 100% | | | | | | | |
| MQTT Messages | 1440/day | | | | | | | |
| S3 Thermal Frames | 144/day | | | | | | | |
| S3 Snapshots | 48/day | | | | | | | |
| Errors in Logs | 0 | | | | | | | |
| CPU Avg % | < 30% | | | | | | | |
| Memory Used MB | < 400 | | | | | | | |
| Temp °C | < 70 | | | | | | | |
| Disk Free GB | > 5 | | | | | | | |
| Uptime hours | 24 | | | | | | | |

#### Weekly Summary

At end of week, compile:

1. **Uptime Report**
   - Total uptime percentage
   - Any downtime incidents
   - Cause of downtime (if any)

2. **Data Collection Report**
   - Total thermal frames captured
   - Total MQTT messages sent
   - Total S3 uploads
   - Any data gaps

3. **Performance Report**
   - Average CPU usage
   - Average memory usage
   - Average temperature
   - Peak usage times

4. **Incident Log**
   - All errors encountered
   - Warnings logged
   - Corrective actions taken

5. **Feedback Summary**
   - Site operator comments
   - Technician observations
   - User experience notes

## Feedback Collection

### Pilot Feedback Form

**Complete at end of 1-week monitoring period:**

```
Pilot Site Feedback: PILOT_001
Completed by: _____________
Date: _____________

Installation Experience:
1. How long did hardware installation take?
   [ ] < 1 hour  [ ] 1-2 hours  [ ] 2-4 hours  [ ] > 4 hours

2. Were the hardware setup instructions clear and complete?
   [ ] Yes, very clear  [ ] Mostly clear  [ ] Some confusion  [ ] Unclear

3. What installation challenges did you encounter?
   _____________________________________________________________

4. What tools or materials were missing/needed?
   _____________________________________________________________

Software Deployment:
5. Which deployment method was used?
   [ ] Balena  [ ] Manual Docker  [ ] Other: _____________

6. How long did software deployment take?
   [ ] < 30 min  [ ] 30-60 min  [ ] 1-2 hours  [ ] > 2 hours

7. Were the provisioning and deployment instructions clear?
   [ ] Yes, very clear  [ ] Mostly clear  [ ] Some confusion  [ ] Unclear

8. What deployment challenges did you encounter?
   _____________________________________________________________

System Operation:
9. Has the system been stable over the monitoring period?
   [ ] Very stable, no issues  [ ] Mostly stable, minor issues
   [ ] Some instability  [ ] Very unstable

10. Have you experienced any system crashes or restarts?
    [ ] None  [ ] 1-2  [ ] 3-5  [ ] > 5

11. Is the web interface responsive and usable?
    [ ] Excellent  [ ] Good  [ ] Acceptable  [ ] Poor

12. Are the temperature readings accurate?
    [ ] Yes, verified  [ ] Seem reasonable  [ ] Uncertain  [ ] Inaccurate

Data Quality:
13. Is thermal data being captured reliably?
    [ ] Yes, consistently  [ ] Mostly, some gaps  [ ] Intermittent  [ ] No

14. Are visual snapshots captured successfully?
    [ ] Yes, all successful  [ ] Mostly successful  [ ] Some failures  [ ] Frequent failures

15. Is data uploading to AWS/S3 working?
    [ ] Yes, verified  [ ] Believe so  [ ] Uncertain  [ ] No

Alerts and Notifications:
16. Have you tested the alert system?
    [ ] Yes, working well  [ ] Yes, some issues  [ ] No, not tested

17. Are alert thresholds appropriate?
    [ ] Yes  [ ] Need adjustment  [ ] Unsure  [ ] Not tested

Documentation:
18. Was the documentation helpful and complete?
    [ ] Excellent  [ ] Good  [ ] Adequate  [ ] Needs improvement

19. What documentation is missing or needs improvement?
    _____________________________________________________________

Overall Assessment:
20. Overall satisfaction with the system:
    [ ] Excellent  [ ] Good  [ ] Acceptable  [ ] Poor

21. Would you recommend this system for full deployment?
    [ ] Yes, strongly recommend  [ ] Yes, with some improvements
    [ ] Maybe, needs work  [ ] No, not ready

22. What improvements are most important?
    1. _____________________________________________________________
    2. _____________________________________________________________
    3. _____________________________________________________________

Additional Comments:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

Signature: ___________________  Date: ___________________
```

## Go/No-Go Criteria

### Phase 4.8: Go/No-Go Decision (End of Week 6)

**Criteria for proceeding to Phase 5 (Full Rollout):**

#### GO Criteria (All Must Be Met)

**System Reliability:**
- [ ] Uptime > 95% over 1-week period
- [ ] No critical failures
- [ ] Auto-recovery from network outages working
- [ ] System stable after 7 days continuous operation

**Data Collection:**
- [ ] Thermal data capture success rate > 95%
- [ ] MQTT telemetry delivery > 95%
- [ ] S3 upload success rate > 90%
- [ ] Local buffer working correctly
- [ ] No significant data gaps

**Performance:**
- [ ] CPU usage < 40% average
- [ ] Memory usage < 60%
- [ ] Temperature < 75°C (no throttling)
- [ ] Web interface responsive (< 3s load time)
- [ ] Processing latency < 100ms

**Functionality:**
- [ ] Thermal camera working correctly
- [ ] Visual camera working correctly
- [ ] AWS IoT connectivity stable
- [ ] Web interface fully functional
- [ ] ROI configuration working
- [ ] Alerts triggering correctly

**Documentation:**
- [ ] All procedures validated and working
- [ ] Troubleshooting guides adequate
- [ ] No major documentation gaps identified
- [ ] Deployment time within acceptable range (< 4 hours)

**Feedback:**
- [ ] Overall satisfaction rating: Good or Excellent
- [ ] No blockers identified
- [ ] Site operator comfortable with system
- [ ] Technician confident in deployment process

#### NO-GO Criteria (Any Triggers Re-evaluation)

**Critical Issues:**
- [ ] Uptime < 80%
- [ ] Frequent system crashes (> 3 per week)
- [ ] Data loss occurring
- [ ] AWS IoT connection unstable
- [ ] Hardware failures

**Significant Issues:**
- [ ] Data capture success < 80%
- [ ] Performance problems (high CPU, memory leaks)
- [ ] Thermal throttling occurring
- [ ] Web interface not working
- [ ] Major functionality broken

**Documentation/Process Issues:**
- [ ] Deployment time > 8 hours
- [ ] Critical documentation missing
- [ ] Provisioning script failures
- [ ] Unresolved troubleshooting issues

**Feedback:**
- [ ] Overall satisfaction: Poor
- [ ] Strong concerns from site operator
- [ ] Technician lacks confidence
- [ ] Major improvements required

### Decision Matrix

| Criteria | Weight | Score (1-5) | Weighted Score |
|----------|--------|-------------|----------------|
| System Reliability | 30% | | |
| Data Collection | 25% | | |
| Performance | 20% | | |
| Functionality | 15% | | |
| Documentation | 10% | | |
| **Total** | **100%** | | |

**Scoring:**
- 5 = Exceeds expectations
- 4 = Meets expectations
- 3 = Acceptable with minor issues
- 2 = Below expectations, needs work
- 1 = Unacceptable

**Decision:**
- Score > 4.0: **GO** - Proceed to Phase 5
- Score 3.5-4.0: **GO with caution** - Address identified issues first
- Score 3.0-3.5: **NO-GO** - Significant improvements needed
- Score < 3.0: **NO-GO** - Major redesign required

## Troubleshooting Log

### Incident Tracking Template

**Use this template to log all issues during pilot:**

```
Incident #: ___
Date/Time: _______________
Site: PILOT_001
Reported by: _______________

Issue Description:
_________________________________________________________________
_________________________________________________________________

Severity:
[ ] Critical (system down)
[ ] High (major functionality impaired)
[ ] Medium (minor functionality impaired)
[ ] Low (cosmetic or minor issue)

Symptoms:
_________________________________________________________________
_________________________________________________________________

Troubleshooting Steps Taken:
1. _________________________________________________________________
2. _________________________________________________________________
3. _________________________________________________________________

Root Cause:
_________________________________________________________________
_________________________________________________________________

Resolution:
_________________________________________________________________
_________________________________________________________________

Time to Resolve: _____ hours

Preventive Measures:
_________________________________________________________________
_________________________________________________________________

Documentation Updates Needed:
_________________________________________________________________

Status: [ ] Open  [ ] Resolved  [ ] Deferred

Resolved by: _______________
Resolution Date/Time: _______________
```

### Common Issues and Solutions

**Issue 1: Device not connecting to AWS IoT**

**Symptoms:** "Failed to connect to AWS IoT" in logs

**Troubleshooting:**
1. Verify certificates exist: `ls -la /data/certificates/`
2. Check certificate permissions: Private key should be 600
3. Verify IoT endpoint in config
4. Test network connectivity: `ping <iot-endpoint>`
5. Check IoT policy attached to certificate
6. Verify thing exists in AWS IoT Core
7. Check system time is synchronized: `timedatectl`

**Resolution:** Usually certificate or network issue

---

**Issue 2: Thermal camera not detected**

**Symptoms:** "Failed to initialize thermal camera" in logs

**Troubleshooting:**
1. Check I2C enabled: `ls /dev/i2c-1`
2. Scan I2C bus: `sudo i2cdetect -y 1`
3. Verify wiring connections
4. Check 3.3V power supply: `vcgencmd measure_volts`
5. Try different I2C speed in `/boot/config.txt`

**Resolution:** Usually wiring or I2C configuration

---

**Issue 3: High CPU temperature / Throttling**

**Symptoms:** Temperature > 80°C, `vcgencmd get_throttled` shows throttling

**Troubleshooting:**
1. Check fan is running
2. Verify heat sinks installed
3. Improve ventilation
4. Reduce processing load
5. Consider active cooler (for Pi 5)

**Resolution:** Improve cooling

---

## Next Steps After Pilot

### If GO Decision:

1. **Document Lessons Learned**
   - Update all documentation with pilot findings
   - Add troubleshooting entries
   - Refine deployment procedures
   - Update time estimates

2. **Prepare for Scale**
   - Order hardware for additional sites
   - Train additional technicians
   - Set up batch provisioning
   - Prepare deployment schedule

3. **Proceed to Phase 5**
   - See DEPLOYMENT_PLAN.md Phase 5
   - Begin rollout to additional sites
   - Implement monitoring dashboards
   - Establish support procedures

### If NO-GO Decision:

1. **Analyze Failures**
   - Review all incidents
   - Identify root causes
   - Prioritize improvements

2. **Make Improvements**
   - Fix identified issues
   - Update hardware/software
   - Enhance documentation
   - Improve procedures

3. **Repeat Pilot**
   - Test improvements
   - Re-validate system
   - Repeat go/no-go evaluation

## Appendix: Pilot Deployment Checklist

**Print this quick reference checklist:**

```
PILOT DEPLOYMENT - QUICK CHECKLIST

Pre-Deployment:
[ ] Equipment gathered
[ ] Software prepared
[ ] Site information collected
[ ] Provisioning completed
[ ] Certificates backed up

Hardware:
[ ] SD card flashed
[ ] Pi configured (I2C, camera, etc.)
[ ] Thermal camera connected (0x33)
[ ] Visual camera connected
[ ] Network connected
[ ] Power supply adequate

Software:
[ ] Application deployed (Balena or manual)
[ ] Certificates uploaded
[ ] Configuration verified
[ ] Application running
[ ] Logs clean (no errors)

Validation:
[ ] Thermal capture working
[ ] Visual capture working
[ ] AWS IoT connected
[ ] S3 uploads working
[ ] Local buffer working
[ ] Alerts working
[ ] ROI configured
[ ] Performance acceptable

Monitoring (7 days):
[ ] Daily health checks
[ ] Metrics tracked
[ ] Incidents logged
[ ] Feedback collected

Go/No-Go:
[ ] Criteria evaluated
[ ] Decision made
[ ] Next steps planned
```

---

**Pilot Deployment Guide Complete**

For questions or issues during pilot, refer to:
- [HARDWARE_SETUP.md](./HARDWARE_SETUP.md) - Hardware instructions
- [PROVISIONING.md](./PROVISIONING.md) - Provisioning and deployment
- [README.md](./README.md) - System overview
- [DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md) - Overall deployment strategy
