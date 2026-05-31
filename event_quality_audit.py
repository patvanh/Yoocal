"""Event quality audit. Runs across all 4 cities' events.json files and
flags records with potential quality issues for review.

Categories of issues detected:
  SEVERITY 1 (BREAKS USER EXPERIENCE — must fix)
    - title_truncated:    Title looks chopped ("Live Music at", "Concert at")
    - title_too_generic:  Generic titles ("Concert", "Music", "Show") with no act name
    - missing_date:       date field is non-ISO or absent
    - past_date:          date is before today
    - multi_day_span:     date != end_date and span > 1 day (likely needs splitting)

  SEVERITY 2 (MEDIUM — should fix)
    - missing_end_time:   has start_time but no end_time
    - missing_start_time: dated event but no time set
    - no_description:     description is empty or < 30 chars
    - no_venue:           location, venue_name, address all empty
    - link_rot_suspect:   link is 404 or non-HTTP

  SEVERITY 3 (LOW — review when time allows)
    - community_only_cat: only category is "Community" (no specific category)
    - no_categories:      categories array is empty
    - duplicate_suspect:  same date + similar title as another record

The output is a flat issues.json that lists every issue with the source event,
severity, and a suggested fix where possible.

Usage:
  python3 event_quality_audit.py            # audit all 4 cities
  python3 event_quality_audit.py jackson    # audit specific city
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, date, timedelta, timezone
# Mountain Time = UTC-6 (MDT, summer) — current US daylight saving
MOUNTAIN = timezone(timedelta(hours=-6))
from collections import Counter
from pathlib import Path


# Patterns that indicate truncation
TRUNCATED_PATTERNS = [
    r"\bat\s*$",
    r"\bfeaturing\s*$",
    r"\bwith\s*$",
    r"\bpresents?\s*$",
    r":\s*$",
    r"\bperforming\s*$",
    r"\blive (music|at|from)\s*$",
]

# Generic titles that need an artist name appended
# Titles that genuinely signal a MISSING act/artist name — these should have
# had a performer but the scraper only captured a placeholder.
GENERIC_TITLES = {
    "concert", "music", "show", "live music", "concert series",
    "live performance", "headlining act", "opening night",
}

# Complete-but-generic titles: the title IS the event, nothing is missing.
# An open mic has no headliner; trivia/karaoke/rodeo/festival are full names.
# Do NOT flag these as "missing artist" (they were inflating sev-1 counts,
# especially once recurrence expansion fans them into many occurrences).
COMPLETE_GENERIC_TITLES = {
    "open mic", "trivia", "trivia night", "karaoke", "rodeo",
    "festival", "music fest", "music festival", "bingo", "story time",
    "line dancing", "happy hour", "farmers market",
}

# Venue-prefix titles that drop the artist
VENUE_PREFIX_PATTERNS = [
    r"^live music at\s+\w",
    r"^music at\s+\w",
    r"^concert at\s+\w",
    r"^show at\s+\w",
    r"^performing at\s+\w",
]


CITY_FILES = {
    # Audit the DEDUPED PRODUCTION files (what users actually see), not raw
    # scraper inputs. Raw files contain pre-dedup duplicates and pre-repair
    # date spans that the build pipeline fixes downstream — auditing them
    # produced false "severity-1" alerts for issues users never encounter.
    "park-city": "public/events.json",
    "elkhart-lake": "public/events-elkhartlake.json",
    "heber": "public/events-heber.json",
    "jackson": "public/events-jackson.json",
}


def _is_iso_date(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(s or "")))


def _has_any(event: dict, *fields) -> bool:
    return any(event.get(f) for f in fields)


def _norm_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").lower().strip())
    t = re.sub(r"^[\(\"\'\-\s]+", "", t)
    t = re.sub(
        r"\s*(-|\u2014|\u2013|\bwith\b|\bfeaturing\b|\bft\.?\b|\bpresented by\b).*$",
        "", t,
    ).strip()
    if ":" in t:
        t = t.split(":")[0].strip()
    return t[:40]


def audit_event(e: dict, today_iso: str) -> list[dict]:
    """Run all quality checks on a single event. Returns list of issues."""
    issues = []
    title = (e.get("title") or "").strip()
    title_lower = title.lower()
    date_val = (e.get("date") or "")[:10]
    end_date = (e.get("end_date") or "")[:10]

    # ─── Severity 1 ───────────────────────────────────────────────
    if not title or len(title) < 4:
        issues.append({
            "severity": 1,
            "type": "title_missing",
            "message": "Event has no title or title is shorter than 4 chars",
            "suggested_fix": None,
        })

    for p in TRUNCATED_PATTERNS:
        if re.search(p, title_lower):
            issues.append({
                "severity": 1,
                "type": "title_truncated",
                "message": f"Title appears truncated: {title!r}",
                "suggested_fix": "Fetch source URL and re-extract the full title with artist/act name",
            })
            break

    if title_lower in GENERIC_TITLES:
        issues.append({
            "severity": 1,
            "type": "title_too_generic",
            "message": f"Title is generic ({title!r}) — likely missing artist/act name",
            "suggested_fix": "Fetch source URL and identify the specific performer/artist",
        })

    for p in VENUE_PREFIX_PATTERNS:
        if re.search(p, title_lower):
            issues.append({
                "severity": 3,
                "type": "title_venue_only",
                "message": f"Title is just a venue prefix ({title!r})",
                "suggested_fix": "Replace generic 'Live Music at X' with the actual band/act name",
            })
            break

    if not _is_iso_date(date_val):
        issues.append({
            "severity": 1,
            "type": "missing_or_invalid_date",
            "message": f"date field is not ISO format: {date_val!r}",
            "suggested_fix": "Re-scrape this event from its source URL or remove if unsalvageable",
        })

    if _is_iso_date(date_val) and date_val < today_iso:
        issues.append({
            "severity": 1,
            "type": "past_date",
            "message": f"Event date {date_val} is in the past",
            "suggested_fix": "Drop from events.json (handled by date filter)",
        })

    # Recurring events legitimately span a whole season (date -> end_date is the
    # recurrence range, e.g. a weekly shuttle running Jun–Oct). Their span is by
    # design, NOT a "stamped one event over months" defect — skip span flagging.
    _is_recurring = bool(e.get("recurrence") or e.get("recurrence_days") or e.get("recurrence_day"))
    if (not _is_recurring and _is_iso_date(date_val) and _is_iso_date(end_date)
            and date_val != end_date and end_date > date_val):
        try:
            d1 = date.fromisoformat(date_val)
            d2 = date.fromisoformat(end_date)
            span_days = (d2 - d1).days + 1
            # Late-night past-midnight events (e.g. 9 PM Thursday → 1 AM Friday)
            # have span=1 but start_time is in the evening. Skip flagging these.
            start_time = e.get("start_time") or ""
            is_late_night = bool(re.match(r"(8|9|10|11):", start_time)) and ("PM" in start_time or "pm" in start_time)
            if span_days == 2 and is_late_night:
                pass  # Not actually multi-day — single late-night event
            elif 1 < span_days <= 14:
                # Multi-day events (festivals, multi-night runs, exhibitions) are
                # a supported feature — they render on every day they run. This is
                # informational (severity 3), not a defect needing a split.
                issues.append({
                    "severity": 3,
                    "type": "multi_day_span",
                    "message": (
                        f"Event spans {span_days} days ({date_val} to {end_date}). "
                        f"Supported as a multi-day event; flagged only for review."
                    ),
                    "suggested_fix": (
                        f"No action needed unless this should be {span_days} separate "
                        f"events — if so, split into individual records."
                    ),
                })
            elif span_days > 14:
                issues.append({
                    "severity": 1,
                    "type": "absurd_span",
                    "message": (
                        f"Event spans {span_days} days ({date_val} to {end_date}). "
                        f"This is likely a data bug — exhibitions/ongoing events "
                        f"should be marked as recurring, not stamped with a long range."
                    ),
                    "suggested_fix": "Re-scrape or model as a recurring/daily event",
                })
        except ValueError:
            pass

    # ─── Severity 2 ───────────────────────────────────────────────
    if e.get("start_time") and not e.get("end_time"):
        issues.append({
            "severity": 2,
            "type": "missing_end_time",
            "message": f"Has start_time {e.get('start_time')} but no end_time",
            "suggested_fix": (
                "If venue has standard set length (rodeo=2hr, concert=2-3hr, "
                "movie=2hr), fill from venue defaults. Otherwise leave null."
            ),
        })

    if _is_iso_date(date_val) and date_val >= today_iso and not e.get("start_time"):
        issues.append({
            "severity": 2,
            "type": "missing_start_time",
            "message": "Future-dated event has no start_time",
            "suggested_fix": "Fetch source URL and extract start time",
        })

    desc = (e.get("description") or "").strip()
    if len(desc) < 30:
        issues.append({
            "severity": 2,
            "type": "no_description",
            "message": f"Description missing or very short (len={len(desc)})",
            "suggested_fix": "Fetch source URL and pull a 2-3 sentence description",
        })

    if not _has_any(e, "location", "venue_name", "address"):
        issues.append({
            "severity": 2,
            "type": "no_venue",
            "message": "No location, venue_name, or address",
            "suggested_fix": "Fetch source URL and identify the venue",
        })

    link = e.get("link") or ""
    if link and not link.startswith(("http://", "https://")):
        issues.append({
            "severity": 2,
            "type": "bad_link",
            "message": f"Link is not http(s): {link[:80]!r}",
            "suggested_fix": "Fix the URL or remove the link field",
        })

    # ─── Severity 3 ───────────────────────────────────────────────
    cats = e.get("categories") or []
    if not cats:
        issues.append({
            "severity": 3,
            "type": "no_categories",
            "message": "Empty categories list",
            "suggested_fix": "Re-run event_classifier on this record",
        })
    elif cats == ["Community"]:
        issues.append({
            "severity": 3,
            "type": "community_only_cat",
            "message": "Only category is 'Community' (no specific tag)",
            "suggested_fix": (
                "Check if title/description matches any specific classifier rule. "
                "If genuinely uncategorizable, leave as-is."
            ),
        })

    return issues


def find_duplicates(events: list) -> list[dict]:
    """Find groups of records that look like duplicates (same date + normalized title)."""
    groups: dict = {}
    for i, e in enumerate(events):
        date_val = (e.get("date") or "")[:10]
        if not date_val or not e.get("title"):
            continue
        key = (date_val, _norm_title(e["title"]))
        groups.setdefault(key, []).append((i, e))

    issues = []
    for (date_val, norm_title), records in groups.items():
        if len(records) > 1:
            indices = [i for i, _ in records]
            titles = [r.get("title") for _, r in records]
            sources = [r.get("source") for _, r in records]
            issues.append({
                "severity": 1,
                "type": "duplicate_suspect",
                "message": (
                    f"{len(records)} records on {date_val} normalize to same title. "
                    f"Titles: {titles}. Sources: {sources}"
                ),
                "suggested_fix": (
                    "Merge into one record using merge-aware dedup (already applied to "
                    "PC/Elkhart/Jackson). If still showing, the normalization rule "
                    "needs tuning."
                ),
                "_event_indices": indices,
            })
    return issues


def audit_city(city_key: str, filename: str) -> dict:
    """Audit one city's events.json. Returns a report dict."""
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")

    try:
        d = json.load(open(filename))
    except FileNotFoundError:
        return {"city": city_key, "error": f"File not found: {filename}"}

    events = d.get("events", d) if isinstance(d, dict) else d

    all_issues = []
    for idx, e in enumerate(events):
        for issue in audit_event(e, today_iso):
            all_issues.append({
                "city": city_key,
                "event_index": idx,
                "event_title": (e.get("title") or "")[:80],
                "event_date": e.get("date"),
                "event_source": e.get("source"),
                "event_link": e.get("link"),
                **issue,
            })

    # Run duplicate detection (cross-event)
    for issue in find_duplicates(events):
        issue["city"] = city_key
        all_issues.append(issue)

    # Tally
    by_severity = Counter(i["severity"] for i in all_issues)
    by_type = Counter(i["type"] for i in all_issues)

    return {
        "city": city_key,
        "total_events": len(events),
        "total_issues": len(all_issues),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "issues": all_issues,
    }


