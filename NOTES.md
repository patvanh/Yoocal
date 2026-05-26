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
