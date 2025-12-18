#!/bin/bash
# Update script for Transformer Monitor

echo "Starting update process..."

# Navigate to project directory
cd /home/pi/transformer-monitor || exit

# Pull latest changes
echo "Pulling latest changes from git..."
git pull

# Update dependencies
echo "Updating Python dependencies..."
pip install -r requirements.txt

# Restart service
echo "Restarting transformer-monitor service..."
sudo systemctl restart transformer-monitor

echo "Update complete!"
