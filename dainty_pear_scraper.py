"""
The Dainty Pear Co. — Midway, UT
================================
A Midway lifestyle/home-goods boutique that hosts classes (mahjong, oil
painting, cookie decorating, etc.). Their /collections/classes/products.json
Shopify endpoint returns clean structured data with titles like
"May 28th- Learn American Mahjong with Mahjong Hive" and the real event
date + time + address in the body_html. We parse the date out of the title
(which is the most reliable source — the body sometimes has the date too,
but the title is always present).
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape

import requests


SOURCE_NAME = "The Dainty Pear Co."
SOURCE_URL = "https://thedaintypearco.com/collections/classes"
API_URL = "https://thedaintypearco.com/collections/classes/products.json"

# Fixed venue — all classes are at the Midway store.
VENUE_NAME = "The Dainty Pear Co."
ADDRESS = "152 W 100 N, Midway, UT 84049"
LOCATION = f"{VENUE_NAME}, {ADDRESS}"
LAT = 40.5118   # 152 W 100 N, Midway, UT (approx)
LNG = -111.4744

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/javascript,*/*;q=0.01",
}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_from_title(title: str, ref_year: int) -> str | None:
    """Title prefix is like 'May 28th- ...' or 'June 11th- ...'. Extract YYYY-MM-DD."""
    m = re.match(
        r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})",
        title.strip(), re.I,
    )
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower()[:3])
    day = int(m.group(2))
    if not mon or not (1 <= day <= 31):
        return None
    return f"{ref_year:04d}-{mon:02d}-{day:02d}"


def _parse_time_from_body(body_html: str) -> str | None:
    """Body has '<strong>May 28th, 2026 | 6:45pm</strong>' style. Extract '6:45 PM'."""
    text = re.sub(r"<[^>]+>", " ", body_html or "")
    text = unescape(text)
    m = re.search(r"\|\s*(\d{1,2}):(\d{2})\s*([ap]m)", text, re.I)
    if not m:
        # Fallback: any time pattern preceded by 'at' or '| '
        m = re.search(r"\b(\d{1,2}):(\d{2})\s*([ap]m)\b", text, re.I)
    if not m:
        return None
    h = int(m.group(1))
    mm = m.group(2)
    ap = m.group(3).upper()
    return f"{h}:{mm} {ap}"


def _description(body_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", body_html or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # Trim the date/address/teacher footer for a cleaner description.
    text = re.split(r"\b(?:\d+\s*\d/2\s+hour\s+class|152\s+W\s+100\s+N)\b", text, 1)[0].strip()
    if len(text) > 400:
        text = text[:397].rstrip() + "..."
    return text


def scrape_dainty_pear() -> list:
    """Fetch class products from Dainty Pear Shopify JSON and return events."""
    print(f"Scraping {SOURCE_NAME} (Shopify JSON)...")
    events: list = []
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        products = r.json().get("products", [])
    except Exception as ex:
        print(f"  ERROR: {ex}")
        return []

    today_iso = datetime.now().strftime("%Y-%m-%d")
    today_year = datetime.now().year

    for p in products:
        try:
            title = (p.get("title") or "").strip()
            if not title:
                continue
            handle = p.get("handle") or ""
            body = p.get("body_html") or ""

            # Tags must include 'class' (defensive — endpoint is the class
            # collection, but Shopify can leak unrelated products).
            tags = [t.lower() for t in (p.get("tags") or [])]
            if "class" not in tags and "Class" != (p.get("product_type") or ""):
                # Most genuine class entries are tagged 'class' OR have
                # product_type 'Class'. Skip ones lacking both.
                if "class" not in (p.get("product_type") or "").lower():
                    continue

            # Use product's created_at year as the year hint — that's the
            # year the class was scheduled in. If the parsed date would be
            # well in the past relative to today, roll forward by 1 year.
            created = p.get("created_at") or ""
            try:
                ref_year = int(created[:4]) if created else today_year
            except ValueError:
                ref_year = today_year

            date_iso = _parse_date_from_title(title, ref_year)
            if not date_iso:
                continue
            # If the parsed date is more than 30 days in the past, assume it
            # rolled into the new year.
            if date_iso < today_iso:
                rolled = f"{ref_year + 1:04d}-{date_iso[5:]}"
                if rolled > today_iso:
                    date_iso = rolled
                # Still in the past after roll? Skip (past class).
                if date_iso < today_iso:
                    continue

            start_time = _parse_time_from_body(body)
            description = _description(body)

            # Variants: first variant's price + availability
            variants = p.get("variants") or []
            price_str = ""
            available = None
            if variants:
                v0 = variants[0]
                price_str = v0.get("price") or ""
                available = v0.get("available")
            price_display = f"${price_str}" if price_str else ""

            # Clean title: strip the date prefix so it doesn't appear twice
            # alongside the date column.
            clean_title = re.sub(
                r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\s*[-–—]\s*",
                "", title, flags=re.I,
            ).strip()
            if not clean_title:
                clean_title = title  # fallback to original if strip emptied it

            link = f"https://thedaintypearco.com/products/{handle}" if handle else SOURCE_URL

            event = {
                "title": clean_title,
                "date": date_iso,
                "description": description,
                "location": LOCATION,
                "venue_name": VENUE_NAME,
                "address": ADDRESS,
                "link": link,
                "source": SOURCE_NAME,
                "source_url": SOURCE_URL,
                "lat": LAT,
                "lng": LNG,
                "is_free": False,
                "categories": ["Class", "Community"],
                "scraped_at": datetime.now().isoformat(),
            }
            if start_time:
                event["start_time"] = start_time
            if price_display:
                event["price"] = price_display
            if available is False:
                event["sold_out"] = True

            events.append(event)
        except Exception as ex:
            print(f"  parse error: {ex}")
            continue

    print(f"  Found {len(events)} classes from {SOURCE_NAME}")
    return events


if __name__ == "__main__":
    evs = scrape_dainty_pear()
    print(json.dumps(evs, indent=2))
