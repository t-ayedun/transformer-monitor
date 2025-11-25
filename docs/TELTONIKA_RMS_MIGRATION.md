# Migrating from Balena to Standalone + Teltonika RMS Connect

Complete guide for moving from Balena Cloud deployment to standalone Python deployment with Teltonika RMS Connect for remote management.

---

## 🎯 Why This Migration?

### **Balena (Before)**
- ✅ Container orchestration
- ✅ Remote updates via dashboard
- ✅ Fleet management
- ✅ Built-in VPN
- ❌ Monthly cost per device (paid plans)
- ❌ Requires Docker/container knowledge
- ❌ Less control over system
- ❌ Dependent on Balena infrastructure

### **Standalone + Teltonika RMS (After)**
- ✅ Direct Python deployment (no containers)
- ✅ Full system control
- ✅ No per-device costs (Teltonika RMS free tier available)
- ✅ Simple pull and run deployment
- ✅ Hardware VPN through Teltonika router
- ✅ Works with cellular or ethernet
- ❌ Manual updates (via git pull)
- ❌ Requires Teltonika router hardware

---

## 📋 Prerequisites

### **Hardware You Need**
1. **Raspberry Pi 4** (already have)
2. **Teltonika Router** with SIM card:
   - RUT955 (4G router - recommended)
   - RUT956 (4G router with GPS)
   - RUTX11 (Dual SIM 4G router)
   - RUTX12 (5G router)
3. **Ethernet cable** to connect Pi to router

### **Accounts You Need**
1. **Teltonika RMS Account**: https://rms.teltonika-networks.com (free tier available)
2. **GitHub/Git access**: To pull repository updates
3. **AWS Account** (optional - for IoT Core)

---

## 🏗️ New Architecture

### **Before (Balena)**
```
Internet
    ↓
Balena Cloud
    ↓ (Container updates, VPN)
Raspberry Pi (Balena OS + Docker)
    └── Transformer Monitor Container
```

### **After (Standalone + RMS)**
```
Internet
    ↓
Teltonika RMS Cloud
    ↓ (Remote management, VPN)
Teltonika Router (OpenVPN Server)
    ↓ (Ethernet)
Raspberry Pi (Raspberry Pi OS + Python)
    └── Transformer Monitor (Native Python)
```

---

## 🔧 Step-by-Step Migration

### **Phase 1: Teltonika Router Setup**

#### 1.1 Physical Connection
```
Transformer Site:

[Internet] ─── SIM Card ──> [Teltonika Router]
                                   │
                                   │ Ethernet
                                   ↓
                             [Raspberry Pi]
```

**Wiring:**
1. Insert SIM card into Teltonika router
2. Power on router (wait 2-3 minutes for boot)
3. Connect Pi to router's LAN port via Ethernet
4. Power on Pi

#### 1.2 Initial Router Configuration

**Access Router WebUI:**
```bash
# From laptop connected to router's WiFi or LAN:
http://192.168.1.1

# Default credentials:
Username: admin
Password: admin01
```

**⚠️ IMMEDIATELY CHANGE DEFAULT PASSWORD!**

**Update Firmware:**
1. Router WebUI → **System → Firmware**
2. Check for updates → Download → Install
3. Wait 5-10 minutes for update and reboot

#### 1.3 Add Router to Teltonika RMS

**Method 1: Via Router WebUI (Easiest)**
1. Login to router → **Services → Cloud Solutions → RMS**
2. Enable RMS
3. Click **Add to RMS**
4. Enter your RMS credentials
5. Router appears in RMS dashboard within 2-3 minutes

**Method 2: Via RMS Dashboard**
1. Go to https://rms.teltonika-networks.com
2. **Devices → Add Device**
3. Enter router's MAC address (found on router label)
4. Router must have RMS enabled and internet connectivity

**Verify in RMS:**
- RMS Dashboard should show your router as "Online"
- Green indicator means connected

---

### **Phase 2: OpenVPN Configuration**

#### 2.1 Enable OpenVPN Server on Router

