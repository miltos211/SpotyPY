import sys
import os
import json
import time
import threading
import argparse
from pathlib import Path
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup path to .lib/
sys.path.append(os.path.join(os.path.dirname(__file__), '.lib'))

from metadata.download import run_yt_dlp, ensure_output_dir, find_lyrics_video
from metadata.tagger import tag_from_enriched
from metadata.artwork import embed_art_from_enriched

# Import logging utilities
from utils.logging import create_logger, thread_safe_print

# Import path utilities
from utils.paths import PathValidator, validate_input_file, validate_directory

# Import CLI utilities
from utils.cli import add_common_arguments, validate_thread_count, create_standard_parser, COMMON_EPILOGS

# Initialize logger
logger = None

def print_menu():
    print("\n=== YouTube Music Fetcher (Threaded Mode) ===")
    print("1. Start download from enriched JSON (with threading)")
    print("2. Start download from enriched JSON (no threading)")
    print("0. Exit")

def prompt_path(prompt, must_exist=False):
    while True:
        path = input(f"{prompt.strip()} ").strip()
        logger.debug(f"User entered path: '{path}'")
        
        if not path:
            print(" Path cannot be empty.")
            continue
            
        if must_exist and not os.path.exists(path):
            logger.error(f"Path does not exist: {path}")
            print(" Path does not exist.")
            continue
            
        logger.debug(f"Path validated: {path}")
        return path

def prompt_thread_count():
    """Ask user for number of threads to use"""
    while True:
        try:
            count = input("Number of concurrent downloads (1-8, default 3): ").strip()
            if not count:
                return 3
            count = int(count)
            if 1 <= count <= 8:
                return count
            print(" Please enter a number between 1 and 8.")
        except ValueError:
            print(" Please enter a valid number.")

def load_enriched_json(path):
    logger.debug(f"Loading JSON from: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Successfully loaded JSON with {len(data)} entries")
        return data
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        print(f" Failed to load JSON: {e}")
        return None

def get_song_duration_seconds(entry):
    """Extract song duration from Spotify data and convert to seconds"""
    try:
        spotify_data = entry.get('spotify', {})
        duration_ms = spotify_data.get('duration_ms')
        if duration_ms:
            duration_seconds = duration_ms / 1000
            return duration_seconds
    except Exception as e:
        return None
    return None

def process_single_song_complete(song_data):
    """
    Process a single song from start to finish (download + metadata + artwork)
    This runs in its own thread
    """
    index, entry, total, output_dir = song_data
    thread_id = threading.get_ident() % 1000  # Short thread ID for logging
    
    logger.debug(f"=== Starting complete processing for song {index}/{total} ===")
    
    try:
        # Phase 1: Download
        download_result = download_song_worker(song_data)
        
        if isinstance(download_result, dict) and download_result["status"] == "downloaded":
            logger.debug(f"Download successful, proceeding to metadata")
            
            # Phase 2: Process metadata and artwork
            metadata_result = process_metadata_worker(download_result["file_path"], download_result["entry"], thread_id)
            
            if metadata_result == "success":
                logger.debug(f"Song {index} completed successfully")
                return {"status": "success", "index": index, "path": download_result["file_path"]}
            else:
                logger.error(f"Metadata failed for song {index}")
                return {"status": "metadata_failed", "index": index}
        else:
            logger.error(f"Download failed for song {index}: {download_result}")
            return {"status": download_result, "index": index}
            
    except Exception as e:
        logger.error(f"Exception in song {index}: {e}")
        return {"status": "exception", "index": index, "error": str(e)}

