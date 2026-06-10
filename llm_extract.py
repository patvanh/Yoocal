#!/usr/bin/env python3
"""llm_extract.py — reusable LLM extraction layer (review system, Phase 1.5).

SOURCE- AND CITY-AGNOSTIC. The design principle: scrapers do dumb fetching and
retain raw text (description / date_label / recurrence_text); THIS pass does the
understanding. Any future city works automatically as long as its scraper keeps
the text. It reads each event's source text, independently extracts the canonical
fields, and writes NON-DESTRUCTIVE proposed corrections to extracted_corrections.json
(it never overwrites your events). You review; a later build hook applies the
high-confidence ones.

Normalized output schema (pipeline-agnostic; an adapter maps it to fan-out encoding):
  title, date(YYYY-MM-DD), end_date, start_time, end_time,
  recurrence ∈ none|daily|weekly|biweekly|monthly_nth|custom,
  recurrence_days [weekday names], recurrence_nth [1..5] (for "1st & 3rd"),
  venue_name, plus per-field confidence 0..1.

USAGE
  # Prompt + cost preview, no API calls (do this first):
  python3 llm_extract.py --dry-run --source "Heber Valley Tourism" --limit 20
  # Real run, scoped + capped; cached-unchanged events are free:
  python3 llm_extract.py --source "Heber Valley Tourism" --limit 25
  # Re-print proposed corrections from the existing file:
  python3 llm_extract.py --report-only

Requires ANTHROPIC_API_KEY (set -a; source .env; set +a).
"""
import os, sys, json, glob, hashlib, argparse, re
from collections import defaultdict

MODEL = "claude-haiku-4-5-20251001"
OUT = "extracted_corrections.json"
PRICE_IN, PRICE_OUT = 1.00, 5.00
# fields we propose corrections for (high-value, the ones that break)
PROPOSE = ["date", "end_date", "start_time", "recurrence", "recurrence_days",
           "recurrence_nth", "venue_name"]
CONF_GATE = 0.75   # only PROPOSE a change at/above this confidence

def load_all_events():
    evs = []
    for f in sorted(glob.glob("public/events-*.json")):
        d = json.load(open(f))
        for e in (d.get("events", d) if isinstance(d, dict) else d):
            e.setdefault("_file", f)
            evs.append(e)
    return evs

def event_id(e):
    base = f"{e.get('title','')}|{(e.get('date') or '')[:10]}|{e.get('source','')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

def source_text(e):
    parts = []
    for k in ["description", "date_label", "recurrence_text"]:
        v = e.get(k)
        if v and str(v).strip():
            parts.append(f"{k}: {str(v).strip()}")
    return "\n".join(parts)

def text_hash(e):
    return hashlib.sha1(source_text(e).encode("utf-8")).hexdigest()[:16]

def existing_view(e):
    return {
        "date": (e.get("date") or "")[:10] or None,
        "end_date": (e.get("end_date") or "")[:10] or None,
        "start_time": e.get("start_time") or None,
        "recurrence": e.get("recurrence") or "none",
        "recurrence_days": e.get("recurrence_days") or e.get("recurrence_day") or None,
        "recurrence_nth": None,
        "venue_name": e.get("venue_name") or e.get("location") or None,
    }

def build_prompt(e):
    return (
        "Extract structured event data from the source text below. Return ONLY "
        "JSON in EXACTLY this schema, no prose, no markdown. Use null where the "
        "text does not state a value — never guess.\n"
        "{\n"
        '  "date": "YYYY-MM-DD or null (the first/next occurrence)",\n'
        '  "end_date": "YYYY-MM-DD or null (series end or multi-day end)",\n'
        '  "start_time": "h:MM AM/PM or null",\n'
        '  "end_time": "h:MM AM/PM or null",\n'
        '  "recurrence": "one of: none, daily, weekly, biweekly, monthly_nth, custom",\n'
        '  "recurrence_days": ["weekday names like Monday"] or null,\n'
        '  "recurrence_nth": [1,3] for \"1st & 3rd\" monthly patterns, else null,\n'
        '  "venue_name": "the specific place/business name if stated, else null",\n'
        '  "confidence": {"date":0.0,"end_date":0.0,"start_time":0.0,"recurrence":0.0,"venue_name":0.0}\n'
        "}\n"
        "Rules: 'Daily, Mon - Sat' => recurrence daily (or weekly with all six "
        "days). '1st & 3rd Tuesday' => monthly_nth, days [Tuesday], nth [1,3]. "
        "'Fri & Sat' with no span => NOT recurring (a two-day event); recurrence "
        "none. A venue_name is a place like 'Folklore Bookshop', not a city like "
        "'Heber Valley, UT' (that is null).\n\n"
        f"Event title (context): {e.get('title','')}\n\n"
        f"SOURCE TEXT:\n{source_text(e)}\n\n"
        "JSON only:"
    )

