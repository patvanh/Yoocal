# Production scraper cleanup notes (found 2026-06-13, daily-scraper failure investigation)

## 1. Daily run transient failure — RESOLVED (self-healed)
- Daily Action failed on data-quality GATE: C6 COVERAGE-CLIFF.
  Park Record was 69 -> 28 (>50% drop), Google Events 13 -> 0.
- Root cause: TRANSIENT. Live re-run of park_record_cityspark_scraper.py
  returned 1,111 healthy events. The bad run got partial API data; gate
  correctly blocked publish; live site stayed on good Jun-10 data (704 PR).
- Action: re-triggered daily workflow. No code fix needed.

## 2. park_record_cityspark_scraper.py — month loop not advancing (FRAGILE)
- The month-by-month loop logged: month=2026-06 +1111, then 2026-07..2027-01 all +0.
- Either one API call returns everything (month param ignored) or pagination
  isn't advancing months. Got the data this time, but the loop structure is
  misleading/fragile. Worth verifying the month iteration actually works, or
  simplifying to the single call that clearly returns the full set.

## 3. Far-town leakage in CitySpark feed (Park Record)
- CitySpark returns a wide region. Saw "Big Cottonwood Canyon Brew Fest" /
  "Brewfest" (Big Cottonwood = SLC side, NOT Park City) in the 1,111.
- Production pipeline filters down to ~704 live, so geo-filtering catches most,
  but worth confirming Big Cottonwood / SLC-area events are dropped.
- NOTE: the universal scraper's geo_validate._named_city_far (built today,
  with big cottonwood / little cottonwood already in _FAR_TOWN_RE) solves
  exactly this. Could share that filter with the production path.

## 4. ACCURACY: aggregators have wrong times; need primary-source verification
Found via "Remaining Native" (Park City Film, Jun 27): VPC lists 7:00 PM,
official parkcityfilm.org says 4pm. Your site shows VPC's wrong 7pm.

Diagnosis:
- parkcityfilm.org is NOT scraped directly. All 7 Park City Film events come
  via aggregators (Park Record 3, VPC 3, KPCW 1) — all second-hand.
