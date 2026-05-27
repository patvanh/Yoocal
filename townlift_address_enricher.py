"""TownLift address enrichment.

TownLift's Tribe API doesn't include venue/address data for many events —
the address lives only in the article body. This module fetches each event
page, uses Claude to extract structured address info, then geocodes via
Nominatim (OpenStreetMap, free) to get lat/lng.

Results cached per event URL so daily re-scrapes only enrich new events.
"""
import json
import os
import re
import time
from pathlib import Path

def _load_dotenv_once():
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass

_load_dotenv_once()

CACHE_PATH = Path(".cache/townlift_enrichment.json")
NOMINATIM_USER_AGENT = "yoocal-events-aggregator/1.0 (https://yoocal.com)"

# Park City / Heber Valley zip codes — used as a cross-check on the LLM output
# (so we don't trust "Park City" with zip 84032 etc.).
PC_ZIPS = {"84060", "84068", "84098"}
HB_ZIPS = {"84032", "84036"}

# Approximate center coords as a final fallback when geocoding fails.
PC_FALLBACK = (40.6461, -111.4980)
HB_FALLBACK = (40.5069, -111.4133)


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


def _fetch_article_text(url, timeout=15):
    """Fetch event page, strip to article body text."""
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Yoocal)"}, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception as ex:
        print(f"  [townlift-enrich] fetch failed for {url}: {ex}")
        return None
    # Strip scripts/styles/nav, then drop tags and squeeze whitespace.
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"<nav.*?</nav>", "", html, flags=re.S | re.I)
    html = re.sub(r"<footer.*?</footer>", "", html, flags=re.S | re.I)
    # Keep a generous window — articles vary in length.
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 6000:
        text = text[:6000]
    return text


def _extract_address_via_llm(title, article_text):
    """Use Claude to extract structured address. Returns dict or None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Sentinel so the caller knows this was a config issue, not a real null.
        return "__SKIP__"

    try:
        import anthropic
    except ImportError:
        print("  [townlift-enrich] anthropic package not installed")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "Extract the event's physical venue address from the article below. "
        "Return ONLY a JSON object with these keys: "
        '{"venue_name": str|null, "street_address": str|null, '
        '"city": str|null, "state": str|null, "zip_code": str|null}. '
        "If no specific physical address is mentioned (e.g. virtual event, "
        "or only a general region named), return all-null values. "
        "Do not invent or guess details not in the text.\n\n"
        f"Event title: {title}\n\n"
        f"Article text:\n{article_text}\n\n"
        "JSON only, no commentary:"
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip code fences if model wrapped output.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        # Sanity: must be a dict with the expected keys.
        if not isinstance(data, dict):
            return None
        return data
    except Exception as ex:
        print(f"  [townlift-enrich] LLM extraction failed: {ex}")
        return None


def _geocode_via_nominatim(query, timeout=10):
    """Geocode a free-form address string. Returns (lat, lng) or None.

    Uses OpenStreetMap Nominatim (free). 1 req/sec rate limit.
    """
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=timeout,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        first = results[0]
        return (float(first["lat"]), float(first["lon"]))
    except Exception as ex:
        print(f"  [townlift-enrich] geocode failed for '{query}': {ex}")
        return None


def enrich_townlift_events(events):
    """Take a list of TownLift events, enrich missing locations in place.

    Returns the same list (mutated). Reports stats at the end.
    """
    cache = _load_cache()
    enriched = cached_hit = llm_null = geocode_fail = 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [townlift-enrich] ANTHROPIC_API_KEY not set — LLM enrichment skipped (no cache writes)")

    for e in events:
        loc = (e.get("location") or "").strip()
        has_real_venue = loc and loc != "Location TBD"
        if has_real_venue and e.get("lat") and e.get("lng"):
            continue  # already complete

        url = e.get("link")
        if not url:
            continue

        # Cache hit?
        if url in cache:
            cached = cache[url]
            cached_hit += 1
            if cached.get("lat") and cached.get("lng"):
                e["lat"] = cached["lat"]
                e["lng"] = cached["lng"]
            if cached.get("location"):
                e["location"] = cached["location"]
            continue

        # Fetch + extract.
        text = _fetch_article_text(url)
        if not text:
            cache[url] = {"status": "fetch_failed"}
            continue

        addr = _extract_address_via_llm(e.get("title", ""), text)
        if addr == "__SKIP__":
            # API not configured this run; don't cache, retry next time.
            continue
        if not addr or not any(addr.values()):
            cache[url] = {"status": "llm_null"}
            llm_null += 1
            continue

        # Build location label + geocode query.
        parts = []
        if addr.get("venue_name"): parts.append(addr["venue_name"])
        if addr.get("street_address"): parts.append(addr["street_address"])
        city_part = addr.get("city") or ""
        state_part = addr.get("state") or "UT"
        if city_part:
            parts.append(f"{city_part}, {state_part}")
        location_label = ", ".join(parts) if parts else None

        # Geocode using street + city + state + zip — most reliable combo.
        geo_query_parts = [addr.get("street_address"), addr.get("city"),
                           addr.get("state"), addr.get("zip_code")]
        geo_query = ", ".join(p for p in geo_query_parts if p)
        time.sleep(1.1)  # Nominatim rate limit
        coords = _geocode_via_nominatim(geo_query) if geo_query else None

        # Fallback by zip if geocoding failed.
        zip_code = (addr.get("zip_code") or "").strip()
        if not coords:
            if zip_code in PC_ZIPS:
                coords = PC_FALLBACK
            elif zip_code in HB_ZIPS:
                coords = HB_FALLBACK
            else:
                geocode_fail += 1

        # Stamp event.
        if location_label:
            e["location"] = location_label
        if coords:
            e["lat"] = coords[0]
            e["lng"] = coords[1]
            enriched += 1

        cache[url] = {
            "status": "ok",
            "location": location_label,
            "lat": coords[0] if coords else None,
            "lng": coords[1] if coords else None,
            "addr_raw": addr,
        }

    _save_cache(cache)
    print(f"  [townlift-enrich] {enriched} enriched, {cached_hit} from cache, "
          f"{llm_null} no-address-in-article, {geocode_fail} geocode-failed")
    return events
