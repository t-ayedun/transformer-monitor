#!/bin/bash

echo "=== DEPLOYMENT SCRIPT FOR SITE B (C468) ==="
echo ""

# Stop the service
echo "1. Stopping service..."
sudo systemctl stop transformer-monitor

# Copy the correct config
echo "2. Copying site-specific config..."
cp config/site_config.C468.yaml config/site_config.yaml

# Verify FTP is enabled
echo "3. Verifying FTP configuration..."
grep "ftp_storage:" -A 5 config/site_config.yaml | head -6

# Create data directories with correct permissions
echo "4. Creating data directories..."
mkdir -p /home/smartie/transformer_monitor_data/{videos,images,temperature}
sudo chown -R smartie:smartie /home/smartie/transformer_monitor_data

# Start the service
echo "5. Starting service..."
sudo systemctl start transformer-monitor

# Wait a moment
sleep 3

# Check status
echo "6. Checking service status..."
sudo systemctl status transformer-monitor | grep "Active:"

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "Monitor logs with: sudo journalctl -u transformer-monitor -f"
