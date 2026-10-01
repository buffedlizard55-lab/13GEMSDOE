#!/usr/bin/env python3
"""Bounded, allowlisted source-change observations; no competition-site polling.

Runs daily in an open-egress runner. Never overwrites last successful content/hash
with a failed request. A changed source is REVIEW_REQUIRED, not a verified new fact.
No credentials are written to reports. Raw bodies are cache-only, not committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {'gdr.openei.org', 'www.usgs.gov', 'docs.nlr.gov', 'docs.nrel.gov',
                 'api.waterdata.usgs.gov', 'api.github.com'}
BLOCKED_HOST_SUFFIX = 'drivendata.org'


def approved(url: str) -> bool:
    try:
        u = urlsplit(url)
        sensitive = {'token', 'access_token', 'key', 'api_key', 'password', 'signature', 'authorization'}
        return (u.scheme == 'https' and u.hostname in ALLOWED_HOSTS and u.port in (None, 443)
                and not u.username and not u.password and not u.hostname.endswith(BLOCKED_HOST_SUFFIX)
                and not any(k.lower() in sensitive for k, _ in parse_qsl(u.query)))
    except (ValueError, TypeError):
        return False



class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip-1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not approved(newurl):
            raise ValueError('Redirect outside approved source hosts')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_source(entry: dict) -> dict:
    url = entry['url']
    if not approved(url):
        raise ValueError('Source URL not approved; competition polling is forbidden')
    req = urllib.request.Request(url, headers={'User-Agent': '13GEMSDOE-source-review/1.0 (+https://github.com/buffedlizard55-lab/13GEMSDOE)',
                                               'Accept': 'application/json' if entry['format'] == 'json' else '*/*'})
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(req, timeout=30) as response:
        data = response.read(entry['max_bytes'] + 1)
        if len(data) > entry['max_bytes']:
            raise ValueError('Source exceeded configured byte limit')
        if not approved(response.geturl()):
            raise ValueError('Unapproved final URL')
        content_type = response.headers.get('Content-Type', '')
        last_modified = response.headers.get('Last-Modified')
        final_url = response.geturl()
    if entry['format'] == 'pdf':
        if not data.startswith(b'%PDF-'):
            raise ValueError('Expected PDF, not an HTML error page')
        semantic = data
        excerpt = 'PDF bytes observed; substantive rules still require source review.'
    elif entry['format'] == 'json':
        obj = json.loads(data)
        semantic = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
        excerpt = 'JSON metadata observed; data obtainability/usefulness not inferred.'
    else:
        text = data.decode('utf8', 'replace')
        parser = VisibleText(); parser.feed(text); text = parser.text()
        if entry.get('required_text', '').lower() not in text.lower() or not text:
            raise ValueError('Expected source text absent; possible blocked/login/error page')
        semantic = text.encode()
        excerpt = text[:280]
    cache = ROOT / '.cache/source_bodies'
    cache.mkdir(parents=True, exist_ok=True)
    (cache / (entry['id'] + '.bin')).write_bytes(data)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'normalized_content_sha256': hashlib.sha256(semantic).hexdigest(),
            'content_type': content_type, 'last_modified': last_modified,
            'final_url': final_url, 'excerpt': excerpt}


def refresh(previous: dict, entries: list[dict], fetch=fetch_source, now=None) -> dict:
    stamp = now or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    old = previous.get('sources', {})
    result = {'schema': 1, 'generated_utc': stamp,
              'scope': 'Approved open-data/organizer-repository endpoints only; NO DrivenData polling.',
              'facts_last_manually_reviewed_utc': '2026-10-01', 'sources': {}}
    for entry in entries:
        if not re.fullmatch(r'[a-z][a-z0-9_]*', entry['id']) or not approved(entry['url']):
            raise ValueError('Invalid source id/endpoint; never store credential-bearing or unapproved URLs')
        prior = old.get(entry['id'], {})
        rec = {**prior, 'title': entry['title'], 'url': entry['url'], 'licence': entry.get('licence'),
               'last_attempt_utc': stamp, 'evidence_class': 'automated_source_observation_not_scientific_certification'}
        try:
            observation = fetch(entry)
            prev_hash = prior.get('normalized_content_sha256')
            changed = prev_hash is not None and (prev_hash != observation['normalized_content_sha256'] or prior.get('url') != entry['url'])
            rec.update(observation, last_success_utc=stamp, last_success_url=entry['url'], status='REVIEW_REQUIRED' if changed else 'OBSERVED_OK',
                       changed_since_previous_success=changed, error=None)
        except Exception as ex:
            rec.update(status='FETCH_FAILED_LAST_SUCCESS_RETAINED' if prior.get('last_success_utc') else 'FETCH_FAILED_NO_SUCCESS',
                       error=f'{type(ex).__name__}: {ex}', changed_since_previous_success=None)
        result['sources'][entry['id']] = rec
    result['n_observed_ok'] = sum(v['status'] in ('OBSERVED_OK', 'REVIEW_REQUIRED') for v in result['sources'].values())
    result['n_failed'] = len(entries) - result['n_observed_ok']
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=ROOT / 'reports/open_source_feed.json')
    ap.add_argument('--strict', action='store_true', help='Fail if any source observation failed (still save honest results)')
    args = ap.parse_args()
    config = json.loads((ROOT / 'config/open_sources.json').read_text())
    old = json.loads(args.output.read_text()) if args.output.exists() else {}
    result = refresh(old, config['sources'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for k, v in result['sources'].items():
        print(k, v['status'], v.get('last_success_utc', 'never'), v.get('error') or '')
    return 1 if args.strict and result['n_failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
