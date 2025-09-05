import re
import json
import os
import spotipy
from datetime import datetime

# Import proper logging system
from utils.logging import get_logger

# Initialize logger for this module
logger = get_logger("spotify_tracks")

def extract_playlist_id(playlist_input):
    """
    Extracts the playlist ID from a Spotify URL or returns it directly if it's already an ID.
    """
    match = re.search(r"(playlist/)?([a-zA-Z0-9]{22})", playlist_input)
    return match.group(2) if match else None

def get_tracks_from_playlist(sp, playlist_input, export_path=None):
    """
    Retrieves all tracks from the given playlist (by name or URL/ID).
    Optionally exports the results to a JSON file if export_path is provided.
    Returns { status: 200, tracks: [...] } or { status: 400, error: ... }
    """
    try:
        playlist_id = extract_playlist_id(playlist_input)
        if not playlist_id:
            return { "status": 400, "error": "Invalid playlist input" }

        limit = 100
        offset = 0
        all_tracks = []

        logger.debug(f"Fetching tracks from playlist: playlist_id={playlist_id}")
        
        while True:
            logger.debug(f"Spotify API call: playlist_items(limit={limit}, offset={offset})")
            try:
                response = sp.playlist_items(playlist_id, limit=limit, offset=offset)
                items = response.get("items", [])
                logger.debug(f"Spotify API success: got {len(items)} items (offset={offset})")
            except spotipy.SpotifyException as e:
                logger.error(f"Spotify API error: HTTP {e.http_status} - {e.reason}")
                if e.http_status == 429:  # Rate limiting
                    retry_after = getattr(e, 'headers', {}).get('retry-after', 'unknown')
                    logger.warning(f"Spotify rate limit hit: retry-after={retry_after}s")
                elif e.http_status == 404:
                    logger.error(f"Playlist not found: {playlist_id}")
                elif e.http_status == 403:
                    logger.error(f"Access denied to playlist: {playlist_id} (may be private)")
                return {"status": e.http_status, "error": f"Spotify API: {e.reason}"}
            except Exception as e:
                logger.error(f"Unexpected Spotify error: {type(e).__name__}: {e}")
                return {"status": 500, "error": f"Unexpected error: {str(e)}"}

            for item in items:
                track = item.get("track")
                if not track:
                    continue  # Skip null entries (e.g., removed songs)

                album = track.get("album", {})

                all_tracks.append({
                    "name": track.get("name"),
                    "artists": [artist["name"] for artist in track.get("artists", [])],
                    "album": album.get("name"),
                    "release_date": album.get("release_date"),
                    "explicit": track.get("explicit"),
                    "track_number": track.get("track_number"),
                    "disc_number": track.get("disc_number"),
                    "duration_ms": track.get("duration_ms"),
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                    "id": track.get("id"),
                    "isrc": track.get("external_ids", {}).get("isrc")
                })

            if response.get("next"):
                offset += limit
            else:
                break

        logger.info(f"Successfully fetched {len(all_tracks)} tracks from Spotify playlist")
        
        # Optional export
        if export_path:
            logger.debug(f"Exporting tracks to: {export_path}")
            try:
                export_dir = os.path.dirname(export_path) or "."
                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(all_tracks, f, indent=2, ensure_ascii=False)
                logger.info(f"Tracks exported successfully to {export_path}")
            except Exception as e:
                logger.error(f"Export failed: {type(e).__name__}: {e}")
                return { "status": 400, "error": f"Failed to export: {str(e)}" }

        return { "status": 200, "tracks": all_tracks }

    except Exception as e:
        logger.exception(f"Unexpected error in get_tracks_from_playlist: {str(e)}")
        return { "status": 400, "error": str(e) }

