"""Resilience guard: prevent a partial/throttled scrape from overwriting good
data. Keyed by source name, works for every city automatically.

Problem it solves: the per-event-page scrapers (e.g. VPC sitemap, 145 pages)
get rate-limited from CI datacenter IPs, so a run may capture only a random
fraction (e.g. 15 of ~112). Whichever events survive is luck-of-timing, so any
event can vanish intermittently. This guard keeps the last KNOWN-GOOD set for a
source whose count collapses, and lets it self-heal on the next full scrape.

State file: last_good_sources.json
  { source_name: {"count": int, "date": "YYYY-MM-DD", "low_streak": int,
                  "events": [ ... ]} }

Rules:
- If incoming_count >= RETAIN_FRACTION * last_good_count -> healthy. Use incoming,
  refresh snapshot, reset low_streak.
- If incoming_count <  RETAIN_FRACTION * last_good_count -> degraded. Use the
  snapshot's events instead, increment low_streak, DON'T refresh the good count.
- If low_streak >= ACCEPT_LOW_AFTER consecutive degraded runs -> treat the new
  lower count as the real baseline (a genuine shrink, e.g. season ending), so we
  don't hold stale data forever. Accept incoming and refresh.
- New/unknown sources (no snapshot) are always accepted (nothing to compare to).
- Sources below MIN_BASELINE are exempt (too small for ratio logic to be useful).
"""
import json
import os
from collections import defaultdict
from datetime import datetime

STATE_FILE = "last_good_sources.json"
RETAIN_FRACTION = 0.50    # below 50% of last-good => degraded
ACCEPT_LOW_AFTER = 3      # after 3 straight low runs, accept the new normal
CATASTROPHIC_FRACTION = 0.20  # a drop below 20% of baseline is treated as
                              # failure/throttling, NEVER auto-accepted as the
                              # new normal — retained indefinitely until recovery
MIN_BASELINE = 8          # don't guard tiny sources
MAX_STORED_EVENTS = 100   # cap events stored per source (keeps state file small)


def _load_state(path=STATE_FILE):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state, path=STATE_FILE):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def apply_resilience_guard(all_events, today_iso=None, state_path=STATE_FILE):
    """Given the combined raw event list, group by source and substitute
    last-good data for any source whose count has collapsed. Returns the
    (possibly augmented) event list. Mutates + persists the state file.

    Returns (events_out, report) where report is a list of per-source dicts
    describing what happened (for logging / the digest)."""
    if today_iso is None:
        today_iso = datetime.now().strftime("%Y-%m-%d")
    state = _load_state(state_path)

    by_source = defaultdict(list)
    for e in all_events:
        by_source[e.get("source") or "(unknown)"].append(e)

    out = []
    report = []
    seen_sources = set()

    for source, evs in by_source.items():
        seen_sources.add(source)
        incoming = len(evs)
        snap = state.get(source)

        # No prior snapshot, or source too small to guard: accept as-is.
        if not snap or snap.get("count", 0) < MIN_BASELINE:
            out.extend(evs)
            state[source] = {"count": incoming, "date": today_iso,
                             "low_streak": 0, "events": evs[:MAX_STORED_EVENTS]}
            report.append({"source": source, "status": "baseline",
                           "incoming": incoming})
            continue

        good = snap.get("count", 0)
        if incoming >= RETAIN_FRACTION * good:
            # Healthy: use incoming, refresh snapshot.
            out.extend(evs)
            state[source] = {"count": incoming, "date": today_iso,
                             "low_streak": 0, "events": evs[:MAX_STORED_EVENTS]}
            report.append({"source": source, "status": "ok",
                           "incoming": incoming, "good": good})
        else:
            streak = snap.get("low_streak", 0) + 1
            catastrophic = incoming < CATASTROPHIC_FRACTION * good
            if streak >= ACCEPT_LOW_AFTER and not catastrophic:
                # Persisted low => accept as the new real baseline.
                out.extend(evs)
                state[source] = {"count": incoming, "date": today_iso,
                                 "low_streak": 0, "events": evs[:MAX_STORED_EVENTS]}
                report.append({"source": source, "status": "accepted_low",
                               "incoming": incoming, "good": good,
                               "streak": streak})
            else:
                # Degraded: substitute last-good events, keep good count.
                retained = snap.get("events") or []
                out.extend(retained)
                snap["low_streak"] = streak
                snap["date"] = today_iso  # note we saw it, but keep good count
                state[source] = snap
                report.append({"source": source, "status": "degraded_retained",
                               "incoming": incoming, "good": good,
                               "retained": len(retained), "streak": streak})

    _save_state(state, state_path)
    return out, report


def format_report(report):
    """One-line-per-source human summary, only for non-ok sources."""
    lines = []
    for r in report:
        if r["status"] == "degraded_retained":
            lines.append(
                f"  GUARD: {r['source']} scraped {r['incoming']} "
                f"(usual ~{r['good']}) — kept last-good {r['retained']} "
                f"events [low streak {r['streak']}]")
        elif r["status"] == "accepted_low":
            lines.append(
                f"  GUARD: {r['source']} low {r['incoming']} for "
                f"{r['streak']} runs — accepting as new baseline")
    return "\n".join(lines)
