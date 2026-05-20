"""LLM-based resolver for ambiguous event quality issues.

Reads audit_issues.json, picks the issue types that need source-URL judgment
(can't be fixed by deterministic rules), fetches each event's source page,
and asks Claude for a structured resolution.

Resolvable issue types:
  - title_venue_only:  "Live Music at Silver Lake" → fetch source → extract artist
  - multi_day_span:    Span > 1 day → fetch source → confirm single vs split

Safeguards:
  - MAX_RESOLVES_PER_RUN caps spend at ~$0.25/day worst case
  - Each fetch limited to 50 KB to keep token usage bounded
  - Confidence threshold: only apply changes Claude marks "high"
  - Low-confidence resolutions log to llm_resolve_uncertain.json for human review

Environment:
  ANTHROPIC_API_KEY  required

Output:
  Updates the relevant public/events-*.json in place
  Writes llm_resolve_log.json (everything attempted)
  Writes llm_resolve_uncertain.json (low-confidence, needs human eyes)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-5-20250929"
MAX_RESOLVES_PER_RUN = 30
FETCH_MAX_BYTES = 50_000
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

# Issue types this resolver handles
RESOLVABLE_TYPES = {"title_venue_only", "multi_day_span", "title_truncated"}

CITY_FILES = {
    "park-city": "public/events.json",
    "elkhart-lake": "public/events-elkhartlake.json",
    "heber": "public/events-heber.json",
    "jackson": "public/events-jackson.json",
}


def _fetch_url_text(url: str) -> str:
    """Fetch a URL and return cleaned text content (max FETCH_MAX_BYTES)."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "yoocal/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        return f"[fetch failed: {e}]"

    soup = BeautifulSoup(r.text[:FETCH_MAX_BYTES * 4], "html.parser")
    # Drop noise
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text[:FETCH_MAX_BYTES]


def _ask_claude(prompt: str) -> dict | None:
    """Call Claude API. Returns parsed JSON response dict or None."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        r = requests.post(
            ANTHROPIC_API,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  [llm] API {r.status_code}: {r.text[:120]}")
            return None
        data = r.json()
        text = data["content"][0]["text"].strip()
        # Strip code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        return json.loads(text)
    except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  [llm] error: {e}")
        return None


# ─── Resolvers per issue type ──────────────────────────────────────

def resolve_title_venue_only(event: dict, source_text: str) -> dict | None:
    """For 'Live Music at Silver Lake' style events, ask Claude to identify
    the actual artist/act."""
    prompt = f"""You are reviewing an event listing where the title only says the venue,
not the actual artist or act performing. From the source page text below,
identify the specific artist/band/performer.

Event title: {event.get("title")!r}
Event date: {event.get("date")}
Event venue: {event.get("venue_name") or event.get("location")!r}

Source page text:
{source_text}

Respond with a single JSON object:
{{
  "confidence": "high" | "medium" | "low",
  "new_title": "...full title with artist...",
  "reasoning": "...one sentence..."
}}

If you cannot identify a specific artist from the source text, set confidence to "low"
and leave new_title empty. Only respond with the JSON object, no other text."""
    return _ask_claude(prompt)


def resolve_multi_day_span(event: dict, source_text: str) -> dict | None:
    """For multi-day events, ask Claude whether they should be one record
    (continuous event) or split (multiple instances)."""
    prompt = f"""You are reviewing a multi-day event listing. From the source page text below,
determine whether this is:
  (a) ONE continuous event spanning multiple days (like a multi-day festival
      where you can attend any/all days), or
  (b) MULTIPLE separate instances of an event (like a play that runs Mon/Wed/Fri)

Event title: {event.get("title")!r}
Date range: {event.get("date")} to {event.get("end_date")}
Description: {(event.get("description") or "")[:300]}

Source page text:
{source_text}

Respond with a single JSON object:
{{
  "confidence": "high" | "medium" | "low",
  "kind": "continuous" | "split",
  "explicit_dates": ["2026-MM-DD", "..."],
  "reasoning": "...one sentence..."
}}

If kind=continuous, leave explicit_dates empty.
If kind=split, list the specific date(s) it actually occurs on from the source.
Only respond with the JSON object, no other text."""
    return _ask_claude(prompt)


def resolve_title_truncated(event: dict, source_text: str) -> dict | None:
    """For truncated titles ('Concert at...'), ask Claude to find the full title."""
    prompt = f"""You are reviewing an event with what appears to be a truncated title.
From the source page text below, find the complete title with all relevant info.

Current (likely truncated) title: {event.get("title")!r}
Event date: {event.get("date")}
Event venue: {event.get("venue_name") or event.get("location")!r}

Source page text:
{source_text}

Respond with a single JSON object:
{{
  "confidence": "high" | "medium" | "low",
  "new_title": "...complete title...",
  "reasoning": "...one sentence..."
}}

