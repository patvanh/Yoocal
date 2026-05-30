"""Deterministic recurrence/date-list parser for event detail pages.

Many event CMS templates (e.g. Simpleview tourism sites like gohebervalley.com)
render an explicit list of occurrence dates under a "Starts" heading, plus a
human schedule under "General Schedule". This parses those deterministically,
so we don't rely on an LLM for clean structured data.

Reusable across cities/scrapers: call parse_occurrence_dates(page_text).
"""
from __future__ import annotations
import re
from datetime import datetime

# "Starts <dates...> Ends" block holds the start-date list. Parse dates only
# from the Starts block to avoid double-counting the parallel Ends list.
_STARTS_BLOCK_RE = re.compile(r"\bStarts\b(.*?)\bEnds\b", re.IGNORECASE | re.DOTALL)
_MDY_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_SCHEDULE_RE = re.compile(r"General Schedule\s*(.*?)\s*Starts", re.IGNORECASE | re.DOTALL)


def parse_occurrence_dates(page_text: str) -> dict | None:
    """Extract explicit occurrence dates + recurrence text from page text.

    Returns {"occurrence_dates": [ISO...], "recurrence_text": str|None} or None
    if no structured date list is found. Only returns occurrence_dates when 2+
    distinct dates are found (a single date isn't a recurrence).
    """
    if not page_text:
        return None
    # Collapse whitespace so the regexes match across original line breaks.
    text = re.sub(r"\s+", " ", page_text)

    m = _STARTS_BLOCK_RE.search(text)
    if not m:
        return None
    block = m.group(1)

    iso_dates = []
    for mm, dd, yyyy in _MDY_RE.findall(block):
        try:
            iso = datetime(int(yyyy), int(mm), int(dd)).date().isoformat()
            iso_dates.append(iso)
        except ValueError:
            continue
    # De-dupe, preserve order
    seen = set()
    iso_dates = [d for d in iso_dates if not (d in seen or seen.add(d))]

    if len(iso_dates) < 2:
        return None  # not a recurring/multi-date event

    sched = _SCHEDULE_RE.search(text)
    rec_text = sched.group(1).strip()[:120] if sched else None

    return {"occurrence_dates": iso_dates, "recurrence_text": rec_text}


# "Recurring weekly on Monday, Thursday, Friday, Saturday" — used by Simpleview
# tourism sites (e.g. visitparkcity.com) in a JSON "recurrence" field. Combined
# with schema.org startDate/endDate, the build fan-out engine computes every
# matching weekday in range. Returns recurrence fields, NOT dates (the engine
# expands them given an end_date).
_WEEKLY_RE = re.compile(
    r"Recurring\s+weekly\s+on\s+([A-Za-z,\s]+?)(?:[\".]|$)",
    re.IGNORECASE,
)
_VALID_DAYS = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}


def parse_weekly_recurrence(page_text: str) -> dict | None:
    """Extract 'Recurring weekly on <days>' -> recurrence fields.

    Returns {"recurrence": "weekly", "recurrence_days": "Monday,Thursday,..."}
    or None. Caller must supply end_date (from schema) for the fan-out engine
    to compute occurrences.
    """
    if not page_text:
        return None
    m = _WEEKLY_RE.search(page_text)
    if not m:
        return None
    raw = m.group(1)
    days = []
    for token in re.split(r"[,\s]+", raw):
        t = token.strip().capitalize()
        if t.lower() in _VALID_DAYS and t not in days:
            days.append(t)
    if not days:
        return None
    return {"recurrence": "weekly", "recurrence_days": ",".join(days)}


if __name__ == "__main__":
    # quick self-test against gohebervalley cheese tasting
    import requests
    H = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"}
    html = requests.get("https://www.gohebervalley.com/cheese-tasting/", headers=H, timeout=20).text
    txt = re.sub(r"<[^>]+>", " ", html)
    out = parse_occurrence_dates(txt)
    print("result:", out)
