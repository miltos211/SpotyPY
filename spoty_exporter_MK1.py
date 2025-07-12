import sys
import os
import json
import argparse
from pathlib import Path

# Setup path to .lib/
sys.path.append(os.path.join(os.path.dirname(__file__), '.lib'))

# Import from namespaced spotify modules
from spotify.auth import get_authenticated_client
from spotify.playlists import get_user_playlists
from spotify.playlist_tracks import get_tracks_from_playlist
from spotify.utils import extract_playlist_id

# Import logging utilities
from utils.logging import create_logger

# Import path utilities
from utils.paths import PathValidator, validate_output_file

# Import CLI utilities
from utils.cli import create_standard_parser, COMMON_EPILOGS

# Initialize logger
logger = None

def print_menu():
    print("\n=== Spotify Playlist Exporter ===")
    print("1. Show all playlists")
    print("2. Export a playlist")
    print("0. Exit")

def find_playlist(input_str, playlists):
    input_str = input_str.strip().lower()

    # Check if it's an index
    if input_str.isdigit():
        idx = int(input_str)
        if 1 <= idx <= len(playlists):
            return playlists[idx - 1]["id"]

    # Try to extract ID from URL or raw ID
    id_from_url = extract_playlist_id(input_str)
    if id_from_url:
        return id_from_url

    # Try fuzzy name match
    for p in playlists:
        if input_str in p["name"].lower():
            return p["id"]

    return None

def parse_arguments():
    """Parse command line arguments"""
    epilog = COMMON_EPILOGS["exporter"].format(script="spoty_exporter_MK1.py")
    parser = create_standard_parser(
        description='Export Spotify playlists to JSON format',
        epilog=epilog
    )
    
    parser.add_argument('-l', '--list', action='store_true',
                        help='List all playlists and exit')
    
    parser.add_argument('-p', '--playlist', type=str,
                        help='Playlist name, index, ID, or URL to export')
    
    parser.add_argument('-o', '--output', type=str,
                        help='Output JSON file path (e.g., out/playlist.json)')
    
    parser.add_argument('--playlist-url', type=str,
                        help='Direct Spotify playlist URL')
    
    parser.add_argument('--playlist-id', type=str,
                        help='Direct Spotify playlist ID')
    
    return parser.parse_args()

def run_cli_mode(args):
    """Run in CLI mode with provided arguments"""
    logger.info("Starting CLI mode")
    
    try:
        sp = get_authenticated_client()
    except Exception as e:
        logger.error(f"Failed to authenticate with Spotify: {e}")
        return False
    
    # Get playlists for reference
    logger.debug("Fetching user playlists")
    result = get_user_playlists(sp)
    if result["status"] != 200:
        logger.error(f"Failed to fetch playlists: {result['error']}")
        return False
    
    playlists = result["playlists"]
    logger.debug(f"Found {result['count']} playlists")
    
    # List mode
    if args.list:
        logger.info(f"Listing {result['count']} playlists")
        print(f"You have {result['count']} playlists:\n")
        for i, pl in enumerate(playlists, 1):
            print(f"{i}. {pl['name']} ({pl['tracks']} tracks)")
        return True
    
    # Export mode - need both playlist and output
    if not args.output:
        logger.error("Output file (-o/--output) is required for export")
        return False
    
    # Validate output path
    is_valid, output_path, error = validate_output_file(args.output)
    if not is_valid:
        logger.error(f"Invalid output path: {error}")
        return False
    
    logger.debug(f"Validated output path: {output_path}")
    
    # Determine playlist ID
    playlist_id = None
    
    if args.playlist_id:
        playlist_id = args.playlist_id
        logger.debug(f"Using provided playlist ID: {playlist_id}")
    elif args.playlist_url:
        playlist_id = extract_playlist_id(args.playlist_url)
        if not playlist_id:
            logger.error("Could not extract playlist ID from URL")
            return False
        logger.debug(f"Extracted playlist ID from URL: {playlist_id}")
    elif args.playlist:
        playlist_id = find_playlist(args.playlist, playlists)
        if not playlist_id:
            logger.error(f"Playlist not found: {args.playlist}")
            return False
        logger.debug(f"Found playlist ID by search: {playlist_id}")
    else:
        logger.error("Must specify playlist (-p, --playlist-url, or --playlist-id)")
        return False
    
    # Export the playlist
    logger.info(f"Exporting playlist to {output_path}")
    result = get_tracks_from_playlist(sp, playlist_id, export_path=str(output_path))
    
    if result["status"] == 200:
        logger.success(f"Exported {len(result['tracks'])} tracks to {output_path}")
        return True
    else:
        logger.error(f"Failed to export: {result['error']}")
        return False

