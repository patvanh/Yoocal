"""Nightly LLM-based scraper health check.

For every source that appears in our raw events files, ask Claude:
  "Given this page's HTML and our scraper's event count, does it look like
   the scraper is working correctly? Roughly how many events should a
   human see on this page?"

Flags sources where the LLM's count is significantly higher than ours
(silent regression — exactly what happened to Deer Valley and VPC).

Output: scraper_llm_health.json with one entry per source.

Env required:
  ANTHROPIC_API_KEY
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import requests

MOUNTAIN = ZoneInfo("America/Denver")
RAW_FILES = [
    "public/raw/events.json",
    "public/raw/events-heber.json",
    "public/raw/events-jackson.json",
    "public/raw/events-elkhartlake.json",
    "public/raw/events-egyptian.json",
]

# Canonical scrape URL for each source. Only sources we know how to refetch are
# included; unknowns are skipped (not flagged).
SOURCE_URLS = {
    "Visit Park City":            "https://www.visitparkcity.com/events/",
    "Visit Park City (sitemap)":  "https://www.visitparkcity.com/events/",
    "Deer Valley Resort":         "https://www.deervalley.com/things-to-do/events",
    "Park City Institute":        "https://www.parkcityinstitute.org/events",
    "Park City Opera":            "https://parkcityopera.org/calendar",
    "Park City Farmers Market":   "https://parkcityfarmersmarket.com/",
    "Mountain Trails Foundation": "https://www.mountaintrails.org/events/",
    "Egyptian Theatre":           "https://parkcityshows.com/shows-ticketing/upcoming-shows",
    "Heber Valley Tourism":       "https://www.gohebervalley.com/events/",
    "KPCW Community Calendar":    "https://www.kpcw.org/community-calendar",
    "Jackson Hole Chamber of Commerce": "https://www.jacksonholechamber.com/events/",
    "Center for the Arts Jackson Hole": "https://www.jhcenterforthearts.org/calendar-events/",
    "Grand Teton Music Festival": "https://gtmf.org/concerts/",
    "National Museum of Wildlife Art": "https://wildlifeart.org/calendar/",
    "Elkhart Lake Tourism":       "https://www.elkhartlake.com/events/",
    "Road America":               "https://www.roadamerica.com/events",
    "The Osthoff Resort":         "https://osthoff.com/events/",
    "Siebkens Resort":            "https://www.siebkens.com/events/",
    "Village of Elkhart Lake":    "https://elkhartlakewi.gov/calendar/",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# When the LLM count exceeds our count by this much, flag as regression.
# 2.0 = LLM saw twice as many events as we scraped.
REGRESSION_FACTOR = 2.0
# Minimum LLM count before we flag — avoids noisy alerts on small sources.
MIN_LLM_COUNT_TO_FLAG = 5


def _load_all_raw_events() -> list:
    """All events across raw files."""
    out = []
    for path in RAW_FILES:
        if not Path(path).exists():
            continue
        try:
            d = json.load(open(path))
            events = d.get("events", d) if isinstance(d, dict) else d
            out.extend(events)
        except Exception as ex:
            print(f"  warn: could not read {path}: {ex}", flush=True)
    return out


def count_events_per_source() -> dict[str, int]:
    """Count events per source across all raw files."""
    counts: Counter = Counter()
    for e in _load_all_raw_events():
        counts[e.get("source") or "UNKNOWN"] += 1
    return dict(counts)


# Venues whose events legitimately arrive under MULTIPLE source names (a
# hardcoded list + a tourism aggregator + a direct scrape all contribute). For
# these, an exact-source count badly undercounts and the LLM health check
# false-flags "missing events". Count by venue keyword across all sources.
_MULTI_SOURCE_VENUES = {
    "The Osthoff Resort": "osthoff",
    "Siebkens Resort": "siebken",
}


def venue_aware_count(source: str, all_events: list) -> int:
    """True count for a source. For known multi-source venues, count any event
    whose title/location/venue/source contains the venue keyword; otherwise
    fall back to exact source match."""
    kw = _MULTI_SOURCE_VENUES.get(source)
    if not kw:
        return sum(1 for e in all_events if (e.get("source") or "") == source)
    n = 0
    for e in all_events:
        blob = " ".join([
            e.get("source") or "", e.get("title") or "",
            e.get("location") or "", e.get("venue_name") or "",
        ]).lower()
        if kw in blob:
            n += 1
    return n


def fetch_page(url: str) -> str | None:
    """Fetch the source page as HTML."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


def ask_llm(source: str, our_count: int, html: str) -> dict:
    """Ask Claude to assess scraper health for one source."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    # Truncate HTML for cost control. The LLM only needs to see enough to count.
    # 50KB is usually plenty to see event listings.
    # Strip script/style tags first so the LLM sees content not noise
    import re as _re
    cleaned = _re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=_re.DOTALL | _re.IGNORECASE)
    cleaned = _re.sub(r"<style\b[^>]*>.*?</style>", "", cleaned, flags=_re.DOTALL | _re.IGNORECASE)
    cleaned = _re.sub(r"<!--.*?-->", "", cleaned, flags=_re.DOTALL)
    # Keep body if we can find it (drops head bloat)
    body_match = _re.search(r"<body[^>]*>(.*?)</body>", cleaned, flags=_re.DOTALL | _re.IGNORECASE)
    if body_match:
        cleaned = body_match.group(1)
    truncated = cleaned[:150000]

    prompt = f"""You are auditing a web scraper. Look at the page HTML below and judge whether our scraper is capturing all the events shown.

