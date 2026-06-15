"""generic_city_scraper.py — the universal "any city" event scraper.

THE VISION
----------
Point it at a city. It discovers that city's event sources (via the existing
discover_sources.py), extracts events from each source using whatever method
works best (schema.org/JSON-LD → Firecrawl+LLM cascade), normalizes to Yoocal
format, and stages them for review (later: auto-push).

No per-source hand-coding. New city = run this with a city name + center
coordinates; it figures out the rest.

PIPELINE
--------
  1. DISCOVER   — discover_sources.py finds candidate sources + detects tech.
                  (Or read an existing pending_sources.json run.)
  2. EXTRACT    — for each source, route by detected tech to the best extractor:
                    schema-org-event / data-attributes / fullcalendar
                        → scrape_schema_org_events (free, structured)
                    everything else / JS-walled / unknown
                        → extract_events_from_url (Firecrawl render + Claude)
                  First method that yields events wins; cascade down on empty.
  3. NORMALIZE  — stamp city, coords, source, default category; geo-filter to
                  the city radius; drop past-dated and dateless events.
  4. STAGE      — write to review_queue/<city>.json for human approval.
                  (Flip STAGE_MODE = "push" later to write straight to
                  public/raw/events-<city>.json instead.)

This module is standalone and side-effect-free until you run it. It never
touches live data; it only writes to review_queue/.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

# Reuse existing, proven extractors.
try:
    from schema_org_scraper import scrape_schema_org_events
except Exception:
    scrape_schema_org_events = None
try:
    from firecrawl_extractor import extract_events_from_url
except Exception:
    extract_events_from_url = None

REVIEW_DIR = Path("review_queue")
STAGE_MODE = os.environ.get("STAGE_MODE", "review")  # "review" | "push"

# Hard cap on event-detail fetches per run (cache hits don't count). Protects
# against a runaway full crawl. Override via env for big first-fill runs.
FIRECRAWL_BUDGET = int(os.environ.get("SCRAPER_FIRECRAWL_BUDGET", "1500"))
_budget_spent = 0

# Hard ceiling per source (seconds). A single stuck render must never hang an
# unattended run. Override with SCRAPER_SOURCE_TIMEOUT. 6 min is generous —
# even a slow source with crawl + render + api-capture finishes well under it.
SOURCE_TIMEOUT_S = int(os.environ.get("SCRAPER_SOURCE_TIMEOUT", "360"))

# Business types that embed others' calendars rather than hosting their own
# events (realtors, lodging, rentals). Skipped at scrape time so existing source
# lists don't pull them in. Mirrors discover_sources.EXCLUDE_DOMAIN_KEYWORDS.
_NON_EVENT_BIZ_KEYWORDS = (
    "realestate", "realtor", "realty", "homes", "properties", "property",
    "remax", "kellerwilliams", "sothebys", "coldwellbanker", "redfin",
    "zillow", "trulia", "vacationrental", "propertymanagement", "forsale",
    # Statewide/regional tourism aggregators — list events across an entire
    # state, so they're mostly geo-noise for one town (travelwisconsin returned
    # 252 events, 206 dropped as out-of-area) and expensive to deep-crawl.
    "travelwisconsin", "travelutah", "visitutah", "wisconsin.gov",
    "travel.wisconsin", "industry.travelwisconsin",
)

import signal as _signal
from contextlib import contextmanager


class _SourceTimeout(Exception):
    pass


@contextmanager
def _source_timeout(seconds):
    """Raise _SourceTimeout if the wrapped block exceeds `seconds`. Uses SIGALRM
    (main thread only; the scraper runs single-threaded so this is fine). On
    platforms without SIGALRM it becomes a no-op so the run still proceeds."""
    if not hasattr(_signal, "SIGALRM"):
        yield
        return

    def _handler(signum, frame):
        raise _SourceTimeout()

    old = _signal.signal(_signal.SIGALRM, _handler)
    _signal.alarm(int(seconds))
    try:
        yield
    finally:
        _signal.alarm(0)
        _signal.signal(_signal.SIGALRM, old)

# Tech types (from discover_sources.py) that scrape_schema_org_events handles well.
SCHEMA_TECHS = {"schema-org-event", "data-attributes", "fullcalendar",
                "wordpress-tribe", "events-list-class"}


def _domain(url):
    return urlparse(url).netloc.replace("www.", "")


# ---------------------------------------------------------------------------
# Extraction: route a source to the best method, cascade on empty
# ---------------------------------------------------------------------------
def extract_source(url, tech_types, city, lat, lng, categories=None, verbose=True,
                   deep=True, max_event_urls=40):
    """Extract events from one source.

    deep=True: first discover all individual event-page URLs (generic sitemap /
    link-crawl), then extract each (schema.org free-path first, Firecrawl on
    miss). This is what pulls the FULL catalog from rich sources (e.g. VPC's 144
    events) instead of just the first list page. Falls back to single-page
    extraction when no event URLs are discovered."""
    source_name = _domain(url)
    widget_events = []  # events from rendering a JS calendar page (if any)

    # ChamberMaster/GrowthZone sources are authoritative LOCAL calendars that
    # legitimately list ~200 events via month-pagination. The default low cap
    # (which exists to stop statewide-aggregator cost bombs) would truncate them,
    # so raise it here. Locality is the distinction: cap statewide noise hard,
    # let a local chamber run full. (chambermaster cap)
    _tt = " ".join(tech_types or []) if isinstance(tech_types, (list, tuple)) else str(tech_types or "")
    if "chambermaster" in _tt.lower() or "/events/calendar" in url.lower():
        max_event_urls = max(max_event_urls, 250)

    # 1. DEEP: discover individual event URLs and extract each. We do this FIRST
    #    (it's mostly cached/cheap), then only fall back to a Playwright widget
    #    render if the crawl came up thin — that avoids paying a ~15s browser
    #    probe on every source, which is what made full runs take ~48 min.
    crawl_events = []
    if deep:
        try:
            from event_link_discovery import discover_event_urls
            event_urls = discover_event_urls(url, max_urls=max_event_urls, verbose=verbose)
        except Exception as ex:
            if verbose:
                print(f"    link-discovery error: {str(ex)[:80]}")
            event_urls = []
        # Giant-sitemap guard: a source offering far more event URLs than a
        # single town could plausibly have is a statewide/regional aggregator
        # (e.g. travelwisconsin.com returned 4600). Deep-crawling it costs
        # hundreds of paid renders for events that mostly geo-fail. Skip the
        # per-URL deep crawl; the calendar-page render below still runs.
        _DEEP_URL_HARD_CAP = 60
        # EXEMPT chambermaster: a local chamber legitimately has hundreds of real
        # event URLs via month-pagination — that's authoritative local data, not
        # an aggregator. The guard is only meant to catch statewide aggregators
        # like travelwisconsin (4600 URLs, non-chambermaster).
        _is_cm = ("chambermaster" in _tt.lower() or "/events/calendar" in url.lower())
        if len(event_urls) > _DEEP_URL_HARD_CAP and not _is_cm:
            if verbose:
                print(f"    deep: {len(event_urls)} urls exceeds cap "
                      f"({_DEEP_URL_HARD_CAP}) — likely a regional aggregator; "
                      f"skipping per-URL deep crawl (calendar render still runs)")
            event_urls = []
        if event_urls:
            try:
                import event_cache as ec
                cache = ec.load()
            except Exception:
                ec, cache = None, {}
            out, seen = [], set()
            n_cached = n_fetched = 0
            for eu in event_urls:
                if ec and ec.is_fresh(cache, eu):
                    evs = ec.get_events(cache, eu)
                    n_cached += 1
                else:
                    if _budget_spent >= FIRECRAWL_BUDGET:
                        if verbose:
                            print(f"    budget cap hit ({FIRECRAWL_BUDGET}); skipping rest")
                        break
                    evs = _extract_one(eu, source_name, city, lat, lng, categories,
                                       verbose=verbose, allow_playwright=False)
                    n_fetched += 1
                    if ec:
                        ec.put(cache, eu, evs)
                for e in evs:
                    k = ((e.get("title") or "").strip().lower(), (e.get("date") or "")[:10])
                    if k not in seen:
                        seen.add(k)
                        out.append(e)
            if ec:
                ec.save(cache)
            crawl_events = out
            if verbose:
                print(f"    deep: {len(event_urls)} urls "
                      f"({n_cached} cached, {n_fetched} fetched) -> {len(out)} events")

    # 2. CALENDAR-PAGE RENDER — always render the source's calendar page with a
    #    real browser ONCE and union those events in. No crawl-count gate (that
    #    broke Park Record: 19 mediocre article-events suppressed the 72 real
    #    calendar events). Doing both + union is robust: rich-crawl sources
    #    (Mountain Town Music) keep their full crawl; widget sources (Park Record)
    #    get their calendar events; neither suppresses the other. One render per
    #    source, so runtime stays ~one browser load per source.
    if deep:
        widget_events = _render_calendar_page(
            url, source_name, city, lat, lng, categories, verbose=verbose)

    # 2.5 EVENT-API CAPTURE — many JS calendars fetch events from an internal
    #     JSON API that is FAR more complete than the sitemap (VPC: 129 recurring
    #     definitions via API vs 148 flat URLs via sitemap, and the API carries
    #     recurrence rules we expand into the full dated calendar). General: we
    #     detect the API by request shape during a render, replay it with limits
    #     widened, then expand recurrences. One capture per domain per run.
    #
    #     GATE: only attempt this when the calendar render actually produced
    #     events — that's the signal the source HAS a JS calendar backed by an
    #     API. Static lodge/info sites that render 0 events have no API to find,
    #     so we skip the extra browser load and keep full runs fast.
    api_events = []
    if deep and widget_events:
        api_events = _capture_api_events(
            url, source_name, city, lat, lng, categories, verbose=verbose)

    # 3. UNION crawl + widget + api, dedup
    if crawl_events or widget_events or api_events:
        merged, seen = [], set()
        for e in crawl_events + widget_events + api_events:
            k = ((e.get("title") or "").strip().lower(), (e.get("date") or "")[:10])
            if k not in seen:
                seen.add(k)
                merged.append(e)
        if merged:
            return merged

    # 4. SHALLOW fallback: extract the given page directly.
    return _extract_one(url, source_name, city, lat, lng, categories, verbose=verbose)


def _render_calendar_page(url, source_name, city, lat, lng, categories, verbose=True):
    """Render the source's calendar page ONCE with Playwright and extract events.
    This catches JS-widget calendars (Park Record) that no HTTP method surfaces.
    Returns events (possibly empty). One render per source — the per-domain cache
    avoids repeats within a run. Skips quickly if Playwright isn't available."""
    global _budget_spent
    if source_name in _PW_RENDER_CACHE:
        return _PW_RENDER_CACHE[source_name]
    evs = []
    try:
        from firecrawl_extractor import extract_via_playwright
        # try the given URL, and one common calendar path if different
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        candidates = [url]
        if not re.search(r"/(calendar|events?)/?$", url):
            candidates.append(root + "/calendar/")
        for turl in candidates[:2]:
            if _budget_spent >= FIRECRAWL_BUDGET:
                break
            got = extract_via_playwright(
                turl, source_name, default_lat=lat, default_lng=lng,
                default_city=city, default_categories=categories or []) or []
            _budget_spent += 1
            if got:
                evs = _dedup_events(got)
                break
    except Exception as ex:
        if verbose:
            print(f"    calendar-render error: {str(ex)[:60]}")
    if verbose:
        print(f"    calendar render -> {len(evs)} events")
    _PW_RENDER_CACHE[source_name] = evs
    return evs


