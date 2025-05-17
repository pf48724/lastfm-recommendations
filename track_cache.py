import os
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_DIR = "cache"
TAG_TRACKS_CACHE_FILE = os.path.join(CACHE_DIR, "tag_tracks_cache.json")
CACHE_EXPIRY_DAYS = 7

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def load_tag_tracks_cache():
    ensure_cache_dir()
    if not os.path.exists(TAG_TRACKS_CACHE_FILE):
        return {"last_updated": time.time(), "tags": {}}
    
    try:
        with open(TAG_TRACKS_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            logger.info(f"Loaded cache with {len(cache.get('tags', {}))} tags")
            return cache
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        return {"last_updated": time.time(), "tags": {}}

def save_tag_tracks_cache(cache):
    ensure_cache_dir()
    try:
        with open(TAG_TRACKS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
            logger.info(f"Saved cache with {len(cache.get('tags', {}))} tags")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def get_tracks_for_tag(tag, get_tracks_func, limit=50, force_refresh=False):
    cache = load_tag_tracks_cache()
    
    cache_age = time.time() - cache.get("last_updated", 0)
    cache_expired = cache_age > (CACHE_EXPIRY_DAYS * 24 * 60 * 60)
    
    if force_refresh or cache_expired:
        logger.info(f"Cache {'expired' if cache_expired else 'refresh forced'}, clearing")
        cache = {"last_updated": time.time(), "tags": {}}
    
    if tag in cache.get("tags", {}) and not force_refresh:
        logger.info(f"Using cached tracks for tag '{tag}'")
        return cache["tags"][tag]
    
    logger.info(f"Fetching tracks for tag '{tag}' from API")
    tracks = get_tracks_func(tag, limit)
    
    if "tags" not in cache:
        cache["tags"] = {}
    cache["tags"][tag] = tracks
    cache["last_updated"] = time.time()
    
    save_tag_tracks_cache(cache)
    
    return tracks

def clear_cache():
    ensure_cache_dir()
    if os.path.exists(TAG_TRACKS_CACHE_FILE):
        os.remove(TAG_TRACKS_CACHE_FILE)
        logger.info("Cache cleared")
