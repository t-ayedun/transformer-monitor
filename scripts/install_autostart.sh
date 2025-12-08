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

# 1. Copy service file
if [ ! -f "$SOURCE_PATH" ]; then
    echo "Error: Service file not found at $SOURCE_PATH"
    exit 1
fi

cp "$SOURCE_PATH" "$SERVICE_PATH"
chmod 644 "$SERVICE_PATH"
echo "Service file copied to $SERVICE_PATH"

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
