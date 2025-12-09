"""
Unified workflow for ZingMP3-Spotify sync.
Shared logic between main.py CLI and bench.py benchmark tool.
"""

from pathlib import Path
from typing import Callable

import spotipy

from cache import get_spotify_cache
from config import PROJECT_ROOT, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from excel import write_excel
from models import SyncOutput, SyncResult, SyncStats
from spotify import (
    create_or_get_playlist,
    get_spotify_client,
    get_spotify_client_headless,
    get_spotify_client_with_auth,
    search_songs_concurrent,
    update_playlist,
)
from zingmp3 import (
    fetch_weekly_chart_live,
    fetch_zingchart_direct,
    fetch_zingchart_live,
    is_weekly_chart_url,
    parse_chart_content,
    parse_chart_file,
)


def get_spotify_client_for_mode(
    needs_playlist: bool = False, headless: bool = False
) -> spotipy.Spotify:
    """Get appropriate Spotify client based on mode.

    Args:
        needs_playlist: Whether playlist management is needed (requires user auth)
        headless: Use refresh token auth (for CI/headless mode)

    Returns:
        Configured Spotify client
    """
    if needs_playlist:
        if headless:
            return get_spotify_client_headless()
        return get_spotify_client_with_auth()
    return get_spotify_client()


def fetch_chart_songs(
    chart_url: str,
    mode: str = "local",
    min_file_size: int = 0,
    save_html: bool = False,
) -> list[dict] | None:
    """Fetch songs from a ZingMP3 chart.

    Args:
        chart_url: URL of the chart to fetch
        mode: "vpn" (direct), "live" (proxy), or "local" (saved file)
        min_file_size: Minimum HTML size to consider valid
        save_html: Save fetched HTML to chart_live.html

    Returns:
        List of song dicts or None if failed
    """
    is_weekly = is_weekly_chart_url(chart_url)
    html_content = None
    songs = None

    if mode == "vpn":
        if is_weekly:
            print("\nWARNING: VPN mode doesn't work for weekly charts (no JSON-LD).")
            print("Please use 'live' mode for weekly charts.")
            return None
        html_content = fetch_zingchart_direct(chart_url)
        if not html_content:
            print("\nFailed to fetch via VPN. Falling back to local...")

    elif mode == "live":
        if is_weekly:
            songs = fetch_weekly_chart_live(chart_url)
            if not songs:
                print("\nFailed to fetch weekly chart via API.")
                return None
        else:
            html_content = fetch_zingchart_live(chart_url, min_size=min_file_size)
            if not html_content:
                print("\nFailed to fetch via proxies. Falling back to local...")

    # Process HTML content or use songs from API
    if songs:
        return songs

    if html_content:
        if save_html:
            save_path = PROJECT_ROOT / "chart_live.html"
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"  Saved HTML to {save_path}")
        return parse_chart_content(html_content)

    # Fall back to local file
    chart_live_file = PROJECT_ROOT / "chart_live.html"
    html_file = PROJECT_ROOT / "chart.html"
    if chart_live_file.exists():
        return parse_chart_file(str(chart_live_file))
    elif html_file.exists():
        return parse_chart_file(str(html_file))

    return None


def build_sync_results(
    songs: list[dict],
    spotify_results: list[dict | None],
) -> tuple[list[SyncResult], list[str]]:
    """Build SyncResult list from songs and Spotify results.

    Args:
        songs: List of ZingMP3 song dicts
        spotify_results: List of Spotify result dicts (or None)

    Returns:
        Tuple of (results list, track URIs list)
    """
    results = []
    track_uris = []

    for song, spotify_result in zip(songs, spotify_results):
        result = SyncResult.from_song_and_spotify(song, spotify_result)
        results.append(result)
        if result.track_uri:
            track_uris.append(result.track_uri)

    return results, track_uris


