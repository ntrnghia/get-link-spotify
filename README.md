# ZingMP3 Chart to Spotify Playlist

Automatically sync ZingMP3's Top 100 chart (https://zingmp3.vn/zing-chart) to a Spotify playlist.

## Features

- Crawl top 100 songs from ZingMP3 chart
- Find matching songs on Spotify
- Create/update a Spotify playlist with the chart songs
- GitHub Actions automation (hourly updates via Vietnam proxies)
- Auto-detect latest stable Python version

## Live Playlist

[ZingMP3 Top 100 on Spotify](https://open.spotify.com/playlist/6F4Uq6BABSn6HupOIrXheZ)

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

# Custom playlist name
python crawl_zingchart.py --playlist --playlist-name "My Chart"
```

## GitHub Actions (Hourly Automation)

The workflow runs automatically every hour at **minute 0** (UTC):
- 00:00, 01:00, 02:00, ... 23:00 UTC

### How It Works

1. Fetches latest stable Python version from GitHub API
2. Gets Vietnam proxy list from proxyscrape API
3. Tries proxies until one successfully fetches ZingMP3 chart
4. Parses chart and finds matching Spotify tracks
5. Updates the Spotify playlist

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

Go to **Actions** tab > "Update ZingMP3 Playlist" > "Run workflow"

## Tech Stack

- Python (auto-detect latest stable version)
- [spotipy](https://github.com/spotipy-dev/spotipy) - Spotify API wrapper
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- GitHub Actions - CI/CD automation

## License

MIT
