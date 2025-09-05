#!/bin/bash
"""
Resume Download Helper for SpotifyToYT

This script automates the resume process:
1. Syncs JSON with existing MP3 files
2. Runs yt_FetchMK1.py to download missing tracks
3. Provides summary report

Usage:
    .debug/resume_download.sh <enriched_json> <songs_dir> [threads]

Examples:
    .debug/resume_download.sh out/playlist_enriched.json songs/ 3
    .debug/resume_download.sh out/liked_songs_enriched.json songs/liked_songs_05-09-25/
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m' 
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <enriched_json> <songs_dir> [threads]"
    echo ""
    echo "Examples:"
    echo "  $0 out/playlist_enriched.json songs/ 3"
    echo "  $0 out/liked_songs_enriched.json songs/liked_songs_05-09-25/"
    exit 1
fi

ENRICHED_JSON="$1"
SONGS_DIR="$2"
THREADS="${3:-3}"  # Default to 3 threads

# Validate inputs
if [ ! -f "$ENRICHED_JSON" ]; then
    print_color $RED "JSON file not found: $ENRICHED_JSON"
    exit 1
fi

if [ ! -d "$SONGS_DIR" ]; then
    print_color $RED "Songs directory not found: $SONGS_DIR"
    exit 1
fi

print_color $BLUE "SpotifyToYT Resume Download Helper"
echo "=" "$(printf '%*s' 40 '' | tr ' ' '=')"
print_color $BLUE "JSON: $ENRICHED_JSON"
print_color $BLUE "Songs: $SONGS_DIR" 
print_color $BLUE "Threads: $THREADS"
echo ""

# Step 1: Sync JSON with existing files
print_color $YELLOW "Step 1: Syncing JSON with existing MP3 files..."
python .debug/json_sync_batch.py "$ENRICHED_JSON" "$SONGS_DIR"
sync_result=$?

if [ $sync_result -eq 2 ]; then
    print_color $RED "Sync failed with error"
    exit 1
elif [ $sync_result -eq 0 ]; then
    print_color $GREEN "All tracks already downloaded - nothing to resume!"
    exit 0
fi

# Step 2: Resume download
print_color $YELLOW "Step 2: Resuming download for missing tracks..."
echo ""

python yt_FetchMK1.py -i "$ENRICHED_JSON" -o "$SONGS_DIR" -t "$THREADS"
download_result=$?

# Step 3: Final sync check
print_color $YELLOW "Step 3: Final verification..."
python .debug/json_sync_batch.py "$ENRICHED_JSON" "$SONGS_DIR" --dry-run
final_result=$?

# Summary
echo ""
print_color $BLUE "RESUME SUMMARY"
echo "=" "$(printf '%*s' 40 '' | tr ' ' '=')"

if [ $final_result -eq 0 ]; then
    print_color $GREEN "Resume completed successfully! All tracks downloaded."
elif [ $final_result -eq 1 ]; then
    print_color $YELLOW "Some tracks still missing. You may need to:"
    echo "   - Check logs for specific errors"
    echo "   - Run the resume script again"
    echo "   - Try with fewer threads if bot detection is active"
else
    print_color $RED "Verification failed"
fi

exit $final_result