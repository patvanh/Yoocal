"""event_link_discovery.py — given a source URL, find ALL its individual event
page URLs using only general web techniques. No per-site config.

Why: a single events/calendar page shows only the first N events. Rich sources
(tourism boards, venues) keep each event on its own URL, listed in a sitemap or
linked from the calendar. To get *all* events (not just page one), discover those
URLs first, then extract each.

TECHNIQUES (all generic, work on any site):
  1. SITEMAP    — try /sitemap.xml, /sitemap_index.xml, and robots.txt's Sitemap:
                  line. Parse (recursing into nested sitemaps), keep URLs whose
                  path looks like an individual event.
  2. LINK CRAWL — fetch the given page, extract <a href> links whose URL path
                  looks like an event (/event/<slug>, /events/<slug>, a date in
                  the path, etc.). Catches sites without a usable sitemap.
  3. (caller then extracts each discovered URL with the existing cascade.)

Fetching uses direct requests first, Firecrawl fallback (handles IP-blocking /
JS), mirroring the extractor's cascade. Returns a de-duped, capped list of URLs.
"""
from __future__ import annotations
import json
import os
import re
from urllib.parse import urljoin, urlparse

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY")

# A URL path looks like an individual event if it has an event segment followed
# by a slug, or contains a date. Tuned to avoid matching the list page itself.
_EVENT_URL_RE = re.compile(
    r"/(events?|e|calendar|happening|festival|concert|show)s?/"
    r"[a-z0-9][a-z0-9\-_/]{3,}",   # a real slug after the segment, not just /events/
    re.I,
)
_DATE_IN_PATH_RE = re.compile(r"/20\d{2}[-/]\d{1,2}[-/]\d{1,2}")


_SOCIAL_DOMAINS = ("facebook.com", "twitter.com", "x.com", "instagram.com",
                   "linkedin.com", "pinterest.com", "youtube.com", "t.co",
                   "reddit.com", "sharer", "/share")
import datetime as _dt
_OLD_YEAR_CUT = _dt.date.today().year - 1  # reject article URLs dated before last year


def _looks_like_event_url(u: str, base_netloc: str = None) -> bool:
    parsed = urlparse(u)
    path = parsed.path
    # reject off-domain links (share buttons, external embeds) — only same-site
    if base_netloc and parsed.netloc and parsed.netloc.replace("www.", "") != base_netloc.replace("www.", ""):
        return False
    # reject social/share URLs outright
    low = u.lower()
    if any(s in low for s in _SOCIAL_DOMAINS):
        return False
    if not path or path.endswith("/events/") or path.endswith("/calendar/"):
        return False
    # reject clearly-old dated URLs (news archives: /2009/11/10/...). A date in
    # the path older than last year is an archived article, not an upcoming event.
    ym = re.search(r"/(20\d{2})/(\d{1,2})/", path)
    if ym and int(ym.group(1)) < _OLD_YEAR_CUT:
        return False
    if _EVENT_URL_RE.search(path) or _DATE_IN_PATH_RE.search(path):
        if any(bad in path.lower() for bad in
               ("/tag/", "/category/", "/author/", "/page/", "/feed", ".xml",
                "/search", "/login", "/wp-", "/sharer")):
            return False
        return True
    return False


def _fetch(url, timeout=20, want="text"):
    """Direct fetch; Firecrawl fallback on failure. Returns text or None."""
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 200:
            return r.text
    except Exception:
        pass
    # Firecrawl fallback (rawHtml so we can parse links / sitemap XML)
    if FIRECRAWL_KEY:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.firecrawl.dev/v1/scrape",
                data=json.dumps({"url": url, "formats": ["rawHtml"]}).encode(),
                headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                         "Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=60))
            return (r.get("data", {}) or {}).get("rawHtml") or None
        except Exception:
            return None
    return None


def _sitemap_urls(base, verbose=True):
    """Find event URLs via sitemap. Recurses into sitemap indexes. Returns a
    dict {url: lastmod_or_empty} so callers can sort by recency rather than
    alphabetically (alphabetical first-N on a huge sitemap returns permalink
    dupes, not current events)."""
    root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    candidates = [f"{root}/sitemap.xml", f"{root}/sitemap_index.xml"]
    robots = _fetch(f"{root}/robots.txt")
    if robots:
        for m in re.findall(r"(?i)sitemap:\s*(\S+)", robots):
            candidates.append(m.strip())

    base_netloc = urlparse(base).netloc
    found, seen_sm, queue = {}, set(), list(dict.fromkeys(candidates))
    depth = 0
    while queue and depth < 60:
        sm = queue.pop(0)
        if sm in seen_sm:
            continue
        seen_sm.add(sm)
        depth += 1
        body = _fetch(sm)
        if not body:
            continue
        # parse <url><loc>..</loc><lastmod>..</lastmod></url> blocks to keep dates
        blocks = re.findall(r"<(?:url|sitemap)>(.*?)</(?:url|sitemap)>", body, re.S | re.I)
        if blocks:
            for b in blocks:
                loc_m = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", b, re.I)
                if not loc_m:
                    continue
                u = loc_m.group(1)
                lm = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", b, re.I)
                lastmod = lm.group(1) if lm else ""
                if u.lower().endswith(".xml") or "sitemap" in u.lower():
                    queue.append(u)
                elif _looks_like_event_url(u, base_netloc):
                    found[u] = lastmod
        else:
            # plain-text / HTML sitemap: just URLs, no dates
            for u in re.findall(r"https?://[^\s<>\"']+", body):
                if u.lower().endswith(".xml") or "sitemap" in u.lower():
                    queue.append(u)
                elif _looks_like_event_url(u, base_netloc):
                    found.setdefault(u, "")
    if verbose and found:
        print(f"    sitemap: {len(found)} event URLs")
    return found


