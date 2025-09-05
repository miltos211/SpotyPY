import sys
import os
import json
import argparse
from dotenv import load_dotenv

# Add the `.lib` folder to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '.lib'))

from youtube.auth import get_youtube_client
from googleapiclient.errors import HttpError

# Import CLI utilities for standardized argument parsing
from utils.cli import create_standard_parser, add_common_arguments, COMMON_EPILOGS

# Initialize logger (will be configured in main())
logger = None

load_dotenv()

def print_privacy_menu():
    print("\n=== Playlist Privacy Options ===")
    print("1. private")
    print("2. unlisted")
    print("3. public")

def prompt_privacy_status():
    options = {
        "1": "private",
        "2": "unlisted",
        "3": "public",
        "private": "private",
        "unlisted": "unlisted",
        "public": "public"
    }
    while True:
        print_privacy_menu()
        choice = input("Choose privacy setting [1/2/3 or word]: ").strip().lower()
        if choice in options:
            return options[choice]
        print(" Invalid option. Try again.")

def create_playlist(youtube, title, privacy):
    logger.debug(f"YouTube API call: playlists().insert(title='{title}', privacy='{privacy}')")
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": "Exported from Spotify.",
                    "defaultLanguage": "en"
                },
                "status": {
                    "privacyStatus": privacy
                }
            }
        )
        response = request.execute()
        
        # Log API response details
        playlist_id = response["id"]
        logger.info(f"YouTube API success: playlist created with ID={playlist_id}")
        
        # Log quota usage if available in response headers
        if hasattr(request, '_http_response') and hasattr(request._http_response, 'headers'):
            headers = request._http_response.headers
            quota_cost = headers.get('X-Quota-Cost')
            quota_remaining = headers.get('X-RateLimit-Remaining')
            if quota_cost:
                logger.debug(f"YouTube API quota cost: {quota_cost} units")
            if quota_remaining:
                logger.info(f"YouTube API quota remaining: {quota_remaining} units")
        
        return playlist_id
        
    except HttpError as e:
        error_content = e.content.decode('utf-8') if e.content else 'No error details'
        logger.error(f"YouTube Data API error: HTTP {e.resp.status} - {error_content}")
        
        if e.resp.status == 403:
            if 'quotaExceeded' in error_content:
                logger.error("YouTube API quota exceeded - daily limit reached")
                logger.error("Wait 24 hours or increase quota limits in Google Cloud Console")
            elif 'insufficientPermissions' in error_content:
                logger.error("Insufficient YouTube permissions - check OAuth scopes")
            else:
                logger.error("YouTube API access forbidden - check authentication")
        elif e.resp.status == 401:
            logger.error("YouTube authentication failed - token may be expired")
        elif e.resp.status == 429:
            logger.warning("YouTube API rate limited - too many requests per second")
        
        raise Exception(f"YouTube playlist creation failed: HTTP {e.resp.status}")
        
    except Exception as e:
        logger.error(f"Unexpected error creating YouTube playlist: {type(e).__name__}: {e}")
        raise

def add_video_to_playlist(youtube, playlist_id, video_id):
    logger.debug(f"YouTube API call: playlistItems().insert(playlist={playlist_id}, video={video_id})")
    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        response = request.execute()
        
        # Log success with video details
        item_id = response.get("id", "unknown")
        logger.debug(f"YouTube API success: video {video_id} added to playlist (item_id={item_id})")
        
        # Log quota usage if available
        if hasattr(request, '_http_response') and hasattr(request._http_response, 'headers'):
            headers = request._http_response.headers
            quota_cost = headers.get('X-Quota-Cost')
            if quota_cost:
                logger.debug(f"YouTube API quota cost: {quota_cost} units")
        
        return response
        
    except HttpError as e:
        error_content = e.content.decode('utf-8') if e.content else 'No error details'
        logger.warning(f"YouTube API error adding video {video_id}: HTTP {e.resp.status} - {error_content}")
        
        if e.resp.status == 403:
            if 'quotaExceeded' in error_content:
                logger.error("YouTube API quota exceeded while adding videos")
            elif 'videoNotFound' in error_content:
                logger.warning(f"Video {video_id} not found or unavailable on YouTube")
            elif 'playlistItemsNotAccessible' in error_content:
                logger.error(f"Cannot add videos to playlist {playlist_id} - permission denied")
        elif e.resp.status == 404:
            logger.warning(f"Video {video_id} not found - may be private or deleted")
        elif e.resp.status == 429:
            logger.warning(f"Rate limited while adding video {video_id} - retrying may help")
            
        # Don't raise exception for individual video failures - let playlist creation continue
        logger.warning(f"Skipping video {video_id} due to API error")
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error adding video {video_id}: {type(e).__name__}: {e}")
        # Don't raise exception - let playlist creation continue
        return None

