"""yoocal quality digest — daily health email.

Rewritten to be owner-friendly: leads with a plain-English health verdict,
shows per-city event counts with normal/abnormal flags, a 5-day per-city
trend, source-level anomalies (sharp jumps/drops), and only then the items
that need manual attention. Reads daily history from scraper_baselines.json.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests

REPO_URL = os.environ.get("REPO_URL", "https://github.com/patvanh/Yoocal")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
DIGEST_FROM = os.environ.get("DIGEST_FROM", "yoocal <quality@yoocal.com>")
DIGEST_TO = os.environ.get("DIGEST_TO", "patrick@vanhornpc.com")
MAX_ISSUES_PER_CITY = 10
ANOMALY_PCT = 0.50  # flag a source if today is >50% above/below recent average

CITY_LABEL = {
    "park-city": "Park City", "parkcity": "Park City",
    "heber": "Heber Valley", "elkhart-lake": "Elkhart Lake",
    "elkhartlake": "Elkhart Lake", "jackson": "Jackson Hole",
}


def _load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _sev_count(by_severity, level):
    return by_severity.get(level, by_severity.get(str(level), 0))


# ── history helpers (read scraper_baselines.json['history']) ──────────

def _city_daily_totals(history):
    """{city: {date: total_events_that_day}} summing all sources."""
    out = {}
    for city, sources in (history or {}).items():
        per_date = defaultdict(int)
        for _src, entries in sources.items():
            for e in entries:
                d = e.get("date")
                if d:
                    per_date[d] += int(e.get("count", 0))
        out[city] = dict(per_date)
    return out


def _recent_dates(city_totals, n=5):
    """The most recent n dates that appear across any city."""
    all_dates = set()
    for per_date in city_totals.values():
        all_dates.update(per_date.keys())
    return sorted(all_dates)[-n:]


def _source_anomalies(history):
    """For each source, compare its latest count to the average of prior
    days. Flag if the latest deviates more than ANOMALY_PCT. Returns list of
    dicts sorted by biggest swing first."""
    flagged = []
    for city, sources in (history or {}).items():
        for src, entries in sources.items():
            pts = [e for e in entries if e.get("date")]
            if len(pts) < 3:  # need some history to judge "normal"
                continue
            pts = sorted(pts, key=lambda e: e["date"])
            latest = pts[-1]
            # Average over recent prior days only (last 7), not all history —
            # early sparse days (a source logging a handful before the full set
            # came online) would otherwise drag the average down and fake a
            # huge "jump".
            prior = pts[:-1][-7:]
            avg = sum(p.get("count", 0) for p in prior) / max(1, len(prior))
            cur = latest.get("count", 0)
            if avg <= 0:
                continue
            change = (cur - avg) / avg
            if abs(change) >= ANOMALY_PCT:
                # Distinguish a PERSISTENT decline (real break — the count has
                # been at/below this low for multiple consecutive days) from a
                # SINGLE-DAY dip (one off scrape, or dedup variation — usually
                # self-corrects and is not alarming). Only drops get this tag.
                persistent = False
                if change < 0 and len(pts) >= 3:
                    last3 = [p.get("count", 0) for p in pts[-3:]]
                    # all of the last 3 days are well below the prior average
                    persistent = all(c < avg * (1 - ANOMALY_PCT) for c in last3)
                flagged.append({
                    "city": city, "source": src,
                    "current": cur, "avg": round(avg, 1),
                    "change": change, "date": latest.get("date"),
                    "persistent": persistent,
                })
    flagged.sort(key=lambda f: abs(f["change"]), reverse=True)
    return flagged


def render_html(audit, repair, llm_health=None, baselines=None, guard_state=None):
    audit_date = audit.get("audit_date", "today")
    reports = audit.get("reports", [])
    history = (baselines or {}).get("history") or {}

    city_totals = _city_daily_totals(history)
    dates = _recent_dates(city_totals, 5)
    anomalies = _source_anomalies(history)
    total_sev1 = sum(_sev_count(r.get("by_severity") or {}, 1) for r in reports)
    total_events = sum(r.get("total_events", 0) for r in reports)

    # ── 1. plain-English verdict ──────────────────────────
    problems = []
    if anomalies:
        problems.append(f"{len(anomalies)} source(s) with unusual counts")
    if total_sev1:
        problems.append(f"{total_sev1} event(s) needing manual review")
    llm_flagged = (llm_health or {}).get("flagged") or []
    if llm_flagged:
        problems.append(f"{len(llm_flagged)} source(s) flagged by health check")

    if problems:
        verdict_color, verdict_bg = "#92400e", "#fffbeb"
        verdict_icon = "&#9888;"
        verdict_text = "A few things to look at: " + "; ".join(problems) + "."
    else:
        verdict_color, verdict_bg = "#065f46", "#ecfdf5"
        verdict_icon = "&#10003;"
        verdict_text = "Everything looks normal across all cities today."

    verdict_html = (
        f'<div style="background:{verdict_bg};color:{verdict_color};padding:16px 18px;'
        f'border-radius:10px;margin-bottom:28px;font-size:16px;font-weight:500">'
        f'{verdict_icon} {verdict_text}</div>'
    )

    # ── 2. per-city totals today, with normal/abnormal flag ───
    city_rows = []
    for r in reports:
        city = r["city"]
        ckey = city.lower().replace(" ", "-")
        label = CITY_LABEL.get(city, CITY_LABEL.get(ckey, city))
        # Use the baseline-history raw counts for BOTH today and the average so
        # they're comparable. (r['total_events'] is the post-fan-out published
        # count — inflated by recurrence expansion — and comparing it to the
        # pre-fan-out historical average made every city look "high".)
        per_date = city_totals.get(city) or city_totals.get(ckey) or {}
        sorted_days = [v for d, v in sorted(per_date.items())]
        today_n = sorted_days[-1] if sorted_days else r.get("total_events", 0)
        # Average over a RECENT window (last 7 prior days), not all history —
        # early dates often have only a source or two logged (e.g. 9 events
        # before the full scraper set came online), which would drag the
        # average down and make a normal day look "high".
        prior_vals = sorted_days[:-1][-7:]
        avg = sum(prior_vals) / len(prior_vals) if prior_vals else 0
        if avg > 0:
            chg = (today_n - avg) / avg
            if chg >= ANOMALY_PCT:
                flag = f'<span style="color:#92400e">&#9650; high (avg ~{round(avg)})</span>'
            elif chg <= -ANOMALY_PCT:
                flag = f'<span style="color:#b91c1c">&#9660; low (avg ~{round(avg)})</span>'
            else:
                flag = f'<span style="color:#6b7280">normal (avg ~{round(avg)})</span>'
        else:
            flag = '<span style="color:#9ca3af">—</span>'
        city_rows.append(
            f'<tr style="border-bottom:1px solid #f0f0f0">'
            f'<td style="padding:10px 8px">{label}</td>'
            f'<td style="padding:10px 8px;text-align:right;font-weight:600">{today_n}</td>'
            f'<td style="padding:10px 8px;text-align:right;font-size:13px">{flag}</td>'
            f'</tr>'
        )
    city_table = (
        '<h2 style="font-size:18px;margin:0 0 12px">Events by city today</h2>'
        '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:28px">'
        '<thead><tr style="background:#f3f4f6">'
        '<th style="padding:8px;text-align:left">City</th>'
        '<th style="padding:8px;text-align:right">Events today</th>'
        '<th style="padding:8px;text-align:right">vs. recent</th>'
        '</tr></thead><tbody>' + ''.join(city_rows) + '</tbody></table>'
    )

    # ── 3. last-5-days per-city trend ─────────────────────
    trend_head = ''.join(f'<th style="padding:8px;text-align:right">{d[5:]}</th>' for d in dates)
    trend_rows = []
    for r in reports:
        city = r["city"]
        ckey = city.lower().replace(" ", "-")
        label = CITY_LABEL.get(city, CITY_LABEL.get(ckey, city))
        per_date = city_totals.get(city) or city_totals.get(ckey) or {}
        cells = ''.join(
            f'<td style="padding:8px;text-align:right">{per_date.get(d, "—")}</td>'
            for d in dates
        )
        trend_rows.append(
            f'<tr style="border-bottom:1px solid #f0f0f0">'
            f'<td style="padding:8px">{label}</td>{cells}</tr>'
        )
    trend_table = (
        '<h2 style="font-size:18px;margin:0 0 6px">Last few days (total events)</h2>'
        '<div style="font-size:13px;color:#6b7280;margin-bottom:12px">'
        'Daily event count per city. Gaps mean the scrape did not run that day.</div>'
        '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:28px">'
        f'<thead><tr style="background:#f3f4f6"><th style="padding:8px;text-align:left">City</th>{trend_head}</tr></thead>'
        '<tbody>' + ''.join(trend_rows) + '</tbody></table>'
    )

    # ── 4. source anomalies ───────────────────────────────
    if anomalies:
        anom_rows = []
        gs = guard_state or {}
        for a in anomalies[:15]:
            label = CITY_LABEL.get(a["city"], a["city"])
            pct = round(a["change"] * 100)
            arrow = "&#9650;" if a["change"] > 0 else "&#9660;"
            color = "#92400e" if a["change"] > 0 else "#b91c1c"
            # If the resilience guard is retaining this source (a throttled/failed
            # scrape), the events are NOT lost — note that so a drop isn't alarming.
            retained = ""
            g = gs.get(a["source"])
            if a["change"] < 0 and g and g.get("low_streak", 0) > 0:
                retained = (
                    f'<div style="font-size:11px;color:#065f46;margin-top:2px">'
                    f'&#10003; retained by guard — {g.get("count", 0)} events still live</div>'
                )
            elif a["change"] < 0 and not a.get("persistent"):
                # One-off dip, not a sustained decline — usually a transient
                # scrape or duplicates removed by dedup, not lost coverage.
                retained = (
                    f'<div style="font-size:11px;color:#6b7280;margin-top:2px">'
                    f'single-day dip — likely transient or dedup cleanup, not a confirmed loss</div>'
                )
            elif a["change"] < 0 and a.get("persistent"):
                retained = (
                    f'<div style="font-size:11px;color:#b91c1c;margin-top:2px">'
                    f'&#9888; down 3+ days running — check this scraper</div>'
                )
            anom_rows.append(
                f'<tr style="border-bottom:1px solid #f0f0f0">'
                f'<td style="padding:8px">{a["source"]}<div style="font-size:12px;color:#9ca3af">{label}</div>{retained}</td>'
                f'<td style="padding:8px;text-align:right;font-weight:600">{a["current"]}</td>'
                f'<td style="padding:8px;text-align:right;color:#6b7280">~{a["avg"]}</td>'
                f'<td style="padding:8px;text-align:right;color:{color};font-weight:600">{arrow} {pct:+d}%</td>'
                f'</tr>'
            )
        anomaly_html = (
            '<h2 style="font-size:18px;margin:0 0 6px">Sources with unusual counts</h2>'
            '<div style="font-size:13px;color:#6b7280;margin-bottom:12px">'
            f'Counts that moved more than {round(ANOMALY_PCT*100)}% from their recent average. '
            'A jump can be a new batch of events (good) or a duplicate; a drop can mean a source broke.</div>'
            '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:28px">'
            '<thead><tr style="background:#f3f4f6">'
            '<th style="padding:8px;text-align:left">Source</th>'
            '<th style="padding:8px;text-align:right">Now</th>'
            '<th style="padding:8px;text-align:right">Usual</th>'
            '<th style="padding:8px;text-align:right">Change</th>'
            '</tr></thead><tbody>' + ''.join(anom_rows) + '</tbody></table>'
        )
    else:
        anomaly_html = (
            '<h2 style="font-size:18px;margin:0 0 12px">Sources with unusual counts</h2>'
            '<div style="padding:14px;background:#ecfdf5;color:#065f46;border-radius:8px;margin-bottom:28px">'
            'None — every source is within its normal range.</div>'
        )

    # ── 5. needs your attention (sev-1 + health flags) ────
    issue_blocks = []
    for r in reports:
        city = r["city"]
        label = CITY_LABEL.get(city, city)
        sev1 = [i for i in r.get("issues", []) if i.get("severity") == 1]
        if not sev1:
            continue
        by_type = Counter(i["type"] for i in sev1)
        rows_html = []
        for i in sev1[:MAX_ISSUES_PER_CITY]:
            link = i.get("event_link") or ""
            link_html = (
                f'<a href="{link}" style="color:#3b82f6;text-decoration:none">view &#8599;</a>'
                if link else ""
            )
            rows_html.append(
                f"<tr style='border-bottom:1px solid #eee'>"
                f"<td style='padding:6px 10px'>"
                f"<div><strong>{(i.get('event_title') or '(no title)')[:80]}</strong></div>"
                f"<div style='font-size:12px;color:#666;margin-top:2px'>{i.get('message', '')[:160]}</div>"
                f"</td>"
                f"<td style='padding:6px 10px;font-size:13px'>{link_html}</td>"
                f"</tr>"
            )
        remaining = max(0, len(sev1) - MAX_ISSUES_PER_CITY)
        more_note = (
            f"<div style='margin-top:8px;font-size:13px;color:#666'>+ {remaining} more</div>"
            if remaining else ""
        )
        type_summary = ", ".join(f"{n} {t.replace('_', ' ')}" for t, n in by_type.most_common())
        issue_blocks.append(
            f"<h3 style='margin:20px 0 8px;font-size:16px'>{label} "
            f"<span style='font-size:13px;font-weight:normal;color:#666'>— {len(sev1)} to review</span></h3>"
            f"<div style='font-size:13px;color:#666;margin-bottom:8px'>{type_summary}</div>"
            f"<table style='width:100%;border-collapse:collapse;border:1px solid #eee'>{''.join(rows_html)}</table>"
            f"{more_note}"
        )

    # health-check flagged sources folded into attention section
    health_block = ""
    if llm_flagged:
        fr = []
        for f in llm_flagged[:10]:
            fr.append(
                f"<tr style='border-bottom:1px solid #eee'>"
                f"<td style='padding:6px 10px'><strong>{f.get('source','?')}</strong>"
                f"<div style='font-size:12px;color:#666'>{(f.get('reason') or f.get('note') or '')[:160]}</div></td></tr>"
            )
        health_block = (
            "<h3 style='margin:20px 0 8px;font-size:16px'>Health check flagged these sources</h3>"
            "<div style='font-size:13px;color:#666;margin-bottom:8px'>Claude compared each source's site to what we scraped.</div>"
            f"<table style='width:100%;border-collapse:collapse;border:1px solid #eee'>{''.join(fr)}</table>"
        )

    if issue_blocks or health_block:
        attention = (
            '<h2 style="font-size:18px;margin:0 0 6px">Needs your attention</h2>'
            '<div style="font-size:13px;color:#6b7280;margin-bottom:8px">'
            'Things auto-repair could not fix on its own — may need manual entry or a look.</div>'
            + ''.join(issue_blocks) + health_block
        )
    else:
        attention = (
            '<h2 style="font-size:18px;margin:0 0 12px">Needs your attention</h2>'
            '<div style="padding:16px;background:#ecfdf5;color:#065f46;border-radius:8px">'
            'Nothing needs manual review today. Clean across all cities.</div>'
        )

    # ── 6. tiny technical footer (auto-repair counts) ─────
    repair_reports = (repair or {}).get("reports", [])
    total_repaired = sum(r.get("total_fixes", 0) for r in repair_reports)
    footer_detail = (
        f'<div style="margin-top:36px;padding-top:14px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af">'
        f'{total_repaired} minor issues auto-repaired this run. '
        f'<a href="{REPO_URL}/actions" style="color:#9ca3af">View run</a></div>'
    )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2937;max-width:680px;margin:0 auto;padding:24px">
  <h1 style="font-size:24px;margin:0 0 4px">yoocal daily health</h1>
  <div style="color:#6b7280;font-size:14px;margin-bottom:24px">{audit_date}</div>
  {verdict_html}
  {city_table}
  {trend_table}
  {anomaly_html}
  {attention}
  {footer_detail}
</body>
</html>"""


