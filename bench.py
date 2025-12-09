#!/usr/bin/env python3
"""
Benchmark tool for ZingMP3-Spotify sync.

Simulates GitHub Actions workflows locally with timing and cache statistics.
Usage:
    python bench.py --chart=top-100
    python bench.py --chart=weekly-vn
    python bench.py --chart=all
    python bench.py --chart=top-100 --clear-cache
    python bench.py --chart=top-100 --no-playlist
"""

import argparse
import time
from dataclasses import dataclass

from cache import clear_all_caches
from config import CHARTS
from workflow import run_chart_sync


@dataclass
class BenchmarkResult:
    """Stores timing and statistics for a benchmark run."""

    chart_name: str
    total_songs: int = 0
    songs_found: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_time: float = 0.0

    def print_summary(self) -> None:
        print(f"\n{'═' * 75}")
        print(f"Benchmark: {self.chart_name}")
        print(f"{'═' * 75}")
        print(f"Songs found: {self.songs_found}/{self.total_songs}")
        print(f"Cache: {self.cache_hits} hits, {self.cache_misses} misses")
        print(f"Total time: {self.total_time:.2f}s")
        print(f"{'═' * 75}")


def run_benchmark(
    chart_key: str,
    no_playlist: bool = False,
    headless: bool = False,
) -> BenchmarkResult:
    """Run benchmark for a single chart.

    Args:
        chart_key: Key from CHARTS config (e.g., 'top-100', 'weekly-vn')
        no_playlist: Skip playlist creation/update
        headless: Use headless Spotify auth

    Returns:
        BenchmarkResult with timing and statistics
    """
    chart = CHARTS[chart_key]
    result = BenchmarkResult(chart_name=f"{chart_key} ({chart['name']})")

    print(f"\n{'=' * 75}")
    print(f"Running benchmark: {chart['name']}")
    print(f"URL: {chart['url']}")
    print(f"Mode: {chart['mode']}")
    print(f"{'=' * 75}")

    start = time.time()

    # Use unified workflow
    output = run_chart_sync(
        chart_url=chart["url"],
        mode=chart["mode"],
        output_file=chart["output_file"],
        playlist_name=chart["playlist"] if not no_playlist else None,
        sorted_playlist_name=chart.get("sorted_playlist", "") if not no_playlist else "",
        trending_playlist_name=chart.get("trending_playlist", "") if not no_playlist else "",
        headless=headless,
        min_file_size=chart["min_file_size"],
        save_html=False,
        progress_callback=None,  # Silent for benchmark
    )

    result.total_time = time.time() - start

    if output.results:
        result.total_songs = output.stats.total_songs
        result.songs_found = output.stats.songs_found
        result.cache_hits = output.stats.cache_hits
        result.cache_misses = output.stats.cache_misses

    result.print_summary()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark ZingMP3-Spotify sync (simulates GitHub Actions workflows)"
    )
    parser.add_argument(
        "--chart",
        type=str,
        required=True,
        choices=list(CHARTS.keys()) + ["all"],
        help="Chart to benchmark (or 'all' for all charts)",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all caches before running (worst-case benchmark)",
    )
    parser.add_argument(
        "--no-playlist",
        action="store_true",
        help="Skip playlist creation/update (faster testing)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use headless Spotify auth (requires SPOTIFY_REFRESH_TOKEN)",
    )
    args = parser.parse_args()

    if args.clear_cache:
        print("Clearing all caches...")
        clear_all_caches()
        print("Caches cleared!")

    if args.chart == "all":
        charts_to_run = list(CHARTS.keys())
    else:
        charts_to_run = [args.chart]

    all_results = []
    total_start = time.time()

    for chart_key in charts_to_run:
        result = run_benchmark(
            chart_key,
            no_playlist=args.no_playlist,
            headless=args.headless,
        )
        all_results.append(result)

    total_time = time.time() - total_start

    # Print overall summary if multiple charts
    if len(all_results) > 1:
        print(f"\n{'═' * 75}")
        print("OVERALL SUMMARY")
        print(f"{'═' * 75}")
        print(f"{'Chart':<30} {'Songs':>8} {'Found':>8} {'Cached':>8} {'Time':>10}")
        print(f"{'─' * 75}")
        for r in all_results:
            print(
                f"{r.chart_name[:30]:<30} {r.total_songs:>8} {r.songs_found:>8} "
                f"{r.cache_hits:>8} {r.total_time:>10.2f}s"
            )
        print(f"{'─' * 75}")
        total_songs = sum(r.total_songs for r in all_results)
        total_found = sum(r.songs_found for r in all_results)
        total_cached = sum(r.cache_hits for r in all_results)
        print(f"{'TOTAL':<30} {total_songs:>8} {total_found:>8} {total_cached:>8} {total_time:>10.2f}s")
        print(f"{'═' * 75}")


if __name__ == "__main__":
    main()
