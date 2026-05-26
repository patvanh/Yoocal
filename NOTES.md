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

## Update 7: Featured tiered cap (868eca8)
- Featured count now scales with the day's active event count:
  <5 events -> max 1 featured; 5-10 -> max 3; 11+ -> max 5. (Was flat MAX=5.)
- It's a MAXIMUM, not a target — only genuine standouts (richness >=2) fill up
  to the cap; no padding with filler. Empty days correctly show 0.
- Also fixed: manual featured flags now LEAD but standouts fill remaining slots
  (previously a manual flag replaced standouts entirely).
- Elkhart "empty featured" investigation conclusion: NOT a bug — empty days are
  genuinely 0-event days (small town, shoulder season). Every day WITH events
  has events clearing the quality bar. The tiered cap was the real improvement
  that came out of looking.
- Verified counts vs real data before ship: Elkhart 2evt->1, 7evt->3, 0evt->0;
  Park City 16evt->5, 26evt->5.

## Update 8: Fixed dead Road America links + link-rot risk noted
- The hardcoded Road America 2026 season (elkhart_scraper.py) used guessed
  /events/<slug> URLs — ALL 9 were 404. Road America's real event pages are at
  the site root (e.g. /motoamerica-superbikes-vintage-motofest), not /events/.
  Remapped 6 to verified-200 real pages, 3 (no confident match) to /events index.
  Fixed scraper source + current production data. Slugs change per season —
  re-verify annually.
- GENERAL RISK: hand-entered/hardcoded event links rot silently (these 404'd,
  only found by clicking). TODO: build a link-health check — curl every event's
  `link`, flag non-200s — run periodically across all cities. Catches dead links
  automatically instead of one-click-at-a-time. Higher value as we add more
  hand-curated resort-town events.

## Update 9: link_health_check.py built (audit tool) — pipeline integration deferred
- New tool link_health_check.py: collects all unique event links across cities,
  checks each (HEAD->GET, threaded), classifies OK/redirect/dead/error. Run plain
  = report + write link_health_fixes.json; --apply writes fixes to city files.
- First run found: 1612 unique links. 91 redirects (mostly %2b->%2B encoding-case
  + http->https, all WORK), 25 genuinely dead (404), ~20 false-positive 403s
  (library + bandsintown — they BLOCK bots but work in browsers; do NOT "fix"),
  1 PLUNJ connection error (transient), 2 trailing-space/%20 links (strip fixes).
- KEY: a one-time --apply changed 213 events, but that's because ONE dead URL
  (visitparkcity.com/event/group-fitness-classes) is on 190 recurring-event
  instances. NOT a bug — it's the recurring-flooding problem (Group Fitness 193x)
  showing up as a shared dead link. The link fix + recurring-flood collapse are
  RELATED — collapsing the flood would fix the link on 1 card instead of 190.
- DECISION: did NOT apply the production fix (gets overwritten by build anyway)
  and did NOT wire into pipeline yet. Reverted the 213 edits.
- TODO — Option 3 (build properly, fresh): make link-health a POST-BUILD step in
  build_master_and_views.py so fixes auto-reapply each rebuild. MUST include:
  (1) a cache (only re-check links not verified in last ~7 days — don't crawl
  1600 links every build); (2) treat ONLY 404/410 as dead (NOT 403/timeout —
  those are false positives, confirmed); (3) only fall back to a verified-200 URL;
  (4) redirects -> final target is safe. Test thoroughly BEFORE wiring — a buggy
  auto-fixer in the pipeline silently degrades links on every build.
- creeksideparkcity.com domain is fully DOWN (8 events) — needs manual source fix.

## Update 10: Option 3 DONE — link-health is now an always-on post-build step
- link_health.py + wired into build_master_and_views.py (before "Done!").
- Runs every build, repairs dead links automatically. 7-day cache -> most builds
  re-check ~0 links (confirmed: 2nd build "1561 cached | 0 to check").
- Fixes ONLY 404/410 -> verified-200 fallback. Guards (tested): 403 treated OK
  (library/bandsintown bot-block but work in browsers, 0 wrongly changed);
  timeouts + redirects left alone (no churn).
- Durable: fresh build re-scraped raw (still had old dead Road America URLs) and
  link-health re-fixed 8 automatically — catches links that come back dead.
- creeksideparkcity.com (dead domain, 8 events) flagged manual each run.
- Cache/log gitignored; changes recorded in link_health_log.json.
- NOTE: ~191 of 219 fixes are ONE link (Group Fitness) flooded across 191
  recurring instances. Recurring-flooding fix (NEXT) collapses that to ~1.

## Update 11: Recurring-flooding — amenity removal (the big fix)
- DIAGNOSIS: the "flood" was one-per-day events stacking in RANGE/all views.
  In single-day views each shows once (correct). Raw had them pre-expanded into
  N dated records (e.g. Group Fitness recurrence=weekly_multiple expanded to 189
  daily records); production stripped the recurrence field so they looked like
  189 independent events.
- TWO categories: (a) always-on BUSINESSES/amenities masquerading as daily
  events (PLUNJ cold plunge 220x, Group Fitness rec-center drop-in 189x) —
  REMOVED; (b) genuine recurring EVENTS (farmers market, yoga, run clubs,
  Fascia) — KEPT.
