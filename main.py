#!/usr/bin/env python3
"""
ZingMP3 Chart Crawler with Spotify Links

Main entry point for syncing ZingMP3 charts to Spotify playlists.
"""

import argparse
import sys

from config import PROJECT_ROOT, ZINGCHART_URL
from workflow import FilteredPlaylist, run_chart_sync


def parse_filtered_playlists(
    names_str: str, keywords_str: str
) -> list[FilteredPlaylist]:
    """Parse paired playlist names and keyword groups into (name, keywords) pairs.

    Multiple playlists are separated by ';'.
    Within one keyword group, individual keywords are separated by ',' (OR match).

    Examples:
        >>> parse_filtered_playlists("Top Remix", "Remix")
        [('Top Remix', ['Remix'])]
        >>> parse_filtered_playlists("Top Remix;Top OST", "Remix;OST")
        [('Top Remix', ['Remix']), ('Top OST', ['OST'])]
        >>> parse_filtered_playlists("Top Mix", "Remix,Mix")
        [('Top Mix', ['Remix', 'Mix'])]
        >>> parse_filtered_playlists("", "")
        []

    Args:
        names_str: Semicolon-separated playlist names
        keywords_str: Semicolon-separated keyword groups (each group is comma-separated)

    Returns:
        List of (playlist_name, keywords) pairs. Pairs missing either part are dropped.
    """
    if not names_str or not keywords_str:
        return []

    names = [n.strip() for n in names_str.split(";") if n.strip()]
    keyword_groups = keywords_str.split(";")

    pairs: list[FilteredPlaylist] = []
    for name, group in zip(names, keyword_groups):
        keywords = [k.strip() for k in group.split(",") if k.strip()]
        if keywords:
            pairs.append((name, keywords))
    return pairs


def main() -> None:
    """Main function to crawl chart and find Spotify links."""
    parser = argparse.ArgumentParser(
        description="ZingMP3 Chart Crawler with Spotify Links"
    )
    parser.add_argument(
        "--vpn",
        action="store_true",
        help="Fetch live data directly (requires VPN to be connected first)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch live data using Vietnam proxies (unreliable)",
    )
    parser.add_argument(
        "--save-html",
        action="store_true",
        help="Save fetched HTML to chart_live.html (only with --vpn or --live)",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Create/update Spotify playlist with chart songs",
    )
    parser.add_argument(
        "--playlist-name",
        type=str,
        default="ZingMP3 Top 100",
        help='Name of the Spotify playlist (default: "ZingMP3 Top 100")',
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless/CI mode (uses SPOTIFY_REFRESH_TOKEN env var)",
    )
    parser.add_argument(
        "--chart-url",
        type=str,
        default=ZINGCHART_URL,
        help="URL of the ZingMP3 chart to crawl",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="zingchart_top_100.xlsx",
        help="Output Excel filename",
    )
    parser.add_argument(
        "--sorted-playlist-name",
        type=str,
        default="",
        help="Create second playlist sorted by Spotify popularity (optional)",
    )
    parser.add_argument(
        "--trending-playlist-name",
        type=str,
        default="",
        help="Create third playlist sorted by rank + popularity (new & trending)",
    )
    parser.add_argument(
        "--min-file-size",
        type=int,
        default=0,
        help="Minimum file size in bytes to consider valid",
    )
    parser.add_argument(
        "--filtered-playlist-name",
        type=str,
        default="",
        help=(
            "Create one or more playlists with songs filtered by keywords. "
            'Use ";" to separate multiple playlist names '
            '(e.g. "ZingMP3 Top Remix;ZingMP3 Top OST").'
        ),
    )
    parser.add_argument(
        "--filter-keywords",
        type=str,
        default="",
        help=(
            "Keyword groups paired with --filtered-playlist-name. "
            'Use "," within a group for OR match, ";" between groups '
            '(e.g. "Remix;OST" or "Remix,Mix;OST,Soundtrack").'
        ),
    )
    args = parser.parse_args()

    # Determine mode
    mode = "vpn" if args.vpn else ("live" if args.live else "local")

    # Parse filtered playlists (supports multiple via ';' separator)
    filtered_playlists = parse_filtered_playlists(
        args.filtered_playlist_name, args.filter_keywords
    )

    # Print header
    print("=" * 60)
    print("ZingMP3 Chart Crawler with Spotify Links")
    print(f"Chart: {args.chart_url}")
    if args.vpn:
        print("Mode: VPN (direct fetch - VPN must be connected)")
    elif args.live:
        print("Mode: PROXY (fetching via Vietnam proxies)")
    else:
        print("Mode: LOCAL (using saved chart.html)")
    if args.playlist:
        print(f"Playlist: Will create/update '{args.playlist_name}'")
    if args.headless:
        print("Auth: Headless mode (using refresh token)")
    for fp_name, fp_keywords in filtered_playlists:
        print(f"Filter: '{fp_name}' <- songs matching {fp_keywords}")
    print(f"Output: {PROJECT_ROOT / args.output_file}")
    print("=" * 60)

    # Progress callback for console output
    def progress_callback(index: int, song: dict, result: dict | None, cached: bool) -> None:
        pos = song["position"]
        name = song["name"]
        cache_tag = " [cached]" if cached else ""
        if result:
            match_pct = result["match_score"] * 100
            print(f"  [{pos:3d}] {name[:30]:30s} FOUND (match: {match_pct:.0f}%){cache_tag}")
        else:
            print(f"  [{pos:3d}] {name[:30]:30s} NOT FOUND{cache_tag}")

    # Run sync
    print("\nFetching chart and syncing to Spotify...")
    output = run_chart_sync(
        chart_url=args.chart_url,
        mode=mode,
        output_file=args.output_file,
        playlist_name=args.playlist_name if args.playlist else None,
        sorted_playlist_name=args.sorted_playlist_name,
        trending_playlist_name=args.trending_playlist_name,
        filtered_playlists=filtered_playlists,
        headless=args.headless,
        min_file_size=args.min_file_size,
        save_html=args.save_html,
        progress_callback=progress_callback,
    )

    if not output.results:
        print("ERROR: No results. Cannot continue.")
        sys.exit(1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Found on Spotify: {output.stats.songs_found}/{output.stats.total_songs} songs")
    print(f"Cache: {output.stats.cache_hits} hits, {output.stats.cache_misses} misses")
    print(f"{'=' * 60}")
    print("DONE!")
    print(f"{'=' * 60}")

    # Print preview
    print("\nPreview (Top 10):")
    print("-" * 100)
    for r in output.results[:10]:
        status = f"Match: {r.match_score*100:.0f}%" if r.found else "NOT FOUND"
        print(f"#{r.rank:2d} | {r.song_name[:25]:25s} | {r.artists[:20]:20s} | {status}")


if __name__ == "__main__":
    main()
