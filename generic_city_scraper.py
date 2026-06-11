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

# Tech types (from discover_sources.py) that scrape_schema_org_events handles well.
SCHEMA_TECHS = {"schema-org-event", "data-attributes", "fullcalendar",
                "wordpress-tribe", "events-list-class"}


def _domain(url):
    return urlparse(url).netloc.replace("www.", "")


# ---------------------------------------------------------------------------
# Extraction: route a source to the best method, cascade on empty
# ---------------------------------------------------------------------------
def extract_source(url, tech_types, city, lat, lng, categories=None, verbose=True,
                   deep=True, max_event_urls=200):
    """Extract events from one source.

    deep=True: first discover all individual event-page URLs (generic sitemap /
    link-crawl), then extract each (schema.org free-path first, Firecrawl on
    miss). This is what pulls the FULL catalog from rich sources (e.g. VPC's 144
    events) instead of just the first list page. Falls back to single-page
    extraction when no event URLs are discovered."""
    source_name = _domain(url)

    # 1. DEEP: discover individual event URLs and extract each.
    if deep:
        try:
            from event_link_discovery import discover_event_urls
            event_urls = discover_event_urls(url, max_urls=max_event_urls, verbose=verbose)
        except Exception as ex:
            if verbose:
                print(f"    link-discovery error: {str(ex)[:80]}")
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
                    evs = _extract_one(eu, source_name, city, lat, lng, categories, verbose=False)
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
            if verbose:
                print(f"    deep: {len(event_urls)} urls "
                      f"({n_cached} cached, {n_fetched} fetched) -> {len(out)} events")
            if out:
                return out
            # fall through to single-page if detail pages yielded nothing

    # 2. SHALLOW fallback: extract the given page directly.
    return _extract_one(url, source_name, city, lat, lng, categories, verbose=verbose)


def _extract_one(url, source_name, city, lat, lng, categories=None, verbose=True):
    """Extract events from a single URL: schema.org (free) then Firecrawl+LLM."""
    events = []
    if scrape_schema_org_events:
        try:
            events = scrape_schema_org_events(
                url, source_name=source_name, default_lat=lat, default_lng=lng,
                default_categories=categories or [], default_city=city) or []
        except Exception:
            events = []
        if verbose and events:
            print(f"    schema.org -> {len(events)} events")
    if not events and extract_events_from_url:
        try:
            events = extract_events_from_url(
                url, source_name, default_lat=lat, default_lng=lng,
                default_categories=categories or []) or []
        except Exception:
            events = []
        if verbose and events:
            print(f"    firecrawl+llm -> {len(events)} events")
    return events


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
def sources_from_discovery(pending_path, city_hint=None, min_score=5):
    """Read pending_sources.json and return [(url, [tech_types])] for the most
    recent run (optionally matching a city), above a score threshold."""
    data = json.loads(Path(pending_path).read_text())
    runs = data.get("runs", [data]) if isinstance(data, dict) else [data]
    run = None
    if city_hint:
        for r in reversed(runs):
            if city_hint.lower() in (r.get("city") or "").lower():
                run = r
                break
    run = run or runs[-1]
    out = []
    for c in run.get("candidates", []):
        if c.get("score", 0) >= min_score:
            techs = [d.get("type") for d in c.get("detected_tech", [])]
            out.append((c["url"], techs))
    return run.get("city", city_hint or "?"), out


# ---------------------------------------------------------------------------
# Orchestrate
# ---------------------------------------------------------------------------
def scrape_city(city, lat, lng, radius_mi=40, pending_path="pending_sources.json",
                min_score=5, categories=None, max_sources=None, verbose=True):
    print(f"\n{'='*60}\nUniversal scrape: {city}\n{'='*60}")
    if not Path(pending_path).exists():
        print(f"No {pending_path} — run discover_sources.py --city \"{city}\" first.")
        return []

    disc_city, sources = sources_from_discovery(pending_path, city_hint=city, min_score=min_score)
    if max_sources:
        sources = sources[:max_sources]
    print(f"Sources to extract: {len(sources)} (score >= {min_score})\n")

    all_events = []
    per_source = []
    for i, (url, techs) in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {_domain(url)} | tech={techs or ['none']}")
        evs = extract_source(url, techs, city, lat, lng, categories=categories, verbose=verbose)
        kept = normalize_and_filter(evs, city, lat, lng, radius_mi, verbose=verbose)
        per_source.append({"url": url, "tech": techs, "raw": len(evs), "kept": len(kept)})
        all_events.extend(kept)

    # de-dup within this scrape by (title, date)
    seen, deduped = set(), []
    for e in all_events:
        k = ((e.get("title") or "").strip().lower(), (e.get("date") or "")[:10])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(e)

    print(f"\n{'='*60}\n{city}: {len(deduped)} events from {len(sources)} sources "
          f"({len(all_events) - len(deduped)} dup-collapsed)\n{'='*60}")
    for ps in per_source:
        print(f"  {ps['kept']:4} kept / {ps['raw']:4} raw | {_domain(ps['url'])}")

    _stage(city, deduped, per_source)
    return deduped


def _stage(city, events, per_source):
    slug = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
    if STAGE_MODE == "push":
        out = Path(f"public/raw/events-{slug}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"events": events}, indent=2))
        print(f"\n[push] wrote {len(events)} events -> {out}")
    else:
        REVIEW_DIR.mkdir(exist_ok=True)
        out = REVIEW_DIR / f"{slug}.json"
        out.write_text(json.dumps({
            "city": city, "generated_at": date.today().isoformat(),
            "event_count": len(events), "sources": per_source, "events": events,
        }, indent=2))
        print(f"\n[review] staged {len(events)} events -> {out}")
        print("  Review, then approve to push into public/raw/.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lng", type=float, required=True)
    ap.add_argument("--radius", type=float, default=40)
    ap.add_argument("--min-score", type=int, default=5)
    ap.add_argument("--max-sources", type=int, default=None)
    ap.add_argument("--pending", default="pending_sources.json")
    args = ap.parse_args()
    scrape_city(args.city, args.lat, args.lng, radius_mi=args.radius,
                pending_path=args.pending, min_score=args.min_score,
                max_sources=args.max_sources)