**Via Router WebUI:**
1. **Services → VPN → OpenVPN**
2. Click **+ Add**
3. Select **Role: Server**

**Configuration:**
```
Enabled: ✓ Yes
TUN/TAP: TUN
Protocol: UDP
Port: 1194
LZO Compression: Yes
Encryption: AES-256-GCM
Authentication: SHA256

Network Settings:
Virtual network IP: 10.8.0.0
Virtual network netmask: 255.255.255.0

Advanced:
Push route: 192.168.1.0 255.255.255.0
Keepalive: 10 60
```

4. Click **Save & Apply**

#### 2.2 Generate Certificates

**Certificate Authority (CA):**
1. OpenVPN config → **Certificate Authority**
2. Click **Generate**
3. Fill details:
   - Common Name: `transformer-monitor-ca`
   - Organization: Your Company
4. Click **Generate**

**Server Certificate:**
1. Click **Generate Server Certificate**
2. Common Name: `transformer-server`
3. Click **Generate**

**Client Certificates** (one per engineer/laptop):
1. Click **Generate Client Certificate**
2. Common Name: `engineer-laptop-1`
3. Click **Generate**
4. Repeat for each person needing access

#### 2.3 Download Client Configuration

1. **OpenVPN → Configuration Files**
2. Select client certificate → **Download**
3. Save `.ovpn` file (e.g., `engineer-laptop-1.ovpn`)
4. Securely share with authorized personnel only

---

### **Phase 3: Raspberry Pi Migration**

#### 3.1 Backup Existing Data (If Migrating Existing Pi)

**If currently running Balena:**
```bash
# SSH into Balena device
balena ssh <device-uuid>

# Backup important data
tar -czf /tmp/backup-$(date +%Y%m%d).tar.gz \
  /data/config \
  /data/certs \
  /data/buffer/*.db

# Download backup to local machine (from your computer)
balena scp <device-uuid>:/tmp/backup-*.tar.gz ./
```

**Important files to backup:**
- `/data/config/*.yaml` - Configuration
- `/data/certs/*.pem` - AWS certificates
- `/data/buffer/*.db` - Event database
- `/data/images/*.jpg` - Recent snapshots (optional)
- `/data/videos/*.h264` - Recent recordings (optional)

#### 3.2 Flash Fresh Raspberry Pi OS

**Option A: Fresh Pi (Recommended)**
1. Download **Raspberry Pi OS Lite (64-bit)** from https://www.raspberrypi.com/software/
2. Flash to SD card using Raspberry Pi Imager
3. **Enable SSH**: Create empty file named `ssh` on boot partition
4. **Configure WiFi** (optional): Create `wpa_supplicant.conf` on boot partition

**Option B: Convert Existing Balena Pi (Advanced)**
```bash
# This will WIPE the device - backup first!
# Re-flash SD card with Raspberry Pi OS
```

#### 3.3 Connect Pi to Router

**Network Connection:**
1. Connect Pi to Teltonika router via Ethernet
2. Boot Pi
3. Find Pi's IP address:
   - Check router's WebUI → **Status → Network → LAN**
   - Or use: `nmap -sn 192.168.1.0/24`

**Set Static IP (Recommended):**

**Via Router DHCP Reservation:**
1. Router WebUI → **Network → DHCP → Static Leases**
2. Find Pi's MAC address
3. Assign static IP: `192.168.1.100`
4. Save and reboot Pi

#### 3.4 Deploy Standalone Application

**SSH into Pi:**
```bash
# Default credentials for new Raspberry Pi OS
ssh pi@192.168.1.100
# Password: raspberry (change immediately!)

# Change password
passwd
```

**Clone Repository:**
```bash
cd ~
git clone <your-repo-url> transformer-monitor
cd transformer-monitor

# Checkout production branch
git checkout claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf
```

**Run Setup:**
```bash
# One-time setup (installs everything)
sudo ./setup_standalone.sh

# This takes 15-20 minutes
# Installs: I2C, camera, Python, dependencies, etc.
```

**Reboot if prompted:**
```bash
sudo reboot
```

#### 3.5 Configure Application

