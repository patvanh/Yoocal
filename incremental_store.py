#!/usr/bin/env python3
"""
incremental_store.py — durable per-event store with freshness tracking.

WHY THIS EXISTS
The old model re-scrapes every page of every source nightly and rebuilds from
scratch. For a source with 1000 stable events where 3 changed, it re-fetches all
1000 — slow, expensive (firecrawl), and fragile (a blocked fetch wipes the whole
source). This module is the foundation for an INCREMENTAL model:

  1. Fetch a source's LISTING only (sitemap/calendar) -> the set of event IDs it
     currently advertises. One cheap fetch.
  2. Diff that against what we already have stored.
  3. Only fetch DETAIL pages for genuinely new events. Keep everything else.
  4. A blocked listing fetch = "no updates today", not "source wiped".

This file provides the primitives only (IDs, hashing, store I/O, a read-only
diff). It changes NO live behavior — it's safe to import and exercise against the
real store without touching the pipeline. Cutover happens later, in shadow mode.

STORE SHAPE (evolves last_good_sources.json, backward-compatible):
  {
    "<source name>": {
      "count": int, "date": "YYYY-MM-DD", "low_streak": int,   # existing fields
      "events": [ { ...event..., "_id":..., "_first_seen":..., "_last_seen":...,
                    "_content_hash":... }, ... ]
    }, ...
  }
Events that predate this module simply get the _id/_first_seen/_last_seen/
_content_hash fields stamped on first pass; nothing else changes.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

MOUNTAIN = timezone(timedelta(hours=-6))

STORE_PATH = os.environ.get("YOOCAL_STORE_PATH", "last_good_sources.json")

# Fields whose change constitutes a *meaningful* event change (worth a refetch /
# a content-hash bump). Deliberately excludes volatile/derived fields like
# scraped_at, _all_sources, lat/lng jitter, and the freshness metadata itself.
_HASH_FIELDS = (
    "title", "date", "end_date", "start_time", "end_time",
    "venue_name", "location", "address", "description", "price", "is_free",
)


def today_iso() -> str:
    return datetime.now(MOUNTAIN).strftime("%Y-%m-%d")


def event_id(e: dict) -> str:
    """Stable identity for an event across days.

    Combines the detail-page link (or source) with title+date. Link alone is NOT
    unique: many sources reuse one venue/listing/calendar URL for dozens of
    distinct events (e.g. PLUNJ's 189 daily sessions all link to plunj.com/, the
    Park Record calendar page is the link for 25 different events). Title+date
    disambiguates those while still treating the same event on the same day as
    one identity across re-scrapes. Recurring events are correctly distinct
    because their dates differ."""
    link = (e.get("link") or "").strip().lower().rstrip("/")
    title = (e.get("title") or "").strip().lower()
    date = (e.get("date") or "")[:10]
    if link and link.startswith("http"):
        return f"url:{link}|{title}|{date}"
    src = (e.get("source") or "").strip().lower()
    return f"key:{src}|{title}|{date}"


def content_hash(e: dict) -> str:
    """Hash of the meaningful event fields, to detect real changes.

    Two records of the same event with identical _HASH_FIELDS hash equal even if
    their scraped_at / derived fields differ — so we don't refetch unchanged
    events. A changed title/time/venue/etc. flips the hash -> refetch candidate.
    """
    parts = []
    for f in _HASH_FIELDS:
        v = e.get(f)
        if isinstance(v, bool):
            v = "1" if v else "0"
        parts.append(f"{f}={(str(v).strip().lower() if v is not None else '')}")
    blob = "\u241f".join(parts)  # unit-separator join, collision-resistant
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def load_store(path: str | None = None) -> dict:
    """Load the store. Returns {} if absent. Never raises on missing file."""
    p = Path(path or STORE_PATH)
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_store(store: dict, path: str | None = None) -> None:
    """Write the store atomically (temp file + replace) so a crash mid-write
    can't corrupt the durable store."""
    p = Path(path or STORE_PATH)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def stamp_freshness(e: dict, day: str | None = None, *, first_seen: bool = False) -> dict:
    """Ensure an event carries _id/_content_hash/_first_seen/_last_seen.

    Idempotent: existing _first_seen is preserved unless first_seen=True forces
    a (re)stamp. Mutates and returns the same dict for convenience.
    """
    day = day or today_iso()
    e["_id"] = event_id(e)
    e["_content_hash"] = content_hash(e)
    if first_seen or not e.get("_first_seen"):
        e["_first_seen"] = e.get("_first_seen") or day
    e["_last_seen"] = day
    return e


def diff_listing(stored_events: list[dict],
                 advertised_ids: Iterable[str],
                 *, today: str | None = None) -> dict:
    """READ-ONLY diff for one source. Computes what an incremental run WOULD do.

    stored_events  : the events we already have for this source (from the store)
    advertised_ids : the event_id()s the source's listing currently advertises
                     (i.e. what a cheap listing fetch returned this run)

    Returns a report dict:
      {
        "new_ids":     [...],   # advertised but not stored -> would fetch detail
        "kept_ids":    [...],   # advertised and stored      -> keep, bump _last_seen
        "dropped_ids": [...],   # stored, future-dated, no longer advertised -> remove
        "stale_kept":  [...],   # stored & past-dated, ignored by listing (archived elsewhere)
        "counts": {...},
      }
    Touches nothing — pure computation, for shadow-mode validation.
    """
    today = today or today_iso()
    advertised = set(advertised_ids)
    stored_by_id = {}
    for e in stored_events:
        stored_by_id[e.get("_id") or event_id(e)] = e

    stored_ids = set(stored_by_id)
    new_ids = sorted(advertised - stored_ids)
    common_ids = advertised & stored_ids

    kept_ids, dropped_ids, stale_past = [], [], []
    for sid in stored_ids:
        e = stored_by_id[sid]
        is_future = (e.get("date") or "")[:10] >= today
        if sid in advertised:
            kept_ids.append(sid)
        elif is_future:
            # future event the source no longer lists -> cancelled/removed
            dropped_ids.append(sid)
        else:
            # past-dated and not in listing: normal (listings show upcoming only)
            stale_past.append(sid)

    return {
        "new_ids": new_ids,
        "kept_ids": sorted(kept_ids),
        "dropped_ids": sorted(dropped_ids),
        "stale_past_ids": sorted(stale_past),
        "counts": {
            "advertised": len(advertised),
            "stored": len(stored_ids),
            "new": len(new_ids),
            "kept": len(kept_ids),
            "dropped_future": len(dropped_ids),
            "stale_past": len(stale_past),
        },
    }


if __name__ == "__main__":
    # Self-check against the real store: stamp freshness in-memory (no write) and
    # report per-source counts + how many events share a stable id (dupes).
    store = load_store()
    print(f"store: {len(store)} sources")
    total = dup = 0
    seen = set()
    for src, blk in store.items():
        for e in blk.get("events", []):
            total += 1
            i = event_id(e)
            if i in seen:
                dup += 1
            seen.add(i)
    print(f"events: {total}, unique ids: {len(seen)}, cross-source id collisions: {dup}")
