"""
Proxy management: fetching, testing, and rotation.
Uses concurrent testing for faster proxy validation.
Optimized for Python free-threading (GIL-free) mode.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

from cache import get_proxy_cache
from config import (
    BROWSER_HEADERS,
    FREE_PROXY_LIST_URL,
    GEONODE_API_URL,
    MAX_PROXY_TRIES,
    PROXYSCRAPE_API_URL,
    PROXY_TEST_WORKERS,
    PROXY_TIMEOUT,
)

# Suppress SSL warnings for proxies
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Thread-local session for connection pooling (improves performance)
_thread_local = threading.local()


def _get_session() -> requests.Session:
    """Get thread-local session for connection reuse."""
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update(BROWSER_HEADERS)
    return _thread_local.session


# =============================================================================
# Private source fetchers (called concurrently)
# =============================================================================


def _fetch_from_proxyscrape() -> list[dict]:
    """Fetch proxies from ProxyScrape API v4."""
    proxies = []
    try:
        response = requests.get(PROXYSCRAPE_API_URL, headers=BROWSER_HEADERS, timeout=PROXY_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            for proxy in data.get("proxies", []):
                proxies.append({
                    "ip": proxy.get("ip", ""),
                    "port": str(proxy.get("port", "")),
                    "source": "proxyscrape",
                })
    except Exception:
        pass
    return proxies


def _fetch_from_geonode() -> list[dict]:
    """Fetch proxies from Geonode API."""
    proxies = []
    try:
        response = requests.get(GEONODE_API_URL, headers=BROWSER_HEADERS, timeout=PROXY_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            for proxy in data.get("data", []):
                # Include all proxies - we test them via HTTP anyway
                proxies.append({
                    "ip": proxy.get("ip", ""),
                    "port": str(proxy.get("port", "")),
                    "source": "geonode",
                })
    except Exception:
        pass
    return proxies


def _fetch_from_free_proxy_list() -> list[dict]:
    """Fetch Vietnam proxies from free-proxy-list.net (scraping)."""
    proxies = []
    try:
        from bs4 import BeautifulSoup

        response = requests.get(FREE_PROXY_LIST_URL, headers=BROWSER_HEADERS, timeout=PROXY_TIMEOUT)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]  # Skip header
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 8:
                        country = cols[2].get_text(strip=True)
                        if country in ("VN", "Vietnam"):
                            proxies.append({
                                "ip": cols[0].get_text(strip=True),
                                "port": cols[1].get_text(strip=True),
                                "source": "free-proxy-list",
                            })
    except Exception:
        pass
    return proxies


# =============================================================================
# Public API
# =============================================================================


def fetch_vietnam_proxies() -> list[dict]:
    """Fetch Vietnam proxies from multiple sources concurrently."""
    all_proxies = []
    sources = [
        ("ProxyScrape", _fetch_from_proxyscrape),
        # ("Geonode", _fetch_from_geonode),
        ("Free-Proxy-List", _fetch_from_free_proxy_list),
    ]

    print("  Fetching from all proxy sources concurrently...")

    # Fetch from all sources in parallel
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        future_to_source = {
            executor.submit(fetcher): name for name, fetcher in sources
        }
        for future in as_completed(future_to_source):
            source_name = future_to_source[future]
            try:
                proxies = future.result()
                if proxies:
                    print(f"    {source_name}: {len(proxies)} proxies")
                    all_proxies.extend(proxies)
                else:
                    print(f"    {source_name}: 0 proxies")
            except Exception as e:
                print(f"    {source_name}: failed ({e})")

    # Remove duplicates by ip:port
    seen = set()
    unique_proxies = []
    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen and p["ip"] and p["port"]:
            seen.add(key)
            unique_proxies.append(p)

    print(f"  Total unique Vietnam proxies: {len(unique_proxies)}")
    return unique_proxies


def fetch_with_proxy(url: str, proxy: dict, timeout: int = PROXY_TIMEOUT) -> str | None:
    """Try to fetch URL using given proxy. Returns HTML content or None."""
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    proxies = {"http": proxy_url, "https": proxy_url}

    # Split timeout: 10s connect, remaining for read (ensures total <= timeout)
    connect_timeout = timeout // 2
    read_timeout = timeout - connect_timeout

    try:
        session = _get_session()
        response = session.get(
            url,
            proxies=proxies,
            timeout=(connect_timeout, read_timeout),
            verify=False,  # Some proxies have SSL issues
        )
        if response.status_code == 200:
            return response.text
    except requests.exceptions.RequestException:
        pass

    return None


def _test_proxy_for_content(
    proxy: dict,
    url: str,
    content_check: str,
    min_size: int,
) -> tuple[dict, str | None, int]:
    """Test a proxy and fetch content if valid. Returns (proxy, html_or_none, speed_ms)."""
    start = time.time()
    html = fetch_with_proxy(url, proxy, timeout=PROXY_TIMEOUT)
    elapsed_ms = int((time.time() - start) * 1000)

    if html and content_check in html and len(html) >= min_size:
        return proxy, html, elapsed_ms
    return proxy, None, elapsed_ms


def fetch_with_proxy_rotation(
    url: str,
    content_check: str = "MusicPlaylist",
    min_size: int = 0,
    max_workers: int = PROXY_TEST_WORKERS,
) -> tuple[str | None, dict | None]:
    """
    Fetch URL using concurrent proxy testing.
    
    Tests proxies in parallel, returns immediately on first success,
    and caches the working proxy.
    
    Args:
        url: URL to fetch
        content_check: String that must be present in response
        min_size: Minimum response size in bytes
        max_workers: Number of concurrent workers
    
    Returns:
        Tuple of (html_content, working_proxy) or (None, None) if all failed
    """
    cache = get_proxy_cache()

    # Try cached proxies first (concurrently, early exit on first success)
    cached_proxies = cache.get_working_proxies()
    if cached_proxies:
        print(f"  Testing {len(cached_proxies)} cached proxies concurrently...")
        
        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = {
            executor.submit(_test_proxy_for_content, proxy, url, content_check, min_size): proxy
            for proxy in cached_proxies
        }
        
        failed_proxies = []
        for future in as_completed(futures):
            proxy, html, speed_ms = future.result()
            if html:
                print(f"    Cache hit: {proxy['ip']}:{proxy['port']} ({speed_ms}ms)")
                # Update speed in cache
                cache.add_working_proxy(proxy["ip"], proxy["port"], speed_ms)
                # Shutdown executor immediately, cancel pending futures
                executor.shutdown(wait=False, cancel_futures=True)
                return html, proxy
            else:
                # Track failed proxies to remove from cache
                failed_proxies.append(proxy)
        
        executor.shutdown(wait=False)
        
        # Remove failed proxies from cache
        for proxy in failed_proxies:
            cache.remove_proxy(proxy["ip"], proxy["port"])
        
        print("    No cached proxies worked, testing fresh proxies...")

    # Fetch fresh proxies from all sources concurrently
    proxies = fetch_vietnam_proxies()
    if not proxies:
        print("  No proxies available!")
        return None, None

    max_tries = min(MAX_PROXY_TRIES, len(proxies))
    print(f"  Testing {max_tries} proxies concurrently ({max_workers} workers)...")

    # Test proxies concurrently - early exit on first success
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = {
        executor.submit(_test_proxy_for_content, proxy, url, content_check, min_size): proxy
        for proxy in proxies[:max_tries]
    }

    for future in as_completed(futures):
        proxy, html, speed_ms = future.result()
        status = "OK" if html else "FAIL"
        print(f"    {proxy['ip']}:{proxy['port']} - {status} ({speed_ms}ms)")
        
        if html:
            # Cache the working proxy
            cache.add_working_proxy(proxy["ip"], proxy["port"], speed_ms)
            print(f"  Found working proxy: {proxy['ip']}:{proxy['port']} ({speed_ms}ms)")
            # Shutdown executor immediately, cancel pending futures
            executor.shutdown(wait=False, cancel_futures=True)
            return html, proxy

    executor.shutdown(wait=False)
    print("  All proxies failed!")
    return None, None
