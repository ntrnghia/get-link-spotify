"""Unified workflow for ZingMP3-Spotify sync."""

from pathlib import Path
from typing import Callable

import spotipy

from cache import get_spotify_cache
from config import PROJECT_ROOT, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from excel import write_excel
from models import SyncOutput, SyncResult, SyncStats
from spotify import (create_or_get_playlist, get_spotify_client, get_spotify_client_headless,
                     get_spotify_client_with_auth, search_songs_concurrent, update_playlist)
from zingmp3 import (fetch_weekly_chart_live, fetch_zingchart_direct, fetch_zingchart_live,
                     is_weekly_chart_url, parse_chart_content, parse_chart_file)


def _get_client(needs_playlist: bool, headless: bool) -> spotipy.Spotify:
    if needs_playlist:
        return get_spotify_client_headless() if headless else get_spotify_client_with_auth()
    return get_spotify_client()


def _fetch_chart(chart_url: str, mode: str, min_file_size: int, save_html: bool) -> list[dict] | None:
    """Fetch songs from a ZingMP3 chart."""
    is_weekly = is_weekly_chart_url(chart_url)
    html, songs = None, None

    if mode == "vpn":
        if is_weekly:
            print("\nWARNING: VPN mode doesn't work for weekly charts. Use 'live' mode.")
            return None
        html = fetch_zingchart_direct(chart_url)
        if not html:
            print("\nFailed to fetch via VPN. Falling back to local...")
    elif mode == "live":
        if is_weekly:
            return fetch_weekly_chart_live(chart_url)
        html = fetch_zingchart_live(chart_url, min_size=min_file_size)
        if not html:
            print("\nFailed to fetch via proxies. Falling back to local...")

    if html:
        if save_html:
            (PROJECT_ROOT / "chart_live.html").write_text(html, encoding="utf-8")
            print(f"  Saved HTML to {PROJECT_ROOT / 'chart_live.html'}")
        return parse_chart_content(html)

    # Fallback to local
    for path in [PROJECT_ROOT / "chart_live.html", PROJECT_ROOT / "chart.html"]:
        if path.exists():
            return parse_chart_file(str(path))
    return None


def _normalize(value: float, min_v: float, max_v: float) -> float:
    return (value - min_v) / (max_v - min_v) if max_v != min_v else 0.0


def _sync_playlists(sp: spotipy.Spotify, results: list[SyncResult], uris: list[str],
                    chart_url: str, playlist_name: str, sorted_name: str, trending_name: str) -> dict[str, str]:
    """Sync results to Spotify playlists."""
    urls = {}
    if not uris:
        return urls

    # Playlist configurations: (name, sort_fn, optional)
    found = [r for r in results if r.found]
    
    def trending_sort(items):
        if not items:
            return items
        ranks, pops = [r.rank for r in items], [r.popularity for r in items]
        min_r, max_r, min_p, max_p = min(ranks), max(ranks), min(pops), max(pops)
        return sorted(items, key=lambda r: _normalize(r.rank, min_r, max_r) + _normalize(r.popularity, min_p, max_p))

    configs = [
        (playlist_name, lambda: uris, False),
        (sorted_name, lambda: [r.track_uri for r in sorted(found, key=lambda x: x.popularity, reverse=True)], True),
        (trending_name, lambda: [r.track_uri for r in trending_sort(found)], True),
    ]

    for name, get_uris, optional in configs:
        if not name or (optional and not name):
            continue
        playlist_uris = get_uris()
        if not playlist_uris:
            continue
        pid, is_new = create_or_get_playlist(sp, name, chart_url)
        count = update_playlist(sp, pid, playlist_uris)
        print(f"  {'Created' if is_new else 'Updated'} playlist '{name}' ({count} tracks)")
        urls[name] = f"https://open.spotify.com/playlist/{pid}"

    return urls


def run_chart_sync(
    chart_url: str, mode: str = "local", output_file: str | None = None,
    playlist_name: str | None = None, sorted_playlist_name: str = "",
    trending_playlist_name: str = "", headless: bool = False,
    min_file_size: int = 0, save_html: bool = False,
    progress_callback: Callable[[int, dict, dict | None, bool], None] | None = None,
) -> SyncOutput:
    """Run complete chart sync workflow."""
    output = SyncOutput()

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\nERROR: Spotify credentials not found!")
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env")
        return output

    songs = _fetch_chart(chart_url, mode, min_file_size, save_html)
    if not songs:
        print("ERROR: Failed to get chart data")
        return output

    output.stats.total_songs = len(songs)
    sp = _get_client(bool(playlist_name), headless)

    def stats_cb(idx: int, song: dict, result: dict | None, cached: bool) -> None:
        if cached:
            output.stats.cache_hits += 1
        else:
            output.stats.cache_misses += 1
        if progress_callback:
            progress_callback(idx, song, result, cached)

    spotify_results = search_songs_concurrent(sp, songs, stats_cb)

    # Build results
    for song, sp_result in zip(songs, spotify_results):
        result = SyncResult.from_song_and_spotify(song, sp_result)
        output.results.append(result)
        if result.track_uri:
            output.track_uris.append(result.track_uri)
    output.stats.songs_found = sum(1 for r in output.results if r.found)

    # Export
    if output_file:
        path = PROJECT_ROOT / output_file if not Path(output_file).is_absolute() else Path(output_file)
        write_excel([r.to_dict() for r in output.results], str(path))
        print(f"  Saved to {path}")

    # Playlists
    if playlist_name and output.track_uris:
        _sync_playlists(sp, output.results, output.track_uris, chart_url,
                       playlist_name, sorted_playlist_name, trending_playlist_name)

    return output
