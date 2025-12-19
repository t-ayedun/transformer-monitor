#!/bin/bash
# Quick fix script for Pi 5 - Pull clean code and restart service

echo "Pulling latest clean code from stable-deployment..."
cd ~/transformer-monitor
git fetch origin
git reset --hard origin/stable-deployment

echo ""
echo "Verifying Python syntax..."
python3 -m py_compile src/camera_web_interface.py && echo "✅ Syntax OK" || echo "❌ Syntax Error!"

echo ""
echo "Restarting service..."
sudo systemctl restart transformer-monitor

echo ""
echo "Waiting 3 seconds..."
sleep 3

echo ""
echo "Checking service status..."
sudo systemctl status transformer-monitor --no-pager -l | head -20

echo ""
echo "Recent logs (press Ctrl+C to exit):"
sudo journalctl -u transformer-monitor -f
