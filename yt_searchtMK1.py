import sys
import os
import json
import time
import subprocess
import threading
import argparse
from pathlib import Path
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# Setup path to .lib/
sys.path.append(os.path.join(os.path.dirname(__file__), '.lib'))

try:
    from ytmusicapi import YTMusic, OAuthCredentials
except ImportError:
    print("ERROR: ytmusicapi not found. Install with: pip install ytmusicapi")
    sys.exit(1)

# Import logging utilities
from utils.logging import thread_safe_print  # setup_logging and LoggerAdapter imported in main()

# Import path utilities
from utils.paths import PathValidator, validate_input_file, validate_output_file

# Import CLI utilities
from utils.cli import add_common_arguments, validate_thread_count, create_standard_parser, COMMON_EPILOGS

# Thread-safe print lock (keep for compatibility)
print_lock = threading.Lock()

# Rate limiting for YouTube Music API
rate_limit_lock = threading.Lock()
last_request_time = 0

# Initialize logger
logger = None

# Remove duplicate thread_safe_print - use the one from utils.logging

def rate_limited_request(func, *args, **kwargs):
    """Execute a function with rate limiting"""
    global last_request_time
    
    with rate_limit_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time
        
        # Ensure minimum 0.1 second delay between requests
        if time_since_last < 0.1:
            time.sleep(0.1 - time_since_last)
        
        last_request_time = time.time()
    
    return func(*args, **kwargs)

def setup_oauth() -> Optional[YTMusic]:
    """Setup OAuth authentication for YouTube Music"""
    oauth_file = "oauth.json"
    
    # Check if oauth.json already exists
    if os.path.exists(oauth_file):
        print(f"Found existing {oauth_file}, attempting to use it...")
        try:
            yt = YTMusic(oauth_file)
            # Test the connection
            yt.get_home()
            print("OAuth authentication successful.")
            return yt
        except Exception as e:
            print(f"Existing OAuth file failed: {e}")
            print("Will create new OAuth credentials...")
    
    # Run ytmusicapi oauth command
    print("\nRunning OAuth setup...")
    print("This will open a browser window for YouTube Music authentication.")
    
    try:
        # Run ytmusicapi oauth command
        result = subprocess.run([
            sys.executable, "-m", "ytmusicapi", "oauth"
        ], cwd=os.getcwd(), timeout=300)
        
        if result.returncode == 0:
            print("OAuth setup completed.")
            
            # Check if oauth.json was created
            if os.path.exists(oauth_file):
                try:
                    yt = YTMusic(oauth_file)
                    yt.get_home()
                    print("OAuth authentication verified.")
                    return yt
                except Exception as e:
                    print(f"OAuth verification failed: {e}")
            else:
                print("OAuth file not found after setup.")
        else:
            print("OAuth setup command failed.")
            
    except subprocess.TimeoutExpired:
        print("OAuth setup timed out. Please try again.")
    except Exception as e:
        print(f"Failed to run OAuth setup: {e}")
    
    # Try browser headers as fallback
    headers_file = "headers_auth.json"
    if os.path.exists(headers_file):
        print(f"\nFound {headers_file}, trying browser headers authentication...")
        try:
            yt = YTMusic(headers_file)
            yt.get_home()
            print("Browser headers authentication successful.")
            return yt
        except Exception as e:
            print(f"Browser headers authentication failed: {e}")
    
    # Try unauthenticated access as last resort
    print("\nTrying unauthenticated access (limited functionality)...")
    try:
        yt = YTMusic()
        # Test with a simple search
        test_results = yt.search("test", limit=1)
        print("Unauthenticated access working.")
        return yt
    except Exception as e:
        print(f"Unauthenticated access failed: {e}")
        
    print("\nManual setup required:")
    print("1. Run: ytmusicapi oauth")
    print("2. Or run: ytmusicapi browser")
    print("3. Then re-run this script")
    return None

def setup_ytmusic() -> Optional[YTMusic]:
    """Setup YouTube Music API client with OAuth"""
    return setup_oauth()

