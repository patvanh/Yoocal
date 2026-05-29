"""
Jackson Hole, WY scraper.

Aggregates events from Jackson Hole-area sources, currently via the
WordPress tribe-events REST API on:
  - gtmf.org (Grand Teton Music Festival — 89 events, classical/orchestral
    summer festival)
  - thecloudveil.com (Jackson Hole hotel that curates a community events
    calendar — 56 events spanning rodeo, fairs, half marathon, concerts)

Output: list of yoocal-formatted event dicts, written to
public/events-jackson.json by main().

Architectural note: this is the first city wired entirely via the
universal toolkit (wp_tribe_events_scraper). No per-source custom
parser code. Adding a new tribe-events source = ~5 lines of config.
"""

import json
from event_classifier import classify_events
import sys
from datetime import datetime, timezone, timedelta

# Mountain Time for today_iso filtering
MOUNTAIN = timezone(timedelta(hours=-6))
from pathlib import Path
from jhiff_scraper import scrape_jhiff

# Local imports
try:
    from wp_tribe_events_scraper import scrape_wp_tribe_events
    from sitemap_event_scraper import scrape_sitemap_events
    from busites_music_scraper import scrape_busites_music
    from busites_music_scraper import scrape_busites_music
except ImportError as e:
    print(f"ERROR: scraper module not found: {e}")
    sys.exit(1)


# Jackson, WY downtown
JACKSON_LAT, JACKSON_LNG = 43.4799, -110.7624


# Each entry maps to a wp_tribe_events configured source.
TRIBE_EVENT_SOURCES = [
    {
        "base_url": "https://gtmf.org",
        "source_name": "Grand Teton Music Festival",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_categories": ["Music", "Concert"],
        "default_city": "Jackson, WY",
    },
    {
        "base_url": "https://thecloudveil.com",
        "source_name": "The Cloudveil",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_categories": ["Community"],
        "default_city": "Jackson, WY",
    },
    {
        "base_url": "https://www.wildlifeart.org",
        "source_name": "National Museum of Wildlife Art",
        "default_lat": 43.4925,
        "default_lng": -110.7438,
        "default_categories": ["Arts"],
        "default_city": "Jackson, WY",
    },
]


# Sitemap-driven sources (Simpleview chambers/tourism, Schema.org Event JSON-LD on each detail page)
SITEMAP_SOURCES = [
    {
        "sitemap_url": "https://www.jacksonholechamber.com/sitemap.xml",
        "url_pattern": r"/event/",
        "source_name": "Jackson Hole Chamber of Commerce",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_city": "Jackson, WY",
        "default_categories": ["Community"],
    },
    {
        "sitemap_url": "https://www.jhcenterforthearts.org/events-sitemap.xml",
        "url_pattern": r"/event/",
        "source_name": "Center for the Arts Jackson Hole",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_city": "Jackson, WY",
        "default_categories": ["Arts"],
    },
]


# Single-page sources (one URL with multiple Schema.org Event JSON-LD blocks)
# Used when the source lists all events on a single page rather than having
# per-event detail URLs in a sitemap.
SINGLE_PAGE_SOURCES = []


# 'busites' CMS venue pages — events embedded as JSON on a listing page.
# We read the listing (correct dates + clean titles), NOT the per-event
# detail pages (which have stale dates and date-polluted titles).
BUSITES_SOURCES = [
    {
        "url": "https://www.milliondollarcowboybar.com/music",
        "source_name": "Million Dollar Cowboy Bar",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_city": "Jackson, WY",
        "default_categories": ["Music", "Nightlife"],
        "venue_name": "Million Dollar Cowboy Bar",
        "venue_addr": "25 N Cache St, Jackson, WY 83001",
    },
]


# RunSignup race-registration API (no auth). API geo-filters by zip+radius, so
# events are already city-scoped — reusable for any city (just change zipcode).
RUNSIGNUP_SOURCES = []  # Disabled for Jackson: Firecrawl extractor (RunningInTheUSA)
# is more complete (15 races vs 4, incl. Old Bill's, John Wayne, Cirque) and
# avoids cross-source duplicates. runsignup_scraper.py kept for reuse/other cities.


