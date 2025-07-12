import json
import os

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

        while True:
            batch = sp.current_user_playlists(limit=limit, offset=offset)
            items = batch.get("items", [])
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

        # Optional export
        if export_path:
            try:
                export_dir = os.path.dirname(export_path) or "."
                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(playlists, f, indent=2, ensure_ascii=False)
            except Exception as e:
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
        return {
            "status": 400,
            "error": str(e)
        }
