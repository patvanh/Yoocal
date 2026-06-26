#!/usr/bin/env python3
"""
incremental_cron.py — nightly incremental store maintenance for cut-over sources.

Runs the incremental update (listing -> diff -> fetch-only-new -> gated commit)
for each source that has been migrated to the incremental model, keeping
last_good_sources.json complete and current. The build's existing resilience
guard then UNIONs the store into the per-city views, so the complete event set
flows through without any change to the scrapers or build.

This runs IN ADDITION to the full scrapers during rollout: the full scrape still
runs (and may be throttled/partial), incremental keeps the store complete, and
the guard unions both. Purely additive — if an incremental run has an off night,
the full scrape + last-good still produce a valid build.

Add a source here once its shadow validation passes and it's been cut over.
"""
from __future__ import annotations
import sys
import traceback

from incremental_update import incremental_update_schema_source, commit_to_store

# Sources migrated to incremental. Each is a schema.org/sitemap source whose
# detail pages parse via scrape_schema_org_events.
INCREMENTAL_SCHEMA_SOURCES = [
    {
        "source_name": "Jackson Hole Chamber of Commerce",
        "sitemap_url": "https://www.jacksonholechamber.com/sitemap.xml",
        "url_pattern": r"/event/",
        "default_lat": 43.4799, "default_lng": -110.7624,
        "default_city": "Jackson, WY",
    },
    # Add more cut-over sources here as they're validated.
]


def main():
    ok, failed = 0, 0
    for cfg in INCREMENTAL_SCHEMA_SOURCES:
        name = cfg["source_name"]
        try:
            print(f"\n[incremental-cron] updating: {name}")
            updated, report = incremental_update_schema_source(
                source_name=name,
                sitemap_url=cfg["sitemap_url"],
                url_pattern=cfg["url_pattern"],
                default_lat=cfg["default_lat"],
                default_lng=cfg["default_lng"],
                default_city=cfg["default_city"],
                verbose=True,
            )
            # Gated commit: aborts on empty / big shrink / balloon.
            wrote = commit_to_store(name, updated, dry_run=False, verbose=True)
            if wrote:
                ok += 1
            else:
                failed += 1
                print(f"[incremental-cron] {name}: commit gate blocked the write "
                      f"(store left unchanged)")
        except Exception:
            failed += 1
            print(f"[incremental-cron] ERROR updating {name}:")
            traceback.print_exc()
            # Never fail the whole cron on one source — the full scrape + last-good
            # still produce a valid build.
            continue
    print(f"\n[incremental-cron] done: {ok} updated, {failed} skipped/failed "
          f"of {len(INCREMENTAL_SCHEMA_SOURCES)} source(s)")
    return 0  # always succeed; incremental is supplementary


if __name__ == "__main__":
    sys.exit(main())
