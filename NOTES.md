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

## Update 17: More Firecrawl sources (Jackson) + category-enrichment attempt REVERTED
- Added 2 more FIRECRAWL_SOURCES to Jackson (committed): grandtarghee.com/events
  (13 events: Targhee Fest, Bluegrass, Pierre's Hole, bike races) + jacksonhole.com
  /events (JHMR: Bike Park, JH Downhill, Food&Wine, People's Market — 7 net after
  dedup). Widened Jackson radius 20->25mi to include Alta/Targhee (23.4mi), Driggs
  (24.2mi), Victor (19.4mi). Jackson now ~574 events, 3 Firecrawl sources.
- PATTERN learned: Firecrawl extractor works great on EVENT-LISTING pages
  (runningintheusa, grandtarghee, jacksonhole.com all clean). FAILS (returns 0,
  correctly) on MARKETING/LANDING pages with no concrete dates (jhrodeo.com =
  recurrence rule "Wed/Sat Memorial-Labor Day" no dates; chamber /old-west-days/
  = prose description). Those need a recurring-event model, not extraction. Test
  candidate URLs: listing page = good, marketing page = skip.
- Chamber "special page" gaps were ILLUSORY: Fall Arts, QuickDraw, art fairs,
  Palates already in chamber /event/ sitemap (earlier fuzzy cross-check just
  mis-matched titles). Chamber coverage is solid. Old West Days = past (May15-25).
- CATEGORY ENRICHMENT ATTEMPT — REVERTED (not committed). Tried adding cycling/
  MTB->Sports+Outdoor, food/wine/brew->Food&Drink, tightening Festival rules.
  GOOD shifts (Outdoors 0->14, Sports 1->26, Food 2->82) BUT entangled with
  pre-existing over-match: Festivals exploded 2->127, Music ->278. ROOT CAUSE:
  greedy rules + the killer case "Grand Teton Music FESTIVAL" — an org/series
  NAME containing a category word ("music festival") makes title rules mis-fire
  (GTMF's 77 concerts -> Festivals). Reverted event_classifier.py to keep safe
  committed state. Events stay live, just some in Community (suboptimal not wrong).
- CATEGORY QUALITY = real next task, but needs a DEDICATED pass, NOT reactive
  keyword-patching (3 iterations tonight kept surfacing new breakage). Needs:
  (a) handle "org/series name contains category word" (GTMF, "X Music Festival"
  series) so series concerts -> Music not Festivals; (b) all-category before/after
  test harness; (c) unify the two taxonomies (classifier CANONICAL_CATEGORIES vs
  normalizer buckets) that keep causing multi-layer ripple. 58% of Jackson still
  buckets Community — main limiter on the future filter UI.

## Update 17: More Firecrawl sources (Jackson) + category-enrichment attempt REVERTED
- Added 2 more FIRECRAWL_SOURCES to Jackson (committed): grandtarghee.com/events
  (13 events: Targhee Fest, Bluegrass, Pierre's Hole, bike races) + jacksonhole.com
  /events (JHMR: Bike Park, JH Downhill, Food&Wine, People's Market — 7 net after
  dedup). Widened Jackson radius 20->25mi to include Alta/Targhee (23.4mi), Driggs
  (24.2mi), Victor (19.4mi). Jackson now ~574 events, 3 Firecrawl sources.
- PATTERN learned: Firecrawl extractor works great on EVENT-LISTING pages
  (runningintheusa, grandtarghee, jacksonhole.com all clean). FAILS (returns 0,
  correctly) on MARKETING/LANDING pages with no concrete dates (jhrodeo.com =
  recurrence rule "Wed/Sat Memorial-Labor Day" no dates; chamber /old-west-days/
  = prose description). Those need a recurring-event model, not extraction. Test
  candidate URLs: listing page = good, marketing page = skip.
- Chamber "special page" gaps were ILLUSORY: Fall Arts, QuickDraw, art fairs,
  Palates already in chamber /event/ sitemap (earlier fuzzy cross-check just
  mis-matched titles). Chamber coverage is solid. Old West Days = past (May15-25).
- CATEGORY ENRICHMENT ATTEMPT — REVERTED (not committed). Tried adding cycling/
  MTB->Sports+Outdoor, food/wine/brew->Food&Drink, tightening Festival rules.
  GOOD shifts (Outdoors 0->14, Sports 1->26, Food 2->82) BUT entangled with
  pre-existing over-match: Festivals exploded 2->127, Music ->278. ROOT CAUSE:
  greedy rules + the killer case "Grand Teton Music FESTIVAL" — an org/series
  NAME containing a category word ("music festival") makes title rules mis-fire
  (GTMF's 77 concerts -> Festivals). Reverted event_classifier.py to keep safe
  committed state. Events stay live, just some in Community (suboptimal not wrong).
- CATEGORY QUALITY = real next task, but needs a DEDICATED pass, NOT reactive
  keyword-patching (3 iterations tonight kept surfacing new breakage). Needs:
  (a) handle "org/series name contains category word" (GTMF, "X Music Festival"
  series) so series concerts -> Music not Festivals; (b) all-category before/after
  test harness; (c) unify the two taxonomies (classifier CANONICAL_CATEGORIES vs
  normalizer buckets) that keep causing multi-layer ripple. 58% of Jackson still
  buckets Community — main limiter on the future filter UI.

## Update 18: Per-city coverage audit (research vs our data)
Method: web-researched each town's real event scene, compared to current sources.
KEY FINDING: coverage is BETTER than expected — aggregators (Park Record, Heber
Valley Tourism, Elkhart Lake Tourism) carry most events. Few real gaps. (Same
lesson as Jackson spreadsheet: much that "looks missing" is under an aggregator.)

- PARK CITY (1136 events, very well covered): Has Park Record (679), Mountain
  Town Music, Egyptian, Deer Valley (62), Visit PC, Farmers Mkt, KPCW, PC
  Institute. Research confirms Deer Valley/Egyptian/Farmers/Institute all present.
  CANDIDATE GAP: Park City Mountain Resort / Canyons Village concerts (not a
  distinct source — verify not inside Park Record). Kimball Arts Fest, Miner's
  Day (verify). LOW priority.
- HEBER (259): Has Heber Valley Tourism (106=gohebervalley), Deer Valley, Google
  Events, Heber Valley Life, RunSignup. CANDIDATE GAPS: Ideal Playhouse (theater
  — Arts&Theater only 17, real playhouse exists), Wasatch Trail Run Series
  (Running only 13). Soldier Hollow/Wasatch Back Art Fest/Railroad likely already
  in the two aggregators — verify. MEDIUM priority.
- ELKHART LAKE (227, well covered): Elkhart Lake Tourism (190=elkhartlake.com) is
  TOP source and already carries Lake Deck Music, Farmers Mkt, Jazz on the Vine,
  Sunset Cruises. Road America (13), Osthoff, Siebkens present. Verdict: little/
  nothing missing. LOW priority.
- JACKSON: overhauled this session (3 Firecrawl sources, 17 races, Targhee/JHMR).
  Well covered.

SHORT real candidate list to verify->maybe wire:
  1. Park City Mountain Resort events (Canyons concerts)
  2. Heber: Ideal Playhouse (theater)
  3. Heber: Wasatch Trail Run Series
BIGGER lever than new sources = CATEGORY FIX (Community still top bucket in 3/4
cities). Coverage is solid; categorization is the real limiter.

## Update 19: Day 10 — backend dedup hardening, search overhaul, cross-city
Long session (8am to mid-afternoon). 18 commits. Site materially better at the
end across recurring-event coverage, dedup, SEO, search semantics, and a new
cross-city browsing mode.

### Commits in order
1. `70bf9a5` HVT date_label parser (weekly recurrence from "Sat May-Sep")
2. `d627ea5` Tokenized search ("running 5k" matches "Trail Series 5K")
3. `60d09d2` HVT bare date-range parser ("Jul 30 - Aug 1" -> 3 records)
4. `861a3bf` Deterministic occurrence_dates from weekly recurrence fields
5. `342a3d8` SEO: cross-city redirect + slugify year-strip (267 404 fix)
6. `40f38b2` Recover corrupted coords + truncated date lists
7. `7c07700` Address-derived coordinates (address > corrupted lat/lng)
8. `a6bdc3c` See all N results overlay (grouped rows + expand + modal)
9. `46e09d9` Align dropdown count with overlay count
10. `ebfbe28` Venue+time dedup + tier-aware aggregator suppression
11. `fc6c94b` Search synonym matching (concert -> music/band/live)
12. `13875ae` Search prefix-key + word-boundary
13. `48d0379` Per-event schema image
14. `a3ef834` Add missing optional fields to YoocalEvent type
15. `ef778a9` Cross-city Piece 1: fetch all cities in parallel
16. `82ba95c` Cross-city Pieces 2 + 2.5: search + city filter pills
17. `a761cda` Cross-city Piece 4: pills on rows + plural search
18. `387a616` Cross-city Piece 3: distance-based ranking in All cities

### New architectural patterns (worth keeping)

**Dedup pipeline is now 4-stage.** Was 1-stage (title+date). Today added:
1. prefix-merge (existing, suffix-variant collapse)
2. aggregator-suppress (existing, low-trust title-match drop)
3. **venue+time-dedup (new)** — same (normalized_venue, date, start_time) =
   same event under different titles. Catches the Keller Williams case (5
   records, 5 different titles, all at Egyptian Theatre May 29 8pm).
4. **venue+date-aggregator-suppress (new)** — when any tier-1/2/3 source
   has an event at a venue+date, drop every tier-4 (Google Events,
   Bandsintown, etc.) record at the same venue+date. Catches corrupted-time
   aggregator dupes that survive #3. Tier-aware via SOURCE_PRIORITY.

Future-me when adding the 5th: copy the pattern of _venue_time_dedup.
Universal-by-default means it lives in build_master_and_views.py and applies
to all 4 cities automatically.

**Address-as-ground-truth coordinates.** HVT API was returning Pennsylvania
lat/lng (39.76, -76.69) for Heber events — radius filter silently dropped
them. Google Events was returning Heber's exact center coords (40.5069,
-111.4133) for Salt Lake events — radius filter incorrectly included them.
Both bugs solved by: parse city name from address/location text, look up its
canonical coords in a _KNOWN_CITIES table (27 entries spanning Heber Valley,
Park City, Salt Lake metro, Jackson area, Elkhart area), override the
source-provided lat/lng. The address string is ground truth; coords are
derived. Also write the corrected lat/lng to e_copy so map pins show the
right location, not just the filter pass.

**Cross-city Model C (current city first, expand to others).** All 4 city
JSONs fetched in parallel on every page load; current city = primary, others
tagged with `_sourceCity` for attribution. Dropdown stays local-only (quick
peek). Overlay shows city filter pills (Heber Valley · Park City · Jackson
Hole · Elkhart Lake · All cities). Default = current city. When user taps
"All cities," sort is distance-first (closer cities lead), date second.
Every event row has a city pill so attribution is visible.

The right user mental model for the sort: distance always wins. Tier
(search prefix-match) only matters within a single city — never overrides
distance. Earlier I had it the other way around and "Concerts on the Slopes"
(PC) appeared first on every city's All cities view because its title
prefix-matched "concert" globally. Broken. Distance-first is correct.

### Hard-won lessons (write these down so I stop repeating them)

**Heredoc backslash trap (bit 4-5 times today).** Bash heredoc + python
script that writes TypeScript regex = backslashes mangled at every layer.
Solution: `cat > file << 'PYEOF'` with single-quoted EOF preserves
backslashes verbatim. Or write Python with raw strings r"..." and avoid
double-escape gymnastics entirely. When the verifier says "True" but the
behavior is broken, suspect backslash mangling first.

**Anchor-mismatch when patching iteratively.** When a multi-step python
script swaps text in one file, the SECOND step's anchor is against the
post-step-1 text, not the original. If I copy the anchor from an old grep,
it won't match anymore. Solution: always grep current text BEFORE writing
the next python anchor. Don't write anchors blind.

**TS errors at verify time are blockers, not warnings.** Today I shipped
commit `48d0379` after the verifier reported "TS errors: error TS2339:
Property 'image_url' does not exist on type 'YoocalEvent'." I read past it
because I was tracking "did the patch land?" (True) and missed that the
build would fail. Vercel built it, failed, then succeeded on the next
commit that added the field. Real lapse — TS errors at verify time mean
STOP, fix the type, then commit. Always.

**Don't ship 150-line single-shot patches.** Earlier in the session I built
the "See all" overlay in one big patch (state + memo + JSX + click handlers
+ grouping + smart sort). Browser testing revealed five separate bugs at
once — couldn't isolate which piece was broken. Eventually found the
real bug (outside-click handler clearing search state on portal open) but
wasted 30+ minutes. Cross-city was built in 5 testable pieces, each
verified in browser before moving on. Took ~2 hours total but every piece
shipped clean. Pieces > shotgun.

**Trust deterministic over LLM (the pattern fired 3 times today).** LLM
enrichers populate occurrence_dates from text, but truncate. Today's fixes
all said "if we can compute it from structured fields, do that, override
the LLM": (a) weekly recurrence + end_date -> compute occurrence dates;
(b) recurrence_text with explicit date enumeration -> regex-extract dates;
(c) date_label with weekday + month range -> parse weekday + month bounds.
Each one moved from "LLM says 13 dates" to "code computes 17 dates" or
similar. When data is deterministic, don't trust the LLM.

**Outside-click handlers + portal-rendered overlays.** Portal renders
outside the dropdown's DOM tree, so an outside-click handler treats the
overlay click as outside-click and wipes search state. Took 30+ minutes
to find. Anytime I add a portal-rendered overlay over UI that has an
outside-click handler, the handler needs a guard: `if (overlayOpen) return`.

**File data realities outpace TypeScript type definitions.** YoocalEvent
and V2YocEvent interfaces were missing many runtime fields (image_url,
venue_name, _sourceCity, recurrence_text, occurrence_dates, ...). Each
new piece of work hits a fresh TS2339 because the type lags reality. Fixed
both interfaces in one pass each, but the underlying issue is real: when
the build script writes new fields, also update the TS interface as part
of the same change.

### Updated TODO (carried forward)
- [x] Schema image quality: earthdiver cdn-cgi width 500->1200 (342c12a).
      Source-capped: 93/107 distinct originals clear 720px; ~13 small ones
      (incl. 550px asset on ~189 events) stay sub-720, CF won't upscale.
      Scoped to earthdiver; image_url is schema-only (no card/pin use).
- [ ] Sanity audit of remaining 668 Heber events
- [ ] Mixed weekly+range patterns in HVT parser ("Weekly, Thu nights, Jun
      4 - Aug 20")
- [ ] VPC CI scrape flakiness (daily bot 13 vs local 100+)
- [ ] Grand Targhee scraper degradation (13 -> 1)
- [x] Jackson classifier bug (~387 stale loop var) — DONE d8e0e09; effect on next scrape
- [ ] Per-source event ID dedup overhaul — multi-day infrastructure; use
      stable source IDs as primary identity, similarity matching as
      separate explicit layer. Eliminates the "new dup pattern emerged"
      churn we keep hitting.
- [ ] Cross-source title-variance dedup beyond what venue-time catches
- [ ] Sun Valley + Ketchum rollout
- [x] API keys rotated (owner, Day 11)
- [~] Category quality: Festivals bucket dropped, CFA source-tag leak fixed,
      music-festival/photograph/disco rules added (Day 11). REMAINING: Community
      ~50-57% is UNDER-mapping (events with no bucket-worthy tag), a separate
      task from the over-matching now fixed.
- [ ] Health check threshold consolidation (sum related source labels)
- [ ] Verify 267 404s drop in Search Console over coming weeks
- GSC "Duplicate, Google chose different canonical" (2 URLs, crawled 26 May):
  BENIGN, no fix. Stale -s apostrophe slugs (billy-blanco-s, miner-s) from old
  slugify, still in Google's index. Current slugify DROPS the apostrophe
  (billy-blancos); sitemap + internal links + page canonical all emit the
  dropped form consistently (verified live + local sitemap.xml). Google
  correctly collapsed the 2 stale variants to the current slug. Scope = 2,
  flat, not trending -- ages out on re-crawl. Do NOT "fix" by re-adding -s:
  that inverts the problem and orphans ~27 live concert-series URLs. Briefly
  tried canonical-from-eventSlug() in [city]/[slug]/page.tsx -- reverted as a
  no-op (exact-match URLs already have slug === eventSlug).
- [ ] Re-trigger Search Console "validate fix" once enough crawl time

## Update 20: Day 11 — image fix, GSC ruled benign, category cleanup, Jackson var

### Shipped
- `342c12a` earthdiver schema image width 500->1200 (clear Google 720px bar).
  Source-capped; ~13 small originals stay sub-720 (CF won't upscale). LIVE.
- `1a3bef2` Category cleanup, verified 17/17 at the BUCKET layer:
  - Music rule: added "music festival" + "acoustic music" so named music
    festivals + concerts-at-festivals classify as Music (were Festival-only).
  - Theater rule: dropped bare \btheat(re|er)\b -- it matched the venue
    phrase "The Center Theater" in descriptions, mislabeling graduations/
    talks/concerts. Kept explicit signals (musical theatre, broadway,
    shakespeare, comedy show, cabaret, dreamcoat, auditions).
  - Festival rule: dropped bare \bcelebration\b (matched anniversaries/
    graduations/hockey).
  - category_normalizer: REMOVED the "Festivals" user-facing bucket. Festival
    events surface under real buckets (Music/Arts & Theater/Food); true multi-
    day festivals fall to Community (accepted). Kills the GTMF-concert noise.
- `d8e0e09` Jackson classifier var fix: main() classified the stale loop var
  "events" (last source only) and discarded it; payload built from unclassified
  "deduped". Now classifies "deduped" before payload, matching Heber/Elkhart
  (which were already correct -- they classify the save_events param).
  EFFECT APPEARS ON NEXT JACKSON SCRAPE; current raw is still buggy-run output.

### New tool (use it for all future category work)
- `classify_audit.py` -- reusable, read-only:
  - `python3 classify_audit.py [city]`      audit: per-bucket counts + sample titles
  - `python3 classify_audit.py trace <Cat> [city]`  shows which rule fired + on what text
  - `check()`        known-answer assertions at the CATEGORY layer
  - `check_buckets()` known-answer assertions at the BUCKET layer (what users see)
  - LESSON: assert at the BUCKET layer (filter_categories), not the category
    layer. categories -> buckets is lossy (Theater+Arts+Film -> "Arts & Theater";
    Festival -> nothing now). I initially asserted one layer too low and it hid
    the source-tag leak. Bucket layer is the one that matters.

### TOP banked TODO (the real next task -- root of today's residuals)
- [ ] Per-source category tag-trust. "Center for the Arts Jackson Hole" blanket-
      tags EVERY event it lists "Arts" (and others "Theater"/"Festival") at the
      SOURCE. classify_event honors source cats via LEGACY_MAP passthrough, so a
      graduation/Big Thief concert/birding festival all land in "Arts & Theater".
      Fix: don't honor a venue's blanket category tag -- require a text signal,
      or per-source trust rules. This is the 3rd face of the same venue leak
      (text-rule = fixed today; source-tag = still open). Affects all cities
      with over-tagging sources.

### Other findings (not bugs, verify later)
- Community still ~49-60% in PC/Heber/Jackson. UNCHANGED by today -- that's
  UNDER-mapping (events with no bucket-worthy tag -> default Community), a
  DIFFERENT problem than the over-matching we fixed. Don't conflate.
- Elkhart Community = 4.3% (vs ~55% elsewhere). Outlier -- verify it's genuine
  good categorization vs a quirk.
- [ ] VERIFY AFTER NEXT SCRAPE: run `classify_audit.py jackson` against the
      regenerated raw to confirm the var fix lands clean categories in prod.

## Update 21: CFA source-tag leak fixed (cbfce92)

- DONE (was Update 20's top banked TODO): Center for the Arts blanket-tags
  ~97% of events "Arts". Added SOURCE_BLANKET_IGNORE in event_classifier.py:
  per-source set of blanket tags (arts/community/theater) that get skipped so
  text rules decide; specific tags (Film, Met Opera) still pass. Extensible --
  add other over-tagging sources to the map.
- Paired text rules so masked events still classify: photograph(y/er)->Arts,
  silent disco + vinyl->Music.
- Verified 20/20 bucket assertions. Jackson Arts&Theater 230->139; other
  cities unchanged (CFA Jackson-only).
- ACCEPTED RESIDUALS: Little Feat (bare band name, no text signal -> Community);
  Fran Lebowitz (Chamber-sourced Theater tag, not CFA -> Arts&Theater). One-offs.
- NOTE: ignore-map is a pragmatic patch. Ideal long-term = text rules good
  enough to not lean on noisy source tags. Community still ~50-57% (under-
  mapping) untouched -- separate task.

## Update 22: VPC health alert = false alarm; found recurring-event gap

### Health alert resolved (shipped, ed99bce)
- VPC-sitemap "CRITICAL actual=20 floor=40" was a FALSE ALARM. ~80% of the 132
  scraped sitemap events dedupe into Park Record / VPC-API (by design); only
  ~20-46 survive as sitemap-labeled, varies daily. Floor 40 sat inside normal
  range. Lowered to 15. Also: requirements.txt was missing 'anthropic' ->
  LLM health check crashed in CI (ModuleNotFoundError). Added it. NO events
  were ever lost; this was monitoring miscalibration + a missing dep.

### Found while investigating: recurring-event under-representation (BANKED)
- Deer Creek Express (/event/deer-creek-express/27887/): runs 4x/week
  (Mon/Thu/Fri/Sat), Jan 19 - Oct 31 2026. We show it as ONE event on today's
  date, not the recurring series. Root cause: VPC's schema.org JSON-LD gives
  only flat startDate/endDate + @type EducationEvent; the recurrence
  ("Recurring weekly on Mon/Thu/Fri/Sat") is in PAGE PROSE only, not structured
  data. schema_org_scraper parses correctly (1 event, recurrence=None) -- it
  literally can't see the recurrence.
- The schema parser, dedup, and past-filter are all CORRECT (verified by
  tracing). startDate-past/endDate-future bump (lines 171-179) works. Not a bug
  in existing code -- a missing FEATURE: prose-recurrence expansion.
- SAME CLASS as existing TODO "mixed weekly+range HVT parser". Should be solved
  together: parse human recurrence text + date range -> expand to instances.
  Shared parser, affects all cities -- needs care + cross-city verification.
- NOTE: earlier confusion was partly a STALE local file -- public/raw/events.json
  was the May-28 snapshot during investigation. Always check updated_at first.

## Update 23: VisitJacksonHole source — DISCOVERY DONE, build banked

Goal: add visitjacksonhole.com/do/events as a Jackson source (suspected biggest
coverage gap — Chamber is healthy at 84/86 for a sample window, resorts are
small-by-nature, but VJH lists ~1100 /event/ links we don't capture).

CONFIRMED REACHABLE (Simpleview site, Algolia-backed search):
- Platform: Simpleview (CRM account "jacksonholewy"; assets on simpleviewinc.com)
- Events are NOT in the sitemap (sitemap index has only post/page/activity subs;
  no /event/ pages). They render client-side from Algolia. So the VPC sitemap
  approach does NOT work here.
- Algolia public creds (from inline <script> on /do/events, var site.ALGOLIA_*):
    APP id:     629LY06J3Z
    public key: 13ba5fb183974c4f50c8847d9815759b
    env:        prod
- Search endpoint works (POST .../1/indexes/{INDEX}/query returns 200 for a valid
  index; we get 404 for wrong names, 403 only on list-indexes = key is search-only).

MISSING PIECE (one 30-sec grab): the exact Algolia INDEX NAME. Guessed ~25
prod_/jacksonholewy_ patterns, all 404. Not in main.min.js as a literal (likely
built at runtime). GET IT FROM THE BROWSER: DevTools > Network > Fetch/XHR,
clear filter, RELOAD page (must record from load — it fires once on load), find
the request to *.algolia.net, copy index from URL path /1/indexes/<INDEX>/query.

BUILD PLAN (own focused session — substantial):
1. New scraper (e.g. visit_jackson_hole_scraper.py): query Algolia index with
   pagination (hitsPerPage + page/offset), filter to events (not activities/
   listings), map their schema -> our event dict (need to inspect fields first
   via one query once index known).
2. Handle dates + recurrence (VJH likely has same prose-recurrence issue as
   Deer Creek — see Update 22).
3. Wire into jackson_scraper.py alongside the other Jackson sources.
4. Dedup: EXPECT HEAVY overlap with Chamber (243) + CFA + Cloudveil. Net-new
   count likely far below 1100 (cf. VPC sitemap ~80% deduped). Real value =
   the net-new events; verify after integrating.
5. Add SOURCE_PRIORITY entry, scraper_health floor, baseline.
6. NOTE: VJH blanket-tags via Simpleview categories — watch for the same
   source-tag leak we fixed for CFA (Update 21). May need SOURCE_BLANKET_IGNORE.
- Park City's visitparkcity.com is ALSO Simpleview — a working VJH Algolia
  scraper could later improve PC coverage too.

### What lives where (quick reference for future-me)
- Backend universal fixes -> `build_master_and_views.py`
- Frontend universal fixes -> `src/components/CalendarClient.tsx`
  (mounted by every city page via CityLanding)
- Event detail pages + JSON-LD schema -> `src/app/[city]/[slug]/page.tsx`
- Per-event slug + cross-city redirect -> `src/lib/events.ts`
- City centers + radius config + SOURCE_PRIORITY -> top of
  `build_master_and_views.py`
