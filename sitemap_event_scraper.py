"""
Sitemap-driven event scraper.

Pattern: fetch a site's /sitemap.xml, extract URLs matching a regex
(e.g. /event/), fetch each detail page, extract Schema.org Event JSON-LD
via the existing schema_org_scraper.

Expands multi-day and recurring events into per-occurrence instances so
they show up on every day they occur, not just startDate.

Validated on jacksonholechamber.com (250 URLs).
"""
from __future__ import annotations
import re
import time
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
import requests
from schema_org_scraper import scrape_schema_org_events


_DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _clone_event_at_date(ev: dict, new_date: str) -> dict:
    # IMPORTANT: stamp BOTH date and end_date to new_date so each per-day
    # clone is self-contained. Inheriting the original range end_date causes
    # the frontend visibility filter to re-render every clone on every day
    # in the original range — compounding duplication.
    new_ev = dict(ev)
    new_ev["date"] = new_date
    new_ev["end_date"] = new_date
    return new_ev


def _expand_event_dates(ev: dict, today: str) -> list:
    """Expand multi-day/recurring events into per-day instances."""
    raw_start = (ev.get("date") or "")[:10]
    raw_end = (ev.get("end_date") or ev.get("endDate") or "")[:10]

    if not raw_start or not raw_end or raw_end <= raw_start:
        return [ev]

    try:
        start_d = date.fromisoformat(raw_start)
        end_d = date.fromisoformat(raw_end)
    except ValueError:
        return [ev]

    # Cap end at 1 year forward
    max_end = date.today() + timedelta(days=365)
    if end_d > max_end:
        end_d = max_end

    span_days = (end_d - start_d).days + 1

    # If the event already carries STRUCTURED recurrence fields (set by
    # parse_weekly_recurrence in schema_org_scraper, e.g. "Recurring weekly on
    # Monday, Thursday"), do NOT expand here. Pass it through untouched so the
    # universal build-time engine (_fan_out_recurring in build_master_and_views)
    # expands it -- single source of truth, avoids dual-expander disagreements.
    if ev.get("recurrence_days") or ev.get("recurrence"):
        return [ev]

    # Legacy fallback: detect day-of-week recurrence from title/description text
    # (for sources that DON'T set the structured fields above).
    desc = (ev.get("description") or "").lower()
    title = (ev.get("title") or "").lower()
    combined = title + " " + desc
    recurring_days = set()
    for name, idx in _DAY_NAMES.items():
        if (name + "s") in combined or ("every " + name) in combined:
            recurring_days.add(idx)

    if recurring_days:
        instances = []
        cur = start_d
        while cur <= end_d:
            if cur.weekday() in recurring_days:
                instances.append(_clone_event_at_date(ev, cur.isoformat()))
            cur += timedelta(days=1)
            if len(instances) > 60:
                break
        if instances:
            return instances

    # Continuous multi-day events (Restaurant Week, festivals spanning days):
    # Return ONE record with date=start, end_date=end. The frontend filter
    # renders multi-day events on every day in range from a single record.
    # Do NOT expand into per-day clones — that produces duplicates because
    # clones inherit the original end_date, causing range-overlap rendering.
    return [ev]


def scrape_sitemap_events(
    sitemap_url,
    url_pattern=r"/event/",
    source_name=None,
    default_lat=None,
    default_lng=None,
    default_city=None,
    default_categories=None,
    max_pages=None,
    delay_seconds=0.15,
    timeout=15,
    min_lastmod_days=None,
):
    if source_name is None:
        source_name = urlparse(sitemap_url).netloc

    try:
        # Use the resilient session (retry/backoff on 429/5xx) so a throttled
        # CI datacenter IP doesn't get a truncated/blocked sitemap and crawl
        # fewer URLs than exist. Same hardening that recovered HVT.
        try:
            from schema_org_scraper import _SESSION as _S
            r = _S.get(
                sitemap_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"},
                timeout=timeout,
            )
        except Exception:
            r = requests.get(
                sitemap_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"},
                timeout=timeout,
            )
    except Exception as e:
        print(f"[sitemap] {source_name}: sitemap fetch failed: {e}")
        return []

    # Get the sitemap text. If the direct fetch was blocked (non-200, or a
    # Cloudflare challenge with no <loc> entries — common from the CI datacenter
    # IP), fall back to Firecrawl via the canonical helper. This is ONE fetch per
    # source (just the sitemap), so it's budget-safe; the per-event detail pages
    # fetched below go through schema_org._fetch, which has its own fallback.
    _sitemap_text = r.text if r.status_code == 200 else ""
    if "<loc>" not in _sitemap_text:
        try:
            from firecrawl_extractor import fetch_html as _fh
            _fc = _fh(sitemap_url, marker="<loc>")
            if _fc and "<loc>" in _fc:
                print(f"[sitemap] {source_name}: recovered sitemap via Firecrawl")
                _sitemap_text = _fc
        except Exception as _fce:
            print(f"[sitemap] {source_name}: Firecrawl sitemap fallback failed: {str(_fce)[:80]}")
    if "<loc>" not in _sitemap_text:
        print(f"[sitemap] {source_name}: sitemap blocked/empty (HTTP {r.status_code})")
        return []

    all_urls = re.findall(r"<loc>([^<]+)</loc>", _sitemap_text)
    urls = [u for u in all_urls if re.search(url_pattern, u)]

    # Optional crawl-efficiency filter: WordPress/MEC sitemaps list every event
    # ever (1000+), but stale pages keep their old <lastmod> while current-season
    # events get re-edited (bumped into the current year). lastmod is the page
    # EDIT time, not the event date — so this is a generous proxy only: it prunes
    # obviously-dead pages to avoid wasted fetches + throttle, and the per-page
    # crawl still does real date filtering. Use a wide window so we never drop a
    # real upcoming event that simply wasn't recently edited.
    if min_lastmod_days is not None:
        import datetime as _dt
        # Map each matching loc to its <lastmod> by walking <url> blocks.
        pairs = re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", r.text)
        lastmod_by_url = {u: m for (u, m) in pairs}
        cutoff = _dt.date.today() - _dt.timedelta(days=min_lastmod_days)
        kept = []
        skipped_stale = 0
        for u in urls:
            lm = lastmod_by_url.get(u, "")[:10]
            if not lm:
                kept.append(u)  # no lastmod -> keep (can't judge)
                continue
            try:
                lm_date = _dt.date.fromisoformat(lm)
            except ValueError:
                kept.append(u); continue
            if lm_date >= cutoff:
                kept.append(u)
            else:
                skipped_stale += 1
        print(f"[sitemap] {source_name}: lastmod filter ({min_lastmod_days}d) "
              f"kept {len(kept)} of {len(urls)} (skipped {skipped_stale} stale)")
        urls = kept

    print(f"[sitemap] {source_name}: {len(urls)} URLs matching {url_pattern!r}")

    if max_pages and len(urls) > max_pages:
        urls = urls[:max_pages]

    _MOUNTAIN = timezone(timedelta(hours=-6))
    today = datetime.now(_MOUNTAIN).strftime("%Y-%m-%d")
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
                expanded = _expand_event_dates(ev, today)
                for e in expanded:
                    d = (e.get("date") or "")[:10]
                    if d and d < today:
                        skipped += 1
                        continue
                    events.append(e)
        except Exception as ex:
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