_PW_RENDER_CACHE = {}  # domain -> rendered events, once per run

_API_CAPTURE_CACHE = {}  # domain -> expanded api events, once per run


def _html_unescape(s):
    try:
        import html
        return html.unescape(s or "")
    except Exception:
        return s or ""


def _map_api_record(rec, source_name, url, city, default_lat, default_lng,
                    categories):
    """Map a raw event-API record (VPC/simpleview-style) into our event dict.
    Tolerant of key variations — only needs a title + a start date."""
    title = (rec.get("title") or rec.get("name") or rec.get("eventName")
             or rec.get("headline") or "").strip()
    title = _html_unescape(title)
    start = (rec.get("startDate") or rec.get("start_date") or rec.get("start")
             or rec.get("date") or rec.get("begin") or "")
    if not title or not start:
        return None
    end = (rec.get("endDate") or rec.get("end_date") or rec.get("end") or "")
    loc = (rec.get("location") or rec.get("venue") or rec.get("venue_name")
           or rec.get("address") or city or "")
    loc = _html_unescape(str(loc)).strip()
    try:
        elat = float(rec.get("latitude") or rec.get("lat") or 0) or (default_lat or 0)
        elng = float(rec.get("longitude") or rec.get("lng")
                     or rec.get("lon") or 0) or (default_lng or 0)
    except (TypeError, ValueError):
        elat, elng = (default_lat or 0), (default_lng or 0)
    link = rec.get("url") or rec.get("link") or url
    if isinstance(link, str) and link.startswith("/"):
        link = f"{urlparse(url).scheme}://{urlparse(url).netloc}{link}"
    return {
        "title": title,
        "date": str(start)[:10],
        "startDate": start, "endDate": end or start,
        "end_date": str(end or start)[:10],
        "recurrence": rec.get("recurrence") or "",
        "recurType": rec.get("recurType"),
        "location": loc, "venue_name": "",
        "link": link, "start_time": None, "end_time": None,
        "source": source_name, "source_url": url,
        "lat": elat, "lng": elng,
        "city": city or "", "categories": categories or [],
    }