def parse_arguments():
    """Parse command line arguments"""
    epilog = COMMON_EPILOGS.get("uploader", '''
Examples:
  python yt_PushMK1.py                                           # Interactive mode
  python yt_PushMK1.py -i enriched.json -t "My Playlist"        # Create private playlist
  python yt_PushMK1.py -i enriched.json -t "Public Songs" --privacy public
  python yt_PushMK1.py --input enriched.json --title "My Mix" --privacy unlisted --debug
        ''').format(script="yt_PushMK1.py")
    
    parser = create_standard_parser(
        description='Create YouTube playlists from enriched JSON data',
        epilog=epilog
    )
    
    # Add common arguments (input, quiet, debug)
    add_common_arguments(parser, script_type="input")
    
    # Add script-specific arguments
    parser.add_argument('-t', '--title', type=str,
                        help='YouTube playlist title')
    
    parser.add_argument('-p', '--privacy', type=str, 
                        choices=['private', 'unlisted', 'public'],
                        default='private',
                        help='Playlist privacy setting (default: private)')
    
    return parser.parse_args()

def run_cli_mode(args):
    """Run in CLI mode with provided arguments"""
    # Validate input file
    if not os.path.isfile(args.input):
        logger.error(f"Input file not found: {args.input}")
        return False

    # Load enriched data
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return False

    # Extract YouTube video IDs
    video_ids = [
        entry["youtube"]["id"]["videoId"]
        for entry in data
        if entry.get("youtube") and entry["youtube"].get("id") and entry["youtube"]["id"].get("videoId")
    ]

    if not video_ids:
        logger.error("No valid video IDs found in the file.")
        return False

    logger.info(f"Found {len(video_ids)} videos to add to playlist")

    # Auth
    try:
        yt = get_youtube_client()
    except Exception as e:
        logger.error(f"YouTube authentication failed: {e}")
        return False

    # Create playlist
    try:
        playlist_id = create_playlist(yt, args.title, args.privacy)
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        logger.info(f"✓ Playlist created: {playlist_url}")
    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        return False

    # Push videos
    logger.info(f"Adding {len(video_ids)} videos to playlist...")
    push_count = 0
    failed_count = 0
    
    for i, video_id in enumerate(video_ids, 1):
        try:
            logger.info(f"[{i}/{len(video_ids)}] Adding: https://www.youtube.com/watch?v={video_id}")
            add_video_to_playlist(yt, playlist_id, video_id)
            push_count += 1
        except Exception as e:
            logger.warning(f"Failed to add video {video_id}: {e}")
            failed_count += 1

    print(f"\n=== Summary ===")
    print(f" Success: {push_count} videos added")
    if failed_count > 0:
        print(f" Failed: {failed_count} videos")
    print(f" Playlist URL: {playlist_url}")
    print(f" Total API queries: {1 + push_count}")  # 1 for create + N adds
    
    return True

def run_interactive_mode():
    """Run in interactive menu mode"""
    # Input file
    input_path = input("Enter path to enriched JSON file: ").strip()
    if not os.path.isfile(input_path):
        logger.error(" Input file not found.")
        return

    # Title + privacy
    playlist_title = input("Enter playlist title: ").strip()
    privacy_status = prompt_privacy_status()

    # Load enriched data
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract YouTube video IDs
    video_ids = [
        entry["youtube"]["id"]["videoId"]
        for entry in data
        if entry.get("youtube") and entry["youtube"].get("id") and entry["youtube"]["id"].get("videoId")
    ]

    if not video_ids:
        logger.error(" No valid video IDs found in the file.")
        return

    # Auth
    yt = get_youtube_client()

    # Create playlist
    playlist_id = create_playlist(yt, playlist_title, privacy_status)
    logger.info(f" Playlist created: https://www.youtube.com/playlist?list={playlist_id}")

    # Push videos
    logger.info("Adding videos to playlist...")
    logger.info(f"Adding videos to playlist...")
    push_count = 0
    for i, video_id in enumerate(video_ids, 1):
        logger.debug(f"PUSH {i}/{len(video_ids)} Adding video: https://www.youtube.com/watch?v={video_id}")
        logger.info(f"[{i}/{len(video_ids)}] Adding video: https://www.youtube.com/watch?v={video_id}")
        add_video_to_playlist(yt, playlist_id, video_id)
        push_count += 1

    logger.info(f" Done! {push_count} videos added.")
    logger.debug(f"Total YouTube API queries: {1 + push_count}")  # 1 for create + N adds

def main():
    global logger
    args = parse_arguments()
    
    # Initialize logger with configurable debug level
    from utils.logging import setup_logging, LoggerAdapter
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging("yt_push", level=log_level, quiet=args.quiet)
    logger = LoggerAdapter("yt_push")
    
    logger.info("YouTube Playlist Creator started")
    logger.debug(f"Arguments: {vars(args)}")
    
    try:
        # Check if CLI arguments were provided
        if args.input and args.title:
            # CLI mode
            logger.info("Running in CLI mode")
            success = run_cli_mode(args)
            logger.info(f"CLI mode completed: {'success' if success else 'failure'}")
            sys.exit(0 if success else 1)
        else:
            # Interactive mode (if missing required args for CLI)
            if args.input or args.title:
                logger.error("For CLI mode, both --input and --title are required")
                logger.error("ERROR: For CLI mode, both --input and --title are required")
                logger.info("Run without arguments for interactive mode")
                sys.exit(1)
            
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
