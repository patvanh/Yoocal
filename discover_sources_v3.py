"""
discover_sources_v3.py — Find event calendars on any town's web presence.

Evolution of v1. Same input/output contract:
  python3 discover_sources_v3.py --city "name"

What v3 adds, in probe-ladder order per candidate:
  1. Sitemap probe       → /sitemap.xml + filter for /event/ URLs
  2. RSS probe           → /event/rss/, /events/feed/, /events/rss/, /feed/
  3. Tribe API probe     → /wp-json/tribe/events/v1/events with browser headers
  4. HTML tech detection → existing TECH_MARKERS table
  5. Playwright fallback → headless Chromium, watch network for known API patterns

Output JSON: pending_sources_v3.json. Each entry has a 'scraper_config' field
ready to drop into a city orchestrator.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests


SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
OUTPUT_FILE = "pending_sources_v3.json"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch(url, timeout=15, accept_json=False):
    """Single HTTP GET, returns (status_code, text, content_type) or (None, '', '')."""
    h = dict(BROWSER_HEADERS)
    if accept_json:
        h["Accept"] = "application/json, text/plain, */*"
    try:
        r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
        return r.status_code, r.text, r.headers.get("content-type", "")
    except Exception:
        return None, "", ""




# --------------------------------------------------------------
# PROBE 1: SITEMAP
# --------------------------------------------------------------

# URL patterns inside a sitemap that suggest event detail pages.
# Order matters — first match wins for emitting a scraper config.
EVENT_URL_PATTERNS = [
    r"/event/",
    r"/events/",
    r"/calendar/",
]


# --------------------------------------------------------------
# RICHNESS VALIDATOR
# --------------------------------------------------------------

def _validate_richness(sample_urls, max_samples=3, timeout=12):
    """
    Fetch a few sample event detail pages and confirm they actually
    contain well-populated event data. Returns dict with:
      - quality_score: 0-3 per page, averaged
      - future_event_ratio: fraction of sampled pages with future startDate
      - sample_count: how many we successfully parsed
      - issues: list of human-readable problems found
    """
    import json as _json
    from datetime import datetime as _dt

    today_iso = _dt.utcnow().strftime("%Y-%m-%d")
    samples = sample_urls[:max_samples]
    parsed = 0
    future_count = 0
    quality_total = 0
    issues = []

    for url in samples:
        code, text, _ = _fetch(url, timeout=timeout)
        if code != 200 or not text:
            issues.append(f"fetch failed: {url[:80]}")
            continue
        # Find Schema.org Event JSON-LD blocks
        ld_pat = r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        ld_blocks = re.findall(ld_pat, text, re.DOTALL)
        event_obj = None
        for blk in ld_blocks:
            try:
                d = _json.loads(blk.strip())
                items = d if isinstance(d, list) else [d]
                for it in items:
                    if isinstance(it, dict) and "Event" in str(it.get("@type", "")):
                        event_obj = it
                        break
                if event_obj:
                    break
            except Exception:
                pass

        if not event_obj:
            issues.append(f"no Event JSON-LD: {url[:80]}")
            continue

        parsed += 1

        # Score this page's richness 0-3
        score = 0
        sd = (event_obj.get("startDate") or "")[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", sd):
            score += 1
            if sd >= today_iso:
                future_count += 1

        loc = event_obj.get("location")
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict) and addr.get("streetAddress"):
                score += 1

        desc = event_obj.get("description") or ""
        if isinstance(desc, str) and len(desc.strip()) > 50:
            score += 1

        quality_total += score

    if parsed == 0:
        return {
            "quality_score": 0.0,
            "future_event_ratio": 0.0,
            "sample_count": 0,
            "issues": issues or ["no pages parsed"],
        }

    return {
        "quality_score": round(quality_total / parsed, 2),
        "future_event_ratio": round(future_count / parsed, 2),
        "sample_count": parsed,
        "issues": issues,
    }


def _adjust_confidence_by_richness(base_confidence, richness):
    """Downgrade confidence if richness check shows weak data."""
    score = richness.get("quality_score", 0)
    ratio = richness.get("future_event_ratio", 0)
    n = richness.get("sample_count", 0)
    if n == 0:
        return "low-no-samples"
    if score < 1.0 or ratio < 0.2:
        return "low-poor-data"
    if score < 2.0:
        return "medium-thin-data"
    return base_confidence


def probe_sitemap(domain):
    """
    Fetch /sitemap.xml at the given domain (with and without www).
    Returns dict with status and (if found) a ready-to-use scraper config.

    domain: bare domain like "www.jacksonholechamber.com"
    """
    # Try both with and without www.
    bases = []
    if domain.startswith("www."):
        bases = [f"https://{domain}", f"https://{domain[4:]}"]
    else:
        bases = [f"https://www.{domain}", f"https://{domain}"]

    for base in bases:
        url = base + "/sitemap.xml"
        code, text, ctype = _fetch(url, timeout=15)
        if code != 200 or not text:
            continue
        # Make sure we got XML, not an HTML fallback page
        if "xml" not in ctype.lower() and "<urlset" not in text and "<sitemapindex" not in text:
            continue

        # Handle sitemap-index (a sitemap of sitemaps) by fetching one level deeper
        sub_locs = re.findall(r"<sitemap>\s*<loc>([^<]+)</loc>", text)
        all_urls = []
        if sub_locs:
            # Cap at 10 sub-sitemaps to avoid runaway
            for sub_url in sub_locs[:10]:
                sub_code, sub_text, _ = _fetch(sub_url, timeout=15)
                if sub_code == 200 and sub_text:
                    all_urls += re.findall(r"<loc>([^<]+)</loc>", sub_text)
        else:
            all_urls = re.findall(r"<loc>([^<]+)</loc>", text)

        if not all_urls:
            continue

        # Try each event-URL pattern, pick the strongest match
        best = None
        for pat in EVENT_URL_PATTERNS:
            matching = [u for u in all_urls if re.search(pat, u)]
            if len(matching) >= 5:  # threshold: 5+ event URLs = real
                if best is None or len(matching) > best["count"]:
                    # Sample across the matching URLs: take from the END (newest)
                    # plus middle, plus a couple from the start. Sitemaps are
                    # typically chronological; newest = most likely to be future.
                    n = len(matching)
                    if n <= 6:
                        sample = matching
                    else:
                        sample = [
                            matching[-1], matching[-2], matching[-3],  # newest 3
                            matching[n // 2],                          # middle
                            matching[0], matching[1],                  # oldest 2
                        ]
                    best = {
                        "pattern": pat,
                        "count": n,
                        "sample_urls": sample,
                    }

        if best:
            # Validate richness: do these URLs actually contain populated events?
            richness = _validate_richness(best["sample_urls"], max_samples=3)
            return {
                "found": True,
                "sitemap_url": url,
                "total_urls_in_sitemap": len(all_urls),
                "event_url_count": best["count"],
                "url_pattern": best["pattern"],
                "sample_urls": best["sample_urls"],
                "richness": richness,
                "estimated_future_events": int(best["count"] * richness.get("future_event_ratio", 0)),
                "scraper_config": {
                    "type": "sitemap_event_scraper",
                    "function": "scrape_sitemap_events",
                    "args": {
                        "sitemap_url": url,
                        "url_pattern": best["pattern"],
                    },
                },
            }

    return {"found": False}






# --------------------------------------------------------------
# PROBE 2: RSS
# --------------------------------------------------------------

RSS_PATHS = [
    "/event/rss/",
    "/events/rss/",
    "/events/feed/",
    "/feed/",
    "/events.rss",
    "/rss/events",
]


def probe_rss(domain):
    """
    Try standard RSS paths. Returns dict with status and scraper config.
    """
    bases = []
    if domain.startswith("www."):
        bases = [f"https://{domain}", f"https://{domain[4:]}"]
    else:
        bases = [f"https://www.{domain}", f"https://{domain}"]

    for base in bases:
        for path_suffix in RSS_PATHS:
            url = base + path_suffix
            code, text, ctype = _fetch(url, timeout=10)
            if code != 200 or not text:
                continue
            # Must look like RSS — content-type or body signal
            looks_rss = (
                "rss" in ctype.lower()
                or "xml" in ctype.lower()
                or "<rss" in text[:500].lower()
                or "<channel>" in text[:1000].lower()
            )
            if not looks_rss:
                continue
            items = re.findall(r"<item[\s>]", text)
            if len(items) < 3:  # need at least a few items
                continue
            # Filter: feed must mention events, not just news
            text_lo = text[:5000].lower()
            event_signal = sum([
                "event" in text_lo,
                "calendar" in text_lo,
                "venue" in text_lo,
            ])
            # Extract <link> URLs from RSS items for richness validation
            link_urls = re.findall(r"<link>([^<]+)</link>", text)
            # Skip the first one (it's the channel link, not an item)
            sample_links = link_urls[1:4] if len(link_urls) > 1 else []
            richness = _validate_richness(sample_links, max_samples=3) if sample_links else {"quality_score": 0, "future_event_ratio": 0, "sample_count": 0, "issues": ["no item links"]}
            return {
                "found": True,
                "feed_url": url,
                "item_count": len(items),
                "event_signal_score": event_signal,
                "richness": richness,
                "estimated_future_events": int(len(items) * richness.get("future_event_ratio", 0)),
                "scraper_config": {
                    "type": "rss_scraper",
                    "function": "scrape_rss",
                    "args": {"feed_url": url},
                },
            }
    return {"found": False}






# --------------------------------------------------------------
# PROBE 3: WORDPRESS TRIBE EVENTS API
# --------------------------------------------------------------



def _validate_tribe_richness(events):
    """
    Score Tribe API events directly from their JSON fields, rather than
    fetching each event's HTML page and looking for JSON-LD.

    Tribe events come back with: id, title, start_date, end_date, venue,
    description, url, etc. Quality is high if title + start_date + a venue
    OR description are present, and the start date is in the future.
    """
    from datetime import datetime
    today_iso = datetime.now().strftime("%Y-%m-%d")

    if not events:
        return {"quality_score": 0.0, "future_event_ratio": 0.0, "sample_count": 0, "issues": ["no events to score"]}

    sampled = events[:5]  # score up to 5
    total_score = 0
    future_count = 0
    issues = []

    for e in sampled:
        score = 0
        if e.get("title"):
            score += 1
        # start_date in Tribe is usually "2026-05-20 18:00:00" or ISO format
        sd = e.get("start_date") or ""
        if sd and len(sd) >= 10:
            score += 1
            if sd[:10] >= today_iso:
                future_count += 1
        # Venue or description as the "richness" indicator
        venue = e.get("venue") or {}
        if (isinstance(venue, dict) and venue.get("venue")) or e.get("description"):
            score += 1
        total_score += score
        if score < 2:
            issues.append(f"thin event: {(e.get('title') or '?')[:40]}")

    avg = total_score / len(sampled)
    return {
        "quality_score": round(avg, 2),
        "future_event_ratio": round(future_count / len(sampled), 2),
        "sample_count": len(sampled),
        "issues": issues,
    }


def probe_wp_tribe(domain):
    """
    Try /wp-json/tribe/events/v1/events?per_page=1 with browser headers.
    Some WP sites disable REST API and return HTML — we must confirm JSON.
    """
    bases = []
    if domain.startswith("www."):
        bases = [f"https://{domain}", f"https://{domain[4:]}"]
    else:
        bases = [f"https://www.{domain}", f"https://{domain}"]

    for base in bases:
        url = f"{base}/wp-json/tribe/events/v1/events?per_page=1"
        code, text, ctype = _fetch(url, timeout=12, accept_json=True)
        if code != 200 or not text:
            continue
        # Must be JSON, not HTML fallback
        if "json" not in ctype.lower() and not text.lstrip().startswith("{"):
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        if not isinstance(data, dict) or "events" not in data:
            continue
        total = data.get("total") or len(data.get("events", []))

        # Score richness directly from the API response (not from HTML pages).
        # The Tribe API gives us all the fields we need to assess quality
        # without an extra HTTP round-trip per event.
        sample_events = []
        try:
            batch_url = f"{base}/wp-json/tribe/events/v1/events?per_page=5"
            bcode, btext, _ = _fetch(batch_url, timeout=12, accept_json=True)
            if bcode == 200 and btext:
                bdata = json.loads(btext)
                sample_events = bdata.get("events", []) or []
        except Exception:
            pass

        richness = _validate_tribe_richness(sample_events)

        return {
            "found": True,
            "api_url": url,
            "total_events": total,
            "richness": richness,
            "estimated_future_events": int(total * richness.get("future_event_ratio", 0)),
            "scraper_config": {
                "type": "wp_tribe_events_scraper",
                "function": "scrape_wp_tribe_events",
                "args": {
                    "base_url": base,
                    "needs_browser_headers": True,
                },
            },
        }
    return {"found": False}






# --------------------------------------------------------------
# PROBE 4: PLAYWRIGHT FALLBACK
# --------------------------------------------------------------

# Network-request URL patterns that indicate an event API call.
# Each matches a substring of a request URL we capture during page load.
PLAYWRIGHT_API_PATTERNS = [
    (r"simpleviewinc\.com/.*api", "simpleview"),
    (r"/api/widget/event", "simpleview-widget"),
    (r"tockify\.com/api/ngevent", "tockify"),
    (r"core\.service\.elfsight\.com", "elfsight"),
    (r"showpass\.com/api/public", "showpass"),
    (r"calendarize-it", "calendarize-it"),
    (r"rhc_action=get_calendar_events", "rhc-calendar"),
    (r"/wp-admin/admin-ajax\.php\?action=.*event", "wp-admin-ajax"),
    (r"/wp-json/.*event", "wp-rest-events"),
    (r"fullcalendar.*\.json", "fullcalendar-feed"),
]

# Common /events-style entry paths to probe in addition to homepage
PLAYWRIGHT_EVENT_PATHS = ["/events/", "/events", "/calendar/", "/calendar", "/things-to-do/events"]


def probe_playwright(domain, timeout_seconds=15):
    """
    Last-resort probe. Launch headless Chromium, navigate to candidate
    event-page URLs, watch network for known event-API patterns, and
    extract Schema.org JSON-LD from the rendered DOM.

    Returns dict with status and (if found) a scraper config hint.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"found": False, "error": "playwright not installed"}

    bases = []
    if domain.startswith("www."):
        bases = [f"https://{domain}"]
    else:
        bases = [f"https://www.{domain}"]

    api_hits = []  # captured network URLs matching our patterns
    dom_hits = []  # DOM selectors that matched event cards
    schema_event_count = 0
    visited_url = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Denver",
            )
            page = ctx.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            })

            def on_request(req):
                u = req.url
                for pat, label in PLAYWRIGHT_API_PATTERNS:
                    if re.search(pat, u, re.IGNORECASE):
                        api_hits.append({"label": label, "url": u[:200]})
                        break

            page.on("request", on_request)

            # Try the candidate event paths in order, stop at first success
            for base in bases:
                for sub in PLAYWRIGHT_EVENT_PATHS:
                    url = base + sub
                    try:
                        page.goto(url, wait_until="networkidle", timeout=timeout_seconds * 1000)
                        visited_url = url
                    except Exception:
                        continue
                    # Try to find Schema.org Event JSON-LD in rendered DOM
                    try:
                        html = page.content()
                        schema_event_count = html.count('"@type":"Event"') + html.count("'@type':'Event'")
                    except Exception:
                        pass

                    # DOM-scrape: look for common event-card selectors in the rendered page.
                    # Many JS-rendered sites don't expose APIs we recognize but DO render
                    # event cards into the DOM with predictable class names.
                    try:
                        dom_selectors = [
                            ".tribe-events-calendar-list__event",
                            ".tribe-events-calendar-day__event",
                            ".tribe-events-loop .type-tribe_events",
                            "[class*='event-card']",
                            "[class*='event-item']",
                            "[class*='EventCard']",
                            "[data-event-id]",
                            "article.event",
                            "li.event",
                            ".event-listing",
                            ".calendar-event",
                            "[itemtype*='Event']",
                        ]
                        for sel in dom_selectors:
                            count = page.locator(sel).count()
                            if count >= 5:
                                dom_hits.append({"selector": sel, "count": count})
                    except Exception:
                        pass

                    if api_hits or schema_event_count >= 3 or dom_hits:
                        break
                if api_hits or schema_event_count >= 3 or dom_hits:
                    break

            browser.close()
    except Exception as e:
        return {"found": False, "error": f"playwright failed: {type(e).__name__}: {e}"}

    if not api_hits and schema_event_count < 3 and not dom_hits:
        return {"found": False, "visited_url": visited_url}

    # Pick the most common API label as the primary hint
    label_counts = {}
    for h in api_hits:
        label_counts[h["label"]] = label_counts.get(h["label"], 0) + 1

    if api_hits:
        primary_label = max(label_counts, key=label_counts.get)
    elif dom_hits:
        primary_label = f"dom-scrape:{dom_hits[0]['selector']}"
    else:
        primary_label = "schema-org-rendered"

    sample_api_url = api_hits[0]["url"] if api_hits else None
    best_dom_selector = max(dom_hits, key=lambda x: x["count"]) if dom_hits else None

    return {
        "found": True,
        "visited_url": visited_url,
        "schema_event_count_in_dom": schema_event_count,
        "api_calls_captured": len(api_hits),
        "dom_selectors_matched": dom_hits,
        "primary_label": primary_label,
        "sample_api_url": sample_api_url,
        "scraper_config": {
            "type": "playwright_capture_scraper",
            "function": "scrape_playwright_capture",
            "args": {
                "page_url": visited_url,
                "api_url_pattern": sample_api_url,
                "dom_selector": best_dom_selector["selector"] if best_dom_selector else None,
                "dom_event_count": best_dom_selector["count"] if best_dom_selector else 0,
                "primary_label": primary_label,
            },
            "notes": "Last-resort scraper — DOM-scrape if dom_selector set, network capture otherwise.",
        },
    }






