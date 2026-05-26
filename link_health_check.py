"""Link-health check across all production city files.

Collects every unique event `link`, checks each (HEAD->GET fallback, threaded),
and classifies OK / redirect / dead / error. For dead links and redirects it
proposes a VERIFIED fix (final redirect target, or domain root only if that
itself returns 200 — never replaces a dead link with another unverified URL).

Writes:
  link_health.json        — full report (all statuses + affected events)
  link_health_fixes.json  — proposed fixes (dead/redirect -> verified URL)

Does NOT modify production files. Review link_health_fixes.json, then run with
--apply to write the fixes into the city files.
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests

CITY_FILES = [
    'public/events.json', 'public/events-heber.json',
    'public/events-jackson.json', 'public/events-elkhartlake.json',
]
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh) Chrome/124.0'}
TIMEOUT = 12
MAX_WORKERS = 8


def collect_links():
    links = {}
    for f in CITY_FILES:
        try:
            data = json.load(open(f))
        except Exception:
            continue
        for e in data.get('events', []):
            u = (e.get('link') or '').strip()
            if u.startswith('http'):
                links.setdefault(u, []).append((f, e.get('title', '')[:40]))
    return links


def check_one(url):
    """Return (url, status, final_url). status in OK/REDIRECT/DEAD/ERROR."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400 or r.status_code == 405:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        code = r.status_code
        final = r.url
        if code == 200:
            # redirected somewhere different?
            if final.rstrip('/') != url.rstrip('/'):
                return (url, 'REDIRECT', final)
            return (url, 'OK', final)
        if code in (404, 410):
            return (url, 'DEAD', None)
        return (url, f'HTTP_{code}', None)
    except Exception as ex:
        return (url, 'ERROR', str(ex)[:40])


def verified_root(url):
    """Return the domain root or /events if EITHER returns 200, else None.
    Never proposes an unverified fallback."""
    p = urlparse(url)
    for path in ('/events', '/'):
        cand = f'{p.scheme}://{p.netloc}{path}'
        try:
            if requests.get(cand, headers=HEADERS, timeout=TIMEOUT).status_code == 200:
                return cand
        except Exception:
            pass
    return None


def main():
    apply = '--apply' in sys.argv
    links = collect_links()
    urls = list(links.keys())
    print(f'Checking {len(urls)} unique links across {len(CITY_FILES)} cities '
          f'({sum(len(v) for v in links.values())} events)...')

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(check_one, u): u for u in urls}
        done = 0
        for fut in as_completed(futs):
            url, status, final = fut.result()
            results[url] = (status, final)
            done += 1
            if done % 200 == 0:
                print(f'  ...{done}/{len(urls)}')

    ok = [u for u, (s, _) in results.items() if s == 'OK']
    redirect = {u: f for u, (s, f) in results.items() if s == 'REDIRECT'}
    dead = [u for u, (s, _) in results.items() if s == 'DEAD']
    other = {u: s for u, (s, _) in results.items() if s not in ('OK', 'REDIRECT', 'DEAD')}

    print(f'\n  OK: {len(ok)} | redirect: {len(redirect)} | DEAD: {len(dead)} | error/other: {len(other)}')

    # Build proposed fixes: redirects -> final target; dead -> verified root
    fixes = {}
    for u, final in redirect.items():
        fixes[u] = final
    if dead:
        print(f'\nResolving fallbacks for {len(dead)} dead links...')
        for u in dead:
            vr = verified_root(u)
            if vr:
                fixes[u] = vr

    # Report
    if dead:
        print('\n=== DEAD links ===')
        for u in dead:
            fix = fixes.get(u, 'NO verified fallback — needs manual fix')
            evs = links[u]
            print(f'  ✗ {u}')
            print(f'      -> proposed: {fix}')
            print(f'      affects {len(evs)} event(s), e.g. {evs[0][1]} ({evs[0][0].split("/")[-1]})')
    if other:
        print('\n=== errors / non-404 problems (NOT auto-fixed) ===')
        for u, s in list(other.items())[:20]:
            print(f'  ? {s}  {u}  ({links[u][0][1]})')

    json.dump({
        'ok': len(ok), 'redirect': redirect, 'dead': dead, 'other': other,
        'affected': {u: links[u] for u in list(dead) + list(other.keys())},
    }, open('link_health.json', 'w'), indent=2, default=str)
    json.dump(fixes, open('link_health_fixes.json', 'w'), indent=2)
    print(f'\nWrote link_health.json + link_health_fixes.json ({len(fixes)} proposed fixes)')

    if apply:
        print('\n--apply: writing fixes into city files...')
        total = 0
        for f in CITY_FILES:
            data = json.load(open(f))
            changed = 0
            for e in data.get('events', []):
                if e.get('link') in fixes:
                    e['link'] = fixes[e['link']]
                    changed += 1
            json.dump(data, open(f, 'w'), indent=2)
            total += changed
            print(f'  {f}: {changed} links updated')
        print(f'Applied {total} link updates. Rebuild + verify before committing.')
    else:
        print('Review link_health_fixes.json, then re-run with --apply to write them.')


if __name__ == '__main__':
    main()
