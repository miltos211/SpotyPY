import os
import subprocess
import json
import re
import time
import random
from urllib.parse import quote

# Import proper logging system
from utils.logging import get_logger

# Initialize logger for this module
logger = get_logger("download")

def detect_youtube_bot_blocking(stderr_output):
    """
    Detect YouTube's 'Sign in to confirm you're not a bot' error
    
    Args:
        stderr_output: yt-dlp stderr string
        
    Returns:
        bool: True if bot detection pattern found
    """
    blocking_patterns = [
        "sign in to confirm you're not a bot",
        "use --cookies-from-browser or --cookies",
        "authentication. see"  # Part of the full error message
    ]
    
    stderr_lower = stderr_output.lower()
    return any(pattern in stderr_lower for pattern in blocking_patterns)

def calculate_smart_bot_delay(thread_count=1, recent_failure_count=0, recent_attempt_count=0, song_failures=0, song_attempts=0):
    """
    Calculate optimal delay for bot detection recovery
    
    Formula:
    - Base: 80 seconds (conservative starting point)
    - Thread Factor: +40% per extra thread (reduces suspicion on single-threaded downloads)
    - Failure Rate Factor: Double delay at 100% batch failure rate (linear scaling)
    - Song Penalty: +50% max for problem tracks (tracks that consistently fail)
    - Randomization: ±20% variance to break predictable patterns
    - Range: 60-240 seconds (user-specified acceptable range)
    
    Args:
        thread_count: Number of concurrent download threads
        recent_failure_count: Recent failures in batch
        recent_attempt_count: Recent attempts in batch  
        song_failures: Individual song failure count
        song_attempts: Individual song attempt count
        
    Returns:
        float: Delay in seconds (60-240 range)
    """
    base_delay = 80
    
    # Thread escalation: +40% per extra thread
    thread_factor = 1 + (thread_count - 1) * 0.4
    
    # Batch failure rate escalation: double at 100% failure rate  
    if recent_attempt_count > 0:
        batch_failure_rate = recent_failure_count / recent_attempt_count
        failure_factor = 1 + batch_failure_rate
    else:
        failure_factor = 1
    
    # Individual song penalty for problem tracks
    if song_attempts > 0:
        song_failure_rate = song_failures / song_attempts
        song_penalty = 1 + (song_failure_rate * 0.5)  # +50% max penalty
    else:
        song_penalty = 1
    
    # Calculate with all factors
    calculated = base_delay * thread_factor * failure_factor * song_penalty
    
    # Randomize (±20% variance)  
    randomized = random.uniform(calculated * 0.8, calculated * 1.2)
    
    # Clamp to acceptable range
    final_delay = max(60, min(240, randomized))
    
    logger.debug(f"Smart delay calculation: base={base_delay}, thread_factor={thread_factor:.2f}, failure_factor={failure_factor:.2f}, song_penalty={song_penalty:.2f}, final={final_delay:.1f}s")
    
    return final_delay

