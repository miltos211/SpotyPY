#!/usr/bin/env python3
"""
JSON-MP3 Sync Utility for SpotifyToYT

This utility synchronizes enriched JSON files with actual MP3 files in the songs directory.
It updates download_state fields to reflect reality, enabling smart resume functionality.

Features:
- Scans songs directory for existing MP3 files
- Compares with enriched JSON download states
- Updates JSON to mark missing files as "pending" for re-download
- Validates existing files (size, accessibility)
- Creates backup of original JSON before modifications
- Provides detailed sync report

Usage:
    python .debug/json_sync.py
"""

import json
import os
import sys
import time
from pathlib import Path
import shutil
from typing import Dict, List, Tuple, Optional

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to match the same logic used in yt_FetchMK1.py
    This ensures we look for files with the correct names.
    """
    # Remove/replace problematic characters
    safe_name = filename
    replacements = {
        '/': '-', '\\': '-', ':': '-', '*': '-', '?': '-',
        '"': "'", '<': '-', '>': '-', '|': '-',
        '\n': ' ', '\r': ' ', '\t': ' '
    }
    
    for old, new in replacements.items():
        safe_name = safe_name.replace(old, new)
    
    # Remove multiple spaces and strip
    while '  ' in safe_name:
        safe_name = safe_name.replace('  ', ' ')
    safe_name = safe_name.strip()
    
    # Handle Windows reserved names
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    if safe_name.upper() in reserved_names:
        safe_name = f"{safe_name}_track"
    
    # Limit length to avoid filesystem issues
    if len(safe_name) > 100:
        safe_name = safe_name[:100]
    
    return safe_name

def find_mp3_files(songs_dir: str) -> Dict[str, str]:
    """
    Scan songs directory and return dict of {sanitized_name: full_path}
    """
    mp3_files = {}
    
    if not os.path.exists(songs_dir):
        print(f"❌ Songs directory not found: {songs_dir}")
        return mp3_files
    
    print(f"🔍 Scanning directory: {songs_dir}")
    
    for root, dirs, files in os.walk(songs_dir):
        for file in files:
            if file.lower().endswith('.mp3'):
                full_path = os.path.join(root, file)
                # Remove .mp3 extension to get base name
                base_name = file[:-4]
                mp3_files[base_name] = full_path
    
    print(f"📁 Found {len(mp3_files)} MP3 files")
    return mp3_files

def validate_mp3_file(file_path: str) -> bool:
    """
    Validate that MP3 file exists and is not corrupted/empty
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        size = os.path.getsize(file_path)
        if size < 1024:  # Less than 1KB is suspicious
            print(f"⚠️  Suspicious small file: {os.path.basename(file_path)} ({size} bytes)")
            return False
        
        # Try to open file to check accessibility
        with open(file_path, 'rb') as f:
            f.read(1024)  # Read first KB to verify accessibility
        
        return True
    except Exception as e:
        print(f"❌ File validation failed for {os.path.basename(file_path)}: {e}")
        return False

