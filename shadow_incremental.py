#!/usr/bin/env python3
"""
shadow_incremental.py — prove the incremental loop against ONE live source,
read-only. Fetches the source listing, diffs against the durable store, and
REPORTS what an incremental run WOULD do. Fetches no detail pages, writes
nothing to the store. Safe to run against production data.

Usage:
    python3 shadow_incremental.py
"""
from __future__ import annotations
import json, re
from urllib.parse import urlparse

from incremental_store import load_store, event_id, today_iso
from firecrawl_extractor import fetch_html, firecrawl_budget_status


def _norm_url(u: str) -> str:
    """Normalize a URL for matching: lowercase, strip scheme/query/trailing slash."""
    u = (u or "").strip().lower()
    if not u:
        return ""
    try:
        p = urlparse(u)
        path = (p.path or "").rstrip("/")
        return f"{p.netloc}{path}"
    except Exception:
        return u.rstrip("/")


def listing_urls_from_sitemap(sitemap_url: str, url_pattern: str) -> list[str]:
    """Fetch a sitemap via the resilient helper and return event URLs matching
    the pattern. One cheap fetch (firecrawl fallback if CI-blocked)."""
    html = fetch_html(sitemap_url, marker="<loc>")
    if not html:
        print(f"  [shadow] listing fetch FAILED for {sitemap_url}")
        return []
    locs = re.findall(r"<loc>([^<]+)</loc>", html)
    return [u for u in locs if re.search(url_pattern, u)]


def shadow_diff_source(source_name: str, sitemap_url: str, url_pattern: str):
    """Run the read-only incremental diff for one source and print a report."""
    store = load_store()
    blk = store.get(source_name) or {}
    stored_events = blk.get("events", [])
    today = today_iso()

    # Advertised URLs from the live listing (normalized).
    advertised_urls = {_norm_url(u) for u in
                       listing_urls_from_sitemap(sitemap_url, url_pattern)}
    advertised_urls.discard("")

    # Stored events' URLs (the listing only knows URLs, not title/date, so we
    # match on the URL component rather than the full event_id).
    stored_by_url = {}
    for e in stored_events:
        stored_by_url.setdefault(_norm_url(e.get("link")), []).append(e)
    stored_urls = set(stored_by_url)
    stored_urls.discard("")

    new_urls = advertised_urls - stored_urls          # would fetch detail
    kept_urls = advertised_urls & stored_urls          # keep, no fetch
    # stored future events whose URL is no longer advertised -> candidate drop
    dropped = []
    for url, evs in stored_by_url.items():
        if not url or url in advertised_urls:
            continue
        for e in evs:
            if (e.get("date") or "")[:10] >= today:
                dropped.append((url, e.get("title")))

    print(f"\n=== SHADOW: {source_name} ===")
    print(f"  listing advertised : {len(advertised_urls)} event URLs")
    print(f"  stored (this src)  : {len(stored_events)} events, {len(stored_urls)} unique URLs")
    print(f"  --> NEW (fetch)    : {len(new_urls)}")
    print(f"  --> KEPT (no fetch): {len(kept_urls)}")
    print(f"  --> DROP (future, unlisted): {len(dropped)}")
    spent, cap = firecrawl_budget_status()
    print(f"  firecrawl spent    : {spent}/{cap}")
    if new_urls:
        print("  sample NEW urls:")
        for u in list(new_urls)[:5]:
            print(f"    + {u}")
    if dropped:
        print("  sample DROP (future events no longer listed):")
        for u, t in dropped[:5]:
            print(f"    - {t!r}  ({u})")
    return {"new": len(new_urls), "kept": len(kept_urls), "dropped": len(dropped)}


if __name__ == "__main__":
    # Jackson Chamber — high volume, firecrawl-wired, sitemap-based.
    shadow_diff_source(
        source_name="Jackson Hole Chamber of Commerce",
        sitemap_url="https://www.jacksonholechamber.com/sitemap.xml",
        url_pattern=r"/event/",
    )
