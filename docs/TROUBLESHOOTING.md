# Troubleshooting Guide

## Common Issues

### 1. Thermal Camera Not Detected or I/O Error

**Symptoms**:
- "Failed to initialize MLX90640" in logs
- "[Errno 121] Remote I/O error"
- "[Errno 5] Input/output error"

**Solutions**:
- **Automatic Recovery**: The system now attempts to auto-recover from I2C errors by resetting the bus. Check logs for "Reinitializing I2C".
- **Manual Check**:
  ```bash
  # Check I2C is enabled and device address (usually 0x33)
  i2cdetect -y 1
  ```
- **Hardware**: Ensure the camera is securely connected to the GPIO pins (SDA/SCL).

### 2. Smart Camera / Recording Issues

**Symptoms**:
- "Failed to start recording: Must pass io.BufferedIOBase"
- "Circular Buffer initialization failed"

**Solutions**:
- **Memory Check**: The circular buffer uses RAM (approx 3-5MB). Ensure the Pi has free memory.
  ```bash
  free -h
  ```
- **Storage Space**: Check if `/data` partition is full.
  ```bash
  df -h /data
  ```

### 3. AWS Connection Fails

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

### 4. Camera Not Working

**Symptoms**: "Camera initialization failed" or "Picamera2 error"

**Solutions**:
- **Legacy Stack**: Ensure legacy camera stack is disabled if using Picamera2.
- **Check Status**:
  ```bash
  vcgencmd get_camera
  # Should show: supported=1 detected=1
  ```

### 5. High CPU Usage

**Causes**:
- Thermal camera refresh rate too high (>8Hz)
- Motion detection processing overhead
- Advanced thermal processing (denoising/upscaling)

**Solutions**:
- Reduce thermal camera refresh rate in config (default is 8Hz).
- Disable "Advanced Processing" if running on older hardware.

### 6. SD Card Full

**Symptoms**: "No space left on device"

**Solutions**:
- **Auto-Cleanup**: The system has active storage management. Check logs for "Storage cleanup triggered".
- **Manual Cleanup**:
  ```bash
  rm /data/logs/*.log.*
  # Clear old images (if buffered locally)
  find /data/images -type f -mtime +7 -delete
  ```

### 7. Device Offline

**Checks**:
- Power supply (use official 5V/3A)
- Network connection
- Router status in Teltonika RMS
- Balena dashboard shows device status

**Recovery**:
```bash
# Reboot via Balena
balena reboot <device-uuid>
```

## Getting Help

1. Check logs: `balena logs <device-uuid> --tail`
2. SSH debug: `balena ssh <device-uuid>`
3. Contact: support@yourcompany.com