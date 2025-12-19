#!/bin/bash
#
# Clean Test Data Script
# Safely removes test data files (images, videos, CSVs, databases) from Pi SD card
# while preserving core software files and configuration
#
# Usage: ./clean_test_data.sh [--dry-run] [--confirm]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
DRY_RUN=false
SKIP_CONFIRM=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --confirm)
            SKIP_CONFIRM=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--dry-run] [--confirm]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be deleted without actually deleting"
            echo "  --confirm    Skip confirmation prompt"
            echo "  --help       Show this help message"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Data Cleanup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Data directories to clean
DATA_DIRS=(
    "/data/images"
    "/data/videos"
    "/data/temperature"
    "/data/buffer"
    "/data/thermal_images"
)

# Database files to clean
DB_FILES=(
    "/data/buffer/readings.db"
    "/data/buffer/readings.db-journal"
)

# Log files to clean (optional)
LOG_DIRS=(
    "/var/log/transformer-monitor"
)

# Function to get directory size
get_dir_size() {
    local dir=$1
    if [ -d "$dir" ]; then
        du -sh "$dir" 2>/dev/null | cut -f1
    else
        echo "N/A"
    fi
}

# Function to count files
count_files() {
    local dir=$1
    if [ -d "$dir" ]; then
        find "$dir" -type f 2>/dev/null | wc -l
    else
        echo "0"
    fi
}

# Show what will be cleaned
echo -e "${YELLOW}The following data will be cleaned:${NC}"
echo ""

total_size=0
total_files=0

for dir in "${DATA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        size=$(get_dir_size "$dir")
        files=$(count_files "$dir")
        echo -e "  📁 $dir"
        echo -e "     Size: ${GREEN}$size${NC}, Files: ${GREEN}$files${NC}"
        total_files=$((total_files + files))
    else
        echo -e "  📁 $dir ${YELLOW}(not found)${NC}"
    fi
done

echo ""
echo -e "${YELLOW}Database files:${NC}"
for db in "${DB_FILES[@]}"; do
    if [ -f "$db" ]; then
        size=$(du -sh "$db" 2>/dev/null | cut -f1)
        echo -e "  🗄️  $db (${GREEN}$size${NC})"
    fi
done

echo ""
echo -e "${BLUE}Total files to delete: ${GREEN}$total_files${NC}"
echo ""

# Safety checks
echo -e "${YELLOW}Safety Checks:${NC}"
echo -e "  ✓ Core software directory (/home/smartie/transformer-monitor) will NOT be touched"
echo -e "  ✓ Configuration files will NOT be deleted"
echo -e "  ✓ Python code will NOT be deleted"
echo -e "  ✓ Only data files in /data/ will be removed"
echo ""

# Confirmation
if [ "$SKIP_CONFIRM" = false ] && [ "$DRY_RUN" = false ]; then
    echo -e "${RED}WARNING: This will permanently delete all test data!${NC}"
    echo -e "${YELLOW}Are you sure you want to continue? (yes/no)${NC}"
    read -r response
    if [ "$response" != "yes" ]; then
        echo -e "${YELLOW}Cleanup cancelled.${NC}"
        exit 0
    fi
fi

# Dry run mode
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}DRY RUN MODE - No files will be deleted${NC}"
    echo ""
fi

# Start cleanup
echo ""
echo -e "${GREEN}Starting cleanup...${NC}"
echo ""

# Clean data directories
for dir in "${DATA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "Cleaning ${BLUE}$dir${NC}..."
        
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY RUN] Would delete all files in $dir"
        else
            # Delete all files but keep directory structure
            find "$dir" -type f -delete 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} Files deleted"
            
            # Remove empty subdirectories
            find "$dir" -type d -empty -delete 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} Empty directories removed"
        fi
    fi
done

# Clean database files
echo ""
echo -e "Cleaning database files..."
for db in "${DB_FILES[@]}"; do
    if [ -f "$db" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY RUN] Would delete $db"
        else
            rm -f "$db"
            echo -e "  ${GREEN}✓${NC} Deleted $db"
        fi
    fi
done

# Optional: Clean logs
echo ""
echo -e "${YELLOW}Clean log files? (yes/no)${NC}"
if [ "$SKIP_CONFIRM" = false ]; then
    read -r clean_logs
else
    clean_logs="no"
fi

if [ "$clean_logs" = "yes" ]; then
    for log_dir in "${LOG_DIRS[@]}"; do
        if [ -d "$log_dir" ]; then
            echo -e "Cleaning ${BLUE}$log_dir${NC}..."
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY RUN] Would delete logs in $log_dir"
            else
                find "$log_dir" -type f -name "*.log*" -delete 2>/dev/null || true
                echo -e "  ${GREEN}✓${NC} Log files deleted"
            fi
        fi
    done
fi

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$DRY_RUN" = false ]; then
    echo -e "${GREEN}✓ Test data has been cleaned${NC}"
    echo -e "${GREEN}✓ Core software is intact${NC}"
    echo -e "${GREEN}✓ Ready for production deployment${NC}"
    echo ""
    echo -e "${YELLOW}Note: The service will recreate necessary directories on next run${NC}"
else
    echo -e "${BLUE}This was a dry run. No files were actually deleted.${NC}"
    echo -e "${YELLOW}Run without --dry-run to perform actual cleanup.${NC}"
fi

echo ""
echo -e "${BLUE}Disk space freed:${NC}"
df -h /data 2>/dev/null || df -h / | grep -v "Filesystem"

echo ""
