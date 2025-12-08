"""
ZingMP3 Chart Crawler with Spotify Links
Parses top 100 songs from chart.html or fetches live from zingmp3.vn using Vietnam proxies
"""

import argparse
import json
import os
import re
import csv
import time
import warnings
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

# Suppress SSL warnings for proxies
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Spotify credentials (from env vars or .env file)
# For local development, create a .env file with:
#   SPOTIFY_CLIENT_ID=your_client_id
#   SPOTIFY_CLIENT_SECRET=your_client_secret
#   SPOTIFY_REFRESH_TOKEN=your_refresh_token (optional, for headless mode)
def _load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env_file()

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# ZingMP3 Chart URL
ZINGCHART_URL = "https://zingmp3.vn/zing-chart"

# Proxy sources
GEONODE_API_URL = "https://proxylist.geonode.com/api/proxy-list?country=VN&limit=50&page=1&sort_by=speed&sort_type=asc"
FREE_PROXY_API_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&country=vn&proxy_format=protocolipport&format=json"

# Request headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
}


def fetch_vietnam_proxies() -> list[dict]:
    """Fetch Vietnam proxies from multiple sources, sorted by speed (fastest first)."""
    proxies = []

    # Source 1: Geonode API
    print("  Fetching from Geonode API...")
    try:
        response = requests.get(GEONODE_API_URL, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for proxy in data.get('data', []):
                proxies.append({
                    'ip': proxy.get('ip', ''),
                    'port': proxy.get('port', ''),
                    'speed': proxy.get('speed', 9999),
                    'source': 'geonode'
                })
            print(f"    Found {len(data.get('data', []))} proxies from Geonode")
    except Exception as e:
        print(f"    Geonode failed: {e}")

    # Source 2: ProxyScrape API
    print("  Fetching from ProxyScrape API...")
    try:
        response = requests.get(FREE_PROXY_API_URL, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            proxy_list = data.get('proxies', [])
            for proxy in proxy_list:
                proxies.append({
                    'ip': proxy.get('ip', ''),
                    'port': str(proxy.get('port', '')),
                    'speed': proxy.get('timeout', 9999),
                    'source': 'proxyscrape'
                })
            print(f"    Found {len(proxy_list)} proxies from ProxyScrape")
    except Exception as e:
        print(f"    ProxyScrape failed: {e}")

    # Source 3: Free Proxy List (backup - scraping)
    if len(proxies) < 5:
        print("  Fetching from free-proxy-list.net...")
        try:
            response = requests.get(
                "https://free-proxy-list.net/",
                headers=HEADERS,
                timeout=15
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table')
                if table:
                    rows = table.find_all('tr')[1:]  # Skip header
                    vn_count = 0
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 8:
                            country = cols[2].get_text(strip=True)
                            if country == 'VN' or country == 'Vietnam':
                                proxies.append({
                                    'ip': cols[0].get_text(strip=True),
                                    'port': cols[1].get_text(strip=True),
                                    'speed': 5000,  # Default speed
                                    'source': 'free-proxy-list'
                                })
                                vn_count += 1
                    print(f"    Found {vn_count} Vietnam proxies from free-proxy-list")
        except Exception as e:
            print(f"    free-proxy-list failed: {e}")

    # Remove duplicates and invalid entries
    seen = set()
    unique_proxies = []
    for p in proxies:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen and p['ip'] and p['port']:
            seen.add(key)
            unique_proxies.append(p)

    # Sort by speed (fastest first)
    unique_proxies.sort(key=lambda x: x.get('speed', 9999))

    print(f"  Total unique Vietnam proxies: {len(unique_proxies)}")
    return unique_proxies


def fetch_with_proxy(url: str, proxy: dict, timeout: int = 15) -> str | None:
    """Try to fetch URL using given proxy. Returns HTML content or None."""
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            proxies=proxies,
            timeout=timeout,
            verify=False  # Some proxies have SSL issues
        )
        if response.status_code == 200:
            return response.text
    except requests.exceptions.RequestException:
        pass

    return None


def fetch_zingchart_direct() -> str | None:
    """Fetch zing-chart page directly (requires VPN to be connected). Returns HTML content or None."""
    print("\n[VPN MODE] Fetching ZingMP3 chart directly (VPN must be connected)...")

    try:
        response = requests.get(
            ZINGCHART_URL,
            headers=HEADERS,
            timeout=30
        )
        if response.status_code == 200 and 'MusicPlaylist' in response.text:
            print("  SUCCESS! Got chart data.")
            return response.text
        elif response.status_code == 200:
            print("  Page loaded but no chart data (geo-blocked?)")
            return None
        else:
            print(f"  Failed: HTTP {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  Connection error: {e}")
        return None


def fetch_zingchart_live() -> str | None:
    """Fetch zing-chart page using Vietnam proxies. Returns HTML content or None."""
    print("\n[PROXY MODE] Fetching ZingMP3 chart using Vietnam proxies...")

    proxies = fetch_vietnam_proxies()
    if not proxies:
        print("  No proxies available!")
        return None

    max_tries = min(30, len(proxies))  # Try up to 30 proxies

    # Try each proxy
    for i, proxy in enumerate(proxies[:max_tries], 1):
        source = proxy.get('source', 'unknown')
        speed = proxy.get('speed', '?')
        print(f"  [{i:2d}/{max_tries}] {proxy['ip']}:{proxy['port']} ({source}, {speed}ms)...", end=" ", flush=True)

        html = fetch_with_proxy(ZINGCHART_URL, proxy)

        if html and 'MusicPlaylist' in html:
            print("SUCCESS!")
            return html
        elif html:
            print("No chart data (geo-blocked?)")
        else:
            print("Connection failed")

    print("  All proxies failed!")
    return None


def parse_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration to MM:SS format.

    Example: PT5M20S -> 5:20
    """
    if not iso_duration:
        return ""

    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return iso_duration

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_chart_content(html_content: str) -> list[dict]:
    """Parse HTML content and extract song data from JSON-LD.

    Returns list of songs with: position, name, duration, artists
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all JSON-LD scripts
    json_ld_scripts = soup.find_all('script', type='application/ld+json')

    songs = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)

            # Look for MusicPlaylist type
            if data.get('@type') == 'MusicPlaylist':
                items = data.get('track', {}).get('itemListElement', [])

                for item in items:
                    song_data = item.get('item', {})
                    artists = song_data.get('byArtist', [])
                    artist_names = [a.get('name', '') for a in artists]

                    songs.append({
                        'position': item.get('position'),
                        'name': song_data.get('name', ''),
                        'duration': parse_duration(song_data.get('duration', '')),
                        'artists': ', '.join(artist_names),
                        'artist_list': artist_names  # Keep list for search
                    })

                break
        except json.JSONDecodeError:
            continue

    return songs


def parse_chart_file(filepath: str) -> list[dict]:
    """Parse chart.html file and extract song data."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    return parse_chart_content(html_content)


def get_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client with client credentials (read-only)."""
    auth_manager = SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_spotify_client_with_auth() -> spotipy.Spotify:
    """Initialize Spotify client with user authorization (for playlist management).

    First time: Opens browser for user login.
    Subsequent runs: Uses cached token from .cache file.
    """
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private"
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_spotify_client_headless() -> spotipy.Spotify:
    """Initialize Spotify client using refresh token (for CI/headless mode).

    Requires SPOTIFY_REFRESH_TOKEN environment variable.
    """
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if not refresh_token:
        raise ValueError("SPOTIFY_REFRESH_TOKEN environment variable not set")

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private",
        open_browser=False
    )

    # Create token info and refresh it
    token_info = auth_manager.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth=token_info['access_token'])


