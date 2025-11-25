#!/bin/bash
###############################################################################
# Transformer Monitor - Startup Script
#
# Simple script to start the transformer monitoring system
# Handles environment setup and graceful shutdown
#
# Usage: ./run.sh
###############################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Transformer Monitor - Starting System            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}ERROR: Virtual environment not found${NC}"
    echo "Please run setup first: sudo ./setup_standalone.sh"
    exit 1
fi

# Load environment variables
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Loading environment variables from .env${NC}"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}⚠ No .env file found - using defaults${NC}"
    echo "  To configure, copy config/default_env.template to .env"
fi

# Verify I2C is enabled
echo -e "${BLUE}Checking I2C interface...${NC}"
if [ -c "/dev/i2c-1" ]; then
    echo -e "${GREEN}✓ I2C enabled${NC}"
else
    echo -e "${RED}ERROR: I2C not enabled${NC}"
    echo "Run: sudo raspi-config"
    echo "Navigate to: Interface Options -> I2C -> Enable"
    exit 1
fi

# Verify camera is enabled
echo -e "${BLUE}Checking camera interface...${NC}"
if [ -d "/sys/class/video-linux" ] || [ -e "/dev/video0" ] || vcgencmd get_camera &>/dev/null; then
    echo -e "${GREEN}✓ Camera interface available${NC}"
else
    echo -e "${YELLOW}⚠ Camera interface may not be enabled${NC}"
    echo "If you encounter camera errors, run: sudo raspi-config"
    echo "Navigate to: Interface Options -> Camera -> Enable"
fi

# Verify thermal camera is connected
echo -e "${BLUE}Checking thermal camera (I2C)...${NC}"
if i2cdetect -y 1 | grep -q "33"; then
    echo -e "${GREEN}✓ MLX90640 thermal camera detected at 0x33${NC}"
else
    echo -e "${YELLOW}⚠ MLX90640 thermal camera not detected${NC}"
    echo "  Make sure camera is properly connected to I2C pins"
    echo "  Continuing anyway..."
fi

# Check configuration
echo -e "${BLUE}Checking configuration...${NC}"
if [ -f "/data/config/site_config.yaml" ]; then
    echo -e "${GREEN}✓ Site configuration exists${NC}"
else
    echo -e "${YELLOW}⚠ Generating default configuration...${NC}"
    venv/bin/python scripts/generate_config.py || {
        echo -e "${RED}ERROR: Failed to generate configuration${NC}"
        exit 1
    }
fi

# Create necessary directories
echo -e "${BLUE}Creating runtime directories...${NC}"
mkdir -p /data/{videos,images,buffer,logs}
echo -e "${GREEN}✓ Directories ready${NC}"

# Activate virtual environment and start application
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              Starting Transformer Monitor                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${GREEN}Web Dashboard: ${BLUE}http://$(hostname -I | awk '{print $1}'):5000${NC}"
echo -e "${GREEN}Press Ctrl+C to stop${NC}"
echo ""

# Handle graceful shutdown
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down gracefully...${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the application
cd "$SCRIPT_DIR/src"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
exec ../venv/bin/python main.py