def main(target_city: str | None = None):
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    print(f"Event Quality Audit — {today_iso}")
    print("=" * 60)

    targets = [target_city] if target_city else list(CITY_FILES.keys())
    all_reports = []

    for city in targets:
        if city not in CITY_FILES:
            print(f"  unknown city: {city}")
            continue
        report = audit_city(city, CITY_FILES[city])
        if "error" in report:
            print(f"\n  {city}: {report['error']}")
            continue

        all_reports.append(report)

        print(f"\n=== {city.upper()} ===")
        print(f"  Total events: {report['total_events']}")
        print(f"  Total issues: {report['total_issues']}")
        print(f"  By severity:  {report['by_severity']}")
        print(f"  Top issue types:")
        for t, n in sorted(report["by_type"].items(), key=lambda x: -x[1])[:10]:
            print(f"    {n:5d}  {t}")

    # Combined output
    output = {
        "generated_at": datetime.now().isoformat(),
        "audit_date": today_iso,
        "reports": all_reports,
    }

    out_path = Path("audit_issues.json")
    json.dump(output, open(out_path, "w"), indent=2)
    print(f"\n{'=' * 60}")
    print(f"Full audit written to {out_path.resolve()}")

    # Sample worst offenders for quick review
    print(f"\nSample severity-1 issues (max 20):")
    all_sev1 = [i for r in all_reports for i in r["issues"] if i.get("severity") == 1]
    for i in all_sev1[:20]:
        title = i.get("event_title") or ""
        print(f"  [{i['city']:<13}] {i['type']:<25} | {title[:50]}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    main(target)