- FIX: EXCLUDED_TITLE_PATTERNS list in build_master_and_views.py, filtered early
  (before dedup/views/link-health). Tight substring match, extensible. Removed
  409 events (PLUNJ 220 + Group Fitness 189). Park City 1558->1149.
- Confirmed link/flood tangle: link-health fixes dropped 219->30 once Group
  Fitness's 191-event dead-link cluster was removed.
- PENDING: genuine recurring events (12-23x each) still stack in all/upcoming
  view. Range-view collapse (one labeled entry in range views, keep per-day in
  single-day views) is a possible polish — ASSESS LIVE FIRST: removing the 2
  big amenities may have made the all-view acceptable without it. Don't build
  unless the live view still feels cluttered (avoid over-engineering).

## TODO (added): Filter UI — multi-select dropdowns
- Want proper filtering on the calendar: dropdown boxes where users can select
  MULTIPLE options (e.g. categories: Music + Arts + Family at once), not just the
  current single day-filter. Likely filters: category/tag, maybe venue, maybe
  free-vs-paid, time-of-day. Multi-select (checkable), combinable.
- Frontend work in CalendarClient — design the filter state + UI, wire to the
  existing filteredEvents logic. Test like the badge work (real data, live view).

## Update 12: #2 + #3 resolved (Creekside removed; "series" investigated)
- #2 Creekside church services: REMOVED. Dead venue domain, no alternate site,
  weekly standing services = amenity noise. Added EXCLUDED_VENUE_PATTERNS
  (venue-match, since title "Church Service" too generic). Cleared link-health's
  only manual-review item. (commit fcaaa54)
- #3 "multi-date series (Triple Trail Challenge)": the NOTES example was STALE —
  no Triple Trail Challenge in current data. Investigated all "Series" events:
  -- Concert "series" (Miner's Park, Newpark, Billy Blanco's) = correctly
     SEPARATE distinct shows (diff artist/night). No fix; not duplicates.
  -- Repeating series (Twilight Ride 9x, Tom Georges 18x) = fine recurring
     events, one-per-date, read OK after amenity cleanup. No fix.
  -- REAL bug found: Crafternoons dup'd (5 dates) — same library event from 2
     feeds, titles "2 Go" vs "To-Go Series", (title,date) key missed it.
- FIX: added "series" to _TITLE_FILLERS + normalize "2 go"/"2go"->"to go".
  Blast-radius tested across 4 cities: ONLY 5 Crafternoons pairs merge, nothing
  else (concert series stayed 17 distinct). Crafternoons 17->12.
- LESSON (again): NOTES item pointed at a stale example; careful look found the
  premise gone but surfaced a real adjacent bug. Verify the problem still exists
  before building for it.

## Update 13: Category normalization + Jackson coverage investigation
- CATEGORIES (shipped, 4564b30): category_normalizer.py maps 53 messy source
  cats -> ~12 clean buckets, stamped as filter_categories (list) on every event
  in build. Title-enrichment for footraces: Running & Races now 73 vs 12 source-
  tagged. Frontend multi-select filter UI = next step, consumes this field.
  KNOWN GAP: enrichment is running-only; "Music Series: Tom Georges" lands in
  Community not Music (source-tagged Community, title not enriched). Add music/
  other title-enrichment later.

- JACKSON COVERAGE INVESTIGATION (what was real vs not):
  -- "Missing events" (Joseph/Technicolor Dreamcoat) = STALE DATA, not a bug.
     Fresh scrape + rebuild pulled it in. Chamber scraper works (sitemap has 230
     /event/ URLs, scraper gets them, 0 failed).
  -- Daily scrape automation (.github/workflows/scrape-daily.yml) IS running &
     committing daily (yoocal-bot, confirmed 5/15-5/25). Not broken.
  -- REAL finding = BREADTH GAP. Jackson has only 6 sources, all single-venue or
     chamber. Running coverage is genuinely thin (1 marathon, 1 5k/10k for a
     summer resort town). Dedicated sites NOT sourced: jacksonholemarathon.com,
     tetonmountainruns.com, runningintheusa.com, Jackson Hole Mountain Resort
     (JHMR), John Wayne events. Also jhnewsandguide.com (JS-rendered, known).
  -- This breadth/discovery gap = THE core problem, and it's the SAME problem as
     the Sun Valley rollout (how to comprehensively source a town). Next big
     focus. Hand-adding sources works but doesn't scale; improving discovery
     (v3 engine) is the real lever.

- WORKFLOW DESIGN NOTE: every scraper step is continue-on-error, and the build
  only fails if PC+Heber+Elkhart ALL fail — Jackson failing alone is silent.
  Consider tightening: alert if any city's event count drops sharply.

## Update 14: Discovery v3 FIXED (root cause = query phrasing) + wiring triage
- ROOT CAUSE of "v3 misses obvious sources": queries used quoted exact-match +
  OR ('"{city}" 5k OR marathon') which SUPPRESSED real event sites in Google
  ranking. Switched to NATURAL phrasing ('{city} running races marathon 5k').
  Tested decisively: quoted form missed jacksonholemarathon/tetonmountainruns/
  runningintheusa; natural form surfaces all of them. (commit 2de934d)
