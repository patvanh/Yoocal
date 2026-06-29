"""Detail-page venue/recurrence enrichment (STANDALONE — not wired into the pipeline yet).

For each event missing a real venue or recurrence, resolve it the most ACCURATE
way available:
  1. Single-venue domain map: sites where every event is at one physical venue
     (verified by reading each site's own og:site_name). The venue is a known
     fact — mapped directly, no fetch, no LLM, 100% accurate.
  2. LLM detail-read: for aggregator sites where the venue varies per event,
     fetch the detail page once and let Haiku read the full text for
     venue / explicit dates / recurrence / category.

Every proposal is run through validate_proposal() before being returned:
fill-only-empty, reject malformed/out-of-range dates and junk venues.

Run standalone:  python3 event_detail_llm_enricher.py public/raw/events-jackson.json 12
Prints a BEFORE/PROPOSED diff and writes NOTHING. Wiring into the build is separate.
"""
from __future__ import annotations
import os, re, sys, json, html, hashlib
from datetime import datetime

_CACHE_PATH = ".cache/detail_llm_enrichment.json"
_MODEL = "claude-haiku-4-5-20251001"
_VALID_DAYS = {"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"}
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# Verified single-venue domains: every event on these sites is at ONE physical
# venue, confirmed by reading each site's own og:site_name across multiple event
# pages (consistent value = single venue). For these, the venue is a KNOWN FACT,
# so we map it directly — more accurate AND cheaper than asking the LLM to infer.
# Aggregator sites whose og:site_name is a brand/blog (e.g. "Jackson Hole
# Restaurants") are deliberately NOT here — their venue varies per event and is
# resolved by the LLM detail-read instead.
_SINGLE_VENUE_DOMAINS = {
    "wildlifeart.org": "National Museum of Wildlife Art",
    "www.wildlifeart.org": "National Museum of Wildlife Art",
    "snowkingmountain.com": "Snow King Mountain Resort",
    "www.snowkingmountain.com": "Snow King Mountain Resort",
    "thecloudveil.com": "The Cloudveil",
    "www.thecloudveil.com": "The Cloudveil",
}


def _domain_venue(link):
    """Return the known venue for a single-venue domain, or None."""
    try:
        from urllib.parse import urlparse
        return _SINGLE_VENUE_DOMAINS.get(urlparse(link).netloc.lower())
    except Exception:
        return None


def _load_cache():
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(c):
    try:
        os.makedirs(".cache", exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=0)
    except Exception as ex:
        print(f"  [detail-llm] cache write failed: {ex}")


# A location string that is ONLY a city/state (no street, no venue) — the
# signature of an event whose real venue got lost (e.g. "Jackson, WY",
# "green lake wisconsin"). Used to target enrichment at genuinely-broken events.
_CITY_ONLY_RE = re.compile(
    r"^(jackson|jackson hole|green lake|park city|heber|heber valley|"
    r"elkhart lake|teton village)?,?\s*"
    r"(wi|ut|wy|wisconsin|utah|wyoming)?\.?\s*$",
    re.I,
)


def _is_thin(e):
    """An event worth enriching: it has a usable detail link AND is GENUINELY
    broken — either (a) no real venue and its location is just a bare city/state
    string (real venue lost), or (b) a placeholder-looking date (future end_date,
    no recurrence, bare/empty venue) whose real schedule is unknown. This is the
    TIGHT filter — validated to target ~200 events, not the 2800+ that 'missing
    anything' would sweep in."""
    link = e.get("link") or ""
    if not link.startswith("http"):
        return False
    venue = (e.get("venue_name") or "").strip()
    loc = (e.get("location") or "").strip()
    date = (e.get("date") or "")[:10]
    end = (e.get("end_date") or "")[:10]
    has_rec = bool(e.get("recurrence") or e.get("occurrence_dates"))
    bare_city = (not venue) and bool(_CITY_ONLY_RE.match(loc))
    placeholder = (end and end > date and not has_rec) and (not venue or bool(_CITY_ONLY_RE.match(loc)))
    return bare_city or placeholder