def create_youtube_metadata(yt_result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ytmusicapi result to match original YouTube API format"""
    
    # Extract video ID from different possible formats
    video_id = None
    if isinstance(yt_result.get('videoId'), str):
        video_id = yt_result['videoId']
    elif isinstance(yt_result.get('id'), str):
        video_id = yt_result['id']
    
    if not video_id:
        return None
    
    # Get thumbnails - ytmusicapi format
    thumbnails = {}
    if 'thumbnails' in yt_result and yt_result['thumbnails']:
        thumb_list = yt_result['thumbnails']
        if len(thumb_list) >= 1:
            thumbnails['default'] = {
                'url': thumb_list[0]['url'],
                'width': thumb_list[0].get('width', 120),
                'height': thumb_list[0].get('height', 90)
            }
        if len(thumb_list) >= 2:
            thumbnails['medium'] = {
                'url': thumb_list[1]['url'],
                'width': thumb_list[1].get('width', 320),
                'height': thumb_list[1].get('height', 180)
            }
        if len(thumb_list) >= 3:
            thumbnails['high'] = {
                'url': thumb_list[2]['url'], 
                'width': thumb_list[2].get('width', 480),
                'height': thumb_list[2].get('height', 360)
            }
    
    # Create YouTube API compatible structure
    youtube_data = {
        "kind": "youtube#searchResult",
        "etag": f"ytmusic_{video_id}",  # Fake etag
        "id": {
            "kind": "youtube#video", 
            "videoId": video_id
        },
        "snippet": {
            "publishedAt": "2024-01-01T00:00:00Z",  # Default date
            "channelId": yt_result.get('artists', [{}])[0].get('id', 'unknown'),
            "title": yt_result.get('title', 'Unknown Title'),
            "description": f"Provided by YouTube Music API - {yt_result.get('title', '')}",
            "thumbnails": thumbnails,
            "channelTitle": f"{yt_result.get('artists', [{}])[0].get('name', 'Unknown')} - Topic",
            "liveBroadcastContent": "none",
            "publishTime": "2024-01-01T00:00:00Z"
        }
    }
    
    return youtube_data

def search_youtube_music(yt: YTMusic, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search YouTube Music for a query (thread-safe with rate limiting)"""
    try:
        logger.debug(f"Searching YouTube Music: '{query}'")
        
        # Search with filter for songs (more accurate than videos) - rate limited
        results = rate_limited_request(yt.search, query, filter="songs", limit=max_results)
        
        if not results:
            # Fallback to general search if no songs found - rate limited
            logger.debug(f"No songs found for '{query}', trying general search")
            results = rate_limited_request(yt.search, query, limit=max_results)
        
        logger.debug(f"Found {len(results)} results for '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return []

def build_search_query(track: Dict[str, Any]) -> str:
    """Build search query from Spotify track data"""
    name = track.get('name', '')
    artists = track.get('artists', [])
    
    if not name:
        return ""
    
    # Clean up track name (remove common suffixes that might hurt search)
    clean_name = name
    suffixes_to_remove = [
        " - Remaster", " - 2005 Remaster", " - Remix", " - Radio Version",
        " - Original Version", " - LP Mix", " - Extended Version"
    ]
    
    for suffix in suffixes_to_remove:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)]
            break
    
    # Build query: "Artist Song"
    if artists and len(artists) > 0:
        primary_artist = artists[0]
        query = f"{primary_artist} {clean_name}"
    else:
        query = clean_name
    
    return query.strip()

def enrich_track_with_youtube(yt: YTMusic, track: Dict[str, Any], index: int, total: int) -> Dict[str, Any]:
    """Enrich a single track with YouTube data (thread-safe)"""
    
    thread_safe_print(f"[{index}/{total}] {track.get('name', 'Unknown')} by {', '.join(track.get('artists', ['Unknown']))}")
    
    # Build search query
    query = build_search_query(track)
    if not query:
        thread_safe_print(f"    Could not build search query")
        return {
            "spotify": track,
            "youtube": None
        }
    
    # Search YouTube Music
    search_results = search_youtube_music(yt, query, max_results=3)
    
    if not search_results:
        thread_safe_print(f"    No results found")
        return {
            "spotify": track,
            "youtube": None
        }
    
    # Take the first (best) result
    best_result = search_results[0]
    
    # Convert to YouTube API format
    youtube_metadata = create_youtube_metadata(best_result)
    
    if youtube_metadata:
        video_id = youtube_metadata["id"]["videoId"]
        thread_safe_print(f"    Found: {best_result.get('title')} (ID: {video_id})")
        
        return {
            "spotify": track,
            "youtube": youtube_metadata
        }
    else:
        thread_safe_print(f"    Failed to process result")
        return {
            "spotify": track,
            "youtube": None
        }

