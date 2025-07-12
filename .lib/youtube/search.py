import re

def normalize_string(s):
    """Lowercase and remove non-alphanumeric characters for loose matching."""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def search_youtube_track(track, yt_client, return_debug=False):
    """
    Search YouTube for a track using ISRC and validate results based on metadata.
    Returns a YouTube video URL if a good match is found, else None.
    If return_debug=True, also returns: (query, full response, matched item)
    """
    isrc = track.get("isrc")
    if not isrc:
        return (None, None, None, None) if return_debug else None

    search_query = isrc

    # Perform search
    request = yt_client.search().list(
        q=search_query,
        part="snippet",
        maxResults=5,
        type="video"
    )
    response = request.execute()

    # Prepare reference metadata
    expected_artist = normalize_string(track["artists"][0])
    expected_title = normalize_string(track["name"])
    expected_duration_sec = track["duration_ms"] / 1000

    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        combined = normalize_string(title + " " + channel)

        if expected_title in combined and expected_artist in combined:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            return (youtube_url, search_query, response, item) if return_debug else youtube_url

    return (None, search_query, response, None) if return_debug else None
