import logging
import pandas as pd
import random
from recommender import Recommender
from last_fm_data_service import get_track_tags as api_get_track_tags, get_similar_tracks as api_get_similar_tracks, get_tracks_by_tag as api_get_tracks_by_tag
from track_cache import get_tracks_for_tag

logger = logging.getLogger(__name__)
tag_cache = {}

def get_track_tags(artist, name):
    key = f"{artist}|{name}".lower()
    if key not in tag_cache:
        tag_cache[key] = api_get_track_tags(artist, name)
    return tag_cache[key]

def prepare_track_data(tracks):
    tracks_data = []
    for track in tracks:
        artist_name = track.get('artist', {}).get('name', 'Unknown') if isinstance(track.get('artist'), dict) else track.get('artist', 'Unknown')
        track_name = track.get('name', 'Unknown')
        track_data = {
            'name': track_name,
            'artist': artist_name,
            'playcount': int(track.get('playcount', 0)),
            'listeners': int(track.get('listeners', 0)) if 'listeners' in track else 0,
            'mbid': track.get('mbid', ''),
            'url': track.get('url', '')
        }
        tags = get_track_tags(artist_name, track_name)
        if not tags:
            continue
        for i, tag in enumerate(tags[:10]):
            tag_name = tag.get('name', '').lower()
            tag_weight = float(tag.get('count', 0))
            if tag_name:
                track_data[f'tag_{i}_name'] = tag_name
                track_data[f'tag_{i}_weight'] = tag_weight
        tracks_data.append(track_data)
    return tracks_data, len(tracks_data) > 0

def create_tag_vector(track_tags, all_possible_tags):
    vector = [0.0] * len(all_possible_tags)
    tag_weights = {tag['name'].lower(): float(tag.get('count', 0)) for tag in track_tags if 'name' in tag}
    for i, tag in enumerate(all_possible_tags):
        if tag in tag_weights:
            vector[i] = tag_weights[tag]
    return vector

def cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

def find_similar_tracks_vector(source_track, candidate_tracks, num_similar=5):
    all_tags = set()
    source_artist = source_track.get('artist', {}).get('name', '') if isinstance(source_track.get('artist'), dict) else source_track.get('artist', '')
    source_name = source_track.get('name', '')
    source_tags = get_track_tags(source_artist, source_name)
    if not source_tags:
        return []
    for tag in source_tags:
        if 'name' in tag:
            all_tags.add(tag['name'].lower())
    candidate_tags = {}
    for track in candidate_tracks:
        artist = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
        name = track.get('name', '')
        track_id = f"{artist}|{name}".lower()
        track_tags = get_track_tags(artist, name)
        if not track_tags:
            continue
        candidate_tags[track_id] = track_tags
        for tag in track_tags:
            if 'name' in tag:
                all_tags.add(tag['name'].lower())
    all_tags_list = list(all_tags)
    source_vector = create_tag_vector(source_tags, all_tags_list)
    similarities = []
    for track in candidate_tracks:
        artist = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
        name = track.get('name', '')
        track_id = f"{artist}|{name}".lower()
        if track_id == f"{source_artist}|{source_name}".lower():
            continue
        if track_id not in candidate_tags:
            continue
        track_vector = create_tag_vector(candidate_tags[track_id], all_tags_list)
        similarity = cosine_similarity(source_vector, track_vector)
        similarities.append((track, similarity))
    similarities.sort(key=lambda x: x[1], reverse=True)
    return [track for track, sim in similarities[:num_similar]]

def get_new_tracks_from_lastfm(top_tracks):
    all_tags = {}
    for track in top_tracks:
        artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
        track_name = track.get('name', '')
        if not artist_name or not track_name:
            continue
        tags = get_track_tags(artist_name, track_name)
        if not tags:
            continue
        for tag in tags:
            tag_name = tag.get('name', '').lower()
            if tag_name:
                all_tags[tag_name] = all_tags.get(tag_name, 0) + int(tag.get('count', 1))
    if not all_tags:
        return []
    sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
    top_tags = [tag for tag, count in sorted_tags[:10]]
    candidate_tracks = []
    for tag in top_tags:
        tag_tracks = get_tracks_for_tag(tag, api_get_tracks_by_tag, limit=20)
        if tag_tracks:
            candidate_tracks.extend(tag_tracks)
            logger.info(f"Added {len(tag_tracks)} tracks from tag '{tag}'")
    seen_keys = set()
    unique_similar_tracks = []
    for track in candidate_tracks:
        artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
        track_name = track.get('name', '')
        key = f"{artist_name}|{track_name}".lower()
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique_similar_tracks.append(track)
    results = []
    for top_track in top_tracks:
        vector_similar = find_similar_tracks_vector(top_track, unique_similar_tracks, num_similar=2)
        results.extend(vector_similar)
    seen = set()
    deduped = []
    for track in results:
        key = f"{track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')}|{track.get('name', '')}".lower()
        if key not in seen:
            seen.add(key)
            deduped.append(track)
    random.shuffle(deduped)
    return deduped

