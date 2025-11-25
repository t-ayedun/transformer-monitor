#!/bin/bash
###############################################################################
# Transformer Monitor - Systemd Service Installer
#
# Install transformer monitor as a systemd service for auto-start on boot
# Run after completing setup_standalone.sh
#
# Usage: sudo ./install_service.sh
###############################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║    Transformer Monitor - Service Installer               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    echo "Usage: sudo ./install_service.sh"
    exit 1
fi

# Get script directory (where the project is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="transformer-monitor"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo -e "${BLUE}Installing systemd service...${NC}"
echo "Project directory: $SCRIPT_DIR"
echo "Service file: $SERVICE_FILE"
echo ""

# Create systemd service file
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Transformer Thermal Monitor
Documentation=https://github.com/yourusername/transformer-monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SUDO_USER
Group=$SUDO_USER
WorkingDirectory=$SCRIPT_DIR

# Load environment variables
EnvironmentFile=-$SCRIPT_DIR/.env

# Set Python path
Environment="PYTHONPATH=$SCRIPT_DIR/src"

# Start command
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/src/main.py

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=transformer-monitor

# Resource limits (optional - prevent runaway processes)
MemoryMax=1G
CPUQuota=80%

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Service file created${NC}"

# Reload systemd daemon
echo -e "${BLUE}Reloading systemd daemon...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

# Enable service (auto-start on boot)
echo -e "${BLUE}Enabling service to start on boot...${NC}"
systemctl enable "$SERVICE_NAME"
echo -e "${GREEN}✓ Service enabled${NC}"

echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           Service Installation Complete!                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}SERVICE COMMANDS:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Start service:    ${BLUE}sudo systemctl start $SERVICE_NAME${NC}"
echo -e "Stop service:     ${BLUE}sudo systemctl stop $SERVICE_NAME${NC}"
echo -e "Restart service:  ${BLUE}sudo systemctl restart $SERVICE_NAME${NC}"
echo -e "Service status:   ${BLUE}sudo systemctl status $SERVICE_NAME${NC}"
echo -e "View logs:        ${BLUE}sudo journalctl -u $SERVICE_NAME -f${NC}"
echo -e "Disable auto-start: ${BLUE}sudo systemctl disable $SERVICE_NAME${NC}"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}The service will automatically start on boot.${NC}"
echo -e "${GREEN}To start it now, run: ${BLUE}sudo systemctl start $SERVICE_NAME${NC}"
echo ""
