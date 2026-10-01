#!/usr/bin/env python3
"""Pin prior project-site HTML/tree identities without treating team claims as facts.

Read-only GitHub access. Official scientific facts come from official sources, NOT
these team sites. Exact shared blobs establish artifact reuse, not submission/score
attribution or improper conduct. No binary datasets are committed by this script.
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
from pathlib import Path

from refresh_open_sources import VisibleText

ROOT = Path(__file__).resolve().parents[1]
REPOS = ['GEMSDOE', 'GEMSDOE2', 'GEMSDOE3', 'GEMSDOE4', '5GEMSDOE', '6GEMSDOE',
         '7GEMSDOE', '8GEMSDOE', 'GEMSDOE9', 'GEMSDOE10', '11GEMSDOE', '12GEMSDOE',
         '14GEMSDOE', '15GEMSDOE', '16GEMSDOE', '17GEMSDOE']
SHARED = '812e61b74050d1350cc2bde1fab0c76ead32e0c4'
OWNER = 'buffedlizard55-lab'


def api(path):
    p = subprocess.run(['gh', 'api', path], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def main() -> int:
    report = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'scope': 'Prior supplied project sites and the 14-17 research follow-ups; read-only GitHub tree/HTML audit.',
              'evidence_boundary': 'Team-authored site descriptions are not official scientific verification or per-file competition receipts.',
              'shared_blob': SHARED, 'shared_blob_file_sha256': '7f00890a62878d612fb5eef67a9a364a2df819433dde74b6762ce4fc0fc4fe15',
              'repos': {}}
    for repo in REPOS:
        try:
            meta = api(f'repos/{OWNER}/{repo}')
            commit = api(f'repos/{OWNER}/{repo}/commits/{meta["default_branch"]}')['sha']
            tree = api(f'repos/{OWNER}/{repo}/git/trees/{commit}?recursive=1')
            files = {r['path']: r for r in tree['tree'] if r['type'] == 'blob'}
            rec = {'commit': commit, 'default_branch': meta['default_branch'], 'tree_truncated': tree.get('truncated', False),
                   'site_url': f'https://{OWNER}.github.io/{repo}/',
                   'shared_ens12_paths': [{'path': r['path'], 'git_blob_sha1': r['sha'], 'bytes': r.get('size')}
                                          for r in files.values() if r['sha'] == SHARED],
                   'site_pages_read': []}
            for name in ('index.html', 'docs/index.html', 'docs/hypotheses.html'):
                if name not in files or files[name].get('size', 0) > 1_000_000:
                    continue
                blob = api(f'repos/{OWNER}/{repo}/git/blobs/{files[name]["sha"]}')
                data = base64.b64decode(blob['content'])
                parser = VisibleText(); parser.feed(data.decode('utf8', 'replace'))
                text = parser.text()
                rec['site_pages_read'].append({'path': name, 'git_blob_sha1': files[name]['sha'],
                                               'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                                               'team_authored_excerpt_not_verified_science': text[:1600]})
            report['repos'][repo] = rec
            print(repo, commit[:12], 'site pages', len(rec['site_pages_read']), 'shared ens12', len(rec['shared_ens12_paths']), flush=True)
        except Exception as ex:
            report['repos'][repo] = {'error': str(ex), 'status': 'NOT_VERIFIED'}
            print(repo, 'NOT_VERIFIED', type(ex).__name__, flush=True)
    found = [k for k, v in report['repos'].items() if v.get('shared_ens12_paths')]
    report['conclusion'] = {'verified_repositories_with_exact_shared_ens12_blob': found,
                            'artifact_reuse_established_for_GEMSDOE_and_5GEMSDOE': all(k in found for k in ('GEMSDOE', '5GEMSDOE')),
                            'per_file_score_attribution': 'UNVERIFIED',
                            'different_map_same_rounded_score_possible': True,
                            'distinct_8GEMSDOE_map_evidence': 'reports/scored_forensics.json; ens12/apex support IoU0.06703'}
    (ROOT / 'reports/sibling_site_audit_2026-10-01.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return 1 if any('error' in r for r in report['repos'].values()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
