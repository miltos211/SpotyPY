import re
import json
import os

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

        while True:
            response = sp.playlist_items(playlist_id, limit=limit, offset=offset)
            items = response.get("items", [])

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

        # Optional export
        if export_path:
            try:
                export_dir = os.path.dirname(export_path) or "."
                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(all_tracks, f, indent=2, ensure_ascii=False)
            except Exception as e:
                return { "status": 400, "error": f"Failed to export: {str(e)}" }

        return { "status": 200, "tracks": all_tracks }

    except Exception as e:
        return { "status": 400, "error": str(e) }