def generate_recommendations(top_tracks):
    try:
        similar_tracks = get_new_tracks_from_lastfm(top_tracks)
        if not similar_tracks:
            logger.warning("No similar tracks found, trying with different settings")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        known_tracks = set()
        for track in top_tracks:
            artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
            track_name = track.get('name', '')
            known_tracks.add(f"{artist_name}|{track_name}".lower())

        new_similar_tracks = []
        for track in similar_tracks:
            artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
            track_name = track.get('name', '')
            track_key = f"{artist_name}|{track_name}".lower()
            if track_key not in known_tracks:
                new_similar_tracks.append(track)

        if not new_similar_tracks:
            logger.warning("No new similar tracks found, trying fallback")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        tracks_data, success = prepare_track_data(top_tracks + new_similar_tracks)
        if not success or not tracks_data:
            logger.warning("Failed to prepare track data, trying fallback")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        tracks_df = pd.DataFrame(tracks_data)
        tag_columns = [col for col in tracks_df.columns if col.startswith('tag_') and col.endswith('_name')]
        all_tags = set()
        for col in tag_columns:
            all_tags.update(tracks_df[col].dropna().unique())
        for tag in all_tags:
            tracks_df[f'tag_{tag}'] = 0
            for col in tag_columns:
                weight_col = col.replace('_name', '_weight')
                mask = tracks_df[col] == tag
                tracks_df.loc[mask, f'tag_{tag}'] = tracks_df.loc[mask, weight_col]
        tracks_df = tracks_df.drop(columns=[col for col in tracks_df.columns if col.startswith('tag_') and (col.endswith('_name') or col.endswith('_weight'))])
        tracks_df['is_known'] = False
        for i, track in enumerate(tracks_data):
            artist_name = track.get('artist', '')
            track_name = track.get('name', '')
            track_key = f"{artist_name}|{track_name}".lower()
            if track_key in known_tracks:
                tracks_df.loc[i, 'is_known'] = True

        recommender = Recommender(n_neighbors=min(20, len(tracks_df)))
        numeric_df = recommender.train(tracks_df)
        if numeric_df.empty:
            logger.warning("Empty numeric DataFrame, using fallback")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        top_track_indices = [i for i, is_known in enumerate(tracks_df['is_known']) if is_known]
        if not top_track_indices:
            logger.warning("No top track indices found, using fallback")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        seed_df = numeric_df.iloc[top_track_indices]
        recommended_indices = recommender.recommend(seed_df, numeric_df)
        new_track_indices = [i for i in recommended_indices if i < len(tracks_data) and not tracks_df.loc[i, 'is_known']]
        ml_recommended_tracks = [tracks_data[i] for i in new_track_indices]

        final_recommendations = []
        for track in ml_recommended_tracks:
            final_recommendations.append({
                'name': track['name'],
                'artist': track['artist'],
                'playcount': track.get('playcount', 0),
                'listeners': track.get('listeners', 0),
                'mbid': track.get('mbid', ''),
                'url': track.get('url', '')
            })

        if not final_recommendations:
            logger.warning("No final recommendations found, using fallback")
            fallback_tracks, _ = fallback_recommendations(top_tracks)
            return fallback_tracks, "Our recommendation algorithm couldn't find perfect matches, but here are some songs you might still enjoy."

        return final_recommendations, None

    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        fallback_tracks, _ = fallback_recommendations(top_tracks)
        return fallback_tracks, "Our recommendation algorithm encountered an error, but here are some songs you might still enjoy."

def fallback_recommendations(top_tracks):
    try:
        all_tags = {}
        for track in top_tracks:
            artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
            track_name = track.get('name', '')
            if not artist_name or not track_name:
                continue
            tags = get_track_tags(artist_name, track_name)
            if not tags:
                continue
            for tag in tags:
                tag_name = tag.get('name', '').lower()
                if tag_name:
                    all_tags[tag_name] = all_tags.get(tag_name, 0) + int(tag.get('count', 1))
        
        if not all_tags:
            return [], "Could not generate any recommendations."
        
        sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
        top_tags = [tag for tag, count in sorted_tags[:15]]
        
        candidate_tracks = []
        for tag in top_tags:
            tag_tracks = get_tracks_for_tag(tag, api_get_tracks_by_tag, limit=30)
            if tag_tracks:
                candidate_tracks.extend(tag_tracks)
                logger.info(f"Fallback: Added {len(tag_tracks)} tracks from tag '{tag}'")
        
        known_tracks = set()
        for track in top_tracks:
            artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
            track_name = track.get('name', '')
            known_tracks.add(f"{artist_name}|{track_name}".lower())
        
        new_tracks = []
        seen = set()
        for track in candidate_tracks:
            artist_name = track.get('artist', {}).get('name', '') if isinstance(track.get('artist'), dict) else track.get('artist', '')
            track_name = track.get('name', '')
            track_key = f"{artist_name}|{track_name}".lower()
            if track_key not in known_tracks and track_key not in seen:
                seen.add(track_key)
                new_tracks.append({
                    'name': track_name,
                    'artist': artist_name,
                    'playcount': int(track.get('playcount', 0)),
                    'listeners': int(track.get('listeners', 0)) if 'listeners' in track else 0,
                    'mbid': track.get('mbid', ''),
                    'url': track.get('url', '')
                })
        
        if not new_tracks:
            return [], "Could not generate any recommendations."
        
        random.shuffle(new_tracks)
        return new_tracks[:20], None
    
    except Exception as e:
        logger.error(f"Error in fallback recommendations: {e}")
        return [], "Could not generate any recommendations."
