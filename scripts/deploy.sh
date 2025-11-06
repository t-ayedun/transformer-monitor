#!/bin/bash
# Deployment script for Balena
# Usage: ./scripts/deploy.sh

set -e

APP_NAME="transformer-monitor"
VERSION=$(cat VERSION)

echo "=========================================="
echo "Deploying $APP_NAME v$VERSION"
echo "=========================================="

# Check Balena CLI
if ! command -v balena &> /dev/null; then
    echo "Error: Balena CLI not installed"
    echo "Install: npm install -g balena-cli"
    exit 1
fi

# Check if logged in
if ! balena whoami &> /dev/null; then
    echo "Not logged in to Balena"
    echo "Run: balena login"
    exit 1
fi

# Confirm
read -p "Deploy to production? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Deploy
echo "Pushing to Balena..."
balena push $APP_NAME

echo "=========================================="
echo "Deployment complete!"
echo "Monitor at: https://dashboard.balena-cloud.com"
echo "=========================================="