# yoocal — TODO

_Last updated: 2026-05-17 (Day 2 afternoon)_

---

## ✅ Shipped today (2026-05-17)

1. **Google Schema.org price format fix** — `offers.price` emits plain numeric ("25" not "$25", "0" for Free). Clears Search Console "Invalid price format" warning.
2. **Visit Park City window 120 → 200 days** — catches fall events VPC has but we were cutting off.
3. **Event submission form at /submit** — light theme, 10-option categories, AM/PM pickers, free/paid toggle, contact info, "interested in featured" checkbox.
4. **Business CTA repointed to /submit** — Basic listing card now says "Submit your event".
5. **Mobile nav shows Submit event** — outlined purple pill, both CTAs visible on small screens.
6. **yoocal.com verified in Resend** — DKIM/SPF/MX green via GoDaddy auto-config. Sends from `submit@yoocal.com` → `hello@yoocal.com`.
7. **RunSignup public API scraper** (`runsignup_scraper.py`) — PC +9 events with real times (Twisted Fork, Mid Mountain 50K, Jupiter Peak 25K, Trail Series, Park City Point 2 Point). Heber +5 net new (Mamele Mountains, DASH Sprint, The Freaky 5K). Filters out volunteers/pacers/virtual/team-variants/ticket-types.
8. **GitHub Actions timeout 30 → 60 min** — Park Record 150-day horizon needs more headroom on slow runners.
9. **Salt Lake Running Co scraper** (`slrc_scraper.py`) — 308 Utah events via Elfsight widget API, filtered to PC + Heber regions. Heber +3 net new (Jordanelle Triathlon, Deer Creek Half, Wasatch Half).
10. **Source-discovery script v1** (`discover_sources.py`) — 8 Google searches via SerpApi, calendar tech detection, scored ranking. Validated on PC (found DVMF, Park City Opera, Mountain Town Music). Jackson Hole cold-start surfaced Grand Teton Music Festival, thecloudveil.com, JHIFF.
11. **Deer Valley Music Festival scraper** (`deer_valley_music_festival_scraper.py`) — 13 concerts via Schema.org MusicEvent JSON-LD. Real start times (7:30 / 8:00 PM). Per-venue lat/lng (Snow Park Amphitheater vs St. Mary's). Lyle Lovett, Chris Botti, Idina Menzel, Chicago, Celine Dion, classical lineup.
12. **Universal Schema.org Event parser v1** (`schema_org_scraper.py`) — generic extractor for any URL with Event/MusicEvent/TheaterEvent/etc JSON-LD. Validated on DVMF (13 events). One-line scraper for any site that follows the standard.
13. **Universal Schema.org Event parser v2** (`schema_org_scraper_v2.py`) — list page → detail page traversal. Tested on Park City Opera /events with `/events/[a-z0-9-]+$` pattern → 9 real events including Opera Around the World free concert series, American Opera at Promontory Shed Amphitheater, American Music in Provo.

## ✅ Shipped yesterday (2026-05-16)

- Park Record horizon 30 → 150 days (the big one)
- Mountain Trails Foundation scraper
- Source priority restructured

---

## 📊 Current numbers

| | PC | Heber | Elkhart Lake | Total |
|---|---|---|---|---|
| Now | ~1348 | ~110 | 124 | ~1582 |
| 2 days ago | 438 | 70 | 124 | 632 |
| Gain | +910 | +40 | 0 | +950 (+150%) |

### Park City source breakdown
- Park Record: 1057
- KPCW Community Calendar: 152
- Deer Valley Resort: 56
- Visit Park City: 40
- Mountain Trails Foundation: 14
- Park City Institute: 14
- RunSignup: 9
- Salt Lake Running Co: 6
- Deer Valley Music Festival: 5
- Running in the USA: 4
- _(Pending wiring: Park City Opera +9 via v2 parser)_

### Heber outdoor coverage
- Was 6 events, now 9 (added Jordanelle Triathlon, Deer Creek Half, Wasatch Half from slrc)

---

## 🎯 Big vision

**"Search any town, get all events."** The generic toolkit is now real — discover_sources.py + schema_org_scraper_v2.py + per-platform scrapers (Elfsight, Calendarize-it, RunSignup, Showpass, Tockify) cover most modern event sites.

### Phases
- **Phase 1:** Deep coverage of PC + Heber + Elkhart Lake ✅ mostly done
- **Phase 2:** Source-discovery script ✅ v1 working
- **Phase 3:** Universal scraper ✅ Schema.org v1+v2 done; HTML/Squarespace next
- **Phase 4:** Multi-town launch — Jackson Hole is first test target
- **Phase 5:** Self-service — user types town, system bootstraps coverage

---

## 🔥 Next up

### IMMEDIATE (next session)
1. **Wire Park City Opera v2 into scraper.py** — 9 events ready. Use `schema_org_scraper_v2.scrape_schema_org_v2(url='https://www.parkcityopera.org/events', link_pattern=r'/events/[a-z0-9-]+$', source_name='Park City Opera', default_lat=40.6461, default_lng=-111.4980, default_city='Park City, UT', default_categories=['Music', 'Opera'])`. Add to source priority around position 3 (specialized venue).
2. **Verify 3 SLRC Heber events live on prod** — Jordanelle Triathlon, Deer Creek Half, Wasatch Half. Spot-check post-Vercel-deploy.
3. **v3 of universal parser** (from user request) — see "Medium" section, decide what improvements to prioritize.

### SHORT (this week)
4. **Mountain Town Music scraper** — discovery script found it, untested.
5. **Jackson Hole bootstrap** — wire GTMF + thecloudveil + JHIFF. First real "any town" launch.
6. **Sundance Mountain Resort, Wasatch State Park** — Heber outdoor gap still has room.
7. **Save-to-calendar app MVP** — `/feed/{token}.ics`. The differentiator.
8. **Open Graph share images** — `/api/og` per-event cards.
9. **Visit Park City "Ongoing" badge** for time-less events.

### MEDIUM
10. **Universal parser v3** — options: (a) JS rendering via Playwright fallback when no Schema.org found, (b) auto-detect link patterns (don't make user specify regex), (c) Squarespace-specific HTML parser since multiple PC sources use it, (d) follow pagination on list pages.
11. **Mobile UX pass** — date pill scrolling, map filter on touch.
12. **Email digest** — daily/weekly "this weekend in PC".
13. **Security audit** — CSP headers, rate-limit /api, secure cookies (needed before save-to-calendar adds accounts).
14. **Discovery script v2** — follow /events/ landing pages, JS via Playwright, better scoring.
15. **Fix Google Maps InvalidKey console warning**.

### LONGER-TERM
16. **LLM-assisted scraper generation** — paste URL, Claude generates parser. Phase 3 extension.
17. **Ad placement** — sponsored events $25-50/wk, venue page sponsorships.
18. **Self-service expansion**.

---

## 🧪 Sources to investigate

### Park City
- **Park City Opera** — `parkcityopera.org/events` — v2 found 9 events, NEEDS WIRING NOW
- **Mountain Town Music** — `mountaintownmusic.org`
- **Egyptian Theatre**
- **Kimball Art Center** — Squarespace
- **Sundance Institute** (film festival, annual but huge)
- **Park City Library**
- **Sundance Mountain Resort**
- **Park City Chamber of Commerce** — discovered, low score
- **Glenwild** — golf club, members-only events (probably skip)

### Heber outdoor (still thin)
- **slrc.com** ✅ +3 events
- **Soldier Hollow** — /events/ 404, may live elsewhere
- **Wasatch State Park**
- **Sundance Resort** (border-adjacent)
- **Wasatch County Library**
- **Wasatch High School athletics**
- **Local cycling clubs**

### Jackson Hole (cold-start target)
- **Grand Teton Music Festival** (`gtmf.org`) — WordPress tribe-events, try v2 with `/events/[^/]+$` pattern
- **thecloudveil.com** — local hotel curating events, WordPress tribe + Schema.org
- **Jackson Hole International Film Festival** (`jhiff.org`)
- **Jackson Hole Half Marathon** (`jhhalf.com`)

---

## 🛠 Generic toolkit

| File | Purpose |
|---|---|
| `discover_sources.py` | Auto-find candidates for any city via Google + tech detection |
| `schema_org_scraper.py` | Universal v1: Schema.org Event JSON-LD from single URL |
| `schema_org_scraper_v2.py` | Universal v2: list → detail page traversal |
| `runsignup_scraper.py` | RunSignup public API |
| `slrc_scraper.py` | Salt Lake Running Co (Elfsight) |

These compose. For new town: `discover_sources.py` → review candidates → Schema.org? use v2 parser → custom? write site-specific.

---

## 🐛 Bugs & polish

- Heber outdoor still thin (~9 events)
- Discovery script scoring imperfect — many real sources score 1-2
- Park Record exhibit "openings" deduplicate as separate events
- Title-keyword search needs word boundaries ("run" matches "Service")
- Google Maps InvalidKey console warning

---

## 🛠 Technical debt

- `scraper.py` 1500+ lines — split per source
- `CalendarClient.tsx:1231+` — old innerHTML pattern, refactor to React
- `scraper.py:263` — dead `scrape_kpcw()`. Delete.
- Vercel build is STRICT TypeScript — be careful

---

## 📚 Reference

### Repo
- patvanh/yoocal — auto-deploys to Vercel on push to main
- Daily scrape: `.github/workflows/scrape-daily.yml` at 10:00 UTC, 60-min timeout

### Mac dev
- `~/Desktop/yoocal`
- `.env` has SERPAPI_KEY, ANTHROPIC_API_KEY, RESEND_API_KEY
- Always `set -a; source .env; set +a` before scripts needing API keys
- `pending_sources.json` gitignored — regenerates per discovery run

### Domain / email
- yoocal.com verified in Resend (DKIM/SPF/MX green)
- Form: `submit@yoocal.com` → `hello@yoocal.com` (forwards to work)
- `submit@` outgoing label only; replies route via Reply-To

### Bot-protection notes
- runningintheusa.com → Cloudflare, Playwright+stealth not enough
- PCMR `/api/MountainApi/GetEvents` → 403 from Python
- soldierhollow.com → /events/ 404

### Patterns
- Per-source scraper: returns `list[dict]` matching standard schema
- Patch scripts (`patch_*.py`) one-time-use, delete after running
- Runtime artifacts gitignored
- Heredoc `<<'PYEOF'` reliable for inline Python
- macOS `strftime("%-I")` works (un-zero-padded hour)
- Squarespace → no Event JSON-LD by default (only WebSite/Organization/LocalBusiness)
- WordPress tribe-events → usually has Schema.org on detail pages, use v2
- Elfsight widgets → `core.service.elfsight.com/p/boot/` API, no auth
- Calendarize-it → `/?rhc_action=get_calendar_events` no auth
- Showpass → `/api/public/events/?venue={id}` no auth
- Tockify CORS-blocks browsers, Python requests works
- Resend free tier needs verified domain for sending to other addresses
- Vercel "Sensitive" env vars: Production + Preview only, not Development
- GitHub PATs need `workflow` scope to push `.github/workflows/` changes
- Rebase conflicts on events.json: `git checkout --ours public/events*.json; git add; git rebase --continue`