def _capture_api_events(url, source_name, city, lat, lng, categories, verbose=True):
    """Capture a source's internal event API, replay it with widened limits, map
    records to our event shape, and expand recurrences into dated occurrences.
    Returns events (possibly empty). One capture per domain per run.

    GENERAL: no per-site URLs. The API is detected by request shape; recurrences
    are read from each record's stated pattern. Works for any site whose calendar
    is backed by a JSON events API."""
    global _budget_spent
    if source_name in _API_CAPTURE_CACHE:
        return _API_CAPTURE_CACHE[source_name]
    out = []
    try:
        from playwright_render import capture_event_api, replay_event_api
        from recurrence_expand import expand_event
        # capture on the source's calendar page — the event API typically only
        # fires on the actual /calendar/ view, not the /events/ landing page.
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        candidates = []
        if re.search(r"/calendar/?$", url):
            candidates.append(url)
        else:
            candidates.append(root + "/events/calendar/")
            candidates.append(root + "/calendar/")
            candidates.append(url)
        recs, api_url = [], None
        for cand in candidates:
            recs, api_url = capture_event_api(cand, verbose=verbose)
            if api_url or recs:
                break
        # SAME-ORIGIN GUARD: a source may embed a THIRD-PARTY calendar widget
        # (e.g. a real-estate site embedding Visit Park City's calendar). If the
        # captured API's host doesn't match the source's host, those events
        # belong to the other source — capturing them here double-counts them
        # under the wrong name. Reject cross-domain captures.
        if api_url:
            src_host = urlparse(url).netloc.replace("www.", "")
            api_host = urlparse(api_url).netloc.replace("www.", "")
            if src_host and api_host and src_host not in api_host \
                    and api_host not in src_host:
                if verbose:
                    print(f"    api-capture: skipped cross-domain API "
                          f"({api_host} != {src_host})")
                _API_CAPTURE_CACHE[source_name] = []
                return []
        if api_url:
            full = replay_event_api(api_url, verbose=verbose) or recs or []
        else:
            full = recs or []
        if full:
            mapped = []
            for r in full:
                m = _map_api_record(r, source_name, url, city, lat, lng, categories)
                if m:
                    mapped.append(m)
            # expand recurrences into dated occurrences (bounded + capped inside)
            for m in mapped:
                out.extend(expand_event(m))
            if verbose:
                print(f"    api-capture: {len(full)} defs -> {len(mapped)} mapped "
                      f"-> {len(out)} dated events")
    except Exception as ex:
        if verbose:
            print(f"    api-capture error: {str(ex)[:70]}")
    _API_CAPTURE_CACHE[source_name] = out
    return out


