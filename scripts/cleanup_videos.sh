#!/bin/bash
# cleanup_videos.sh
# Removes video files larger than 100MB to prevent bandwidth exhaustion
# Usage: ./cleanup_videos.sh [dry-run]

VIDEO_DIR="/home/smartie/transformer_monitor_data/videos"
MAX_SIZE__MB=100
LOG_FILE="/home/smartie/transformer_monitor_data/logs/cleanup.log"

# Ensure log directory exists
mkdir -p $(dirname "$LOG_FILE")

echo "=== Video Cleanup Started: $(date) ===" | tee -a "$LOG_FILE"

# Check if directory exists
if [ ! -d "$VIDEO_DIR" ]; then
    echo "Error: Video directory $VIDEO_DIR not found." | tee -a "$LOG_FILE"
    exit 1
fi

# Find large files
echo "Scanning for files larger than ${MAX_SIZE__MB}MB in $VIDEO_DIR..." | tee -a "$LOG_FILE"
FOUND_FILES=$(find "$VIDEO_DIR" -type f -size +${MAX_SIZE__MB}M)

if [ -z "$FOUND_FILES" ]; then
    echo "No large files found." | tee -a "$LOG_FILE"
    exit 0
fi

# List files found
echo "$FOUND_FILES" | while read -r file; do
    size=$(du -h "$file" | cut -f1)
    echo "Found: $file ($size)" | tee -a "$LOG_FILE"
done

# Check mode
if [ "$1" == "dry-run" ]; then
    echo "--- DRY RUN: No files deleted ---" | tee -a "$LOG_FILE"
else
    # Delete files
    echo "$FOUND_FILES" | while read -r file; do
        rm "$file"
        if [ $? -eq 0 ]; then
            echo "Deleted: $file" | tee -a "$LOG_FILE"
        else
            echo "Failed to delete: $file" | tee -a "$LOG_FILE"
        fi
    done
fi

echo "=== Cleanup Complete: $(date) ===" | tee -a "$LOG_FILE"
echo ""
