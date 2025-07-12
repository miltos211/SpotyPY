import sys
import os
import json
import argparse
from dotenv import load_dotenv

# Add the `.lib` folder to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '.lib'))

from youtube.auth import get_youtube_client

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
    print(f"\n{debug('[API]')} Creating playlist...")
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
    return response["id"]

def add_video_to_playlist(youtube, playlist_id, video_id):
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
    request.execute()

def debug(msg):
    return f"[debug] {msg}"

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Create YouTube playlists from enriched JSON data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python yt_PushMK1.py                                           # Interactive mode
  python yt_PushMK1.py -i enriched.json -t "My Playlist"        # Create private playlist
  python yt_PushMK1.py -i enriched.json -t "Public Songs" --privacy public
  python yt_PushMK1.py --input enriched.json --title "My Mix" --privacy unlisted
        '''
    )
    
    parser.add_argument('-i', '--input', type=str,
                        help='Input enriched JSON file path')
    
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
        print(f"ERROR: Input file not found: {args.input}")
        return False

    # Load enriched data
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON: {e}")
        return False

    # Extract YouTube video IDs
    video_ids = [
        entry["youtube"]["id"]["videoId"]
        for entry in data
        if entry.get("youtube") and entry["youtube"].get("id") and entry["youtube"]["id"].get("videoId")
    ]

    if not video_ids:
        print("ERROR: No valid video IDs found in the file.")
        return False

    print(f"Found {len(video_ids)} videos to add to playlist")

    # Auth
    try:
        yt = get_youtube_client()
    except Exception as e:
        print(f"ERROR: YouTube authentication failed: {e}")
        return False

    # Create playlist
    try:
        playlist_id = create_playlist(yt, args.title, args.privacy)
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        print(f"✓ Playlist created: {playlist_url}")
    except Exception as e:
        print(f"ERROR: Failed to create playlist: {e}")
        return False

    # Push videos
    print(f"\nAdding {len(video_ids)} videos to playlist...")
    push_count = 0
    failed_count = 0
    
    for i, video_id in enumerate(video_ids, 1):
        try:
            print(f"[{i}/{len(video_ids)}] Adding: https://www.youtube.com/watch?v={video_id}")
            add_video_to_playlist(yt, playlist_id, video_id)
            push_count += 1
        except Exception as e:
            print(f"  Failed to add video {video_id}: {e}")
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
        print(" Input file not found.")
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
        print(" No valid video IDs found in the file.")
        return

    # Auth
    yt = get_youtube_client()

    # Create playlist
    playlist_id = create_playlist(yt, playlist_title, privacy_status)
    print(f" Playlist created: https://www.youtube.com/playlist?list={playlist_id}")

    # Push videos
    print(f"\n{debug('')} Adding videos to playlist...\n")
    push_count = 0
    for i, video_id in enumerate(video_ids, 1):
        print(f"{debug(f'PUSH {i}/{len(video_ids)}')} Adding video: https://www.youtube.com/watch?v={video_id}")
        add_video_to_playlist(yt, playlist_id, video_id)
        push_count += 1

    print(f"\n Done! {push_count} videos added.")
    print(f"{debug('Total YouTube API queries: ' + str(1 + push_count))}")  # 1 for create + N adds

def main():
    args = parse_arguments()
    
    # Check if CLI arguments were provided
    if args.input and args.title:
        # CLI mode
        success = run_cli_mode(args)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode (if missing required args for CLI)
        if args.input or args.title:
            print("ERROR: For CLI mode, both --input and --title are required")
            print("Run without arguments for interactive mode")
            sys.exit(1)
        run_interactive_mode()

if __name__ == "__main__":
    main()
