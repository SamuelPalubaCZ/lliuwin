#!/usr/bin/env python3
"""Read GitHub history without executing third-party code; retain source evidence."""
import concurrent.futures as futures
import datetime
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / 'docs' / 'upstream-snapshot.json'

def api(path):
    result = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    if result.returncode:
        return {'error': result.stderr.strip()}
    return json.loads(result.stdout)

def pages(path):
    rows = []
    for page in range(1, 100):
        part = api(path + ('&' if '?' in path else '?') + 'per_page=100&page=%s' % page)
        if not isinstance(part, list):
            return rows, part
        rows.extend(part)
        if len(part) < 100:
            return rows, None
    raise RuntimeError('Pagination limit reached')

def inspect(repo):
    branches, error = pages('repos/' + repo + '/branches')
    releases, release_error = pages('repos/' + repo + '/releases')
    runs = api('repos/' + repo + '/actions/runs?per_page=5')
    return {'repo': repo, 'branches': branches, 'error': error,
            'releases': [{k: r.get(k) for k in ('tag_name', 'target_commitish', 'published_at', 'prerelease', 'body', 'html_url')} for r in releases],
            'release_error': release_error,
            'runs': [{k: r.get(k) for k in ('head_sha', 'conclusion', 'event', 'html_url')} for r in runs.get('workflow_runs', [])]}

def main():
    data = {'date': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    data['lliurex'] = api('repos/hakuna-m/wubiuefi/compare/master...lliurex:lliuwin:master')
    data['missing'] = api('repos/lliurex/lliuwin/compare/master...hakuna-m:wubiuefi:master')
    data['issues'], data['issues_error'] = pages('repos/hakuna-m/wubiuefi/issues?state=all')
    fork_names = set()
    for repo in ('hakuna-m/wubiuefi', 'lliurex/lliuwin'):
        rows, error = pages('repos/' + repo + '/forks')
        if error:
            raise RuntimeError(error)
        fork_names.update(r['full_name'] for r in rows)
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        data['forks'] = list(pool.map(inspect, sorted(fork_names)))
    CACHE.write_text(json.dumps(data, indent=2) + '\n')
    print('Saved %d forks and %d issue/PR records to %s' % (len(data['forks']), len(data['issues']), CACHE), flush=True)

if __name__ == '__main__':
    main()
