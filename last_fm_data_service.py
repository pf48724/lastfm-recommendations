import requests
import logging
import time
import random
from last_fm_auth import get_lastfm_api_key, get_lastfm_api_url

logger = logging.getLogger(__name__)

def retry_api_call(func, max_retries=3, delay=1, *args, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API call failed (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                sleep_time = delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                logger.error("Max retries reached, giving up.")
                raise

def make_lastfm_request(method, params=None):
    if params is None:
        params = {}
    
    api_key = get_lastfm_api_key()
    api_url = get_lastfm_api_url()
    
    params.update({
        'method': method,
        'api_key': api_key,
        'format': 'json'
    })
    
    logger.info(f"Making Last.fm API request: {method} with params: {params}")
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    return response.json()

def get_user_top_tracks(username, period='overall', limit=50):
    try:
        params = {
            'user': username,
            'period': period,
            'limit': limit
        }
        
        response = retry_api_call(make_lastfm_request, 3, 1, 'user.gettoptracks', params)
        
        if 'toptracks' in response and 'track' in response['toptracks']:
            return response['toptracks']['track']
        else:
            logger.error("Unexpected response format from Last.fm API")
            return []
    except Exception as e:
        logger.error(f"Failed to get top tracks: {str(e)}")
        return []

def get_track_tags(artist_name, track_name, limit=10):
    try:
        params = {
            'artist': artist_name,
            'track': track_name,
            'limit': limit
        }
        
        response = retry_api_call(make_lastfm_request, 3, 1, 'track.gettoptags', params)
        
        if 'toptags' in response and 'tag' in response['toptags']:
            return response['toptags']['tag']
        else:
            logger.error(f"Unexpected response format from Last.fm API for track {track_name}")
            return []
    except Exception as e:
        logger.error(f"Failed to get tags for track {track_name}: {str(e)}")
        return []

def get_tracks_by_tag(tag_name, limit=50):
    try:
        params = {
            'tag': tag_name,
            'limit': limit
        }
        
        logger.info(f"Requesting top tracks for tag: {tag_name}")
        response = retry_api_call(make_lastfm_request, 3, 1, 'tag.getTopTracks', params)
        
        if 'tracks' in response and 'track' in response['tracks']:
            tracks = response['tracks']['track']
            logger.info(f"Found {len(tracks)} tracks for tag: {tag_name}")
            return tracks
        else:
            logger.error(f"Unexpected response format from Last.fm API for tag {tag_name}")
            logger.error(f"Response: {response}")
            
            if 'error' in response:
                logger.error(f"Error code: {response.get('error')}, Message: {response.get('message')}")
            
            return []
    except Exception as e:
        logger.error(f"Failed to get tracks for tag {tag_name}: {str(e)}")
        return []

def get_similar_tracks(artist_name, track_name, limit=20):
    try:
        params = {
            'artist': artist_name,
            'track': track_name,
            'limit': limit
        }
        
        logger.info(f"Requesting similar tracks for {artist_name} - {track_name}")
        response = retry_api_call(make_lastfm_request, 3, 1, 'track.getsimilar', params)
        
        logger.info(f"Response keys: {response.keys()}")
        if 'similartracks' in response:
            logger.info(f"similartracks keys: {response['similartracks'].keys()}")
        
        if 'similartracks' in response and 'track' in response['similartracks']:
            similar_tracks = response['similartracks']['track']
            logger.info(f"Found {len(similar_tracks)} similar tracks for {artist_name} - {track_name}")
            return similar_tracks
        else:
            logger.error(f"Unexpected response format from Last.fm API for track {track_name}")
            logger.error(f"Response: {response}")
            
            if 'error' in response:
                logger.error(f"Error code: {response.get('error')}, Message: {response.get('message')}")
            
            return []
    except Exception as e:
        logger.error(f"Failed to get similar tracks for {track_name}: {str(e)}")
        return []