IMPORTANT: This is the raw HTML — JavaScript has NOT been executed. If the page renders events via JS, the HTML may show empty containers with no events. That is NOT a scraper bug — that is just how the static HTML looks. In that case, report page_status as "javascript_required" and judgment as "cannot_assess".

Source: {source}
Our scraper currently returns: {our_count} events for this source across our database (this is a cumulative count from many scrapes, may exceed today's visible events).

HTML (body only, scripts/styles stripped, truncated to 150KB):
{truncated}

Tasks:
1. Roughly how many distinct upcoming events does this page seem to list? Count event cards, titles, listings. Do not count past events. Give your best estimate as a single integer.
2. Does the page look healthy (lots of real events) or broken/empty/blocked (login wall, error, captcha, "no events")?
3. Is our count of {our_count} plausibly close to what the page shows? Note: our count is the database total across many runs, so it may exceed what's visible today (the page shows now-events only).

Respond ONLY with strict JSON, no prose, in this exact schema:
{{
  "llm_count_on_page": <integer>,
  "page_status": "healthy" | "empty" | "blocked" | "error" | "javascript_required",
  "judgment": "ok" | "scraper_likely_missing_events" | "scraper_count_seems_correct" | "page_broken" | "cannot_assess",
  "notes": "<one short sentence>"
}}"""

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip any code fences if Claude added them
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "llm_count_on_page": 0,
            "page_status": "error",
            "judgment": "page_broken",
            "notes": f"could not parse LLM response: {text[:120]}",
        }


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set, aborting", flush=True)
        sys.exit(1)

    print(f"Scraper LLM health check starting at {datetime.now(MOUNTAIN).isoformat()}", flush=True)
    counts = count_events_per_source()
    print(f"Found {len(counts)} sources in raw files", flush=True)
    all_events = _load_all_raw_events()  # for venue-aware counts (multi-source venues)

    results = []
    flagged = []
    for source, _raw_count in sorted(counts.items(), key=lambda x: -x[1]):
        # Venue-aware count: for venues whose events span multiple source names
        # (Osthoff, Siebkens), this gives the true total so the check doesn't
        # false-flag "missing". For all other sources it equals the raw count.
        our_count = venue_aware_count(source, all_events)
        url = SOURCE_URLS.get(source)
        if not url:
            results.append({
                "source": source,
                "our_count": our_count,
                "status": "skipped_no_url",
                "url": None,
            })
            continue

        print(f"  [{source}] {our_count} events; fetching {url}...", flush=True)
        html = fetch_page(url)
        if not html:
            results.append({
                "source": source,
                "our_count": our_count,
                "url": url,
                "status": "fetch_failed",
            })
            continue

        try:
            assessment = ask_llm(source, our_count, html)
        except Exception as ex:
            results.append({
                "source": source,
                "our_count": our_count,
                "url": url,
                "status": "llm_error",
                "error": str(ex),
            })
            continue

        llm_count = assessment.get("llm_count_on_page", 0)
        judgment = assessment.get("judgment", "ok")
        status = assessment.get("page_status", "unknown")

        record = {
            "source": source,
            "our_count": our_count,
            "url": url,
            "status": "checked",
            "llm_count_on_page": llm_count,
            "page_status": status,
            "judgment": judgment,
            "notes": assessment.get("notes", ""),
        }
        results.append(record)

        # Flag conditions:
        # - page reports healthy events but we have suspiciously few
        # - judgment explicitly says scraper missing events
        is_flagged = False
        if status == "healthy" and llm_count >= MIN_LLM_COUNT_TO_FLAG and our_count < (llm_count / REGRESSION_FACTOR):
            is_flagged = True
            record["flagged_reason"] = f"LLM sees ~{llm_count} events but our DB has {our_count}"
        elif (judgment == "scraper_likely_missing_events"
              and status not in ("javascript_required", "empty")
              and llm_count >= MIN_LLM_COUNT_TO_FLAG
              and our_count < llm_count):
            # Only trust the "missing events" judgment when the page genuinely
            # shows MORE than we have. When our_count >= llm_count we clearly
            # aren't missing the page's events (e.g. Osthoff: 78 in DB vs a
            # 12-event carousel) — the judgment string alone is not enough.
            is_flagged = True
            record["flagged_reason"] = f"LLM judgment: scraper likely missing events (LLM ~{llm_count} vs our {our_count})"
        elif status in ("blocked", "error"):
            is_flagged = True
            record["flagged_reason"] = f"Source page is {status}"

        if is_flagged:
            flagged.append(record)
            print(f"    FLAG: {record['flagged_reason']}", flush=True)
        else:
            print(f"    OK ({status}, LLM sees ~{llm_count})", flush=True)

    output = {
        "checked_at": datetime.now(MOUNTAIN).isoformat(),
        "total_sources": len(counts),
        "sources_checked": sum(1 for r in results if r.get("status") == "checked"),
        "sources_flagged": len(flagged),
        "results": results,
        "flagged": flagged,
    }

    out_path = Path("scraper_llm_health.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nWrote {out_path}: {len(flagged)} flagged source(s) of {output['sources_checked']} checked", flush=True)


if __name__ == "__main__":
    main()
