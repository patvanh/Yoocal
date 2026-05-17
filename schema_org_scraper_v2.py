"""
Universal Schema.org Event scraper — v2 with list→detail traversal.

v1 (the original) extracts Schema.org Event JSON-LD from a single URL.
That works for sites that put all events on one page (DVMF).

v2 adds the missing piece: given a LIST page, follow links to detail pages
and extract Schema.org Event JSON-LD from each. This handles the much more
common pattern where /events/ is just a directory of links to /events/slug/.

Public API:
    scrape_schema_org_v2(
        url='https://example.com/events',
        link_pattern=r'/events/[a-z0-9-]+$',  # which links count as event detail pages
        ...other args same as v1
    ) -> list of event dicts

If link_pattern is None, it falls back to v1 behavior (just scrape the URL).

Strategy:
  1. Fetch the list page
  2. Run v1 extraction on it (gets any events embedded directly)
  3. Find all links matching link_pattern
  4. Visit each detail page, run v1 extraction
  5. Dedup by (title, date) and return

Caches detail pages in-process to avoid duplicate fetches within one run.

Example: Park City Opera
    scrape_schema_org_v2(
        url='https://www.parkcityopera.org/events',
        link_pattern=r'/events/[a-z0-9-]+$',
        source_name='Park City Opera',
        default_lat=40.6461, default_lng=-111.4980,
        default_city='Park City, UT',
        default_categories=['Music', 'Opera'],
        max_detail_pages=40,
    )
"""

import re
import time
from urllib.parse import urljoin, urlparse

import requests

from schema_org_scraper import (
    scrape_schema_org_events,
    _fetch,
    _extract_schema_events,
    _parse_event,
    DEFAULT_HEADERS,
)


def scrape_schema_org_v2(
    url,
    link_pattern=None,
    source_name=None,
    default_lat=None,
    default_lng=None,
    default_categories=None,
    default_city=None,
    max_detail_pages=50,
    delay_seconds=0.4,
    timeout=20,
):
    """
    Scrape a list page + each linked detail page for Schema.org Events.

    Args:
        url: The list page URL
        link_pattern: Regex (Python re) that matches event detail URL paths.
            E.g. r'/events/[a-z0-9-]+$' matches /events/lyle-lovett but
            not /events or /events/page/2. If None, only scrapes `url`.
        source_name: Override for "source" field
        default_lat/lng: Coordinates if event location can't be geocoded
        default_categories: Category strings
        default_city: City name used in location string fallback
        max_detail_pages: Cap on detail pages to visit
        delay_seconds: Sleep between detail page fetches (be polite)

    Returns:
        List of event dicts in yoocal schema format, deduped by (title, date).
    """
    if not source_name:
        source_name = urlparse(url).netloc.replace("www.", "")

    print(f"  [{source_name}] v2 scraping {url}")

    # Step 1: events directly on the list page (rare but possible)
    list_events = scrape_schema_org_events(
        url=url,
        source_name=source_name,
        default_lat=default_lat,
        default_lng=default_lng,
        default_categories=default_categories,
        default_city=default_city,
        timeout=timeout,
    )
    print(f"  [{source_name}] list page direct extract: {len(list_events)} events")

    # If no link_pattern, just return list-page events
    if not link_pattern:
        return list_events

    # Step 2: find links on the list page
    try:
        html_text = _fetch(url, timeout=timeout)
    except Exception as ex:
        print(f"  [{source_name}] fetch failed: {ex}")
        return list_events

    pat = re.compile(link_pattern)
    found_paths = set()
    for m in re.finditer(r'href="(/[^"#?]+)"', html_text):
        path = m.group(1).rstrip("/")
        if pat.search(path):
            found_paths.add(path)

    # Resolve to full URLs
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    detail_urls = sorted({urljoin(base, p) for p in found_paths})
    print(f"  [{source_name}] found {len(detail_urls)} detail URLs matching pattern")

    # Cap
    if max_detail_pages and len(detail_urls) > max_detail_pages:
        detail_urls = detail_urls[:max_detail_pages]
        print(f"  [{source_name}] capping at {max_detail_pages} detail pages")

    # Step 3: visit each detail page
    detail_events = []
    failed = 0
    no_schema = 0
    for i, detail_url in enumerate(detail_urls, 1):
        try:
            events = scrape_schema_org_events(
                url=detail_url,
                source_name=source_name,
                default_lat=default_lat,
                default_lng=default_lng,
                default_categories=default_categories,
                default_city=default_city,
                timeout=timeout,
            )
            if events:
                detail_events.extend(events)
            else:
                no_schema += 1
        except Exception as ex:
            failed += 1
            print(f"    [{i}/{len(detail_urls)}] {detail_url[-50:]} — FAIL: {ex}")
            continue
        if delay_seconds:
            time.sleep(delay_seconds)

    print(f"  [{source_name}] detail pages: {len(detail_events)} events ({no_schema} no-schema, {failed} fetch-failed)")

    # Step 4: dedup
    all_events = list_events + detail_events
    seen = set()
    out = []
    for e in all_events:
        key = (e["title"].lower().strip()[:50], e["date"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)

    print(f"  [{source_name}] TOTAL after dedup: {len(out)} events")
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the v2 universal Schema.org Event parser.")
    parser.add_argument("--url", required=True, help="List page URL")
    parser.add_argument("--pattern", default=None, help="Regex for event detail URL paths (e.g., '/events/[a-z0-9-]+$')")
    parser.add_argument("--source", default=None, help="Override source name")
    parser.add_argument("--city", default=None, help="Default city for location fallback")
    parser.add_argument("--max-pages", type=int, default=30, help="Cap on detail pages")
    args = parser.parse_args()

    events = scrape_schema_org_v2(
        url=args.url,
        link_pattern=args.pattern,
        source_name=args.source,
        default_city=args.city,
        max_detail_pages=args.max_pages,
    )
    print(f"\n{len(events)} unique events:\n")
    for e in events:
        time_s = e.get("start_time", "(all day)")
        loc_short = e["location"].split(",")[0][:40]
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:50]:50s} | {loc_short}")
