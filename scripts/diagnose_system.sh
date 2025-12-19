#!/bin/bash

echo "=== SYSTEM DIAGNOSTIC ==="
echo ""

echo "1. Checking if service is running:"
sudo systemctl status transformer-monitor | grep "Active:"
echo ""

echo "2. Checking data directories:"
ls -la /home/smartie/transformer_monitor_data/ 2>/dev/null || echo "Directory does not exist!"
echo ""

echo "3. Checking for video files:"
find /home/smartie/transformer_monitor_data/videos -type f 2>/dev/null | head -5 || echo "No videos found"
echo ""

echo "4. Checking for temperature CSVs:"
find /home/smartie/transformer_monitor_data/temperature -type f 2>/dev/null | head -5 || echo "No CSVs found"
echo ""

echo "5. Checking for images:"
find /home/smartie/transformer_monitor_data/images -type f 2>/dev/null | head -5 || echo "No images found"
echo ""

echo "6. Checking service logs (last 30 lines):"
sudo journalctl -u transformer-monitor -n 30 --no-pager
echo ""

echo "7. Checking config file:"
if [ -f "config/site_config.yaml" ]; then
    echo "Config exists: config/site_config.yaml"
    grep "remote_dir" config/site_config.yaml
else
    echo "ERROR: config/site_config.yaml NOT FOUND!"
fi
echo ""

echo "8. Checking FTP connection from service perspective:"
echo "   (Looking for FTP-related log entries)"
sudo journalctl -u transformer-monitor | grep -i "ftp" | tail -10