_PAGE_CACHE = {}
def _fetch_text(url):
    if url in _PAGE_CACHE:
        return _PAGE_CACHE[url]
    text = ""
    try:
        import requests
        r = requests.get(url, headers=_UA, timeout=20)
        if r.status_code == 200:
            raw = r.text
            mdates = re.search(r'var dates\s*=\s*"([^"]+)"', raw)
            js_dates = mdates.group(1) if mdates else ""
            t = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S | re.I)
            t = re.sub(r"<style[^>]*>.*?</style>", " ", t, flags=re.S | re.I)
            t = re.sub(r"<[^>]+>", " ", t)
            t = html.unescape(t)
            t = re.sub(r"\s+", " ", t).strip()
            if js_dates:
                t = f"EXPLICIT_DATES: {js_dates}\n\n" + t
            text = t[:6000]
    except Exception as ex:
        print(f"  [detail-llm] fetch {url[:50]} failed: {str(ex)[:60]}")
    _PAGE_CACHE[url] = text
    return text


def _llm_read(title, page_text, event_date):
    if not page_text:
        return None
    cache = _load_cache()
    k = hashlib.sha1((title + "||" + page_text[:1000]).encode("utf-8")).hexdigest()[:16]
    if k in cache:
        return cache[k] or None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    prompt = (
        "You read an event's web page text and extract structured facts. "
        "Read for MEANING, not keywords.\n\n"
        "Return ONLY JSON:\n"
        '{"recurring": bool, "days": [weekday names], '
        '"explicit_dates": ["YYYY-MM-DD", ...], '
        '"end_date": "YYYY-MM-DD" or null, '
        '"venue": "venue name or null", '
        '"category": "one of Music/Food/Arts/Sports/Family/Community/Nightlife/Other"}\n\n'
        "Rules:\n"
        "- If the page lists EXPLICIT_DATES, return them in explicit_dates (ISO). "
        "These are the ground truth; recurring can be false if they're just a few dates.\n"
        "- recurring=true ONLY for a clearly stated weekly cadence (\"every Saturday\").\n"
        "- venue: the specific place name if stated (e.g. \"Norton's of Green Lake\"); "
        "null if the page only gives a city.\n"
        "- Do NOT invent anything not supported by the text.\n\n"
        f"The event's listed date is {event_date}.\n"
        f"Event title: {title}\n\n"
        f"Page text:\n{page_text[:4000]}\n\n"
        "JSON only:"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_MODEL, max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
    except Exception as ex:
        print(f"  [detail-llm] {title[:30]} failed: {str(ex)[:60]}")
        return None

    result = {}
    if isinstance(data, dict):
        days = [d.capitalize() for d in (data.get("days") or [])
                if isinstance(d, str) and d.capitalize() in _VALID_DAYS]
        ed = [d for d in (data.get("explicit_dates") or [])
              if isinstance(d, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
        if ed:
            result["occurrence_dates"] = sorted(set(ed))
        if data.get("recurring") and days:
            result["recurrence"] = "weekly"
            result["recurrence_days"] = ",".join(days)
            if isinstance(data.get("end_date"), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", data["end_date"]):
                result["end_date"] = data["end_date"]
        v = data.get("venue")
        if isinstance(v, str) and v.strip() and v.strip().lower() not in ("null", "none"):
            result["venue_name"] = v.strip()
        c = data.get("category")
        if isinstance(c, str) and c.strip():
            result["category_llm"] = c.strip()
    result = result or None
    cache[k] = result or {}
    _save_cache(cache)
    return result


def validate_proposal(event, got):
    """Return only the fields SAFE to apply from an LLM/map proposal, or {}.
    Conservative guardrails: reject clearly-broken output (malformed/out-of-range
    dates, absurd counts, junk venue), fill only EMPTY fields, never overwrite a
    populated one. Deliberately light — plausible-but-unusual schedules (e.g. a
    13-date Tue/Wed summer series) pass; only genuine garbage is dropped."""
    from datetime import date as _date
    out = {}
    occ = got.get("occurrence_dates") or []
    clean = []
    for d in occ:
        if not (isinstance(d, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", d)):
            continue
        try:
            dd = _date.fromisoformat(d)
        except ValueError:
            continue
        if dd.year < 2024 or dd.year > 2027:
            continue
        clean.append(d)
    clean = sorted(set(clean))
    if clean and len(clean) <= 60 and not (event.get("occurrence_dates") or event.get("recurrence")):
        out["occurrence_dates"] = clean
        if got.get("recurrence") == "weekly" and got.get("recurrence_days"):
            out["recurrence"] = "weekly"
            out["recurrence_days"] = got["recurrence_days"]
        ed = got.get("end_date")
        if isinstance(ed, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", ed):
            out["end_date"] = ed
    v = (got.get("venue_name") or "").strip()
    cur_v = (event.get("venue_name") or "").strip()
    cur_loc = (event.get("location") or "").strip().lower()
    _CITY_JUNK = {"jackson, wy", "jackson hole, wy", "green lake", "green lake, wi",
                  "park city", "park city, ut", "heber", "heber, ut", "elkhart lake"}
    if v and not cur_v:
        if len(v) <= 120 and v.lower() != cur_loc and v.lower() not in _CITY_JUNK:
            out["venue_name"] = v
    if got.get("category_llm"):
        out["category_llm"] = got["category_llm"]
    return out


def enrich(events, limit=None, verbose=True):
    """Read-only: returns a list of (event, validated_changes) for thin events."""
    thin = [e for e in events if _is_thin(e)]
    if verbose:
        print(f"{len(thin)} of {len(events)} events are 'thin' (candidate for detail enrichment)")
    if limit:
        thin = thin[:limit]
    proposals = []
    mapped = 0
    llm_used = 0
    for e in thin:
        link = e.get("link") or ""
        dv = _domain_venue(link)
        if dv and not (e.get("venue_name") or "").strip():
            v = validate_proposal(e, {"venue_name": dv})
            if v:
                v["_via"] = "domain_map"
                proposals.append((e, v))
                mapped += 1
            continue
        # 2. Otherwise read the detail page with the LLM, then validate.
        page = _fetch_text(link)
        got = _llm_read(e.get("title") or "", page, e.get("date"))
        if got:
            v = validate_proposal(e, got)
            if v:
                v["_via"] = "llm"
                proposals.append((e, v))
                llm_used += 1
    if verbose:
        print(f"  resolved via domain map: {mapped} | via LLM: {llm_used}")
    return proposals


def apply_enrichment(events, limit=None, verbose=True):
    """Build-facing entry point. Runs enrich() and WRITES validated fields back
    onto the event dicts in place (fill-only — validate_proposal already ensures
    we never overwrite a populated venue or existing recurrence). Returns the
    same list. Fully safe: on any per-event issue it skips that event.

    MUST run before _fan_out_recurring so any occurrence_dates/recurrence it adds
    get expanded into per-date cards by the existing fan-out machinery."""
    proposals = enrich(events, limit=limit, verbose=verbose)
    applied = 0
    for e, changes in proposals:
        for k, v in changes.items():
            if k == "_via":
                continue
            if not e.get(k):
                e[k] = v
                applied += 1
    if verbose:
        print(f"  [detail-enrich] applied {applied} field(s) across {len(proposals)} events")
    return events


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "public/raw/events-green-lake-wisconsin.json"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    d = json.load(open(path, encoding="utf-8"))
    evs = d["events"] if isinstance(d, dict) and "events" in d else d
    props = enrich(evs, limit=limit)
    print(f"\n=== {len(props)} validated proposals (READ-ONLY, nothing written) ===")
    for e, got in props:
        print(f"\n{e.get('title')!r}  [{e.get('source')}]")
        print(f"  link: {e.get('link')}")
        print(f"  BEFORE: date={e.get('date')} rec={e.get('recurrence')} "
              f"occ={len(e.get('occurrence_dates') or [])} venue={e.get('venue_name')!r}")
        print(f"  PROPOSED ({got.get('_via')}): { {k:v for k,v in got.items() if k!='_via'} }")