- Also: 15->31 templates covering ALL category buckets; removed max_domains=20
  cap; blacklisted Fed-symposium + data-broker noise. 91 domains found, 42
  "actionable."
- KEY LESSON: discovery's estimated_future_events is RAW/statewide-blind. High
  counts from regional aggregators mislead. travelwyoming.com showed ~330 but
  TESTED: only ~9 Jackson-area per 120 URLs, several already-have dupes (GTMF,
  Wildlife Art). NOT worth wiring (scrape 580 statewide pages for ~couple dozen
  net new). Locally-scoped domains beat big aggregators.
- WIRING TRIAGE (verify each before wiring — counts lie):
  -- Already have: jacksonholechamber, gtmf, milliondollarcowboybar.
  -- SKIP: travelwyoming (statewide, mostly out-of-radius/dupes), findarace.com
     (2897 NATIONAL races — would need geo-filter to Jackson).
  -- PROMISING local (verify like travelwyoming, then wire): jhlandtrust.org
     (~48, land-trust outdoor events), dishingjh.com (~7, food, wp_tribe),
     skinnyskis.com (43 sitemap event URLs, local ski/trail shop), mtntrails.net
     (32 sitemap event URLs, local trails). buckrail.com (~60 RSS) +
     localnews8.com (~50 RSS) = local news feeds, verify relevance.
  -- RACE SITES with NO sitemap (need custom scraper): jacksonholemarathon.com,
     tetonmountainruns.com, jhhalf.com. Custom/JS or RunSignup-backed.
  -- VALIDATOR NOTE: richness validator marked real sitemap sources as
     'low-no-samples' (skinnyskis 43 urls, mtntrails 32) when sample-fetch
     failed — may be under-rating good sources. Worth revisiting.
- jhnewsandguide.com: has scrapeable sitemap (~6) — NOT JS-only as previously
  thought. Re-evaluate.

## Update 16: Generic Firecrawl+LLM extractor BUILT (the scalable backbone)
- NEW firecrawl_extractor.py — extract_events_from_url(url, source_name, ...):
  Firecrawl /scrape -> clean markdown (handles JS/anti-bot/403s) -> Anthropic API
  (claude-haiku-4-5-20251001) extracts events as strict JSON -> sanity filter
  (date must parse + be future; title >=3 chars) -> yoocal events. Strips nav
  chrome before sending to LLM + 40k char cap (CRITICAL: without chrome-strip,
  nav menus ate the budget and we got 1 race instead of 15 — verify extraction
  COUNT, not just "looks clean").
- Wired into jackson_scraper.py as FIRECRAWL_SOURCES (config list + loop, like
  RUNSIGNUP/SITEMAP). New stubborn source = ONE config line, no custom scraper.
- First source: runningintheusa (was 403-blocked to plain requests). Got 15
  races ALL distances, incl. ones RunSignup/chamber missed: Old Bill's Fun Run,
  John Wayne Grit Series, Cirque Series, Tin Cup, Lyndsey Kunz Memorial.
- DROPPED RunSignup for Jackson (RUNSIGNUP_SOURCES=[]): Firecrawl extractor more
  complete (15 vs 4) + avoids cross-source dups (dedup did NOT merge fuzzy
  cross-source title variants — "Teton Mountain Runs" Jul11-12 vs Jul12, "JH
  Marathon, Hole Half..." vs "Jackson Hole Marathon"). runsignup_scraper.py KEPT
  for reuse/other cities. One source = no dup problem.
- RESULT: Jackson Running & Races 1 -> 17 events (session start: "1 marathon,
  1 5k"). Multi-day same-name races (Grand Teton Half Jun5+6, Targhee Jul4+5,
  Teton Mtn Runs Jul11+12) KEPT SEPARATE intentionally — they're different
  distances/races per day; merging would hide events.
- COST NOTE: daily GitHub Actions workflow now makes Firecrawl + Anthropic calls
  per FIRECRAWL_SOURCES entry. Both keys already in Actions secrets. Minor cost,
  scales with # of firecrawl sources. Use sparingly — only for sites the free
  structured paths (sitemap/RSS/API) can't handle.
- STRATEGY (three tiers, confirmed): 1) free structured (chamber sitemap,
  RunSignup API) first; 2) Firecrawl+LLM fallback for blocked/JS/messy; 3) custom
  code last resort. Scales to any city by config.
- NEXT CANDIDATES for FIRECRAWL_SOURCES (the spreadsheet gaps): chamber special
  pages (Old West Days, Fall Arts, 4th of July), grandtarghee.com (Targhee Fest/
  Bluegrass), jhrodeo.com (rodeo), jacksonhole.com (resort events). Each = 1 line.
- FUTURE: use Firecrawl as v3 discovery's FALLBACK PROBE tier (for domains the
  cheap structural probes fail) so v3 stops having dead ends. Cost: ~1 Firecrawl
  call per probed domain — gate it to only sites cheap probes can't validate.
