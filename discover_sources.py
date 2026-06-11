"""
discover_sources.py — Auto-discover event calendar sources for any town.

This is the foundation for the "search any town, get all events" vision.
Given a city name, it:
  1. Runs targeted Google searches via SerpApi
  2. Visits each result URL
  3. Detects calendar tech (FullCalendar, Tockify, WordPress events, etc)
  4. Scores each candidate by signal strength
  5. Samples a few events if possible (verification)
  6. Writes findings to pending_sources.json
  7. Optionally emails a summary via Resend

Usage:
    python3 discover_sources.py --city "park city utah"
    python3 discover_sources.py --city "jackson hole wyoming"
    python3 discover_sources.py --city "park city utah" --email
    python3 discover_sources.py --city "jackson hole wyoming" --max-urls 30

Requires:
    SERPAPI_KEY env var (already set for our existing scrapers)
    RESEND_API_KEY env var (only if --email flag is used)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

# --------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
OUTPUT_FILE = "pending_sources.json"

# Sources we already know about — skip these
ALREADY_KNOWN_DOMAINS = {
    "parkrecord.com", "visitparkcity.com", "kpcw.org", "deervalley.com",
    "parkcityinstitute.org", "parkcitytrails.org", "runsignup.com",
    "slrc.com", "runningintheusa.com", "gohebervalley.com",
    "elkhartlake.com", "roadamerica.com",
}

# Domains we should NEVER suggest as scraping targets
BLACKLIST_DOMAINS = {
    # Social media
    "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
    "linkedin.com", "youtube.com", "reddit.com", "pinterest.com",
    # Review aggregators
    "yelp.com", "tripadvisor.com", "yelp.ca", "google.com",
    # News aggregators (different from local newspapers — those are good sources)
    "news.google.com", "msn.com", "bing.com",
    # Generic event marketplaces — usually wider than one town, and have their own APIs we'd integrate differently
    "eventbrite.com", "ticketmaster.com", "stubhub.com", "seatgeek.com",
    "meetup.com",  # Meetup has an API; treat separately
    # SEO content farms
    "thingstodopost.com", "tripsavvy.com", "afar.com",
}

# Calendar tech detection markers
# Format: (pattern, calendar_type, signal_strength_score)
TECH_MARKERS = [
    # Strong signals — calendar widgets we know how to scrape
    (r"core\.service\.elfsight\.com/p/boot/", "elfsight", 9),
    (r"rhc_action=get_calendar_events", "calendarize-it", 9),
    (r"tockify\.com/api/ngevent", "tockify-api", 9),
    (r"tockify\.com/api", "tockify", 8),
    (r"showpass\.com/api/public", "showpass-api", 9),
    (r"showpass-embed", "showpass-embed", 7),
    (r"wp-json/tribe/events", "wordpress-tribe", 9),
    (r"tribe-events-calendar", "wordpress-tribe", 7),

    # Medium signals — common calendar libraries
    (r"fullcalendar", "fullcalendar", 6),
    (r"data-event-id", "data-attributes", 5),
    (r"ai1ec_event", "all-in-one-events", 6),
    (r'"@type"\s*:\s*"Event"', "schema-org-event", 7),

    # Weak signals — page has SOMETHING about events
    (r"upcoming\s*events", "text-only", 1),
    (r"event\s*calendar", "text-only", 1),
    (r"events?-list", "events-list-class", 2),
]

# Schema.org JSON-LD Event pattern — extract titles/dates if found
SCHEMA_EVENT_PATTERN = re.compile(
    r'"@type"\s*:\s*"Event"[^}]*?"name"\s*:\s*"([^"]+)"[^}]*?"startDate"\s*:\s*"([^"]+)"',
    re.IGNORECASE | re.DOTALL,
)

# --------------------------------------------------------------
# 1. SEARCH — get a list of candidate URLs
# --------------------------------------------------------------

QUERY_TEMPLATES = [
    '"{city}" events calendar',
    '"{city}" upcoming events',
    '"{city}" things to do this weekend',
    '"{city}" concerts',
    '"{city}" festivals',
    '"{city}" races',
    '"{city}" community calendar',
    '"{city}" arts and culture events',
]


def search_for_candidates(city, max_per_query=10):
    """Run a batch of Google searches via SerpApi. Returns deduped list of URLs."""
    if not SERPAPI_KEY:
        print("ERROR: SERPAPI_KEY env var not set. Aborting.")
        sys.exit(1)

    seen_urls = set()
    candidates = []

    for tpl in QUERY_TEMPLATES:
        query = tpl.format(city=city)
        print(f"  [search] {query}")

        try:
            r = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "q": query,
                    "api_key": SERPAPI_KEY,
                    "num": max_per_query,
                    "engine": "google",
                },
                timeout=20,
            )
            data = r.json()
        except Exception as ex:
            print(f"    SerpApi error: {ex}")
            continue

        for result in data.get("organic_results", []):
            url = result.get("link", "")
            title = result.get("title", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({"url": url, "title": title, "query": query})

        time.sleep(0.5)  # be nice to SerpApi

    print(f"\n  Got {len(candidates)} unique URLs across {len(QUERY_TEMPLATES)} queries")
    return candidates


# --------------------------------------------------------------
# 2. FILTER — drop blacklisted and already-known domains
# --------------------------------------------------------------

def is_useful_candidate(url):
    """Return (True, reason) if worth investigating, (False, reason) otherwise."""
    try:
        domain = urlparse(url).netloc.lower()
        # Strip www.
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return False, "unparseable"

    if domain in BLACKLIST_DOMAINS:
        return False, "blacklisted"
    if domain in ALREADY_KNOWN_DOMAINS and os.environ.get("INCLUDE_KNOWN") != "1":
        return False, "already-known"

    # Skip Eventbrite city pages (eventbrite.com/d/...)
    if "eventbrite." in domain:
        return False, "eventbrite-marketplace"

    return True, "ok"


# --------------------------------------------------------------
# 3. FETCH + DETECT — visit each URL and look for calendar tech
# --------------------------------------------------------------

def fetch_and_detect(url, timeout=15):
    """Fetch URL, detect calendar markers, sample events. Returns dict or None."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except Exception as ex:
        return {"error": f"fetch failed: {type(ex).__name__}"}

    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}

    text = r.text
    text_lower = text.lower()
    bytes_len = len(r.content)

    # Detect tech markers
    detected = []
    total_score = 0
    for pattern, name, score in TECH_MARKERS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            detected.append({"type": name, "score": score})
            total_score += score

    # Future-dated ISO strings — strong signal that real events exist
    current_year = datetime.now().year
    future_year_pattern = rf"\b({current_year}|{current_year+1})-\d{{2}}-\d{{2}}\b"
    future_dates = set(re.findall(future_year_pattern, text))
    if future_dates:
        total_score += min(len(future_dates), 5)  # cap bonus at 5

    # Sample events — Schema.org JSON-LD is the cleanest
    samples = []
    for m in SCHEMA_EVENT_PATTERN.finditer(text):
        name, start_date = m.group(1), m.group(2)
        samples.append({"title": name[:80], "date": start_date[:10]})
        if len(samples) >= 5:
            break

    # If no Schema.org, try to find any obvious event title + date pairs
    if not samples and future_dates:
        # Look for h2/h3 titles near dates (very rough heuristic)
        # Just report how many future dates we found
        samples = [{"note": f"{len(future_dates)} future-dated strings detected"}]

    final_url = r.url

    return {
        "fetch_status": "ok",
        "final_url": final_url,
        "bytes": bytes_len,
        "detected_tech": detected,
        "future_dates_count": len(future_dates),
        "samples": samples,
        "score": total_score,
    }


