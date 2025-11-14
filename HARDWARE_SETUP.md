# Raspberry Pi Hardware Setup Guide

Complete guide for setting up Transformer Thermal Monitor on Raspberry Pi 4 Model B and Raspberry Pi 5.

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Raspberry Pi 4B Setup](#raspberry-pi-4b-setup)
- [Raspberry Pi 5 Setup](#raspberry-pi-5-setup)
- [Hardware Assembly](#hardware-assembly)
- [Initial Configuration](#initial-configuration)
- [Software Installation](#software-installation)
- [Hardware Testing](#hardware-testing)
- [Troubleshooting](#troubleshooting)

## Hardware Requirements

### Core Components

#### Option 1: Raspberry Pi 4 Model B

**Required:**
- Raspberry Pi 4 Model B (4GB or 8GB RAM recommended)
- Official Raspberry Pi Power Supply (USB-C, 5V 3A, 15W)
- microSD Card (32GB minimum, Class 10, A1 or A2 rated)
- MLX90640 Thermal Camera (32×24 resolution)
- Raspberry Pi Camera Module 3 (or compatible)
- Camera cable (15-pin to 15-pin, 150mm recommended)

**Recommended:**
- Raspberry Pi 4 Case with fan (for cooling)
- Heat sinks for CPU/RAM
- microSD card reader
- Ethernet cable (for initial setup)

#### Option 2: Raspberry Pi 5

**Required:**
- Raspberry Pi 5 (4GB or 8GB RAM)
- Official Raspberry Pi 27W USB-C Power Supply (5V 5A)
- microSD Card (32GB minimum, Class 10, A2 rated)
- MLX90640 Thermal Camera (32×24 resolution)
- Raspberry Pi Camera Module 3
- Camera cable (15-pin to 15-pin, 150mm)
- **Note:** Pi 5 requires PCIe compatibility for some accessories

**Recommended:**
- Raspberry Pi 5 Active Cooler (official)
- Raspberry Pi 5 Case (official or compatible)
- microSD card reader
- Ethernet cable

### Networking Components (Optional but Recommended)

**Option A: Local Network Connection**
- Ethernet cable (Cat5e or better)
- Network switch/router with available port

**Option B: Cellular Connection (for remote sites)**
- Teltonika RUT955 or RUT956 Router
- 4G/LTE SIM card with data plan
- External LTE antenna (for better reception)
- Ethernet cable (Pi to router)

### Enclosure and Mounting

**For Outdoor/Industrial Deployment:**
- IP65 rated enclosure (300mm × 200mm × 120mm minimum)
- DIN rail mounting bracket (if applicable)
- Cable glands for wire entry
- Desiccant pack (moisture control)
- Thermal padding/insulation

**For Indoor/Lab Testing:**
- Desktop stand or mounting plate
- Cable management clips
- Power strip with surge protection

### Tools Required

- Phillips screwdriver (#1 or #2)
- Tweezers (for ribbon cable installation)
- Multimeter (for voltage verification)
- USB keyboard and mouse (for initial setup)
- HDMI monitor or micro-HDMI adapter (for initial setup)
- Computer with SD card reader

## Raspberry Pi 4B Setup

### Step 1: Prepare the SD Card

#### 1.1: Download Raspberry Pi OS

```bash
# On your computer:

# Option A: Use Raspberry Pi Imager (Recommended)
# Download from: https://www.raspberrypi.com/software/

# Option B: Download image manually
wget https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2024-03-15/2024-03-15-raspios-bookworm-arm64-lite.img.xz
```

**Recommended OS:** Raspberry Pi OS Lite (64-bit) - Bookworm or later

#### 1.2: Flash SD Card

**Using Raspberry Pi Imager:**
1. Insert SD card into computer
2. Open Raspberry Pi Imager
3. Choose OS: "Raspberry Pi OS Lite (64-bit)"
4. Choose Storage: Your SD card
5. Click settings gear icon (⚙️):
   - Set hostname: `transformer-monitor-SITE_ID`
   - Enable SSH (use password authentication)
   - Set username: `pi`
   - Set password: (secure password)
   - Configure WiFi (optional)
   - Set locale settings (timezone, keyboard)
6. Click "Write"

**Using dd (Linux/Mac):**
```bash
# Extract image
unxz 2024-03-15-raspios-bookworm-arm64-lite.img.xz

# Find SD card device
lsblk

# Flash (replace /dev/sdX with your SD card)
sudo dd if=2024-03-15-raspios-bookworm-arm64-lite.img of=/dev/sdX bs=4M status=progress
sudo sync
```

#### 1.3: Enable SSH (if not using Imager)

```bash
# Mount boot partition
# On the boot partition, create empty ssh file:
touch /Volumes/boot/ssh  # Mac
touch /media/$USER/boot/ssh  # Linux
```

#### 1.4: Configure WiFi (optional)

Create `wpa_supplicant.conf` in boot partition:

```bash
cat > /Volumes/boot/wpa_supplicant.conf <<EOF
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="Your-WiFi-SSID"
    psk="Your-WiFi-Password"
    key_mgmt=WPA-PSK
}
EOF
```

### Step 2: First Boot and Initial Configuration

#### 2.1: Insert SD Card and Power On

1. Insert SD card into Pi 4B
2. Connect Ethernet cable (recommended for first boot)
3. Connect HDMI monitor (optional)
4. Connect USB keyboard (optional)
5. Connect power supply
6. Wait for boot (30-60 seconds)

#### 2.2: Find Pi IP Address

**Option A: Check router DHCP leases**
- Login to router admin panel
- Look for device named `transformer-monitor-SITE_ID` or `raspberrypi`

**Option B: Use network scanner**
```bash
# Install nmap
sudo apt-get install nmap  # Linux
brew install nmap          # Mac

# Scan network (replace with your network)
nmap -sn 192.168.1.0/24 | grep -B 2 "Raspberry Pi"
```

**Option C: Connect monitor and keyboard**
- Login locally
- Run: `hostname -I`

#### 2.3: SSH to Pi

```bash
# SSH to Pi (replace with actual IP)
ssh pi@192.168.1.100

# Accept fingerprint
# Enter password set during imaging
```

#### 2.4: Update System

```bash
# Update package lists
sudo apt-get update

# Upgrade all packages (this may take 10-20 minutes)
sudo apt-get upgrade -y

# Reboot
sudo reboot
```

### Step 3: Configure Raspberry Pi 4B

#### 3.1: Run raspi-config

```bash
sudo raspi-config
```

**Configure the following:**

1. **System Options → Hostname**
   - Set to: `transformer-monitor-SITE_ID`

2. **Interface Options → I2C**
   - Enable I2C (for thermal camera)

3. **Interface Options → Camera**
   - Enable legacy camera support (may not be needed for libcamera)

4. **Performance Options → GPU Memory**
   - Set to: 128 MB (for camera processing)

5. **Localisation Options → Timezone**
   - Set to your site timezone

6. **Advanced Options → Expand Filesystem**
   - Expand to use full SD card

7. **Finish and Reboot**

#### 3.2: Verify I2C Enabled

```bash
# Check I2C modules loaded
lsmod | grep i2c

# Should show i2c_bcm2835 and i2c_dev

# List I2C buses
ls -l /dev/i2c*

# Should show /dev/i2c-1
```

#### 3.3: Install I2C Tools

```bash
sudo apt-get install -y i2c-tools

# Test I2C bus (thermal camera should show at 0x33 when connected)
sudo i2cdetect -y 1
```

#### 3.4: Configure Camera

```bash
# Pi 4B uses libcamera
# Test camera (after connecting)
libcamera-hello --list-cameras

# Should detect Camera Module 3
```

### Step 4: Install Docker (for containerized deployment)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add pi user to docker group
sudo usermod -aG docker pi

# Install docker-compose
sudo apt-get install -y docker-compose

# Log out and back in for group changes
exit
ssh pi@<pi-ip>

# Verify Docker
docker --version
docker-compose --version
```

## Raspberry Pi 5 Setup

### Key Differences from Pi 4B

**Hardware Changes:**
- **Power Requirements:** Requires 5V 5A (27W) power supply (vs 3A for Pi 4)
- **PCIe Support:** Has PCIe 2.0 interface for future expansion
- **Camera Connectors:** Uses same 15-pin connector but verify compatibility
- **Improved Performance:** ~3x faster CPU, better GPU
- **Active Cooling Required:** Runs hotter, needs active cooler

**Software Changes:**
- **Kernel:** Requires Linux 6.1+ kernel
- **Bootloader:** Different firmware
- **I2C:** Same configuration
- **Camera:** Uses libcamera (same as Pi 4 with latest OS)

### Step 1: Prepare SD Card for Pi 5

**Important:** Pi 5 requires updated firmware. Use Raspberry Pi Imager or latest OS image.

```bash
# Download latest Raspberry Pi OS for Pi 5
# Use Raspberry Pi Imager (recommended)
# OR download from:
wget https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-2024-03-15/2024-03-15-raspios-bookworm-arm64-lite.img.xz

# This OS version supports both Pi 4 and Pi 5
```

Flash using same procedure as Pi 4B (see Step 1.2 above).

### Step 2: First Boot Configuration

Follow same procedure as Pi 4B (Steps 2.1-2.4).

**Pi 5 Specific Notes:**
- First boot may take longer (firmware initialization)
- May see multiple boot cycles (this is normal)
- Active cooler fan will start immediately

### Step 3: Configure Raspberry Pi 5

#### 3.1: Run raspi-config

Same as Pi 4B (see Step 3.1), with these additions:

```bash
sudo raspi-config
```

**Additional Pi 5 Specific Settings:**

1. **Performance Options → Fan**
   - Configure fan speed (if using official active cooler)
   - Temperature threshold: 60°C
   - Fan speed: High

2. **Advanced Options → PCIe Speed**
   - Set to Gen 2 (default) or Gen 3 (experimental, faster but may cause issues)

#### 3.2: Update Firmware and EEPROM

```bash
# Update firmware
sudo apt-get update
sudo apt-get upgrade -y

# Update EEPROM
sudo rpi-eeprom-update

# If update available:
sudo rpi-eeprom-update -a
sudo reboot
```

#### 3.3: Configure I2C (same as Pi 4)

```bash
# Install I2C tools
sudo apt-get install -y i2c-tools

# Verify I2C
lsmod | grep i2c
ls -l /dev/i2c*

# Test I2C bus
sudo i2cdetect -y 1
```

#### 3.4: Configure Camera

```bash
# Pi 5 uses libcamera exclusively
# Test camera
libcamera-hello --list-cameras

# List available cameras
libcamera-hello --list-cameras

# Expected output:
# 0 : imx708 [4608x2592] (/base/axi/pcie@120000/rp1/i2c@80000/imx708@1a)
```

### Step 4: Install Docker

Same as Pi 4B (see Pi 4B Step 4).

## Hardware Assembly

### MLX90640 Thermal Camera Connection

#### Wiring Diagram

```
MLX90640          Raspberry Pi (4B/5)
--------          -------------------
VIN      ------>  Pin 1  (3.3V)
GND      ------>  Pin 6  (GND)
SCL      ------>  Pin 5  (GPIO 3 / SCL)
SDA      ------>  Pin 3  (GPIO 2 / SDA)
```

#### Physical Connection Steps

1. **Power off Pi** (disconnect power)

2. **Locate GPIO pins** on Pi:
   ```
   3.3V  (Pin 1) [ ][ ] Pin 2  (5V)
   SDA   (Pin 3) [ ][ ] Pin 4  (5V)
   SCL   (Pin 5) [ ][ ] Pin 6  (GND)
   ```

3. **Connect MLX90640:**
   - Use female-to-female jumper wires
   - Connect VIN to 3.3V (Pin 1) - **NOT 5V!**
   - Connect GND to GND (Pin 6)
   - Connect SCL to Pin 5 (GPIO 3)
   - Connect SDA to Pin 3 (GPIO 2)

4. **Secure connections:**
   - Ensure tight connections
   - Use cable ties or tape to secure wires
   - Avoid stress on connections

5. **Test connection:**
   ```bash
   # Power on Pi
   # Run I2C scan
   sudo i2cdetect -y 1

   # Should show device at 0x33:
   #      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
   # 30: -- -- -- 33 -- -- -- -- -- -- -- -- -- -- -- --
   ```

#### I2C Address Configuration

The MLX90640 default I2C address is **0x33**.

If you need to use a different address (multiple sensors):
- Some MLX90640 boards have jumpers to change address to 0x32
- Check your board documentation

**Update configuration:**
```yaml
# In site_config.yaml:
thermal_camera:
  i2c_address: 0x33  # Or 0x32 if changed
```

### Raspberry Pi Camera Module 3 Connection

#### Camera Cable Installation

**For Pi 4B:**

1. **Locate camera connector:**
   - Between HDMI ports and audio jack
   - Black plastic connector with tab

2. **Open connector:**
   - Gently pull up on black plastic tab (pulls straight up)
   - Tab should be raised ~2mm

3. **Insert cable:**
   - Blue tab on cable faces away from HDMI ports
   - Contacts face toward HDMI ports
   - Insert fully into connector (should feel firm)

4. **Close connector:**
   - Push down on black plastic tab
   - Should click into place

**For Pi 5:**

1. **Locate camera connector:**
   - Between the two micro-HDMI ports
   - Similar black plastic connector

2. **Follow same procedure as Pi 4B:**
   - Open tab (pull up)
   - Insert cable (blue tab away from ports)
   - Close tab (push down)

**Important:** Be gentle! The connector can break if forced.

#### Cable Orientation Check

```
Looking at connector from above:
[Black Tab]
[==========]  ← Cable inserted here
[Connector]

Cable orientation:
[Blue Tab] facing away from PCB
[Contacts] facing toward PCB
```

#### Test Camera

```bash
# List cameras
libcamera-hello --list-cameras

# Expected output (Camera Module 3):
# 0 : imx708 [4608x2592] (/base/axi/...)

# Test capture
libcamera-still -o test.jpg

# View test image
# Copy to computer:
scp pi@<pi-ip>:~/test.jpg .
```

### Enclosure Assembly

#### Desktop/Lab Setup

1. **Mount Pi in case:**
   - Install standoffs
   - Secure Pi with screws
   - Attach heat sinks (if not using fan)
   - Install fan (if case includes one)

2. **Route cables:**
   - Camera cable through designated slot
   - I2C wires through cable management
   - Keep away from fan blades

3. **Ventilation:**
   - Ensure air flow for cooling
   - Don't block ventilation holes
   - Position fan to exhaust hot air

#### Outdoor/Industrial Enclosure

1. **Plan layout:**
   - Pi mounted on DIN rail or standoffs
   - Camera positioned for viewing transformer
   - Thermal camera with clear view

2. **Install components:**
   - Mount Pi in enclosure
   - Install power supply
   - Route cables through cable glands
   - Seal cable glands

3. **Environmental protection:**
   - Add desiccant pack for moisture
   - Ensure IP65 rating maintained
   - Verify cable gland seals

4. **Thermal management:**
   - Add ventilation or fan if needed
   - Monitor internal temperature
   - Consider heater for extreme cold

## Initial Configuration

### Network Configuration

#### Static IP (Recommended for Production)

```bash
# Edit dhcpcd.conf
sudo nano /etc/dhcpcd.conf

# Add at end of file:
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# Save and exit (Ctrl+X, Y, Enter)

# Restart networking
sudo systemctl restart dhcpcd
```

#### Configure with Teltonika Router

**Router Setup:**
1. Access router: `http://192.168.1.1`
2. Login with admin credentials
3. Navigate to Network → LAN
4. Configure DHCP reservation for Pi MAC address
5. Or configure static IP on Pi (as above)

**Verify connectivity:**
```bash
# Test internet
ping -c 3 google.com

# Test DNS
nslookup google.com

# Check routing
ip route
```

### Time Synchronization

```bash
# Enable NTP
sudo timedatectl set-ntp true

# Verify time is correct
timedatectl

# Set timezone (if not already set)
sudo timedatectl set-timezone America/New_York
```

### Security Hardening

#### Change Default Password

```bash
# Change pi user password
passwd

# Enter new secure password
```

#### SSH Key Authentication (Recommended)

```bash
# On your computer, generate SSH key
ssh-keygen -t ed25519 -C "transformer-monitor-SITE_ID"

# Copy public key to Pi
ssh-copy-id pi@<pi-ip>

# Test key-based login
ssh pi@<pi-ip>

# Disable password authentication
sudo nano /etc/ssh/sshd_config

# Change:
PasswordAuthentication no

# Restart SSH
sudo systemctl restart ssh
```

#### Configure Firewall

```bash
# Install UFW
sudo apt-get install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow web interface
sudo ufw allow 5000/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## Software Installation

### Clone Repository

```bash
# Install git
sudo apt-get install -y git

# Clone repository
cd ~
git clone https://github.com/yourusername/transformer-monitor.git
cd transformer-monitor
```

### Option 1: Docker Installation (Recommended)

```bash
cd ~/transformer-monitor

# Copy deployment package files (from provisioning)
# If deploying manually, copy certificates and config
mkdir -p /data/certificates
sudo cp /path/to/certificates/* /data/certificates/
sudo chmod 600 /data/certificates/private.pem.key

# Create .env file
cp .env.example .env
nano .env
# Set SITE_ID, AWS credentials, etc.

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Option 2: Python Virtual Environment

```bash
cd ~/transformer-monitor

# Install Python dependencies
sudo apt-get install -y python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Copy configuration
mkdir -p config
cp config/site_config.template.yaml config/site_config.yaml
nano config/site_config.yaml
# Edit configuration

# Run application
python src/main.py
```

### Install System Service (for auto-start)

```bash
# Create systemd service
sudo nano /etc/systemd/system/transformer-monitor.service

# Add content:
[Unit]
Description=Transformer Thermal Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/transformer-monitor
ExecStart=/home/pi/transformer-monitor/venv/bin/python /home/pi/transformer-monitor/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Save and exit

# Enable and start service
sudo systemctl enable transformer-monitor
sudo systemctl start transformer-monitor

# Check status
sudo systemctl status transformer-monitor

# View logs
sudo journalctl -u transformer-monitor -f
```

## Hardware Testing

### Test Thermal Camera

```bash
# Activate virtual environment
source ~/transformer-monitor/venv/bin/activate

# Run thermal camera test
python3 <<EOF
from thermal_capture import ThermalCapture
import numpy as np

print("Initializing thermal camera...")
thermal = ThermalCapture(i2c_addr=0x33)

print("Capturing frame...")
frame = thermal.get_frame()

if frame is not None:
    print(f"✓ Frame captured: {frame.shape}")
    print(f"  Min temp: {np.min(frame):.2f}°C")
    print(f"  Max temp: {np.max(frame):.2f}°C")
    print(f"  Avg temp: {np.mean(frame):.2f}°C")
    print("\nThermal camera: OK")
else:
    print("✗ Failed to capture frame")
EOF
```

### Test Visual Camera

```bash
# Test with libcamera
libcamera-still -o test_camera.jpg

# Verify image created
ls -lh test_camera.jpg

# Should show file ~1-3 MB

# Test with Python
python3 <<EOF
from picamera2 import Picamera2
import time

print("Initializing camera...")
picam2 = Picamera2()
config = picam2.create_still_configuration()
picam2.configure(config)

print("Starting camera...")
picam2.start()
time.sleep(2)

print("Capturing image...")
picam2.capture_file("test_picamera2.jpg")

print("✓ Camera capture: OK")
picam2.close()
EOF
```

### Test Complete System

```bash
# Access web interface
# From browser: http://<pi-ip>:5000

# Check health endpoint
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy"}

# Deep health check
curl http://localhost:5000/health/deep

# Should show all components OK
```

### Performance Benchmarks

#### Raspberry Pi 4B Expected Performance
- **Thermal capture rate:** 3-4 FPS
- **Processing latency:** 30-50ms per frame
- **CPU usage:** 15-25% during capture
- **Memory usage:** 200-300 MB
- **Temperature:** 50-65°C (with case fan)

#### Raspberry Pi 5 Expected Performance
- **Thermal capture rate:** 4-5 FPS (same sensor limitation)
- **Processing latency:** 10-20ms per frame
- **CPU usage:** 10-15% during capture
- **Memory usage:** 250-350 MB
- **Temperature:** 55-70°C (with active cooler)

**Monitor Performance:**
```bash
# Check CPU temperature
vcgencmd measure_temp

# Monitor CPU usage
htop

# Monitor process
top -p $(pgrep -f main.py)

# Check memory
free -h
```

## Troubleshooting

### Thermal Camera Issues

**Issue: "Failed to initialize thermal camera"**

**Solutions:**
1. Verify I2C enabled:
   ```bash
   ls /dev/i2c-1  # Should exist
   lsmod | grep i2c  # Should show i2c modules
   ```

2. Check wiring:
   ```bash
   sudo i2cdetect -y 1
   # Should show device at 0x33
   ```

3. Test different I2C speeds:
   ```bash
   sudo nano /boot/config.txt
   # Add or modify:
   dtparam=i2c_arm=on,i2c_arm_baudrate=100000
   # Save and reboot
   ```

4. Check power supply:
   ```bash
   vcgencmd get_throttled
   # 0x0 = OK, anything else = power issues
   ```

**Issue: "Thermal data all zeros or invalid"**

**Solutions:**
1. Wait for sensor warm-up (30 seconds after power on)
2. Check sensor temperature:
   ```python
   from thermal_capture import ThermalCapture
   thermal = ThermalCapture()
   print(thermal.get_sensor_temperature())
   # Should be ~25-35°C
   ```

### Camera Issues

**Issue: "Camera not detected"**

**Solutions:**
1. Check cable connection:
   - Reseat camera cable
   - Verify blue tab orientation
   - Check for damage on cable

2. Check camera enabled:
   ```bash
   libcamera-hello --list-cameras
   # Should show camera
   ```

3. Update firmware:
   ```bash
   sudo apt-get update
   sudo apt-get upgrade
   sudo rpi-update  # Use with caution
   sudo reboot
   ```

4. Check camera power:
   ```bash
   vcgencmd get_camera
   # Should show: supported=1 detected=1
   ```

### Network Issues

**Issue: "No network connection"**

**Solutions:**
1. Check cable connection (for Ethernet)
2. Verify network configuration:
   ```bash
   ip addr
   ping 192.168.1.1  # Gateway
   ping 8.8.8.8      # Internet
   ```

3. Reset network:
   ```bash
   sudo systemctl restart dhcpcd
   sudo systemctl restart networking
   ```

### Performance Issues

**Issue: "System slow or hanging"**

**Solutions:**
1. Check CPU temperature:
   ```bash
   vcgencmd measure_temp
   # Should be <80°C
   ```

2. Check for throttling:
   ```bash
   vcgencmd get_throttled
   # 0x0 = OK
   # 0x50000 = Previously throttled (historical)
   # 0x50005 = Currently throttled
   ```

3. Improve cooling:
   - Add/upgrade heat sinks
   - Add case fan
   - Improve airflow
   - For Pi 5: ensure active cooler working

4. Check memory:
   ```bash
   free -h
   # Ensure sufficient free memory
   ```

### Docker Issues

**Issue: "Docker container won't start"**

**Solutions:**
1. Check Docker status:
   ```bash
   sudo systemctl status docker
   ```

2. View container logs:
   ```bash
   docker-compose logs transformer-monitor
   ```

3. Check permissions:
   ```bash
   # Ensure user in docker group
   groups pi | grep docker

   # If not, add and re-login
   sudo usermod -aG docker pi
   exit
   ssh pi@<pi-ip>
   ```

## Hardware Comparison Summary

| Feature | Raspberry Pi 4B | Raspberry Pi 5 |
|---------|-----------------|----------------|
| **CPU** | Quad-core Cortex-A72 1.5GHz | Quad-core Cortex-A76 2.4GHz |
| **RAM** | 2/4/8 GB | 4/8 GB |
| **Power** | 5V 3A (15W) | 5V 5A (27W) |
| **I2C** | Supported (1 MHz max) | Supported (1 MHz max) |
| **Camera** | 15-pin connector, libcamera | 15-pin connector, libcamera |
| **Performance** | Good (baseline) | Excellent (~3x faster) |
| **Temperature** | 50-65°C (with fan) | 55-70°C (with active cooler) |
| **Cooling** | Passive/fan optional | Active cooling recommended |
| **Price** | $35-75 | $60-80 |
| **Best For** | Cost-effective, proven | Future-proof, high performance |

**Recommendation:**
- **Pi 4B:** Proven, cost-effective, well-supported. Great for current deployment.
- **Pi 5:** Future-proof, faster processing, better for scaling or advanced features.

Both work excellently for this application. Choose based on budget and performance needs.

## Next Steps

After hardware setup and testing:

1. **Proceed to provisioning** - See [PROVISIONING.md](./PROVISIONING.md)
2. **Configure ROIs** - Access web interface for ROI mapping
3. **Validate deployment** - Follow Phase 4 pilot checklist
4. **Monitor operation** - Use Balena dashboard or local monitoring

## Support Resources

- **Raspberry Pi Documentation:** https://www.raspberrypi.com/documentation/
- **MLX90640 Datasheet:** https://www.melexis.com/en/product/MLX90640/
- **Camera Module 3 Guide:** https://www.raspberrypi.com/documentation/accessories/camera.html
- **libcamera Documentation:** https://libcamera.org/
- **I2C Troubleshooting:** https://learn.adafruit.com/adafruit-mlx90640-ir-thermal-camera/python-circuitpython

## Appendix: Pin Reference

### Raspberry Pi GPIO Pinout (Pi 4B and Pi 5)

```
     3.3V  [ 1] [ 2]  5V
GPIO  2/SDA [ 3] [ 4]  5V
GPIO  3/SCL [ 5] [ 6]  GND
GPIO  4     [ 7] [ 8]  GPIO 14 (TXD)
      GND   [ 9] [10]  GPIO 15 (RXD)
GPIO 17     [11] [12]  GPIO 18
GPIO 27     [13] [14]  GND
GPIO 22     [15] [16]  GPIO 23
     3.3V   [17] [18]  GPIO 24
GPIO 10     [19] [20]  GND
GPIO  9     [21] [22]  GPIO 25
GPIO 11     [23] [24]  GPIO  8
      GND   [25] [26]  GPIO  7
GPIO  0/ID_SD [27] [28]  GPIO  1/ID_SC
GPIO  5     [29] [30]  GND
GPIO  6     [31] [32]  GPIO 12
GPIO 13     [33] [34]  GND
GPIO 19     [35] [36]  GPIO 16
GPIO 26     [37] [38]  GPIO 20
      GND   [39] [40]  GPIO 21
```

### I2C Connections

| Function | GPIO Pin | Physical Pin |
|----------|----------|--------------|
| SDA (Data) | GPIO 2 | Pin 3 |
| SCL (Clock) | GPIO 3 | Pin 5 |
| 3.3V Power | - | Pin 1 or 17 |
| Ground | - | Pin 6, 9, 14, 20, 25, 30, 34, 39 |

### Camera Connector

Both Pi 4B and Pi 5 use the same 15-pin camera connector (between HDMI ports).
