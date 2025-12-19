#!/bin/bash
# Fix merge conflicts on Pi 5 by pulling clean version from remote

set -e  # Exit on error

echo "=========================================="
echo "Fixing Merge Conflicts on Pi 5"
echo "=========================================="

# Navigate to project directory
cd ~/transformer-monitor

echo ""
echo "Current git status:"
git status

echo ""
echo "Checking for merge conflict markers..."
if grep -r "<<<<<<< HEAD" src/ config/ 2>/dev/null; then
    echo ""
    echo "⚠️  Found merge conflict markers!"
    echo ""
    
    # Show which files have conflicts
    echo "Files with conflicts:"
    grep -l "<<<<<<< HEAD" src/*.py config/*.py 2>/dev/null || true
    
    echo ""
    echo "Fetching latest from origin..."
    git fetch origin
    
    echo ""
    echo "Resetting to clean stable-deployment branch..."
    git reset --hard origin/stable-deployment
    
    echo ""
    echo "✅ Merge conflicts resolved!"
else
    echo "✅ No merge conflict markers found"
fi

echo ""
echo "Verifying Python syntax..."
python3 -m py_compile src/camera_web_interface.py && echo "✅ camera_web_interface.py - OK" || echo "❌ camera_web_interface.py - SYNTAX ERROR"
python3 -m py_compile src/main.py && echo "✅ main.py - OK" || echo "❌ main.py - SYNTAX ERROR"

echo ""
echo "Restarting transformer-monitor service..."
sudo systemctl restart transformer-monitor

echo ""
echo "Waiting 5 seconds for service to start..."
sleep 5

echo ""
echo "Service status:"
sudo systemctl status transformer-monitor --no-pager -l

echo ""
echo "Recent logs:"
sudo journalctl -u transformer-monitor -n 20 --no-pager

echo ""
echo "=========================================="
echo "Done! Check the logs above for any errors."
echo "=========================================="
