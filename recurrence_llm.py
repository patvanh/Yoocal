"""LLM-based recurrence extractor.

Regex recurrence parsing (recurrence_parser.py) only catches a few fixed
phrasings (e.g. "Recurring weekly on Saturday"). Real event descriptions state
schedules in open-ended natural language ("held every Saturday from June through
October", "Saturdays all summer", "weekly on Sat 10-1"). This reads the meaning
via a small Claude call and returns STRUCTURED recurrence, or null for one-time
events. Cached by content hash so the API is called once per unique description.

Mirrors the client/cache/fallback pattern of townlift_address_enricher.py.
"""
from __future__ import annotations
import os, re, json, hashlib
from datetime import datetime

_CACHE_PATH = ".cache/recurrence_enrichment.json"
_MODEL = "claude-haiku-4-5-20251001"  # cheap/fast; structured extraction
_VALID_DAYS = {"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"}


def _load_cache():
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(".cache", exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=0)
    except Exception as ex:
        print(f"  [recurrence-llm] cache write failed: {ex}")


def _key(title, description):
    h = hashlib.sha1((title + "||" + description).encode("utf-8")).hexdigest()
    return h[:16]


def extract_recurrence_llm(title, description, event_date=None):
    """Return {"recurrence":"weekly","recurrence_days":"Saturday[,Sunday]",
    "end_date":"YYYY-MM-DD"|null} for a recurring event, or None for one-time.

    Returns None on any error / missing key (caller falls back to regex).
    Cached by (title, description) hash.
    """
    if not description:
        return None
    cache = _load_cache()
    k = _key(title or "", description)
    if k in cache:
        return cache[k] or None  # cached null stored as {} -> None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None  # no key: silently fall back to regex, don't cache

    try:
        import anthropic
    except ImportError:
        return None

    year_hint = ""
    if event_date:
        year_hint = f"The event's known start date is {event_date}. Use that year for any end_date you infer.\n"

    prompt = (
        "You determine whether an event recurs on a weekly schedule, based on its "
        "description. Read for MEANING, not keywords.\n\n"
        "Return ONLY a JSON object:\n"
        '{"recurring": bool, "days": [weekday names], "end_date": "YYYY-MM-DD" or null}\n\n'
        "Rules:\n"
        "- recurring=true ONLY if the text states a repeating weekly schedule "
        '(e.g. "every Saturday", "Saturdays through October", "weekly on Sat & Sun").\n'
        "- A single dated event, or vague language with no clear weekly cadence, is "
        "recurring=false.\n"
        "- days: full weekday names it recurs on, e.g. [\"Saturday\"]. Empty if not recurring.\n"
        "- end_date: if the text gives an end (e.g. \"through October\"), return the last "
        "day of that period as YYYY-MM-DD; else null.\n"
        "- Do NOT invent a schedule that isn't clearly stated.\n\n"
        f"{year_hint}"
        f"Event title: {title}\n\n"
        f"Description:\n{description[:2000]}\n\n"
        "JSON only, no commentary:"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_MODEL, max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
    except Exception as ex:
        print(f"  [recurrence-llm] failed: {ex}")
        return None

    result = None
    if isinstance(data, dict) and data.get("recurring"):
        days = [d.capitalize() for d in (data.get("days") or [])
                if isinstance(d, str) and d.capitalize() in _VALID_DAYS]
        if days:
            result = {"recurrence": "weekly", "recurrence_days": ",".join(days)}
            ed = data.get("end_date")
            if isinstance(ed, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", ed):
                result["end_date"] = ed

    cache[k] = result or {}
    _save_cache(cache)
    return result


if __name__ == "__main__":
    tests = [
        ("Midway Farmers Market", "The market is held every Saturday from 10:00 am to 1:00 pm at the Midway Town Square from June through October."),
        ("New Year's Eve Gala", "Ring in 2027 with us on December 31 at 8pm. One night only."),
        ("Live Jazz Nights", "Join us every Friday and Saturday evening for live jazz, 7-10pm, all year."),
        ("Annual 5K Run", "The 12th annual Heber 5K takes place Saturday, July 4 at 8am."),
    ]
    for t, d in tests:
        print(f"\n{t!r}\n  -> {extract_recurrence_llm(t, d, '2026-06-27')}")
