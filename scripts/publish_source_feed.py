#!/usr/bin/env python3
"""One reusable GitHub issue exposes current source observations to static Pages.

Only approved source observations, not facts/weights/submission assets. Uses gh,
never credentials in files. The scheduled runner's issues:write token can publish
without touching main or creating another branch. Failure remains a failed step
plus an observation artifact, never a fake success. --seed reads prior successes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'buffedlizard55-lab/13GEMSDOE'
TITLE = 'Automated official-source observations (not competition scores)'
BEGIN = '<!-- 13GEMSDOE_SOURCE_FEED_V1 -->'
END = '<!-- END_13GEMSDOE_SOURCE_FEED_V1 -->'
BOT = 'github-actions[bot]'


def api(args):
    p = subprocess.run(['gh', 'api', *args], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def find_issue():
    rows = api([f'repos/{REPO}/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&sort=updated'])
    return next((r for r in rows if r['title'] == TITLE and r['user']['login'] == BOT and not r.get('pull_request')), None)


def parse_feed(body):
    if not isinstance(body, str) or BEGIN not in body or END not in body:
        raise ValueError('Missing source-feed envelope')
    middle = body.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if not middle.startswith('```json\n') or not middle.endswith('```'):
        raise ValueError('Malformed source-feed JSON block')
    obj = json.loads(middle[len('```json\n'):-3])
    if obj.get('schema') != 1 or not isinstance(obj.get('sources'), dict) or len(obj['sources']) > 20:
        raise ValueError('Unexpected feed schema')
    return obj


def body_for(feed):
    rows = ['# Approved open-data source observations', '',
            '**Not a leaderboard feed, platform receipt, or scientific certification.**',
            'This single bot issue is updated automatically. Changed source content needs review; failed requests preserve the last successful observation.',
            '', f'Observation run: `{feed["generated_utc"]}`', '',
            '| Source | State | Last successful observation |', '|---|---|---|']
    for rec in feed['sources'].values():
        rows.append(f'| {rec["title"].replace("|", " ")} | {rec["status"]} | {rec.get("last_success_utc", "none")} |')
    rows.extend(['', 'Machine-readable observation record for the static site:', BEGIN,
                 '```json', json.dumps(feed, indent=2, ensure_ascii=False), '```', END,
                 '', 'Scope: approved GDR/USGS/NLR/open-repository endpoints only. **NO automatic DrivenData/forum polling.**'])
    text = '\n'.join(rows)
    if len(text) > 60_000:
        raise ValueError('Feed exceeds bounded GitHub issue payload')
    return text


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--feed', type=Path, default=ROOT / '.cache/open_source_feed.json')
    ap.add_argument('--seed', action='store_true', help='Read previous bot-issued successes, or initial stored observations; no write to GitHub')
    args = ap.parse_args()
    issue = find_issue()
    if args.seed:
        feed = parse_feed(issue['body']) if issue else json.loads((ROOT / 'reports/open_source_feed.json').read_text())
        args.feed.parent.mkdir(parents=True, exist_ok=True); args.feed.write_text(json.dumps(feed, indent=2) + '\n')
        print('Seeded previous successful observations; not a new source check.')
        return 0
    feed = json.loads(args.feed.read_text())
    # Validate even if a compromised or unrelated input tries to change publication scope.
    from refresh_open_sources import approved
    if feed.get('schema') != 1 or not all(approved(r['url']) for r in feed['sources'].values()):
        raise ValueError('Unapproved source payload')
    payload = {'title': TITLE, 'body': body_for(feed)}
    if issue:
        payload['state'] = 'open'
    temp = ROOT / '.cache/source_issue_payload.json'; temp.parent.mkdir(exist_ok=True); temp.write_text(json.dumps(payload) + '\n')
    route = f'repos/{REPO}/issues' + (f'/{issue["number"]}' if issue else '')
    result = api(['--method', 'PATCH' if issue else 'POST', route, '--input', str(temp)])
    print('Published observation issue:', result['html_url'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
