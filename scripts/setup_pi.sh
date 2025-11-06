#!/bin/bash
# Initial Raspberry Pi setup script
# Run this BEFORE deploying via Balena

set -e

echo "=========================================="
echo "Raspberry Pi Initial Setup"
echo "=========================================="

# Update system
echo "Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# Enable I2C
echo "Enabling I2C..."
sudo raspi-config nonint do_i2c 0

# Enable Camera
echo "Enabling Camera..."
sudo raspi-config nonint do_camera 0

# Install essential tools
echo "Installing tools..."
sudo apt-get install -y \
    git \
    i2c-tools \
    python3-pip \
    vim

# Set up watchdog
echo "Configuring watchdog..."
echo "bcm2835_wdt" | sudo tee -a /etc/modules
sudo modprobe bcm2835_wdt

# Disable unnecessary services (optional, for performance)
echo "Disabling unnecessary services..."
sudo systemctl disable bluetooth
sudo systemctl disable hciuart

# Configure network (if using static IP)
# Uncomment and modify if needed
# echo "Configuring static IP..."
# sudo tee -a /etc/dhcpcd.conf <<EOF
# interface eth0
# static ip_address=192.168.1.100/24
# static routers=192.168.1.1
# static domain_name_servers=8.8.8.8
# EOF

echo "=========================================="
echo "Setup complete! Please reboot."
echo "After reboot, flash Balena image."
echo "=========================================="