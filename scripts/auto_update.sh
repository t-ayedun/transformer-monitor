#!/bin/bash
# =============================================================================
# auto_update.sh
#
# Checks if the remote stable-deployment branch has new commits.
# If yes: pulls the latest code and restarts the transformer-monitor service.
#
# Designed to be triggered by a systemd timer every hour.
# Very low compute cost: just a git fetch + hash comparison.
#
# Log: /home/smartie/transformer_monitor_data/logs/auto_update.log
# =============================================================================

set -euo pipefail

PROJECT_DIR="/home/smartie/transformer-monitor"
BRANCH="stable-deployment"
LOG_FILE="/home/smartie/transformer_monitor_data/logs/auto_update.log"
MAX_LOG_MB=5

mkdir -p "$(dirname "$LOG_FILE")"

# ── Log rotation ──────────────────────────────────────────────────────────────
if [ -f "$LOG_FILE" ]; then
    size_mb=$(du -m "$LOG_FILE" | cut -f1)
    if [ "$size_mb" -ge "$MAX_LOG_MB" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
    fi
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== Auto-update check ==="

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [ ! -d "$PROJECT_DIR/.git" ]; then
    log "ERROR: $PROJECT_DIR is not a git repository. Aborting."
    exit 1
fi

cd "$PROJECT_DIR"

# Ensure we are on the right branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    log "WARNING: Currently on branch '$CURRENT_BRANCH', not '$BRANCH'. Skipping update."
    exit 0
fi

# ── Check for new commits (extremely lightweight — just a network fetch) ──────
log "Fetching remote..."
git fetch origin "$BRANCH" --quiet 2>&1 | tee -a "$LOG_FILE" || {
    log "WARNING: git fetch failed (network issue?). Will retry next cycle."
    exit 0
}

LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    log "Already up to date ($LOCAL_HASH). No action needed."
    exit 0
fi

log "New commits detected! Local: ${LOCAL_HASH:0:8} → Remote: ${REMOTE_HASH:0:8}"

# ── Pull ──────────────────────────────────────────────────────────────────────
log "Pulling latest code..."
git pull origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

NEW_HASH=$(git rev-parse HEAD)
log "Updated to: $NEW_HASH"

# ── Restart service ───────────────────────────────────────────────────────────
log "Restarting transformer-monitor service..."
sudo systemctl restart transformer-monitor 2>&1 | tee -a "$LOG_FILE"

# Brief pause then verify it came back up
sleep 5
SERVICE_STATE=$(systemctl is-active transformer-monitor 2>/dev/null || echo "failed")
if [ "$SERVICE_STATE" = "active" ]; then
    log "✅ Service restarted successfully."
else
    log "❌ Service did not come back up (state: $SERVICE_STATE). Check: sudo journalctl -u transformer-monitor -n 50"
fi

log "=== Update complete ==="
