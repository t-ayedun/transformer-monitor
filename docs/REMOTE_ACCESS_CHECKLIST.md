# Remote Access Setup Checklist

Quick checklist for setting up remote access to transformer monitoring sites.

## Pre-Installation Checklist

- [ ] Teltonika router model: _______________
- [ ] SIM card inserted and activated
- [ ] Router has internet connectivity
- [ ] Raspberry Pi assigned static IP: _______________
- [ ] RMS account created: _______________@_______________
- [ ] OpenVPN client software installed on your computer

---

## Router Setup Checklist

### RMS Configuration
- [ ] Router added to RMS account
- [ ] Router appears online in RMS dashboard
- [ ] Router assigned to correct group/organization
- [ ] Default admin password changed
- [ ] Router firmware updated to latest version

### OpenVPN Server Configuration
- [ ] OpenVPN service enabled on router
- [ ] Server configured with:
  - [ ] Protocol: UDP
  - [ ] Port: 1194
  - [ ] Encryption: AES-256
  - [ ] Virtual network: 10.8.0.0/24
  - [ ] Route to LAN: 192.168.x.0/24
- [ ] CA certificate generated
- [ ] Server certificate generated
- [ ] Client certificate(s) generated
- [ ] Client .ovpn file downloaded

### Network Configuration
- [ ] Raspberry Pi assigned static IP
- [ ] Firewall allows VPN → LAN traffic
- [ ] Raspberry Pi accessible from router (ping test)
- [ ] Web interface accessible locally: http://192.168.x.x:5000

---

## Client Setup Checklist

- [ ] OpenVPN client software installed
- [ ] Client configuration (.ovpn) imported
- [ ] VPN connection successful
- [ ] Received VPN IP (10.8.0.x)
- [ ] Can ping router: 192.168.x.1
- [ ] Can ping Raspberry Pi: 192.168.x.100
- [ ] Can access web interface via VPN: http://192.168.x.100:5000
- [ ] Dashboard loads successfully
- [ ] ROI Mapper accessible
- [ ] Video streams working

---

## Security Checklist

- [ ] Router admin password changed from default
- [ ] Strong WiFi password set
- [ ] OpenVPN uses AES-256 encryption
- [ ] Unique client certificates per user
- [ ] Unused router services disabled (Telnet, FTP)
- [ ] Firewall rules reviewed and configured
- [ ] SSH access restricted (if possible)
- [ ] RMS account has 2FA enabled (if available)
- [ ] Access credentials documented securely

---

## Testing Checklist

### Local Testing (Before VPN)
- [ ] Router web UI accessible: http://192.168.1.1
- [ ] Raspberry Pi pingable: ping 192.168.x.100
- [ ] Web UI accessible locally: http://192.168.x.100:5000
- [ ] Thermal camera stream working
- [ ] Visual camera stream working
- [ ] ROI mapper functional
- [ ] Data being sent to AWS

### Remote Testing (Via VPN)
- [ ] VPN connects successfully
- [ ] Can ping router from VPN
- [ ] Can ping Pi from VPN
- [ ] Web UI accessible via VPN
- [ ] All camera streams working remotely
- [ ] No significant lag or latency
- [ ] SSH access works (if enabled)

### Failover Testing
- [ ] Disconnect VPN and reconnect
- [ ] Test cellular failover (if router has backup connection)
- [ ] Power cycle router and verify auto-reconnect
- [ ] Verify RMS shows router status correctly

---

## Documentation Checklist

Create and store securely:
- [ ] Site ID: _______________
- [ ] Router serial number: _______________
- [ ] Router admin username: _______________
- [ ] Router admin password: _______________ (store in password manager)
- [ ] Router LAN IP: _______________
- [ ] Router public IP/hostname: _______________
- [ ] Raspberry Pi static IP: _______________
- [ ] OpenVPN port: _______________
- [ ] RMS account email: _______________
- [ ] Client certificate names and users
- [ ] Emergency contact: _______________

---

## Multi-Site Tracking

| Site ID | Router SN | Router IP | Pi IP | VPN Cert | Status | Notes |
|---------|-----------|-----------|-------|----------|--------|-------|
| SITE_001 | | 192.168.1.1 | 192.168.1.100 | client-site1 | ✓ | |
| SITE_002 | | 192.168.2.1 | 192.168.2.100 | client-site2 | ✓ | |
| SITE_003 | | 192.168.3.1 | 192.168.3.100 | client-site3 | ⏳ | Pending |

---

## Troubleshooting Quick Reference

**Can't connect to VPN:**
1. Check router is online in RMS
2. Verify OpenVPN service running on router
3. Check client config file is correct
4. Verify firewall allows UDP 1194

**Connected but can't access Pi:**
1. Check Pi static IP is correct
2. Ping Pi from VPN: ping 192.168.x.100
3. Check firewall allows VPN → LAN
4. Verify web server is running

**Web UI slow/not loading:**
1. Check cellular signal strength
2. Verify Pi is not overloaded (CPU/memory)
3. Test local access (if on-site)
4. Check Balena logs for errors

---

## Maintenance Schedule

- [ ] **Weekly:** Check all sites are online in RMS
- [ ] **Monthly:** Review VPN connection logs
- [ ] **Quarterly:** Update router firmware
- [ ] **Quarterly:** Test VPN access from different locations
- [ ] **Annually:** Rotate OpenVPN certificates
- [ ] **Annually:** Review and revoke unused certificates

---

## Emergency Contacts

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Technical Lead | | | |
| Site Manager | | | |
| ISP Support | | | |
| Teltonika Support | | +370 5 2127472 | gsc@teltonika.lt |

---

**Checklist Version:** 1.0
**Last Updated:** 2025-11-17
**Site:** _______________
**Completed By:** _______________
**Date:** _______________
