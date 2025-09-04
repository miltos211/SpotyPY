#!/bin/bash

# SpotifyToYT Pipeline Script
# Usage: ./start.sh [playlist_name_or_url] [--debug]

set -e  # Exit on any error

# Check for debug flag
DEBUG_MODE=false
if [[ "$*" == *"--debug"* ]]; then
    DEBUG_MODE=true
    # Remove --debug from arguments
    set -- "${@/--debug}"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to clean filename for file system
clean_filename() {
    echo "$1" | sed 's/[<>:"/\\|?*]/_/g' | sed 's/ /_/g' | sed 's/__*/_/g' | sed 's/_$//' | sed 's/^_//'
}

# Function to get logging flags based on debug mode
get_log_flags() {
    if [[ "$DEBUG_MODE" == true ]]; then
        echo "--debug"
    else
        echo "--quiet"
    fi
}

# Check if Python environment is available
check_python() {
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
    fi
    
    # Check if required packages are available
    if ! python -c "import spotipy, ytmusicapi, yt_dlp, mutagen" &> /dev/null; then
        print_error "Required packages not installed. Run: pip install -r requirements.txt"
    fi
}

# Create necessary directories
setup_directories() {
    print_step "Setting up directories..."
    mkdir -p out
    mkdir -p songs
    mkdir -p logs
    print_success "Directories created"
}

# Step 1: Export Spotify playlist
export_spotify_playlist() {
    local playlist_input="$1"
    local playlist_name="$2"
    
    print_step "Step 1: Exporting Spotify playlist..."
    
    local json_file="out/${playlist_name}.json"
    
    local log_flags=$(get_log_flags)
    
    if [[ "$playlist_input" == http* ]]; then
        # URL provided
        python spoty_exporter_MK1.py --playlist-url "$playlist_input" -o "$json_file" $log_flags
    elif [[ "$playlist_input" =~ ^[0-9]+$ ]]; then
        # Number provided (playlist index)
        python spoty_exporter_MK1.py -p "$playlist_input" -o "$json_file" $log_flags
    else
        # Playlist name provided
        python spoty_exporter_MK1.py -p "$playlist_input" -o "$json_file" $log_flags
    fi
    
    if [[ $? -eq 0 && -f "$json_file" ]]; then
        print_success "Spotify playlist exported to $json_file"
        export SPOTIFY_JSON="$json_file"
    else
        print_error "Failed to export Spotify playlist"
    fi
}

# Step 2: Search YouTube Music matches
search_youtube_matches() {
    local playlist_name="$1"
    
    print_step "Step 2: Searching YouTube Music matches..."
    
    local input_file="$SPOTIFY_JSON"
    local output_file="out/${playlist_name}-enriched.json"
    
    # Use threading for faster processing
    local log_flags=$(get_log_flags)
    python yt_searchtMK1.py -i "$input_file" -o "$output_file" -t 3 $log_flags
    
    if [[ $? -eq 0 && -f "$output_file" ]]; then
        print_success "YouTube matches found and saved to $output_file"
        export ENRICHED_JSON="$output_file"
    else
        print_error "Failed to find YouTube matches"
    fi
}

# Step 3: Download audio files
download_audio_files() {
    local playlist_name="$1"
    
    print_step "Step 3: Downloading audio files..."
    
    local input_file="$ENRICHED_JSON"
    local output_dir="songs/${playlist_name}"
    
    # Create playlist-specific directory
    mkdir -p "$output_dir"
    
    # Use threading for faster downloads
    local log_flags=$(get_log_flags)
    python yt_FetchMK1.py -i "$input_file" -o "$output_dir" -t 3 $log_flags
    
    if [[ $? -eq 0 ]]; then
        print_success "Audio files downloaded to $output_dir"
        export SONGS_DIR="$output_dir"
    else
        print_error "Failed to download audio files"
    fi
}

# Step 4: Create YouTube playlist (optional)
create_youtube_playlist() {
    local playlist_name="$1"
    
    print_step "Step 4: Creating YouTube playlist (optional)..."
    
    read -p "Do you want to create a YouTube playlist? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        local input_file="$ENRICHED_JSON"
        local log_flags=$(get_log_flags)
        python yt_PushMK1.py -i "$input_file" -t "$playlist_name" -p "private" $log_flags
        
        if [[ $? -eq 0 ]]; then
            print_success "YouTube playlist created successfully"
        else
            print_warning "Failed to create YouTube playlist (this is optional)"
        fi
    else
        print_step "Skipping YouTube playlist creation"
    fi
}

# Main function
main() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "    SpotifyToYT Pipeline Script"
    if [[ "$DEBUG_MODE" == true ]]; then
        echo "         DEBUG MODE ENABLED"
    fi
    echo "=========================================="
    echo -e "${NC}"
    
    # Check if playlist argument provided
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 [playlist_name_or_url_or_index] [--debug]"
        echo ""
        echo "Examples:"
        echo "  $0 \"My Awesome Playlist\"                   # Normal operation (INFO level)"
        echo "  $0 \"My Awesome Playlist\" --debug           # Debug mode (detailed logging)"
        echo "  $0 \"https://open.spotify.com/playlist/...\"  # From Spotify URL"
        echo "  $0 1 --debug                                # By playlist index with debug"
        echo ""
        echo "Or run without arguments to list playlists first:"
        python spoty_exporter_MK1.py -l
        echo ""
        read -p "Enter playlist name, URL, or index: " playlist_input
    else
        playlist_input="$1"
    fi
    
    # Check prerequisites
    check_python
    setup_directories
    
    # Generate clean playlist name for file system
    if [[ "$playlist_input" == http* ]]; then
        # For URLs, we'll get the name after export
        playlist_name="playlist_$(date +%Y%m%d_%H%M%S)"
    elif [[ "$playlist_input" =~ ^[0-9]+$ ]]; then
        # For indices, get the actual playlist name first
        print_step "Getting playlist name for index $playlist_input..."
        actual_name=$(python spoty_exporter_MK1.py -l 2>/dev/null | grep "^$playlist_input\." | sed "s/^$playlist_input\. //" | sed 's/ ([0-9]* tracks)$//')
        if [[ -n "$actual_name" ]]; then
            playlist_name=$(clean_filename "$actual_name")
            print_step "Found playlist: $actual_name"
        else
            playlist_name="playlist_$(date +%Y%m%d_%H%M%S)"
        fi
    else
        # For names, clean it up
        playlist_name=$(clean_filename "$playlist_input")
    fi
    
    # Run the pipeline
    export_spotify_playlist "$playlist_input" "$playlist_name"
    
    # No need for post-export name extraction anymore - we get it upfront
    print_step "Using playlist name: $playlist_name"
    
    search_youtube_matches "$playlist_name"
    download_audio_files "$playlist_name"
    create_youtube_playlist "$playlist_name"
    
    # Final summary
    echo -e "${GREEN}"
    echo "=========================================="
    echo "           Pipeline Complete!"
    echo "=========================================="
    echo -e "${NC}"
    echo "Files created:"
    echo "  Spotify JSON: $SPOTIFY_JSON"
    echo "  Enriched JSON: $ENRICHED_JSON"
    echo "  Songs folder: $SONGS_DIR"
    echo ""
    echo "Total songs downloaded: $(find "$SONGS_DIR" -name "*.mp3" | wc -l)"
    echo ""
    print_success "Pipeline completed successfully!"
}

# Run main function with all arguments
main "$@"
