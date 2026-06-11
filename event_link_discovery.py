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


def _looks_like_event_url(u: str) -> bool:
    path = urlparse(u).path
    if not path or path.endswith("/events/") or path.endswith("/calendar/"):
        return False
    if _EVENT_URL_RE.search(path) or _DATE_IN_PATH_RE.search(path):
        # exclude obvious non-event paths
        if any(bad in path.lower() for bad in
               ("/tag/", "/category/", "/author/", "/page/", "/feed", ".xml",
                "/search", "/login", "/wp-")):
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
    """Find event URLs via sitemap. Recurses into sitemap indexes."""
    root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    candidates = [f"{root}/sitemap.xml", f"{root}/sitemap_index.xml"]
    # robots.txt may name sitemaps
    robots = _fetch(f"{root}/robots.txt")
    if robots:
        for m in re.findall(r"(?i)sitemap:\s*(\S+)", robots):
            candidates.append(m.strip())

    found, seen_sm, queue = set(), set(), list(dict.fromkeys(candidates))
    depth = 0
    while queue and depth < 50:
        sm = queue.pop(0)
        if sm in seen_sm:
            continue
        seen_sm.add(sm)
        depth += 1
        body = _fetch(sm)
        if not body:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I)
        if not locs:  # maybe a plain-text or HTML sitemap
            locs = re.findall(r"https?://[^\s<>\"']+", body)
        for u in locs:
            if u.lower().endswith(".xml") or "sitemap" in u.lower():
                queue.append(u)            # nested sitemap
            elif _looks_like_event_url(u):
                found.add(u)
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
        if urlparse(u).netloc == urlparse(page_url).netloc and _looks_like_event_url(u):
            found.add(u)
    if verbose and found:
        print(f"    link-crawl: {len(found)} event URLs")
    return found


def discover_event_urls(source_url, max_urls=300, verbose=True):
    """Return a list of individual event-page URLs for a source, via sitemap
    first then link-crawl. Capped at max_urls."""
    urls = _sitemap_urls(source_url, verbose=verbose)
    if len(urls) < 5:  # sitemap thin/absent -> also crawl the page
        urls |= _crawl_links(source_url, verbose=verbose)
    out = sorted(urls)[:max_urls]
    if verbose:
        print(f"    => {len(out)} event URLs discovered for {urlparse(source_url).netloc}")
    return out


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "https://www.visitparkcity.com/events/"
    urls = discover_event_urls(src)
    for u in urls[:30]:
        print(" ", u)
    print(f"\ntotal: {len(urls)}")
