"""
WordPress The Events Calendar (tribe-events) REST API scraper.

Many WordPress sites use "The Events Calendar" plugin by Modern Tribe.
It exposes a public REST API at /wp-json/tribe/events/v1/events that
returns paginated JSON event lists with rich nested venue/category data.

This is way cleaner than HTML scraping. Single config entry handles
any site running tribe-events.

Public API:
    scrape_wp_tribe_events(
        base_url='https://gtmf.org',
        source_name='Grand Teton Music Festival',
        default_lat=43.4799, default_lng=-110.7624,
        default_categories=['Music', 'Concert'],
        max_pages=10,
        ...
    ) -> list of event dicts

Tested on:
  - gtmf.org (Grand Teton Music Festival, 89 events)
  - thecloudveil.com (Jackson Hole hotel events, 56 events)

The endpoint /wp-json/tribe/events/v1/events:
  - Returns paginated JSON, default per_page=10
  - Pagination via 'next_rest_url' field
  - Each event has: title, description, excerpt, start_date, end_date,
    all_day, url, image, cost, categories[], venue{}, organizer[]
  - Times are in event-local timezone (use 'timezone' field)
  - HTML entities encoded ("&#8217;" etc) — needs html.unescape

If the endpoint returns 401/403 or doesn't exist, the site either
doesn't use tribe-events or has it locked down. We bail gracefully.
"""

import requests
import re
import html
import time
from datetime import datetime
from urllib.parse import urljoin

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# WordPress tribe-events API endpoint suffix
API_PATH = "/wp-json/tribe/events/v1/events"


def scrape_wp_tribe_events(
    base_url,
    source_name=None,
    default_lat=None,
    default_lng=None,
    default_categories=None,
    default_city=None,
    max_pages=10,
    per_page=20,
    delay_seconds=0.3,
    timeout=20,
):
    """
    Pull all future events from a WordPress site using The Events Calendar plugin.

    Args:
        base_url: Root URL like 'https://gtmf.org' (no trailing /events path)
        source_name: Override source field. Defaults to URL hostname.
        default_lat / default_lng: Fallback coords when venue lacks them
        default_categories: Category strings if event has no categories
        default_city: City name for location fallback
        max_pages: Cap on pagination (each page = per_page events)
        per_page: Events per API request (default 20)
        delay_seconds: Sleep between paginated requests

    Returns:
        List of event dicts in yoocal schema format.
    """
    if not source_name:
        from urllib.parse import urlparse
        source_name = urlparse(base_url).netloc.replace("www.", "")

    base_url = base_url.rstrip("/")
    first_url = f"{base_url}{API_PATH}?per_page={per_page}"

    print(f"  [{source_name}] scraping {first_url}")

    raw_events = []
    next_url = first_url
    pages_fetched = 0
    while next_url and pages_fetched < max_pages:
        try:
            r = requests.get(next_url, headers=DEFAULT_HEADERS, timeout=timeout)
        except Exception as ex:
            print(f"    page {pages_fetched + 1}: fetch failed: {ex}")
            break

        if r.status_code != 200:
            print(f"    page {pages_fetched + 1}: HTTP {r.status_code}")
            break

        try:
            data = r.json()
        except Exception as ex:
            print(f"    page {pages_fetched + 1}: JSON decode failed: {ex}")
            break

        page_events = data.get("events", [])
        if not page_events:
            break
        raw_events.extend(page_events)
        pages_fetched += 1

        next_url = data.get("next_rest_url")
        if next_url and delay_seconds:
            time.sleep(delay_seconds)

    if not raw_events:
        print(f"  [{source_name}] no events returned")
        return []

    print(f"  [{source_name}] fetched {len(raw_events)} raw events across {pages_fetched} pages")

    # Parse + filter future
    today_iso = datetime.now().strftime("%Y-%m-%d")
    out = []
    dropped_past = 0
    dropped_bad = 0

    for raw in raw_events:
        parsed = _parse_event(
            raw,
            source_name=source_name,
            source_url=base_url,
            default_lat=default_lat,
            default_lng=default_lng,
            default_categories=default_categories,
            default_city=default_city,
        )
        if not parsed:
            dropped_bad += 1
            continue
        if parsed["date"] < today_iso:
            dropped_past += 1
            continue
        out.append(parsed)

    print(f"  [{source_name}] {len(out)} future events (dropped {dropped_past} past, {dropped_bad} unparseable)")
    return out