_PW_DECISION_CACHE = {}  # domain -> bool, decided once per run


def _source_needs_playwright(source_url, source_name, city, lat, lng,
                             categories, verbose=True, return_events=False):
    """Decide ONCE whether a source needs Playwright. Tests the source's main /
    calendar page with the fast ladder vs Playwright. If Playwright finds events
    the fast methods don't, the source has a JS widget calendar -> return True.
    Cached per-domain so it runs once per source, not per URL.

    return_events=True also returns the events Playwright rendered during the
    probe, so the caller can reuse them instead of rendering the page again.

    This is what keeps full runs fast: only widget sources (rare) pay the browser
    cost; the many sitemap/static sources skip Playwright entirely."""
    global _budget_spent
    dom = source_name
    if dom in _PW_DECISION_CACHE:
        decision, evs = _PW_DECISION_CACHE[dom]
        return (decision, evs) if return_events else decision

    decision, probe_events = False, []
    try:
        from firecrawl_extractor import extract_via_playwright
        root = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"
        test_urls = [source_url]
        for p in ("/calendar/", "/events/", "/event-calendar/"):
            if root + p != source_url:
                test_urls.append(root + p)
        for turl in test_urls[:2]:
            fast = _extract_one(turl, source_name, city, lat, lng, categories,
                                verbose=False, allow_playwright=False) or []
            if fast:
                continue
            if _budget_spent < FIRECRAWL_BUDGET:
                pw = extract_via_playwright(turl, source_name, default_lat=lat,
                                            default_lng=lng, default_city=city,
                                            default_categories=categories or []) or []
                _budget_spent += 1
                if pw:
                    decision, probe_events = True, pw
                    break
    except Exception:
        decision, probe_events = False, []

    _PW_DECISION_CACHE[dom] = (decision, probe_events)
    if verbose:
        print(f"    [{dom}] playwright-needed: {decision}")
    return (decision, probe_events) if return_events else decision


