# .lib/spotify/utils.py

import re

def extract_playlist_id(playlist_input):
    """
    Extracts the playlist ID from a Spotify URL or returns it directly if it's already an ID.
    """
    match = re.search(r"(playlist/)?([a-zA-Z0-9]{22})", playlist_input)
    return match.group(2) if match else None
