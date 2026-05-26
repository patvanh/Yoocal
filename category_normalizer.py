"""Normalize messy source categories (53 distinct) into ~12 clean, user-facing
filter buckets, plus title-based enrichment for high-intent types the source
tags miss (esp. running — 77 real runs but only 12 source-tagged 'Running').

Produces a `filter_categories` LIST per event (events can span buckets, e.g. a
family run club is both 'Running & Races' and 'Family & Kids').

Footraces are kept PRECISE: only running signals (5k/10k/marathon/run club/
trail run/fun run), not bare 'race' (avoids soapbox/bike/derby false matches).
"""
import re

# Clean bucket <- set of source category strings (lowercased match)
BUCKET_FROM_SOURCE = {
    "Music": {"music", "concert", "on the road concerts", "outdoor concerts",
              "festival orchestra series", "open rehearsals", "gateway series",
              "benoliel chamber music series", "teton house concert series"},
    "Arts & Theater": {"arts", "art", "theater", "opera", "film",
                        "metropolitan opera in hd", "scholarship competition"},
    "Food & Drink": {"food & drink", "food and beverage", "food"},
    "Family & Kids": {"kids", "family", "musical adventures", "camps&clinics"},
    "Outdoors": {"outdoor", "hiking", "mountain biking", "cycling", "garden",
                 "gardening", "environment"},
    "Running & Races": {"running"},
    "Sports": {"sports", "sports/recreation", "sports and recreation", "soccer"},
    "Wellness": {"wellness", "mindfulness", "yoga"},
    "Festivals": {"festival", "market/festival"},
    "Education & Talks": {"education", "library", "historical"},
    "Nightlife": {"nightlife"},
    "Community": {"community", "other community events", "government", "volunteer",
                  "community-outreach", "on site", "free", "teton valley events",
                  "teton valley events", "events at the center"},
}

# reverse lookup: source-cat -> bucket
_SOURCE_TO_BUCKET = {}
for bucket, sources in BUCKET_FROM_SOURCE.items():
    for s in sources:
        _SOURCE_TO_BUCKET[s] = bucket

# Title-enrichment: footrace signals (precise). Bare "race" only counts with a
# running qualifier nearby.
_RUN_PATTERNS = [
    r"\b\d+\s?k\b",            # 5k, 10k, 5 k
    r"\bmarathon\b",
    r"\bhalf marathon\b",
    r"\brun club\b",
    r"\btrail run\b",
    r"\bfun run\b",
    r"\bturkey trot\b",
    r"\b(road|trail|mountain)\s?race\b",  # qualified race
]
_RUN_RE = re.compile("|".join(_RUN_PATTERNS), re.I)
# distance + "race" combo, or "run/runners" as a standalone activity word
_RUN_EXTRA = re.compile(r"\b(\d+\s?(mile|mi)\s?(run|race))\b|\brunners?\b|\b5k\b|\b10k\b", re.I)


def _title_is_footrace(title):
    t = (title or "").lower()
    if _RUN_RE.search(t) or _RUN_EXTRA.search(t):
        return True
    # " run " as activity (Friday Run Club already caught; this catches "Spring Run")
    if re.search(r"\brun\b", t) and not re.search(r"\b(run time|dry run|home run|run of)\b", t):
        # require another athletic hint to avoid "run of the show" etc.
        if re.search(r"\b(5k|10k|race|trail|miles?|club|jog|charity)\b", t):
            return True
    return False


_VALID_BUCKETS_LOWER = {b.lower(): b for b in [
    "Music", "Arts & Theater", "Food & Drink", "Outdoors", "Running & Races",
    "Sports", "Family & Kids", "Festivals", "Wellness", "Nightlife",
    "Education & Talks", "Community",
]}


def filter_categories_for(event):
    """Return sorted list of clean buckets for an event."""
    buckets = set()
    for c in (event.get("categories") or []):
        cl = (c or "").strip().lower()
        # Honor categories already given as a clean bucket name (e.g. API
        # sources like RunSignup that tag events "Running & Races" directly).
        if cl in _VALID_BUCKETS_LOWER:
            buckets.add(_VALID_BUCKETS_LOWER[cl])
            continue
        b = _SOURCE_TO_BUCKET.get(cl)
        if b:
            buckets.add(b)
    # title enrichment: footraces
    if _title_is_footrace(event.get("title")):
        buckets.add("Running & Races")
    if not buckets:
        buckets.add("Community")  # default catch-all
    return sorted(buckets)


# All user-facing buckets, in display order
ALL_BUCKETS = ["Music", "Arts & Theater", "Food & Drink", "Outdoors",
               "Running & Races", "Sports", "Family & Kids", "Festivals",
               "Wellness", "Nightlife", "Education & Talks", "Community"]


if __name__ == "__main__":
    import json
    from collections import Counter
    bucket_counts = Counter()
    run_enriched = []
    for f in ['public/events.json','public/events-heber.json',
              'public/events-jackson.json','public/events-elkhartlake.json']:
        for e in json.load(open(f))["events"]:
            fc = filter_categories_for(e)
            for b in fc:
                bucket_counts[b] += 1
            # track what got pulled into Running by TITLE (not source-tagged)
            if "Running & Races" in fc and "running" not in [c.lower() for c in (e.get("categories") or [])]:
                run_enriched.append((e.get("title","")[:50], e.get("categories")))
    print("=== bucket coverage (events per bucket; multi-bucket so sums > total) ===")
    for b in ALL_BUCKETS:
        print(f"  {bucket_counts[b]:5d}  {b}")
    print()
    print(f"=== Running & Races: {len(run_enriched)} events enriched BY TITLE (not source-tagged) ===")
    for t, c in run_enriched:
        print(f"  {str(c):30} | {t}")
