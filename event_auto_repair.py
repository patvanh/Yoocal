"""Rule-based auto-repair for event quality issues.

Runs against each city's events.json (or against audit_issues.json from
event_quality_audit.py) and applies deterministic fixes for the patterns
we know how to handle without needing an LLM.

Patterns handled:
  1. absurd_span (>14 days) for ongoing-class titles → mark as recurring,
     drop the bogus end_date
  2. multi_day_span (≤14 days) → split into per-day records IF description
     contains explicit dates ("May 18, 19 & 20")
  3. missing_end_time → fill from venue_hours_defaults
  4. past_date → drop the record
  5. community_only_cat / no_categories → re-run classifier

Issues that require LLM resolution (not handled here):
  - title_venue_only
  - title_truncated
  - multi_day_span where description has no date markers

Outputs:
  - The patched events.json files (in-place)
  - A repair_log.json summarizing what was changed
  - An unresolved_issues.json with what still needs Claude/human attention
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, date, timedelta, timezone
# Mountain Time = UTC-7 (MST) or UTC-6 (MDT) — current US daylight saving
MOUNTAIN = timezone(timedelta(hours=-6))
from collections import Counter
from pathlib import Path


CITY_FILES = {
    "park-city": "public/events.json",
    "elkhart-lake": "public/events-elkhartlake.json",
    "heber": "public/events-heber.json",
    "jackson": "public/events-jackson.json",
}


# Patterns in titles that suggest the event is an ongoing class/program/exhibition
ONGOING_TITLE_PATTERNS = [
    r"\bclass(es)?\b",
    r"\btour(s)?\b",
    r"\bprogramming\b",
    r"\bworkshops?\b",
    r"\bexhibition\b",
    r"\bexhibit\b",
    r"\bregistration\b",
    r"\bopen now\b",
    r"\bseries\b",
    r"\bsessions?\b",
    r"\bdrop[- ]in\b",
    r"\bongoing\b",
]


# Venue/event type → default duration in hours
VENUE_HOURS_DEFAULTS = {
    # event types
    "rodeo": 2,
    "concert": 3,
    "movie": 2,
    "film fest": 2,
    "show": 2,
    "tour": 1,
    "walking tour": 1,
    "lecture": 1.5,
    "workshop": 2,
    "class": 1,
    "yoga": 1,
    "fitness": 1,
    "storytime": 0.5,
    "story time": 0.5,
    "open mic": 2,
    "trivia": 2,
    "karaoke": 3,
}


# Patterns that extract explicit dates from descriptions
# "May 18, 19, & 20 @ 7:30 pm"  → [18, 19, 20]
# "Jun 12-14"  → [12, 13, 14]
# "May 18-20, 2026" → [18, 19, 20]
def extract_explicit_days_from_text(desc: str, month_num: int) -> list[int]:
    """Find explicit day numbers in description text for a known month.

    Returns sorted list of day-of-month integers or empty list if no match.
    """
    if not desc:
        return []

    months_re = (
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?"
    )

    days = set()

    # Pattern A: "May 18, 19 & 20" or "May 18, 19, and 20"
    m = re.search(
        rf"(?i)\b({months_re})\s+(\d{{1,2}})\s*(?:,\s*(\d{{1,2}}))?\s*(?:,\s*(\d{{1,2}}))?\s*(?:&|and)\s*(\d{{1,2}})",
        desc,
    )
    if m:
        for g in m.groups()[1:]:
            if g and g.isdigit():
                days.add(int(g))

    # Pattern B: "May 18-20" or "May 18 - 20"
    m = re.search(
        rf"(?i)\b({months_re})\s+(\d{{1,2}})\s*[-\u2013\u2014]\s*(\d{{1,2}})",
        desc,
    )
    if m:
        start, end = int(m.group(2)), int(m.group(3))
        if 1 <= start <= 31 and start <= end <= 31:
            for d in range(start, end + 1):
                days.add(d)

    return sorted(days)


def _is_iso_date(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(s or "")))


def _looks_ongoing(title: str) -> bool:
    t = (title or "").lower()
    return any(re.search(p, t) for p in ONGOING_TITLE_PATTERNS)


def _guess_duration_hours(title: str, venue: str = "") -> float | None:
    """Return guessed duration in hours, or None if can't guess."""
    haystack = ((title or "") + " " + (venue or "")).lower()
    for keyword, hours in VENUE_HOURS_DEFAULTS.items():
        if keyword in haystack:
            return hours
    return None


