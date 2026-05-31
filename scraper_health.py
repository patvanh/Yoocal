"""Scraper health check. Runs after every scrape across all 4 cities.

For each event source, compares today's event count to:
  1. The 7-day rolling average (auto-updates)
  2. A hardcoded sanity range (catastrophic failure detection)

Output:
  - scraper_health.json (read by audit_email_digest.py)
  - Sends URGENT email if any source is severely degraded
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
import requests


MOUNTAIN = timezone(timedelta(hours=-6))

CITY_FILES = {
    "park-city": "public/raw/events.json",
    "elkhart-lake": "public/raw/events-elkhartlake.json",
    "heber": "public/raw/events-heber.json",
    "jackson": "public/raw/events-jackson.json",
}

BASELINES_FILE = "scraper_baselines.json"
HEALTH_OUTPUT = "scraper_health.json"
HISTORY_DAYS = 7

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
ALERT_TO = os.environ.get("YOOCAL_DIGEST_TO", "patrick@vanhornpc.com")
ALERT_FROM = "yoocal alerts <quality@yoocal.com>"

# Per-(city, source) floors: alert if a known major source falls below this.
# Format: (city, source) -> minimum expected count.
# Only set floors for sources where we KNOW the city normally has lots of data.
HEALTH_FLOORS = {
    ("park-city", "The Park Record"): 300,
    ("park-city", "Park City Annual Events"): 200,
    ("park-city", "Mountain Town Music"): 50,
    ("park-city", "Deer Valley Resort"): 20,
    ("park-city", "Visit Park City"): 15,  # Most VPC events get deduped to higher-priority sources
    ("park-city", "Visit Park City (sitemap)"): 15,  # ~80% of sitemap events dedupe into Park Record/VPC-API; only ~36 survive as sitemap-labeled. Week ranged 20-46. Floor below normal range w/ margin.
    ("park-city", "Park City Farmers Market"): 10,
    ("park-city", "Park City Institute"): 5,
    ("heber", "Heber Valley Tourism"): 30,
    ("heber", "Heber Valley Life"): 10,
    # KPCW is a Park City station; its Heber subset is naturally tiny (a
    # handful of events). No floor here — low Heber KPCW counts are normal,
    # not a scraper failure.
    ("jackson", "Jackson Hole Chamber of Commerce"): 100,
    ("jackson", "Center for the Arts Jackson Hole"): 30,
    ("jackson", "The Cloudveil"): 20,
    ("jackson", "Grand Teton Music Festival"): 30,
    ("elkhart-lake", "Elkhart Lake Tourism"): 50,
}


def _load_baselines() -> dict:
    try:
        return json.load(open(BASELINES_FILE))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"history": {}, "version": 1}


def _save_baselines(data: dict):
    json.dump(data, open(BASELINES_FILE, "w"), indent=2)


def _count_by_source(events: list) -> dict:
    return dict(Counter(e.get("source", "unknown") for e in events))


def _classify_health(actual: int, baseline, floor) -> tuple:
    if floor is not None and actual < floor:
        return "CRITICAL", f"actual={actual}, floor={floor} (below catastrophic threshold)"

    if baseline is None or baseline == 0:
        return "OK", f"actual={actual} (no baseline yet)"

    ratio = actual / baseline
    if actual == 0 and baseline >= 10:
        return "CRITICAL", f"actual=0, baseline={baseline:.0f} (returned NOTHING)"
    if ratio < 0.3:
        return "SEVERE", f"actual={actual}, baseline={baseline:.0f} ({ratio*100:.0f}% of normal)"
    if ratio < 0.7:
        return "DEGRADED", f"actual={actual}, baseline={baseline:.0f} ({ratio*100:.0f}% of normal)"
    if ratio > 1.5:
        return "ELEVATED", f"actual={actual}, baseline={baseline:.0f} ({ratio*100:.0f}% of normal)"
    return "OK", f"actual={actual}, baseline={baseline:.0f}"


def run_health_check() -> dict:
    today_iso = datetime.now(MOUNTAIN).strftime("%Y-%m-%d")
    baselines = _load_baselines()
    history = baselines.setdefault("history", {})

    today_counts = {}
    for city, path in CITY_FILES.items():
        try:
            d = json.load(open(path))
            events = d.get("events", d) if isinstance(d, dict) else d
            today_counts[city] = _count_by_source(events)
        except FileNotFoundError:
            today_counts[city] = {}

    cutoff_date = (datetime.now(MOUNTAIN) - timedelta(days=HISTORY_DAYS + 1)).strftime("%Y-%m-%d")
    for city, source_counts in today_counts.items():
        city_hist = history.setdefault(city, {})
        for source, count in source_counts.items():
            entries = city_hist.setdefault(source, [])
            entries = [e for e in entries if e["date"] != today_iso and e["date"] > cutoff_date]
            entries.append({"date": today_iso, "count": count})
            city_hist[source] = entries

    report = {"checked_at": datetime.now(MOUNTAIN).isoformat(), "today": today_iso, "cities": {}}
    critical_alerts = []

    for city, source_counts in today_counts.items():
        city_report = []
        city_hist = history.get(city, {})
        for source, actual in sorted(source_counts.items(), key=lambda x: -x[1]):
            prior_entries = [e for e in city_hist.get(source, []) if e["date"] != today_iso]
            baseline = mean([e["count"] for e in prior_entries]) if prior_entries else None
            floor = HEALTH_FLOORS.get((city, source))
            severity, msg = _classify_health(actual, baseline, floor)

            city_report.append({
                "source": source,
                "actual": actual,
                "baseline": round(baseline, 1) if baseline else None,
                "floor": floor,
                "severity": severity,
                "message": msg,
            })

            if severity in ("CRITICAL", "SEVERE"):
                critical_alerts.append({
                    "city": city, "source": source,
                    "severity": severity, "message": msg,
                })

        report["cities"][city] = city_report

    report["critical_alerts"] = critical_alerts

    _save_baselines(baselines)
    json.dump(report, open(HEALTH_OUTPUT, "w"), indent=2)

    return report


def send_urgent_alert(report: dict) -> bool:
    # DISABLED: this urgent-alert email is now redundant. The resilience guard
    # (scrape_resilience.py) auto-retains last-good data when a source drops, so
    # a throttled scrape no longer means missing events for users; and the daily
    # digest (audit_email_digest.py) reports any anomalies in plain language.
    # Keeping the health CHECK (it writes baselines) but not the scary email.
    print("Health alert email disabled (resilience guard + digest cover this).")
    return False

    alerts = report.get("critical_alerts", [])
    if not alerts:
        return False
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set — can't send urgent alert")
        return False

    rows = []
    for a in alerts:
        bg = "#fef2f2" if a["severity"] == "CRITICAL" else "#fffbeb"
        color = "#dc2626" if a["severity"] == "CRITICAL" else "#d97706"
        rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:8px 12px;font-weight:600;color:{color}'>{a['severity']}</td>"
            f"<td style='padding:8px 12px'>{a['city']}</td>"
            f"<td style='padding:8px 12px;font-weight:500'>{a['source']}</td>"
            f"<td style='padding:8px 12px;font-size:13px;color:#666'>{a['message']}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;color:#1f2937;max-width:680px;margin:0 auto;padding:24px">
  <h1 style="font-size:22px;color:#dc2626;margin:0 0 4px">⚠️ Scraper Health Alert</h1>
  <div style="color:#6b7280;font-size:14px;margin-bottom:24px">{report['today']} · {len(alerts)} source(s) degraded</div>
  <p style="font-size:14px;color:#374151;margin-bottom:16px">
    One or more scrapers returned fewer results than expected. Investigate before users notice missing events.
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;border:1px solid #e5e7eb">
    <thead><tr style="background:#f3f4f6">
      <th style="padding:8px 12px;text-align:left">Severity</th><th style="padding:8px 12px;text-align:left">City</th>
      <th style="padding:8px 12px;text-align:left">Source</th><th style="padding:8px 12px;text-align:left">Detail</th>
    </tr></thead><tbody>{''.join(rows)}</tbody></table>
  <div style="margin-top:24px;font-size:13px;color:#6b7280">
    <a href="https://github.com/patvanh/Yoocal/actions" style="color:#3b82f6">View latest workflow run</a>
  </div>
</body></html>"""

    try:
        r = requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": ALERT_FROM, "to": [ALERT_TO],
                  "subject": f"⚠️ [yoocal] URGENT — {len(alerts)} scraper(s) degraded", "html": html},
            timeout=20)
        if r.status_code == 200:
            print(f"OK: urgent alert sent to {ALERT_TO}")
            return True
        print(f"FAILED: {r.status_code} - {r.text[:200]}")
        return False
    except requests.RequestException as e:
        print(f"FAILED: {e}")
        return False


def main():
    report = run_health_check()
    print(f"Scraper Health Check — {report['today']}")
    print("=" * 60)
    for city, sources in report["cities"].items():
        crit = sum(1 for s in sources if s["severity"] in ("CRITICAL", "SEVERE"))
        warn = sum(1 for s in sources if s["severity"] == "DEGRADED")
        print(f"\n{city}: {len(sources)} sources, {crit} severe, {warn} warnings")
        for s in sources[:10]:
            badge = {"CRITICAL": "[!]", "SEVERE": "[!]", "DEGRADED": "[~]",
                     "ELEVATED": "[^]", "OK": "[ ]"}.get(s["severity"], "[?]")
            print(f"  {badge} {s['source'][:35]:35s} {s['message']}")

    print(f"\nHealth report: {HEALTH_OUTPUT}")
    print(f"Baselines: {BASELINES_FILE}")

    if report["critical_alerts"]:
        print(f"\nWARNING: {len(report['critical_alerts'])} CRITICAL/SEVERE alerts — sending email")
        send_urgent_alert(report)


if __name__ == "__main__":
    main()
