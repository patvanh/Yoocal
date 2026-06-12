"""geo_validate.py — geocode scraped events and reject out-of-area ones.

THE PROBLEM this solves:
Aggregator sources (run guides, race calendars) list events across a whole
state. When such an event has no address, earlier code stamped it with the
city-center coordinates as a fallback — so the radius filter thought it was
0 miles away and let it through. Result: a Bears Ears ultra (300 mi away)
shows up in the Park City queue.

THE FIX:
  1. GEOCODE  — if an event has a venue/address but no real coords, look them
                up (Nominatim, free). Now the radius filter has true distance.
  2. VALIDATE — if an event still has no coords, scan its text (title, venue,
                description) for a place name. If it names a *different* known
                town far from the target, reject it. If it names the target
                city/region, keep it. If it names nothing, keep it but flag as
                unverified (so the review queue can surface it).

Nominatim is rate-limited (1 req/sec) and cached to disk so repeat runs are
free. No API key needed.
"""
from __future__ import annotations
import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

_CACHE = Path(".cache/geocode.json")
_UA = "YoocalGeocoder/1.0 (events aggregator; contact hello@yoocal.com)"
_last_call = [0.0]


def _haversine_mi(lat1, lng1, lat2, lng2):
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _load_cache():
    if _CACHE.exists():
        try:
            return json.loads(_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(c):
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(c, indent=2))


def geocode(query, cache):
    """Return (lat, lng) for a place string, or None. Cached; rate-limited."""
    q = (query or "").strip()
    if not q:
        return None
    if q in cache:
        v = cache[q]
        return tuple(v) if v else None
    # polite rate-limit: >= 1s between live calls
    dt = time.time() - _last_call[0]
    if dt < 1.1:
        time.sleep(1.1 - dt)
    url = ("https://nominatim.openstreetmap.org/search?"
           + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1}))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        data = json.load(urllib.request.urlopen(req, timeout=15))
        _last_call[0] = time.time()
        if data:
            latlng = (float(data[0]["lat"]), float(data[0]["lon"]))
            cache[q] = latlng
            return latlng
    except Exception:
        pass
    cache[q] = None
    return None


# Towns far enough from a typical resort-town target that naming them in the
# title almost always means the event is elsewhere. The target city is always
# allowed regardless.
import re as _re
_FAR_TOWN_RE = _re.compile(
    r"\b(salt lake|slc|sandy|draper|provo|orem|ogden|logan|st\.? george|"
    r"cedar city|moab|vernal|price|tooele|lehi|american fork|spanish fork|"
    r"mapleton|highland|brigham city|bountiful|layton|kaysville|"
    r"south jordan|west jordan|west valley|murray|midvale|riverton|herriman|"
    r"cottonwood heights|millcreek|holladay|taylorsville|magna|"
    r"huntsville|snowbasin|eden, ut|morgan, ut|"
    r"big cottonwood|little cottonwood|brighton|snowbird|alta|solitude|"
    r"bears ears|uinta|beaver|hawaii|nevada|idaho|wyoming|colorado)\b", _re.I)


def _text_location_ok(e, allow_tokens):
    """For an event we couldn't geocode: scan its text. Names a clearly-different
    far town -> False; names the target -> True; names nothing -> None.
    Far-town is checked FIRST so 'Sandy City 5K' (has generic 'city') is rejected."""
    blob = " ".join(str(e.get(k) or "") for k in
                    ("title", "venue_name", "location", "address", "description")).lower()
    # distinctive tokens only — drop generic words that collide with other towns
    distinctive = [t for t in allow_tokens if t not in ("city", "utah", "ut", "town", "the")]
    if _FAR_TOWN_RE.search(blob):
        return False
    if any(tok in blob for tok in distinctive):
        return True
    return None


# Match a "City, ST" or "City, Statename" mention in location text. Generic —
# works for any state, so the named-city check isn't Utah-specific.
_CITY_STATE_RE = _re.compile(
    r"([A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+){0,2}),\s*"
    r"(A[LKZR]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|"
    r"N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY]|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|"
    r"Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|"
    r"Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|"
    r"Mississippi|Missouri|Montana|Nebraska|Nevada|New\s+\w+|North\s+\w+|"
    r"Ohio|Oklahoma|Oregon|Pennsylvania|Rhode\s+Island|South\s+\w+|Tennessee|"
    r"Texas|Utah|Vermont|Virginia|Washington|West\s+Virginia|Wisconsin|Wyoming)\b")


