"""test_strategies.py — run EVERY extraction strategy against EVERY discovered
source and report a matrix, so we learn which strategy wins on which source.

Unlike generic_city_scraper (which cascades and stops at the first hit), this
runs each strategy independently and records what each found. Output: a
source x strategy table of event counts, plus a sample of events per source.

Strategies tested:
  1. schema_org   — scrape_schema_org_events (free; JSON-LD / datetime attrs)
  2. firecrawl_llm— extract_events_from_url (Firecrawl render + Claude)
  (room to add: tockify API, wp-tribe API, ICS feed, etc.)

Usage:
  python3 test_strategies.py --city "park city utah" --min-score 0
  (min-score 0 = test ALL discovered candidates, not just high-scorers)
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

try:
    from schema_org_scraper import scrape_schema_org_events
except Exception:
    scrape_schema_org_events = None
try:
    from firecrawl_extractor import extract_events_from_url
except Exception:
    extract_events_from_url = None


def _domain(url):
    return urlparse(url).netloc.replace("www.", "")


def _future_only(events):
    today = date.today().isoformat()
    return [e for e in (events or []) if (e.get("date") or "")[:10] >= today]


def strat_schema(url, city, lat, lng):
    if not scrape_schema_org_events:
        return None, "unavailable"
    try:
        evs = scrape_schema_org_events(url, source_name=_domain(url),
                                       default_lat=lat, default_lng=lng,
                                       default_city=city) or []
        return _future_only(evs), None
    except Exception as ex:
        return None, str(ex)[:60]


def strat_firecrawl(url, city, lat, lng):
    if not extract_events_from_url:
        return None, "unavailable"
    try:
        evs = extract_events_from_url(url, _domain(url),
                                      default_lat=lat, default_lng=lng) or []
        return _future_only(evs), None
    except Exception as ex:
        return None, str(ex)[:60]


STRATEGIES = [("schema_org", strat_schema), ("firecrawl_llm", strat_firecrawl)]


def load_candidates(pending_path, city_hint, min_score):
    data = json.loads(Path(pending_path).read_text())
    runs = data.get("runs", [data]) if isinstance(data, dict) else [data]
    # pick the most recent NON-EMPTY run matching the city
    chosen = None
    for r in reversed(runs):
        if city_hint.lower() in (r.get("city") or "").lower() and r.get("candidates"):
            chosen = r
            break
    chosen = chosen or (runs[-1] if runs else {})
    cands = [c for c in chosen.get("candidates", []) if c.get("score", 0) >= min_score]
    # also include the full all_results list if present (so min_score=0 sees everything)
    if min_score <= 0 and chosen.get("all_results_for_review"):
        seen = {c["url"] for c in cands}
        for c in chosen["all_results_for_review"]:
            if c.get("url") and c["url"] not in seen:
                cands.append(c)
                seen.add(c["url"])
    return chosen.get("city", city_hint), cands


def run(city, lat, lng, pending_path="pending_sources.json", min_score=0):
    disc_city, cands = load_candidates(pending_path, city, min_score)
    print(f"\n{'='*72}\nStrategy test: {city} — {len(cands)} sources, "
          f"{len(STRATEGIES)} strategies each\n{'='*72}\n")

    rows = []
    all_events = []
    for i, c in enumerate(cands, 1):
        url = c["url"]
        dom = _domain(url)
        print(f"[{i}/{len(cands)}] {dom[:45]:45} (score {c.get('score',0)})")
        row = {"domain": dom, "url": url, "score": c.get("score", 0)}
        best = []
        for sname, sfn in STRATEGIES:
            evs, err = sfn(url, city, lat, lng)
            n = len(evs) if evs else 0
            row[sname] = n if not err else f"err"
            print(f"      {sname:14} -> {n if not err else 'ERR: '+str(err)}")
            if evs and len(evs) > len(best):
                best = evs
        row["best"] = len(best)
        rows.append(row)
        for e in best:
            e.setdefault("_source_domain", dom)
        all_events.extend(best)
        print()

    # Matrix summary
    print(f"{'='*72}\nMATRIX (events found per strategy)\n{'='*72}")
    hdr = f"{'source':40} {'score':>5} " + " ".join(f"{s:>14}" for s, _ in STRATEGIES) + f" {'BEST':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda x: -x["best"]):
        cells = " ".join(f"{str(r[s]):>14}" for s, _ in STRATEGIES)
        print(f"{r['domain'][:40]:40} {r['score']:>5} {cells} {r['best']:>6}")

    productive = [r for r in rows if r["best"] > 0]
    print(f"\n{'='*72}")
    print(f"{len(productive)}/{len(rows)} sources produced events | "
          f"{sum(r['best'] for r in rows)} total events (best-strategy per source)")
    # strategy win counts
    wins = {s: 0 for s, _ in STRATEGIES}
    for r in rows:
        best_s = max(((s, r[s]) for s, _ in STRATEGIES if isinstance(r[s], int)),
                     key=lambda x: x[1], default=(None, 0))
        if best_s[1] > 0:
            wins[best_s[0]] += 1
    print("strategy wins:", {k: v for k, v in wins.items()})
    print(f"{'='*72}")

    # stage for review
    Path("review_queue").mkdir(exist_ok=True)
    slug = city.lower().replace(" ", "-")
    out = Path("review_queue") / f"{slug}-strategytest.json"
    out.write_text(json.dumps({
        "city": city, "generated_at": date.today().isoformat(),
        "matrix": rows, "event_count": len(all_events), "events": all_events,
    }, indent=2))
    print(f"\nStaged {len(all_events)} events + matrix -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lng", type=float, required=True)
    ap.add_argument("--min-score", type=int, default=0)
    ap.add_argument("--pending", default="pending_sources.json")
    args = ap.parse_args()
    run(args.city, args.lat, args.lng, pending_path=args.pending, min_score=args.min_score)
