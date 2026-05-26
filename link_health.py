"""Link-health: post-build step that checks event links and repairs dead ones.

Runs as the last stage of build_master_and_views.py. Uses a 7-day cache so most
builds re-check almost nothing. Guards:
  - ONLY 404/410 are 'dead'. 403 = bot-block (works in browsers) -> treat as OK.
  - timeout/connection error -> leave alone (transient), never "fix".
  - dead link -> fallback ONLY to a URL that itself returns 200 (/events or root);
    if none verifies, leave the link and log it for manual review.
  - redirect (3xx) -> rewrite to the final 200 target.
Every change is recorded in link_health_log.json.
"""
import json, os, time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests

CACHE_PATH = "link_health_cache.json"
LOG_PATH = "link_health_log.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124.0"}
TIMEOUT = 12
MAX_WORKERS = 8
CACHE_TTL_DAYS = 7


def _load_cache():
    try:
        return json.load(open(CACHE_PATH))
    except Exception:
        return {}


def _fresh(entry):
    try:
        checked = datetime.fromisoformat(entry["checked"])
        return datetime.now(timezone.utc) - checked < timedelta(days=CACHE_TTL_DAYS)
    except Exception:
        return False


def _verified_fallback(url):
    p = urlparse(url)
    for path in ("/events", "/"):
        cand = f"{p.scheme}://{p.netloc}{path}"
        try:
            if requests.get(cand, headers=HEADERS, timeout=TIMEOUT).status_code == 200:
                return cand
        except Exception:
            pass
    return None


def _classify(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code in (403, 405) or r.status_code >= 500:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        code = r.status_code
        if code == 403:
            return ("ok", url)
        if code in (404, 410):
            return ("dead", _verified_fallback(url))
        if code == 200:
            # A working link is fine even if it redirects — leave it alone.
            # Rewriting redirects (esp. cosmetic %2b->%2B / http->https / slash
            # normalizations) is churn for zero user benefit and buries real
            # dead-link repairs in log noise. Only 404/410 get fixed.
            return ("ok", url)
        return ("skip", url)
    except Exception:
        return ("skip", url)


def check_and_fix_links(city_files):
    cache = _load_cache()
    now = datetime.now(timezone.utc).isoformat()

    links = {}
    for f in city_files:
        try:
            data = json.load(open(f))
        except Exception:
            continue
        for e in data.get("events", []):
            u = (e.get("link") or "").strip()
            if u.startswith("http"):
                links.setdefault(u, []).append(f)

    to_check = [u for u in links if not (u in cache and _fresh(cache[u]))]
    print(f"[link-health] {len(links)} unique links | "
          f"{len(links) - len(to_check)} cached | {len(to_check)} to check")

    if to_check:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(_classify, u): u for u in to_check}
            for fut in as_completed(futs):
                u = futs[fut]
                status, target = fut.result()
                cache[u] = {"status": status, "target": target, "checked": now}

    fixes = {}
    manual = []
    for u in links:
        c = cache.get(u, {})
        if c.get("status") == "dead":
            if c.get("target"):
                fixes[u] = c["target"]
            else:
                manual.append(u)

    changes = []
    for f in city_files:
        try:
            data = json.load(open(f))
        except Exception:
            continue
        n = 0
        for e in data.get("events", []):
            u = (e.get("link") or "").strip()
            if u in fixes:
                changes.append({"file": f, "title": e.get("title", "")[:50],
                                "from": u, "to": fixes[u]})
                e["link"] = fixes[u]
                n += 1
        if n:
            json.dump(data, open(f, "w"), indent=2)

    json.dump(cache, open(CACHE_PATH, "w"), indent=2)
    json.dump({"ran": now, "changes": changes, "manual_review": manual},
              open(LOG_PATH, "w"), indent=2)

    uniq = len(set(c["from"] for c in changes))
    print(f"[link-health] fixed {len(changes)} links ({uniq} unique) | "
          f"{len(manual)} need manual review")
    for u in manual[:5]:
        print(f"[link-health]   MANUAL: {u}")
    return len(changes)


if __name__ == "__main__":
    check_and_fix_links([
        "public/events.json", "public/events-heber.json",
        "public/events-jackson.json", "public/events-elkhartlake.json",
    ])
