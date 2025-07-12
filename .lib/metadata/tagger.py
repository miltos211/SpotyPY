import os
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

def clean_string(text, max_length=None):
    """Clean and validate string input"""
    if not text:
        return ""
    
    # Convert to string and strip
    text = str(text).strip()
    
    # Remove control characters and fix encoding issues
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Truncate if too long
    if max_length and len(text) > max_length:
        text = text[:max_length].strip()
    
    return text

def extract_title_from_filename(filename):
    """Extract a reasonable title from filename as fallback"""
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Clean up common patterns
    name = re.sub(r'\s*\(feat\..*?\)', '', name)  # Remove feat. parts
    name = re.sub(r'\s*\[.*?\]', '', name)        # Remove bracketed content
    name = re.sub(r'\s*-\s*Official.*', '', name, flags=re.IGNORECASE)  # Remove "Official Video" etc
    
    return name.strip()

def validate_artist_name(artist):
    """Check if artist name looks suspicious (too short, weird chars)"""
    if not artist:
        return False
    
    # Flag suspiciously short names (likely truncated)
    if len(artist) <= 2:
        return False
    
    # Flag names with weird patterns
    if re.match(r'^[A-Z]{1,3}$', artist):  # All caps, very short
        return False
    
    return True

def tag_mp3(file_path, metadata):
    """
    Applies metadata to an MP3 file using Spotify metadata.
    Overwrites any existing tags.
    metadata = {
        "title": str,
        "artists": [str, ...],
        "album": str,
        "release_date": str (YYYY or YYYY-MM-DD),
        "track_number": int,
        "disc_number": int,
        "duration_ms": int,
        "explicit": bool,
        "isrc": str,
        "spotify_id": str,
        "spotify_url": str
    }
    """
    try:
        # Check if file exists and is valid
        if not os.path.exists(file_path):
            return { "status": 400, "error": "File does not exist" }
        
        if os.path.getsize(file_path) == 0:
            return { "status": 400, "error": "File is empty" }

        # Load audio file
        audio = MP3(file_path, ID3=ID3)

        # Remove existing tags completely (overwrite)
        audio.delete()
        audio.save()

        # Now re-tag from scratch
        audio_tags = EasyID3()
        
        # Handle title - ensure it's not empty and reasonable
        title = clean_string(metadata.get("title", ""), max_length=200)
        if not title:
            # Fallback to filename
            filename = os.path.basename(file_path)
            title = extract_title_from_filename(filename)
        
        if not title:
            title = "Unknown Title"
        
        audio_tags["title"] = title
        
        # Handle artists - support multiple artists and ensure not empty
        artists = metadata.get("artists", [])
        primary_artist = None
        all_artists = []
        
        if isinstance(artists, list) and artists:
            # Clean artist names but don't be too strict with validation for Spotify data
            valid_artists = []
            for artist in artists:
                cleaned = clean_string(artist, max_length=100)
                if cleaned:
                    valid_artists.append(cleaned)
            
            if valid_artists:
                primary_artist = valid_artists[0]
                all_artists = valid_artists
        elif isinstance(artists, str):
            cleaned = clean_string(artists, max_length=100)
            if cleaned:
                primary_artist = cleaned
                all_artists = [cleaned]
        
        # If no valid artist found, use Unknown Artist
        if not primary_artist:
            primary_artist = "Unknown Artist"
            all_artists = ["Unknown Artist"]
        
        audio_tags["artist"] = primary_artist
        if len(all_artists) > 1:
            audio_tags["albumartist"] = ", ".join(all_artists)
        
        # Handle album
        album = clean_string(metadata.get("album", ""), max_length=200)
        if not album:
            album = "Unknown Album"
        audio_tags["album"] = album

        # Handle release date
        if metadata.get("release_date"):
            try:
                release_date = clean_string(metadata["release_date"])
                year = release_date.split("-")[0]
                if year.isdigit() and len(year) == 4 and 1900 <= int(year) <= 2030:
                    audio_tags["date"] = year
            except (IndexError, AttributeError, ValueError):
                pass  # Skip if date format is invalid
        
        # Handle track number
        if metadata.get("track_number"):
            try:
                track_num = int(metadata["track_number"])
                if 1 <= track_num <= 999:  # Reasonable range
                    audio_tags["tracknumber"] = str(track_num)
            except (ValueError, TypeError):
                pass  # Skip if track number is invalid
        
        # Handle disc number
        if metadata.get("disc_number"):
            try:
                disc_num = int(metadata["disc_number"])
                if 1 <= disc_num <= 99:  # Reasonable range
                    audio_tags["discnumber"] = str(disc_num)
            except (ValueError, TypeError):
                pass  # Skip if disc number is invalid

        # Handle genre if available
        if metadata.get("genre"):
            genres = metadata.get("genre")
            if isinstance(genres, list) and genres:
                genre = clean_string(genres[0], max_length=50)
                if genre:
                    audio_tags["genre"] = genre
            elif isinstance(genres, str):
                genre = clean_string(genres, max_length=50)
                if genre:
                    audio_tags["genre"] = genre
        
        # Handle ISRC (International Standard Recording Code) - CRITICAL for MusicBrainz Picard!
        if metadata.get("isrc"):
            isrc = clean_string(metadata["isrc"], max_length=12)
            if isrc and len(isrc) == 12:  # ISRC should be exactly 12 characters
                audio_tags["isrc"] = isrc
        
        # Handle duration - convert from milliseconds to seconds for some players
        if metadata.get("duration_ms"):
            try:
                duration_ms = int(metadata["duration_ms"])
                if duration_ms > 0:
                    duration_seconds = duration_ms / 1000
                    audio_tags["length"] = str(int(duration_seconds))
            except (ValueError, TypeError):
                pass
        
        # Handle explicit content flag
        if metadata.get("explicit") is not None:
            try:
                explicit = bool(metadata["explicit"])
                audio_tags["explicit"] = "1" if explicit else "0"
            except (ValueError, TypeError):
                pass
        
        # Handle Spotify ID and URL as custom fields (for reference)
        # Note: EasyID3 doesn't support "comment" field, so we'll use "website" for URL
        if metadata.get("spotify_url"):
            spotify_url = clean_string(metadata["spotify_url"], max_length=200)
            if spotify_url:
                audio_tags["website"] = spotify_url

        # Save to file
        audio_tags.save(file_path)
        
        # Verify the file still exists and has content after tagging
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return { "status": 400, "error": "File corrupted during tagging" }
        
        return { "status": 200 }

    except Exception as e:
        return { "status": 400, "error": f"Tagging failed: {str(e)}" }