def download_song_worker(song_data):
    """Worker function for downloading a single song"""
    index, entry, total, output_dir = song_data
    thread_id = threading.get_ident() % 1000
    
    logger.debug(f"Download worker started for song {index}")
    
    # Extract song info
    spotify_name = entry.get('spotify', {}).get('name', 'Unknown')
    spotify_artists = entry.get('spotify', {}).get('artists', ['Unknown'])
    song_duration = get_song_duration_seconds(entry)
    
    logger.debug(f"Processing: {spotify_name} by {', '.join(spotify_artists)}")
    
    youtube = entry.get("youtube")
    if not youtube or not youtube.get("id") or not youtube["id"].get("videoId"):
        logger.warning(f"Missing YouTube data for song {index}")
        thread_safe_print(f"[{index}/{total}] Skipped: Missing YouTube metadata - {spotify_name}")
        return "skipped"

    video_id = youtube["id"]["videoId"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    thread_safe_print(f"[{index}/{total}] Downloading: {spotify_name} by {', '.join(spotify_artists)}")
    logger.debug(f"Video URL: {video_url}")

    # Try primary download
    download_result = run_yt_dlp(
        video_url=video_url,
        output_dir=output_dir,
        audio_format="mp3",
        audio_quality="0"
    )
    
    logger.debug(f"Primary download result: {download_result.get('status', 'Unknown')}")

    # If primary download failed with YouTube blocking, try lyrics video fallback
    if download_result["status"] == 500:  # YouTube blocking detected
        logger.debug("Trying lyrics video fallback")
        thread_safe_print(f"[{index}/{total}] Searching for lyrics video fallback...")
        
        lyrics_video_id = find_lyrics_video(
            song_name=spotify_name,
            artist_name=', '.join(spotify_artists),
            expected_duration=song_duration
        )
        
        if lyrics_video_id:
            lyrics_url = f"https://www.youtube.com/watch?v={lyrics_video_id}"
            logger.debug(f"Found lyrics video: {lyrics_url}")
            thread_safe_print(f"[{index}/{total}] Trying lyrics video...")
            
            lyrics_result = run_yt_dlp(
                video_url=lyrics_url,
                output_dir=output_dir,
                audio_format="mp3",
                audio_quality="0"
            )
            
            if lyrics_result["status"] == 200:
                logger.debug("Lyrics video download successful")
                thread_safe_print(f"[{index}/{total}] Lyrics video download successful!")
                download_result = lyrics_result
            else:
                logger.warning("Lyrics video also failed")
        else:
            logger.warning("No suitable lyrics video found")

    # Final check if download succeeded
    if download_result["status"] != 200:
        thread_safe_print(f"[{index}/{total}] Failed: {download_result.get('error', 'Unknown error')}")
        return "failed"

    file_path = download_result["path"]
    if not os.path.isfile(file_path):
        thread_safe_print(f"[{index}/{total}] Skipped: Downloaded file not found")
        return "skipped"

    file_size = os.path.getsize(file_path)
    logger.debug(f"Download complete: {file_path} ({file_size} bytes)")
    thread_safe_print(f"[{index}/{total}] Download complete: {os.path.basename(file_path)}")
    
    return {"status": "downloaded", "file_path": file_path, "entry": entry}

def process_metadata_worker(file_path, entry, thread_id):
    """Worker function for processing metadata and artwork"""
    logger.debug(f"Starting metadata processing for: {os.path.basename(file_path)}")
    
    # Check file before processing
    if not os.path.isfile(file_path):
        logger.error(f"File not found: {file_path}")
        return "failed"
    
    file_size_before = os.path.getsize(file_path)
    logger.debug(f"File size before metadata: {file_size_before} bytes")
    
    # Tag metadata
    logger.debug("Starting metadata tagging")
    tag_result = tag_from_enriched(entry, file_path)
    
    if tag_result["status"] != 200:
        logger.error(f"Tagging failed: {tag_result.get('error', 'Unknown error')}")
        return "failed"
    
    logger.debug("Tagging completed successfully")
    
    # Check file after tagging
    if not os.path.isfile(file_path):
        logger.error(f"File disappeared after tagging")
        return "failed"
    
    file_size_after_tags = os.path.getsize(file_path)
    logger.debug(f"File size after tagging: {file_size_after_tags} bytes")

    # Embed album art
    logger.debug("Starting artwork embedding")
    art_result = embed_art_from_enriched(entry, file_path)
    
    if art_result["status"] != 200:
        logger.error(f"Artwork embedding failed: {art_result.get('error', 'Unknown error')}")
        return "failed"
    
    logger.debug("Artwork embedding completed successfully")
    
    # Final file check
    if not os.path.isfile(file_path):
        logger.error(f"File disappeared after artwork")
        return "failed"
    
    file_size_final = os.path.getsize(file_path)
    logger.debug(f"Final file size: {file_size_final} bytes")
    logger.debug(f"Metadata processing completed successfully")
    
    return "success"

def process_songs_threaded(entries, output_dir, max_workers=3):
    """Process songs using hybrid approach: threaded downloads, sequential metadata"""
    logger.debug(f"Starting hybrid processing with {max_workers} download workers")
    
    total = len(entries)
    results = {"success": 0, "failed": 0, "skipped": 0, "metadata_failed": 0}
    downloaded_files = []
    
    # Prepare song data for workers
    song_data_list = [(i+1, entry, total, output_dir) for i, entry in enumerate(entries)]
    
    thread_safe_print(f"\nProcessing {total} songs with {max_workers} concurrent download threads...\n")
    
    # Phase 1: Threaded downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks
        future_to_song = {executor.submit(download_song_worker, song_data): song_data 
                         for song_data in song_data_list}
        
        # Process completed downloads
        for future in as_completed(future_to_song):
            song_data = future_to_song[future]
            song_index = song_data[0]
            try:
                download_result = future.result()
                
                if isinstance(download_result, dict) and download_result["status"] == "downloaded":
                    downloaded_files.append((song_index, download_result["file_path"], download_result["entry"]))
                    thread_safe_print(f"✓ [{song_index}/{total}] Downloaded: {os.path.basename(download_result['file_path'])}")
                elif download_result == "skipped":
                    results["skipped"] += 1
                    thread_safe_print(f"⚠ [{song_index}/{total}] Skipped")
                else:
                    results["failed"] += 1
                    thread_safe_print(f"✗ [{song_index}/{total}] Download failed")
                    
            except Exception as e:
                results["failed"] += 1
                logger.error(f"Exception downloading song {song_index}: {e}")
                thread_safe_print(f"✗ [{song_index}/{total}] Download exception: {str(e)}")
    
    # Phase 2: Sequential metadata and artwork processing
    if downloaded_files:
        thread_safe_print(f"\nProcessing metadata and artwork sequentially for {len(downloaded_files)} downloaded songs...\n")
        
        for song_index, file_path, entry in downloaded_files:
            try:
                thread_safe_print(f"[{song_index}/{total}] Processing metadata: {os.path.basename(file_path)}")
                metadata_result = process_metadata_worker(file_path, entry, "sequential")
                
                if metadata_result == "success":
                    results["success"] += 1
                    thread_safe_print(f"✓ [{song_index}/{total}] Complete: {os.path.basename(file_path)}")
                else:
                    results["metadata_failed"] += 1
                    thread_safe_print(f"⚠ [{song_index}/{total}] Downloaded but metadata failed")
                    
            except Exception as e:
                results["metadata_failed"] += 1
                logger.error(f"Exception processing metadata for song {song_index}: {e}")
                thread_safe_print(f"⚠ [{song_index}/{total}] Metadata exception: {str(e)}")
    
    return results

def process_songs_sequential(entries, output_dir):
    """Process songs sequentially (original method)"""
    logger.debug("Starting sequential processing")
    
    total = len(entries)
    downloaded = []
    skipped = failed = 0

    logger.debug(f"Starting download phase for {total} tracks")
    print(f"\nDownloading {total} tracks sequentially...\n")
    
    # Download phase
    for i, entry in enumerate(entries, 1):
        song_data = (i, entry, total, output_dir)
        result = download_song_worker(song_data)
        
        if isinstance(result, dict) and result["status"] == "downloaded":
            downloaded.append(result)
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    logger.debug(f"Download phase complete. Downloaded: {len(downloaded)}, Skipped: {skipped}, Failed: {failed}")
    print(f"\nStarting metadata embedding...\n")

    # Metadata phase
    done = 0
    for i, item in enumerate(downloaded, 1):
        print(f"[{i}/{len(downloaded)}] Processing: {os.path.basename(item['file_path'])}")
        result = process_metadata_worker(item["file_path"], item["entry"], "main")
        
        if result == "success":
            done += 1
        else:
            failed += 1

    return {"success": done, "failed": failed, "skipped": skipped, "metadata_failed": 0}

def parse_arguments():
    """Parse command line arguments"""
    epilog = COMMON_EPILOGS["downloader"].format(script="yt_FetchMK1.py")
    parser = create_standard_parser(
        description='Download audio files from enriched YouTube Music data',
        epilog=epilog
    )
    
    # Add common arguments (input, output, threads, quiet)
    add_common_arguments(parser, script_type="io")
    
    # Add script-specific arguments
    parser.add_argument('--artwork-dir', type=str,
                        help='Temporary artwork directory (default: same as output)')
    
    return parser.parse_args()

def run_cli_mode(args):
    """Run in CLI mode with provided arguments"""
    logger.info("CLI Mode Started")
    logger.debug(f"Input: {args.input}")
    logger.debug(f"Output: {args.output}")
    logger.debug(f"Threads: {args.threads}")
    
    # Validate input file
    is_valid, input_path, error = validate_input_file(args.input, extensions=['.json'])
    if not is_valid:
        logger.error(f"Invalid input file: {error}")
        return False
    
    logger.debug(f"Validated input file: {input_path}")
    
    # Validate and set up directories
    is_valid, output_dir, error = validate_directory(args.output, create=True)
    if not is_valid:
        logger.error(f"Invalid output directory: {error}")
        return False
    
    if args.artwork_dir:
        is_valid, artwork_dir, error = validate_directory(args.artwork_dir, create=True)
        if not is_valid:
            logger.error(f"Invalid artwork directory: {error}")
            return False
    else:
        artwork_dir = output_dir
    
    logger.debug(f"Validated directories - Output: {output_dir}, Artwork: {artwork_dir}")
    
    # Load data
    entries = load_enriched_json(str(input_path))
    if not entries:
        logger.error("No entries loaded from JSON file")
        return False
    
    # Validate thread count
    thread_count = args.threads
    is_valid, error = validate_thread_count(thread_count, max_threads=8)
    if not is_valid:
        logger.error(error)
        return False
    
    logger.info(f"Processing {len(entries)} tracks...")
    
    # Process tracks
    start_time = time.time()
    
    if thread_count == 0:
        logger.info("Using sequential processing")
        results = process_songs_sequential(entries, str(output_dir))
    else:
        logger.info(f"Using threaded processing with {thread_count} workers")
        results = process_songs_threaded(entries, str(output_dir), thread_count)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Print results
    print(f"\n=== Summary ===")
    print(f" Success: {results['success']}")
    print(f" Failed: {results['failed']}")
    print(f" Skipped: {results['skipped']}")
    if results['metadata_failed'] > 0:
        print(f" Metadata Failed: {results['metadata_failed']}")
    print(f" Time: {duration:.2f} seconds")
    
    logger.info(f"Processing completed in {duration:.2f}s - Success: {results['success']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
    
    return results['success'] > 0 or results['skipped'] > 0  # Success if any files processed

def run_interactive_mode():
    """Run in interactive menu mode"""
    logger.debug("=== Interactive Mode Started ===")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Working directory: {os.getcwd()}")
    logger.debug(f"Script path: {__file__}")
    
    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        logger.debug(f"User choice: '{choice}'")

        if choice in ["1", "2"]:
            logger.debug("Starting download process")
            
            json_path = prompt_path("Enter path to enriched JSON:", must_exist=True)
            output_dir = prompt_path("Enter output directory for audio files:")
            artwork_tmp = prompt_path("Enter temporary artwork folder (can be same as output):")

            logger.debug(f"Paths configured - JSON: {json_path}, Output: {output_dir}, Artwork: {artwork_tmp}")

            logger.debug("Ensuring output directories exist")
            ensure_output_dir(output_dir)
            ensure_output_dir(artwork_tmp)
            logger.debug("Directories created/verified")

            entries = load_enriched_json(json_path)
            if not entries:
                logger.warning("No entries loaded, returning to menu")
                continue

            start_time = time.time()
            
            if choice == "1":  # Threaded
                thread_count = prompt_thread_count()
                logger.debug(f"Using {thread_count} threads")
                results = process_songs_threaded(entries, output_dir, thread_count)
            else:  # Sequential
                results = process_songs_sequential(entries, output_dir)

            end_time = time.time()
            duration = end_time - start_time
            
            logger.debug(f"All processing complete in {duration:.2f} seconds")
            print(f"\n=== Summary ===")
            print(f" Success: {results['success']}")
            print(f" Failed: {results['failed']}")
            print(f" Skipped: {results['skipped']}")
            if results['metadata_failed'] > 0:
                print(f" Metadata Failed: {results['metadata_failed']}")
            print(f" Time: {duration:.2f} seconds")

        elif choice == "0":
            logger.debug("User chose to exit")
            print(" Goodbye!")
            break
        else:
            logger.debug(f"Invalid choice: {choice}")
            print(" Invalid option. Try again.")

def main():
    global logger
    args = parse_arguments()
    
    # Initialize logger
    logger = create_logger("yt_fetch", quiet=args.quiet)
    
    logger.info("YouTube Music Fetcher started")
    logger.debug(f"Arguments: {vars(args)}")
    
    try:
        # Check if CLI arguments were provided
        if args.input and args.output:
            # CLI mode
            logger.info("Running in CLI mode")
            success = run_cli_mode(args)
            logger.info(f"CLI mode completed: {'success' if success else 'failure'}")
            sys.exit(0 if success else 1)
        else:
            # Interactive mode (if missing required args for CLI)
            if args.input or args.output or args.threads > 0:
                logger.error("For CLI mode, both --input and --output are required")
                print("ERROR: For CLI mode, both --input and --output are required")
                print("Run without arguments for interactive mode")
                sys.exit(1)
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