def sync_to_playlists(
    sp: spotipy.Spotify,
    results: list[SyncResult],
    track_uris: list[str],
    playlist_name: str,
    chart_url: str = "",
    sorted_playlist_name: str = "",
    trending_playlist_name: str = "",
) -> dict[str, str]:
    """Sync results to Spotify playlists.

    Args:
        sp: Spotify client (with user auth)
        results: List of SyncResult
        track_uris: List of track URIs to add
        playlist_name: Main playlist name
        chart_url: Chart URL for playlist description
        sorted_playlist_name: Optional second playlist sorted by popularity (high to low)
        trending_playlist_name: Optional third playlist sorted by rank + popularity (new & trending)

    Returns:
        Dict of playlist names to URLs
    """
    playlist_urls = {}

    if not track_uris:
        return playlist_urls

    # Main playlist
    playlist_id, is_new = create_or_get_playlist(sp, playlist_name, chart_url)
    action = "Created" if is_new else "Updated"
    tracks_added = update_playlist(sp, playlist_id, track_uris)
    print(f"  {action} playlist '{playlist_name}' ({tracks_added} tracks)")
    playlist_urls[playlist_name] = f"https://open.spotify.com/playlist/{playlist_id}"

    # Sorted by popularity playlist (optional) - most popular first
    if sorted_playlist_name:
        sorted_results = sorted(
            [r for r in results if r.found],
            key=lambda x: x.popularity,
            reverse=True,
        )
        sorted_uris = [r.track_uri for r in sorted_results]

        sorted_id, is_new = create_or_get_playlist(sp, sorted_playlist_name, chart_url)
        action = "Created" if is_new else "Updated"
        update_playlist(sp, sorted_id, sorted_uris)
        print(f"  {action} sorted playlist '{sorted_playlist_name}'")
        playlist_urls[sorted_playlist_name] = f"https://open.spotify.com/playlist/{sorted_id}"

    # Trending playlist (optional) - sorted by normalized rank + popularity (low = new & trending)
    if trending_playlist_name:
        found_results = [r for r in results if r.found]
        
        if found_results:
            # Calculate min/max for normalization
            ranks = [r.rank for r in found_results]
            pops = [r.popularity for r in found_results]
            min_rank, max_rank = min(ranks), max(ranks)
            min_pop, max_pop = min(pops), max(pops)
            
            # Normalize function (handles edge case where min == max)
            def normalize(value: float, min_val: float, max_val: float) -> float:
                if max_val == min_val:
                    return 0.0
                return (value - min_val) / (max_val - min_val)
            
            # Sort by normalized rank + normalized popularity (ascending)
            trending_results = sorted(
                found_results,
                key=lambda r: (
                    normalize(r.rank, min_rank, max_rank) +
                    normalize(r.popularity, min_pop, max_pop)
                ),
            )
            trending_uris = [r.track_uri for r in trending_results]

            trending_id, is_new = create_or_get_playlist(sp, trending_playlist_name, chart_url)
            action = "Created" if is_new else "Updated"
            update_playlist(sp, trending_id, trending_uris)
            print(f"  {action} trending playlist '{trending_playlist_name}'")
            playlist_urls[trending_playlist_name] = f"https://open.spotify.com/playlist/{trending_id}"

    return playlist_urls


def run_chart_sync(
    chart_url: str,
    mode: str = "local",
    output_file: str | None = None,
    playlist_name: str | None = None,
    sorted_playlist_name: str = "",
    trending_playlist_name: str = "",
    headless: bool = False,
    min_file_size: int = 0,
    save_html: bool = False,
    progress_callback: Callable[[int, dict, dict | None, bool], None] | None = None,
) -> SyncOutput:
    """Run complete chart sync workflow.

    Args:
        chart_url: URL of the ZingMP3 chart
        mode: Fetch mode - "vpn", "live", or "local"
        output_file: Path to output Excel file (None to skip)
        playlist_name: Spotify playlist name (None to skip playlist)
        sorted_playlist_name: Optional second playlist sorted by popularity (high to low)
        trending_playlist_name: Optional third playlist sorted by rank + popularity (new & trending)
        headless: Use headless Spotify auth
        min_file_size: Minimum HTML size to consider valid
        save_html: Save fetched HTML to file
        progress_callback: Optional callback(index, song, result, cached)

    Returns:
        SyncOutput with results, stats, and track URIs
    """
    output = SyncOutput()

    # Check credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\nERROR: Spotify credentials not found!")
        print("Set environment variables or create .env file with:")
        print("  SPOTIFY_CLIENT_ID=your_client_id")
        print("  SPOTIFY_CLIENT_SECRET=your_client_secret")
        return output

    # Fetch chart
    songs = fetch_chart_songs(chart_url, mode, min_file_size, save_html)
    if not songs:
        print("ERROR: Failed to get chart data")
        return output

    output.stats.total_songs = len(songs)

    # Initialize Spotify
    sp = get_spotify_client_for_mode(
        needs_playlist=bool(playlist_name),
        headless=headless,
    )

    # Track cache stats via callback wrapper
    def stats_callback(index: int, song: dict, result: dict | None, cached: bool) -> None:
        if cached:
            output.stats.cache_hits += 1
        else:
            output.stats.cache_misses += 1
        if progress_callback:
            progress_callback(index, song, result, cached)

    # Search Spotify
    spotify_results = search_songs_concurrent(sp, songs, stats_callback)

    # Build results
    output.results, output.track_uris = build_sync_results(songs, spotify_results)
    output.stats.songs_found = sum(1 for r in output.results if r.found)

    # Export to Excel
    if output_file:
        output_path = PROJECT_ROOT / output_file if not Path(output_file).is_absolute() else Path(output_file)
        write_excel([r.to_dict() for r in output.results], str(output_path))
        print(f"  Saved to {output_path}")

    # Sync to playlists
    if playlist_name and output.track_uris:
        sync_to_playlists(
            sp,
            output.results,
            output.track_uris,
            playlist_name,
            chart_url,
            sorted_playlist_name,
            trending_playlist_name,
        )

    return output
