#!/bin/bash
set -e

echo "=========================================="
echo "Transformer Monitor Starting"
echo "=========================================="

# Wait for system to stabilize
echo "Waiting for system initialization..."
sleep 10

# Check I2C devices
echo "Checking I2C devices..."
if command -v i2cdetect &> /dev/null; then
    i2cdetect -y 1 || echo "Warning: I2C detection failed"
fi

# Check for certificates
echo "Checking certificates..."
CERT_DIR="/data/certs"
if [ ! -f "$CERT_DIR/certificate.pem.crt" ]; then
    echo "WARNING: Device certificate not found!"
    echo "Please upload certificates to $CERT_DIR/"
fi

# Check configuration
echo "Checking configuration..."
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="/data/config"

if [ ! -f "$CONFIG_DIR/site_config.yaml" ]; then
    echo "Creating site configuration from template..."
    # Ensure config directory exists
    if [ ! -d "$CONFIG_DIR" ]; then
        echo "Error: $CONFIG_DIR does not exist. Please run: sudo mkdir -p /data/{config,logs,images,buffer,certs} && sudo chown -R \$USER:\$USER /data"
        exit 1
    fi
    python3 "$PROJECT_ROOT/scripts/generate_config.py"
fi

# Display environment
echo "Environment:"
echo "  PROJECT_ROOT: $PROJECT_ROOT"
echo "  SITE_ID: ${SITE_ID:-NOT SET}"
echo "  IOT_ENDPOINT: ${IOT_ENDPOINT:-NOT SET}"
echo "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"

# Start the application
echo "Starting monitor application..."
cd "$PROJECT_ROOT"
exec python3 -u src/main.py