# FTP Circuit Breaker Fix

## Problem
The FTP server blocked the IP address (156.0.213.166) due to firewall rules, causing the transformer monitor to continuously retry connections. This resulted in:
- High CPU usage (66.9%)
- Continuous error logging
- Potential hosting resource exhaustion

## Solution
Implemented a **circuit breaker pattern** in `ftp_publisher.py` that:

1. **Tracks consecutive connection failures**
2. **Automatically pauses connection attempts** after 3 consecutive failures
3. **Waits 5 minutes** before attempting to reconnect
4. **Resets the circuit breaker** on successful connection

## Changes Made

### 1. Circuit Breaker State Variables
Added to `FTPPublisher.__init__()`:
```python
self.circuit_breaker_active = False
self.circuit_breaker_until = 0
self.circuit_breaker_duration = 300  # 5 minutes pause
self.consecutive_failures = 0
self.max_failures_before_break = 3  # Trip after 3 failures
```

### 2. Connection Logic Updates
- `_connect()`: Checks circuit breaker before attempting connection, increments failure counter, activates circuit breaker after 3 failures
- `_ensure_connection()`: Quick check for circuit breaker before acquiring lock

### 3. Manual Control Methods
Added utility methods:
- `pause_uploads(duration_seconds)` - Manually pause FTP uploads
- `resume_uploads()` - Manually resume FTP uploads
- `is_paused()` - Check if uploads are currently paused
- `get_stats()` - Now includes circuit breaker status

## Immediate Actions Required

### Option 1: Restart the Service (Recommended)
The circuit breaker will automatically activate after 3 failures and pause for 5 minutes:

```bash
sudo systemctl restart transformer-monitor
```

Monitor the logs:
```bash
sudo journalctl -u transformer-monitor -f
```

You should see:
```
FTP circuit breaker activated after 3 failures. Pausing connection attempts for 300s (until HH:MM:SS)
```

### Option 2: Resolve the Firewall Block
1. Visit the CAPTCHA URL provided in the error message:
   ```
   https://premium99.web-hosting.com/
   ```
2. Complete the CAPTCHA to unblock your IP
3. Restart the service

### Option 3: Disable FTP Temporarily
Edit the site configuration:
```bash
nano ~/transformer-monitor/config/site_config.yaml
```

Set:
```yaml
ftp_storage:
  enabled: false
```

Then restart:
```bash
sudo systemctl restart transformer-monitor
```

## Long-term Recommendations

1. **Monitor Circuit Breaker Status**: Check logs regularly for circuit breaker activations
2. **Adjust Thresholds**: If needed, modify in `ftp_publisher.py`:
   - `max_failures_before_break`: Number of failures before pausing (default: 3)
   - `circuit_breaker_duration`: Pause duration in seconds (default: 300 = 5 minutes)

3. **Consider Alternative Upload Methods**:
   - Use AWS IoT instead of FTP for real-time data
   - Implement exponential backoff for individual upload attempts
   - Add rate limiting to prevent rapid retries

## Verification

After restarting, check that the circuit breaker is working:

```bash
# Watch for circuit breaker activation
sudo journalctl -u transformer-monitor -f | grep -i "circuit breaker"

# Check CPU usage (should drop significantly)
top -p $(pgrep -f transformer-monitor)
```

Expected behavior:
- After 3 FTP failures, you'll see: `FTP circuit breaker activated`
- No more FTP connection attempts for 5 minutes
- CPU usage should drop below 25%
- After 5 minutes, one retry attempt, then another 5-minute pause if still blocked

## Files Modified
- `src/ftp_publisher.py` - Added circuit breaker logic
- `scripts/ftp_control.py` - Created utility script (for reference)