If you cannot find a complete title from the source text, set confidence to "low"
and leave new_title empty. Only respond with the JSON object, no other text."""
    return _ask_claude(prompt)


RESOLVERS = {
    "title_venue_only": resolve_title_venue_only,
    "multi_day_span": resolve_multi_day_span,
    "title_truncated": resolve_title_truncated,
}


# ─── Main orchestration ──────────────────────────────────────────

def load_events_per_city() -> dict:
    """Load all city JSON files into a dict[city_key] -> events list."""
    out = {}
    for city, path in CITY_FILES.items():
        try:
            d = json.load(open(path))
            out[city] = d.get("events", d) if isinstance(d, dict) else d
        except FileNotFoundError:
            out[city] = []
    return out


def save_events(city: str, events: list):
    """Save events back to its file, preserving wrapper format."""
    path = CITY_FILES[city]
    try:
        d = json.load(open(path))
    except FileNotFoundError:
        return
    if isinstance(d, dict) and "events" in d:
        d["events"] = events
        json.dump(d, open(path, "w"), indent=2)
    else:
        json.dump(events, open(path, "w"), indent=2)


def apply_resolution(event: dict, issue_type: str, resolution: dict, city_events: list) -> tuple[bool, str]:
    """Mutate event(s) based on Claude's resolution. Returns (applied, note)."""
    confidence = (resolution.get("confidence") or "").lower()
    if confidence != "high":
        return False, f"confidence={confidence}, not applying"

    if issue_type == "title_venue_only" or issue_type == "title_truncated":
        new_title = (resolution.get("new_title") or "").strip()
        if not new_title or len(new_title) < 4:
            return False, "no usable new_title"
        old = event.get("title")
        event["title"] = new_title
        event["_resolved_from"] = old
        return True, f"title: {old!r} → {new_title!r}"

    if issue_type == "multi_day_span":
        kind = resolution.get("kind")
        if kind == "continuous":
            # Keep as-is
            return False, "confirmed continuous, no change"
        if kind == "split":
            dates = resolution.get("explicit_dates") or []
            valid = [d for d in dates if re.match(r"^\d{4}-\d{2}-\d{2}$", str(d))]
            if not valid:
                return False, "split kind but no valid dates"
            # Remove original from list, add per-date copies
            try:
                city_events.remove(event)
            except ValueError:
                return False, "event not in list, skipping"
            for d in valid:
                copy = dict(event)
                copy["date"] = d
                copy["end_date"] = d
                copy["_resolved_from"] = f"split from {event.get('date')}-{event.get('end_date')}"
                city_events.append(copy)
            return True, f"split into {len(valid)} per-day records: {valid}"

    return False, f"unhandled issue_type={issue_type}"


def main():
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY not set — cannot run")
        sys.exit(1)

    try:
        audit = json.load(open("audit_issues.json"))
    except FileNotFoundError:
        print("audit_issues.json not found — run event_quality_audit.py first")
        sys.exit(1)

    # Collect resolvable issues across all cities, sorted by priority
    pending = []
    for r in audit.get("reports", []):
        city = r["city"]
        for i in r.get("issues", []):
            if i.get("type") in RESOLVABLE_TYPES and i.get("severity") == 1:
                pending.append((city, i))

    print(f"LLM Resolver — {datetime.now().isoformat()}")
    print(f"  Found {len(pending)} resolvable severity-1 issues")
    print(f"  Cap: {MAX_RESOLVES_PER_RUN} per run")
    pending = pending[:MAX_RESOLVES_PER_RUN]
    print(f"  Resolving {len(pending)} this run")
    print()

    events_per_city = load_events_per_city()
    log = []
    uncertain = []
    applied_count = 0
    touched_cities = set()

    for city, issue in pending:
        events = events_per_city.get(city) or []
        idx = issue.get("event_index")
        if idx is None or idx >= len(events):
            log.append({"city": city, "type": issue["type"], "skipped": "no event_index"})
            continue

        event = events[idx]
        issue_type = issue["type"]
        title = (event.get("title") or "")[:50]
        link = event.get("link") or ""

        print(f"  [{city}] {issue_type:20s} | {title}")

        if not link or not link.startswith(("http://", "https://")):
            print(f"    skipped: no usable source URL")
            log.append({"city": city, "title": title, "type": issue_type, "skipped": "no link"})
            continue

        # Fetch source page
        source_text = _fetch_url_text(link)
        if source_text.startswith("[fetch failed"):
            print(f"    {source_text}")
            log.append({"city": city, "title": title, "type": issue_type, "skipped": source_text})
            continue

        # Ask Claude
        resolver = RESOLVERS[issue_type]
        resolution = resolver(event, source_text)
        if not resolution:
            log.append({"city": city, "title": title, "type": issue_type, "skipped": "no llm response"})
            continue

        # Apply if confident enough
        applied, note = apply_resolution(event, issue_type, resolution, events)
        print(f"    {'✓' if applied else '·'} {note}")
        print(f"      reasoning: {resolution.get('reasoning', '')[:90]}")

        entry = {
            "city": city,
            "title": title,
            "type": issue_type,
            "link": link,
            "resolution": resolution,
            "applied": applied,
            "note": note,
        }
        log.append(entry)
        if not applied:
            uncertain.append(entry)
        else:
            applied_count += 1
            touched_cities.add(city)

        time.sleep(0.5)  # gentle rate limit

    # Save touched cities
    for city in touched_cities:
        save_events(city, events_per_city[city])
        print(f"  saved {city}")

    # Write logs
    Path("llm_resolve_log.json").write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "attempted": len(pending),
        "applied": applied_count,
        "log": log,
    }, indent=2))
    Path("llm_resolve_uncertain.json").write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "uncertain": uncertain,
    }, indent=2))

    print()
    print(f"Applied {applied_count} of {len(pending)} resolutions")
    print(f"Logs: llm_resolve_log.json + llm_resolve_uncertain.json")


if __name__ == "__main__":
    main()