def ensure_output_dir(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        logger.info(f"Created directory: {path}")
    return path

def run_yt_dlp_with_context(video_url, output_dir, audio_format="mp3", audio_quality="0", custom_filename=None, 
                           thread_count=1, batch_failure_count=0, batch_attempt_count=0, 
                           song_failure_count=0, song_attempt_count=0):
    """Download audio from YouTube using yt-dlp
    
    Args:
        video_url: YouTube video URL
        output_dir: Directory to save the file
        audio_format: Audio format (default: mp3)
        audio_quality: Audio quality (default: 0)
        custom_filename: Custom filename without extension (avoids race conditions in threaded downloads)
    """
    try:
        # Ensure output directory exists
        ensure_output_dir(output_dir)
        
        # Create yt-dlp command with thread-safe filename
        if custom_filename:
            # Use custom filename to prevent race conditions between threads
            output_template = os.path.join(output_dir, f"{custom_filename}.%(ext)s")
        else:
            # Fall back to YouTube title (legacy behavior)
            output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "-x",  # Extract audio only
            "--audio-format", audio_format,
            "--audio-quality", audio_quality,
            "--no-playlist",  # Only download single video
            "--ignore-errors",  # Continue on errors
            "--force-overwrites",  # Overwrite existing files to ensure metadata is updated
            "--sleep-interval", "5",  # 5 seconds between downloads (anti-bot)
            "--max-sleep-interval", "15",  # Random up to 15 seconds
            "--limit-rate", "1M",  # 1MB/s bandwidth limit (appears more human)
            "--concurrent-fragments", "2",  # Limit fragments per video (less aggressive)
            "--extractor-args", "youtube:player_client=web,mweb",  # Force web clients (avoid DRM issues)
            "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",  # Your Chrome user agent
            "--extractor-args", "youtube:player_skip=configs",  # Skip problematic YouTube player config checks
            "-o", output_template,
            video_url
        ]
        
        # Run yt-dlp
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Always log yt-dlp stdout/stderr for debugging (even on success)
        if result.stdout.strip():
            logger.debug(f"yt-dlp stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            # Log stderr at debug level for troubleshooting
            logger.debug(f"yt-dlp stderr: {result.stderr.strip()}")
            
            # Check for specific YouTube issues and log them appropriately
            stderr_lower = result.stderr.lower()
            if "some tv client https formats have been skipped as they are drm protected" in stderr_lower:
                logger.info("YouTube DRM warning detected (TV client formats skipped) - using web client fallback")
            if "some web client https formats have been skipped" in stderr_lower:
                logger.info("YouTube web client format issues detected - may affect quality")
            if "youtube is forcing sabr streaming" in stderr_lower:
                logger.info("YouTube SABR streaming detected - handled by player config bypass")
        
        if result.returncode == 0:
            # Try to find the downloaded file
            if custom_filename:
                # With custom filename, we know exactly what file to expect (thread-safe)
                expected_file = f"{custom_filename}.{audio_format}"
                file_path = os.path.join(output_dir, expected_file)
                
                if os.path.exists(file_path):
                    # File exists as expected
                    pass
                else:
                    # Fallback: search for the file in case yt-dlp modified the name
                    files = os.listdir(output_dir)
                    matching_files = [f for f in files if f.startswith(custom_filename) and f.endswith(f'.{audio_format}')]
                    if matching_files:
                        file_path = os.path.join(output_dir, matching_files[0])
                    else:
                        return {"status": 404, "error": f"Expected file {expected_file} not found after download"}
            else:
                # Legacy mode: find most recent file (race condition prone)
                files = os.listdir(output_dir)
                audio_files = [f for f in files if f.endswith(f'.{audio_format}')]
                
                if audio_files:
                    latest_file = max(audio_files, key=lambda f: os.path.getctime(os.path.join(output_dir, f)))
                    file_path = os.path.join(output_dir, latest_file)
                else:
                    return {"status": 404, "error": "No audio files found after download"}
            
            # Return success for both custom and legacy modes
            return {
                "status": 200,
                "path": file_path,
                "message": "Download successful"
            }
        else:
            # Log detailed failure information
            logger.error(f"yt-dlp failed with return code {result.returncode}")
            logger.error(f"yt-dlp command: {' '.join(cmd)}")
            
            # Check if it's a bot detection blocking error
            if detect_youtube_bot_blocking(result.stderr):
                logger.warning("YouTube bot detection triggered - applying smart delay")
                
                # Calculate context-aware delay with real batch and song context
                delay = calculate_smart_bot_delay(
                    thread_count=thread_count,
                    recent_failure_count=batch_failure_count,
                    recent_attempt_count=batch_attempt_count,
                    song_failures=song_failure_count,
                    song_attempts=song_attempt_count
                )
                
                logger.info(f"Bot detection delay: {delay:.1f} seconds")
                time.sleep(delay)
                
                return {
                    "status": 500,
                    "error": "DL_BOT_DETECTED",
                    "delay_applied": delay,
                    "retry_recommended": True,
                    "stderr": result.stderr
                }
            elif "video unavailable" in result.stderr.lower():
                logger.warning("Video unavailable detected")
                return {
                    "status": 500,
                    "error": f"Video unavailable: {result.stderr}"
                }
            elif "the downloaded file is empty" in result.stderr.lower():
                logger.warning("Empty file download - likely DRM or format extraction issue")
                return {
                    "status": 500,
                    "error": f"Empty file downloaded (DRM/format issue): {result.stderr}"
                }
            elif "private video" in result.stderr.lower() or "this video is private" in result.stderr.lower():
                logger.info("Video is private - expected failure")
                return {
                    "status": 404,
                    "error": f"Video is private: {result.stderr}"
                }
            else:
                logger.error(f"Unknown yt-dlp failure: {result.stderr}")
                return {
                    "status": 500,
                    "error": f"yt-dlp failed: {result.stderr}"
                }
                
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timeout after 5 minutes for URL: {video_url}")
        return {
            "status": 500,
            "error": "Download timeout (5 minutes)"
        }
    except Exception as e:
        logger.exception(f"Unexpected error in yt-dlp download: {str(e)}")
        logger.debug(f"Failed URL: {video_url}")
        logger.debug(f"Output directory: {output_dir}")
        return {
            "status": 500,
            "error": f"Unexpected error: {str(e)}"
        }

def run_yt_dlp(video_url, output_dir, audio_format="mp3", audio_quality="0", custom_filename=None):
    """
    Compatibility wrapper for run_yt_dlp_with_context
    Uses default context values for backwards compatibility
    """
    return run_yt_dlp_with_context(
        video_url=video_url,
        output_dir=output_dir, 
        audio_format=audio_format,
        audio_quality=audio_quality,
        custom_filename=custom_filename,
        thread_count=1,
        batch_failure_count=0,
        batch_attempt_count=0,
        song_failure_count=0,
        song_attempt_count=0
    )

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
        logger.warning(f"Error finding lyrics video for '{song_name}' by '{artist_name}': {e}")
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
        
        # Log search command output for debugging
        if result.stderr.strip():
            logger.debug(f"yt-dlp search stderr: {result.stderr.strip()}")
        
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
        logger.warning(f"Error searching YouTube for query '{query}': {e}")
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
            logger.debug(f"Song duration: {duration_seconds} seconds ({duration_ms}ms)")
            return duration_seconds
    except Exception as e:
        logger.warning(f"Could not get song duration: {e}")
    return None