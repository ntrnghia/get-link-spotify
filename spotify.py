"""
Spotify API wrapper with concurrent search and caching.
Uses rapidfuzz for fast string matching.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import spotipy
from rapidfuzz import fuzz
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from cache import get_spotify_cache
from config import (
    PLAYLIST_BATCH_SIZE,
    REQUEST_DELAY,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_RETRY_ATTEMPTS,
    SPOTIFY_RETRY_DELAY,
    SPOTIFY_SEARCH_LIMIT,
    SPOTIFY_SEARCH_WORKERS,
)

import time


def get_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client with client credentials (read-only)."""
    auth_manager = SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_spotify_client_with_auth() -> spotipy.Spotify:
    """Initialize Spotify client with user authorization (for playlist management).

    First time: Opens browser for user login.
    Subsequent runs: Uses cached token from .cache file.
    """
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private",
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_spotify_client_headless() -> spotipy.Spotify:
    """Initialize Spotify client using refresh token (for CI/headless mode).

    Requires SPOTIFY_REFRESH_TOKEN environment variable.
    """
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if not refresh_token:
        raise ValueError("SPOTIFY_REFRESH_TOKEN environment variable not set")

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private",
        open_browser=False,
    )

    # Create token info and refresh it
    token_info = auth_manager.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth=token_info["access_token"])


