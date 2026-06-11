"""event_cache.py — persistent cache for per-event-URL extraction results.

WHY: deep crawling extracts each event's detail page individually. Without a
cache, every daily run re-Firecrawls all ~100-150 pages per source — the "scary"
recurring cost. An event detail page barely changes once published, so caching
the extracted result and only re-fetching new/stale URLs turns a $50-200/mo
naive crawl into a ~$5-15/mo cached one.

DESIGN (mirrors primary_source_enricher's proven cache):
  - key: the event URL.
  - value: {events: [...], status, _cached_at}.
  - "ok" results (events found) are trusted for OK_TTL_DAYS, then re-fetched
    (catches detail edits / cancellations) — long TTL because detail pages are
    stable.
  - "empty"/"fail" results are remembered for FAIL_TTL_DAYS so we don't retry
    dead URLs every run, but do eventually re-check.
  - sitemap lastmod (when available) can force a refresh: pass lastmod and if it
    is newer than the cache entry, we re-fetch regardless of TTL.

The cache file lives under .cache/ (gitignored locally; persisted in CI via the
actions/cache step we added for the enricher — same directory).
"""
from __future__ import annotations
import json
import os
from datetime import date
from pathlib import Path

CACHE_PATH = Path(".cache/event_extraction.json")
OK_TTL_DAYS = int(os.environ.get("EVENT_OK_TTL_DAYS", "21"))    # detail pages are stable
FAIL_TTL_DAYS = int(os.environ.get("EVENT_FAIL_TTL_DAYS", "5"))


def load():
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}


def save(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _age_days(entry):
    ts = (entry or {}).get("_cached_at", "")
    try:
        return (date.today() - date.fromisoformat(ts[:10])).days
    except Exception:
        return 999


def is_fresh(cache, url, lastmod=None):
    """True if we can serve this URL from cache without re-fetching."""
    e = cache.get(url)
    if not e:
        return False
    # sitemap lastmod newer than our cache -> stale, must refetch
    if lastmod and e.get("_cached_at") and lastmod[:10] > e["_cached_at"][:10]:
        return False
    age = _age_days(e)
    if e.get("status") == "ok":
        return age < OK_TTL_DAYS
    # empty / fail
    return age < FAIL_TTL_DAYS


def get_events(cache, url):
    return (cache.get(url) or {}).get("events") or []


def put(cache, url, events):
    cache[url] = {
        "events": events or [],
        "status": "ok" if events else "empty",
        "_cached_at": date.today().isoformat(),
    }


def stats(cache):
    from collections import Counter
    return dict(Counter((v or {}).get("status") for v in cache.values()))
