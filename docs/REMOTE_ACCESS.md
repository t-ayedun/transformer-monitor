# Remote Access Guide - OpenVPN & Teltonika RMS

## Overview

This guide covers setting up secure remote access to your transformer monitoring devices using:
- **Teltonika RMS** (Remote Management System) for router management
- **OpenVPN** for secure remote access to the Raspberry Pi and web interface
- **Port forwarding** for web UI access

## Architecture

```
Internet
    ↓
Teltonika RMS Cloud
    ↓ (Cellular/Ethernet)
Teltonika Router (with OpenVPN Server)
    ↓ (Ethernet)
Raspberry Pi 4 (Transformer Monitor)
    └── Web Interface: http://192.168.x.x:5000
    └── SSH: port 22
```

## Prerequisites

- Teltonika router (RUT955, RUT956, RUTX11, etc.) with active SIM card
- Router firmware updated to latest version
- Teltonika RMS account (free tier available)
- OpenVPN client software on your computer
- Static IP configured for Raspberry Pi (recommended)

---

## Part 1: Teltonika RMS Setup

### 1.1 Create RMS Account

1. Go to https://rms.teltonika-networks.com
2. Click **Sign Up** (or use existing account)
3. Complete registration and verify email
4. Login to RMS dashboard

### 1.2 Add Router to RMS

**Option A: During Router Setup**
1. Connect to router web UI (default: `192.168.1.1`)
2. Login (default: `admin` / `admin01` - **change this!**)
3. Navigate to **Services → Cloud Solutions → RMS**
4. Enable RMS and click **Add to RMS**
5. Enter your RMS credentials
6. Router will appear in your RMS dashboard within 2-3 minutes

**Option B: Manual Addition**
1. In RMS dashboard, go to **Devices → Add Device**
2. Enter router MAC address (found on router label or web UI)
3. Router must have internet connectivity and RMS enabled

### 1.3 Organize Devices

Create groups for better management:
1. In RMS: **Devices → Groups → Create Group**
2. Example groups: "Transformer Stations", "Lagos Sites", "Test Devices"
3. Assign routers to appropriate groups

---

## Part 2: OpenVPN Server Setup on Teltonika Router

### 2.1 Access Router Configuration