def create_or_get_playlist(sp: spotipy.Spotify, playlist_name: str) -> tuple[str, bool]:
    """Create playlist or get existing one.

    Returns tuple of (playlist_id, is_new).
    """
    user_id = sp.current_user()['id']

    # Search existing playlists
    playlists = sp.current_user_playlists(limit=50)
    while playlists:
        for playlist in playlists['items']:
            if playlist['name'] == playlist_name:
                return playlist['id'], False

        # Get next page
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            break

    # Create new playlist
    new_playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=True,
        description="ZingMP3 Top 100 Chart - Auto-updated by ZingChart Crawler"
    )
    return new_playlist['id'], True


def update_playlist(sp: spotipy.Spotify, playlist_id: str, track_ids: list[str]) -> int:
    """Replace all tracks in playlist with new ones.

    Returns number of tracks added.
    """
    # Filter out None/empty track IDs
    valid_track_ids = [tid for tid in track_ids if tid]

    if not valid_track_ids:
        return 0

    # Clear existing tracks by replacing with new ones
    # Spotify API allows up to 100 tracks per request
    sp.playlist_replace_items(playlist_id, valid_track_ids[:100])

    # If more than 100 tracks, add the rest
    if len(valid_track_ids) > 100:
        for i in range(100, len(valid_track_ids), 100):
            batch = valid_track_ids[i:i+100]
            sp.playlist_add_items(playlist_id, batch)

    return len(valid_track_ids)