- VPC's event page has a "VISIT WEBSITE" button linking to the real source,
  BUT that link is only in the rendered page, NOT in the events API record
  (API 'url' field = VPC's own internal path, e.g. /event/.../27842/).
- primary_source_enricher.py is BUILT for this (registry: domain -> trust=1
  primary; replaces weak fields like start_time). It just needs the official
  link to follow, which we don't currently capture.

STATUS (2026-06-13): Plan A DONE. parkcityfilm_scraper.py built + wired;
enricher REGISTRY has parkcityfilm.org trust=1. Remaining Native now resolves
to 4pm (see section 5). Plan B (follow VISIT WEBSITE links from aggregator
pages) NOT done — still open, see TO-DO #B1 below.

## 5. CONFLICT SURFACING — backend + card DONE, modal render REMAINING
Goal (Patrick's spec): when sources disagree on time/date/venue/price, surface
it rather than guessing. Direct source's link/time wins; show flag; if time
conflicts and NO direct source, hide time on card (show on click); when time
conflicts, show BOTH source links in modal.

DONE + TESTED:
- build_master_and_views.py merge_events: detects conflicts -> base["_conflicts"]
  = {field: [{value, source}...]}, base["_time_uncertain"] (True only if no
  Tier-1 source supplied time), base["_source_links"] (both links when time
  conflicts). "Park City Film" added to SOURCE_PRIORITY Tier 1.
  Verified: Remaining Native [VPC 7pm + PCF 4pm] -> start_time 4:00 PM,
  link=parkcityfilm.org, _time_uncertain False, _conflicts has both, 2 links.
- parkcityfilm_scraper.py built + wired (workflow line 69, build INPUT_FILES,
  enricher REGISTRY trust=1). Returns 13 events, Remaining Native @ 4pm.
- CalendarClient.tsx: V2YocEvent type has _conflicts/_time_uncertain/
  _source_links; React card hides time when _time_uncertain (line 542);
  both string-template cards emit data-conflicts/data-source-links/
  data-time-uncertain (URL-encoded JSON). tsc clean.

MODAL RENDER — DONE (2026-06-13):
- The INLINE string-template modal (CalendarClient ~2742, fires on grid-card
  click) now parses card.dataset.conflicts + card.dataset.sourceLinks
  (decodeURIComponent + JSON.parse, wrapped in try/catch) and renders:
  * amber conflict flag row per conflicting field ("<Field> varies by source:
    Park City Film: 4:00 PM • Visit Park City: 7:00 PM. Please confirm with
    the venue.") — class ye-conflict-flag
  * dual source-link row when _source_links has 2+ entries
- VERIFIED end-to-end via a full build_master_and_views.py run: Remaining
  Native -> start_time 4:00 PM, link=parkcityfilm.eventive.org,
  _time_uncertain False, _conflicts {time:[PCF 4pm, VPC 7pm]}, 2 source_links.
- NOT done: the React EventModal.tsx path (handleEventClick ~1451) was NOT
  updated — it doesn't render the flag. Only matters if that modal ever fires
  for grid cards; the inline one is what fires today. See TO-DO #F1.
- Shipped in commit a57fd34.


================================================================================
# OPEN TO-DO  (consolidated 2026-06-13 end of session)
================================================================================

## Verify / watch (low effort, do soon)
- [ ] V1. Watch the NEXT daily GitHub Action run. Confirm parkcityfilm_scraper.py
      runs clean in CI (it's continue-on-error:true, so a failure is silent —
      check it actually emits ~13 events, not 0). This is the first unattended
      run of the new scraper.
- [ ] V2. Confirm the Remaining Native 4pm correction is LIVE on the site after
      that run (the local build proved it; production updates on next cron +
      rebuild). Click the event, confirm 4pm + amber flag + both source links.

## Data accuracy / scraper correctness
- [x] D1. park_record_cityspark_scraper.py month-loop — RESOLVED 2026-06-15.
      NOT a bug: the first call (month=2026-06) returns ALL ~1118 future events;
      later months legitimately add 0 (already in set). The loop is a harmless
      future-proof safety net (kept). REAL issue was fragility: the whole scrape
      hinged on that one first call, so a transient timeout gave a partial scrape
      (24 events) and tripped C6. FIXED: fetch_page now retries 3x w/ 2/4/8s
      backoff (commit f9b00de). Healthy path unchanged (~1118).
- [x] D0. DAILY RUNS FAILING EVERY DAY — RESOLVED 2026-06-15. Root cause: C1
      (RECURRING-DROPPED) was in the gate's GATEABLE_CODES but is a heuristic
      guess, not a verifiable defect. It false-positived daily on window-edge
      events (single occurrence dated today/tomorrow) and title-split variants
      ('Midway Farmers Market' vs 'Saturday Midway Farmers Market' — 18 real
      occurrences seen as a drop). Removed C1 from GATEABLE_CODES (commit
      9d080d3); now gates only on C2/C5/C7. C1 still reported as HIGH in digest.
      NOTE: the data always SHIPPED fine — the gate runs after the commit/push,
      so it only reddened the run as an alarm; the site was never broken.
- [ ] D5. Google Events (SerpApi) C6 cliff: saw 16 -> 0 (and 13 -> 0 earlier).
      Same single-call fragility as Park Record but much smaller stakes (16 vs
      1118 events). No longer gates (C6 non-gateable) but periodically loses
      those events. Give it the same retry-with-backoff treatment as
      park_record fetch_page (commit f9b00de pattern).
- [ ] D2. Far-town leakage in CitySpark feed (section 3): confirm Big Cottonwood
      / SLC-area events are dropped in production. Consider sharing the universal
      scraper's geo_validate._named_city_far with the PRODUCTION path (today it
      only runs in the universal/staging path).
- [ ] D3. Mountain Town Music depth: universal scraper gets ~96-108 vs live 215.
      Investigate the gap.
- [ ] D4. Park Record cityspark API mapping in the UNIVERSAL scraper: returns
      records the mapper doesn't parse -> 0 mapped. Add a mapper for that shape.

## Universal scraper (still staging-only — STAGE_MODE="review")
- [ ] U1. Discovery venue-query expansion: QUERY_TEMPLATES in discover_sources.py
      is still the old ~8 generic queries. Add theater / performing-arts /
      gallery / museum / opera / library / radio venue-type queries so discovery
      finds Egyptian Theatre, KPCW, Park City Institute (it never found them).
      NOTE: this edit was written earlier in a prior session then LOST (never
      persisted). Needs to be redone from scratch.
- [ ] U2. THE big validation we've never done: run the universal scraper against
      a GENUINELY NEW city (zero ground truth, no hand-built scraper) to see if
      it can bootstrap a city. This is its actual purpose. All the hardening
      (API capture, recurrence, timeouts, guards, geo) is in place; it has only
      ever been tested on Park City where we already have tuned scrapers.
- [ ] U3. Universal scraper is NOT wired to production by design. Decide if/when
      it ever feeds live (currently writes review_queue/ only). For an
      already-covered city it's a downgrade (~777 vs 1,942); its value is NEW
      cities (U2).

## Conflict-surfacing follow-ups (feature shipped; these are extensions)
- [ ] F1. React EventModal.tsx does NOT render the conflict flag (only the inline
      modal does). Add it there too for safety in case that path ever fires:
      EventModalData type += conflicts?/sourceLinks?; handleEventClick (~1451)
      passes them; render flag + dual links in the component.
- [ ] B1. (Was section 4 Plan B — the powerful general fix) Capture the "VISIT
      WEBSITE" link from aggregator event PAGES (VPC's is JS-rendered, only in
      the page not the API record) and feed it to primary_source_enricher so
      ANY aggregator event can be verified against its true source — not just
      venues we hand-add as scrapers. Expensive (render per event); evaluate
      cost vs. just adding more direct venue scrapers.

## Suggestions raised today (not yet scoped into tasks)
- [ ] S1. News-article event extraction: the Offset Biergarten existed only in a
      TownLift ARTICLE, not in any calendar feed, so no scraper caught it (had to
      add it by hand to pc_recurring_locals.py). A "phase 2" LLM pass over local
      news for events-not-in-calendars would catch these. Real but messy —
      deferred.
- [ ] S2. As more direct venue scrapers get added (like parkcityfilm), more
      aggregator/venue time conflicts will surface automatically via the new
      conflict system — good, but watch that the flag doesn't get noisy. If many
      events show flags, consider tightening (e.g. only flag when the gap is
      material, or suppress when one source is a known-bad time).

## Monetization plumbing (deferred — summer is the window)
- [ ] M1. /go click-redirect route + affiliate link wrapping.
- [ ] M2. Stripe payment links (Featured $0.99/day, Partner $9.99/day).
- [ ] M3. Featured-placement sales flow.
- [ ] M4. Sponsor outreach + first newsletter.

## New venue scrapers discussed (candidates)
- [ ] N1. The Cabin, The Spur, Snake River Brewing (Jackson) — were on the radar.