def parse_response(raw):
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)

def diff_proposal(existing, extracted, src_text="", today=None):
    """Return {field: {old, new, conf}} for fields the model is confident about
    AND that differ from existing. Non-destructive — just a proposal.
    DATE GUARD: never propose date/end_date unless the source has an explicit
    4-digit year, and never propose a past date (the model guesses years wrong
    when the source omits them, which would drop events into the past)."""
    import re as _re, datetime as _dt
    conf = extracted.get("confidence") or {}
    today = today or _dt.date.today().isoformat()
    has_year = bool(_re.search(r"\b20\d{2}\b", src_text or ""))
    def _date_ok(v):
        if not has_year:
            return False               # source has no year -> don't touch date
        try:
            return v[:10] >= today      # never move into the past
        except Exception:
            return False
    out = {}
    for f in PROPOSE:
        new = extracted.get(f)
        if new in (None, "", [], "none") and f != "recurrence":
            continue
        old = existing.get(f)
        if f in ("date", "end_date") and not _date_ok(new):
            continue
        # normalize list compare
        norm = lambda v: tuple(v) if isinstance(v, list) else v
        if norm(new) == norm(old):
            continue
        c = conf.get(f if f in conf else f.split("_")[0], conf.get("recurrence", 0)) \
            if f.startswith("recurrence") else conf.get(f, 0)
        try: c = float(c)
        except (TypeError, ValueError): c = 0.0
        if c < CONF_GATE:
            continue
        out[f] = {"old": old, "new": new, "conf": round(c, 2)}
    return out

def report(store):
    by_src = defaultdict(lambda: defaultdict(int)); n_src = defaultdict(int)
    proposals = []
    for eid, rec in store.items():
        if "proposal" not in rec: continue
        s = rec.get("source", "(unknown)"); n_src[s] += 1
        for f in rec["proposal"]:
            by_src[s][f] += 1
        if rec["proposal"]:
            proposals.append(rec)
    print(f"\n{'source':32} {'n':>4}  proposed field corrections")
    for s in sorted(n_src, key=lambda x: -n_src[x]):
        flds = ", ".join(f"{f}×{c}" for f, c in sorted(by_src[s].items(), key=lambda kv:-kv[1]))
        print(f"  {s[:30]:30} {n_src[s]:>4}  {flds}")
    changed = [r for r in proposals if r["proposal"]]
    print(f"\nPROPOSED CORRECTIONS ({len(changed)} events; non-destructive, review before apply):")
    for r in changed[:40]:
        print(f"  [{r.get('source','')[:18]}] {r.get('title','')[:46]!r}")
        for f, d in r["proposal"].items():
            print(f"       {f}: {d['old']!r} -> {d['new']!r}  (conf {d['conf']})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source"); ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    events = load_all_events()
    store = json.load(open(OUT)) if os.path.exists(OUT) else {}
    if args.report_only:
        report(store); return

    todo = []
    for e in events:
        if args.source and e.get("source") != args.source: continue
        if not source_text(e): continue
        eid = event_id(e); th = text_hash(e)
        if eid in store and store[eid].get("text_hash") == th: continue
        todo.append((eid, th, e))
    todo = todo[: args.limit]

    if args.dry_run:
        print(f"DRY RUN — would extract {len(todo)} event(s) "
              f"(source={args.source or 'ALL'}, limit={args.limit}); 0 API calls.")
        if todo:
            _, _, e = todo[0]; p = build_prompt(e)
            est = (len(p)//4*len(todo))/1e6*PRICE_IN + 300*len(todo)/1e6*PRICE_OUT
            print(f"\n--- SAMPLE PROMPT (1 of {len(todo)}) ---\n{p}\n")
            print(f"--- est cost for {len(todo)} on {args.model}: ${est:.4f} ---")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set. Run: set -a; source .env; set +a"); sys.exit(1)
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    done = failed = 0
    for eid, th, e in todo:
        try:
            resp = client.messages.create(
                model=args.model, max_tokens=700,
                messages=[{"role": "user", "content": build_prompt(e)}])
            extracted = parse_response(resp.content[0].text)
            store[eid] = {
                "source": e.get("source"), "title": e.get("title"),
                "date": (e.get("date") or "")[:10], "text_hash": th,
                "extracted": extracted,
                "proposal": diff_proposal(existing_view(e), extracted, source_text(e)),
            }
            done += 1
        except Exception as ex:
            failed += 1; print(f"  extract failed [{e.get('title','')[:40]}]: {ex}")
        if done and done % 10 == 0:
            json.dump(store, open(OUT, "w"), indent=2)
    json.dump(store, open(OUT, "w"), indent=2)
    print(f"\nextracted {done}, failed {failed}, total {len(store)} -> {OUT}")
    report(store)

if __name__ == "__main__":
    main()