def normalize_title(title: str) -> str:
    """Normalize title for comparison (lowercase, remove extra spaces)."""
    return ' '.join(title.lower().split())


def title_match_score(search_title: str, spotify_title: str) -> int:
    """Score how well a Spotify title matches the search title.

    Higher score = better match.
    """
    search_norm = normalize_title(search_title)
    spotify_norm = normalize_title(spotify_title)

    # Exact match (ignoring case) = highest score
    if search_norm == spotify_norm:
        return 100

    # Check for unwanted suffixes in Spotify result
    # If we're NOT searching for a remix/cover but Spotify returns one, penalize
    suffixes = ['remix', 'cover', 'acoustic', 'live', 'version', 'edit', 'mix']
    search_has_suffix = any(s in search_norm for s in suffixes)
    spotify_has_suffix = any(s in spotify_norm for s in suffixes)

    if not search_has_suffix and spotify_has_suffix:
        return 10  # Heavy penalty - we don't want remixes when searching for original

    if search_has_suffix and not spotify_has_suffix:
        return 20  # We want a remix but got original - not ideal

    # Partial match - Spotify title starts with or contains search title
    if spotify_norm.startswith(search_norm):
        return 80

    if search_norm in spotify_norm:
        return 60

    # Default - some match but not great
    return 40


def search_spotify(sp: spotipy.Spotify, song_name: str, artists: list[str]) -> dict | None:
    """Search for a song on Spotify.

    Returns dict with: url, album_name, track_uri, or None if not found
    """
    # Try different search strategies
    search_queries = []

    # Strategy 1: Full search with song name and first artist
    if artists:
        search_queries.append(f'track:"{song_name}" artist:"{artists[0]}"')

    # Strategy 2: Just song name and artist without quotes
    if artists:
        search_queries.append(f'{song_name} {artists[0]}')

    # Strategy 3: Just song name
    search_queries.append(song_name)

    for query in search_queries:
        try:
            results = sp.search(q=query, type='track', limit=10)  # Get more results to find best match
            tracks = results.get('tracks', {}).get('items', [])

            if tracks:
                # Score each track and pick the best match
                best_track = None
                best_score = -1

                for track in tracks:
                    score = title_match_score(song_name, track['name'])
                    if score > best_score:
                        best_score = score
                        best_track = track

                if best_track:
                    return {
                        'url': best_track['external_urls'].get('spotify', ''),
                        'album_name': best_track['album'].get('name', ''),
                        'spotify_artist': ', '.join([a['name'] for a in best_track['artists']]),
                        'track_uri': best_track['uri']  # For playlist management
                    }
        except Exception as e:
            print(f"  Search error for '{query}': {e}")
            continue

    return None


