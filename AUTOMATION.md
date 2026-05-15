# Yoocal — daily scrape automation

## What this is

A GitHub Actions workflow that runs all three scrapers (Park City, Heber Valley,
Elkhart Lake) every day at 4 AM Mountain Time. It commits the updated JSON
files to `main`, which automatically triggers a Vercel deploy. So your site
stays fresh without you doing anything.

## Files

```
.github/workflows/scrape-daily.yml  ← the scheduler
requirements.txt                    ← Python deps the scrapers need
```

## How it works

1. **4 AM Mountain Time daily.** GitHub Actions wakes up.
2. **Runs each scraper independently.** If Park City breaks, Heber + Elkhart Lake still run.
3. **Builds a summary report** in the GitHub Actions log (top of "Daily scrape" job)
   showing which cities succeeded/failed and how many events are in each JSON.
4. **Commits the new JSON.** Author shows as `yoocal-bot`.
5. **Vercel auto-deploys** because of the new commit.

## How to know if it ran

- Go to https://github.com/patvanh/yoocal/actions
- "Daily event scrape" runs are listed at the top
- Green check = all 3 scrapers worked
- Yellow exclamation = at least one scraper failed (workflow still succeeded)
- Red X = all three failed OR something broke before scrapers ran

## How to run it manually right now

Two ways:

1. **From GitHub UI:**
   - https://github.com/patvanh/yoocal/actions
   - Click "Daily event scrape" on the left
   - Click "Run workflow" → "Run workflow" (green button on the right)

2. **From your Mac:**
   ```bash
   cd ~/Desktop/yoocal
   python scraper.py && python heber_scraper.py && python elkhart_scraper.py
   git add public/events*.json
   git commit -m "manual scrape"
   git push
   ```

## How to change the schedule

Edit `.github/workflows/scrape-daily.yml`, find the line:

```yaml
- cron: "0 10 * * *"
```

That's `minute hour day month day-of-week` in UTC. Some examples:

| Cron string | Means |
| --- | --- |
| `"0 10 * * *"` | 10:00 UTC daily = 4 AM Mountain (DST) or 3 AM (standard) |
| `"0 12 * * *"` | 12:00 UTC daily = 6 AM Mountain (DST) |
| `"0 10,18 * * *"` | 10 AM UTC AND 6 PM UTC daily |
| `"0 * * * *"` | Every hour on the hour |
| `"0 10 * * 1-5"` | 10:00 UTC weekdays only |

Tools like crontab.guru help visualize cron strings.

## Known limitations (and how we'll address them)

1. **Heber events often lack `start_time`** → shows "All day" on the site.
   Will fix when we rebuild scrapers (next priority).

2. **Heber events have generic `location: "Heber Valley, UT"`** instead of
   specific venues → 98% of events don't match a curated venue. Same fix.

3. **No failure notifications.** Right now you have to check the Actions
   tab manually. We can add email / Slack / Discord notifications later
   (GitHub natively supports email-on-failure for the repo owner).

4. **Timezone DST quirk.** Cron jobs run in UTC, so during DST the run is
   at 4 AM Mountain; during standard time it shifts to 3 AM Mountain.
   For a daily content site, this is fine.