def _parse_event(raw, source_name, source_url, default_lat, default_lng,
                 default_categories, default_city):
    """Convert one tribe-events event dict into yoocal schema."""
    try:
        # Title — decode HTML entities
        title = html.unescape(raw.get("title", "") or "")
        title = title.strip()
        if not title:
            return None

        # Date / time
        start_str = raw.get("start_date", "") or ""
        end_str = raw.get("end_date", "") or ""
        all_day = bool(raw.get("all_day"))

        # Format: "2026-06-07 15:00:00"
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                except ValueError:
                    return None

        date_iso = start_dt.strftime("%Y-%m-%d")

        start_time = None
        if not all_day:
            # Skip the time if it's exactly 00:00:00 (often means "no time set")
            if start_dt.hour != 0 or start_dt.minute != 0:
                start_time = start_dt.strftime("%-I:%M %p")

        # End time
        end_time = None
        end_date_iso = None
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                if end_dt.strftime("%Y-%m-%d") != date_iso:
                    end_date_iso = end_dt.strftime("%Y-%m-%d")
                if not all_day and (end_dt.hour != 0 or end_dt.minute != 0):
                    end_time = end_dt.strftime("%-I:%M %p")
            except ValueError:
                pass

        # Venue
        venue = raw.get("venue") or {}
        venue_name = ""
        location_parts = []
        venue_lat = venue_lng = None

        if isinstance(venue, dict) and venue:
            venue_name = (venue.get("venue") or "").strip()
            if venue_name:
                location_parts.append(venue_name)
            addr = (venue.get("address") or "").strip()
            if addr:
                location_parts.append(addr)
            city = (venue.get("city") or "").strip()
            state = (venue.get("state") or venue.get("stateprovince") or "").strip()
            if city and state:
                location_parts.append(f"{city}, {state}")
            elif city:
                location_parts.append(city)

            # Some tribe-events sites expose lat/lng on venue
            try:
                vlat = venue.get("geo_lat") or venue.get("latitude")
                vlng = venue.get("geo_lng") or venue.get("longitude")
                if vlat and vlng:
                    venue_lat = float(vlat)
                    venue_lng = float(vlng)
            except (ValueError, TypeError):
                pass

        if location_parts:
            location = ", ".join(location_parts)
        elif default_city:
            location = default_city
        else:
            location = "Location TBD"

        # Description — strip HTML
        desc = raw.get("description") or raw.get("excerpt") or ""
        desc = html.unescape(desc)
        # Decode backslash string-escapes the WP feed sometimes emits
        # (e.g. "Norton\\'s", "debut! \\n") that html.unescape leaves intact.
        desc = desc.replace("\\n", " ").replace("\\t", " ")
        desc = desc.replace("\\'", "'").replace('\\"', '"')
        desc = desc.replace("\\", "")
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) > 600:
            desc = desc[:1997] + "..."
        if not desc:
            desc = title

        # Link — prefer event url, fall back to source
        link = raw.get("url") or raw.get("website") or source_url

        # Image
        image_url = ""
        img_obj = raw.get("image")
        if isinstance(img_obj, dict):
            image_url = img_obj.get("url") or ""
        elif isinstance(img_obj, str):
            image_url = img_obj

        # Categories — extract names
        categories = []
        cat_list = raw.get("categories") or []
        if isinstance(cat_list, list):
            for c in cat_list:
                if isinstance(c, dict):
                    name = (c.get("name") or "").strip()
                    if name:
                        categories.append(name)
        if not categories and default_categories:
            categories = list(default_categories)
        if not categories:
            categories = ["Event"]

        event = {
            "title": title,
            "date": date_iso,
            "description": desc,
            "location": location,
            "link": link,
            "source": source_name,
            "source_url": source_url,
            "lat": venue_lat if venue_lat is not None else (default_lat if default_lat is not None else 0),
            "lng": venue_lng if venue_lng is not None else (default_lng if default_lng is not None else 0),
            "categories": categories,
        }
        if start_time:
            event["start_time"] = start_time
        if end_time:
            event["end_time"] = end_time
        if end_date_iso:
            event["end_date"] = end_date_iso
        if image_url:
            event["image_url"] = image_url

        return event

    except Exception:
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the WordPress tribe-events scraper on a base URL.")
    parser.add_argument("--base-url", required=True, help="Site root like 'https://gtmf.org'")
    parser.add_argument("--source", default=None, help="Override source name")
    parser.add_argument("--city", default=None, help="Default city for location fallback")
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    events = scrape_wp_tribe_events(
        base_url=args.base_url,
        source_name=args.source,
        default_city=args.city,
        max_pages=args.max_pages,
    )
    print(f"\n{len(events)} future events:\n")
    for e in events:
        time_s = e.get("start_time", "(all day)")
        loc_short = (e.get("location") or "").split(",")[0][:40]
        cats = ",".join(e.get("categories", []))[:30]
        print(f"  {e['date']} {time_s:>9s} | {e['title'][:50]:50s} | {cats:20s} | {loc_short}")