def sync_json_with_mp3s(json_path: str, songs_dir: str, dry_run: bool = False) -> Dict[str, int]:
    """
    Synchronize enriched JSON with actual MP3 files
    
    Returns dict with counts: {found, missing, corrupted, updated}
    """
    # Load JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load JSON: {e}")
        return {}
    
    # Get existing MP3 files
    mp3_files = find_mp3_files(songs_dir)
    
    stats = {
        'found': 0,
        'missing': 0, 
        'corrupted': 0,
        'updated': 0,
        'already_pending': 0
    }
    
    print(f"\n🔄 Analyzing {len(data)} tracks...")
    
    for i, entry in enumerate(data):
        spotify = entry.get('spotify', {})
        song_name = spotify.get('name', 'Unknown')
        artists = ', '.join(spotify.get('artists', ['Unknown']))
        
        # Generate expected filename (same logic as yt_FetchMK1.py)
        expected_filename = sanitize_filename(song_name)
        
        # Initialize download_state if missing
        if 'download_state' not in entry:
            entry['download_state'] = {
                "status": "pending",
                "attempt_count": 0,
                "failure_count": 0,
                "last_error": None,
                "last_attempt": None,
                "delays_applied": [],
                "file_path": None,
                "file_size": None,
                "completed_at": None
            }
        
        download_state = entry['download_state']
        current_status = download_state.get('status', 'pending')
        current_path = download_state.get('file_path')
        
        # Check if MP3 file exists
        found_file = None
        if expected_filename in mp3_files:
            found_file = mp3_files[expected_filename]
        else:
            # Fallback: search by song name (fuzzy match)
            for mp3_name, mp3_path in mp3_files.items():
                if song_name.lower() in mp3_name.lower() or mp3_name.lower() in song_name.lower():
                    found_file = mp3_path
                    break
        
        if found_file and validate_mp3_file(found_file):
            # File exists and is valid
            stats['found'] += 1
            
            if current_status != 'completed':
                # Update JSON to reflect completed status
                download_state['status'] = 'completed'
                download_state['file_path'] = found_file
                download_state['file_size'] = os.path.getsize(found_file)
                download_state['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                stats['updated'] += 1
                print(f"✅ [{i+1}/{len(data)}] Found: {song_name} by {artists}")
            
        elif found_file and not validate_mp3_file(found_file):
            # File exists but is corrupted
            stats['corrupted'] += 1
            download_state['status'] = 'pending'
            download_state['file_path'] = None
            download_state['last_error'] = 'File corrupted - needs re-download'
            stats['updated'] += 1
            print(f"🔄 [{i+1}/{len(data)}] Corrupted (will re-download): {song_name} by {artists}")
            
        else:
            # File is missing
            stats['missing'] += 1
            
            if current_status == 'pending':
                stats['already_pending'] += 1
                print(f"⏳ [{i+1}/{len(data)}] Already pending: {song_name} by {artists}")
            else:
                # Mark as pending for re-download
                download_state['status'] = 'pending'
                download_state['file_path'] = None
                download_state['last_error'] = 'File missing - needs download'
                stats['updated'] += 1
                print(f"🔄 [{i+1}/{len(data)}] Missing (will download): {song_name} by {artists}")
    
    # Save updated JSON (unless dry run)
    if not dry_run and stats['updated'] > 0:
        # Create backup first
        backup_path = f"{json_path}.backup.{int(time.time())}"
        shutil.copy2(json_path, backup_path)
        print(f"\n💾 Created backup: {backup_path}")
        
        # Save updated JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Updated JSON saved: {json_path}")
    
    return stats

def print_report(stats: Dict[str, int], dry_run: bool = False):
    """Print sync report"""
    print(f"\n{'=' * 50}")
    print(f"📊 SYNC REPORT {'(DRY RUN)' if dry_run else ''}")
    print(f"{'=' * 50}")
    print(f"✅ Files found and valid:     {stats.get('found', 0)}")
    print(f"❌ Files missing:             {stats.get('missing', 0)}")
    print(f"🔧 Files corrupted:           {stats.get('corrupted', 0)}")  
    print(f"⏳ Already pending:           {stats.get('already_pending', 0)}")
    print(f"🔄 JSON entries updated:      {stats.get('updated', 0)}")
    
    total_issues = stats.get('missing', 0) + stats.get('corrupted', 0)
    if total_issues > 0:
        print(f"\n🎯 {total_issues} tracks will be downloaded on next run")
    else:
        print(f"\n✨ All tracks are properly downloaded!")

def main():
    print("🔄 SpotifyToYT JSON-MP3 Sync Utility")
    print("=" * 40)
    
    # Get input paths
    json_path = input("📁 Enter path to enriched JSON file: ").strip()
    if not json_path:
        print("❌ JSON path is required")
        return
    
    if not os.path.exists(json_path):
        print(f"❌ JSON file not found: {json_path}")
        return
    
    songs_dir = input("📁 Enter path to songs directory (default: songs/): ").strip()
    if not songs_dir:
        songs_dir = "songs/"
    
    # Ask for dry run
    dry_run_input = input("🧪 Dry run? (y/N): ").strip().lower()
    dry_run = dry_run_input in ['y', 'yes']
    
    if dry_run:
        print("\n🧪 DRY RUN MODE - No files will be modified")
    else:
        print("\n⚠️  LIVE MODE - JSON will be updated and backup created")
        confirm = input("Continue? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Cancelled")
            return
    
    # Perform sync
    try:
        stats = sync_json_with_mp3s(json_path, songs_dir, dry_run)
        print_report(stats, dry_run)
        
        if not dry_run and stats.get('updated', 0) > 0:
            print(f"\n🚀 Ready for resume! Run yt_FetchMK1.py with the updated JSON to download missing tracks.")
            
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()