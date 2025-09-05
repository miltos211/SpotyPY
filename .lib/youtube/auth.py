import os
import pickle
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import proper logging system
from utils.logging import get_logger

# Initialize logger for this module
logger = get_logger("youtube_auth")

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/youtube"]

def get_youtube_client():
    """Authenticate via OAuth and return an authorized YouTube API client. Reuses token if available."""
    logger.debug("Initializing YouTube Data API client")
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), "token.pickle")

    # Load token if it exists
    if os.path.exists(token_path):
        logger.debug(f"Loading existing YouTube token from: {token_path}")
        try:
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
            logger.debug("YouTube token loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YouTube token: {type(e).__name__}: {e}")
            logger.warning("Will attempt fresh OAuth authentication")
    else:
        logger.debug("No existing YouTube token found - will need OAuth authentication")

    # If no (valid) token, refresh or prompt login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired YouTube credentials")
            try:
                creds.refresh(Request())
                logger.info("YouTube credential refresh successful")
            except Exception as e:
                logger.error(f"YouTube credential refresh failed: {type(e).__name__}: {e}")
                logger.warning("Will attempt fresh OAuth authentication")
                creds = None  # Force fresh auth
        
        if not creds:  # Fresh auth needed
            logger.info("Starting fresh YouTube OAuth authentication flow")
            # Validate environment variables
            client_id = os.getenv("YT_CLIENT_ID")
            client_secret = os.getenv("YT_CLIENT_SECRET")
            redirect_uri = os.getenv("YT_REDIRECT_URI")
            
            if not all([client_id, client_secret, redirect_uri]):
                missing = [name for name, val in [('YT_CLIENT_ID', client_id), ('YT_CLIENT_SECRET', client_secret), ('YT_REDIRECT_URI', redirect_uri)] if not val]
                logger.error(f"Missing YouTube OAuth environment variables: {', '.join(missing)}")
                raise ValueError(f"Missing required YouTube OAuth config: {', '.join(missing)}")
            
            logger.debug("Creating YouTube OAuth flow configuration")
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": [redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            
            try:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                logger.info("Starting local OAuth server for YouTube authentication...")
                creds = flow.run_local_server(port=0)
                logger.info("YouTube OAuth authentication completed successfully")
            except Exception as e:
                logger.error(f"YouTube OAuth flow failed: {type(e).__name__}: {e}")
                raise

        # Save token
        logger.debug(f"Saving YouTube token to: {token_path}")
        try:
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
            logger.info("YouTube token saved successfully")
        except Exception as e:
            logger.error(f"Failed to save YouTube token: {type(e).__name__}: {e}")
            logger.warning("Authentication will be required on next run")

    # Build and test YouTube API client
    logger.debug("Building YouTube Data API v3 client")
    try:
        youtube_client = build("youtube", "v3", credentials=creds)
        logger.info("YouTube Data API client created successfully")
        return youtube_client
    except Exception as e:
        logger.error(f"Failed to create YouTube API client: {type(e).__name__}: {e}")
        raise
