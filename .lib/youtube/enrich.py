from .search import search_youtube_track

def enrich_tracks_with_youtube(tracks, yt_client, verbose=False):
    """
    Given a list of Spotify tracks, return a list of dicts with full Spotify + YouTube info.
    Each entry will be:
    {
        "spotify": { ... original track ... },
        "youtube": { ... matched YouTube item ... }  # or None if no match
    }
    """
    enriched = []
    total = len(tracks)
    matched = 0

    for i, track in enumerate(tracks, 1):
        if verbose:
            print(f"[{i}/{total}] Searching: {track['name']} by {', '.join(track['artists'])}")

        youtube_url, search_query, response_data, matched_item = search_youtube_track(
            track,
            yt_client,
            return_debug=True
        )

        if matched_item:
            matched += 1

        enriched.append({
            "spotify": track,
            "youtube": matched_item
        })

    if verbose:
        print(f"\n✅ Enrichment complete! Matched {matched}/{total} tracks.")

    return enriched
