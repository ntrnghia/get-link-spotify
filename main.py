#!/usr/bin/env python3
"""
ZingMP3 Chart Crawler with Spotify Links

Main entry point for syncing ZingMP3 charts to Spotify playlists.
"""

import argparse
import sys

from config import PROJECT_ROOT, ZINGCHART_URL
from workflow import run_chart_sync


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
        help="Create playlist with songs filtered by keywords (optional)",
    )
    parser.add_argument(
        "--filter-keywords",
        type=str,
        default="",
        help='Comma-separated keywords to filter songs by name (e.g. "Tết,Xuân,Năm nay")',
    )
    args = parser.parse_args()

    # Determine mode
    mode = "vpn" if args.vpn else ("live" if args.live else "local")

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
    if args.filter_keywords:
        print(f"Filter: songs matching '{args.filter_keywords}'")
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

    # Parse filter keywords
    filter_keywords = (
        [k.strip() for k in args.filter_keywords.split(",") if k.strip()]
        if args.filter_keywords
        else []
    )

    # Run sync
    print("\nFetching chart and syncing to Spotify...")
    output = run_chart_sync(
        chart_url=args.chart_url,
        mode=mode,
        output_file=args.output_file,
        playlist_name=args.playlist_name if args.playlist else None,
        sorted_playlist_name=args.sorted_playlist_name,
        trending_playlist_name=args.trending_playlist_name,
        filtered_playlist_name=args.filtered_playlist_name,
        filter_keywords=filter_keywords,
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
