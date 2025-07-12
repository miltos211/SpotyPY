import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
import os
import tempfile
import time
from urllib.parse import urlparse
import mimetypes

def detect_image_format(image_data):
    """Detect image format from binary data"""
    if image_data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    elif image_data.startswith(b'GIF8'):
        return 'image/gif'
    elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
        return 'image/webp'
    else:
        return 'image/jpeg'  # Default fallback

def get_youtube_thumbnail_urls(youtube_data):
    """Extract thumbnail URLs from YouTube data in order of preference"""
    urls = []
    
    if not youtube_data or not isinstance(youtube_data, dict):
        return urls
    
    snippet = youtube_data.get('snippet', {})
    thumbnails = snippet.get('thumbnails', {})
    
    # Order of preference: high, medium, default
    for quality in ['high', 'medium', 'default']:
        if quality in thumbnails and 'url' in thumbnails[quality]:
            url = thumbnails[quality]['url']
            # Try to get higher resolution version
            if quality == 'high':
                # Try maxres version
                high_res = url.replace('/hqdefault.jpg', '/maxresdefault.jpg')
                urls.append(high_res)
            urls.append(url)
    
    return urls

def fetch_spotify_cover_url(spotify_url):
    """
    Calls Spotify's oEmbed endpoint and retrieves the album cover URL.
    Returns the 640x640 version if available.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(
            "https://open.spotify.com/oembed", 
            params={"url": spotify_url},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        thumbnail_url = data.get("thumbnail_url")
        if not thumbnail_url:
            return { "status": 400, "error": "No thumbnail_url in oEmbed response" }

        # Try multiple resolution options
        urls = []
        
        # Try 640x640 (high quality)
        high_res_url = thumbnail_url.replace("300x300", "640x640")
        urls.append(high_res_url)
        
        # Fallback to original
        urls.append(thumbnail_url)
        
        return { "status": 200, "urls": urls }

    except Exception as e:
        return { "status": 400, "error": str(e) }

def download_image(image_url, max_retries=3):
    """
    Downloads the image from a URL with retries.
    Returns { status: 200, data: <bytes>, mime_type: str } or { status: 400, error: str }
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                image_url, 
                headers=headers, 
                timeout=15,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check if we got actual image data
            content = response.content
            if len(content) < 100:  # Too small to be a real image
                raise Exception(f"Downloaded content too small ({len(content)} bytes)")
            
            # Detect actual image format
            mime_type = detect_image_format(content)
            
            return { 
                "status": 200, 
                "data": content, 
                "mime_type": mime_type,
                "size": len(content)
            }
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
                continue
            return { "status": 400, "error": f"Failed after {max_retries} attempts: {str(e)}" }
    
    return { "status": 400, "error": "Max retries exceeded" }

def embed_cover_art(file_path, image_bytes, mime_type='image/jpeg'):
    """
    Embeds image_bytes into the given MP3 file as album artwork.
    Returns { status: 200 } or { status: 400, error: str }
    """
    try:
        # Validate inputs
        if not os.path.exists(file_path):
            return { "status": 400, "error": "MP3 file does not exist" }
        
        if not image_bytes or len(image_bytes) < 100:
            return { "status": 400, "error": "Invalid image data" }
        
        # Load the MP3 file
        audio = MP3(file_path, ID3=ID3)

        # Ensure ID3 tags exist
        if audio.tags is None:
            audio.add_tags()

        # Remove existing album art to avoid duplicates
        # Look for existing APIC frames
        existing_apic_keys = [key for key in audio.tags.keys() if key.startswith('APIC')]
        for key in existing_apic_keys:
            del audio.tags[key]

        # Add new album art
        audio.tags.add(
            APIC(
                encoding=3,         # UTF-8
                mime=mime_type,     # Use detected mime type
                type=3,             # Cover (front)
                desc='Album Cover',
                data=image_bytes
            )
        )

        # Save with backup
        audio.save(v2_version=3)  # Use ID3v2.3 for better compatibility
        
        return { "status": 200, "size": len(image_bytes), "mime_type": mime_type }

    except Exception as e:
        return { "status": 400, "error": f"Failed to embed artwork: {str(e)}" }

def try_multiple_sources(url_list, source_name=""):
    """Try downloading from multiple URLs until one succeeds"""
    for i, url in enumerate(url_list):
        if not url:
            continue
            
        result = download_image(url)
        if result["status"] == 200:
            return result
        
        # Log the failure but continue trying
        print(f"    {source_name} source {i+1} failed: {result.get('error', 'Unknown error')}")
    
    return { "status": 400, "error": f"All {source_name} sources failed" }

def embed_art_from_enriched(enriched_entry, file_path):
    """
    Enhanced pipeline: tries multiple sources for album artwork.
    Priority: Spotify oEmbed -> YouTube thumbnails -> Fallback
    Returns { status: 200 } or { status: 400, error: str }
    """
    try:
        # Extract data from enriched entry
        spotify = enriched_entry.get("spotify", {})
        youtube = enriched_entry.get("youtube", {})
        
        spotify_url = spotify.get("spotify_url")
        track_name = spotify.get("name", "Unknown Track")
        artist_names = spotify.get("artists", ["Unknown Artist"])
        
        print(f"    Fetching artwork for: {track_name} by {', '.join(artist_names)}")
        
        # Source 1: Try Spotify oEmbed (best quality, but often fails)
        spotify_success = False
        if spotify_url:
            print(f"    Trying Spotify oEmbed...")
            cover_result = fetch_spotify_cover_url(spotify_url)
            if cover_result["status"] == 200:
                result = try_multiple_sources(cover_result["urls"], "Spotify")
                if result["status"] == 200:
                    print(f"    ✓ Spotify artwork downloaded ({result['size']} bytes)")
                    embed_result = embed_cover_art(file_path, result["data"], result["mime_type"])
                    if embed_result["status"] == 200:
                        return embed_result
                    print(f"    Spotify embed failed: {embed_result.get('error')}")
                else:
                    print(f"    Spotify download failed: {result.get('error')}")
            else:
                print(f"    Spotify oEmbed failed: {cover_result.get('error')}")
        
        # Source 2: Try YouTube thumbnails (fallback)
        if youtube:
            print(f"    Trying YouTube thumbnails...")
            youtube_urls = get_youtube_thumbnail_urls(youtube)
            if youtube_urls:
                result = try_multiple_sources(youtube_urls, "YouTube")
                if result["status"] == 200:
                    print(f"    ✓ YouTube thumbnail downloaded ({result['size']} bytes)")
                    embed_result = embed_cover_art(file_path, result["data"], result["mime_type"])
                    if embed_result["status"] == 200:
                        return embed_result
                    print(f"    YouTube embed failed: {embed_result.get('error')}")
                else:
                    print(f"    YouTube thumbnails failed: {result.get('error')}")
            else:
                print(f"    No YouTube thumbnail URLs found")
        
        # If we get here, all sources failed
        return { 
            "status": 400, 
            "error": "No artwork sources succeeded. Tried Spotify oEmbed and YouTube thumbnails." 
        }

    except Exception as e:
        return { "status": 400, "error": f"Artwork pipeline error: {str(e)}" }
