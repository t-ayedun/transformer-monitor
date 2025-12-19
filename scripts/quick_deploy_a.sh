#!/bin/bash
# Quick fix deployment for Site A (C368)

echo "Stopping service..."
sudo systemctl stop transformer-monitor

echo "Copying config..."
cp /home/smartie/transformer-monitor/config/site_config.C368.yaml /home/smartie/transformer-monitor/config/site_config.yaml

echo "Verifying config has required fields..."
grep "id:" /home/smartie/transformer-monitor/config/site_config.yaml | head -1
grep "i2c_address:" /home/smartie/transformer-monitor/config/site_config.yaml | head -1

echo "Creating directories..."
mkdir -p /home/smartie/transformer_monitor_data/{videos,images,temperature,logs,buffer}

echo "Starting service..."
sudo systemctl start transformer-monitor

sleep 2
echo "Service status:"
sudo systemctl status transformer-monitor --no-pager | grep "Active:"
