import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Import proper logging system
from utils.logging import get_logger

# Initialize logger for this module
logger = get_logger("spotify_auth")

# Load environment variables from .env
load_dotenv()

# Define all scopes you might need — easy to edit later
SCOPE = (
    "user-read-private "
    "user-read-email "
    "user-top-read "
    "user-read-recently-played "
    "playlist-read-private "
    "user-follow-read "
    "user-library-read"
)

def get_authenticated_client():
    """
    Returns an authenticated Spotify client using Spotipy.
    Will prompt the user the first time via browser.
    """
    logger.debug("Initializing Spotify authentication")
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))
        logger.info("Spotify authentication successful")
        return sp
    except Exception as e:
        logger.error(f"Spotify authentication failed: {type(e).__name__}: {e}")
        raise

def authenticate_and_test():
    """
    Returns a status and basic user info if authentication succeeds.
    Can be used as a health check.
    """
    logger.debug("Testing Spotify authentication and fetching user info")
    try:
        sp = get_authenticated_client()
        logger.debug("Spotify API call: current_user()")
        user = sp.current_user()
        
        user_id = user.get("id")
        display_name = user.get("display_name")
        product = user.get("product")
        
        logger.info(f"Spotify auth test successful: user={user_id}, name={display_name}, product={product}")
        
        return {
            "status": 200,
            "user": {
                "id": user_id,
                "display_name": display_name,
                "email": user.get("email"),
                "product": product,
                "country": user.get("country"),
            }
        }
    except spotipy.SpotifyException as e:
        logger.error(f"Spotify API error during auth test: HTTP {e.http_status} - {e.reason}")
        if e.http_status == 401:
            logger.error("Spotify token expired or invalid - re-authentication needed")
        return {
            "status": e.http_status,
            "error": f"Spotify API: {e.reason}"
        }
    except Exception as e:
        logger.error(f"Unexpected error during Spotify auth test: {type(e).__name__}: {e}")
        return {
            "status": 400,
            "error": str(e)
        }