def _dedup_events(events):
    seen, out = set(), []
    for e in events:
        k = ((e.get("title") or "").strip().lower(), (e.get("date") or "")[:10])
        if k and k not in seen:
            seen.add(k)
            out.append(e)
    return out


_DEDUP_STRIP_RE = re.compile(
    r"\b(in concert|live in concert|live|presents?|feat\.?|featuring|"
    r"with special guests?|tickets?|tour|the\b)\b", re.I)


def _dedup_norm_title(t):
    """Normalize a title for cross-source matching: lowercase, strip common
    filler words and punctuation. Conservative — keeps the distinctive words so
    different events stay different."""
    t = (t or "").lower()
    t = _DEDUP_STRIP_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _smart_dedup(events, day_window=1, verbose=True):
    """Collapse the SAME event appearing from multiple sources. Conservative:
    only merges when normalized titles are IDENTICAL (not just similar) and the
    dates are within `day_window` days. Keeps the richer record (more fields
    filled). Under-merging is safe; over-merging deletes distinct events, so we
    require exact normalized-title equality, never fuzzy similarity.

    Returns (deduped_list, num_merged)."""
    from datetime import date as _date
    def richness(e):
        return sum(1 for k in ("start_time", "venue_name", "address", "description",
                               "image_url", "end_time") if e.get(k))
    def parse(d):
        try:
            return _date.fromisoformat((d or "")[:10])
        except Exception:
            return None

    # bucket by normalized title; within a bucket, merge records whose dates are
    # within the window.
    buckets = {}
    for e in events:
        buckets.setdefault(_dedup_norm_title(e.get("title")), []).append(e)

    out, merged = [], 0
    for norm, group in buckets.items():
        if not norm or len(group) == 1:
            out.extend(group)
            continue
        group.sort(key=lambda e: (e.get("date") or ""))
        used = [False] * len(group)
        for i, e in enumerate(group):
            if used[i]:
                continue
            cluster = [e]
            di = parse(e.get("date"))
            for j in range(i + 1, len(group)):
                if used[j]:
                    continue
                dj = parse(group[j].get("date"))
                if di and dj and abs((dj - di).days) <= day_window:
                    cluster.append(group[j])
                    used[j] = True
            used[i] = True
            # keep the richest record in the cluster
            best = max(cluster, key=richness)
            out.append(best)
            merged += len(cluster) - 1
    if verbose and merged:
        print(f"  smart-dedup: merged {merged} cross-source duplicates")
    return out, merged


