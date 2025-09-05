import json
import os
import spotipy

# Import proper logging system
from utils.logging import get_logger

# Initialize logger for this module
logger = get_logger("spotify_playlists")

def get_user_playlists(sp, export_path=None):
    """
    Retrieves all playlists for the current user.
    Automatically handles pagination (in batches of 50).
    Optionally exports the results to a JSON file if export_path is provided.
    Returns a dictionary: { status: 200, count: X, playlists: [...] } or { status: 400, error: ... }
    """
    try:
        playlists = []
        limit = 50
        offset = 0

        logger.debug("Fetching user playlists from Spotify")
        
        while True:
            logger.debug(f"Spotify API call: current_user_playlists(limit={limit}, offset={offset})")
            try:
                batch = sp.current_user_playlists(limit=limit, offset=offset)
                items = batch.get("items", [])
                logger.debug(f"Spotify API success: got {len(items)} playlists (offset={offset})")
            except spotipy.SpotifyException as e:
                logger.error(f"Spotify API error: HTTP {e.http_status} - {e.reason}")
                if e.http_status == 429:  # Rate limiting
                    retry_after = getattr(e, 'headers', {}).get('retry-after', 'unknown')
                    logger.warning(f"Spotify rate limit hit: retry-after={retry_after}s")
                elif e.http_status == 401:
                    logger.error("Spotify authentication failed - token may be expired")
                return {"status": e.http_status, "error": f"Spotify API: {e.reason}"}
            except Exception as e:
                logger.error(f"Unexpected Spotify error: {type(e).__name__}: {e}")
                return {"status": 500, "error": f"Unexpected error: {str(e)}"}
            playlists.extend([
                {
                    "name": pl.get("name"),
                    "id": pl.get("id"),
                    "tracks": pl["tracks"]["total"],
                    "public": pl.get("public"),
                    "url": pl["external_urls"]["spotify"],
                    "owner": pl.get("owner", {}).get("display_name"),
                    "snapshot_id": pl.get("snapshot_id")
                }
                for pl in items
            ])

            if batch.get("next"):
                offset += limit
            else:
                break

        logger.info(f"Successfully fetched {len(playlists)} playlists from Spotify")
        
        # Optional export
        if export_path:
            logger.debug(f"Exporting playlists to: {export_path}")
            try:
                export_dir = os.path.dirname(export_path) or "."
                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(playlists, f, indent=2, ensure_ascii=False)
                logger.info(f"Playlists exported successfully to {export_path}")
            except Exception as e:
                logger.error(f"Export failed: {type(e).__name__}: {e}")
                return {
                    "status": 400,
                    "error": f"Failed to export: {str(e)}"
                }

        return {
            "status": 200,
            "count": len(playlists),
            "playlists": playlists
        }

    except Exception as e:
        logger.exception(f"Unexpected error in get_user_playlists: {str(e)}")
        return {
            "status": 400,
            "error": str(e)
        }