**SSH back in after reboot:**
```bash
ssh pi@192.168.1.100
cd transformer-monitor
```

**Edit configuration:**
```bash
nano .env
```

**Required settings:**
```bash
# Site identification
SITE_ID=TRANSFORMER_001
SITE_NAME=Main Substation Transformer
SITE_LOCATION=North Yard

# Thermal camera
THERMAL_EMISSIVITY=0.95

# Alert thresholds
TEMP_WARNING=75
TEMP_CRITICAL=85
TEMP_EMERGENCY=95

# AWS IoT (if using)
AWS_IOT_ENABLED=true
IOT_ENDPOINT=your-endpoint.iot.us-east-1.amazonaws.com
IOT_THING_NAME=transformer-001

# FTP cold storage (optional)
FTP_ENABLED=false
```

**Restore AWS certificates** (if migrating):
```bash
# Copy certificates from backup
scp backup-certificates.tar.gz pi@192.168.1.100:~/
ssh pi@192.168.1.100
tar -xzf backup-certificates.tar.gz -C /data/certs/

# Set permissions
sudo chmod 644 /data/certs/root-ca.pem
sudo chmod 644 /data/certs/device-cert.pem
sudo chmod 600 /data/certs/device-key.pem
```

#### 3.6 Start Application

**Run in foreground** (for testing):
```bash
./run.sh
```

**Expected output:**
```
╔═══════════════════════════════════════════════════════════╗
║              Starting Transformer Monitor                ║
╚═══════════════════════════════════════════════════════════╝

✓ Loading environment variables from .env
✓ I2C enabled
✓ Camera interface available
✓ MLX90640 thermal camera detected at 0x33
✓ Site configuration exists
✓ Directories ready

Web Dashboard: http://192.168.1.100:5000
Press Ctrl+C to stop
```

**Test locally** (from Pi):
```bash
curl http://localhost:5000
# Should return HTML
```

#### 3.7 Install as System Service (Auto-Start on Boot)

```bash
# Install service
sudo ./install_service.sh

# Start service
sudo systemctl start transformer-monitor

# Enable auto-start on boot
sudo systemctl enable transformer-monitor

# Check status
sudo systemctl status transformer-monitor

# View logs
sudo journalctl -u transformer-monitor -f
```

---

### **Phase 4: Remote Access Setup**

#### 4.1 Configure Firewall on Router

**Allow VPN → LAN traffic:**
1. Router WebUI → **Network → Firewall**
2. **Add new rule:**
   ```
   Name: VPN to LAN
   Source zone: vpn_server
   Destination zone: lan
   Action: ACCEPT
   ```
3. Save

#### 4.2 Install OpenVPN Client on Your Laptop

**Windows:**
1. Download from https://openvpn.net/community-downloads/
2. Install OpenVPN GUI

**macOS:**
1. Install Tunnelblick from https://tunnelblick.net/

**Linux:**
```bash
sudo apt install openvpn
```

**Mobile:**
- Android: OpenVPN Connect (Play Store)
- iOS: OpenVPN Connect (App Store)

#### 4.3 Connect via VPN

**Windows:**
1. Copy `.ovpn` file to `C:\Program Files\OpenVPN\config\`
2. Right-click OpenVPN GUI in system tray
3. Select config → **Connect**

**macOS:**
1. Double-click `.ovpn` file
2. Tunnelblick imports it
3. Click **Connect**

**Linux:**
```bash
sudo openvpn --config engineer-laptop-1.ovpn
```

**Verify connection:**
```bash
# You should get VPN IP like 10.8.0.6
ifconfig tun0  # Linux/Mac
ipconfig       # Windows

# Test connectivity to Pi
ping 192.168.1.100
```

#### 4.4 Access Web Dashboard Remotely

**Once connected to VPN:**
1. Open browser
2. Navigate to: `http://192.168.1.100:5000`
3. Dashboard loads just like local access!

**Access via SSH:**
```bash
ssh pi@192.168.1.100
```

---

### **Phase 5: Teltonika RMS Connect Features**

#### 5.1 RMS Connect (Quick Remote Access)

