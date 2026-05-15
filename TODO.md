# Yoocal — TODO list

Saved: May 15, 2026
Context: end of marathon dev session. Three cities live with clean data,
automated daily scraping, no cross-city contamination.

## Current production state

| | Park City | Heber Valley | Elkhart Lake |
|---|---|---|---|
| Live events | 435 | 173 | 124 |
| Daily auto-refresh | yes (4 AM Mountain) | yes | yes |
| Cross-city contamination | none | none | none |
| Time coverage | 75% | 57% | not measured |
| Venue coverage | 91% | 63% | not measured |

---

## HIGH VALUE, MANAGEABLE EFFORT

### 1. Mobile UX polish (~1–2 hours)
Original kickoff priority. Site works on mobile but isn't optimized. Likely
targets: event card readability, day-pill scroll on small screens, modal
sizing, hero section on portrait phones.

### 2. Email digest — "This Weekend" Thursday email (~2–3 hours)
Original kickoff priority. Groupmail signup form already exists at
https://forms.groupmail.info/subscribe/yoocal. Work: write a script that
generates the email body from each city's weekend events and pushes to
Groupmail's API on Thursdays. Could run from the same GitHub Actions cron.

### 3. Open Graph / social share images (~1 hour)
When someone shares a yoocal event link on iMessage/Slack/Twitter, what
shows up? Right now probably nothing or generic. Adding og:image plus
dynamic image generation for event pages makes shares look professional.

### 4. SEO improvements (~1 hour)
We did Schema.org Event JSON-LD today. Still missing: per-event Open Graph
tags, sitemap.xml, robots.txt review, page titles per event, meta
descriptions.

---

## MEDIUM VALUE

### 5. Charleston / Daniel coverage gap (~30 min)
Heber Valley has 0 events from Charleston and Daniel. They're small towns
but listed in the About page as part of the valley. Worth checking if there
are local Facebook pages or community boards we can scrape.

### 6. Visit Park City: show "Ongoing" instead of blank for time-less events (~30 min)
We decided NOT to do this today, but it's still a real UI improvement for
50+ events. When an event has no start_time and the description says
"ongoing", "daily", "open daily", or similar — show "Ongoing" in the time
slot instead of nothing. Better signal than blank.

### 7. Add more cities (~varies)
Aspen and Jackson Hole show as "coming soon" placeholders. Each new city
= scraper + about page + small CITIES config addition. Pattern is now
well-established from Heber.

### 8. Park City data quality, round 2 (~1 hour)
Today we fixed Google Events broken dates. Visit Park City times are
mostly source-limited. But we haven't really looked at the Park Record
scraper (373 events from there). Worth checking time/venue coverage on
that source specifically.

---

## LOWER VALUE OR RISKY

### 9. Unify modals (~1.5 hours, risky)
Homepage CalendarClient.tsx still uses an old innerHTML + global window
function pattern for modals. Newer pages use React EventModal. Refactoring
would touch ~6 places in the homepage. Risk of regression > current pain.

### 10. Web security audit (~1 hour)
Already rotated SerpApi key and moved keys to env vars today. Bigger
review would check: gitignore patterns, XSS in user-generated content
(there isn't any yet so low-risk), input sanitization, dependency vulns.

### 11. Performance audit (~1 hour)
Site is fast but: hero image is full-resolution Park City photo (could
be optimized), each city loads ALL events on page load (could paginate
at 50+), no service worker for offline.

### 12. Analytics / observability (~30 min)
No way today to know if users are clicking events, which days are popular,
which cities get traffic. Could add Plausible or Umami (privacy-friendly,
free).

---

## CLAUDE-AS-AGENT IDEAS (discussed end of May 15 session)

### Approach C (recommended for finding more events):
Use Claude in a one-time discovery session to map every event source per
city — newspapers, chambers, Facebook pages, venue calendars, ticketing
platforms — then build targeted scrapers for the good ones. Sustainable,
free to run daily on existing GitHub Actions cron.

### Morning monitoring agent (good first agent project):
Small Claude API call once a day that emails: "Today's scrape ran. Found
N new events for PC, M for Heber, K for Elkhart. Time/venue coverage:
PC 76%, Heber 58%. Top 5 worth highlighting: ..."  Reliable, low-cost
(~$0.10/day), gives you a daily briefing feel.

### Avoid: Claude as daily scraper
Asking Claude to find events daily via web search + API is unreliable
(hallucinations), expensive (~$1,095/year for 3 cities), and loses source
attribution (users can't click through to original listings).

---

## RECOMMENDED NEXT MOVE

If only ONE more thing gets built: the Thursday email digest (#2).
You've been building this for engagement and the email loop is what
brings people back. Everything else is incremental polish. The email
is the growth lever.

---

## ALREADY SHIPPED ON MAY 15 (for reference)

1. /venues page (curated venues, filter chips, modal)
2. Heber Valley as third full city (About, This Weekend, Venues, event pages)
3. SerpApi key rotation (leaked key disabled, new key in GitHub Secrets)
4. API keys moved from hardcoded to env vars + GitHub Secrets
5. Daily scrape automation (GitHub Actions, 4 AM Mountain)
6. Heber scraper rewrite (Playwright-based gohebervalley.com — 107 events from 0)
7. Expanded Heber contamination filter (9 more far-Utah town keywords)
8. PC scraper now re-routes Heber Valley events at scrape time
9. Step 2: PC homepage shows only PC events; Heber appears past 20mi radius
10. Day-pill counters and hero stat respect the supplemental filter
11. Heber wired into homepage as third browseable city
12. Google Events scraper drops unparseable/past dates (29 broken events removed)