def enrich_track_worker(args):
    """Worker function for threading - processes a single track"""
    yt, track, index, total = args
    return enrich_track_with_youtube(yt, track, index, total)

def enrich_tracks_with_youtube_music_threaded(tracks: List[Dict[str, Any]], yt: YTMusic, max_workers: int = 3) -> List[Dict[str, Any]]:
    """Enrich all tracks with YouTube Music data using multithreading"""
    
    total = len(tracks)
    thread_safe_print(f"\nProcessing {total} tracks with {max_workers} concurrent threads...\n")
    
    # Prepare worker arguments
    worker_args = [(yt, track, i+1, total) for i, track in enumerate(tracks)]
    
    # Results dictionary to maintain order
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {executor.submit(enrich_track_worker, args): args[2] 
                          for args in worker_args}
        
        # Process completed tasks
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
                results[index] = result
            except Exception as e:
                thread_safe_print(f"Exception processing track {index}: {e}")
                # Create a failed result
                results[index] = {
                    "spotify": tracks[index-1],
                    "youtube": None
                }
    
    # Convert results dict back to ordered list
    enriched_tracks = [results[i] for i in range(1, total + 1)]
    
    return enriched_tracks

def enrich_tracks_with_youtube_music_sequential(tracks: List[Dict[str, Any]], yt: YTMusic, verbose: bool = True) -> List[Dict[str, Any]]:
    """Enrich all tracks with YouTube Music data sequentially (original method)"""
    
    enriched_tracks = []
    total = len(tracks)
    
    for i, track in enumerate(tracks, 1):
        enriched_track = enrich_track_with_youtube(yt, track, i, total)
        enriched_tracks.append(enriched_track)
        
        # Small delay to be respectful to the service
        if i < total:
            time.sleep(0.1)
    
    return enriched_tracks

def enrich_tracks_with_youtube_music(tracks: List[Dict[str, Any]], yt: YTMusic, verbose: bool = True) -> List[Dict[str, Any]]:
    """Enrich all tracks with YouTube Music data (backwards compatibility)"""
    return enrich_tracks_with_youtube_music_sequential(tracks, yt, verbose)

def print_summary(enriched_tracks: List[Dict[str, Any]]):
    """Print summary statistics"""
    total = len(enriched_tracks)
    found = sum(1 for track in enriched_tracks if track.get('youtube') is not None)
    missing = total - found
    
    print(f"\nSummary:")
    print(f"  Found YouTube matches: {found}")
    print(f"  No matches found: {missing}")
    print(f"  Success rate: {(found/total*100):.1f}%")

def print_menu():
    """Print menu options"""
    print("\n=== YouTube Music Search & Enrichment ===")
    print("1. Process with multithreading (faster)")
    print("2. Process sequentially (original method)")
    print("0. Exit")

def prompt_thread_count():
    """Ask user for number of threads to use"""
    while True:
        try:
            count = input("Number of concurrent searches (1-8, default 3): ").strip()
            if not count:
                return 3
            count = int(count)
            if 1 <= count <= 8:
                return count
            print(" Please enter a number between 1 and 8.")
        except ValueError:
            print(" Please enter a valid number.")

def parse_arguments():
    """Parse command line arguments"""
    epilog = COMMON_EPILOGS["processor"].format(script="yt_searchtMK1.py")
    parser = create_standard_parser(
        description='Search YouTube Music for Spotify tracks and create enriched JSON',
        epilog=epilog
    )
    
    # Add common arguments (input, output, threads, quiet, debug)
    add_common_arguments(parser, script_type="io")
    
    return parser.parse_args()

