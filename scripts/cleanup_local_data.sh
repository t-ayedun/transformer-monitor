#!/bin/bash
# =============================================================================
# cleanup_local_data.sh
#
# Frees up disk space on the Raspberry Pi by deleting non-essential local files
# while preserving core monitoring data (CSVs, thermal .png images, raw .npy).
#
# What is DELETED:
#   - Video files            (.mp4, .h264)
#   - Telemetry JSON/JSONL   (.json, .jsonl) from the telemetry/ dir
#   - Visual event images    (.jpg) from images/events/
#   - Periodic snapshots     (.jpg) from images/snapshots/
#
# What is PRESERVED:
#   - Temperature CSV files  (*_Temperature_*.csv)  ← core data
#   - Thermal PNG heatmaps   (*.png)                ← presentable thermal images
#   - Thermal raw data       (*.npy)                ← raw sensor arrays
#   - Application logs
#
# Usage:
#   bash cleanup_local_data.sh              # Run cleanup
#   bash cleanup_local_data.sh --dry-run    # Preview only — nothing deleted
#   bash cleanup_local_data.sh --threshold  # Only clean if disk is ≥ threshold%
#
# The --threshold flag reads DISK_THRESHOLD_PERCENT below. You can also call
# this script from a cron job with --threshold so it self-triggers only when needed:
#
#   # Run at 3am daily, auto-clean when disk ≥ 85% full
#   0 3 * * * /home/smartie/transformer-monitor/scripts/cleanup_local_data.sh --threshold >> /home/smartie/transformer_monitor_data/logs/cleanup.log 2>&1
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
DATA_DIR="/home/smartie/transformer_monitor_data"
LOG_FILE="$DATA_DIR/logs/cleanup.log"
DISK_THRESHOLD_PERCENT=80   # Only clean when disk usage reaches this % (--threshold mode)

VIDEO_DIRS=(
    "$DATA_DIR/videos"
    "/data/videos"
    "/home/smartie/pi-camera-stream-flask/static/recordings"
)
TELEMETRY_DIR="$DATA_DIR/telemetry"
IMAGES_EVENTS_DIR="$DATA_DIR/images/events"
IMAGES_SNAPSHOTS_DIR="$DATA_DIR/images/snapshots"

# ── Parse Args ───────────────────────────────────────────────────────────────
DRY_RUN=false
CHECK_THRESHOLD=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)   DRY_RUN=true ;;
        --threshold) CHECK_THRESHOLD=true ;;
    esac
done

# ── Setup ────────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── Disk Threshold Check ──────────────────────────────────────────────────────
if $CHECK_THRESHOLD; then
    DISK_USED_PERCENT=$(df / | awk 'NR==2 {gsub(/%/, "", $5); print $5}')
    log "Disk usage: ${DISK_USED_PERCENT}% (threshold: ${DISK_THRESHOLD_PERCENT}%)"
    if [ "$DISK_USED_PERCENT" -lt "$DISK_THRESHOLD_PERCENT" ]; then
        log "Disk usage is below threshold. No cleanup needed."
        exit 0
    fi
    log "Disk usage at or above threshold — starting cleanup."
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
TOTAL_FREED=0
FILES_DELETED=0

delete_files() {
    local description="$1"
    shift
    local found
    found=$(find "$@" 2>/dev/null || true)

    if [ -z "$found" ]; then
        log "  No files found: $description"
        return
    fi

    echo "$found" | while IFS= read -r file; do
        size_bytes=$(stat -c%s "$file" 2>/dev/null || echo 0)
        size_human=$(du -sh "$file" 2>/dev/null | cut -f1 || echo "?")
        if $DRY_RUN; then
            log "  [DRY-RUN] Would delete: $file ($size_human)"
        else
            rm -f "$file"
            log "  Deleted: $file ($size_human)"
            TOTAL_FREED=$((TOTAL_FREED + size_bytes))
            FILES_DELETED=$((FILES_DELETED + 1))
        fi
    done
}

delete_empty_dirs() {
    local dir="$1"
    if [ -d "$dir" ]; then
        find "$dir" -type d -empty -delete 2>/dev/null || true
    fi
}

# ── Main Cleanup ──────────────────────────────────────────────────────────────
log "============================================================"
log "  Cleanup started  $([ $DRY_RUN = true ] && echo '[DRY-RUN]' || echo '[LIVE]')"
log "============================================================"

# 1. Videos (.mp4, .h264)
log ""
log "── Video files ──────────────────────────────────────────────"
for VIDEO_DIR in "${VIDEO_DIRS[@]}"; do
    if [ -d "$VIDEO_DIR" ]; then
        delete_files "videos in $VIDEO_DIR" \
            "$VIDEO_DIR" -type f \( -name "*.mp4" -o -name "*.h264" \)
        delete_empty_dirs "$VIDEO_DIR"
    else
        log "  Skipping (not found): $VIDEO_DIR"
    fi
done

# 2. Telemetry JSON/JSONL (these are already in AWS/S3, not core data on Pi)
log ""
log "── Telemetry JSON/JSONL files ───────────────────────────────"
if [ -d "$TELEMETRY_DIR" ]; then
    delete_files "telemetry JSON" \
        "$TELEMETRY_DIR" -type f \( -name "*.json" -o -name "*.jsonl" \)
    delete_empty_dirs "$TELEMETRY_DIR"
else
    log "  Skipping (not found): $TELEMETRY_DIR"
fi

# 3. Event images (.jpg only — NOT .png thermal heatmaps, NOT .npy raw data)
log ""
log "── Event images (.jpg only, preserving .png and .npy) ───────"
if [ -d "$IMAGES_EVENTS_DIR" ]; then
    delete_files "event .jpg images" \
        "$IMAGES_EVENTS_DIR" -type f -name "*.jpg"
    delete_empty_dirs "$IMAGES_EVENTS_DIR"
else
    log "  Skipping (not found): $IMAGES_EVENTS_DIR"
fi

# 4. Periodic snapshots (.jpg only — same rule)
log ""
log "── Periodic snapshot images (.jpg only) ─────────────────────"
if [ -d "$IMAGES_SNAPSHOTS_DIR" ]; then
    delete_files "snapshot .jpg images" \
        "$IMAGES_SNAPSHOTS_DIR" -type f -name "*.jpg"
    delete_empty_dirs "$IMAGES_SNAPSHOTS_DIR"
else
    log "  Skipping (not found): $IMAGES_SNAPSHOTS_DIR"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
log ""
log "============================================================"
if $DRY_RUN; then
    log "  DRY-RUN complete. No files were actually deleted."
    log "  Re-run without --dry-run to perform the actual cleanup."
else
    FREED_MB=$(echo "scale=1; $TOTAL_FREED / 1048576" | bc 2>/dev/null || echo "?")
    log "  Cleanup complete."
    log "  Files deleted : $FILES_DELETED"
    log "  Space freed   : ~${FREED_MB} MB"
    log ""
    log "  Current disk usage:"
    df -h / | tee -a "$LOG_FILE"
fi
log "============================================================"
log ""
