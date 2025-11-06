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
if [ ! -f "/data/config/site_config.yaml" ]; then
    echo "Creating site configuration from template..."
    mkdir -p /data/config
    python3 /app/scripts/generate_config.py
fi

# Display environment
echo "Environment:"
echo "  SITE_ID: ${SITE_ID:-NOT SET}"
echo "  IOT_ENDPOINT: ${IOT_ENDPOINT:-NOT SET}"
echo "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"

# Start the application
echo "Starting monitor application..."
cd /app
exec python3 -u src/main.py