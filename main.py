#!/usr/bin/env python3
"""ZingMP3 Chart Crawler with Spotify Links - CLI entry point."""

import argparse
import sys

from config import PROJECT_ROOT, ZINGCHART_URL
from workflow import run_chart_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="ZingMP3 Chart Crawler with Spotify Links")
    parser.add_argument("--vpn", action="store_true", help="Fetch via VPN (must be connected)")
    parser.add_argument("--live", action="store_true", help="Fetch via Vietnam proxies")
    parser.add_argument("--save-html", action="store_true", help="Save fetched HTML")
    parser.add_argument("--playlist", action="store_true", help="Create/update Spotify playlist")
    parser.add_argument("--playlist-name", type=str, default="ZingMP3 Top 100")
    parser.add_argument("--headless", action="store_true", help="Use SPOTIFY_REFRESH_TOKEN")
    parser.add_argument("--chart-url", type=str, default=ZINGCHART_URL)
    parser.add_argument("--output-file", type=str, default="zingchart_top_100.xlsx")
    parser.add_argument("--sorted-playlist-name", type=str, default="")
    parser.add_argument("--trending-playlist-name", type=str, default="")
    parser.add_argument("--min-file-size", type=int, default=0)
    args = parser.parse_args()

    mode = "vpn" if args.vpn else ("live" if args.live else "local")

    print("=" * 60)
    print("ZingMP3 Chart Crawler with Spotify Links")
    print(f"Chart: {args.chart_url}")
    print(f"Mode: {'VPN' if args.vpn else 'PROXY' if args.live else 'LOCAL'}")
    if args.playlist:
        print(f"Playlist: {args.playlist_name}")
    print(f"Output: {PROJECT_ROOT / args.output_file}")
    print("=" * 60)

    def progress(idx: int, song: dict, result: dict | None, cached: bool) -> None:
        pos, name = song["position"], song["name"]
        tag = " [cached]" if cached else ""
        if result:
            print(f"  [{pos:3d}] {name[:30]:30s} FOUND (match: {result['match_score']*100:.0f}%){tag}")
        else:
            print(f"  [{pos:3d}] {name[:30]:30s} NOT FOUND{tag}")

    print("\nFetching chart and syncing to Spotify...")
    output = run_chart_sync(
        chart_url=args.chart_url, mode=mode, output_file=args.output_file,
        playlist_name=args.playlist_name if args.playlist else None,
        sorted_playlist_name=args.sorted_playlist_name,
        trending_playlist_name=args.trending_playlist_name,
        headless=args.headless, min_file_size=args.min_file_size,
        save_html=args.save_html, progress_callback=progress,
    )

    if not output.results:
        print("ERROR: No results.")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"Found: {output.stats.songs_found}/{output.stats.total_songs} songs")
    print(f"Cache: {output.stats.cache_hits} hits, {output.stats.cache_misses} misses")
    print(f"{'=' * 60}\nDONE!\n{'=' * 60}")

    print("\nPreview (Top 10):\n" + "-" * 100)
    for r in output.results[:10]:
        status = f"Match: {r.match_score*100:.0f}%" if r.found else "NOT FOUND"
        print(f"#{r.rank:2d} | {r.song_name[:25]:25s} | {r.artists[:20]:20s} | {status}")


if __name__ == "__main__":
    main()
