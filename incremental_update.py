#!/usr/bin/env python3
"""
incremental_update.py — the real incremental loop for ONE source, in shadow mode.

Unlike shadow_incremental.py (which only REPORTS the diff), this actually fetches
+ parses the NEW event pages, builds the updated event set (kept-from-store +
newly-fetched), and writes it to a SHADOW store file for comparison against a
full scrape. It does NOT touch the live store or the live pipeline.

The win it demonstrates: on a normal run it fetches detail pages for only the
handful of genuinely-new events, not the source's entire catalog.

Detail parsing reuses the source's existing parser (scrape_schema_org_events for
sitemap/schema.org sources) so the incremental output is identical in shape to
what the full scrape produces — which is what makes the shadow comparison valid.
"""
from __future__ import annotations
import json, os, time
from pathlib import Path

from incremental_store import (load_store, event_id, today_iso, stamp_freshness,
                               content_hash)
from shadow_incremental import listing_urls_from_sitemap, _norm_url
from firecrawl_extractor import firecrawl_budget_status


def incremental_update_schema_source(source_name, sitemap_url, url_pattern,
                                     default_lat, default_lng, default_city,
                                     *, max_new=None, verbose=True):
    """Run the incremental loop for a sitemap+schema.org source. Shadow mode:
    returns the updated event set and a report; writes nothing live."""
    from schema_org_scraper import scrape_schema_org_events

    store = load_store()
    stored = store.get(source_name, {}).get("events", [])
    today = today_iso()

    # 1. LISTING — one cheap fetch (firecrawl fallback if CI-blocked).
    advertised = listing_urls_from_sitemap(sitemap_url, url_pattern)
    advertised_norm = {_norm_url(u): u for u in advertised}

    # 2. DIFF by normalized URL.
    stored_by_url = {}
    for e in stored:
        stored_by_url.setdefault(_norm_url(e.get("link")), []).append(e)
    new_urls = [orig for n, orig in advertised_norm.items() if n not in stored_by_url]
    if max_new:
        new_urls = new_urls[:max_new]

    # 3. FETCH + PARSE only the NEW urls (reusing the existing parser).
    new_events = []
    t0 = time.monotonic()
    for u in new_urls:
        evs = scrape_schema_org_events(u, source_name=source_name,
                                       default_lat=default_lat, default_lng=default_lng,
                                       default_city=default_city)
        for e in evs:
            stamp_freshness(e, today, first_seen=True)
            new_events.append(e)
    fetch_secs = time.monotonic() - t0

    # 4. BUILD updated set: keep stored events still advertised (bump _last_seen),
    #    drop future-dated events no longer advertised, add the new ones.
    kept, dropped = [], []
    for n, evs in stored_by_url.items():
        if n in advertised_norm:
            for e in evs:
                stamp_freshness(e, today)  # bump _last_seen
                kept.append(e)
        else:
            for e in evs:
                if (e.get("date") or "")[:10] >= today:
                    dropped.append(e)      # future + unlisted -> removed
                else:
                    kept.append(e)         # past -> retain (archived by build)
    updated = kept + new_events

    spent, cap = firecrawl_budget_status()
    report = {
        "source": source_name,
        "advertised": len(advertised_norm),
        "stored": len(stored),
        "new_fetched": len(new_events),
        "new_urls": len(new_urls),
        "kept": len(kept),
        "dropped_future": len(dropped),
        "updated_total": len(updated),
        "fetch_secs": round(fetch_secs, 1),
        "firecrawl": f"{spent}/{cap}",
    }
    if verbose:
        print(f"\n=== INCREMENTAL (shadow): {source_name} ===")
        for k, v in report.items():
            print(f"  {k:>15}: {v}")
        print(f"  --> fetched {len(new_urls)} detail pages instead of {len(advertised_norm)} "
              f"({100 - (100*len(new_urls)//max(len(advertised_norm),1))}% fewer)")

    # 5. SHADOW write (separate file, never the live store).
    Path("shadow_store").mkdir(exist_ok=True)
    out = Path("shadow_store") / f"{source_name.replace(' ', '_').replace('/', '_')}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"count": len(updated), "date": today, "events": updated},
                  fh, indent=2, ensure_ascii=False)
    if verbose:
        print(f"  shadow store -> {out}")
    return updated, report


if __name__ == "__main__":
    # Jackson Chamber — shadow loop already validated; now fetch the new events.
    # Cap new fetches low for a quick first run; remove max_new for the full set.
    incremental_update_schema_source(
        source_name="Jackson Hole Chamber of Commerce",
        sitemap_url="https://www.jacksonholechamber.com/sitemap.xml",
        url_pattern=r"/event/",
        default_lat=43.4799, default_lng=-110.7624, default_city="Jackson, WY",
        max_new=5,
    )
