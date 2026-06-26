"""Build events-all.json master file and per-city radius-filtered views.

Reads the 4 per-city events-*.json files, merges + dedupes globally,
writes events-all.json, then writes per-city views by radius filtering.

Architecture:
  events-all.json    ← all events nationwide, source of truth
  events.json        ← Park City filtered view (within 10mi of city center)
  events-heber.json  ← Heber filtered view (within 10mi)
  events-jackson.json ← Jackson filtered view (within 20mi)
  events-elkhartlake.json ← Elkhart filtered view (within 15mi)

Cross-region events (e.g. PC Marathon through Heber) naturally appear
on BOTH calendars without duplication.
"""
from __future__ import annotations

import json
import os
from venue_lookup import lookup_venue_by_address
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

MOUNTAIN = timezone(timedelta(hours=-6))

# City centers + radius (miles)
CITIES = {
    "park-city": {
        "lat": 40.6461, "lng": -111.4980, "radius_mi": 10,
        "out_file": "public/events.json",
    },
    "heber": {
        "lat": 40.5069, "lng": -111.4133, "radius_mi": 10,
        "out_file": "public/events-heber.json",
    },
    "jackson": {
        "lat": 43.4799, "lng": -110.7624, "radius_mi": 25,
        "out_file": "public/events-jackson.json",
    },
    "elkhart-lake": {
        "lat": 43.8330, "lng": -88.0426, "radius_mi": 15,
        "out_file": "public/events-elkhartlake.json",
    },
    "green-lake": {
        "lat": 43.8408, "lng": -88.9576, "radius_mi": 25,
        "out_file": "public/events-greenlake.json",
    },
}

# Source files to read (current per-city files act as INPUT until we migrate scrapers)
INPUT_FILES = [
    "public/raw/events.json",
    "public/raw/events-heber.json",
    # Heber-addressed events relocated out of the Park City scrape (e.g. Deer
    # Creek Express). Written ONLY by scraper.py's merge_into_heber_file; no
    # other writer touches it, so it cannot be clobbered. The build routes these
    # to the correct city view by address/radius like any other event.
    "public/raw/events-heber-relocated.json",
    "public/raw/events-jackson.json",
    "public/raw/events-elkhartlake.json",
    "public/raw/events-egyptian.json",
    "public/raw/events-parkcityfilm.json",
    "public/raw/events-green-lake-wisconsin.json",
]

from category_normalizer import filter_categories_for

MASTER_FILE = "public/events-all.json"

# Always-on businesses/amenities that masquerade as daily events — they recur
# near-daily across months and are drop-in services, not dated happenings, so
# they flood the calendar. Removed early (before dedup/views/link-health).
# Matched by case-insensitive title substring; keep patterns TIGHT so they can
# never catch a real event. Add new amenities here as you spot them.
EXCLUDED_TITLE_PATTERNS = [
    "plunj",                               # PLUNJ — cold plunge drop-in
    "group fitness classes",               # daily rec-center drop-in (title is generic; venue carries the location)
    "triple trail challenge",              # TTC = "do all 3" series umbrella; its
                                           # legs (Round Valley Rambler, Jupiter
                                           # Peak 25K, Mid Mountain 50K) are each
                                           # listed separately, so the umbrella is
                                           # a redundant meta-entry (also mis-priced).
]

# Some amenities are better matched by VENUE than title (e.g. recurring church
# services where the title is generic "Church Service"). Case-insensitive
# substring on venue_name.
EXCLUDED_VENUE_PATTERNS = [
    "creekside christian fellowship",      # weekly church services (dead site)
]

_ALL_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday",
                 "saturday", "sunday"}


def _is_always_on_program(e):
    """Structural amenity signal: recurs every day of the week with no specific
    start time => an always-on program (drop-in fitness, open swim, facility
    hours), not a dated event. Fanning it out floods the calendar with one
    time-less card per day. Catches this class without hardcoding each title in
    EXCLUDED_TITLE_PATTERNS. Tight on purpose (all 7 days AND no time) so real
    recurring events — which have specific days and usually a time — are safe."""
    if (e.get("recurrence") or "").lower() not in ("weekly", "weekly_multiple"):
        return False
    if (e.get("start_time") or "").strip():
        return False
    days_raw = e.get("recurrence_days") or e.get("recurrence_day") or ""
    days = {d.strip().lower() for d in days_raw.replace("|", ",").split(",") if d.strip()}
    return _ALL_WEEKDAYS.issubset(days)


def _is_excluded_amenity(e):
    t = (e.get("title") or "").lower()
    if any(p in t for p in EXCLUDED_TITLE_PATTERNS):
        return True
    v = (e.get("venue_name") or "").lower()
    if any(p in v for p in EXCLUDED_VENUE_PATTERNS):
        return True
    if _is_always_on_program(e):
        return True
    return False


