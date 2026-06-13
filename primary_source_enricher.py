"""primary_source_enricher.py — the universal "get the real data" layer.

PURPOSE
-------
Aggregators (nowplayingutah via The Park Record, SerpApi/Google Events) give
BREADTH but unreliable DETAILS: wrong times, generic titles, truncated recurring
date lists. Primary sources (a chamber's own page, a venue's own site) give
CORRECT, structured details. This module takes any event that carries a
primary-source URL and replaces its weak fields with authoritative data pulled
from that page.

It generalizes the Heber enricher (which only handled gohebervalley.com) into a
city-agnostic cascade keyed off a small per-domain REGISTRY.

THE CASCADE (cheapest reliable signal first; only escalate on miss)
-------------------------------------------------------------------
  1. CACHE        — per-URL; trust only deterministic entries, re-fetch the rest.
  2. JSON-LD      — schema.org Event in the page (free, exact). Many CMS emit it.
  3. DETERMINISTIC— the "Starts <date list>" recurrence block (free, exact).
                    Reuses recurrence_parser.parse_occurrence_dates.
  4. DIRECT FETCH — plain requests with a real browser UA. Free. Works for most
                    sites from a residential IP.
  5. FIRECRAWL    — render + clean markdown for JS-walled / IP-blocking sites
                    (gohebervalley, dishingjh, jacksonhole all block datacenter
                    IPs). Paid (~$0.01-0.03/page) so only used when 4 fails.
  6. LLM EXTRACT  — Claude pulls structured fields from whatever text we got.
                    Paid (cheap, Haiku). Only when 2+3 found nothing.

COST CONTROL
------------
- Steps 2-4 are free; most pages resolve there.
- Firecrawl (5) fires only on direct-fetch failure (403 / JS shell / too-short).
- LLM (6) fires only when deterministic parsing found nothing.
- Deterministic results are cached permanently; LLM/empty results are re-tried
  each run so they self-heal but never poison the cache.
- A per-run Firecrawl budget cap prevents a bad run from spending unbounded.

REGISTRY
--------
Each entry says how to treat a domain. Adding a primary source = one dict entry,
no new scraper. `trust` is the SOURCE_PRIORITY hint the build can use; `extract`
chooses the cascade flavour.
"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path

try:
    from recurrence_parser import parse_occurrence_dates
except Exception:  # allow standalone testing without the module
    def parse_occurrence_dates(_text):
        return None

CACHE_PATH = Path(".cache/primary_source_enrichment.json")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
EXTRACT_MODEL = "claude-haiku-4-5-20251001"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Per-run Firecrawl spend cap (number of pages). Tune per budget.
FIRECRAWL_BUDGET = int(os.environ.get("FIRECRAWL_BUDGET", "300"))

# How long to trust an LLM-extracted result before re-fetching. Event details
# (lineups, times, prices) rarely change daily; weekly refresh keeps Firecrawl
# spend low while still self-healing. Override via env for testing.
LLM_CACHE_DAYS = int(os.environ.get("LLM_CACHE_DAYS", "7"))

# How long to remember a fetch failure before retrying (dead/blocking links).
FAIL_RETRY_DAYS = int(os.environ.get("FAIL_RETRY_DAYS", "3"))


# ---------------------------------------------------------------------------
# REGISTRY: domain -> how to treat it. One line per primary source.
#   trust:   priority hint (1 = primary/venue/chamber, 2 = trusted, 3 = default)
#   render:  "auto" (try direct, Firecrawl on fail) | "always" (JS-walled) | "never"
#   needs_js: hint that direct fetch returns a JS shell (force Firecrawl)
# ---------------------------------------------------------------------------
REGISTRY = {
    "gohebervalley.com":    {"trust": 1, "render": "auto"},
    "jacksonhole.com":      {"trust": 1, "render": "auto"},
    "dishingjh.com":        {"trust": 2, "render": "auto"},
    "visitparkcity.com":    {"trust": 1, "render": "auto"},
    "parkcityfilm.org":      {"trust": 1, "render": "auto"},
    "parkcity.org":         {"trust": 1, "render": "auto"},
    "elkhartlake.com":      {"trust": 1, "render": "auto"},
    "roadamerica.com":      {"trust": 1, "render": "auto"},
    "osthoff.com":          {"trust": 1, "render": "auto"},
    "siebkens.com":         {"trust": 1, "render": "auto"},
}

# Sources whose records are leads-only (details should be replaced from primary).
LOW_TRUST_SOURCES = {"The Park Record", "Google Events", "Eventbrite",
                     "Bandsintown", "EventTicketsCenter"}


def _registry_for(url: str):
    host = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    host = host.lstrip("www.")
    for dom, cfg in REGISTRY.items():
        if host == dom or host.endswith("." + dom):
            return cfg
    return None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except Exception:
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


# ---------------------------------------------------------------------------
# Fetch layers
# ---------------------------------------------------------------------------
def _direct_fetch(url, timeout=20):
    """Plain requests with a real UA. Returns raw HTML or None."""
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        if r.status_code != 200:
            return None
        html = r.text
        # Detect a JS shell (tiny body, no event text) — signal to escalate.
        if len(html) < 1500:
            return None
        return html
    except Exception:
        return None


def _firecrawl_fetch(url, timeout=60):
    """Firecrawl render -> markdown. Returns markdown text or None. Paid."""
    if not FIRECRAWL_KEY:
        return None
    import urllib.request
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=json.dumps({"url": url, "formats": ["markdown", "rawHtml"]}).encode(),
        headers={"Authorization": f"Bearer {FIRECRAWL_KEY}",
                 "Content-Type": "application/json"},
    )
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception as e:
        print(f"  [firecrawl] error: {str(e)[:100]}")
        return None
    if not r.get("success"):
        return None
    data = r.get("data", {}) or {}
    # Prefer rawHtml (lets JSON-LD + deterministic parsers run); fall back to md.
    return data.get("rawHtml") or data.get("markdown") or None


def _html_to_text(html):
    """Strip scripts/styles/nav/footer, collapse to plain text. No length cap."""
    h = html
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<nav.*?</nav>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<footer.*?</footer>", " ", h, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", h)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Extraction layers
# ---------------------------------------------------------------------------
def _extract_jsonld_events(html):
    """Pull schema.org Event objects from <script type=ld+json> blocks.

    Returns a dict of normalized fields (start_time, end_time, occurrence_dates,
    venue_name, street_address, price, is_free) or None. Free + exact."""
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I)
    events = []
    for b in blocks:
        b = b.strip()
        try:
            data = json.loads(b)
        except Exception:
            # some sites concatenate or wrap in @graph; try light salvage
            try:
                data = json.loads(re.sub(r",\s*}", "}", b))
            except Exception:
                continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data])
        for n in nodes if isinstance(nodes, list) else [nodes]:
            if not isinstance(n, dict):
                continue
            t = n.get("@type", "")
            t = t if isinstance(t, str) else (t[0] if isinstance(t, list) and t else "")
            if "Event" in (t or ""):
                events.append(n)
    if not events:
        return None

    def _time_of(iso):
        m = re.search(r"T(\d{2}):(\d{2})", iso or "")
        if not m:
            return None
        h, mn = int(m.group(1)), int(m.group(2))
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{mn:02d} {ap}"

    occ, start_time, end_time, venue, street, price, is_free = [], None, None, None, None, None, None
    for ev in events:
        sd = ev.get("startDate") or ""
        d = sd[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            occ.append(d)
            if start_time is None:
                start_time = _time_of(sd)
            if end_time is None:
                end_time = _time_of(ev.get("endDate") or "")
        loc = ev.get("location") or {}
        if isinstance(loc, dict):
            venue = venue or loc.get("name")
            addr = loc.get("address")
            if isinstance(addr, dict):
                street = street or addr.get("streetAddress")
            elif isinstance(addr, str):
                street = street or addr
        offers = ev.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                p = float(offers["price"])
                price = price if price is not None else (f"${p:.0f}" if p else "Free")
                if p == 0:
                    is_free = True
            except Exception:
                pass
    occ = sorted(set(occ))
    if not occ:
        return None
    return {
        "occurrence_dates": occ,
        "start_time": start_time,
        "end_time": end_time,
        "venue_name": venue,
        "street_address": street,
        "price": price,
        "is_free": is_free,
        "_via": "jsonld",
    }


def _llm_extract(text, title_hint, current_year, timeout=90):
    """Claude pulls canonical fields from page text. Paid (Haiku). Returns dict."""
    if not ANTHROPIC_KEY:
        return None
    import urllib.request
    md = text[:40000]
    prompt = (
        "From this event page, extract the canonical details for the MAIN event "
        f"titled similar to: \"{title_hint}\". Return ONLY a JSON object, no prose: "
        '{"start_time": "H:MM AM/PM or null", "end_time": "H:MM AM/PM or null", '
        '"venue_name": str or null, "street_address": str or null, '
        '"occurrence_dates": ["YYYY-MM-DD", ...] (all listed dates, [] if none), '
        '"recurrence_text": str or null, "price": str or null, '
        '"is_free": true/false/null}. '
        f"For undated/year-less dates assume {current_year} or later, never past. "
        f"\n\n--- PAGE ---\n{md}"
    )
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": EXTRACT_MODEL, "max_tokens": 1500,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
        txt = r.get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        print(f"  [llm] error: {str(e)[:100]}")
        return None
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            obj["_via"] = "llm"
            return obj
    except Exception:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                obj["_via"] = "llm"
                return obj
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# The cascade for a single URL
# ---------------------------------------------------------------------------
def _resolve_url(url, title_hint, cache, budget):
    """Run the cascade for one URL. Returns (fields_dict_or_None, status, budget)."""
    # 1. cache:
    #    - deterministic/jsonld: trusted permanently (structured, exact).
    #    - llm: trusted for LLM_CACHE_DAYS (event details rarely change daily;
    #      re-fetching every run is the main recurring Firecrawl cost). Re-fetch
    #      only once it goes stale, so it self-heals weekly instead of daily.
    cached = cache.get(url)
    if cached:
        st = cached.get("status")
        if st in ("deterministic", "jsonld"):
            return cached, "cache", budget
        if st == "llm":
            ts = cached.get("_cached_at", "")
            try:
                age = (date.today() - date.fromisoformat(ts[:10])).days
            except Exception:
                age = 999
            if age < LLM_CACHE_DAYS:
                return cached, "cache", budget
        if st in ("fetch_failed", "no_data"):
            # Don't retry a known failure every run (wastes budget). Re-check
            # after a few days in case the page comes back.
            ts = cached.get("_cached_at", "")
            try:
                age = (date.today() - date.fromisoformat(ts[:10])).days
            except Exception:
                age = 999
            if age < FAIL_RETRY_DAYS:
                return None, "cache", budget

    cfg = _registry_for(url) or {"render": "auto"}
    html = None

    # 4. direct fetch (free) unless registry forces render
    if cfg.get("render") != "always":
        html = _direct_fetch(url)

    # 5. firecrawl (paid) on miss / forced
    used_firecrawl = False
    if html is None and budget > 0 and (cfg.get("render") in ("auto", "always")):
        fc = _firecrawl_fetch(url)
        if fc:
            html = fc
            used_firecrawl = True
            budget -= 1

    if not html:
        cache[url] = {"status": "fetch_failed", "_cached_at": date.today().isoformat()}
        return None, "fetch_failed", budget

    # 2. JSON-LD (free, exact)
    jl = _extract_jsonld_events(html)
    if jl and jl.get("occurrence_dates"):
        rec = {**jl, "status": "jsonld"}
        cache[url] = rec
        return rec, "jsonld", budget

    # 3. deterministic "Starts <dates>" block (free, exact)
    text = _html_to_text(html)
    det = parse_occurrence_dates(text)
    if det and det.get("occurrence_dates"):
        rec = {
            "occurrence_dates": det["occurrence_dates"],
            "recurrence_text": det.get("recurrence_text"),
            "status": "deterministic",
            "_via": "deterministic",
        }
        cache[url] = rec
        return rec, "deterministic", budget

    # 6. LLM extract (paid, cheap) — last resort
    llm = _llm_extract(text, title_hint, date.today().year)
    if llm:
        rec = {**llm, "status": "llm", "_cached_at": date.today().isoformat()}
        cache[url] = rec  # cached with a TTL; re-fetched weekly, not daily
        return rec, "llm", budget

    cache[url] = {"status": "no_data", "_cached_at": date.today().isoformat()}
    return None, "no_data", budget


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def _apply_fields(e, fields):
    """Write authoritative fields onto an event. Times/venue/dates from a primary
    source OVERWRITE weak aggregator data; only fill price/address if missing.

    Date safety: occurrence_dates are filtered to today-or-future, and the
    event's start date is NEVER moved earlier than max(today, its current date).
    A primary page often lists past occurrences of a series; those must not drag
    the event backward into the past.
    """
    today = date.today().isoformat()
    occ = fields.get("occurrence_dates")
    if occ:
        future = [d for d in occ if d and d[:10] >= today]
        if future:
            e["occurrence_dates"] = future
            earliest = future[0]
            cur = e.get("date") or ""
            # only ADVANCE forward to the earliest future occurrence if the
            # current date is itself past/empty; never move earlier than today.
            if not cur or cur[:10] < today:
                e["date"] = earliest
        # if every listed occurrence is past, leave the event's dates untouched
    if fields.get("recurrence_text"):
        e["recurrence_text"] = fields["recurrence_text"]
    if fields.get("start_time"):
        e["start_time"] = fields["start_time"]      # overwrite: primary wins
    if fields.get("end_time"):
        e["end_time"] = fields["end_time"]
    if fields.get("venue_name") and not e.get("venue_name"):
        e["venue_name"] = fields["venue_name"]
    if fields.get("street_address") and not e.get("address"):
        e["address"] = fields["street_address"]
    if fields.get("price") and not e.get("price"):
        e["price"] = fields["price"]
    if fields.get("is_free") is not None and e.get("is_free") is None:
        e["is_free"] = fields["is_free"]


def enrich_primary_sources(events, verbose=True):
    """For every event whose link points at a known primary source, replace its
    weak fields with authoritative data from that page. Mutates + returns events.

    Aggregator records (LOW_TRUST_SOURCES) are NOT enriched here — they are leads;
    the build's source-priority handles preferring the primary record over them.
    """
    cache = _load_cache()
    budget = FIRECRAWL_BUDGET
    stats = {"cache": 0, "jsonld": 0, "deterministic": 0, "llm": 0,
             "fetch_failed": 0, "no_data": 0, "skipped": 0}

    # Group by URL so a series (N date-copies sharing one detail page) is fetched once.
    by_url = {}
    for e in events:
        url = (e.get("link") or "").rstrip("/")
        if not url or not _registry_for(url):
            stats["skipped"] += 1
            continue
        by_url.setdefault(url, []).append(e)

    for url, group in by_url.items():
        title_hint = (group[0].get("title") or "")[:80]
        fields, status, budget = _resolve_url(url, title_hint, cache, budget)
        stats[status] = stats.get(status, 0) + 1
        if fields:
            for e in group:
                _apply_fields(e, fields)

    _save_cache(cache)
    if verbose:
        print(f"  [primary-enrich] {len(by_url)} urls | "
              f"cache {stats['cache']} jsonld {stats['jsonld']} "
              f"det {stats['deterministic']} llm {stats['llm']} "
              f"fail {stats['fetch_failed']} none {stats['no_data']} | "
              f"firecrawl budget left {budget}")
    return events


if __name__ == "__main__":
    import sys
    # standalone smoke test on a single URL
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.gohebervalley.com/heber-city-park-saturday-music-series"
    title = sys.argv[2] if len(sys.argv) > 2 else "Saturday Sunset Music Series"
    cache = {}
    fields, status, _ = _resolve_url(url.rstrip("/"), title, cache, 5)
    print(f"status: {status}")
    if fields:
        print(json.dumps({k: v for k, v in fields.items() if k != "_via"}, indent=2)[:1200])
