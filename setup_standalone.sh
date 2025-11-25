#!/bin/bash
###############################################################################
# Transformer Monitor - Standalone Setup Script
#
# This script performs complete automated setup on a fresh Raspberry Pi OS
# Run once after cloning the repository
#
# Usage: sudo ./setup_standalone.sh
###############################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Transformer Monitor - Standalone Setup                 ║"
echo "║   Automated Raspberry Pi Configuration                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    echo "Usage: sudo ./setup_standalone.sh"
    exit 1
fi

# Detect if running on Raspberry Pi
echo -e "${BLUE}[1/10] Detecting hardware...${NC}"
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}WARNING: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    PI_MODEL=$(grep "Model" /proc/cpuinfo | cut -d':' -f2 | xargs)
    echo -e "${GREEN}✓ Detected: $PI_MODEL${NC}"
fi

# Update package lists
echo -e "${BLUE}[2/10] Updating package lists...${NC}"
apt-get update -qq

# Install system dependencies
echo -e "${BLUE}[3/10] Installing system dependencies...${NC}"
echo "This may take 5-10 minutes..."

PACKAGES=(
    python3-dev
    python3-pip
    python3-venv
    i2c-tools
    libi2c-dev
    libatlas-base-dev
    libopencv-dev
    python3-opencv
    libcamera-dev
    libcamera-apps
    python3-libcamera
    python3-picamera2
    git
    sqlite3
)

apt-get install -y "${PACKAGES[@]}" > /dev/null 2>&1 || {
    echo -e "${YELLOW}Some packages failed to install. Continuing...${NC}"
}

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Enable I2C interface
echo -e "${BLUE}[4/10] Enabling I2C interface...${NC}"
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
    echo -e "${GREEN}✓ I2C enabled (reboot required)${NC}"
    REBOOT_REQUIRED=1
else
    echo -e "${GREEN}✓ I2C already enabled${NC}"
fi

# Add user to i2c group
if ! groups $SUDO_USER | grep -q "i2c"; then
    usermod -a -G i2c $SUDO_USER
    echo -e "${GREEN}✓ Added $SUDO_USER to i2c group${NC}"
fi

# Enable Pi Camera
echo -e "${BLUE}[5/10] Enabling Pi Camera...${NC}"
if ! grep -q "^camera_auto_detect=1" /boot/config.txt; then
    echo "camera_auto_detect=1" >> /boot/config.txt
    echo -e "${GREEN}✓ Camera enabled (reboot required)${NC}"
    REBOOT_REQUIRED=1
else
    echo -e "${GREEN}✓ Camera already enabled${NC}"
fi

# Create data directories
echo -e "${BLUE}[6/10] Creating data directories...${NC}"
mkdir -p /data/{config,certs,videos,images,buffer,logs}
chown -R $SUDO_USER:$SUDO_USER /data
chmod -R 755 /data
echo -e "${GREEN}✓ Data directories created at /data${NC}"

# Create Python virtual environment
echo -e "${BLUE}[7/10] Creating Python virtual environment...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    sudo -u $SUDO_USER python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Install Python dependencies
echo -e "${BLUE}[8/10] Installing Python packages...${NC}"
echo "This may take 10-15 minutes (OpenCV is large)..."
sudo -u $SUDO_USER venv/bin/pip install --upgrade pip > /dev/null 2>&1
sudo -u $SUDO_USER venv/bin/pip install -r requirements.txt || {
    echo -e "${YELLOW}WARNING: Some Python packages may have failed${NC}"
    echo "Try running manually: venv/bin/pip install -r requirements.txt"
}
echo -e "${GREEN}✓ Python packages installed${NC}"

# Generate default configuration
echo -e "${BLUE}[9/10] Generating default configuration...${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    if [ -f "config/default_env.template" ]; then
        cp config/default_env.template .env
        echo -e "${YELLOW}⚠ Created .env from template${NC}"
        echo -e "${YELLOW}  IMPORTANT: Edit .env file with your settings before running!${NC}"
    else
        echo -e "${YELLOW}⚠ No .env template found - you'll need to create .env manually${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Run config generation
if [ -f "scripts/generate_config.py" ]; then
    sudo -u $SUDO_USER venv/bin/python scripts/generate_config.py || {
        echo -e "${YELLOW}⚠ Config generation failed - you may need to configure manually${NC}"
    }
    echo -e "${GREEN}✓ Configuration files generated${NC}"
else
    echo -e "${YELLOW}⚠ Config generator not found - manual configuration required${NC}"
fi

# Set permissions
echo -e "${BLUE}[10/10] Setting permissions...${NC}"
chown -R $SUDO_USER:$SUDO_USER "$SCRIPT_DIR"
chmod +x run.sh 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true
echo -e "${GREEN}✓ Permissions set${NC}"

# Summary
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              Setup Complete!                              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}✓ System dependencies installed${NC}"
echo -e "${GREEN}✓ I2C and camera interfaces enabled${NC}"
echo -e "${GREEN}✓ Python virtual environment created${NC}"
echo -e "${GREEN}✓ Data directories created${NC}"
echo -e "${GREEN}✓ Configuration generated${NC}"

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"

if [ -n "$REBOOT_REQUIRED" ]; then
    echo -e "${YELLOW}1. REBOOT REQUIRED to enable I2C and camera${NC}"
    echo -e "   Run: ${BLUE}sudo reboot${NC}"
    echo ""
    echo -e "${YELLOW}2. After reboot, configure your settings:${NC}"
else
    echo -e "${YELLOW}1. Configure your settings:${NC}"
fi

echo -e "   Edit: ${BLUE}.env${NC}"
echo -e "   Set: SITE_ID, location, AWS settings (if using AWS)"
echo ""

if [ -n "$REBOOT_REQUIRED" ]; then
    echo -e "${YELLOW}3. Optionally, add AWS certificates to:${NC}"
else
    echo -e "${YELLOW}2. Optionally, add AWS certificates to:${NC}"
fi
echo -e "   ${BLUE}/data/certs/root-ca.pem${NC}"
echo -e "   ${BLUE}/data/certs/device-cert.pem${NC}"
echo -e "   ${BLUE}/data/certs/device-key.pem${NC}"
echo ""

if [ -n "$REBOOT_REQUIRED" ]; then
    echo -e "${YELLOW}4. Start monitoring:${NC}"
else
    echo -e "${YELLOW}3. Start monitoring:${NC}"
fi
echo -e "   ${BLUE}./run.sh${NC}"
echo ""

if [ -n "$REBOOT_REQUIRED" ]; then
    echo -e "${YELLOW}5. (Optional) Install as system service:${NC}"
else
    echo -e "${YELLOW}4. (Optional) Install as system service:${NC}"
fi
echo -e "   ${BLUE}sudo ./install_service.sh${NC}"
echo ""

echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"

if [ -n "$REBOOT_REQUIRED" ]; then
    echo ""
    echo -e "${RED}⚠ REBOOT REQUIRED ⚠${NC}"
    echo -e "${YELLOW}Run: sudo reboot${NC}"
fi