def string_similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0) using rapidfuzz."""
    if not a or not b:
        return 0.0
    return fuzz.ratio(a.lower(), b.lower()) / 100.0


def duration_to_seconds(duration_str: str) -> int | None:
    """Convert duration string (M:SS or H:MM:SS) to seconds."""
    if not duration_str:
        return None
    parts = duration_str.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def duration_similarity(zing_duration: str, spotify_ms: int) -> float:
    """Compare durations using proportional difference.

    Formula: 1 - |diff| / max(zing_sec, spotify_sec)
    Returns similarity 0.0 to 1.0.
    """
    zing_sec = duration_to_seconds(zing_duration)
    if zing_sec is None or zing_sec == 0:
        return 0.5  # No data, neutral score
    spotify_sec = spotify_ms // 1000
    if spotify_sec == 0:
        return 0.5

    diff = abs(zing_sec - spotify_sec)
    max_duration = max(zing_sec, spotify_sec)
    similarity = 1.0 - (diff / max_duration)

    return max(0.0, similarity)


def artist_similarity(zing_artists: list[str], spotify_artists: list[dict]) -> float:
    """Compare artist lists, return similarity 0.0 to 1.0."""
    if not zing_artists or not spotify_artists:
        return 0.5  # No data, neutral score

    spotify_names = [a["name"] for a in spotify_artists]

    # Find best match between any ZingMP3 artist and any Spotify artist
    best_match = 0.0
    for zing_artist in zing_artists:
        for spotify_artist in spotify_names:
            sim = string_similarity(zing_artist, spotify_artist)
            best_match = max(best_match, sim)

    return best_match


def calculate_match_score(song: dict, spotify_track: dict) -> float:
    """Calculate comprehensive match score between ZingMP3 song and Spotify track.

    Returns score from 0.0 to 1.0 (higher = better match).
    Uses equal weights for: Title, Artist, Duration (33.3% each)
    """
    title_sim = string_similarity(song["name"], spotify_track["name"])
    artist_sim = artist_similarity(
        song.get("artist_list", []), spotify_track.get("artists", [])
    )
    duration_sim = duration_similarity(
        song.get("duration", ""), spotify_track.get("duration_ms", 0)
    )

    # Simple average of 3 fields (equal weights)
    return (title_sim + artist_sim + duration_sim) / 3


def _search_with_retry(sp: spotipy.Spotify, query: str) -> dict | None:
    """Execute Spotify search with exponential backoff retry."""
    for attempt in range(SPOTIFY_RETRY_ATTEMPTS):
        try:
            return sp.search(q=query, type="track", limit=SPOTIFY_SEARCH_LIMIT)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:  # Rate limited
                delay = SPOTIFY_RETRY_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
            raise
        except Exception:
            if attempt < SPOTIFY_RETRY_ATTEMPTS - 1:
                time.sleep(SPOTIFY_RETRY_DELAY)
                continue
            raise
    return None


def search_spotify_single(sp: spotipy.Spotify, song: dict) -> dict | None:
    """Search for a single song on Spotify (no caching).

    Args:
        sp: Spotify client
        song: Dict with name, artists, artist_list, duration, url

    Returns dict with Spotify fields + match_score, or None if not found
    """
    song_name = song["name"]
    artists = song.get("artist_list", [])

    # Try different search strategies
    search_queries = []

    # Strategy 1: Full search with song name and first artist
    if artists:
        search_queries.append(f'track:"{song_name}" artist:"{artists[0]}"')

    # Strategy 2: Just song name and artist without quotes
    if artists:
        search_queries.append(f"{song_name} {artists[0]}")

    # Strategy 3: Just song name
    search_queries.append(song_name)

    for query in search_queries:
        try:
            results = _search_with_retry(sp, query)
            if results is None:
                continue
            tracks = results.get("tracks", {}).get("items", [])

            if tracks:
                # Score each track and pick the best match
                best_track = None
                best_score = -1

                for track in tracks:
                    score = calculate_match_score(song, track)
                    if score > best_score:
                        best_score = score
                        best_track = track

                if best_track:
                    # Convert duration_ms to M:SS format
                    duration_ms = best_track.get("duration_ms", 0)
                    if duration_ms:
                        minutes = duration_ms // 60000
                        seconds = (duration_ms % 60000) // 1000
                        spotify_duration = f"{minutes}:{seconds:02d}"
                    else:
                        spotify_duration = ""

                    return {
                        "spotify_name": best_track["name"],
                        "spotify_artist": ", ".join(
                            [a["name"] for a in best_track["artists"]]
                        ),
                        "spotify_album": best_track["album"].get("name", ""),
                        "spotify_duration": spotify_duration,
                        "spotify_url": best_track["external_urls"].get("spotify", ""),
                        "popularity": best_track.get("popularity", 0),
                        "track_uri": best_track["uri"],
                        "match_score": best_score,
                    }
        except Exception as e:
            print(f"  Search error for '{query}': {e}")
            continue

    return None


def search_spotify(sp: spotipy.Spotify, song: dict) -> tuple[dict | None, bool]:
    """Search for a song on Spotify with caching.

    Returns:
        Tuple of (result_dict, was_cached)
    """
    cache = get_spotify_cache()
    artists = song.get("artists", "")

    # Check cache first
    cached = cache.get_song(song["name"], artists)
    if cached is not None:
        return cached, True

    # Search Spotify
    result = search_spotify_single(sp, song)

    # Cache result (even if None, to avoid repeated searches)
    if result is not None:
        cache.set_song(song["name"], artists, result)
    else:
        # Cache negative result with empty dict
        cache.set_song(song["name"], artists, {})

    return result, False


def search_songs_concurrent(
    sp: spotipy.Spotify,
    songs: list[dict],
    progress_callback: Callable[[int, dict, dict | None, bool], None] | None = None,
) -> list[dict]:
    """Search for multiple songs concurrently with caching.

    Args:
        sp: Spotify client
        songs: List of song dicts
        progress_callback: Optional callback(index, song, result, was_cached)

    Returns:
        List of result dicts in same order as input songs
    """
    results = [None] * len(songs)
    cache_hits = 0
    cache_misses = 0

    def search_with_index(index: int, song: dict) -> tuple[int, dict | None, bool]:
        result, was_cached = search_spotify(sp, song)
        # Handle empty dict from negative cache
        if result == {}:
            result = None
        time.sleep(REQUEST_DELAY)  # Small delay to avoid rate limiting
        return index, result, was_cached

    with ThreadPoolExecutor(max_workers=SPOTIFY_SEARCH_WORKERS) as executor:
        futures = {
            executor.submit(search_with_index, i, song): i
            for i, song in enumerate(songs)
        }

        for future in as_completed(futures):
            index, result, was_cached = future.result()
            results[index] = result

            if was_cached:
                cache_hits += 1
            else:
                cache_misses += 1

            if progress_callback:
                progress_callback(index, songs[index], result, was_cached)

    print(f"  Cache: {cache_hits} hits, {cache_misses} misses")
    return results


def create_or_get_playlist(
    sp: spotipy.Spotify, playlist_name: str, chart_url: str = ""
) -> tuple[str, bool]:
    """Create playlist or get existing one.

    Returns tuple of (playlist_id, is_new).
    """
    user_id = sp.current_user()["id"]

    # Search existing playlists
    playlists = sp.current_user_playlists(limit=50)
    while playlists:
        for playlist in playlists["items"]:
            if playlist["name"] == playlist_name:
                return playlist["id"], False

        # Get next page
        if playlists["next"]:
            playlists = sp.next(playlists)
        else:
            break

    # Create new playlist
    description = (
        f"ZingMP3 Chart - Auto-updated by ZingChart Crawler - {chart_url}"
        if chart_url
        else "ZingMP3 Chart - Auto-updated by ZingChart Crawler"
    )
    new_playlist = sp.user_playlist_create(
        user=user_id, name=playlist_name, public=True, description=description
    )
    return new_playlist["id"], True


def update_playlist(sp: spotipy.Spotify, playlist_id: str, track_uris: list[str]) -> int:
    """Replace all tracks in playlist with new ones.

    Returns number of tracks added.
    """
    # Filter out None/empty track URIs
    valid_uris = [uri for uri in track_uris if uri]

    if not valid_uris:
        return 0

    # Clear existing tracks by replacing with new ones
    sp.playlist_replace_items(playlist_id, valid_uris[:PLAYLIST_BATCH_SIZE])

    # If more than batch size, add the rest
    if len(valid_uris) > PLAYLIST_BATCH_SIZE:
        for i in range(PLAYLIST_BATCH_SIZE, len(valid_uris), PLAYLIST_BATCH_SIZE):
            batch = valid_uris[i : i + PLAYLIST_BATCH_SIZE]
            sp.playlist_add_items(playlist_id, batch)

    return len(valid_uris)
