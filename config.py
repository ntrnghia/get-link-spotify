"""
Configuration constants for ZingMP3-Spotify sync.
All magic numbers and settings centralized here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# PATHS
# =============================================================================
PROJECT_ROOT = Path(__file__).parent
SPOTIFY_CACHE_FILE = PROJECT_ROOT / ".spotify_cache.json"
PROXY_CACHE_FILE = PROJECT_ROOT / ".proxy_cache.json"

# =============================================================================
# TIMEOUTS (seconds)
# =============================================================================
PROXY_TIMEOUT = 20
API_TIMEOUT = 20
REQUEST_TIMEOUT = 20

# =============================================================================
# DELAYS (seconds)
# =============================================================================
REQUEST_DELAY = 0.1  # Delay between Spotify API calls to avoid rate limiting

# =============================================================================
# LIMITS
# =============================================================================
MAX_PROXY_TRIES = 30  # Maximum proxies to try before giving up
PROXY_TEST_WORKERS = 2  # Concurrent proxy testing threads (increased for faster testing)
SPOTIFY_SEARCH_LIMIT = 10  # Results per Spotify search query
SPOTIFY_SEARCH_WORKERS = 4  # Concurrent Spotify search threads (keep low to avoid rate limits)
PLAYLIST_BATCH_SIZE = 100  # Spotify playlist API batch limit
SPOTIFY_RETRY_ATTEMPTS = 3  # Number of retries on rate limit
SPOTIFY_RETRY_DELAY = 2.0  # Base delay for exponential backoff (seconds)

# =============================================================================
# CACHE TTL
# =============================================================================
SPOTIFY_CACHE_TTL_HOURS = 24  # How long to cache Spotify search results
PROXY_CACHE_TTL_MINUTES = 120  # How long to cache working proxies (2 hours for CI)
CACHE_BATCH_SIZE = 10  # Number of writes before flushing to disk

# =============================================================================
# SPOTIFY CREDENTIALS
# =============================================================================
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_REFRESH_TOKEN = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")

# =============================================================================
# URLS
# =============================================================================
ZINGCHART_URL = "https://zingmp3.vn/zing-chart"

# Proxy sources (fetched concurrently)
PROXYSCRAPE_API_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&country=vn&proxy_format=protocolipport&format=json"
GEONODE_API_URL = "https://proxylist.geonode.com/api/proxy-list?country=VN&limit=100&page=1&sort_by=lastChecked&sort_type=desc"
FREE_PROXY_LIST_URL = "https://free-proxy-list.net/"

# =============================================================================
# REQUEST HEADERS
# =============================================================================
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://zingmp3.vn/",
}

# =============================================================================
# EXCEL FORMATTING
# =============================================================================
EXCEL_COLUMN_WIDTHS = [6, 30, 25, 8, 45, 30, 25, 25, 8, 45, 10, 10]
EXCEL_HEADERS = [
    # ZingMP3 data (5 columns)
    "Rank", "Song Name", "Artists", "Duration", "ZingMP3 Link",
    # Spotify data (6 columns)
    "Song Name (Spotify)", "Artists (Spotify)", "Album (Spotify)",
    "Duration (Spotify)", "Spotify Link", "Popularity",
    # Match result (1 column)
    "Match %",
]

# =============================================================================
# CHART CONFIGURATIONS (for bench.py)
# =============================================================================
CHARTS = {
    "top-100": {
        "url": "https://zingmp3.vn/zing-chart",
        "name": "Top 100",
        "playlist": "ZingMP3 Top 100",
        "sorted_playlist": "ZingMP3 Top 100 (sorted by Spotify popularity)",
        "trending_playlist": "ZingMP3 Top 100 (new & trending)",
        "output_file": "zingchart_top_100.xlsx",
        "min_file_size": 100000,
        "mode": "live",
    },
    "weekly-vn": {
        "url": "https://zingmp3.vn/zing-chart-tuan/bai-hat-Viet-Nam/IWZ9Z08I.html",
        "name": "Weekly VN",
        "playlist": "ZingMP3 Weekly VN",
        "sorted_playlist": "",
        "output_file": "zingchart_weekly_vn.xlsx",
        "min_file_size": 50000,
        "mode": "live",
    },
    "weekly-usuk": {
        "url": "https://zingmp3.vn/zing-chart-tuan/bai-hat-US-UK/IWZ9Z0BW.html",
        "name": "Weekly US-UK",
        "playlist": "ZingMP3 Weekly US-UK",
        "sorted_playlist": "",
        "output_file": "zingchart_weekly_usuk.xlsx",
        "min_file_size": 30000,
        "mode": "live",
    },
    "weekly-kpop": {
        "url": "https://zingmp3.vn/zing-chart-tuan/bai-hat-Kpop/IWZ9Z0BO.html",
        "name": "Weekly K-POP",
        "playlist": "ZingMP3 Weekly K-POP",
        "sorted_playlist": "",
        "output_file": "zingchart_weekly_kpop.xlsx",
        "min_file_size": 30000,
        "mode": "live",
    },
}
