#!/bin/bash
#
# Upload Certificates to Balena Device
# Securely transfers AWS IoT certificates to deployed device
#
# Usage: ./upload_certificates.sh <site_id>
#

set -e

SITE_ID=$1
DEVICE_NAME="${SITE_ID}-monitor"
CERT_DIR="./provisioned_sites/${SITE_ID}/certificates"

if [ -z "$SITE_ID" ]; then
    echo "Usage: $0 <site_id>"
    echo "Example: $0 SITE_001"
    exit 1
fi

echo "======================================"
echo "  Upload Certificates: ${SITE_ID}"
echo "======================================"
echo ""

# Check if certificates exist
if [ ! -d "$CERT_DIR" ]; then
    echo "❌ Error: Certificates not found in $CERT_DIR"
    exit 1
fi

# Check balena CLI
if ! command -v balena &> /dev/null; then
    echo "❌ Error: Balena CLI not installed"
    exit 1
fi

echo "[1/3] Checking device status..."
if ! balena device $DEVICE_NAME &> /dev/null; then
    echo "❌ Error: Device $DEVICE_NAME not found"
    exit 1
fi

# Check if device is online
STATUS=$(balena device $DEVICE_NAME | grep "Status:" | awk '{print $2}')
if [ "$STATUS" != "online" ]; then
    echo "❌ Error: Device is not online (status: $STATUS)"
    echo "   Wait for device to come online and try again"
    exit 1
fi
echo "  ✓ Device is online"

echo ""
echo "[2/3] Creating certificates directory on device..."
balena ssh $DEVICE_NAME "mkdir -p /data/certificates && chmod 700 /data/certificates"
echo "  ✓ Directory created"

echo ""
echo "[3/3] Uploading certificates..."

# Upload each certificate file
for cert in AmazonRootCA1.pem device.pem.crt private.pem.key; do
    if [ -f "${CERT_DIR}/${cert}" ]; then
        echo "  Uploading ${cert}..."
        balena scp "${CERT_DIR}/${cert}" "${DEVICE_NAME}:/data/certificates/${cert}"

        # Set restrictive permissions on private key
        if [ "$cert" == "private.pem.key" ]; then
            balena ssh $DEVICE_NAME "chmod 600 /data/certificates/private.pem.key"
        fi
    else
        echo "  ⚠ Warning: ${cert} not found"
    fi
done

echo ""
echo "  ✓ Certificates uploaded"

echo ""
echo "======================================"
echo "  Certificate Upload Complete!"
echo "======================================"
echo ""
echo "Verify certificates:"
echo "  balena ssh $DEVICE_NAME 'ls -la /data/certificates/'"
echo ""
echo "Restart application:"
echo "  balena restart $DEVICE_NAME"
echo ""
echo "View logs:"
echo "  balena logs $DEVICE_NAME --tail"
echo ""
echo "======================================"
