#!/usr/bin/env python3
"""apply_corrections.py — applies reviewed llm_extract proposals to events.

NON-DESTRUCTIVE in this form: reads extracted_corrections.json + events, applies
high-confidence proposals (recurrence/venue/time; NEVER date), and writes a
PREVIEW to corrected_preview.json plus a change report. Wiring into the build is
a separate step done only after the preview is reviewed.

Maps llm_extract's normalized recurrence to fan-out's actual encoding:
  weekly/daily -> recurrence="weekly", recurrence_days="Mon,Tue,..."
  monthly_nth + nth list [1,3] -> SPLIT into two records: monthly_nth_1 +
    monthly_nth_3 (fan-out takes a single ordinal per record)
  none -> clears recurrence
Venue/time -> field overwrite. Date/end_date -> never applied (guard).
"""
import json, sys, hashlib, argparse, glob
from collections import Counter

CONF_GATE = 0.85
CORR = "extracted_corrections.json"

def load_events():
    evs = []
    for f in sorted(glob.glob("public/events-*.json")):
        d = json.load(open(f)); evs += d.get("events", d) if isinstance(d, dict) else d
    return evs

def event_id(e):
    base = f"{e.get('title','')}|{(e.get('date') or '')[:10]}|{e.get('source','')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

def _norm_days(v):
    if isinstance(v, list): return [str(x).strip().capitalize() for x in v if x]
    if isinstance(v, str): return [x.strip().capitalize() for x in v.replace("|", ",").split(",") if x.strip()]
    return []

def _series_already_ended(e):
    """True if the event's existing bounds put its last occurrence at/before today."""
    import datetime as _dt
    today = _dt.date.today().isoformat()
    occ = [o[:10] for o in (e.get("occurrence_dates") or []) if o]
    last = (e.get("end_date") or "")[:10] or (max(occ) if occ else "")
    return bool(last and last <= today)

def apply_to_event(e, proposal):
    """Return a list of corrected event copies (usually 1; >1 for multi-nth)."""
    base = dict(e)
    def newval(f):
        d = proposal.get(f)
        return d["new"] if isinstance(d, dict) and "new" in d else None

    # simple field overwrites (never date/end_date)
    _CANON = {"Music","Arts & Theater","Food & Drink","Outdoors","Running & Races",
              "Sports","Family & Kids","Wellness","Nightlife","Education & Talks","Community"}
    if newval("venue_name"): base["venue_name"] = newval("venue_name")
    if newval("start_time"): base["start_time"] = newval("start_time")
    if newval("end_time"):   base["end_time"]   = newval("end_time")
    if newval("address"):    base["address"]    = newval("address")
    if newval("description"):base["description"]= newval("description")
    if newval("price"):      base["price"]      = newval("price")
    if newval("is_free") is not None: base["is_free"] = newval("is_free")
    _cat = newval("category")
    if _cat in _CANON:
        base["categories"] = [_cat]

    rec = newval("recurrence")
    if rec is None:
        return [base]  # no recurrence change
    # Only FILL missing recurrence or REDUCE to none. Never CHANGE an existing
    # recurrence value: a fanned record may rely on bounds not present here, so
    # re-asserting it can project phantom future dates (e.g. Weekly Stillness).
    _existing_rec = (e.get("recurrence") or "").strip()
    if rec not in ("none", "") and _existing_rec:
        return [base]  # already recurring -> leave recurrence alone (venue/time still applied)

    days = _norm_days(newval("recurrence_days") or e.get("recurrence_days") or e.get("recurrence_day"))
    nth = newval("recurrence_nth")

    if rec in ("none", ""):
        base["recurrence"] = ""
        base.pop("recurrence_day", None); base.pop("recurrence_days", None)
        return [base]

    if rec in ("weekly", "biweekly", "daily"):
        base["recurrence"] = "weekly"
        if rec == "daily" and not days:
            days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        base["recurrence_days"] = ",".join(days) if days else base.get("recurrence_days")
        base.pop("recurrence_day", None)
        # preserve existing bounds so fan-out doesn't project past the real run
        if e.get("end_date"): base["end_date"] = e["end_date"]
        if e.get("occurrence_dates"): base["occurrence_dates"] = e["occurrence_dates"]
        return [base]

    if rec == "monthly_nth":
        if not days:
            return [base]  # can't encode without a weekday
        ords = nth if isinstance(nth, list) and nth else [1]
        out = []
        for o in ords:
            c = dict(base)
            c["recurrence"] = f"monthly_nth_{o}"
            c["recurrence_day"] = days[0]
            c.pop("recurrence_days", None)
            out.append(c)
        return out

    return [base]  # unknown recurrence -> leave as-is

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    if not glob.glob(CORR):
        print(f"{CORR} not found — run llm_extract.py first."); sys.exit(1)
    corr = json.load(open(CORR))
    events = load_events()
    changed, added, preview = 0, 0, []
    field_counts = Counter()
    for e in events:
        eid = event_id(e)
        rec = corr.get(eid)
        prop = rec.get("proposal") if rec else None
        if not prop:
            continue
        gated = {f: d for f, d in prop.items()
                 if f not in ("date", "end_date") and isinstance(d, dict)
                 and float(d.get("conf", 0)) >= CONF_GATE}
        if not gated:
            continue
        result = apply_to_event(e, gated)
        for f in gated: field_counts[f] += 1
        changed += 1
        if len(result) > 1: added += len(result) - 1
        preview.append({"id": eid, "title": e.get("title"), "applied": list(gated.keys()),
                        "n_records": len(result),
                        "result_recurrence": [r.get("recurrence") for r in result]})
    json.dump(preview, open("corrected_preview.json", "w"), indent=2)
    print(f"events corrected: {changed}  (extra records from multi-nth split: +{added})")
    print("fields applied:", dict(field_counts))
    print("\nsample (first 20):")
    for p in preview[:20]:
        print(f"  {p['title'][:46]!r} <- {p['applied']}  -> {p['n_records']} rec {p['result_recurrence']}")

if __name__ == "__main__":
    main()
