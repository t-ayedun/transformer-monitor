#!/bin/bash
set -e

echo "=========================================="
echo "Transformer Monitor Auto-Start Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root (sudo)"
  exit 1
fi

SERVICE_NAME="transformer-monitor.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
SOURCE_PATH="$(dirname $(readlink -f $0))/transformer-monitor.service"

echo "Installing service from $SOURCE_PATH..."

# 1. Detect User and Path
# Get the regular user who owns the script directory (assuming not root, or fallback to 'pi')
REAL_USER=$(stat -c '%U' "$SOURCE_PATH")
# If script is owned by root (unlikely if cloned by user), try to guess from sudo env
if [ "$REAL_USER" == "root" ] && [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
fi

# Get absolute path to the project root (one level up from scripts/)
PROJECT_ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

echo "Configuration detected:"
echo "  User: $REAL_USER"
echo "  Path: $PROJECT_ROOT"

# 1. Copy and Configure service file
if [ ! -f "$SOURCE_PATH" ]; then
    echo "Error: Service file not found at $SOURCE_PATH"
    exit 1
fi

# Use sed to replace placeholders/defaults with actual values
# We work on a temp file first
TMP_SERVICE="/tmp/$SERVICE_NAME"
cp "$SOURCE_PATH" "$TMP_SERVICE"

# Replace User=pi with User=$REAL_USER
sed -i "s/^User=.*/User=$REAL_USER/" "$TMP_SERVICE"

# Replace WorkingDirectory with actual path
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$PROJECT_ROOT|" "$TMP_SERVICE"

# Replace ExecStart path
sed -i "s|^ExecStart=.*|ExecStart=$PROJECT_ROOT/scripts/start.sh|" "$TMP_SERVICE"

# Move to final location
mv "$TMP_SERVICE" "$SERVICE_PATH"
chmod 644 "$SERVICE_PATH"
echo "Service file configured and installed to $SERVICE_PATH"

# 2. Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# 3. Enable service
echo "Enabling $SERVICE_NAME..."
systemctl enable "$SERVICE_NAME"

# 4. Check status
if systemctl is-enabled "$SERVICE_NAME" >/dev/null; then
    echo "✅ Success: Service enabled and will start on boot."
    echo "To start immediately, run: sudo systemctl start $SERVICE_NAME"
    echo "To check logs, run: sudo journalctl -u $SERVICE_NAME -f"
else
    echo "❌ Error: Failed to enable service."
    exit 1
fi
echo "=========================================="