def clean_youtube_title(title):
    """Clean up YouTube title for better metadata"""
    if not title:
        return ""
    
    # Remove common YouTube suffixes
    suffixes_to_remove = [
        r'\s*\(Official\s+Music\s+Video\)',
        r'\s*\(Official\s+Video\)',
        r'\s*\(Lyrics?\)',
        r'\s*\(Lyric\s+Video\)',
        r'\s*\[Official\s+Music\s+Video\]',
        r'\s*\[Official\s+Video\]',
        r'\s*\[Lyrics?\]',
        r'\s*\[Lyric\s+Video\]',
        r'\s*\|\s*Official\s+Music\s+Video',
        r'\s*-\s*Official\s+Music\s+Video',
        r'\s*\(HD\)',
        r'\s*\[HD\]',
        r'\s*\(4K\)',
        r'\s*\[4K\]',
    ]
    
    cleaned = title
    for suffix in suffixes_to_remove:
        cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

def tag_from_enriched(enriched_entry, file_path):
    """
    Extracts metadata from enriched JSON entry and applies it to the audio file.
    Returns { status, error? }
    """
    try:
        spotify = enriched_entry.get("spotify", {})
        
        # Prioritize Spotify data - it's usually the most reliable
        meta = {}
        
        # Title - prefer Spotify name
        if spotify.get("name"):
            meta["title"] = clean_string(spotify["name"])
        
        # Artists - prefer Spotify artists
        if spotify.get("artists") and isinstance(spotify["artists"], list):
            # Spotify artists are usually clean, just validate they're not empty
            valid_artists = [clean_string(artist) for artist in spotify["artists"] if clean_string(artist)]
            if valid_artists:
                meta["artists"] = valid_artists
        
        # Album - prefer Spotify album
        if spotify.get("album"):
            meta["album"] = clean_string(spotify["album"])
        
        # Release date - prefer Spotify release_date
        if spotify.get("release_date"):
            meta["release_date"] = clean_string(spotify["release_date"])
        
        # Track number - prefer Spotify track_number
        if spotify.get("track_number"):
            meta["track_number"] = spotify["track_number"]
        
        # Disc number - from Spotify
        if spotify.get("disc_number"):
            meta["disc_number"] = spotify["disc_number"]
        
        # Duration - from Spotify
        if spotify.get("duration_ms"):
            meta["duration_ms"] = spotify["duration_ms"]
        
        # Explicit flag - from Spotify
        if spotify.get("explicit") is not None:
            meta["explicit"] = spotify["explicit"]
        
        # ISRC - CRITICAL for MusicBrainz Picard matching!
        if spotify.get("isrc"):
            meta["isrc"] = spotify["isrc"]
        
        # Spotify ID and URL for reference
        if spotify.get("id"):
            meta["spotify_id"] = spotify["id"]
        
        if spotify.get("spotify_url"):
            meta["spotify_url"] = spotify["spotify_url"]
        
        # Add genre if available (Spotify usually doesn't have this in track data)
        if spotify.get("genres"):
            meta["genre"] = spotify.get("genres")
        
        # Fallback to YouTube only if Spotify data is missing
        if not meta.get("title"):
            youtube = enriched_entry.get("youtube", {})
            snippet = youtube.get("snippet", {})
            yt_title = snippet.get("title", "")
            
            if yt_title:
                cleaned_title = clean_youtube_title(yt_title)
                if cleaned_title:
                    meta["title"] = cleaned_title
        
        # Final fallback: use filename if still no title
        if not meta.get("title"):
            filename = os.path.basename(file_path)
            meta["title"] = extract_title_from_filename(filename)
        
        # Ensure we have at least a title
        if not meta.get("title"):
            meta["title"] = "Unknown Title"
        
        return tag_mp3(file_path, meta)

    except Exception as e:
        return { "status": 400, "error": f"Metadata extract error: {str(e)}" }