# --------------------------------------------------------------
# QUERY TEMPLATES
# --------------------------------------------------------------

QUERY_TEMPLATES = [
    '"{city}" chamber of commerce events',
    '"{city}" events calendar',
    '"{city}" upcoming events',
    '"{city}" things to do this weekend',
    '"{city}" concerts',
    '"{city}" festivals',
    '"{city}" community calendar',
    '"{city}" arts and culture events',
    # Local media — papers and stations often aggregate the whole valley,
    # including events in smaller neighboring towns within the radius.
    '"{city}" newspaper events calendar',
    '"{city}" local news community calendar',
    '"{city}" radio station events',
    '"{city}" public library events calendar',
    # Venue-direct + civic sources
    '"{city}" live music tonight',
    '"{city}" brewery OR taproom events',
    '"{city}" city government calendar',
]


# Domains never worth probing
BLACKLIST_DOMAINS = {
    # Social
    "facebook.com", "m.facebook.com", "instagram.com", "twitter.com",
    "x.com", "tiktok.com", "linkedin.com", "youtube.com",
    "reddit.com", "pinterest.com",
    # Reviews/aggregators
    "yelp.com", "tripadvisor.com", "google.com",
    "news.google.com", "msn.com", "bing.com",
    # National event marketplaces
    "eventbrite.com", "ticketmaster.com", "stubhub.com", "seatgeek.com",
    "meetup.com", "eventeny.com", "allevents.in", "eventscase.com",
    # Nonprofits / orgs whose sitemaps surface in city searches but
    # aren't local-event aggregators (they're org-internal calendars)
    "encircletogether.org",
    # Real-estate / professional service blogs that happen to mention events
    "homesbymeriann.com",
}


