#!/usr/bin/env python3
"""
coverage_audit.py — measure every source's true (home-IP) ceiling vs. what the
last CI scrape committed, to find sources silently losing events.

Backs up raw files, runs each city scraper fresh, counts per source, RESTORES
the raw files (so this audit does NOT change committed data), writes a gap report.
Never touches last_good_sources.json.

USAGE:
    python3 coverage_audit.py            # all cities
    python3 coverage_audit.py heber      # one city
"""
import json, os, sys, shutil, importlib, datetime
from collections import Counter

RAW_FILES = {
    "park-city": "public/raw/events.json",
    "heber":     "public/raw/events-heber.json",
    "jackson":   "public/raw/events-jackson.json",
    "elkhart":   "public/raw/events-elkhartlake.json",
    "egyptian":  "public/raw/events-egyptian.json",
}
SCRAPER_MODULE = {
    "park-city": "scraper", "heber": "heber_scraper", "jackson": "jackson_scraper",
    "elkhart": "elkhart_scraper", "egyptian": "egyptian_scraper",
}
REPORT = "coverage_audit_report.txt"

def _load(path):
    try:
        d = json.load(open(path))
        return d.get("events", d) if isinstance(d, dict) else d
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _counts(path):
    return Counter(e.get("source") or "(unknown)" for e in _load(path))

def main():
    targets = sys.argv[1:] or list(RAW_FILES.keys())
    backup_dir = "/tmp/coverage_audit_backup"
    os.makedirs(backup_dir, exist_ok=True)

    committed = {}
    for city in targets:
        path = RAW_FILES[city]
        committed[city] = _counts(path)
        if os.path.exists(path):
            shutil.copy(path, os.path.join(backup_dir, os.path.basename(path)))
    print(f"Backed up raw files to {backup_dir}", flush=True)

    fresh = {}
    for city in targets:
        mod_name = SCRAPER_MODULE[city]
        print(f"\n{'='*60}\nRunning {mod_name}.main()  ({city})\n{'='*60}", flush=True)
        try:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            mod.main()
        except SystemExit:
            pass
        except Exception as ex:
            print(f"  !! {mod_name}.main() raised: {ex}", flush=True)
        fresh[city] = _counts(RAW_FILES[city])

    for city in targets:
        bak = os.path.join(backup_dir, os.path.basename(RAW_FILES[city]))
        if os.path.exists(bak):
            shutil.copy(bak, RAW_FILES[city])
    print(f"\nRestored committed raw files from backup (no data changed).", flush=True)

    lines = [f"COVERAGE AUDIT  {datetime.datetime.now().isoformat()}",
             "fresh = this machine (unthrottled); committed = last CI scrape", ""]
    for city in targets:
        lines.append(f"\n=== {city} ===")
        lines.append("%-40s %9s %9s %7s  %s" % ("source","committed","fresh","gap","flag"))
        all_srcs = set(committed[city]) | set(fresh[city])
        rows = []
        for s in all_srcs:
            c = committed[city].get(s,0); f = fresh[city].get(s,0); gap = f-c
            if f==0 and c>0: flag="BROKEN(local 0)"
            elif c==0 and f>0: flag="NEW(not in CI)"
            elif f>=c*1.10 and gap>=5: flag="LOSS(CI<local)"
            elif c>f and c>=f*1.10 and (c-f)>=5: flag="CI_MORE?"
            else: flag="ok"
            rows.append((gap,s,c,f,flag))
        for gap,s,c,f,flag in sorted(rows, key=lambda r:-r[0]):
            lines.append("%-40s %9d %9d %+7d  %s" % (s[:40],c,f,gap,flag))
    report = "\n".join(lines)
    open(REPORT,"w").write(report)
    print("\n"+report, flush=True)
    print(f"\n\nReport written to {REPORT}", flush=True)

if __name__ == "__main__":
    main()
