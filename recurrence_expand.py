"""recurrence_expand.py — expand recurring event definitions into individual
dated occurrences.

Sources like VPC's API return ONE record per recurring series, with the pattern
stated in plain text (e.g. "Recurring weekly on Monday, Thursday") plus start/
end dates. To match a per-date events list, each series must be fanned out into
one event per occurrence date.

GENERAL by design — reads the stated pattern, no per-site logic:
  - "weekly on <days>"      -> those weekdays each week in range
  - "every week day"/"daily on weekdays" -> Mon-Fri
  - "daily"/"every day"     -> every day in range
  - "every other week on <days>" -> biweekly
  - "monthly"               -> same day-of-month each month
  - one-time (no recurrence) -> single event on its start date

Always BOUNDED: occurrences only within [startDate, endDate]. If endDate is
missing, cap at a horizon (default 365 days) so a weekly event doesn't project
forever. (Matches the standing rule: bound projection to real end, never emit
phantom far-future dates.)
"""
from __future__ import annotations
import re
from datetime import date, datetime, timedelta

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
    "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}
_HORIZON_DAYS = 180
_MAX_OCCURRENCES = 60  # cap per series — daily events shouldn't flood the
                       # calendar with 180 rows; live data tops out ~60.


def _to_date(v):
    """Parse an ISO date/datetime (or 'YYYY-MM-DD') into a date, or None."""
    if not v:
        return None
    s = str(v)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _named_days(text):
    """Extract weekday indices named in a recurrence string."""
    days = set()
    low = text.lower()
    for name, idx in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", low):
            days.add(idx)
    return days


def expand_occurrences(recurrence, start, end, horizon_days=_HORIZON_DAYS,
                       today=None):
    """Return a list of date objects on which the event occurs.

    recurrence: the pattern string (may be empty/None for one-time events)
    start, end: ISO date strings or date objects (end may be None)
    """
    today = today or date.today()
    sd = start if isinstance(start, date) else _to_date(start)
    ed = end if isinstance(end, date) else _to_date(end)
    if not sd:
        return []
    # never emit dates before today (past occurrences are not useful)
    range_start = max(sd, today)
    horizon = today + timedelta(days=horizon_days)
    range_end = min(ed, horizon) if ed else horizon
    if range_end < range_start:
        return []

    rec = (recurrence or "").strip().lower()

    # one-time event
    if not rec or "recur" not in rec and "every" not in rec and "daily" not in rec \
            and "weekly" not in rec and "monthly" not in rec:
        return [sd] if range_start <= sd <= range_end else (
            [range_start] if sd <= today <= range_end else [])

    occ = []
    d = range_start

    # every weekday (Mon-Fri)
    if "week day" in rec or "weekday" in rec or "every business day" in rec:
        while d <= range_end:
            if d.weekday() < 5:
                occ.append(d)
            d += timedelta(days=1)
        return occ

    # daily / every day
    if "daily" in rec or "every day" in rec:
        while d <= range_end:
            occ.append(d)
            d += timedelta(days=1)
        return occ

    # weekly / biweekly on named days
    days = _named_days(rec)
    biweekly = "every other" in rec or "biweekly" in rec or "bi-weekly" in rec
    if days:
        # anchor for biweekly parity = the series start week
        anchor = sd
        while d <= range_end:
            if d.weekday() in days:
                if biweekly:
                    weeks = (d - anchor).days // 7
                    if weeks % 2 == 0:
                        occ.append(d)
                else:
                    occ.append(d)
            d += timedelta(days=1)
        return occ

    # monthly (same day-of-month as start)
    if "monthly" in rec or "every month" in rec:
        dom = sd.day
        y, mo = range_start.year, range_start.month
        while True:
            try:
                cand = date(y, mo, dom)
            except ValueError:
                cand = None
            if cand and range_start <= cand <= range_end:
                occ.append(cand)
            if date(y, mo, 1) > range_end:
                break
            mo += 1
            if mo > 12:
                mo = 1; y += 1
            if y > range_end.year + 1:
                break
        return occ

    # weekly with no named day -> use the start's weekday
    if "weekly" in rec:
        wd = sd.weekday()
        while d <= range_end:
            if d.weekday() == wd:
                occ.append(d)
            d += timedelta(days=1)
        return occ

    # unknown pattern -> at least emit the start date
    return [sd] if range_start <= sd <= range_end else []


def expand_event(ev, horizon_days=_HORIZON_DAYS, today=None):
    """Given an event dict with 'recurrence' + start/end, return a list of event
    dicts, one per occurrence date (date set in 'date' as YYYY-MM-DD). A
    one-time event yields a single dict. Non-recurring events pass through."""
    rec = ev.get("recurrence") or ""
    start = ev.get("startDate") or ev.get("start_date") or ev.get("date")
    end = ev.get("endDate") or ev.get("end_date")
    dates = expand_occurrences(rec, start, end, horizon_days, today)
    if not dates:
        return [ev]
    # cap per series: daily/high-frequency events shouldn't produce 180 rows.
    # Keep the soonest _MAX_OCCURRENCES (the near-term ones matter most).
    if len(dates) > _MAX_OCCURRENCES:
        dates = sorted(dates)[:_MAX_OCCURRENCES]
    out = []
    for d in dates:
        e2 = dict(ev)
        e2["date"] = d.isoformat()
        e2["_expanded_from_recurrence"] = bool(rec)
        out.append(e2)
    return out


if __name__ == "__main__":
    # quick self-test
    tests = [
        ("Recurring weekly on Monday, Thursday, Friday", "2026-06-01", "2026-06-30"),
        ("Recurring every week day", "2026-06-01", "2026-06-14"),
        ("Recurring weekly on Friday", "2026-06-01", "2026-08-31"),
        ("", "2026-07-04", None),  # one-time
        ("Recurring every other week on Saturday", "2026-06-06", "2026-07-31"),
    ]
    for rec, s, e in tests:
        occ = expand_occurrences(rec, s, e, today=date(2026, 6, 1))
        print(f"{rec[:40] or '(one-time)':40} {s}->{e}: {len(occ)} dates "
              f"-> {[d.isoformat() for d in occ[:5]]}{'...' if len(occ)>5 else ''}")
