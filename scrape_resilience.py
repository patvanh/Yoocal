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
CATASTROPHIC_ACCEPT_AFTER = 5  # a catastrophic-but-PERSISTENT level (held this
                               # many straight runs) is real, not a blip, so
                               # accept it — otherwise a source that legitimately
                               # shrinks a lot (e.g. sitemap->Firecrawl) is frozen
                               # on stale data forever.
CATASTROPHIC_FRACTION = 0.20  # a drop below 20% of baseline is treated as
                              # failure/throttling, NEVER auto-accepted as the
                              # new normal — retained indefinitely until recovery
MIN_BASELINE = 8          # don't guard tiny sources
# (cap removed) retain the FULL event set so a failed source recovers fully.


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


def _future_only(events, today_iso):
    """Keep only events on/after today (or with a future end_date). Prevents a
    long-failed source's frozen snapshot from serving events that have since
    passed, and keeps the state file from hoarding stale rows."""
    out = []
    for e in events:
        d = (e.get("date") or "")[:10]
        end = (e.get("end_date") or "")[:10]
        if (d and d >= today_iso) or (end and end >= today_iso):
            out.append(e)
    return out


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
                             "low_streak": 0, "events": evs}
            report.append({"source": source, "status": "baseline",
                           "incoming": incoming})
            continue

        good = snap.get("count", 0)
        if incoming >= RETAIN_FRACTION * good:
            # Healthy: refresh the snapshot — but UNION with stored events so the
            # store never SHRINKS. A scrape can be healthy (above the retain
            # threshold) yet still smaller than what we already know, e.g. when an
            # incremental-maintained source has a complete 238-event store but the
            # nightly full scrape is rate-limited to 160. Replacing outright would
            # discard the extra known events (and undo incremental's work every
            # night). Unioning keeps the larger, complete set. Dedup by
            # (normalized title, date); incoming wins on tie (freshest fields).
            _stored = _future_only(snap.get("events") or [], today_iso)
            def _k(e):
                t = "".join((e.get("title") or "").lower().split())
                return (t, (e.get("date") or "")[:10])
            _seen = set()
            _union = []
            for e in evs + _stored:  # incoming first -> fresher fields win on tie
                k = _k(e)
                if k in _seen:
                    continue
                _seen.add(k)
                _union.append(e)
            out.extend(_union)
            state[source] = {"count": len(_union), "date": today_iso,
                             "low_streak": 0, "events": _union}
            report.append({"source": source, "status": "ok",
                           "incoming": incoming, "good": good,
                           "unioned": len(_union)})
        else:
            streak = snap.get("low_streak", 0) + 1
            catastrophic = incoming < CATASTROPHIC_FRACTION * good
            accept = (streak >= ACCEPT_LOW_AFTER and not catastrophic) or \
                     (streak >= CATASTROPHIC_ACCEPT_AFTER)
            if accept:
                # Persisted low => accept as the new real baseline.
                out.extend(evs)
                state[source] = {"count": incoming, "date": today_iso,
                                 "low_streak": 0, "events": evs}
                report.append({"source": source, "status": "accepted_low",
                               "incoming": incoming, "good": good,
                               "streak": streak})
            else:
                # Degraded: retain last-good events so a throttled scrape doesn't
                # gut the source — but UNION with the incoming events, so any NEW
                # events the current (partial) scrape captured are still kept.
                # Without this, a brand-new event (e.g. Midway Swiss Days, freshly
                # added to a throttled source) would be dropped because it's not
                # in the older snapshot. Dedup by (normalized title, date).
                retained = _future_only(snap.get("events") or [], today_iso)
                def _k(e):
                    t = "".join((e.get("title") or "").lower().split())
                    return (t, (e.get("date") or "")[:10])
                seen_keys = set()
                unioned = []
                for e in retained + evs:  # retained first (last-good wins on tie)
                    k = _k(e)
                    if k in seen_keys:
                        continue
                    seen_keys.add(k)
                    unioned.append(e)
                out.extend(unioned)
                snap["low_streak"] = streak
                snap["date"] = today_iso  # note we saw it, but keep good count
                state[source] = snap
                report.append({"source": source, "status": "degraded_retained",
                               "incoming": incoming, "good": good,
                               "retained": len(retained), "unioned": len(unioned),
                               "streak": streak})

    # ── Totally-missing sources ──────────────────────────────────────────
    # The loop above only sees sources PRESENT in this scrape. A source that
    # returns ZERO events (a total CI failure, not a partial collapse) never
    # appears in by_source, so it would silently vanish — the exact gap that
    # let "Center for the Arts Jackson Hole" (208 -> 0) gut the Jackson view
    # despite being in last_good. Catch sources in state that we did NOT see at
    # all this run and retain their last-good events (same low-streak logic).
    for source, snap in list(state.items()):
        if source in seen_sources:
            continue
        good = snap.get("count", 0)
        if good < MIN_BASELINE:
            continue  # too small to guard
        streak = snap.get("low_streak", 0) + 1
        retained = _future_only(snap.get("events") or [], today_iso)
        if retained:
            out.extend(retained)
        snap["low_streak"] = streak
        snap["date"] = today_iso
        state[source] = snap
        report.append({"source": source, "status": "missing_retained",
                       "incoming": 0, "good": good,
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
        elif r["status"] == "missing_retained":
            lines.append(
                f"  GUARD: {r['source']} returned NOTHING "
                f"(usual ~{r['good']}) — kept last-good {r['retained']} "
                f"events [missing streak {r['streak']}]")
        elif r["status"] == "accepted_low":
            lines.append(
                f"  GUARD: {r['source']} low {r['incoming']} for "
                f"{r['streak']} runs — accepting as new baseline")
    return "\n".join(lines)