**No VPN needed for quick access:**

**Access Router WebUI via RMS:**
1. RMS Dashboard → Select device
2. Click **WebUI** button
3. Opens router interface through RMS proxy

**Access Pi Terminal via RMS:**
1. RMS Dashboard → Select device
2. Click **Terminal** or **SSH**
3. Opens SSH session through RMS cloud

**Note:** RMS Connect requires RMS subscription (check pricing)

#### 5.2 RMS Monitoring Features

**Device Monitoring:**
- Real-time online/offline status
- Signal strength (cellular)
- Data usage tracking
- Connection history

**Alerts:**
- Configure alerts for offline devices
- Email notifications
- SMS alerts (paid feature)

**Remote Management:**
- Reboot router remotely
- Update firmware
- View/download logs
- Configuration backup/restore

#### 5.3 Multiple Sites Management

**Organize in RMS:**
1. Create groups: **Devices → Groups**
   - Example: "Lagos Transformers", "Abuja Sites"
2. Assign devices to groups
3. Apply bulk configurations
4. Monitor all sites from one dashboard

---

## 🔄 New Deployment Workflow

### **Balena Workflow (Old)**
```bash
# Update code
git commit -am "Add feature"
git push

# Balena builds and deploys to all devices automatically
# Wait 10-30 minutes for container updates
```

### **Standalone + RMS Workflow (New)**
```bash
# Update code
git commit -am "Add feature"
git push

# For each Pi (or create update script):
# 1. Via VPN:
ssh pi@192.168.1.100
cd transformer-monitor
git pull origin claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf
sudo systemctl restart transformer-monitor

# 2. Via RMS Terminal:
# Connect via RMS → Terminal
cd transformer-monitor && git pull && sudo systemctl restart transformer-monitor
```

**Create Update Script** (optional):
```bash
#!/bin/bash
# update_all_sites.sh

SITES=(
  "192.168.1.100"  # Site 1
  "192.168.2.100"  # Site 2
  "192.168.3.100"  # Site 3
)

for site in "${SITES[@]}"; do
  echo "Updating $site..."
  ssh pi@$site "cd transformer-monitor && git pull && sudo systemctl restart transformer-monitor"
done
```

---

## 📊 Feature Comparison

| Feature | Balena | Standalone + RMS |
|---------|--------|------------------|
| **Remote Access** | Balena VPN | Teltonika OpenVPN |
| **Remote Updates** | Automatic via push | Manual via SSH/git pull |
| **Fleet Management** | Balena Dashboard | Teltonika RMS |
| **Cost per Device** | $12-30/month/device | Free (RMS Connect: ~$2-5/month) |
| **Container Updates** | Automatic | Not needed (direct Python) |
| **System Control** | Limited | Full root access |
| **Monitoring** | Balena Dashboard | RMS Dashboard |
| **VPN Setup** | Automatic | Manual (one-time) |
| **Cellular Data** | Device-dependent | Via Teltonika router |
| **Offline Resilience** | Limited | Excellent (local buffer) |
| **Hardware Required** | None (uses device network) | Teltonika router |

---

## 💡 Best Practices

### **1. Network Design**

**Assign unique subnets per site:**
```
Site 1 (Lagos):      192.168.1.0/24 → Pi: 192.168.1.100
Site 2 (Abuja):      192.168.2.0/24 → Pi: 192.168.2.100
Site 3 (Port Harcourt): 192.168.3.0/24 → Pi: 192.168.3.100
```

**Benefits:**
- No IP conflicts when connecting to multiple sites
- Easy identification by IP
- Simplified firewall rules

### **2. VPN Certificate Management**

**Generate certificates per user:**
```
engineer-john.ovpn    → John's laptop
engineer-sarah.ovpn   → Sarah's laptop
mobile-ops.ovpn       → Operations mobile device
```

**Revoke when users leave:**
1. Router → OpenVPN → Certificate Management
2. Select certificate → **Revoke**
3. User can no longer connect

### **3. Security Hardening**