def run_interactive_mode():
    """Run in interactive menu mode"""
    logger.info("Starting interactive mode")
    
    try:
        sp = get_authenticated_client()
    except Exception as e:
        logger.error(f"Failed to authenticate with Spotify: {e}")
        print("ERROR: Failed to authenticate with Spotify")
        return

    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        logger.debug(f"User selected option: {choice}")

        if choice == "1":
            logger.debug("Fetching user playlists")
            result = get_user_playlists(sp)
            if result["status"] == 200:
                logger.info(f"Retrieved {result['count']} playlists")
                print(f"\n You have {result['count']} playlists:\n")
                for i, pl in enumerate(result["playlists"], 1):
                    print(f"{i}. {pl['name']} ({pl['tracks']} tracks)")
                playlists = result["playlists"]
            else:
                logger.error(f"Failed to fetch playlists: {result['error']}")
                print(" Failed to fetch playlists:", result["error"])

        elif choice == "2":
            if 'playlists' not in locals():
                logger.warning("User tried to export without fetching playlists first")
                print(" Please run option 1 first to fetch your playlists.")
                continue

            selection = input("Enter playlist name, URL, ID, or index: ").strip()
            logger.debug(f"User selected playlist: {selection}")
            playlist_id = find_playlist(selection, playlists)

            if not playlist_id:
                logger.warning(f"Playlist not found: {selection}")
                print(" Playlist not found.")
                continue

            output_file = input("Enter path to export JSON file (e.g. `out/playlist.json`): ").strip()
            
            # Validate output path
            is_valid, output_path, error = validate_output_file(output_file)
            if not is_valid:
                logger.error(f"Invalid output path: {error}")
                print(f" Error: {error}")
                continue
            
            logger.info(f"Exporting playlist {playlist_id} to {output_path}")
            result = get_tracks_from_playlist(sp, playlist_id, export_path=str(output_path))

            if result["status"] == 200:
                logger.success(f"Exported {len(result['tracks'])} tracks to {output_path}")
                print(f" Exported {len(result['tracks'])} tracks to {output_path}")
            else:
                logger.error(f"Failed to export: {result['error']}")
                print(" Failed to export:", result["error"])

        elif choice == "0":
            logger.info("User chose to exit")
            print(" Goodbye!")
            break
        else:
            logger.debug(f"Invalid option selected: {choice}")
            print(" Invalid option. Try again.")

def main():
    global logger
    args = parse_arguments()
    
    # Initialize logger based on CLI arguments
    quiet = hasattr(args, 'quiet') and args.quiet  # Add quiet support if needed
    logger = create_logger("spoty_exporter", quiet=quiet)
    
    logger.debug("Application started")
    logger.debug(f"Arguments: {vars(args)}")
    
    try:
        # Check if any CLI arguments were provided
        if args.list or args.playlist or args.playlist_url or args.playlist_id or args.output:
            # CLI mode
            logger.info("Running in CLI mode")
            success = run_cli_mode(args)
            logger.info(f"CLI mode completed with status: {'success' if success else 'failure'}")
            sys.exit(0 if success else 1)
        else:
            # Interactive mode
            logger.info("Running in interactive mode")
            run_interactive_mode()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
