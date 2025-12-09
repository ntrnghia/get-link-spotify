# ZingMP3 Charts to Spotify Playlists

Automatically sync ZingMP3 charts to Spotify playlists.

## Features

- Sync multiple ZingMP3 charts to Spotify playlists
- **Concurrent proxy testing** with early exit on first success
- **Concurrent Spotify search** with file-based caching (24h TTL)
- Fast string matching using [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)
- Comprehensive match scoring (title, artist, duration - 33% each)
- Excel output with side-by-side ZingMP3 and Spotify data comparison
- Optional popularity-sorted playlist creation
- GitHub Actions automation with Vietnam proxies
- Auto-detect latest stable Python version
- DRY workflow architecture (reusable workflow)
- **Benchmark tool** for testing all charts locally

## Live Playlists

| Playlist | Songs | Schedule | Link |
|----------|-------|----------|------|
| ZingMP3 Top 100 | 100 | Every hour | [Open](https://open.spotify.com/playlist/6F4Uq6BABSn6HupOIrXheZ) |
| ZingMP3 Top 100 (sorted by Spotify popularity) | 100 | Every hour | [Open](https://open.spotify.com/playlist/64TpllojsS4Tj4n8eyIgu3) |
| ZingMP3 Top 100 (new & trending) | 100 | Every hour | [Open](https://open.spotify.com/playlist/1KjsCsUthDVwi0XMHZJ5jz) |
| ZingMP3 Weekly VN | 40 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/3bvdEpWQUuMSiEWB3bw1ZD) |
| ZingMP3 Weekly US-UK | 20 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/4NKRGmHpU5gbMM6W0raGZR) |
| ZingMP3 Weekly K-POP | 20 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/4sbme4bfHlU02n3lhCgzhQ) |

> **New & Trending**: Songs sorted by `normalized_rank + normalized_popularity` (ascending). Both values are scaled 0-1 based on actual min/max. Lower score = high chart position + low Spotify popularity = truly new/trending songs.

## Supported Charts

| Chart | URL | Songs |
|-------|-----|-------|
| Top 100 | https://zingmp3.vn/zing-chart | 100 |
| Weekly VN | https://zingmp3.vn/zing-chart-tuan/bai-hat-Viet-Nam/IWZ9Z08I.html | 40 |
| Weekly US-UK | https://zingmp3.vn/zing-chart-tuan/bai-hat-US-UK/IWZ9Z0BW.html | 20 |
| Weekly K-POP | https://zingmp3.vn/zing-chart-tuan/bai-hat-Kpop/IWZ9Z0BO.html | 20 |

## Setup

### 1. Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://127.0.0.1:8888/callback` to Redirect URIs
4. Copy your Client ID and Client Secret

### 2. Local Development

```bash
# Clone the repo
git clone https://github.com/ntrnghia/get-link-spotify.git
cd get-link-spotify

# Create virtual environment
python -m venv env
env\Scripts\activate  # Windows
# source env/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
echo "SPOTIFY_CLIENT_ID=your_client_id" > .env
echo "SPOTIFY_CLIENT_SECRET=your_client_secret" >> .env
```

### 3. Usage

```bash
# Using saved chart.html (offline)
python main.py

# Fetch live from ZingMP3 (requires VPN to Vietnam)
python main.py --vpn

# Fetch live using Vietnam proxies
python main.py --live

# Update Spotify playlist
python main.py --playlist

# Custom chart URL and playlist name
python main.py --live --playlist \
  --chart-url "https://zingmp3.vn/zing-chart-tuan/bai-hat-Viet-Nam/IWZ9Z08I.html" \
  --playlist-name "ZingMP3 Weekly VN" \
  --output-file "weekly_vn.xlsx"

# Create additional playlist sorted by Spotify popularity
python main.py --playlist \
  --playlist-name "ZingMP3 Top 100" \
  --sorted-playlist-name "ZingMP3 Top 100 (sorted by Spotify popularity)"

# Create trending playlist (sorted by rank + popularity, new & trending first)
python main.py --playlist \
  --playlist-name "ZingMP3 Top 100" \
  --trending-playlist-name "ZingMP3 Top 100 (new & trending)"
```

### 4. Benchmark Tool

Test performance locally with the benchmark tool:

