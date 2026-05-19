"""Canonical event categorization for yoocal.

Maps each event to 1-4 categories from a fixed taxonomy + cross-cutting
facets ("free admission", "21+", "outdoor", "indoor", etc).

Used by each city scraper at save time — runs after dedup, before write —
so every event in events.json has consistent categorization regardless of
which source it came from.

Approach:
  1. Map any pre-existing categories on the event to canonical names
     ("Sports/Recreation" -> "Sports", "Art" -> "Arts").
  2. Run a rule-based classifier over title + description + venue + source.
  3. Apply facets ("free", "ticketed", "outdoor", "21+").
  4. Drop the legacy "Community" junk-drawer category if more specific
     categories were inferred — otherwise keep it as a fallback.
"""
from __future__ import annotations

import re


CANONICAL_CATEGORIES = [
    "Music", "Food & Drink", "Arts", "Theater", "Sports",
    "Outdoor", "Family", "Kids", "Wellness", "Education",
    "Festival", "Government", "Community",
]


LEGACY_MAP = {
    "art": "Arts", "arts": "Arts",
    "music": "Music",
    "outdoor": "Outdoor", "outdoors": "Outdoor",
    "community": "Community",
    "family": "Family",
    "kids": "Kids",
    "wellness": "Wellness",
    "education": "Education",
    "festival": "Festival", "festivals": "Festival",
    "theater": "Theater", "theatre": "Theater",
    "free": "Free",
    "sports": "Sports", "sport": "Sports",
    "sports/recreation": "Sports",
    "recreation": "Outdoor",
    "garden": "Outdoor",
    "community-outreach": "Community",
    "community outreach": "Community",
    "camps&clinics": "Kids",
    "camps & clinics": "Kids",
    "food & drink": "Food & Drink",
    "food and drink": "Food & Drink",
    "food and beverage": "Food & Drink",
    "food": "Food & Drink",
    "drink": "Food & Drink",
    "library": "Education",
    "film": "Arts",
    "running": "Sports",
    "on site": "Music",
    "musical adventures": "Music",
    "other community events": "Community",
    "on the road concerts": "Music",
    "festival orchestra series": "Music",
    "teton valley events": "Community",
    "benoliel chamber music series": "Music",
    "open rehearsals": "Music",
    "teton house concert series": "Music",
    "outdoor concerts": "Music",
    "gateway series": "Music",
    "events at the center": "Arts",
    "scholarship competition": "Music",
}