# --------------------------------------------------------------
# 4. MAIN — orchestrate
# --------------------------------------------------------------

def discover(city, max_urls=50, send_email=False):
    print(f"\n{'='*60}")
    print(f"Source discovery for: {city}")
    print(f"{'='*60}\n")

    # Search
    print("Step 1: Running Google searches...")
    candidates = search_for_candidates(city)

    # Filter
    print("\nStep 2: Filtering candidates...")
    filtered = []
    skipped_already_known = 0
    skipped_blacklisted = 0
    for c in candidates:
        ok, reason = is_useful_candidate(c["url"])
        if ok:
            filtered.append(c)
        else:
            if reason == "already-known":
                skipped_already_known += 1
            elif reason == "blacklisted":
                skipped_blacklisted += 1
    print(f"  Kept {len(filtered)} (skipped {skipped_already_known} known, {skipped_blacklisted} blacklisted)")

    if not filtered:
        print("\nNo new candidates found. Exiting.")
        return

    # Cap at max_urls
    filtered = filtered[:max_urls]

    # Fetch + detect
    print(f"\nStep 3: Fetching + detecting calendar tech ({len(filtered)} URLs)...")
    results = []
    for i, c in enumerate(filtered, 1):
        url = c["url"]
        domain = urlparse(url).netloc
        print(f"  [{i:>2}/{len(filtered)}] {domain[:50]}", end="", flush=True)
        info = fetch_and_detect(url)
        c.update(info)
        results.append(c)

        score = info.get("score", 0)
        tech = ", ".join(d["type"] for d in info.get("detected_tech", [])) or "none"
        if "error" in info:
            print(f" — {info['error']}")
        else:
            print(f" — score={score}, tech=[{tech[:40]}]")
        time.sleep(0.5)

    # Score + sort
    print("\nStep 4: Scoring and ranking...")
    # Drop low-score and error candidates
    scored = [r for r in results if r.get("score", 0) >= 2]
    scored.sort(key=lambda r: r.get("score", 0), reverse=True)
    print(f"  {len(scored)} candidates scored >= 5")

    # Write output
    output = {
        "city": city,
        "discovered_at": datetime.now().isoformat(),
        "total_search_results": len(candidates),
        "filtered_count": len(filtered),
        "candidates": scored,
        "all_results_for_review": results,
    }

    out_path = OUTPUT_FILE
    # If file exists, append to a list keyed by city
    if os.path.exists(out_path):
        try:
            existing = json.load(open(out_path))
            if isinstance(existing, dict) and "runs" in existing:
                existing["runs"].append(output)
                final = existing
            else:
                final = {"runs": [existing, output]} if isinstance(existing, dict) else {"runs": [output]}
        except Exception:
            final = {"runs": [output]}
    else:
        final = {"runs": [output]}

    with open(out_path, "w") as f:
        json.dump(final, f, indent=2)
    print(f"\nSaved to {out_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Top candidates for {city}:")
    print(f"{'='*60}")
    for r in scored[:10]:
        url = r["url"][:75]
        score = r.get("score", 0)
        tech = ", ".join(d["type"] for d in r.get("detected_tech", []))
        print(f"  [{score:>2}] {url}")
        print(f"       tech: {tech}")
        if r.get("samples"):
            for s in r["samples"][:2]:
                if "title" in s and "date" in s:
                    print(f"       sample: {s['date']} | {s['title'][:60]}")
                elif "note" in s:
                    print(f"       {s['note']}")
        print()

    # Email summary
    if send_email and scored:
        send_summary_email(city, scored[:10])


