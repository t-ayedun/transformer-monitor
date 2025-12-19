#!/bin/bash

# Configuration
DATA_DIR="/home/pi/transformer_monitor_data/videos"
WIFI_MODE_DIR="/home/pi/pi-camera-stream-flask/static/recordings"
DAYS_TO_KEEP=1

echo "Starts cleanup of video files..."

# Clean up main data directory
if [ -d "$DATA_DIR" ]; then
    echo "Cleaning $DATA_DIR (older than $DAYS_TO_KEEP days)..."
    find "$DATA_DIR" -name "*.mp4" -type f -mtime +$DAYS_TO_KEEP -delete
    find "$DATA_DIR" -name "*.h264" -type f -mtime +$DAYS_TO_KEEP -delete
    echo "Done."
else
    echo "Directory $DATA_DIR does not exist."
fi

# Clean up possible legacy/wifi mode directory
if [ -d "$WIFI_MODE_DIR" ]; then
    echo "Cleaning $WIFI_MODE_DIR (older than $DAYS_TO_KEEP days)..."
    find "$WIFI_MODE_DIR" -name "*.mp4" -type f -mtime +$DAYS_TO_KEEP -delete
    echo "Done."
else
    echo "Directory $WIFI_MODE_DIR does not exist."
fi

# Check disk usage
echo ""
echo "Current Disk Usage:"
df -h /
