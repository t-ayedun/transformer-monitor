#!/bin/bash
# =============================================================================
# cpu_monitor.sh
#
# Logs a CPU, memory, temperature, and disk snapshot every run.
# Designed to be called by cron every 5 minutes for a continuous audit trail.
#
# Log file: /home/smartie/transformer_monitor_data/logs/cpu_audit.log
#
# Add to cron (crontab -e):
#   */5 * * * * /home/smartie/transformer-monitor/scripts/cpu_monitor.sh
# =============================================================================

LOG_FILE="/home/smartie/transformer_monitor_data/logs/cpu_audit.log"
MAX_LOG_MB=5          # Rotate log when it exceeds this size
CPU_WARN_THRESHOLD=70 # Warn if CPU% exceeds this
TEMP_WARN_THRESHOLD=70 # Warn if CPU temp (°C) exceeds this

mkdir -p "$(dirname "$LOG_FILE")"

# ── Rotate log if too large ───────────────────────────────────────────────────
if [ -f "$LOG_FILE" ]; then
    size_mb=$(du -m "$LOG_FILE" | cut -f1)
    if [ "$size_mb" -ge "$MAX_LOG_MB" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
    fi
fi

# ── Gather metrics ────────────────────────────────────────────────────────────
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# CPU usage: average over 1-second sample
CPU_IDLE=$(top -bn1 | grep "Cpu(s)" | awk '{print $8}' | tr -d '%')
CPU_USED=$(echo "100 - ${CPU_IDLE:-0}" | bc 2>/dev/null || echo "?")

# Memory
MEM_INFO=$(free -m | awk 'NR==2{printf "used=%dMB total=%dMB (%.0f%%)", $3, $2, $3*100/$2}')

# CPU temperature
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    RAW_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    TEMP_C=$(echo "scale=1; $RAW_TEMP / 1000" | bc)
else
    TEMP_C="N/A"
fi

# Disk usage
DISK_INFO=$(df -h / | awk 'NR==2{printf "used=%s/%s (%s)", $3, $2, $5}')

# Service status
SERVICE_STATUS=$(systemctl is-active transformer-monitor 2>/dev/null || echo "unknown")

# ── Build log line ────────────────────────────────────────────────────────────
LEVEL="INFO"
NOTES=""

if [ "$CPU_USED" != "?" ] && [ "$(echo "$CPU_USED > $CPU_WARN_THRESHOLD" | bc 2>/dev/null)" = "1" ]; then
    LEVEL="WARN"
    NOTES="${NOTES}HIGH_CPU(${CPU_USED}%) "
fi

if [ "$TEMP_C" != "N/A" ] && [ "$(echo "$TEMP_C > $TEMP_WARN_THRESHOLD" | bc 2>/dev/null)" = "1" ]; then
    LEVEL="WARN"
    NOTES="${NOTES}HIGH_TEMP(${TEMP_C}°C) "
fi

LOG_LINE="[$TIMESTAMP] [$LEVEL] CPU=${CPU_USED}% | Temp=${TEMP_C}°C | Mem: $MEM_INFO | Disk: $DISK_INFO | Service=$SERVICE_STATUS${NOTES:+ | $NOTES}"

echo "$LOG_LINE" >> "$LOG_FILE"

# Also print to stdout (useful for manual runs)
echo "$LOG_LINE"
