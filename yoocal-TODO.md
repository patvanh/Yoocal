# yoocal — TODO

_Last updated: 2026-05-16_

---

## ✅ Shipped today (2026-05-16)

- **Park Record horizon: 30 → 150 days** (biggest single win)
  - Was capped at 30 days creating a cliff (329 May events → 6 Sept)
  - Now scrapes 150 days with randomized order, jittered 1-3s delays, early-exit safety
  - Result: 375 → ~1100 Park Record events. Total PC: 656 → 1371 events.
- **Mountain Trails Foundation scraper** (parkcitytrails.org via Calendarize-it API)
  - +12 net new outdoor events including Tour des Suds, Jupiter Peak 25k, Mid Mountain 50k, 6 volunteer trail-building days
- **Source priority reordered:** specialized venue sources first
  - Deer Valley > Mountain Trails Foundation > PCI > Park Record > KPCW > Google > Running > VPC
  - Restored Deer Valley source attribution (2 → 56 events)
- **Calendar coverage now extends through October 2026**

## ✅ Shipped yesterday (2026-05-15)

- KPCW Community Calendar source (Tockify API): +155 PC, +22 Heber
- Deer Valley Resort source (embedded JSON): +55 PC, +6 Heber
- Park City Institute source (Showpass API): +9 PC net
- Improved dedup logic (loose key catches "Allen Stone" vs "Allen Stone with Special Guest…")
- Event card UI polish (end_time display, dropped "+" multi-day, white text)
- Google Events broken-date cleanup

---

## 📊 Current numbers

| | PC | Heber | Elkhart Lake | Total |
|---|---|---|---|---|
| **End of 2026-05-16** | 1371 | 101 | 124 | 1596 |
| Start of week | 438 | 70 | 124 | 632 |
| Gain | +933 | +31 | 0 | +964 |

### Outdoor events in Heber (only 6 real ones — coverage gap!)
- Whoop UCI Mountain Bike World Cup at Soldier Hollow (Sept 19)
- Heber Valley Main-to-Main 5K/10K, High Uinta Half Marathon, Runtastic Heber Half
- Swiss Days 10K Run, Utah Marathon

---

## 🎯 Big vision (long-term)

**"Search any town, get all events."** The platform should work for any small/mid town in the US — not just Park City and Heber. Goal: typing in a town name pulls up curated, current events automatically.

### Path forward (incremental, realistic)
- **Phase 1: Deep coverage** of PC + Heber + Elkhart Lake (where we are)
- **Phase 2: Weekly source-discovery script** — auto-finds new event aggregators per town, queues them for review
- **Phase 3: LLM-assisted scraper generation** — paste a URL, Claude generates a parser
- **Phase 4: Multi-town launch** — armed with discovery + auto-scrapers, expand to 5-10 towns
- **Phase 5: Self-service** — anyone can add their town, the system bootstraps coverage automatically

This is a 6-12 month build. Phase 2 is where we should start next.

---

## 🔥 Next up (priority order)

### 1. Weekly source-discovery script ⭐ NEW PRIORITY
Build a Python script that:
- Takes a city as input (`--city "park city utah"`)
- Runs 6-8 targeted Google searches via SerpApi
- Visits each result URL
- Detects calendar tech: FullCalendar, Tockify, Eventbrite embed, Showpass, WordPress events, ICS feeds, embedded JSON
- Scores each candidate
- Writes promising candidates to `pending_sources.json` for review
- Runs manually + on a weekly cron

### 2. Save-to-favorite-calendar app
The differentiating feature. Users save events; system pushes them to Apple/Google/Outlook via per-user ICS feed. Real-time updates when saved events change.

Smallest meaningful slice:
- Anonymous "save events" → personal token URL → ICS feed at `/feed/{token}.ics`
- No auth, no DB needed initially
- Users add URL as a calendar subscription
- Phase 2 adds change detection + notifications

### 3. RunSignup expansion to Park City
- We use RunSignup for Heber; add a parallel call for PC
- Would catch Twisted Fork, Triple Trail events, others auto-updating

