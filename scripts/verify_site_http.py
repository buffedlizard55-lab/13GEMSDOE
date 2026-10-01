#!/usr/bin/env python3
"""Actual HTTP TIFF/ZIP/manifest/site delivery checks, local or GitHub Pages.

Exact named bytes, aliases, ZIP membership/CRC, decoded grid/footprint/range and
all internal site asset/download links are checked. No competition-form acceptance
is inferred. Local mode starts/stops its own restricted temporary static server.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import numpy as np
import rasterio
from rasterio.io import MemoryFile

from serve_site import SiteHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems import rio  # noqa: E402
LIVE = 'https://buffedlizard55-lab.github.io/13GEMSDOE/'
REVISION = 'r15-audit-20261001'


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.resources = []; self.downloads = []; self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.add(a['id'])
        if tag in ('a', 'link') and a.get('href'):
            self.resources.append(a['href'])
        if tag in ('script', 'img') and a.get('src'):
            self.resources.append(a['src'])
        if tag == 'a' and 'download' in a:
            self.downloads.append(a.get('href'))


def request(url, limit=8_000_000):
    req = urllib.request.Request(url, headers={'User-Agent': '13GEMSDOE-delivery-check/1.0', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Response exceeded bounded byte limit')
        return data, response.headers.get_content_type(), response.geturl()


def run(base, delivery_only=False):
    m = json.loads((ROOT / 'docs/downloads/submit.json').read_text())
    if m.get('schema') != 2:
        raise ValueError('Schema2 required')
    try:
        rio.resolve_raw('labels')
    except FileNotFoundError:
        subprocess.run(['bash', 'scripts/download_competition_data.sh', '--small'], cwd=ROOT, check=True)
    labels_path = rio.resolve_raw('labels')
    # Don't derive the verification footprint from the prediction under test.
    pin = '7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093'
    if hashlib.sha256(labels_path.read_bytes()).hexdigest() != pin:
        raise ValueError('Independent official label pin mismatch')
    with rasterio.open(labels_path) as s:
        footprint = s.read(1) >= 0
    checks = []
    cache = {}

    def record(ok, text):
        checks.append({'pass': bool(ok), 'check': text})
        print(('PASS ' if ok else 'FAIL '), text)

    def get(path, limit=8_000_000):
        if path not in cache:
            cache[path] = request(urljoin(base, path), limit)
        return cache[path]

    try:
        raw, mime, _ = get('docs/downloads/submit.json', 250_000)
        remote = json.loads(raw)
        record(mime != 'text/html' and remote.get('schema') == 2, 'HTTP manifest is JSON/schema2, not an HTML login/error page')
        record(remote['note_for_form'] == m['note_for_form'], 'HTTP manifest exact submission note')
        if not delivery_only:
            record(remote.get('submission_policy') == m.get('submission_policy'), 'HTTP scientific slot policy matches reviewed manifest')
            record(remote.get('status', {}).get('platform_acceptance_established') is False,
                   'HTTP manifest does not invent platform acceptance')
        roles = [('primary', m['primary']), ('diagnostic', m['hedge'])]
        for alt in m.get('alternates', []):
            roles.extend([(alt['stem'] + '/research-primary', alt['primary']), (alt['stem'] + '/research-diagnostic', alt['hedge'])])
        for name, entry in roles:
            p, z = 'docs/downloads/' + entry['file'], 'docs/downloads/' + entry['zip']
            body, mime, _ = get(p, entry['bytes'] + 1024)
            record(len(body) == entry['bytes'] and hashlib.sha256(body).hexdigest() == entry['sha256'], name + ': actual HTTP TIFF size/SHA256')
            record(mime in ('image/tiff', 'image/geotiff', 'application/octet-stream'), name + ': TIFF response is not HTML')
            zipped, mime, _ = get(z, entry['zip_bytes'] + 1024)
            record(len(zipped) == entry['zip_bytes'] and hashlib.sha256(zipped).hexdigest() == entry['zip_sha256'], name + ': actual HTTP ZIP size/SHA256')
            with zipfile.ZipFile(io.BytesIO(zipped)) as archive:
                names = archive.namelist()
                ok = names == [entry['file']] and archive.testzip() is None
                member = archive.read(entry['file']) if entry['file'] in names else b''
                record(ok and member == body, name + ': delivered ZIP contains exactly the delivered TIFF, CRC intact')
        for role in ('primary', 'hedge'):
            entry = m[role]
            record(remote[role]['file'] == entry['file'] and remote[role]['sha256'] == entry['sha256'] and
                   remote[role]['zip'] == entry['zip'] and remote[role]['zip_sha256'] == entry['zip_sha256'], role + ': remote manifest roles/hash agree')
            body = get('docs/downloads/' + entry['file'])[0]
            with MemoryFile(body) as mem:
                with mem.open() as s:
                    a = s.read(1)
                    record(s.count == 1 and s.dtypes == ('float32',) and s.shape == rio.EXPECTED_SHAPE and
                           str(s.crs) == rio.EXPECTED_CRS and tuple(s.transform)[:6] == rio.EXPECTED_TRANSFORM,
                           role + ': delivered raster exact official band/dtype/CRS/shape/affine')
                    record(np.isfinite(a[footprint]).all() and np.all((a[footprint] >= 0) & (a[footprint] <= 1)), role + ': ALL footprint pixels finite and within [0,1]')
                    if role == 'primary':
                        record(np.isnan(a[~footprint]).all() and s.nodata is not None and np.isnan(s.nodata), 'delivered primary: official NaN-outside/NoData convention')
                        primary_inside = a[footprint].copy()
                    else:
                        record(np.array_equal(a[footprint], primary_inside) and np.all(a[~footprint] == 0) and s.nodata is None, 'delivered diagnostic: same footprint map, zero outside, no NoData')
        for alias, role in {'latest.tif': ('primary', 'file'), 'latest.zip': ('primary', 'zip'),
                            'latest_zerofill.tif': ('hedge', 'file'), 'latest_zerofill.zip': ('hedge', 'zip')}.items():
            delivered = get('docs/downloads/' + alias)[0]
            canonical = get('docs/downloads/' + m[role[0]][role[1]])[0]
            record(delivered == canonical, 'HTTP alias byte identity: ' + alias)
        pages = ['index.html'] + ['docs/' + f for f in ('index.html', 'executive_summary.html', 'evidence.html', 'hypotheses.html', 'sources.html')]
        for path in pages:
            body, mime, _ = get(path, 500_000)
            text = body.decode('utf8'); parser = Links(); parser.feed(text)
            expect = ('docs/' if path == 'index.html' else '') + 'downloads/' + m['primary']['file']
            record(mime == 'text/html' and parser.downloads and parser.downloads[0] == expect,
                   path + ': first actual download anchor is the primary TIFF')
            record(expect in text.split('<body', 1)[-1][:4096], path + ': primary link is at very top of body')
            if not delivery_only:
                record(SHA(body) == SHA((ROOT / path).read_bytes()) and REVISION in text,
                       path + ': deployed HTML is the exact reviewed generated page')
            for href in sorted(set(parser.resources)):
                if href.startswith('#'):
                    record(href[1:] in parser.ids, path + ': in-page anchor resolves: ' + href)
                    continue
                if urlsplit(href).scheme or href.startswith('//'):
                    continue  # official external links were reviewed separately
                resolved = urljoin(path, href)
                try:
                    data, _, _ = get(resolved)
                    record(bool(data), path + ': HTTP internal resource resolves: ' + href)
                except Exception as ex:
                    record(False, path + ': broken internal resource ' + href + ': ' + str(ex))
        if base.startswith('http://127.0.0.1:'):
            for private in ('.git/HEAD', '.git/config', '.venv/pyvenv.cfg', 'data/raw/labels.tif', 'docs/%2e%2e/.git/HEAD'):
                try:
                    request(urljoin(base, private)); record(False, 'Private path must not be exposed: ' + private)
                except urllib.error.HTTPError as ex:
                    record(ex.code in (403, 404), 'Private path not exposed: ' + private)
    except Exception as ex:
        record(False, 'HTTP verification aborted: ' + str(ex))
    failures = [c for c in checks if not c['pass']]
    return {'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'base_url': base, 'mode': 'DELIVERY_ONLY_NO_DEPLOYMENT_VERSION_ASSERTION' if delivery_only else 'FULL_SITE_DELIVERY',
            'primary_sha256': m['primary']['sha256'], 'site_revision_expected': REVISION,
            'platform_acceptance_established': False, 'total': len(checks), 'passed': len(checks)-len(failures),
            'failed': len(failures), 'checks': checks, 'all_passed': not failures}


def SHA(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--live', action='store_true'); ap.add_argument('--base-url')
    ap.add_argument('--delivery-only', action='store_true', help='Predeployment bytes check; does NOT assert updated UI is deployed')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.live and args.base_url:
        ap.error('Choose --live OR --base-url')
    server = None
    try:
        if args.live:
            base = LIVE
        elif args.base_url:
            base = args.base_url.rstrip('/') + '/'
        else:
            server = ThreadingHTTPServer(('0.0.0.0', 0), SiteHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}/'
        report = run(base, args.delivery_only)
        out = args.output or ROOT / ('reports/live_delivery.json' if args.live else '.cache/site_http.json')
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=2) + '\n')
        print(f'\n{report["passed"]}/{report["total"]} HTTP checks passed; platform acceptance NOT inferred.')
        return 0 if report['all_passed'] else 1
    finally:
        if server:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    raise SystemExit(main())
