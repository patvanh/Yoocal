# Yoocal — Working Notes & Lessons (read at start of each session)

## Pipeline mental model
- Scrapers write per-city RAW files: public/raw/events-*.json
- build_master_and_views.py: reads raw -> global dedup -> repairs -> writes
  deduped master public/events-all.json -> radius-filters into per-city
  PRODUCTION files (public/events.json, events-heber.json, etc.)
- The SITE serves production files (deduped). Users never see raw.

## Dedup architecture
- Primary key: event_key() = (normalized_title, date)
- _normalize_title(): strips HTML, unescapes entities, lowercases, drops
  punctuation + filler words. Title-cleaning chokepoint.
- _clean_display_text(): cleans user-facing title/desc — strips HTML,
  unescapes entities, decodes percent-encoding (%26). Put future encoding
  fixes HERE.
- _prefix_merge(): 2nd pass, merges when one normalized title is a strict
  string-PREFIX of another same-day (terse vs full lineup). GUARD: won't
  merge if the terser title is race-like (has a distance token) — race
  distances stay separate cards.
- _is_junk_title() / _JUNK_TITLES: exact-match blocklist for scraped UI nav
  labels ("Views Navigation" etc). Exact-match only, NOT length-based, so
  real short titles (MAX, 10K) survive.

## Product decisions (don't relitigate)
- Architecture stays town-scoped (featured cities + point/radius), NOT regions.
- Same-day races at different distances = SEPARATE cards by default. Exception
  races (owner wants merged, e.g. Round Valley Rambler) go in a MANUAL
  overrides list, NOT the merge algorithm.
- Festivals containing a race sub-event DO merge. Concerts: headliner-only vs
  full-lineup at same venue = merge.
- Featured events: manual flags lead; else only genuine standouts (richness
  >=2), capped at 5 but NEVER padded; else fall back to single best. Featured
  currently keyed to "today" only — does NOT follow the day-filter yet.

## Lessons (process)
1. ALWAYS inspect real data before concluding. Tonight's wasted cycles came
   from jumping ahead (failed sed revert, "stale audit" misread, subset-merge
   over-merge).
2. TEST merge/dedup/date logic against real cases BEFORE rebuilding/deploying.
3. ASK owner on judgment calls one at a time.
4. Data-correct != user-correct. The timezone bug was invisible in every data
   check — only caught by looking at the LIVE site in the evening.
5. macOS sed -i '' is fragile — use Python for in-place edits.
6. Bash chokes on :NN and ! in double-quoted python -c — use heredocs.
7. Container has NO access to local repo. Owner runs commands, pastes output.

## Scaling loop (proven w/ TownLift)
discover -> vet -> wire -> verify -> rebuild -> commit
discover_sources_v3.py --city "X" -> review pending_sources_v3.json -> add
scraper fn/config -> isolation-test -> full scrape -> build -> confirm -> commit.
discover_sources_v3 now has newspaper/radio/TV/library/venue query templates.

## Open TODOs
- [ ] Featured strip should follow the selected day-filter (Tomorrow/Pick date),
      currently hardcoded to today. Wire dayFilter/pickedDate into the memo.
- [ ] Empty-day UX: fall-forward to upcoming when a day has no events.
- [ ] Recurring event flooding (PLUNJ 225x, Group Fitness) — collapse repeats.
- [ ] Jackson discovery results sitting done in pending_sources_v3.json — triage.
- [ ] Triple Trail Challenge / multi-date series events — need representation.
- [ ] Optional: Round Valley Rambler merge override.
- [ ] Tune featured QUALITY_BAR per-city if it feels too sparse/generous.

## Strategy (owner, near full-time)
1. Resort towns FIRST (Sun Valley + Ketchum, then Vail/Aspen/Telluride).
2. Depth: complete existing cities. 3. Automation. 4. Utah breadth (deferred).
Growth (/go tracking, monetization) AFTER data is complete.

## Housekeeping
- audit_issues.json = build artifact, leave uncommitted.
- scraper_baselines.json + scraper_health.json ARE committed (rolling state).
- Rotate the SerpApi + Anthropic keys leaked in old chat history.
- Repo: github.com/patvanh/Yoocal. HEAD after tonight: a005bb1 (8 commits).

## Update 2: datetime-attr ingestion COMPLETE (a792b83)
- schema_org_scraper.py now ingests events from datetime="..." attrs when a
  page has no Event JSON-LD (_human_to_iso_datetime + _fallback_event_from_html).
  Synthesizes a raw Event (name from H1/title branding-stripped, startDate from
  datetime attr) and runs it through the normal _parse_event path. Tested:
  U-Foria @ Cowboy Bar -> clean event w/ date+time. JSON-LD path unchanged.
- CAPABILITY is now end-to-end (discovery in 4c750cf + ingestion here). To wire
  a datetime-attr source, just add it to a city scraper's source list like any
  sitemap source — it works now, no new code needed.
