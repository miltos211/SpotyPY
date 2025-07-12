import os
import subprocess
import json
import re
import time
from urllib.parse import quote

def debug_log(message, level="INFO"):
    """Simple debug logging function"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def ensure_output_dir(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        print(f"Created directory: {path}")
    return path

def run_yt_dlp(video_url, output_dir, audio_format="mp3", audio_quality="0"):
    """Download audio from YouTube using yt-dlp"""
    try:
        # Ensure output directory exists
        ensure_output_dir(output_dir)
        
        # Create yt-dlp command
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "-x",  # Extract audio only
            "--audio-format", audio_format,
            "--audio-quality", audio_quality,
            "--no-playlist",  # Only download single video
            "--ignore-errors",  # Continue on errors
            "--force-overwrites",  # Overwrite existing files to ensure metadata is updated
            "-o", output_template,
            video_url
        ]
        
        # Run yt-dlp
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Try to find the downloaded file
            # yt-dlp should have created a file, let's find it
            files = os.listdir(output_dir)
            audio_files = [f for f in files if f.endswith(f'.{audio_format}')]
            
            if audio_files:
                # Get the most recently created file
                latest_file = max(audio_files, key=lambda f: os.path.getctime(os.path.join(output_dir, f)))
                file_path = os.path.join(output_dir, latest_file)
                
                return {
                    "status": 200,
                    "path": file_path,
                    "message": "Download successful"
                }
            else:
                return {
                    "status": 500,
                    "error": "Download completed but file not found"
                }
        else:
            # Check if it's a blocking error
            error_text = result.stderr.lower()
            if "sign in to confirm" in error_text or "video unavailable" in error_text:
                return {
                    "status": 500,
                    "error": f"YouTube blocking detected: {result.stderr}"
                }
            else:
                return {
                    "status": 500,
                    "error": f"yt-dlp failed: {result.stderr}"
                }
                
    except subprocess.TimeoutExpired:
        return {
            "status": 500,
            "error": "Download timeout (5 minutes)"
        }
    except Exception as e:
        return {
            "status": 500,
            "error": f"Unexpected error: {str(e)}"
        }

def find_lyrics_video(song_name, artist_name, expected_duration=None):
    """
    Search for a lyrics video on YouTube for the given song
    Returns video ID if found, None otherwise
    """
    try:
        # Clean up search terms
        clean_song = re.sub(r'[^\w\s]', '', song_name)
        clean_artist = re.sub(r'[^\w\s]', '', artist_name)
        
        # Try different search variations
        search_queries = [
            f"{clean_artist} {clean_song} lyrics",
            f"{clean_artist} {clean_song} lyric video",
            f"{clean_song} {clean_artist} lyrics",
            f"{clean_song} lyrics {clean_artist}"
        ]
        
        for query in search_queries:
            video_id = search_youtube_for_lyrics(query, expected_duration)
            if video_id:
                return video_id
                
        return None
        
    except Exception as e:
        print(f"Error finding lyrics video: {e}")
        return None

def search_youtube_for_lyrics(query, expected_duration=None):
    """
    Search YouTube for a specific query and return the best match video ID
    This is a simplified version - you might want to use YouTube API for better results
    """
    try:
        # Use yt-dlp to search (this is a basic implementation)
        search_cmd = [
            "yt-dlp",
            "--get-id",
            "--get-title", 
            "--get-duration",
            f"ytsearch5:{query}",  # Search for top 5 results
            "--no-warnings"
        ]
        
        result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            
            # Parse the output (format: title, duration, id, title, duration, id, ...)
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    title = lines[i]
                    duration = lines[i + 1] if i + 1 < len(lines) else ""
                    video_id = lines[i + 2] if i + 2 < len(lines) else ""
                    
                    # Check if this looks like a lyrics video
                    title_lower = title.lower()
                    if any(word in title_lower for word in ['lyrics', 'lyric', 'official lyric']):
                        # If we have expected duration, try to match it
                        if expected_duration and duration:
                            video_duration = parse_duration(duration)
                            if video_duration and abs(video_duration - expected_duration) <= 30:  # 30 second tolerance
                                return video_id
                        else:
                            return video_id
            
            # If no lyrics video found, return first result
            if len(lines) >= 3:
                return lines[2]  # First video ID
                
        return None
        
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        return None

def parse_duration(duration_str):
    """
    Parse duration string (like "3:45" or "1:23:45") to seconds
    """
    try:
        parts = duration_str.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            return None
    except:
        return None

def get_song_duration_seconds(entry):
    """Extract song duration from Spotify data and convert to seconds"""
    try:
        spotify_data = entry.get('spotify', {})
        duration_ms = spotify_data.get('duration_ms')
        if duration_ms:
            duration_seconds = duration_ms / 1000
            debug_log(f"Song duration: {duration_seconds} seconds ({duration_ms}ms)")
            return duration_seconds
    except Exception as e:
        debug_log(f"Could not get song duration: {e}", "WARN")
    return None

def process_song(index, entry, total, output_dir):
    debug_log(f"=== Processing song {index}/{total} ===")
    
    # Log entry structure
    debug_log(f"Entry keys: {list(entry.keys())}")
    debug_log(f"Spotify data: {entry.get('spotify', {}).get('name', 'Unknown')} by {entry.get('spotify', {}).get('artists', ['Unknown'])}")
    
    youtube = entry.get("youtube")
    debug_log(f"YouTube data present: {youtube is not None}")
    
    if not youtube:
        debug_log("No YouTube data in entry", "WARN")
        print(f"[{index}/{total}] Skipped: Missing YouTube metadata")
        return "skipped"

    debug_log(f"YouTube keys: {list(youtube.keys())}")
    
    if not youtube.get("id"):
        debug_log("No 'id' field in YouTube data", "WARN")
        print(f"[{index}/{total}] Skipped: Missing YouTube metadata")
        return "skipped"

    video_id = youtube["id"].get("videoId")
    debug_log(f"Video ID extracted: {video_id}")
    
    if not video_id:
        debug_log("No videoId in YouTube.id field", "WARN")
        print(f"[{index}/{total}] Skipped: Missing videoId")
        return "skipped"

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    debug_log(f"Constructed video URL: {video_url}")
    
    spotify_name = entry.get('spotify', {}).get('name', 'Unknown')
    spotify_artists = entry.get('spotify', {}).get('artists', ['Unknown'])
    song_duration = get_song_duration_seconds(entry)
    
    print(f"\n[{index}/{total}] Downloading: {spotify_name} by {', '.join(spotify_artists)}")
    print(f" Video URL: {video_url}")
    debug_log(f"Starting yt-dlp download to: {output_dir}")

    # Try primary download
    debug_log("Calling run_yt_dlp function")
    download_result = run_yt_dlp(
        video_url=video_url,
        output_dir=output_dir,
        audio_format="mp3",
        audio_quality="0"
    )
    
    debug_log(f"Primary yt-dlp result: {download_result}")
    debug_log(f"Primary download status: {download_result.get('status', 'Unknown')}")

    # If primary download failed with YouTube blocking, try lyrics video fallback
    if download_result["status"] == 500:  # YouTube blocking detected
        debug_log("Primary download failed due to YouTube blocking, trying lyrics video fallback")
        print(f" Primary download blocked by YouTube, searching for lyrics video...")
        
        # Search for lyrics video
        lyrics_video_id = find_lyrics_video(
            song_name=spotify_name,
            artist_name=', '.join(spotify_artists),
            expected_duration=song_duration
        )
        
        if lyrics_video_id:
            debug_log(f"Found lyrics video: {lyrics_video_id}")
            lyrics_url = f"https://www.youtube.com/watch?v={lyrics_video_id}"
            print(f" Trying lyrics video: {lyrics_url}")
            
            # Try downloading the lyrics video
            lyrics_result = run_yt_dlp(
                video_url=lyrics_url,
                output_dir=output_dir,
                audio_format="mp3",
                audio_quality="0"
            )
            
            if lyrics_result["status"] == 200:
                debug_log("Lyrics video download successful")
                print(f" Lyrics video download successful!")
                download_result = lyrics_result
            else:
                debug_log(f"Lyrics video download also failed: {lyrics_result.get('error', 'Unknown error')}")
                print(f" Lyrics video download also failed: {lyrics_result.get('error', 'Unknown error')}")
        else:
            debug_log("No suitable lyrics video found")
            print(f" No suitable lyrics video found")

    # Final check if download succeeded
    if download_result["status"] != 200:
        debug_log(f"All download attempts failed with status {download_result['status']}: {download_result.get('error', 'Unknown error')}", "ERROR")
        print(f" All download attempts failed: {download_result['error']}")
        return "failed"

    file_path = download_result["path"]
    debug_log(f"Downloaded file path: {file_path}")
    debug_log(f"File exists check: {os.path.isfile(file_path) if file_path else 'No path provided'}")
    
    if not os.path.isfile(file_path):
        debug_log(f"Downloaded file not found at: {file_path}", "ERROR")
        print(" Skipped: Downloaded file not found.")
        return "skipped"

    file_size = os.path.getsize(file_path)
    debug_log(f"File size: {file_size} bytes")
    print(f" Download complete: {file_path}")
    
    result = { "status": "downloaded", "file_path": file_path, "entry": entry }
    debug_log(f"Returning success result: {result['status']}")
    return result