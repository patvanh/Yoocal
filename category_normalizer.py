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

# Domain -> bucket fallback for sources whose events have NO category signal in
# the title (e.g. iceboat.org lists "DN Western Challenge" — opaque title, but
# the source only does iceboat racing; raceentry/fleetfeet only list footraces).
# Used as a last resort before the Community catch-all. Keyed on a substring of
# the event's source field.
_DOMAIN_BUCKET = {
    "iceboat.org": "Sports",
    "iceboat": "Sports",
    "raceentry.com": "Running & Races",
    "fleetfeet": "Running & Races",
    "finishers.com": "Running & Races",
    "runguides.com": "Running & Races",
    "runsignup": "Running & Races",
    "raceroster": "Running & Races",
}

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
_RUN_EXTRA = re.compile(r"\b\d+\s?k\b|\b\d+\s?(mile|mi)\s?(run|race)\b|half\s+marathon|\bmarathon\b|\bultra\b|fun\s+run|trail\s+(run|race|series|challenge)|hill\s+climb|\brambler\b|\brelay\b|\bduathlon\b|\btriathlon\b|\brunners?\b", re.I)


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
    "Sports", "Family & Kids", "Wellness", "Nightlife",
    "Education & Talks", "Community",
]}



# Title-keyword inference for events whose source gave no usable category.
# Ordered by specificity; an event can match multiple buckets. Case-insensitive.
_TITLE_BUCKET_PATTERNS = [
    ("Music", r"\b(live music|concert|band|acoustic|\bdj\b|symphony|orchestra|jazz|blues|open mic|singer|songwriter|bluegrass|karaoke|recital|musical)\b"),
    ("Food & Drink", r"\b(happy hour|\bbbq\b|barbecue|dinner|brunch|breakfast|luncheon|\bwine\b|winery|\bbeer\b|brewing|brewery|tasting|cocktail|supper|sundae|ice cream|farmers? market|food truck|pancake|fish fry|coffee|bake sale)\b|chili\s?cook|cook[\s-]?off|cook[\s-]?out"),
    ("Arts & Theater", r"\b(opera|theat(er|re)|\bart\b|arts|gallery|exhibit|painting|paint|pottery|\bglass\b|\bcraft|sculpture|museum|drawing|photography|quilt|knitting|author|book club|comedy|improv|magic show)\b"),
    ("Outdoors", r"\b(hike|hiking|kayak|paddle|canoe|\bboat|sail|nature|trail|birding|garden|gardening|camp(ing)?|fishing|outdoor|stargaz)\b"),
    ("Sports", r"\b(tournament|\bgolf|regatta|iceboat|pickleball|tennis|softball|baseball|basketball|disc golf|\b4 ?on ?4\b|bowling|cornhole)\b"),
    ("Family & Kids", r"\b(kids?|children|family|story ?time|toddler|youth|baby|bilingual baby|teen|scouts?|playground|petting zoo|easter egg)\b"),
    ("Wellness", r"\b(yoga|meditation|mindfulness|wellness|reiki|pilates|tai chi|breathwork|sound bath)\b"),
    ("Education & Talks", r"\b(lecture|\btalk\b|class|seminar|workshop|library|\bhistory\b|historical|presentation|lesson|tutorial|cpr|first aid|genealogy|book sale)\b"),
    ("Community", r"\b(meeting|fundraiser|blood drive|support group|clean ?up|mixer|\bfair\b|festival|parade|vigil|rummage|bake sale|volunteer|church|worship|mass|service)\b"),
]
import re as _re_cat
_TITLE_BUCKET_RE = [(b, _re_cat.compile(p, _re_cat.I)) for b, p in _TITLE_BUCKET_PATTERNS]


def _infer_buckets_from_title(title):
    t = (title or "")
    out = set()
    for bucket, rx in _TITLE_BUCKET_RE:
        if rx.search(t):
            out.add(bucket)
    return out


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
    title_text = (event.get("title") or "") + " " + (event.get("description") or "")
    buckets |= _infer_buckets_from_title(title_text)
    # Source-domain fallback: when title/category gave nothing, infer from the
    # source domain (iceboat.org -> Sports, race sites -> Running & Races).
    if not buckets:
        src = (event.get("source") or "").lower() + " " + (event.get("link") or "").lower()
        for frag, bucket in _DOMAIN_BUCKET.items():
            if frag in src:
                buckets.add(bucket)
                break
    if not buckets:
        buckets.add("Community")  # default catch-all
    return sorted(buckets)


# All user-facing buckets, in display order
ALL_BUCKETS = ["Music", "Arts & Theater", "Food & Drink", "Outdoors",
               "Running & Races", "Sports", "Family & Kids",
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
