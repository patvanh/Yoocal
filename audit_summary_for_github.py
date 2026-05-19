"""Print a markdown summary of audit_issues.json for the GitHub Actions
workflow run summary."""
import json
import sys


def main():
    try:
        d = json.load(open("audit_issues.json"))
    except FileNotFoundError:
        print("(audit_issues.json not found)")
        return

    for r in d.get("reports", []):
        s1 = r["by_severity"].get(1, 0)
        s2 = r["by_severity"].get(2, 0)
        s3 = r["by_severity"].get(3, 0)
        city = r["city"]
        events = r["total_events"]
        issues = r["total_issues"]
        print(
            f"- **{city}**: {events} events, {issues} issues "
            f"(sev1: {s1}, sev2: {s2}, sev3: {s3})"
        )


if __name__ == "__main__":
    main()
