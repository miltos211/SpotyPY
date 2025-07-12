import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Load environment variables from .env
load_dotenv()

# Define all scopes you might need — easy to edit later
SCOPE = (
    "user-read-private "
    "user-read-email "
    "user-top-read "
    "user-read-recently-played "
    "playlist-read-private "
    "user-follow-read"
)

def get_authenticated_client():
    """
    Returns an authenticated Spotify client using Spotipy.
    Will prompt the user the first time via browser.
    """
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))
    return sp

def authenticate_and_test():
    """
    Returns a status and basic user info if authentication succeeds.
    Can be used as a health check.
    """
    try:
        sp = get_authenticated_client()
        user = sp.current_user()
        return {
            "status": 200,
            "user": {
                "id": user.get("id"),
                "display_name": user.get("display_name"),
                "email": user.get("email"),
                "product": user.get("product"),
                "country": user.get("country"),
            }
        }
    except Exception as e:
        return {
            "status": 400,
            "error": str(e)
        }
