"""playwright_render.py — final-rung renderer for pages whose events are injected
by JavaScript that even Firecrawl's enhanced proxy can't surface (e.g. embedded
calendar widgets like nowplayingutah on parkrecord.com/calendar/).

Runs a real headless Chromium, executes the page's JS, waits for the DOM to
settle (and optionally for event-like content to appear), then returns the
rendered HTML/text for the normal LLM extractor to parse.

This is the most expensive/slow strategy, so it's only invoked as the LAST
escalation rung after free methods, Firecrawl standard, and Firecrawl enhanced
have all returned nothing.

Requires: playwright (already in requirements) + a one-time `playwright install
chromium`. If unavailable, render_with_playwright returns None and the caller
simply skips this rung — never crashes the run.
"""
from __future__ import annotations

_PLAYWRIGHT_OK = None  # lazy availability check, cached


def _available():
    global _PLAYWRIGHT_OK
    if _PLAYWRIGHT_OK is None:
        try:
            from playwright.sync_api import sync_playwright  # noqa
            _PLAYWRIGHT_OK = True
        except Exception:
            _PLAYWRIGHT_OK = False
    return _PLAYWRIGHT_OK


def capture_event_api(url, wait_ms=15000, timeout_ms=70000, verbose=True):
    """Render a calendar page and capture any background API call that returns
    event data. Many JS calendars fetch events from an internal JSON endpoint —
    far more complete than the sitemap (VPC: 684 via API vs 148 via sitemap).

    Detects the event API two ways (general, no per-site URLs):
      1. URL path looks like an events endpoint (.../events.../find, /rest_v2/,
         'events_by_date', '/api/events', 'tribe/events', etc.)
      2. Response JSON has many records with date+title-ish fields.
    Returns the parsed JSON (raw) of the richest event response, or [].
    """
    if not _available():
        return []
    from playwright.sync_api import sync_playwright
    import re as _re2

    # URL patterns that strongly indicate an events API (general across CMSs)
    api_url_re = _re2.compile(
        r"(events?_by_date|events?_events|/rest_v2/.*event|/api/.*event|"
        r"tribe/events|/events/.*\b(find|list|search|feed|json)\b|"
        r"plugins_events|/wp-json/.*event|eventsservice|calendar.*json)", _re2.I)

    captured = []  # (url, raw_json, n_records)

    def count_records(obj):
        """Find the largest list of event-like dicts anywhere in the JSON."""
        best = []
        def walk(o, depth=0):
            nonlocal best
            if depth > 6:
                return
            if isinstance(o, list):
                eventy = [r for r in o if isinstance(r, dict) and (
                    any(k.lower() in ("title","name","eventname","headline")
                        for k in r) and
                    any(k.lower() in ("date","startdate","start_date","start",
                                      "begin","eventdate","datetime","when","dates")
                        for k in r))]
                if len(eventy) > len(best):
                    best = eventy
                for r in o[:50]:
                    walk(r, depth+1)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v, depth+1)
        walk(obj)
        return best

    def on_response(resp):
        try:
            if resp.request.resource_type not in ("xhr", "fetch"):
                return
            u = resp.url
            ct = (resp.headers or {}).get("content-type", "").lower()
            url_hit = bool(api_url_re.search(u))
            if not url_hit and "json" not in ct:
                return
            body = resp.json()
            recs = count_records(body)
            # accept if URL looks like an events API (even a few records) OR the
            # response clearly holds many event records
            if (url_hit and recs) or len(recs) >= 3:
                captured.append((u, recs, len(recs)))
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36"),
                timezone_id="America/Denver",
            ).new_page()
            page.set_default_timeout(timeout_ms)
            page.on("response", on_response)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            page.wait_for_timeout(wait_ms)
            try:
                for _ in range(4):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(1500)
            except Exception:
                pass
            browser.close()
    except Exception as ex:
        if verbose:
            print(f"      [api-capture] error: {str(ex)[:80]}")
        return []

    if not captured:
        return [], None
    captured.sort(key=lambda t: t[2], reverse=True)
    best_url, best, n = captured[0]
    if verbose:
        print(f"      [api-capture] event API ({n} records): {best_url[:70]}")
    return best, best_url


