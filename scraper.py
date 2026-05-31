#!/usr/bin/env python3
"""
Yoocal Scraper v2 — Park City Events
Sources:
  1. visitparkcity.com  — tourism events
  2. KPCW.org           — community/nonprofit events
  3. Eventbrite         — ticketed events
  4. RunSignup          — races and fitness events
  5. parkrecord.com     — local newspaper (uses Playwright)

Run: python3 scraper.py
Output: events.json
"""

import requests
from schema_org_scraper import _extract_time_from_html
from venue_lookup import lookup_venue_address
from mountain_town_music_scraper import scrape_mountain_town_music
import os
from bs4 import BeautifulSoup
import json
from event_classifier import classify_events
import re
from datetime import datetime, timedelta, timezone

# Mountain Time for date filtering across DST changes
MOUNTAIN = timezone(timedelta(hours=-6))

def normalize_date_str(s):
    """Convert ISO datetime string to YYYY-MM-DD"""
    if not s: return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def extract_time_from_iso(s):
    """Extract 12-hour time string from ISO datetime.
    VPC API returns local Mountain Time without Z suffix — use as-is.
    Only convert if explicitly UTC (ends with Z or +00:00)."""
    if not s: return ""
    m = re.search(r'T(\d{2}):(\d{2})', str(s))
    if not m: return ""
    h, mn = int(m.group(1)), m.group(2)
    # Only subtract for explicit UTC timestamps
    if str(s).endswith('Z') or '+00:00' in str(s):
        h = (h - 6) % 24  # UTC to MDT
    if h == 0 and mn == "00": return ""  # midnight = no time
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mn} {ampm}"

def extract_time_from_string(s):
    """Extract first time from a plain string e.g. 'Saturday May 16, 7:00 PM' -> '7:00 PM'"""
    if not s: return ""
    m = re.search(r'\b(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))', str(s))
    return m.group(1).strip() if m else ""

def extract_end_time_from_string(s):
    """Extract end time from a range string e.g. '5:00 PM - 8:00 PM' -> '8:00 PM'"""
    if not s: return ""
    # Match patterns like "5pm-8pm", "5:00 PM - 8:00 PM", "5:00-8:00pm"
    m = re.search(r'\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)?\s*[-–to]+\s*(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)|\d{1,2}\s?(?:AM|PM|am|pm))', str(s))
    if m:
        return m.group(1).strip()
    return ""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ─────────────────────────────────────────────
# Resilient HTTP: one shared Session with retry/backoff for ALL scrapers in
# this module. CI datacenter IPs get rate-limited (HTTP 429) by some event
# sites; a bare requests.get drops the page silently on throttle. _get() retries
# 429/5xx with exponential backoff (respecting Retry-After) so pages aren't lost.
# Use _get(url, ...) anywhere we'd have used requests.get(url, ...) for a page
# fetch. Signature mirrors requests.get; HEADERS are applied by default.
import time as _time
import random as _random
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
    _RETRY = Retry(
        total=4, connect=3, read=3, status=4,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
except Exception:
    _RETRY = None
_SESSION = requests.Session()
_adapter = HTTPAdapter(max_retries=_RETRY, pool_connections=10, pool_maxsize=20)
_SESSION.mount("https://", _adapter)
_SESSION.mount("http://", _adapter)


def _get(url, **kwargs):
    """Resilient GET: shared session + retry/backoff + jitter. Defaults to
    module HEADERS and a 20s timeout if not provided. Drop-in for requests.get
    on page fetches."""
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 20)
    kwargs.setdefault("allow_redirects", True)
    last = None
    for attempt in range(1, 4):
        try:
            if attempt == 1:
                _time.sleep(_random.uniform(0.0, 0.2))
            return _SESSION.get(url, **kwargs)
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            last = e
            if attempt < 3:
                _time.sleep(1.0 * attempt + _random.uniform(0, 0.4))
    if last:
        raise last
    raise RuntimeError("fetch failed without exception")