def send_summary_email(city, top_candidates):
    """Email a summary of findings via Resend."""
    if not RESEND_API_KEY:
        print("Skipping email (RESEND_API_KEY not set)")
        return

    lines = [f"Source discovery results for: {city}", "", f"Top {len(top_candidates)} candidates:", ""]
    for r in top_candidates:
        score = r.get("score", 0)
        tech = ", ".join(d["type"] for d in r.get("detected_tech", []))
        lines.append(f"  [{score}] {r['url']}")
        lines.append(f"      tech: {tech}")
        for s in r.get("samples", [])[:2]:
            if "title" in s and "date" in s:
                lines.append(f"      sample: {s['date']} | {s['title'][:60]}")
        lines.append("")

    body = "\n".join(lines)

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "yoocal discovery <submit@yoocal.com>",
                "to": ["hello@yoocal.com"],
                "subject": f"[yoocal discovery] {city} — {len(top_candidates)} sources found",
                "text": body,
            },
            timeout=20,
        )
        if r.status_code == 200:
            print("Email summary sent.")
        else:
            print(f"Email failed: {r.status_code} {r.text[:200]}")
    except Exception as ex:
        print(f"Email error: {ex}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", required=True, help="e.g. 'park city utah'")
    parser.add_argument("--max-urls", type=int, default=50)
    parser.add_argument("--email", action="store_true", help="Send summary email via Resend")
    args = parser.parse_args()

    discover(args.city, max_urls=args.max_urls, send_email=args.email)