def main():
    """Main function to crawl chart and find Spotify links."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ZingMP3 Chart Crawler with Spotify Links')
    parser.add_argument('--vpn', action='store_true',
                        help='Fetch live data directly (requires VPN to be connected first)')
    parser.add_argument('--live', action='store_true',
                        help='Fetch live data using Vietnam proxies (unreliable)')
    parser.add_argument('--save-html', action='store_true',
                        help='Save fetched HTML to chart_live.html (only with --vpn or --live)')
    parser.add_argument('--playlist', action='store_true',
                        help='Create/update Spotify playlist with chart songs (requires browser login)')
    parser.add_argument('--playlist-name', type=str, default='ZingMP3 Top 100',
                        help='Name of the Spotify playlist (default: "ZingMP3 Top 100")')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless/CI mode (uses SPOTIFY_REFRESH_TOKEN env var)')
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    html_file = script_dir / 'chart.html'
    output_csv = script_dir / 'zingchart_spotify.csv'

    print("=" * 60)
    print("ZingMP3 Chart Crawler with Spotify Links")
    if args.vpn:
        print("Mode: VPN (direct fetch - VPN must be connected)")
    elif args.live:
        print("Mode: PROXY (fetching via Vietnam proxies - unreliable)")
    else:
        print("Mode: LOCAL (using saved chart.html)")
    if args.playlist:
        print(f"Playlist: Will create/update '{args.playlist_name}'")
    if args.headless:
        print("Auth: Headless mode (using refresh token)")
    print("=" * 60)

    # Get HTML content
    html_content = None

    if args.vpn:
        # VPN mode - direct fetch
        html_content = fetch_zingchart_direct()
        if not html_content:
            print("\nFailed to fetch via VPN. Make sure VPN is connected!")
            print("Falling back to local chart.html...")

    elif args.live:
        # Proxy mode
        html_content = fetch_zingchart_live()
        if not html_content:
            print("\nFailed to fetch via proxies. Falling back to local chart.html...")

    # Process HTML content or fallback to local file
    if html_content:
        # Optionally save HTML
        if args.save_html:
            save_path = script_dir / 'chart_live.html'
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  Saved HTML to {save_path}")

        print(f"\n[1/3] Parsing live HTML content...")
        songs = parse_chart_content(html_content)
    else:
        # Use local file - check for chart_live.html first (from proxy fetch), then chart.html
        chart_live_file = script_dir / 'chart_live.html'
        if chart_live_file.exists():
            print(f"\n[1/3] Parsing {chart_live_file} (fetched via proxy)...")
            songs = parse_chart_file(str(chart_live_file))
        elif html_file.exists():
            print(f"\n[1/3] Parsing {html_file}...")
            songs = parse_chart_file(str(html_file))
        else:
            print(f"ERROR: No chart HTML found (checked chart_live.html and chart.html). Cannot continue.")
            import sys
            sys.exit(1)

    print(f"Found {len(songs)} songs")

    # Check Spotify credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("\nERROR: Spotify credentials not found!")
        print("Please set environment variables or create a .env file with:")
        print("  SPOTIFY_CLIENT_ID=your_client_id")
        print("  SPOTIFY_CLIENT_SECRET=your_client_secret")
        return

    # Initialize Spotify
    print("\n[2/3] Connecting to Spotify API...")
    if args.playlist:
        if args.headless:
            print("  (Using refresh token for headless mode)")
            sp = get_spotify_client_headless()
        else:
            print("  (Using user authorization for playlist management)")
            sp = get_spotify_client_with_auth()
    else:
        sp = get_spotify_client()
    print("Connected!")

    # Search Spotify for each song
    print("\n[3/3] Searching Spotify for each song...")
    results = []
    track_uris = []  # Collect track URIs for playlist

    for song in songs:
        pos = song['position']
        name = song['name']
        artists = song['artist_list']

        print(f"  [{pos:3d}/100] {name} - {song['artists'][:30]}...", end=" ")

        spotify_result = search_spotify(sp, name, artists)

        if spotify_result:
            print(f"FOUND")
            results.append({
                'rank': pos,
                'song_name': name,
                'artists': song['artists'],
                'duration': song['duration'],
                'album': spotify_result['album_name'],
                'spotify_link': spotify_result['url']
            })
            track_uris.append(spotify_result['track_uri'])
        else:
            print("NOT FOUND")
            results.append({
                'rank': pos,
                'song_name': name,
                'artists': song['artists'],
                'duration': song['duration'],
                'album': '',
                'spotify_link': 'Not found'
            })

        # Small delay to avoid rate limiting
        time.sleep(0.1)

    # Save to CSV
    print(f"\nSaving results to {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['rank', 'song_name', 'artists', 'duration', 'album', 'spotify_link'])
        writer.writeheader()
        writer.writerows(results)

    # Summary
    found_count = sum(1 for r in results if r['spotify_link'] != 'Not found')
    print(f"\n{'=' * 60}")
    print(f"CSV saved to: {output_csv}")
    print(f"Found on Spotify: {found_count}/{len(results)} songs")

    # Update Spotify playlist if requested
    if args.playlist:
        print(f"\n[4/4] Updating Spotify playlist...")
        playlist_id, is_new = create_or_get_playlist(sp, args.playlist_name)
        if is_new:
            print(f"  Created new playlist: '{args.playlist_name}'")
        else:
            print(f"  Found existing playlist: '{args.playlist_name}'")

        tracks_added = update_playlist(sp, playlist_id, track_uris)
        print(f"  Added {tracks_added} tracks to playlist")
        playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
        print(f"  Playlist URL: {playlist_url}")

    print(f"\n{'=' * 60}")
    print("DONE!")
    print(f"{'=' * 60}")

    # Print first 10 as preview
    print("\nPreview (Top 10):")
    print("-" * 80)
    for r in results[:10]:
        status = "OK" if r['spotify_link'] != 'Not found' else "NOT FOUND"
        print(f"#{r['rank']:2d} | {r['song_name'][:25]:25s} | {r['artists'][:20]:20s} | {status}")


if __name__ == '__main__':
    main()