def _add_hours_to_time_str(time_str: str, hours: float) -> str | None:
    """Convert '8:00 PM' + 2 hours → '10:00 PM'. Returns None on parse failure."""
    if not time_str:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP]M)", time_str.strip(), re.IGNORECASE)
    if not m:
        return None
    h = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).upper()

    # Convert to 24h
    if ampm == "PM" and h != 12:
        h += 12
    elif ampm == "AM" and h == 12:
        h = 0

    total_minutes = h * 60 + minute + int(hours * 60)
    total_minutes %= (24 * 60)  # wrap past midnight
    new_h = total_minutes // 60
    new_m = total_minutes % 60

    new_ampm = "AM" if new_h < 12 else "PM"
    display_h = new_h % 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{new_m:02d} {new_ampm}"


# ─── Repair functions ─────────────────────────────────────────────

def repair_absurd_span(events: list, today_iso: str) -> dict:
    """Find events with span > 14 days that look ongoing. Drop the end_date,
    mark as recurring. Don't split — just acknowledge it's ongoing."""
    fixed = 0
    examples = []
    for e in events:
        date_val = (e.get("date") or "")[:10]
        end_date = (e.get("end_date") or "")[:10]
        if not (_is_iso_date(date_val) and _is_iso_date(end_date)):
            continue
        try:
            d1 = date.fromisoformat(date_val)
            d2 = date.fromisoformat(end_date)
            span_days = (d2 - d1).days + 1
        except ValueError:
            continue

        if span_days > 14 and _looks_ongoing(e.get("title", "")):
            # Drop end_date, mark as ongoing
            e["end_date"] = None
            e["is_ongoing"] = True
            fixed += 1
            if len(examples) < 5:
                examples.append({
                    "title": e.get("title"),
                    "had_span": span_days,
                })
    return {"fixed": fixed, "examples": examples}


def repair_multi_day_splittable(events: list, today_iso: str) -> dict:
    """Find multi-day events with explicit dates in their description.
    Split into per-day records.

    Returns dict with 'fixed', 'examples', and list of indices to insert.
    """
    fixed = 0
    examples = []
    new_records = []
    to_remove = []

    for idx, e in enumerate(events):
        date_val = (e.get("date") or "")[:10]
        end_date = (e.get("end_date") or "")[:10]
        if not (_is_iso_date(date_val) and _is_iso_date(end_date)):
            continue
        if date_val == end_date:
            continue
        try:
            d1 = date.fromisoformat(date_val)
            d2 = date.fromisoformat(end_date)
            span_days = (d2 - d1).days + 1
        except ValueError:
            continue
        if not (1 < span_days <= 14):
            continue

        # Try to extract explicit days from description
        desc = e.get("description") or ""
        explicit_days = extract_explicit_days_from_text(desc, d1.month)

        if explicit_days:
            # Match explicit days against the date span
            year, month = d1.year, d1.month
            matched_dates = []
            for day in explicit_days:
                try:
                    target = date(year, month, day)
                    if d1 <= target <= d2:
                        matched_dates.append(target)
                except ValueError:
                    pass

            if matched_dates:
                # Create one record per matched date
                for md in matched_dates:
                    copy = dict(e)
                    copy["date"] = md.isoformat()
                    copy["end_date"] = md.isoformat()
                    copy["_repaired_from"] = f"multi_day_split (was {date_val} to {end_date})"
                    new_records.append(copy)

                to_remove.append(idx)
                fixed += 1
                if len(examples) < 5:
                    examples.append({
                        "title": e.get("title"),
                        "original_span": f"{date_val} to {end_date}",
                        "split_into": [md.isoformat() for md in matched_dates],
                    })

    # Apply mutations: remove old records in reverse-index order, then append new
    for idx in sorted(to_remove, reverse=True):
        events.pop(idx)
    events.extend(new_records)

    return {"fixed": fixed, "examples": examples}


