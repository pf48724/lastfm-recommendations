import os
from dotenv import load_dotenv

load_dotenv()

def get_lastfm_api_key():
    return os.getenv("LASTFM_API_KEY")

def get_lastfm_api_secret():
    return os.getenv("LASTFM_API_SECRET")

def get_lastfm_api_url():
    return "http://ws.audioscrobbler.com/2.0/"