def _extract_one(url, source_name, city, lat, lng, categories=None, verbose=True,
                 allow_playwright=False):
    """Try EVERY free strategy on this URL and UNION the results. Only escalate
    to paid strategies (Firecrawl render, then enhanced proxy) if the free union
    came up empty. This is 'exhaust free recourses, then pay' — the opposite of
    the old stop-at-first-hit cascade.

    Returns the deduped union of whatever the strategies found."""
    global _budget_spent
    found = []

    # ---- FREE strategies (always run, union results) ----
    # 1. schema.org / JSON-LD on the page
    if scrape_schema_org_events:
        try:
            evs = scrape_schema_org_events(
                url, source_name=source_name, default_lat=lat, default_lng=lng,
                default_categories=categories or [], default_city=city) or []
            if evs:
                found += evs
                if verbose:
                    print(f"      [free] schema.org -> {len(evs)}")
        except Exception:
            pass

    # 2. direct-fetch + embedded JSON-LD (different parser path; catches pages
    #    schema_org_scraper's fetch misses but a raw parse finds)
    try:
        from schema_org_scraper import _fetch as _sos_fetch, _extract_schema_events
        html = _sos_fetch(url)
        if html:
            raw = _extract_schema_events(html) or []
            if raw:
                # these are schema blocks; reuse the same parser the module uses
                from schema_org_scraper import _parse_event
                for blk in raw:
                    try:
                        ev = _parse_event(blk, source_name, url, lat, lng,
                                          categories or [], city)
                        if ev:
                            found.append(ev)
                    except Exception:
                        pass
                if verbose and raw:
                    print(f"      [free] direct json-ld -> {len(raw)} blocks")
    except Exception:
        pass

    found = _dedup_events(found)
    if found:
        return found  # free tier produced events; don't pay

    # ---- PAID strategies (only when free found nothing) ----
    if extract_events_from_url and _budget_spent < FIRECRAWL_BUDGET:
        # 3. Firecrawl standard render + LLM extract
        try:
            evs = extract_events_from_url(
                url, source_name, default_lat=lat, default_lng=lng,
                default_categories=categories or []) or []
            _budget_spent += 1
            if evs:
                if verbose:
                    print(f"      [paid] firecrawl render -> {len(evs)}")
                return _dedup_events(evs)
        except Exception:
            pass

        # 4. Firecrawl ENHANCED proxy — stronger backend for anti-bot / heavy-JS
        #    sites that the standard render returns empty for (e.g. widget calendars).
        if _budget_spent < FIRECRAWL_BUDGET:
            try:
                evs = extract_events_from_url(
                    url, source_name, default_lat=lat, default_lng=lng,
                    default_categories=categories or [], proxy="enhanced") or []
                _budget_spent += 1
                if evs:
                    if verbose:
                        print(f"      [paid] firecrawl enhanced -> {len(evs)}")
                    return _dedup_events(evs)
                # empty -> fall through to Playwright (do NOT return here)
            except TypeError:
                # extractor doesn't support proxy kwarg yet; skip to Playwright
                pass
            except Exception:
                pass

        # 5. PLAYWRIGHT — final rung: real headless browser. Controlled by
        #    allow_playwright (decided once per SOURCE, not guessed per URL) so we
        #    don't run a 15s browser render on hundreds of past-show pages. A
        #    source is flagged playwright-needed only if a sample test showed
        #    Playwright finds events the faster methods miss (e.g. Park Record's
        #    JS widget calendar).
        if allow_playwright and _budget_spent < FIRECRAWL_BUDGET:
            try:
                from firecrawl_extractor import extract_via_playwright
                evs = extract_via_playwright(
                    url, source_name, default_lat=lat, default_lng=lng,
                    default_city=city, default_categories=categories or []) or []
                _budget_spent += 1
                if evs:
                    if verbose:
                        print(f"      [paid] playwright -> {len(evs)}")
                    return _dedup_events(evs)
            except Exception:
                pass

    return []


# ---------------------------------------------------------------------------
# Normalize + geo-filter
# ---------------------------------------------------------------------------
def _haversine_mi(lat1, lng1, lat2, lng2):
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


_JUNK_TITLE_RE = re.compile(
    r"\b(open house|new listing|for sale|for rent|price reduc|mls #|"
    r"under contract|just listed|home tour|model home)\b", re.I)