# Firecrawl-backed generic extractor sources: blocked/JS/messy sites that plain
# scraping + sitemaps can't handle. Firecrawl fetches clean markdown, then the
# Anthropic API extracts structured events. New stubborn source = one line here.
# (Free structured sources stay on their own scrapers; this is the fallback.)
FIRECRAWL_SOURCES = [
    {
        "url": "https://www.runningintheusa.com/race/list/within-25-miles-of-jackson%20hole-wy/upcoming",
        "source_name": "RunningInTheUSA Jackson",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_city": "Jackson, WY",
        "default_categories": ["Running & Races"],
    },
    {
        "url": "https://www.grandtarghee.com/events/",
        "source_name": "Grand Targhee Resort",
        "default_lat": 43.7871,
        "default_lng": -110.9596,
        "default_city": "Alta, WY",
        "default_categories": [],
    },
    {
        "url": "https://www.jacksonhole.com/events",
        "source_name": "Jackson Hole Mountain Resort",
        "default_lat": JACKSON_LAT,
        "default_lng": JACKSON_LNG,
        "default_city": "Jackson, WY",
        "default_categories": [],
    },
]



SOURCE_PRIORITY = {
    "Grand Teton Music Festival": 0,
    "Center for the Arts Jackson Hole": 0,
    "National Museum of Wildlife Art": 0,
    "Jackson Hole Chamber of Commerce": 1,
    "The Cloudveil": 2,
}


def _jh_richness_score(e):
    """Lower score = better record. Used to pick a merge base."""
    score = 0
    if e.get("start_time"):
        score -= 2
    if e.get("address"):
        score -= 2
    if e.get("description"):
        score -= 1
    if e.get("image_url"):
        score -= 1
    if e.get("end_time"):
        score -= 1
    if e.get("link"):
        score -= 1
    return score


def _jh_norm_title(title: str) -> str:
    """Normalize a title for dedup matching."""
    import re
    t = re.sub(r"\s+", " ", (title or "").lower().strip())
    t = re.sub(r"^[\(\"\'\-\s]+", "", t)
    t = re.sub(
        r"\s*(-|\u2014|\u2013|\bwith\b|\bfeaturing\b|\bft\.?\b|\bpresented by\b).*$",
        "", t,
    ).strip()
    if ":" in t:
        t = t.split(":")[0].strip()
    return t[:40]


def _jh_merge_records(records: list) -> dict:
    """Merge a group of duplicate records into one enriched entry."""
    records.sort(key=lambda e: (
        SOURCE_PRIORITY.get(e.get("source", ""), 99),
        _jh_richness_score(e),
    ))
    base = records[0]
    merged = dict(base)

    # Longest title wins (more context preferred)
    titles = [r.get("title") for r in records if r.get("title")]
    if titles:
        titles.sort(key=lambda t: (-len(t), t))
        merged["title"] = titles[0]

    # Longest description wins
    descs = [r.get("description") or "" for r in records]
    descs.sort(key=lambda d: -len(d))
    if descs and descs[0]:
        merged["description"] = descs[0]

    # First non-empty image / end_time / link
    for r in records:
        if r.get("image_url"):
            merged["image_url"] = r["image_url"]; break
    for r in records:
        if r.get("end_time"):
            merged["end_time"] = r["end_time"]; break

    # Longest venue / address / location
    for field in ("venue_name", "address", "location"):
        candidates = [r.get(field) for r in records if r.get(field)]
        candidates.sort(key=lambda v: -len(v))
        if candidates:
            merged[field] = candidates[0]

    # Categories: union preserving order
    cats: list = []
    for r in records:
        for c in r.get("categories") or []:
            if c not in cats:
                cats.append(c)
    if cats:
        merged["categories"] = cats

    # Facets: union
    facets = set()
    for r in records:
        for f in r.get("facets") or []:
            facets.add(f)
    if facets:
        merged["facets"] = sorted(facets)

    return merged