def send_email(html, subject):
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set — cannot send email")
        return False
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": DIGEST_FROM, "to": [DIGEST_TO], "subject": subject, "html": html},
            timeout=20,
        )
        if r.status_code == 200:
            print(f"OK: digest sent to {DIGEST_TO}")
            return True
        print(f"FAILED: Resend returned {r.status_code} — {r.text[:200]}")
        return False
    except requests.RequestException as e:
        print(f"FAILED: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    audit = _load_json("audit_issues.json")
    if not audit:
        print("No audit_issues.json found — run event_quality_audit.py first")
        sys.exit(1)
    repair = _load_json("repair_log.json")
    llm_health = _load_json("scraper_llm_health.json")
    baselines = _load_json("scraper_baselines.json")
    guard_state = _load_json("last_good_sources.json")

    audit_date = audit.get("audit_date", "today")
    reports = audit.get("reports", [])
    total_sev1 = sum(_sev_count(r.get("by_severity") or {}, 1) for r in reports)
    total_events = sum(r.get("total_events", 0) for r in reports)
    flag_count = len((llm_health or {}).get("flagged") or [])
    flag_tag = f", {flag_count} flagged" if flag_count else ""
    subject = f"[yoocal] {audit_date} — {total_events} events, {total_sev1} to review{flag_tag}"

    html = render_html(audit, repair, llm_health, baselines, guard_state)

    if dry_run:
        Path("audit_digest_preview.html").write_text(html)
        print("Dry run — HTML preview written to audit_digest_preview.html")
        print(f"Subject: {subject}")
    else:
        send_email(html, subject)


if __name__ == "__main__":
    main()