def get_liked_songs(sp, export_path=None, test_limit=None):
    """
    Retrieves liked songs from the user's Spotify library.
    Optionally exports the results to a JSON file if export_path is provided.
    
    Args:
        sp: Authenticated Spotify client
        export_path: Path to export JSON file (optional)
        test_limit: Limit number of tracks for testing (optional)
        
    Returns: 
        { status: 200, tracks: [...] } or { status: 400, error: ... }
    """
    try:
        limit = 50  # Spotify API max for liked songs
        offset = 0
        all_tracks = []

        logger.debug(f"Fetching liked songs from Spotify library")
        
        while True:
            # Apply test limit if specified
            if test_limit and len(all_tracks) >= test_limit:
                logger.info(f"Test limit reached: stopping at {len(all_tracks)} tracks")
                break
            
            logger.debug(f"Spotify API call: current_user_saved_tracks(limit={limit}, offset={offset})")
            try:
                response = sp.current_user_saved_tracks(limit=limit, offset=offset)
                items = response.get("items", [])
                logger.debug(f"Spotify API success: got {len(items)} liked songs (offset={offset})")
            except spotipy.SpotifyException as e:
                logger.error(f"Spotify API error: HTTP {e.http_status} - {e.reason}")
                if e.http_status == 429:  # Rate limiting
                    retry_after = getattr(e, 'headers', {}).get('retry-after', 'unknown')
                    logger.warning(f"Spotify rate limit hit: retry-after={retry_after}s")
                elif e.http_status == 403:
                    logger.error("Access denied to liked songs - check 'user-library-read' scope")
                return {"status": e.http_status, "error": f"Spotify API: {e.reason}"}
            except Exception as e:
                logger.error(f"Unexpected Spotify error: {type(e).__name__}: {e}")
                return {"status": 500, "error": f"Unexpected error: {str(e)}"}

            for item in items:
                # Apply test limit check per item
                if test_limit and len(all_tracks) >= test_limit:
                    break
                    
                track = item.get("track")
                if not track:
                    continue  # Skip null entries

                album = track.get("album", {})

                all_tracks.append({
                    "name": track.get("name"),
                    "artists": [artist["name"] for artist in track.get("artists", [])],
                    "album": album.get("name"),
                    "release_date": album.get("release_date"),
                    "explicit": track.get("explicit"),
                    "track_number": track.get("track_number"),
                    "disc_number": track.get("disc_number"),
                    "duration_ms": track.get("duration_ms"),
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                    "id": track.get("id"),
                    "isrc": track.get("external_ids", {}).get("isrc")
                })

            # Check if we have more tracks to fetch (unless test limit hit)
            if response.get("next") and (not test_limit or len(all_tracks) < test_limit):
                offset += limit
            else:
                break

        logger.info(f"Successfully fetched {len(all_tracks)} liked songs from Spotify")
        
        # Optional export with date-based naming
        if export_path:
            logger.debug(f"Exporting liked songs to: {export_path}")
            try:
                export_dir = os.path.dirname(export_path) or "."
                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(all_tracks, f, indent=2, ensure_ascii=False)
                logger.info(f"Liked songs exported successfully to {export_path}")
            except Exception as e:
                logger.error(f"Export failed: {type(e).__name__}: {e}")
                return { "status": 400, "error": f"Failed to export: {str(e)}" }

        return { "status": 200, "tracks": all_tracks }

    except Exception as e:
        logger.exception(f"Unexpected error in get_liked_songs: {str(e)}")
        return { "status": 400, "error": str(e) }

def generate_liked_songs_path(base_dir="out"):
    """
    Generate date-based path for liked songs export.
    Format: liked_songs_DD-MM-YY/liked_songs_DD-MM-YY.json
    
    Args:
        base_dir: Base directory for export (default: "out")
        
    Returns:
        tuple: (folder_path, json_path)
    """
    today = datetime.now().strftime("%d-%m-%y")
    folder_name = f"liked_songs_{today}"
    json_name = f"liked_songs_{today}.json"
    
    folder_path = os.path.join(base_dir, folder_name)
    json_path = os.path.join(folder_path, json_name)
    
    return folder_path, json_path