**Pi Security:**
```bash
# Change default password
passwd

# Disable password SSH (use keys only)
ssh-keygen -t ed25519
# Add key to ~/.ssh/authorized_keys
# Edit /etc/ssh/sshd_config: PasswordAuthentication no
sudo systemctl restart ssh

# Enable firewall
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow 5000/tcp
sudo ufw enable
```

**Router Security:**
```
✓ Change default admin password
✓ Enable HTTPS for WebUI
✓ Disable unused services (Telnet, HTTP)
✓ Use WPA3 for WiFi
✓ Enable firewall logging
✓ Regularly update firmware
```

### **4. Monitoring & Alerts**

**RMS Alerts:**
1. RMS → **Monitoring → Alerts**
2. Create alert: "Device Offline"
3. Set notification: Email/SMS
4. Action: Notify when router offline > 5 minutes

**Pi Health Monitoring:**
```bash
# Add to cron for daily health check
# /etc/cron.daily/health-check.sh

#!/bin/bash
DISK_USAGE=$(df -h /data | tail -1 | awk '{print $5}' | sed 's/%//')
CPU_TEMP=$(vcgencmd measure_temp | sed 's/temp=//')

if [ $DISK_USAGE -gt 80 ]; then
  echo "High disk usage: ${DISK_USAGE}%" | mail -s "Pi Alert" ops@example.com
fi
```

### **5. Backup Strategy**

**Automated Backups:**
```bash
# Create backup script: /home/pi/backup.sh

#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/data/backups"
mkdir -p $BACKUP_DIR

# Backup configuration and databases
tar -czf $BACKUP_DIR/backup-$DATE.tar.gz \
  /home/pi/transformer-monitor/.env \
  /data/config/ \
  /data/certs/ \
  /data/buffer/*.db

# Keep only last 7 days
find $BACKUP_DIR -name "backup-*.tar.gz" -mtime +7 -delete

# Optional: Upload to FTP/S3
# ...
```

**Add to crontab:**
```bash
crontab -e
# Add: 0 2 * * * /home/pi/backup.sh
```

---

## 🚨 Troubleshooting

### **Issue: Can't connect to VPN**

**Check:**
```bash
# 1. Router has internet
# RMS dashboard shows router "Online"

# 2. OpenVPN service running
# Router → Status → Services → OpenVPN should show "Running"

# 3. Firewall allows UDP 1194
# Router → Network → Firewall → Port Forwarding
# External port 1194 should be open

# 4. Router's public IP hasn't changed
# If using dynamic IP, update .ovpn file with current IP
```

**Solution:**
```bash
# Restart OpenVPN service
# Router → Services → OpenVPN → Restart

# Check logs
# Router → System → Troubleshoot → System Log
# Filter: "openvpn"
```

### **Issue: Connected to VPN but can't access Pi**

**Check:**
```bash
# 1. Pi is online
ping 192.168.1.100

# 2. Web server is running
ssh pi@192.168.1.100
sudo systemctl status transformer-monitor

# 3. Firewall rule exists
# Router → Network → Firewall
# VPN → LAN traffic should be allowed

# 4. Pi has correct IP
ip addr show eth0
```

**Solution:**
```bash
# Restart monitoring service
sudo systemctl restart transformer-monitor

# Check if port 5000 is listening
netstat -tlnp | grep 5000
```

### **Issue: Application won't start**

**Check logs:**
```bash
# System logs
sudo journalctl -u transformer-monitor -n 50

# Application logs
tail -f /data/logs/transformer_monitor.log

# Check Python environment
cd ~/transformer-monitor
venv/bin/python --version
venv/bin/pip list
```

**Common issues:**
```bash
# I2C not enabled
sudo raspi-config
# Interface Options → I2C → Enable

# Camera not detected
vcgencmd get_camera
libcamera-hello --list-cameras

# Dependencies missing
cd ~/transformer-monitor
venv/bin/pip install -r requirements.txt
```

---

## 📱 Mobile Access

### **Via OpenVPN Connect App**

**Setup:**
1. Install OpenVPN Connect from app store
2. Email `.ovpn` file to yourself
3. Open on phone → Import to OpenVPN Connect
4. Tap to connect