def run_cli_mode(args):
    """Run in CLI mode with provided arguments"""
    # Validate input file
    is_valid, input_path, error = validate_input_file(args.input, extensions=['.json'])
    if not is_valid:
        logger.error(f"Invalid input file: {error}")
        return False
    
    logger.debug(f"Validated input file: {input_path}")
    
    # Load Spotify tracks
    try:
        with input_path.open("r", encoding="utf-8") as f:
            all_tracks = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return False
    
    if len(all_tracks) == 0:
        logger.error("No tracks found in the input file")
        return False
    
    logger.info(f"Loaded {len(all_tracks)} tracks from {input_path}")
    
    # Setup YouTube Music API
    yt = setup_ytmusic()
    if not yt:
        return False
    
    # Determine and validate output path
    if args.output:
        is_valid, output_path, error = validate_output_file(args.output)
        if not is_valid:
            logger.error(f"Invalid output file: {error}")
            return False
    else:
        # Default to enriched_output.json in same directory as input
        default_output = input_path.parent / "enriched_output.json"
        is_valid, output_path, error = validate_output_file(default_output)
        if not is_valid:
            logger.error(f"Cannot create default output file: {error}")
            return False
    
    logger.debug(f"Validated output path: {output_path}")
    
    # Validate thread count
    thread_count = args.threads
    is_valid, error = validate_thread_count(thread_count, max_threads=8)
    if not is_valid:
        print(f"ERROR: {error}")
        return False
    
    # Process tracks
    start_time = time.time()
    
    if thread_count == 0:
        print(f"Starting YouTube Music enrichment for {len(all_tracks)} tracks sequentially...")
        enriched_tracks = enrich_tracks_with_youtube_music_sequential(all_tracks, yt, verbose=not args.quiet)
    else:
        print(f"Starting YouTube Music enrichment for {len(all_tracks)} tracks with {thread_count} threads...")
        enriched_tracks = enrich_tracks_with_youtube_music_threaded(all_tracks, yt, thread_count)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Save enriched data
    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(enriched_tracks, f, ensure_ascii=False, indent=2)
        
        print_summary(enriched_tracks)
        print(f"\nProcessing completed in {duration:.2f} seconds")
        print(f"Saved enriched data to: {output_path}")
        print(f"Ready for use with yt_FetchMK1.py!")
        logger.info(f"Successfully saved {len(enriched_tracks)} enriched tracks to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save output: {e}")
        return False

def run_interactive_mode():
    """Run in interactive menu mode"""
    while True:
        print_menu()
        choice = input("Choose processing method: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
        elif choice not in ["1", "2"]:
            print("Invalid option. Try again.")
            continue
        
        # Get input file
        filepath = input("Enter path to Spotify JSON file: ").strip()
        
        if not os.path.isfile(filepath):
            print("ERROR: File not found.")
            continue
        
        # Load Spotify tracks
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                all_tracks = json.load(f)
        except Exception as e:
            print(f"ERROR: Failed to load JSON: {e}")
            continue
        
        if len(all_tracks) == 0:
            print("ERROR: No tracks found in the input.")
            continue
        
        print(f"Loaded {len(all_tracks)} tracks from {filepath}")
        
        # Setup YouTube Music API
        yt = setup_ytmusic()
        if not yt:
            continue
        
        # Get threading option for choice 1
        if choice == "1":
            thread_count = prompt_thread_count()
            print(f"\nStarting YouTube Music enrichment for {len(all_tracks)} tracks with {thread_count} threads...\n")
        else:
            print(f"\nStarting YouTube Music enrichment for {len(all_tracks)} tracks sequentially...\n")
        
        # Record start time
        start_time = time.time()
        
        # Enrich tracks based on choice
        if choice == "1":
            enriched_tracks = enrich_tracks_with_youtube_music_threaded(all_tracks, yt, thread_count)
        else:
            enriched_tracks = enrich_tracks_with_youtube_music_sequential(all_tracks, yt, verbose=True)
        
        # Record end time
        end_time = time.time()
        duration = end_time - start_time
        
        # Output file path (same directory as input)
        output_path = os.path.join(os.path.dirname(filepath), "enriched_output.json")
        
        # Save enriched data
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(enriched_tracks, f, ensure_ascii=False, indent=2)
            
            print_summary(enriched_tracks)
            print(f"\nProcessing completed in {duration:.2f} seconds")
            print(f"Saved enriched data to: {output_path}")
            print(f"Ready for use with yt_FetchMK1.py!")
            
        except Exception as e:
            print(f"ERROR: Failed to save output: {e}")
        
        # Ask if user wants to process another file
        another = input("\nProcess another file? (y/n): ").strip().lower()
        if another not in ['y', 'yes']:
            break

def main():
    global logger
    args = parse_arguments()
    
    # Initialize logger with configurable debug level
    from utils.logging import setup_logging, LoggerAdapter
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging("yt_search", level=log_level, quiet=args.quiet)
    logger = LoggerAdapter("yt_search")
    
    logger.info("YouTube Music Search & Enrichment started")
    logger.debug(f"Arguments: {vars(args)}")
    
    try:
        # Check if CLI arguments were provided
        if args.input:
            # CLI mode
            logger.info("Running in CLI mode")
            success = run_cli_mode(args)
            logger.info(f"CLI mode completed: {'success' if success else 'failure'}")
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