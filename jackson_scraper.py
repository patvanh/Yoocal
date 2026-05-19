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
import sys
from datetime import datetime
from pathlib import Path
from jhiff_scraper import scrape_jhiff

# Local imports
try:
    from wp_tribe_events_scraper import scrape_wp_tribe_events
    from sitemap_event_scraper import scrape_sitemap_events
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
]


def deduplicate(events):
    """Dedup by (title, date). Prefer events with start_time, then by source priority."""
    source_priority = {
        "Grand Teton Music Festival": 0,
        "Jackson Hole Chamber of Commerce": 1,
        "The Cloudveil": 2,
    }
    seen = {}
    for e in events:
        title = (e.get("title") or "").lower().strip()[:40]
        date = (e.get("date") or "")[:10]
        if not title or not date:
            continue
        key = (title, date)
        existing = seen.get(key)
        if existing is None:
            seen[key] = e
            continue
        # Tiebreak: source priority first, then has-time, then longer description
        e_pri = source_priority.get(e.get("source", ""), 99)
        ex_pri = source_priority.get(existing.get("source", ""), 99)
        if e_pri < ex_pri:
            seen[key] = e
        elif e_pri == ex_pri:
            e_score = (1 if e.get("start_time") else 0) + len(e.get("description") or "") / 1000
            ex_score = (1 if existing.get("start_time") else 0) + len(existing.get("description") or "") / 1000
            if e_score > ex_score:
                seen[key] = e
    return sorted(seen.values(), key=lambda e: e.get("date", ""))


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

    print(f"\nTotal raw events: {len(all_events)}")
    deduped = deduplicate(all_events)
    print(f"After dedup: {len(deduped)}")

    # Per-source breakdown
    from collections import Counter
    print("\nSources:")
    for s, n in Counter(e.get("source", "?") for e in deduped).most_common():
        print(f"  {s}: {n}")

    # Write out
    out_path = Path(__file__).parent / "public" / "events-jackson.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
