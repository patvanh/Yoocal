#!/usr/bin/env python3
"""verify_events.py — Phase 1 of the review system.

Reads each event's stored source text (description + date_label + recurrence_text)
and asks the model whether the 5 extracted fields (title, date, start_time,
recurrence, venue) match it. Cross-checked, cached by content hash, scoped by
source/limit. Writes verification.json and prints a per-source error-rate report.

USAGE
  # See the prompt + a cost estimate WITHOUT calling the API (do this first):
  python3 verify_events.py --dry-run --source "Heber Valley Tourism" --limit 20

  # Real run, scoped + capped (cost guard). Cached events are skipped (free):
  python3 verify_events.py --source "Heber Valley Tourism" --limit 50

  # Re-print the report from existing verification.json without re-verifying:
  python3 verify_events.py --report-only

Requires ANTHROPIC_API_KEY in env (set -a; source .env; set +a).
"""
import os, sys, json, glob, hashlib, argparse, re
from collections import defaultdict

MODEL = "claude-haiku-4-5-20251001"   # cheap read; matches scraper_llm_health.py
CACHE = "verification.json"
FIELDS = ["title", "date", "start_time", "recurrence", "venue"]
# rough Haiku pricing (USD per 1M tokens) — adjust if your rate differs
PRICE_IN, PRICE_OUT = 1.00, 5.00

def load_all_events():
    evs = []
    for f in sorted(glob.glob("public/events-*.json")):
        d = json.load(open(f))
        evs += d.get("events", d) if isinstance(d, dict) else d
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

def extracted_fields(e):
    rec = e.get("recurrence") or "(none)"
    day = e.get("recurrence_day") or e.get("recurrence_days") or ""
    if day:
        rec = f"{rec} on {day}"
    return {
        "title": e.get("title") or "",
        "date": (e.get("date") or "")[:10] + (f" to {(e.get('end_date') or '')[:10]}" if e.get("end_date") else ""),
        "start_time": e.get("start_time") or "(none)",
        "recurrence": rec,
        "venue": e.get("venue_name") or e.get("location") or "(none)",
    }

def content_hash(e):
    blob = source_text(e) + "||" + json.dumps(extracted_fields(e), sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

def build_prompt(e):
    fields = extracted_fields(e)
    lines = "\n".join(f"  {k}: {fields[k]!r}" for k in FIELDS)
    return (
        "You verify scraped event data against its source text. For EACH field, "
        "decide if the extracted value is supported by the source text.\n"
        "verdict = 'match' (clearly supported), 'mismatch' (contradicted by the "
        "source), or 'unsure' (source doesn't say). For a mismatch, give the "
        "correct value from the source. Recurrence: 'weekly on Friday' must mean "
        "the source describes a repeating weekly event, NOT a one-time event that "
        "happens to fall on a Friday or names two days like 'Fri & Sat'.\n\n"
        "Return ONLY this JSON, no prose, no markdown:\n"
        '{"fields":{"title":{"verdict":"...","correct":null,"note":"..."},'
        '"date":{...},"start_time":{...},"recurrence":{...},"venue":{...}},'
        '"overall_confidence":0.0}\n\n'
        f"SOURCE TEXT:\n{source_text(e)}\n\n"
        f"EXTRACTED FIELDS:\n{lines}\n\n"
        "JSON only:"
    )

def parse_response(raw):
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)

def report(cache, events_by_id):
    # per-source per-field tallies
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    worst = []
    for eid, rec in cache.items():
        if "fields" not in rec:
            continue
        src = rec.get("source", "(unknown)")
        mism = []
        for f in FIELDS:
            v = (rec["fields"].get(f) or {}).get("verdict", "unsure")
            agg[src][f][v] += 1
            if v == "mismatch":
                mism.append(f)
        if mism:
            worst.append((src, rec.get("title", ""), mism, rec["fields"]))
    print(f"\n{'source':32} {'n':>4}  " + "  ".join(f"{f[:9]:>11}" for f in FIELDS))
    print(f"{'':32} {'':>4}  " + "  ".join(f"{'mism%':>11}" for _ in FIELDS))
    for src in sorted(agg, key=lambda s: -sum(agg[s][FIELDS[0]].values())):
        n = sum(agg[src][FIELDS[0]].values())
        cells = []
        for f in FIELDS:
            t = agg[src][f]; tot = sum(t.values()) or 1
            cells.append(f"{round(100*t['mismatch']/tot):>10}%")
        print(f"{src[:32]:32} {n:>4}  " + "  ".join(cells))
    print(f"\nMISMATCHES ({len(worst)} events with >=1 field flagged):")
    for src, title, mism, fdetail in worst[:30]:
        print(f"  [{src[:20]}] {title[:50]!r} -> {', '.join(mism)}")
        for f in mism:
            d = fdetail[f]
            print(f"       {f}: {d.get('note','')}  (correct: {d.get('correct')})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    events = load_all_events()
    by_id = {event_id(e): e for e in events}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    if args.report_only:
        report(cache, by_id); return

    # select work: scoped by source, skip cached-and-unchanged, cap by limit
    todo = []
    for e in events:
        if args.source and e.get("source") != args.source:
            continue
        if not source_text(e):           # nothing to verify against
            continue
        eid = event_id(e); ch = content_hash(e)
        if eid in cache and cache[eid].get("content_hash") == ch:
            continue                     # unchanged -> free
        todo.append((eid, ch, e))
    todo = todo[: args.limit]

    if args.dry_run:
        print(f"DRY RUN — would verify {len(todo)} event(s) "
              f"(source={args.source or 'ALL'}, limit={args.limit}); 0 API calls.")
        if todo:
            _, _, e = todo[0]
            p = build_prompt(e)
            approx_in = (len(p) // 4) * len(todo)        # ~4 chars/token
            approx_out = 250 * len(todo)
            est = approx_in / 1e6 * PRICE_IN + approx_out / 1e6 * PRICE_OUT
            print(f"\n--- SAMPLE PROMPT (event 1 of {len(todo)}) ---\n{p}\n")
            print(f"--- est. cost for {len(todo)} events on {args.model}: ${est:.4f} ---")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set. Run: set -a; source .env; set +a"); sys.exit(1)
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    done = failed = 0
    for eid, ch, e in todo:
        try:
            resp = client.messages.create(
                model=args.model, max_tokens=600,
                messages=[{"role": "user", "content": build_prompt(e)}],
            )
            data = parse_response(resp.content[0].text)
            cache[eid] = {
                "source": e.get("source"), "title": e.get("title"),
                "date": (e.get("date") or "")[:10], "content_hash": ch,
                "model": args.model, "fields": data.get("fields", {}),
                "overall_confidence": data.get("overall_confidence"),
            }
            done += 1
        except Exception as ex:
            failed += 1
            print(f"  verify failed [{e.get('title','')[:40]}]: {ex}")
        if done and done % 10 == 0:
            json.dump(cache, open(CACHE, "w"), indent=2)   # checkpoint
    json.dump(cache, open(CACHE, "w"), indent=2)
    print(f"\nverified {done}, failed {failed}, cached total {len(cache)} -> {CACHE}")
    report(cache, by_id)

if __name__ == "__main__":
    main()
