#!/bin/bash
# Update script for Transformer Monitor

echo "Starting update process..."

# Navigate to project directory (support both standard paths)
if [ -d "/home/smartie/transformer-monitor" ]; then
    cd /home/smartie/transformer-monitor
elif [ -d "/home/pi/transformer-monitor" ]; then
    cd /home/pi/transformer-monitor
else
    # Fallback to current directory or exit
    echo "Could not find transformer-monitor directory in standard locations."
    echo "Assuming current directory..."
fi

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
