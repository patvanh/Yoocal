"""compare_playwright.py — for a set of source URLs, extract via the FAST path
(schema.org / Firecrawl) and via PLAYWRIGHT, and report event counts side by
side. Answers: is Playwright worth running more broadly, or do fast methods
already get the full set?

  python3 compare_playwright.py
"""
import sys
from firecrawl_extractor import extract_events_from_url, extract_via_playwright

# A few Park City sources that returned events via the fast path. Mix of types.
SOURCES = [
    ("https://www.visitparkcity.com/events/", "visitparkcity.com"),
    ("https://www.parkcityopera.org/", "parkcityopera.org"),
    ("https://www.mountaintownmusic.org/", "mountaintownmusic.org"),
    ("https://www.kimballartcenter.org/", "kimballartcenter.org"),
    ("https://www.parkrecord.com/calendar/", "parkrecord.com"),
]
LAT, LNG, CITY = 40.6461, -111.4980, "Park City"

print(f"{'source':28} {'fast':>6} {'playwright':>11}  winner")
print("-" * 60)
for url, name in SOURCES:
    try:
        fast = extract_events_from_url(url, name, default_lat=LAT, default_lng=LNG,
                                       default_city=CITY) or []
    except Exception:
        fast = []
    try:
        pw = extract_via_playwright(url, name, default_lat=LAT, default_lng=LNG,
                                    default_city=CITY) or []
    except Exception:
        pw = []
    nf, np_ = len(fast), len(pw)
    winner = "playwright" if np_ > nf * 1.3 else ("fast" if nf >= np_ else "~tie")
    print(f"{name:28} {nf:>6} {np_:>11}  {winner}")

    # also show unique-to-playwright titles (events fast missed)
    fast_t = {(e.get("title") or "").strip().lower() for e in fast}
    pw_only = [e for e in pw if (e.get("title") or "").strip().lower() not in fast_t]
    if pw_only:
        print(f"    playwright found {len(pw_only)} the fast path MISSED, e.g.:")
        for e in pw_only[:5]:
            print(f"      - {(e.get('title') or '')[:48]}")
