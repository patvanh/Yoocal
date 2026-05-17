"""
Generic RSS event-feed scraper.

Works on any site exposing an RSS feed of events. Common URL patterns:
  - {site}/event/rss/      ← Simpleview tourism boards / chambers
  - {site}/events/feed/    ← WordPress
  - {site}/feed/           ← WordPress (fallback)
  - {site}/events.rss      ← custom

Extracts title, link, description, categories, and date.

Date handling: RSS event feeds usually put the event date in <pubDate>.
We parse RFC-822 dates and also try to find a date in the description body
(many feeds include "MM/DD/YYYY to MM/DD/YYYY" patterns).

Public API:
  scrape_rss(feed_url, source_name=None, default_lat=None, default_lng=None,
             default_city=None, timeout=20, max_items=500)
"""

from __future__ import annotations
import html
import re
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree as ET

import requests


_DATE_RANGE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*to\s*(\d{1,2})/(\d{1,2})/(\d{4})")
_DATE_SINGLE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _strip_html(s: str) -> str:
    """Cheap HTML stripper for descriptions."""
    if not s:
        return ""
    # remove tags
    no_tags = re.sub(r"<[^>]+>", " ", s)
    # collapse whitespace
    cleaned = re.sub(r"\s+", " ", no_tags).strip()
    return html.unescape(cleaned)


def _extract_image(desc_html: str) -> str:
    """Find the first <img src='...'> in the description."""
    if not desc_html:
        return ""
    m = re.search(r"<img[^>]+src=['\"]([^'\"]+)['\"]", desc_html)
    return m.group(1) if m else ""


def _parse_event_dates(pub_date_str: str, desc_html: str):
    """
    Return (start_date_iso, end_date_iso). Both 'YYYY-MM-DD' or None.

    Strategy:
      1. Find 'MM/DD/YYYY to MM/DD/YYYY' in description (most reliable).
      2. Fall back to single 'MM/DD/YYYY' in description.
      3. Fall back to RFC-822 pubDate.
    """
    desc_text = _strip_html(desc_html)
    rng = _DATE_RANGE_RE.search(desc_text)
    if rng:
        m1, d1, y1, m2, d2, y2 = rng.groups()
        start = f"{y1}-{int(m1):02d}-{int(d1):02d}"
        end = f"{y2}-{int(m2):02d}-{int(d2):02d}"
        return start, end

    single = _DATE_SINGLE_RE.search(desc_text)
    if single:
        m1, d1, y1 = single.groups()
        d = f"{y1}-{int(m1):02d}-{int(d1):02d}"
        return d, d

    if pub_date_str:
        try:
            dt = parsedate_to_datetime(pub_date_str)
            iso = dt.strftime("%Y-%m-%d")
            return iso, iso
        except Exception:
            pass

    return None, None


def _to_yoocal_event(
    item: ET.Element,
    feed_url: str,
    source_name: str,
    default_lat: Optional[float],
    default_lng: Optional[float],
    default_city: Optional[str],
) -> Optional[dict]:
    def text(tag: str) -> str:
        el = item.find(tag)
        return (el.text or "").strip() if el is not None else ""

    title = text("title")
    if not title:
        return None
    link = text("link")
    pub_date = text("pubDate")
    desc_html = text("description")

    start_date, end_date = _parse_event_dates(pub_date, desc_html)
    if not start_date:
        return None

    categories = []
    for c in item.findall("category"):
        if c.text:
            categories.append(c.text.strip())

    description = _strip_html(desc_html)
    # remove the date-range substring from the description if present
    description = _DATE_RANGE_RE.sub("", description)
    description = _DATE_SINGLE_RE.sub("", description).strip(" -")

    image_url = _extract_image(desc_html)

    return {
        "title": html.unescape(title),
        "date": start_date,
        "description": description[:800],
        "location": default_city or "",
        "link": link or feed_url,
        "source": source_name,
        "source_url": feed_url,
        "lat": default_lat,
        "lng": default_lng,
        "categories": categories,
        "start_time": "",
        "end_time": "",
        "image_url": image_url,
    }


def scrape_rss(
    feed_url: str,
    source_name: Optional[str] = None,
    default_lat: Optional[float] = None,
    default_lng: Optional[float] = None,
    default_city: Optional[str] = None,
    timeout: int = 20,
    max_items: int = 500,
) -> list:
    """Scrape an RSS event feed into yoocal events."""
    if source_name is None:
        # crude: derive from domain
        m = re.search(r"https?://([^/]+)", feed_url)
        source_name = m.group(1) if m else feed_url

    print(f"[rss] {source_name}: fetching {feed_url}")
    try:
        r = requests.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124.0"},
            timeout=timeout,
        )
    except Exception as e:
        print(f"[rss] {source_name}: request failed: {e}")
        return []

    if r.status_code != 200:
        print(f"[rss] {source_name}: HTTP {r.status_code}")
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"[rss] {source_name}: XML parse failed: {e}")
        return []

    # Standard RSS 2.0: rss > channel > item
    items = root.findall(".//item")
    if not items:
        # Atom fallback: atom:entry (with namespace)
        items = root.findall("{http://www.w3.org/2005/Atom}entry")

    from datetime import datetime
    today_iso = datetime.utcnow().strftime("%Y-%m-%d")
    events = []
    skipped_past = 0
    for it in items[:max_items]:
        ev = _to_yoocal_event(it, feed_url, source_name, default_lat, default_lng, default_city)
        if ev:
            if ev["date"] < today_iso:
                skipped_past += 1
                continue
            events.append(ev)
    if skipped_past:
        print(f"[rss] {source_name}: skipped {skipped_past} past events")

    print(f"[rss] {source_name}: {len(events)} events parsed from {len(items)} items")
    return events


if __name__ == "__main__":
    out = scrape_rss(
        feed_url="https://www.jacksonholechamber.com/event/rss/",
        source_name="Jackson Hole Chamber of Commerce",
        default_lat=43.4799,
        default_lng=-110.7624,
        default_city="Jackson, WY",
    )
    print(f"\n=== Got {len(out)} events ===\n")
    for ev in out[:10]:
        print(f"  {ev['date']} | {ev['title'][:65]}")
        if ev['categories']:
            print(f"           cats: {ev['categories'][:3]}")
