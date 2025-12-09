"""
ZingMP3 chart parsing and fetching.
Supports both HTML/JSON-LD parsing and mobile API.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

from config import (
    API_HEADERS,
    API_TIMEOUT,
    BROWSER_HEADERS,
    REQUEST_TIMEOUT,
    ZINGCHART_URL,
)
from proxy import fetch_with_proxy_rotation


def is_weekly_chart_url(url: str) -> bool:
    """Check if URL is a weekly chart (requires API access)."""
    return "zing-chart-tuan" in url


def parse_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration to MM:SS format.

    Example: PT5M20S -> 5:20
    """
    if not iso_duration:
        return ""

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
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

    Returns list of songs with: position, name, duration, artists, artist_list, url
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all JSON-LD scripts
    json_ld_scripts = soup.find_all("script", type="application/ld+json")

    songs = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)

            # Look for MusicPlaylist type
            if data.get("@type") == "MusicPlaylist":
                items = data.get("track", {}).get("itemListElement", [])

                for item in items:
                    song_data = item.get("item", {})
                    artists = song_data.get("byArtist", [])
                    artist_names = [a.get("name", "") for a in artists]

                    songs.append({
                        "position": item.get("position"),
                        "name": song_data.get("name", ""),
                        "duration": parse_duration(song_data.get("duration", "")),
                        "artists": ", ".join(artist_names),
                        "artist_list": artist_names,
                        "url": item.get("url", ""),
                    })

                break
        except json.JSONDecodeError:
            continue

    return songs


def parse_chart_file(filepath: str) -> list[dict]:
    """Parse chart HTML file and extract song data."""
    with open(filepath, "r", encoding="utf-8") as f:
        html_content = f.read()
    return parse_chart_content(html_content)


def parse_api_chart_items(items: list[dict]) -> list[dict]:
    """Parse chart items from ZingMP3 API response.

    Returns list of songs with: position, name, duration, artists, artist_list
    """
    songs = []
    for i, item in enumerate(items, 1):
        # Parse duration from seconds
        duration_sec = item.get("duration", 0)
        if duration_sec:
            minutes = duration_sec // 60
            seconds = duration_sec % 60
            duration = f"{minutes}:{seconds:02d}"
        else:
            duration = ""

        # Get artists
        artists_names = item.get("artistsNames", "") or ""
        artist_list = [a.strip() for a in artists_names.split(",") if a.strip()]

        songs.append({
            "position": i,
            "name": item.get("title", ""),
            "duration": duration,
            "artists": artists_names,
            "artist_list": artist_list,
            "url": "",
        })

    return songs


def parse_mobile_weekly_chart(html: str) -> list[dict] | None:
    """Parse weekly chart from mobile site HTML.

    Returns list of songs with: position, name, duration, artists, artist_list
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find all chart items
    chart_items = soup.find_all("li", class_="z-chart-item")
    if not chart_items:
        return None

    songs = []
    for item in chart_items:
        # Get rank
        rank_elem = item.find(class_="sort-number")
        rank = rank_elem.get_text(strip=True) if rank_elem else str(len(songs) + 1)

        # Get card-info
        card_info = item.find(class_="card-info")
        if not card_info:
            continue

        # Get title
        title_elem = card_info.find(class_="title")
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Get artist
        artist_elem = card_info.find(class_="artist")
        artist = artist_elem.get_text(strip=True) if artist_elem else ""

        if title:
            # Parse artists into list
            artist_list = [a.strip() for a in artist.split(",") if a.strip()]

            songs.append({
                "position": int(rank) if rank.isdigit() else len(songs) + 1,
                "name": title,
                "duration": "",  # Mobile site doesn't show duration
                "artists": artist,
                "artist_list": artist_list,
                "url": "",
            })

    return songs if songs else None


def get_mobile_weekly_url(chart_url: str) -> str:
    """Convert desktop weekly chart URL to mobile URL."""
    return chart_url.replace("://zingmp3.vn/", "://m.zingmp3.vn/")


def fetch_zingchart_direct(chart_url: str | None = None) -> str | None:
    """Fetch zing-chart page directly (requires VPN). Returns HTML or None."""
    url = chart_url or ZINGCHART_URL
    print(f"\n[VPN MODE] Fetching {url} directly (VPN must be connected)...")

    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200 and "MusicPlaylist" in response.text:
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


def fetch_zingchart_live(chart_url: str | None = None, min_size: int = 0) -> str | None:
    """Fetch zing-chart page using Vietnam proxies. Returns HTML or None."""
    url = chart_url or ZINGCHART_URL
    print(f"\n[PROXY MODE] Fetching {url} using Vietnam proxies...")

    html, _ = fetch_with_proxy_rotation(url, content_check="MusicPlaylist", min_size=min_size)
    return html


def fetch_weekly_chart_live(chart_url: str) -> list[dict] | None:
    """Fetch weekly chart from mobile site with Vietnam proxies.

    Returns list of songs directly or None if failed.
    """
    mobile_url = get_mobile_weekly_url(chart_url)
    print(f"\n[MOBILE MODE] Fetching weekly chart from {mobile_url}...")

    html, _ = fetch_with_proxy_rotation(
        mobile_url, content_check="z-chart-item", min_size=0
    )

    if html:
        songs = parse_mobile_weekly_chart(html)
        if songs:
            print(f"  Parsed {len(songs)} songs")
            return songs

    return None
