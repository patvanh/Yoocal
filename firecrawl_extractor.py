"""Generic event extractor: any URL -> clean markdown (Firecrawl) -> structured
events (Anthropic API). The universal fallback for sites that block scraping or
render via JS, where sitemap/JSON-LD scraping fails. New source = one config
line, no custom scraper.

Pipeline: Firecrawl /scrape -> markdown -> Claude extracts events as JSON ->
normalize (dates, location, link) -> sanity-filter (parseable + future) -> yoocal events.
"""
import os, json, re, urllib.request, urllib.error
from datetime import datetime, date

FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
EXTRACT_MODEL = "claude-haiku-4-5-20251001"


def _firecrawl_markdown(url, timeout=60, proxy=None, retries=2):
    """Fetch a URL via Firecrawl, return clean markdown (or None).
    proxy='enhanced' uses the stronger anti-bot backend (+credits when invoked),
    for heavy-JS / widget / bot-protected pages the basic render returns empty.

    Retries on transient errors (5xx, timeouts) with backoff — these are server
    hiccups that succeed on a second try. Does NOT retry permanent errors (4xx
    like 404), which won't change."""
    import time
    body = {"url": url, "formats": ["markdown"]}
    if proxy:
        body["proxy"] = proxy
        body["waitFor"] = 6000  # give widget calendars time to populate
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            "https://api.firecrawl.dev/v1/scrape",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                     "Content-Type": "application/json"},
        )
        try:
            r = json.load(urllib.request.urlopen(req, timeout=timeout))
            if not r.get("success"):
                print(f"  [firecrawl] not success: {str(r)[:120]}")
                return None
            return (r.get("data", {}) or {}).get("markdown", "") or ""
        except urllib.error.HTTPError as e:
            last_err = e
            # 4xx = permanent (bad URL, auth) -> don't retry
            if 400 <= e.code < 500:
                print(f"  [firecrawl] fetch error: {str(e)[:120]}")
                return None
            # 5xx = transient -> retry with backoff
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
        except Exception as e:
            # timeouts / connection errors -> transient, retry
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
    print(f"  [firecrawl] fetch error after {retries+1} tries: {str(last_err)[:100]}")
    return None


def _firecrawl_rawhtml(url, timeout=60, proxy="enhanced", retries=2):
    """Fetch a URL via Firecrawl and return RAW HTML (or None).

    Same as _firecrawl_markdown but requests the rawHtml format — needed for
    scrapers that parse embedded JSON / specific markup the markdown conversion
    would strip (e.g. gohebervalley's earthdiver JSON blob). Defaults to the
    'enhanced' anti-bot proxy because this path exists specifically to get past
    Cloudflare challenges that block our datacenter/CI IP."""
    import time
    body = {"url": url, "formats": ["rawHtml"]}
    if proxy:
        body["proxy"] = proxy
        body["waitFor"] = 6000
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            "https://api.firecrawl.dev/v1/scrape",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                     "Content-Type": "application/json"},
        )
        try:
            r = json.load(urllib.request.urlopen(req, timeout=timeout))
            if not r.get("success"):
                print(f"  [firecrawl-raw] not success: {str(r)[:120]}")
                return None
            data = r.get("data", {}) or {}
            return data.get("rawHtml") or data.get("html") or ""
        except urllib.error.HTTPError as e:
            last_err = e
            if 400 <= e.code < 500:
                print(f"  [firecrawl-raw] fetch error: {str(e)[:120]}")
                return None
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
    print(f"  [firecrawl-raw] fetch error after {retries+1} tries: {str(last_err)[:100]}")
    return None


# --- Canonical page fetch with automatic Cloudflare fallback -----------------
# ONE place every scraper should fetch through. Tries a normal direct request
# first (free, works from residential IPs). If that comes back blocked — a
# Cloudflare/bot challenge, which arrives as HTTP 200 + a tiny interstitial page
# so status-code retries never catch it — it transparently refetches through
# Firecrawl's enhanced anti-bot proxy and returns the real rendered HTML.
#
# Scrapers pass an optional `marker`: a substring that MUST appear in a good
# response (e.g. the embedded-JSON key a parser needs, or '<urlset' for a
# sitemap). If the marker is given and absent from the direct fetch, that counts
# as blocked too — this catches silent blocks that don't show obvious challenge
# text. Returns the HTML string, or None if both paths fail.
import requests as _rq

_CHALLENGE_MARKERS = (
    "just a moment", "checking your browser", "cf-challenge", "cf_chl",
    "attention required", "enable javascript and cookies",
)

def _looks_blocked(html, marker=None):
    if not html:
        return True
    low = html.lower()
    if any(t in low for t in _CHALLENGE_MARKERS) and len(html) < 5000:
        return True
    if marker and marker not in html:
        return True
    return False

