"""Generic event extractor: any URL -> clean markdown (Firecrawl) -> structured
events (Anthropic API). The universal fallback for sites that block scraping or
render via JS, where sitemap/JSON-LD scraping fails. New source = one config
line, no custom scraper.

Pipeline: Firecrawl /scrape -> markdown -> Claude extracts events as JSON ->
normalize (dates, location, link) -> sanity-filter (parseable + future) -> yoocal events.
"""
import os, json, re, urllib.request
from datetime import datetime, date

FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
EXTRACT_MODEL = "claude-haiku-4-5-20251001"


def _firecrawl_markdown(url, timeout=60):
    """Fetch a URL via Firecrawl, return clean markdown (or None)."""
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=json.dumps({"url": url, "formats": ["markdown"]}).encode(),
        headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                 "Content-Type": "application/json"},
    )
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception as e:
        print(f"  [firecrawl] fetch error: {str(e)[:120]}")
        return None
    if not r.get("success"):
        print(f"  [firecrawl] not success: {str(r)[:120]}")
        return None
    return (r.get("data", {}) or {}).get("markdown", "") or ""


def _claude_extract(markdown, source_hint, current_year, timeout=90):
    """Ask Claude to pull structured events from markdown. Returns list of dicts."""
    # Strip nav chrome (link-only list items, month/day filter menus) so the
    # token budget is spent on real content, not navigation. Then cap higher.
    lines = markdown.split("\n")
    kept = []
    for ln in lines:
        s = ln.strip()
        # drop pure-navigation bullets: "- [Word](url)" with nothing else
        if re.match(r"^-?\s*\[[^\]]{1,20}\]\([^)]+\)\s*$", s):
            continue
        kept.append(ln)
    cleaned = "\n".join(kept)
    # Cap higher now that chrome is gone (event lists can be long)
    md = cleaned[:40000]
    prompt = (
        "Extract EVENTS from this web page content. Return ONLY a JSON array, no "
        "prose, no markdown fences. Each event: {\"title\": str, \"date\": "
        "\"YYYY-MM-DD\", \"end_date\": \"YYYY-MM-DD or null\", \"location\": str, "
        "\"url\": str or null}. Rules: ONLY real dated events (skip navigation, "
        "ads, recurring-but-undated activities, 'date TBA'). If a date has no "
        f"year, assume {current_year} or later (never past). Use 24h math; output "
        "ISO dates. If you cannot find a clear date for an event, OMIT it. If no "
        f"events, return []. Source context: {source_hint}\n\n--- PAGE ---\n{md}"
    )
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": EXTRACT_MODEL, "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
        txt = r.get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        print(f"  [extract] API error: {str(e)[:120]}")
        return []
    # Strip any accidental code fences
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(txt)
        return data if isinstance(data, list) else []
    except Exception:
        # try to salvage a JSON array substring
        m = re.search(r"\[.*\]", txt, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        print(f"  [extract] could not parse JSON ({len(txt)} chars)")
        return []


def _valid_iso(s):
    try:
        return date.fromisoformat((s or "")[:10]).isoformat()
    except Exception:
        return None


def extract_events_from_url(url, source_name, default_lat=None, default_lng=None,
                            default_city=None, default_categories=None,
                            page_param=None, max_pages=1):
    """Firecrawl-fetch + Claude-extract events from any URL -> yoocal events.

    Pagination: when page_param is set and max_pages > 1, fetch successive pages
    by appending ?{page_param}={n} for n = 1..max_pages, merging and de-duping by
    (title, date). Stops early the first time a page adds no NEW events (end of
    list), so max_pages is a safe upper bound, not a fixed Firecrawl cost.
    """
    today = date.today()
    if page_param and max_pages > 1:
        sep = "&" if "?" in url else "?"
        page_urls = [f"{url}{sep}{page_param}={n}" for n in range(1, max_pages + 1)]
    else:
        page_urls = [url]
    out, seen = [], set()
    for i, page_url in enumerate(page_urls):
        md = _firecrawl_markdown(page_url)
        if not md:
            if i == 0:
                print(f"  [{source_name}] no markdown")
            break
        raw = _claude_extract(md, source_name, today.year)
        added = 0
        for e in raw:
            if not isinstance(e, dict):
                continue
            start = _valid_iso(e.get("date"))
            if not start or start < today.isoformat():
                continue  # sanity: must parse + be future
            title = (e.get("title") or "").strip()
            if not title or len(title) < 3:
                continue
            key = (title.lower(), start)
            if key in seen:
                continue  # cross-page (or in-page) duplicate
            seen.add(key)
            end = _valid_iso(e.get("end_date")) or start
            out.append({
                "title": title,
                "date": start,
                "end_date": end,
                "location": (e.get("location") or default_city or "").strip(),
                "venue_name": "",
                "link": (e.get("url") or page_url),
                "source": source_name,
                "source_url": page_url,
                "lat": default_lat or 0,
                "lng": default_lng or 0,
                "city": default_city or "",
                "categories": default_categories or [],
            })
            added += 1
        # End of pagination: a later page that contributed nothing new.
        if i > 0 and added == 0:
            break
    print(f"  [{source_name}] {len(out)} events (firecrawl+extract, {len(page_urls)} page(s) max)")
    return out


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.runningintheusa.com/race/list/within-25-miles-of-jackson%20hole-wy/upcoming"
    evs = extract_events_from_url(url, "TEST", default_city="Jackson, WY",
                                  default_categories=["Running & Races"])
    print(f"\n=== {len(evs)} events ===")
    for e in evs[:20]:
        print(f"  {e['date']} -> {e['end_date']} | {e['title'][:42]:42} | {e['location'][:25]}")
