"""Heber Valley Tourism (gohebervalley.com) event detail enricher.

The Heber Valley Tourism scraper only reads listing-page data (start date,
title, summary). The detail pages contain crucial fields the listings hide:
  - Multi-day date ranges ("July 23 through August 1")
  - Recurrence ("Every Saturday from May to October")
  - Per-day schedules for multi-day events

This module fetches each event's detail page, uses Claude to extract structured
dates/recurrence, and caches the result per URL so re-runs only enrich new
events.

Output: enriched event dicts with these new fields where applicable:
  - end_date: ISO date string when event spans multiple days
  - recurrence_text: human-readable description ("Every Saturday")
  - occurrence_dates: list of ISO dates if recurring or multi-day

The fan-out into individual day events happens later in the master build —
this module only enriches, it doesn't multiply events.
"""
import json
import os
import re
import time
from pathlib import Path

from recurrence_parser import parse_occurrence_dates

CACHE_PATH = Path(".cache/heber_valley_enrichment.json")


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


def _fetch_page_text(url, timeout=15):
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception as ex:
        print(f"  [hv-enrich] fetch failed for {url}: {ex}")
        return None
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"<nav.*?</nav>", "", html, flags=re.S | re.I)
    html = re.sub(r"<footer.*?</footer>", "", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    # Do NOT truncate: recurring-event date lists ("Starts ...") run long and
    # often sit past 8KB; cutting here drops months of occurrences.
    return text


def _extract_dates_via_llm(title, start_date_hint, article_text):
    """Ask Claude to extract structured date info. Returns dict or '__SKIP__' or None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "__SKIP__"
    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"Today is {time.strftime('%Y-%m-%d')}. The article below is THE AUTHORITATIVE source "
        f"for this event's dates.\n\n"
        f"(A listing card hinted start_date={start_date_hint or 'unknown'}, but this is NOT "
        "reliable — the article often shows different/wider dates. Trust the article over the hint.)\n\n"
        "Extract the date pattern AND the venue/location from the article. Return ONLY JSON:\n"
        '{\n'
        '  "start_date": "YYYY-MM-DD" or null,\n'
        '  "end_date": "YYYY-MM-DD" or null (only if event spans >1 day),\n'
        '  "is_recurring": true or false,\n'
        '  "recurrence_text": "human description" or null,\n'
        '  "occurrence_dates": ["YYYY-MM-DD", ...] or null (every occurrence through the real end date, do NOT cap),\n'
        '  "venue_name": "the venue/place name (e.g. Wasatch County Outdoor Arena)" or null,\n'
        '  "street_address": "street address only (e.g. 415 South Southfield Road)" or null,\n'
        '  "city": "city name (e.g. Heber City)" or null,\n'
        '  "zip_code": "5-digit zip" or null\n'
        '}\n\n'
        "Rules:\n"
        "- The article overrides any hint. If the article says 'July 23 through August 1' "
        "and the hint was 2026-07-27, set start_date=2026-07-23 and end_date=2026-08-01.\n"
        "- If the article says 'Every Saturday from June to October' set is_recurring=true, "
        "recurrence_text='Every Saturday June-October', and occurrence_dates to every Saturday "
        "from the start through the real end date (e.g. all the way through October).\n"
        "- If single one-day event, leave end_date/is_recurring/occurrence_dates null/false.\n"
        "- Year is 2026 unless the article explicitly says otherwise.\n"
        "- Look carefully for date ranges like 'DATES:', 'When:', 'July X through August Y'.\n"
        "- For venue/address: look for 'Location', 'Address', 'Venue' labels. Extract the\n"
        "  real place name and street address if present. Leave null if not stated.\n\n"
        f"Event title: {title}\n\n"
        f"Article text:\n{article_text}\n\n"
        "JSON only:"
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception as ex:
        print(f"  [hv-enrich] LLM extraction failed: {ex}")
        return None


def enrich_heber_valley_events(events):
    """Take Heber Valley Tourism events, fetch each detail page, enrich in place.

    Sets end_date, recurrence_text, occurrence_dates fields where applicable.
    Returns the mutated list.
    """
    cache = _load_cache()
    enriched = cached_hit = no_change = api_skipped = 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [hv-enrich] ANTHROPIC_API_KEY not set — skipping (no cache writes)")

    for e in events:
        # Only target Heber Valley Tourism events. Other sources we leave alone.
        if e.get("source") != "Heber Valley Tourism":
            continue

        url = e.get("link")
        if not url or "gohebervalley.com" not in url:
            continue
        url = url.rstrip("/")  # normalize: trailing-slash variants share one cache key

        # Only TRUST cache entries from the deterministic parser (page-structured,
        # stable, uncapped). LLM-derived ("ok") or failed entries are re-fetched
        # and re-parsed each run so the accurate result wins and stale/capped LLM
        # data self-heals. These CMS pages almost all carry the structured block,
        # so after one run nearly everything is a cached deterministic hit.
        if url in cache and cache[url].get("status") == "deterministic":
            cached = cache[url]
            cached_hit += 1
            llm_start = cached.get("start_date")
            if llm_start and llm_start < (e.get("date") or "9999"):
                e["date"] = llm_start
            if cached.get("end_date"): e["end_date"] = cached["end_date"]
            if cached.get("recurrence_text"): e["recurrence_text"] = cached["recurrence_text"]
            if cached.get("occurrence_dates"): e["occurrence_dates"] = cached["occurrence_dates"]
            _vn = (cached.get("venue_name") or "").strip()
            _st = (cached.get("street_address") or "").strip()
            _ci = (cached.get("city") or "").strip()
            _zp = (cached.get("zip_code") or "").strip()
            if _vn and not e.get("venue_name"):
                e["venue_name"] = _vn
            if _st and not e.get("address"):
                _ap = [_st]
                if _ci: _ap.append(_ci)
                _ap.append("UT")
                if _zp: _ap.append(_zp)
                e["address"] = ", ".join(_ap)
            _cl = (e.get("location") or "").strip().lower()
            if (_vn or _st) and _cl in ("", "heber valley, ut", "heber city, ut"):
                _lp = []
                if _vn: _lp.append(_vn)
                if _st: _lp.append(_st)
                if _ci: _lp.append(f"{_ci}, UT")
                if _lp:
                    e["location"] = ", ".join(_lp)
            continue

        text = _fetch_page_text(url)
        if not text:
            cache[url] = {"status": "fetch_failed"}
            continue

        # Deterministic first: structured "Starts <date list>" block (Simpleview
        # CMS template). Reliable + free; LLM only as fallback when absent.
        det = parse_occurrence_dates(text)
        if det and det.get("occurrence_dates"):
            e["occurrence_dates"] = det["occurrence_dates"]
            if det.get("recurrence_text"):
                e["recurrence_text"] = det["recurrence_text"]
            cache[url] = {
                "start_date": det["occurrence_dates"][0],
                "occurrence_dates": det["occurrence_dates"],
                "recurrence_text": det.get("recurrence_text"),
                "status": "deterministic",
            }
            enriched += 1
            continue

        result = _extract_dates_via_llm(e.get("title", ""), e.get("date"), text)
        if result == "__SKIP__":
            api_skipped += 1
            continue
        if not result:
            cache[url] = {"status": "llm_failed"}
            continue

        # Stamp the event with whatever the LLM found.
        changed = False
        # Override start date if LLM found an earlier one (article often has wider range than listing).
        llm_start = result.get("start_date")
        if llm_start and llm_start < (e.get("date") or "9999"):
            e["date"] = llm_start
            changed = True
        if result.get("end_date") and result["end_date"] != e.get("date"):
            e["end_date"] = result["end_date"]
            changed = True
        if result.get("recurrence_text"):
            e["recurrence_text"] = result["recurrence_text"]
            changed = True
        if result.get("occurrence_dates"):
            e["occurrence_dates"] = result["occurrence_dates"]
            changed = True
        # Venue + address: fill if the event lacks them (don't overwrite good data).
        vn = (result.get("venue_name") or "").strip()
        st = (result.get("street_address") or "").strip()
        ci = (result.get("city") or "").strip()
        zp = (result.get("zip_code") or "").strip()
        if vn and not e.get("venue_name"):
            e["venue_name"] = vn
            changed = True
        if st and not e.get("address"):
            addr_parts = [st]
            if ci: addr_parts.append(ci)
            addr_parts.append("UT")
            if zp: addr_parts.append(zp)
            e["address"] = ", ".join(addr_parts)
            changed = True
        # Build a rich location label from venue + city if current is generic.
        cur_loc = (e.get("location") or "").strip().lower()
        if (vn or st) and cur_loc in ("", "heber valley, ut", "heber city, ut"):
            loc_parts = []
            if vn: loc_parts.append(vn)
            if st: loc_parts.append(st)
            if ci: loc_parts.append(f"{ci}, UT")
            elif not vn and not st: loc_parts.append("Heber City, UT")
            if loc_parts:
                e["location"] = ", ".join(loc_parts)
                changed = True
        if changed:
            enriched += 1
        else:
            no_change += 1

        cache[url] = {
            "status": "ok",
            "start_date": result.get("start_date"),
            "end_date": result.get("end_date"),
            "recurrence_text": result.get("recurrence_text"),
            "occurrence_dates": result.get("occurrence_dates"),
            "venue_name": result.get("venue_name"),
            "street_address": result.get("street_address"),
            "city": result.get("city"),
            "zip_code": result.get("zip_code"),
        }

    _save_cache(cache)
    print(f"  [hv-enrich] {enriched} enriched, {cached_hit} from cache, "
          f"{no_change} single-day (no change), {api_skipped} skipped (no API key)")
    return events
