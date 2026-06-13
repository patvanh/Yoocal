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

NEXT-SESSION PLAN (well-scoped):
  A. Add parkcityfilm.org as a direct source (clean showtimes page, states
     times plainly: "Saturday, June 27th at 4pm"). Either a small dedicated
     scraper like other venue scrapers, or add to universal scraper sources.
     Then add parkcityfilm.org to enricher REGISTRY as trust=1 so its 4pm
     overwrites VPC's 7pm on dedup/enrich.
  B. (Bigger, general) Capture the "VISIT WEBSITE" link from VPC event pages
     and feed it to the enricher so ANY aggregator event can be verified
     against its primary source. Expensive (render per event) — evaluate.

IMMEDIATE: optional event_overrides.py entry to force Remaining Native -> 4pm.

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

REMAINING (next session — modal render only):
- TWO modal systems exist:
  (a) React EventModal.tsx — fed by handleEventClick (CalendarClient ~1451)
  (b) inline string-template modal built around CalendarClient ~2714
      (meta.push HTML, reads card.dataset.*)
  Determine which fires on card click (likely the inline one for grid cards),
  render in the correct one(s):
  1. EventModalData type: add conflicts?, sourceLinks? (EventModal.tsx ~18)
  2. handleEventClick (~1451): pass ev._conflicts -> conflicts, ev._source_links
  3. inline modal (~2714): parse card.dataset.conflicts (decodeURIComponent +
     JSON.parse), render flag block after the time row
  4. Render: conflict flag = disclaimer showing each value+source
     ("Park City Film: 4:00 PM • Visit Park City: 7:00 PM — confirm with venue")
     + dual source links when sourceLinks present.
- Test in browser on Remaining Native (Jun 27): should show 4pm (not hidden,
  PCF is direct), a flag noting VPC says 7pm, and both links.
