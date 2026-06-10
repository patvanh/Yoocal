"""concerts_commons_enricher.py — give the Teton Village "Concerts on the Commons"
records their real band name as the title.

Problem: the Dishing Jackson Hole source lists 7 separate Sunday concerts all under
the identical generic title "Sunday Fundays, Concert on the Commons Series", so the
site shows 7 indistinguishable cards (and the audit flags them as cross-source
dups). The actual band names live only on jacksonhole.com/concerts-on-the-commons.

Fix: fetch that one schedule page, build a {date -> band name} map from the artist
section headers, and rewrite each matching record's title to the band name. Self-
updating (re-fetched each run); no hardcoded lineup. Safe: only touches records
whose title contains "concert on the commons" (or the Dishing series), and only
when a band is found for that exact date.
"""
from __future__ import annotations
import re
from datetime import datetime

SCHEDULE_URL = "https://www.jacksonhole.com/concerts-on-the-commons"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Each artist block on the page is an <h2>Band Name</h2> followed (later) by an
# <h3><strong>Month D, YYYY (T PM)</strong></h3>. We pair each date with the
# nearest preceding <h2>, skipping non-artist headers. The <h2> text carries the
# correctly-spelled name (the image alt= text has typos like "Object Hevay").
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)
_DATE_RE = re.compile(r"<h3[^>]*><strong>([A-Z][a-z]+ \d{1,2}, \d{4})")
_SKIP_H2 = {
    "schedule", "explore the artists", "subscribe", "stay connected",
    "get the app", "our partners",
}


def _fetch(url: str, timeout: int = 20) -> str:
    try:
        import requests
    except ImportError:
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
        if r.status_code != 200:
            print(f"  [coc-enrich] schedule fetch HTTP {r.status_code}")
            return ""
        return r.text
    except Exception as ex:
        print(f"  [coc-enrich] schedule fetch failed: {ex}")
        return ""


def build_date_band_map(html: str) -> dict:
    """Return {YYYY-MM-DD: 'Band Name'} by pairing each date header with the
    nearest preceding <h2> artist name in the raw page HTML."""
    if not html:
        return {}
    h2s = []
    for m in _H2_RE.finditer(html):
        name = re.sub(r"<[^>]+>", "", m.group(1))
        name = (name.replace("&amp;", "&").replace("&#39;", "'")
                    .replace("&rsquo;", "'").strip())
        if name and name.lower() not in _SKIP_H2:
            h2s.append((m.start(), name))
    out = {}
    for dm in _DATE_RE.finditer(html):
        prior = [h for h in h2s if h[0] < dm.start()]
        if not prior:
            continue
        band = prior[-1][1]
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                d = datetime.strptime(dm.group(1).strip(), fmt).date().isoformat()
                out[d] = band
                break
            except ValueError:
                continue
    return out


def enrich_concerts_on_the_commons(events: list) -> list:
    """Rewrite generic 'Concerts on the Commons' titles to the real band name,
    matched by date. Mutates and returns the list."""
    targets = [
        e for e in events
        if "concert on the commons" in (e.get("title") or "").lower()
        or "concerts on the commons" in (e.get("title") or "").lower()
    ]
    if not targets:
        return events

    html = _fetch(SCHEDULE_URL)
    if not html:
        print("  [coc-enrich] no schedule fetched; titles left unchanged")
        return events
    date_band = build_date_band_map(html)
    if not date_band:
        print("  [coc-enrich] could not parse any date->band; titles unchanged")
        return events

    renamed = 0
    for e in targets:
        d = (e.get("date") or "")[:10]
        band = date_band.get(d)
        if band:
            e["title"] = f"{band} — Concerts on the Commons"
            # category: these are concerts
            cats = e.get("categories") or []
            if "Music" not in cats:
                e["categories"] = ["Music"] + [c for c in cats if c != "Music"]
            renamed += 1
    if renamed:
        print(f"  [coc-enrich] renamed {renamed} Concerts on the Commons records to band names")
    return events


if __name__ == "__main__":
    html = _fetch(SCHEDULE_URL)
    m = build_date_band_map(html)
    print(f"parsed {len(m)} date->band entries:")
    for d in sorted(m):
        print(" ", d, "->", m[d])
