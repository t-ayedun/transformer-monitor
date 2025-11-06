# Troubleshooting Guide

## Common Issues

### 1. Thermal Camera Not Detected

**Symptoms**: "Failed to initialize MLX90640" in logs

**Solutions**:
```bash
# Check I2C is enabled
ls /dev/i2c-*

# Scan for devices
i2cdetect -y 1

# Should see device at 0x33
# If not:
# - Check physical connections
# - Verify I2C is enabled in config.txt
# - Try different I2C address (0x32 or 0x33)
```

### 2. AWS Connection Fails

**Symptoms**: "Connection failed" or certificate errors

**Checks**:
- Verify certificates are in `/data/certs/`
- Check certificate permissions (should be readable)
- Verify IoT endpoint is correct
- Check thing name matches certificate
- Ensure policy is attached to certificate
```bash
# Test connectivity
ping xxxxx-ats.iot.region.amazonaws.com

# Check certificate files
ls -la /data/certs/
```

### 3. Camera Not Working

**Symptoms**: "Camera initialization failed"

**Solutions**:
```bash
# Check camera is detected
vcgencmd get_camera

# Should show: supported=1 detected=1

# If not, enable camera
sudo raspi-config nonint do_camera 0
sudo reboot
```

### 4. High CPU Usage

**Causes**:
- Thermal camera refresh rate too high
- Too frequent captures
- Image processing overhead

**Solutions**:
- Reduce thermal camera refresh rate (8Hz is good balance)
- Increase capture interval
- Check for runaway processes

### 5. SD Card Full

**Symptoms**: "No space left on device"

**Solutions**:
```bash
# Check disk usage
df -h

# Clear old logs
rm /data/logs/*.log.*

# Clear old images (if buffered locally)
find /data/images -type f -mtime +7 -delete

# Check database size
du -h /data/buffer/readings.db
```

### 6. Device Offline

**Checks**:
- Power supply (use official 5V/3A)
- Network connection
- Router status in Teltonika RMS
- Balena dashboard shows device status

**Recovery**:
```bash
# Reboot via Balena
balena reboot <device-uuid>

# Or physically power cycle
```

### 7. Data Not Reaching AWS

**Debug steps**:
```bash
# Check local buffer
balena ssh <device-uuid>
sqlite3 /data/buffer/readings.db "SELECT COUNT(*) FROM telemetry WHERE sent=0"

# Check logs for publish errors
balena logs <device-uuid> | grep -i error

# Verify network connectivity
ping 8.8.8.8
```

## Getting Help

1. Check logs: `balena logs <device-uuid> --tail`
2. SSH debug: `balena ssh <device-uuid>`
3. Contact: support@yourcompany.com