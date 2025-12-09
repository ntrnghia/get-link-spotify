# ZingMP3 Chart to Spotify Playlist

Automatically sync ZingMP3 charts to Spotify playlists.

## Features

- Sync multiple ZingMP3 charts to Spotify playlists
- GitHub Actions automation with Vietnam proxies
- Auto-detect latest stable Python version
- DRY workflow architecture (reusable workflow)

## Live Playlists

| Playlist | Songs | Schedule | Link |
|----------|-------|----------|------|
| ZingMP3 Top 100 | 100 | Every hour | [Open](https://open.spotify.com/playlist/6F4Uq6BABSn6HupOIrXheZ) |
| ZingMP3 Weekly VN | 40 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/3bvdEpWQUuMSiEWB3bw1ZD) |
| ZingMP3 Weekly US-UK | 20 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/4NKRGmHpU5gbMM6W0raGZR) |
| ZingMP3 Weekly K-POP | 20 | Every Monday 0:00 VN | [Open](https://open.spotify.com/playlist/4sbme4bfHlU02n3lhCgzhQ) |

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
cp .env.example .env
# Edit .env and add your Spotify credentials
```

### 3. Usage

```bash
# Using saved chart.html (offline)
python crawl_zingchart.py

# Fetch live from ZingMP3 (requires VPN to Vietnam)
python crawl_zingchart.py --vpn

# Fetch live using Vietnam proxies
python crawl_zingchart.py --live

# Update Spotify playlist
python crawl_zingchart.py --playlist

# Custom chart URL and playlist name
python crawl_zingchart.py --live --playlist \
  --chart-url "https://zingmp3.vn/zing-chart-tuan/bai-hat-Viet-Nam/IWZ9Z08I.html" \
  --playlist-name "ZingMP3 Weekly VN" \
  --output-file "weekly_vn.xlsx"
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
2. Gets Vietnam proxy list from ProxyScrape API
3. Tries proxies until one successfully fetches ZingMP3 chart:
   - **Top 100**: Parses JSON-LD from desktop site HTML
   - **Weekly charts**: Parses mobile site (`m.zingmp3.vn`) which has server-side rendered data
4. Retries up to 3 times per proxy for partial data
5. Searches Spotify for matching tracks
6. Updates the Spotify playlist

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
   python crawl_zingchart.py --playlist
   ```
2. Browser will open for Spotify login
3. After login, check `.cache` file for `refresh_token`
4. Copy the token value to GitHub Secrets

### Manual Trigger

Go to **Actions** tab > Select any workflow > "Run workflow"

## Project Structure

```
.github/workflows/
├── sync-chart.yml      # Reusable workflow (DRY)
├── top-100.yml         # Top 100 (every hour)
├── weekly-vn.yml       # Weekly VN (every Monday)
├── weekly-usuk.yml     # Weekly US-UK (every Monday)
└── weekly-kpop.yml     # Weekly K-POP (every Monday)
```

## Tech Stack

- Python (auto-detect latest stable version)
- [spotipy](https://github.com/spotipy-dev/spotipy) - Spotify API wrapper
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- GitHub Actions - CI/CD automation

## License

MIT
