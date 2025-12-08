# ZingMP3 Chart to Spotify Playlist

Automatically sync ZingMP3's Top 100 chart to a Spotify playlist.

## Features

- Crawl top 100 songs from ZingMP3 chart
- Find matching songs on Spotify
- Create/update a Spotify playlist with the chart songs
- GitHub Actions automation for hourly updates

## Setup

### 1. Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://127.0.0.1:8888/callback` to Redirect URIs
4. Copy your Client ID and Client Secret

### 2. Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/get-link-spotify.git
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

# Fetch live using Vietnam proxies (unreliable)
python crawl_zingchart.py --live

# Update Spotify playlist
python crawl_zingchart.py --vpn --playlist

# Custom playlist name
python crawl_zingchart.py --vpn --playlist --playlist-name "My Chart"
```

## GitHub Actions (Hourly Automation)

### Setup Secrets

Go to your repo Settings > Secrets and variables > Actions, and add:

- `SPOTIFY_CLIENT_ID` - Your Spotify app client ID
- `SPOTIFY_CLIENT_SECRET` - Your Spotify app client secret
- `SPOTIFY_REFRESH_TOKEN` - Get from `.cache` file after first local run

### Manual Trigger

Go to Actions tab > "Update ZingMP3 Playlist" > "Run workflow"

## License

MIT