**Via RMS (Recommended for Remote):**
1. RMS Dashboard → Select router → **WebUI**
2. Click **Connect** (opens router's web interface)

**Via Direct Access (Local):**
1. Connect to router's WiFi or LAN
2. Browse to `http://192.168.1.1` (or router's IP)
3. Login with credentials

### 2.2 Configure OpenVPN Server

1. Navigate to **Services → VPN → OpenVPN**
2. Click **+ Add** to create new instance
3. Select **Role: Server**

**Server Configuration:**
```
Enabled: ✓
TUN/TAP: TUN
Protocol: UDP
Port: 1194
LZO: Yes (compression)
Encryption: AES-256-CBC (or AES-256-GCM for better performance)
Authentication: SHA256
Virtual network IP: 10.8.0.0
Virtual network netmask: 255.255.255.0
```

**Advanced Settings:**
```
Push option: route 192.168.1.0 255.255.255.0
  (This allows VPN clients to access local network where Pi is connected)

Keepalive: 10 60
Client to client: No (unless you need multiple clients to talk to each other)
```

4. Click **Save & Apply**

### 2.3 Generate Certificates

1. In OpenVPN config, go to **Certificate Authority** section
2. Click **Generate** for CA certificate
3. Fill in details:
   - Common Name: `transformer-monitor-ca`
   - Organization: Your company name
4. Click **Generate**

5. Generate **Server Certificate**:
   - Common Name: `transformer-monitor-server`
   - Click **Generate**

6. Generate **Client Certificates** (one per user/device):
   - Common Name: `client-admin` (or user name)
   - Click **Generate**
   - Repeat for each user who needs access

### 2.4 Download Client Configuration

1. Go to **OpenVPN → Configuration Files**
2. Click **Download** for the client you created
3. Save `.ovpn` file (e.g., `client-admin.ovpn`)
4. Securely share with authorized users only

---

## Part 3: Raspberry Pi Network Configuration

### 3.1 Assign Static IP to Raspberry Pi

**Option A: Via Router DHCP Reservation**
1. Router WebUI → **Network → DHCP → Static Leases**
2. Find Raspberry Pi MAC address in connected clients
3. Assign static IP (e.g., `192.168.1.100`)
4. Save and reboot Pi

**Option B: Via Balena Dashboard**
1. Balena Dashboard → Device → Device Configuration
2. Add custom network configuration (if supported)

**Recommended Static IP:** `192.168.1.100` (or within your router's subnet)

### 3.2 Configure Firewall (Router)

1. Router → **Network → Firewall**
2. Ensure traffic from VPN zone (10.8.0.0/24) to LAN is allowed

**Firewall Rule:**
```
Name: VPN to LAN
Source zone: vpn_server
Destination zone: lan
Action: ACCEPT
```

---

## Part 4: Connect via OpenVPN

### 4.1 Install OpenVPN Client

**Windows:**
- Download OpenVPN GUI from https://openvpn.net/community-downloads/
- Install with default settings

**macOS:**
- Install Tunnelblick: https://tunnelblick.net/

**Linux:**
```bash
sudo apt install openvpn
```

**Mobile:**
- Android: OpenVPN Connect (Play Store)
- iOS: OpenVPN Connect (App Store)

### 4.2 Import Configuration

**Windows (OpenVPN GUI):**
1. Copy `.ovpn` file to `C:\Program Files\OpenVPN\config\`
2. Right-click OpenVPN GUI icon in system tray
3. Select your config → **Connect**

**macOS (Tunnelblick):**
1. Double-click `.ovpn` file
2. Tunnelblick will import it
3. Click Connect

**Linux:**
```bash
sudo openvpn --config client-admin.ovpn
```

### 4.3 Verify Connection

Once connected, you should receive an IP like `10.8.0.6`

**Test connectivity:**
```bash
# Ping router
ping 192.168.1.1

# Ping Raspberry Pi
ping 192.168.1.100

# Check if ports are accessible
nc -zv 192.168.1.100 5000  # Web interface
nc -zv 192.168.1.100 22    # SSH
```

---

## Part 5: Access Web Interface Remotely

### 5.1 Via OpenVPN (Recommended - Secure)

1. Connect to OpenVPN
2. Open browser
3. Navigate to: `http://192.168.1.100:5000`
4. Dashboard and ROI Mapper accessible

**Advantages:**
- Encrypted traffic
- Full access to local network
- No port forwarding needed
- Access multiple devices

### 5.2 Via Port Forwarding (Alternative - Less Secure)

**Only use if OpenVPN is not feasible**

1. Router → **Network → Firewall → Port Forwarding**
2. Add rule:
   ```
   Name: Transformer Web UI
   External port: 5000
   Internal IP: 192.168.1.100
   Internal port: 5000
   Protocol: TCP
   ```
3. Access via: `http://<router-public-ip>:5000`

**Security considerations:**
- Add firewall rules to restrict source IPs
- Consider changing external port to non-standard (e.g., 15000)
- Use strong passwords
- Enable HTTPS (requires SSL certificate setup)

---

## Part 6: SSH Access

### 6.1 Via OpenVPN

```bash
# Connect to VPN first, then:
ssh root@192.168.1.100

# Or via Balena:
balena ssh <device-uuid>
```

### 6.2 Via RMS Remote Access

Teltonika RMS provides direct SSH access:

1. RMS Dashboard → Select device → **Terminal**
2. This opens SSH session through RMS cloud
3. Useful when VPN is not available

**Limitations:**
- Requires RMS subscription (may have free tier limits)
- Slightly higher latency than direct VPN

---

## Part 7: Security Best Practices

### 7.1 Router Security

```
✓ Change default admin password
✓ Enable HTTPS for router WebUI
✓ Disable WPS
✓ Use strong WiFi password (WPA3 if available)
✓ Keep firmware updated
✓ Disable unused services (Telnet, FTP)
✓ Enable firewall logging
✓ Restrict SSH to LAN only (unless needed)
```

### 7.2 OpenVPN Security

```
✓ Use strong encryption (AES-256)
✓ Generate unique certificates per user
✓ Revoke certificates when users leave
✓ Use certificate passwords (optional but recommended)
✓ Limit VPN access to specific IPs if possible
✓ Monitor VPN logs for unauthorized attempts
✓ Rotate certificates periodically (every 1-2 years)
```

### 7.3 Web Interface Security

```
✓ Add authentication to Flask app (currently open!)
✓ Use HTTPS (requires SSL setup)
✓ Implement rate limiting
✓ Add session timeout
✓ Log all access attempts
```

**IMPORTANT:** The current web interface has no authentication. Consider adding Flask-Login or HTTP Basic Auth before exposing to internet.

---

## Part 8: Monitoring & Troubleshooting

### 8.1 Check VPN Status

**Router:**
- Navigate to **Status → Networking → OpenVPN**
- Shows connected clients, traffic, uptime

**RMS:**
- Dashboard shows router online/offline status
- Can view VPN client connections

### 8.2 Common Issues

**Issue: Can't connect to VPN**
```bash
# Check:
- Router has internet connectivity
- OpenVPN service is running on router
- Firewall allows UDP 1194
- Client config file is correct
- Router's public IP hasn't changed (if using static IP in config)
```

**Solution:**
```bash
# In router:
Services → OpenVPN → Restart service

# Check logs:
System → Administration → Troubleshoot → System Log
Filter for "openvpn"
```

**Issue: Connected to VPN but can't access Pi**
```bash
# Check:
- Pi has correct static IP
- Firewall allows traffic from VPN zone to LAN
- Pi is online (ping test)
- Web server is running on Pi
```

**Solution:**
```bash
# SSH into Pi and check:
balena ssh <device-uuid>

# Check if web server is running:
netstat -tlnp | grep 5000

# Check container status:
docker ps
```

**Issue: Slow VPN connection**
```bash
# Optimize:
- Use UDP instead of TCP protocol
- Enable LZO compression
- Reduce MTU size (try 1400)
- Use closer RMS server region
```

---

## Part 9: Multiple Sites Setup

### 9.1 Architecture for Multiple Transformers

```
Your Office/Home
    ↓ (OpenVPN)
Site 1: Teltonika Router → Pi → Transformer A
Site 2: Teltonika Router → Pi → Transformer B
Site 3: Teltonika Router → Pi → Transformer C
```

### 9.2 Network Planning

Assign unique subnets per site:
- Site 1: `192.168.1.0/24` (Pi: `192.168.1.100`)
- Site 2: `192.168.2.0/24` (Pi: `192.168.2.100`)
- Site 3: `192.168.3.0/24` (Pi: `192.168.3.100`)

### 9.3 Accessing Multiple Sites

**Option A: Multiple VPN Connections**
- Each router has its own OpenVPN server
- Connect to one site at a time
- Disconnect and reconnect to switch sites

**Option B: Central VPN Server (Advanced)**
- Set up central OpenVPN server on cloud VPS
- All routers connect as clients to central server
- You connect to central server and access all sites
- Requires more complex setup but better for many sites

---

## Part 10: Quick Reference

### Router Default Access
```
URL: http://192.168.1.1
Default User: admin
Default Pass: admin01 (CHANGE THIS!)
```

### Pi Access (Local)
```
Web UI: http://192.168.1.100:5000
SSH: ssh root@192.168.1.100
```

### Pi Access (Remote via VPN)
```
1. Connect OpenVPN
2. Web UI: http://192.168.1.100:5000
3. SSH: ssh root@192.168.1.100
```

### RMS URLs
```
RMS Dashboard: https://rms.teltonika-networks.com
Documentation: https://wiki.teltonika-networks.com/
```

### OpenVPN Default Port
```
Protocol: UDP
Port: 1194
```

---

## Support Resources

- **Teltonika Wiki:** https://wiki.teltonika-networks.com/
- **RMS Documentation:** https://wiki.teltonika-networks.com/view/RMS
- **OpenVPN Docs:** https://community.openvpn.net/openvpn/wiki
- **Balena Docs:** https://www.balena.io/docs/

---

## Next Steps

1. ✓ Create RMS account and add routers
2. ✓ Configure OpenVPN server on each router
3. ✓ Generate and download client certificates
4. ✓ Assign static IPs to Raspberry Pis
5. ✓ Test VPN connection
6. ✓ Access web interface remotely
7. ✓ Document access credentials securely
8. ✓ Add authentication to web interface (recommended)
9. ✓ Set up monitoring/alerts for offline devices

---

**Last Updated:** 2025-11-17
**Version:** 1.0
