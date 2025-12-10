"""ZingMP3 chart parsing and fetching."""

import json
import re

import requests
from bs4 import BeautifulSoup

from config import BROWSER_HEADERS, REQUEST_TIMEOUT, ZINGCHART_URL
from proxy import fetch_with_proxy_rotation


def is_weekly_chart_url(url: str) -> bool:
    return "zing-chart-tuan" in url


def _parse_duration(iso: str) -> str:
    """Convert ISO 8601 duration (PT5M20S) to M:SS format."""
    if not iso or not (m := re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)):
        return iso or ""
    h, mins, s = int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0)
    return f"{h}:{mins:02d}:{s:02d}" if h else f"{mins}:{s:02d}"


def _make_song(pos: int, name: str, duration: str, artists: str | list, url: str = "") -> dict:
    """Create standardized song dict."""
    artist_list = artists if isinstance(artists, list) else [a.strip() for a in artists.split(",") if a.strip()]
    return {
        "position": pos, "name": name, "duration": duration,
        "artists": ", ".join(artist_list) if isinstance(artists, list) else artists,
        "artist_list": artist_list, "url": url,
    }


def parse_chart_content(html: str) -> list[dict]:
    """Parse HTML and extract songs from JSON-LD."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if data.get("@type") == "MusicPlaylist":
                return [
                    _make_song(
                        item.get("position"), item.get("item", {}).get("name", ""),
                        _parse_duration(item.get("item", {}).get("duration", "")),
                        [a.get("name", "") for a in item.get("item", {}).get("byArtist", [])],
                        item.get("url", ""),
                    )
                    for item in data.get("track", {}).get("itemListElement", [])
                ]
        except json.JSONDecodeError:
            continue
    return []


def parse_chart_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        return parse_chart_content(f.read())


def parse_mobile_weekly_chart(html: str) -> list[dict] | None:
    """Parse weekly chart from mobile site HTML."""
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    for item in soup.find_all("li", class_="z-chart-item"):
        rank_elem, card = item.find(class_="sort-number"), item.find(class_="card-info")
        if not card:
            continue
        title_elem, artist_elem = card.find(class_="title"), card.find(class_="artist")
        if title := (title_elem.get_text(strip=True) if title_elem else ""):
            rank = rank_elem.get_text(strip=True) if rank_elem else str(len(songs) + 1)
            songs.append(_make_song(
                int(rank) if rank.isdigit() else len(songs) + 1, title, "",
                artist_elem.get_text(strip=True) if artist_elem else "",
            ))
    return songs or None


def fetch_zingchart_direct(chart_url: str | None = None) -> str | None:
    """Fetch zing-chart directly (requires VPN)."""
    url = chart_url or ZINGCHART_URL
    print(f"\n[VPN MODE] Fetching {url} directly (VPN must be connected)...")
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and "MusicPlaylist" in resp.text:
            print("  SUCCESS! Got chart data.")
            return resp.text
        print("  Page loaded but no chart data (geo-blocked?)" if resp.status_code == 200 else f"  Failed: HTTP {resp.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  Connection error: {e}")
    return None


def fetch_zingchart_live(chart_url: str | None = None, min_size: int = 0) -> str | None:
    """Fetch zing-chart using Vietnam proxies."""
    url = chart_url or ZINGCHART_URL
    print(f"\n[PROXY MODE] Fetching {url} using Vietnam proxies...")
    return fetch_with_proxy_rotation(url, content_check="MusicPlaylist", min_size=min_size)[0]


def fetch_weekly_chart_live(chart_url: str) -> list[dict] | None:
    """Fetch weekly chart from mobile site with Vietnam proxies."""
    mobile_url = chart_url.replace("://zingmp3.vn/", "://m.zingmp3.vn/")
    print(f"\n[MOBILE MODE] Fetching weekly chart from {mobile_url}...")
    if html := fetch_with_proxy_rotation(mobile_url, content_check="z-chart-item", min_size=0)[0]:
        if songs := parse_mobile_weekly_chart(html):
            print(f"  Parsed {len(songs)} songs")
            return songs
    return None
