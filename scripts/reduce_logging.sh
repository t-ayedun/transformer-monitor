#!/bin/bash
# Reduce log verbosity on Pi 5
# This changes the log level from INFO to WARNING for cleaner output

echo "Setting log level to WARNING for cleaner output..."

# Update the environment file if it exists
if [ -f /home/smartie/transformer-monitor/.env ]; then
    sed -i 's/LOG_LEVEL=INFO/LOG_LEVEL=WARNING/g' /home/smartie/transformer-monitor/.env
    echo "✅ Updated .env file"
else
    echo "⚠️  .env file not found, setting environment variable directly"
fi

# Set for current session
export LOG_LEVEL=WARNING

echo ""
echo "Restarting service with new log level..."
sudo systemctl restart transformer-monitor

echo ""
echo "Waiting 5 seconds for service to start..."
sleep 5

echo ""
echo "Service status:"
sudo systemctl status transformer-monitor --no-pager -l | head -15

echo ""
echo "Recent logs (should be much quieter now):"
echo "Press Ctrl+C to exit"
sudo journalctl -u transformer-monitor -f
