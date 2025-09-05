#!/usr/bin/env python3
"""
Batch JSON-MP3 Sync Utility for SpotifyToYT

Non-interactive version for automation and scripting.

Usage:
    python .debug/json_sync_batch.py <enriched_json> <songs_dir> [--dry-run]

Examples:
    python .debug/json_sync_batch.py out/playlist_enriched.json songs/
    python .debug/json_sync_batch.py out/liked_songs_enriched.json songs/liked_songs_05-09-25/ --dry-run
"""

import sys
import os

# Add .lib to path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.lib'))

# Import the sync logic from the interactive version
sys.path.append(os.path.dirname(__file__))
from json_sync import sync_json_with_mp3s, print_report

def main():
    if len(sys.argv) < 3:
        print("Usage: python json_sync_batch.py <enriched_json> <songs_dir> [--dry-run]")
        print("\nExamples:")
        print("  python .debug/json_sync_batch.py out/playlist_enriched.json songs/")
        print("  python .debug/json_sync_batch.py out/liked_songs_enriched.json songs/liked_songs_05-09-25/ --dry-run")
        sys.exit(1)
    
    json_path = sys.argv[1]
    songs_dir = sys.argv[2] 
    dry_run = '--dry-run' in sys.argv
    
    # Validate inputs
    if not os.path.exists(json_path):
        print(f"JSON file not found: {json_path}")
        sys.exit(1)
    
    if not os.path.exists(songs_dir):
        print(f"Songs directory not found: {songs_dir}")
        sys.exit(1)
    
    print(f"SpotifyToYT JSON-MP3 Sync (Batch Mode)")
    print(f"JSON: {json_path}")
    print(f"Songs: {songs_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)
    
    try:
        stats = sync_json_with_mp3s(json_path, songs_dir, dry_run)
        print_report(stats, dry_run)
        
        # Exit codes for automation
        total_issues = stats.get('missing', 0) + stats.get('corrupted', 0)
        if total_issues > 0:
            print(f"\n🎯 Exit code 1: {total_issues} tracks need downloading")
            sys.exit(1)  # Issues found
        else:
            print(f"\n✨ Exit code 0: All tracks synchronized")
            sys.exit(0)  # All good
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)  # Error occurred

if __name__ == "__main__":
    main()