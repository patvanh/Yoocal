"""Scraper for 'busites' CMS music/event pages (e.g. Million Dollar Cowboy Bar).

These pages embed all events as a JSON array in the HTML:
  {"title":"X","image":"...","path":"/events/...","start":"YYYY-MM-DD HH:MM:SS","html":"..."}
The individual /events/ detail pages have stale dates + polluted titles, so we
read the embedded array on the listing page instead — it has correct dates and
clean titles.
"""
import re
import requests
from datetime import datetime

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"}
_REC = re.compile(
    r'\{"title":"((?:[^"\\]|\\.)*)","image":"([^"]*)","path":"([^"]*)",'
    r'"start":"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):\d{2}"'
    r',"html":"((?:[^"\\]|\\.)*)"'
)


def _clean_title(raw):
    # JSON string -> python: handle \uXXXX and escaped chars
    try:
        return re.sub(r"\s+", " ", bytes(raw, "utf-8").decode("unicode_escape")).strip()
    except Exception:
        return re.sub(r"\s+", " ", raw).strip()


def _to_12h(hh, mm):
    hh = int(hh)
    ampm = "AM" if hh < 12 else "PM"
    h12 = hh if 1 <= hh <= 12 else (hh - 12 if hh > 12 else 12)
    return f"{h12}:{mm} {ampm}"


def scrape_busites_music(
    url,
    source_name,
    default_lat=None,
    default_lng=None,
    default_city=None,
    default_categories=None,
    venue_name=None,
    venue_addr=None,
    timeout=20,
):
    venue_name_addr = ", ".join([x for x in [venue_name, venue_addr] if x])
    """Return future yoocal events from a busites embedded-JSON listing page."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        from firecrawl_extractor import fetch_html as _fh
        text = _fh(url, headers=_HEADERS) or ""
    except Exception as ex:
        print(f"  [{source_name}] fetch failed: {ex}")
        return []

    out = []
    seen = set()
    past = 0
    base = url.split("/music")[0]
    for raw_title, image, path, d, hh, mm, raw_html in _REC.findall(text):
        if d < today:
            past += 1
            continue
        title = _clean_title(raw_title)
        if not title or len(title) < 2:
            continue
        key = (title.lower(), d)
        if key in seen:
            continue
        seen.add(key)
        desc = _clean_title(raw_html)
        desc = re.sub(r"&nbsp;", " ", desc).strip()
        path = path.replace("\\/", "/")  # JSON-escaped slashes -> real
        link = base + path if path.startswith("/") else path
        out.append({
            "title": title,
            "date": d,
            "end_date": None,
            "start_time": _to_12h(hh, mm),
            "end_time": None,
            "source": source_name,
            "source_url": link,
            "link": link,
            "lat": default_lat,
            "lng": default_lng,
            "location": venue_name_addr or (default_city or ""),
            "venue_name": venue_name or source_name,
            "address": venue_addr or "",
            "image_url": image.replace("\\/", "/") if image else "",
            "description": desc[:2000],
            "categories": list(default_categories or ["Event"]),
        })
    print(f"[busites] {source_name}: {len(out)} future, {past} past")
    return out


if __name__ == "__main__":
    evs = scrape_busites_music(
        "https://www.milliondollarcowboybar.com/music",
        source_name="Million Dollar Cowboy Bar",
        default_lat=43.4799, default_lng=-110.7624,
        default_city="Jackson, WY", default_categories=["Music", "Nightlife"],
    )
    print(f"{len(evs)} events")
    for e in evs[:5]:
        print("  ", e["date"], e["start_time"], "|", e["title"])