def deduplicate(events):
    """Merge-aware dedup. Groups by (date, normalized_title) and merges
    duplicate records into one enriched entry."""
    groups: dict = {}
    for e in events:
        date = (e.get("date") or "")[:10]
        if not date or not e.get("title"):
            continue
        norm = _jh_norm_title(e["title"])
        key = (date, norm)
        groups.setdefault(key, []).append(e)

    unique = []
    merged_count = 0
    for key, records in groups.items():
        if len(records) == 1:
            unique.append(records[0])
        else:
            unique.append(_jh_merge_records(records))
            merged_count += len(records) - 1

    if merged_count:
        print(f"  [JH dedup] merged {merged_count} duplicate records into existing entries")

    return sorted(unique, key=lambda e: e.get("date", ""))


def main():
    print("=" * 60)
    print(f"Jackson Hole scrape — {datetime.now().isoformat()}")
    print("=" * 60)

    all_events = []

    # JHiFF — Jackson Hole International Film Festival screenings
    try:
        jhiff_events = scrape_jhiff()
        all_events.extend(jhiff_events)
    except Exception as ex:
        print(f"  [JHiFF] scraper failed: {ex}")
    for cfg in TRIBE_EVENT_SOURCES:
        print(f"\n--- {cfg['source_name']} ---")
        try:
            events = scrape_wp_tribe_events(**cfg)
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    for cfg in SITEMAP_SOURCES:
        print(f"\n--- {cfg['source_name']} (sitemap) ---")
        try:
            events = scrape_sitemap_events(**cfg)
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    for cfg in SINGLE_PAGE_SOURCES:
        print(f"\n--- {cfg['source_name']} (single-page) ---")
        try:
            from schema_org_scraper import scrape_schema_org_events
            events = scrape_schema_org_events(
                max_events=50,
                timeout=20,
                **cfg,
            )
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    for cfg in BUSITES_SOURCES:
        print(f"\n--- {cfg['source_name']} (busites) ---")
        try:
            events = scrape_busites_music(**cfg)
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    for cfg in RUNSIGNUP_SOURCES:
        print(f"\n--- {cfg['source_name']} (runsignup) ---")
        try:
            from runsignup_scraper import scrape_runsignup_races
            events = scrape_runsignup_races(**cfg)
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    for cfg in FIRECRAWL_SOURCES:
        print(f"\n--- {cfg['source_name']} (firecrawl) ---")
        try:
            from firecrawl_extractor import extract_events_from_url
            events = extract_events_from_url(**cfg)
            all_events.extend(events)
        except Exception as ex:
            print(f"  ERROR scraping {cfg['source_name']}: {ex}")
            continue

    print(f"\nTotal raw events: {len(all_events)}")
    deduped = deduplicate(all_events)
    print(f"After dedup: {len(deduped)}")

    # Enrich Cloudveil's generic "King Concerts 2026" records with
    # per-date band names scraped from snowkingmountain.com.
    try:
        from snow_king_concerts import enrich_king_concerts
        enrich_king_concerts(deduped)
    except Exception as ex:
        print(f"  [Snow King] enrich skipped: {ex}")

    # Per-source breakdown
    from collections import Counter
    print("\nSources:")
    for s, n in Counter(e.get("source", "?") for e in deduped).most_common():
        print(f"  {s}: {n}")

    # Write out
    out_path = Path(__file__).parent / "public" / "raw" / "events-jackson.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Apply canonical category classification before writing.
    # (classify the deduped list, not the stale last-source loop var.)
    from event_classifier import classify_events as _classify_events
    deduped = _classify_events(deduped)

    payload = {
        "updated_at": datetime.now().isoformat(),
        "scraped_at": datetime.now().isoformat(),
        "total": len(deduped),
        "events": deduped,
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved {len(deduped)} events to {out_path}")


if __name__ == "__main__":
    main()
