"""Spotify API wrapper with concurrent search and caching."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import spotipy
from rapidfuzz import fuzz
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from cache import get_spotify_cache
from config import (PLAYLIST_BATCH_SIZE, REQUEST_DELAY, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
                    SPOTIFY_REDIRECT_URI, SPOTIFY_RETRY_ATTEMPTS, SPOTIFY_RETRY_DELAY,
                    SPOTIFY_SEARCH_LIMIT, SPOTIFY_SEARCH_WORKERS)


def get_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client with client credentials (read-only)."""
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))


def get_spotify_client_with_auth() -> spotipy.Spotify:
    """Initialize Spotify client with user authorization (for playlist management)."""
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI, scope="playlist-modify-public playlist-modify-private"))


def get_spotify_client_headless() -> spotipy.Spotify:
    """Initialize Spotify client using refresh token (for CI/headless mode)."""
    if not (refresh_token := os.environ.get("SPOTIFY_REFRESH_TOKEN")):
        raise ValueError("SPOTIFY_REFRESH_TOKEN environment variable not set")
    auth = SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET,
                        redirect_uri=SPOTIFY_REDIRECT_URI, scope="playlist-modify-public playlist-modify-private",
                        open_browser=False)
    return spotipy.Spotify(auth=auth.refresh_access_token(refresh_token)["access_token"])


def _similarity(a: str, b: str) -> float:
    return fuzz.ratio(a.lower(), b.lower()) / 100.0 if a and b else 0.0


def _duration_to_sec(d: str) -> int | None:
    if not d:
        return None
    parts = d.split(":")
    try:
        return sum(int(p) * m for p, m in zip(reversed(parts), [1, 60, 3600]))
    except ValueError:
        return None


def _duration_sim(zing_dur: str, spotify_ms: int) -> float:
    zing_sec = _duration_to_sec(zing_dur)
    if not zing_sec:
        return 0.5
    spotify_sec = spotify_ms // 1000
    if not spotify_sec:
        return 0.5
    return max(0.0, 1.0 - abs(zing_sec - spotify_sec) / max(zing_sec, spotify_sec))


def _artist_sim(zing_artists: list[str], spotify_artists: list[dict]) -> float:
    if not zing_artists or not spotify_artists:
        return 0.5
    return max(_similarity(za, sa["name"]) for za in zing_artists for sa in spotify_artists)


def _match_score(song: dict, track: dict) -> float:
    """Calculate match score (0-1) using title, artist, duration."""
    return (
        _similarity(song["name"], track["name"]) +
        _artist_sim(song.get("artist_list", []), track.get("artists", [])) +
        _duration_sim(song.get("duration", ""), track.get("duration_ms", 0))
    ) / 3


def _search_with_retry(sp: spotipy.Spotify, query: str) -> dict | None:
    for attempt in range(SPOTIFY_RETRY_ATTEMPTS):
        try:
            return sp.search(q=query, type="track", limit=SPOTIFY_SEARCH_LIMIT)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                time.sleep(SPOTIFY_RETRY_DELAY * (2 ** attempt))
                continue
            raise
        except Exception:
            if attempt < SPOTIFY_RETRY_ATTEMPTS - 1:
                time.sleep(SPOTIFY_RETRY_DELAY)
                continue
            raise
    return None


def _build_queries(song: dict) -> list[str]:
    """Build search queries for a song."""
    name, artists = song["name"], song.get("artist_list", [])
    queries = []
    if artists:
        queries.extend([f'track:"{name}" artist:"{artists[0]}"', f"{name} {artists[0]}"])
    queries.append(name)
    return queries


def _format_result(track: dict, score: float) -> dict:
    """Format Spotify track as result dict."""
    duration_ms = track.get("duration_ms", 0)
    return {
        "spotify_name": track["name"],
        "spotify_artist": ", ".join(a["name"] for a in track["artists"]),
        "spotify_album": track["album"].get("name", ""),
        "spotify_duration": f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}" if duration_ms else "",
        "spotify_url": track["external_urls"].get("spotify", ""),
        "popularity": track.get("popularity", 0),
        "track_uri": track["uri"],
        "match_score": score,
    }


def search_spotify_single(sp: spotipy.Spotify, song: dict) -> dict | None:
    """Search for a single song on Spotify."""
    for query in _build_queries(song):
        try:
            if not (results := _search_with_retry(sp, query)):
                continue
            if tracks := results.get("tracks", {}).get("items", []):
                best = max(tracks, key=lambda t: _match_score(song, t))
                return _format_result(best, _match_score(song, best))
        except Exception as e:
            print(f"  Search error for '{query}': {e}")
    return None


def search_songs_concurrent(
    sp: spotipy.Spotify, songs: list[dict],
    progress_callback: Callable[[int, dict, dict | None, bool], None] | None = None,
) -> list[dict]:
    """Search for multiple songs concurrently with caching."""
    cache = get_spotify_cache()
    results = [None] * len(songs)
    cache_misses = []

    # Phase 1: Check cache
    for i, song in enumerate(songs):
        if (cached := cache.get_song(song["name"], song.get("artists", ""))) is not None:
            results[i] = cached if cached != {} else None
            if progress_callback:
                progress_callback(i, song, results[i], True)
        else:
            cache_misses.append(i)

    # Phase 2: Fetch misses concurrently
    if cache_misses:
        def search_idx(idx: int) -> tuple[int, dict | None]:
            song = songs[idx]
            result = search_spotify_single(sp, song)
            cache.set_song(song["name"], song.get("artists", ""), result if result else {})
            time.sleep(REQUEST_DELAY)
            return idx, result

        with ThreadPoolExecutor(max_workers=SPOTIFY_SEARCH_WORKERS) as executor:
            for future in as_completed({executor.submit(search_idx, i): i for i in cache_misses}):
                idx, result = future.result()
                results[idx] = result
                if progress_callback:
                    progress_callback(idx, songs[idx], result, False)

    print(f"  Cache: {len(songs) - len(cache_misses)} hits, {len(cache_misses)} misses")
    return results


def create_or_get_playlist(sp: spotipy.Spotify, name: str, chart_url: str = "") -> tuple[str, bool]:
    """Create playlist or get existing one. Returns (playlist_id, is_new)."""
    user_id = sp.current_user()["id"]
    playlists = sp.current_user_playlists(limit=50)
    while playlists:
        for p in playlists["items"]:
            if p["name"] == name:
                return p["id"], False
        playlists = sp.next(playlists) if playlists["next"] else None

    desc = f"ZingMP3 Chart - Auto-updated by ZingChart Crawler{f' - {chart_url}' if chart_url else ''}"
    return sp.user_playlist_create(user=user_id, name=name, public=True, description=desc)["id"], True


def update_playlist(sp: spotipy.Spotify, playlist_id: str, track_uris: list[str]) -> int:
    """Replace all tracks in playlist. Returns count added."""
    uris = [u for u in track_uris if u]
    if not uris:
        return 0
    sp.playlist_replace_items(playlist_id, uris[:PLAYLIST_BATCH_SIZE])
    for i in range(PLAYLIST_BATCH_SIZE, len(uris), PLAYLIST_BATCH_SIZE):
        sp.playlist_add_items(playlist_id, uris[i:i + PLAYLIST_BATCH_SIZE])
    return len(uris)