**Access Dashboard:**
1. Connect VPN
2. Open browser
3. Go to: `http://192.168.1.100:5000`
4. Mobile-optimized dashboard loads

---

## 💰 Cost Comparison

### **Monthly Costs Per Site**

| Item | Balena | Standalone + RMS |
|------|--------|------------------|
| Platform subscription | $12-30 | $0 (free tier) |
| RMS Connect | N/A | $2-5 (optional) |
| Cellular data (4GB) | $10-20 | $10-20 |
| Hardware (one-time) | $0 | $80-150 (router) |
| **Monthly total** | **$22-50** | **$10-25** |
| **Annual savings** | - | **$144-300/site** |

**For 10 sites:**
- Balena: $220-500/month = $2,640-6,000/year
- RMS: $100-250/month = $1,200-3,000/year
- **Savings: $1,440-3,000/year**

**Router investment pays for itself in 2-4 months per site!**

---

## 📚 Additional Resources

- **Teltonika RMS:** https://rms.teltonika-networks.com
- **RMS Wiki:** https://wiki.teltonika-networks.com/view/RMS
- **Router Manuals:** https://wiki.teltonika-networks.com/view/Category:Routers
- **OpenVPN Docs:** https://openvpn.net/community-resources/
- **Existing docs:** `docs/REMOTE_ACCESS.md`

---

## ✅ Migration Checklist

### **Pre-Migration**
- [ ] Purchase Teltonika router(s)
- [ ] Get SIM card(s) with data plan
- [ ] Create Teltonika RMS account
- [ ] Backup existing Balena device data
- [ ] Download AWS certificates (if using)
- [ ] Document current configurations

### **Router Setup**
- [ ] Insert SIM card and power on router
- [ ] Access router WebUI (192.168.1.1)
- [ ] Change default password
- [ ] Update firmware
- [ ] Add router to RMS
- [ ] Configure OpenVPN server
- [ ] Generate certificates
- [ ] Download client .ovpn files
- [ ] Configure firewall rules

### **Pi Migration**
- [ ] Flash Raspberry Pi OS to SD card
- [ ] Connect Pi to router via Ethernet
- [ ] Set static IP for Pi
- [ ] SSH into Pi
- [ ] Clone repository
- [ ] Run setup_standalone.sh
- [ ] Reboot Pi
- [ ] Configure .env file
- [ ] Copy AWS certificates
- [ ] Test application (./run.sh)
- [ ] Install systemd service
- [ ] Verify auto-start after reboot

### **Remote Access**
- [ ] Install OpenVPN client on laptop
- [ ] Import .ovpn configuration
- [ ] Connect to VPN
- [ ] Verify Pi accessibility
- [ ] Test web dashboard access
- [ ] Test SSH access
- [ ] Configure RMS alerts

### **Testing**
- [ ] Temperature readings accurate
- [ ] Motion detection working
- [ ] Video recording functional
- [ ] AWS IoT publishing (if enabled)
- [ ] Web dashboard accessible remotely
- [ ] ROI mapper functional
- [ ] Recent files display working
- [ ] System survives reboot

### **Decommissioning Balena**
- [ ] Verify new system fully operational
- [ ] Download final backups from Balena
- [ ] Document new access procedures
- [ ] Update team documentation
- [ ] Cancel Balena subscription (if paid)

---

## 🎉 Congratulations!

You've successfully migrated from Balena to standalone deployment with Teltonika RMS Connect!

**You now have:**
- ✅ Full system control
- ✅ Lower operational costs
- ✅ Secure remote access via VPN
- ✅ Professional remote management with RMS
- ✅ Simple deployment workflow
- ✅ Hardware-based VPN security

**Next Steps:**
1. Monitor system for 24-48 hours
2. Train team on new access procedures
3. Set up RMS alerts for critical events
4. Create update procedures
5. Replicate to additional sites

---

**Document Version:** 1.0
**Last Updated:** 2025-11-21
**Branch:** `claude/manage-project-branches-01GZMeBa8zXZeWey1Fok1bMf`
