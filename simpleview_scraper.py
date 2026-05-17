"""
Simpleview CMS scraper — works on tourism boards, chambers of commerce, and DMOs.

Simpleview is a popular CMS for tourism. They expose an events API at:
  {base_url}/includes/rest_v2/plugins_events_events_by_date/find/?json={FILTER}

The filter is a MongoDB-style query with date_range. The API rejects requests
that don't look browser-originated (returns 403), so we send full browser
headers including Referer and Origin.

Known Simpleview sites:
  - www.jacksonholechamber.com (Jackson Hole, WY)
  - www.visitparkcity.com (could replace our current PC scraper if API responds)
  - many others — search for "Simpleview" in homepage source

Public API:
  scrape_simpleview(base_url, source_name=None, default_lat=None,
                    default_lng=None, default_city=None, days_ahead=180,
                    delay_seconds=0.3, timeout=20)
"""

from __future__ import annotations
import json
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import requests


def _build_filter(days_ahead: int = 180) -> str:
    """Build the MongoDB-style filter the Simpleview events API expects."""
    today = datetime.utcnow()
    end = today + timedelta(days=days_ahead)
    filt = {
        "filter": {
            "active": True,
            "$and": [
                {
                    "date_range": {
                        "start": {"$date": today.strftime("%Y-%m-%dT00:00:00.000Z")},
                        "end": {"$date": end.strftime("%Y-%m-%dT23:59:59.000Z")},
                    }
                }
            ],
        },
        "options": {
            "limit": 500,
            "sort": {"startDate": 1},
        },
    }
    return urllib.parse.quote(json.dumps(filt))


def _browser_headers(base_url: str) -> dict:
    """Headers that look like a real browser; Simpleview rejects bare Python."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{base_url}/events/",
        "Origin": base_url,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }


def _to_yoocal_event(
    doc: dict,
    base_url: str,
    source_name: str,
    default_lat: Optional[float],
    default_lng: Optional[float],
    default_city: Optional[str],
) -> Optional[dict]:
    """Map a Simpleview event doc into yoocal's schema."""
    title = (doc.get("title") or "").strip()
    if not title:
        return None

    start = doc.get("startDate") or doc.get("date") or ""
    if not start:
        return None
    # startDate looks like "2026-05-17T04:00:00.000Z" — peel out the date
    date_part = start[:10]
    if len(date_part) != 10 or not date_part[0:4].isdigit():
        return None

    # Time (UTC). Simpleview stores midnight-local-converted-to-UTC,
    # so 04:00:00Z roughly = midnight Mountain. We keep this raw for now;
    # downstream displays in local TZ.
    start_time = start[11:16] if len(start) >= 16 else ""
    end_raw = doc.get("endDate") or ""
    end_time = end_raw[11:16] if len(end_raw) >= 16 else ""

    location = (doc.get("location") or "").strip()
    description = (doc.get("description") or "").strip()
    url_path = (doc.get("url") or "").strip()
    link = f"{base_url}{url_path}" if url_path.startswith("/") else (url_path or f"{base_url}/events/")

    lat = doc.get("latitude")
    lng = doc.get("longitude")
    try:
        lat = float(lat) if lat else default_lat
        lng = float(lng) if lng else default_lng
    except (TypeError, ValueError):
        lat, lng = default_lat, default_lng

    # Image
    image_url = ""
    media = doc.get("media_raw") or []
    if isinstance(media, list) and media:
        first = media[0]
        if isinstance(first, dict):
            image_url = first.get("uri") or first.get("url") or ""
            if image_url and image_url.startswith("/"):
                image_url = f"{base_url}{image_url}"

    categories = []
    raw_cats = doc.get("categories") or []
    if isinstance(raw_cats, list):
        for c in raw_cats:
            if isinstance(c, dict):
                name = c.get("catName") or c.get("name")
                if name:
                    categories.append(name)
            elif isinstance(c, str):
                categories.append(c)

    return {
        "title": title,
        "date": date_part,
        "description": description,
        "location": location or (default_city or ""),
        "link": link,
        "source": source_name,
        "source_url": f"{base_url}/events/",
        "lat": lat,
        "lng": lng,
        "categories": categories,
        "start_time": start_time,
        "end_time": end_time,
        "image_url": image_url,
    }


def scrape_simpleview(
    base_url: str,
    source_name: Optional[str] = None,
    default_lat: Optional[float] = None,
    default_lng: Optional[float] = None,
    default_city: Optional[str] = None,
    days_ahead: int = 180,
    delay_seconds: float = 0.3,
    timeout: int = 20,
) -> list:
    """Scrape events from a Simpleview-powered tourism/chamber site."""
    base_url = base_url.rstrip("/")
    if source_name is None:
        source_name = base_url.replace("https://", "").replace("http://", "").rstrip("/")

    filter_param = _build_filter(days_ahead=days_ahead)
    api_url = (
        f"{base_url}/includes/rest_v2/plugins_events_events_by_date/find/"
        f"?json={filter_param}"
    )

    print(f"[simpleview] {source_name}: fetching {api_url[:100]}...")
    try:
        r = requests.get(api_url, headers=_browser_headers(base_url), timeout=timeout)
    except Exception as e:
        print(f"[simpleview] {source_name}: request failed: {e}")
        return []

    if r.status_code != 200:
        print(f"[simpleview] {source_name}: HTTP {r.status_code}, body: {r.text[:200]}")
        return []

    try:
        data = r.json()
    except Exception as e:
        print(f"[simpleview] {source_name}: JSON parse failed: {e}")
        return []

    # docs can be {"docs": [...]} or {"docs": {"docs": [...], "count": N}}
    raw_docs = data.get("docs")
    if isinstance(raw_docs, dict):
        docs = raw_docs.get("docs", [])
    elif isinstance(raw_docs, list):
        docs = raw_docs
    else:
        docs = []

    events = []
    for d in docs:
        ev = _to_yoocal_event(d, base_url, source_name, default_lat, default_lng, default_city)
        if ev:
            events.append(ev)

    print(f"[simpleview] {source_name}: {len(events)} events parsed")
    time.sleep(delay_seconds)
    return events


if __name__ == "__main__":
    out = scrape_simpleview(
        base_url="https://www.jacksonholechamber.com",
        source_name="Jackson Hole Chamber of Commerce",
        default_lat=43.4799,
        default_lng=-110.7624,
        default_city="Jackson, WY",
        days_ahead=180,
    )
    print(f"\n=== Got {len(out)} events ===\n")
    for ev in out[:5]:
        print(f"  {ev['date']} {ev['start_time']:>5} | {ev['title'][:60]} @ {ev['location']}")