- NOT YET WIRED: Million Dollar Cowboy Bar into Jackson. Low priority — its
  sitemap is mostly past events, sparse future. Add a config entry to
  jackson_scraper.py + rebuild whenever you want those few Jackson shows.
- Supported human date formats in the fallback: "Mon DD, YYYY HH:MM AM/PM" and
  variants. If a future source uses a different format, add it to the fmts list
  in both _human_to_iso_datetime (schema_org_scraper) and _parse_human_date (v3).

## Update 3: Cowboy Bar wiring REVERTED (date-integrity issue)
- Wired then UNWIRED milliondollarcowboybar.com. Per-URL scrape looked perfect
  (72 clean events in isolation), but PRODUCTION spot-check found events on
  dates absent from their source pages — e.g. "Rhett Haney" pages have datetime
  attrs of Mar 23/24/25 2026 (past, correctly scraped as empty), yet production
  showed Rhett Haney on May 25-30 2026 with polluted titles ("Rhett Haney June
  19, 2025"). Bad dates come from the scrape+_expand_event_dates+dedup
  interaction, NOT single pages. Root cause not fully traced.
- LESSON: per-URL/isolation tests passed; the bug only appeared in final
  production data. ALWAYS spot-check production output, not just components.
- Cowboy Bar TODO if revisited: (1) trace why production assigns dates not on
  the page (likely a sibling event with malformed end_date triggering range
  expansion + title collision in dedup); (2) strip trailing dates from <title>
  in _fallback_event_from_html; (3) re-validate IN PRODUCTION before shipping.
  Do NOT rewire as-is.
- KEPT (sound, tested): v3 datetime-attr discovery (4c750cf), schema_org
  datetime ingestion (a792b83), full-list richness sampling (256f7cf).

## Update 4: Cowboy Bar WIRED CORRECTLY (df96bf5) — supersedes Update 3
- The revert in Update 3 was correct at the time (the /events/ sitemap pages
  have stale dates + polluted titles), but we then found the RIGHT source: the
  /music listing page embeds all events as a JSON array with correct dates and
  clean titles. Owner's screenshot of the live calendar is what corrected the
  earlier wrong conclusion that the dates were "fabricated" — they were real.
- New module busites_music_scraper.py reads that embedded JSON (title + start +
  image + html-description per record). Wired as BUSITES_SOURCES in
  jackson_scraper.py. 68 future live-music events, verified IN PRODUCTION:
  Rhett Haney May 25-30 correct, 0 title pollution, 0 out-of-range dates.
- The /music embedded-JSON pattern is a 'busites' CMS thing — busites_music_
  scraper is REUSABLE for other venues on that CMS (look for the S3 path
  busites_www and a /music or similar listing page).
- KEY LESSON (reinforced): the sitemap pointed at the WRONG representation of
  the events. When a source looks broken, check whether the site has a cleaner
  listing/calendar page before abandoning it. Also: owner domain knowledge
  ("live music every day") + a screenshot beat the scraped data and caught a
  wrong conclusion.

## Update 5: Featured follows selected day (fixed) + 2 display TODOs
- FIXED: featured memo was hardcoded to "today" — on the June 1 view it showed
  a past May 26 event labeled "Happening today." Now derives the viewed day
  from dayFilter/pickedDate and filters featured to it. Verified via build.
- TODO (display polish, NOT data bugs — data is correct):
  1. "Happening today" FEATURED badge text is hardcoded in the render; should
     reflect the selected day (e.g. "Featured" or "Happening Jun 1") instead of
     always "today". Search CalendarClient.tsx for the badge label.
  2. Multi-day events (e.g. Center for the Arts exhibitions running May 25 ->
     Jun 1) show their START-DATE badge ("May 25") on every day in range, so on
     the June 1 view they look like misplaced old events. They ARE correctly on
     June 1 (span includes it). Decide UX: show "Through Jun 1" / "Ongoing" /
     the span, instead of the bare start date. Needs design judgment — do fresh.

## Update 6: Multi-day badge + featured display FIXED (afc7d5b) — all cities
- Root cause of "June 1 shows May 25 events" / "featured shows wrong date":
  V2EventCard always badged event.date (the start). Multi-day events (e.g.
  Center for the Arts exhibitions May 25->Jun 1) badged "May 25" on every day
  in their run, looking like misplaced past events — worst in the featured strip.
- FIX (all cities — one shared CalendarClient/V2EventCard): added viewedDay prop.
  Single-day modes (today/tomorrow/pickdate): multi-day events badge the VIEWED
  day + a "thru [end]" line. Single-day events + range modes (weekend/7days/all)
  badge their own date. Featured label now "Happening [day]" not always "today".
- Verified: badge logic tested across single/multi-day x viewed/range BEFORE
  ship (not just compile); confirmed live on PC, Heber, Jackson, Elkhart.
- Display logic is shared across all 4 cities — per-city differences are DATA
  only. So display fixes are inherently all-cities.
