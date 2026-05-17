"""
Sitemap-driven event scraper.

Pattern: fetch a site's /sitemap.xml, extract URLs matching a regex
(e.g. /event/), fetch each detail page, extract Schema.org Event JSON-LD
via the existing schema_org_scraper.

Works on any site with:
  1. A discoverable sitemap.xml
  2. Event detail pages at predictable URL prefixes
  3. Schema.org Event JSON-LD on each detail page

Validated on jacksonholechamber.com (250 URLs → 220 future events).
Likely works on many other Simpleview tourism boards / chambers.
"""
from __future__ import annotations
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import requests
from schema_org_scraper import scrape_schema_org_events


def scrape_sitemap_events(
    sitemap_url: str,
    url_pattern: str = r"/event/",
    source_name: Optional[str] = None,
    default_lat: Optional[float] = None,
    default_lng: Optional[float] = None,
    default_city: Optional[str] = None,
    default_categories: Optional[list] = None,
    max_pages: Optional[int] = None,
    delay_seconds: float = 0.15,
    timeout: int = 15,
) -> list:
    if source_name is None:
        source_name = urlparse(sitemap_url).netloc

    try:
        r = requests.get(
            sitemap_url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"},
            timeout=timeout,
        )
    except Exception as e:
        print(f"[sitemap] {source_name}: sitemap fetch failed: {e}")
        return []

    if r.status_code != 200:
        print(f"[sitemap] {source_name}: sitemap HTTP {r.status_code}")
        return []

    all_urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    urls = [u for u in all_urls if re.search(url_pattern, u)]
    print(f"[sitemap] {source_name}: {len(urls)} URLs matching {url_pattern!r}")

    if max_pages and len(urls) > max_pages:
        urls = urls[:max_pages]

    today = datetime.utcnow().strftime("%Y-%m-%d")
    events = []
    skipped = 0
    failed = 0
    for i, u in enumerate(urls, 1):
        try:
            page_events = scrape_schema_org_events(
                url=u,
                source_name=source_name,
                default_lat=default_lat,
                default_lng=default_lng,
                default_city=default_city,
                default_categories=default_categories or [],
                max_events=5,
                timeout=timeout,
            )
            for ev in page_events:
                d = (ev.get("date") or "")[:10]
                if d and d < today:
                    skipped += 1
                    continue
                events.append(ev)
        except Exception:
            failed += 1
        time.sleep(delay_seconds)

    print(
        f"[sitemap] {source_name}: {len(events)} future, {skipped} past, "
        f"{failed} failed (of {len(urls)} URLs)"
    )
    return events


if __name__ == "__main__":
    out = scrape_sitemap_events(
        sitemap_url="https://www.jacksonholechamber.com/sitemap.xml",
        url_pattern=r"/event/",
        source_name="Jackson Hole Chamber of Commerce",
        default_lat=43.4799,
        default_lng=-110.7624,
        default_city="Jackson, WY",
        default_categories=["Community"],
    )
    print(f"\n=== {len(out)} events ===")
