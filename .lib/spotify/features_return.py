# .lib/features_return.py

def get_available_features(sp):
    capabilities = {}

    # 1. Can fetch basic user info
    try:
        user = sp.current_user()
        capabilities['profile'] = True
    except Exception:
        capabilities['profile'] = False

    # 2. Can fetch user's playlists
    try:
        sp.current_user_playlists(limit=1)
        capabilities['playlists'] = True
    except Exception:
        capabilities['playlists'] = False

    # 3. Can fetch top tracks
    try:
        sp.current_user_top_tracks(limit=1)
        capabilities['top_tracks'] = True
    except Exception:
        capabilities['top_tracks'] = False

    # 4. Can fetch recently played
    try:
        sp.current_user_recently_played(limit=1)
        capabilities['recently_played'] = True
    except Exception:
        capabilities['recently_played'] = False

    # 5. Can follow artists (or check following)
    try:
        sp.current_user_followed_artists(limit=1)
        capabilities['followed_artists'] = True
    except Exception:
        capabilities['followed_artists'] = False

    return capabilities
