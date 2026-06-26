"""Snow King Concerts enricher.

The Cloudveil's Tribe API publishes the King Concerts summer series as a single
recurring event called "King Concerts 2026" with band names hidden in prose. The
canonical lineup lives on snowkingmountain.com/king-concerts in a table:
    BAND_NAME | DATE | PRICE | PRICE | PRICE

This module:
  1. Fetches the snowkingmountain.com lineup page.
  2. Parses a {date_iso: band_name} map from the table.
  3. Exposes enrich_king_concerts(events) which rewrites the title of any
     "King Concerts 2026" record whose date matches the lineup map.

Records with no lineup match retain their original title.
"""
from __future__ import annotations

import re
from typing import Dict, List

import requests


LINEUP_URL = "https://snowkingmountain.com/king-concerts/"
_MONTHS = {
    "May": 5, "June": 6, "July": 7,
    "August": 8, "Aug": 8, "Sept": 9, "September": 9,
}
_DATE_PAT = re.compile(
    r"((?:May|June|July|August|Aug|Sept|September)\s+\d{1,2}"
    r"(?:\s*\+\s*(?:May|June|July|August|Aug|Sept|September)?\s*\d{1,2})?)"
)


def fetch_lineup(year: int = 2026, timeout: int = 20) -> Dict[str, str]:
    """Return {YYYY-MM-DD: band_name} from snowkingmountain.com lineup page."""
    try:
        from firecrawl_extractor import fetch_html as _fh
        html = _fh(LINEUP_URL)
        if not html:
            print(f"  [Snow King lineup] fetch failed (direct + Firecrawl)")
            return {}
    except Exception as e:
        print(f"  [Snow King lineup] fetch failed: {e}")
        return {}

    text = re.sub(r"<[^>]+>", " | ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&apos;|&#8217;|&#x2019;", "'", text)
    text = re.sub(r"\s+", " ", text).strip()

    matches = list(_DATE_PAT.finditer(text))
    results: Dict[str, str] = {}

    for i, m in enumerate(matches):
        date_str = m.group(1).strip()
        prev_end = matches[i - 1].end() if i > 0 else 0
        preceding = text[prev_end:m.start()]
        parts = [p.strip() for p in preceding.split("|") if p.strip()]
        band_parts: List[str] = []
        for p in parts:
            if re.match(r"^\$\d", p):
                continue
            if p.upper() in ("SOLD OUT", "FREE"):
                continue
            if len(p) < 2:
                continue
            band_parts.append(p)
        if not band_parts:
            continue
        band = band_parts[-1]

        # Skip prose false-positives — band names are short, prose is long.
        # 120 chars is a generous cap; real band lines top out around 80.
        if len(band) > 120:
            continue
        # Skip promotional/marketing copy that contains date-looking words
        # but isn't a band (e.g. "Widespread on sale Thursday")
        low = band.lower()
        if any(k in low for k in ("on sale", "tickets", "tba", "announced", "presale", "pre-sale")):
            continue
        # Strip trailing "+" with no opener
        band = re.sub(r"\s*\+\s*$", "", band).strip()
        if not band:
            continue

        # Parse one or more dates from "June 8" or "July 31 + Aug 1"
        last_month = None
        for piece in re.split(r"\s*\+\s*", date_str):
            mm = re.match(
                r"(May|June|July|August|Aug|Sept|September)?\s*(\d{1,2})",
                piece.strip(),
            )
            if not mm:
                continue
            mo_name = mm.group(1)
            day = int(mm.group(2))
            mo = _MONTHS.get(mo_name) if mo_name else last_month
            if mo:
                last_month = mo
                results[f"{year}-{mo:02d}-{day:02d}"] = band

    return results


def enrich_king_concerts(events: list) -> int:
    """Mutate events in place: rewrite title of King Concerts records using lineup map.

    Returns number of records rewritten.
    """
    lineup = fetch_lineup()
    if not lineup:
        print("  [Snow King] lineup empty; titles unchanged")
        return 0

    rewritten = 0
    for ev in events:
        if ev.get("title") != "King Concerts 2026":
            continue
        date_key = (ev.get("date") or "")[:10]
        band = lineup.get(date_key)
        if not band:
            continue
        ev["title"] = f"{band} at Snow King"
        rewritten += 1

    print(f"  [Snow King] rewrote {rewritten} of {sum(1 for e in events if 'Snow King' in (e.get('title') or '') or 'King Concerts' in (e.get('title') or ''))} King Concerts titles ({len(lineup)} dates in lineup)")
    return rewritten


if __name__ == "__main__":
    lineup = fetch_lineup()
    print(f"Parsed {len(lineup)} dates from lineup:")
    for d in sorted(lineup):
        print(f"  {d}: {lineup[d]}")
