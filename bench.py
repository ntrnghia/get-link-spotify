#!/usr/bin/env python3
"""Benchmark tool for ZingMP3-Spotify sync."""

import argparse
import time
from dataclasses import dataclass

from cache import clear_all_caches
from config import CHARTS
from workflow import run_chart_sync


@dataclass
class BenchResult:
    name: str
    total: int = 0
    found: int = 0
    cached: int = 0
    time: float = 0.0

    def print(self) -> None:
        print(f"\n{'═' * 75}\nBenchmark: {self.name}\n{'═' * 75}")
        print(f"Songs found: {self.found}/{self.total}\nCache: {self.cached} hits, {self.total - self.cached} misses")
        print(f"Total time: {self.time:.2f}s\n{'═' * 75}")


def run_benchmark(chart_key: str, no_playlist: bool = False, headless: bool = False) -> BenchResult:
    chart = CHARTS[chart_key]
    result = BenchResult(name=f"{chart_key} ({chart['name']})")

    print(f"\n{'=' * 75}\nRunning benchmark: {chart['name']}\nURL: {chart['url']}\nMode: {chart['mode']}\n{'=' * 75}")

    start = time.time()
    output = run_chart_sync(
        chart_url=chart["url"], mode=chart["mode"], output_file=chart["output_file"],
        playlist_name=chart["playlist"] if not no_playlist else None,
        sorted_playlist_name=chart.get("sorted_playlist", "") if not no_playlist else "",
        trending_playlist_name=chart.get("trending_playlist", "") if not no_playlist else "",
        headless=headless, min_file_size=chart["min_file_size"],
    )
    result.time = time.time() - start

    if output.results:
        result.total, result.found, result.cached = output.stats.total_songs, output.stats.songs_found, output.stats.cache_hits

    result.print()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ZingMP3-Spotify sync")
    parser.add_argument("--chart", type=str, required=True, choices=list(CHARTS.keys()) + ["all"])
    parser.add_argument("--clear-cache", action="store_true", help="Clear caches first")
    parser.add_argument("--no-playlist", action="store_true", help="Skip playlist updates")
    parser.add_argument("--headless", action="store_true", help="Use refresh token auth")
    args = parser.parse_args()

    if args.clear_cache:
        print("Clearing all caches...")
        clear_all_caches()

    charts = list(CHARTS.keys()) if args.chart == "all" else [args.chart]
    results, start = [], time.time()

    for key in charts:
        results.append(run_benchmark(key, args.no_playlist, args.headless))

    if len(results) > 1:
        total_time = time.time() - start
        print(f"\n{'═' * 75}\nOVERALL SUMMARY\n{'═' * 75}")
        print(f"{'Chart':<30} {'Songs':>8} {'Found':>8} {'Cached':>8} {'Time':>10}\n{'─' * 75}")
        for r in results:
            print(f"{r.name[:30]:<30} {r.total:>8} {r.found:>8} {r.cached:>8} {r.time:>10.2f}s")
        print(f"{'─' * 75}")
        print(f"{'TOTAL':<30} {sum(r.total for r in results):>8} {sum(r.found for r in results):>8} "
              f"{sum(r.cached for r in results):>8} {total_time:>10.2f}s\n{'═' * 75}")


if __name__ == "__main__":
    main()
