"""Proxy management: fetching, testing, and rotation."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3
from bs4 import BeautifulSoup

from cache import get_proxy_cache
from config import BROWSER_HEADERS, FREE_PROXY_LIST_URL, MAX_PROXY_TRIES, PROXYSCRAPE_API_URL, PROXY_TEST_WORKERS, PROXY_TIMEOUT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_thread_local = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update(BROWSER_HEADERS)
    return _thread_local.session


def _fetch_proxies(url: str, parser) -> list[dict]:
    """Generic proxy fetcher."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=PROXY_TIMEOUT)
        return parser(resp) if resp.status_code == 200 else []
    except Exception:
        return []


def _parse_proxyscrape(resp) -> list[dict]:
    return [{"ip": p.get("ip", ""), "port": str(p.get("port", "")), "source": "proxyscrape"}
            for p in resp.json().get("proxies", [])]


def _parse_free_proxy_list(resp) -> list[dict]:
    proxies = []
    if table := BeautifulSoup(resp.text, "html.parser").find("table"):
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) >= 8 and cols[2].get_text(strip=True) in ("VN", "Vietnam"):
                proxies.append({"ip": cols[0].get_text(strip=True), "port": cols[1].get_text(strip=True), "source": "free-proxy-list"})
    return proxies


PROXY_SOURCES = [
    ("ProxyScrape", PROXYSCRAPE_API_URL, _parse_proxyscrape),
    # ("Free-Proxy-List", FREE_PROXY_LIST_URL, _parse_free_proxy_list),
]


def fetch_vietnam_proxies() -> list[dict]:
    """Fetch Vietnam proxies from multiple sources concurrently."""
    all_proxies = []
    print("  Fetching from all proxy sources concurrently...")

    with ThreadPoolExecutor(max_workers=len(PROXY_SOURCES)) as executor:
        futures = {executor.submit(_fetch_proxies, url, parser): name for name, url, parser in PROXY_SOURCES}
        for future in as_completed(futures):
            name, proxies = futures[future], future.result()
            print(f"    {name}: {len(proxies)} proxies")
            all_proxies.extend(proxies)

    # Deduplicate
    seen = set()
    unique = [p for p in all_proxies if p["ip"] and p["port"] and (key := f"{p['ip']}:{p['port']}") not in seen and not seen.add(key)]
    print(f"  Total unique Vietnam proxies: {len(unique)}")
    return unique


def fetch_with_proxy(url: str, proxy: dict, timeout: int = PROXY_TIMEOUT) -> str | None:
    """Try to fetch URL using given proxy."""
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    try:
        resp = _get_session().get(url, proxies={"http": proxy_url, "https": proxy_url},
                                   timeout=(timeout // 2, timeout - timeout // 2), verify=False)
        return resp.text if resp.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def _test_proxy(proxy: dict, url: str, content_check: str, min_size: int) -> tuple[dict, str | None, int]:
    """Test a proxy and fetch content if valid."""
    start = time.time()
    html = fetch_with_proxy(url, proxy, PROXY_TIMEOUT)
    elapsed_ms = int((time.time() - start) * 1000)
    return (proxy, html, elapsed_ms) if html and content_check in html and len(html) >= min_size else (proxy, None, elapsed_ms)


def _test_proxies_concurrent(proxies: list[dict], url: str, content_check: str, min_size: int, 
                             cache, max_workers: int, label: str) -> tuple[str | None, dict | None]:
    """Test proxies concurrently, return on first success."""
    if not proxies:
        return None, None
    
    print(f"  Testing {len(proxies)} {label} proxies concurrently...")
    failed = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_test_proxy, p, url, content_check, min_size): p for p in proxies}
        for future in as_completed(futures):
            proxy, html, speed_ms = future.result()
            if html:
                print(f"    {'Cache hit' if label == 'cached' else proxy['ip'] + ':' + proxy['port']}: {proxy['ip']}:{proxy['port']} ({speed_ms}ms)")
                cache.add_working_proxy(proxy["ip"], proxy["port"], speed_ms)
                executor.shutdown(wait=False, cancel_futures=True)
                return html, proxy
            elif label == "cached":
                failed.append(proxy)
            else:
                print(f"    {proxy['ip']}:{proxy['port']} - FAIL ({speed_ms}ms)")
    
    for p in failed:
        cache.remove_proxy(p["ip"], p["port"])
    return None, None


def fetch_with_proxy_rotation(url: str, content_check: str = "MusicPlaylist", min_size: int = 0,
                              max_workers: int = PROXY_TEST_WORKERS) -> tuple[str | None, dict | None]:
    """Fetch URL using concurrent proxy testing with caching."""
    cache = get_proxy_cache()

    # Try cached proxies first
    if cached := cache.get_working_proxies():
        if result := _test_proxies_concurrent(cached, url, content_check, min_size, cache, max_workers, "cached"):
            if result[0]:
                return result
        print("    No cached proxies worked, testing fresh proxies...")

    # Fetch and test fresh proxies
    proxies = fetch_vietnam_proxies()
    if not proxies:
        print("  No proxies available!")
        return None, None

    result = _test_proxies_concurrent(proxies[:min(MAX_PROXY_TRIES, len(proxies))], url, content_check, min_size, cache, max_workers, "fresh")
    if result[0]:
        print(f"  Found working proxy: {result[1]['ip']}:{result[1]['port']}")
        return result
    
    print("  All proxies failed!")
    return None, None