def normalize_and_filter(events, city, lat, lng, radius_mi, verbose=True):
    """Stamp city/source defaults, drop past-dated & dateless, geo-filter to
    radius when an event has its own coordinates, and drop obvious non-public
    events (real-estate listings, etc.)."""
    today = date.today().isoformat()
    out = []
    dropped_past = dropped_nodate = dropped_far = dropped_junk = 0
    for e in events:
        title = e.get("title") or ""
        if _JUNK_TITLE_RE.search(title):
            dropped_junk += 1
            continue
        d = (e.get("date") or "")[:10]
        if not d:
            dropped_nodate += 1
            continue
        if d < today:
            dropped_past += 1
            continue
        elat, elng = e.get("lat"), e.get("lng")
        if elat and elng and radius_mi:
            try:
                if _haversine_mi(lat, lng, float(elat), float(elng)) > radius_mi:
                    dropped_far += 1
                    continue
            except (TypeError, ValueError):
                pass
        e.setdefault("city", city)
        out.append(e)
    if verbose:
        print(f"  normalize: kept {len(out)} "
              f"(dropped {dropped_past} past, {dropped_nodate} dateless, "
              f"{dropped_far} out-of-radius, {dropped_junk} junk)")
    return out


# ---------------------------------------------------------------------------
# Source selection from a discovery run
# ---------------------------------------------------------------------------
def sources_from_discovery(pending_path, city_hint=None, min_score=0):
    """Read pending_sources.json and return [(url, [tech_types])] for the most
    recent run matching a city.

    IMPORTANT: reads the FULL discovered list (all_results_for_review), not just
    the high-scored `candidates`. The static-HTML scorer scores JS-driven sources
    (VPC, Park Record) near 0 because their events load via JavaScript and aren't
    in the raw HTML — so gating on score throws away the best sources. We extract
    from EVERY discovered source and let actual event yield be the real measure.
    min_score defaults to 0 (no gate)."""
    data = json.loads(Path(pending_path).read_text())
    runs = data.get("runs", [data]) if isinstance(data, dict) else [data]
    # most recent NON-EMPTY run matching the city
    run = None
    if city_hint:
        for r in reversed(runs):
            if city_hint.lower() in (r.get("city") or "").lower() and \
               (r.get("all_results_for_review") or r.get("candidates")):
                run = r
                break
    run = run or (runs[-1] if runs else {})

    # union of the full discovered list and the scored candidates
    pool = {}
    for c in run.get("all_results_for_review", []) or []:
        if c.get("url"):
            pool[c["url"]] = c
    for c in run.get("candidates", []) or []:
        if c.get("url"):
            pool[c["url"]] = c  # candidates carry detected_tech; prefer them

    out = []
    for url, c in pool.items():
        if c.get("score", 0) >= min_score:
            techs = [d.get("type") for d in c.get("detected_tech", [])]
            out.append((url, techs))
    return run.get("city", city_hint or "?"), out


# ---------------------------------------------------------------------------
# Orchestrate
# ---------------------------------------------------------------------------
def scrape_city(city, lat, lng, radius_mi=25, pending_path="pending_sources.json",
                min_score=0, categories=None, max_sources=None, verbose=True):
    print(f"\n{'='*60}\nUniversal scrape: {city}\n{'='*60}")
    if not Path(pending_path).exists():
        print(f"No {pending_path} — run discover_sources.py --city \"{city}\" first.")
        return []

    disc_city, sources = sources_from_discovery(pending_path, city_hint=city, min_score=min_score)
    # dedup by domain — discovery often returns several pages of the same site
    # (VPC appeared 4x); crawling each repeats the same sitemap/geocoding work.
    # Keep the first (usually the events/ landing) URL per domain.
    _seen_dom, _deduped, _skipped_biz = set(), [], 0
    for url, techs in sources:
        dom = _domain(url)
        if dom in _seen_dom:
            continue
        # skip business types that embed others' calendars (realtors, lodging,
        # rentals) — they don't host their own events and cause double-counting.
        if any(kw in dom for kw in _NON_EVENT_BIZ_KEYWORDS):
            _skipped_biz += 1
            continue
        _seen_dom.add(dom)
        _deduped.append((url, techs))
    if verbose and _skipped_biz:
        print(f"  (skipped {_skipped_biz} non-event-business sources: "
              f"realtor/lodging/rental)")
    if verbose and len(_deduped) < len(sources):
        print(f"  (deduped {len(sources)} sources -> {len(_deduped)} unique domains)")
    sources = _deduped
    if max_sources:
        sources = sources[:max_sources]
    print(f"Sources to extract: {len(sources)} (score >= {min_score})\n")

    all_events = []
    per_source = []
    for i, (url, techs) in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {_domain(url)} | tech={techs or ['none']}")
        # HARD PER-SOURCE TIMEOUT — no single source may hang the whole run
        # (a stuck browser render once froze a run for 10h). If a source exceeds
        # the ceiling, abandon it and move on. Essential for unattended runs.
        evs = []
        try:
            with _source_timeout(SOURCE_TIMEOUT_S):
                evs = extract_source(url, techs, city, lat, lng,
                                     categories=categories, verbose=verbose)
        except _SourceTimeout:
            print(f"    [{_domain(url)}] TIMED OUT after {SOURCE_TIMEOUT_S}s "
                  f"-> skipping source")
            evs = []
        except Exception as _ee:
            print(f"    [{_domain(url)}] error: {str(_ee)[:70]} -> skipping")
            evs = []
        kept = normalize_and_filter(evs, city, lat, lng, radius_mi, verbose=verbose)
        try:
            from geo_validate import geo_validate
            kept = geo_validate(kept, city, lat, lng, radius_mi, verbose=verbose)
        except Exception as _ge:
            if verbose:
                print(f"    geo-validate skipped: {str(_ge)[:60]}")
        per_source.append({"url": url, "tech": techs, "raw": len(evs), "kept": len(kept)})
        all_events.extend(kept)

    # cross-source dedup: collapse the same event from multiple sources
    # (conservative — exact normalized title + dates within a day).
    deduped, _merged = _smart_dedup(all_events, day_window=1, verbose=verbose)

    print(f"\n{'='*60}\n{city}: {len(deduped)} events from {len(sources)} sources "
          f"({len(all_events) - len(deduped)} dup-collapsed)\n{'='*60}")
    for ps in per_source:
        print(f"  {ps['kept']:4} kept / {ps['raw']:4} raw | {_domain(ps['url'])}")

    _stage(city, deduped, per_source)
    return deduped


