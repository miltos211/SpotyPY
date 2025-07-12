import os
import pickle
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/youtube"]

def get_youtube_client():
    """Authenticate via OAuth and return an authorized YouTube API client. Reuses token if available."""
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), "token.pickle")

    # Load token if it exists
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # If no (valid) token, refresh or prompt login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": os.getenv("YT_CLIENT_ID"),
                    "client_secret": os.getenv("YT_CLIENT_SECRET"),
                    "redirect_uris": [os.getenv("YT_REDIRECT_URI")],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)