### 4. Heber outdoor coverage gap (only 6 events!)
Sources to investigate:
- **slrc.com/event-calendar/** ⭐ user-suggested (Salt Lake Running Co — runs PC Trail Series, likely covers Heber races too)
- **Soldier Hollow** events (UCI MTB, Nordic, biathlon training)
- **Wasatch State Park** events
- **Sundance Resort** (border-adjacent)
- **Heber Valley Half Marathon** (different from Runtastic Heber Half)
- Local cycling clubs
- Wasatch County Library, Wasatch High School athletics
- Charleston / Daniel / Midway specific events

### 5. Mobile UX improvements
- Test all event card / modal interactions on mobile
- Date pill scrolling on small screens
- Map filter behavior on touch
- "Use my location" prompt UX
- Bottom-sheet modal style for events?

### 6. Email digest via Groupmail
- https://forms.groupmail.info/subscribe/yoocal
- Daily or weekly "what's happening this weekend"
- Could share auth/saved-events with calendar-sync feature

### 7. Open Graph / social share images
- /api/og endpoint for per-event share cards
- Used when sharing event URLs on iMessage / Twitter / FB
- Currently shows generic yoocal preview

### 8. Visit Park City "Ongoing" badge for time-less events
- ~50 VPC events have no start_time (ongoing classes, exhibits)
- Show "Ongoing" or "Today" label instead of nothing

### 9. Web security audit
- Content-Security-Policy headers
- User input properly escaped
- HTTPS-only, secure cookies when adding auth
- Rate-limiting on /api endpoints (critical before calendar-sync feature)

### 10. PCMR scraper (low priority — 403'd)
- API found at `/api/MountainApi/GetEvents` but returns 403 from Python
- Could try with Chrome extension browser tools (signed-in session)
- Only 3 events, already covered by Park Record

---

## 🧪 Sources to investigate

### Park City
- **Egyptian Theatre** — own events page may have calendar feed
- **Kimball Art Center** — Squarespace, look for embedded JSON or RSS
- **Sundance Institute (film festival)**
- **Park City Library**
- **Sundance Mountain Resort** events
- **Showpass for other venues** — same scraper pattern, different venue ID

### Multi-city / outdoor (long-term)
- **slrc.com/event-calendar/** — Salt Lake Running Co, broad Utah coverage
- **runguides.com** — has event detail pages but state listing is small
- **letsdothis.com**, **findarace.com**, **ultrasignup.com**
- **trailforks.com** — mountain bike events
- **mtbproject.com**, **Strava events**

---

## 🐛 Bugs & polish

- Heber outdoor coverage thin (6 events vs PC's ~30+)
- Several Park Record exhibit "openings" deduplicate as separate events
- Title-keyword matching needs word boundaries ("run" matches "Service")

---

## 🛠 Technical debt

- `scraper.py:263` — dead `scrape_kpcw()` function. Delete it.
- `CalendarClient.tsx:1231+` — old `innerHTML + openEventModal` pattern. Refactor to React + EventModal.
- `scraper.py` is 1400+ lines — split into per-source modules
- Vercel build is STRICT TypeScript

---

## 📚 Reference info

### Repo
- patvanh/yoocal (public on GitHub)
- Auto-deploy to Vercel on push to main
- Daily scrape via GitHub Actions at 10:00 UTC

### Per-source scraper files
- `scraper.py` — main orchestrator + VPC + Park Record + Eventbrite + Running + Google
- `kpcw_scraper.py` — Tockify API
- `deer_valley_scraper.py` — embedded JSON in HTML
- `park_city_institute_scraper.py` — Showpass API
- `park_city_trails_scraper.py` — Mountain Trails Foundation Calendarize-it API
- `heber_scraper.py` — Playwright + RunSignup + Google

### Bot-protection notes
- runningintheusa.com → Cloudflare challenge, Playwright+stealth fails
- PCMR's `/api/MountainApi/GetEvents` → 403 from Python (needs browser session)
- All current sources are open and well-behaved

### Patterns established
- Scraper modules return `list[dict]` matching standard schema
- Patch scripts (`patch_*.py`) are one-time-use, delete after running
- Runtime artifacts go in .gitignore
- Heredoc `<<'PYEOF'` is reliable
- macOS strftime `%-I` works
- Squarespace + WordPress sites usually expose backend JSON APIs
- HTML-entity encoded JSON in `<var class="results">` = Sitecore pattern
- Tockify CORS-blocks browsers, Python `requests` works
- Showpass: `/api/public/events/?venue={id}` — no auth
- Calendarize-it: `/?rhc_action=get_calendar_events` — no auth