def repair_missing_end_times(events: list) -> dict:
    """Fill end_time for events with start_time and a guessable duration."""
    fixed = 0
    examples = []
    for e in events:
        if e.get("end_time"):
            continue
        if not e.get("start_time"):
            continue

        venue = e.get("venue_name") or e.get("location") or ""
        hours = _guess_duration_hours(e.get("title", ""), venue)
        if hours is None:
            continue

        new_end = _add_hours_to_time_str(e["start_time"], hours)
        if new_end:
            e["end_time"] = new_end
            fixed += 1
            if len(examples) < 5:
                examples.append({
                    "title": e.get("title"),
                    "start_time": e["start_time"],
                    "new_end_time": new_end,
                    "duration_hours": hours,
                })
    return {"fixed": fixed, "examples": examples}


def repair_past_dates(events: list, today_iso: str) -> dict:
    """Remove events with dates in the past."""
    before = len(events)
    examples = []
    keep = []
    for e in events:
        date_val = (e.get("date") or "")[:10]
        end_date = (e.get("end_date") or "")[:10]
        latest = end_date if _is_iso_date(end_date) else date_val
        if _is_iso_date(latest) and latest < today_iso:
            if len(examples) < 5:
                examples.append({
                    "title": e.get("title"),
                    "date": e.get("date"),
                })
            continue
        keep.append(e)
    events[:] = keep
    return {"fixed": before - len(keep), "examples": examples}


def repair_classification(events: list) -> dict:
    """Re-run the canonical classifier on events with empty or community-only categories."""
    try:
        from event_classifier import classify_event
    except ImportError:
        return {"fixed": 0, "examples": [], "error": "event_classifier not importable"}

    fixed = 0
    examples = []
    for e in events:
        cats = e.get("categories") or []
        if cats and cats != ["Community"]:
            continue

        before_cats = list(cats)
        classify_event(e)
        after_cats = e.get("categories") or []

        if after_cats != before_cats:
            fixed += 1
            if len(examples) < 5:
                examples.append({
                    "title": e.get("title"),
                    "before": before_cats,
                    "after": after_cats,
                })
    return {"fixed": fixed, "examples": examples}


# ─── Main orchestration ──────────────────────────────────────────

def repair_city(city_key: str, filename: str, today_iso: str) -> dict:
    """Run all repair passes on one city's events.json."""
    try:
        d = json.load(open(filename))
    except FileNotFoundError:
        return {"city": city_key, "error": f"File not found: {filename}"}

    events = d.get("events", d) if isinstance(d, dict) else d
    before_count = len(events)

    report = {"city": city_key, "before_count": before_count, "passes": {}}

    # Run each repair pass in order
    report["passes"]["past_dates"] = repair_past_dates(events, today_iso)
    report["passes"]["absurd_spans"] = repair_absurd_span(events, today_iso)
    report["passes"]["multi_day_splits"] = repair_multi_day_splittable(events, today_iso)
    report["passes"]["missing_end_times"] = repair_missing_end_times(events)
    report["passes"]["classification"] = repair_classification(events)

    report["after_count"] = len(events)
    report["total_fixes"] = sum(p.get("fixed", 0) for p in report["passes"].values())

    # Save
    d["events"] = events
    json.dump(d, open(filename, "w"), indent=2)

    return report


def main(target_city: str | None = None):
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    print(f"Event Auto-Repair — {today_iso}")
    print("=" * 60)

    targets = [target_city] if target_city else list(CITY_FILES.keys())
    all_reports = []

    for city in targets:
        if city not in CITY_FILES:
            print(f"  unknown city: {city}")
            continue
        report = repair_city(city, CITY_FILES[city], today_iso)
        if "error" in report:
            print(f"  {city}: {report['error']}")
            continue
        all_reports.append(report)

        print(f"\n=== {city.upper()} ===")
        print(f"  Before: {report['before_count']}  After: {report['after_count']}")
        print(f"  Total fixes: {report['total_fixes']}")
        for pass_name, result in report["passes"].items():
            n = result.get("fixed", 0)
            if n > 0:
                print(f"    {pass_name:25s} fixed {n}")
                for ex in result.get("examples", [])[:2]:
                    title = ex.get("title", "")[:45]
                    detail = (
                        ex.get("new_end_time")
                        or ex.get("split_into")
                        or ex.get("had_span")
                        or ex.get("after")
                        or ex.get("date")
                    )
                    print(f"      • {title:45s} → {detail}")

    out_path = Path("repair_log.json")
    json.dump({
        "generated_at": datetime.now().isoformat(),
        "audit_date": today_iso,
        "reports": all_reports,
    }, open(out_path, "w"), indent=2)
    print(f"\nFull repair log written to {out_path.resolve()}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    main(target)