def _stage(city, events, per_source):
    """Split events by location confidence and stage separately:
      - VERIFIED (publish-ready): location confirmed local — real coords in
        radius, or text names the target city. These are safe to publish.
      - UNVERIFIED (needs review): location couldn't be confirmed (no coords,
        text inconclusive). Held for human approval, NOT auto-published.

    This keeps out-of-area / uncertain events out of what goes live, while
    preserving them for review rather than silently dropping them."""
    slug = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
    verified = [e for e in events if not e.get("_geo_unverified")]
    unverified = [e for e in events if e.get("_geo_unverified")]

    if STAGE_MODE == "push":
        # only publish the verified set
        out = Path(f"public/raw/events-{slug}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"events": verified}, indent=2))
        print(f"\n[push] wrote {len(verified)} VERIFIED events -> {out}")
        if unverified:
            rev = REVIEW_DIR / f"{slug}-unverified.json"
            REVIEW_DIR.mkdir(exist_ok=True)
            rev.write_text(json.dumps({
                "city": city, "generated_at": date.today().isoformat(),
                "event_count": len(unverified), "events": unverified,
            }, indent=2))
            print(f"[review] {len(unverified)} unverified held for approval -> {rev}")
    else:
        REVIEW_DIR.mkdir(exist_ok=True)
        # verified -> publish-ready review file
        v = REVIEW_DIR / f"{slug}.json"
        v.write_text(json.dumps({
            "city": city, "generated_at": date.today().isoformat(),
            "event_count": len(verified), "sources": per_source,
            "events": verified,
        }, indent=2))
        # unverified -> separate review file
        u = REVIEW_DIR / f"{slug}-unverified.json"
        u.write_text(json.dumps({
            "city": city, "generated_at": date.today().isoformat(),
            "event_count": len(unverified), "events": unverified,
        }, indent=2))
        print(f"\n[review] {len(verified)} verified-local -> {v}")
        print(f"[review] {len(unverified)} unverified (location unconfirmed) -> {u}")
        print("  Verified set is publish-ready; review the unverified file to approve/reject.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lng", type=float, required=True)
    ap.add_argument("--radius", type=float, default=25)
    ap.add_argument("--min-score", type=int, default=0)
    ap.add_argument("--max-sources", type=int, default=None)
    ap.add_argument("--pending", default="pending_sources.json")
    args = ap.parse_args()
    scrape_city(args.city, args.lat, args.lng, radius_mi=args.radius,
                pending_path=args.pending, min_score=args.min_score,
                max_sources=args.max_sources)