CLASSIFIER_RULES: list[tuple[str, list[str]]] = [
    ("Government", [
        r"\bcity council\b", r"\btown council\b", r"\bcounty commission\b",
        r"\bplanning commission\b", r"\bzoning board\b",
        r"\bpublic hearing\b", r"\btown hall meeting\b",
        r"\bmayor'?s? (office|town hall|address)\b",
        r"\bcity board\b", r"\bschool board\b",
        r"\bmunicipal\b", r"\bcouncil meeting\b", r"\bcommission meeting\b",
    ]),
    ("Music", [
        r"\blive music\b", r"\bconcert\b", r"\bband\b(?!\s*camp)",
        r"\bdj\b", r"\bsongwriter\b", r"\bjam session\b",
        r"\borchestra\b", r"\bchamber music\b", r"\bsymphony\b",
        r"\bopera\b", r"\bjazz\b", r"\bbluegrass\b",
        r"\bacoustic (set|show|night)\b",
        r"\brecital\b",
        r"\btribute (band|to)\b", r"\bopen mic\b",
    ]),
    ("Theater", [
        r"\btheat(re|er)\b", r"\bmusical theatre?\b",
        r"\bbroadway\b", r"\bshakespeare\b",
        r"\bcomedy (show|night|tour)\b", r"\bstand-?up comedy\b",
        r"\bcabaret\b",
    ]),
    ("Arts", [
        r"\b(art|fine art) (show|exhibit|opening|walk|class|workshop|festival)\b",
        r"\bgallery (opening|exhibit|reception)\b",
        r"\bexhibition\b", r"\bexhibit\b",
        r"\bceramics\b", r"\bpottery\b", r"\boil painting\b",
        r"\bdrawing class\b", r"\bsculpture\b", r"\bart fair\b",
        r"\bphotography exhibit\b", r"\bartist talk\b",
        r"\bmuseum\b",
    ]),
    ("Food & Drink", [
        r"\bfarmers? market\b", r"\bfarmers? & artisans?\b",
        r"\btasting\b", r"\bwine\s+(tasting|dinner|night|pairing)\b",
        r"\bbeer\s+(fest|garden|tasting|night)\b",
        r"\bsupper club\b", r"\bbrunch\b",
        r"\bbrewery (tour|tasting)\b",
        r"\bculinary\b", r"\bchef\b", r"\bfood truck\b",
        r"\bcocktail\b", r"\bmixology\b",
        r"\boktoberfest\b", r"\belktoberfest\b",
        r"\bdinner (theater|series|club)\b",
        r"\bfood vendors\b", r"\bfood and drinks?\b",
        r"\bsundayy?\s+market\b",  # "Sunday Market"
        r"\bopen[- ]air market\b", r"\bstreet market\b",
    ]),
    ("Sports", [
        r"\b\d+k (run|race|walk)\b", r"\bmarathon\b",
        r"\btournament\b", r"\bchampionship\b", r"\bregatta\b",
        r"\b(superbike|motoamerica|indycar|imsa|trans am|scca|gt world|vintage racing)\b",
        r"\b(racing|race weekend|race day)\b",
        r"\bsoccer match\b", r"\bbasketball game\b", r"\bhockey\b",
        r"\bfootball game\b", r"\bbaseball\b", r"\btennis match\b",
        r"\brun club\b",
        r"\bpickleball\b", r"\bgolf (tournament|outing|classic)\b",
        r"\bski (race|tournament)\b",
        r"\bcrossfit\b",
    ]),
    ("Outdoor", [
        r"\bhike\b", r"\bhiking\b", r"\btrail (run|race|festival|day)\b",
        r"\bpaddle (board|day|night)\b", r"\bkayak\b", r"\bcanoe\b",
        r"\bbird (walk|tour|show)\b",
        r"\bballoon (fest|festival|show|glow)\b",
        r"\bgarden tour\b", r"\boutdoor (movie|concert|yoga|class|market|festival|event)\b",
        r"\bnature walk\b", r"\bcamping\b", r"\bfly fish\b",
        r"\bmoonlight (hike|walk)\b", r"\bplant tour\b",
        r"\bsnowshoe\b", r"\bski day\b",
        r"\bclimbing wall\b",
        r"\blakefront\b", r"\blakeside\b",
        r"\bopen[- ]air\b", r"\bstreet (festival|fair|party)\b",
        r"\bin the park\b",
        r"\bon the shore\b",
    ]),
    ("Wellness", [
        r"\byoga\b", r"\bmeditation\b", r"\bmindful(ness)?\b",
        r"\bwellness\b", r"\bspa\b", r"\bmassage\b",
        r"\bbreathwork\b", r"\bsound bath\b",
        r"\b(pilates|zumba|trx|barre|hiit|boot ?camp)\b",
        r"\bfitness (class|series)\b", r"\bmuscle up\b",
    ]),
    ("Kids", [
        r"\bkids\b", r"\bchildren'?s\b", r"\byouth\b",
        r"\bstorytime\b", r"\bstory time\b",
        r"\bsummer camp\b", r"\bday camp\b",
        r"\btoddler\b", r"\bpreschool\b",
        r"\bteen (night|club)\b",
        r"\bfamily game\b", r"\bbook baby\b",
        r"\bafter[- ]school\b",
    ]),
    ("Family", [
        r"\bfamily[- ](friendly|fun|day|night)\b",
        r"\ball ages\b",
        r"\bparade\b", r"\bcommunity fair\b",
        r"\bfourth of july\b", r"\b4th of july\b",
        r"\beaster (egg hunt|brunch)\b", r"\bhalloween (parade|party)\b",
        r"\bsanta\b", r"\btree lighting\b",
    ]),
    ("Education", [
        r"\blecture\b", r"\bworkshop\b", r"\bseminar\b",
        r"\btraining\b(?!.*camp)", r"\bcourse\b",
        r"\bdiscussion group\b", r"\bbook club\b",
        r"\bspeaker series\b", r"\bauthor (visit|reading|talk)\b",
        r"\bsymposium\b", r"\bconference\b(?!.*championship)",
    ]),
    ("Festival", [
        r"\bfestival\b", r"\bfest\b(?!\s*\d)",
        r"\bsundance\b", r"\bsong summit\b",
        r"\bsundance film\b", r"\boctoberfest\b",
        r"\bcountry fair\b", r"\bsummer fair\b",
        r"\bjazz on the vine\b", r"\bsavor the\b",
    ]),
]


