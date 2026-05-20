"""Universal event scraper — single engine for ALL sources.

Layered architecture:
  Layer 1: fetch()             — HTTP request, auto-falls back to Playwright for JS-rendered sites
  Layer 2: extract_all()       — runs JSON-LD, microdata, CSS, LLM in parallel
  Layer 3: merge_extractions() — picks best fields across methods, scores confidence

Lifetime: starts side-by-side with existing scrapers, gradually replaces them.
"""
from __future__ import annotations

import os
import re
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any
import requests
from bs4 import BeautifulSoup

MOUNTAIN = timezone(timedelta(hours=-6))

CACHE_DIR = Path(".scrape_cache")
CACHE_TTL = 3600  # 1 hour

JS_RENDERED_MARKERS = [
    "Loading...",
    "Loading…",
    "<noscript>",
    "ng-app",
    "data-reactroot",
    "id=\"root\">\\s*<",  # empty React root
    "id=\"__next\">\\s*<",  # empty Next.js root
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class FetchResult:
    """Result of fetching a URL."""
    url: str
    status: int
    html: str
    method: str   # "requests" | "playwright" | "cache"
    fetched_at: str
    error: str | None = None

    def is_js_rendered_placeholder(self) -> bool:
        """Heuristic: does the HTML look like a JS placeholder?"""
        if len(self.html) < 5000:
            return True
        for marker in JS_RENDERED_MARKERS:
            if re.search(marker, self.html):
                return True
        # If the page has fewer than 3 visible text chunks > 100 chars, likely JS-rendered
        soup = BeautifulSoup(self.html, "html.parser")
        text_blocks = [t.strip() for t in soup.stripped_strings if len(t.strip()) > 100]
        return len(text_blocks) < 3


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def _read_cache(url: str) -> FetchResult | None:
    p = _cache_path(url)
    if not p.exists():
        return None
    try:
        d = json.load(open(p))
        # Check TTL
        age = time.time() - d.get("_cached_at", 0)
        if age > CACHE_TTL:
            return None
        d.pop("_cached_at", None)
        return FetchResult(**d)
    except Exception:
        return None


def _write_cache(result: FetchResult):
    CACHE_DIR.mkdir(exist_ok=True)
    d = asdict(result)
    d["_cached_at"] = time.time()
    try:
        json.dump(d, open(_cache_path(result.url), "w"))
    except Exception:
        pass


def fetch(url: str, *, use_cache: bool = True, force_playwright: bool = False) -> FetchResult:
    """Layer 1: Fetch a URL with automatic Playwright fallback for JS-rendered sites.
    
    Order:
      1. Try cache (if not expired)
      2. Try requests.get() (fast)
      3. If response looks like a JS placeholder → fall back to Playwright
      4. force_playwright=True skips steps 1-2
    """
    if use_cache and not force_playwright:
        cached = _read_cache(url)
        if cached:
            cached.method = "cache"
            return cached

    if not force_playwright:
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            result = FetchResult(
                url=url, status=r.status_code, html=r.text,
                method="requests",
                fetched_at=datetime.now(MOUNTAIN).isoformat(),
            )
            if not result.is_js_rendered_placeholder():
                _write_cache(result)
                return result
            # Falls through to Playwright
        except requests.RequestException as e:
            print(f"  [fetch] requests failed for {url}: {e} — trying Playwright")

    # Playwright fallback
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                # Try to wait for common event-list indicators (any of these = events loaded)
                try:
                    page.wait_for_selector(
                        ".fc-event, .fc-list-event, [itemtype*='schema.org/Event'], "
                        ".event-item, .event-card, [class*='event-listing']",
                        timeout=15000,
                    )
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
                # Scroll to trigger lazy-load
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(2000)
                html = page.content()
                result = FetchResult(
                    url=url, status=200, html=html,
                    method="playwright",
                    fetched_at=datetime.now(MOUNTAIN).isoformat(),
                )
                _write_cache(result)
                return result
            finally:
                browser.close()
    except Exception as e:
        return FetchResult(
            url=url, status=0, html="", method="playwright",
            fetched_at=datetime.now(MOUNTAIN).isoformat(),
            error=str(e),
        )


# ============================================================
# Layer 2: Extractors
# ============================================================

@dataclass
class ExtractedEvent:
    """One event with field-level confidence."""
    title: str = ""
    title_confidence: str = "low"   # high | medium | low
    date: str = ""
    date_confidence: str = "low"
    start_time: str = ""
    start_time_confidence: str = "low"
    end_time: str = ""
    end_time_confidence: str = "low"
    description: str = ""
    description_confidence: str = "low"
    venue_name: str = ""
    venue_confidence: str = "low"
    address: str = ""
    link: str = ""
    image_url: str = ""
    source_method: str = ""  # which extractor produced this
    raw: dict = field(default_factory=dict)


def _normalize_date(s: str) -> str:
    """Convert various date string formats to ISO YYYY-MM-DD."""
    if not s:
        return ""
    s = s.strip()
    # ISO already
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    # Month DD, YYYY
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        try:
            d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")
            return d.strftime("%Y-%m-%d")
        except ValueError:
            try:
                d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
                return d.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


def _normalize_time(s: str) -> str:
    """Convert various time formats to 'H:MM AM/PM'."""
    if not s:
        return ""
    s = s.strip().upper().replace(".", "")
    # 7:00 PM / 7 PM
    m = re.match(r"(\d{1,2}):?(\d{2})?\s*(AM|PM)", s)
    if m:
        h = int(m.group(1))
        mn = m.group(2) or "00"
        ampm = m.group(3)
        return f"{h}:{mn} {ampm}"
    # 24-hour HH:MM
    m = re.match(r"(\d{1,2}):(\d{2})", s)
    if m:
        h = int(m.group(1))
        mn = m.group(2)
        if h < 12:
            return f"{h or 12}:{mn} AM"
        if h == 12:
            return f"12:{mn} PM"
        return f"{h - 12}:{mn} PM"
    return ""


def _split_datetime(iso_str: str) -> tuple[str, str]:
    """Split an ISO datetime '2026-05-20T19:30:00' into (date, time)."""
    if not iso_str:
        return "", ""
    iso_str = iso_str.strip()
    # Pure date
    if "T" not in iso_str and " " not in iso_str:
        return _normalize_date(iso_str), ""
    # Split datetime
    for sep in ["T", " "]:
        if sep in iso_str:
            date_part, time_part = iso_str.split(sep, 1)
            return _normalize_date(date_part), _normalize_time(time_part[:5])
    return _normalize_date(iso_str), ""


def extract_jsonld(html: str, base_url: str = "") -> list[ExtractedEvent]:
    """Layer 2a: Extract events from schema.org JSON-LD script tags."""
    events = []
    soup = BeautifulSoup(html, "html.parser")
    
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        
        # JSON-LD can be a single object, array, or @graph
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data:
                items = data["@graph"]
            else:
                items = [data]
        
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_type = item_type[0] if item_type else ""
            
            if "Event" not in str(item_type):
                continue
            
            ev = ExtractedEvent(source_method="jsonld", raw=item)
            ev.title = item.get("name", "").strip()
            ev.title_confidence = "high" if ev.title else "low"
            
            start_date, start_time = _split_datetime(item.get("startDate", ""))
            ev.date = start_date
            ev.date_confidence = "high" if ev.date else "low"
            ev.start_time = start_time
            ev.start_time_confidence = "high" if ev.start_time else "low"
            
            _, end_time = _split_datetime(item.get("endDate", ""))
            ev.end_time = end_time
            ev.end_time_confidence = "high" if ev.end_time else "low"
            
            ev.description = (item.get("description", "") or "").strip()
            ev.description_confidence = "high" if ev.description else "low"
            
            loc = item.get("location", {})
            if isinstance(loc, dict):
                ev.venue_name = (loc.get("name", "") or "").strip()
                ev.venue_confidence = "high" if ev.venue_name else "low"
                addr = loc.get("address", "")
                if isinstance(addr, dict):
                    parts = [
                        addr.get("streetAddress", ""),
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                    ]
                    ev.address = ", ".join(p for p in parts if p).strip()
                elif isinstance(addr, str):
                    ev.address = addr
            
            ev.link = item.get("url", "") or base_url
            
            img = item.get("image", "")
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url", "")
            ev.image_url = img or ""
            
            if ev.title and ev.date:
                events.append(ev)
    
    return events


def extract_microdata(html: str, base_url: str = "") -> list[ExtractedEvent]:
    """Layer 2b: Extract events from schema.org microdata (itemtype attributes)."""
    events = []
    soup = BeautifulSoup(html, "html.parser")
    
    event_nodes = soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Event", re.I)})
    
    for node in event_nodes:
        ev = ExtractedEvent(source_method="microdata")
        
        def get_prop(prop: str) -> str:
            el = node.find(attrs={"itemprop": prop})
            if not el:
                return ""
            # Most microdata uses content="" attr OR text content
            return (el.get("content") or el.get("datetime") or el.get_text(strip=True) or "").strip()
        
        ev.title = get_prop("name")
        ev.title_confidence = "high" if ev.title else "low"
        
        start_iso = get_prop("startDate")
        ev.date, ev.start_time = _split_datetime(start_iso)
        ev.date_confidence = "high" if ev.date else "low"
        ev.start_time_confidence = "high" if ev.start_time else "low"
        
        _, end_time = _split_datetime(get_prop("endDate"))
        ev.end_time = end_time
        ev.end_time_confidence = "high" if end_time else "low"
        
        ev.description = get_prop("description")
        ev.description_confidence = "medium" if ev.description else "low"
        
        loc = node.find(attrs={"itemprop": "location"})
        if loc:
            name_el = loc.find(attrs={"itemprop": "name"})
            if name_el:
                ev.venue_name = name_el.get_text(strip=True)
                ev.venue_confidence = "high" if ev.venue_name else "low"
        
        link_el = node.find("a", href=True)
        if link_el:
            href = link_el["href"]
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            ev.link = href
        
        img_el = node.find("img")
        if img_el and img_el.get("src"):
            ev.image_url = img_el["src"]
        
        if ev.title and ev.date:
            events.append(ev)
    
    return events


def extract_fullcalendar_dom(html: str, base_url: str = "") -> list[ExtractedEvent]:
    """Layer 2c: Extract events from FullCalendar-rendered DOM.
    
    FullCalendar uses classes like fc-event, fc-list-event, fc-event-title.
    """
    events = []
    soup = BeautifulSoup(html, "html.parser")
    
    # Try multiple FullCalendar event selectors
    selectors = [".fc-event", ".fc-list-event", ".fc-daygrid-event"]
    nodes = []
    for sel in selectors:
        nodes.extend(soup.select(sel))
    
    seen = set()
    for node in nodes:
        text = node.get_text(" ", strip=True)
        if not text or text in seen:
            continue
        seen.add(text)
        
        ev = ExtractedEvent(source_method="fullcalendar_dom")
        
        # Title: usually in .fc-event-title or .fc-list-event-title
        title_el = node.select_one(".fc-event-title, .fc-list-event-title, .fc-title")
        if title_el:
            ev.title = title_el.get_text(strip=True)
            ev.title_confidence = "medium"
        else:
            ev.title = text[:100]
            ev.title_confidence = "low"
        
        # Date: from data-date attribute, or parent .fc-day
        parent = node.find_parent(attrs={"data-date": True})
        if parent:
            ev.date = _normalize_date(parent["data-date"])
            ev.date_confidence = "high"
        elif node.get("data-date"):
            ev.date = _normalize_date(node["data-date"])
            ev.date_confidence = "high"
        
        # Time
        time_el = node.select_one(".fc-event-time, .fc-list-event-time")
        if time_el:
            ev.start_time = _normalize_time(time_el.get_text(strip=True))
            ev.start_time_confidence = "medium"
        
        # Link
        link_el = node.find("a", href=True) or node.find_parent("a", href=True)
        if link_el:
            href = link_el.get("href", "")
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            ev.link = href
        
        if ev.title:
            events.append(ev)
    
    return events


def extract_earthdiver(html: str, base_url: str = "") -> list[ExtractedEvent]:
    """Layer 2d: Extract events from Earthdiver CMS sites (gohebervalley.com style).
    
    Pattern: <a href="/event-slug"><div class="pinnable_item" data-id="...">
                <div class="spot_1 title">EVENT TITLE</div>
                <div class="spot_2 spot_secondary">Sep 4-5, 8:00 AM - 8:00 PM</div>
             </a>
    """
    events = []
    soup = BeautifulSoup(html, "html.parser")
    
    # Find all pinnable_item divs with data-id
    nodes = soup.find_all(attrs={"class": "pinnable_item", "data-id": True})
    
    seen_ids = set()
    for node in nodes:
        eid = node.get("data-id")
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        
        ev = ExtractedEvent(source_method="earthdiver")
        
        title_el = node.select_one(".spot_1.title, .spot_1")
        if title_el:
            ev.title = title_el.get_text(strip=True)
            ev.title_confidence = "high"
        
        date_el = node.select_one(".spot_2.spot_secondary, .spot_2")
        if date_el:
            date_text = date_el.get_text(strip=True)
            # Parse "Sep 4-5, 8:00 AM - 8:00 PM" or "Jun 26-27" or "May 20, 7:00 PM"
            # Try to split out date range and time
            time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', date_text)
            if time_match:
                ev.start_time = _normalize_time(time_match.group(1))
                ev.start_time_confidence = "medium"
                # Also try to find end time
                all_times = re.findall(r'\d{1,2}:\d{2}\s*[AP]M', date_text)
                if len(all_times) > 1:
                    ev.end_time = _normalize_time(all_times[1])
                    ev.end_time_confidence = "medium"
            
            # Try to parse the date portion (before the comma)
            date_portion = date_text.split(",")[0].strip()
            # Look for "Sep 4-5" or "Sep 4" patterns
            # Try "Month DD" or "Month DD - DD" or "Month DD & DD" — use the LATEST day
            m = re.match(r"([A-Za-z]+)\s+(\d{1,2})(?:\s*[-&]\s*(\d{1,2}))?", date_portion)
            if m:
                month_name = m.group(1)
                start_day = int(m.group(2))
                end_day = int(m.group(3)) if m.group(3) else start_day
                # Use END day for "is this still happening" check — but expose START as the date
                year = datetime.now(MOUNTAIN).year
                ev.date = _normalize_date(f"{month_name} {start_day}, {year}")
                if ev.date:
                    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
                    # Compute end date for past-check
                    end_iso = _normalize_date(f"{month_name} {end_day}, {year}")
                    # Only bump to next year if the END date is in the past
                    if end_iso and end_iso < today_iso:
                        ev.date = _normalize_date(f"{month_name} {start_day}, {year + 1}")
                    ev.date_confidence = "medium"
                ev.raw["original_date_text"] = date_text
        
        # Link from parent <a>
        parent_a = node.find_parent("a", href=True)
        if parent_a:
            href = parent_a.get("href", "")
            if href.startswith("/"):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            ev.link = href
        
        # Find event category from classes on the node
        # (e.g. "color_32" relates to a category color, but the actual category lives on a sibling)
        
        if ev.title and ev.date:
            events.append(ev)
    
    return events


def extract_all(html: str, base_url: str = "") -> dict[str, list[ExtractedEvent]]:
    """Layer 2: Run ALL extractors in parallel. Returns dict of method -> events list."""
    return {
        "jsonld": extract_jsonld(html, base_url),
        "microdata": extract_microdata(html, base_url),
        "fullcalendar_dom": extract_fullcalendar_dom(html, base_url),
        "earthdiver": extract_earthdiver(html, base_url),
    }


if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.gohebervalley.com/events/"
    print(f"Fetching: {test_url}")
    r = fetch(test_url)
    print(f"  method: {r.method}  status: {r.status}  html: {len(r.html)} bytes\n")
    
    print(f"Running ALL extractors on {test_url}...")
    results = extract_all(r.html, base_url=test_url)
    for method, events in results.items():
        print(f"\n  [{method}] found {len(events)} events")
        for e in events[:5]:
            print(f"    - {e.title[:50]:50s} | date={e.date or '?':10s} | time={e.start_time or '?':10s}")




# ============================================================
# Layer 3: Orchestrator
# ============================================================

def scrape_source(url: str, source_name: str = "", default_lat: float = None,
                  default_lng: float = None, default_city: str = "") -> list[dict]:
    """Full pipeline: fetch → extract → return event dicts in events.json format."""
    print(f"  [{source_name}] Fetching {url}...")
    r = fetch(url)
    if r.error or r.status >= 400:
        print(f"  [{source_name}] FAILED: {r.error or r.status}")
        return []
    
    extractions = extract_all(r.html, base_url=url)
    best_method, best_events = max(extractions.items(), key=lambda kv: len(kv[1]))
    
    if not best_events:
        print(f"  [{source_name}] No events found by any extractor")
        return []
    
    print(f"  [{source_name}] Best extractor: {best_method} ({len(best_events)} events)")
    
    output = []
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    for e in best_events:
        if not e.title or not e.date:
            continue
        if e.date < today_iso:
            continue
        output.append({
            "title": e.title,
            "date": e.date,
            "start_time": e.start_time or None,
            "end_time": e.end_time or None,
            "description": e.description or "",
            "venue_name": e.venue_name or "",
            "address": e.address or "",
            "location": e.venue_name or default_city,
            "lat": default_lat,
            "lng": default_lng,
            "link": e.link or url,
            "source": source_name,
            "source_url": url,
            "image_url": e.image_url or None,
            "scraped_at": datetime.now(MOUNTAIN).isoformat(),
            "_extractor": e.source_method,
            "_confidence": {
                "title": e.title_confidence,
                "date": e.date_confidence,
                "start_time": e.start_time_confidence,
            },
        })
    
    return output


def scrape_gohebervalley() -> list[dict]:
    """Heber Valley Tourism via gohebervalley.com (replaces hardcoded KNOWN list)."""
    return scrape_source(
        url="https://www.gohebervalley.com/events/",
        source_name="Heber Valley Tourism",
        default_lat=40.5069,
        default_lng=-111.4133,
        default_city="Heber Valley, UT",
    )
