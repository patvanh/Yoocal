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


def render_with_playwright(url, wait_ms=8000, wait_selector=None,
                           scroll=True, timeout_ms=45000, verbose=True):
    """Load url in headless Chromium, let JS run, return rendered HTML or None.

    wait_selector: optional CSS selector to wait for (more reliable than a fixed
    delay when you know the widget's container). Falls back to wait_ms otherwise.
    scroll: scroll to bottom to trigger lazy-loaded / infinite-scroll content.
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
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
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