def fetch_html(url, marker=None, timeout=30, headers=None):
    """Fetch a page, transparently falling back to Firecrawl when blocked.

    url     : page to fetch
    marker  : optional substring that must be present in a valid response;
              if absent, the direct fetch is treated as blocked and Firecrawl
              is tried (covers silent Cloudflare blocks with no challenge text).
    Returns the HTML string or None.
    """
    hdrs = headers or {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    direct = None
    try:
        r = _rq.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            direct = r.text
    except Exception as e:
        print(f"  [fetch_html] direct fetch error {url[:60]}: {str(e)[:80]}")

    if direct is not None and not _looks_blocked(direct, marker):
        return direct  # direct fetch good — no firecrawl cost

    # Blocked (challenge page, missing marker, or direct failed) -> Firecrawl.
    print(f"  [fetch_html] direct blocked/insufficient for {url[:60]} -> Firecrawl")
    fc = _firecrawl_rawhtml(url, timeout=max(timeout, 60))
    if fc and not _looks_blocked(fc, marker):
        print(f"  [fetch_html] Firecrawl recovered {url[:60]} ({len(fc)} bytes)")
        return fc
    print(f"  [fetch_html] BLOCKED: both direct and Firecrawl failed for {url[:60]}")
    return direct  # return whatever we got (may be None) so caller can decide


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
        "\"YYYY-MM-DD\", \"end_date\": \"YYYY-MM-DD or null\", \"start_time\": "
        "\"H:MM AM/PM or null\", \"end_time\": \"H:MM AM/PM or null\", "
        "\"location\": str, \"url\": str or null}. Rules: ONLY real dated events "
        "(skip navigation, ads, recurring-but-undated activities, 'date TBA'). "
        "Capture the start time (and end time if shown) exactly as written, e.g. "
        "'7:00 PM'. If a date has no year, assume "
        f"{current_year} or later (never past). Use 24h math; output "
        "ISO dates. If you cannot find a clear date for an event, OMIT it. If no "
        f"events, return []. Source context: {source_hint}\n\n--- PAGE ---\n{md}"
    )
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": EXTRACT_MODEL, "max_tokens": 8000,
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
        pass
    # Salvage 1: a clean array substring
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # Salvage 2: response was TRUNCATED mid-array (ran out of tokens). Keep every
    # complete {...} object and close the array ourselves.
    objs = re.findall(r"\{[^{}]*\}", txt, re.DOTALL)
    if objs:
        try:
            data = json.loads("[" + ",".join(objs) + "]")
            print(f"  [extract] salvaged {len(data)} events from truncated JSON")
            return data if isinstance(data, list) else []
        except Exception:
            pass
    print(f"  [extract] could not parse JSON ({len(txt)} chars)")
    return []


def _valid_iso(s):
    try:
        return date.fromisoformat((s or "")[:10]).isoformat()
    except Exception:
        return None


def extract_via_playwright(url, source_name, default_lat=None, default_lng=None,
                           default_city=None, default_categories=None,
                           wait_selector=None):
    """Final-rung extractor: render the page with a real headless browser
    (executes JS the way Firecrawl can't for some widget calendars), convert to
    text, and run the same Claude extraction. Returns events or []."""
    try:
        from playwright_render import render_with_playwright
    except Exception:
        return []
    html = render_with_playwright(url, wait_selector=wait_selector, verbose=True)
    if not html:
        return []
    # crude HTML -> text so the LLM sees clean content
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) < 200:
        return []
    today = date.today()
    raw = _claude_extract(text[:50000], source_name, today.year)
    out, seen = [], set()
    for e in raw:
        if not isinstance(e, dict):
            continue
        start = _valid_iso(e.get("date"))
        if not start or start < today.isoformat():
            continue
        title = (e.get("title") or "").strip()
        if not title or len(title) < 3:
            continue
        key = (title.lower(), start)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title, "date": start,
            "end_date": _valid_iso(e.get("end_date")) or start,
            "location": (e.get("location") or default_city or "").strip(),
            "venue_name": "", "link": (e.get("url") or url),
            "start_time": (e.get("start_time") or "").strip() or None,
            "end_time": (e.get("end_time") or "").strip() or None,
            "source": source_name, "source_url": url,
            "lat": default_lat or 0, "lng": default_lng or 0,
            "city": default_city or "", "categories": default_categories or [],
        })
    print(f"  [{source_name}] {len(out)} events (playwright+extract)")
    return out


def extract_events_from_url(url, source_name, default_lat=None, default_lng=None,
                            default_city=None, default_categories=None,
                            page_param=None, max_pages=1, proxy=None):
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
        md = _firecrawl_markdown(page_url, proxy=proxy)
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
                "start_time": (e.get("start_time") or "").strip() or None,
                "end_time": (e.get("end_time") or "").strip() or None,
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