FACET_RULES: list[tuple[str, list[str]]] = [
    ("Free", [
        r"\bfree (admission|to attend|to all|to the public|event)\b",
        r"\bfree (yoga|concert|class|market|movie|show|workshop|hike)\b",
        r"\bno (charge|admission|cover|cost)\b",
        r"\bfree of charge\b",
        r"\$0\b", r"\bcomplimentary\b",
    ]),
    ("21+", [
        r"\b21\+\b", r"\b21 and (over|up|older)\b",
        r"\badults only\b", r"\bmust be 21\b",
    ]),
    ("Drop-in", [
        r"\bdrop[- ]in\b", r"\bno (rsvp|registration|reservation) (required|needed)\b",
        r"\bjust show up\b",
    ]),
]


def _build_text_blob(event: dict) -> str:
    parts = [
        event.get("title") or "",
        event.get("description") or "",
        event.get("venue_name") or "",
        event.get("location") or "",
        event.get("source") or "",
        event.get("series") or "",
    ]
    return " ".join(parts).lower()


def _classify_with_rules(text: str, rules: list) -> list:
    hits = []
    for label, patterns in rules:
        for p in patterns:
            if re.search(p, text):
                if label not in hits:
                    hits.append(label)
                break
    return hits


def classify_event(event: dict) -> dict:
    """Apply canonical categorization. Mutates and returns the event."""
    text = _build_text_blob(event)

    legacy_cats = event.get("categories") or []
    canonical_from_legacy = []
    facets_from_legacy = []
    for raw in legacy_cats:
        if not raw:
            continue
        key = str(raw).strip().lower()
        mapped = LEGACY_MAP.get(key)
        if mapped == "Free":
            facets_from_legacy.append("Free")
        elif mapped:
            canonical_from_legacy.append(mapped)
        elif raw in CANONICAL_CATEGORIES:
            canonical_from_legacy.append(raw)

    rule_cats = _classify_with_rules(text, CLASSIFIER_RULES)

    combined = []
    for c in canonical_from_legacy + rule_cats:
        if c not in combined:
            combined.append(c)

    has_specific = any(c != "Community" for c in combined)
    if has_specific:
        combined = [c for c in combined if c != "Community"]

    if not combined:
        combined = ["Community"]

    event["categories"] = combined

    facet_hits = _classify_with_rules(text, FACET_RULES)
    facets = list(set(facets_from_legacy + facet_hits))
    if facets:
        event["facets"] = sorted(facets)

    return event


def classify_events(events: list) -> list:
    for e in events:
        classify_event(e)
    return events


if __name__ == "__main__":
    samples = [
        {"title": "Park Silly Sunday Market", "description": "Outdoor market with live music and food."},
        {"title": "City Council Meeting", "description": "Regular city council session."},
        {"title": "Yoga in the Park", "description": "Free outdoor yoga class."},
        {"title": "Suzie & The Detonators at Lake Deck", "description": "Live music on the lakefront. Free admission. 21+ after 9pm."},
        {"title": "Storytime at the Library", "description": "Preschool storytime."},
        {"title": "Sundance Film Festival", "description": "10-day festival of independent film."},
        {"title": "Park City IndyCar Grand Prix", "description": "IndyCar Series race weekend at Road America."},
        {"title": "Yoga", "description": "Drop-in yoga class. No registration needed."},
    ]
    for s in samples:
        result = classify_event(s)
        print(f"  {s['title']:48s} -> {result.get('categories')} facets={result.get('facets', [])}")