def haversine_miles(lat1, lng1, lat2, lng2):
    """Distance between two points in miles."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# Filler words that appear in aggregator titles but not venue-direct titles.
# Stripping these helps "Iris DeMent Tickets" and "An Evening with Iris DeMent"
# collapse to the same dedup key.
_TITLE_FILLERS = {
    "tickets", "ticket", "live", "presents", "an", "a", "the",
    "evening", "with", "feat", "featuring", "vs", "and",
    "concert", "show", "performance", "performs",
    "series",  # "...Concert Series" / "...To-Go Series" suffix noise
    "park", "city", "county",  # location/administrative words also strip
    "at",  # collapses "@ Venue" (punct stripped to space) with "at Venue"
}

_JUNK_TITLES = {
    # Scraped UI/navigation labels that aren't events (common from WordPress
    # Events Calendar / MEC month-view widgets). Exact-match after lowering.
    "views navigation", "event views navigation", "navigation",
    "skip to content", "skip to main content", "read more", "load more",
    "view all events", "see all events", "calendar of events",
    "events search and views navigation", "list", "month", "day", "today",
    "previous events", "next events", "previous day", "next day",
    # Section headers scraped as events from listing pages (not real events).
    "what’s on this season", "what's on this season", "whats on this season",
    "what’s on", "what's on",
}


def _is_junk_title(title: str) -> bool:
    t = (title or "").strip().lower()
    return t in _JUNK_TITLES


def _normalize_title(title: str) -> str:
    """Aggressive normalization: strip HTML, lowercase, drop punctuation + filler words."""
    import re as _re
    import html as _html
    if not title:
        return ""
    t = _html.unescape(title)               # &amp; -> &, &#39; -> '
    t = _re.sub(r"<[^>]+>", " ", t)         # strip HTML tags (<em>, </em>, <strong>...)
    t = t.lower()
    # Drop a leading "<presenter> presents <:|-|/>" promoter clause (e.g.
    # "Park City Film Presents: Jack Johnson" -> "Jack Johnson"). Runs before
    # tokenizing so the whole clause goes, not just the word "presents". Only
    # strips when real title text remains after the separator.
    _pm = _re.match(r"^.{0,80}?\bpresents\b\s*[:/-]\s*(.+)$", t)
    if _pm and _pm.group(1).strip():
        t = _pm.group(1)
    t = _re.sub(r"['’]s\b", "", t)         # strip possessive 's ("Heber's" -> "heber")
    # Canonicalize race-distance synonyms so "13.1M Half Marathon" and bare
    # "Half Marathon" (same distance, different notation) dedupe to one event.
    # Word forms first; bare "marathon" is left alone (a half != a full) and
    # other distances (5k/10k) keep their own distinct tokens.
    t = _re.sub(r"\bhalf[\s-]?marathon\b", " halfmarathon ", t)
    t = _re.sub(r"\b13\.1\s*(?:miles?|mi|m)\b", " halfmarathon ", t)
    t = _re.sub(r"\bfull[\s-]?marathon\b", " fullmarathon ", t)
    t = _re.sub(r"\b26\.2\s*(?:miles?|mi|m)\b", " fullmarathon ", t)
    t = _re.sub(r"[^a-z0-9 ]+", " ", t)     # punctuation -> space
    # Collapse common phrasing variants from multi-feed dupes: "2 go"/"2go" is
    # the same as "to go" (e.g. "Crafternoons 2 Go" vs "Crafternoons To-Go").
    t = _re.sub(r"\b2 ?go\b", "to go", t)
    tokens = [w for w in t.split() if w and w not in _TITLE_FILLERS]
    # Strip a day-of-week word at the very start or end of the title — recurring
    # events shouldn't be keyed by their day name.
    _DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    while tokens and tokens[0] in _DAYS:
        tokens = tokens[1:]
    while tokens and tokens[-1] in _DAYS:
        tokens = tokens[:-1]
    # Strip a LEADING standalone year ("2026 Kimball Arts Festival") so a
    # year-prefixed aggregator title dedupes with the bare title. Guard against
    # eating a real date phrase: only strip if what follows isn't a month/
    # ordinal/day-number (defined just below as _DATE_CTX).
    # Strip a trailing standalone year ("...Rodeo 2026") so cross-source
    # dupes match. Don't strip when the previous token is a month name or
    # an ordinal suffix — that indicates a date phrase ("may 28 2026" or
    # "june 14 2026") that must stay intact for context.
    _MONTHS = {"january","february","march","april","may","june","july",
               "august","september","october","november","december",
               "jan","feb","mar","apr","jun","jul","aug","sep","sept","oct","nov","dec"}
    _DATE_CTX = _MONTHS | {"th","st","nd","rd"} | {str(d) for d in range(1, 32)}
    # Leading year (mirror of trailing-year strip below).
    if (tokens and len(tokens) >= 2
            and _re.fullmatch(r"20\d\d", tokens[0])
            and tokens[1] not in _DATE_CTX):
        tokens = tokens[1:]
    if (tokens and len(tokens) >= 2
            and _re.fullmatch(r"20\d\d", tokens[-1])
            and tokens[-2] not in _DATE_CTX):
        tokens = tokens[:-1]
    # Collapse adjacent duplicate tokens (e.g. canonicalized "halfmarathon
    # halfmarathon" from "13.1M Half Marathon").
    deduped = []
    for _w in tokens:
        if not deduped or deduped[-1] != _w:
            deduped.append(_w)
    tokens = deduped
    return " ".join(tokens)


def event_key(e: dict) -> tuple:
    """Unique key for global dedup: (normalized_title, date).

    We deliberately do NOT include start_time. Aggregators (Park Record,
    Google Events) often have empty or wrong times for events that the
    venue-direct source (Egyptian Theatre) has correctly. Including time
    in the key would prevent the merge and we would see duplicate cards.

    Tradeoff: a venue running two different shows of the same act on the
    same date (8pm + 10:30pm separate ticketed sets) will collapse to one
    record. This is rare and the merged record retains the earlier time.

    Title normalization is aggressive — drops filler words ("tickets",
    "an evening with", "live", etc.) so aggregator titles collapse to the
    same key as venue-direct titles for the same show.
    """
    title = _normalize_title(e.get("title") or "")
    date = (e.get("date") or "")[:10]
    return (title, date)


def _fan_out_recurring(events):
    """Expand multi-day and recurring events into one record per occurrence date.

    Two sources of "occurs on multiple days" data:
    1. occurrence_dates: explicit list (set by enrichers for 'every Saturday' patterns).
    2. end_date > date: continuous date range (e.g. 'July 23 through August 1').
    Each fanned-out copy becomes a single-day event. Dedup key is (title, date)
    so siblings don't collapse.
    """
    from datetime import datetime, timedelta
    import re as _rec_re
    result = []
    fanned = 0
    _WEEKDAY_IDX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                    "Friday": 4, "Saturday": 5, "Sunday": 6}
    _MONTH_IDX = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                  "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10,
                  "nov": 11, "dec": 12, "january": 1, "february": 2, "march": 3,
                  "april": 4, "june": 6, "july": 7, "august": 8, "september": 9,
                  "october": 10, "november": 11, "december": 12}
    _DATE_PAIR_RE = _rec_re.compile(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\s+(\d{1,2})\b",
        _rec_re.IGNORECASE,
    )
    for e in events:
        # If recurrence_text contains an explicit list of dates ("May 29, June
        # 12, July 10, August 14, September 18"), parse them deterministically
        # and use them instead of any LLM-generated occurrence_dates. LLMs
        # truncate enumerated lists (Princess Pirate Train listed 5 dates but
        # the LLM only populated 4). Only fires when the regex finds MORE dates
        # than the LLM did, and at least 3 — avoids triggering on short text.
        rec_text = e.get("recurrence_text") or ""
        if rec_text:
            existing_occ = e.get("occurrence_dates") or []
            matches = _DATE_PAIR_RE.findall(rec_text)
            if len(matches) >= 3 and len(matches) > len(existing_occ):
                try:
                    base_year = int((e.get("date") or "")[:4])
                except (ValueError, TypeError):
                    base_year = None
                if base_year:
                    parsed = []
                    last_month = 0
                    year = base_year
                    for month_str, day_str in matches:
                        m = _MONTH_IDX.get(month_str.lower())
                        if not m:
                            continue
                        d = int(day_str)
                        # If we see a month going backwards, roll year forward
                        # (handles Dec 31 -> Jan 1 of next year cases).
                        if last_month and m < last_month:
                            year += 1
                        last_month = m
                        try:
                            iso = datetime(year, m, d).date().isoformat()
                            parsed.append(iso)
                        except ValueError:
                            continue
                    # Dedupe while preserving order
                    seen = set()
                    parsed_unique = [d for d in parsed if not (d in seen or seen.add(d))]
                    if len(parsed_unique) > len(existing_occ):
                        e["occurrence_dates"] = parsed_unique
        # If a record has structured weekly recurrence fields, compute its
        # occurrence_dates deterministically and override any LLM-generated
        # list. LLMs sometimes truncate (e.g. stopping at Aug 22 for a
        # May 30 - Sep 19 series); deterministic computation captures every
        # matching weekday in range.
        rec = (e.get("recurrence") or "")
        # Defensive: a one-time event mis-tagged weekly (e.g. "Deer Creek Half
        # Marathon" on a Saturday) must NOT fan out — especially open-ended
        # (no end_date), where it would project months of phantom occurrences.
        # Skip projection when the title looks like a single-occurrence event
        # AND there's no explicit end_date to bound it.
        _title_lo = (e.get("title") or "").lower()
        _ONE_TIME = ("marathon", "half marathon", " 5k", " 10k", "10k ", "5k ",
                     " race", "race ", "fun run", " ultra", " triathlon")
        if (rec in ("weekly", "weekly_multiple") and not e.get("end_date")
                and any(p in _title_lo for p in _ONE_TIME)):
            rec = ""  # treat as non-recurring; falls through to single event
        if rec in ("weekly", "weekly_multiple"):
            day_str = e.get("recurrence_day") or e.get("recurrence_days") or ""
            target_indices = set()
            for d in day_str.replace("|", ",").split(","):
                idx = _WEEKDAY_IDX.get(d.strip())
                if idx is not None:
                    target_indices.add(idx)
            if target_indices:
                try:
                    sd = datetime.strptime((e.get("date") or "")[:10], "%Y-%m-%d").date()
                    # Open-ended weekly events (e.g. VPC API "Yoga every Thursday"
                    # with no endDate) project 180 days forward. Each scrape
                    # regenerates from source, so cancelled events self-correct;
                    # the 60-occurrence cap below is the hard backstop.
                    # Bound the projection. Prefer an explicit end_date; else,
                    # if the scraper already gave an occurrence list, trust its
                    # LAST date as the end so we never invent phantom weeks past
                    # the real run (the Heber market is Jun 11-Aug 20, not out to
                    # December). Only truly list-less events project 180 days.
                    _occ_existing = [o for o in (e.get("occurrence_dates") or []) if o]
                    if e.get("end_date"):
                        ed = datetime.strptime(e["end_date"][:10], "%Y-%m-%d").date()
                    elif _occ_existing:
                        ed = max(datetime.strptime(o[:10], "%Y-%m-%d").date() for o in _occ_existing)
                    else:
                        ed = datetime.now().date() + timedelta(days=180)
                    cap_end = datetime.now().date() + timedelta(days=365)
                    if ed > cap_end:
                        ed = cap_end
                    computed = []
                    d = sd
                    while d <= ed and len(computed) < 60:
                        if d.weekday() in target_indices:
                            computed.append(d.isoformat())
                        d += timedelta(days=1)
                    if computed:
                        e["occurrence_dates"] = computed
                except (ValueError, TypeError):
                    pass
        occ = e.get("occurrence_dates") or []
        end_date = e.get("end_date")
        start_date = (e.get("date") or "")[:10]
        if occ:
            _series_end = max([o[:10] for o in occ if o] + ([end_date[:10]] if end_date else []))
            for d in occ:
                copy = dict(e)
                copy["date"] = d
                copy["end_date"] = None
                copy.pop("occurrence_dates", None)
                copy["series_end"] = _series_end  # last date of the series (survives fan-out)
                result.append(copy)
            fanned += 1
        elif end_date and start_date and end_date > start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                if (end - start).days > 60:
                    result.append(e)
                    continue
                d = start
                while d <= end:
                    copy = dict(e)
                    copy["date"] = d.isoformat()
                    copy["end_date"] = None
                    copy["series_end"] = end.isoformat()  # last date of the run (survives fan-out)
                    result.append(copy)
                    d += timedelta(days=1)
                fanned += 1
            except (ValueError, TypeError):
                result.append(e)
        elif (e.get("recurrence") or "").startswith("monthly_nth_") and (
            e.get("recurrence_day") or e.get("recurrence_days")
        ):
            # Monthly Nth weekday recurrence (e.g. "3rd Thursday of every month").
            # Expand to 12 occurrences over the next ~13 months, skipping any
            # occurrence before the event's own start_date.
            try:
                rec_type = e.get("recurrence") or ""
                ord_part = rec_type[len("monthly_nth_"):]
                # Ordinal can be a digit ("1"-"5") or "last"
                if ord_part == "last":
                    ordinal = "last"
                else:
                    ordinal = int(ord_part)
                day_str = e.get("recurrence_day") or (e.get("recurrence_days") or "").split(",")[0].strip()
                _DAY_IDX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                            "Friday": 4, "Saturday": 5, "Sunday": 6}
                target_weekday = _DAY_IDX.get(day_str)
                if target_weekday is None:
                    result.append(e)
                    continue
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                # Walk forward 13 months
                emitted = 0
                year, month = start.year, start.month
                for _ in range(13):
                    # Find the nth (or last) target_weekday in this (year, month)
                    if ordinal == "last":
                        # Start from last day of month, walk backward
                        if month == 12:
                            next_first = datetime(year + 1, 1, 1).date()
                        else:
                            next_first = datetime(year, month + 1, 1).date()
                        d = next_first - timedelta(days=1)
                        while d.weekday() != target_weekday:
                            d -= timedelta(days=1)
                    else:
                        # First of month, find first occurrence of target_weekday, add (ordinal-1) weeks
                        first = datetime(year, month, 1).date()
                        offset = (target_weekday - first.weekday()) % 7
                        d = first + timedelta(days=offset + 7 * (ordinal - 1))
                        # Sanity: d should still be in (year, month)
                        if d.month != month:
                            # No Nth weekday in this month (e.g. "5th Friday" in a short month)
                            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
                            continue
                    if d >= start:
                        copy = dict(e)
                        copy["date"] = d.isoformat()
                        copy["end_date"] = None
                        result.append(copy)
                        emitted += 1
                    year, month = (year, month + 1) if month < 12 else (year + 1, 1)
                if emitted:
                    fanned += 1
                else:
                    result.append(e)
            except (ValueError, TypeError, KeyError):
                result.append(e)
        else:
            result.append(e)
    if fanned:
        print(f"  Fanned out {fanned} multi-day/recurring events ({len(events)} -> {len(result)})")
    return result


import re as _re_pricing

# Ticket platforms whose presence in a link strongly implies a paid event.
_TICKET_PLATFORMS = (
    "holdmyticket", "eventbrite", "showpass", "etix", "seetickets",
    "axs.com", "ticketmaster", "tickets.", "/tickets", "eventticketscenter",
)
# "free" used as a real admission signal, with word boundaries. We require a
# nearby admission-context word to avoid "freestyle", "freedom", "feel free".
_FREE_RE = _re_pricing.compile(
    r"\bfree\b(?!\s*(?:style|dom|s\b))", _re_pricing.I
)
_FREE_CONTEXT = (
    "admission", "free event", "free show", "free concert", "free activity",
    "free craft", "free live", "is free", "and free", "free and open",
    "free to attend", "no charge", "no cost", "free entry", "free monthly",
    "free weekly", "free community", "free,", "free.", "free!", "free and open",
    "admission is free", "no admission",
)
_FREE_FALSE = ("freestyle", "freedom", "feel free", "frees ", "gluten-free", "free parking", "traffic-free", "smoke-free", "car-free", "hands-free")

# A dollar amount in the text ("$5 per person", "Cost is $48", "Pricing: $25")
# is a strong paid signal.
_PRICE_RE = _re_pricing.compile(r"\$\s?\d{1,4}(?:\.\d{2})?\b")

# Sources whose events are essentially always free community programming.
_FREE_SOURCES = {
    "Park City Farmers Market", "Mountain Trails Foundation",
}

# Sources that are essentially always ticketed/paid (concerts, races, motorsports).
_PAID_SOURCES = {
    "Deer Valley Music Festival", "Grand Teton Music Festival",
    "The Grand Teton Music Festival",
    "Road America",          # motorsports — paid admission/tickets
    "RunSignup",             # race registration — entry fee
    "Salt Lake Running Co",  # race registration — entry fee
}


import datetime as _dt_span

# Try to recover an explicit end day from a title like "July 16-18, 2026" or
# "May 29 - June 2". Returns an ISO date string or None.
_TITLE_RANGE_RE = _re_pricing.compile(
    r"([A-Z][a-z]+)\s+(\d{1,2})\s*[-–]\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2})",
)
_MONTHS_SPAN = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june","july","august",
     "september","october","november","december"], start=1)}


def _recover_end_from_title(title: str, start_iso: str):
    m = _TITLE_RANGE_RE.search(title or "")
    if not m:
        return None
    mon1, d1, mon2, d2 = m.group(1), m.group(2), m.group(3), m.group(4)
    end_mon = (mon2 or mon1).lower()
    if end_mon not in _MONTHS_SPAN:
        return None
    try:
        year = int(start_iso[:4])
        end = _dt_span.date(year, _MONTHS_SPAN[end_mon], int(d2))
        start = _dt_span.date.fromisoformat(start_iso[:10])
        # If recovered end is before start, it likely rolled into next year.
        if end < start:
            end = _dt_span.date(year + 1, _MONTHS_SPAN[end_mon], int(d2))
        # Only accept if it's a sane multi-day span (<= 31 days).
        if 0 <= (end - start).days <= 31:
            return end.isoformat()
    except (ValueError, TypeError):
        return None
    return None


# Maximum plausible span (days) for a single discrete event card. Beyond this,
# an end_date is almost certainly a parse error or a recurring/ongoing program
# mis-captured as one event. We try to recover from the title, else drop it.
_MAX_EVENT_SPAN_DAYS = 31


def _sanitize_span(record: dict) -> dict:
    start = (record.get("date") or "")[:10]
    end = (record.get("end_date") or "")[:10]
    if not start or not end or end == start:
        return record
    try:
        d1 = _dt_span.date.fromisoformat(start)
        d2 = _dt_span.date.fromisoformat(end)
    except ValueError:
        return record
    span = (d2 - d1).days
    if span < 0:
        # end before start — bogus, drop end_date
        record["end_date"] = None
        return record
    if span <= _MAX_EVENT_SPAN_DAYS:
        return record  # plausible multi-day event, keep
    # Implausible span: try to recover the true end from the title.
    recovered = _recover_end_from_title(record.get("title", ""), start)
    if recovered:
        record["end_date"] = recovered
    else:
        # Can't recover — treat as single-day so it doesn't smear across months.
        record["end_date"] = None
    return record


# Known single-venue sources where the source name == the venue, with a
# fixed real address. When a record from one of these sources lacks an
# address, we stamp the canonical one. Verified against official sources
# (Yelp / Google / venue websites).
_SINGLE_VENUE_ADDRESSES = {
    "The Osthoff Resort": {
        "venue_name": "The Osthoff Resort",
        "address": "101 Osthoff Avenue, Elkhart Lake, WI 53020",
    },
    "Grand Targhee Resort": {
        "venue_name": "Grand Targhee Resort",
        "address": "3300 E Ski Hill Road, Alta, WY 83414",
    },
    "Jackson Hole Mountain Resort": {
        "venue_name": "Jackson Hole Mountain Resort",
        "address": "3395 Cody Lane, Teton Village, WY 83025",
    },
    "National Museum of Wildlife Art": {
        "venue_name": "National Museum of Wildlife Art",
        "address": "2820 Rungius Road, Jackson, WY 83001",
    },
}

# Title-prefix-keyed venue lookup. When the event TITLE indicates a
# known race/series, stamp the canonical venue + address even if the source
# scraper didn't include them. Universal across all sources.
_TITLE_VENUE_LOOKUP = (
    # (substring to match in title.lower(), venue_name, address)
    ("park city trail series", "Quinn's Junction Trailhead",
     "425 Gillmor Way, Park City, UT 84060"),
)


_VENUE_NAME_ADDRESSES = {
    "Road America": "N7390 US-12, Elkhart Lake, WI 53020",
    "Siebkens Resort": "284 S Lake Street, Elkhart Lake, WI 53020",
    "The Osthoff Resort": "101 Osthoff Avenue, Elkhart Lake, WI 53020",
    "Osthoff Lake Deck": "101 Osthoff Avenue, Elkhart Lake, WI 53020",
    "Vintage Elkhart Lake": "100 East Rhine Street, Elkhart Lake, WI 53020",
    "Throttlestop": "20 Victory Lane, Elkhart Lake, WI 53020",
    "The Tiki Bar at Elkhart Lake Beach Resort": "276 Victorian Village Drive, Elkhart Lake, WI 53020",
    "Lake Street Cafe": "Lake Street, Elkhart Lake, WI 53020",
    "Swaner Preserve and EcoCenter": "1258 Center Drive, Park City, UT 84098",
    "Swaner Preserve & EcoCenter": "1258 Center Drive, Park City, UT 84098",
    "Park City Library": "1255 Park Avenue, Park City, UT 84060",
    "Walk Festival Hall": "3330 Cody Lane, Teton Village, WY 83025",
    "Snow King Mountain": "402 E Snow King Avenue, Jackson, WY 83001",
}


_VENUE_ALIASES = {
    "goldener hirsch, auberge collection": "Goldener Hirsch",
    "blair education center - intermountain park city hospital": "Blair Education Center at Intermountain Park City Hospital",
    "alpine park city social aid & pleasure club": "Park City Social Aid & Pleasure Club",
    "swaner preserve and ecocenter": "Swaner Preserve & EcoCenter",
}


def _norm_venue_key(name: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (name or "").strip().lower())


def _strip_venue_promoter(name: str) -> str:
    """Drop a leading '<promoter> Presents <:|-|/>' label some feeds bake into
    venue_name (e.g. 'Grand Valley Bank Presents / Jazz In City Park')."""
    import re as _re
    m = _re.match(r"^.{0,80}?\bpresents\b\s*[:/-]\s*(.+)$", name or "", _re.I)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return name


def _canonicalize_venue(record: dict) -> int:
    """Normalize venue_name in place: strip a promoter prefix, then map a known
    same-place alias to one canonical name. Returns 1 if changed, else 0."""
    vn = (record.get("venue_name") or "").strip()
    if not vn:
        return 0
    cleaned = _strip_venue_promoter(vn)
    canon = _VENUE_ALIASES.get(_norm_venue_key(cleaned), cleaned)
    if canon != record.get("venue_name"):
        record["venue_name"] = canon
        return 1
    return 0


def _apply_single_venue_lookup(record: dict) -> dict:
    """Fill address from known-venue lookup tables. Source-keyed first, then
    venue_name-keyed. Never overwrites existing fields."""
    src = record.get("source") or ""
    if src in _SINGLE_VENUE_ADDRESSES:
        info = _SINGLE_VENUE_ADDRESSES[src]
        if not record.get("address"):
            record["address"] = info["address"]
        if not record.get("venue_name"):
            record["venue_name"] = info["venue_name"]
    if not record.get("address"):
        venue = (record.get("venue_name") or "").strip()
        if venue and venue in _VENUE_NAME_ADDRESSES:
            record["address"] = _VENUE_NAME_ADDRESSES[venue]
    # Title-keyed lookup: catches recurring races scraped by multiple
    # sources where the source-specific scrapers don't all share venue logic
    # (e.g. Trail Series 5K via MTF gets Quinn's Junction, but 10K/Half via
    # Salt Lake Running Co does not — this universalizes it).
    if not record.get("address"):
        title_lo = (record.get("title") or "").lower()
        for needle, venue, address in _TITLE_VENUE_LOOKUP:
            if needle in title_lo:
                if not record.get("venue_name"):
                    record["venue_name"] = venue
                record["address"] = address
                break
    return record


def _derive_address(record: dict) -> dict:
    """Populate the structured `address` field from `location` when possible.

    Many scrapers put the full street address in `location` only (e.g.
    "The Cloudveil, 112 Center ST, Jackson, WY" or "101 Osthoff Avenue,
    Elkhart Lake, WI"). For schema.org SEO and a consistent data model, we
    want the structured `address` field populated too. Conservative: only
    fills when location looks like it contains a real street (has a digit
    followed by a street word, or matches an obvious street pattern). Never
    overwrites an existing address.
    """
    if record.get("address"):
        return record  # already has structured address
    loc = (record.get("location") or "").strip()
    if not loc:
        return record
    # Strip the venue_name prefix if it's at the front of location.
    venue = (record.get("venue_name") or "").strip()
    candidate = loc
    if venue and candidate.lower().startswith(venue.lower()):
        candidate = candidate[len(venue):].lstrip(",").strip()
    # If after stripping the venue we have a comma-separated string,
    # candidate looks like "123 Street, City, ST 12345". Confirm it has
    # something that looks like a street number or a PO/route designator.
    has_street_signal = bool(_re_addr_street.search(candidate))
    if has_street_signal and "," in candidate:
        record["address"] = candidate
    return record


_re_addr_street = _re_pricing.compile(
    # A digit followed by a word, OR a route/PO style identifier (US-12, N7390),
    # OR explicit street words preceded by a number.
    r"\b(?:\d+\s+[A-Za-z]|[NSEW]\d{2,5}\b|\bUS-\d+|\bP\.?O\.? Box\b|"
    r"\bRoute\s+\d+|\bRd\b|\bSt\b|\bSt\.|\bStreet\b|\bAvenue\b|"
    r"\bAve\b|\bAve\.|\bBoulevard\b|\bBlvd\b|\bDrive\b|\bDr\b|\bDr\.|"
    r"\bLane\b|\bLn\b|\bWay\b|\bParkway\b|\bPkwy\b|\bCircle\b|\bCt\b)",
    _re_pricing.I,
)


def _infer_pricing(record: dict) -> dict:
    """Set is_free / price when a confident signal exists; leave unset otherwise.

    Conservative: only tags when there's a clear signal. Existing values win.
    """
    if "is_free" in record or record.get("price"):
        return record  # already has pricing info — don't override

    link = (record.get("link") or "").lower()
    text = ((record.get("title") or "") + " " + (record.get("description") or "")).lower()
    source = record.get("source", "")

    # Paid signal: a real ticketing-platform link.
    if any(tp in link for tp in _TICKET_PLATFORMS):
        record["is_free"] = False
        return record

    # Paid signal: a categorically ticketed source.
    if source in _PAID_SOURCES:
        record["is_free"] = False
        return record

    # Paid signal: an explicit dollar amount in the text (e.g. "$5 per person",
    # "Cost is $48"). A "$0" or "$0.00" is actually free, so guard against that.
    price_m = _PRICE_RE.search(text)
    if price_m and price_m.group(0).replace("$", "").replace(" ", "") not in ("0", "0.00"):
        record["is_free"] = False
        return record

    # Race-distance guard: titles like "5K", "10K", "Half Marathon", or
    # "Marathon" imply a paid race registration, even when the source (e.g.
    # Mountain Trails Foundation) is otherwise mostly free. Don't auto-tag
    # these as free.
    title_lo = (record.get("title") or "").lower()
    if _re_pricing.search(r"\b(\d+\s?k|\d+\s?mile|half\s+marathon|marathon|ultra|fun\s+run|trail\s+(run|race|series|challenge)|hill\s+climb|rambler|relay|duathlon|triathlon)\b", title_lo):
        record["is_free"] = False
        return record

    # Free signal: known-free source, or "free" with admission context and no
    # false-positive phrase.
    if source in _FREE_SOURCES:
        record["is_free"] = True
        record["price"] = "Free"
        return record

    if any(fp in text for fp in _FREE_FALSE):
        return record  # ambiguous — skip
    if _FREE_RE.search(text) and any(ctx in text for ctx in _FREE_CONTEXT):
        record["is_free"] = True
        record["price"] = "Free"
        return record

    return record


def _backfill_venue(record: dict) -> dict:
    """If venue_name is missing or looks like an address, resolve via venues.ts."""
    current_venue = (record.get("venue_name") or "").strip()
    looks_like_address = current_venue and current_venue[:1].isdigit()
    if not current_venue or looks_like_address:
        for candidate in [current_venue, record.get("location"), record.get("address")]:
            if not candidate:
                continue
            resolved_name, _ = lookup_venue_by_address(candidate)
            if resolved_name:
                record["venue_name"] = resolved_name
                break
    return record


def _clean_display_text(s: str) -> str:
    """Strip HTML tags + unescape HTML and URL/percent encoding for user-facing text."""
    import re as _re, html as _html
    from urllib.parse import unquote as _unquote
    if not s:
        return s
    # Decode percent-encoding (%26 -> &, %20 -> space) only if it looks encoded,
    # to avoid mangling legitimate % signs (e.g. "20% off").
    if _re.search(r"%[0-9A-Fa-f]{2}", s):
        s = _unquote(s)
    s = _html.unescape(s)                   # &amp; -> &, &#39; -> '
    s = _re.sub(r"<[^>]+>", "", s)          # remove HTML tags
    s = _re.sub(r"\s+", " ", s).strip()    # collapse whitespace
    return s


_DISPLAY_MONTHS = {"january","february","march","april","may","june","july",
    "august","september","october","november","december","jan","feb","mar",
    "apr","jun","jul","aug","sep","sept","oct","nov","dec"}


def _strip_title_year(t: str) -> str:
    """Drop a leading aggregator year prefix from a DISPLAY title. Conservative:
    only when 2+ words remain and the next word isn't a month/number."""
    import re as _re
    m = _re.match(r"^(20\d\d)\s+(.+)$", t or "")
    if not m:
        return t
    rest = m.group(2).strip()
    words = rest.split()
    if len(words) < 2:
        return t
    nxt = words[0].lower().strip(".,")
    if nxt in _DISPLAY_MONTHS or nxt.isdigit():
        return t
    return rest


def _best_display_title(records: list) -> str:
    """Among records merged into one event, pick the cleanest title: prefer one
    WITHOUT a '<promoter> Presents' prefix, then the shortest (least cruft)."""
    import re as _re
    titles = [(_r.get("title") or "").strip() for _r in records]
    titles = [t for t in titles if t]
    if not titles:
        return ""
    def _score(t):
        has_promoter = 1 if _re.match(r"^.{0,80}?\bpresents\b\s*[:/-]", t, _re.I) else 0
        return (has_promoter, len(t))
    return min(titles, key=_score)


def _normalize_image_url(url: str) -> str:
    """Bump earthdiver Cloudflare image-transform width so schema images clear
    Google's 720px rich-result minimum. CF clamps to the asset's native width,
    so this never upscales: small originals stay small, larger ones get bigger.
    Scoped to the earthdiver cdn-cgi path on purpose (width= is a path option
    there in our data, not a generic query param)."""
    import re as _re
    if not url:
        return url
    if "earthdiver.com/cdn-cgi/image/" not in url:
        return url
    return _re.sub(r"width=\d+", "width=1200", url, count=1)


# Module-level source priority. Used by merge_events when dedup groups
# disagree on a field — the lower-priority source's value loses. Default
# for unknown sources is Tier 2
# equivalent — a source we haven't classified is usually a venue/organizer
# worth trusting more than a third-party aggregator.
SOURCE_PRIORITY = {
    # Tier 1: verified venue or primary organizer
    "Oakley City": 1, "Eccles Center": 1, "Park City Institute": 1,
    "Deer Valley Resort": 1, "Park City Mountain": 1,
    "Deer Valley Music Festival": 1, "Grand Teton Music Festival": 1,
    "The Grand Teton Music Festival": 1,
    "The Cloudveil": 1, "The Osthoff Resort": 1, "Siebkens Resort": 1,
    "Road America": 1, "National Museum of Wildlife Art": 1,
    "Center for the Arts Jackson Hole": 1, "Park City Opera": 1,
    "Park City Song Summit": 1, "Park City Farmers Market": 1,
    "Mountain Trails Foundation": 1, "Village of Elkhart Lake": 1,
    "Egyptian Theatre": 1,
    "Park City Film": 1,
    "Wasatch County Parks & Rec": 1,
    # Tier 2: trusted aggregator / tourism board / local newspaper
    "The Park Record": 2, "Park City Annual Events": 2,
    # Chambers/tourism boards are primary sources — outrank The Park Record
    # (which republishes the nowplayingutah aggregator, often with wrong times).
    "Heber Valley Tourism": 1,
    "Visit Park City": 2, "Visit Park City (sitemap)": 2,
    "Mountain Town Music": 2,
    "Jackson Hole Chamber of Commerce": 2, "Elkhart Lake Tourism": 2,
    "RunSignup": 2, "Salt Lake Running Co": 2,
    "Park City Gallery Association": 2,
    # Tier 3: community calendar / non-canonical local source
    "KPCW Community Calendar": 3, "Heber Valley Life": 3,
    # Tier 4: third-party aggregator (never overrides Tier 1-3 fields)
    "Google Events": 4, "Eventbrite": 4, "Bandsintown": 4,
    "EventTicketsCenter": 4,
}

DEFAULT_PRIORITY = 3  # unknown source -> assume community calendar tier


def _venue_consistent_with_address(venue: str, location: str, address: str) -> bool:
    """True if venue_name plausibly matches the event's own location/address text.
    Used to reject a merged venue_name that contradicts the event's real place
    (e.g. venue 'Park City Mountain' on an event whose address is 'Main Street')."""
    if not venue:
        return True
    v = _normalize_venue(venue)
    if not v:
        return True
    hay = _normalize_venue(((location or "") + " " + (address or "")))
    if v in hay:
        return True
    # Or a meaningful (len>4) token of the venue appears in the location/address.
    return any(tok in hay for tok in v.split() if len(tok) > 4)


def merge_events(records: list[dict]) -> dict:
    """When multiple records dedupe to the same key, pick the best fields."""
    if len(records) == 1:
        _r = _sanitize_span(_infer_pricing(_derive_address(_apply_single_venue_lookup(_backfill_venue(dict(records[0]))))))
        _r["title"] = _strip_title_year(_clean_display_text(_r.get("title", "")))
        if _r.get("description"):
            _r["description"] = _clean_display_text(_r["description"])
        if _r.get("image_url"):
            _r["image_url"] = _normalize_image_url(_r["image_url"])
        return _r
    
    # Sort by source priority (lower = better). Constants are module-level.
    records.sort(key=lambda r: SOURCE_PRIORITY.get(r.get("source", ""), DEFAULT_PRIORITY))
    
    base = dict(records[0])  # highest-priority record wins as base
    
    # Fill in missing fields from lower-priority records
    for r in records[1:]:
        for key in ["description", "start_time", "end_time", "address",
                    "venue_name", "image_url", "link", "lat", "lng"]:
            if not base.get(key) and r.get(key):
                base[key] = r[key]
        # Merge categories
        cats = set(base.get("categories") or [])
        cats.update(r.get("categories") or [])
        if cats:
            base["categories"] = sorted(cats)
        # Track all sources
        srcs = set(base.get("_all_sources") or [base.get("source", "")])
        srcs.add(r.get("source", ""))
        srcs.discard("")
        base["_all_sources"] = sorted(srcs)

    # --- cross-source conflict detection -------------------------------
    # When sources disagree on a user-facing field, we surface the conflict
    # rather than silently trusting one. Record each distinct value with its
    # source so the modal can show "Source A: X / Source B: Y".
    def _src_priority(rec):
        return SOURCE_PRIORITY.get(rec.get("source", ""), DEFAULT_PRIORITY)

    def _collect(field):
        vals = {}
        for r in records:
            v = r.get(field)
            v = (str(v).strip() if v is not None else "")
            if v:
                vals.setdefault(v, r.get("source", "?"))
        return vals  # value -> first source that reported it

    _conflicts = {}
    for field, label in (("start_time", "time"), ("date", "date"),
                         ("venue_name", "venue"), ("price", "price")):
        vals = _collect(field)
        if len(vals) > 1:
            _conflicts[label] = [{"value": v, "source": src}
                                 for v, src in vals.items()]

    # price conflict also covers free-vs-paid disagreement
    _free_vals = {bool(r.get("is_free")) for r in records if "is_free" in r}
    if len(_free_vals) > 1 and "price" not in _conflicts:
        _conflicts["price"] = [
            {"value": ("Free" if r.get("is_free") else (r.get("price") or "Paid")),
             "source": r.get("source", "?")}
            for r in records if "is_free" in r or r.get("price")]

    if _conflicts:
        base["_conflicts"] = _conflicts
        # TIME certainty: certain if a Tier-1 (direct/venue) source gave a time,
        # even if an aggregator disagrees. Otherwise (only aggregators, and they
        # conflict) the time is uncertain -> frontend hides it on the card.
        if "time" in _conflicts:
            tier1_has_time = any(
                _src_priority(r) == 1 and (r.get("start_time") or "").strip()
                for r in records)
            base["_time_uncertain"] = not tier1_has_time
            # when time conflicts, keep BOTH links so user can verify each source
            links = []
            for r in sorted(records, key=_src_priority):
                lk = r.get("link")
                if lk and lk not in [x["url"] for x in links]:
                    links.append({"url": lk, "source": r.get("source", "?")})
            if len(links) > 1:
                base["_source_links"] = links

    # Venue sanity: the priority source's venue_name can contradict the event's
    # own address (same event reported by multiple sources; one mis-tags the
    # venue, e.g. 'Park City Mountain' on a Main Street event). If the chosen
    # venue_name appears nowhere in the merged location/address, prefer a
    # conflicting venue value that IS consistent; if none, clear it so display
    # falls back to the (correct) location. Only fires on contradictions, so
    # events whose venue matches their address are untouched.
    _bv = base.get("venue_name")
    if _bv and not _venue_consistent_with_address(_bv, base.get("location"), base.get("address")):
        _alt = None
        for _v in _collect("venue_name"):
            if _venue_consistent_with_address(_v, base.get("location"), base.get("address")):
                _alt = _v
                break
        base["venue_name"] = _alt  # consistent alternative, or None to fall back to location

    base = _sanitize_span(_infer_pricing(_derive_address(_apply_single_venue_lookup(_backfill_venue(base)))))
    base["title"] = _strip_title_year(_clean_display_text(_best_display_title(records) or base.get("title", "")))
    if base.get("description"):
        base["description"] = _clean_display_text(base["description"])
    if base.get("image_url"):
        base["image_url"] = _normalize_image_url(base["image_url"])
    return base


def _too_far_to_merge(a: dict, b: dict, max_miles: float = 15.0) -> bool:
    """True if a and b have coordinates and are more than max_miles apart.

    Distance is a hard veto on merging: two events that far apart are not the
    same event no matter how similar their titles. Used by every merge pass
    (prefix, fuzzy, link) so a cross-city title collision (e.g. Park City
    "Savor the Summit" vs a Jackson event titled "Savor", 200mi apart) can
    never collapse into one record through ANY path. Missing coords -> returns
    False (can't prove distance; preserves old behavior for coordless records).
    """
    la, lna, lb, lnb = a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng")
    if all(v is not None for v in (la, lna, lb, lnb)):
        try:
            return haversine_miles(float(la), float(lna), float(lb), float(lnb)) > max_miles
        except (ValueError, TypeError):
            return False
    return False


def _prefix_merge(events: list[dict]) -> list[dict]:
    """Second-pass dedup for suffix-variant dupes the (title,date) key misses.

    Merges when one normalized title is a strict STRING-PREFIX of another on the
    same date. String-prefix (not token-subset) is deliberate: it only fires when
    one title is literally the start of the other, so descriptive fluff suffixes
    collapse but events that diverge mid-string stay separate.

    MERGES:  "the babys" ⊂ "the babys residency ut"
             "downtown night" ⊂ "downtown night a taste of elkhart lake"
             "latino arts festival" ⊂ "latino arts festival june 12 14 2026"
    KEEPS:   "high uinta half marathon 5k" vs "...half marathon" (diverge at 5k)
             "runtastic heber 5k" vs "runtastic heber half marathon"
    (Same-name races at different distances stay as separate cards so no
    distance is hidden inside a merged title.)
    """
    from collections import defaultdict
    import re as _re
    by_date = defaultdict(list)
    for e in events:
        by_date[(e.get("date") or "")[:10]].append(e)

    out = []
    absorbed = 0
    for _date, group in by_date.items():
        norms = [_normalize_title(e.get("title") or "") for e in group]
        dropped = [False] * len(group)
        for i in range(len(group)):
            if dropped[i] or not norms[i]:
                continue
            for j in range(len(group)):
                if i == j or dropped[j] or not norms[j]:
                    continue
                a, b = norms[i], norms[j]
                # Don't merge across race-distance variants — keep each distance
                # as its own card (e.g. "Round Valley Rambler 7K" must NOT absorb
                # into "Round Valley Rambler 7K Half Marathon"). The suffix that
                # distinguishes a from b is what matters.
                # Block merge only when the TERSER title (b) is itself race-like:
                # then the longer one is just another distance and must stay a
                # separate card ("Round Valley Rambler 7K" vs "...7K Half Marathon").
                # A festival whose name has no race word (e.g. "Red White and Blue
                # Festival") still absorbs a race sub-event suffix -> merge.
                _race_re = r"\b(\d+\s*k|\d+\s*mile|half marathon|marathon)\b"
                _b_is_race = _re.search(_race_re, b)
                # b is a strict string-prefix of a, and b is not itself a race
                # listing -> b is the terser duplicate, merge it in.
                if a != b and a.startswith(b + " ") and not _b_is_race:
                    if _too_far_to_merge(group[i], group[j]):
                        continue  # different cities -> not the same event
                    group[i] = merge_events([group[i], group[j]])
                    norms[i] = _normalize_title(group[i].get("title") or "")
                    dropped[j] = True
                    absorbed += 1
        out.extend(e for k, e in enumerate(group) if not dropped[k])

    if absorbed:
        print(f"  [prefix-merge] absorbed {absorbed} suffix-variant duplicates")
    return out


# Low-trust aggregators whose records should be suppressed when a higher-quality
# source already lists the same event. Google Events in particular has been
# observed mis-tagging dates (e.g. Mountain Valley Stampede Rodeo on Jul 29
# when the real run is Jul 30-Aug 1 per Heber Valley Tourism).
_LOW_TRUST_AGGREGATORS = {"Google Events", "Eventbrite", "Bandsintown", "EventTicketsCenter", "The Park Record"}


def _suppress_aggregator_dupes(events: list, window_days: int = 7) -> list:
    """Drop low-trust aggregator records that duplicate higher-quality sources.

    For each record from a _LOW_TRUST_AGGREGATORS source, check whether ANY
    other record with the same normalized title exists from a non-aggregator
    source within +/-window_days. If so, drop the aggregator record (its data
    is less reliable; better to show only the canonical source).

    Conservative: only operates on records FROM aggregator sources. Records
    between high-quality sources (Park Record, VPC, MTM, etc.) are completely
    untouched. Aggregator records with NO higher-quality counterpart are kept
    (Google Events sometimes has events nobody else covers).
    """
    from datetime import datetime as _dt, timedelta as _td
    from collections import defaultdict as _dd

    # Index ALL non-aggregator records by normalized title -> set of dates
    import re as _sup_re
    def _suppress_key(title):
        t = _normalize_title(title or "")
        t = _sup_re.sub(r"^(hebers|heber|park city|jacksons|jackson|midway|kamas|oakley)\b\s*", "", t)
        t = _sup_re.sub(r"^s\s+", "", t)
        return t.strip()
    high_trust_by_title = _dd(list)
    for e in events:
        src = e.get("source") or ""
        if src in _LOW_TRUST_AGGREGATORS:
            continue
        nt = _suppress_key(e.get("title") or "")
        d = e.get("date")
        if nt and d:
            try:
                high_trust_by_title[nt].append(_dt.fromisoformat(d))
            except ValueError:
                continue

    dropped_count = 0
    out = []
    pad = _td(days=window_days)
    for e in events:
        src = e.get("source") or ""
        if src not in _LOW_TRUST_AGGREGATORS:
            out.append(e)
            continue
        # Check if a high-trust source has this title near this date
        nt = _suppress_key(e.get("title") or "")
        d = e.get("date")
        if not nt or not d:
            out.append(e)
            continue
        try:
            event_date = _dt.fromisoformat(d)
        except ValueError:
            out.append(e)
            continue
        candidates = high_trust_by_title.get(nt, [])
        has_overlap = any(abs((c - event_date).days) <= window_days for c in candidates)
        if has_overlap:
            dropped_count += 1
            continue  # suppress this aggregator record
        out.append(e)

    if dropped_count:
        print(f"  [aggregator-suppress] dropped {dropped_count} low-trust dupes")
    return out


def _normalize_venue(venue: str) -> str:
    """Normalize a venue string for cross-source matching. Strips address
    suffix (anything after the first comma), lowercases, collapses whitespace,
    and folds 'theatre/theater' variants."""
    if not venue:
        return ""
    v = venue.split(",")[0].strip().lower()
    v = " ".join(v.split())  # collapse whitespace
    v = v.replace("theater", "theatre")  # canonical spelling
    return v


def _normalize_time(t: str) -> str:
    """Normalize a time string to 'HH:MM' 24h for matching. Returns empty
    if unparseable."""
    if not t:
        return ""
    import re as _re
    m = _re.match(r"^\s*(\d{1,2}):?(\d{2})?\s*(AM|PM)?\s*$", str(t), _re.IGNORECASE)
    if not m:
        return ""
    h = int(m.group(1))
    mn = int(m.group(2) or 0)
    ampm = (m.group(3) or "").upper()
    if ampm == "PM" and h != 12:
        h += 12
    elif ampm == "AM" and h == 12:
        h = 0
    if h > 23 or mn > 59:
        return ""
    return f"{h:02d}:{mn:02d}"


def _link_merge(events: list) -> list:
    """Same-date events pointing to the SAME registration/event link are the same
    event even when titles differ wildly ("Round Valley Rambler (7k & Half
    Marathon)" vs "RVR 1/2 Marathon & 7K Trail Run", both runttc.com; "Moose on
    the Loose Kid #1" vs "Moose on the Loose Kids Trail Race", both
    parkcityss.org/moose-on-the-loose). The link is a stronger, lower-risk signal
    than fuzzy title matching.

    Guard: do NOT merge a series UMBRELLA into one of its legs that shares the
    same landing page ("Triple Trail Challenge" vs its "Round Valley Rambler" leg
    on runttc.com). "Concert series" is exempt — it names a venue/recurring series
    of individual shows, not a multi-event umbrella."""
    import re as _re
    from collections import defaultdict as _dd
    _UMBRELLA = _re.compile(r"\b(series|challenge|triple|championship|grand slam|circuit|market|festival|fair|fest)\b")

    def _is_umbrella(t):
        t2 = _re.sub(r"concert series", "", t)
        return bool(_UMBRELLA.search(t2))

    def _norm_link(u):
        u = (u or "").strip().lower()
        if not u:
            return ""
        u = _re.sub(r"^https?://", "", u)
        u = _re.sub(r"^www\.", "", u)
        return u.rstrip("/")

    def _mergeable(a, b):
        ta, tb = _normalize_title(a.get("title") or ""), _normalize_title(b.get("title") or "")
        if not ta or not tb:
            return False
        if _is_umbrella(ta) != _is_umbrella(tb):
            return False
        return True

    by_key = _dd(list)
    passthrough = []
    for e in events:
        nl = _norm_link(e.get("link"))
        if nl:
            by_key[((e.get("date") or "")[:10], nl)].append(e)
        else:
            passthrough.append(e)

    out = list(passthrough)
    merged = 0
    for _key, group in by_key.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        kept = []
        used = [False] * len(group)
        for i in range(len(group)):
            if used[i]:
                continue
            cur = group[i]
            for j in range(i + 1, len(group)):
                if used[j]:
                    continue
                if _mergeable(cur, group[j]):
                    if _too_far_to_merge(cur, group[j]):
                        continue  # same link but far apart -> not the same event
                    cur = merge_events([cur, group[j]])
                    used[j] = True
                    merged += 1
            kept.append(cur)
        out.extend(kept)
    if merged:
        print(f"  [link-merge] merged {merged} same-date same-link duplicates")
    return out


def _cross_source_fuzzy_merge(events: list) -> list:
    """Same-date, cross-source near-duplicate titles that exact-match and
    _prefix_merge miss (word reorder, dropped/added leading word, curly-quote
    or em-dash punctuation, single-char typo). DIFFERENT sources only; token-set
    Jaccard >= 0.85; hard block when the symmetric token diff contains a
    race-distance or bare-number token (so '7K' vs 'Half Marathon' and different
    acts in a shared series stay separate). Winner via merge_events."""
    from collections import defaultdict as _dd
    import re as _re
    _RACE_NUM = _re.compile(r"^(\d+\s*k|\d+\s*mile|half|marathon|\d{2,4})$")

    def _compatible(t1, t2, same_venue=False, same_location=False):
        n1, n2 = _normalize_title(t1 or ""), _normalize_title(t2 or "")
        if not n1 or not n2:
            return False
        if n1 == n2:
            return True
        s1, s2 = set(n1.split()), set(n2.split())
        if not s1 or not s2:
            return False
        diff = s1 ^ s2
        if any(_RACE_NUM.match(tok) for tok in diff):
            return False
        # (a) high token-set overlap (reorder / one-word diff / punctuation)
        if len(s1 & s2) / len(s1 | s2) >= 0.75:
            return True
        # (b) full-subset case: one title's tokens are wholly contained in the
        # other (e.g. "Until Dawn" inside "...Live Music by Until Dawn", or
        # "Farmers & Artisans Market" inside "Elkhart Lake Farmers & Artisans
        # Market"). Jaccard is low here because the wrapper adds many tokens, but
        # it is the same event. Guard against generic short subsets ("Live
        # Music", "Concert") by requiring the SHORTER title to carry >= 2
        # distinctive (non-stopword) tokens.
        _STOP = {"the", "a", "an", "of", "by", "at", "in", "on", "and", "live",
                 "music", "event", "events", "series", "with", "to", "for"}
        small, big = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
        if small.issubset(big) and len(small - _STOP) >= 2:
            return True
        # (b2) same PRECISE location (<0.5mi, set by caller) + subset: when two
        # records sit at essentially the same coordinates on the same date and
        # one title's tokens subset the other's, they are the same event even if
        # only ONE distinctive token remains after stopwords. The tight location
        # match is the guard here (replacing the >=2-token rule that protects the
        # title-only case), so e.g. "Saturday Sunset Music Series" and "Heber's
        # Saturday Sunset Music Series" at the same park on the same date merge,
        # while generic-word collisions in DIFFERENT places never reach this branch.
        if same_location and small.issubset(big) and len(small - _STOP) >= 1:
            return True
        # Day-of-week words get stripped asymmetrically by _normalize_title
        # (leading day removed, mid-title day kept), so retry the subset test
        # with day names removed from both sides. Date already disambiguates
        # recurring events, so dropping the day word here is safe.
        _DOW = {"monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday"}
        sd_small = small - _DOW
        if sd_small and sd_small.issubset(big - _DOW) and len(sd_small - _STOP) >= 2:
            return True
        # (c) character-level near-identity: catches one-word typos
        # ('Tournament'/'Tounament'), curly-quote/plural variants ('Slow
        # Food'/'Slow Foods'), and preposition swaps ('from'/'of Little
        # Feat') that token-set Jaccard misses. High ratio only (>=0.90).
        # Guards: never bridge a cohort marker (men's vs women's, junior
        # vs senior) -- genuinely DIFFERENT events with near-identical
        # strings. Race/number diffs already rejected at top of _compatible.
        # Caller additionally restricts this to SAME-VENUE pairs.
        import difflib as _difflib
        _DISTINCT = {"men", "mens", "women", "womens", "boys", "girls",
                     "junior", "juniors", "senior", "seniors", "adult",
                     "adults", "kids", "youth", "beginner", "advanced",
                     "intermediate"}
        _diff = s1 ^ s2
        if same_venue and not (_diff & _DISTINCT) and \
                _difflib.SequenceMatcher(None, n1, n2).ratio() >= 0.90:
            return True
        return False

    by_date = _dd(list)
    for e in events:
        by_date[(e.get("date") or "")[:10]].append(e)
    out = []
    merged = 0
    for _date, group in by_date.items():
        dropped = [False] * len(group)
        for i in range(len(group)):
            if dropped[i]:
                continue
            for j in range(i + 1, len(group)):
                if dropped[j] or group[i].get("source") == group[j].get("source"):
                    continue
                # Geographic guard: two events far apart are NOT the same event,
                # no matter how similar their titles. Without this, generic-word
                # title overlap merges genuinely different events in different
                # cities (e.g. Park City's "Summer Yoga Festival" was absorbed
                # into Jackson's "Summer Festival" 200mi away). Only applies when
                # BOTH have coordinates; missing coords -> fall through to the
                # title check (preserves old behavior for coordless records).
                _la, _lna = group[i].get("lat"), group[i].get("lng")
                _lb, _lnb = group[j].get("lat"), group[j].get("lng")
                if all(v is not None for v in (_la, _lna, _lb, _lnb)):
                    try:
                        if haversine_miles(float(_la), float(_lna), float(_lb), float(_lnb)) > 15:
                            continue
                    except (ValueError, TypeError):
                        pass
                _vi = _normalize_venue(group[i].get("venue_name") or group[i].get("location") or "")
                _vj = _normalize_venue(group[j].get("venue_name") or group[j].get("location") or "")
                _same_venue = bool(_vi) and _vi == _vj
                # Precise co-location (<0.5mi): a strong same-event signal that
                # lets _compatible relax its distinctive-token requirement safely.
                _same_location = False
                if all(v is not None for v in (_la, _lna, _lb, _lnb)):
                    try:
                        _same_location = haversine_miles(float(_la), float(_lna), float(_lb), float(_lnb)) <= 0.5
                    except (ValueError, TypeError):
                        pass
                if _compatible(group[i].get("title"), group[j].get("title"),
                               same_venue=_same_venue, same_location=_same_location):
                    group[i] = merge_events([group[i], group[j]])
                    dropped[j] = True
                    merged += 1
        out.extend(e for k, e in enumerate(group) if not dropped[k])
    if merged:
        print(f"  [cross-source-merge] merged {merged} cross-source near-duplicates")
    return out


def _venue_time_dedup(events: list) -> list:
    """Collapse records sharing the same (normalized_venue, date, start_time).

    These are almost certainly the same real-world event under different
    titles -- e.g. 'Keller & The Keels' / 'Keller Williams & The Keels' /
    'Egyptian Theater - Keller & The Keels' all at Egyptian Theatre, May 29,
    8 PM. Different sources phrase event titles differently; venue + date +
    time is a reliable identity signal.

    Safety:
    - Requires all three keys present and parseable. Missing any -> record
      passes through unchanged. No collapse can fire on incomplete data.
    - Recurring events stay distinct because dates differ.
    - Same-venue same-day different-time events stay distinct (e.g. 6pm
      trivia + 8pm concert at one bar).

    Winner selection: highest SOURCE_PRIORITY (lowest priority number).
    Ties broken by description length (longer = more info).
    """
    from collections import defaultdict as _dd
    groups = _dd(list)
    untouchable = []
    for e in events:
        v = _normalize_venue(e.get("venue_name") or e.get("location") or "")
        d = (e.get("date") or "")[:10]
        t = _normalize_time(e.get("start_time") or "")
        if not v or not d or not t:
            untouchable.append(e)
            continue
        groups[(v, d, t)].append(e)

    out = list(untouchable)
    dropped = 0
    for key, members in groups.items():
        if len(members) == 1:
            out.append(members[0])
            continue
        # Same venue/date/time is a strong signal but NOT sufficient on its own:
        # two genuinely different events can share an arena and start time (e.g.
        # 'Mountain Valley Stampede Rodeo' and 'Mountain Valley Special Needs
        # Round Up Rodeo' both 7pm at the rodeo grounds). Only collapse members
        # whose titles are actually similar. Sub-group by title compatibility:
        # a member joins a bucket if its normalized title is a substring of, or
        # shares strong token overlap with, the bucket's representative.
        def _title_compatible(t1, t2):
            n1, n2 = _normalize_title(t1), _normalize_title(t2)
            if not n1 or not n2:
                return True  # can't judge -> allow (preserve old behavior)
            if n1 == n2 or n1 in n2 or n2 in n1:
                return True
            s1, s2 = set(n1.split()), set(n2.split())
            if not s1 or not s2:
                return True
            # Jaccard (intersection / UNION), not min-overlap. Min-overlap is
            # fooled by shared boilerplate: 'Mountain Valley Stampede Rodeo' vs
            # 'Mountain Valley Special Needs Round Up Rodeo' share 3 generic
            # tokens (mountain/valley/rodeo) = 0.75 by min, but the
            # distinguishing words differ entirely. Jaccard = 3/8 = 0.375,
            # correctly judging them DIFFERENT. Keller variant titles still
            # score high (mostly identical tokens) and merge.
            jaccard = len(s1 & s2) / len(s1 | s2)
            return jaccard >= 0.6
        buckets = []  # list of [representative_title, [members]]
        for e in members:
            placed = False
            for b in buckets:
                if _title_compatible(b[0], e.get("title") or ""):
                    b[1].append(e); placed = True; break
            if not placed:
                buckets.append([e.get("title") or "", [e]])
        for _rep, bucket_members in buckets:
            if len(bucket_members) == 1:
                out.append(bucket_members[0])
                continue
            bucket_members.sort(key=lambda r: (
                SOURCE_PRIORITY.get(r.get("source", ""), DEFAULT_PRIORITY),
                -len(r.get("description") or ""),
            ))
            out.append(bucket_members[0])
            dropped += len(bucket_members) - 1

    if dropped:
        print(f"  [venue-time-dedup] collapsed {dropped} same-venue same-time records")
    return out


def _venue_date_aggregator_suppress(events: list) -> list:
    """When a tier-1 or tier-2 source has ANY event at a venue on a date, drop
    every aggregator (tier-4) record at the same venue+date. Aggregators
    (Google Events, Bandsintown) frequently report the same event under
    different titles, times, or with missing fields -- the canonical source
    has the truth.

    Stronger than _suppress_aggregator_dupes which requires title match;
    this only needs venue+date overlap. Safe because tier-4 sources are by
    definition low-trust, and the venue/date check is a strong signal of
    same-event."""
    from collections import defaultdict as _dd
    # Index high-trust venue+date pairs
    high_trust_keys = set()
    for e in events:
        src = e.get("source") or ""
        prio = SOURCE_PRIORITY.get(src, DEFAULT_PRIORITY)
        if prio >= 4:  # skip aggregators
            continue
        v = _normalize_venue(e.get("venue_name") or e.get("location") or "")
        d = (e.get("date") or "")[:10]
        if v and d:
            high_trust_keys.add((v, d))

    dropped = 0
    out = []
    for e in events:
        src = e.get("source") or ""
        prio = SOURCE_PRIORITY.get(src, DEFAULT_PRIORITY)
        if prio < 4:
            out.append(e)
            continue
        v = _normalize_venue(e.get("venue_name") or e.get("location") or "")
        d = (e.get("date") or "")[:10]
        if v and d and (v, d) in high_trust_keys:
            dropped += 1
            continue  # suppress: a real source has this venue+date
        out.append(e)

    if dropped:
        print(f"  [venue-date-suppress] dropped {dropped} aggregator records covered by canonical sources")
    return out



def main():
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    print(f"Building master + city views — {today_iso}")
    print("=" * 60)
    
    # Step 1: Read all input files, merge into a big list
    all_events = []
    for path in INPUT_FILES:
        try:
            d = json.load(open(path))
            events = d.get("events", d) if isinstance(d, dict) else d
            print(f"  Loaded {len(events):5d} from {path}")
            all_events.extend(events)
        except FileNotFoundError:
            print(f"  SKIP: {path} not found")

    # Resilience guard: if a source's count has collapsed vs its last-known-good
    # (e.g. VPC sitemap throttled from CI: 15 of ~112 pages fetched), substitute
    # the last-good events so a partial scrape doesn't silently gut the site.
    # Self-heals on recovery; accepts a persistent drop after a few runs.
    try:
        # Rename generic "Concerts on the Commons" records to the real band name
        # (fetched from jacksonhole.com schedule). Runs before dedup so distinct
        # titles flow through and the cross-source dup false-positives clear.
        try:
            if os.environ.get("SKIP_ENRICH"):
                print("  SKIP_ENRICH set — skipping concerts-on-the-commons enrich")
            else:
                from concerts_commons_enricher import enrich_concerts_on_the_commons
                all_events = enrich_concerts_on_the_commons(all_events)
        except Exception as _ce:
            print(f"  WARN: concerts-on-the-commons enrich skipped: {_ce}")

        # Universal primary-source enrichment: for any event whose link points at
        # a registry-known primary source (chamber/venue), pull authoritative
        # dates/times/venue from that page (cascade: cache/jsonld/deterministic/
        # direct/firecrawl/llm). Replaces weak aggregator details with correct
        # data. Fully guarded: any failure leaves events un-enriched, never breaks
        # the build. Date-safe: never moves an event into the past.
        try:
            if os.environ.get("SKIP_ENRICH"):
                print("  SKIP_ENRICH set — skipping primary-source enrich")
            else:
                from primary_source_enricher import enrich_primary_sources
                all_events = enrich_primary_sources(all_events)
        except Exception as _pe:
            print(f"  WARN: primary-source enrich skipped: {_pe}")

        from scrape_resilience import apply_resilience_guard, format_report
        _before_guard = len(all_events)
        all_events, _guard_report = apply_resilience_guard(all_events, today_iso)
        _guard_msg = format_report(_guard_report)
        if _guard_msg:
            print("  Resilience guard adjustments:")
            print(_guard_msg)
        if len(all_events) != _before_guard:
            print(f"  Resilience guard: {_before_guard} -> {len(all_events)} events after retention")
    except Exception as _guard_ex:
        print(f"  Resilience guard skipped: {_guard_ex}")

    # Google Events (SerpApi) retired as a source: it echoes events we already
    # get from official/venue sources, often with wrong dates (e.g. it listed
    # the Deer Valley Music Festival a day early), and those date-mismatched
    # dupes slip past dedup. Drop all of its records site-wide.
    _before_ge = len(all_events)
    all_events = [e for e in all_events
                  if (e.get("source") or "").strip().lower() != "google events"]
    if len(all_events) != _before_ge:
        print(f"  Dropped {_before_ge - len(all_events)} Google Events records (source retired)")

    # Drop scraped UI/navigation labels that aren't real events.
    # Strip trailing recurrence descriptors ("- Every Saturday!", etc.) from
    # ALL event titles, regardless of source. Once an event is a specific dated
    # occurrence, the "Every <Day>" suffix is redundant and often contradictory
    # (a Wednesday instance inheriting "- Every Saturday!" from a series name).
    # Done here at build time so stale cached titles get cleaned too, not just
    # freshly-scraped ones.
    import re as _re_title
    _EVERY_SUFFIX = _re_title.compile(
        r"\s*[-–—|:]?\s*every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s*!*\s*$",
        _re_title.IGNORECASE
    )
    _title_cleaned = 0
    for _e in all_events:
        _t = _e.get("title") or ""
        _nt = _EVERY_SUFFIX.sub("", _t).strip()
        if _nt and _nt != _t:
            _e["title"] = _nt
            _title_cleaned += 1
    if _title_cleaned:
        print(f"  Cleaned {_title_cleaned} '- Every <Day>' title suffixes")

    try:
        import os as _os, json as _json
        _corr_path = _os.path.join(_os.path.dirname(__file__), "reviewed_corrections.json")
        if _os.path.exists(_corr_path):
            import apply_corrections as _ac
            _corr = _json.load(open(_corr_path))
            # index corrections by (normalized title, source) so every date-copy
            # of an event gets the same field fix (venue/category/etc.)
            _by_ts = {}
            for _v in _corr.values():
                _k = (( _v.get("title") or "").strip().lower(), _v.get("source") or "")
                _by_ts.setdefault(_k, {}).update(_v.get("proposal") or {})
            _applied, _added, _out = 0, 0, []
            for _e in all_events:
                _k = (( _e.get("title") or "").strip().lower(), _e.get("source") or "")
                _prop = _by_ts.get(_k)
                if not _prop:
                    _out.append(_e); continue
                _gated = {f: d for f, d in _prop.items()
                          if f not in ("date", "end_date") and isinstance(d, dict)
                          and float(d.get("conf", 0)) >= 0.85}
                if not _gated:
                    _out.append(_e); continue
                _res = _ac.apply_to_event(_e, _gated)
                _applied += 1
                if len(_res) > 1: _added += len(_res) - 1
                _out.extend(_res)
            all_events = _out
            print(f"  Applied reviewed corrections to {_applied} events (+{_added} from multi-nth split)")
    except Exception as _ce:
        print(f"  WARN: corrections apply skipped: {_ce}")

    all_events = _fan_out_recurring(all_events)

    _before_junk = len(all_events)
    all_events = [e for e in all_events if not _is_junk_title(e.get("title"))]
    if _before_junk != len(all_events):
        print(f"Dropped {_before_junk - len(all_events)} junk-title non-events")

    # Drop always-on businesses/amenities masquerading as daily events (PLUNJ,
    # rec-center drop-in classes) — they flood the calendar. See EXCLUDED list.
    _before_excl = len(all_events)
    all_events = [e for e in all_events if not _is_excluded_amenity(e)]
    if _before_excl != len(all_events):
        print(f"Dropped {_before_excl - len(all_events)} always-on amenity events")

    # Drop "starts-today" placeholders: a scraper that couldn't parse a recurring
    # event's schedule defaulted the start to the scrape date and stamped a
    # season-long end with no recurrence, so it renders as a phantom "today" on
    # the wrong day. Signature: start == build date, span > _MAX_EVENT_SPAN_DAYS,
    # no recurrence/occurrence list. (Root fix belongs in the source scraper.)
    def _is_today_placeholder(e):
        dt = (e.get("date") or "")[:10]
        ed = (e.get("end_date") or "")[:10]
        if dt != today_iso or not ed or ed <= dt:
            return False
        if (e.get("recurrence") or e.get("recurrence_days")
                or e.get("recurrence_day") or e.get("occurrence_dates")):
            return False
        try:
            span = (_dt_span.date.fromisoformat(ed) - _dt_span.date.fromisoformat(dt)).days
        except ValueError:
            return False
        return span > _MAX_EVENT_SPAN_DAYS
    _before_ph = len(all_events)
    _dropped_ph = [e for e in all_events if _is_today_placeholder(e)]
    all_events = [e for e in all_events if not _is_today_placeholder(e)]
    if _dropped_ph:
        print(f"Dropped {len(_dropped_ph)} 'starts-today' placeholder record(s) "
              f"(unparsed recurring): "
              + ", ".join(f"{e.get('title')} [{e.get('source')}]" for e in _dropped_ph[:8]))

    print(f"\nTotal records (before dedup): {len(all_events)}")
    
    # Canonicalize venue names (curated same-place aliases + strip
    # "<promoter> Presents /" prefixes) BEFORE dedup so venue-based passes,
    # address lookups, and display all agree on one name per place.
    _vc = sum(_canonicalize_venue(e) for e in all_events)
    if _vc:
        print(f"Canonicalized {_vc} venue name(s)")

    # Step 2: Global dedup
    by_key = {}
    for e in all_events:
        k = event_key(e)
        by_key.setdefault(k, []).append(e)
    
    deduped = [merge_events(group) for group in by_key.values()]
    print(f"Deduped records: {len(deduped)}")
    print(f"Duplicates merged: {len(all_events) - len(deduped)}")

    # Second pass: merge suffix-variant dupes the (title,date) key missed.
    deduped = _prefix_merge(deduped)
    print(f"After prefix-merge: {len(deduped)}")

    # Third pass: cross-source near-dupes (reorder/prefix/punctuation/typo) that
    # exact-match + prefix-merge miss. Different-source only, Jaccard>=0.85,
    # race/number guard. See _cross_source_fuzzy_merge.
    deduped = _cross_source_fuzzy_merge(deduped)
    print(f"After cross-source-merge: {len(deduped)}")

    deduped = _link_merge(deduped)
    print(f"After link-merge: {len(deduped)}")
    
    # Third pass: drop low-trust aggregator records (Google Events, Eventbrite)
    # that duplicate higher-quality sources. Conservative — only suppresses
    # within +/-7 days of a same-title match from a non-aggregator source.
    deduped = _suppress_aggregator_dupes(deduped)
    deduped = _venue_time_dedup(deduped)
    deduped = _venue_date_aggregator_suppress(deduped)
    print(f"After aggregator-suppress: {len(deduped)}")
    
    # Step 3: Filter past events
    future = [e for e in deduped if (e.get("date") or "")[:10] >= today_iso]

    # Stamp clean, user-facing filter buckets onto every event (Music, Arts &
    # Theater, Running & Races, etc.) — maps the 50+ messy source categories
    # into ~12 buckets + title enrichment (e.g. footraces). Frontend filters
    # on this field. See category_normalizer.py.
    for _e in future:
        _e["filter_categories"] = filter_categories_for(_e)
    print(f"Future events: {len(future)}")
    
    # Step 4: Write master file
    master = {
        "version": 2,
        "generated_at": datetime.now(MOUNTAIN).isoformat(),
        "today": today_iso,
        "event_count": len(future),
        "events": future,
    }
    Path(MASTER_FILE).parent.mkdir(parents=True, exist_ok=True)
    json.dump(master, open(MASTER_FILE, "w"), indent=2)
    print(f"\n[master] wrote {len(future)} events to {MASTER_FILE}")
    
    # Step 5: Build per-city views by radius
    print(f"\n{'City':<15} {'In radius':>10} {'Has geo':>10}")
    print(f"{'-'*15} {'-'*10} {'-'*10}")
    for city, cfg in CITIES.items():
        in_radius = []
        has_geo = 0
        for e in future:
            lat = e.get("lat")
            lng = e.get("lng")

            # ADDRESS-DERIVED COORDS: when the event's address mentions a known
            # city, use that city's center as the authoritative location. Handles
            # two failure modes:
            # (1) Bad coords + good address (Princess Pirate Train: PA coords,
            #     Heber City address) -> address wins, event lands in Heber view.
            # (2) Good-looking coords + address says elsewhere (Caltucky: Heber
            #     center coords falsified by Google Events, but address clearly
            #     says Cottonwood Heights) -> address wins, event excluded from
            #     Heber view as it should be.
            # The address string is the ground truth — coords are derived data.
            _KNOWN_CITIES = {
                # Wasatch / Heber Valley area
                "heber city, ut": (40.5069, -111.4133),
                "heber valley, ut": (40.5069, -111.4133),
                "midway, ut": (40.5119, -111.4744),
                "midway city, ut": (40.5119, -111.4744),
                "charleston, ut": (40.4730, -111.4661),
                "wallsburg, ut": (40.3919, -111.4286),
                "kamas, ut": (40.6438, -111.2811),
                # Summit / Park City area
                "park city, ut": (40.6461, -111.4980),
                # Salt Lake area (excluded from Heber/PC views)
                "cottonwood heights, ut": (40.6195, -111.8104),
                "sandy, ut": (40.5649, -111.8389),
                "salt lake city, ut": (40.7608, -111.8910),
                "millcreek, ut": (40.6869, -111.8754),
                "south jordan, ut": (40.5621, -111.9297),
                "west jordan, ut": (40.6097, -111.9391),
                "west valley city, ut": (40.6916, -112.0010),
                "draper, ut": (40.5247, -111.8638),
                "provo, ut": (40.2338, -111.6585),
                "orem, ut": (40.2969, -111.6946),
                "lehi, ut": (40.3916, -111.8508),
                "american fork, ut": (40.3769, -111.7958),
                # Utah ski/resort outliers
                "sundance, ut": (40.3925, -111.5810),
                # Jackson area
                "jackson, wy": (43.4799, -110.7624),
                "wilson, wy": (43.5005, -110.8748),
                "teton village, wy": (43.5875, -110.8275),
                # Elkhart Lake area
                "elkhart lake, wi": (43.8330, -88.0426),
                "plymouth, wi": (43.7491, -87.9728),
                "sheboygan, wi": (43.7508, -87.7145),
                "green lake, wi": (43.8408, -88.9576),
                "ripon, wi": (43.8422, -88.8359),
                "princeton, wi": (43.8497, -89.1290),
                "berlin, wi": (43.9678, -88.9434),
                "markesan, wi": (43.7064, -88.9817),
                "oshkosh, wi": (44.0247, -88.5426),
                "stevens point, wi": (44.5236, -89.5746),
                "stevens point": (44.5236, -89.5746),
                "appleton, wi": (44.2619, -88.4154),
                "madison, wi": (43.0731, -89.4012),
                "milwaukee, wi": (43.0389, -87.9065),
                "green bay, wi": (44.5133, -88.0133),
                "wausau, wi": (44.9591, -89.6301),
                "fond du lac, wi": (43.7730, -88.4470),
            }
            _addr_text = ((e.get("location") or "") + " " + (e.get("address") or "")).lower()
            addr_match = None
            for city_key, city_coords in _KNOWN_CITIES.items():
                if city_key in _addr_text:
                    addr_match = city_coords
                    break
            if addr_match:
                lat, lng = addr_match

            # Sanity check: if lat/lng exists but is wildly wrong (more than
            # 100mi from EVERY city center), the source data is corrupted.
            # Treat as missing so the source-based fallback kicks in.
            if lat is not None and lng is not None:
                try:
                    flat, flng = float(lat), float(lng)
                    min_dist = min(
                        haversine_miles(c["lat"], c["lng"], flat, flng)
                        for c in CITIES.values()
                    )
                    if min_dist > 100:
                        lat, lng = None, None
                except (ValueError, TypeError):
                    lat, lng = None, None

            # Source-based geo fallback for events missing or discarded coords.
            # Also uses address text to recover events whose source is generic
            # (e.g. "Heber Valley Life") but whose address clearly indicates a
            # known city.
            if lat is None or lng is None:
                source = (e.get("source") or "").lower()
                addr = (e.get("address") or "").lower() + " " + (e.get("location") or "").lower()
                if "elkhart" in source or "osthoff" in source or "road america" in source or "siebkens" in source or "elkhart lake" in addr:
                    lat, lng = 43.8330, -88.0426  # Elkhart Lake center
                elif "heber" in source or "wasatch" in source or "midway" in source or "heber city" in addr or "midway, ut" in addr:
                    lat, lng = 40.5069, -111.4133  # Heber center
                elif "jackson" in source or "teton" in source or "cloudveil" in source or "jackson, wy" in addr or "wilson, wy" in addr:
                    lat, lng = 43.4799, -110.7624  # Jackson center
                elif "park city" in source or "park record" in source or "mountain town" in source or "deer valley" in source or "park city, ut" in addr:
                    lat, lng = 40.6461, -111.4980  # PC center
                else:
                    continue
            has_geo += 1
            try:
                dist = haversine_miles(cfg["lat"], cfg["lng"], float(lat), float(lng))
            except (ValueError, TypeError):
                continue
            if dist <= cfg["radius_mi"]:
                # Add a distance hint for frontend. Also persist the corrected
                # lat/lng we computed (from address lookup, source fallback, or
                # the trusted original) so map pins use the right coordinates
                # rather than the source-corrupted ones we kept around for the
                # original record.
                e_copy = dict(e)
                e_copy["_distance_mi"] = round(dist, 1)
                e_copy["lat"] = float(lat)
                e_copy["lng"] = float(lng)
                in_radius.append(e_copy)
        
        # Write per-city view
        out = {
            "version": 2,
            "city": city,
            "city_center": {"lat": cfg["lat"], "lng": cfg["lng"]},
            "radius_mi": cfg["radius_mi"],
            "generated_at": datetime.now(MOUNTAIN).isoformat(),
            "today": today_iso,
            "event_count": len(in_radius),
            "events": in_radius,
        }
        json.dump(out, open(cfg["out_file"], "w"), indent=2)
        print(f"{city:<15} {len(in_radius):>10} {has_geo:>10}")

    # Post-build: repair dead event links (cached, 7-day TTL). Dead 404/410 only;
    # 403s and redirects are left alone. See link_health.py.
    try:
        from link_health import check_and_fix_links
        check_and_fix_links([c["out_file"] for c in CITIES.values()])
    except Exception as ex:
        print(f"[link-health] skipped ({ex})")

    print(f"\nDone!")


if __name__ == "__main__":
    main()
