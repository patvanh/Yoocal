"""Daily audit digest email via Resend.

Reads audit_issues.json + repair_log.json (produced by event_quality_audit.py
and event_auto_repair.py respectively). Sends an HTML email digest to the
admin summarizing:
  - What was auto-repaired
  - What severity-1 issues remain
  - Direct GitHub links to inspect each problem record

Designed to run as the final step in the daily GitHub Actions workflow,
after audit + repair have written their JSON outputs.

Environment variables:
  RESEND_API_KEY   required
  YOOCAL_DIGEST_TO email recipient (default: patrick@vanhornpc.com)

Usage:
  python audit_email_digest.py            # send digest
  python audit_email_digest.py --dry-run  # print HTML to stdout, do not send
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests


RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DIGEST_TO = os.environ.get("YOOCAL_DIGEST_TO", "patrick@vanhornpc.com")
DIGEST_FROM = "yoocal quality <quality@yoocal.com>"
REPO_URL = "https://github.com/patvanh/Yoocal"

# Max severity-1 issues to include in the email body. Beyond this we
# show a count and link to the JSON file.
MAX_ISSUES_PER_CITY = 8


def _load_json(path: str) -> dict | None:
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _sev_count(by_severity: dict, level: int) -> int:
    """Get a severity count from the by_severity dict, handling int or str keys."""
    return by_severity.get(level, by_severity.get(str(level), 0))


def _sev1_issues(reports: list) -> list:
    """Pull severity-1 issues from all city reports, deduped by event_index."""
    out = []
    seen = set()
    for r in reports:
        for i in r.get("issues", []):
            if i.get("severity") != 1:
                continue
            key = (r["city"], i.get("event_index"), i.get("type"))
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
    return out


def render_html(audit: dict, repair: dict | None) -> str:
    """Render the email body as HTML."""
    audit_date = audit.get("audit_date", "today")
    reports = audit.get("reports", [])
    repair_reports = (repair or {}).get("reports", [])

    # ─── Header summary ─────────────────────────────────────
    rows = []
    for r in reports:
        sev = r.get("by_severity") or {}
        rows.append(
            f"<tr>"
            f"<td>{r['city']}</td>"
            f"<td style='text-align:right'>{r['total_events']}</td>"
            f"<td style='text-align:right'>{_sev_count(sev, 1)}</td>"
            f"<td style='text-align:right'>{_sev_count(sev, 2)}</td>"
            f"<td style='text-align:right'>{_sev_count(sev, 3)}</td>"
            f"<td style='text-align:right'><strong>{r['total_issues']}</strong></td>"
            f"</tr>"
        )

    repair_rows = []
    if repair_reports:
        for r in repair_reports:
            passes = r.get("passes") or {}
            fixes_by_type = ", ".join(
                f"{p}={result.get('fixed', 0)}"
                for p, result in passes.items()
                if result.get("fixed", 0) > 0
            )
            repair_rows.append(
                f"<tr>"
                f"<td>{r['city']}</td>"
                f"<td style='text-align:right'>{r.get('before_count', '—')}</td>"
                f"<td style='text-align:right'>{r.get('after_count', '—')}</td>"
                f"<td style='text-align:right'><strong>{r.get('total_fixes', 0)}</strong></td>"
                f"<td style='font-size:13px;color:#666'>{fixes_by_type or '—'}</td>"
                f"</tr>"
            )

    # ─── Sev-1 issues per city ──────────────────────────────
    issue_blocks = []
    for r in reports:
        city = r["city"]
        sev1 = [i for i in r.get("issues", []) if i.get("severity") == 1]
        if not sev1:
            continue
        by_type = Counter(i["type"] for i in sev1)
        rows_html = []
        for i in sev1[:MAX_ISSUES_PER_CITY]:
            link = i.get("event_link") or ""
            link_html = (
                f'<a href="{link}" style="color:#3b82f6;text-decoration:none">source ↗</a>'
                if link else ""
            )
            rows_html.append(
                f"<tr style='border-bottom:1px solid #eee'>"
                f"<td style='padding:6px 10px;font-family:monospace;font-size:12px;color:#dc2626'>{i.get('type', '?')}</td>"
                f"<td style='padding:6px 10px'>"
                f"  <div><strong>{(i.get('event_title') or '')[:80]}</strong></div>"
                f"  <div style='font-size:12px;color:#666;margin-top:2px'>{i.get('message', '')[:160]}</div>"
                f"</td>"
                f"<td style='padding:6px 10px;font-size:13px'>{link_html}</td>"
                f"</tr>"
            )
        remaining = max(0, len(sev1) - MAX_ISSUES_PER_CITY)
        more_note = ""
        if remaining:
            more_note = (
                f"<div style='margin-top:8px;font-size:13px;color:#666'>"
                f"+ {remaining} more — see full list in "
                f"<a href='{REPO_URL}/blob/main/audit_issues.json' style='color:#3b82f6'>audit_issues.json</a>"
                f"</div>"
            )
        type_summary = ", ".join(f"{n} {t}" for t, n in by_type.most_common())
        issue_blocks.append(
            f"<h3 style='margin:24px 0 8px;font-size:18px'>{city} "
            f"<span style='font-size:14px;font-weight:normal;color:#666'>"
            f"— {len(sev1)} severity-1 issues</span></h3>"
            f"<div style='font-size:13px;color:#666;margin-bottom:8px'>{type_summary}</div>"
            f"<table style='width:100%;border-collapse:collapse;border:1px solid #eee'>"
            f"{''.join(rows_html)}"
            f"</table>"
            f"{more_note}"
        )

    # ─── Email shell ────────────────────────────────────────
    total_sev1 = sum(_sev_count(r.get("by_severity") or {}, 1) for r in reports)
    total_repaired = sum(r.get("total_fixes", 0) for r in repair_reports)

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2937;max-width:680px;margin:0 auto;padding:24px">

  <h1 style="font-size:24px;margin:0 0 4px">yoocal quality digest</h1>
  <div style="color:#6b7280;font-size:14px;margin-bottom:24px">{audit_date}</div>

  <div style="background:#f9fafb;padding:16px;border-radius:8px;margin-bottom:24px">
    <div style="font-size:14px;color:#374151">
      <strong>{total_repaired}</strong> issues auto-repaired
      &middot;
      <strong>{total_sev1}</strong> severity-1 issues remain
    </div>
  </div>

  <h2 style="font-size:18px;margin:0 0 12px">Per-city audit</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#f3f4f6">
        <th style="padding:8px;text-align:left">City</th>
        <th style="padding:8px;text-align:right">Events</th>
        <th style="padding:8px;text-align:right">Sev 1</th>
        <th style="padding:8px;text-align:right">Sev 2</th>
        <th style="padding:8px;text-align:right">Sev 3</th>
        <th style="padding:8px;text-align:right">Total</th>
      </tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  {('<h2 style="font-size:18px;margin:24px 0 12px">Auto-repair summary</h2>'
    '<table style="width:100%;border-collapse:collapse;font-size:14px">'
    '<thead><tr style="background:#f3f4f6">'
    '<th style="padding:8px;text-align:left">City</th>'
    '<th style="padding:8px;text-align:right">Before</th>'
    '<th style="padding:8px;text-align:right">After</th>'
    '<th style="padding:8px;text-align:right">Fixes</th>'
    '<th style="padding:8px;text-align:left">Details</th>'
    '</tr></thead>'
    '<tbody>' + ''.join(repair_rows) + '</tbody>'
    '</table>') if repair_rows else ''}

  <h2 style="font-size:18px;margin:32px 0 8px">Severity-1 issues needing review</h2>
  <div style="font-size:13px;color:#6b7280;margin-bottom:16px">
    These are events where users would see something broken: wrong dates, missing band names,
    duplicate records, etc. Auto-repair couldn't resolve these on its own.
  </div>
  {''.join(issue_blocks) if issue_blocks else '<div style="padding:16px;background:#ecfdf5;color:#065f46;border-radius:8px">No severity-1 issues remaining. Clean across all 4 cities.</div>'}

  <div style="margin-top:48px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af">
    Generated by event_quality_audit.py + audit_email_digest.py · 
    <a href="{REPO_URL}/actions" style="color:#9ca3af">View latest run</a>
  </div>

</body>
</html>"""


def send_email(html: str, subject: str) -> bool:
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set — cannot send email")
        return False

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": DIGEST_FROM,
                "to": [DIGEST_TO],
                "subject": subject,
                "html": html,
            },
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

    audit_date = audit.get("audit_date", "today")
    reports = audit.get("reports", [])
    total_sev1 = sum(_sev_count(r.get("by_severity") or {}, 1) for r in reports)
    total_events = sum(r.get("total_events", 0) for r in reports)

    subject = f"[yoocal] {audit_date} digest — {total_sev1} sev-1, {total_events} events"

    html = render_html(audit, repair)

    if dry_run:
        # Print to stdout for inspection
        Path("audit_digest_preview.html").write_text(html)
        print(f"Dry run — HTML preview written to audit_digest_preview.html")
        print(f"Subject: {subject}")
        print(f"Would send to: {DIGEST_TO}")
        print(f"Would send from: {DIGEST_FROM}")
    else:
        send_email(html, subject)


if __name__ == "__main__":
    main()