def _domain_of(url):
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def _is_useful_domain(domain):
    return domain and domain not in BLACKLIST_DOMAINS


# --------------------------------------------------------------
# SEARCH (uses SerpApi, same approach as v1)
# --------------------------------------------------------------

def search_for_candidates(city, max_per_query=10):
    if not SERPAPI_KEY:
        print("ERROR: SERPAPI_KEY env var not set.")
        sys.exit(1)

    seen = set()
    results = []
    for tpl in QUERY_TEMPLATES:
        q = tpl.format(city=city)
        print(f"  [search] {q}")
        try:
            r = requests.get(
                "https://serpapi.com/search.json",
                params={"q": q, "api_key": SERPAPI_KEY, "num": max_per_query, "engine": "google"},
                timeout=20,
            )
            data = r.json()
        except Exception as ex:
            print(f"    SerpApi error: {ex}")
            continue
        for item in data.get("organic_results", []):
            url = item.get("link", "")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append({"url": url, "title": item.get("title", ""), "query": q})
        time.sleep(0.5)
    print(f"  -> {len(results)} unique URLs across {len(QUERY_TEMPLATES)} queries")
    return results


# --------------------------------------------------------------
# ORCHESTRATOR
# --------------------------------------------------------------

def discover(city, max_domains=20):
    print(f"\n{'='*60}\nDiscovery v3 — {city}\n{'='*60}\n")

    print("Step 1: Google search for candidate URLs...")
    candidates = search_for_candidates(city)

    # Dedup by domain, drop blacklisted
    print("\nStep 2: Filtering to unique useful domains...")
    seen_domains = {}
    for c in candidates:
        d = _domain_of(c["url"])
        if not _is_useful_domain(d):
            continue
        seen_domains.setdefault(d, c)  # keep first-seen
    print(f"  -> {len(seen_domains)} unique useful domains")

    if max_domains:
        domains_in_order = list(seen_domains.keys())[:max_domains]
    else:
        domains_in_order = list(seen_domains.keys())

    print(f"\nStep 3: Probing top {len(domains_in_order)} domains...")
    out = []
    for i, d in enumerate(domains_in_order, 1):
        print(f"  [{i}/{len(domains_in_order)}] {d}")
        report = {"domain": d, "first_seen_url": seen_domains[d]["url"], "probes": {}}

        s = probe_sitemap(d)
        report["probes"]["sitemap"] = s
        if s["found"]:
            print(f"    sitemap: FOUND {s['event_url_count']} event URLs ({s['url_pattern']!r})")

        r = probe_rss(d)
        report["probes"]["rss"] = r
        if r["found"]:
            print(f"    rss: FOUND {r['item_count']} items")

        t = probe_wp_tribe(d)
        report["probes"]["wp_tribe"] = t
        if t["found"]:
            print(f"    wp_tribe: FOUND {t['total_events']} events")

        # Playwright only if cheap probes all empty
        if not (s["found"] or r["found"] or t["found"]):
            print(f"    cheap probes empty — running playwright...")
            pw = probe_playwright(d)
            report["probes"]["playwright"] = pw
            if pw["found"]:
                dom_info = ""
                if pw.get("dom_selectors_matched"):
                    sel = pw["dom_selectors_matched"][0]
                    dom_info = f", DOM: {sel['count']} {sel['selector']!r}"
                print(f"    playwright: FOUND label={pw['primary_label']!r}{dom_info}")

        # Rank: prefer sitemap (best signal), then tribe, then rss, then playwright
        if s["found"]:
            base_conf = "high"
            if "richness" in s:
                base_conf = _adjust_confidence_by_richness(base_conf, s["richness"])
            report["recommendation"] = s["scraper_config"]
            report["confidence"] = base_conf
            report["estimated_future_events"] = s.get("estimated_future_events", 0)
        elif t["found"]:
            base_conf = "high"
            if "richness" in t:
                base_conf = _adjust_confidence_by_richness(base_conf, t["richness"])
            report["recommendation"] = t["scraper_config"]
            report["confidence"] = base_conf
            report["estimated_future_events"] = t.get("estimated_future_events", 0)
        elif r["found"]:
            base_conf = "medium"
            if "richness" in r:
                base_conf = _adjust_confidence_by_richness(base_conf, r["richness"])
            report["recommendation"] = r["scraper_config"]
            report["confidence"] = base_conf
            report["estimated_future_events"] = r.get("estimated_future_events", 0)
        elif report["probes"].get("playwright", {}).get("found"):
            report["recommendation"] = report["probes"]["playwright"]["scraper_config"]
            report["confidence"] = "low-needs-custom-adapter"
        else:
            report["recommendation"] = None
            report["confidence"] = "none"

        out.append(report)
        time.sleep(0.3)

    # Sort: actionable findings first
    confidence_rank = {
        "high": 0,
        "medium": 1,
        "medium-thin-data": 2,
        "low-poor-data": 3,
        "low-no-samples": 4,
        "low-needs-custom-adapter": 5,
        "none": 6,
    }
    out.sort(key=lambda x: confidence_rank.get(x["confidence"], 99))

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "city": city,
        "domains_probed": len(out),
        "findings": out,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote {OUTPUT_FILE} ({len(out)} domains).")

    actionable = [x for x in out if x["recommendation"]]
    print(f"\nSummary: {len(actionable)} actionable findings out of {len(out)} domains.")
    for x in actionable[:10]:
        est = x.get("estimated_future_events", "?")
        print(f"  [{x['confidence']}] {x['domain']} -> {x['recommendation']['type']} (~{est} future events)")




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover event-calendar sources for a town.")
    parser.add_argument("--city", required=True, help='City name, e.g. "Jackson Hole Wyoming"')
    parser.add_argument("--max-domains", type=int, default=20, help="Max unique domains to probe (default 20)")
    args = parser.parse_args()
    discover(args.city, max_domains=args.max_domains)