def _named_city_far(e, city, target_lat, target_lng, radius_mi, cache):
    """GENERAL far-location check (not reliant on a hardcoded list, but with one
    as a reliable fast path). If the event's location text names a 'City, State':
      - if it's the target city -> keep (False)
      - if it matches the known far-town list -> reject (True), no geocode needed
      - else geocode that city and reject if beyond radius
    Also runs a raw far-town backstop on the location text (catches 'Salt Lake
    City' / 'Huntsville' even without a ', ST' suffix). Works for any target
    city; the geocode path generalizes, the list makes common cases reliable."""
    target_city_tokens = {t for t in _re.split(r"[ ,]+", city.lower())
                          if len(t) > 2 and t not in ("city", "utah", "the")}
    blob = " ".join(str(e.get(k) or "") for k in
                    ("location", "venue_name", "address")).lower()
    # backstop: a known far-town named anywhere in the location text, and the
    # target city NOT named -> reject. Catches 'Gallivan Center, Salt Lake City'
    # (no state) and 'Snowbasin Rd, Huntsville'.
    if _FAR_TOWN_RE.search(blob) and not any(tok in blob for tok in target_city_tokens):
        return True

    for key in ("location", "venue_name", "address", "title"):
        txt = str(e.get(key) or "")
        m = _CITY_STATE_RE.search(txt)
        if not m:
            continue
        named = m.group(1).strip()
        named_low = named.lower()
        if any(tok in named_low for tok in target_city_tokens):
            return False
        if _FAR_TOWN_RE.search(named_low):
            return True
        geo = geocode(f"{named}, {m.group(2)}", cache)
        if geo:
            d = _haversine_mi(target_lat, target_lng, geo[0], geo[1])
            return d > radius_mi
    return False


def _place_query(e, city):
    """Build the best geocode query string from an event's fields."""
    for key in ("address", "venue_name", "location", "venue"):
        v = e.get(key)
        if v and len(str(v)) > 3:
            # append city/state if the value looks like a bare venue name
            s = str(v)
            if "," not in s:
                s = f"{s}, {city}"
            return s
    return None


def geo_validate(events, city, lat, lng, radius_mi, verbose=True):
    """Geocode coordinate-less events, then drop those outside the radius or
    clearly in another town. Returns kept list."""
    cache = _load_cache()
    # tokens that mean "this IS the target area" — the city words + 'park city'
    allow_tokens = [t for t in _re.split(r"[ ,]+", city.lower()) if len(t) > 2]
    kept = []
    n_geocoded = n_dropped_far = n_dropped_text = n_dropped_named = n_unverified = 0
    for e in events:
        # FIRST: general named-city check (runs ALWAYS, even when coords exist).
        # Catches events whose text names a far city but whose coordinates were
        # mis-geocoded into the radius (e.g. SLC concerts from aggregators).
        if _named_city_far(e, city, lat, lng, radius_mi, cache):
            n_dropped_named += 1
            continue

        elat, elng = e.get("lat"), e.get("lng")
        has_real = (elat and elng and
                    not (abs(float(elat) - lat) < 1e-6 and abs(float(elng) - lng) < 1e-6))

        if not has_real:
            q = _place_query(e, city)
            geo = geocode(q, cache) if q else None
            if geo:
                e["lat"], e["lng"] = geo
                elat, elng = geo
                has_real = True
                n_geocoded += 1

        if has_real:
            try:
                dist = _haversine_mi(lat, lng, float(elat), float(elng))
                if dist > radius_mi:
                    n_dropped_far += 1
                    continue
            except (TypeError, ValueError):
                pass
        else:
            verdict = _text_location_ok(e, allow_tokens)
            if verdict is False:
                n_dropped_text += 1
                continue
            if verdict is None:
                e["_geo_unverified"] = True
                n_unverified += 1
        kept.append(e)

    _save_cache(cache)
    if verbose:
        print(f"  geo-validate: kept {len(kept)} "
              f"(geocoded {n_geocoded}, dropped {n_dropped_far} far + "
              f"{n_dropped_text} far-by-name + {n_dropped_named} named-city, "
              f"{n_unverified} unverified)")
    return kept


if __name__ == "__main__":
    import sys
    # quick manual test
    cache = _load_cache()
    for q in sys.argv[1:]:
        print(q, "->", geocode(q, cache))
    _save_cache(cache)
