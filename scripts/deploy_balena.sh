#!/bin/bash
#
# Balena Deployment Script
# Automates deployment to Balena fleet
#
# Usage: ./deploy_balena.sh <site_id>
#

set -e  # Exit on error

SITE_ID=$1
BALENA_APP="${BALENA_APP:-transformer-monitor}"
PROVISIONED_DIR="./provisioned_sites/${SITE_ID}"

if [ -z "$SITE_ID" ]; then
    echo "Usage: $0 <site_id>"
    echo "Example: $0 SITE_001"
    exit 1
fi

echo "======================================"
echo "  Balena Deployment: ${SITE_ID}"
echo "======================================"
echo ""

# Check if site has been provisioned
if [ ! -d "$PROVISIONED_DIR" ]; then
    echo "❌ Error: Site ${SITE_ID} not found in provisioned_sites/"
    echo "   Run provision_site.py first"
    exit 1
fi

# Check balena CLI is installed
if ! command -v balena &> /dev/null; then
    echo "❌ Error: Balena CLI not installed"
    echo "   Install: npm install -g balena-cli"
    exit 1
fi

# Check balena login
if ! balena whoami &> /dev/null; then
    echo "❌ Error: Not logged into Balena"
    echo "   Run: balena login"
    exit 1
fi

echo "[1/6] Checking Balena application..."
if ! balena app $BALENA_APP &> /dev/null; then
    echo "  Creating Balena application: $BALENA_APP"
    balena app create $BALENA_APP --type raspberrypi4-64
fi
echo "  ✓ Application exists: $BALENA_APP"

echo ""
echo "[2/6] Registering device..."
DEVICE_NAME="${SITE_ID}-monitor"

# Check if device already exists
if balena device $DEVICE_NAME &> /dev/null; then
    echo "  ⚠ Device already exists: $DEVICE_NAME"
    read -p "  Reuse existing device? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "  Aborted."
        exit 1
    fi
else
    echo "  Creating device: $DEVICE_NAME"
    balena device register $BALENA_APP --name $DEVICE_NAME
fi
echo "  ✓ Device registered: $DEVICE_NAME"

echo ""
echo "[3/6] Setting environment variables..."

# Load environment variables from provisioned config
if [ -f "${PROVISIONED_DIR}/config/.env" ]; then
    source "${PROVISIONED_DIR}/config/.env"

    # Set device environment variables
    balena env add -d $DEVICE_NAME SITE_ID "$SITE_ID" || balena env update -d $DEVICE_NAME SITE_ID "$SITE_ID"
    balena env add -d $DEVICE_NAME SITE_NAME "$SITE_NAME" || balena env update -d $DEVICE_NAME SITE_NAME "$SITE_NAME"
    balena env add -d $DEVICE_NAME TRANSFORMER_SN "$TRANSFORMER_SN" || balena env update -d $DEVICE_NAME TRANSFORMER_SN "$TRANSFORMER_SN"
    balena env add -d $DEVICE_NAME TIMEZONE "$TIMEZONE" || balena env update -d $DEVICE_NAME TIMEZONE "$TIMEZONE"
    balena env add -d $DEVICE_NAME AWS_REGION "$AWS_REGION" || balena env update -d $DEVICE_NAME AWS_REGION "$AWS_REGION"
    balena env add -d $DEVICE_NAME IOT_ENDPOINT "$IOT_ENDPOINT" || balena env update -d $DEVICE_NAME IOT_ENDPOINT "$IOT_ENDPOINT"
    balena env add -d $DEVICE_NAME IOT_THING_NAME "$IOT_THING_NAME" || balena env update -d $DEVICE_NAME IOT_THING_NAME "$IOT_THING_NAME"
    balena env add -d $DEVICE_NAME PRODUCTION_MODE "true" || balena env update -d $DEVICE_NAME PRODUCTION_MODE "true"

    echo "  ✓ Environment variables configured"
else
    echo "  ⚠ Warning: .env file not found, skipping environment variables"
fi

echo ""
echo "[4/6] Building and pushing application..."
echo "  This may take 5-15 minutes..."

# Use Balena-specific docker-compose
cp docker-compose.balena.yml docker-compose.yml.bak
balena push $BALENA_APP --source . --dockerignore .dockerignore

echo "  ✓ Application pushed to Balena cloud"

echo ""
echo "[5/6] Downloading Balena OS image..."
IMAGE_FILE="${PROVISIONED_DIR}/balena-${SITE_ID}.img"

if [ ! -f "$IMAGE_FILE" ]; then
    balena os download $BALENA_APP --output $IMAGE_FILE --version latest
    echo "  ✓ OS image downloaded: $IMAGE_FILE"
else
    echo "  ✓ Using existing OS image: $IMAGE_FILE"
fi

echo ""
echo "[6/6] Configuring OS image with device..."
balena os configure $IMAGE_FILE --device $DEVICE_NAME

echo "  ✓ OS image configured"

echo ""
echo "======================================"
echo "  Deployment Prepared!"
echo "======================================"
echo ""
echo "📦 Balena OS Image:  $IMAGE_FILE"
echo "🔧 Device Name:      $DEVICE_NAME"
echo "☁️  Application:      $BALENA_APP"
echo ""
echo "Next steps:"
echo "1. Flash SD card:"
echo "   balena local flash $IMAGE_FILE"
echo ""
echo "2. Copy certificates to device after it comes online:"
echo "   ./scripts/upload_certificates.sh $SITE_ID"
echo ""
echo "3. Monitor device logs:"
echo "   balena logs $DEVICE_NAME --tail"
echo ""
echo "======================================"