def _crawl_links(page_url, verbose=True):
    """Fallback: extract event-looking links from the page itself."""
    html = _fetch(page_url)
    if not html:
        return set()
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    found = set()
    for h in hrefs:
        u = urljoin(page_url, h)
        if _looks_like_event_url(u, urlparse(page_url).netloc):
            found.add(u)
    if verbose and found:
        print(f"    link-crawl: {len(found)} event URLs")
    return found


def _dedup_permalink_variants(urls):
    """Collapse near-duplicate permalink variants that differ only by a trailing
    -N (e.g. /show/foo-2/, /show/foo-3/ ... are the same event re-published).
    Keeps the base slug once. Generic — helps any WordPress-style site whose
    sitemap accumulates numbered duplicates."""
    by_base = {}
    for u in urls:
        base = re.sub(r"-\d+/?$", "", u.rstrip("/"))
        # keep the shortest (usually the canonical) URL for each base slug
        if base not in by_base or len(u) < len(by_base[base]):
            by_base[base] = u
    return list(by_base.values())


import re as _re_cm
from datetime import date as _date_cm

def _is_chambermaster(url, html=None):
    """ChamberMaster/GrowthZone signature: chambermaster.com host/assets,
    growthzone, or the /events/calendar URL pattern these sites use."""
    u = (url or "").lower()
    if "chambermaster.com" in u:
        return True
    if "/events/calendar" in u or "/events/details/" in u:
        return True
    if html and ("chambermaster.com" in html.lower() or "growthzone" in html.lower()):
        return True
    return False

def _chambermaster_month_urls(source_url, months_ahead=8, verbose=True):
    """Walk a ChamberMaster calendar forward month-by-month, collecting every
    /events/details/<slug>-<id> link. These sites paginate one month per page at
    {base}/events/calendar/YYYY-MM-01. ~8 cheap HTML fetches enumerate the whole
    season (no per-URL firecrawl needed — links are in the HTML). Bounded: stops
    after 2 consecutive empty months."""
    from urllib.parse import urlparse as _up
    pr = _up(source_url)
    base = f"{pr.scheme}://{pr.netloc}"
    detail_re = _re_cm.compile(r'(?:https?://[^"/]+)?(/events/details/[^"#?\s]+)', _re_cm.I)
    found, seen = [], set()
    today = _date_cm.today()
    y, m = today.year, today.month
    empty_streak = 0
    for i in range(months_ahead + 1):
        mm = (m - 1 + i) % 12 + 1
        yy = y + (m - 1 + i) // 12
        month_url = f"{base}/events/calendar/{yy:04d}-{mm:02d}-01"
        html = _fetch(month_url, want="text")
        if not html:
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        n_before = len(found)
        for mch in detail_re.finditer(html):
            path = mch.group(1).split("?")[0]  # strip ?calendarMonth=... dup param
            full = base + path
            if full not in seen:
                seen.add(full)
                found.append(full)
        if len(found) == n_before:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0
    if verbose:
        print(f"    chambermaster: walked {i+1} months -> {len(found)} event URLs")
    return found


def discover_event_urls(source_url, max_urls=300, verbose=True):
    """Return individual event-page URLs for a source.

    Strategy (all generic, no per-site code):
      1. crawl the listing page itself — its links are the CURRENT events.
      2. read the sitemap, keeping lastmod dates.
      3. dedup permalink variants (-2,-3.. suffixes).
      4. rank by recency (lastmod desc) so a huge sitemap yields recently-updated
         (i.e. upcoming) events, NOT the alphabetical-first chunk.
    Listing-page links are prioritized since they reflect what's live now."""
    # ChamberMaster/GrowthZone: month-walk is the authoritative enumeration
    # (the generic sitemap/crawl only catches the first month). Try it first;
    # if it yields events, those ARE the complete set. (chambermaster month-walk)
    if _is_chambermaster(source_url):
        cm_urls = _chambermaster_month_urls(source_url, verbose=verbose)
        if len(cm_urls) >= 10:
            return _dedup_permalink_variants(cm_urls)[:max_urls]

    sitemap = _sitemap_urls(source_url, verbose=verbose)          # {url: lastmod}
    crawl = _crawl_links(source_url, verbose=verbose)             # set
    # also crawl a few common listing paths generically
    root = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"
    for path in ("/events/", "/shows/", "/calendar/", "/event/", "/whats-on/"):
        if len(crawl) < 20:
            crawl |= _crawl_links(root + path, verbose=False)

    # listing-page links first (current), then sitemap by recency
    ranked = []
    seen = set()
    for u in crawl:                         # current/live events first
        if u not in seen:
            seen.add(u); ranked.append(u)
    # sitemap URLs sorted by lastmod descending (recent first); blanks last
    sm_sorted = sorted(sitemap.items(), key=lambda kv: kv[1] or "", reverse=True)
    for u, _lm in sm_sorted:
        if u not in seen:
            seen.add(u); ranked.append(u)

    ranked = _dedup_permalink_variants(ranked)
    out = ranked[:max_urls]
    if verbose:
        print(f"    => {len(out)} event URLs for {urlparse(source_url).netloc} "
              f"(crawl {len(crawl)}, sitemap {len(sitemap)}, after dedup {len(ranked)})")
    return out


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "https://www.visitparkcity.com/events/"
    urls = discover_event_urls(src)
    for u in urls[:30]:
        print(" ", u)
    print(f"\ntotal: {len(urls)}")