# ─────────────────────────────────────────────
# 1. VISIT PARK CITY — Smart API Scraper
# ─────────────────────────────────────────────
def scrape_visit_park_city():
    print("Scraping visitparkcity.com (Smart API)...")
    events = []

    def normalize_date(s):
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s or '')
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

    def parse_recurrence(rec_str):
        """Parse VPC API recurrence string into (type, day_names).

        Critical: 'monthly' must be checked BEFORE 'weekly' because strings
        like "monthly on the 3rd Thursday" contain a weekday name but are
        monthly events, not weekly. Returns:
          - ('daily', [])
          - ('monthly_nth', [day]) when an ordinal is present (1st-4th, last)
            and a weekday name is present
          - ('monthly', days) for generic monthly
          - ('weekly', [day]) / ('weekly_multiple', [days])
          - (None, []) when nothing recognized
        For 'monthly_nth' the ordinal is embedded in the type string as
        e.g. 'monthly_nth_3' for 3rd, 'monthly_nth_last' for last.
        """
        if not rec_str: return None, []
        s = rec_str.lower()
        days = [d.capitalize() for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] if d in s]
        if 'daily' in s: return 'daily', []
        # Check 'monthly' BEFORE the days-based weekly branch.
        if 'monthly' in s:
            import re as _re
            # Map word/numeric ordinals to integers (or 'last')
            _ORD = {'first': 1, '1st': 1, 'second': 2, '2nd': 2,
                    'third': 3, '3rd': 3, 'fourth': 4, '4th': 4,
                    'fifth': 5, '5th': 5, 'last': 'last'}
            m = _re.search(r'\b(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)\b', s)
            if m and days:
                ord_key = _ORD[m.group(1)]
                return f'monthly_nth_{ord_key}', days
            return 'monthly', days
        if days: return ('weekly' if len(days) == 1 else 'weekly_multiple'), days
        return None, []

    # Day-name -> Python weekday() index (Mon=0 .. Sun=6)
    _DOW_INDEX = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}

    def next_occurrence_on_or_after(ref_date, rec_days):
        """Given a reference date (datetime.date) and a list of day names,
        return the next date on/after ref_date that falls on one of those days.
        If rec_days is empty, returns ref_date unchanged (caller handles daily)."""
        if not rec_days:
            return ref_date
        targets = {_DOW_INDEX[d] for d in rec_days if d in _DOW_INDEX}
        if not targets:
            return ref_date
        for offset in range(0, 7):
            cand = ref_date + timedelta(days=offset)
            if cand.weekday() in targets:
                return cand
        return ref_date

    today = datetime.now()
    start_str = today.strftime("%Y-%m-%d")
    end_str = (today + timedelta(days=200)).strftime("%Y-%m-%d")
    calendar_url = f"https://www.visitparkcity.com/events/calendar/?bounds=false&view=grid&sort=date&filter_daterange%5Bstart%5D={start_str}&filter_daterange%5Bend%5D={end_str}"

    captured_api_url = [None]
    captured_cookies = [None]

    def handle_request(request):
        if 'plugins_events_events_by_date' in request.url and not captured_api_url[0]:
            captured_api_url[0] = request.url
            captured_cookies[0] = request.headers.get('cookie', '')

    try:
        from playwright.sync_api import sync_playwright
        import urllib.parse

        api_response_data = [None]
        print("  Step 1: Capturing session and fetching API in same browser context...")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Denver",
            )
            page = ctx.new_page()
            page.on('request', handle_request)
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            })
            try:
                page.goto(calendar_url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            page.wait_for_timeout(10000)
            try:
                page.evaluate("window.scrollTo(0, 600)")
                page.wait_for_timeout(3000)
            except:
                pass

            if not captured_api_url[0]:
                browser.close()
                print("  Could not capture API URL — falling back to basic scrape")
                raise Exception("No API URL captured")

            parsed = urllib.parse.urlparse(captured_api_url[0])
            params = urllib.parse.parse_qs(parsed.query)
            json_param = params.get('json', [''])[0]
            token = params.get('token', [''])[0]
            api_base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            query = json.loads(json_param)
            query['options']['limit'] = 500
            # NOTE: adding fields like admission, cost, price, free, description,
            # contact triggers a 500 from VPC's API. Use only the default fields.

            new_json = json.dumps(query, separators=(',', ':'))
            full_url = f"{api_base}?json={urllib.parse.quote(new_json)}&token={token}"

            print("  Step 2: Fetching all events from API (in-browser session)...")
            try:
                # CRITICAL: use page.request.get from INSIDE Playwright so the
                # session token stays valid (VPC invalidates tokens replayed
                # from outside the browser context).
                response = page.request.get(full_url, timeout=20000)
                if response.status == 500:
                    print("  VPC API returned 500 — retrying once...")
                    page.wait_for_timeout(2000)
                    response = page.request.get(full_url, timeout=20000)
                if response.status != 200:
                    browser.close()
                    raise Exception(f"API returned {response.status}")
                api_response_data[0] = response.json()
            finally:
                browser.close()

        if not api_response_data[0]:
            raise Exception("No API data captured")

        docs = api_response_data[0].get("docs", {}).get("docs", [])
        total = api_response_data[0].get("docs", {}).get("count", 0)
        print(f"  Got {len(docs)} events (total available: {total})")

        today_str = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
        junk = ['not just a ski town', 'summer hiking', 'treat yourself', 'shopping', 'beauty & wellness']
        seen = set()

        for doc in docs:
            try:
                title = (doc.get("title") or "").strip()
                title = title.replace("&#8211;", "–").replace("&amp;", "&").replace("&#039;", "'")
                if not title or len(title) < 3: continue
                if any(j in title.lower() for j in junk): continue
                key = title.lower()[:40]
                if key in seen: continue
                seen.add(key)

                raw_start = doc.get("startDate") or doc.get("date") or ""
                start_date = normalize_date(raw_start)
                raw_time = extract_time_from_iso(raw_start)
                # Drop midnight and 1:00 AM as false VPC defaults
                start_time = "" if raw_time in ["12:00 AM", "1:00 AM"] else raw_time

                raw_end = doc.get("endDate") or ""
                end_date = normalize_date(raw_end)
                raw_end_time = extract_time_from_iso(raw_end)
                # Simpleview returns "11:59 PM", "12:00 AM", or "1:00 AM" as
                # placeholders for all-day events — drop these.
                end_time = "" if raw_end_time in ("12:00 AM", "11:59 PM", "1:00 AM") else raw_end_time
                # Don't keep an orphan end_time with no start_time — looks broken in UI
                if end_time and not start_time:
                    end_time = ""

                recurrence, rec_days = parse_recurrence(doc.get("recurrence", ""))

                # Fallback: API gave no recurrence string, but the TITLE declares
                # one ("... - Every Thursday"). VPC has summer patio/class series
                # (Yoga, Music, ESL) formatted this way. Treat as weekly so the
                # build engine fans them out (180-day horizon when open-ended).
                if not recurrence:
                    _dm = re.search(
                        r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                        title, re.IGNORECASE)
                    if _dm:
                        recurrence = "weekly"
                        rec_days = [_dm.group(1).capitalize()]

                # Fix stale recurring dates: the API returns the date a
                # recurrence STARTED (often months/years ago). Blindly clamping
                # to today stamps every recurring event on today regardless of
                # its real day (e.g. 'Friday Nights Live' showing on a Wednesday).
                # Instead, compute the next real occurrence.
                if start_date and start_date < today_str:
                    if recurrence in ("weekly", "weekly_multiple") and rec_days:
                        # Find next date matching the recurrence day(s).
                        ref = datetime.now(MOUNTAIN).date()
                        nxt = next_occurrence_on_or_after(ref, rec_days)
                        start_date = nxt.strftime("%Y-%m-%d")
                    elif recurrence == "daily":
                        start_date = today_str
                    elif recurrence and recurrence.startswith("monthly_nth_") and rec_days:
                        # Find next Nth weekday occurrence on or after today.
                        # The build-time fan-out will then expand to ~12 months.
                        ref = datetime.now(MOUNTAIN).date()
                        ord_part = recurrence[len("monthly_nth_"):]
                        ordinal = "last" if ord_part == "last" else int(ord_part)
                        _DI = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
                        target_wday = _DI.get(rec_days[0])
                        if target_wday is None:
                            continue
                        from datetime import timedelta as _td
                        year, month = ref.year, ref.month
                        nxt = None
                        for _ in range(13):
                            if ordinal == "last":
                                if month == 12:
                                    first_next = datetime(year+1, 1, 1).date()
                                else:
                                    first_next = datetime(year, month+1, 1).date()
                                d = first_next - _td(days=1)
                                while d.weekday() != target_wday:
                                    d -= _td(days=1)
                            else:
                                first = datetime(year, month, 1).date()
                                offset = (target_wday - first.weekday()) % 7
                                d = first + _td(days=offset + 7*(ordinal-1))
                                if d.month != month:
                                    year, month = (year, month+1) if month < 12 else (year+1, 1)
                                    continue
                            if d >= ref:
                                nxt = d
                                break
                            year, month = (year, month+1) if month < 12 else (year+1, 1)
                        if nxt is None:
                            continue
                        start_date = nxt.strftime("%Y-%m-%d")
                    else:
                        # Non-recurring event with a past date, OR monthly with
                        # no parseable day — we can't trust it lands today. Drop
                        # it rather than show a wrong date.
                        continue
                location = doc.get("location") or "Park City, UT"
                url_path = doc.get("url") or ""
                link = f"https://www.visitparkcity.com{url_path}" if url_path and not url_path.startswith("http") else (url_path or "https://www.visitparkcity.com/events/")

                admission = str(doc.get("admission") or "").strip()
                price_raw = str(doc.get("price") or doc.get("cost") or "").strip()
                price = admission or price_raw
                free_flag = doc.get("free")

                description = str(doc.get("description") or doc.get("description_raw") or "").strip()[:2000]
                description = re.sub(r'<[^>]+>', '', description)
                desc_lower = description.lower()

                if free_flag == True or price.lower() in ["free", "0", "$0"] or "free" in desc_lower or price.lower().startswith("free"):
                    is_free = True
                elif price == "" and free_flag is None:
                    is_free = None
                else:
                    is_free = False
                description = re.sub(r'<[^>]+>', '', description)

                lat = doc.get("latitude") or doc.get("listing", {}).get("latitude") if isinstance(doc.get("listing"), dict) else None
                lng = doc.get("longitude") or doc.get("listing", {}).get("longitude") if isinstance(doc.get("listing"), dict) else None

                event = {
                    "title": title,
                    "date": start_date or "See website",
                    "description": description,
                    "location": location,
                    "link": link,
                    "source": "Visit Park City",
                    "source_url": "https://www.visitparkcity.com/events/",
                    "is_free": is_free,
                    "price": price,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                if end_time: event["end_time"] = end_time
                if lat: event["lat"] = float(lat)
                if lng: event["lng"] = float(lng)
                if end_date: event["end_date"] = end_date

                # Extract structured address from the listing's address object
                listing = doc.get("listing") if isinstance(doc.get("listing"), dict) else {}
                addr_obj = listing.get("address") if isinstance(listing.get("address"), dict) else {}
                street = (addr_obj.get("address_1") or addr_obj.get("streetAddress") or "").strip()
                city_part = (addr_obj.get("city") or addr_obj.get("addressLocality") or "").strip()
                region = (addr_obj.get("state") or addr_obj.get("addressRegion") or "").strip()
                postal = (addr_obj.get("zip") or addr_obj.get("postalCode") or "").strip()
                addr_str = ", ".join(p for p in [street, city_part, region, postal] if p)
                if addr_str:
                    event["address"] = addr_str
                if listing.get("title") or listing.get("name"):
                    event["venue_name"] = (listing.get("title") or listing.get("name")).strip()
                if recurrence:
                    event["recurrence"] = recurrence
                    event["recurrence_day"] = rec_days[0] if len(rec_days) == 1 else ""
                    event["recurrence_days"] = ",".join(rec_days) if len(rec_days) > 1 else ""

                # Smart-API doesn't return times for many events. If we have a
                # detail-page URL and no start_time yet, fetch the page and
                # extract from visible HTML (e.g. "Time: 9:00 AM to 10:30 AM").
                if not event.get("start_time") and event.get("link", "").startswith("http"):
                    try:
                        page_resp = _get(
                            event["link"],
                            timeout=10,
                        )
                        if page_resp.status_code == 200:
                            st, et = _extract_time_from_html(page_resp.text)
                            if st:
                                event["start_time"] = st
                                if et:
                                    event["end_time"] = et
                    except Exception:
                        pass  # fail silently — no time worse than crash

                events.append(event)
            except:
                continue

        print(f"  Found {len(events)} events from Visit Park City")

    except Exception as e:
        print(f"  Smart scrape failed ({e}), using basic scrape...")
        try:
            url = "https://www.visitparkcity.com/events/"
            r = _get(url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            # Find every article that has a date marker
            today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
            seen_links = set()

            for art in soup.find_all("article"):
                try:
                    # Title from h2/h3/h4
                    title_el = art.find(["h2", "h3", "h4"])
                    if not title_el:
                        continue
                    title = title_el.get_text(" ", strip=True)
                    if len(title) < 3:
                        continue

                    # Detail link
                    link_el = art.find("a", href=re.compile(r"^/event/"))
                    if not link_el:
                        link_el = art.find("a", href=True)
                    link = link_el["href"] if link_el else url
                    if link.startswith("/"):
                        link = "https://www.visitparkcity.com" + link
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    # Date from <li class="info-item date">
                    date_el = art.find("li", class_=re.compile(r"info-item.*date|date.*info-item"))
                    if not date_el:
                        # Try the standalone .info-item.date pattern
                        date_el = art.find(attrs={"class": re.compile(r"info-item")})
                        if date_el and "date" not in " ".join(date_el.get("class", [])):
                            date_el = None
                    if not date_el:
                        continue  # no date -> skip; do not write "See website"
                    date_text = date_el.get_text(" ", strip=True)
                    # Parse "May 21, 2026 - Sep 13, 2026" or "May 21, 2026"
                    m = re.search(r"([A-Z][a-z]{2,8})\s+(\d{1,2}),?\s+(\d{4})", date_text)
                    if not m:
                        continue
                    try:
                        dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")
                    except ValueError:
                        try:
                            dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")
                        except ValueError:
                            continue
                    date_str = dt.strftime("%Y-%m-%d")
                    if date_str < today_iso:
                        continue

                    # End date (multi-day events)
                    end_match = re.search(r"-\s*([A-Z][a-z]{2,8})\s+(\d{1,2}),?\s+(\d{4})", date_text)
                    end_date_str = None
                    if end_match:
                        try:
                            end_dt = datetime.strptime(
                                f"{end_match.group(1)} {end_match.group(2)} {end_match.group(3)}",
                                "%b %d %Y",
                            )
                            end_date_str = end_dt.strftime("%Y-%m-%d")
                        except ValueError:
                            pass

                    # Venue from <li class="info-item venue">
                    venue_el = art.find(attrs={"class": re.compile(r"info-item.*venue|venue.*info-item")})
                    venue_name = venue_el.get_text(" ", strip=True) if venue_el else ""

                    event = {
                        "title": title,
                        "date": date_str,
                        "description": "",
                        "location": venue_name or "Park City, UT",
                        "venue_name": venue_name or None,
                        "link": link,
                        "source": "Visit Park City",
                        "source_url": url,
                        "scraped_at": datetime.now().isoformat(),
                    }
                    if end_date_str and end_date_str != date_str:
                        event["end_date"] = end_date_str
                    events.append(event)
                except Exception:
                    continue
            print(f"  Fallback found {len(events)} events with real dates")
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")

    # GUARD: if the VPC scrape returned an unusually low count, augment with
    # yesterday's stored VPC events to avoid losing coverage during their
    # server flakes. Normal runs return ~90-100 events; under 80 = weak.
    VPC_WEAK_THRESHOLD = 25
    if len(events) < VPC_WEAK_THRESHOLD:
        print(f"  WARN: only {len(events)} VPC events (threshold {VPC_WEAK_THRESHOLD}) — merging with stored data")
        try:
            stored_path = os.path.join(os.path.dirname(__file__), "public", "events.json")
            with open(stored_path) as f_in:
                stored = json.load(f_in)
            stored_vpc = [e for e in stored.get("events", []) if e.get("source") == "Visit Park City"]
            # Only keep future events from storage
            today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
            future_stored = [e for e in stored_vpc if (e.get("date") or "")[:10] >= today_iso]
            # Dedup by title — prefer fresh events over stored
            seen_titles = {e.get("title", "").lower()[:40] for e in events}
            for e in future_stored:
                key = e.get("title", "").lower()[:40]
                if key and key not in seen_titles:
                    events.append(e)
                    seen_titles.add(key)
            print(f"  After merge with stored VPC data: {len(events)} events")
        except Exception as merge_ex:
            print(f"  WARN: could not load stored VPC events for merge: {merge_ex}")

    return events


# ─────────────────────────────────────────────
# 2. KPCW COMMUNITY CALENDAR
# ─────────────────────────────────────────────
def scrape_kpcw():
    print("Scraping KPCW.org community calendar...")
    events = []
    try:
        url = "https://www.kpcw.org/kpcw-community-calendar"
        r = _get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|card|item|post", re.I)) or
            soup.find_all("li", class_=re.compile(r"event|item", re.I))
        )

        skip_titles = {"kpcw", "community calendar", "submit", "donate", "listen", "submit it here", "home", "news", "about"}

        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find("a")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 5: continue
                if any(s in title.lower() for s in skip_titles): continue
                if title.lower() in ['home', 'news', 'about', 'contact', 'events', 'calendar']: continue

                date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                raw_date = date_el.get_text(strip=True) if date_el else "See website"
                date = normalize_date_str(raw_date) or raw_date
                start_time = extract_time_from_string(raw_date)

                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:2000] if desc_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.kpcw.org" + link

                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Park City, UT", "link": link,
                    "source": "KPCW Community Calendar",
                    "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except:
                continue

        print(f"  Found {len(events)} events from KPCW")
    except Exception as e:
        print(f"  Error scraping KPCW: {e}")
    return events


# ─────────────────────────────────────────────
# 3. EVENTBRITE
# ─────────────────────────────────────────────
def scrape_eventbrite():
    print("Scraping Eventbrite...")
    events = []

    def normalize_date(date_str):
        if not date_str: return "See website"
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return "See website"

    urls = [
        "https://www.eventbrite.com/d/ut--park-city/events/",
        "https://www.eventbrite.com/d/ut--84060/events/",
    ]

    for url in urls:
        try:
            r = _get(url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") not in ["Event", "SocialEvent", "MusicEvent", "BusinessEvent"]:
                            continue
                        title = item.get("name", "")
                        if not title or len(title) < 3: continue

                        raw_start = item.get("startDate", "")
                        date = normalize_date(raw_start)
                        start_time = extract_time_from_iso(raw_start) or extract_time_from_string(raw_start)
                        description = re.sub(r'<[^>]+>', '', item.get("description", ""))[:2000]

                        loc = item.get("location", {})
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            city = addr.get("addressLocality", "") if isinstance(addr, dict) else ""
                            state = addr.get("addressRegion", "") if isinstance(addr, dict) else ""
                            venue = loc.get("name", "")
                            location = f"{venue} {city} {state}".strip()
                        else:
                            location = "Park City, UT"

                        if location and 'ut' not in location.lower() and 'utah' not in location.lower() and 'park city' not in location.lower():
                            continue

                        link = item.get("url", url)
                        offers = item.get("offers", {})
                        price = offers.get("price", "") if isinstance(offers, dict) else ""

                        event = {
                            "title": title,
                            "date": date,
                            "description": description,
                            "location": location or "Park City, UT",
                            "link": link,
                            "price": str(price),
                            "source": "Eventbrite",
                            "source_url": url,
                            "scraped_at": datetime.now().isoformat()
                        }
                        if start_time: event["start_time"] = start_time
                        events.append(event)
                except:
                    continue

            for card in soup.find_all("div", attrs={"data-event-id": True}):
                try:
                    title_el = card.find(["h2","h3","h4"]) or card.find(class_=re.compile(r"title", re.I))
                    if not title_el: continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3: continue
                    date_el = card.find("time") or card.find(class_=re.compile(r"date", re.I))
                    raw_date = date_el.get("datetime", "") if date_el else ""
                    date = normalize_date(raw_date)
                    start_time = extract_time_from_iso(raw_date)
                    link_el = card.find("a", href=True)
                    link = link_el["href"] if link_el else url
                    event = {
                        "title": title, "date": date, "description": "",
                        "location": "Park City, UT", "link": link,
                        "source": "Eventbrite", "source_url": url,
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except:
                    continue

        except Exception as e:
            print(f"  Eventbrite URL failed ({url}): {e}")
            continue

    print(f"  Found {len(events)} events from Eventbrite")
    return events


# ─────────────────────────────────────────────
# 4. RUNNING IN THE USA
# ─────────────────────────────────────────────
def scrape_running_in_the_usa():
    print("Scraping runningintheusa.com for Park City races...")
    events = []
    try:
        url = "https://www.runningintheusa.com/race/list/park%20city-ut/upcoming"
        r = _get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        containers = (
            soup.find_all("div", class_=re.compile(r"race|event|result|card|row|item", re.I)) or
            soup.find_all("tr") or
            soup.find_all("li")
        )

        for c in containers:
            try:
                title_el = c.find("a") or c.find("h2") or c.find("h3") or c.find("h4")
                if not title_el: continue
                title = title_el.get_text(strip=True)
                skip = ["more information", "details", "update", "save", "upcoming races", "sort by"]
                if len(title) < 3 or title.lower() in skip: continue

                date_el = c.find(class_=re.compile(r"date|time", re.I)) or c.find("time")
                raw_date = date_el.get_text(strip=True) if date_el else "See website"
                date = normalize_date_str(raw_date) or raw_date
                start_time = extract_time_from_string(raw_date)

                dist_el = c.find(class_=re.compile(r"dist|distance|type", re.I))
                distance = dist_el.get_text(strip=True) if dist_el else ""

                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.runningintheusa.com" + link

                event = {
                    "title": title,
                    "date": date,
                    "description": f"Race in Park City, UT. {distance}".strip().rstrip("."),
                    "location": "Park City, UT",
                    "link": link,
                    "source": "Running in the USA",
                    "source_url": url,
                    "category": "sports",
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except:
                continue

    except Exception as e:
        print(f"  HTTP scrape failed ({e}), using known races only")

    known_races = [
        {
            "title": "Running with Ed 2026",
            "date": "2026-05-16",
            "start_time": "7:00 AM",
            "description": "Park City's favorite community relay race fundraiser for the Park City Education Foundation. 27.6 mile 8-leg relay starting at Basin Recreation Fieldhouse.",
            "location": "Basin Recreation Fieldhouse, Park City, UT",
            "link": "https://www.runningwithed.com",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — 5K",
            "date": "2026-06-06",
            "start_time": "7:00 AM",
            "description": "Race 1 of 3 in the Park City Trail Series. A forgiving 5K course on Park City's iconic trails, perfect for new and seasoned trail runners alike. Finisher's medal and race swag included.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — 10K",
            "date": "2026-07-11",
            "start_time": "7:00 AM",
            "description": "Race 2 of 3 in the Park City Trail Series. A 10K on Park City's iconic trails. Mix and match races or sign up for the full series.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Park City Trail Series — Half Marathon",
            "date": "2026-08-01",
            "start_time": "7:00 AM",
            "description": "Race 3 of 3 in the Park City Trail Series. A half marathon on Park City's iconic trails to cap the summer series. Finisher's medal and race swag included.",
            "location": "Park City, UT",
            "link": "https://runsignup.com/Race/UT/ParkCity/ParkCityTrailSeriesFullSeries",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "featured": True,
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Triple Trail Challenge — Round Valley Rambler & Jupiter Peak",
            "date": "2026-06-13",
            "start_time": "7:00 AM",
            "description": "Three-race series: Round Valley Rambler Half Marathon, Jupiter Peak 25K, and Mid Mountain 50K. June through August.",
            "location": "Park City, UT",
            "link": "https://www.runttc.com",
            "source": "Running in the USA",
            "source_url": "https://www.runningintheusa.com",
            "category": "sports",
            "scraped_at": datetime.now().isoformat()
        }
    ]

    existing_titles = {e["title"].lower() for e in events}
    for race in known_races:
        if race["title"].lower() not in existing_titles:
            events.append(race)

    print(f"  Found {len(events)} races from Running in the USA")
    return events


# ─────────────────────────────────────────────
# 5. PARK RECORD — AI-powered + hardcoded fallback
# ─────────────────────────────────────────────
def scrape_park_record():
    print("Scraping Park Record (AI-powered)...")
    events = []

    KNOWN_PARK_RECORD_EVENTS = [
        {
            "title": "Something Rotten Jr. — Egyptian Theatre YouTheatre",
            "date": "2026-05-09",
            "end_date": "2026-05-10",
            "start_time": "1:00 PM",
            "description": "YouTheatre presents 'Something Rotten Jr.' at 1pm & 5pm at Randy Barton Black Box Theatre, 330 Main St. Tickets $10 adults, free ages 17 & under.",
            "location": "Egyptian Theatre, 330 Main St, Park City",
            "link": "https://www.parkcityshows.com",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Sunday Craft at Swaner EcoCenter",
            "date": "2026-05-11",
            "end_date": "2026-10-31",
            "start_time": "11:00 AM",
            "recurrence": "weekly",
            "recurrence_day": "Sunday",
            "description": "Sunday Craft every Sunday 11am-1pm at Swaner Preserve & EcoCenter, 1258 Center Drive. Upcycled nature-themed craft. Free.",
            "location": "Swaner Preserve & EcoCenter, 1258 Center Drive, Kimball Junction",
            "link": "https://www.swanerecocenter.org",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Local Speaker Series: Improvisation with AishaZCello",
            "date": "2026-05-12",
            "start_time": "5:00 PM",
            "description": "Free presentation at Park City Library, 5pm Tuesday. Cellist Aisha Z discusses and performs her live looping cello project.",
            "location": "Park City Library, 1255 Park Ave",
            "link": "https://www.parkcitylibrary.org",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
        {
            "title": "Summit County Library Chess Club",
            "date": "2026-05-11",
            "end_date": "2026-12-31",
            "start_time": "6:00 PM",
            "recurrence": "weekly",
            "recurrence_day": "Monday",
            "description": "Chess Club meets 6-7:45pm on 2nd and 4th Mondays at Kimball Junction Branch, 1885 W. Ute Blvd, Room 133. All abilities welcome, ages 18+.",
            "location": "Kimball Junction Library, 1885 W. Ute Blvd",
            "link": "https://summit.events.mylibrary.digital",
            "source": "The Park Record",
            "source_url": "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/",
            "scraped_at": datetime.now().isoformat()
        },
    ]

    try:
        from playwright.sync_api import sync_playwright
        print("  Loading Park Record calendar with Playwright...")

        def extract_events_from_page(page):
            return page.evaluate("""() => {
                const events = [];
                const allEventEls = document.querySelectorAll('.eventInfo');
                allEventEls.forEach(el => {
                    let parent = el.parentElement;
                    let date = '';
                    for (let i = 0; i < 8; i++) {
                        if (!parent) break;
                        const dateEl = parent.querySelector('[class*="csDate"]');
                        if (dateEl && !el.contains(dateEl)) { date = dateEl.innerText?.trim(); break; }
                        parent = parent.parentElement;
                    }
                    const title = el.querySelector('.csOneLine span')?.innerText?.trim();
                    const venue = el.querySelector('.csVenue span')?.innerText?.trim();
                    const time = el.querySelector('.csTime')?.innerText?.trim();
                    const link = el.closest('a')?.href || el.querySelector('a')?.href || '';
                    if (title) events.push({title, venue, time, date, link});
                });
                return events;
            }""")

        all_extracted = []
        seen_keys = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            import random, time
            day_offsets = list(range(150))
            random.shuffle(day_offsets)

            day_results = {}
            EARLY_EXIT_THRESHOLD = 30

            for i, day_offset in enumerate(day_offsets):
                target_date = datetime.now() + timedelta(days=day_offset)
                date_str = target_date.strftime("%Y-%m-%d")
                url = f"https://www.parkrecord.com/calendar/#!/show?start={date_str}"

                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(6000)
                    try:
                        page.wait_for_selector('.eventInfo', timeout=8000)
                        page.wait_for_timeout(2000)
                    except:
                        pass

                    extracted = extract_events_from_page(page)
                    day_count = 0
                    for item in extracted:
                        title = item.get("title","").lower()[:40]
                        key = f"{title}|{date_str}"
                        if title and key not in seen_keys:
                            seen_keys.add(key)
                            item["_scrape_date"] = date_str
                            all_extracted.append(item)
                            day_count += 1
                    day_results[day_offset] = day_count
                    print(f"    [{i+1:3d}/150] {date_str}: {len(extracted)} visible, {day_count} new")
                except Exception as e:
                    day_results[day_offset] = 0
                finally:
                    page.close()

                time.sleep(random.uniform(1.0, 3.0))

                if i > 0 and i % 20 == 0:
                    chronological = sorted(day_results.keys(), reverse=True)
                    if len(chronological) >= EARLY_EXIT_THRESHOLD:
                        far_end = chronological[:EARLY_EXIT_THRESHOLD]
                        if all(day_results.get(d, 0) == 0 for d in far_end):
                            print(f"  Early-exit: last {EARLY_EXIT_THRESHOLD} chronological days all empty, stopping")
                            break

            browser.close()

        print(f"  DOM scraper found {len(all_extracted)} unique events across up to 150 days")
        print(f"  Fetching event details (price, description)...")

        detail_cache = {}
        unique_links = list({item.get("link","") for item in all_extracted if item.get("link","")})[:100]

        def fetch_event_detail(link):
            if not link or link in detail_cache: return
            try:
                r = _get(link, timeout=8)
                soup = BeautifulSoup(r.text, "html.parser")
                detail = {}
                price_el = soup.find(string=re.compile(r'Price|Cost|Admission', re.I))
                if price_el:
                    parent = price_el.parent
                    next_el = parent.find_next_sibling() or parent.parent.find_next_sibling()
                    if next_el:
                        price_text = next_el.get_text(strip=True)
                        if price_text:
                            detail['price'] = price_text
                            detail['is_free'] = 'free' in price_text.lower() or price_text in ['0', '$0']
                desc_el = soup.find(string=re.compile(r'Description', re.I))
                if desc_el:
                    parent = desc_el.parent
                    next_el = parent.find_next_sibling()
                    if next_el:
                        detail['description'] = next_el.get_text(strip=True)[:2000]
                detail_cache[link] = detail
            except:
                detail_cache[link] = {}

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(fetch_event_detail, unique_links)

        today_str = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
        for item in all_extracted:
            title = item.get("title", "").strip()
            if not title or len(title) < 3: continue

            link = item.get("link", "")
            m = re.search(r'(\d{4}-\d{2}-\d{2})T', link)
            date = m.group(1) if m else item.get("_scrape_date")

            venue = item.get("venue", "") or "Park City, UT"
            time_str = item.get("time", "")
            # Normalize time from Park Record (e.g. "7:00pm" -> "7:00 PM")
            start_time = ""
            end_time = ""
            if time_str:
                t = re.search(r'(\d{1,2}:\d{2})\s?(am|pm|AM|PM)', time_str)
                if t:
                    start_time = f"{t.group(1)} {t.group(2).upper()}"
                else:
                    start_time = time_str
                end_time = extract_end_time_from_string(time_str)
            # Always try link URL as fallback if no time found yet
            if not start_time:
                t = re.search(r'\d{4}-\d{2}-\d{2}T(\d{2})', link)
                if t:
                    h = int(t.group(1))
                    if h != 0:
                        ampm = "AM" if h < 12 else "PM"
                        h12 = h % 12 or 12
                        start_time = f"{h12}:00 {ampm}"

            detail = detail_cache.get(link, {})
            description = detail.get('description', '')
            if not description:
                description = f"At {venue}." if venue and venue != "Park City, UT" else ""
                if time_str:
                    description = f"{time_str} at {venue}." if venue else time_str

            # Try extracting end time from description if not found yet
            if not end_time and description:
                end_time = extract_end_time_from_string(description)

            price = detail.get('price', '')
            is_free = detail.get('is_free', None)

            # Better free/paid from description text since detail fetch is often blocked
            if is_free is None and description:
                desc_lower = description.lower()
                if any(w in desc_lower for w in ['free admission', 'free event', 'no cost', 'no charge', 'free and open', 'free to attend', 'free entry', 'at no cost']):
                    is_free = True
                elif any(w in desc_lower for w in ['tickets', 'admission', '$', 'purchase', 'register', 'registration required', 'fee']):
                    is_free = False

            event = {
                "title": title,
                "date": date or "See website",
                "description": description,
                "location": venue or "Park City, UT",
                "link": link or "https://www.parkrecord.com/calendar/",
                "source": "The Park Record",
                "source_url": "https://www.parkrecord.com/calendar/",
                "price": price,
                "is_free": is_free,
                "scraped_at": datetime.now().isoformat()
            }

            # Venue address lookup — Park Record only gives venue NAME,
            # not address. Look up known PC venues for street address.
            v_name, v_addr = lookup_venue_address(venue or "")
            if v_name:
                event["venue_name"] = v_name
            if v_addr:
                event["address"] = v_addr

            if start_time: event["start_time"] = start_time
            if end_time: event["end_time"] = end_time
            events.append(event)

        if events:
            print(f"  Found {len(events)} events from Park Record calendar")
            existing = {e["title"].lower()[:30] for e in events}
            for e in KNOWN_PARK_RECORD_EVENTS:
                if e["title"].lower()[:30] not in existing:
                    events.append(e)
            print(f"  Total Park Record events: {len(events)}")
            return events

    except Exception as e:
        print(f"  Playwright DOM scrape failed: {e}")

    try:
        article_url = ""
        today_dt = datetime.now()

        for days_back in range(0, 14):
            check_date = datetime(today_dt.year, today_dt.month, max(1, today_dt.day - days_back))
            url = f"https://www.parkrecord.com/{check_date.year}/{str(check_date.month).zfill(2)}/"
            try:
                r = _get(url, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "scene-happenings" in href or "community-calendar" in href:
                        article_url = href
                        break
                if article_url:
                    break
            except:
                continue

        if not article_url:
            try:
                search_url = "https://www.parkrecord.com/?s=scene+happenings"
                r = _get(search_url, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "scene-happenings" in href and "2026" in href:
                        article_url = href
                        break
            except:
                pass

        if not article_url:
            article_url = "https://www.parkrecord.com/2026/05/08/scene-happenings-may-9-to-may-12/"

        print(f"  Fetching: {article_url}")

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
                page.goto(article_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
            soup = BeautifulSoup(html, "html.parser")
        except:
            r = _get(article_url, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

        article_body = (
            soup.find("div", class_=re.compile(r"article-body|entry-content|post-content|content", re.I)) or
            soup.find("article") or soup.find("main")
        )
        article_text = article_body.get_text(separator="\n", strip=True)[:8000] if article_body else ""

        if article_text and len(article_text) > 200 and "checking your browser" not in article_text.lower():
            print(f"  Article text: {len(article_text)} chars — Using AI to extract events...")
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                prompt = f"""Read this Park City newspaper article and extract all events as a JSON array.
Each item: title, date (e.g. "May 12" or "every Sunday"), time (e.g. "7:00 PM" or ""), location (or "Park City, UT"), description (1-2 sentences), link (URL if mentioned or ""), is_free (true/false/null).
Only real events. Return ONLY valid JSON array, no other text.

ARTICLE:
{article_text}"""
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    json={"model": "claude-sonnet-4-5", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
                    timeout=30
                )
                if response.status_code == 200:
                    content = response.json().get("content", [{}])[0].get("text", "").strip()
                    content = re.sub(r'```(?:json)?', '', content).strip().rstrip('`').strip()
                    match = re.search(r'\[.*\]', content, re.DOTALL)
                    if match:
                        extracted = json.loads(match.group(0))
                        for item in extracted:
                            if not item.get("title"): continue
                            date_str = item.get("date", "See website")
                            time_str = item.get("time", "")
                            event = {
                                "title": item["title"],
                                "date": date_str,
                                "description": item.get("description", ""),
                                "location": item.get("location", "Park City, UT"),
                                "link": item.get("link", article_url) or article_url,
                                "source": "The Park Record",
                                "source_url": article_url,
                                "scraped_at": datetime.now().isoformat()
                            }
                            if time_str: event["start_time"] = time_str
                            events.append(event)
                        print(f"  AI extracted {len(events)} events from Park Record")
                else:
                    print(f"  Claude API error: {response.status_code}")
        else:
            print("  Cloudflare blocked — using hardcoded Park Record events")

    except Exception as e:
        print(f"  Park Record AI error: {e}")

    existing = {e["title"].lower()[:30] for e in events}
    for e in KNOWN_PARK_RECORD_EVENTS:
        if e["title"].lower()[:30] not in existing:
            events.append(e)

    print(f"  Found {len(events)} total events from Park Record")
    return events


# ─────────────────────────────────────────────
# HANDLE RECURRING EVENTS
# ─────────────────────────────────────────────


SOURCE_PRIORITY = {
    "Deer Valley Resort": 0,
    "Deer Valley Music Festival": 1,
    "Mountain Trails Foundation": 2,
    "Park City Opera": 3,
    "Park City Institute": 4,
    "Mountain Town Music": 5,
    "The Park Record": 6,
    "KPCW Community Calendar": 7,
    "Park Silly Sunday Market": 8,
    "Park City Annual Events": 8,
    "Park City Farmers Market": 8,
    "Park City Song Summit": 8,
    "Park City Gallery Association": 8,
    "Visit Park City (sitemap)": 9,
    "Google Events": 10,
    "RunSignup": 11,
    "Salt Lake Running Co": 12,
    "Running in the USA": 13,
    "Visit Park City": 14,
}


# _ATTRIBUTION_PRIORITY controls which record's `source` and `link` win when
# duplicates are merged. Separate from SOURCE_PRIORITY (which controls
# data-richness ordering) because the two questions are different:
#   - Whose data fields are richest? -> SOURCE_PRIORITY + richness score
#   - Whose attribution / link should the user see? -> _ATTRIBUTION_PRIORITY
# Venue-direct sources win attribution (canonical link). Aggregators lose.
_ATTRIBUTION_PRIORITY = {
    # Tier 0: venue-direct (events on their own calendar)
    "Deer Valley Resort": 0,
    "Deer Valley Music Festival": 0,
    "Park City Opera": 0,
    "Park City Institute": 0,
    "Mountain Town Music": 0,
    "Mountain Trails Foundation": 0,
    "Park City Song Summit": 0,
    "Park City Gallery Association": 0,
    "Park Silly Sunday Market": 0,
    "Park City Farmers Market": 0,
    "Egyptian Theatre": 0,
    "The Dainty Pear Co.": 0,
    # Tier 1: official tourism authority
    "Visit Park City": 1,
    "Park City Annual Events": 1,
    # Sitemap is a fallback parse path; live API is more authoritative.
    "Visit Park City (sitemap)": 2,
    "Heber Valley Tourism": 1,
    # Tier 2: local newspaper aggregator
    "The Park Record": 2,
    "TownLift": 2,
    # Tier 3: community calendar
    "KPCW Community Calendar": 3,
    # Tier 4: race aggregators
    "RunSignup": 4,
    "Salt Lake Running Co": 4,
    "Running in the USA": 4,
    # Tier 5: search aggregators (worst attribution)
    "Google Events": 5,
}


def _pc_richness_score(e):
    """Lower score = better record. Used to order dedup groups so the
    richest record wins as the merge base."""
    score = 0
    d = e.get("date") or ""
    if d and d != "See website" and d[:4].isdigit():
        score -= 4
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
    return score


def _pc_norm_title(title: str) -> str:
    """Normalize a title for dedup matching. Strips leading punctuation,
    subtitles after colons, trailing 'with/featuring/special guest', dashes."""
    t = re.sub(r"\s+", " ", (title or "").lower().strip())
    t = re.sub(r"^[\(\"\'\-\s]+", "", t)
    # Drop "with/featuring/special guest" tails
    t = re.sub(
        r"\s*(-|\u2014|\u2013|\bwith\b|\bfeaturing\b|\bft\.?\b|\bpresented by\b|\bspecial guest\b).*$",
        "", t,
    ).strip()
    # Drop subtitle after colon
    if ":" in t:
        t = t.split(":")[0].strip()
    return t[:35]


def _pc_merge_records(records: list) -> dict:
    """Merge a group of records (all same date + normalized title) into one
    enriched record. Strategy:
      - Base = highest-priority source + richest data
      - Title: prefer the longest non-redundant title
      - Description: longest
      - venue_name / address / location: longest non-empty
      - image_url / end_time: first non-empty from richness order
      - categories: union (preserve order)
      - link: best source's link
    """
    records.sort(key=lambda e: (SOURCE_PRIORITY.get(e.get("source", ""), 99), _pc_richness_score(e)))
    base = records[0]
    merged = dict(base)

    # Title: longest from records (more context preferred — e.g. include "at Drift" suffix)
    titles = [r.get("title") for r in records if r.get("title")]
    if titles:
        titles.sort(key=lambda t: (-len(t), t))
        merged["title"] = titles[0]

    # Description: longest
    descs = [r.get("description") or "" for r in records]
    descs.sort(key=lambda d: -len(d))
    if descs and descs[0]:
        merged["description"] = descs[0]

    # Image: first non-empty walking richness order
    for r in records:
        if r.get("image_url"):
            merged["image_url"] = r["image_url"]
            break

    # End time: first non-empty
    for r in records:
        if r.get("end_time"):
            merged["end_time"] = r["end_time"]
            break

    # Venue / address / location: longest non-empty
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

    # ATTRIBUTION OVERRIDE: pick `source` and `link` from the venue-direct or
    # tourism-authority record (per _ATTRIBUTION_PRIORITY) regardless of which
    # record won as data-richness base. Users get a canonical link to the
    # authoritative listing, not an aggregator article. Data fields stay
    # whatever was richest above.
    attribution_winner = min(
        records,
        key=lambda r: _ATTRIBUTION_PRIORITY.get(r.get("source", ""), 99),
    )
    if attribution_winner.get("source"):
        merged["source"] = attribution_winner["source"]
    if attribution_winner.get("link"):
        merged["link"] = attribution_winner["link"]
    # Track all source contributors so we can verify dedup made the right merge.
    contributors = set()
    for r in records:
        s = r.get("source")
        if s:
            contributors.add(s)
    if len(contributors) > 1:
        merged["_all_sources"] = sorted(contributors)

    return merged


def deduplicate(events):
    """Merge-aware dedup for Park City. Groups by (date, normalized_title)
    and consolidates duplicate records into one enriched entry."""
    groups: dict = {}
    for e in events:
        date = (e.get("date") or "")[:10]
        if not date or not e.get("title"):
            continue
        norm = _pc_norm_title(e["title"])
        key = (date, norm)
        groups.setdefault(key, []).append(e)

    unique = []
    merged_count = 0
    for key, records in groups.items():
        if len(records) == 1:
            unique.append(records[0])
        else:
            unique.append(_pc_merge_records(records))
            merged_count += len(records) - 1

    if merged_count:
        print(f"  [PC dedup] merged {merged_count} duplicate records into existing entries")
    return unique


# ─────────────────────────────────────────────
# 6. SERPAPI — Google Events for Park City
# ─────────────────────────────────────────────
def scrape_google_events():
    print("Scraping Google Events via SerpApi...")
    events = []
    SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

    queries = [
        "events in Park City Utah",
        "concerts Park City Utah",
        "Park City Utah festivals",
        "things to do Park City Utah this weekend",
    ]

    seen = set()

    for query in queries:
        try:
            url = "https://serpapi.com/search"
            params = {
                "engine": "google_events",
                "q": query,
                "location": "Park City, Utah, United States",
                "gl": "us",
                "hl": "en",
                "api_key": SERPAPI_KEY
            }
            r = _get(url, params=params, timeout=15)
            if r.status_code != 200:
                print(f"  SerpApi error {r.status_code} for '{query}'")
                continue

            data = r.json()
            results = data.get("events_results", [])
            print(f"  '{query}': {len(results)} events")

            for item in results:
                try:
                    title = item.get("title", "").strip()
                    if not title or len(title) < 3: continue
                    key = title.lower()[:40]
                    if key in seen: continue
                    seen.add(key)

                    date_info = item.get("date", {})
                    when = date_info.get("when", "")
                    start_date = date_info.get("start_date", "")
                    date = normalize_date_str(start_date) or normalize_date_str(when)
                    # Drop events with unparseable dates — they were previously
                    # falling through with date="See website" and breaking the UI
                    if not date:
                        continue
                    # Drop events whose date is in the past (Google sometimes
                    # returns stale data)
                    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
                    if date < today_iso:
                        continue
                    start_time = extract_time_from_string(when)

                    address = item.get("address", [])
                    if isinstance(address, list):
                        location = ", ".join(address)
                    else:
                        location = str(address) or "Park City, UT"

                    if location and not any(x in location.lower() for x in ['park city', 'ut', 'utah', 'heber', 'summit']):
                        continue

                    link = item.get("link", "") or item.get("event_location_map", {}).get("link", "")
                    ticket_info = item.get("ticket_info", [])
                    if ticket_info and isinstance(ticket_info, list):
                        link = ticket_info[0].get("link", link)

                    is_free = None
                    description = item.get("description", "")
                    if "free" in description.lower() or "free" in title.lower():
                        is_free = True
                    elif ticket_info:
                        is_free = False

                    thumbnail = item.get("thumbnail", "")

                    event = {
                        "title": title,
                        "date": date,
                        "description": description[:2000],
                        "location": location or "Park City, UT",
                        "link": link or "https://www.google.com/search?q=" + title.replace(" ", "+"),
                        "source": "Google Events",
                        "source_url": "https://www.google.com",
                        "is_free": is_free,
                        "thumbnail": thumbnail,
                        "scraped_at": datetime.now().isoformat()
                    }
                    if start_time: event["start_time"] = start_time
                    events.append(event)
                except:
                    continue

        except Exception as e:
            print(f"  SerpApi error for '{query}': {e}")
            continue

    print(f"  Found {len(events)} unique events from Google Events")
    return events


def scrape_utah_com():
    print("Scraping utah.com Park City events...")
    events = []
    try:
        urls = [
            "https://www.utah.com/events/?location=Park+City&radius=10",
            "https://www.utah.com/events/park-city/",
        ]
        for url in urls:
            try:
                r = _get(url, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                containers = (
                    soup.find_all("article") or
                    soup.find_all("div", class_=re.compile(r"event|card|listing", re.I)) or
                    soup.find_all("li", class_=re.compile(r"event|item", re.I))
                )
                for c in containers:
                    try:
                        title_el = c.find("h2") or c.find("h3") or c.find("h4")
                        if not title_el: continue
                        title = title_el.get_text(strip=True)
                        if len(title) < 3: continue
                        date_el = c.find(class_=re.compile(r"date|time|when", re.I)) or c.find("time")
                        raw_date = date_el.get_text(strip=True) if date_el else ""
                        date = normalize_date_str(raw_date) or "See website"
                        start_time = extract_time_from_string(raw_date)
                        desc_el = c.find("p")
                        description = desc_el.get_text(strip=True)[:2000] if desc_el else ""
                        link_el = c.find("a", href=True)
                        link = link_el["href"] if link_el else url
                        if link.startswith("/"): link = "https://www.utah.com" + link
                        event = {
                            "title": title, "date": date, "description": description,
                            "location": "Park City, UT", "link": link,
                            "source": "Utah.com", "source_url": url,
                            "scraped_at": datetime.now().isoformat()
                        }
                        if start_time: event["start_time"] = start_time
                        events.append(event)
                    except: continue
                if events: break
            except Exception as e:
                print(f"  utah.com URL failed: {e}")
                continue
        print(f"  Found {len(events)} events from utah.com")
    except Exception as e:
        print(f"  Error scraping utah.com: {e}")
    return events


# ─────────────────────────────────────────────
# 7. PARK CITY ARTS COUNCIL (pcscarts.org)
# ─────────────────────────────────────────────
def scrape_arts_council():
    print("Scraping Park City Arts Council events...")
    events = []
    try:
        from playwright.sync_api import sync_playwright
        url = "https://www.pcscarts.org/event-calendar"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            page.wait_for_timeout(5000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        containers = (
            soup.find_all("article") or
            soup.find_all("div", class_=re.compile(r"event|tribe|card", re.I)) or
            soup.find_all("li", class_=re.compile(r"event|tribe", re.I))
        )
        for c in containers:
            try:
                title_el = c.find("h2") or c.find("h3") or c.find("h4") or c.find(class_=re.compile(r"title", re.I))
                if not title_el: continue
                title = title_el.get_text(strip=True)
                if len(title) < 3: continue
                date_el = c.find(class_=re.compile(r"date|time|start", re.I)) or c.find("time") or c.find("abbr")
                raw_date = date_el.get_text(strip=True) if date_el else ""
                date = normalize_date_str(raw_date) or "See website"
                start_time = extract_time_from_string(raw_date)
                desc_el = c.find("p")
                description = desc_el.get_text(strip=True)[:2000] if desc_el else ""
                link_el = c.find("a", href=True)
                link = link_el["href"] if link_el else url
                if link.startswith("/"): link = "https://www.pcscarts.org" + link
                event = {
                    "title": title, "date": date, "description": description,
                    "location": "Park City, UT", "link": link,
                    "source": "PC Arts Council", "source_url": url,
                    "scraped_at": datetime.now().isoformat()
                }
                if start_time: event["start_time"] = start_time
                events.append(event)
            except: continue
        print(f"  Found {len(events)} events from Arts Council")
    except Exception as e:
        print(f"  Error scraping Arts Council: {e}")
    return events


# -------------------------------------------------------
# KPCW (covers both Park City and Heber Valley)
# -------------------------------------------------------
def scrape_kpcw_and_cache_heber():
    """Run KPCW scraper; return PC events, cache Heber events for the other pipeline."""
    try:
        from kpcw_scraper import scrape_kpcw_calendar
    except ImportError:
        print("  kpcw_scraper not available, skipping KPCW")
        return []

    pc_events, heber_events = scrape_kpcw_calendar()

    # Cache Heber events so heber_scraper.py can pick them up
    if heber_events:
        cache = {
            "updated_at": datetime.now().isoformat(),
            "events": heber_events,
        }
        try:
            # Apply canonical category classification before writing.
            from event_classifier import classify_events as _classify_events
            heber_events = _classify_events(heber_events)

            cache["events"] = heber_events
            with open("kpcw_heber_cache.json", "w") as f:
                json.dump(cache, f, indent=2)
            print(f"  Cached {len(heber_events)} Heber events from KPCW for heber_scraper to merge")
        except Exception as ex:
            print(f"  Warning: could not write kpcw_heber_cache.json: {ex}")

    return pc_events


# -------------------------------------------------------
# DEER VALLEY (resort calendar — music festival, hikes, etc)
# -------------------------------------------------------
def scrape_deer_valley_wrapper():
    """Run the Deer Valley scraper if available."""
    try:
        from deer_valley_scraper import scrape_deer_valley
    except ImportError:
        print("  deer_valley_scraper not available, skipping")
        return []
    try:
        return scrape_deer_valley()
    except Exception as ex:
        print(f"  Deer Valley scraper failed: {ex}")
        return []


# -------------------------------------------------------
# PARK CITY INSTITUTE (Concerts on the Slopes via Showpass)
# -------------------------------------------------------
def scrape_park_city_institute_wrapper():
    """Run the Park City Institute scraper if available."""
    try:
        from park_city_institute_scraper import scrape_park_city_institute
    except ImportError:
        print("  park_city_institute_scraper not available, skipping")
        return []
    try:
        return scrape_park_city_institute()
    except Exception as ex:
        print(f"  Park City Institute scraper failed: {ex}")
        return []


# -------------------------------------------------------
# MOUNTAIN TRAILS FOUNDATION (parkcitytrails.org)
# -------------------------------------------------------
def scrape_park_city_trails_wrapper():
    """Run the Mountain Trails Foundation scraper if available."""
    try:
        from park_city_trails_scraper import scrape_park_city_trails
    except ImportError:
        print("  park_city_trails_scraper not available, skipping")
        return []
    try:
        return scrape_park_city_trails()
    except Exception as ex:
        print(f"  Mountain Trails Foundation scraper failed: {ex}")
        return []


# -------------------------------------------------------
# RUNSIGNUP (Park City races)
# -------------------------------------------------------
def scrape_visit_park_city_sitemap_wrapper():
    """Wrapper around sitemap_event_scraper for visitparkcity.com."""
    try:
        from sitemap_event_scraper import scrape_sitemap_events
    except ImportError:
        print("[VPC sitemap] sitemap_event_scraper not available")
        return []
    try:
        return scrape_sitemap_events(
            sitemap_url="https://www.visitparkcity.com/sitemap.xml",
            url_pattern=r"/event/",
            source_name="Visit Park City (sitemap)",
            default_lat=40.6461,
            default_lng=-111.4980,
            default_city="Park City, UT",
            default_categories=["Community"],
            delay_seconds=1.5,  # slow crawl to stay under VPC rate limit from CI
        )
    except Exception as ex:
        print(f"[VPC sitemap] failed: {ex}")
        return []


def scrape_runsignup_parkcity_wrapper():
    """Run the RunSignup PC scraper if available."""
    try:
        from runsignup_scraper import scrape_runsignup_parkcity
    except ImportError:
        print("  runsignup_scraper not available, skipping")
        return []
    try:
        return scrape_runsignup_parkcity()
    except Exception as ex:
        print(f"  RunSignup PC scraper failed: {ex}")
        return []


# -------------------------------------------------------
# SLRC (Salt Lake Running Co)
# -------------------------------------------------------
def scrape_slrc_parkcity_wrapper():
    """Run the SLRC PC scraper if available."""
    try:
        from slrc_scraper import scrape_slrc_parkcity
    except ImportError:
        print("  slrc_scraper not available, skipping")
        return []
    try:
        return scrape_slrc_parkcity()
    except Exception as ex:
        print(f"  SLRC PC scraper failed: {ex}")
        return []


# -------------------------------------------------------
# DEER VALLEY MUSIC FESTIVAL
# -------------------------------------------------------
def scrape_dvmf_wrapper():
    """Run the Deer Valley Music Festival scraper if available."""
    try:
        from deer_valley_music_festival_scraper import scrape_deer_valley_music_festival
    except ImportError:
        print("  deer_valley_music_festival_scraper not available, skipping")
        return []
    try:
        return scrape_deer_valley_music_festival()
    except Exception as ex:
        print(f"  DVMF scraper failed: {ex}")
        return []


# -------------------------------------------------------
# PARK CITY OPERA (via universal Schema.org v2)
# -------------------------------------------------------
def scrape_park_city_opera_wrapper():
    """Run Park City Opera scraper via universal Schema.org v2 parser."""
    try:
        from schema_org_scraper_v2 import scrape_schema_org_v2
    except ImportError:
        print("  schema_org_scraper_v2 not available, skipping")
        return []
    try:
        return scrape_schema_org_v2(
            url="https://www.parkcityopera.org/events",
            link_pattern=r"/events/[a-z0-9-]+$",
            source_name="Park City Opera",
            default_lat=40.6461,
            default_lng=-111.4980,
            default_city="Park City, UT",
            default_categories=["Music", "Opera"],
            max_detail_pages=40,
            delay_seconds=0.3,
        )
    except Exception as ex:
        print(f"  Park City Opera scraper failed: {ex}")
        return []


# -------------------------------------------------------
# GEOGRAPHIC RE-ROUTING (Park City -> Heber Valley)
# -------------------------------------------------------
HEBER_VENUE_KEYWORDS = [
    "heber valley",
    "soldier hollow",
    "heber city",
    "midway, ut",
    "midway town",
    "wallsburg",
    "deer creek state park",
    "kamas",
]


def is_heber_valley_event(event):
    """Return True if the event location is clearly in Heber Valley."""
    loc = (event.get("location") or "").lower()
    if not loc:
        return False
    return any(kw in loc for kw in HEBER_VENUE_KEYWORDS)


def relocate_heber_events(events):
    """Split events into (park_city_events, heber_events) by location."""
    pc, heber = [], []
    for e in events:
        if is_heber_valley_event(e):
            heber.append(e)
        else:
            pc.append(e)
    print(f"  Re-routing: {len(heber)} events identified as Heber Valley (will be moved)")
    return pc, heber


def merge_into_heber_file(new_events, filename="public/events-heber.json"):
    """Merge new Heber events into the Heber file with title+date dedup."""
    if not new_events:
        return

    existing_events = []
    if os.path.exists(filename):
        try:
            with open(filename) as f:
                data = json.load(f)
            existing_events = data.get("events", []) if isinstance(data, dict) else data
        except Exception as ex:
            print(f"  Warning: could not load existing {filename}: {ex}")

    seen = set()
    merged = []
    for e in existing_events + new_events:
        key = (
            (e.get("title", "") or "").lower().strip()[:40],
            (e.get("date", "") or "")[:10],
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)

    output = {
        "updated_at": datetime.now().isoformat(),
        "total": len(merged),
        "events": merged,
    }
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    added = len(merged) - len(existing_events)
    print(
        f"  Merged into {filename}: {len(existing_events)} existing + "
        f"{len(new_events)} from PC scrape = {len(merged)} total ({added} net new)"
    )


def save_events(events, filename="public/raw/events.json"):
    # Drop records with non-ISO dates ("See website", "TBA", etc).
    # These come from HTML scrapers that couldn't parse a real date.
    import re as _re
    before = len(events)
    events = [e for e in events if _re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date","")))]
    dropped = before - len(events)
    if dropped:
        print(f"  [save_events] dropped {dropped} records with non-ISO dates")
    output = {
        "updated_at": datetime.now().isoformat(),
        "total": len(events),
        "events": events
    }
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(events)} events to {filename}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Yoocal Scraper v2 -- Park City Events")
    print("=" * 55)
    print()

    all_events = []
    all_events += scrape_visit_park_city()
    all_events += scrape_visit_park_city_sitemap_wrapper()
    try:
        all_events += scrape_mountain_town_music()
    except Exception as ex:
        print(f"  [MTM] scraper failed: {ex}")
    all_events += scrape_eventbrite()
    all_events += scrape_running_in_the_usa()
    # Park Record: use the CitySpark API (the data source behind
    # parkrecord.com/calendar/). The old HTML-walker is kept as a fallback
    # in case the API ever changes shape.
    try:
        from park_record_cityspark_scraper import scrape_park_record_cityspark
        pr_events = scrape_park_record_cityspark()
        if pr_events:
            all_events += pr_events
        else:
            print("  [Park Record/CitySpark] returned 0 — falling back to legacy HTML scraper")
            all_events += scrape_park_record()
    except Exception as ex:
        print(f"  [Park Record/CitySpark] failed: {ex} — falling back")
        all_events += scrape_park_record()
    try:
        from pc_recurring_locals import scrape_recurring_locals
        all_events += scrape_recurring_locals()
    except Exception as ex:
        print(f"  [recurring_locals] skipped: {ex}")
    try:
        from park_silly_scraper import scrape_park_silly
        all_events += scrape_park_silly()
    except Exception as ex:
        print(f"  [park_silly] skipped: {ex}")
    all_events += scrape_google_events()
    all_events += scrape_utah_com()
    all_events += scrape_arts_council()
    # KPCW covers both Park City and Heber. Tockify repeats some announcements
    # as multi-day promotional billboards; kpcw_scraper._collapse_billboards now
    # collapses those to a single card while preserving genuine weekly recurring
    # events (e.g. "Yoga on the Patio - Every Thursday"). PC events flow into the
    # calendar; Heber events are cached for heber_scraper.py to pick up.
    all_events += scrape_kpcw_and_cache_heber()
    all_events += scrape_deer_valley_wrapper()
    all_events += scrape_park_city_institute_wrapper()
    all_events += scrape_park_city_trails_wrapper()
    all_events += scrape_dvmf_wrapper()
    all_events += scrape_park_city_opera_wrapper()
    all_events += scrape_runsignup_parkcity_wrapper()
    all_events += scrape_slrc_parkcity_wrapper()

    print(f"\nTotal raw events: {len(all_events)}")
    unique = deduplicate(all_events)
    print(f"After deduplication: {len(unique)}")
    print(f"After recurring tagging: {len(unique)}")

    # Re-route Heber Valley events to the Heber file BEFORE saving PC
    pc_events, heber_events = relocate_heber_events(unique)
    if heber_events:
        merge_into_heber_file(heber_events)

    save_events(pc_events)

    print()
    print("Done! Sample events found:")
    for e in unique[:10]:
        print(f"  [{e['source']}] {e['title']} -- {e['date']} {e.get('start_time','')}")

if __name__ == "__main__":
    main()