def replay_event_api(api_url, verbose=True):
    """Re-fetch a captured event-API URL with limits bumped, to get the FULL
    set of event definitions (the page often loads only a small window). General:
    finds limit/per_page/count params (in query string OR in a json= blob) and
    raises them, widens any date range, then fetches the JSON directly.

    Returns the largest event-record list found, or []."""
    import urllib.parse, urllib.request, urllib.error, json as _json, re as _re3
    from datetime import date, timedelta

    def _records(obj):
        best = []
        def walk(o, d=0):
            nonlocal best
            if d > 6: return
            if isinstance(o, list):
                ev = [r for r in o if isinstance(r, dict) and
                      any(k.lower() in ("title","name","eventname","headline") for k in r) and
                      any(k.lower() in ("date","startdate","start_date","start","begin",
                          "eventdate","datetime","when","dates") for k in r)]
                if len(ev) > len(best): best = ev
                for r in o[:200]: walk(r, d+1)
            elif isinstance(o, dict):
                for v in o.values(): walk(v, d+1)
        walk(obj)
        return best

    try:
        parsed = urllib.parse.urlparse(api_url)
        params = urllib.parse.parse_qs(parsed.query)
        today = date.today()
        wide_end = (today + timedelta(days=365)).isoformat()

        # Case A: a json= blob (VPC / simpleview style) — bump options.limit AND
        # widen any date range so we get the full forward calendar, not just the
        # default ~1-week window the calendar page requested.
        if "json" in params:
            try:
                blob = _json.loads(params["json"][0])
                opts = blob.setdefault("options", {})
                opts["limit"] = 1000
                opts["skip"] = 0
                # widen nested date ranges wherever they appear in the filter.
                # VPC shape: filter.date_range.{start,end}.$date (ISO strings).
                wide_end_iso = (today + timedelta(days=400)).strftime(
                    "%Y-%m-%dT06:00:00.000Z")
                def _widen_dates(o):
                    if isinstance(o, dict):
                        for k, v in o.items():
                            kl = str(k).lower()
                            if kl in ("end", "enddate", "end_date", "to", "$lte", "before") \
                               and isinstance(v, dict) and "$date" in v:
                                v["$date"] = wide_end_iso
                            elif kl in ("end", "enddate", "end_date") and isinstance(v, str):
                                o[k] = wide_end_iso
                            else:
                                _widen_dates(v)
                    elif isinstance(o, list):
                        for it in o:
                            _widen_dates(it)
                _widen_dates(blob.get("filter", {}))
                params["json"] = [_json.dumps(blob)]
            except Exception:
                pass
        # Case B: plain limit-ish query params
        for k in list(params.keys()):
            kl = k.lower()
            if kl in ("limit", "per_page", "perpage", "count", "pagesize", "page_size"):
                params[k] = ["1000"]
            if kl in ("end", "enddate", "end_date", "to", "before"):
                params[k] = [wide_end]

        new_q = urllib.parse.urlencode(params, doseq=True)
        full = urllib.parse.urlunparse(parsed._replace(query=new_q))
        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

        def _fetch(method):
            if method == "GET":
                r = urllib.request.Request(full, headers={
                    "User-Agent": ua,
                    "Accept": "application/json, text/plain, */*"})
                return _json.load(urllib.request.urlopen(r, timeout=30))
            # POST: some APIs (cityspark) only accept POST; send query as JSON body
            body = _json.dumps({k: (v[0] if len(v) == 1 else v)
                                for k, v in params.items()}).encode()
            r = urllib.request.Request(full.split("?")[0], data=body, headers={
                "User-Agent": ua, "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*"})
            return _json.load(urllib.request.urlopen(r, timeout=30))

        try:
            data = _fetch("GET")
        except urllib.error.HTTPError as he:
            if he.code in (405, 400, 411):   # method/shape not allowed -> try POST
                data = _fetch("POST")
            else:
                raise
        recs = _records(data)
        if verbose:
            print(f"      [api-replay] {len(recs)} records (limit bumped)")
        return recs
    except Exception as ex:
        if verbose:
            print(f"      [api-replay] error: {str(ex)[:80]}")
        return []


def render_with_playwright(url, wait_ms=8000, wait_selector=None,
                           scroll=True, timeout_ms=60000, verbose=True):
    """Load url in headless Chromium, let JS run, return rendered HTML or None.

    wait_selector: optional CSS selector to wait for (more reliable than a fixed
    delay when you know the widget's container). Falls back to wait_ms otherwise.
    scroll: scroll to bottom to trigger lazy-loaded / infinite-scroll content.

    Uses 'domcontentloaded' (not 'networkidle') because ad/tracker-heavy event
    sites often never reach network idle and would hang the full timeout. We then
    explicitly wait for JS/widgets via wait_ms or wait_selector.
    """
    if not _available():
        if verbose:
            print("      [playwright] not installed — skipping (run: playwright install chromium)")
        return None
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36")
            ).new_page()
            page.set_default_timeout(timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                # even domcontentloaded can flake; try a plain load and continue
                try:
                    page.goto(url, timeout=timeout_ms)
                except Exception:
                    browser.close()
                    if verbose:
                        print("      [playwright] goto failed")
                    return None
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=wait_ms)
                except Exception:
                    pass
            else:
                page.wait_for_timeout(wait_ms)
            if scroll:
                try:
                    for _ in range(4):
                        page.mouse.wheel(0, 4000)
                        page.wait_for_timeout(1200)
                except Exception:
                    pass
            html = page.content()
            browser.close()
            if verbose:
                print(f"      [playwright] rendered {len(html)} chars")
            return html
    except Exception as ex:
        if verbose:
            print(f"      [playwright] error: {str(ex)[:90]}")
        return None


if __name__ == "__main__":
    import sys, re
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.parkrecord.com/calendar/"
    html = render_with_playwright(url)
    if html:
        dates = len(re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}", html))
        print(f"rendered {len(html)} chars | {dates} date-mentions")
    else:
        print("no render")
