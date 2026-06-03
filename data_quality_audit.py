#!/usr/bin/env python3
"""
data_quality_audit.py — Standing data-quality guard for yoocal.

Scans every published city view (public/events-*.json) and flags the
categories of bugs we keep finding by hand, so they get caught automatically
in every city instead of being rediscovered one spot-checked day at a time.

Each check corresponds to a real bug class found in production:

  C1  RECURRING-DROPPED   A title+venue appears on only ONE future date but its
                          title/recurrence implies it should repeat (e.g. weekly
                          karaoke that the scraper dropped as "past").
  C2  MULTIDAY-GAP        An event has date < end_date (a multi-day run) but is
                          missing interior days in the published view (the
                          "Stampede 7/31 vanished" class — venue/time over-merge).
  C3  VENUE-TIME-COLLISION  Two DIFFERENT-titled events share venue+date+time.
                          Usually fine post-fix, but flags potential over-merge
                          or genuinely-distinct events that were collapsed.
  C4  BAD-DATE            Events with a past date in a "future" view, or dates
                          implausibly far out (>18 months), or unparseable dates.
  C5  CROSS-SOURCE-DUP    Same date + near-identical title from two sources
                          (the "Joe Hill lecture / Lecture" class).
  C6  COVERAGE-CLIFF      A source that previously contributed many events now
                          contributes few/none (compares to an optional baseline).
  C7  FIELD-HEALTH        Missing critical fields (no date, no title), or
                          encoding artifacts (%26, &amp;, &quot;) leaking into
                          titles.

Usage:
    python3 data_quality_audit.py
    python3 data_quality_audit.py --city jackson         # one city
    python3 data_quality_audit.py --save-baseline        # snapshot counts
    python3 data_quality_audit.py --max-examples 8       # more examples per finding

Exit code is 0 if no HIGH-severity findings, 1 otherwise — so CI can gate on it.

Read-only: never writes to event data. The only file it may write is
data_quality_baseline.json (with --save-baseline), used by C6.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime, date, timedelta

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

VIEW_GLOB = "public/events-*.json"
BASELINE_FILE = "data_quality_baseline.json"
TODAY = date.today()
TODAY_ISO = TODAY.isoformat()
FAR_FUTURE_DAYS = 550  # ~18 months; dates beyond this are suspicious

# STRONG recurrence signals: explicit cadence words. A title containing one of
# these almost certainly denotes a repeating event, so appearing on only one
# future date is a real red flag (the karaoke-dropped class).
_RECURRING_STRONG = re.compile(
    r"\b(weekly|biweekly|every (mon|tues?|wed(nes)?|thurs?|fri|sat(ur)?|sun)(day)?s?"
    r"|every week|every other (week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|recurring|each (week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|farmers?\s*market|story\s?time)\b",
    re.IGNORECASE,
)

# Titles that are inherently SINGLE-occurrence even if a source sets a stray
# recurrence field (annual races, one-night galas). A recurrence flag on these
# is bad source data, not a dropped series — C1 must not HIGH-flag them.
_SINGULAR_EVENT = re.compile(
    r"\b(marathon|half\s*marathon|10k|5k|1k|50k|50\s*mile|ultra|relay|triathlon"
    r"|duathlon|gala|fun\s*run|hill\s*climb|challenge|fest|festival|championship"
    r"|tournament|invitational|classic|open|derby"
    # On-demand BOOKABLE experiences: a recurrence field means "available on
    # various days", not a fixed dropped series. VPC lists them per-date.
    r"|class|experience|tasting|workshop|tour|lesson|session|reservation"
    r"|for \d+|guests?)\b",
    re.IGNORECASE,
)

# WEAK signals: generic activity words that appear in plenty of legitimate
# ONE-OFF events ('Family Yoga in the Garden', 'Live Music by Bowser'). These
# alone are NOT enough to flag — we only treat a weak-signal title as suspicious
# when OTHER events with a near-identical title exist on different dates (i.e.
# the series is clearly recurring but this instance is orphaned). See C1 logic.
_RECURRING_WEAK = re.compile(
    r"\b(trivia|karaoke|open mic|happy hour|bingo|yoga|live music"
    r"|sunday service|sunday worship|book club|game night)\b",
    re.IGNORECASE,
)

# Encoding artifacts that should never appear in a clean title (C7).
_ENCODING_ARTIFACTS = ("%26", "%20", "&amp;", "&quot;", "&#39;", "&#039;", "\\u")

# Severity labels
HIGH, MED, LOW = "HIGH", "MED", "LOW"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def load_events(path):
    with open(path) as f:
        d = json.load(f)
    return d.get("events", d) if isinstance(d, dict) else d


def ev_date(e):
    return (e.get("date") or "")[:10]


def ev_end(e):
    return (e.get("end_date") or "")[:10]


def ev_venue(e):
    return (e.get("venue_name") or e.get("location") or "").strip().lower()


def norm_title(t):
    """Light normalization for grouping (NOT the build's aggressive one)."""
    t = (t or "").lower()
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_iso(d):
    try:
        return date.fromisoformat(d[:10])
    except (ValueError, TypeError):
        return None


def jaccard(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def city_from_path(path):
    base = os.path.basename(path)
    m = re.match(r"events-(.+)\.json$", base)
    return m.group(1) if m else base


# --------------------------------------------------------------------------
# Checks  (each returns a list of finding dicts)
# --------------------------------------------------------------------------

def check_recurring_dropped(events, max_ex):
    """C1: an event that should recur appears on only one future date.

    Two ways to qualify as suspicious:
      (a) STRONG title signal ('weekly', 'every Tuesday', 'farmers market') and
          only one future date — the karaoke-dropped class.
      (b) The event's own recurrence field is set (recurrence/recurrence_days)
          but it still appears on only one future date — the data claims it
          repeats yet it was not expanded.
    A WEAK title signal alone ('yoga', 'live music') does NOT qualify — those
    are common in one-off events (a different band each night)."""
    future = [e for e in events if ev_date(e) >= TODAY_ISO]
    by_key = defaultdict(set)
    sample = {}
    reason = {}
    for e in future:
        title = e.get("title") or ""
        has_strong = bool(_RECURRING_STRONG.search(title))
        claims_recurrence = bool(e.get("recurrence") or e.get("recurrence_days"))
        is_singular = bool(_SINGULAR_EVENT.search(title))
        # A recurrence field on an inherently-singular event (a half marathon,
        # gala, etc.) is bad source data, not a dropped series — don't trust it.
        if is_singular:
            claims_recurrence = False
        if not (has_strong or claims_recurrence):
            continue
        key = norm_title(title)
        by_key[key].add(ev_date(e))
        sample.setdefault(key, e)
        # recurrence-field = strong evidence (HIGH). strong-title alone = a guess
        # from the name with no data backing it (MED).
        reason.setdefault(key, "recurrence-field" if claims_recurrence else "strong-title")
    findings = []
    for key, dates in by_key.items():
        if len(dates) == 1:
            e = sample[key]
            findings.append({
                "title": e.get("title"),
                "venue": ev_venue(e) or "(no venue)",
                "only_date": next(iter(dates)),
                "why": reason[key],
                "source": e.get("source"),
            })
    findings.sort(key=lambda f: f["title"] or "")
    has_field_evidence = any(f["why"] == "recurrence-field" for f in findings)
    if not findings:
        sev = LOW
    elif has_field_evidence:
        sev = HIGH
    else:
        sev = MED
    return {
        "code": "C1",
        "name": "RECURRING-DROPPED",
        "severity": sev,
        "count": len(findings),
        "desc": "Event should recur (recurrence field set, or strong cadence word in "
                "title) but appears on only ONE future date. recurrence-field findings "
                "are HIGH (data-backed); strong-title-only are MED (name-based guess).",
        "examples": findings[:max_ex],
    }


def check_multiday_gap(events, max_ex):
    """C2: an event spans date..end_date but interior days are missing."""
    # Group occurrences by (title, venue) and check ranges.
    by_key = defaultdict(list)
    for e in events:
        d = ev_date(e)
        if d < TODAY_ISO and ev_end(e) < TODAY_ISO:
            continue
        by_key[(norm_title(e.get("title") or ""), ev_venue(e))].append(e)

    findings = []
    for key, group in by_key.items():
        # Find any record that declares a multi-day span.
        spans = [(parse_iso(ev_date(e)), parse_iso(ev_end(e)), e)
                 for e in group if ev_end(e) and ev_end(e) > ev_date(e)]
        present_dates = {ev_date(e) for e in group}
        for start, end, e in spans:
            if not start or not end:
                continue
            span_len = (end - start).days
            if span_len < 1 or span_len > 30:
                continue  # ignore single-day and very long ranges
            # Which interior days are missing from the published set?
            missing = []
            d = start
            while d <= end:
                if d.isoformat() not in present_dates:
                    missing.append(d.isoformat())
                d += timedelta(days=1)
            # If the event was fanned out we'd see each day as its own record;
            # missing interior days => gap.
            if missing and len(missing) < span_len:  # some present, some missing
                findings.append({
                    "title": e.get("title"),
                    "venue": ev_venue(e) or "(no venue)",
                    "span": f"{start.isoformat()}..{end.isoformat()}",
                    "missing": missing[:6],
                    "source": e.get("source"),
                })
                break
    findings.sort(key=lambda f: f["title"] or "")
    return {
        "code": "C2",
        "name": "MULTIDAY-GAP",
        "severity": HIGH if findings else LOW,
        "count": len(findings),
        "desc": "Multi-day event (date..end_date) is missing interior days in the "
                "published view — the 'Stampede 7/31 vanished' class.",
        "examples": findings[:max_ex],
    }


def check_venue_time_collision(events, max_ex):
    """C3: different-titled events sharing venue+date+time (possible over/under-merge)."""
    groups = defaultdict(list)
    for e in events:
        if ev_date(e) < TODAY_ISO:
            continue
        v = ev_venue(e)
        t = (e.get("start_time") or "").strip().lower()
        d = ev_date(e)
        if not v or not t or not d:
            continue
        groups[(v, d, t)].append(e)
    findings = []
    for (v, d, t), members in groups.items():
        titles = {norm_title(m.get("title") or "") for m in members if m.get("title")}
        if len(titles) >= 2:
            # are they actually dissimilar (genuinely different events kept) or
            # similar (possible should-have-merged)? report dissimilar clusters,
            # they are the interesting "two real events same slot" case.
            tl = list(titles)
            dissimilar = any(
                jaccard(tl[i], tl[j]) < 0.6
                for i in range(len(tl)) for j in range(i + 1, len(tl))
            )
            findings.append({
                "venue": v, "date": d, "time": t,
                "titles": [m.get("title") for m in members][:4],
                "dissimilar": dissimilar,
            })
    # Only the dissimilar ones are worth a human glance.
    dissimilar = [f for f in findings if f["dissimilar"]]
    return {
        "code": "C3",
        "name": "VENUE-TIME-COLLISION",
        "severity": LOW,
        "count": len(dissimilar),
        "desc": "Different-titled events share venue+date+time. Expected to be rare; "
                "verifies the venue-time dedup is neither over- nor under-merging.",
        "examples": dissimilar[:max_ex],
    }


def check_bad_dates(events, max_ex):
    """C4: past dates in a future view, implausibly-far dates, unparseable dates."""
    far = TODAY + timedelta(days=FAR_FUTURE_DAYS)
    past, far_out, unparseable = [], [], []
    for e in events:
        d = ev_date(e)
        end = ev_end(e)
        eff_end = end or d
        pd = parse_iso(d)
        if not pd:
            unparseable.append({"title": e.get("title"), "raw_date": e.get("date"),
                                "source": e.get("source")})
            continue
        if eff_end < TODAY_ISO:
            past.append({"title": e.get("title"), "date": d, "end": end or "-",
                         "source": e.get("source")})
        if pd > far:
            far_out.append({"title": e.get("title"), "date": d,
                            "source": e.get("source")})
    total = len(past) + len(far_out) + len(unparseable)
    return {
        "code": "C4",
        "name": "BAD-DATE",
        "severity": MED if (past or unparseable) else LOW,
        "count": total,
        "desc": "Past events in a future view, dates >18mo out, or unparseable dates.",
        "examples": {
            "past": past[:max_ex],
            "far_future": far_out[:max_ex],
            "unparseable": unparseable[:max_ex],
        },
    }


def check_cross_source_dup(events, max_ex):
    """C5: same date + near-identical title from two different sources."""
    by_date = defaultdict(list)
    for e in events:
        d = ev_date(e)
        if d >= TODAY_ISO and e.get("title"):
            by_date[d].append(e)
    findings = []
    for d, evs in by_date.items():
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                a, b = evs[i], evs[j]
                na, nb = norm_title(a.get("title")), norm_title(b.get("title"))
                if na == nb:
                    sim = 1.0
                else:
                    sim = jaccard(na, nb)
                    # also catch substring containment
                    if na in nb or nb in na:
                        sim = max(sim, 0.85)
                if sim >= 0.8 and a.get("source") != b.get("source"):
                    findings.append({
                        "date": d,
                        "title_a": a.get("title"), "src_a": a.get("source"),
                        "title_b": b.get("title"), "src_b": b.get("source"),
                        "sim": round(sim, 2),
                    })
    findings.sort(key=lambda f: -f["sim"])
    return {
        "code": "C5",
        "name": "CROSS-SOURCE-DUP",
        "severity": MED if findings else LOW,
        "count": len(findings),
        "desc": "Same date + near-identical title from two sources — a dedup miss.",
        "examples": findings[:max_ex],
    }


def check_coverage_cliff(events, city, baseline, max_ex):
    """C6: a source's future-event count dropped sharply vs baseline."""
    cur = Counter()
    for e in events:
        if ev_date(e) >= TODAY_ISO:
            cur[e.get("source") or "(none)"] += 1
    findings = []
    if baseline and city in baseline:
        prev = baseline[city]
        for src, prev_n in prev.items():
            now_n = cur.get(src, 0)
            if prev_n >= 10 and now_n < prev_n * 0.5:  # lost >half of a sizable source
                findings.append({"source": src, "was": prev_n, "now": now_n,
                                 "lost": prev_n - now_n})
    findings.sort(key=lambda f: -f["lost"])
    return {
        "code": "C6",
        "name": "COVERAGE-CLIFF",
        "severity": HIGH if findings else LOW,
        "count": len(findings),
        "desc": "A source lost >50% of its events vs the saved baseline "
                "(throttle, scraper break, or site change).",
        "examples": findings[:max_ex],
        "_current_counts": dict(cur),  # used by --save-baseline
    }


def check_field_health(events, max_ex):
    """C7: missing title/date, or encoding artifacts in titles."""
    no_date, no_title, artifacts = [], [], []
    for e in events:
        if not e.get("title"):
            no_title.append({"date": ev_date(e), "source": e.get("source")})
        if not ev_date(e):
            no_date.append({"title": e.get("title"), "source": e.get("source")})
        title = e.get("title") or ""
        hit = [a for a in _ENCODING_ARTIFACTS if a in title]
        if hit:
            artifacts.append({"title": title, "artifacts": hit,
                              "source": e.get("source")})
    total = len(no_date) + len(no_title) + len(artifacts)
    return {
        "code": "C7",
        "name": "FIELD-HEALTH",
        "severity": MED if (no_date or no_title) else (LOW if not artifacts else MED),
        "count": total,
        "desc": "Missing critical fields or encoding artifacts (%26, &amp;, &quot;) "
                "leaking into titles.",
        "examples": {
            "no_date": no_date[:max_ex],
            "no_title": no_title[:max_ex],
            "encoding_artifacts": artifacts[:max_ex],
        },
    }


def check_ongoing_dropped(events, max_ex):
    """C8: ongoing date-range events (past start, future end) should EXIST.

    Seasonal/multi-week events — scenic trains, summer exhibits, 'all summer'
    attractions, long recurring runs — have a start date in the past and an end
    date in the future. A healthy dataset always has some. ZERO is the signature
    of a scraper dropping the whole class as 'past' before checking end_date
    (the Deer Creek Express bug, dropped repeatedly in scraper.py). We flag a
    near-empty count as a likely systematic drop, and also surface any single
    event whose end_date is in the future but whose start was dropped to a
    suspiciously-late value (best-effort)."""
    from collections import defaultdict as _dd
    ongoing = []
    for e in events:
        d = ev_date(e); end = ev_end(e)
        if d and end and d <= TODAY_ISO <= end:
            ongoing.append(e)
    # Also recognize a fanned-out RECURRING SERIES that straddles today: the same
    # title on >=1 past date AND >=1 today/future date. The build represents long
    # recurring runs (e.g. Deer Creek Express, ~60 Mon/Thu/Fri/Sat dates) as dated
    # occurrences with no end_date, which the range test alone misses.
    by_title = _dd(list)
    for e in events:
        t = (e.get("title") or "").strip().lower()
        d = ev_date(e)
        if t and d:
            by_title[t].append(d)
    straddling_series = 0
    for t, dates in by_title.items():
        if len(dates) >= 3:
            if any(x < TODAY_ISO for x in dates) and any(x >= TODAY_ISO for x in dates):
                straddling_series += 1
    ongoing_total = len(ongoing) + straddling_series
    suspicious = (len(events) >= 500 and ongoing_total == 0)
    return {
        "code": "C8",
        "name": "ONGOING-DROPPED",
        "severity": MED if suspicious else LOW,
        "count": 0 if not suspicious else 1,
        "desc": "Date-range events (past start, future end) are MISSING entirely "
                "(0 found in a populated dataset) — signature of a scraper dropping "
                "ongoing/seasonal events as 'past' before checking end_date.",
        "examples": [{"ongoing_range_rows": len(ongoing),
                      "straddling_recurring_series": straddling_series,
                      "note": "0 of BOTH in a populated city = likely class-drop bug"}]
                     if suspicious else [{"ongoing_range_rows": len(ongoing),
                                          "straddling_recurring_series": straddling_series}],
    }


ALL_CHECKS = [
    check_recurring_dropped,
    check_multiday_gap,
    check_venue_time_collision,
    check_bad_dates,
    check_cross_source_dup,
    check_field_health,
    check_ongoing_dropped,
    # C6 handled separately (needs baseline + city)
]


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def fmt_examples(ex, indent="      "):
    out = []
    if isinstance(ex, dict):
        for sub, items in ex.items():
            if not items:
                continue
            out.append(f"{indent}{sub}: ({len(items)} shown)")
            for it in items:
                out.append(f"{indent}  - {json.dumps(it, ensure_ascii=False)}")
    else:
        for it in ex:
            out.append(f"{indent}- {json.dumps(it, ensure_ascii=False)}")
    return "\n".join(out)


def run_city(path, baseline, max_ex):
    city = city_from_path(path)
    events = load_events(path)
    results = [chk(events, max_ex) for chk in ALL_CHECKS]
    results.append(check_coverage_cliff(events, city, baseline, max_ex))
    return city, len(events), results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", help="audit only this city (slug, e.g. jackson)")
    ap.add_argument("--save-baseline", action="store_true",
                    help="write current per-source counts to data_quality_baseline.json")
    ap.add_argument("--max-examples", type=int, default=5)
    ap.add_argument("--glob", default=VIEW_GLOB)
    ap.add_argument("--json", metavar="PATH",
                    help="also write all findings to this JSON file (for the digest)")
    ap.add_argument("--gate", action="store_true",
                    help="exit non-zero ONLY on gateable HIGH findings (real data "
                         "bugs: C1/C2/C5/C7). C6 coverage-cliff is excluded — it "
                         "fires on transient CI throttles the resilience guard "
                         "already handles, so it must not block the data commit.")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob))
    if args.city:
        paths = [p for p in paths if city_from_path(p) == args.city]
    if not paths:
        print(f"No view files matched {args.glob!r}"
              + (f" for city {args.city!r}" if args.city else ""))
        sys.exit(2)

    baseline = {}
    if os.path.exists(BASELINE_FILE) and not args.save_baseline:
        try:
            baseline = json.load(open(BASELINE_FILE))
        except Exception:
            baseline = {}

    print("=" * 72)
    print(f"yoocal data-quality audit — {TODAY_ISO}")
    print("=" * 72)

    high_total = 0
    gateable_high = 0
    GATEABLE_CODES = {"C1", "C2", "C5", "C7"}  # real data bugs; NOT C6 (transient)
    new_baseline = {}
    findings_out = {"generated_at": TODAY_ISO, "cities": {}}

    for path in paths:
        city, n, results = run_city(path, baseline, args.max_examples)
        print(f"\n### {city}  ({n} events)")
        findings_out["cities"][city] = {"events": n, "findings": []}
        for r in results:
            if r["code"] == "C6":
                new_baseline[city] = r.pop("_current_counts")
            sev = r["severity"]
            if r["count"] and sev in (HIGH, MED):
                findings_out["cities"][city]["findings"].append({
                    "code": r["code"], "name": r["name"],
                    "severity": sev, "count": r["count"],
                })
            mark = {"HIGH": "‼", "MED": "•", "LOW": " "}[sev]
            line = f"  [{mark} {sev:4}] {r['code']} {r['name']}: {r['count']}"
            print(line)
            if r["count"] and sev in (HIGH, MED):
                print(f"        {r['desc']}")
                ex = fmt_examples(r["examples"])
                if ex:
                    print(ex)
            if sev == HIGH and r["count"]:
                high_total += r["count"]
                if r["code"] in GATEABLE_CODES:
                    gateable_high += r["count"]

    if args.save_baseline:
        with open(BASELINE_FILE, "w") as f:
            json.dump(new_baseline, f, indent=2)
        print(f"\nSaved baseline -> {BASELINE_FILE} "
              f"({sum(len(v) for v in new_baseline.values())} source-counts across "
              f"{len(new_baseline)} cities)")

    findings_out["high_total"] = high_total
    if args.json:
        with open(args.json, "w") as f:
            json.dump(findings_out, f, indent=2)
        print(f"\nWrote findings -> {args.json}")

    print("\n" + "=" * 72)
    print(f"HIGH-severity findings: {high_total}  "
          f"(gateable: {gateable_high}, non-gateable e.g. C6: {high_total - gateable_high})")
    print("=" * 72)
    if args.gate:
        sys.exit(1 if gateable_high else 0)
    sys.exit(1 if high_total else 0)


if __name__ == "__main__":
    main()