```bash
# Benchmark Top 100 chart
python bench.py --chart=top-100

# Benchmark all charts
python bench.py --chart=all

# Clear cache before benchmark (worst-case timing)
python bench.py --chart=top-100 --clear-cache

# Skip playlist updates (faster testing)
python bench.py --chart=top-100 --no-playlist
```

## GitHub Actions Automation

### Workflow Schedules

| Workflow | Schedule | Description |
|----------|----------|-------------|
| Update ZingMP3 Top 100 | Every hour | Main chart (100 songs) |
| Update ZingMP3 Weekly VN | Sunday 17:00 UTC | Vietnam weekly (40 songs) |
| Update ZingMP3 Weekly US-UK | Sunday 17:00 UTC | US-UK weekly (20 songs) |
| Update ZingMP3 Weekly K-POP | Sunday 17:00 UTC | K-POP weekly (20 songs) |

> Note: Sunday 17:00 UTC = Monday 0:00 Vietnam time (UTC+7)

### How It Works

1. Fetches latest stable Python version from GitHub API
2. Restores Spotify/proxy cache from previous runs (single cache entry, updated each run)
3. Gets Vietnam proxies from multiple sources concurrently (ProxyScrape, Free-Proxy-List)
4. Tests cached proxies first, then fresh proxies concurrently (2 workers) with early exit on first success:
   - **Top 100**: Parses JSON-LD from desktop site HTML
   - **Weekly charts**: Parses mobile site (`m.zingmp3.vn`) which has server-side rendered data
5. Searches Spotify concurrently (4 workers) with caching:
   - Cache hits skip API calls entirely (24h TTL)
   - Uses rapidfuzz for fast string similarity matching
   - Scores matches using title, artist, duration (33% each)
6. Updates the Spotify playlist (and optional popularity-sorted/trending playlists)
7. Deletes old cache and saves updated cache (maintains single cache entry)

### Setup Secrets

Go to your repo **Settings > Secrets and variables > Actions**, and add:

| Secret | Description |
|--------|-------------|
| `SPOTIFY_CLIENT_ID` | Your Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | Get from `.cache` file after first local run |

### Get Refresh Token

1. Run locally with `--playlist` flag once:
   ```bash
   python main.py --playlist
   ```
2. Browser will open for Spotify login
3. After login, check `.cache` file for `refresh_token`
4. Copy the token value to GitHub Secrets

### Manual Trigger

Go to **Actions** tab > Select any workflow > "Run workflow"

## Project Structure

```
├── main.py             # CLI entry point
├── bench.py            # Benchmark tool
├── config.py           # Centralized configuration
├── models.py           # Type-safe dataclasses
├── cache.py            # File-based JSON caching with TTL
├── proxy.py            # Concurrent proxy fetching/testing
├── spotify.py          # Concurrent Spotify search with caching
├── zingmp3.py          # Chart parsing (HTML/JSON-LD, mobile API)
├── workflow.py         # Unified sync logic
├── excel.py            # Excel export
├── .spotify_cache.json # Spotify search cache (auto-generated)
├── .proxy_cache.json   # Working proxy cache (auto-generated)
└── .github/workflows/
    ├── sync-chart.yml  # Reusable workflow (DRY)
    ├── top-100.yml     # Top 100 (every hour)
    ├── weekly-vn.yml   # Weekly VN (every Monday)
    ├── weekly-usuk.yml # Weekly US-UK (every Monday)
    └── weekly-kpop.yml # Weekly K-POP (every Monday)
```

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `PROXY_TIMEOUT` | 30s | Total timeout for proxy requests (split: 15s connect, 15s read) |
| `PROXY_TEST_WORKERS` | 2 | Concurrent proxy testing threads |
| `PROXY_CACHE_TTL_MINUTES` | 120 | How long to cache working proxies (2 hours) |
| `SPOTIFY_SEARCH_WORKERS` | 4 | Concurrent Spotify search threads |
| `SPOTIFY_CACHE_TTL_HOURS` | 24 | How long to cache Spotify search results |
| `CACHE_BATCH_SIZE` | 10 | Writes before flushing cache to disk |

## Tech Stack

- Python 3.11+ (auto-detect latest stable version)
- [spotipy](https://github.com/spotipy-dev/spotipy) - Spotify API wrapper
- [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) - Fast string similarity matching
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [openpyxl](https://openpyxl.readthedocs.io/) - Excel file generation
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable loading
- GitHub Actions - CI/CD automation

## License

MIT
